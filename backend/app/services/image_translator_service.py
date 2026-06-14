"""
Deterministic image-text translator.

Why this exists: ``vertex_ai_provider.translate_image_text`` asks
``gemini-2.5-flash-image`` to BOTH translate and re-render the image in
one shot. The generation step is fundamentally not letterform-aware for
CJK / Arabic / Thai — even with the exact target string in the prompt
the model produces glyph SHAPES that look like the target script but
are not real characters (e.g. "Summer Sale 50% Off" → "妥冬偂飾 Sale
50% 折卬" on the live build).

This module replaces the rendering pass with a deterministic pipeline:

  1. Multimodal Gemini extracts each visible text block, returning
     bounding box (normalized 0-1000 coords, Gemini's standard format),
     source text, and a translation in one structured-output call.
  2. PIL inpaints each bbox with a colour sampled from the surrounding
     pixels — covers the original text.
  3. PIL.ImageDraw renders the translation at the same bbox using a CJK
     font (NotoSans CJK is in the base image) so every glyph is the
     real character.

The result has perfect character accuracy in any language Gemini can
translate to. The drawback vs. the generative path is that we can't
match decorative typography exactly — translated text is set in a
neutral sans-serif. For e-commerce / signage / packaging this is the
correct tradeoff: visible-broken Chinese is far worse than crisp
sans-serif Chinese.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Font discovery
# ─────────────────────────────────────────────────────────────────────────────

# Debian's fonts-noto-cjk package drops the font under one of these names
# depending on package version. We try each in priority order at module
# load so the font is paid for once, not per request.
_CJK_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    # macOS dev fallbacks
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
]


def _find_cjk_font_path() -> Optional[str]:
    for path in _CJK_FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


CJK_FONT_PATH = _find_cjk_font_path()
if CJK_FONT_PATH:
    logger.info("[image_translator] CJK font: %s", CJK_FONT_PATH)
else:
    logger.warning("[image_translator] No CJK font found — CJK output will tofu")


# ─────────────────────────────────────────────────────────────────────────────
# Gemini OCR + bbox + translate (one structured-output call)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TextRegion:
    """One detected text block, with normalized [0..1000] coordinates."""

    source: str
    translated: str
    # Gemini multimodal returns bounding boxes as [ymin, xmin, ymax, xmax]
    # on a 0..1000 grid. We keep that convention end-to-end and convert
    # to pixel coords only at the moment PIL needs them.
    ymin: int
    xmin: int
    ymax: int
    xmax: int

    def to_pixels(self, width: int, height: int) -> Tuple[int, int, int, int]:
        """Return (x0, y0, x1, y1) in absolute pixel coords."""
        x0 = max(0, int(self.xmin / 1000.0 * width))
        y0 = max(0, int(self.ymin / 1000.0 * height))
        x1 = min(width, int(self.xmax / 1000.0 * width))
        y1 = min(height, int(self.ymax / 1000.0 * height))
        if x1 <= x0:
            x1 = min(width, x0 + 1)
        if y1 <= y0:
            y1 = min(height, y0 + 1)
        return x0, y0, x1, y1


# Prompt asks Gemini to return JSON with both translated text AND
# bounding boxes. The bbox format matches Gemini's documented "ground"
# convention (ymin, xmin, ymax, xmax on a 0..1000 grid) so we don't need
# any coordinate conversion on the model side.
_OCR_BBOX_PROMPT_TEMPLATE = (
    "Extract every distinct visible text block in this image{source_hint}, "
    "then translate each block into {target_language}.\n\n"
    "For each block, return its bounding box on a 0..1000 normalized grid "
    "(0 = top/left, 1000 = bottom/right) in the order [ymin, xmin, ymax, xmax].\n\n"
    "Keep brand names, URLs, prices, numbers, and currency symbols unchanged "
    "unless they are normal words that must be localized.\n\n"
    "Group visually-separated text blocks (one signage line, one product label, "
    "one sticker) as separate items. Inside a single block, preserve line "
    "breaks as '\\n' inside the source/translated strings.\n\n"
    "{instructions_hint}"
    "Return ONLY a JSON array — no prose, no markdown fences — of objects with "
    "this exact shape:\n"
    '  [{{"source": "<original text>", "translated": "<target-language text>", '
    '"box_2d": [<ymin>, <xmin>, <ymax>, <xmax>]}}, ...]\n\n'
    "If the image has no visible text, return []."
)


async def _ocr_translate(
    client,
    model: str,
    img_bytes: bytes,
    mime: str,
    target_language: str,
    source_language: Optional[str],
    instructions: Optional[str] = None,
) -> List[TextRegion]:
    from google.genai import types

    source_hint = f" from {source_language}" if source_language else ""
    # The user's tone/brand guidance (e.g. "keep prices unchanged", "casual
    # tone", "keep brand name in English") shapes HOW each block is
    # translated. Previously it was collected in the UI and then dropped on
    # the floor; now it reaches the translation model.
    instructions_hint = (
        f"Follow these additional translation instructions: {instructions.strip()}\n\n"
        if instructions and instructions.strip()
        else ""
    )
    prompt = _OCR_BBOX_PROMPT_TEMPLATE.format(
        source_hint=source_hint,
        target_language=target_language,
        instructions_hint=instructions_hint,
    )
    response = await asyncio.to_thread(
        client.models.generate_content,
        model=model,
        contents=[
            types.Part.from_bytes(data=img_bytes, mime_type=mime),
            prompt,
        ],
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=4096,
            response_mime_type="application/json",
        ),
    )

    raw = (response.text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:].lstrip()
    try:
        parsed = json.loads(raw or "[]")
    except json.JSONDecodeError as exc:
        logger.warning("[image_translator] OCR JSON parse failed: %s — raw=%s", exc, raw[:300])
        return []

    if not isinstance(parsed, list):
        return []

    regions: List[TextRegion] = []
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        src = str(entry.get("source") or "").strip()
        tgt = str(entry.get("translated") or "").strip()
        bbox = entry.get("box_2d") or entry.get("bbox") or entry.get("bounding_box")
        if not (src and tgt and isinstance(bbox, list) and len(bbox) == 4):
            continue
        try:
            ymin, xmin, ymax, xmax = (int(round(float(v))) for v in bbox)
        except (TypeError, ValueError):
            continue
        if ymax <= ymin or xmax <= xmin:
            continue
        regions.append(
            TextRegion(source=src, translated=tgt, ymin=ymin, xmin=xmin, ymax=ymax, xmax=xmax)
        )
    return regions


# ─────────────────────────────────────────────────────────────────────────────
# PIL rendering — inpaint original text + draw translation
# ─────────────────────────────────────────────────────────────────────────────


def _sample_background_color(img: Image.Image, box: Tuple[int, int, int, int]) -> Tuple[int, int, int]:
    """Pick a 'background' colour by sampling a thin frame just OUTSIDE the
    text box. Falls back to the bbox average when the image edge limits how
    much frame we can read.

    The frame approach beats sampling inside the bbox (which would average
    in the text colour) and beats the page's median (which would average in
    the foreground subject)."""
    width, height = img.size
    x0, y0, x1, y1 = box
    margin = max(4, min((x1 - x0), (y1 - y0)) // 8)
    fx0 = max(0, x0 - margin)
    fy0 = max(0, y0 - margin)
    fx1 = min(width, x1 + margin)
    fy1 = min(height, y1 + margin)

    crop = img.crop((fx0, fy0, fx1, fy1)).convert("RGB")
    # Mask out the inner (text) rectangle by drawing it over with a unique
    # sentinel colour, then drop those pixels before averaging. We approximate
    # by reducing colours and picking the mode, which is robust enough for
    # mostly-uniform backgrounds (sale cards, packaging, signage).
    small = crop.resize((min(crop.width, 64), min(crop.height, 64)))
    quantized = small.quantize(colors=8).convert("RGB")
    pixels = list(quantized.getdata())
    if not pixels:
        return (255, 255, 255)
    # Tally and pick the most common, but skip any pixel inside the text box
    # by recomputing relative bounds on the resized frame.
    rw, rh = quantized.size
    inner_x0 = int((x0 - fx0) / max(1, fx1 - fx0) * rw)
    inner_y0 = int((y0 - fy0) / max(1, fy1 - fy0) * rh)
    inner_x1 = int((x1 - fx0) / max(1, fx1 - fx0) * rw)
    inner_y1 = int((y1 - fy0) / max(1, fy1 - fy0) * rh)
    counts: Dict[Tuple[int, int, int], int] = {}
    for y in range(rh):
        for x in range(rw):
            if inner_x0 <= x < inner_x1 and inner_y0 <= y < inner_y1:
                continue
            px = pixels[y * rw + x]
            counts[px] = counts.get(px, 0) + 1
    if not counts:
        return (255, 255, 255)
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _sample_text_color(img: Image.Image, box: Tuple[int, int, int, int], bg: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Pick the dominant non-background colour from inside the text box."""
    crop = img.crop(box).convert("RGB")
    small = crop.resize((min(crop.width, 48), min(crop.height, 48)))
    quantized = small.quantize(colors=8).convert("RGB")
    counts: Dict[Tuple[int, int, int], int] = {}
    for px in quantized.getdata():
        if _color_distance(px, bg) < 40:
            continue
        counts[px] = counts.get(px, 0) + 1
    if not counts:
        # Decide by overall lightness — dark bg → light text, vice versa.
        return (255, 255, 255) if sum(bg) < 384 else (24, 24, 24)
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _color_distance(a: Tuple[int, int, int], b: Tuple[int, int, int]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def _background_is_textured(img: Image.Image, box: Tuple[int, int, int, int], threshold: float = 22.0) -> bool:
    """True when the area around the text box has high colour spread (gradient,
    photo, or pattern). For those a flat fill leaves an obvious rectangle, so
    the caller blurs the region instead of stamping a solid slab."""
    width, height = img.size
    x0, y0, x1, y1 = box
    margin = max(4, min((x1 - x0), (y1 - y0)) // 6)
    fx0, fy0 = max(0, x0 - margin), max(0, y0 - margin)
    fx1, fy1 = min(width, x1 + margin), min(height, y1 + margin)
    crop = img.crop((fx0, fy0, fx1, fy1)).convert("RGB").resize((32, 32))
    px = list(crop.getdata())
    if len(px) < 8:
        return False
    n = len(px)
    mean = (
        sum(p[0] for p in px) / n,
        sum(p[1] for p in px) / n,
        sum(p[2] for p in px) / n,
    )
    spread = sum(_color_distance(p, mean) for p in px) / n
    return spread > threshold


def _outline_for(text_color: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Pick a contrasting outline colour so the translated text stays legible
    whether it lands on a flat fill or a blurred photo region."""
    luminance = 0.299 * text_color[0] + 0.587 * text_color[1] + 0.114 * text_color[2]
    return (0, 0, 0) if luminance > 140 else (255, 255, 255)


def _fit_font(
    text: str, box_width: int, box_height: int, font_path: Optional[str]
) -> ImageFont.FreeTypeFont:
    """Binary-search the largest font size where the rendered text fits the
    bbox (longest single line stays within width; total height stays within
    height). Lines are split on explicit '\\n' so callers can preserve
    multi-line layouts coming back from the OCR step."""
    lines = text.split("\n") or [text]
    # Start with a height-based upper bound; refine via measurement.
    hi = max(8, int(box_height / max(1, len(lines)) * 1.2))
    lo = 6
    best = lo
    while lo <= hi:
        mid = (lo + hi) // 2
        try:
            font = (
                ImageFont.truetype(font_path, size=mid)
                if font_path
                else ImageFont.load_default()
            )
        except (OSError, IOError):
            font = ImageFont.load_default()
            return font
        widest = 0
        total_h = 0
        line_h = mid + 4
        for line in lines:
            bbox = font.getbbox(line)
            widest = max(widest, bbox[2] - bbox[0])
            total_h += line_h
        if widest <= box_width and total_h <= box_height:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    try:
        return ImageFont.truetype(font_path, size=best) if font_path else ImageFont.load_default()
    except (OSError, IOError):
        return ImageFont.load_default()


def render_translation(img_bytes: bytes, regions: List[TextRegion]) -> bytes:
    """Take the original image + Gemini-returned regions and produce a
    new PNG with each region inpainted and re-rendered."""
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    width, height = img.size
    draw = ImageDraw.Draw(img)

    for region in regions:
        if not region.translated.strip():
            continue
        box = region.to_pixels(width, height)
        # Inflate slightly so the inpaint covers any anti-aliased edges
        # of the original glyphs.
        pad_x = max(2, (box[2] - box[0]) // 20)
        pad_y = max(2, (box[3] - box[1]) // 20)
        padded = (
            max(0, box[0] - pad_x),
            max(0, box[1] - pad_y),
            min(width, box[2] + pad_x),
            min(height, box[3] + pad_y),
        )
        bg = _sample_background_color(img, padded)
        text_color = _sample_text_color(img, box, bg)
        # Cover the original glyphs. On a uniform background a flat fill is the
        # cleanest result; on a gradient / photo / pattern a flat slab leaves an
        # obvious rectangle, so blur the region instead — the old text smears
        # into the surrounding colours while the gradient/texture survives.
        if _background_is_textured(img, box):
            blur_radius = max(6, min(padded[3] - padded[1], padded[2] - padded[0]) // 3)
            region_crop = img.crop(padded).filter(ImageFilter.GaussianBlur(radius=blur_radius))
            img.paste(region_crop, (padded[0], padded[1]))
        else:
            draw.rectangle(padded, fill=bg)

        font = _fit_font(
            region.translated,
            padded[2] - padded[0] - 8,
            padded[3] - padded[1] - 4,
            CJK_FONT_PATH,
        )
        # Centre the rendered text inside the bbox so a tight-fit translation
        # doesn't sit flush-left under a centred original.
        lines = region.translated.split("\n") or [region.translated]
        line_height = font.size + 4
        total_h = line_height * len(lines)
        cy = padded[1] + max(0, (padded[3] - padded[1] - total_h) // 2)
        # A thin contrasting outline keeps the text readable on top of a
        # blurred photo region (where there's no flat backing colour).
        stroke_w = max(1, font.size // 14)
        outline = _outline_for(text_color)
        for line in lines:
            text_box = font.getbbox(line)
            tw = text_box[2] - text_box[0]
            cx = padded[0] + max(0, (padded[2] - padded[0] - tw) // 2)
            draw.text((cx, cy), line, font=font, fill=text_color, stroke_width=stroke_w, stroke_fill=outline)
            cy += line_height

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


async def translate_image_pil(
    text_client,
    text_model: str,
    img_bytes: bytes,
    mime: str,
    target_language: str,
    source_language: Optional[str] = None,
    instructions: Optional[str] = None,
) -> bytes:
    """End-to-end: take source PNG/JPEG bytes, return translated PNG bytes.

    Raises on a hard failure (Gemini OCR error, image decode error). Returns
    the original image unchanged when Gemini reports no text regions — the
    caller can decide whether that's success or a soft error.
    """
    regions = await _ocr_translate(
        text_client, text_model, img_bytes, mime, target_language, source_language, instructions
    )
    if not regions:
        logger.info("[image_translator] no text regions returned; returning source unchanged")
        return img_bytes
    return await asyncio.to_thread(render_translation, img_bytes, regions)
