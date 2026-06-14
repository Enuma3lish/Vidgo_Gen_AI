"""Shared upload validation helpers for tool media inputs."""

from __future__ import annotations

import os
import base64
import binascii
from dataclasses import dataclass
from io import BytesIO
from typing import Literal, Optional
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError


MediaKind = Literal["image", "video"]

AI_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
AI_VIDEO_CONTENT_TYPES = {"video/mp4", "video/webm", "video/quicktime"}
AI_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
AI_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v"}
CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
}
MAX_DIMENSION_PROBE_BYTES = 25 * 1024 * 1024


@dataclass(frozen=True)
class ImageDimensionRules:
    label: str
    min_width: int = 128
    min_height: int = 128
    max_width: int = 4096
    max_height: int = 4096
    max_megapixels: float = 16.0
    min_aspect_ratio: float = 0.25
    max_aspect_ratio: float = 4.0
    guidance: str = "Please crop, resize, or choose a different image."


COMMON_IMAGE_DIMENSION_RULES = ImageDimensionRules(
    label="Image",
    guidance="Please choose an image between 128px and 4096px on each side.",
)
PRODUCT_SCENE_IMAGE_DIMENSION_RULES = ImageDimensionRules(
    label="Product scene input",
    min_width=256,
    min_height=256,
    guidance="Please choose a clear product image between 256px and 4096px on each side.",
)
TRY_ON_GARMENT_IMAGE_DIMENSION_RULES = ImageDimensionRules(
    label="Try-on garment input",
    min_width=256,
    min_height=256,
    min_aspect_ratio=0.5,
    max_aspect_ratio=2.0,
    guidance="Please choose a clear garment image that is square or portrait/landscape, not an extreme panorama.",
)
TRY_ON_MODEL_IMAGE_DIMENSION_RULES = ImageDimensionRules(
    label="Try-on model input",
    min_width=384,
    min_height=512,
    min_aspect_ratio=0.5,
    max_aspect_ratio=0.9,
    guidance="Please choose a full-body portrait model image, roughly 2:3 or 3:4.",
)
ROOM_REDESIGN_IMAGE_DIMENSION_RULES = ImageDimensionRules(
    label="Room redesign input",
    min_width=512,
    min_height=512,
    min_aspect_ratio=0.5,
    max_aspect_ratio=2.2,
    guidance="Please choose a room photo at least 512px on each side, not an extreme panorama.",
)
IMAGE_TO_VIDEO_DIMENSION_RULES = ImageDimensionRules(
    label="Short video input",
    min_width=256,
    min_height=256,
    min_aspect_ratio=0.45,
    max_aspect_ratio=2.2,
    guidance="Please choose an image close to 16:9, 1:1, or 9:16 so the video API can use it.",
)
AVATAR_HEADSHOT_DIMENSION_RULES = ImageDimensionRules(
    label="AI avatar headshot",
    min_width=256,
    min_height=256,
    min_aspect_ratio=0.75,
    max_aspect_ratio=1.25,
    guidance="Please choose a square or near-square head-and-shoulders portrait; full-body photos are rejected by the avatar API.",
)

UPLOAD_IMAGE_DIMENSION_RULES_BY_TOOL = {
    "background_removal": COMMON_IMAGE_DIMENSION_RULES,
    "product_scene": PRODUCT_SCENE_IMAGE_DIMENSION_RULES,
    "try_on": TRY_ON_GARMENT_IMAGE_DIMENSION_RULES,
    "room_redesign": ROOM_REDESIGN_IMAGE_DIMENSION_RULES,
    "short_video": IMAGE_TO_VIDEO_DIMENSION_RULES,
    "ai_avatar": AVATAR_HEADSHOT_DIMENSION_RULES,
    "pattern_generate": COMMON_IMAGE_DIMENSION_RULES,
    "effect": COMMON_IMAGE_DIMENSION_RULES,
}


def invalid_upload_exception(message: str, status_code: int = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error_code": "invalid_upload", "message": message},
    )


def image_dimension_rules_for_tool(tool_type: Optional[str]) -> ImageDimensionRules:
    return UPLOAD_IMAGE_DIMENSION_RULES_BY_TOOL.get((tool_type or "").strip(), COMMON_IMAGE_DIMENSION_RULES)


def allowed_types_for(kind: MediaKind) -> set[str]:
    return AI_IMAGE_CONTENT_TYPES if kind == "image" else AI_VIDEO_CONTENT_TYPES


def allowed_extensions_for(kind: MediaKind) -> set[str]:
    return AI_IMAGE_EXTENSIONS if kind == "image" else AI_VIDEO_EXTENSIONS


def readable_allowed_types(kind: MediaKind) -> str:
    return "JPG, PNG, or WebP image" if kind == "image" else "MP4, WebM, or MOV video"


def extension_for_content_type(content_type: str) -> str:
    return CONTENT_TYPE_EXTENSIONS.get(content_type, ".bin")


def detect_media_content_type(content: bytes) -> Optional[str]:
    header = content[:32]
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    if header.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        major_brand = header[8:12]
        if major_brand in {b"qt  ", b"moov"}:
            return "video/quicktime"
        return "video/mp4"
    return None


def _image_size_from_content(content: bytes) -> tuple[int, int]:
    try:
        with Image.open(BytesIO(content)) as image:
            width, height = image.size
            orientation = image.getexif().get(274)
            if orientation in {5, 6, 7, 8}:
                width, height = height, width
            return width, height
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise invalid_upload_exception(
            "Image dimensions could not be read. Please choose a different image."
        ) from exc


def _format_dimension_error(rules: ImageDimensionRules, width: int, height: int, reason: str) -> HTTPException:
    return invalid_upload_exception(
        f"{rules.label} is {width}x{height}, which {reason}. {rules.guidance}"
    )


def validate_image_dimensions(content: bytes, rules: ImageDimensionRules) -> tuple[int, int]:
    width, height = _image_size_from_content(content)
    if width < rules.min_width or height < rules.min_height:
        raise _format_dimension_error(
            rules,
            width,
            height,
            f"is smaller than the required {rules.min_width}x{rules.min_height} minimum",
        )
    if width > rules.max_width or height > rules.max_height:
        raise _format_dimension_error(
            rules,
            width,
            height,
            f"exceeds the {rules.max_width}x{rules.max_height} maximum",
        )

    megapixels = (width * height) / 1_000_000
    if megapixels > rules.max_megapixels:
        raise _format_dimension_error(
            rules,
            width,
            height,
            f"is too large ({megapixels:.1f} MP, max {rules.max_megapixels:.0f} MP)",
        )

    aspect_ratio = width / height
    if aspect_ratio < rules.min_aspect_ratio or aspect_ratio > rules.max_aspect_ratio:
        raise _format_dimension_error(
            rules,
            width,
            height,
            f"has an unsupported aspect ratio ({aspect_ratio:.2f})",
        )
    return width, height


def media_kind_from_content_type(content_type: Optional[str]) -> Optional[MediaKind]:
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized in AI_IMAGE_CONTENT_TYPES:
        return "image"
    if normalized in AI_VIDEO_CONTENT_TYPES:
        return "video"
    return None


def validate_uploaded_content(
    *,
    content: bytes,
    declared_content_type: Optional[str],
    expected_kind: Optional[MediaKind],
    max_bytes: int,
    dimension_rules: Optional[ImageDimensionRules] = None,
) -> str:
    """Validate an uploaded file and return the normalized content type."""
    declared = (declared_content_type or "").split(";", 1)[0].strip().lower()
    declared_kind = media_kind_from_content_type(declared)

    if expected_kind and declared not in allowed_types_for(expected_kind):
        raise invalid_upload_exception(
            f"This tool only accepts {readable_allowed_types(expected_kind)} files. Please choose a different file."
        )
    if not expected_kind and declared_kind is None:
        raise invalid_upload_exception(
            "Unsupported file type. Please choose a JPG, PNG, WebP image or an MP4, WebM, MOV video."
        )

    if len(content) > max_bytes:
        limit_mb = max_bytes // (1024 * 1024)
        actual_mb = round(len(content) / (1024 * 1024), 1)
        raise invalid_upload_exception(
            f"File is too large ({actual_mb} MB). Maximum allowed is {limit_mb} MB. Please choose a smaller file.",
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    detected = detect_media_content_type(content)
    if not detected:
        expected_label = readable_allowed_types(expected_kind) if expected_kind else "supported image or video"
        raise invalid_upload_exception(
            f"File content could not be recognized as a {expected_label}. Please choose a different file."
        )

    detected_kind = media_kind_from_content_type(detected)
    if expected_kind and detected_kind != expected_kind:
        raise invalid_upload_exception(
            f"This tool only accepts {readable_allowed_types(expected_kind)} files. Please choose a different file."
        )
    if not expected_kind and detected_kind is None:
        raise invalid_upload_exception(
            "Unsupported file content. Please choose a JPG, PNG, WebP image or an MP4, WebM, MOV video."
        )

    if expected_kind and detected not in allowed_types_for(expected_kind):
        raise invalid_upload_exception(
            f"This tool only accepts {readable_allowed_types(expected_kind)} files. Please choose a different file."
        )

    if detected_kind == "image":
        validate_image_dimensions(content, dimension_rules or COMMON_IMAGE_DIMENSION_RULES)

    return detected


def _extension_from_url(url: str) -> str:
    parsed = urlparse(url)
    return os.path.splitext(parsed.path.lower())[1]


def validate_media_url_or_raise(url: Optional[str], expected_kind: MediaKind, label: str = "file") -> None:
    """Reject obvious URL media mismatches such as .mp4 sent to image-only APIs."""
    if not url:
        return

    cleaned = url.strip()
    if cleaned.startswith("data:"):
        prefix = cleaned.split(",", 1)[0].lower()
        if expected_kind == "image" and not prefix.startswith("data:image/"):
            raise invalid_upload_exception(
                f"{label} must be a {readable_allowed_types(expected_kind)}. Please choose a different file."
            )
        if expected_kind == "video" and not prefix.startswith("data:video/"):
            raise invalid_upload_exception(
                f"{label} must be a {readable_allowed_types(expected_kind)}. Please choose a different file."
            )
        return

    ext = _extension_from_url(cleaned)
    if not ext:
        return

    allowed = allowed_extensions_for(expected_kind)
    opposite = AI_VIDEO_EXTENSIONS if expected_kind == "image" else AI_IMAGE_EXTENSIONS
    if ext in opposite or ext not in allowed:
        raise invalid_upload_exception(
            f"{label} must be a {readable_allowed_types(expected_kind)}. Please choose a different file."
        )


async def _read_image_url_bytes(url: str) -> bytes:
    cleaned = url.strip()
    if cleaned.startswith("data:"):
        try:
            prefix, payload = cleaned.split(",", 1)
        except ValueError as exc:
            raise invalid_upload_exception("Image data URL is invalid. Please choose a different image.") from exc
        if ";base64" not in prefix.lower():
            raise invalid_upload_exception("Image data URL must be base64 encoded. Please choose a different image.")
        try:
            content = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise invalid_upload_exception("Image data URL could not be decoded. Please choose a different image.") from exc
        if len(content) > MAX_DIMENSION_PROBE_BYTES:
            raise invalid_upload_exception("Image is too large to inspect. Please choose a smaller image.")
        return content

    if cleaned.startswith("/static") or cleaned.startswith("static"):
        static_path = "/" + cleaned.lstrip("/")
        candidates = [
            os.path.join("/app", static_path.lstrip("/")),
            os.path.join(os.getcwd(), static_path.lstrip("/")),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                with open(candidate, "rb") as handle:
                    content = handle.read(MAX_DIMENSION_PROBE_BYTES + 1)
                if len(content) > MAX_DIMENSION_PROBE_BYTES:
                    raise invalid_upload_exception("Image is too large to inspect. Please choose a smaller image.")
                return content
        raise invalid_upload_exception("Uploaded image could not be found. Please upload or choose the image again.")

    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise invalid_upload_exception("Image URL must be public HTTP or HTTPS. Please upload or choose the image again.")

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(cleaned)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise invalid_upload_exception("Image could not be reached for validation. Please upload or choose the image again.") from exc

    content = response.content
    if len(content) > MAX_DIMENSION_PROBE_BYTES:
        raise invalid_upload_exception("Image is too large to inspect. Please choose a smaller image.")
    return content


async def validate_image_url_dimensions_or_raise(
    url: Optional[str],
    rules: ImageDimensionRules,
) -> tuple[int, int] | None:
    if not url:
        return None
    content = await _read_image_url_bytes(url)
    content_type = detect_media_content_type(content)
    if media_kind_from_content_type(content_type) != "image":
        raise invalid_upload_exception(
            f"{rules.label} must be a {readable_allowed_types('image')}. Please choose a different file."
        )
    return validate_image_dimensions(content, rules)