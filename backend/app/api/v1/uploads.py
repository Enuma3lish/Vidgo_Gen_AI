"""
Subscriber Material Upload API

Subscribers can upload their own images/videos and trigger real AI API calls.
Results are returned without watermarks and can be downloaded.

Endpoints:
- POST /uploads/material                  - Upload a file and trigger generation
- GET  /uploads/my-uploads                - List user's upload history
- GET  /uploads/{upload_id}               - Get status / result of a specific upload
- GET  /uploads/{upload_id}/download      - Download result (no watermark)
- GET  /uploads/models/{tool_type}        - List available models for a tool (with credit costs)
"""
import asyncio
import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import httpx

from app.api.deps import get_db, get_current_active_user, is_subscribed_user
from app.models.user import User
from app.models.user_upload import UserUpload, UploadStatus
from app.core.config import get_settings
from app.core.upload_validation import (
    extension_for_content_type,
    image_dimension_rules_for_tool,
    validate_uploaded_content,
)
from app.providers.provider_router import get_provider_router, TaskType
from app.services.gcs_storage_service import get_gcs_storage
from app.services.email_service import send_admin_tool_failure_email

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/uploads", tags=["uploads"])
provider_router = get_provider_router()
_UPLOAD_GENERATION_TASKS: set[asyncio.Task] = set()

# Generic, user-facing message returned when an upload-triggered generation
# fails for an internal reason. Admin is notified via email separately.
GENERIC_UPLOAD_FAILURE_MESSAGE = (
    "This tool is temporarily unavailable. Please try again later."
)

# ─────────────────────────────────────────
# Model / credit configuration
# ─────────────────────────────────────────

# Base credit cost per tool type (VidGo 2.0 spec — 2026-05)
# Image tools = 1 (standard) / 3 (premium); Video tools = 10 (std) / 30 (pro);
# Video extend/repair = 15.
TOOL_BASE_CREDITS = {
    "background_removal": 1,
    "product_scene": 1,
    "try_on": 10,
    "room_redesign": 1,
    "short_video": 10,
    "video_transform": 15,
    "ai_avatar": 30,
    "pattern_generate": 1,
    "effect": 1,
}

# Available models per tool type with their credit multipliers
# Multipliers are chosen so default×multiplier lands on the spec tier
# (1→3 for premium image, 10→30 for premium video).
TOOL_MODELS = {
    "background_removal": [
        {"id": "default", "name": "Standard", "name_zh": "標準", "credit_multiplier": 1},
    ],
    "product_scene": [
        {"id": "default", "name": "Standard (Flux)", "name_zh": "標準 (Flux)", "credit_multiplier": 1},
        {"id": "wan_pro", "name": "Pro (Flux Kontext)", "name_zh": "進階 (Flux Kontext)", "credit_multiplier": 3},
    ],
    "try_on": [
        {"id": "default", "name": "Standard (Kling v1.5)", "name_zh": "標準 (Kling v1.5)", "credit_multiplier": 1},
        {"id": "kling_v2", "name": "Premium (Kling v2)", "name_zh": "精緻 (Kling v2)", "credit_multiplier": 3},
    ],
    "room_redesign": [
        {"id": "default", "name": "Standard (Flux)", "name_zh": "標準 (Flux)", "credit_multiplier": 1},
        {"id": "wan_pro", "name": "Pro (Flux Kontext)", "name_zh": "進階 (Flux Kontext)", "credit_multiplier": 3},
    ],
    "short_video": [
        {"id": "pixverse_v4.5", "name": "Fast (Pixverse v4.5)", "name_zh": "快速 (Pixverse v4.5)", "credit_multiplier": 1},
        {"id": "pixverse_v5", "name": "Creative (Pixverse v5)", "name_zh": "創意 (Pixverse v5)", "credit_multiplier": 1.5},
        {"id": "kling_v2", "name": "High Quality (Kling v2)", "name_zh": "高品質 (Kling v2)", "credit_multiplier": 3},
        {"id": "luma_ray2", "name": "Cinematic (Luma Ray2)", "name_zh": "電影級 (Luma Ray2)", "credit_multiplier": 3},
    ],
    "video_transform": [
        {"id": "default", "name": "Standard (Wan VACE)", "name_zh": "標準 (Wan VACE)", "credit_multiplier": 1},
    ],
    "ai_avatar": [
        {"id": "default", "name": "Standard", "name_zh": "標準", "credit_multiplier": 1},
    ],
    "pattern_generate": [
        {"id": "default", "name": "Standard (Flux)", "name_zh": "標準 (Flux)", "credit_multiplier": 1},
        {"id": "wan_pro", "name": "Pro (Flux Kontext)", "name_zh": "進階 (Flux Kontext)", "credit_multiplier": 3},
    ],
    "effect": [
        {"id": "default", "name": "Standard (Flux I2I)", "name_zh": "標準 (Flux I2I)", "credit_multiplier": 1},
        {"id": "wan_pro", "name": "Pro (Flux Kontext)", "name_zh": "進階 (Flux Kontext)", "credit_multiplier": 3},
    ],
}

MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
PRODUCT_SCENE_PROMPT_MAX_CHARS = 500

IMAGE_UPLOAD_TOOLS = {
    "background_removal",
    "product_scene",
    "try_on",
    "room_redesign",
    "short_video",
    "ai_avatar",
    "pattern_generate",
    "effect",
}
VIDEO_UPLOAD_TOOLS = {"video_transform"}

UPLOAD_DIR = "/app/static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

DOWNLOAD_MEDIA_TYPES_BY_EXTENSION = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".m4v": "video/mp4",
}
DOWNLOAD_EXTENSIONS_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
}


# ─────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────

class ModelInfo(BaseModel):
    id: str
    name: str
    name_zh: str
    credit_cost: int
    credit_multiplier: float


class ToolModelsResponse(BaseModel):
    tool_type: str
    models: List[ModelInfo]


class UploadResponse(BaseModel):
    upload_id: str
    status: str
    credits_used: int
    message: str


class UploadStatusResponse(BaseModel):
    upload_id: str
    tool_type: str
    status: str
    selected_model: Optional[str]
    credits_used: int
    file_url: Optional[str] = None
    result_url: Optional[str] = None
    result_video_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

def _calculate_credit_cost(tool_type: str, model_id: str) -> int:
    """Calculate total credits for a generation."""
    base = TOOL_BASE_CREDITS.get(tool_type, 10)
    models = TOOL_MODELS.get(tool_type, [])
    multiplier = 1.0
    for m in models:
        if m["id"] == model_id:
            multiplier = m["credit_multiplier"]
            break
    return max(1, int(base * multiplier))


def _is_valid_model(tool_type: str, model_id: str) -> bool:
    """Return whether the requested model is available for the given tool."""
    if model_id == "default":
        return tool_type in TOOL_MODELS
    return any(model["id"] == model_id for model in TOOL_MODELS.get(tool_type, []))


def _deduct_upload_credits(user: User, amount: int) -> dict[str, int]:
    """Deduct upload credits and return the exact bucket breakdown."""
    remaining = amount
    breakdown = {"subscription_credits": 0, "purchased_credits": 0, "bonus_credits": 0}

    for field in breakdown:
        available = max(0, getattr(user, field) or 0)
        used = min(available, remaining)
        setattr(user, field, available - used)
        breakdown[field] = used
        remaining -= used
        if remaining == 0:
            break

    if remaining:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits. This generation costs {amount} credits."
        )

    return breakdown


def _refund_upload_credits(user: User, breakdown: dict[str, int]) -> None:
    """Restore credits deducted by upload_and_generate when generation fails."""
    for field, amount in breakdown.items():
        setattr(user, field, (getattr(user, field) or 0) + amount)


def _normalize_upload_prompt(tool_type: str, prompt: Optional[str]) -> Optional[str]:
    """Normalize bounded prompts before storing or sending to providers."""
    if prompt is None:
        return None

    cleaned = " ".join(prompt.split())
    if tool_type == "product_scene" and len(cleaned) > PRODUCT_SCENE_PROMPT_MAX_CHARS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product scene prompt must be {PRODUCT_SCENE_PROMPT_MAX_CHARS} characters or fewer.",
        )
    return cleaned or None


def _load_upload_extra_params(upload: UserUpload) -> dict:
    if not upload.extra_params:
        return {}
    try:
        data = json.loads(upload.extra_params)
        return data if isinstance(data, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


async def _refund_failed_upload(
    db: AsyncSession,
    upload: UserUpload,
    credit_breakdown: dict[str, int],
) -> None:
    """Refund a failed background generation exactly once."""
    extra_params = _load_upload_extra_params(upload)
    if extra_params.get("credits_refunded"):
        return

    result = await db.execute(select(User).where(User.id == upload.user_id))
    user = result.scalars().first()
    if not user:
        logger.error("Cannot refund failed upload %s: user not found", upload.id)
        return

    _refund_upload_credits(user, credit_breakdown)
    extra_params["credits_refunded"] = True
    upload.extra_params = json.dumps(extra_params)
    await db.commit()


async def _trigger_generation_background(
    upload_id: str,
    file_url: str,
    tool_type: str,
    model_id: str,
    prompt: str,
    credit_breakdown: dict[str, int],
) -> None:
    """Run provider generation after the upload response has been returned."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(UserUpload).where(UserUpload.id == uuid.UUID(upload_id)))
        upload = result.scalars().first()
        if not upload:
            logger.error("Background generation upload not found: %s", upload_id)
            return

        try:
            await _trigger_generation(upload, file_url, tool_type, model_id, prompt, db)
        except Exception as exc:
            logger.exception("Background generation failed for upload %s", upload_id)
            upload.status = UploadStatus.FAILED
            upload.error_message = GENERIC_UPLOAD_FAILURE_MESSAGE
            await db.commit()
            try:
                user_email_result = await db.execute(select(User).where(User.id == upload.user_id))
                user_for_alert = user_email_result.scalars().first()
                user_email = getattr(user_for_alert, "email", None)
            except Exception:
                user_email = None
            try:
                await send_admin_tool_failure_email(
                    tool_name=f"upload:{tool_type}",
                    user_email=user_email,
                    error=exc,
                    request_id=upload_id,
                    extra_context={
                        "model_id": model_id,
                        "file_url": file_url,
                    },
                )
            except Exception as alert_exc:  # pragma: no cover - defensive
                logger.error("Admin alert email failed for upload %s: %s", upload_id, alert_exc)

        if upload.status == UploadStatus.FAILED:
            await _refund_failed_upload(db, upload, credit_breakdown)


def _schedule_generation_task(
    background_tasks: BackgroundTasks,
    upload_id: str,
    file_url: str,
    tool_type: str,
    model_id: str,
    prompt: str,
    credit_breakdown: dict[str, int],
) -> None:
    """Start upload generation outside the request response lifecycle."""
    args = (upload_id, file_url, tool_type, model_id, prompt, credit_breakdown)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        background_tasks.add_task(_trigger_generation_background, *args)
        return

    task = loop.create_task(_trigger_generation_background(*args))
    _UPLOAD_GENERATION_TASKS.add(task)

    def _cleanup(done: asyncio.Task) -> None:
        _UPLOAD_GENERATION_TASKS.discard(done)
        if done.cancelled():
            logger.warning("Detached upload generation task was cancelled: %s", upload_id)
            return
        exc = done.exception()
        if exc:
            logger.error(
                "Detached upload generation task crashed for %s: %s",
                upload_id,
                exc,
                exc_info=(type(exc), exc, exc.__traceback__),
            )

    task.add_done_callback(_cleanup)


async def _save_upload(file: UploadFile, user_id: str, tool_type: str) -> tuple[str, int, str]:
    """Save uploaded file to durable storage. Returns (file_url, file_size)."""
    content = await file.read()
    file_size = len(content)

    expected_kind = "video" if tool_type in VIDEO_UPLOAD_TOOLS else "image"
    content_type = validate_uploaded_content(
        content=content,
        declared_content_type=file.content_type,
        expected_kind=expected_kind,
        max_bytes=MAX_UPLOAD_BYTES,
        dimension_rules=image_dimension_rules_for_tool(tool_type),
    )
    filename = f"{user_id}_{uuid.uuid4().hex}{extension_for_content_type(content_type)}"

    gcs = get_gcs_storage()
    if gcs.enabled:
        file_url = gcs.upload_public(
            data=content,
            blob_name=f"uploads/{user_id}/{filename}",
            content_type=content_type,
        )
        return file_url, file_size, content_type

    dest = os.path.join(UPLOAD_DIR, filename)
    with open(dest, "wb") as f:
        f.write(content)

    # Return a URL path accessible via static files
    file_url = f"/static/uploads/{filename}"
    return file_url, file_size, content_type

class VideoNormalizeResponse(BaseModel):
    """Response from the server-side video normalize endpoint."""
    video_url: str
    size_bytes: int
    duration_sec: float
    width: int
    height: int
    content_type: str = "video/mp4"
    normalized: bool = True
    note: Optional[str] = None


# Cap raw incoming video uploads. We accept large originals so we can
# transcode them down to the dubbing/transform/short-video provider
# budgets, but anything above this is rejected at the FastAPI layer to
# protect Cloud Run memory.
MAX_VIDEO_NORMALIZE_INPUT_BYTES = 500 * 1024 * 1024  # 500 MB
VIDEO_NORMALIZE_TARGET_BYTES = 20 * 1024 * 1024  # 20 MB
VIDEO_NORMALIZE_MAX_DIMENSION = 720  # longest edge
VIDEO_NORMALIZE_MAX_DURATION_SEC = 120  # hard cap; longer clips fail fast


async def _probe_video_metadata(path: Path) -> tuple[float, int, int]:
    """Return (duration_sec, width, height) via ffprobe; raise if unreadable."""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height:format=duration",
        "-of", "json",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        detail = (stderr or b"").decode("utf-8", errors="replace")[-500:]
        raise HTTPException(status_code=400, detail=f"Video could not be inspected: {detail}")
    try:
        data = json.loads(stdout.decode("utf-8", errors="replace"))
        stream = (data.get("streams") or [{}])[0]
        fmt = data.get("format") or {}
        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
        duration = float(fmt.get("duration") or 0.0)
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Video metadata unreadable.") from exc
    if width <= 0 or height <= 0:
        raise HTTPException(status_code=400, detail="Video has no decodable video stream.")
    return duration, width, height


@router.post("/video-normalize", response_model=VideoNormalizeResponse)
async def normalize_video(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """Server-side video re-encode for the upload pipelines.

    Accepts any browser-recordable container (mp4/webm/mov/quicktime),
    transcodes to H.264/AAC MP4 with `+faststart`, caps the longest edge
    at 720 px, and tries to keep the output under ~20 MB so PiAPI / Pollo
    / Vertex V2V providers don't reject the file. Returns a permanent
    GCS URL the frontend can use as the `video_url` for short-video,
    video-transform, or video-dubbing.

    Strategy:
      - Single-pass libx264 with crf=28, scale to fit max edge, +faststart
      - If still over budget, retry at crf=32 (smaller, slightly softer)
      - If still over, retry at crf=36 (last resort before failing)
      - On any ffmpeg failure we fall through and return the original
        bytes wrapped in an mp4 container if we can, else 422.
    """
    # Hard cap raw input. UploadFile.size is set by FastAPI when the
    # Content-Length is known; otherwise we measure as we stream.
    if file.size is not None and file.size > MAX_VIDEO_NORMALIZE_INPUT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Source video exceeds the {MAX_VIDEO_NORMALIZE_INPUT_BYTES // (1024 * 1024)} MB limit.",
        )

    ext = (Path(file.filename or "").suffix or ".mp4").lower()
    if ext not in {".mp4", ".mov", ".webm", ".m4v", ".quicktime"}:
        ext = ".mp4"

    with tempfile.TemporaryDirectory(prefix="vidgo-vnorm-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_path = tmp_path / f"input{ext}"
        output_path = tmp_path / "normalized.mp4"

        # Stream the upload to disk so we never hold the whole file in
        # memory; abort if we exceed the cap mid-stream.
        size_so_far = 0
        with open(input_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size_so_far += len(chunk)
                if size_so_far > MAX_VIDEO_NORMALIZE_INPUT_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Source video exceeds the {MAX_VIDEO_NORMALIZE_INPUT_BYTES // (1024 * 1024)} MB limit.",
                    )
                out.write(chunk)

        duration, src_w, src_h = await _probe_video_metadata(input_path)
        if duration > VIDEO_NORMALIZE_MAX_DURATION_SEC:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Video duration {duration:.1f}s exceeds the "
                    f"{VIDEO_NORMALIZE_MAX_DURATION_SEC}s normalize cap. "
                    "Please trim the clip first."
                ),
            )

        # Fast-path: if the source is already an MP4 within budget on every
        # axis, skip the re-encode and persist the original bytes to GCS.
        # That keeps the per-upload Cloud Run CPU cost near-zero for the
        # common "user has a small clean clip" case.
        already_ok = (
            size_so_far <= VIDEO_NORMALIZE_TARGET_BYTES * 1.05
            and max(src_w, src_h) <= VIDEO_NORMALIZE_MAX_DIMENSION
            and ext in {".mp4", ".m4v"}
        )
        if already_ok:
            output_bytes = input_path.read_bytes()
            user_id = str(current_user.id)
            gcs = get_gcs_storage()
            blob_name = f"uploads/videos/{user_id}/{uuid.uuid4().hex[:12]}.mp4"
            if gcs.enabled:
                video_url = gcs.upload_public(
                    data=output_bytes, blob_name=blob_name, content_type="video/mp4",
                )
            else:
                local_dir = Path(UPLOAD_DIR)
                local_dir.mkdir(parents=True, exist_ok=True)
                local_name = f"{user_id}_{uuid.uuid4().hex[:12]}.mp4"
                (local_dir / local_name).write_bytes(output_bytes)
                video_url = f"/static/uploads/{local_name}"
            return VideoNormalizeResponse(
                video_url=video_url,
                size_bytes=len(output_bytes),
                duration_sec=duration,
                width=src_w,
                height=src_h,
                content_type="video/mp4",
                normalized=False,
                note="Source already within budget; persisted as-is.",
            )

        # Hard wall-clock cap per ffmpeg pass. A 120 s 1080p source encodes
        # in ~30 s on Cloud Run's 1 vCPU; if we ever blow past 5 minutes the
        # input is pathological (broken container, unseekable webm) and we
        # should kill the process instead of letting it tie up the worker
        # until Cloud Run's 3600 s request timeout fires.
        ENCODE_TIMEOUT_SEC = 300

        async def run_encode(crf: int) -> tuple[int, str]:
            scale = (
                f"scale='if(gt(iw,ih),min({VIDEO_NORMALIZE_MAX_DIMENSION},iw),-2)':"
                f"'if(gt(ih,iw),min({VIDEO_NORMALIZE_MAX_DIMENSION},ih),-2)'"
            )
            args = [
                "ffmpeg", "-y",
                "-i", str(input_path),
                "-vf", scale,
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", str(crf),
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                str(output_path),
            ]
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=ENCODE_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError:
                logger.error("[video-normalize] ffmpeg crf=%s exceeded %ss; killing", crf, ENCODE_TIMEOUT_SEC)
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                # Drain any remaining output so the pipe doesn't hold a
                # zombie around. Bound this wait so a misbehaving subprocess
                # can't lock us up a second time.
                try:
                    await asyncio.wait_for(proc.communicate(), timeout=5)
                except Exception:
                    pass
                return -1, f"ffmpeg timed out after {ENCODE_TIMEOUT_SEC}s"
            detail = (stderr or stdout).decode("utf-8", errors="replace")[-1500:]
            return proc.returncode, detail

        last_detail = ""
        success_crf: Optional[int] = None
        for crf in (28, 32, 36):
            if output_path.exists():
                output_path.unlink()
            rc, last_detail = await run_encode(crf)
            if rc != 0 or not output_path.exists():
                logger.warning("[video-normalize] crf=%s failed: %s", crf, last_detail[-400:])
                continue
            if output_path.stat().st_size <= VIDEO_NORMALIZE_TARGET_BYTES * 1.05:
                success_crf = crf
                break
            # Output exists but is still oversized — try a harsher CRF.

        if not output_path.exists():
            raise HTTPException(
                status_code=422,
                detail=f"Video re-encode failed: {last_detail[-400:]}",
            )

        output_bytes = output_path.read_bytes()
        out_duration, out_w, out_h = await _probe_video_metadata(output_path)

        user_id = str(current_user.id)
        gcs = get_gcs_storage()
        blob_name = f"uploads/videos/{user_id}/{uuid.uuid4().hex[:12]}.mp4"
        if gcs.enabled:
            video_url = gcs.upload_public(
                data=output_bytes,
                blob_name=blob_name,
                content_type="video/mp4",
            )
        else:
            local_dir = Path(UPLOAD_DIR)
            local_dir.mkdir(parents=True, exist_ok=True)
            local_name = f"{user_id}_{uuid.uuid4().hex[:12]}.mp4"
            (local_dir / local_name).write_bytes(output_bytes)
            video_url = f"/static/uploads/{local_name}"

        note = None
        if success_crf is None:
            note = "Output is still larger than the soft target; provider may downsample further."
        return VideoNormalizeResponse(
            video_url=video_url,
            size_bytes=len(output_bytes),
            duration_sec=out_duration,
            width=out_w,
            height=out_h,
            content_type="video/mp4",
            normalized=True,
            note=note,
        )


async def _run_ffmpeg_video_transform(source_url: str, upload: UserUpload) -> str:
    """Apply a lightweight local video transform when external V2V providers are unavailable."""
    with tempfile.TemporaryDirectory(prefix="vidgo-video-transform-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_path = tmp_path / "input.mp4"
        output_path = tmp_path / "output.mp4"

        async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
            response = await client.get(source_url)
            response.raise_for_status()
            input_path.write_bytes(response.content)

        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-vf",
            "eq=contrast=1.08:saturation=1.18:brightness=0.02,unsharp=5:5:0.6:3:3:0.3",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(output_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0 or not output_path.exists():
            detail = (stderr or stdout).decode("utf-8", errors="replace")[-1000:]
            raise RuntimeError(f"ffmpeg video transform failed: {detail}")

        output_bytes = output_path.read_bytes()
        gcs = get_gcs_storage()
        if gcs.enabled:
            return gcs.upload_public(
                data=output_bytes,
                blob_name=f"generated/video/uploads/{upload.user_id}/{upload.id}.mp4",
                content_type="video/mp4",
            )

        output_dir = Path(UPLOAD_DIR).parent / "generated"
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"video_transform_{upload.id}.mp4"
        local_output = output_dir / filename
        local_output.write_bytes(output_bytes)
        public_base = settings.BACKEND_URL.rstrip("/") if settings.BACKEND_URL else ""
        return f"{public_base}/static/generated/{filename}" if public_base else f"/static/generated/{filename}"


# ─────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────

@router.get("")
async def uploads_overview(
    current_user: User = Depends(get_current_active_user),
):
    """Upload service overview. Requires authentication."""
    return {
        "service": "uploads",
        "message": "Subscriber material upload service",
        "user_id": str(current_user.id),
        "endpoints": {
            "upload_material": "POST /api/v1/uploads/material",
            "my_uploads": "GET /api/v1/uploads/my-uploads",
            "get_models": "GET /api/v1/uploads/models/{tool_type}",
        },
        "supported_tools": list(TOOL_MODELS.keys()),
    }


@router.get("/models/{tool_type}", response_model=ToolModelsResponse)
async def get_tool_models(
    tool_type: str,
    current_user: User = Depends(get_current_active_user),
):
    """
    List available AI models for a tool type, with credit costs per model.
    Requires authentication; paid subscribers can use premium models.
    """
    models_raw = TOOL_MODELS.get(tool_type)
    if models_raw is None:
        raise HTTPException(status_code=404, detail=f"Unknown tool type: {tool_type}")

    subscribed = is_subscribed_user(current_user)
    base = TOOL_BASE_CREDITS.get(tool_type, 10)

    models = []
    for m in models_raw:
        # Non-subscribers can only see the default model
        if not subscribed and m["id"] != "default":
            continue
        models.append(ModelInfo(
            id=m["id"],
            name=m["name"],
            name_zh=m["name_zh"],
            credit_cost=max(1, int(base * m["credit_multiplier"])),
            credit_multiplier=m["credit_multiplier"],
        ))

    return ToolModelsResponse(tool_type=tool_type, models=models)


@router.post("/material", response_model=UploadResponse)
async def upload_and_generate(
    background_tasks: BackgroundTasks,
    tool_type: str = Form(...),
    model_id: str = Form(default="default"),
    prompt: Optional[str] = Form(default=None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a material image and trigger real AI generation (subscribers only).

    The result is stored without watermarks and available for download.
    Credits are deducted based on tool type and selected model.
    """
    is_admin = bool(getattr(current_user, "is_superuser", False))
    if not is_admin and not is_subscribed_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A subscription is required to use custom material upload and real API generation."
        )

    # Validate tool type
    if tool_type not in TOOL_BASE_CREDITS:
        raise HTTPException(status_code=400, detail=f"Unknown tool type: {tool_type}")

    if tool_type not in IMAGE_UPLOAD_TOOLS and tool_type not in VIDEO_UPLOAD_TOOLS:
        raise HTTPException(status_code=400, detail=f"Uploads are not configured for tool type: {tool_type}")

    if not _is_valid_model(tool_type, model_id):
        raise HTTPException(status_code=400, detail=f"Unknown model_id '{model_id}' for tool_type '{tool_type}'")

    prompt = _normalize_upload_prompt(tool_type, prompt)

    # Calculate credit cost
    credit_cost = 0 if is_admin else _calculate_credit_cost(tool_type, model_id)

    # Check credit balance
    total_credits = current_user.total_credits
    if not is_admin and total_credits < credit_cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits. This generation costs {credit_cost} credits, you have {total_credits}."
        )

    # Save file
    file_url, file_size, content_type = await _save_upload(file, str(current_user.id), tool_type)

    # Create upload record (starts as PROCESSING)
    upload = UserUpload(
        user_id=current_user.id,
        tool_type=tool_type,
        original_filename=file.filename,
        file_url=file_url,
        file_size=file_size,
        content_type=content_type,
        prompt=prompt,
        selected_model=model_id,
        status=UploadStatus.PROCESSING,
        credits_used=credit_cost,
    )
    db.add(upload)
    await db.flush()
    upload_id = str(upload.id)

    credit_breakdown = (
        {"subscription_credits": 0, "purchased_credits": 0, "bonus_credits": 0}
        if is_admin
        else _deduct_upload_credits(current_user, credit_cost)
    )
    upload.extra_params = json.dumps({
        "credit_breakdown": credit_breakdown,
        "credits_refunded": False,
    })

    await db.commit()
    _schedule_generation_task(
        background_tasks,
        upload_id,
        file_url,
        tool_type,
        model_id,
        prompt or "",
        credit_breakdown,
    )

    return UploadResponse(
        upload_id=upload_id,
        status=UploadStatus.PROCESSING.value,
        credits_used=credit_cost,
        message="Generation started. Check status at /uploads/{upload_id}",
    )


async def _trigger_generation(
    upload: UserUpload,
    file_url: str,
    tool_type: str,
    model_id: str,
    prompt: str,
    db: AsyncSession,
):
    """Call the AI provider and store results on the upload record."""
    # Build absolute URL for the uploaded file (for external API)
    abs_file_url = file_url  # provider handles /static/ → base64 conversion

    result = None
    if tool_type == "background_removal":
        result = await provider_router.route(
            TaskType.BACKGROUND_REMOVAL,
            {"image_url": abs_file_url}
        )
        if result.get("success"):
            output = result.get("output", {})
            upload.result_url = output.get("image_url") or output.get("url")

    elif tool_type in ("product_scene", "room_redesign", "pattern_generate", "effect", "try_on"):
        # Use EFFECTS task type for image-to-image style transformations (including try-on)
        result = await provider_router.route(
            TaskType.EFFECTS,
            {
                "image_url": abs_file_url,
                "prompt": prompt,
                "strength": 0.65,
                "model": model_id if model_id != "default" else None,
            }
        )
        if result.get("success"):
            output = result.get("output", {})
            upload.result_url = (
                output.get("image_url")
                or (output.get("images", [{}])[0].get("url") if output.get("images") else None)
            )

    elif tool_type == "short_video":
        i2v_model = model_id if model_id != "default" else "pixverse_v4.5"
        result = await provider_router.route(
            TaskType.I2V,
            {"image_url": abs_file_url, "prompt": prompt, "model": i2v_model, "duration": 5}
        )
        if result.get("success"):
            output = result.get("output", {})
            upload.result_video_url = output.get("video_url") or output.get("url")

    elif tool_type == "video_transform":
        provider_error = None
        try:
            result = await provider_router.route(
                TaskType.V2V,
                {
                    "video_url": abs_file_url,
                    "prompt": prompt,
                    "effect": "style_transfer",
                    "intensity": 0.5,
                }
            )
        except Exception as exc:
            provider_error = str(exc)
            logger.warning("Provider V2V failed for upload %s; trying local transform: %s", upload.id, exc)

        if not result or not result.get("success"):
            provider_error = provider_error or result.get("error", "Provider returned no result") if result else provider_error
            try:
                local_video_url = await _run_ffmpeg_video_transform(abs_file_url, upload)
                result = {"success": True, "output": {"video_url": local_video_url}}
            except Exception as exc:
                result = {
                    "success": False,
                    "error": f"Provider V2V failed ({provider_error or 'unknown'}); local transform failed ({exc})",
                }

        if result.get("success"):
            output = result.get("output", {})
            upload.result_video_url = output.get("video_url") or output.get("url")

    elif tool_type == "ai_avatar":
        script = prompt or "Hello, I am your AI assistant."
        result = await provider_router.route(
            TaskType.AVATAR,
            {
                "image_url": abs_file_url,
                "script": script,
                "text": script,
                "language": "en",
                "duration": 30,
                "user_id": str(upload.user_id),
            }
        )
        if result.get("success"):
            output = result.get("output", {})
            upload.result_video_url = output.get("video_url") or output.get("url")

    if result and result.get("success"):
        upload.status = UploadStatus.COMPLETED
        upload.completed_at = datetime.now(timezone.utc)
    else:
        provider_error = result.get("error", "Unknown error") if result else "Provider returned no result"
        logger.error(
            "Upload generation failed for upload %s (tool=%s): %s",
            upload.id,
            tool_type,
            provider_error,
        )
        upload.status = UploadStatus.FAILED
        upload.error_message = GENERIC_UPLOAD_FAILURE_MESSAGE
        try:
            await send_admin_tool_failure_email(
                tool_name=f"upload:{tool_type}",
                user_email=None,
                error=RuntimeError(provider_error),
                request_id=str(upload.id),
                extra_context={"model_id": model_id, "stage": "provider_result"},
            )
        except Exception as alert_exc:  # pragma: no cover - defensive
            logger.error("Admin alert email failed for upload %s: %s", upload.id, alert_exc)

    await db.commit()


@router.get("/my-uploads", response_model=List[UploadStatusResponse])
async def list_my_uploads(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
):
    """List the current user's upload history (most recent first)."""
    result = await db.execute(
        select(UserUpload)
        .where(UserUpload.user_id == current_user.id)
        .order_by(UserUpload.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    uploads = result.scalars().all()

    return [
        UploadStatusResponse(
            upload_id=str(u.id),
            tool_type=u.tool_type,
            status=u.status.value,
            selected_model=u.selected_model,
            credits_used=u.credits_used or 0,
            file_url=u.file_url,
            result_url=u.result_url,
            result_video_url=u.result_video_url,
            error_message=u.error_message,
            created_at=u.created_at.isoformat() if u.created_at else "",
            completed_at=u.completed_at.isoformat() if u.completed_at else None,
        )
        for u in uploads
    ]


@router.get("/{upload_id}", response_model=UploadStatusResponse)
async def get_upload_status(
    upload_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the status and result of a specific upload."""
    result = await db.execute(
        select(UserUpload).where(
            UserUpload.id == upload_id,
            UserUpload.user_id == current_user.id,
        )
    )
    upload = result.scalars().first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    return UploadStatusResponse(
        upload_id=str(upload.id),
        tool_type=upload.tool_type,
        status=upload.status.value,
        selected_model=upload.selected_model,
        credits_used=upload.credits_used or 0,
        file_url=upload.file_url,
        result_url=upload.result_url,
        result_video_url=upload.result_video_url,
        error_message=upload.error_message,
        created_at=upload.created_at.isoformat() if upload.created_at else "",
        completed_at=upload.completed_at.isoformat() if upload.completed_at else None,
    )


@router.get("/{upload_id}/download")
async def download_result(
    upload_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Download the generation result without watermark (subscribers only).

    Returns the file as a streaming response.
    """
    if not getattr(current_user, "is_superuser", False) and not is_subscribed_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A subscription is required to download results."
        )

    result = await db.execute(
        select(UserUpload).where(
            UserUpload.id == upload_id,
            UserUpload.user_id == current_user.id,
        )
    )
    upload = result.scalars().first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    if upload.status != UploadStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Generation is not completed yet (status: {upload.status.value})"
        )

    result_url = upload.result_video_url or upload.result_url
    if not result_url:
        raise HTTPException(status_code=404, detail="No result available for download")

    # If local file, serve directly
    if result_url.startswith("/static/") or result_url.startswith("/app/"):
        local_path = result_url.replace("/static/", "/app/static/")
        if os.path.exists(local_path):
            ext = os.path.splitext(local_path)[1].lower()
            media_type = DOWNLOAD_MEDIA_TYPES_BY_EXTENSION.get(ext, "application/octet-stream")
            filename = f"vidgo_result_{upload_id[:8]}{ext}"

            def iterfile():
                with open(local_path, "rb") as f:
                    yield from f

            return StreamingResponse(
                iterfile(),
                media_type=media_type,
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

    # Remote URL — proxy the download
    async with httpx.AsyncClient() as client:
        response = await client.get(result_url, follow_redirects=True, timeout=30)
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="Could not fetch result from storage")

        content_type = response.headers.get("content-type", "application/octet-stream")
        normalized_content_type = content_type.split(";", 1)[0].strip().lower()
        ext = DOWNLOAD_EXTENSIONS_BY_CONTENT_TYPE.get(normalized_content_type)
        if not ext:
            ext = os.path.splitext(result_url.split("?", 1)[0])[1].lower() or ".bin"
        filename = f"vidgo_result_{upload_id[:8]}{ext}"

        return StreamingResponse(
            iter([response.content]),
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
