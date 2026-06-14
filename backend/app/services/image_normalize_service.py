"""
Server-side image normaliser.

Replaces the "reject if doesn't fit our dimension rule" behaviour of the
upload endpoints with "accept anything PIL can decode, re-encode as PNG
within the rule." Users were uploading iPhone HEIC photos or 6000-pixel
panoramas and seeing a confusing 422 — this lets them succeed.

Accepted inputs:
  - JPG, PNG, WebP (PIL native)
  - HEIC, HEIF (via pillow-heif plugin, opener auto-registered)
  - BMP, TIFF, GIF (PIL native — converted to PNG)
  - Anything else PIL can open via codec fallbacks

Output: an in-memory PNG that fits inside ImageDimensionRules
(default 128px–4096px each side, max 16 MP, aspect 0.25–4.0).
Oversize images are scaled to fit. Out-of-aspect images are
centre-cropped to the nearest allowed aspect. Tiny images (< min)
are upscaled with Lanczos.

Re-raises ``HTTPException(415)`` only when the bytes are NOT a
recognisable image at all (e.g. an HTML upload, broken PDF).
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import Tuple

from fastapi import HTTPException, status
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.upload_validation import (
    COMMON_IMAGE_DIMENSION_RULES,
    ImageDimensionRules,
)

logger = logging.getLogger(__name__)


# Register HEIF/HEIC opener so PIL.Image.open() picks up iPhone photos.
# Wrapped in try/except so the import does not crash the worker if the
# wheel isn't yet installed (e.g. tests on a slim image).
try:
    import pillow_heif  # type: ignore[import-not-found]
    pillow_heif.register_heif_opener()
    _HEIF_AVAILABLE = True
    logger.info("[image-normalize] HEIC/HEIF support registered via pillow-heif")
except Exception as exc:  # pragma: no cover - import-time only
    _HEIF_AVAILABLE = False
    logger.info("[image-normalize] pillow-heif not available (%s) — iPhone HEIC uploads will be rejected", exc)


@dataclass
class NormalizedImage:
    bytes: bytes
    content_type: str  # always "image/png" after normalize
    width: int
    height: int
    original_format: str
    was_modified: bool


def _fit_dimensions(width: int, height: int, rules: ImageDimensionRules) -> Tuple[int, int]:
    """Return (new_w, new_h) that satisfies the rules. Preserves aspect
    ratio when possible; reports back what the rule allows otherwise."""
    new_w, new_h = width, height

    # Scale DOWN if either edge or megapixel cap is exceeded.
    scale_down = 1.0
    if new_w > rules.max_width:
        scale_down = min(scale_down, rules.max_width / new_w)
    if new_h > rules.max_height:
        scale_down = min(scale_down, rules.max_height / new_h)
    megapixels = (new_w * new_h) / 1_000_000
    if megapixels > rules.max_megapixels:
        scale_down = min(scale_down, (rules.max_megapixels / megapixels) ** 0.5)
    if scale_down < 1.0:
        new_w = max(1, int(new_w * scale_down))
        new_h = max(1, int(new_h * scale_down))

    # Scale UP if both edges are below the min (preserve aspect).
    if new_w < rules.min_width and new_h < rules.min_height:
        scale_up = max(rules.min_width / new_w, rules.min_height / new_h)
        new_w = int(new_w * scale_up)
        new_h = int(new_h * scale_up)
    # If only one edge is below min, scale by that one (still preserves aspect).
    elif new_w < rules.min_width:
        scale_up = rules.min_width / new_w
        new_w = int(new_w * scale_up)
        new_h = int(new_h * scale_up)
    elif new_h < rules.min_height:
        scale_up = rules.min_height / new_h
        new_w = int(new_w * scale_up)
        new_h = int(new_h * scale_up)

    return new_w, new_h


def _crop_to_aspect(img: Image.Image, rules: ImageDimensionRules) -> Image.Image:
    """If the image aspect is outside the rule, centre-crop to the nearest
    allowed aspect. Returning the original image when it's already inside
    the band keeps the typical e-commerce 16:9 / 4:3 / 3:4 photo untouched."""
    w, h = img.size
    if h == 0:
        return img
    aspect = w / h
    if rules.min_aspect_ratio <= aspect <= rules.max_aspect_ratio:
        return img

    if aspect > rules.max_aspect_ratio:
        # Too wide — narrow it by trimming the sides.
        target_w = int(h * rules.max_aspect_ratio)
        left = (w - target_w) // 2
        return img.crop((left, 0, left + target_w, h))
    # Too tall — trim top and bottom.
    target_h = int(w / rules.min_aspect_ratio)
    top = (h - target_h) // 2
    return img.crop((0, top, w, top + target_h))


def normalize_uploaded_image(
    content: bytes,
    *,
    rules: ImageDimensionRules = COMMON_IMAGE_DIMENSION_RULES,
    max_bytes: int = 20 * 1024 * 1024,
) -> NormalizedImage:
    """Decode arbitrary image bytes, normalize, return PNG bytes that fit
    the supplied dimension rules. Raises ``HTTPException(415)`` only when
    the bytes are not a recognisable image; otherwise we always produce a
    usable PNG."""
    if not content:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Empty upload — please choose a file.",
        )
    if len(content) > max_bytes * 2:
        # 2x soft cap so we don't load a 1 GB payload into memory just to
        # tell the user it's too big — the FastAPI multipart limit usually
        # catches this first, this is the belt.
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File is too large. Maximum allowed is {max_bytes // (1024 * 1024)} MB.",
        )

    try:
        img = Image.open(io.BytesIO(content))
        img.load()
    except UnidentifiedImageError:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                "We couldn't read your file as an image. Please upload a "
                "JPG, PNG, WebP, HEIC, BMP, TIFF, or GIF photo."
            ),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Could not decode image: {exc}",
        )

    original_format = (img.format or "UNKNOWN").upper()

    # Respect EXIF orientation (iPhone photos load sideways otherwise) and
    # collapse to RGB so PNG export is deterministic. PNG can keep RGBA, so
    # we only flatten RGBA → RGB when we end up encoding for a model that
    # rejects transparency. Here we keep RGBA to preserve cutouts.
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:  # noqa: BLE001
        pass
    if img.mode not in {"RGB", "RGBA"}:
        img = img.convert("RGBA" if "A" in img.mode else "RGB")

    was_modified = original_format != "PNG"

    # Aspect crop first (cheaper than resize, less data thrown away).
    cropped = _crop_to_aspect(img, rules)
    if cropped is not img:
        was_modified = True
        img = cropped

    target_w, target_h = _fit_dimensions(img.width, img.height, rules)
    if (target_w, target_h) != img.size:
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        was_modified = True

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    out_bytes = buf.getvalue()

    # PNG can balloon for high-res photos — if we still exceed max_bytes,
    # progressively reduce quality by re-encoding as JPEG; user gets a
    # usable file rather than a 413 wall.
    if len(out_bytes) > max_bytes:
        rgb_img = img.convert("RGB") if img.mode == "RGBA" else img
        for quality in (90, 80, 70, 60):
            buf = io.BytesIO()
            rgb_img.save(buf, format="JPEG", quality=quality, optimize=True)
            cand = buf.getvalue()
            if len(cand) <= max_bytes:
                out_bytes = cand
                return NormalizedImage(
                    bytes=out_bytes,
                    content_type="image/jpeg",
                    width=img.width,
                    height=img.height,
                    original_format=original_format,
                    was_modified=True,
                )
        # Final fallback: return the smallest we could make and let the
        # downstream uploader decide.
        out_bytes = cand

    return NormalizedImage(
        bytes=out_bytes,
        content_type="image/png",
        width=img.width,
        height=img.height,
        original_format=original_format,
        was_modified=was_modified,
    )
