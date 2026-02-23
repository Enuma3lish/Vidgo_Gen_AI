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
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import httpx

from app.api.deps import get_db, get_current_active_user, is_subscribed_user
from app.models.user import User
from app.models.user_upload import UserUpload, UploadStatus
from app.core.config import get_settings
from app.providers.provider_router import get_provider_router, TaskType

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/uploads", tags=["uploads"])
provider_router = get_provider_router()

# ─────────────────────────────────────────
# Model / credit configuration
# ─────────────────────────────────────────

# Base credit cost per tool type
TOOL_BASE_CREDITS = {
    "background_removal": 5,
    "product_scene": 10,
    "try_on": 15,
    "room_redesign": 10,
    "short_video": 30,
    "ai_avatar": 40,
    "pattern_generate": 8,
    "effect": 10,
}

# Available models per tool type with their credit multipliers
TOOL_MODELS = {
    "background_removal": [
        {"id": "default", "name": "Standard", "name_zh": "標準", "credit_multiplier": 1},
    ],
    "product_scene": [
        {"id": "default", "name": "Standard (Flux)", "name_zh": "標準 (Flux)", "credit_multiplier": 1},
        {"id": "wan_pro", "name": "Pro (Wan Pro)", "name_zh": "進階 (Wan Pro)", "credit_multiplier": 2},
    ],
    "try_on": [
        {"id": "default", "name": "Standard (Kling v1.5)", "name_zh": "標準 (Kling v1.5)", "credit_multiplier": 1},
        {"id": "kling_v2", "name": "Premium (Kling v2)", "name_zh": "精緻 (Kling v2)", "credit_multiplier": 2},
    ],
    "room_redesign": [
        {"id": "default", "name": "Standard (Flux)", "name_zh": "標準 (Flux)", "credit_multiplier": 1},
        {"id": "wan_pro", "name": "Pro (Wan Pro)", "name_zh": "進階 (Wan Pro)", "credit_multiplier": 2},
    ],
    "short_video": [
        {"id": "pixverse_v4.5", "name": "Fast (Pixverse v4.5)", "name_zh": "快速 (Pixverse v4.5)", "credit_multiplier": 1},
        {"id": "pixverse_v5", "name": "Creative (Pixverse v5)", "name_zh": "創意 (Pixverse v5)", "credit_multiplier": 1.5},
        {"id": "kling_v2", "name": "High Quality (Kling v2)", "name_zh": "高品質 (Kling v2)", "credit_multiplier": 2},
        {"id": "luma_ray2", "name": "Cinematic (Luma Ray2)", "name_zh": "電影級 (Luma Ray2)", "credit_multiplier": 3},
    ],
    "ai_avatar": [
        {"id": "default", "name": "Standard", "name_zh": "標準", "credit_multiplier": 1},
    ],
    "pattern_generate": [
        {"id": "default", "name": "Standard (Flux)", "name_zh": "標準 (Flux)", "credit_multiplier": 1},
        {"id": "wan_pro", "name": "Pro (Wan Pro)", "name_zh": "進階 (Wan Pro)", "credit_multiplier": 2},
    ],
    "effect": [
        {"id": "default", "name": "Standard (Flux I2I)", "name_zh": "標準 (Flux I2I)", "credit_multiplier": 1},
        {"id": "wan_pro", "name": "Pro (Wan Pro)", "name_zh": "進階 (Wan Pro)", "credit_multiplier": 2},
    ],
}

ALLOWED_CONTENT_TYPES = {ct.strip() for ct in settings.UPLOAD_ALLOWED_TYPES.split(",")}
MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

UPLOAD_DIR = "/app/static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


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


async def _save_upload(file: UploadFile, user_id: str) -> tuple[str, int]:
    """Save uploaded file to disk. Returns (file_url, file_size)."""
    ext = os.path.splitext(file.filename or "upload")[1] or ".jpg"
    filename = f"{user_id}_{uuid.uuid4().hex}{ext}"
    dest = os.path.join(UPLOAD_DIR, filename)

    content = await file.read()
    file_size = len(content)

    if file_size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE_MB} MB."
        )

    with open(dest, "wb") as f:
        f.write(content)

    # Return a URL path accessible via static files
    file_url = f"/static/uploads/{filename}"
    return file_url, file_size


# ─────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────

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
    if not is_subscribed_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A subscription is required to use custom material upload and real API generation."
        )

    # Validate content type
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}. Allowed: {settings.UPLOAD_ALLOWED_TYPES}"
        )

    # Validate tool type
    if tool_type not in TOOL_BASE_CREDITS:
        raise HTTPException(status_code=400, detail=f"Unknown tool type: {tool_type}")

    # Calculate credit cost
    credit_cost = _calculate_credit_cost(tool_type, model_id)

    # Check credit balance
    total_credits = current_user.total_credits
    if total_credits < credit_cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits. This generation costs {credit_cost} credits, you have {total_credits}."
        )

    # Save file
    file_url, file_size = await _save_upload(file, str(current_user.id))

    # Create upload record (starts as PROCESSING)
    upload = UserUpload(
        user_id=current_user.id,
        tool_type=tool_type,
        original_filename=file.filename,
        file_url=file_url,
        file_size=file_size,
        content_type=file.content_type,
        prompt=prompt,
        selected_model=model_id,
        status=UploadStatus.PROCESSING,
        credits_used=credit_cost,
    )
    db.add(upload)
    await db.flush()
    upload_id = str(upload.id)

    # Deduct credits
    if current_user.subscription_credits >= credit_cost:
        current_user.subscription_credits -= credit_cost
    elif (current_user.subscription_credits or 0) + (current_user.purchased_credits or 0) >= credit_cost:
        remaining = credit_cost - (current_user.subscription_credits or 0)
        current_user.subscription_credits = 0
        current_user.purchased_credits = (current_user.purchased_credits or 0) - remaining
    else:
        # Deduct from bonus credits as last resort
        current_user.bonus_credits = (current_user.bonus_credits or 0) - credit_cost

    await db.commit()

    # Trigger async generation (fire-and-forget via ARQ worker or inline)
    try:
        await _trigger_generation(upload, file_url, tool_type, model_id, prompt or "", db)
    except Exception as e:
        logger.error(f"Generation trigger failed for upload {upload_id}: {e}")
        # Mark as failed but don't raise — credits already deducted, refund logic can be added
        upload.status = UploadStatus.FAILED
        upload.error_message = str(e)
        await db.commit()

    return UploadResponse(
        upload_id=upload_id,
        status=upload.status.value,
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

    elif tool_type == "ai_avatar":
        result = await provider_router.route(
            TaskType.AVATAR,
            {"image_url": abs_file_url, "text": prompt or "Hello, I am your AI assistant."}
        )
        if result.get("success"):
            output = result.get("output", {})
            upload.result_video_url = output.get("video_url") or output.get("url")

    if result and result.get("success"):
        upload.status = UploadStatus.COMPLETED
        upload.completed_at = datetime.now(timezone.utc)
    else:
        error = result.get("error", "Unknown error") if result else "Provider returned no result"
        upload.status = UploadStatus.FAILED
        upload.error_message = error

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
    if not is_subscribed_user(current_user):
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
            media_type = "video/mp4" if ext == ".mp4" else "image/jpeg"
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
        ext = ".mp4" if "video" in content_type else ".jpg"
        filename = f"vidgo_result_{upload_id[:8]}{ext}"

        return StreamingResponse(
            iter([response.content]),
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
