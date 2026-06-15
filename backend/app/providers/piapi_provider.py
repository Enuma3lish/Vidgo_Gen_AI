"""
PiAPI Provider for Wan API access.

Supported models (via PiAPI):
- Wan: wan26-txt2video (Text-to-Video)
- Wan: wan26-img2video (Image-to-Video)
- Wan: txt2img (Text-to-Image via Flux)

API Documentation: https://piapi.ai/docs/wan-api
"""
import httpx
import asyncio
import json
from typing import Dict, Any, Optional
import logging
import base64
import io
import os
import tempfile
import uuid

from app.providers.base import BaseProvider
from app.services.gcs_storage_service import get_gcs_storage
from app.core.model_registry import (
    PIAPI_MODELS,
    PIAPI_KLING_VERSIONS,
    PIAPI_MIDJOURNEY_PROCESS_MODE,
)

logger = logging.getLogger(__name__)


# Transient PiAPI upstream failures we should retry instead of surfacing
# straight to the user. Matched case-insensitively against str(error).
#  - cookie_expired: PiAPI's internal Kling session cookie lapsed; the next
#    request usually re-establishes it within ~5 s.
#  - too many requests / 10001: PiAPI's global Luma rate-limit window.
#  - task timeout / task failed (10000): occasionally caused by transient
#    Kling/Luma queue stalls; one retry frequently succeeds.
#  - upload_verify_timeout / UploadResource: timed out / upload failed:
#    PiAPI's Kling image-ingestion pipeline occasionally stalls for 3 min
#    then errors. The next attempt typically reuses a fresh upload slot.
_TRANSIENT_PIAPI_ERROR_HINTS = (
    "cookie_expired",
    "too many requests",
    "rate limit",
    "10001",
    "task timeout",
    "piapi task timeout",
    "upload_verify_timeout",
    "uploadresource: timed out",
    "kling-engine upload failed",
    "create generation task: upload image",
)


def _is_transient_piapi_error(err: BaseException | str) -> bool:
    msg = str(err).lower()
    return any(hint in msg for hint in _TRANSIENT_PIAPI_ERROR_HINTS)


# ─────────────────────────────────────────────────────────────────────────
# Polling-timeout floors (seconds)
# ─────────────────────────────────────────────────────────────────────────
# Image generation finishes well under 10 min; video generation — especially
# Kling 3.0/Omni, Veo 3.1 and Wan — routinely idles 8-15 min between PiAPI
# status transitions. These constants make "video waits longer than image" a
# STRUCTURAL guarantee instead of something every call site must remember: the
# video methods raise any caller-supplied timeout UP TO the matching floor, so
# a forgotten `timeout=` can never silently apply the image-length 600 s ceiling
# to a video job. That leak was the root cause of intermittent Kling 3.0
# "no result" aborts (e.g. the claymation T2V and most TaskType.I2V call sites
# routed video with no explicit timeout → 600 s). A caller that needs even
# longer can still pass a larger explicit `timeout` — the floor is a minimum,
# never a cap. All three are env-overridable for ops tuning without a redeploy.
IMAGE_GEN_TIMEOUT_SEC = int(os.getenv("IMAGE_GEN_TIMEOUT_SEC", "600"))
VIDEO_GEN_TIMEOUT_SEC = int(os.getenv("VIDEO_GEN_TIMEOUT_SEC", "1200"))
# Kling 3.0/Omni is the slowest tier (multimodal + audio/lip-sync); give the
# premium path users pay 750 credits for extra headroom over the generic floor.
KLING_OMNI_TIMEOUT_SEC = int(os.getenv("KLING_OMNI_TIMEOUT_SEC", "1800"))


def _video_poll_timeout(params: Dict[str, Any], floor: int = VIDEO_GEN_TIMEOUT_SEC) -> int:
    """Resolve a video job's poll timeout: the larger of the caller's explicit
    ``timeout`` and the video floor. Guarantees video ≥ floor > image (600 s).

    ``_max_wait_override`` bypasses the floor — for INTERNAL fallback legs
    only (e.g. the avatar presenter-I2V fallback), where the whole multi-step
    chain must finish inside the client's HTTP timeout. 2026-06-12: a stuck
    Seedance fallback polled the full 1200 s floor while the browser gave up
    at 15 min total, so the user saw a connection abort with no error body.
    """
    override = params.get("_max_wait_override")
    if override:
        try:
            return max(60, int(override))
        except (TypeError, ValueError):
            pass
    try:
        requested = int(params.get("timeout") or 0)
    except (TypeError, ValueError):
        requested = 0
    return max(requested, floor)


def _aspect_from_wh(width, height) -> str:
    """Map (width, height) → PiAPI aspect_ratio string ("1:1", "4:3", "16:9", etc.)
    used by Gemini-family tasks (nano-banana, seedream) that don't accept
    raw pixel sizes. Snaps to the nearest catalogue ratio so callers can keep
    passing the same width/height they use for Flux without code changes.
    """
    try:
        w = float(width) if width else 0.0
        h = float(height) if height else 0.0
    except (TypeError, ValueError):
        return "1:1"
    if w <= 0 or h <= 0:
        return "1:1"
    ratio = w / h
    candidates = {
        "1:1": 1.0,
        "4:3": 4 / 3,
        "3:4": 3 / 4,
        "16:9": 16 / 9,
        "9:16": 9 / 16,
        "3:2": 3 / 2,
        "2:3": 2 / 3,
    }
    return min(candidates.items(), key=lambda kv: abs(kv[1] - ratio))[0]


def _make_on_submit_wrapper(raw_on_submit, provider_name: str):
    """Adapt a caller's ``on_submit(task_id, provider_name)`` callback into
    the single-arg form ``_submit_and_poll`` expects. Returns None if the
    caller didn't pass one — _submit_and_poll then skips the durable record
    callback entirely (the 99% of internal callers that don't need reclaim).

    Used by image_to_video / text_to_video / kling_video_generation /
    generate_avatar so a Cloud-Run-killed foreground request can be reclaimed
    by the worker via app/models/pending_provider_task.py.
    """
    if raw_on_submit is None:
        return None

    async def _wrapped(task_id: str):
        await raw_on_submit(task_id, provider_name)

    return _wrapped


class PiAPIProvider(BaseProvider):
    """
    PiAPI Provider - Primary provider for VidGo.
    Uses PiAPI to access Wan models for T2I, I2V, T2V.
    """

    name = "piapi"
    BASE_URL = "https://api.piapi.ai/api/v1"

    def __init__(self):
        self.api_key = os.getenv("PIAPI_KEY", "")
        if not self.api_key:
            logger.warning("PIAPI_KEY not set in environment")

        self.client = httpx.AsyncClient(
            # 20 minutes per individual HTTP call. Kling Avatar / Veo 3.1 /
            # Kling Omni polling can idle for 8-15 minutes between status
            # transitions on long jobs; the previous 10-minute ceiling was
            # tripping on healthy renders that just needed more poll cycles.
            timeout=1200.0,
            headers={
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
            }
        )

    async def _retry_transient(
        self,
        op_name: str,
        coro_factory,
        *,
        attempts: int = 3,
        backoff_seconds: tuple[float, ...] = (5.0, 15.0, 30.0),
    ) -> Dict[str, Any]:
        """Run an async PiAPI submit/poll and retry on transient upstream errors.

        coro_factory is a zero-arg callable returning a fresh coroutine each
        attempt — we can't reuse a coroutine after the first await raises.
        """
        last_exc: BaseException | None = None
        for i in range(attempts):
            try:
                return await coro_factory()
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if i == attempts - 1 or not _is_transient_piapi_error(exc):
                    raise
                delay = backoff_seconds[min(i, len(backoff_seconds) - 1)]
                logger.warning(
                    "[piapi] %s transient failure (attempt %d/%d): %s — retrying in %.0fs",
                    op_name,
                    i + 1,
                    attempts,
                    str(exc)[:200],
                    delay,
                )
                await asyncio.sleep(delay)
        # Unreachable: loop either returns or re-raises last_exc on final attempt.
        assert last_exc is not None
        raise last_exc

    async def health_check(self) -> bool:
        """Check whether PiAPI is reachable without creating a billable task."""
        if not self.api_key:
            return False

        try:
            response = await self.client.get(
                f"{self.BASE_URL}/task",
                timeout=10.0
            )
            if response.status_code in [401, 403]:
                return False
            return response.status_code < 500
        except Exception as e:
            logger.error(f"PiAPI health check failed: {e}")
            return False

    def _resolve_image_url(self, url: str) -> str:
        """Convert local /static/ paths to accessible URLs for external API calls.
        Prefers PUBLIC_APP_URL (public URL) over base64 to avoid 'task input too large' errors."""
        if url.startswith("/static") or url.startswith("static"):
            static_path = "/" + url.lstrip("/")  # normalize to /static/...
            # Prefer public URL (works for all APIs including Kling try-on which rejects base64)
            public_base = os.environ.get("PUBLIC_APP_URL", "").rstrip("/")
            if public_base:
                return f"{public_base}{static_path}"
            # Fallback to base64 (works for Flux but may fail for Kling)
            import base64
            import mimetypes
            local_path = os.path.join("/app", url.lstrip("/"))
            if os.path.exists(local_path):
                mime_type = mimetypes.guess_type(local_path)[0] or "image/png"
                with open(local_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                return f"data:{mime_type};base64,{b64}"
            logger.warning(f"[PiAPI] Local file not found: {local_path}")
        return url

    async def _prepare_avatar_audio_url(self, audio_url: str, user_id: Optional[str] = None) -> str:
        """Convert avatar dubbing audio to a stable public MP3 for Kling ingestion."""
        if not audio_url or not audio_url.startswith(("http://", "https://")):
            return audio_url

        gcs = get_gcs_storage()
        if not gcs.enabled:
            return audio_url

        try:
            async with httpx.AsyncClient(timeout=120.0) as http:
                response = await http.get(audio_url, follow_redirects=True)
                response.raise_for_status()
                source_bytes = response.content

            with tempfile.TemporaryDirectory() as tmpdir:
                input_path = os.path.join(tmpdir, "input_audio")
                output_path = os.path.join(tmpdir, "avatar_audio.mp3")
                with open(input_path, "wb") as f:
                    f.write(source_bytes)

                proc = await asyncio.create_subprocess_exec(
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    input_path,
                    "-ac",
                    "1",
                    "-ar",
                    "44100",
                    "-codec:a",
                    "libmp3lame",
                    "-b:a",
                    "128k",
                    output_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()
                if proc.returncode != 0:
                    raise RuntimeError(stderr.decode("utf-8", errors="ignore") or "ffmpeg audio conversion failed")

                with open(output_path, "rb") as f:
                    normalized = f.read()

            prefix = f"users/{user_id}/avatar-audio" if user_id else "generated/avatar-audio"
            blob_name = f"{prefix}/avatar_tts_{uuid.uuid4().hex[:12]}.mp3"
            piapi_url = await self._upload_ephemeral_resource(
                normalized,
                file_name=f"avatar_tts_{uuid.uuid4().hex[:12]}.mp3",
                content_type="audio/mpeg",
            )
            if piapi_url:
                logger.warning(
                    "[PiAPI] Avatar: normalized TTS audio to PiAPI upload (%s -> %s bytes)",
                    len(source_bytes),
                    len(normalized),
                )
                return piapi_url

            public_url = gcs.upload_public(normalized, blob_name, content_type="audio/mpeg")
            logger.warning(
                "[PiAPI] Avatar: normalized TTS audio to GCS fallback (%s -> %s bytes)",
                len(source_bytes),
                len(normalized),
            )
            return public_url
        except Exception as e:
            logger.warning(f"[PiAPI] Avatar: audio normalization failed, trying GCS copy fallback: {e}")
            try:
                persisted = await gcs.persist_url(
                    audio_url,
                    media_type="audio",
                    user_id=user_id,
                    filename_hint=f"avatar_tts_{uuid.uuid4().hex[:12]}",
                )
                return persisted
            except Exception as fallback_error:
                logger.warning(f"[PiAPI] Avatar: audio GCS fallback failed, using provider URL: {fallback_error}")
                return audio_url

    async def _prepare_avatar_image_url(self, image_url: str, user_id: Optional[str] = None) -> str:
        """Normalize avatar input to a small public JPEG for Kling ingestion."""
        if not image_url or not image_url.startswith(("http://", "https://")):
            return image_url

        gcs = get_gcs_storage()
        if not gcs.enabled:
            return image_url

        try:
            async with httpx.AsyncClient(timeout=60.0) as http:
                response = await http.get(image_url, follow_redirects=True)
                response.raise_for_status()
                source_bytes = response.content

            from PIL import Image, ImageOps

            image = Image.open(io.BytesIO(source_bytes))
            image = ImageOps.exif_transpose(image)
            if image.mode in {"RGBA", "LA", "P"}:
                image = image.convert("RGBA")
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")

            image.thumbnail((512, 512), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=88, optimize=True, progressive=False)
            normalized = buffer.getvalue()

            piapi_url = await self._upload_ephemeral_resource(
                normalized,
                file_name=f"avatar_{uuid.uuid4().hex[:12]}.jpg",
                content_type="image/jpeg",
            )
            if piapi_url:
                logger.warning(
                    "[PiAPI] Avatar: normalized input image to PiAPI upload (%s -> %s bytes, %sx%s)",
                    len(source_bytes),
                    len(normalized),
                    image.width,
                    image.height,
                )
                return piapi_url

            prefix = f"users/{user_id}/avatar-inputs" if user_id else "generated/avatar-inputs"
            blob_name = f"{prefix}/avatar_{uuid.uuid4().hex[:12]}.jpg"
            public_url = gcs.upload_public(normalized, blob_name, content_type="image/jpeg")
            logger.warning(
                "[PiAPI] Avatar: normalized input image to GCS fallback (%s -> %s bytes, %sx%s)",
                len(source_bytes),
                len(normalized),
                image.width,
                image.height,
            )
            return public_url
        except Exception as e:
            logger.warning(f"[PiAPI] Avatar: image normalization failed, using original URL: {e}")
            return image_url

    async def _upload_ephemeral_resource(self, data: bytes, file_name: str, content_type: str) -> Optional[str]:
        """Upload a temporary resource to PiAPI storage and return its public URL."""
        if not self.api_key or not data:
            return None

        try:
            payload = {
                "file_name": file_name,
                "file_data": base64.b64encode(data).decode("ascii"),
            }
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    "https://upload.theapi.app/api/ephemeral_resource",
                    headers={
                        "x-api-key": self.api_key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            if response.status_code >= 400:
                logger.warning(
                    "[PiAPI] Avatar: ephemeral upload failed status=%s body=%s",
                    response.status_code,
                    response.text[:300],
                )
                return None

            body = response.json()
            url = (body.get("data") or {}).get("url")
            if not url:
                logger.warning("[PiAPI] Avatar: ephemeral upload returned no URL: %s", body)
                return None
            return url
        except Exception as e:
            logger.warning(f"[PiAPI] Avatar: ephemeral upload error for {content_type}: {e}")
            return None

    async def _fallback_avatar_video(self, image_url: str, audio_url: str, script: str) -> Dict[str, Any]:
        """Fallback when Kling Avatar cannot ingest an otherwise valid portrait."""
        # Same fix as the primary path (BUG-005): keep the spoken content out
        # of the visual prompt so the image-to-video model doesn't render any
        # of the script as on-screen text. The lip-sync step still uses the
        # full audio so the message itself is preserved.
        # 2026-06-11: clean positive prompt — do NOT name "text/captions/etc."
        # here either (naming them can make the model render them). The I2V
        # path has no negative_prompt knob, so a text-free brief is the safest.
        presenter_prompt = (
            "natural presenter talking to camera, subtle head movement, "
            "friendly expression, professional studio lighting, stable face, "
            "clean cinematic talking-head portrait, plain neutral background"
        )

        logger.warning("[PiAPI] Avatar: trying presenter image-to-video fallback")
        try:
            base_video = await self.image_to_video({
                "image_url": image_url,
                "prompt": presenter_prompt,
                "duration": 5,
                "resolution": "720P",
                # Bound this fallback leg well below the 1200 s video floor:
                # the avatar chain (Kling fail ~2 min + this + lip-sync +
                # static render) must finish inside the frontend's 15-min
                # request timeout or the user sees a bodyless abort.
                "_max_wait_override": 300,
            })
        except Exception as e:
            logger.warning("[PiAPI] Avatar: presenter image-to-video fallback raised: %s", e)
            logger.warning("[PiAPI] Avatar: falling back to static portrait+speech MP4")
            return await self._render_static_avatar_video(image_url, audio_url)

        if not base_video.get("success"):
            logger.warning(
                "[PiAPI] Avatar: presenter I2V fallback failed (%s); falling back to static portrait+speech MP4",
                base_video.get("error"),
            )
            return await self._render_static_avatar_video(image_url, audio_url)

        output = base_video.get("output") or {}
        video_url = output.get("video_url") or output.get("url")
        if not video_url or not audio_url:
            base_video.setdefault("output", output)
            if video_url:
                base_video["output"]["video_url"] = video_url
            return base_video

        lip_sync_payload = {
            "model": PIAPI_MODELS["kling_lip_sync"],
            "task_type": "lip_sync",
            "input": {
                "video_url": video_url,
                "tts_text": "",
                "tts_timbre": "",
                "tts_speed": 1,
                "local_dubbing_url": audio_url,
            },
            "config": {
                "service_mode": "public"
            }
        }
        logger.warning("[PiAPI] Avatar: trying lip-sync fallback on generated presenter video")
        try:
            # Bounded like the I2V leg above — keep the total chain inside
            # the client's request timeout.
            lip_sync = await self._submit_and_poll(lip_sync_payload, max_wait_seconds=300)
        except Exception as e:
            logger.warning("[PiAPI] Avatar: lip-sync fallback raised, returning presenter video: %s", e)
            base_video.setdefault("output", output)
            base_video["output"]["video_url"] = video_url
            base_video["output"]["avatar_fallback"] = "presenter_i2v"
            return base_video

        if lip_sync.get("success"):
            lip_output = lip_sync.get("output") or {}
            lip_video_url = lip_output.get("video_url") or lip_output.get("url")
            if not lip_video_url:
                works = lip_output.get("works") or []
                for work in works if isinstance(works, list) else []:
                    if isinstance(work, dict):
                        video = work.get("video")
                        if isinstance(video, dict) and video.get("url"):
                            lip_video_url = video["url"]
                            break
                        if isinstance(video, str):
                            lip_video_url = video
                            break
            if lip_video_url:
                lip_sync.setdefault("output", lip_output)
                lip_sync["output"]["video_url"] = lip_video_url
            return lip_sync

        logger.warning("[PiAPI] Avatar: lip-sync fallback failed, returning presenter video: %s", lip_sync.get("error"))
        base_video.setdefault("output", output)
        base_video["output"]["video_url"] = video_url
        base_video["output"]["avatar_fallback"] = "presenter_i2v"
        return base_video

    async def _render_static_avatar_video(self, image_url: str, audio_url: str) -> Dict[str, Any]:
        """Last-resort MP4 fallback with the uploaded portrait and generated speech."""
        gcs = get_gcs_storage()
        if not gcs.enabled:
            return {"success": False, "error": "Avatar fallback storage is not configured"}

        try:
            async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
                image_response = await client.get(image_url)
                image_response.raise_for_status()
                image_bytes = image_response.content

                audio_bytes = b""
                if audio_url:
                    audio_response = await client.get(audio_url)
                    audio_response.raise_for_status()
                    audio_bytes = audio_response.content

            with tempfile.TemporaryDirectory() as tmpdir:
                image_path = os.path.join(tmpdir, "avatar.jpg")
                audio_path = os.path.join(tmpdir, "speech.mp3")
                output_path = os.path.join(tmpdir, "avatar.mp4")
                with open(image_path, "wb") as f:
                    f.write(image_bytes)
                with open(audio_path, "wb") as f:
                    f.write(audio_bytes)

                if audio_bytes:
                    cmd = [
                        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-loop", "1", "-framerate", "30", "-i", image_path,
                        "-i", audio_path,
                        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
                        "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
                        "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
                        output_path,
                    ]
                else:
                    cmd = [
                        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-loop", "1", "-framerate", "30", "-i", image_path,
                        "-t", "5",
                        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
                        "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
                        "-movflags", "+faststart",
                        output_path,
                    ]

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()
                if proc.returncode != 0:
                    raise RuntimeError(stderr.decode("utf-8", errors="ignore") or "ffmpeg avatar fallback failed")

                with open(output_path, "rb") as f:
                    video_bytes = f.read()

            video_url = gcs.upload_public(
                video_bytes,
                f"generated/avatar/fallback/avatar_{uuid.uuid4().hex[:12]}.mp4",
                content_type="video/mp4",
            )
            logger.warning("[PiAPI] Avatar: rendered local portrait+audio fallback MP4 (%s bytes)", len(video_bytes))
            return {
                "success": True,
                "task_id": "local-avatar-fallback",
                "output": {
                    "video_url": video_url,
                    "avatar_fallback": "static_portrait_audio",
                },
            }
        except Exception as e:
            logger.warning("[PiAPI] Avatar: local fallback failed: %s", e)
            return {"success": False, "error": f"Avatar fallback failed: {e}"}

    # ─────────────────────────────────────────────────────────────────────────
    # TEXT TO IMAGE (using Flux via PiAPI)
    # ─────────────────────────────────────────────────────────────────────────

    async def text_to_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate image from text via PiAPI. Default model is Flux schnell;
        callers can switch by setting ``params["model"]`` to ``qwen`` or
        ``z-image`` (verified against live PiAPI catalog 2026-05-20).

        Hunyuan and Seedance T2I are NOT available on PiAPI — those are
        video-only product lines. Use ``qwen`` for Chinese-prompt strength
        and ``z-image`` for cheap/fast generation.

        Args:
            params: {
                "prompt": str,
                "negative_prompt": str (optional),
                "size": str (optional, default "1024*1024"),
                "model": str (optional; "flux" | "qwen" | "z-image"),
            }

        Returns:
            {"success": True, "task_id": str, "output": {"image_url": str}}
        """
        self._log_request("text_to_image", params)

        # Parse size
        size = params.get("size", "1024*1024")
        if "*" in size:
            width, height = map(int, size.split("*"))
        else:
            width, height = 1024, 1024

        # Model family dispatch (revised 2026-05-20 after live PiAPI probe).
        # Qwen Image and Z-Image Turbo are the only Flux-alternatives PiAPI
        # actually exposes via /api/v1/task. Hunyuan/Seedance were guesses
        # in the prior revision and silently returned default-model output.
        model_id = str(params.get("model") or "").lower().strip()
        aspect = str(params.get("aspect_ratio") or "1:1")
        if "nano-banana-pro" in model_id or "nano_banana_pro" in model_id:
            # Nano Banana Pro (Google Gemini 2.5 Flash Image Pro via PiAPI).
            # Input shape is aspect_ratio + resolution string, not w/h.
            payload = {
                "model": PIAPI_MODELS["nano_banana_pro_model"],
                "task_type": PIAPI_MODELS["nano_banana_pro_task"],
                "input": {
                    "prompt": params["prompt"],
                    "aspect_ratio": aspect,
                    "resolution": params.get("resolution") or "2K",
                },
            }
        elif "nano-banana" in model_id or "nano_banana" in model_id or "nanobanana" in model_id:
            payload = {
                "model": PIAPI_MODELS["nano_banana_2_model"],
                "task_type": PIAPI_MODELS["nano_banana_2_task"],
                "input": {
                    "prompt": params["prompt"],
                    "aspect_ratio": aspect,
                    "resolution": params.get("resolution") or "1K",
                },
            }
        elif "seedream" in model_id:
            # Seedream 5 Lite (ByteDance) — supports up to 3K, free-form aspect.
            payload = {
                "model": PIAPI_MODELS["seedream_5_lite_model"],
                "task_type": PIAPI_MODELS["seedream_5_lite_task"],
                "input": {
                    "prompt": params["prompt"],
                    "aspect_ratio": aspect,
                    "size": params.get("size") or "2K",
                },
            }
        elif "qwen" in model_id:
            payload = {
                "model": PIAPI_MODELS["qwen_t2i"],
                "task_type": "txt2img",
                "input": {
                    "prompt": params["prompt"],
                    "negative_prompt": params.get("negative_prompt", ""),
                    "width": width,
                    "height": height,
                },
            }
        elif "z-image" in model_id or "z_image" in model_id or "zimage" in model_id:
            payload = {
                "model": PIAPI_MODELS["z_image_t2i"],
                "task_type": "txt2img",
                "input": {
                    "prompt": params["prompt"],
                    "negative_prompt": params.get("negative_prompt", ""),
                    "width": width,
                    "height": height,
                },
            }
        else:
            payload = {
                "model": PIAPI_MODELS["flux_t2i"],
                "task_type": "txt2img",
                "input": {
                    "prompt": params["prompt"],
                    "negative_prompt": params.get("negative_prompt", ""),
                    "width": width,
                    "height": height,
                },
            }

        result = await self._submit_and_poll(payload)

        # Normalise the output shape so downstream callers can always read
        # ``output["image_url"]`` regardless of which model produced the result.
        # Flux returns ``image_url`` (singular); Qubico/z-image (and some other
        # Qubico models) return ``image_urls`` (an array). Without this
        # normalisation the midjourney-imagine + pattern-generate endpoints
        # see no ``image_url``, refund the credits and tell the user "no
        # result", even though the image was actually generated. Reported
        # 2026-05-22 (live https://piapi.ai/workspace/z-image runs OK but the
        # vidgo.co T2I picker reported failure).
        if result.get("success"):
            output = result.get("output") or {}
            if not output.get("image_url"):
                imgs = output.get("image_urls") or output.get("images") or []
                first: Optional[str] = None
                if isinstance(imgs, list) and imgs:
                    first_item = imgs[0]
                    if isinstance(first_item, str):
                        first = first_item
                    elif isinstance(first_item, dict):
                        first = first_item.get("url") or first_item.get("image_url")
                if first:
                    output["image_url"] = first
                    result["output"] = output
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # IMAGE TO IMAGE (using Flux via PiAPI)
    # ─────────────────────────────────────────────────────────────────────────

    async def image_to_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform image using Flux img2img via PiAPI.
        Reference: https://piapi.ai/docs/flux-api/image-to-image

        Args:
            params: {
                "image_url": str,  # Input image URL
                "prompt": str,
                "negative_prompt": str (optional),
                "strength": float (optional, 0.0-1.0, default 0.75),
                "width": int (optional, default 1024),
                "height": int (optional, default 768)
            }

        Returns:
            {"success": True, "task_id": str, "output": {"image_url": str}}
        """
        self._log_request("image_to_image", params)

        model = str(params.get("model") or "").strip().lower()
        if model in {"wan_pro", "flux_kontext", "kontext", "pro"}:
            return await self.kontext_image(params)

        # Nano Banana / Nano Banana Pro (Google Gemini 2.5 Flash Image via PiAPI)
        # also accept an input image for context-preserving edits. Schema mirrors
        # the T2I path but adds an `image_urls` array (PiAPI requires the plural
        # field, not `image`). Stronger subject preservation than Kontext for
        # commercial product placement; verified 2026-06-14.
        # `extra_image_urls` appends additional reference images (e.g. a style /
        # inspiration image for redesign) — Gemini-family models accept multiple.
        def _nano_image_urls() -> list:
            urls = [self._resolve_image_url(params["image_url"])]
            for extra in (params.get("extra_image_urls") or []):
                if extra:
                    urls.append(self._resolve_image_url(extra))
            return urls

        if "nano-banana-pro" in model or "nano_banana_pro" in model:
            aspect = params.get("aspect_ratio") or _aspect_from_wh(
                params.get("width"), params.get("height")
            )
            payload = {
                "model": PIAPI_MODELS["nano_banana_pro_model"],
                "task_type": PIAPI_MODELS["nano_banana_pro_task"],
                "input": {
                    "prompt": params["prompt"],
                    "image_urls": _nano_image_urls(),
                    "aspect_ratio": aspect,
                    "resolution": params.get("resolution") or "2K",
                },
            }
            return await self._submit_and_poll(payload)
        if "nano-banana" in model or "nano_banana" in model or "nanobanana" in model:
            aspect = params.get("aspect_ratio") or _aspect_from_wh(
                params.get("width"), params.get("height")
            )
            payload = {
                "model": PIAPI_MODELS["nano_banana_2_model"],
                "task_type": PIAPI_MODELS["nano_banana_2_task"],
                "input": {
                    "prompt": params["prompt"],
                    "image_urls": _nano_image_urls(),
                    "aspect_ratio": aspect,
                    "resolution": params.get("resolution") or "1K",
                },
            }
            return await self._submit_and_poll(payload)

        payload = {
            "model": PIAPI_MODELS["flux_i2i"],
            "task_type": "img2img",
            "input": {
                "image": self._resolve_image_url(params["image_url"]),
                "prompt": params["prompt"],
                "negative_prompt": params.get("negative_prompt", ""),
                "denoise": params.get("strength", params.get("denoise", 0.75)),
            }
        }

        return await self._submit_and_poll(payload)

    async def kontext_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Edit image using Kontext (context-aware editing) via PiAPI.
        Alternative to img2img that might be available on more plans.
        Reference: https://piapi.ai/docs/flux-api/kontext

        Args:
            params: {
                "image_url": str,  # Input image URL
                "prompt": str,  # Editing instruction
                "width": int (optional, default 1024),
                "height": int (optional, default 768),
                "steps": int (optional, default 10)
            }

        Returns:
            {"success": True, "task_id": str, "output": {"image_url": str}}
        """
        self._log_request("kontext_image", params)

        # IMPORTANT: the Qubico flux1-dev-advanced "kontext" task has a CLOSED
        # input schema (verified against piapi.ai/docs/flux-api/kontext,
        # 2026-06-03): prompt, image, width, height, seed, steps (default 28,
        # max 40) ONLY. It does NOT accept negative_prompt or guidance_scale —
        # sending them risks a 400, so we never add them here. Anti-hallucination
        # for Kontext must be expressed in the POSITIVE prompt (which is also
        # how instruction-edit models like Kontext are meant to be steered).
        payload = {
            "model": PIAPI_MODELS["flux_kontext"],
            "task_type": "kontext",
            "input": {
                "image": self._resolve_image_url(params["image_url"]),
                "prompt": params["prompt"],
                "width": params.get("width", 1024),
                "height": params.get("height", 768),
                # Vendor default is 28; callers (interior/magic) pass 28 for
                # fidelity. Clamp to the documented 1..40 range.
                "steps": max(1, min(40, int(params.get("steps", 28)))),
                "seed": -1
            }
        }

        return await self._submit_and_poll(payload)

    # ─────────────────────────────────────────────────────────────────────────
    # MIDJOURNEY IMAGINE (text-to-image)
    # ─────────────────────────────────────────────────────────────────────────

    async def midjourney_imagine(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate image via Midjourney through PiAPI.
        Reference: piapi.ai/docs/midjourney-api/imagine

        PiAPI exposes a single ``midjourney`` model alias; the underlying MJ
        version (v6/v7) is selected server-side. Cost vs latency is tuned via
        ``process_mode``: ``relax`` (cheapest, slow), ``fast`` (default), or
        ``turbo`` (most expensive, fastest).

        Args:
            params: {
                "prompt": str (required),
                "aspect_ratio": str (optional, "1:1"/"16:9"/"9:16"/...),
                "process_mode": str (optional, "relax"|"fast"|"turbo";
                    defaults to PIAPI_MIDJOURNEY_PROCESS_MODE = "fast"),
                "skip_prompt_check": bool (optional, default False),
            }

        Returns:
            {"success": True, "task_id": str, "output": {"image_url": str,
             "images": [str, ...]}}
        """
        self._log_request("midjourney_imagine", params)

        process_mode = params.get("process_mode") or PIAPI_MIDJOURNEY_PROCESS_MODE
        if process_mode not in {"relax", "fast", "turbo"}:
            process_mode = "fast"

        payload = {
            "model": PIAPI_MODELS["midjourney"],
            "task_type": "imagine",
            "input": {
                "prompt": params["prompt"],
                "aspect_ratio": params.get("aspect_ratio", "1:1"),
                "process_mode": process_mode,
                "skip_prompt_check": bool(params.get("skip_prompt_check", False)),
            },
        }

        result = await self._submit_and_poll(payload)
        output = result.get("output") or {}
        if isinstance(output, dict):
            # Midjourney returns image_url (primary) and image_urls (multi-grid
            # variants). temporary_image_urls is the time-limited CDN copy.
            image_url = (
                output.get("image_url")
                or (output.get("temporary_image_urls") or [None])[0]
                or output.get("discord_image_url")
            )
            if image_url:
                output["image_url"] = image_url
            images = output.get("image_urls") or output.get("temporary_image_urls") or []
            if images:
                output["images"] = images
            result["output"] = output
        return result

    async def _resize_image_for_trellis(self, image_url: str, max_dim: int = 1024) -> str:
        """
        Download image, resize to fit within max_dim × max_dim, re-upload to GCS.
        Returns a public URL of the resized image (or original if already small enough).
        Trellis rejects images larger than 1024×1024.
        """
        try:
            from PIL import Image as PILImage
            import io as _io

            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                resp = await client.get(image_url)
                resp.raise_for_status()
                data = resp.content

            img = PILImage.open(_io.BytesIO(data))
            w, h = img.size
            if w <= max_dim and h <= max_dim:
                return image_url  # already within bounds

            scale = max_dim / max(w, h)
            new_w, new_h = int(w * scale), int(h * scale)
            img = img.resize((new_w, new_h), PILImage.LANCZOS)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            buf = _io.BytesIO()
            img.save(buf, format="JPEG", quality=92)
            resized_bytes = buf.getvalue()

            gcs = get_gcs_storage()
            if gcs.enabled:
                blob_name = f"temp/trellis_resize_{uuid.uuid4().hex}.jpg"
                resized_url = gcs.upload_public(resized_bytes, blob_name, "image/jpeg")
                logger.info(f"[trellis_3d] Resized {w}x{h} → {new_w}x{new_h}, re-uploaded to {resized_url}")
                return resized_url

            # Fallback: base64 data URL
            b64 = base64.b64encode(resized_bytes).decode()
            return f"data:image/jpeg;base64,{b64}"

        except Exception as exc:
            logger.warning(f"[trellis_3d] Could not resize image {image_url}: {exc} — using original")
            return image_url

    async def trellis_3d(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a GLB model from a public image URL using Qubico Trellis.

        Pass `model_version`: 'v1' (default, Qubico/trellis, $0.02) or
        'v2' (Qubico/trellis2, higher fidelity, $0.10). Both are image-to-3d.

        PiAPI returns Trellis outputs as no_background_image, combined_video,
        and model_file. Normalize model_file to model_url so the provider
        router can persist and return it consistently.
        Trellis hard-limits input images to 1024×1024; we auto-resize larger images.
        """
        self._log_request("image_to_3d", params)

        model_version = str(params.get("model_version", "v1")).lower()
        model_name = (
            PIAPI_MODELS["trellis_v2"]
            if model_version in ("v2", "trellis2", "hq", "hd")
            else PIAPI_MODELS["trellis_v1"]
        )

        image_url = self._resolve_image_url(params["image_url"])
        # Trellis rejects images > 1024×1024 — auto-resize if needed
        image_url = await self._resize_image_for_trellis(image_url, max_dim=1024)

        payload = {
            "model": model_name,
            "task_type": "image-to-3d",
            "input": {
                "image": image_url,
            },
        }

        result = await self._submit_and_poll(payload)
        output = result.get("output") or {}
        if isinstance(output, dict):
            model_url = output.get("model_url") or output.get("model_file") or output.get("url")
            if model_url:
                output["model_url"] = model_url
            if output.get("no_background_image") and not output.get("image_url"):
                output["image_url"] = output["no_background_image"]
            if output.get("combined_video") and not output.get("video_url"):
                output["video_url"] = output["combined_video"]
            result["output"] = output

        return result

    # ─────────────────────────────────────────────────────────────────────────
    # VIRTUAL TRY-ON (Kling AI via PiAPI)
    # ─────────────────────────────────────────────────────────────────────────

    async def virtual_try_on(
        self,
        model_image_url: str,
        garment_image_url: Optional[str] = None,
        upper_garment_url: Optional[str] = None,
        lower_garment_url: Optional[str] = None,
        category: str = "dress",
        batch_size: int = 1,
        on_submit=None,
    ) -> Dict[str, Any]:
        """
        Virtual Try-On using Kling AI via PiAPI.
        Reference: https://piapi.ai/docs/kling-api/virtual-try-on-api

        This is a TRUE virtual try-on that overlays clothing onto a model photo,
        NOT just generating a new image from text.

        Args:
            model_image_url: Photo of person/model
            garment_image_url: Clothing image (full body garment OR routed by category)
            upper_garment_url: Upper body garment only (optional)
            lower_garment_url: Lower body garment only (optional)
            category: When only garment_image_url is given, controls which Kling
                input slot it goes into:
                  - "upper_body" → upper_input
                  - "lower_body" → lower_input
                  - "dress" / "full_body" → dress_input (default)
            batch_size: Number of output images (1-4, default 1)

        Notes:
            - Either garment_image_url OR (upper_garment_url + lower_garment_url) must be provided
            - garment_image_url is for full-body garments (dress_input in API)
            - upper/lower for separate top/bottom

        Returns:
            {"success": True, "task_id": str, "output": {"image_url": str, "images": [...]}}
        """
        self._log_request("virtual_try_on", {
            "model_image_url": model_image_url,
            "garment_image_url": garment_image_url,
            "category": category,
        })

        input_data = {
            "model_input": model_image_url,
            "batch_size": batch_size
        }

        # Add garment input - either full body or upper/lower
        if garment_image_url:
            cat = (category or "dress").lower()
            if cat == "upper_body":
                input_data["upper_input"] = garment_image_url
            elif cat == "lower_body":
                input_data["lower_input"] = garment_image_url
            else:  # dress / full_body / default
                input_data["dress_input"] = garment_image_url
        else:
            if upper_garment_url:
                input_data["upper_input"] = upper_garment_url
            if lower_garment_url:
                input_data["lower_input"] = lower_garment_url

        payload = {
            "model": PIAPI_MODELS["kling_try_on"],
            "task_type": "ai_try_on",
            "input": input_data
        }

        # on_submit captures the upstream task_id the moment it's assigned, so a
        # request killed mid-poll can be recovered by the reclaim worker.
        _on_submit = _make_on_submit_wrapper(on_submit, "piapi")
        return await self._retry_transient(
            "virtual_try_on",
            lambda: self._submit_and_poll(payload, on_submit=_on_submit),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # IMAGE TO VIDEO (Wan 2.6 via PiAPI)
    # ─────────────────────────────────────────────────────────────────────────

    async def image_to_video(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate video from image using Wan 2.6 I2V via PiAPI.

        Args:
            params: {
                "image_url": str,
                "prompt": str (optional),
                "duration": int (optional, 5/10/15, default 5),
                "resolution": str (optional, "720P" or "1080P", default "1080P"),
            }

        Returns:
            {"success": True, "task_id": str, "output": {"video_url": str}}
        """
        self._log_request("image_to_video", params)

        family = self._resolve_video_model(params.get("model"))
        model_key, _, i2v_task_key = self._VIDEO_MODEL_MAP[family]
        model_id   = PIAPI_MODELS[model_key]
        task_type  = PIAPI_MODELS[i2v_task_key]
        image_url  = self._resolve_image_url(params["image_url"])
        prompt     = params.get("prompt", "smooth natural motion")
        duration   = params.get("duration", 5)

        # PiAPI's "unified" task endpoint actually accepts a DIFFERENT input
        # shape per model family. Verified by 200-response curl probes
        # against api.piapi.ai 2026-05-22. Sending the wrong shape returns
        # either "invalid model" or "invalid request" and the entire short-
        # video flow falls through provider_router to "all providers failed".
        if family == "seedance":
            input_payload: Dict[str, Any] = {
                "prompt":       prompt,
                "image_urls":   [image_url],
                "duration":     duration,
                "aspect_ratio": params.get("aspect_ratio", "16:9"),
            }
        elif family == "hailuo":
            input_payload = {
                "prompt":       prompt,
                "image_url":    image_url,
                "model":        PIAPI_MODELS["hailuo_i2v_variant"],
                "duration":     duration,
            }
        elif family == "hunyuan":
            input_payload = {
                "prompt":       prompt,
                "image_url":    image_url,
            }
        elif family == "veo":
            # Veo 3.1 I2V (verified 2026-05-23). Input takes image_urls[]
            # like Seedance. Duration is a string with unit ("5s" / "8s").
            input_payload = {
                "prompt":          prompt,
                "image_urls":      [image_url],
                "negative_prompt": params.get("negative_prompt", ""),
                "aspect_ratio":    params.get("aspect_ratio", "16:9"),
                "duration":        f"{int(duration)}s" if isinstance(duration, (int, float)) else str(duration),
                "resolution":      params.get("resolution", "720p"),
                "generate_audio":  bool(params.get("generate_audio", False)),
            }
        else:  # "wan"
            input_payload = {
                "prompt":          prompt,
                "image":           image_url,
                "negative_prompt": params.get("negative_prompt", ""),
                "duration":        duration,
                "resolution":      params.get("resolution", "1080P"),
                "image_fidelity":  float(params.get("image_fidelity", 0.85)),
                "watermark":       False,
            }
            if params.get("motion_bucket_id") is not None:
                input_payload["motion_bucket_id"] = int(params["motion_bucket_id"])

        payload = {"model": model_id, "task_type": task_type, "input": input_payload}
        # Video floor (1200 s) applies even when the caller forgets `timeout`.
        # short-video / avatar pass 1200 explicitly; the many internal I2V call
        # sites (demo, material, rescue, uploads) previously fell through to the
        # 600 s image default and aborted long Wan/Veo renders mid-flight.
        max_wait = _video_poll_timeout(params)
        _on_submit_i2v = _make_on_submit_wrapper(params.get("on_submit"), "piapi")
        # Retry transient PiAPI stalls (queue stall, rate limit, upload timeout)
        # on the SAME model before the provider_router falls back to Vertex/Veo
        # or Pollo. Without this, a one-off Seedance/Wan hiccup silently served
        # the user a different-looking video from a different model — the main
        # cause of "I2V result is inconsistent run-to-run". attempts=2 bounds
        # the worst case to a single retry (a full-timeout retry is expensive).
        # Bounded internal fallback legs (_max_wait_override, e.g. the avatar
        # presenter fallback) must NOT retry a full-timeout attempt — that
        # doubles the leg's wall clock and blows the parent chain's budget
        # (2026-06-12: avatar fallback spent 2×300 s here before the static
        # fallback, pushing the whole chain past the client timeout).
        _attempts = 1 if params.get("_max_wait_override") else 2
        result = await self._retry_transient(
            "image_to_video",
            lambda: self._submit_and_poll(
                payload, max_wait_seconds=max_wait, on_submit=_on_submit_i2v,
            ),
            attempts=_attempts,
        )

        # Normalise the output shape — PiAPI is wildly inconsistent across
        # families. Verified field names (2026-05-22 live probe):
        #   Seedance: output["video"]            (singular, NO _url)
        #   Hailuo:   output["video_url"] or output["download_url"]
        #   Wan:      output["video_url"]
        #   Hunyuan:  output["video_url"] or output["video_urls"][0]
        # Pick the first non-empty among the known fields and promote to
        # ``video_url`` so tools.py + generation.py read uniformly. Without
        # this Seedance specifically silently returns a successful task with
        # no displayable URL → user sees "no result".
        if result.get("success"):
            output = result.get("output") or {}
            if not output.get("video_url"):
                resolved: Optional[str] = None
                # 1) Singular alternates Seedance / others use
                for k in ("video", "url", "download_url"):
                    v = output.get(k)
                    if isinstance(v, str) and v:
                        resolved = v
                        break
                # 2) Array variants
                if not resolved:
                    arrs = output.get("video_urls") or output.get("urls") or output.get("videos") or []
                    if isinstance(arrs, list) and arrs:
                        first = arrs[0]
                        if isinstance(first, str):
                            resolved = first
                        elif isinstance(first, dict):
                            resolved = first.get("url") or first.get("video_url") or first.get("video")
                if resolved:
                    output["video_url"] = resolved
                    result["output"] = output
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # TEXT TO VIDEO (Wan 2.6 via PiAPI)
    # ─────────────────────────────────────────────────────────────────────────

    # ── Video model dispatch table (2026-05-19 tier revision) ──
    # Each row picks the PiAPI (model, t2v_task, i2v_task) triplet for a
    # named video family. Aliases (lowercase keys) are normalized in
    # _resolve_video_model() below so callers can pass any common spelling.
    _VIDEO_MODEL_MAP = {
        "seedance": ("seedance_video", "seedance_t2v_task", "seedance_i2v_task"),
        "hailuo":   ("hailuo_video",   "hailuo_t2v_task",   "hailuo_i2v_task"),
        "hunyuan":  ("hunyuan_video",  "hunyuan_t2v_task",  "hunyuan_i2v_task"),
        "wan":      ("wan_video",      "wan_t2v_task",      "wan_i2v_task"),
        # Veo 3.1 Fast (Google via PiAPI). Verified stable 2026-05-23.
        # Same model+task for both T2V and I2V; presence of image_urls in the
        # input switches Google's pipeline into I2V mode automatically.
        "veo":      ("veo_31_fast_model", "veo_31_fast_task", "veo_31_fast_task"),
    }

    @staticmethod
    def _resolve_video_model(model_id: Optional[str]) -> str:
        """Map any caller-supplied alias to one of the _VIDEO_MODEL_MAP keys.
        Defaults to ``seedance`` (the new owner-approved primary), so passing
        ``None`` or an unknown alias produces a Seedance 2.0 Fast run."""
        if not model_id:
            return "seedance"
        m = str(model_id).lower().strip()
        # Strip vendor prefixes + common version suffixes so aliases like
        # "Seedance 2.0 Fast" / "seedance_v2" / "Doubao/seedance" all match.
        if "seedance" in m or "doubao" in m:
            return "seedance"
        if "hailuo" in m or "minimax" in m:
            return "hailuo"
        if "hunyuan" in m or "tencent" in m:
            return "hunyuan"
        if "veo" in m:
            return "veo"
        if m.startswith("wan") or "wan2" in m or m.startswith("wan_"):
            return "wan"
        # Unknown alias → fall back to default tier (Seedance Fast).
        return "seedance"

    async def text_to_video(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate video from text via PiAPI. Model family is selected by
        ``params["model"]`` (default: Seedance 2.0 Fast). Supported families:
        ``seedance`` (primary), ``hailuo`` (fast/cheap), ``hunyuan`` (中文),
        ``wan`` (legacy/specialty).

        Returns:
            {"success": True, "task_id": str, "output": {"video_url": str}}
        """
        self._log_request("text_to_video", params)

        family = self._resolve_video_model(params.get("model"))
        model_key, t2v_task_key, _ = self._VIDEO_MODEL_MAP[family]
        model_id   = PIAPI_MODELS[model_key]
        task_type  = PIAPI_MODELS[t2v_task_key]
        prompt     = params["prompt"]
        duration   = params.get("duration", 5)

        # Per-family input shape (see image_to_video for context).
        if family == "seedance":
            input_payload: Dict[str, Any] = {
                "prompt":       prompt,
                "duration":     duration,
                "aspect_ratio": params.get("aspect_ratio", "16:9"),
            }
        elif family == "hailuo":
            input_payload = {
                "prompt":   prompt,
                "model":    PIAPI_MODELS["hailuo_t2v_variant"],
                "duration": duration,
            }
        elif family == "hunyuan":
            input_payload = {"prompt": prompt}
        elif family == "veo":
            # Veo 3.1 Fast input shape (verified 2026-05-23). Duration is a
            # string with unit suffix ("5s" / "8s"). resolution=720p saves
            # credits; 1080p available on premium plan only.
            input_payload = {
                "prompt":          prompt,
                "negative_prompt": params.get("negative_prompt", ""),
                "aspect_ratio":    params.get("aspect_ratio", "16:9"),
                "duration":        f"{int(duration)}s" if isinstance(duration, (int, float)) else str(duration),
                "resolution":      params.get("resolution", "720p"),
                "generate_audio":  bool(params.get("generate_audio", False)),
            }
        else:  # "wan"
            input_payload = {
                "prompt":          prompt,
                "negative_prompt": params.get("negative_prompt", ""),
                "duration":        duration,
                "resolution":      params.get("resolution", "1080P"),
                "aspect_ratio":    params.get("aspect_ratio", "16:9"),
                "watermark":       False,
            }

        payload = {"model": model_id, "task_type": task_type, "input": input_payload}
        max_wait = _video_poll_timeout(params)
        _on_submit_t2v = _make_on_submit_wrapper(params.get("on_submit"), "piapi")
        result = await self._submit_and_poll(
            payload, max_wait_seconds=max_wait, on_submit=_on_submit_t2v,
        )

        # Normalise output (same logic as image_to_video).
        if result.get("success"):
            output = result.get("output") or {}
            if not output.get("video_url"):
                urls = output.get("video_urls") or output.get("urls") or []
                if isinstance(urls, list) and urls:
                    first = urls[0]
                    if isinstance(first, str):
                        output["video_url"] = first
                    elif isinstance(first, dict):
                        output["video_url"] = first.get("url") or first.get("video_url")
                elif output.get("url"):
                    output["video_url"] = output["url"]
                result["output"] = output
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # KLING VIDEO GENERATION (text-to-video + image-to-video, with version pin)
    # ─────────────────────────────────────────────────────────────────────────

    async def kling_video_generation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate video using Kling via PiAPI.
        Reference: piapi.ai/docs/kling-api/create-task

        Mode is auto-selected by presence of ``image_url``:
          - no image_url → text-to-video (uses ``aspect_ratio``)
          - image_url    → image-to-video (uses ``image_url`` + optional
                          ``image_tail_url`` for first-last frame)

        ``version`` defaults to PIAPI_KLING_VERSIONS["default"] (2.6 GA).
        Pass ``tier="flagship"`` to use 2.1-master (pro-mode only). Or pass
        an explicit ``version`` string ("1.5"/"1.6"/"2.1"/"2.1-master"/
        "2.5"/"2.6") to override.

        Args:
            params: {
                "prompt": str (required),
                "negative_prompt": str (optional, max 2500),
                "duration": int (optional, 5|10, default 5),
                "aspect_ratio": str (optional, T2V only, "16:9"|"9:16"|"1:1"),
                "image_url": str (optional, switches to I2V),
                "image_tail_url": str (optional, I2V end frame),
                "mode": str (optional, "std"|"pro"; auto "pro" for 2.1-master),
                "cfg_scale": float (optional, 0-1),
                "version": str (optional, explicit override),
                "tier": str (optional, "default"|"flagship"),
                "enable_audio": bool (optional),
            }

        Returns:
            {"success": True, "task_id": str, "output": {"video_url": str}}
        """
        self._log_request("kling_video_generation", params)

        # Version selection: explicit > tier preset > registry default
        version = params.get("version")
        if not version:
            tier = (params.get("tier") or "default").lower()
            version = PIAPI_KLING_VERSIONS.get(tier, PIAPI_KLING_VERSIONS["default"])

        # Mode selection: PiAPI Kling accepts ONLY mode={std, pro}. The
        # previous code sent mode="omni" for Kling 3.0/Omni, which PiAPI
        # silently rejected — the upstream task either fell back to a lower
        # version or produced no result, surfacing to users as "Kling 3.0
        # broken." Fix (2026-05-31): for 3.0 / omni tier we send mode="pro"
        # with version="3.0" (the standard PiAPI shape for the multimodal
        # tier), and rely on enable_audio=true to flip on lip-sync output.
        if params.get("mode"):
            mode = params["mode"]
        elif version == "2.1-master":
            mode = "pro"
        elif version == "3.0" or (params.get("tier") or "").lower() == "omni":
            mode = "pro"
        else:
            mode = "std"

        # Kling 3.0/Omni's whole point is the audio/lip-sync output, so flip
        # enable_audio on by default for that tier (callers can still pass
        # enable_audio=False if they want a silent 3.0 generation).
        if version == "3.0" and params.get("enable_audio") is None:
            params = {**params, "enable_audio": True}

        input_data: Dict[str, Any] = {
            "prompt": params["prompt"],
            "version": version,
            "mode": mode,
            "duration": int(params.get("duration", 5)),
        }
        if params.get("negative_prompt"):
            input_data["negative_prompt"] = params["negative_prompt"]
        if params.get("cfg_scale") is not None:
            input_data["cfg_scale"] = str(params["cfg_scale"])
        if params.get("enable_audio") is not None:
            input_data["enable_audio"] = bool(params["enable_audio"])

        if params.get("image_url"):
            input_data["image_url"] = self._resolve_image_url(params["image_url"])
            if params.get("image_tail_url"):
                input_data["image_tail_url"] = self._resolve_image_url(params["image_tail_url"])
        else:
            # aspect_ratio is T2V-only per Kling docs
            input_data["aspect_ratio"] = params.get("aspect_ratio", "16:9")

        payload = {
            "model": PIAPI_MODELS["kling_video"],
            "task_type": "video_generation",
            "input": input_data,
            "config": {"service_mode": "public"},
        }

        # Tier-aware floor: Kling 3.0/Omni gets the higher 1800 s ceiling since
        # it's the slowest (multimodal + audio); every other Kling version uses
        # the generic 1200 s video floor. Either way a video job can never inherit
        # the 600 s image-length default the way it did before this fix.
        _kling_floor = (
            KLING_OMNI_TIMEOUT_SEC
            if (version == "3.0" or (params.get("tier") or "").lower() == "omni")
            else VIDEO_GEN_TIMEOUT_SEC
        )
        max_wait = _video_poll_timeout(params, _kling_floor)
        _on_submit_kling = _make_on_submit_wrapper(params.get("on_submit"), "piapi")
        result = await self._retry_transient(
            "kling_video_generation",
            lambda: self._submit_and_poll(
                payload, max_wait_seconds=max_wait, on_submit=_on_submit_kling,
            ),
        )
        output = result.get("output") or {}
        if isinstance(output, dict):
            # Kling returns the video at one of several locations depending on
            # task variant and version. Expanded 2026-05-31 after a live probe
            # confirmed Kling 3.0/Omni returns its URL under output.video.resource
            # (or .resource_without_watermark) rather than the top-level
            # video_url / works[] paths used by older Kling versions.
            video_url = output.get("video_url") or output.get("url") or ""
            # Kling 3.0/Omni: output.video.resource (or _without_watermark)
            if not video_url:
                v = output.get("video")
                if isinstance(v, dict):
                    video_url = (
                        v.get("resource_without_watermark")
                        or v.get("resource")
                        or v.get("url")
                        or v.get("video_url")
                        or ""
                    )
                elif isinstance(v, str):
                    video_url = v
            # Older variant: output.works[].video.url
            if not video_url:
                works = output.get("works") or []
                if isinstance(works, list):
                    for w in works:
                        if isinstance(w, dict):
                            v = w.get("video")
                            if isinstance(v, dict) and v.get("url"):
                                video_url = v["url"]
                                break
                            if isinstance(v, dict) and v.get("resource"):
                                video_url = v["resource"]
                                break
                            if isinstance(v, str):
                                video_url = v
                                break
            # Catch-all: a 'videos' or 'video_urls' array.
            if not video_url:
                arrs = output.get("videos") or output.get("video_urls") or []
                if isinstance(arrs, list) and arrs:
                    first = arrs[0]
                    if isinstance(first, str):
                        video_url = first
                    elif isinstance(first, dict):
                        video_url = (
                            first.get("url")
                            or first.get("video_url")
                            or first.get("resource_without_watermark")
                            or first.get("resource")
                            or ""
                        )
            if video_url:
                output["video_url"] = video_url
            else:
                # Diagnostic: log the keys we DID see so we can extend the
                # normalizer next time PiAPI shifts the output shape.
                logger.warning(
                    "[PiAPI] kling_video_generation: success but no video URL — output keys=%s",
                    list(output.keys()),
                )
            result["output"] = output
        return result

    # ── Luma Dream Machine removed 2026-05-19. Use Seedance/Hailuo/Hunyuan/
    # Wan via text_to_video()/image_to_video(), or Kling Omni via
    # kling_video_generation(params={"tier": "omni"}).

    async def sora2_video_generation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate video via OpenAI Sora 2 / Sora 2 Pro through PiAPI's proxy.
        Reference: piapi.ai/sora-2 (text-to-video and image-to-video both
        supported; pro mode reaches 1080p with synchronized audio).

        Mode is auto-selected by presence of ``image_url``:
          - no image_url → text-to-video (uses ``aspect_ratio``)
          - image_url    → image-to-video

        Args:
            params: {
                "prompt": str (required, ≤2500 chars),
                "negative_prompt": str (optional),
                "duration": int (optional, 4-12, default 5),
                "aspect_ratio": str (optional, T2V only, "16:9"|"9:16"|"1:1"),
                "image_url": str (optional, switches to I2V),
                "resolution": str (optional, "720p"|"1080p"; default 1080p
                                   to match the 80-credit billing row),
                "enable_audio": bool (optional, default True),
            }

        Returns:
            {"success": True, "task_id": str, "output": {"video_url": str}}
        """
        self._log_request("sora2_video_generation", params)

        # PiAPI's sora2 tasks document duration as an enum {4, 8, 12} —
        # snap to the nearest allowed value (submit-time validation is
        # lenient, but off-enum values are unreliable at render time).
        try:
            requested = int(params.get("duration", 4))
        except (TypeError, ValueError):
            requested = 4
        duration = min((4, 8, 12), key=lambda v: abs(v - requested))

        input_data: Dict[str, Any] = {
            "prompt": params["prompt"],
            "duration": duration,
            "resolution": str(params.get("resolution") or "1080p"),
        }
        # Audio is Sora 2 Pro's headline feature; default on but let callers
        # opt out for silent renders.
        if params.get("enable_audio") is None:
            input_data["enable_audio"] = True
        else:
            input_data["enable_audio"] = bool(params["enable_audio"])
        if params.get("negative_prompt"):
            input_data["negative_prompt"] = params["negative_prompt"]

        if params.get("image_url"):
            input_data["image_url"] = self._resolve_image_url(params["image_url"])
        else:
            # aspect_ratio is T2V-only; Sora 2 derives I2V framing from the
            # input. PiAPI documents only 16:9 / 9:16 — map anything else
            # (e.g. the old 1:1 option) to 16:9.
            ar = str(params.get("aspect_ratio") or "16:9")
            input_data["aspect_ratio"] = ar if ar in ("16:9", "9:16") else "16:9"

        payload = {
            "model": PIAPI_MODELS["sora2_model"],
            "task_type": PIAPI_MODELS["sora2_task"],
            "input": input_data,
            "config": {"service_mode": "public"},
        }

        # Sora 2 Pro is in the same latency class as Veo / Kling Omni — give
        # it the Omni-length floor so a forgotten timeout never aborts a healthy
        # 10+ minute render. Caller-supplied larger timeouts still win.
        max_wait = _video_poll_timeout(params, KLING_OMNI_TIMEOUT_SEC)
        _on_submit_sora = _make_on_submit_wrapper(params.get("on_submit"), "piapi")
        result = await self._retry_transient(
            "sora2_video_generation",
            lambda: self._submit_and_poll(
                payload, max_wait_seconds=max_wait, on_submit=_on_submit_sora,
            ),
        )
        output = result.get("output") or {}
        if isinstance(output, dict):
            # Sora 2's output shape mirrors Kling 3.0 — the video URL may live at
            # any of `video_url` / `url` / `video.resource` / `videos[0].url`.
            # Mirror kling_video_generation's normalizer so the router gets the
            # standard `output.video_url` regardless of PiAPI's nesting.
            video_url = output.get("video_url") or output.get("url") or ""
            if not video_url:
                v = output.get("video")
                if isinstance(v, dict):
                    video_url = (
                        v.get("resource_without_watermark")
                        or v.get("resource")
                        or v.get("url")
                        or v.get("video_url")
                        or ""
                    )
                elif isinstance(v, str):
                    video_url = v
            if not video_url:
                arrs = output.get("videos") or output.get("video_urls") or []
                if isinstance(arrs, list) and arrs:
                    first = arrs[0]
                    if isinstance(first, str):
                        video_url = first
                    elif isinstance(first, dict):
                        video_url = (
                            first.get("url")
                            or first.get("video_url")
                            or first.get("resource_without_watermark")
                            or first.get("resource")
                            or ""
                        )
            if video_url:
                output["video_url"] = video_url
            else:
                logger.warning(
                    "[PiAPI] sora2_video_generation: success but no video URL — output keys=%s",
                    list(output.keys()),
                )
            result["output"] = output
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # INTERIOR DESIGN (using Flux img2img as fallback)
    # ─────────────────────────────────────────────────────────────────────────

    async def doodle_interior(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate interior design from image using TRUE Image-to-Image.
        Now uses Flux img2img to actually process the input image.

        Args:
            params: {
                "image_url": str,
                "prompt": str (optional),
                "style": str (optional, default "modern"),
                "room_type": str (optional, default "living_room")
            }

        Returns:
            {"success": True, "task_id": str, "output": {"image_url": str}}
        """
        self._log_request("doodle_interior", params)

        style = str(params.get("style", "modern")).replace("_", " ")
        prompt = params.get("prompt", "")
        # 2026-06-03 — space_kind-aware framing. Previously EVERY call (incl.
        # exterior building renders) was framed as "interior design … room
        # footprint … staged with furniture", which actively induced the model
        # to hallucinate interior cues onto a facade. Now exterior/commercial
        # get the correct framing + preservation constraints.
        space_kind = (params.get("space_kind") or "interior").lower()

        # Kontext has NO negative_prompt (closed schema) — so the anti-drift
        # guidance lives entirely in this POSITIVE constraint text.
        anti_drift = (
            "Do not distort, warp, bend, move, add, remove, or duplicate any walls, "
            "windows, doors, columns, beams or the camera perspective; keep their "
            "exact count, position and proportions; do not invent extra openings, "
            "rooms, levels, or architectural structures that are not in the input."
        )
        if space_kind == "exterior":
            framing = "professional architectural exterior visualization"
            constraints = (
                "Preserve the existing building massing, number of storeys, rooflines, "
                "and the position and count of windows and doors and the footprint. "
                f"Do NOT add interior elements or furniture. {anti_drift} "
                "Photorealistic architectural exterior photography, sharp focus, "
                "no people, no pets, no text, no watermark."
            )
        elif space_kind == "commercial":
            framing = "professional commercial-space visualization"
            constraints = (
                "Preserve the original walls, windows, doors, columns, ceiling structure, "
                f"and the overall floor plan. {anti_drift} "
                "Photorealistic commercial interior photography, sharp focus, "
                "no people, no pets, no text, no watermark."
            )
        else:
            room_type = params.get("room_type", "living room")
            framing = f"{room_type} interior design, professional architectural rendering"
            constraints = (
                "Preserve the original walls, windows, doors, ceiling, and room footprint. "
                f"Restyle with furniture, decor, and lighting only. {anti_drift} "
                "Photorealistic real-estate interior photography, sharp focus, "
                "no people, no humans, no faces, no hands, no pets."
            )

        full_prompt = f"{style} {framing}. {prompt}. {constraints}"

        # 2026-06-15 — high-fidelity opt-in. When the caller asks for the
        # Nano Banana Pro model, route to the Gemini-family I2I path which
        # preserves structure better than Kontext and accepts a second
        # "style reference" image (image_urls array) for inspiration-based
        # restyling. The reference image is appended so the model treats the
        # FIRST image as the room to keep and the SECOND as the look to apply.
        model_id = str(params.get("model") or "").lower()
        if "nano-banana" in model_id or "nano_banana" in model_id:
            style_reference_url = params.get("style_reference_url")
            i2i_params = {
                "image_url": params["image_url"],
                "prompt": (
                    full_prompt
                    + (
                        " Use the second provided image ONLY as a style, palette, "
                        "and material reference; do NOT copy its layout or objects — "
                        "keep the first image's room geometry."
                        if style_reference_url else ""
                    )
                ),
                "model": "nano-banana-pro" if "pro" in model_id else "nano-banana",
                "width": 1024,
                "height": 768,
                "aspect_ratio": "4:3",
                "resolution": "2K",
            }
            if style_reference_url:
                i2i_params["extra_image_urls"] = [style_reference_url]
            return await self.image_to_image(i2i_params)

        # Default: Flux Kontext I2I. steps=28 (vendor default; the old 10
        # under-sampled and cost fidelity). negative_prompt is intentionally
        # NOT passed — the kontext task rejects it.
        return await self.kontext_image({
            "image_url": params["image_url"],
            "prompt": full_prompt,
            "width": 1024,
            "height": 768,
            "steps": params.get("steps", 28),
        })

    async def controlnet_render(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Flux ControlNet render — hard-locks the output geometry to a control
        image so the model cannot drift or invent structure. The strongest
        anti-hallucination lever for interior renders (validated live against
        api.piapi.ai on 2026-06-11; controlnet-lora is supported only on
        Qubico/flux1-dev-advanced).

        params: {
          image_url: str,            # control image (floor plan / room / sketch / 3D model)
          prompt: str,
          control_type: str,         # 'depth' (default) | 'canny' | 'soft_edge' | 'openpose'
          control_strength: float,   # 0-1, higher = stricter geometry lock (default 0.6)
          negative_prompt, steps, guidance_scale, timeout
        }
        Returns {success, task_id, output: {image_url}} (temp PiAPI URL — caller
        must persist to GCS).
        """
        image_url = self._resolve_image_url(params["image_url"])
        payload = {
            "model": "Qubico/flux1-dev-advanced",
            "task_type": "controlnet-lora",
            "input": {
                "prompt": params.get("prompt", ""),
                "negative_prompt": params.get(
                    "negative_prompt",
                    "low quality, distorted, warped geometry, deformed, extra rooms, "
                    "extra windows, duplicated walls, people, text, watermark",
                ),
                "steps": int(params.get("steps", 28)),
                "guidance_scale": float(params.get("guidance_scale", 3.5)),
                "control_net_settings": [{
                    "control_type": params.get("control_type", "depth"),
                    "control_image": image_url,
                    "control_strength": float(params.get("control_strength", 0.6)),
                    "return_preprocessed_image": False,
                }],
            },
        }
        result = await self._submit_and_poll(
            payload, max_wait_seconds=int(params.get("timeout", IMAGE_GEN_TIMEOUT_SEC)),
        )
        if result.get("success"):
            out = result.get("output") or {}
            img = out.get("image_url") or (out.get("image_urls") or [None])[0] or out.get("url")
            if img:
                out["image_url"] = img
            result["output"] = out
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # BACKGROUND REMOVAL (using local rembg library)
    # ─────────────────────────────────────────────────────────────────────────

    async def background_removal(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Calls PiAPI image-toolkit background-remove — higher quality on
        # complex subjects (hair, fine edges) than local rembg. Router falls
        # through to Vertex's rembg fallback on 500.
        # NOTE: PiAPI image-toolkit expects the input key `image` (URL or
        # base64), NOT `image_url`. The wrong key returns HTTP 500.
        self._log_request("background_removal", params)

        input_block: Dict[str, Any] = {
            "image": self._resolve_image_url(params["image_url"]),
        }
        # Fine-edge / alpha-matting controls: enabled by default for the
        # product-cutout flow so hair, comb teeth, and translucent edges
        # come back with a real soft alpha rather than a 1-bit hard mask.
        # Toolkit accepts these as hints; ignored by older variants.
        if params.get("alpha_matting", True):
            input_block["alpha_matting"] = True
        if params.get("fine_detail", True):
            input_block["fine_detail"] = True

        payload = {
            "model": PIAPI_MODELS["image_toolkit"],
            "task_type": "background-remove",
            "input": input_block,
        }

        return await self._submit_and_poll(payload)

    # ─────────────────────────────────────────────────────────────────────────
    # VIDEO BACKGROUND REMOVE (Qubico video-toolkit via PiAPI)
    # ─────────────────────────────────────────────────────────────────────────

    async def video_background_remove(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Remove the background from a video via PiAPI Qubico video-toolkit.

        Added 2026-05-24 after a live probe of Qubico's video endpoints
        showed this is the only one in healthy state:
          - video-toolkit `background-remove`  → HEALTHY (returns mp4 URL)
          - video-toolkit `upscale`            → DROPPED (timed out 5 min)
          - video-toolkit `watermark-remove`   → DROPPED (endpoint missing)

        PiAPI docs (https://piapi.ai/zh-TW/video-remove-background):
          model      = "Qubico/video-toolkit"
          task_type  = "background-remove"
          input.video = public URL of the source MP4
          input.invert_output = bool (default false; true returns the
                                background instead of the subject)
          Max 20MB, 10-2000 frames, max 1024x2048 resolution.
          Pricing: $0.0004 / frame.

        Args:
            params: {
                "video_url": str,  # public URL — base64 not accepted
                "invert_output": bool (optional, default False),
            }
        Returns:
            {"success": True, "task_id": str, "output": {"video_url": str}}
        """
        self._log_request("video_background_remove", params)

        payload = {
            "model": "Qubico/video-toolkit",
            "task_type": "background-remove",
            "input": {
                "video": params["video_url"],
                "invert_output": bool(params.get("invert_output", False)),
            },
        }
        # 2026-06 reclaim hook — same contract as image_to_video et al.
        # Long inputs (up to 2000 frames) can poll for 5-10 min; a killed
        # foreground request would otherwise orphan the upstream task.
        _on_submit_bg = _make_on_submit_wrapper(params.get("on_submit"), "piapi")
        max_wait = _video_poll_timeout(params)
        return await self._submit_and_poll(
            payload, max_wait_seconds=max_wait, on_submit=_on_submit_bg,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # VIDEO STYLE TRANSFER (Wan VACE via PiAPI)
    # ─────────────────────────────────────────────────────────────────────────

    # Video-style-transfer (V2V) removed 2026-05-31 — Wan 2.1 VACE was pulled
    # from PiAPI's catalog and the Seedance first-frame fallback was a stand-in
    # rather than a real per-frame style transfer. The whole V2V surface (this
    # method, the TaskType.V2V enum, /api/v1/tools/video-transform endpoint,
    # and the frontend tab) was removed per owner directive.


    # ─────────────────────────────────────────────────────────────────────────
    # UPSCALE
    # ─────────────────────────────────────────────────────────────────────────

    async def upscale(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upscale image resolution.

        Args:
            params: {
                "image_url": str,
                "scale": int (optional, 2 or 4)
            }

        Returns:
            {"success": True, "task_id": str, "output": {"image_url": str}}
        """
        self._log_request("upscale", params)

        # Qubico/image-toolkit upscale requires the input key `image` (not
        # `image_url`). PiAPI rejects the wrong key with a 500. Also normalize
        # backend-local /static/ paths so PiAPI can fetch the source.
        payload = {
            "model": PIAPI_MODELS["image_toolkit"],
            "task_type": "upscale",
            "input": {
                "image": self._resolve_image_url(params["image_url"]),
                "scale": params.get("scale", 2),
            }
        }

        # 2026-06 reclaim hook — image-toolkit upscale can stall to 5 min on
        # bad PiAPI days. Most calls finish in seconds, but the foreground
        # request is on the hook for whatever the upstream returns; the hook
        # lets the worker recover those rare long jobs.
        _on_submit_up = _make_on_submit_wrapper(params.get("on_submit"), "piapi")
        return await self._submit_and_poll(payload, on_submit=_on_submit_up)

    # ─────────────────────────────────────────────────────────────────────────
    # TEXT TO SPEECH (F5-TTS via PiAPI)
    # ─────────────────────────────────────────────────────────────────────────

    # ─── OpenAI-compatible TTS via PiAPI (tts-1) — primary path ────────────
    # PiAPI's Qubico/tts F5-TTS model has been returning "internal server error
    # 500" on every call for several days (task creates fine, fails at worker
    # level: `logs: ["internal server error\nstatus code: 500\nfailed to do
    # request"]`). Their OpenAI-compatible /v1/audio/speech endpoint with
    # tts-1 works reliably, supports 6 voices, no ref_audio required, and
    # returns the MP3 bytes synchronously. We use it as the primary TTS path
    # and only fall through to F5-TTS when the caller explicitly wants voice
    # cloning (ref_audio supplied AND not the dead default).

    OPENAI_COMPAT_TTS_URL = "https://api.piapi.ai/v1/audio/speech"
    OPENAI_VOICE_DEFAULT = "alloy"
    OPENAI_VOICES = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}

    async def _tts_via_openai_compat(self, text: str, voice: str | None) -> Dict[str, Any]:
        """Call PiAPI's OpenAI-compatible /v1/audio/speech, persist the MP3
        bytes to GCS, and return a result shape that matches the rest of the
        TTS pipeline ({success, output:{audio_url, duration_estimate_s}})."""
        v = (voice or self.OPENAI_VOICE_DEFAULT).lower()
        if v not in self.OPENAI_VOICES:
            v = self.OPENAI_VOICE_DEFAULT
        payload = {"model": PIAPI_MODELS["tts_openai"], "input": text, "voice": v}
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.post(
                    self.OPENAI_COMPAT_TTS_URL,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
            if r.status_code != 200:
                detail = r.text[:300]
                logger.error("[PiAPI] tts-1 HTTP %d: %s", r.status_code, detail)
                return {"success": False, "error": f"tts-1 returned HTTP {r.status_code}: {detail}"}
            audio_bytes = r.content
            if not audio_bytes or len(audio_bytes) < 1024:
                return {"success": False, "error": "tts-1 returned empty audio"}
            # Persist to GCS so the dubbing ffmpeg mux can fetch it later.
            gcs = get_gcs_storage()
            blob_name = f"generated/audio/tts_{uuid.uuid4().hex[:12]}.mp3"
            audio_url: Optional[str]
            if gcs.enabled:
                audio_url = gcs.upload_public(data=audio_bytes, blob_name=blob_name, content_type="audio/mpeg")
            else:
                # Local dev fallback — caller must be running under PUBLIC_APP_URL
                tmp = os.path.join("/app/static/generated", os.path.basename(blob_name))
                os.makedirs(os.path.dirname(tmp), exist_ok=True)
                with open(tmp, "wb") as f:
                    f.write(audio_bytes)
                public_base = os.environ.get("PUBLIC_APP_URL", "").rstrip("/")
                audio_url = f"{public_base}/static/generated/{os.path.basename(blob_name)}" if public_base else f"/static/generated/{os.path.basename(blob_name)}"
            logger.info("[PiAPI] tts-1 success: %d bytes → %s", len(audio_bytes), audio_url)
            return {
                "success": True,
                "task_id": f"tts1-{uuid.uuid4().hex[:8]}",
                "output": {"audio_url": audio_url, "voice": v, "model": "tts-1"},
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("[PiAPI] tts-1 exception: %s", exc)
            return {"success": False, "error": f"tts-1 exception: {exc}"}

    async def text_to_speech(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate speech audio from text. PiAPI exposes two TTS surfaces:

        1. OpenAI-compatible /v1/audio/speech with `tts-1` — synchronous MP3
           response, 6 fixed voices (alloy/echo/fable/onyx/nova/shimmer),
           supports en/zh/ja/ko/es and many more, no reference audio required.
        2. Qubico/tts F5-TTS via the async /api/v1/task endpoint — zero-shot
           voice cloning from a reference audio clip. Currently broken
           upstream (worker returns 500 on every call as of 2026-05-09).

        Routing rule:
          - If `ref_audio` is supplied AND non-empty AND voice cloning is
            actually required → use F5-TTS, fall back to tts-1 on 500.
          - Otherwise → use tts-1 directly (the common case for video_dubbing
            where the user just wants a localized voiceover, not a clone).

        Args:
            params: {
                "text": str,
                "ref_audio": str | None,   # voice-clone reference URL
                "ref_text": str | None,    # transcript of the reference clip
                "voice": str | None,       # tts-1 voice id (alloy/echo/...)
            }

        Returns:
            {"success": True, "task_id": str, "output": {"audio_url": str}}
        """
        self._log_request("text_to_speech", params)

        text = params.get("text") or ""
        ref_audio = (params.get("ref_audio") or "").strip()
        voice_hint = params.get("voice") or params.get("voice_id")

        # Path A: caller wants voice cloning → F5-TTS, with tts-1 fallback.
        # _submit_and_poll RAISES on task failure (not returns success=False),
        # so we have to wrap it. Auth errors get surfaced; everything else
        # (notably the persistent upstream 500) falls through to tts-1.
        if ref_audio:
            payload = {
                "model": PIAPI_MODELS["tts_f5"],
                "task_type": "zero-shot",
                "input": {"gen_text": text, "ref_audio": ref_audio},
                "config": {"service_mode": "public"},
            }
            ref_text = params.get("ref_text")
            if ref_text:
                payload["input"]["ref_text"] = ref_text

            err_text = ""
            try:
                result = await self._submit_and_poll(payload)
                if isinstance(result, dict) and result.get("success") is True:
                    return result
                if isinstance(result, dict):
                    err_text = (result.get("error") or result.get("message") or "")
            except Exception as exc:  # noqa: BLE001
                err_text = str(exc)

            err_text_lower = err_text.lower()
            if any(tok in err_text_lower for tok in ("unauthorized", "forbidden", "permission", "403", "401", "model_not_authorized")):
                return {
                    "success": False,
                    "error": (
                        "Voice cloning model is not enabled on this PiAPI account. "
                        "Enable F5-TTS / voice-clone access in the PiAPI dashboard, "
                        "or omit ref_audio to use the built-in default voice."
                    ),
                }
            logger.warning("[PiAPI] F5-TTS failed (%s); falling back to tts-1", err_text[:160])
            return await self._tts_via_openai_compat(text, voice_hint)

        # Path B (default): no voice cloning needed → tts-1.
        return await self._tts_via_openai_compat(text, voice_hint)

    # ─────────────────────────────────────────────────────────────────────────
    # AVATAR (Kling Avatar via PiAPI — talking head video)
    # ─────────────────────────────────────────────────────────────────────────

    async def generate_avatar(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate talking-head avatar video using Kling Avatar via PiAPI.
        Reference: https://piapi.ai/docs/kling-api/kling-avatar-api

        Two modes:
        1. With audio URL (local_dubbing_url) — lip-syncs to provided audio
        2. With text prompt only — Kling generates audio internally

        Pipeline: If script text is provided without audio, we first try F5-TTS
        to generate audio, then pass it to Kling Avatar. If TTS fails, we fall
        back to Kling's built-in prompt-to-audio.

        Args:
            params: {
                "image_url": str,          # Avatar image (person photo)
                "script": str,             # Text script for the avatar to speak
                "language": str,           # Language code (optional)
                "voice_id": str,           # Voice reference audio URL (optional)
                "duration": int,           # Target duration in seconds (optional)
                "audio_url": str,          # Pre-generated audio URL (optional)
                "mode": str,               # "std" or "pro" (optional, default "std")
            }

        Returns:
            {"success": True, "task_id": str, "output": {"video_url": str}}
        """
        self._log_request("generate_avatar", params)

        image_url = self._resolve_image_url(params["image_url"])
        image_url = await self._prepare_avatar_image_url(image_url, params.get("user_id"))
        script = params.get("script") or params.get("text") or params.get("prompt") or ""
        audio_url = params.get("audio_url") or params.get("local_dubbing_url")
        mode = params.get("mode", "std")

        # Step 1: Kling Avatar REQUIRES local_dubbing_url (audio file).
        # Prompt-only mode is NOT supported. Generate audio via TTS-1.
        #
        # voice_id arrives as one of the 6 OpenAI voices (alloy/echo/fable/
        # onyx/nova/shimmer) — see a2e_service.A2E_VOICES. Pass it through
        # as `voice`, NOT `ref_audio`. The old code stuck it into ref_audio,
        # which forced F5-TTS (zero-shot voice cloning), which 500'd, and
        # the fallback to tts-1 then coerced the voice to default "alloy".
        # Result: every Chinese avatar spoke with a heavy English accent
        # because alloy is English-leaning. Reported 2026-05-22.
        if script and not audio_url:
            voice_hint = params.get("voice_id") or ""
            logger.info("[PiAPI] Avatar: generating speech via tts-1 (voice=%s)", voice_hint or "alloy")
            try:
                tts_result = await self.text_to_speech({
                    "text": script,
                    "voice": voice_hint,
                })
            except Exception as e:
                logger.warning("[PiAPI] Avatar: TTS raised, using visual fallback: %s", e)
                return await self._fallback_avatar_video(image_url, "", script)
            if tts_result.get("success"):
                audio_url = tts_result.get("output", {}).get("audio_url")
                logger.info(f"[PiAPI] Avatar: TTS audio ready: {audio_url[:80] if audio_url else 'None'}")
            else:
                tts_error = tts_result.get("error", "TTS failed")
                logger.warning("[PiAPI] Avatar: TTS failed, using visual fallback: %s", tts_error)
                return await self._fallback_avatar_video(image_url, "", script)

        if not audio_url:
            return {"success": False, "error": "Audio generation failed. Please provide an audio URL or script text."}

        audio_url = await self._prepare_avatar_audio_url(audio_url, params.get("user_id"))

        # Step 2: Build Kling Avatar request (requires local_dubbing_url).
        # NOTE: Kling's `prompt` field controls the *visual scene*, not the
        # spoken content. The script reaches Kling via `local_dubbing_url`
        # (the TTS audio) and must NEVER appear in `prompt` (BUG-005: it got
        # rendered as on-screen captions).
        #
        # 2026-06-11: the POSITIVE prompt must also not enumerate "no text /
        # no captions / no subtitles". Naming those tokens in a generative
        # prompt frequently backfires and makes the model render that very
        # text on screen (the "don't think of an elephant" failure) — the
        # likely cause of stray on-screen words reported on subscriber
        # avatars. Keep the positive prompt a clean visual brief that never
        # mentions text, and put the exclusions ONLY in negative_prompt.
        input_data: Dict[str, Any] = {
            "image_url": image_url,
            "local_dubbing_url": audio_url,
            "mode": mode,
            "batch_size": params.get("batch_size", 1),
            "prompt": (
                "A person speaking naturally and directly to the camera, "
                "subtle lip-sync and gentle head movement, friendly "
                "professional expression, soft studio lighting, plain "
                "neutral background, clean cinematic talking-head portrait"
            ),
            "negative_prompt": (
                "text, captions, subtitles, watermark, logo, on-screen "
                "graphics, written words, overlays"
            ),
        }

        payload = {
            "model": PIAPI_MODELS["kling_avatar"],
            "task_type": "avatar",
            "input": input_data,
            "config": {
                "service_mode": "public"
            }
        }

        logger.warning(
            "[PiAPI] Avatar: sending to Kling (image_host=%s, audio_host=%s, mode=%s)",
            httpx.URL(image_url).host if image_url.startswith(("http://", "https://")) else "local",
            httpx.URL(audio_url).host if audio_url.startswith(("http://", "https://")) else "local",
            mode,
        )
        max_wait = int(params.get("timeout") or 600)
        # Retry transient Kling Avatar failures (upload_verify_timeout,
        # kling-engine upload failed, queue stalls — all in the transient hint
        # list) on the SAME path before degrading. Previously ANY failure
        # dropped straight to _fallback_avatar_video, so a one-off ingestion
        # stall left the user with a generic presenter clip or a static
        # portrait+audio MP4 instead of a real lip-synced avatar — the main
        # cause of "avatar is sometimes just a still image". attempts=2 keeps
        # the extra wait bounded to one retry.
        # Forward the durable-record callback (used by long-poll endpoints
        # to persist the upstream task_id so a killed request can be reclaimed).
        # See module-level _make_on_submit_wrapper docstring for the contract.
        _on_submit_wrapped = _make_on_submit_wrapper(params.get("on_submit"), "piapi")

        try:
            result = await self._retry_transient(
                "generate_avatar",
                lambda: self._submit_and_poll(
                    payload, max_wait_seconds=max_wait, on_submit=_on_submit_wrapped,
                ),
                attempts=2,
            )
        except Exception as e:
            logger.warning("[PiAPI] Avatar: dedicated Kling Avatar raised, using fallback: %s", e)
            return await self._fallback_avatar_video(image_url, audio_url, script)

        if not result.get("success"):
            logger.warning("[PiAPI] Avatar: dedicated Kling Avatar failed, using fallback: %s", result.get("error"))
            return await self._fallback_avatar_video(image_url, audio_url, script)

        # Normalize output: Kling returns video in output
        if result.get("success"):
            output = result.get("output", {})
            video_url = output.get("video_url") or output.get("url") or ""
            if not video_url:
                # Find the video in Kling's nested works[] structure. Per the
                # official Get-Task schema (https://piapi.ai/docs/kling-api/get-task)
                # a completed work's video lives at works[].video.resource /
                # .resource_without_watermark — there is NO works[].video.url
                # field. The old code only checked .url, so a successfully
                # rendered Kling Avatar returned no URL and the caller wrongly
                # degraded to the presenter / static-portrait fallback. Prefer
                # the watermark-free resource (we apply our own watermark later).
                works = output.get("works", [])
                if works and isinstance(works, list):
                    for w in works:
                        if not isinstance(w, dict):
                            continue
                        v = w.get("video")
                        if isinstance(v, dict):
                            cand = (
                                v.get("resource_without_watermark")
                                or v.get("resource")
                                or v.get("url")
                                or v.get("video_url")
                            )
                            if cand:
                                video_url = cand
                                break
                        elif isinstance(v, str) and v:
                            video_url = v
                            break
            if video_url:
                result["output"]["video_url"] = video_url

        return result

    # ─────────────────────────────────────────────────────────────────────────
    # INTERNAL METHODS
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_task_error(task_data: Dict[str, Any]) -> str:
        """Pull a human-readable failure reason out of a PiAPI Get-Task body.

        Per the official response schema
        (https://piapi.ai/docs/kling-api/get-task) ``data.error`` is an OBJECT
        ``{code, raw_message, message, detail}`` \u2014 NOT a string \u2014 and the
        worker-level reason for some failures (e.g. the F5-TTS "internal server
        error 500") only surfaces in ``data.logs``. The old code did
        ``task_data.get("error", "Unknown error")`` and raised the raw dict, so
        logs/users saw ``{'code': ..., 'message': ...}`` and the clean message
        was buried (and ``_is_transient_piapi_error`` had to match against the
        stringified dict). Extract the best available string instead.
        """
        err = task_data.get("error")
        if isinstance(err, dict):
            msg = err.get("message") or err.get("raw_message")
            if msg:
                return str(msg)
        elif isinstance(err, str) and err:
            return err
        # Fall back to the logs array (worker-level failure detail).
        logs = task_data.get("logs")
        if isinstance(logs, list) and logs:
            parts = []
            for item in logs:
                if isinstance(item, str) and item:
                    parts.append(item)
                elif isinstance(item, dict):
                    m = item.get("message") or item.get("msg")
                    if m:
                        parts.append(str(m))
            if parts:
                return "; ".join(parts)
        return "Unknown error"

    async def _submit_and_poll(
        self,
        payload: Dict[str, Any],
        max_wait_seconds: int = IMAGE_GEN_TIMEOUT_SEC,
        on_submit=None,
    ) -> Dict[str, Any]:
        """Submit task and poll for result.

        ``max_wait_seconds`` caps total polling time. Default is the image
        floor (600 s); the video paths (image_to_video / text_to_video /
        kling_video_generation) resolve their own higher floor via
        ``_video_poll_timeout`` — 1200 s generic, 1800 s for Kling 3.0/Omni —
        so long Kling Omni / Veo / Wan jobs aren't aborted mid-render.

        ``on_submit`` is an optional async callback ``f(task_id: str)``
        fired the moment we capture the upstream task id, BEFORE polling
        starts. Used by long-poll endpoints (avatar / Veo / Kling Omni)
        to durably record the task id in `pending_provider_tasks` so a
        request-killed / Cloud-Run-evicted poll can be reclaimed later by
        the worker (see app/models/pending_provider_task.py and
        app/worker.py reclaim_pending_provider_tasks_task).
        """
        # Submit task
        try:
            response = await self.client.post(
                f"{self.BASE_URL}/task",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            self._log_response(payload.get("task_type", "unknown"), False, str(e))
            raise Exception(f"PiAPI request failed: {e.response.text}")
        except Exception as e:
            self._log_response(payload.get("task_type", "unknown"), False, str(e))
            raise

        # Handle different response formats
        if "data" in data and "task_id" in data["data"]:
            task_id = data["data"]["task_id"]
        elif "task_id" in data:
            task_id = data["task_id"]
        else:
            # Check if result is immediate
            if "output" in data or "result" in data:
                output = data.get("output") or data.get("result")
                self._log_response(payload.get("task_type", "unknown"), True)
                return {
                    "success": True,
                    "task_id": data.get("id", "immediate"),
                    "output": output
                }
            raise Exception(f"Invalid PiAPI response: {data}")

        # Fire the durable-record callback NOW, before polling. If the
        # callback itself errors we still poll — losing the reclaim record
        # is preferable to dropping a live upstream job.
        if on_submit is not None and task_id:
            try:
                await on_submit(task_id)
            except Exception as cb_exc:
                logger.warning(
                    "[PiAPI] on_submit callback for task %s raised: %s",
                    task_id, cb_exc,
                )

        # Poll for result. 5-second cadence, so attempts ≈ seconds / 5.
        max_attempts = max(1, max_wait_seconds // 5)
        for attempt in range(max_attempts):
            try:
                status_response = await self.client.get(
                    f"{self.BASE_URL}/task/{task_id}"
                )
                status_data = status_response.json()

                # Handle different response structures
                if "data" in status_data:
                    task_data = status_data["data"]
                else:
                    task_data = status_data

                status = task_data.get("status", "").lower()

                if status in ["completed", "success", "done"]:
                    output = task_data.get("output") or task_data.get("result", {})
                    self._log_response(payload.get("task_type", "unknown"), True)
                    return {
                        "success": True,
                        "task_id": task_id,
                        "output": output
                    }
                elif status in ["failed", "error"]:
                    error_msg = self._extract_task_error(task_data)
                    self._log_response(payload.get("task_type", "unknown"), False, error_msg)
                    raise Exception(error_msg)

                # Still processing, wait and retry
                await asyncio.sleep(5)

            # A transient blip while POLLING (network drop, 5xx error body that
            # isn't valid JSON, connection reset) must NOT kill an otherwise
            # healthy upstream task — the generation is still running on PiAPI's
            # side. Swallow these and keep polling. Note: the deliberate
            # ``raise Exception(error_msg)`` for a *failed task* above is a bare
            # Exception and is intentionally NOT caught here, so genuine task
            # failures still propagate to the caller (and _retry_transient).
            except (httpx.HTTPStatusError, httpx.TransportError, json.JSONDecodeError) as e:
                if attempt < max_attempts - 1:
                    logger.warning(
                        "[PiAPI] poll transient error for task %s (attempt %d/%d): %s — continuing",
                        task_id,
                        attempt + 1,
                        max_attempts,
                        str(e)[:160],
                    )
                    await asyncio.sleep(5)
                    continue
                raise Exception(f"Failed to poll task status: {e}")

        self._log_response(payload.get("task_type", "unknown"), False, "Task timeout")
        raise Exception("PiAPI task timeout - generation took too long")

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
