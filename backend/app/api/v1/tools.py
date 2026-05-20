"""
VidGo Tools API - Unified API for 6 Core Tools
Based on ARCHITECTURE_FINAL.md specification

Tools:
1. Background Removal - /tools/remove-bg
2. Product Scene - /tools/product-scene
3. AI Try-On - /tools/try-on
4. Room Redesign - /tools/room-redesign
5. Short Video - /tools/short-video
6. AI Avatar - /tools/avatar (NEW: Photo-to-Avatar with lip sync)
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
import json as _json
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
import asyncio
import uuid
import tempfile
from pathlib import Path
from PIL import Image, ImageOps
import httpx
from io import BytesIO

from app.services.effects_service import VIDGO_STYLES, get_style_by_id, get_style_prompt
from app.services.rescue_service import get_rescue_service
from app.providers.provider_router import get_provider_router, TaskType
from app.core.config import get_settings
from app.core.upload_validation import (
    AVATAR_HEADSHOT_DIMENSION_RULES,
    COMMON_IMAGE_DIMENSION_RULES,
    IMAGE_TO_VIDEO_DIMENSION_RULES,
    PRODUCT_SCENE_IMAGE_DIMENSION_RULES,
    ROOM_REDESIGN_IMAGE_DIMENSION_RULES,
    TRY_ON_GARMENT_IMAGE_DIMENSION_RULES,
    TRY_ON_MODEL_IMAGE_DIMENSION_RULES,
    validate_image_url_dimensions_or_raise,
    validate_media_url_or_raise,
)
# Voice data still sourced from a2e_service module for compatibility
try:
    from app.services.a2e_service import A2E_VOICES
except ImportError:
    A2E_VOICES = {"en": [], "zh-TW": []}
from app.api.deps import get_current_user_optional, get_current_user, get_db, get_redis, is_subscribed_user, get_user_plan_features
from app.models.user_generation import UserGeneration
from app.models.material import Material, ToolType, MaterialSource, MaterialStatus
from app.services.credit_service import CreditService
from app.services.demo_cache_service import DemoCacheService
from app.services.gcs_storage_service import get_gcs_storage
from app.services.email_service import send_admin_tool_failure_email
from app.services.prompt_refinement_service import get_prompt_refinement_service
from app.services.prompt_library import lookup_prompt as _lookup_curated_prompt
import logging
import os
import hashlib

logger = logging.getLogger(__name__)


def _resolve_curated_prompt(
    tool_key: str,
    prompt_id: Optional[str],
    locale: Optional[str],
) -> Optional[str]:
    """Resolve a curated prompt id to canonical EN/ZH text.

    Returns None if prompt_id is not set OR doesn't exist in the library.
    Endpoints should call this at the top, then prefer the returned text
    over any free-form `custom_prompt` / `script` / `prompt` field on the
    request — that way the client cannot smuggle in arbitrary text.
    """
    if not prompt_id:
        return None
    text = _lookup_curated_prompt(tool_key, prompt_id, locale)
    if text is None:
        logger.warning("Unknown prompt_id %r for tool %s — falling back to free-form prompt", prompt_id, tool_key)
    return text
settings = get_settings()

# Generic, user-facing message returned when an internal tool exception occurs.
# The original exception detail is logged and emailed to admins instead.
GENERIC_TOOL_FAILURE_MESSAGE = (
    "This tool is temporarily unavailable. Please try again in a few minutes."
)


def _notify_admin_of_tool_failure(
    tool_name: str,
    exc: BaseException,
    user=None,
    extra_context: Optional[Dict[str, Any]] = None,
) -> None:
    """Schedule an admin alert email without blocking the request."""
    try:
        user_email = getattr(user, "email", None) if user is not None else None
        request_id = uuid.uuid4().hex[:12]
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                send_admin_tool_failure_email(
                    tool_name=tool_name,
                    user_email=user_email,
                    error=exc,
                    request_id=request_id,
                    extra_context=extra_context or {},
                )
            )
        except RuntimeError:
            # No running loop (rare in async endpoints) – best effort, log only.
            logger.error("No running loop to schedule admin alert for %s", tool_name)
    except Exception as alert_exc:  # pragma: no cover - defensive
        logger.error("Failed to schedule admin alert for %s: %s", tool_name, alert_exc)


def _provider_failure_response(
    tool_name: str,
    result: Dict[str, Any],
    user=None,
    user_message: Optional[str] = None,
):
    provider_error = result.get("error") or result.get("message") or "Provider returned success=false"
    logger.error("%s provider failure: %s", tool_name, provider_error)
    _notify_admin_of_tool_failure(
        tool_name,
        RuntimeError(str(provider_error)),
        user,
        extra_context={"provider_result": result},
    )
    return ToolResponse(success=False, message=user_message or GENERIC_TOOL_FAILURE_MESSAGE)


async def _persist_provider_url(
    url: Optional[str],
    media_type: str,
    user,
) -> Optional[str]:
    """Persist a provider-returned (PiAPI / Pollo CDN) URL to GCS so it
    survives past the upstream's 14-day expiry. Returns the original URL on
    failure (14-day grace from CDN). See GCSStorageService.safe_persist_url."""
    user_id = str(user.id) if user is not None and getattr(user, "id", None) else None
    return await get_gcs_storage().safe_persist_url(url, media_type, user_id)


def _stream_with_heartbeat(worker_coro_factory):
    """Wrap a long-running JSON-returning coroutine in a chunked streaming
    response that emits a single space every 25 seconds while the work runs.

    Why: Cloud Run can keep a request alive for 1 hour, but every proxy in
    between (Cloudflare free tier in particular at ~100 s, and GCLB backend
    services at their configured idle timeout) will close an idle connection
    long before our slowest providers (Kling Avatar with F5-TTS fallback,
    Veo, Wan 14B) finish. As long as bytes flow regularly, the proxies hold
    the connection open. The leading whitespace is parsed cleanly by
    ``JSON.parse`` and by httpx's ``response.json()`` on the client side
    because the JSON spec allows insignificant whitespace before the value.

    Args:
        worker_coro_factory: zero-arg callable that returns the coroutine to
            run. We accept a factory rather than a coroutine so we can start
            the worker inside the generator (avoids the "coroutine was never
            awaited" warning when the client disconnects early).
    """

    async def _gen():
        queue: asyncio.Queue = asyncio.Queue()
        sentinel_done = object()

        async def _heartbeat():
            try:
                while True:
                    await asyncio.sleep(25)
                    await queue.put(b" ")
            except asyncio.CancelledError:
                return

        async def _worker():
            try:
                result = await worker_coro_factory()
                payload = result if isinstance(result, (bytes, bytearray)) else _json.dumps(
                    result, default=str
                ).encode("utf-8")
                await queue.put(payload)
            except HTTPException as exc:
                # Preserve validation/auth errors as JSON so the client gets
                # the same shape it would have without streaming. We can't
                # change the HTTP status mid-stream (headers are flushed
                # with 200 the moment we start writing) so we encode the
                # status into the JSON body and let the caller branch on
                # ``success: false``.
                detail = exc.detail if isinstance(exc.detail, (str, int, float, bool)) else _json.dumps(exc.detail)
                await queue.put(
                    _json.dumps(
                        {"success": False, "message": str(detail), "status_code": exc.status_code}
                    ).encode("utf-8")
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("[stream_with_heartbeat] worker failed: %s", exc)
                await queue.put(
                    _json.dumps(
                        {"success": False, "message": GENERIC_TOOL_FAILURE_MESSAGE}
                    ).encode("utf-8")
                )
            finally:
                await queue.put(sentinel_done)

        hb_task = asyncio.create_task(_heartbeat())
        worker_task = asyncio.create_task(_worker())
        try:
            while True:
                chunk = await queue.get()
                if chunk is sentinel_done:
                    break
                yield chunk
        finally:
            hb_task.cancel()
            if not worker_task.done():
                worker_task.cancel()
            try:
                await hb_task
            except Exception:  # noqa: BLE001
                pass

    return StreamingResponse(_gen(), media_type="application/json")


async def _refine_generation_prompt(
    prompt: str,
    tool_name: str,
    prompt_role: str,
    user_prompt: bool = False,
    context: Optional[Dict[str, Any]] = None,
) -> tuple[str, Dict[str, Any]]:
    """Refine a provider prompt with Gemini, falling back to the original text."""
    service = get_prompt_refinement_service()
    result = await service.refine_for_tool(
        prompt=prompt,
        tool_name=tool_name,
        prompt_role=prompt_role,
        user_prompt=user_prompt,
        context=context or {},
    )
    if result.changed:
        logger.info("Gemini refined %s %s", tool_name, prompt_role)
    elif result.error:
        logger.warning("Gemini prompt refinement skipped for %s: %s", tool_name, result.error)
    return result.refined_prompt, result.to_metadata()

PRODUCT_SCENE_MAX_DIMENSION = 1536
PRODUCT_SCENE_CUSTOM_PROMPT_MAX_CHARS = 300
PRODUCT_SCENE_CUSTOM_SCENE_TYPE = "custom"


async def _maybe_recycle_for_demo(
    db: AsyncSession,
    user_gen: UserGeneration,
    tool_type: ToolType,
    topic: str = "_all",
    prompt: str = "",
    input_image_url: str | None = None,
    input_video_url: str | None = None,
    result_image_url: str | None = None,
    result_video_url: str | None = None,
    effect_prompt: str | None = None,
    input_params: dict | None = None,
):
    """
    Flag high-quality subscriber generations as candidates for demo gallery.

    Creates a Material record with status=PENDING and source=USER.
    Admin can later approve/feature these via the admin dashboard,
    providing free, authentic demo content from real SMB use cases.
    """
    # Only recycle if we have a result
    if not result_image_url and not result_video_url:
        return

    try:
        # Check if we already have enough user-sourced materials for this tool+topic
        existing_count = await db.execute(
            select(func.count()).select_from(Material).where(
                Material.tool_type == tool_type,
                Material.topic == topic,
                Material.source == MaterialSource.USER,
            )
        )
        count = existing_count.scalar() or 0
        if count >= 10:  # Cap at 10 pending user materials per tool+topic
            return

        lookup_content = f"{tool_type.value}:{prompt}:{effect_prompt or ''}:{user_gen.id}"
        lookup_hash = hashlib.sha256(lookup_content.encode()).hexdigest()[:64]

        # Check if this hash already exists to avoid unique constraint violation
        existing = await db.execute(
            select(Material.id).where(Material.lookup_hash == lookup_hash)
        )
        if existing.scalar_one_or_none():
            return

        material = Material(
            lookup_hash=lookup_hash,
            tool_type=tool_type,
            topic=topic,
            prompt=prompt,
            effect_prompt=effect_prompt,
            input_image_url=input_image_url,
            input_video_url=input_video_url,
            result_image_url=result_image_url,
            result_video_url=result_video_url,
            result_watermarked_url=result_image_url or result_video_url,
            source=MaterialSource.USER,
            status=MaterialStatus.PENDING,
            is_active=False,
            input_params=input_params or {},
        )
        db.add(material)
        logger.info(f"[Recycle] Flagged user generation for demo review: {tool_type.value}/{topic}")
    except Exception as e:
        # Rollback to clear the failed flush state so caller's commit works
        try:
            await db.rollback()
        except Exception:
            pass
        logger.debug(f"[Recycle] Skip: {e}")


# Static demo URLs for premium tools whose tool_type strings don't map to
# the Material.tool_type enum (and which therefore have no Material rows
# the demo cache could ever find). Each entry is a pre-rendered asset
# generated via backend/scripts/generate_brand_assets.py --set demos and
# uploaded to GCS. Re-running the script regenerates these files at the
# same blob paths, so URLs stay stable.
_PREMIUM_DEMO_FALLBACKS = {
    "image_generation_premium": {
        "result_url": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/premium/demos/premium-image.png",
        "kind": "image",
        "prompt": "Cinematic golden-hour city skyline with dramatic clouds (Premium AI Image demo).",
    },
    # Kling Video — standard tier (tier="default" in the request, used by
    # most non-premium subscribers). Same MP4 as the premium-tier slot
    # because the upstream model is the same family.
    "video_generation_standard": {
        "result_url": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/premium/demos/kling-video.mp4",
        "kind": "video",
        "prompt": "Cinematic ocean waves at sunset (Kling Video demo).",
    },
    "video_generation_premium": {
        "result_url": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/premium/demos/kling-video.mp4",
        "kind": "video",
        "prompt": "Cinematic ocean waves at sunset (Kling Video demo).",
    },
    # video_generation_professional was the Luma tier — removed 2026-05-19.
}


async def _demo_response(
    db: AsyncSession,
    tool_type: str,
    topic: str | None = None,
    cta: str = "Subscribe for custom generation.",
    product_id: str | None = None,
    input_image_url: str | None = None,
    input_video_url: str | None = None,
    effect_prompt: str | None = None,
):
    """Resolve a demo result honoring the user's chosen input + effect.

    Flow:
        1. If the tool_type is one of the premium tiers that aren't backed
           by a Material.tool_type enum (Flux / Kling / Luma), short-circuit
           to a static pre-rendered asset hosted on GCS. The materials
           table has no rows for these tool_types and the
           `_generate_on_demand` switch has no handler for them, so
           without this fallback the call ends in a 503.
        2. Otherwise, check the DB for an existing (tool, effect_or_topic,
           input_url) row via lookup_hash → fall back to generic topic
           match → otherwise run on-demand generation against the user's
           chosen input + effect, cache the result, and return it.
    """
    fallback = _PREMIUM_DEMO_FALLBACKS.get(tool_type)
    if fallback:
        return ToolResponse(
            success=True,
            result_url=fallback["result_url"],
            credits_used=0,
            cached=True,
            is_demo=True,
            demo_input_url=None,
            demo_prompt=fallback["prompt"],
            message=f"This is a demo example. {cta}",
        )

    try:
        redis = await get_redis()
    except Exception:
        redis = None
    demo = await DemoCacheService(db, redis).get_or_generate(
        tool_type,
        topic,
        product_id=product_id,
        input_image_url=input_image_url,
        input_video_url=input_video_url,
        effect_prompt=effect_prompt,
    )
    if not demo:
        raise HTTPException(status_code=503, detail="Demo generation temporarily unavailable. Please try again.")
    return ToolResponse(
        success=True,
        result_url=demo["result_url"],
        credits_used=0,
        cached=True,
        is_demo=True,
        demo_input_url=demo.get("input_image_url"),
        demo_prompt=demo.get("prompt"),
        message=f"This is a demo example. {cta}",
    )

router = APIRouter()


def _resolve_public_url(url: str) -> str:
    """Convert /static/ paths to public URLs so external AI APIs can access them."""
    if not url:
        return url
    if url.startswith("/static/") or url.startswith("/app/static/"):
        static_path = url if url.startswith("/static/") else "/static/" + url[len("/app/static/"):]
        public_base = os.environ.get("PUBLIC_APP_URL", "").rstrip("/")
        if public_base:
            return f"{public_base}{static_path}"
    return url


async def _ensure_public_image_url(url: str, user_id: Optional[str] = None) -> str:
    """Ensure an image URL is fetchable by external providers (PiAPI, Pollo,
    Vertex AI). Frontend uploaders read files via FileReader.readAsDataURL
    and post a ``data:image/...;base64,...`` URL — Qubico/image-toolkit and
    Kling reject data URLs (or silently 500), and Vertex/PIL paths try to
    HTTP GET them. We decode the data URL once on receipt and persist the
    bytes to GCS, then route the resulting public URL to the provider.

    Returns the original URL unchanged for non-data URLs (already public
    HTTPS, or /static/ paths handled by _resolve_public_url).
    """
    if not url:
        return url
    if not url.startswith("data:"):
        return _resolve_public_url(url)

    import base64

    try:
        prefix, payload = url.split(",", 1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Image data URL is malformed.")

    header = prefix.lower()
    if "base64" not in header:
        raise HTTPException(status_code=400, detail="Image data URL must be base64-encoded.")

    mime = "image/png"
    if "image/" in header:
        mime_part = header.split(";", 1)[0]
        if mime_part.startswith("data:"):
            mime = mime_part[len("data:") :] or "image/png"

    try:
        data = base64.b64decode(payload, validate=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Image data URL could not be decoded.") from exc

    ext_by_mime = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/webp": "webp",
        "image/gif": "gif",
    }
    ext = ext_by_mime.get(mime, "png")

    gcs = get_gcs_storage()
    blob_name = f"uploads/{user_id or 'anon'}/{uuid.uuid4().hex[:12]}.{ext}"
    if gcs.enabled:
        try:
            return gcs.upload_public(data=data, blob_name=blob_name, content_type=mime)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[upload] GCS upload failed, falling back to /static/: %s", exc)

    static_dir = Path("/app/static/uploads")
    static_dir.mkdir(parents=True, exist_ok=True)
    local_name = f"{uuid.uuid4().hex[:12]}.{ext}"
    (static_dir / local_name).write_bytes(data)
    return _resolve_public_url(f"/static/uploads/{local_name}")


async def _download_media_to_path(url: str, path: Path) -> None:
    """Download a public URL or copy a local /static/ file into a temp path."""
    resolved_url = _resolve_public_url(url)
    if resolved_url.startswith("/static/"):
        candidates = [Path("/app") / resolved_url.lstrip("/"), Path.cwd() / resolved_url.lstrip("/")]
        for candidate in candidates:
            if candidate.exists():
                path.write_bytes(candidate.read_bytes())
                return
        raise FileNotFoundError(f"Local static file not found: {resolved_url}")

    async with httpx.AsyncClient(timeout=240.0, follow_redirects=True) as client:
        response = await client.get(resolved_url)
        response.raise_for_status()
        path.write_bytes(response.content)


async def _run_ffmpeg_voiceover_mux(video_url: str, audio_url: str, user_id: str) -> str:
    """Combine the dubbed voiceover with the source video while keeping the
    original ambient audio under it. We never truncate the video to the
    voiceover length, and we never drop the original audio entirely — both
    of those produce results that feel broken to the end user.

    Strategy:
      v: keep original video stream verbatim.
      a: amix(generated_voice @ ~1.0, original_audio @ ~0.15) padded to the
         video duration so the dubbed track plays for the full clip.
      If the source video has no audio track, we fall back to using the
      voiceover only, padded to video length.
    """
    with tempfile.TemporaryDirectory(prefix="vidgo-dubbing-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_video = tmp_path / "input_video"
        input_audio = tmp_path / "voiceover"
        output_video = tmp_path / "dubbed.mp4"

        await _download_media_to_path(video_url, input_video)
        await _download_media_to_path(audio_url, input_audio)

        async def run_ffmpeg(args: list[str]) -> tuple[int, str]:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            detail = (stderr or stdout).decode("utf-8", errors="replace")[-1200:]
            return process.returncode, detail

        # Detect whether the source video has any audio track. ffprobe is
        # already installed alongside ffmpeg in the runtime image.
        async def has_audio_stream(path: Path) -> bool:
            probe = await asyncio.create_subprocess_exec(
                "ffprobe", "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=index",
                "-of", "csv=p=0",
                str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await probe.communicate()
            return bool((stdout or b"").strip())

        source_has_audio = await has_audio_stream(input_video)

        if source_has_audio:
            # Mix: dub at 1.0, original at 0.15. apad ensures the dub track
            # extends to the full video length; amix with first input as
            # duration source keeps the mix locked to the dub-leading channel.
            filter_complex = (
                "[1:a]aresample=44100,apad[dub];"
                "[0:a]aresample=44100,volume=0.15[bg];"
                "[dub][bg]amix=inputs=2:duration=longest:dropout_transition=0,"
                "atrim=duration=VIDDUR_PLACEHOLDER,asetpts=PTS-STARTPTS[aout]"
            )
        else:
            filter_complex = (
                "[1:a]aresample=44100,apad,"
                "atrim=duration=VIDDUR_PLACEHOLDER,asetpts=PTS-STARTPTS[aout]"
            )

        # Get video duration so atrim can pin the audio to the visual length.
        async def video_duration(path: Path) -> float:
            probe = await asyncio.create_subprocess_exec(
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await probe.communicate()
            try:
                return float((stdout or b"0").decode("utf-8", errors="ignore").strip() or 0)
            except ValueError:
                return 0.0

        vid_dur = await video_duration(input_video)
        # Fall back: if probe failed, drop the atrim clause entirely.
        if vid_dur > 0.1:
            filter_complex = filter_complex.replace("VIDDUR_PLACEHOLDER", f"{vid_dur:.3f}")
        else:
            filter_complex = filter_complex.replace(
                "atrim=duration=VIDDUR_PLACEHOLDER,asetpts=PTS-STARTPTS", ""
            ).rstrip(",")

        copy_args = [
            "ffmpeg", "-y",
            "-i", str(input_video),
            "-i", str(input_audio),
            "-filter_complex", filter_complex,
            "-map", "0:v:0",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            str(output_video),
        ]
        returncode, detail = await run_ffmpeg(copy_args)

        if returncode != 0 or not output_video.exists():
            reencode_args = [
                "ffmpeg", "-y",
                "-i", str(input_video),
                "-i", str(input_audio),
                "-filter_complex", filter_complex,
                "-map", "0:v:0",
                "-map", "[aout]",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                str(output_video),
            ]
            returncode, detail = await run_ffmpeg(reencode_args)

        if returncode != 0 or not output_video.exists():
            raise RuntimeError(f"ffmpeg dubbing mux failed: {detail}")

        output_bytes = output_video.read_bytes()
        output_id = uuid.uuid4().hex[:12]
        gcs = get_gcs_storage()
        if gcs.enabled:
            return gcs.upload_public(
                data=output_bytes,
                blob_name=f"generated/video/dubbing/{user_id}/{output_id}.mp4",
                content_type="video/mp4",
            )

        output_dir = Path("/app/static/generated")
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"video_dubbing_{output_id}.mp4"
        local_output = output_dir / filename
        local_output.write_bytes(output_bytes)
        public_base = os.environ.get("PUBLIC_APP_URL", "").rstrip("/") or settings.BACKEND_URL.rstrip("/")
        static_path = f"/static/generated/{filename}"
        return f"{public_base}{static_path}" if public_base else static_path


async def _extract_first_frame_to_gcs(video_url: str, user_id: str | None) -> str:
    """Extract the first frame of a video and persist it as a public JPEG.

    Used by video_transform: every V2V provider in the chain (piapi_mcp's
    Wan referenceImage, Pollo, Vertex AI) actually wants a still image — none
    of them accept an MP4 URL — so we hand them a first-frame still and let
    the prompt drive the style.
    """
    with tempfile.TemporaryDirectory(prefix="vidgo-firstframe-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_video = tmp_path / "input_video"
        output_image = tmp_path / "first_frame.jpg"

        await _download_media_to_path(video_url, input_video)

        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y",
            "-i", str(input_video),
            "-frames:v", "1",
            "-q:v", "2",
            str(output_image),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0 or not output_image.exists():
            detail = (stderr or b"").decode("utf-8", errors="replace")[-800:]
            raise RuntimeError(f"ffmpeg first-frame extraction failed: {detail}")

        data = output_image.read_bytes()
        output_id = uuid.uuid4().hex[:12]
        gcs = get_gcs_storage()
        if gcs.enabled:
            user_prefix = user_id or "anon"
            return gcs.upload_public(
                data=data,
                blob_name=f"generated/image/firstframe/{user_prefix}/{output_id}.jpg",
                content_type="image/jpeg",
            )
        output_dir = Path("/app/static/generated")
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"first_frame_{output_id}.jpg"
        local_output = output_dir / filename
        local_output.write_bytes(data)
        public_base = os.environ.get("PUBLIC_APP_URL", "").rstrip("/") or settings.BACKEND_URL.rstrip("/")
        static_path = f"/static/generated/{filename}"
        return f"{public_base}{static_path}" if public_base else static_path


async def _translate_text_for_dubbing(text: str, target_language: str, source_language: str | None = None) -> str:
    """Translate a spoken script with Gemini when available; fall back to source text."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    try:
        from app.services.gemini_service import get_gemini_service
        from google.genai import types

        gemini = get_gemini_service()
        if not getattr(gemini, "api_key", "") and not getattr(gemini, "_use_vertex", False):
            return cleaned

        language_hint = f" from {source_language}" if source_language else ""
        prompt = (
            f"Translate this spoken video script{language_hint} to {target_language}. "
            "Keep it natural for voiceover, preserve names, brands, numbers, and line breaks. "
            "Return only the translated script, no explanations.\n\n"
            f"{cleaned}"
        )
        client = gemini._get_genai_client()
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=getattr(gemini, "model_name", "gemini-2.5-flash"),
            contents=[prompt],
            config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=1200),
        )
        translated = (response.text or "").strip().strip('"')
        return translated or cleaned
    except Exception as exc:
        logger.warning("Video dubbing translation fallback used: %s", exc)
        return cleaned


async def _refund_credits(db: AsyncSession, user, amount: int, service_type: str):
    """Refund credits on operation failure.

    Hardened against a session that may already be in a failed/rolled-back
    state from the caller's primary error path. We snapshot the user
    attributes BEFORE issuing any DB operation so even if the session was
    invalidated (e.g. by a prior StringDataRightTruncationError raising
    PendingRollbackError on the next access) we can still log meaningfully
    and won't crash this finalizer with a secondary 500.
    """
    # Snapshot identity before any await touches the session.
    try:
        user_id_str = str(getattr(user, "id", "unknown"))
        is_super = bool(getattr(user, "is_superuser", False))
        deduction_snapshot = dict(getattr(user, "_last_credit_deduction", None) or {})
    except Exception as snap_exc:  # pragma: no cover - defensive
        logger.error("Refund snapshot failed for %s: %s", service_type, snap_exc)
        return

    try:
        if is_super:
            logger.info(
                "Skipping refund for superuser %s on failed %s; no credits were deducted",
                user_id_str,
                service_type,
            )
            return

        # Ensure the session is usable. If a prior statement failed we MUST
        # rollback before issuing any further DB work or asyncpg will raise
        # InvalidRequestError("This Session's transaction has been rolled back").
        try:
            await db.rollback()
        except Exception:
            # Best effort: if rollback itself fails the underlying connection
            # is unusable; we still want to log and exit cleanly.
            logger.warning("Refund: db.rollback() failed before refund for user %s", user_id_str)
            return

        credit_svc = CreditService(db)
        deduction = deduction_snapshot or {"subscription": amount}

        for credit_type in ("bonus", "subscription", "purchased"):
            bucket_amount = int(deduction.get(credit_type) or 0)
            if bucket_amount <= 0:
                continue
            await credit_svc.add_credits(
                user_id=user_id_str,
                amount=bucket_amount,
                credit_type=credit_type,
                transaction_type="refund",
                description=f"Refund: {service_type} failed",
                metadata={"refund_source": credit_type},
            )
        logger.info(f"Refunded {amount} credits to user {user_id_str} for failed {service_type}")
    except Exception as e:
        logger.error(f"Failed to refund {amount} credits to user {user_id_str}: {e}")


async def _check_plan_feature(
    db: AsyncSession,
    user,
    feature: str,
    feature_label: str = ""
) -> tuple:
    """Check if user's plan allows a specific feature.
    Returns (allowed: bool, error_msg: str | None, plan_features: dict | None)

    Admin (superuser) accounts bypass plan feature checks.
    """
    if getattr(user, "is_superuser", False):
        return True, None, {"plan_name": "admin", feature: True}

    plan_features = await get_user_plan_features(user, db)
    if not plan_features:
        return False, "Subscription required", None
    if not plan_features.get(feature, False):
        plan_name = plan_features.get("plan_name", "current")
        label = feature_label or feature.replace("_", " ")
        return False, f"Your {plan_name} plan does not include {label}. Please upgrade your plan.", plan_features
    return True, None, plan_features


async def _check_plan_resolution(
    db: AsyncSession,
    user,
    requested_resolution: str
) -> tuple:
    """Check if user's plan allows the requested resolution.
    Returns (allowed: bool, error_msg: str | None)

    Admin (superuser) accounts bypass resolution checks.
    """
    if getattr(user, "is_superuser", False):
        return True, None

    plan_features = await get_user_plan_features(user, db)
    if not plan_features:
        return False, "Subscription required"
    resolution_order = {"720p": 0, "1080p": 1, "4k": 2}
    max_res = plan_features.get("max_resolution", "720p")
    max_level = resolution_order.get(max_res, 0)
    req_level = resolution_order.get(requested_resolution, 0)
    if req_level > max_level:
        return False, f"Your {plan_features['plan_name']} plan supports up to {max_res}. Please upgrade for {requested_resolution}."
    return True, None


async def _check_concurrent_limit(db: AsyncSession, user) -> tuple:
    """Check if user has reached concurrent generation limit.
    Returns (ok: bool, error_msg: str | None)"""
    credit_svc = CreditService(db)
    within_limit, error_msg = await credit_svc.check_concurrent_limit(str(user.id))
    if not within_limit:
        return False, error_msg
    return True, None


async def _check_and_deduct_credits(
    db: AsyncSession,
    user,
    amount: int,
    service_type: str,
    redis_client=None
) -> tuple:
    """Check concurrent limit, check credits, and deduct.
    Returns (ok: bool, error_msg: str | None)

    Cost resolution: queries ``ServicePricing`` by ``service_type`` first;
    if a row exists, its ``credit_cost`` overrides the caller-supplied
    ``amount``. This makes the per-endpoint hardcoded CREDIT_COST constants
    a fallback only, so ops can dial deduction weights via DB without a
    redeploy ("deduction firewall"). The caller's ``amount`` is still used
    when no ServicePricing row matches (e.g. service_types not yet seeded).

    Admin (superuser) accounts bypass credit checks — they can use all
    tools without needing credits. A zero-cost transaction is still
    recorded for auditing.
    """
    # Admins bypass credit checks entirely
    if getattr(user, "is_superuser", False):
        return True, None

    # Check concurrent generation limit first
    ok, err = await _check_concurrent_limit(db, user)
    if not ok:
        return False, err

    try:
        from app.services.abuse_prevention_service import AbusePreventionService
        rate_redis = redis_client or await get_redis()
        abuse = AbusePreventionService(rate_redis)
        rate = await abuse.check_generation_user(str(user.id))
        if not rate.allowed:
            return False, rate.message
    except Exception as exc:
        logger.warning("Generation abuse check skipped for user %s: %s", user.id, exc)

    credit_svc = CreditService(db, redis_client)

    # Dynamic deduction config: prefer ServicePricing.credit_cost when seeded.
    # Falling back to the caller's hardcoded amount keeps behavior identical
    # when no row exists, which is critical for endpoints whose service_type
    # has not yet been added to the seed.
    effective_amount = amount
    try:
        pricing = await credit_svc.get_service_pricing(service_type)
        if pricing and pricing.credit_cost is not None:
            effective_amount = int(pricing.credit_cost)
            if effective_amount != amount:
                logger.info(
                    "Credit cost override for %s: hardcoded=%d, ServicePricing=%d",
                    service_type, amount, effective_amount,
                )
    except Exception as exc:
        logger.warning("ServicePricing lookup failed for %s, using hardcoded %d: %s", service_type, amount, exc)

    has_enough = await credit_svc.check_sufficient(str(user.id), effective_amount)
    if not has_enough:
        return False, f"Insufficient credits. Need {effective_amount} credits."
    success, result = await credit_svc.deduct_credits(
        user_id=str(user.id),
        amount=effective_amount,
        service_type=service_type,
    )
    if not success:
        return False, result.get("error", "Credit deduction failed")
    setattr(user, "_last_credit_deduction", result.get("deducted", {}))
    return True, None


# ============================================================================
# Request/Response Models
# ============================================================================

class RemoveBackgroundRequest(BaseModel):
    """Remove background from image (with optional replacement background).

    Three output modes, in priority order:
      1. `background_image_url` set → composite the cutout onto that image
         (the image is auto-resized to match the cutout's aspect ratio).
      2. `background_color` set (hex `#RRGGBB`/`#RGB` or named) → composite
         the cutout onto a solid color canvas.
      3. `output_format` controls the no-replacement modes:
            - `"png"`     → transparent PNG (default)
            - `"white"`   → flatten onto white canvas
            - `"black"`   → flatten onto black canvas
    """
    image_url: str = Field(..., description="Publicly reachable image URL to process.")
    output_format: str = Field("png", description="Output background mode when no replacement is provided: 'png' (transparent), 'white', or 'black'.")
    background_color: Optional[str] = Field(
        None,
        max_length=32,
        description="Optional solid replacement background. Hex (#RRGGBB / #RGB) or a CSS color name (e.g. 'beige', 'navy'). Overrides output_format.",
    )
    background_image_url: Optional[str] = Field(
        None,
        max_length=2048,
        description="Optional replacement background image URL (jpg/png/webp). The cutout is composited on top of this image. Overrides background_color and output_format.",
    )
    ai_background_prompt: Optional[str] = Field(
        None,
        max_length=500,
        description=(
            "Optional natural-language description of a background to generate "
            "with Flux T2I. When provided, the prompt is rendered into a "
            "background image (same aspect ratio as the cutout) and the "
            "transparent product is composited on top. Takes priority over "
            "background_image_url / background_color / output_format."
        ),
    )

    @field_validator("background_color")
    @classmethod
    def _validate_color(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        v = v.strip()
        return v or None


class RemoveBackgroundBatchRequest(BaseModel):
    """Batch remove background"""
    image_urls: List[str] = Field(..., description="List of publicly reachable image URLs to process. Maximum 10 per request.")
    output_format: str = Field("png", description="Output background mode for every image in the batch.")
    background_color: Optional[str] = Field(None, max_length=32, description="Optional solid replacement background; same shape as the single endpoint.")
    background_image_url: Optional[str] = Field(None, max_length=2048, description="Optional replacement background image URL; same shape as the single endpoint.")
    ai_background_prompt: Optional[str] = Field(None, max_length=500, description="Optional Flux T2I prompt to generate a background image; same shape as the single endpoint.")


class ProductSceneRequest(BaseModel):
    """Generate product in new scene"""
    product_image_url: Optional[str] = Field(None, description="Primary product image URL. Use this or image_url.")
    image_url: Optional[str] = Field(None, description="Alias for product_image_url for client compatibility.")
    product_id: Optional[str] = Field(None, description="Optional preset product identifier used to match a cached demo example.")
    scene_type: str = Field(
        "studio",
        max_length=40,
        description="Named preset scene. Valid values: studio, nature, elegant, minimal, lifestyle, urban, seasonal, holiday, spring, valentines, black_friday, christmas, new_year.",
    )
    prompt_id: Optional[str] = Field(
        None,
        description="Curated prompt id from frontend-vue/src/data/prompt_library.json (e.g. 'ps_001'). When set, the server resolves the canonical prompt text and ignores `custom_prompt`.",
    )
    locale: Optional[str] = Field(
        None,
        max_length=10,
        description="UI locale hint (e.g. 'zh-TW', 'en', 'ja'). Used only when prompt_id resolves: zh-* picks the Chinese variant, anything else picks the English variant.",
    )
    custom_prompt: Optional[str] = Field(
        None,
        max_length=PRODUCT_SCENE_CUSTOM_PROMPT_MAX_CHARS,
        description="Optional natural-language scene prompt (legacy free-text path). Ignored when prompt_id is provided.",
    )
    template_id: Optional[str] = Field(
        None,
        description="Optional template identifier. Highest priority override for scene generation; takes precedence over both custom_prompt and scene_type.",
    )
    placement: Optional[str] = Field(
        None,
        pattern="^(center|left|right|foreground|background)$",
        description=(
            "Optional product placement hint within the new scene. One of "
            "'center', 'left', 'right', 'foreground', 'background'. "
            "When set, an explicit positioning clause is appended to the "
            "edit prompt to bias the I2I composition."
        ),
    )

    def get_product_url(self) -> str:
        url = self.product_image_url or self.image_url
        if not url:
            raise ValueError("product_image_url or image_url is required")
        return _resolve_public_url(url)

    @field_validator("scene_type")
    @classmethod
    def normalize_scene_type(cls, value: str) -> str:
        scene_type = (value or "studio").strip()
        return scene_type or "studio"

    @field_validator("custom_prompt")
    @classmethod
    def normalize_custom_prompt(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None


class TryOnRequest(BaseModel):
    """AI Try-On - virtual clothing try-on"""
    garment_image_url: Optional[str] = Field(None, description="Garment image URL to place on the model. Use this or image_url.")
    image_url: Optional[str] = Field(None, description="Alias for garment_image_url for client compatibility.")
    model_image_url: Optional[str] = Field(None, description="Optional explicit model image URL. If omitted, the API falls back to model_id or a preset model.")
    model_id: Optional[str] = Field(None, description="Optional preset model identifier such as female-1 or male-1.")
    angle: str = Field("front", description="Target garment view angle: front, side, or back.")
    background: str = Field("white", description="Requested background for the try-on result: white, transparent, or studio.")
    template_id: Optional[str] = Field(None, description="Optional style template that controls the try-on scene or background.")
    category: str = Field(
        "dress",
        pattern="^(upper_body|lower_body|dress|full_body)$",
        description=(
            "Garment category controlling which input slot Kling uses: "
            "'upper_body' → upper_input, 'lower_body' → lower_input, "
            "'dress' / 'full_body' → dress_input (full-body or dress garment). "
            "Defaults to 'dress' to preserve existing behavior."
        ),
    )

    def get_garment_url(self) -> str:
        url = self.garment_image_url or self.image_url
        if not url:
            raise ValueError("garment_image_url or image_url is required")
        return _resolve_public_url(url)


class RoomRedesignRequest(BaseModel):
    """Room Redesign - transform room style"""
    room_image_url: Optional[str] = Field(None, description="Source room image URL. Use this or image_url.")
    image_url: Optional[str] = Field(None, description="Alias for room_image_url for client compatibility.")
    style: str = Field("modern_minimalist", description="Preset style ID. Look up against INTERIOR_STYLES (space_kind='interior'), EXTERIOR_STYLES (space_kind='exterior'), or COMMERCIAL_STYLES (space_kind='commercial').")
    space_kind: str = Field(
        "interior",
        description="'interior' (default) selects an INTERIOR_STYLES preset; 'exterior' selects an EXTERIOR_STYLES preset (building facades, gardens, storefronts); 'commercial' selects a COMMERCIAL_STYLES preset (restaurant, retail, hotel, office, café, gym).",
    )
    mode: str = Field(
        "redesign",
        pattern="^(redesign|stage)$",
        description="'redesign' (default) restyles an existing furnished room. 'stage' is AI Virtual Staging: takes an empty room photo and furnishes it in the chosen style. The selected style still drives the look; mode controls whether existing furniture is preserved or generated.",
    )
    prompt_id: Optional[str] = Field(
        None,
        description="Curated prompt id from prompt_library.json (e.g. 'rr_001'). When set, server resolves canonical text and ignores `custom_prompt`.",
    )
    locale: Optional[str] = Field(None, max_length=10, description="UI locale hint for prompt_id resolution.")
    custom_prompt: Optional[str] = Field(None, description="Optional detailed redesign instruction (legacy free-text path). Ignored when prompt_id is provided.")
    preserve_structure: bool = Field(True, description="Keep the original room layout and architectural structure while changing the design style.")
    style_strength: float = Field(0.7, ge=0.0, le=1.0, description="Stylization intensity, 0.0 (very faithful to source) to 1.0 (heavily restyled). Default 0.7 favors a clearly noticeable redesign while preserving room layout.")
    # Optional chip-driven modifiers appended to the final prompt.
    # `lighting_tone` adjusts ambience; `material_accent` swaps the
    # dominant surface material. ReRoom-inspired (2026-05-18).
    lighting_tone: Optional[str] = Field(
        None,
        pattern="^(daylight|warm_evening|dramatic_spotlight|golden_hour|moody)$",
        description="Optional lighting-tone modifier appended to the prompt: daylight | warm_evening | dramatic_spotlight | golden_hour | moody.",
    )
    material_accent: Optional[str] = Field(
        None,
        pattern="^(wood|marble|concrete|linen|brass|leather|terrazzo)$",
        description="Optional dominant-material modifier: wood | marble | concrete | linen | brass | leather | terrazzo.",
    )
    variation_count: int = Field(
        1,
        ge=1,
        le=3,
        description="How many distinct renders to return in one call (1-3). When >1 the server fires N parallel calls with light prompt diversification and returns all URLs in `results`. Useful for client-deck workflows.",
    )

    def get_room_url(self) -> str:
        url = self.room_image_url or self.image_url
        if not url:
            raise ValueError("room_image_url or image_url is required")
        return _resolve_public_url(url)


class ShortVideoRequest(BaseModel):
    """Short Video - image to video with optional TTS"""
    image_url: str = Field(..., description="Input image URL used as the starting frame for video generation.")
    motion_strength: int = Field(5, ge=1, le=10, description="Motion intensity from 1 to 10. Higher values produce more camera or object movement.")
    model_id: Optional[str] = Field(
        None,
        description=(
            "Optional video model family. Falls back to Seedance 2.0 Fast (best CP value) "
            "when omitted. Accepted aliases: "
            "'seedance' (default tier, primary), "
            "'kling_omni' / 'kling_v3' (premium — top quality + audio), "
            "'hailuo' / 'minimax' (cheapest + fastest), "
            "'hunyuan' (中文 prompts + dynamic motion), "
            "'wan' (specialty / legacy), "
            "or any pixverse_v4.5 / pixverse_v5 / kling_v1.5 / kling_v2 string. "
            "PiAPI is the primary provider; Pollo is the automatic backup."
        ),
    )
    style: Optional[str] = Field(None, description="Optional visual style or effect hint to steer the motion result.")
    prompt_id: Optional[str] = Field(
        None,
        description="Curated motion prompt id (e.g. 'sv_001'). Server resolves canonical text; supersedes free-form motion prompts.",
    )
    locale: Optional[str] = Field(None, max_length=10, description="UI locale hint for prompt_id resolution.")
    script: Optional[str] = Field(None, description="Optional narration script for text-to-speech voice-over.")
    voice_id: Optional[str] = Field(None, description="Optional voice identifier for TTS narration.")
    negative_prompt: Optional[str] = Field(None, max_length=500, description="Optional things to avoid (e.g. 'extra arms, distorted face'). A product-safety baseline is always applied.")


class ImageTranslateRequest(BaseModel):
    """Translate visible text inside an image while preserving the original layout."""
    image_url: str = Field(..., description="Input image URL that contains visible text to translate.")
    target_language: str = Field("Traditional Chinese", max_length=80, description="Language to translate visible text into.")
    source_language: Optional[str] = Field(None, max_length=80, description="Optional source language hint.")
    instructions: Optional[str] = Field(None, max_length=500, description="Optional layout, brand, or tone instructions.")

    @field_validator("target_language", "source_language", "instructions")
    @classmethod
    def normalize_text_field(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None


class VideoDubbingRequest(BaseModel):
    """Generate translated speech and mux it onto an uploaded video."""
    video_url: str = Field(..., description="Input video URL to localize.")
    target_language: str = Field("Traditional Chinese", max_length=80, description="Target spoken language.")
    source_language: Optional[str] = Field(None, max_length=80, description="Optional source language hint.")
    source_script: Optional[str] = Field(None, max_length=4000, description="Original transcript/script to translate before dubbing.")
    translated_script: Optional[str] = Field(None, max_length=4000, description="Already translated voiceover script. Takes priority over source_script.")
    voice_reference_url: Optional[str] = Field(None, max_length=1000, description="Optional reference voice audio URL for voice cloning.")
    voice_reference_text: Optional[str] = Field(None, max_length=1000, description="Optional transcript for the reference voice audio.")

    @field_validator("target_language", "source_language", "source_script", "translated_script", "voice_reference_url", "voice_reference_text")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class AvatarRequest(BaseModel):
    """AI Avatar - Photo-to-Avatar with lip sync"""
    image_url: str = Field(..., description="Clear frontal headshot URL used to generate the speaking avatar.")
    script: Optional[str] = Field(None, description="Exact speech content. Optional when prompt_id is provided — the server resolves the canonical script text from the curated library.")
    prompt_id: Optional[str] = Field(
        None,
        description="Curated avatar-script id from prompt_library.json (e.g. 'av_001'). Server resolves canonical script and overrides any free-form `script`.",
    )
    locale: Optional[str] = Field(None, max_length=10, description="UI locale hint for prompt_id resolution.")
    language: str = Field("en", description="Speech language code, for example 'en' or 'zh-TW'.")
    voice_id: Optional[str] = Field(None, description="Optional voice identifier. If omitted, the first supported voice for the selected language is used.")
    duration: int = Field(30, ge=1, le=120, description="Target video duration in seconds.")
    aspect_ratio: str = Field("9:16", description="Target video aspect ratio: 9:16, 16:9, or 1:1.")
    resolution: str = Field("720p", description="Output resolution: 720p or 1080p.")


class ToolResponse(BaseModel):
    """Standard tool response"""
    success: bool
    result_url: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    translated_script: Optional[str] = None
    results: Optional[List[Dict]] = None
    credits_used: int = 0
    message: Optional[str] = None
    cached: bool = False
    # Demo before/after pair — set when returning a pre-generated example
    is_demo: bool = False
    demo_input_url: Optional[str] = None   # "before" image from the pre-generated example
    demo_prompt: Optional[str] = None      # prompt used to generate the example
    # 2026-05-18 — image-understanding fusion (see image_understanding_service.py).
    # Set on tools that take BOTH an uploaded image and a text prompt
    # (room redesign, product scene, effects, I2V, avatar). Lets the
    # frontend surface "we see: __" and warn the user when their text
    # prompt was suppressed because it contradicted the image.
    vision_summary: Optional[str] = None
    user_prompt_used: Optional[bool] = None
    prompt_gap_reason: Optional[str] = None


# ============================================================================
# Scene Templates
# ============================================================================

SCENE_TEMPLATES = [
    {"id": "studio", "name": "Studio", "name_zh": "攝影棚", "preview_url": "/static/scenes/studio.jpg",
     "prompt": "product on infinite white cyclorama, three-point studio lighting with 5600K key light at 45 degrees left, fill light at 30 percent, subtle rim light from behind, f/8 aperture 100mm macro lens, sharp focus, soft gradient shadow beneath product, clean commercial e-commerce catalog photography, no people no person no human"},
    {"id": "nature", "name": "Nature", "name_zh": "自然風景", "preview_url": "/static/scenes/nature.jpg",
     "prompt": "product placed on weathered natural stone surface, lush green garden background with soft bokeh, warm golden hour sunlight filtering through leaves, f/2.8 aperture 85mm lens, shallow depth of field, dappled light patterns, organic earthy tones, lifestyle product photography, no people no person no human"},
    {"id": "elegant", "name": "Elegant", "name_zh": "質感場景", "preview_url": "/static/scenes/elegant.jpg",
     "prompt": "product on polished dark stone surface with subtle veining, warm tungsten accent lighting from above, dark moody background with soft amber glow, f/4 aperture 90mm lens, rich deep shadows, hints of brushed brass accents nearby, refined editorial product photography aesthetic, no people no person no human"},
    {"id": "minimal", "name": "Minimal", "name_zh": "極簡風格", "preview_url": "/static/scenes/minimal.jpg",
     "prompt": "product on flat matte white surface, single large softbox overhead creating even diffused light, very subtle shadow, f/11 aperture 50mm lens, perfectly clean negative space, Scandinavian minimalist composition, neutral off-white tones, modern e-commerce flatlay photography, no people no person no human"},
    {"id": "lifestyle", "name": "Lifestyle", "name_zh": "生活情境", "preview_url": "/static/scenes/lifestyle.jpg",
     "prompt": "product casually placed on light oak wooden table in a cozy living room, soft natural window light from the right, linen cloth and ceramic mug as props, shallow depth of field f/2.8 85mm lens, warm neutral color palette, inviting lived-in atmosphere, Instagram lifestyle flat lay photography, no people no person no human"},
    {"id": "urban", "name": "Urban", "name_zh": "都市街景", "preview_url": "/static/scenes/urban.jpg",
     "prompt": "product placed on raw concrete ledge, modern glass and steel architecture blurred in background, overcast even city light, f/4 aperture 50mm lens, desaturated cool grey-blue tones with subtle teal accent, contemporary urban street style product photography, editorial magazine quality, no people no person no human"},
    {"id": "seasonal", "name": "Seasonal", "name_zh": "季節", "preview_url": "/static/scenes/seasonal.jpg",
     "prompt": "product on rustic wooden surface surrounded by scattered autumn maple leaves in amber and crimson, warm low-angle golden afternoon sun, f/3.5 aperture 85mm lens, soft bokeh with warm particles in air, rich warm color grading, seasonal harvest mood, editorial product photography, no people no person no human"},
    {"id": "holiday", "name": "Holiday", "name_zh": "節日", "preview_url": "/static/scenes/holiday.jpg",
     "prompt": "product placed among wrapped gift boxes with satin ribbons, twinkling warm white fairy lights bokeh in background, pine branches and red ornaments as props, warm candlelight tone mixed with soft studio fill, f/2.8 aperture 85mm lens, festive holiday campaign photography aesthetic, no people no person no human"},
    {"id": "spring", "name": "Spring Sale", "name_zh": "春季特賣", "preview_url": "/static/scenes/spring.jpg",
     "prompt": "product on light wooden table surrounded by fresh cherry blossom petals in soft pink, bright spring morning sunlight streaming through window, pastel green and pink color palette, gentle breeze atmosphere, scattered flower buds and new leaves, f/2.8 aperture 85mm lens, fresh spring campaign photography aesthetic, no people no person no human"},
    {"id": "valentines", "name": "Valentine's Day", "name_zh": "情人節", "preview_url": "/static/scenes/valentines.jpg",
     "prompt": "product placed on rose-petal-covered marble surface, romantic red and pink roses surrounding, soft warm candlelight bokeh, heart-shaped decorations and satin ribbons as props, intimate warm lighting with pink hue, f/2.8 aperture 85mm lens, romantic Valentine campaign photography, no people no person no human"},
    {"id": "black_friday", "name": "Black Friday", "name_zh": "黑色星期五", "preview_url": "/static/scenes/black_friday.jpg",
     "prompt": "product on sleek glossy black surface, dramatic spotlight from above, bold neon sale tags and shopping bags in background, high contrast black and gold color scheme, modern retail campaign look, metallic accent reflections, f/4 aperture 50mm lens, premium Black Friday promotional photography, no people no person no human"},
    {"id": "christmas", "name": "Christmas", "name_zh": "聖誕節", "preview_url": "/static/scenes/christmas.jpg",
     "prompt": "product nestled among christmas pine branches with red berries, warm golden fairy lights twinkling in background, red and green gift ribbons, snow frost effect on edges, traditional red and gold christmas ornaments as props, cozy warm white lighting, f/2.8 aperture 85mm lens, magical christmas campaign photography, no people no person no human"},
    {"id": "new_year", "name": "New Year", "name_zh": "新年", "preview_url": "/static/scenes/new_year.jpg",
     "prompt": "product on elegant reflective gold surface, sparkling confetti and streamers in background, champagne glass and clock showing midnight as props, luxurious black and gold color scheme, celebratory firework bokeh lights, festive new year countdown atmosphere, f/2.8 aperture 85mm lens, glamorous New Year campaign photography, no people no person no human"},
]

# Interior design styles for Room Redesign
# IDs must match DESIGN_STYLES keys in interior_design_service.py so demo Material DB lookup works
INTERIOR_STYLES = [
    {"id": "modern_minimalist", "name": "Modern Minimalist", "name_zh": "現代極簡", "preview_url": "/static/interior/modern_minimalist.jpg",
     "prompt": "modern minimalist interior design, clean geometric lines, neutral white and warm grey palette, low-profile furniture with hidden storage, polished concrete or light oak flooring, floor-to-ceiling windows with sheer linen curtains, recessed LED strip lighting, single statement art piece on wall, f/16 architectural lens, photorealistic 3D rendering quality, empty room no people no person no human"},
    {"id": "scandinavian", "name": "Scandinavian", "name_zh": "北歐風格", "preview_url": "/static/interior/scandinavian.jpg",
     "prompt": "Scandinavian hygge interior, pale birch wood furniture with rounded edges, matte white walls, chunky knit wool throw on light grey sofa, woven rug on pale oak herringbone floor, pendant lamp with matte metal detail, potted monstera plant in ceramic planter, soft north-facing window light, warm 3200K accent lighting, cozy functional living, photorealistic interior render, empty room no people no person no human"},
    {"id": "japanese", "name": "Japanese Zen", "name_zh": "日式禪風", "preview_url": "/static/interior/japanese.jpg",
     "prompt": "Japanese wabi-sabi zen interior, tatami mat flooring with shoji paper sliding screens, low natural cypress wood platform furniture, ikebana flower arrangement, tokonoma alcove with hanging scroll, diffused paper lantern lighting, muted earth tones with charcoal and cream, bamboo accent wall, zen rock garden visible through window, serene meditative atmosphere, photorealistic architectural visualization, empty room no people no person no human"},
    {"id": "industrial", "name": "Industrial", "name_zh": "工業風", "preview_url": "/static/interior/industrial.jpg",
     "prompt": "industrial loft interior, exposed red brick walls with original mortar joints, black steel I-beam ceiling with exposed ductwork, polished concrete floor, oversized factory-frame windows with black metal mullions, Edison bulb pendant cluster on twisted cloth cord, worn leather tufted sofa, reclaimed wood and steel pipe shelving, warm tungsten mixed with cool daylight, urban warehouse conversion aesthetic, photorealistic render, empty room no people no person no human"},
    {"id": "bohemian", "name": "Bohemian", "name_zh": "波西米亞", "preview_url": "/static/interior/bohemian.jpg",
     "prompt": "bohemian eclectic interior, layered kilim rugs on terracotta tile floor, macrame wall hanging next to gallery wall of mixed frames, rattan chair with colorful cushions, trailing pothos and fiddle leaf fig plants, woven basket pendant lamps, warm amber string lights draped across ceiling, rich tones of emerald and burnt orange against white walls, artistic maximalist lived-in atmosphere, photorealistic interior photography, empty room no people no person no human"},
    {"id": "mediterranean", "name": "Mediterranean", "name_zh": "地中海風格", "preview_url": "/static/interior/mediterranean.jpg",
     "prompt": "Mediterranean coastal interior, hand-laid terracotta hexagonal floor tiles, whitewashed lime plaster walls with arched doorways, cerulean blue window shutters, wrought iron light fixtures with warm candle-style bulbs, solid wood dining table with linen runner, ceramic hand-painted accent tiles, bougainvillea visible through open window, warm golden afternoon sunlight streaming in, relaxed coastal elegance, photorealistic architectural render, empty room no people no person no human"},
    {"id": "mid_century_modern", "name": "Mid-Century Modern", "name_zh": "中世紀現代", "preview_url": "/static/interior/mid_century_modern.jpg",
     "prompt": "mid-century modern interior circa 1960, classic molded plywood lounge chair with leather cushion, teak credenza with tapered legs, starburst metal chandelier, sunburst wall clock, bold mustard yellow accent wall against warm white, geometric patterned area rug, large picture window with view of greenery, warm afternoon light casting long shadows, retro atomic age style, photorealistic interior photography, empty room no people no person no human"},
    {"id": "coastal", "name": "Coastal", "name_zh": "海岸風格", "preview_url": "/static/interior/coastal.jpg",
     "prompt": "coastal interior, whitewashed shiplap walls, bleached driftwood-finish wide plank flooring, soft navy and crisp white linen upholstery, natural woven seagrass baskets and rattan pendant lights, large sliding glass doors open to ocean view, weathered rope detail accents, shells and sea glass decor on floating shelves, bright airy natural daylight, relaxed seaside living, photorealistic interior render, empty room no people no person no human"},
    {"id": "farmhouse", "name": "Farmhouse", "name_zh": "農舍風格", "preview_url": "/static/interior/farmhouse.jpg",
     "prompt": "modern farmhouse interior, reclaimed barn wood accent wall with original nail holes, white subway tile kitchen backsplash with dark grout, apron-front farmhouse sink, open shelving with mason jars and stoneware, black matte hardware on cream Shaker cabinets, wrought iron chandelier with warm Edison bulbs, woven runner on wide plank pine floor, warm morning light through multi-pane windows, cozy country charm, photorealistic interior photography, empty room no people no person no human"},
    {"id": "art_deco", "name": "Art Deco", "name_zh": "裝飾藝術", "preview_url": "/static/interior/art_deco.jpg",
     "prompt": "Art Deco style interior, geometric chevron patterned stone floor in black and white, deep green tufted sofa with metallic nailhead trim, sunburst mirror with decorative frame, fluted column details, lacquered black console table with brass inlay, glass display cabinet with vintage decanters, dramatic uplighting on fluted wall panels, rich jewel tones with mirror accents, 1920s inspired geometric sophistication, photorealistic architectural visualization, empty room no people no person no human"},
    # 2026-05-18 ReRoom-inspired style expansion — adds 8 categories the
    # competitor highlights heavily on tw.reroom.ai. Same prompt grammar
    # as the existing 10 entries so the demo / curated-prompt pipeline
    # treats them uniformly.
    {"id": "japandi", "name": "Japandi", "name_zh": "日式北歐",
     "prompt": "Japandi interior blending Japanese wabi-sabi with Scandinavian warmth, pale ash wood and warm white palette, low-profile linen sofa, hand-thrown ceramic vessels on floating walnut shelf, paper lantern pendant, single bonsai on raw-edge bench, generous negative space, soft north-facing window light, photorealistic architectural render, empty room no people no person no human"},
    {"id": "wabi_sabi", "name": "Wabi-Sabi", "name_zh": "侘寂",
     "prompt": "wabi-sabi interior, hand-troweled lime plaster walls in dusty taupe, cracked stoneware urn with dried branches, hand-loomed natural linen drapery, weathered oak plank flooring, a single tatami corner, candle-warm ambient light, monochrome earthy palette, photorealistic interior photography, empty room no people no person no human"},
    {"id": "contemporary_luxury", "name": "Contemporary Luxury", "name_zh": "當代奢華",
     "prompt": "contemporary luxury interior, book-matched Calacatta marble feature wall with bronze veining, deep velvet emerald sofa with brass legs, sculptural alabaster pendant chandelier, fluted oak feature wall, full-height windows with floor-pooling drapery, dramatic warm uplighting, refined editorial aesthetic, photorealistic architectural rendering, empty room no people no person no human"},
    {"id": "hollywood_regency", "name": "Hollywood Regency", "name_zh": "好萊塢攝政",
     "prompt": "Hollywood Regency interior, glossy black lacquered cabinetry with gold leaf accents, mirrored console with crystal lamp, blush velvet tufted sofa, oversized starburst mirror, animal print accent pillow, palm fronds in brass urn, dramatic statement chandelier, theatrical jewel-toned palette, photorealistic interior photography, empty room no people no person no human"},
    {"id": "retro_70s", "name": "1970s Lounge", "name_zh": "1970 復古",
     "prompt": "1970s retro lounge interior, burnt orange and mustard yellow modular sectional, shag area rug, dark walnut paneling on accent wall, brass arc floor lamp, smoked glass coffee table, macrame wall art, bold geometric wallpaper, warm amber tungsten lighting, vintage cocktail bar vibe, photorealistic interior render, empty room no people no person no human"},
    {"id": "spanish_revival", "name": "Spanish Revival", "name_zh": "西班牙復興",
     "prompt": "Spanish Revival interior, hand-painted talavera tile floor, lime-washed ivory plaster walls with arched doorway, dark wrought iron pendant chandelier, exposed wood ceiling beams with carved corbels, terracotta accents and serape textile drape over leather club chair, warm Andalusian afternoon light, photorealistic architectural visualization, empty room no people no person no human"},
    {"id": "desert_modern", "name": "Desert Modern", "name_zh": "沙漠現代",
     "prompt": "desert modern interior, warm white plaster walls, sun-bleached oak floors, low-slung sand-toned linen sofa, saguaro and barrel cactus in matte black planters, terracotta and rust accent textiles, Palm-Springs-inspired butterfly chair, golden hour sunlight raking across walls, calm minimalist Southwestern aesthetic, photorealistic interior render, empty room no people no person no human"},
    {"id": "cyberpunk_loft", "name": "Cyberpunk Loft", "name_zh": "賽博龐克 Loft",
     "prompt": "cyberpunk loft interior, dark concrete walls with magenta and cyan neon LED accents, glossy black modular sofa, holographic pendant fixtures, exposed cable trays, floor-to-ceiling rain-slicked window overlooking neon cityscape, deep navy and electric pink palette, atmospheric haze, photorealistic dystopian architectural render, empty room no people no person no human"},
]

# 2026-05-18 — Commercial / hospitality space catalog (ReRoom-inspired).
# Exposed when the request carries `space_kind="commercial"`. Each prompt
# describes a complete commercial environment the model can stage from a
# bare interior photo (or transform an existing one). Same "no people"
# guard as the other catalogs — every render is for a marketing
# proposal / property-listing context where stray figures are bugs.
COMMERCIAL_STYLES = [
    {"id": "restaurant_bistro", "name": "Bistro Restaurant", "name_zh": "小酒館餐廳",
     "prompt": "modern bistro restaurant interior, warm dark wood tables and bentwood chairs, marble bar with brass railing, vintage Edison bulb pendant cluster, exposed brick accent wall with framed menu chalkboards, warm amber tungsten lighting, intimate inviting dining atmosphere, photorealistic commercial interior render, no people no person no human"},
    {"id": "retail_boutique", "name": "Retail Boutique", "name_zh": "精品零售店",
     "prompt": "premium retail boutique interior, polished concrete floor, white minimalist display walls with floating brass shelves, single-rack brass clothing rail, sculptural mannequins in window, soft warm museum-quality track lighting, cream and warm white palette with brass accents, refined editorial commercial space, photorealistic interior photography, no products no people no person no human"},
    {"id": "hotel_lobby", "name": "Hotel Lobby", "name_zh": "飯店大廳",
     "prompt": "boutique hotel lobby interior, double-height ceiling with sculptural brass chandelier, polished marble floor with herringbone wood inlay, velvet sectional sofa in deep emerald, walnut concierge desk, oversized abstract painting, warm layered ambient lighting, sophisticated hospitality atmosphere, photorealistic architectural render, no people no person no human"},
    {"id": "modern_office", "name": "Modern Office", "name_zh": "現代辦公室",
     "prompt": "modern open-plan office interior, light oak workstations with cable management, ergonomic mesh chairs, acoustic felt ceiling baffles, glass-walled meeting rooms with biophilic plant accents, full-height windows with motorized shades, neutral grey and warm wood palette, productive professional atmosphere, photorealistic commercial interior visualization, empty no people no person no human"},
    {"id": "cafe_warm", "name": "Cozy Café", "name_zh": "溫馨咖啡館",
     "prompt": "cozy specialty coffee café interior, exposed brick wall with chalkboard menu, reclaimed wood counter with copper espresso machine, mix of bentwood chairs and leather banquette seating, warm Edison filament pendants, hanging trailing plants from beam, warm cream and chocolate brown palette, inviting third-place atmosphere, photorealistic commercial interior render, no people no person no human"},
    {"id": "gym_studio", "name": "Boutique Gym", "name_zh": "精品健身房",
     "prompt": "boutique fitness studio interior, polished black rubber gym flooring, mirrored accent wall, exposed black ductwork on white-painted ceiling, branded LED accent strip lighting, sculptural mid-grey weight bench, statement neon wall sign, energetic but premium athletic atmosphere, photorealistic commercial interior visualization, empty no people no person no human"},
]

# Building exterior catalog — exposed under the same /room-redesign
# endpoint when the request carries `space_kind="exterior"`. Mirrors
# INTERIOR_STYLES in shape so the frontend can switch catalogs without
# changing call sites. Prompts encode "no people" because every render
# is for a marketing/proposal context where stray figures are bugs.
EXTERIOR_STYLES = [
    {"id": "modern_glass_facade", "name": "Modern Glass Facade", "name_zh": "現代玻璃帷幕", "preview_url": "/static/exterior/modern_glass_facade.jpg",
     "prompt": "modern architectural exterior with floor-to-ceiling glass curtain wall, slim black aluminum mullions, polished concrete entry plaza, accent landscape lighting at dusk, photorealistic architectural visualization, no people no person no human"},
    {"id": "scandi_wood_house", "name": "Nordic Wood House", "name_zh": "北歐木屋", "preview_url": "/static/exterior/scandi_wood_house.jpg",
     "prompt": "Nordic timber-clad two-storey house exterior, vertical pine cladding stained black, gable roof, large picture windows with white trim, snowy ground with soft natural daylight, photorealistic architectural rendering, no people no person no human"},
    {"id": "japanese_zen_courtyard", "name": "Japanese Courtyard", "name_zh": "日式合院", "preview_url": "/static/exterior/japanese_zen_courtyard.jpg",
     "prompt": "Japanese contemporary house exterior with cypress wood lattice, white plaster walls, low pitched dark tile roof, raked gravel zen garden in foreground, soft morning light, photorealistic architectural rendering, no people no person no human"},
    {"id": "mediterranean_villa", "name": "Mediterranean Villa", "name_zh": "地中海別墅", "preview_url": "/static/exterior/mediterranean_villa.jpg",
     "prompt": "Mediterranean villa exterior with whitewashed lime plaster walls, blue wooden shutters, terracotta barrel-tile roof, climbing bougainvillea over arched entry, golden hour sunlight, photorealistic architectural visualization, no people no person no human"},
    {"id": "industrial_loft_facade", "name": "Industrial Loft", "name_zh": "工業 Loft 外觀", "preview_url": "/static/exterior/industrial_loft_facade.jpg",
     "prompt": "industrial loft exterior with exposed red brick, large black steel-framed factory windows, rooftop terrace with planter boxes, urban warehouse conversion, overcast even lighting, photorealistic architectural render, no people no person no human"},
    {"id": "tropical_resort", "name": "Tropical Resort", "name_zh": "熱帶度假", "preview_url": "/static/exterior/tropical_resort.jpg",
     "prompt": "tropical resort villa exterior, white stucco walls with teak wood accents, infinity pool reflecting palm trees, thatched accent canopy, vibrant garden landscaping, late afternoon sun, photorealistic architectural visualization, no people no person no human"},
    {"id": "midcentury_ranch", "name": "Mid-Century Ranch", "name_zh": "中世紀美式平房", "preview_url": "/static/exterior/midcentury_ranch.jpg",
     "prompt": "mid-century modern ranch house exterior, low-pitched gable roof, exposed wood beams, butterfly carport, warm timber siding with stone accents, manicured lawn, dusk lighting, photorealistic architectural render, no people no person no human"},
    {"id": "urban_townhouse", "name": "Urban Townhouse", "name_zh": "都會聯排別墅", "preview_url": "/static/exterior/urban_townhouse.jpg",
     "prompt": "contemporary urban townhouse facade, dark grey fiber cement panel cladding mixed with timber accents, recessed entry with planter, soft side-light, photorealistic architectural visualization, no people no person no human"},
    {"id": "rustic_stone_cabin", "name": "Rustic Stone Cabin", "name_zh": "鄉村石屋", "preview_url": "/static/exterior/rustic_stone_cabin.jpg",
     "prompt": "rustic stone cabin exterior with thick fieldstone walls, cedar shake roof, large stone chimney, woodland clearing setting, warm afternoon light through trees, photorealistic architectural render, no people no person no human"},
    {"id": "commercial_storefront", "name": "Boutique Storefront", "name_zh": "精品店面", "preview_url": "/static/exterior/commercial_storefront.jpg",
     "prompt": "boutique retail storefront exterior, minimalist black metal facade with floor-to-ceiling glass shopfront, illuminated brand signage, polished concrete sidewalk, evening ambient lighting, photorealistic architectural rendering, no people no person no human, no text on signage"},
    {"id": "warehouse_loft_exterior", "name": "Warehouse Loft Conversion", "name_zh": "倉庫改建外觀", "preview_url": "/static/exterior/warehouse_loft_exterior.jpg",
     "prompt": "converted warehouse loft exterior, restored brick facade, large multi-pane steel windows, contemporary rooftop addition with green planted terrace, mixed-use urban context, soft daylight, photorealistic architectural render, no people no person no human"},
    {"id": "garden_studio", "name": "Garden Studio", "name_zh": "花園工作室", "preview_url": "/static/exterior/garden_studio.jpg",
     "prompt": "small backyard studio cabin exterior, charred timber siding (yakisugi), single sliding glass door, surrounded by ornamental grasses, gravel walkway, golden hour, photorealistic architectural visualization, no people no person no human"},
]

# Preset models for Try-On (IDs match frontend: "female-1", "male-1" etc.)
TRYON_MODELS = {
    # Legacy gender-prefixed IDs — kept as aliases for backwards compat
    # with any old client / cached frontend.
    "female-1": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/female-1.png",
    "female-2": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/female-2.png",
    "female-3": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/female-3.png",
    "male-1": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/male-1.png",
    "male-2": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/male-2.png",
    "male-3": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/male-3.png",
    # New named IDs the frontend modelOptions list uses (avery/sam/...).
    # Each maps to the same physical PNG as one of the legacy IDs, but
    # also points at standalone files so re-runs of the brand-asset
    # script overwrite a stable URL per name.
    "avery":   "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/avery.png",
    "sam":     "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/sam.png",
    "taylor":  "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/taylor.png",
    "kendall": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/kendall.png",
    "jordan":  "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/jordan.png",
    "casey":   "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/casey.png",
    "alex":    "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/alex.png",
    "maya":    "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/maya.png",
    "reece":   "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/reece.png",
    "lena":    "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/lena.png",
    "julia":   "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/julia.png",
}

# TTS Voices
TTS_VOICES = [
    {"id": "female_zh", "name": "Chinese Female", "name_zh": "中文女聲", "language": "zh-TW", "gender": "female"},
    {"id": "male_zh", "name": "Chinese Male", "name_zh": "中文男聲", "language": "zh-TW", "gender": "male"},
    {"id": "female_en", "name": "English Female", "name_zh": "英文女聲", "language": "en-US", "gender": "female"},
    {"id": "male_en", "name": "English Male", "name_zh": "英文男聲", "language": "en-US", "gender": "male"},
    {"id": "taigi", "name": "Taiwanese", "name_zh": "台語", "language": "nan-TW", "gender": "neutral"},
]


# ============================================================================
# Tool listing
# ============================================================================

AVAILABLE_TOOLS = [
    {"id": "background_removal", "name": "Smart Background Removal", "name_zh": "智能去背", "endpoint": "/tools/remove-bg", "method": "POST",
     "description": "Remove background from product images with AI"},
    {"id": "product_scene", "name": "AI Product Scene Studio", "name_zh": "AI 商品情境攝影棚", "endpoint": "/tools/product-scene", "method": "POST",
     "description": "Place products in professional AI-generated scenes with cinematic lighting"},
    {"id": "try_on", "name": "AI Model Try-On", "name_zh": "AI 模特換裝", "endpoint": "/tools/try-on", "method": "POST",
     "description": "Virtual try-on with AI models for clothing showcases"},
    {"id": "room_redesign", "name": "Interior Render & Proposal Studio", "name_zh": "室內設計渲染與提案工具", "endpoint": "/tools/room-redesign", "method": "POST",
     "description": "Transform room photos, empty spaces, sketches, or plans into proposal-ready photorealistic interior renders"},
    {"id": "short_video", "name": "Product Dynamic Video (I2V)", "name_zh": "商品動態短影音（圖生影片）", "endpoint": "/tools/short-video", "method": "POST",
     "description": "Turn product images into dynamic short videos for ads"},
    {"id": "hd_upscale", "name": "Commercial HD Upscale", "name_zh": "商用無損放大", "endpoint": "/tools/upscale", "method": "POST",
     "description": "Upscale images to 4K for e-commerce and print"},
    {"id": "ai_avatar", "name": "AI Avatar", "name_zh": "AI 數位人", "endpoint": "/tools/avatar", "method": "POST",
     "description": "Create avatar videos with lip-sync narration"},
]


@router.get("/list")
async def list_tools():
    """List all available VidGo AI tools with their endpoints and descriptions."""
    return {"tools": AVAILABLE_TOOLS, "total": len(AVAILABLE_TOOLS)}


# ============================================================================
# Tool 1: Background Removal
# ============================================================================

async def _flatten_to_white_background(image_url: str, user_id) -> Optional[str]:
    """Backwards-compat wrapper. New callers should use _composite_cutout_on_background."""
    return await _composite_cutout_on_background(image_url, user_id, color=(255, 255, 255))


def _parse_color(value: str) -> Optional[tuple[int, int, int]]:
    """Parse a hex (`#RRGGBB`, `#RGB`) or named CSS color into an RGB tuple.

    Falls back to PIL's ImageColor for the named-color path so we get the
    full CSS palette (beige, navy, slategray, etc.) without maintaining our
    own dictionary. Returns None if the input is malformed.
    """
    if not value:
        return None
    v = value.strip()
    try:
        from PIL import ImageColor
        rgb = ImageColor.getrgb(v)  # raises ValueError on bad input
        # ImageColor may return RGBA — drop alpha for the canvas fill.
        return (rgb[0], rgb[1], rgb[2])
    except Exception:
        logger.warning("_parse_color: rejected color %r", v)
        return None


async def _composite_cutout_on_background(
    cutout_url: str,
    user_id,
    *,
    color: Optional[tuple[int, int, int]] = None,
    background_image_url: Optional[str] = None,
) -> Optional[str]:
    """Composite a transparent cutout onto a replacement background.

    Exactly one of `color` or `background_image_url` should be supplied.
    The replacement background image is auto-resized + cropped (cover) to
    match the cutout's dimensions so the result has no letterboxing. The
    composite is uploaded as JPEG at 92% quality. Returns the new URL,
    or None on any failure (caller falls back to the transparent PNG).
    """
    from io import BytesIO

    # Download the cutout (transparent PNG from BG-removal upstream).
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(cutout_url)
            resp.raise_for_status()
            cutout_bytes = resp.content
    except Exception as fetch_err:
        logger.warning("composite: failed to download cutout %s: %s", cutout_url, fetch_err)
        return None

    cutout = Image.open(BytesIO(cutout_bytes))
    if cutout.mode != "RGBA":
        cutout = cutout.convert("RGBA")
    width, height = cutout.size

    # Build the replacement canvas.
    if background_image_url:
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                bg_resp = await client.get(background_image_url)
                bg_resp.raise_for_status()
                bg_bytes = bg_resp.content
        except Exception as bg_err:
            logger.warning("composite: failed to download replacement bg %s: %s", background_image_url, bg_err)
            return None
        try:
            bg = Image.open(BytesIO(bg_bytes)).convert("RGB")
        except Exception as bg_open_err:
            logger.warning("composite: replacement bg not a valid image: %s", bg_open_err)
            return None
        # Cover-fit: scale so the bg covers the cutout dimensions, then center-crop.
        bw, bh = bg.size
        scale = max(width / bw, height / bh)
        new_w, new_h = int(bw * scale + 0.5), int(bh * scale + 0.5)
        bg = bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - width) // 2
        top = (new_h - height) // 2
        canvas = bg.crop((left, top, left + width, top + height))
    elif color is not None:
        canvas = Image.new("RGB", (width, height), color)
    else:
        canvas = Image.new("RGB", (width, height), (255, 255, 255))

    canvas.paste(cutout, mask=cutout.split()[-1])
    buf = BytesIO()
    canvas.save(buf, format="JPEG", quality=92)
    out_bytes = buf.getvalue()

    file_id = uuid.uuid4().hex[:12]
    blob_name = f"generated/image/bg_replace/{user_id}/{file_id}.jpg"
    gcs = get_gcs_storage()
    if getattr(gcs, "enabled", False):
        return gcs.upload_public(data=out_bytes, blob_name=blob_name, content_type="image/jpeg")
    output_dir = Path("/app/static/generated")
    output_dir.mkdir(parents=True, exist_ok=True)
    local_path = output_dir / f"bg_replace_{file_id}.jpg"
    local_path.write_bytes(out_bytes)
    return f"/static/generated/{local_path.name}"


@router.post("/remove-bg", response_model=ToolResponse)
async def remove_background(
    request: RemoveBackgroundRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional)
):
    """
    Remove background from product image.
    Returns transparent PNG or white background.

    USER TIER LOGIC:
    - Demo users: Return pre-generated result from Material DB
    - Subscribers: Real-time background removal + save to UserGeneration

    Credits: 3 per image
    """
    validate_media_url_or_raise(str(request.image_url), "image", "Background removal input")
    await validate_image_url_dimensions_or_raise(str(request.image_url), COMMON_IMAGE_DIMENSION_RULES)
    request.image_url = await _ensure_public_image_url(
        str(request.image_url),
        user_id=str(current_user.id) if current_user else None,
    )

    # ========== DEMO USER: Return cached demo example ==========
    if not is_subscribed_user(current_user):
        return await _demo_response(
            db,
            ToolType.BACKGROUND_REMOVAL,
            cta="Subscribe to process your own images.",
            input_image_url=_resolve_public_url(str(request.image_url)) if request.image_url else None,
        )

    # ========== SUBSCRIBER: Real-time Generation ==========
    CREDIT_COST = 3
    ok, err = await _check_and_deduct_credits(db, current_user, CREDIT_COST, "background_removal")
    if not ok:
        return ToolResponse(success=False, message=err)

    try:
        provider_router = get_provider_router()
        result = await provider_router.route(
            TaskType.BACKGROUND_REMOVAL,
            {"image_url": _resolve_public_url(str(request.image_url))}
        )

        if result.get("success"):
            output = result.get("output", {})
            result_url = output.get("image_url")
            # Persist PiAPI CDN result to GCS so it survives 14-day expiry.
            result_url = await _persist_provider_url(result_url, "image", current_user)

            # Replacement background: priority is ai_prompt > image > color >
            # output_format. Each path falls back to the transparent PNG on
            # failure so the user always gets a usable result.
            replacement_done = False

            # AI text-to-background — generate a scene image via Flux T2I,
            # then composite the cutout on top. Uses the same provider
            # chain (TaskType.T2I) the rest of the app already trusts.
            if result_url and request.ai_background_prompt:
                try:
                    bg_result = await provider_router.route(
                        TaskType.T2I,
                        {
                            "prompt": request.ai_background_prompt,
                            # Background scenes look best landscape — 4:3 is a
                            # good neutral that crops to most product shots.
                            "size": "1152*864",
                        },
                    )
                    bg_url = (bg_result.get("output") or {}).get("image_url") if bg_result.get("success") else None
                    bg_url = await _persist_provider_url(bg_url, "image", current_user) if bg_url else None
                    if bg_url:
                        replaced = await _composite_cutout_on_background(
                            result_url, current_user.id,
                            background_image_url=bg_url,
                        )
                        if replaced:
                            result_url = replaced
                            replacement_done = True
                except Exception as bg_err:
                    logger.warning("background_removal: ai-background composite failed: %s", bg_err)

            if not replacement_done and result_url and request.background_image_url:
                try:
                    replaced = await _composite_cutout_on_background(
                        result_url, current_user.id,
                        background_image_url=str(request.background_image_url),
                    )
                    if replaced:
                        result_url = replaced
                        replacement_done = True
                except Exception as bg_err:
                    logger.warning("background_removal: bg-image composite failed: %s", bg_err)

            if not replacement_done and result_url and request.background_color:
                color_rgb = _parse_color(request.background_color)
                if color_rgb is not None:
                    try:
                        replaced = await _composite_cutout_on_background(
                            result_url, current_user.id, color=color_rgb,
                        )
                        if replaced:
                            result_url = replaced
                            replacement_done = True
                    except Exception as bg_err:
                        logger.warning("background_removal: bg-color composite failed: %s", bg_err)

            # output_format="white" / "black" — only honored when no
            # explicit replacement was supplied.
            if not replacement_done and result_url:
                fmt = (request.output_format or "png").lower()
                if fmt in ("white", "black"):
                    color_rgb = (255, 255, 255) if fmt == "white" else (0, 0, 0)
                    try:
                        flattened = await _composite_cutout_on_background(
                            result_url, current_user.id, color=color_rgb,
                        )
                        if flattened:
                            result_url = flattened
                    except Exception as flatten_err:  # pragma: no cover - defensive
                        logger.warning(
                            "background_removal: %s-flatten post-process failed: %s",
                            fmt, flatten_err,
                        )

            # Save to UserGeneration
            user_gen = UserGeneration(
                user_id=current_user.id,
                tool_type=ToolType.BACKGROUND_REMOVAL,
                input_image_url=str(request.image_url),
                input_params={
                    "output_format": request.output_format,
                    "background_color": request.background_color,
                    "background_image_url": request.background_image_url,
                    "ai_background_prompt": request.ai_background_prompt,
                },
                result_image_url=result_url,
                credits_used=CREDIT_COST,
            )
            user_gen.set_expiry()
            db.add(user_gen)

            # Recycle for demo gallery (admin review required)
            await _maybe_recycle_for_demo(
                db, user_gen, ToolType.BACKGROUND_REMOVAL,
                topic="product", prompt="User background removal",
                input_image_url=str(request.image_url),
                result_image_url=result_url,
            )

            await db.commit()

            return ToolResponse(
                success=True,
                result_url=result_url,
                credits_used=3,
                message="Background removed successfully"
            )
        else:
            await _refund_credits(db, current_user, CREDIT_COST, "background_removal")
            return _provider_failure_response("background_removal", result, current_user)
    except Exception as e:
        logger.error(f"Background removal error: {e}", exc_info=True)
        await _refund_credits(db, current_user, CREDIT_COST, "background_removal")
        _notify_admin_of_tool_failure("background_removal", e, current_user)
        return ToolResponse(
            success=False,
            message=GENERIC_TOOL_FAILURE_MESSAGE,
        )


@router.post("/remove-bg/batch", response_model=ToolResponse)
async def remove_background_batch(
    request: RemoveBackgroundBatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Batch remove background from multiple images.
    Maximum 10 images per request.

    Credits: 3 per image (requires authenticated user)
    """
    if len(request.image_urls) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 images per batch")

    for image_url in request.image_urls:
        validate_media_url_or_raise(str(image_url), "image", "Batch background removal input")
        await validate_image_url_dimensions_or_raise(str(image_url), COMMON_IMAGE_DIMENSION_RULES)

    # Check plan-level batch processing permission
    allowed, err, _ = await _check_plan_feature(db, current_user, "batch_processing", "batch processing")
    if not allowed:
        raise HTTPException(status_code=403, detail=err)

    total_cost = len(request.image_urls) * 3
    if not getattr(current_user, "is_superuser", False):
        credit_service = CreditService(db)
        balance = await credit_service.get_balance(str(current_user.id))
        if balance["total"] < total_cost:
            raise HTTPException(status_code=403, detail=f"Insufficient credits. Need {total_cost}, have {balance['total']}")

    results = []
    credits_used = 0
    provider_router = get_provider_router()

    # If the caller asked for an AI-generated scene, render it once and
    # reuse the same background image across the whole batch (saves
    # money and keeps the set visually consistent).
    shared_ai_background: Optional[str] = None
    if request.ai_background_prompt:
        try:
            bg_result = await provider_router.route(
                TaskType.T2I,
                {"prompt": request.ai_background_prompt, "size": "1152*864"},
            )
            bg_url = (bg_result.get("output") or {}).get("image_url") if bg_result.get("success") else None
            shared_ai_background = await _persist_provider_url(bg_url, "image", current_user) if bg_url else None
        except Exception as bg_err:
            logger.warning("background_removal[batch]: ai-background generation failed: %s", bg_err)

    color_rgb = _parse_color(request.background_color) if request.background_color else None
    flatten_color = None
    if (request.output_format or "").lower() in ("white", "black"):
        flatten_color = (255, 255, 255) if request.output_format.lower() == "white" else (0, 0, 0)

    for image_url in request.image_urls:
        try:
            # Use provider router for background removal (PiAPI)
            result = await provider_router.route(
                TaskType.BACKGROUND_REMOVAL,
                {"image_url": str(image_url)}
            )
            if result.get("success"):
                output = result.get("output", {})
                cutout_url = output.get("image_url")
                cutout_url = await _persist_provider_url(cutout_url, "image", current_user)

                # Apply the same priority chain as the single endpoint.
                bg_choice = shared_ai_background or request.background_image_url
                if cutout_url and bg_choice:
                    try:
                        composed = await _composite_cutout_on_background(
                            cutout_url, current_user.id,
                            background_image_url=str(bg_choice),
                        )
                        if composed:
                            cutout_url = composed
                    except Exception as bg_err:
                        logger.warning("background_removal[batch]: image composite failed: %s", bg_err)
                elif cutout_url and color_rgb is not None:
                    try:
                        composed = await _composite_cutout_on_background(
                            cutout_url, current_user.id, color=color_rgb,
                        )
                        if composed:
                            cutout_url = composed
                    except Exception as bg_err:
                        logger.warning("background_removal[batch]: color composite failed: %s", bg_err)
                elif cutout_url and flatten_color is not None:
                    try:
                        composed = await _composite_cutout_on_background(
                            cutout_url, current_user.id, color=flatten_color,
                        )
                        if composed:
                            cutout_url = composed
                    except Exception as bg_err:
                        logger.warning("background_removal[batch]: flatten failed: %s", bg_err)

                results.append({
                    "input_url": str(image_url),
                    "result_url": cutout_url,
                    "success": True
                })
                if not getattr(current_user, "is_superuser", False):
                    credits_used += 3
            else:
                results.append({
                    "input_url": str(image_url),
                    "success": False,
                    "error": result.get("error", "Failed")
                })
        except Exception as e:
            results.append({
                "input_url": str(image_url),
                "success": False,
                "error": str(e)
            })

    return ToolResponse(
        success=True,
        results=results,
        credits_used=credits_used,
        message=f"Processed {len(results)} images"
    )


# ============================================================================
# Tool 2: Product Scene
# ============================================================================

@router.post("/product-scene", response_model=ToolResponse)
async def generate_product_scene(
    request: ProductSceneRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional)
):
    """
    Generate product in a professional scene/background.

    USER TIER LOGIC:
    - Demo users: Return pre-generated result from Material DB (with watermark)
    - Subscribers: Real-time I2I generation (no watermark, can download)

    3-Step I2I Process (for subscribers):
    1. Remove background from product image (rembg)
    2. Generate scene background (T2I)
    3. Composite product onto scene (PIL)

    Scene prompt priority: template_id > custom scene prompt > preset scene_type
    Scene types: studio, nature, elegant, minimal, lifestyle, urban, seasonal, holiday, spring, valentines, black_friday, christmas, new_year, custom
    Credits: 10 per generation
    """
    try:
        product_media_url = request.get_product_url()
    except ValueError:
        product_media_url = None
    if product_media_url:
        validate_media_url_or_raise(product_media_url, "image", "Product scene input")
        await validate_image_url_dimensions_or_raise(product_media_url, PRODUCT_SCENE_IMAGE_DIMENSION_RULES)
        promoted = await _ensure_public_image_url(
            product_media_url,
            user_id=str(current_user.id) if current_user else None,
        )
        if request.product_image_url:
            request.product_image_url = promoted
        if request.image_url:
            request.image_url = promoted

    # Resolve curated prompt server-side: when prompt_id is supplied, use the
    # canonical text from prompt_library.json and switch to scene_type=custom
    # so the existing custom-scene code path handles it. The client cannot
    # smuggle arbitrary text via custom_prompt when prompt_id is present.
    curated = _resolve_curated_prompt("product_scene", request.prompt_id, request.locale)
    if curated:
        request.custom_prompt = curated
        request.scene_type = PRODUCT_SCENE_CUSTOM_SCENE_TYPE
        request.template_id = None

    valid_scene_ids = {scene["id"] for scene in SCENE_TEMPLATES}
    valid_scene_options = ", ".join(scene["id"] for scene in SCENE_TEMPLATES)
    if request.scene_type not in valid_scene_ids and request.scene_type != PRODUCT_SCENE_CUSTOM_SCENE_TYPE:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scene_type '{request.scene_type}'. Valid options: {valid_scene_options}, or '{PRODUCT_SCENE_CUSTOM_SCENE_TYPE}' with custom_prompt.",
        )

    if request.custom_prompt and request.scene_type != PRODUCT_SCENE_CUSTOM_SCENE_TYPE and not request.template_id:
        raise HTTPException(
            status_code=400,
            detail="custom_prompt is only allowed when scene_type is 'custom'. Choose a preset scene without custom_prompt or set scene_type to 'custom'.",
        )

    # Resolve scene prompt — template_id takes priority, then custom_prompt, then scene_type
    scene_prompt: Optional[str] = None
    if request.template_id:
        from app.services.template_prompt_service import resolve_template_prompt
        scene_prompt = await resolve_template_prompt(db, request.template_id)
        if not scene_prompt:
            raise HTTPException(status_code=400, detail="Template not found or inactive.")

    if not scene_prompt:
        if request.custom_prompt:
            scene_prompt = request.custom_prompt
        else:
            scene = next((s for s in SCENE_TEMPLATES if s["id"] == request.scene_type), None)
            if not scene:
                raise HTTPException(
                    status_code=400,
                    detail="Custom scene requires custom_prompt or template_id.",
                )
            scene_prompt = scene["prompt"]

    if not is_subscribed_user(current_user) and (
        request.scene_type == PRODUCT_SCENE_CUSTOM_SCENE_TYPE or request.custom_prompt or request.template_id
    ):
        raise HTTPException(
            status_code=403,
            detail="A subscription is required to use custom Product Scene prompts or templates.",
        )

    if request.scene_type == PRODUCT_SCENE_CUSTOM_SCENE_TYPE and not scene_prompt:
        raise HTTPException(
            status_code=400,
            detail="Custom scene requires custom_prompt or template_id.",
        )

    if request.scene_type == PRODUCT_SCENE_CUSTOM_SCENE_TYPE and not request.custom_prompt and not request.template_id:
        raise HTTPException(
            status_code=400,
            detail="Custom scene requires custom_prompt or template_id.",
        )

    # ========== DEMO USER: Return cached demo example ==========
    if not is_subscribed_user(current_user):
        user_product_url = None
        try:
            user_product_url = str(request.get_product_url())
        except ValueError:
            user_product_url = None
        return await _demo_response(
            db,
            ToolType.PRODUCT_SCENE,
            topic=request.scene_type,
            product_id=request.product_id,
            cta="Subscribe to generate custom scenes.",
            input_image_url=user_product_url,
            effect_prompt=scene_prompt,
        )

    # ========== SUBSCRIBER: Real-time I2I Generation ==========
    CREDIT_COST = 10
    ok, err = await _check_and_deduct_credits(db, current_user, CREDIT_COST, "product_scene")
    if not ok:
        return ToolResponse(success=False, message=err)

    logger.info(f"Subscriber: Starting 3-step I2I generation for {request.product_image_url}")

    # 2026-05-18 — image-understanding fusion runs only when the user
    # supplied a custom prompt. Catalog scene prompts are vetted and
    # don't need realignment. Fail-open on any Gemini error.
    fusion = None
    if request.custom_prompt and request.custom_prompt.strip():
        try:
            from app.services.image_understanding_service import (
                get_image_understanding_service,
            )

            fusion = await get_image_understanding_service().describe_and_fuse(
                image_url=str(request.get_product_url()),
                user_prompt=request.custom_prompt,
                tool_context=f"product_scene:{request.scene_type}",
                language="zh-TW",
            )
            if fusion.fused_prompt:
                scene_prompt = fusion.fused_prompt
        except Exception as _exc:
            logger.warning("product_scene fusion failed: %s", _exc)

    try:
        provider_router = get_provider_router()
        product_url = str(request.get_product_url())
        # Build a Kontext-style edit instruction. Kontext is a true I2I edit
        # model that keeps the source product (shape, label, color, perspective)
        # and rewrites only the surrounding scene. This replaces the previous
        # 3-step rembg → T2I scene → PIL paste pipeline, which often produced
        # results where the product was missing, distorted, or inconsistently
        # lit because the new background was generated independently from the
        # product photo.
        placement_map = {
            "center": " Position the product in the center of the frame.",
            "left": " Position the product on the left third of the frame.",
            "right": " Position the product on the right third of the frame.",
            "foreground": " Position the product prominently in the foreground.",
            "background": " Place the product slightly back in the scene with the surrounding scene more dominant.",
        }
        placement_clause = placement_map.get(request.placement or "", "")
        base_full_prompt = (
            "PRESERVE PRODUCT IDENTITY: do not alter the product's silhouette, "
            "label position, brand colors, packaging shape, material reflectance, "
            "logos, or any printed text. Composite the product unchanged into "
            "the new scene as if photographed in place. "
            f"Place THIS exact product, preserving every label, shape, color, "
            f"material, proportion, and perspective, into the following scene: "
            f"{scene_prompt}.{placement_clause} "
            f"Photorealistic commercial product photography, "
            f"natural studio-quality lighting that matches the new scene, "
            f"realistic shadow and contact ground reflection under the product, "
            f"high resolution, sharp focus, no extra products, no extra text, "
            f"no logos other than what is already on the product, no people. "
            "Negative: do not redesign, recolor, restyle, or replace the "
            "product; do not modify packaging artwork or text; do not crop "
            "the product."
        )
        full_prompt, prompt_refinement = await _refine_generation_prompt(
            base_full_prompt,
            "product_scene",
            "image-to-image product placement prompt",
            user_prompt=bool(request.custom_prompt or request.template_id),
            context={"scene_type": request.scene_type, "template_id": request.template_id},
        )

        # Single-step I2I edit (Flux Kontext via PiAPI). Kontext takes the
        # product image as visual context and emits a new image where the
        # product is preserved and only the background scene is rewritten.
        logger.info("Kontext I2I: editing product into scene...")
        i2i_params = {
            "image_url": product_url,
            "prompt": full_prompt,
            "model": "flux_kontext",
            "width": 1024,
            "height": 768,
        }
        i2i_result = await provider_router.route(TaskType.I2I, i2i_params)

        result_url: Optional[str] = None
        composite_fallback_used = False
        if i2i_result.get("success"):
            output = i2i_result.get("output") or {}
            result_url = (
                output.get("image_url")
                or i2i_result.get("image_url")
                or i2i_result.get("output_url")
            )

        # Defensive fallback: if Kontext is rate-limited or the active plan
        # does not include it, fall back to the legacy 3-step composite so the
        # subscriber still gets a deliverable instead of a refund spiral.
        if not result_url:
            logger.warning(
                "Kontext I2I unavailable (%s) — falling back to legacy "
                "rembg + T2I + composite pipeline.",
                i2i_result.get("error"),
            )
            composite_fallback_used = True

            # Step 1: Remove background
            rembg_result = await provider_router.route(
                TaskType.BACKGROUND_REMOVAL,
                {"image_url": product_url}
            )
            if not rembg_result.get("success"):
                raise Exception(f"Background removal failed: {rembg_result.get('error')}")

            product_no_bg_url = rembg_result["output"]["image_url"]

            # Step 2: Generate scene background
            scene_only_prompt = (
                f"{scene_prompt}, scene background only with clear open area for "
                "product compositing, no product or object in center, "
                "photorealistic high-resolution commercial photography"
            )
            scene_prompt_refined, _ = await _refine_generation_prompt(
                scene_only_prompt,
                "product_scene",
                "scene background prompt",
                user_prompt=bool(request.custom_prompt or request.template_id),
                context={"scene_type": request.scene_type, "template_id": request.template_id},
            )
            t2i_result = await provider_router.route(
                TaskType.T2I,
                {"prompt": scene_prompt_refined}
            )
            if not t2i_result.get("success"):
                raise Exception(f"Scene generation failed: {t2i_result.get('error')}")

            scene_url = t2i_result["output"]["image_url"]

            # Step 3: Composite
            composite_result = await _composite_product_scene(product_no_bg_url, scene_url)
            if not composite_result.get("success"):
                raise Exception(f"Product compositing failed: {composite_result.get('error')}")

            result_url = composite_result["image_url"]

        # Persist provider CDN result to GCS so it survives 14-day expiry.
        result_url = await _persist_provider_url(result_url, "image", current_user)

        # Save to UserGeneration
        user_gen = UserGeneration(
            user_id=current_user.id,
            tool_type=ToolType.PRODUCT_SCENE,
            input_image_url=str(request.get_product_url()),
            input_params={
                "scene_type": request.scene_type,
                "custom_prompt": request.custom_prompt,
                "placement": request.placement,
                "prompt_refinement": prompt_refinement,
                "pipeline": "composite_fallback" if composite_fallback_used else "kontext_i2i",
            },
            input_text=full_prompt,
            result_image_url=result_url,
            credits_used=10,
        )
        user_gen.set_expiry()
        db.add(user_gen)

        # Recycle for demo gallery
        await _maybe_recycle_for_demo(
            db, user_gen, ToolType.PRODUCT_SCENE,
            topic=request.scene_type or "studio",
            prompt=full_prompt,
            input_image_url=str(request.get_product_url()),
            result_image_url=result_url,
            input_params={"scene_type": request.scene_type, "prompt_refinement": prompt_refinement},
        )

        await db.commit()

        return ToolResponse(
            success=True,
            result_url=result_url,
            credits_used=10,
            message="Product scene generated successfully (subscriber)",
            vision_summary=(fusion.image_summary or None) if fusion else None,
            user_prompt_used=(fusion.used_user_prompt if fusion else None),
            prompt_gap_reason=(fusion.gap_reason if fusion else None),
        )

    except Exception as e:
        logger.error(f"Product scene error: {e}", exc_info=True)
        await _refund_credits(db, current_user, CREDIT_COST, "product_scene")
        _notify_admin_of_tool_failure("product_scene", e, current_user)
        return ToolResponse(
            success=False,
            message=GENERIC_TOOL_FAILURE_MESSAGE,
        )


async def _composite_product_scene(product_no_bg_url: str, scene_url: str) -> dict:
    """
    Composite a transparent product image onto a scene background.

    Args:
        product_no_bg_url: URL/path to product image with transparent background
        scene_url: URL/path to scene background image

    Returns:
        {"success": True, "image_url": str} or {"success": False, "error": str}
    """
    try:
        def _prepare_image(source: Image.Image, mode: str) -> Image.Image:
            prepared = ImageOps.exif_transpose(source)
            if max(prepared.size) > PRODUCT_SCENE_MAX_DIMENSION:
                prepared.thumbnail(
                    (PRODUCT_SCENE_MAX_DIMENSION, PRODUCT_SCENE_MAX_DIMENSION),
                    Image.Resampling.LANCZOS,
                )
            return prepared.convert(mode)

        async def _load_image(url: str, mode: str) -> Image.Image:
            if url.startswith("/static") or url.startswith("static"):
                local_path = Path("/app") / url.lstrip("/")
                with Image.open(local_path) as source:
                    return _prepare_image(source, mode)

            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
            with Image.open(BytesIO(response.content)) as source:
                return _prepare_image(source, mode)

        product_img = await _load_image(product_no_bg_url, "RGBA")
        scene_img = await _load_image(scene_url, "RGB")
        product_resized: Image.Image | None = None
        upload_buffer: BytesIO | None = None

        # Resize product to fit nicely in scene (60% of scene width, centered)
        scene_w, scene_h = scene_img.size
        target_w = int(scene_w * 0.6)

        prod_w, prod_h = product_img.size
        scale = target_w / prod_w
        new_w = target_w
        new_h = int(prod_h * scale)

        # Ensure product doesn't exceed scene height
        if new_h > scene_h * 0.8:
            scale = (scene_h * 0.8) / prod_h
            new_h = int(prod_h * scale)
            new_w = int(prod_w * scale)

        product_resized = product_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Center product on scene
        x_offset = (scene_w - new_w) // 2
        y_offset = (scene_h - new_h) // 2

        # Composite onto the RGB scene using the product alpha channel.
        scene_img.paste(product_resized, (x_offset, y_offset), product_resized)

        filename = f"product_scene_{uuid.uuid4().hex[:8]}.png"
        from app.services.gcs_storage_service import get_gcs_storage
        gcs = get_gcs_storage()
        if gcs.enabled:
            upload_buffer = BytesIO()
            scene_img.save(upload_buffer, "PNG", optimize=True)
            upload_buffer.seek(0)
            result_url = gcs.upload_public(
                data=upload_buffer.getvalue(),
                blob_name=f"generated/image/{filename}",
                content_type="image/png",
            )
        else:
            output_dir = Path("/app/static/generated")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / filename
            scene_img.save(output_path, "PNG", optimize=True)
            result_url = f"/static/generated/{filename}"

        logger.info(f"[Composite] Saved: {result_url}")
        return {"success": True, "image_url": result_url}

    except Exception as e:
        logger.error(f"[Composite] Error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if upload_buffer is not None:
            upload_buffer.close()
        if product_resized is not None:
            product_resized.close()
        if 'product_img' in locals():
            product_img.close()
        if 'scene_img' in locals():
            scene_img.close()


# ============================================================================
# Tool 3: AI Try-On
# ============================================================================

@router.post("/try-on", response_model=ToolResponse)
async def ai_try_on(
    request: TryOnRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional)
):
    """
    Virtual try-on - place garment on model.

    USER TIER LOGIC:
    - Demo users: Return pre-generated result from Material DB
    - Subscribers: Real-time try-on generation + save to UserGeneration

    Credits: 15 per generation
    """
    try:
        garment_media_url = request.get_garment_url()
    except ValueError:
        garment_media_url = None
    if garment_media_url:
        validate_media_url_or_raise(garment_media_url, "image", "Try-on garment input")
        await validate_image_url_dimensions_or_raise(garment_media_url, TRY_ON_GARMENT_IMAGE_DIMENSION_RULES)
        promoted_garment = await _ensure_public_image_url(
            garment_media_url,
            user_id=str(current_user.id) if current_user else None,
        )
        if request.garment_image_url:
            request.garment_image_url = promoted_garment
        if request.image_url:
            request.image_url = promoted_garment
    if request.model_image_url:
        validate_media_url_or_raise(str(request.model_image_url), "image", "Try-on model input")
        await validate_image_url_dimensions_or_raise(str(request.model_image_url), TRY_ON_MODEL_IMAGE_DIMENSION_RULES)
        request.model_image_url = await _ensure_public_image_url(
            str(request.model_image_url),
            user_id=str(current_user.id) if current_user else None,
        )

    # ========== DEMO USER: Return cached demo example ==========
    if not is_subscribed_user(current_user):
        try:
            user_garment = str(request.get_garment_url())
        except ValueError:
            user_garment = None
        return await _demo_response(
            db,
            ToolType.TRY_ON,
            cta="Subscribe to try on your own garments.",
            product_id=request.model_id,
            input_image_url=user_garment,
        )

    # ========== SUBSCRIBER: Real-time Generation ==========
    CREDIT_COST = 15
    ok, err = await _check_and_deduct_credits(db, current_user, CREDIT_COST, "virtual_try_on")
    if not ok:
        return ToolResponse(success=False, message=err)

    logger.info(f"Subscriber: Starting real-time Try-On")

    try:
        garment_url = request.get_garment_url()

        # Auto-fix garment image URL if too small (Kling AI requires >= 512px)
        # For URLs with width param (Unsplash, CDN), request larger image
        import re
        w_match = re.search(r'[?&]w=(\d+)', garment_url)
        if w_match and int(w_match.group(1)) < 512:
            garment_url = re.sub(r'([?&])w=\d+', r'\g<1>w=768', garment_url)
            logger.info(f"  Adjusted garment URL width to 768px")
        elif w_match is None:
            # For URLs without width param, check actual image dimensions
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    img_resp = await client.get(garment_url)
                    if img_resp.status_code == 200:
                        img = Image.open(BytesIO(img_resp.content))
                        w, h = img.size
                        if w < 512 or h < 512:
                            logger.warning(f"  Garment image is {w}x{h}, Kling AI requires >= 512px. Upscaling...")
                            scale = max(512 / w, 512 / h)
                            new_w, new_h = int(w * scale), int(h * scale)
                            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                            # VG-BUG-007 fix: upload to GCS (not ephemeral
                            # /app/static/generated/) so PiAPI can fetch it
                            # reliably even when a different Cloud Run instance
                            # handles its subsequent GET.
                            from app.services.gcs_storage_service import get_gcs_storage
                            gcs = get_gcs_storage()
                            upscale_name = f"tryon_upscaled_{uuid.uuid4().hex[:8]}.jpg"
                            if gcs.enabled:
                                buf = BytesIO()
                                img.convert("RGB").save(buf, "JPEG", quality=90)
                                buf.seek(0)
                                garment_url = gcs.upload_public(
                                    data=buf.getvalue(),
                                    blob_name=f"generated/image/{upscale_name}",
                                    content_type="image/jpeg",
                                )
                                logger.info(f"  Upscaled garment to {new_w}x{new_h}, uploaded to GCS: {garment_url[:80]}")
                            else:
                                upscale_dir = Path("/app/static/generated")
                                upscale_dir.mkdir(parents=True, exist_ok=True)
                                upscale_path = upscale_dir / upscale_name
                                img.convert("RGB").save(upscale_path, "JPEG", quality=90)
                                public_base = os.environ.get("PUBLIC_APP_URL", "").rstrip("/")
                                garment_url = f"{public_base}/static/generated/{upscale_name}" if public_base else f"/static/generated/{upscale_name}"
                                logger.info(f"  Upscaled garment to {new_w}x{new_h} (ephemeral path, GCS disabled)")
            except Exception as e:
                logger.warning(f"  Garment size check skipped: {e}")

        # Determine model image URL — must be public URL (Kling rejects base64)
        model_url = None
        if request.model_image_url:
            model_url = _resolve_public_url(str(request.model_image_url))
        elif request.model_id:
            model_url = TRYON_MODELS.get(request.model_id)
            if not model_url:
                await _refund_credits(db, current_user, CREDIT_COST, "virtual_try_on")
                return ToolResponse(success=False, message=f"Unknown model_id: {request.model_id}")

        # Route via PIAPI Client directly for specialized Try-On
        from scripts.services.piapi_client import PiAPIClient
        piapi = PiAPIClient(api_key=os.getenv("PIAPI_KEY", ""))

        # Map category → which Kling input slot to use.
        # PiAPIClient.virtual_try_on() accepts dress_input (full body) or
        # upper_input / lower_input. The category field on the request lets
        # the caller pick the slot; "dress"/"full_body" send a single garment
        # via dress_input, while "upper_body"/"lower_body" send via the
        # corresponding split slot.
        tryon_kwargs: Dict[str, Any] = {"model_image_url": model_url}
        if request.category == "upper_body":
            tryon_kwargs["garment_image_url"] = ""
            tryon_kwargs["upper_garment_url"] = garment_url
        elif request.category == "lower_body":
            tryon_kwargs["garment_image_url"] = ""
            tryon_kwargs["lower_garment_url"] = garment_url
        else:
            tryon_kwargs["garment_image_url"] = garment_url

        result = await piapi.virtual_try_on(**tryon_kwargs)

        if not result.get("success"):
             # Fallback to T2I? No, Try-On is specific.
             raise Exception(result.get("error", "Try-on failed"))

        # Extract result URL
        result_url = result.get("image_url") or result.get("output", {}).get("image_url")
        if not result_url:
             # Check list output
              images = result.get("output", {}).get("images", [])
              if images:
                   result_url = images[0].get("url") if isinstance(images[0], dict) else images[0]

        if not result_url:
             raise Exception("No result URL returned from Try-On service")

        # Persist PiAPI CDN result to GCS so it survives 14-day expiry.
        result_url = await _persist_provider_url(result_url, "image", current_user)

        # Save to UserGeneration
        user_gen = UserGeneration(
            user_id=current_user.id,
            tool_type=ToolType.TRY_ON,
            input_image_url=str(request.get_garment_url()),
            input_params={
                "model_id": request.model_id,
                "model_image_url": str(request.model_image_url) if request.model_image_url else None,
                "angle": request.angle,
                "category": request.category,
            },
            result_image_url=result_url,
            credits_used=15,
        )
        user_gen.set_expiry()
        db.add(user_gen)

        # Recycle for demo gallery
        await _maybe_recycle_for_demo(
            db, user_gen, ToolType.TRY_ON,
            topic="casual", prompt="User try-on",
            input_image_url=str(request.get_garment_url()),
            result_image_url=result_url,
            input_params={"model_id": request.model_id},
        )

        await db.commit()

        return ToolResponse(
            success=True,
            result_url=result_url,
            credits_used=15,
            message="Virtual try-on successful"
        )

    except Exception as e:
        logger.error(f"Try-On error: {e}", exc_info=True)
        await _refund_credits(db, current_user, CREDIT_COST, "virtual_try_on")
        _notify_admin_of_tool_failure("try_on", e, current_user)
        return ToolResponse(
            success=False,
            message=GENERIC_TOOL_FAILURE_MESSAGE,
        )



# ============================================================================
# Tool 4: Room Redesign
# ============================================================================

@router.post("/room-redesign", response_model=ToolResponse)
async def room_redesign(
    request: RoomRedesignRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional)
):
    """
    Transform room interior style.

    USER TIER LOGIC:
    - Demo users: Return pre-generated result from Material DB
    - Subscribers: Real-time interior design + save to UserGeneration

    Styles: modern, nordic, japanese, industrial, minimalist, luxury, bohemian, coastal
    Credits: 20 per generation
    """
    try:
        room_media_url = request.get_room_url()
    except ValueError:
        room_media_url = None
    if room_media_url:
        validate_media_url_or_raise(room_media_url, "image", "Room redesign input")
        await validate_image_url_dimensions_or_raise(room_media_url, ROOM_REDESIGN_IMAGE_DIMENSION_RULES)
        promoted_room = await _ensure_public_image_url(
            room_media_url,
            user_id=str(current_user.id) if current_user else None,
        )
        if request.room_image_url:
            request.room_image_url = promoted_room
        if request.image_url:
            request.image_url = promoted_room

    # Resolve curated prompt — overrides any free-form custom_prompt.
    curated = _resolve_curated_prompt("room_redesign", request.prompt_id, request.locale)
    if curated:
        request.custom_prompt = curated

    # Pick the right catalog. `space_kind` defaults to 'interior' so old
    # clients keep working; 'exterior' → EXTERIOR_STYLES, 'commercial'
    # → COMMERCIAL_STYLES (restaurant / retail / hotel / office / café / gym).
    if request.space_kind == "exterior":
        _catalog = EXTERIOR_STYLES
    elif request.space_kind == "commercial":
        _catalog = COMMERCIAL_STYLES
    else:
        _catalog = INTERIOR_STYLES

    # ========== DEMO USER: Return cached demo example ==========
    if not is_subscribed_user(current_user):
        try:
            user_room = str(request.get_room_url())
        except ValueError:
            user_room = None
        interior_match = next((s for s in _catalog if s["id"] == request.style), None)
        room_effect_prompt = request.custom_prompt or (interior_match["prompt"] if interior_match else None)
        return await _demo_response(
            db,
            ToolType.ROOM_REDESIGN,
            topic=request.style,
            cta="Subscribe to redesign your own rooms.",
            input_image_url=user_room,
            effect_prompt=room_effect_prompt,
        )

    # ========== SUBSCRIBER: Real-time Generation ==========
    CREDIT_COST = 20
    ok, err = await _check_and_deduct_credits(db, current_user, CREDIT_COST, "room_redesign")
    if not ok:
        return ToolResponse(success=False, message=err)

    interior = next((s for s in _catalog if s["id"] == request.style), None)
    if not interior:
        interior = _catalog[0]

    # 2026-05-18 — image-understanding fusion runs only when the user
    # supplied custom text. Curated catalog prompts are already vetted
    # and don't need realignment. Fail-open: any Gemini error returns
    # the user's text unchanged with fusion=None.
    fusion = None
    if request.custom_prompt and request.custom_prompt.strip():
        try:
            from app.services.image_understanding_service import (
                get_image_understanding_service,
            )

            fusion = await get_image_understanding_service().describe_and_fuse(
                image_url=str(request.get_room_url()),
                user_prompt=request.custom_prompt,
                tool_context=f"room_redesign:{request.space_kind}:{request.mode}",
                language="zh-TW",
            )
        except Exception as _exc:
            logger.warning("room_redesign fusion failed: %s", _exc)

    effective_user_text = (
        fusion.fused_prompt if fusion and fusion.fused_prompt else request.custom_prompt
    )
    style_prompt = effective_user_text or interior["prompt"]
    # Inject style_strength as explicit intensity guidance into the prompt.
    # Underlying Kontext / Gemini I2I has no native `strength` param, so we
    # communicate intensity via natural language. The router still receives
    # the numeric value for any provider that can use it.
    if request.style_strength <= 0.35:
        intensity_clause = "Apply the new style very subtly; keep most of the original room visible."
    elif request.style_strength <= 0.65:
        intensity_clause = "Apply the new style with balanced intensity; keep room layout and major furniture, restyle finishes, lighting, and decor."
    elif request.style_strength <= 0.85:
        intensity_clause = "Apply the new style strongly; restyle finishes, furniture, lighting and decor while preserving room layout, walls and windows."
    else:
        intensity_clause = "Apply the new style very aggressively; fully restyle finishes, furniture, lighting and decor while preserving room geometry, doorways and windows."

    # Stage mode = AI Virtual Staging. Input is an empty room photo; the
    # model must invent furniture, decor, and styling from scratch while
    # preserving walls, windows, doors, and floor finish. ReRoom-inspired
    # flagship use-case (2026-05-18).
    stage_clause = ""
    if request.mode == "stage":
        stage_clause = (
            " The input is an EMPTY room. Furnish it completely in the chosen "
            "style: add appropriate sofas, tables, lighting fixtures, rugs, "
            "art, and accent decor. Preserve the original walls, windows, "
            "doors, and overall room geometry. The final image must look "
            "like a professionally staged real-estate listing photo."
        )

    # Optional chip-driven modifiers — appended *after* the curated style
    # prompt so they accent rather than override the chosen aesthetic.
    LIGHTING_CLAUSES = {
        "daylight":            " Lit by soft cool natural daylight from large windows; balanced exposure, no harsh shadows.",
        "warm_evening":        " Warm 2700K evening interior lighting from layered lamps; cozy atmospheric ambience.",
        "dramatic_spotlight":  " Dramatic directional spotlighting from above; bold shadows and high contrast.",
        "golden_hour":         " Late-golden-hour sunlight raking across surfaces; warm amber highlights, long soft shadows.",
        "moody":               " Moody low-key lighting with deep shadow play; cinematic and atmospheric.",
    }
    MATERIAL_CLAUSES = {
        "wood":      " Dominant material is warm natural oak / walnut wood across floors, ceilings, and feature walls.",
        "marble":    " Dominant material is veined Calacatta or Carrara marble across counters and feature surfaces.",
        "concrete":  " Dominant material is polished pigmented concrete across floors, walls, and select furnishings.",
        "linen":     " Dominant material is natural unbleached linen across upholstery, drapery, and soft furnishings.",
        "brass":     " Brass and bronze accents throughout: hardware, lighting, frames, and select decor pieces.",
        "leather":   " Dominant material is rich saddle or oxblood leather across major upholstered pieces.",
        "terrazzo":  " Terrazzo with mixed-color aggregate across floors and select surfaces; soft confetti pattern.",
    }
    lighting_clause = LIGHTING_CLAUSES.get((request.lighting_tone or "").lower(), "")
    material_clause = MATERIAL_CLAUSES.get((request.material_accent or "").lower(), "")

    # 2026-05-18 — hard "no people" constraint for every interior render.
    # Architectural / staging renders must show the space itself, not
    # photographer / occupants / pets. Reinforced redundantly because some
    # upstream models (Gemini, PiAPI Flux) drop a single negative cue.
    no_people_clause = (
        " Empty room: NO people, NO humans, NO faces, NO hands, NO pets, "
        "NO photographer in frame, NO occupants — render the space only, "
        "as a clean unpopulated architectural proposal."
    )

    style_prompt = f"{style_prompt} {intensity_clause}{stage_clause}{lighting_clause}{material_clause}{no_people_clause}".strip()
    style_prompt, prompt_refinement = await _refine_generation_prompt(
        style_prompt,
        "room_redesign",
        "interior redesign prompt",
        user_prompt=bool(request.custom_prompt),
        context={"style": request.style, "preserve_structure": request.preserve_structure, "style_strength": request.style_strength},
    )

    try:
        router = get_provider_router()
        # Map style_strength (0-1, UI slider) to denoising_strength.
        # Floor at 0.6 because Kontext/Flux below ~0.55 often returns the
        # original image with cosmetic-only deltas, defeating the redesign.
        denoising_strength = max(0.6, min(0.85, 0.5 + request.style_strength * 0.4))

        # variation_count > 1 fires N parallel calls. The user pays N×
        # the base cost. Each variant gets a small prompt diversifier so
        # the same model+style yields distinct compositions / camera angles.
        # Deduction happens once for variant 1, then we top up for the rest.
        n_variants = max(1, min(3, request.variation_count or 1))
        if n_variants > 1:
            additional = (n_variants - 1) * CREDIT_COST
            ok2, err2 = await _check_and_deduct_credits(db, current_user, additional, "room_redesign")
            if not ok2:
                # Already paid for one — proceed with single result
                n_variants = 1

        DIVERSIFIERS = [
            "",
            " Choose an alternate camera composition and lens choice (wider angle, slight reframing); keep room geometry unchanged.",
            " Choose a different time of day and lighting mood (e.g. blue-hour or overcast) and slightly different decor accents; keep room geometry unchanged.",
        ]

        async def _one_render(idx: int) -> str | None:
            prompt = style_prompt + (DIVERSIFIERS[idx] if idx < len(DIVERSIFIERS) else "")
            r = await router.route(
                TaskType.INTERIOR,
                {
                    "image_url": str(request.get_room_url()),
                    "prompt": prompt,
                    "style": request.style,
                    "preserve_structure": request.preserve_structure,
                    "strength": request.style_strength,
                    "denoising_strength": denoising_strength,
                },
            )
            url = r.get("image_url") or r.get("output_url") or (r.get("output", {}).get("image_url") if isinstance(r.get("output"), dict) else None)
            return await _persist_provider_url(url, "image", current_user)

        import asyncio as _asyncio
        rendered = await _asyncio.gather(
            *[_one_render(i) for i in range(n_variants)],
            return_exceptions=True,
        )
        output_urls = [u for u in rendered if isinstance(u, str) and u]
        # Refund any failed variants
        failed = n_variants - len(output_urls)
        if failed > 0:
            await _refund_credits(db, current_user, failed * CREDIT_COST, "room_redesign")

        if not output_urls:
            return _provider_failure_response("room_redesign", {"error": "all variants failed"}, current_user)

        # Persist primary result + variants as separate UserGeneration rows
        primary_url = output_urls[0]
        for url in output_urls:
            user_gen = UserGeneration(
                user_id=current_user.id,
                tool_type=ToolType.ROOM_REDESIGN,
                input_image_url=str(request.get_room_url()),
                input_params={
                    "style": request.style,
                    "space_kind": request.space_kind,
                    "mode": request.mode,
                    "lighting_tone": request.lighting_tone,
                    "material_accent": request.material_accent,
                    "custom_prompt": request.custom_prompt,
                    "preserve_structure": request.preserve_structure,
                    "style_strength": request.style_strength,
                    "variation_count": n_variants,
                    "is_primary": (url == primary_url),
                    "prompt_refinement": prompt_refinement,
                },
                input_text=style_prompt,
                result_image_url=url,
                credits_used=CREDIT_COST,
            )
            user_gen.set_expiry()
            db.add(user_gen)

        # Demo recycle uses the primary result only
        primary_gen = UserGeneration(
            user_id=current_user.id,
            tool_type=ToolType.ROOM_REDESIGN,
            input_image_url=str(request.get_room_url()),
            input_text=style_prompt,
            result_image_url=primary_url,
        )
        await _maybe_recycle_for_demo(
            db, primary_gen, ToolType.ROOM_REDESIGN,
            topic=request.style or "modern",
            prompt=style_prompt,
            input_image_url=str(request.get_room_url()),
            result_image_url=primary_url,
            input_params={"style": request.style, "space_kind": request.space_kind, "mode": request.mode, "prompt_refinement": prompt_refinement},
        )

        await db.commit()

        return ToolResponse(
            success=True,
            result_url=primary_url,
            results=[{"image_url": u} for u in output_urls],
            credits_used=CREDIT_COST * len(output_urls),
            message=("Room redesign successful" if request.mode == "redesign" else "AI staging successful"),
            vision_summary=(fusion.image_summary or None) if fusion else None,
            user_prompt_used=(fusion.used_user_prompt if fusion else None),
            prompt_gap_reason=(fusion.gap_reason if fusion else None),
        )
    except Exception as e:
        logger.error(f"Room Redesign error: {e}", exc_info=True)
        await _refund_credits(db, current_user, CREDIT_COST, "room_redesign")
        _notify_admin_of_tool_failure("room_redesign", e, current_user)
        return ToolResponse(
            success=False,
            message=GENERIC_TOOL_FAILURE_MESSAGE,
        )


# ============================================================================
# Tool 5: Short Video
# ============================================================================

@router.post("/short-video")
async def generate_short_video(
    request: ShortVideoRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional)
):
    """
    Generate short video from image — chunked streaming with 25 s keep-alive
    heartbeat so Cloudflare / GCLB / Cloud Run idle timeouts don't close
    the connection during long Wan I2V or Veo runs (5-10 min typical).
    """
    async def _do_generate_short_video() -> Dict[str, Any]:
        result = await _generate_short_video_inner(request, db, current_user)
        return result.model_dump() if hasattr(result, "model_dump") else result

    return _stream_with_heartbeat(_do_generate_short_video)


async def _generate_short_video_inner(
    request: "ShortVideoRequest",
    db: AsyncSession,
    current_user,
) -> ToolResponse:
    """
    Generate short video from image.

    USER TIER LOGIC:
    - Demo users: Return pre-generated result from Material DB
    - Subscribers: Real-time video generation + save to UserGeneration

    Credits: 25-35 (varies by features used)
    """
    validate_media_url_or_raise(str(request.image_url), "image", "Short video input")
    await validate_image_url_dimensions_or_raise(str(request.image_url), IMAGE_TO_VIDEO_DIMENSION_RULES)
    request.image_url = await _ensure_public_image_url(
        str(request.image_url),
        user_id=str(current_user.id) if current_user else None,
    )

    # Resolve curated motion prompt — pin the request.style to the canonical
    # motion text so motion_prompt_base downstream uses it.
    curated_motion = _resolve_curated_prompt("short_video", request.prompt_id, request.locale)
    if curated_motion:
        request.style = curated_motion

    # ========== DEMO USER: Return cached demo example ==========
    if not is_subscribed_user(current_user):
        user_frame_url = _resolve_public_url(str(request.image_url)) if request.image_url else None
        # Motion prompt — prefer an explicit style hint from the client; otherwise
        # derive a terse motion description from motion_strength so the cache key
        # differentiates between "gentle" and "dramatic" selections.
        demo_effect_prompt = request.style or (
            "dramatic cinematic motion" if (request.motion_strength or 5) >= 7
            else "gentle cinematic motion" if (request.motion_strength or 5) >= 4
            else "subtle cinematic motion"
        )
        return await _demo_response(
            db,
            ToolType.SHORT_VIDEO,
            cta="Subscribe to create your own videos.",
            input_image_url=user_frame_url,
            effect_prompt=demo_effect_prompt,
        )

    # ========== SUBSCRIBER: Real-time Generation ==========
    CREDIT_COST = 25
    ok, err = await _check_and_deduct_credits(db, current_user, CREDIT_COST, "short_video")
    if not ok:
        return ToolResponse(success=False, message=err)

    try:
        credits_used = CREDIT_COST

        # Use Provider Router for I2V
        # motion_strength (1-10) maps to PiAPI prompt intensity description
        provider_router = get_provider_router()
        strength = request.motion_strength or 5
        if strength <= 3:
            motion_desc = (
                "slow cinematic dolly forward, barely perceptible parallax drift, "
                "ambient environmental micro-motion such as soft fabric sway or gentle light flicker, "
                "steady locked exposure, smooth 24fps film cadence, no abrupt movement"
            )
        elif strength <= 5:
            motion_desc = (
                "gentle cinematic orbit revealing product depth, natural environmental motion "
                "like leaves rustling or curtains breathing in breeze, subtle light shift as if "
                "clouds passing, smooth stabilized camera, elegant slow-motion feel"
            )
        elif strength <= 7:
            motion_desc = (
                "confident cinematic tracking shot, moderate parallax with foreground-background separation, "
                "natural physics-based motion on fabrics and hair, dynamic lighting transition "
                "from shadow to highlight, smooth crane-like vertical reveal, professional commercial quality"
            )
        else:
            motion_desc = (
                "dramatic cinematic push-in with rack focus, bold sweeping camera arc, energetic subject motion "
                "with flowing fabrics and dramatic wind effect, dynamic lighting with lens flare accents, "
                "high-energy fashion commercial or product launch campaign feel, 60fps smooth slow-motion"
            )
        style_hint = get_style_prompt(request.style) if request.style else None
        motion_prompt_base = (
            f"{motion_desc}. Visual style guidance: {style_hint or request.style}"
            if request.style else motion_desc
        )
        motion_prompt, prompt_refinement = await _refine_generation_prompt(
            motion_prompt_base,
            "short_video",
            "image-to-video motion prompt",
            user_prompt=bool(request.style),
            context={"motion_strength": strength, "style": request.style},
        )

        # Image understanding pass — caption the user's frame with Gemini
        # Vision and fuse the description into the motion prompt. Without
        # this the I2V model often hallucinates props ("bubble tea on
        # product shot") because Wan/Seedance get no info about *what*
        # the source image actually depicts beyond the literal pixels.
        # Fail-open: if Gemini errors out we just use the motion prompt
        # as-is so the tool keeps working.
        public_image_url = _resolve_public_url(str(request.image_url))
        try:
            from app.services.image_understanding_service import (
                get_image_understanding_service,
            )
            fusion = await get_image_understanding_service().describe_and_fuse(
                image_url=public_image_url,
                user_prompt=motion_prompt,
                tool_context=f"short_video motion_strength={strength}",
            )
            if fusion.fused_prompt:
                motion_prompt = fusion.fused_prompt
        except Exception as exc:  # noqa: BLE001
            logger.info("short_video image understanding skipped: %s", exc)

        task_params = {
            "image_url": public_image_url,
            "prompt": motion_prompt,
            "duration": 5,
            # Anti-hallucination baseline: keep the input product/subject; suppress
            # PiAPI Wan I2V's known tendency to insert unrelated food/drink props.
            "negative_prompt": (
                "food, drink, beverage, bubble tea, boba, coffee, tea, juice, alcohol, snacks, "
                "extra hands, extra fingers, extra limbs, deformed, distorted, low quality, "
                "blurry, watermark, text overlay, subtitles, brand logos not in source, "
                "changed product shape, changed product color, changed packaging"
                + (f". Also avoid: {request.negative_prompt}" if request.negative_prompt else "")
            ),
            # Strong product-identity preservation. Lower motion_strength implies
            # we want the product even more locked-in, so push image_fidelity up
            # and motion_bucket down for subtle motion settings.
            "image_fidelity": 0.95 if strength <= 3 else 0.90 if strength <= 5 else 0.85 if strength <= 7 else 0.80,
            "motion_bucket_id": 60 if strength <= 3 else 100 if strength <= 5 else 150 if strength <= 7 else 200,
        }

        if request.model_id:
            task_params["model"] = request.model_id

        # Kling family routing — when the user picks a Kling tier from the
        # short-video model dropdown (kling_omni / kling_v3 / kling_v2 / etc.)
        # we hand the request off to TaskType.KLING_VIDEO so the actual Kling
        # provider method runs. Without this short-circuit, _resolve_video_model
        # in piapi_provider would fall through to Seedance and the user would
        # silently get a Seedance video instead of the Kling they selected.
        is_kling_model = bool(request.model_id) and "kling" in str(request.model_id).lower()
        if is_kling_model:
            # Map model_id → Kling tier. "kling_omni" / "kling_v3" / "kling3"
            # all hit the new Omni tier (3.0 multimodal). Older Kling v2 /
            # v1.5 picks land on the default tier (2.6).
            mid = str(request.model_id).lower()
            if "omni" in mid or "_v3" in mid or "kling3" in mid or "kling-3" in mid:
                kling_tier = "omni"
            elif "master" in mid or "flagship" in mid:
                kling_tier = "flagship"
            else:
                kling_tier = "default"
            result = await provider_router.route(
                TaskType.KLING_VIDEO,
                {
                    **task_params,
                    "tier": kling_tier,
                },
            )
        else:
            result = await provider_router.route(
                TaskType.I2V,
                task_params
            )

        if not result.get("success"):
            await _refund_credits(db, current_user, CREDIT_COST, "short_video")
            return _provider_failure_response("short_video", result, current_user)

        video_url = result.get("video_url") or result.get("output", {}).get("video_url") or result.get("output_url")
        # Persist PiAPI/Pollo CDN video to GCS so it survives 14-day expiry.
        video_url = await _persist_provider_url(video_url, "video", current_user)

        # Optional: Apply style transformation (Video-to-Video)
        # Requires can_use_effects plan feature
        apply_style = False
        style_prompt_refinement = None
        style_transfer_error = None
        if request.style and video_url:
            effects_ok, _, _ = await _check_plan_feature(
                db, current_user, "can_use_effects", "video style effects"
            )
            apply_style = effects_ok

        if apply_style and request.style and video_url:
            style_prompt = get_style_prompt(request.style)
            if style_prompt:
                style_prompt, style_prompt_refinement = await _refine_generation_prompt(
                    style_prompt,
                    "video_transform",
                    "short video style transfer prompt",
                    user_prompt=True,
                    context={"style": request.style, "source_tool": "short_video"},
                )
                try:
                    source_frame_url = _resolve_public_url(str(request.image_url))
                    style_result = await provider_router.route(
                        TaskType.V2V,
                        {
                            "video_url": video_url,
                            "image_url": source_frame_url,
                            "first_frame_url": source_frame_url,
                            "prompt": style_prompt,
                            "model": request.model_id,
                            "duration": 5,
                        }
                    )
                    output_url = style_result.get("video_url") or style_result.get("output_url") or style_result.get("output", {}).get("video_url")
                    if output_url:
                        video_url = output_url
                        # Deduct extra 5 credits for style transfer
                        extra_ok, _ = await _check_and_deduct_credits(db, current_user, 5, "short_video_style")
                        if extra_ok:
                            credits_used += 5
                except Exception as exc:
                    style_transfer_error = str(exc)
                    logger.warning(
                        "Short video style transfer failed; returning base I2V result: %s",
                        exc,
                        exc_info=True,
                    )

        if video_url:
            # Save to UserGeneration
            user_gen = UserGeneration(
                user_id=current_user.id,
                tool_type=ToolType.SHORT_VIDEO,
                input_image_url=str(request.image_url),
                input_params={
                    "motion_strength": request.motion_strength,
                    "style": request.style,
                    "model_id": request.model_id,
                    "motion_prompt": motion_prompt,
                    "prompt_refinement": prompt_refinement,
                    "style_prompt_refinement": style_prompt_refinement,
                    "style_transfer_error": style_transfer_error,
                },
                result_video_url=video_url,
                credits_used=credits_used,
            )
            user_gen.set_expiry()
            db.add(user_gen)

            # Recycle for demo gallery
            await _maybe_recycle_for_demo(
                db, user_gen, ToolType.SHORT_VIDEO,
                topic="product_showcase", prompt=motion_prompt,
                input_image_url=str(request.image_url),
                result_video_url=video_url,
            )

            await db.commit()

            return ToolResponse(
                success=True,
                result_url=video_url,
                credits_used=credits_used,
                message=(
                    "Short video generated successfully"
                    if not style_transfer_error
                    else "Short video generated successfully. Style transfer is temporarily unavailable, so the base video was returned."
                )
            )
        else:
            await _refund_credits(db, current_user, CREDIT_COST, "short_video")
            return ToolResponse(
                success=False,
                message="Video generation returned no URL"
            )

    except Exception as e:
        logger.error(f"Short video error: {e}", exc_info=True)
        await _refund_credits(db, current_user, CREDIT_COST, "short_video")
        _notify_admin_of_tool_failure("short_video", e, current_user)
        return ToolResponse(
            success=False,
            message=GENERIC_TOOL_FAILURE_MESSAGE,
        )


## Text-to-Video endpoint removed — too expensive with low ROI.
## E-commerce users need their real products animated (I2V), not AI-generated videos from text.


# ============================================================================
# Video Style Transfer — PiAPI Wan VACE V2V
# ============================================================================

class VideoTransformRequest(BaseModel):
    """Transform video with style"""
    video_url: str
    prompt: str  # style description
    style: Optional[str] = None


@router.post("/video-transform")
async def video_transform(
    request: VideoTransformRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional)
):
    """
    Apply style transfer to a video — chunked streaming with 25 s keep-alive
    so edge proxies don't drop the connection during long V2V runs.
    """
    async def _do_video_transform() -> Dict[str, Any]:
        result = await _video_transform_inner(request, db, current_user)
        return result.model_dump() if hasattr(result, "model_dump") else result

    return _stream_with_heartbeat(_do_video_transform)


async def _video_transform_inner(
    request: "VideoTransformRequest",
    db: AsyncSession,
    current_user,
) -> ToolResponse:
    """
    Apply style transfer to a video.

    Uses PiAPI Wan VACE video-to-video.
    Credits: 35 per generation
    """
    validate_media_url_or_raise(str(request.video_url), "video", "Video transform input")

    if not is_subscribed_user(current_user):
        return await _demo_response(
            db,
            ToolType.SHORT_VIDEO,
            cta="Subscribe for video style transfer.",
            input_video_url=request.video_url,
            effect_prompt=request.prompt,
        )

    CREDIT_COST = 35
    ok, err = await _check_and_deduct_credits(db, current_user, CREDIT_COST, "video_transform")
    if not ok:
        return ToolResponse(success=False, message=err)

    try:
        router_instance = get_provider_router()
        refined_prompt, prompt_refinement = await _refine_generation_prompt(
            request.prompt,
            "video_transform",
            "video-to-video style prompt",
            user_prompt=True,
            context={"style": request.style},
        )

        # All V2V providers in the chain (piapi_mcp's Wan referenceImage, Pollo,
        # Vertex AI) reject MP4 URLs — they need a still image. Extract the
        # first frame and pass it as image_url / first_frame_url so each
        # provider gets the format it actually expects.
        try:
            first_frame_url = await _extract_first_frame_to_gcs(
                str(request.video_url),
                str(current_user.id) if current_user is not None and getattr(current_user, "id", None) else None,
            )
        except Exception as ff_exc:
            logger.error("video_transform first-frame extraction failed: %s", ff_exc, exc_info=True)
            await _refund_credits(db, current_user, CREDIT_COST, "video_transform")
            return ToolResponse(
                success=False,
                message="Could not read the input video. Please upload a standard MP4 (H.264) under 200 MB.",
            )

        result = await router_instance.route(
            TaskType.V2V,
            {
                "video_url": request.video_url,
                "image_url": first_frame_url,
                "first_frame_url": first_frame_url,
                "prompt": refined_prompt,
                "style": request.style,
            }
        )

        if result.get("success"):
            output = result.get("output", {})
            video_url = output.get("video_url")
            # Persist PiAPI/Pollo CDN video to GCS so it survives 14-day expiry.
            video_url = await _persist_provider_url(video_url, "video", current_user)

            generation = UserGeneration(
                user_id=current_user.id,
                tool_type=ToolType.SHORT_VIDEO,
                input_video_url=request.video_url,
                input_text=refined_prompt,
                input_params={
                    "prompt": request.prompt,
                    "refined_prompt": refined_prompt,
                    "style": request.style,
                    "prompt_refinement": prompt_refinement,
                },
                result_video_url=video_url,
                credits_used=CREDIT_COST,
            )
            generation.set_expiry()
            db.add(generation)
            await db.commit()

            return ToolResponse(
                success=True,
                result_url=video_url,
                credits_used=CREDIT_COST,
                message="Video transformed successfully"
            )
        else:
            await _refund_credits(db, current_user, CREDIT_COST, "video_transform")
            return _provider_failure_response("video_transform", result, current_user)
    except Exception as e:
        logger.error(f"Video transform error: {e}", exc_info=True)
        await _refund_credits(db, current_user, CREDIT_COST, "video_transform")
        _notify_admin_of_tool_failure("video_transform", e, current_user)
        return ToolResponse(success=False, message=GENERIC_TOOL_FAILURE_MESSAGE)


# ============================================================================
# Image Upscale — PiAPI image-toolkit
# ============================================================================

class UpscaleRequest(BaseModel):
    """Upscale image to higher resolution"""
    image_url: str
    scale: int = Field(2, ge=2, le=10)  # PiAPI MCP accepts 2x through 10x


@router.post("/upscale", response_model=ToolResponse)
async def upscale_image(
    request: UpscaleRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional)
):
    """
    Upscale image to 2x or 4x resolution.

    Uses PiAPI image-toolkit upscale.
    Credits: 10 per generation
    """
    validate_media_url_or_raise(str(request.image_url), "image", "Upscale input")
    await validate_image_url_dimensions_or_raise(str(request.image_url), COMMON_IMAGE_DIMENSION_RULES)

    # Frontend uploaders post base64 data: URLs. PiAPI, Pollo, and Vertex
    # all need a fetchable public URL, so promote data URLs to GCS once
    # here. Downstream code reads request.image_url unchanged.
    request.image_url = await _ensure_public_image_url(
        str(request.image_url),
        user_id=str(current_user.id) if current_user else None,
    )

    if not is_subscribed_user(current_user):
        return await _demo_response(
            db,
            ToolType.EFFECT,
            cta="Subscribe for HD upscale.",
            input_image_url=_resolve_public_url(str(request.image_url)) if request.image_url else None,
            effect_prompt=f"upscale_{request.scale}x",
        )

    # Plan-gate high-scale upscale: 2x ≈ 1080p, 4x ≈ 4K
    requested_resolution = "4k" if request.scale >= 4 else "1080p"
    res_ok, res_err = await _check_plan_resolution(db, current_user, requested_resolution)
    if not res_ok:
        return ToolResponse(success=False, message=res_err)

    CREDIT_COST = 10
    ok, err = await _check_and_deduct_credits(db, current_user, CREDIT_COST, "upscale")
    if not ok:
        return ToolResponse(success=False, message=err)

    try:
        router_instance = get_provider_router()
        result = await router_instance.route(
            TaskType.UPSCALE,
            {
                "image_url": _resolve_public_url(request.image_url),
                "scale": request.scale,
            }
        )

        if result.get("success"):
            output = result.get("output", {})
            image_url = output.get("image_url")
            # Persist PiAPI CDN result to GCS so it survives 14-day expiry.
            image_url = await _persist_provider_url(image_url, "image", current_user)

            generation = UserGeneration(
                user_id=current_user.id,
                tool_type=ToolType.EFFECT,
                input_image_url=request.image_url,
                input_params={"scale": request.scale, "action": "upscale"},
                result_image_url=image_url,
                credits_used=CREDIT_COST,
            )
            generation.set_expiry()
            db.add(generation)
            await db.commit()

            return ToolResponse(
                success=True,
                result_url=image_url,
                credits_used=CREDIT_COST,
                message=f"Image upscaled {request.scale}x successfully"
            )
        else:
            await _refund_credits(db, current_user, CREDIT_COST, "upscale")
            return _provider_failure_response("upscale", result, current_user)
    except Exception as e:
        logger.error(f"Upscale error: {e}", exc_info=True)
        await _refund_credits(db, current_user, CREDIT_COST, "upscale")
        _notify_admin_of_tool_failure("image_upscale", e, current_user)
        return ToolResponse(success=False, message=GENERIC_TOOL_FAILURE_MESSAGE)


# ============================================================================
# Tool 6: AI Avatar
# ============================================================================

@router.post("/avatar")
async def generate_avatar_video(
    request: AvatarRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional)
):
    """
    Generate AI Avatar video from photo with lip sync.

    Returns ``application/json`` streamed with a 25-second keep-alive
    heartbeat so intermediate proxies (Cloudflare, GCLB, Cloud Run gateway)
    do not drop the connection while PiAPI Kling Avatar (with F5-TTS or
    tts-1 fallback) is still running upstream — that path can take up to
    10 minutes for longer scripts.

    USER TIER LOGIC:
    - Demo users: Return pre-generated result from Material DB
    - Subscribers: Real-time avatar generation + save to UserGeneration

    Supported languages: 'en' (English), 'zh-TW' (Traditional Chinese)
    Credits: 30 per generation
    """

    async def _do_generate_avatar() -> Dict[str, Any]:
        return (await _generate_avatar_inner(request, db, current_user)).model_dump()

    return _stream_with_heartbeat(_do_generate_avatar)


async def _generate_avatar_inner(
    request: "AvatarRequest",
    db: AsyncSession,
    current_user,
) -> ToolResponse:
    """Actual avatar generation logic — split out from the route handler so
    we can wrap it in a chunked streaming response with periodic keep-alive
    bytes (see ``_stream_with_heartbeat``). All return paths produce a
    ``ToolResponse`` so the wrapper can serialise the final JSON payload."""
    from app.models.material import MaterialSource, MaterialStatus

    validate_media_url_or_raise(str(request.image_url), "image", "AI avatar headshot")
    await validate_image_url_dimensions_or_raise(str(request.image_url), AVATAR_HEADSHOT_DIMENSION_RULES)
    request.image_url = await _ensure_public_image_url(
        str(request.image_url),
        user_id=str(current_user.id) if current_user else None,
    )

    # Resolve curated avatar script. The avatar `language` field decides which
    # canonical variant to use: zh-TW → ZH script; otherwise → EN script.
    curated_script = _resolve_curated_prompt("ai_avatar", request.prompt_id, request.locale or request.language)
    if curated_script:
        request.script = curated_script
    if not request.script or not request.script.strip():
        raise HTTPException(
            status_code=400,
            detail="Either 'script' or 'prompt_id' is required for the avatar tool.",
        )

    # ========== DEMO USER: Return cached demo example ==========
    if not is_subscribed_user(current_user):
        user_headshot = _resolve_public_url(str(request.image_url)) if request.image_url else None
        return await _demo_response(
            db,
            ToolType.AI_AVATAR,
            cta="Subscribe to create your own avatars.",
            input_image_url=user_headshot,
            effect_prompt=request.script,
        )

    # ========== SUBSCRIBER: Real-time Generation ==========
    # Check plan-level resolution limit
    res_ok, res_err = await _check_plan_resolution(db, current_user, request.resolution)
    if not res_ok:
        return ToolResponse(success=False, message=res_err)

    # Hardcoded fallback aligned with the seeded ServicePricing row
    # (ai_avatar.credit_cost=300, api_cost_usd≈$0.30). Previously 30, which
    # would have surfaced as a 10x silent jump the moment the seed ran
    # against prod DB once dynamic ServicePricing lookup took effect.
    CREDIT_COST = 300
    ok, err = await _check_and_deduct_credits(db, current_user, CREDIT_COST, "ai_avatar")
    if not ok:
        return ToolResponse(success=False, message=err)

    try:
        # Validate language
        if request.language not in ["en", "zh-TW", "ja", "ko"]:
            await _refund_credits(db, current_user, CREDIT_COST, "ai_avatar")
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported language: {request.language}. Supported: en, zh-TW, ja, ko"
            )

        # Validate duration
        if request.duration < 5 or request.duration > 120:
            await _refund_credits(db, current_user, CREDIT_COST, "ai_avatar")
            raise HTTPException(
                status_code=400,
                detail="Duration must be between 5 and 120 seconds"
            )

        provider_router = get_provider_router()

        logger.info(f"Calling Gemini Avatar API for subscriber: {request.script[:50]}...")

        result = await provider_router.route(
            TaskType.AVATAR,
            {
                "image_url": _resolve_public_url(str(request.image_url)),
                "script": request.script,
                "language": request.language,
                "voice_id": request.voice_id,
                "duration": request.duration,
                "user_id": str(current_user.id),
            }
        )

        if result.get("success"):
            output = result.get("output", {})
            video_url = output.get("video_url") or result.get("video_url")
            # Persist provider CDN video to GCS so it survives 14-day expiry.
            video_url = await _persist_provider_url(video_url, "video", current_user)

            # Save to UserGeneration (for subscriber's personal gallery)
            user_gen = UserGeneration(
                user_id=current_user.id,
                tool_type=ToolType.AI_AVATAR,
                input_image_url=str(request.image_url),
                input_params={
                    "language": request.language,
                    "voice_id": request.voice_id,
                    "duration": request.duration
                },
                input_text=request.script,
                result_video_url=video_url,
                result_metadata={
                    "api": "gemini-avatar",
                    "action": "photo_to_avatar",
                    "language": request.language
                },
                credits_used=30,
            )
            user_gen.set_expiry()
            db.add(user_gen)

            # Recycle for demo gallery
            await _maybe_recycle_for_demo(
                db, user_gen, ToolType.AI_AVATAR,
                topic="spokesperson", prompt=request.script[:100],
                input_image_url=str(request.image_url),
                result_video_url=video_url,
                input_params={"language": request.language},
            )

            await db.commit()

            return ToolResponse(
                success=True,
                result_url=video_url,
                credits_used=30,
                message=f"Avatar video generated successfully in {request.language}"
            )
        else:
            await _refund_credits(db, current_user, CREDIT_COST, "ai_avatar")
            return ToolResponse(
                success=False,
                message=result.get("error", "Avatar generation failed")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Avatar generation error: {e}", exc_info=True)
        await _refund_credits(db, current_user, CREDIT_COST, "ai_avatar")
        _notify_admin_of_tool_failure("ai_avatar", e, current_user)
        return ToolResponse(
            success=False,
            message=GENERIC_TOOL_FAILURE_MESSAGE,
        )


@router.get("/avatar/voices")
async def get_avatar_voices(
    language: Optional[str] = None
):
    """
    Get available avatar voices.
    Filter by language: 'en', 'zh-TW', 'ja', 'ko'
    """
    if language and language in A2E_VOICES:
        return A2E_VOICES[language]
    return A2E_VOICES


@router.get("/avatar/characters")
async def get_avatar_characters():
    """
    Get available avatar characters.

    Frontend should use these characters instead of fixed Unsplash images.
    Each character includes:
    - id: Character ID for generation
    - name: Character name
    - preview_url: Preview image URL
    - lang: Supported language(s)

    Characters are organized by gender where possible.
    Note: Avatar generation now uses Gemini via provider router.
    """
    # Return empty list since A2E characters are no longer available
    # Avatar generation now routes through Gemini
    return {
        "success": True,
        "female": [],
        "male": [],
        "other": [],
        "total": 0,
        "note": "Avatar generation now uses Gemini. Use any headshot image."
    }


# ============================================================================
# Image-to-Image Transform
# ============================================================================

class ImageTransformRequest(BaseModel):
    """Image-to-Image transformation using PiAPI Flux"""
    image_url: str
    prompt: str
    strength: float = 0.75  # 0.0 (subtle) to 1.0 (dramatic)
    negative_prompt: Optional[str] = None


@router.post("/image-transform", response_model=ToolResponse)
async def image_transform(
    request: ImageTransformRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional)
):
    """
    True Image-to-Image transformation via PiAPI Flux.

    Upload a source image and describe how to transform it.
    Supports style changes, scene modifications, artistic effects, etc.

    USER TIER LOGIC:
    - Demo users: Return pre-generated result from Material DB (EFFECT type)
    - Subscribers: Real-time I2I via PiAPI Flux img2img

    Credits: 20 (free) / 80 (paid) per generation
    """
    validate_media_url_or_raise(str(request.image_url), "image", "Image transform input")
    await validate_image_url_dimensions_or_raise(str(request.image_url), COMMON_IMAGE_DIMENSION_RULES)
    request.image_url = await _ensure_public_image_url(
        str(request.image_url),
        user_id=str(current_user.id) if current_user else None,
    )

    # ========== DEMO USER: Return cached demo example ==========
    if not is_subscribed_user(current_user):
        return await _demo_response(
            db,
            ToolType.EFFECT,
            cta="Subscribe for custom I2I transformations.",
            input_image_url=_resolve_public_url(str(request.image_url)) if request.image_url else None,
            effect_prompt=request.prompt,
        )

    # ========== SUBSCRIBER: Real-time I2I Generation ==========
    # Check plan-level effects permission
    allowed, err, _ = await _check_plan_feature(db, current_user, "can_use_effects", "effects/image transform")
    if not allowed:
        return ToolResponse(success=False, message=err)

    from app.services.tier_config import get_credit_cost, get_user_tier

    tier = get_user_tier(current_user)
    cost = get_credit_cost("i2i", current_user)

    ok, err = await _check_and_deduct_credits(db, current_user, cost, "image_transform")
    if not ok:
        return ToolResponse(success=False, message=err)

    try:
        provider_router = get_provider_router()
        refined_prompt, prompt_refinement = await _refine_generation_prompt(
            request.prompt,
            "image_transform",
            "image-to-image edit prompt",
            user_prompt=True,
            context={"strength": request.strength},
        )
        result = await provider_router.route(
            TaskType.I2I,
            {
                "image_url": _resolve_public_url(str(request.image_url)),
                "prompt": refined_prompt,
                "strength": request.strength,
                "negative_prompt": request.negative_prompt or "",
            },
            user_tier=tier,
        )

        if result.get("success"):
            output = result.get("output", {})
            result_url = output.get("image_url")

            # Save to UserGeneration
            user_gen = UserGeneration(
                user_id=current_user.id,
                tool_type=ToolType.EFFECT,
                input_image_url=str(request.image_url),
                input_text=refined_prompt,
                input_params={
                    "strength": request.strength,
                    "negative_prompt": request.negative_prompt,
                    "mode": "i2i_transform",
                    "original_prompt": request.prompt,
                    "prompt_refinement": prompt_refinement,
                },
                result_image_url=result_url,
                credits_used=cost,
            )
            user_gen.set_expiry()
            db.add(user_gen)
            await db.commit()

            return ToolResponse(
                success=True,
                result_url=result_url,
                credits_used=cost,
                message="Image transformed successfully"
            )
        else:
            await _refund_credits(db, current_user, cost, "image_transform")
            return ToolResponse(
                success=False,
                message=result.get("error", "Image transformation failed")
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image transform error: {e}", exc_info=True)
        await _refund_credits(db, current_user, cost, "image_transform")
        _notify_admin_of_tool_failure("image_transform", e, current_user)
        return ToolResponse(
            success=False,
            message=GENERIC_TOOL_FAILURE_MESSAGE,
        )


# ============================================================================
# Image Translation & Video Dubbing
# ============================================================================

def _build_image_translation_prompt(request: ImageTranslateRequest) -> str:
    source_clause = f" from {request.source_language}" if request.source_language else ""
    extra = f" Extra instructions: {request.instructions}" if request.instructions else ""
    return (
        f"Translate every visible text element in this image{source_clause} into {request.target_language}. "
        "Replace the original text in-place while preserving the same layout, line breaks, typography weight, "
        "signage/card/poster boundaries, product photography, colors, lighting, and non-text image content. "
        "Keep brand names, logos, URLs, numbers, and currency symbols unchanged unless they are normal words that must be localized. "
        "Do not add new objects, remove products, or change faces. Produce a clean commercial-quality localized image."
        f"{extra}"
    )


@router.post("/image-translate", response_model=ToolResponse)
async def image_translate(
    request: ImageTranslateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    """Translate visible text inside an image using the existing I2I provider path."""
    validate_media_url_or_raise(str(request.image_url), "image", "Image translation input")
    await validate_image_url_dimensions_or_raise(str(request.image_url), COMMON_IMAGE_DIMENSION_RULES)
    # Promote data: URLs to GCS so Gemini's HTTP fetch in translate_image_text
    # works on subscriber uploads.
    request.image_url = await _ensure_public_image_url(
        str(request.image_url),
        user_id=str(current_user.id) if current_user else None,
    )
    prompt = _build_image_translation_prompt(request)

    if not is_subscribed_user(current_user):
        preview_url = _resolve_public_url(str(request.image_url))
        try:
            return await _demo_response(
                db,
                ToolType.EFFECT,
                cta="Subscribe to translate your own images.",
                input_image_url=preview_url,
                effect_prompt=prompt,
            )
        except HTTPException as exc:
            if exc.status_code != 503:
                raise
            return ToolResponse(
                success=True,
                result_url=preview_url,
                image_url=preview_url,
                credits_used=0,
                cached=True,
                is_demo=True,
                demo_input_url=preview_url,
                demo_prompt=prompt,
                message="Demo preview ready. Subscribe to translate your own images.",
            )

    allowed, err, _ = await _check_plan_feature(db, current_user, "can_use_effects", "image translation")
    if not allowed:
        return ToolResponse(success=False, message=err)

    from app.services.tier_config import get_credit_cost

    cost = get_credit_cost("i2i", current_user)
    ok, err = await _check_and_deduct_credits(db, current_user, cost, "image_translation")
    if not ok:
        return ToolResponse(success=False, message=err)

    try:
        router_instance = get_provider_router()
        original_translation_prompt = prompt
        # Image translation needs in-place text replacement. The generic I2I
        # router (Flux derive_image / Imagen edit) produces a creative re-paint
        # where text becomes decorative gibberish. Call Gemini 2.5 Flash Image
        # directly — it's the only model in our stack that reads source text
        # and re-renders the same image with translated text in the same
        # layout. Skip prompt refinement: the literal prompt is already tuned.
        result = await router_instance.vertex_ai.translate_image_text(
            {
                "image_url": _resolve_public_url(str(request.image_url)),
                "target_language": request.target_language,
                "source_language": request.source_language,
                "instructions": request.instructions,
            }
        )
        prompt_refinement = {"changed": False, "reason": "direct_gemini_image_edit"}

        if not result.get("success"):
            await _refund_credits(db, current_user, cost, "image_translation")
            return _provider_failure_response("image_translation", result, current_user)

        output = result.get("output", {})
        result_url = output.get("image_url") or result.get("image_url")
        if not result_url:
            await _refund_credits(db, current_user, cost, "image_translation")
            return ToolResponse(success=False, message="Image translation failed: no output URL")
        # Persist provider CDN result to GCS so it survives 14-day expiry.
        result_url = await _persist_provider_url(result_url, "image", current_user)

        user_gen = UserGeneration(
            user_id=current_user.id,
            tool_type=ToolType.EFFECT,
            input_image_url=str(request.image_url),
            input_text=prompt,
            input_params={
                "mode": "image_translation",
                "target_language": request.target_language,
                "source_language": request.source_language,
                "instructions": request.instructions,
                "original_prompt": original_translation_prompt,
                "prompt_refinement": prompt_refinement,
            },
            result_image_url=result_url,
            result_metadata={"action": "image_translation", "provider_task": "i2i"},
            credits_used=cost,
        )
        user_gen.set_expiry()
        db.add(user_gen)
        await _maybe_recycle_for_demo(
            db,
            user_gen,
            ToolType.EFFECT,
            topic="image_translation",
            prompt=prompt,
            input_image_url=str(request.image_url),
            result_image_url=result_url,
            effect_prompt=prompt,
            input_params={"mode": "image_translation", "target_language": request.target_language},
        )
        await db.commit()

        return ToolResponse(
            success=True,
            result_url=result_url,
            image_url=result_url,
            credits_used=cost,
            message=f"Image translated to {request.target_language}",
        )
    except Exception as exc:
        logger.error("Image translation error: %s", exc, exc_info=True)
        await _refund_credits(db, current_user, cost, "image_translation")
        _notify_admin_of_tool_failure("image_translation", exc, current_user)
        return ToolResponse(success=False, message=GENERIC_TOOL_FAILURE_MESSAGE)


@router.post("/video-dubbing", response_model=ToolResponse)
async def video_dubbing(
    request: VideoDubbingRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    """Create a localized voiceover track and return a new dubbed MP4."""
    validate_media_url_or_raise(str(request.video_url), "video", "Video dubbing input")
    script = request.translated_script or request.source_script
    if not script:
        return ToolResponse(
            success=False,
            message="Please provide a source script/transcript or a translated script for dubbing.",
        )

    if not is_subscribed_user(current_user):
        demo_video = _resolve_public_url(str(request.video_url))
        return ToolResponse(
            success=True,
            result_url=demo_video,
            video_url=demo_video,
            translated_script=script,
            credits_used=0,
            cached=True,
            is_demo=True,
            message="Demo preview ready. Subscribe to generate a dubbed video with your own media.",
        )

    translated_script = request.translated_script or await _translate_text_for_dubbing(
        request.source_script or "",
        request.target_language,
        request.source_language,
    )

    allowed, err, _ = await _check_plan_feature(db, current_user, "can_use_effects", "video dubbing")
    if not allowed:
        return ToolResponse(success=False, message=err)

    # 30 credits per tier_config.py video_dubbing default; UI hard-codes the
    # same value on CreditCost so the displayed cost matches what we deduct.
    CREDIT_COST = 30
    ok, err = await _check_and_deduct_credits(db, current_user, CREDIT_COST, "video_dubbing")
    if not ok:
        return ToolResponse(success=False, message=err)

    # Pick a sensible default tts-1 voice based on the target language.
    # tts-1 is multilingual but each voice has a slightly different timbre;
    # these picks are the most natural-sounding for each market.
    def _pick_voice_for(lang: str) -> str:
        l = (lang or "").lower()
        if l.startswith("zh"): return "nova"      # clearer Mandarin diction
        if l.startswith("ja"): return "nova"
        if l.startswith("ko"): return "shimmer"
        if l.startswith("es"): return "fable"
        return "alloy"                             # default (en + others)

    try:
        router_instance = get_provider_router()
        speech_result = await router_instance.piapi.text_to_speech(
            {
                "text": translated_script,
                "ref_audio": request.voice_reference_url or "",
                "ref_text": request.voice_reference_text,
                "voice": _pick_voice_for(request.target_language),
            }
        )
        if not speech_result.get("success"):
            await _refund_credits(db, current_user, CREDIT_COST, "video_dubbing")
            err_text = (speech_result.get("error") or speech_result.get("message") or "").lower()
            # PiAPI's F5-TTS upstream is currently 500'ing on every call; surface
            # an honest message instead of the generic "tool unavailable" so the
            # user knows it's a voice-cloning service issue (not their video).
            if "failed to get input audio" in err_text or "invalid request" in err_text:
                friendly = (
                    "The voice cloning service could not read the reference voice clip. "
                    "Please upload a 16 kHz mono WAV/MP3 reference voice (5-15 s of clean speech) and try again."
                )
            elif "internal server error" in err_text or "failed to do request" in err_text or "500" in err_text:
                friendly = (
                    "The voice cloning service is temporarily down upstream (PiAPI F5-TTS). "
                    "Please try again in a few minutes."
                )
            else:
                friendly = GENERIC_TOOL_FAILURE_MESSAGE
            return _provider_failure_response("video_dubbing", speech_result, current_user, user_message=friendly)

        speech_output = speech_result.get("output", {})
        audio_url = speech_output.get("audio_url") or speech_output.get("url") or speech_result.get("audio_url")
        if not audio_url:
            await _refund_credits(db, current_user, CREDIT_COST, "video_dubbing")
            return ToolResponse(success=False, message="Speech generation failed: no audio URL")

        result_video_url = await _run_ffmpeg_voiceover_mux(
            _resolve_public_url(str(request.video_url)),
            audio_url,
            str(current_user.id),
        )

        # Capture which TTS engine actually produced the audio so we can
        # tell whether the user got their voice clone or a fallback voice.
        speech_provider = "piapi_tts"
        speech_meta = (speech_result.get("output") or {}) if isinstance(speech_result, dict) else {}
        if speech_meta.get("model") == "tts-1":
            speech_provider = f"piapi_tts_1:{speech_meta.get('voice') or 'alloy'}"

        user_gen = UserGeneration(
            user_id=current_user.id,
            tool_type=ToolType.SHORT_VIDEO,
            input_video_url=str(request.video_url),
            input_text=translated_script,
            input_params={
                "mode": "video_dubbing",
                "target_language": request.target_language,
                "source_language": request.source_language,
                "has_voice_reference": bool(request.voice_reference_url),
            },
            result_video_url=result_video_url,
            result_metadata={
                "action": "video_dubbing",
                "audio_url": audio_url,
                "speech_provider": speech_provider,
                "mux": "ffmpeg",
            },
            credits_used=CREDIT_COST,
        )
        user_gen.set_expiry()
        db.add(user_gen)
        await _maybe_recycle_for_demo(
            db,
            user_gen,
            ToolType.SHORT_VIDEO,
            topic="video_dubbing",
            prompt=translated_script[:300],
            input_video_url=str(request.video_url),
            result_video_url=result_video_url,
            effect_prompt=f"dubbed_{request.target_language}",
            input_params={"mode": "video_dubbing", "target_language": request.target_language},
        )
        await db.commit()

        return ToolResponse(
            success=True,
            result_url=result_video_url,
            video_url=result_video_url,
            audio_url=audio_url,
            translated_script=translated_script,
            credits_used=CREDIT_COST,
            message=f"Video dubbed in {request.target_language}",
        )
    except Exception as exc:
        logger.error("Video dubbing error: %s", exc, exc_info=True)
        await _refund_credits(db, current_user, CREDIT_COST, "video_dubbing")
        _notify_admin_of_tool_failure("video_dubbing", exc, current_user)

        # Map the exception to an actionable user-facing message. Each branch
        # corresponds to a specific failure mode we know happens in practice
        # so the user can take the right next step instead of seeing the
        # generic "tool unavailable" placeholder.
        exc_text = str(exc).lower()
        exc_type = type(exc).__name__

        # 1. PiAPI F5-TTS upstream 500. Path A (with ref_audio) catches this
        #    in text_to_speech() and falls back to tts-1, but if the user-
        #    supplied ref returns an explicit auth error we still raise.
        if "internal server error" in exc_text or "failed to do request" in exc_text or "failed to get input audio" in exc_text:
            return ToolResponse(success=False, message=(
                "The voice cloning service is temporarily down upstream. "
                "Please try again in a few minutes, or remove the voice reference to use the standard voice."
            ))
        # 2. ffmpeg muxing failed (bad video container, missing audio stream,
        #    encoder error). User needs a different input video.
        if "ffmpeg dubbing mux failed" in exc_text or "ffmpeg" in exc_text:
            return ToolResponse(success=False, message=(
                "Could not combine the audio with your video. "
                "Please use a standard MP4 (H.264) under 200 MB and try again."
            ))
        # 3. Input video URL not reachable from our backend (Cloud Run egress
        #    blocked, signed URL expired, host returns 4xx/5xx).
        if (
            "filenotfounderror" in exc_text
            or "client error '4" in exc_text
            or "server error '5" in exc_text
            or "could not download" in exc_text
            or exc_type in ("HTTPStatusError", "TimeoutException", "ConnectError")
        ):
            return ToolResponse(success=False, message=(
                "Could not read the input video. The URL may be unreachable, "
                "private, or have expired. Please re-upload the video and try again."
            ))
        # 4. GCS upload failed at persist time.
        if "upload" in exc_text and ("gcs" in exc_text or "storage" in exc_text):
            return ToolResponse(success=False, message=(
                "Could not save the dubbed video to storage. Please try again in a moment."
            ))
        # 5. tts-1 quota / rate-limit upstream.
        if "tts-1 returned http 429" in exc_text or "rate" in exc_text and "limit" in exc_text:
            return ToolResponse(success=False, message=(
                "Voice generation is rate-limited right now. Please try again in a minute."
            ))
        # 6. Anything else.
        return ToolResponse(success=False, message=GENERIC_TOOL_FAILURE_MESSAGE)


# ============================================================================
# Premium / Flagship Model Endpoints (Midjourney, Kling video, Luma)
# ----------------------------------------------------------------------------
# Credit costs flow through ServicePricing rows seeded in
# backend/scripts/seed_new_pricing_tiers.py. The hardcoded values below are
# fallback only — _check_and_deduct_credits prefers the DB-driven amount.
#
# Demo users hit _demo_response with the new service_type string; until ops
# seeds demo_examples rows for these tools the demo cache will return 503,
# which is the intended "subscribe to unlock" UX for flagship models.
# ============================================================================


class MidjourneyImagineRequest(BaseModel):
    """Generate a single image via Midjourney through PiAPI."""
    prompt: str = Field(..., min_length=1, max_length=2000)
    aspect_ratio: str = Field(default="1:1", description="1:1, 16:9, 9:16, 4:3, 3:4, etc.")
    process_mode: Optional[str] = Field(
        default=None,
        description="relax | fast | turbo. Defaults to PIAPI_MIDJOURNEY_PROCESS_MODE."
    )
    model: Optional[str] = Field(
        default=None,
        description=(
            "Optional T2I model family. Falls back to Flux when omitted. "
            "Accepted values: 'flux' (default), 'qwen', 'z-image'. "
            "Maps to piapi_provider.text_to_image() dispatch (verified "
            "against PiAPI's live catalog 2026-05-20)."
        ),
    )


@router.post("/midjourney-imagine", response_model=ToolResponse)
async def midjourney_imagine(
    request: MidjourneyImagineRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    """
    Premium image generation.

    Originally backed by Midjourney via PiAPI, but PiAPI permanently
    dropped Midjourney support in 2026-05 ("sorry, we no longer support
    MidJourney service"). The endpoint now routes through TaskType.T2I,
    which uses Flux (PiAPI MCP → PiAPI REST → Pollo → Vertex AI) — the
    premium image-generation tier the rest of the app already uses. The
    50-credit price stays in place so existing pricing isn't broken.

    UI still calls this path; clients don't need any change.
    """
    if not is_subscribed_user(current_user):
        return await _demo_response(
            db,
            "image_generation_premium",
            cta="Subscribe to generate premium AI images.",
            effect_prompt=request.prompt[:200],
        )

    CREDIT_COST = 50
    ok, err = await _check_and_deduct_credits(
        db, current_user, CREDIT_COST, "image_generation_premium"
    )
    if not ok:
        return ToolResponse(success=False, message=err)

    # Map MJ aspect_ratio (e.g. "16:9") to a Flux-compatible WxH size.
    aspect_to_size = {
        "1:1":  "1024*1024",
        "16:9": "1280*720",
        "9:16": "720*1280",
        "4:3":  "1152*896",
        "3:4":  "896*1152",
        "3:2":  "1216*832",
        "2:3":  "832*1216",
    }
    size = aspect_to_size.get(request.aspect_ratio, "1024*1024")

    try:
        provider_router = get_provider_router()
        route_params: Dict[str, Any] = {
            "prompt": request.prompt,
            "size": size,
        }
        if request.model and request.model.lower() != "flux":
            # piapi_provider.text_to_image() picks the family by params["model"]:
            # qwen → Qubico/qwen-image, z-image → Qubico/z-image, anything else
            # falls back to Flux. No whitelist needed; the provider's else-branch
            # is the safe default.
            route_params["model"] = request.model
        result = await provider_router.route(TaskType.T2I, route_params)
        if not result.get("success"):
            await _refund_credits(db, current_user, CREDIT_COST, "image_generation_premium")
            return ToolResponse(success=False, message=result.get("error") or GENERIC_TOOL_FAILURE_MESSAGE)

        output = result.get("output") or {}
        image_url = output.get("image_url")
        image_url = await _persist_provider_url(image_url, "image", current_user)
        if not image_url:
            await _refund_credits(db, current_user, CREDIT_COST, "image_generation_premium")
            return ToolResponse(success=False, message="Image generation returned no result. Please try again.")

        return ToolResponse(
            success=True,
            result_url=image_url,
            image_url=image_url,
            credits_used=CREDIT_COST,
            message="Image generated.",
        )
    except Exception as exc:
        logger.error("midjourney_imagine error: %s", exc, exc_info=True)
        await _refund_credits(db, current_user, CREDIT_COST, "image_generation_premium")
        _notify_admin_of_tool_failure("midjourney_imagine", exc, current_user)
        # Surface the upstream message when it exists so users see "PiAPI
        # rate-limited" / "Pollo credits depleted" instead of the masked
        # GENERIC fallback. Falls back to GENERIC for empty/None.
        return ToolResponse(success=False, message=str(exc) or GENERIC_TOOL_FAILURE_MESSAGE)


class KlingVideoRequest(BaseModel):
    """Generate video via Kling (PiAPI). T2V if no image_url; I2V otherwise."""
    prompt: str = Field(..., min_length=1, max_length=2500)
    tier: str = Field(
        default="default",
        description=(
            '"default" → Kling 2.6 (~100 credits); '
            '"flagship" → Kling 2.1-master pro mode (~500 credits); '
            '"omni" → Kling 3.0 multimodal with audio + lip-sync (~750 credits, 2026-05-19 tier addition)'
        ),
    )
    aspect_ratio: str = Field(default="16:9", description="T2V only: 16:9 / 9:16 / 1:1")
    duration: int = Field(default=5, description="5 or 10")
    image_url: Optional[str] = Field(default=None, description="If set, switches to image-to-video")
    image_tail_url: Optional[str] = Field(default=None, description="Optional end frame for I2V")
    negative_prompt: Optional[str] = Field(default=None, max_length=2500)
    cfg_scale: Optional[float] = Field(default=None, ge=0.0, le=1.0)


@router.post("/kling-video", response_model=ToolResponse)
async def kling_video(
    request: KlingVideoRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    """
    Premium Kling video generation. Three tiers:
      - tier="default"  → Kling 2.6 std mode, video_generation_standard pricing
      - tier="flagship" → Kling 2.1-master pro mode, video_flagship pricing
      - tier="omni"     → Kling 3.0 / Omni (multimodal, includes audio + lip-sync)
    """
    tier = (request.tier or "default").lower()
    if tier not in {"default", "flagship", "omni"}:
        return ToolResponse(success=False, message="tier must be 'default', 'flagship', or 'omni'")

    if tier == "omni":
        # Kling 3.0 / Omni — 2026-05-19 owner-approved premium tier
        # (頂級品質 + audio). Priced above flagship because the multimodal
        # output is the most expensive Kling task per PiAPI's price sheet.
        service_type = "video_kling_omni"
        credit_cost_fallback = 750
        demo_cta = "Subscribe to unlock Kling 3.0 / Omni multimodal videos."
    elif tier == "flagship":
        service_type = "video_flagship"
        credit_cost_fallback = 500
        demo_cta = "Subscribe to unlock Kling 2.1-master flagship videos."
    else:
        service_type = "video_generation_standard"
        credit_cost_fallback = 100
        demo_cta = "Subscribe to generate Kling videos."

    if not is_subscribed_user(current_user):
        return await _demo_response(
            db,
            service_type,
            cta=demo_cta,
            input_image_url=request.image_url,
            effect_prompt=request.prompt[:200],
        )

    if request.image_url:
        request.image_url = await _ensure_public_image_url(
            request.image_url, user_id=str(current_user.id) if current_user else None
        )
    if request.image_tail_url:
        request.image_tail_url = await _ensure_public_image_url(
            request.image_tail_url, user_id=str(current_user.id) if current_user else None
        )

    ok, err = await _check_and_deduct_credits(
        db, current_user, credit_cost_fallback, service_type
    )
    if not ok:
        return ToolResponse(success=False, message=err)

    try:
        provider_router = get_provider_router()
        result = await provider_router.route(
            TaskType.KLING_VIDEO,
            {
                "prompt": request.prompt,
                "tier": tier,
                "aspect_ratio": request.aspect_ratio,
                "duration": request.duration,
                "image_url": request.image_url,
                "image_tail_url": request.image_tail_url,
                "negative_prompt": request.negative_prompt,
                "cfg_scale": request.cfg_scale,
            },
        )
        if not result.get("success"):
            await _refund_credits(db, current_user, credit_cost_fallback, service_type)
            return ToolResponse(success=False, message=result.get("error") or GENERIC_TOOL_FAILURE_MESSAGE)

        output = result.get("output") or {}
        video_url = output.get("video_url")
        video_url = await _persist_provider_url(video_url, "video", current_user)
        if not video_url:
            await _refund_credits(db, current_user, credit_cost_fallback, service_type)
            return ToolResponse(success=False, message="Kling returned no video URL. Please try again.")

        return ToolResponse(
            success=True,
            result_url=video_url,
            video_url=video_url,
            credits_used=credit_cost_fallback,
            message=f"Video generated via Kling ({tier}).",
        )
    except Exception as exc:
        logger.error("kling_video error: %s", exc, exc_info=True)
        await _refund_credits(db, current_user, credit_cost_fallback, service_type)
        _notify_admin_of_tool_failure("kling_video", exc, current_user)
        # Surface the upstream message so users see the real reason (PiAPI
        # rate-limit, model unsupported, etc.) rather than the generic mask.
        return ToolResponse(success=False, message=str(exc) or GENERIC_TOOL_FAILURE_MESSAGE)


# /luma-video endpoint removed 2026-05-19. Use /tools/short-video with
# model_id="seedance" (default tier), "hailuo", "hunyuan", or "wan" — or
# /tools/kling-video with tier="omni" for Kling 3.0 premium output.


# ============================================================================
# Template & Resource Endpoints
# ============================================================================

@router.get("/templates/scenes")
async def get_scene_templates():
    """Get available scene templates for Product Scene tool"""
    return SCENE_TEMPLATES


@router.get("/templates/interior-styles")
async def get_interior_styles(space_kind: str = "interior"):
    """Get available styles for Room Redesign.

    `space_kind="interior"` (default) returns INTERIOR_STYLES;
    `"exterior"` returns EXTERIOR_STYLES (building facades, gardens,
    storefronts); `"commercial"` returns COMMERCIAL_STYLES (restaurant,
    retail, hotel lobby, modern office, café, gym). Frontend tab
    switches drive this via query param.
    """
    if space_kind == "exterior":
        return EXTERIOR_STYLES
    if space_kind == "commercial":
        return COMMERCIAL_STYLES
    return INTERIOR_STYLES


@router.get("/templates/exterior-styles")
async def get_exterior_styles():
    """Convenience alias — returns EXTERIOR_STYLES directly so older clients
    can hit a dedicated route without needing the `space_kind` query param."""
    return EXTERIOR_STYLES


@router.get("/templates/commercial-styles")
async def get_commercial_styles():
    """Convenience alias — returns COMMERCIAL_STYLES directly. Added
    2026-05-18 alongside the ReRoom-inspired commercial space tab."""
    return COMMERCIAL_STYLES


@router.get("/templates/style-templates")
async def get_style_templates(
    tool_type: str = "product_scene",
    category: Optional[str] = None,
    featured_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """
    Get curated style templates for Product Scene or Try-On tools.
    Returns localized names + preview thumbnails. Prompts are never exposed.
    """
    from app.services.template_prompt_service import get_templates
    templates = await get_templates(db, tool_type, category, featured_only)
    return {"templates": templates, "total": len(templates)}


@router.get("/models/list")
async def get_tryon_models(
    gender: Optional[str] = None,
    body_type: Optional[str] = None
):
    """Get available models for AI Try-On tool"""
    models = [
        {"id": mid, "preview_url": url, "gender": "female" if "female" in mid else "male"}
        for mid, url in TRYON_MODELS.items()
    ]
    if gender:
        models = [m for m in models if m["gender"] == gender]
    return models


@router.get("/voices/list")
async def get_tts_voices(
    language: Optional[str] = None,
    gender: Optional[str] = None
):
    """Get available TTS voices for Short Video tool"""
    voices = TTS_VOICES
    if language:
        voices = [v for v in voices if v["language"].startswith(language)]
    if gender:
        voices = [v for v in voices if v["gender"] == gender]
    return voices


@router.get("/styles")
async def get_video_styles():
    """Get available video styles (unified with effects API)"""
    return VIDGO_STYLES
