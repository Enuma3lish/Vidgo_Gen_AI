"""Download endpoints for generated user media."""
import logging
from urllib.parse import quote, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user, is_subscribed_user
from app.models.user import User
from app.models.user_generation import UserGeneration
from app.services.gcs_storage_service import get_gcs_storage

logger = logging.getLogger(__name__)
router = APIRouter()


def _filename_for(generation: UserGeneration, url: str) -> str:
    """Build a friendly download filename: vidgo-<tool>-<id>.<ext>."""
    path = urlparse(url).path
    ext = path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
    if not ext or len(ext) > 5:
        ext = "mp4" if generation.result_video_url else "png"
    raw = getattr(generation, "tool_type", None)
    # tool_type is an enum (ToolType.SHORT_VIDEO) — strip the prefix and use .value/.name.
    tool = (getattr(raw, "value", None) or getattr(raw, "name", None) or str(raw) or "result")
    tool = str(tool).rsplit(".", 1)[-1].replace("_", "-").lower()
    return f"vidgo-{tool}-{generation.id}.{ext}"


@router.get("/{generation_id}")
async def download_generation_result(
    generation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download a generated work through the canonical download URL."""
    if not is_subscribed_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required to download",
        )

    result = await db.execute(
        select(UserGeneration).where(
            UserGeneration.id == generation_id,
            UserGeneration.user_id == current_user.id,
        )
    )
    generation = result.scalar_one_or_none()

    if not generation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work not found")

    if generation.is_media_expired:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                "This work's media has expired (14-day retention period). "
                "The generation record is kept for your history, but the media file is no longer available for download."
            ),
        )

    download_url = generation.result_video_url or generation.result_image_url
    if not download_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No result file available")

    filename = _filename_for(generation, download_url)

    # Preferred path: re-sign GCS URL with response-content-disposition so the
    # browser saves the file as <filename> instead of opening it inline.
    gcs = get_gcs_storage()
    signed = gcs.refresh_signed_url(download_url, download_filename=filename)
    if signed and signed != download_url:
        return RedirectResponse(url=signed)

    # Fallback for non-GCS URLs (legacy / provider CDN): proxy with our own
    # Content-Disposition header so the file still saves correctly.
    try:
        async def _stream():
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                async with client.stream("GET", download_url) as resp:
                    if resp.status_code != 200:
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"Upstream returned {resp.status_code}",
                        )
                    async for chunk in resp.aiter_bytes(chunk_size=64 * 1024):
                        yield chunk

        media_type = "video/mp4" if generation.result_video_url else "image/png"
        headers = {
            "Content-Disposition": (
                f'attachment; filename="{filename.encode("ascii", "ignore").decode() or "vidgo-download"}"; '
                f"filename*=UTF-8''{quote(filename)}"
            ),
            "Cache-Control": "private, no-store",
        }
        return StreamingResponse(_stream(), media_type=media_type, headers=headers)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[downloads] proxy failed for %s: %s", generation_id, e)
        # Last-resort fallback: redirect (file may open inline, but at least works).
        return RedirectResponse(url=download_url)
