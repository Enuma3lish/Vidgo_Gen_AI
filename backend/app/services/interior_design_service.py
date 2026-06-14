"""
Interior Design Service
Uses Gemini 2.5 Flash Image for AI-powered room redesign and interior design generation.

Features:
- Image + Text → Image: Upload room photo + text prompt = redesigned room
- Text → Image: Generate design from text description only
- Multi-image Fusion: Combine room photo with style reference
- Iterative Editing: Multi-turn dialogue for continuous refinement
- Style Transfer: Apply specific design styles to rooms
"""
import asyncio
import logging
import base64
import os
import uuid
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# Available interior design styles
DESIGN_STYLES = {
    "modern_minimalist": {
        "id": "modern_minimalist",
        "name": "Modern Minimalist",
        "name_zh": "現代極簡",
        "description": "Clean lines, neutral colors, minimal furniture, open spaces",
        "prompt_suffix": "modern minimalist interior, clean geometric lines, neutral white and warm grey palette, low-profile furniture with hidden storage, polished concrete or light oak flooring, floor-to-ceiling windows with sheer linen curtains, recessed LED strip lighting, single statement art piece, architectural visualization quality"
    },
    "scandinavian": {
        "id": "scandinavian",
        "name": "Scandinavian",
        "name_zh": "北歐風格",
        "description": "Light wood, white walls, cozy textiles, functional design",
        "prompt_suffix": "Scandinavian hygge interior, pale birch wood furniture with rounded edges, matte white walls, chunky knit wool throw on light grey sofa, sheepskin rug on pale oak herringbone floor, brass pendant lamp, potted monstera in ceramic planter, soft north-facing window light, warm cozy functional living"
    },
    "japanese": {
        "id": "japanese",
        "name": "Japanese Zen",
        "name_zh": "日式禪風",
        "description": "Tatami, shoji screens, natural materials, zen simplicity",
        "prompt_suffix": "Japanese wabi-sabi zen interior, tatami mat flooring with shoji paper sliding screens, low natural cypress wood platform furniture, ikebana arrangement, tokonoma alcove, diffused paper lantern lighting, muted earth tones with charcoal and cream, bamboo accent wall, serene meditative atmosphere"
    },
    "industrial": {
        "id": "industrial",
        "name": "Industrial",
        "name_zh": "工業風",
        "description": "Exposed brick, metal accents, raw textures, urban loft",
        "prompt_suffix": "industrial loft interior, exposed red brick walls with original mortar, black steel I-beam ceiling with exposed ductwork, polished concrete floor, oversized factory windows with black metal mullions, Edison bulb pendant cluster, worn leather tufted sofa, reclaimed wood and steel pipe shelving, warehouse conversion aesthetic"
    },
    "bohemian": {
        "id": "bohemian",
        "name": "Bohemian",
        "name_zh": "波西米亞",
        "description": "Eclectic patterns, rich colors, layered textiles, artistic",
        "prompt_suffix": "bohemian eclectic interior, layered Moroccan kilim rugs on terracotta tile, macrame wall hanging, rattan peacock chair with colorful cushions, trailing pothos and fiddle leaf fig plants, woven basket pendant lamps, amber string lights, rich emerald and burnt orange jewel tones, artistic maximalist lived-in atmosphere"
    },
    "mediterranean": {
        "id": "mediterranean",
        "name": "Mediterranean",
        "name_zh": "地中海風格",
        "description": "Terracotta, blue accents, arched doorways, rustic charm",
        "prompt_suffix": "Mediterranean coastal interior, hand-laid terracotta hexagonal floor tiles, whitewashed lime plaster walls with arched doorways, cerulean blue window shutters, wrought iron fixtures with candle-style bulbs, solid wood dining table with linen runner, ceramic hand-painted accent tiles, warm golden afternoon sunlight, relaxed coastal elegance"
    },
    "art_deco": {
        "id": "art_deco",
        "name": "Art Deco",
        "name_zh": "裝飾藝術",
        "description": "Geometric patterns, metallic accents, refined materials, sophistication",
        "prompt_suffix": "Art Deco style interior, geometric chevron patterned stone floor in black and white, deep green tufted sofa with metallic nailhead trim, sunburst decorative mirror, fluted column details, lacquered black console with brass inlay, glass display cabinet, dramatic uplighting on fluted wall panels, 1920s inspired geometric sophistication"
    },
    "mid_century_modern": {
        "id": "mid_century_modern",
        "name": "Mid-Century Modern",
        "name_zh": "中世紀現代",
        "description": "Organic curves, retro furniture, bold colors, iconic design",
        "prompt_suffix": "mid-century modern interior circa 1960, classic molded plywood lounge chair with leather cushion, teak credenza with tapered legs, starburst metal chandelier, sunburst wall clock, bold mustard yellow accent wall, geometric patterned area rug, large picture window with greenery view, retro atomic age style"
    },
    "coastal": {
        "id": "coastal",
        "name": "Coastal",
        "name_zh": "海岸風格",
        "description": "Blue tones, white furniture, nautical elements, beachy",
        "prompt_suffix": "coastal Hampton interior, whitewashed shiplap walls, bleached driftwood-finish wide plank flooring, soft navy and crisp white linen upholstery, natural seagrass baskets and rattan pendant lights, large sliding glass doors open to ocean view, weathered rope detail accents, bright airy natural daylight, relaxed seaside living"
    },
    "farmhouse": {
        "id": "farmhouse",
        "name": "Farmhouse",
        "name_zh": "農舍風格",
        "description": "Rustic wood, vintage accents, cozy warmth, country charm",
        "prompt_suffix": "modern farmhouse interior, reclaimed barn wood accent wall with original nail holes, white subway tile backsplash with dark grout, apron-front farmhouse sink, open shelving with mason jars and stoneware, black matte hardware on cream Shaker cabinets, wrought iron chandelier with Edison bulbs, wide plank pine floor, warm morning light"
    }
}


# ── Atmosphere adjustments (lighting / color temperature / material) ───────
# Shared by 立體圖 (isometric) and 3D 效果圖 (render tiers) so the user can
# fine-tune the same render instead of regenerating blind. Clauses are
# additive — they style light and surfaces only and never touch geometry,
# so they stay compatible with the anti-hallucination invariants below.
LIGHTING_TONES = {
    "daylight":           "Lit by soft natural daylight through the windows; balanced exposure, no harsh shadows.",
    "warm_evening":       "Warm evening interior lighting from layered lamps; cozy atmospheric ambience.",
    "golden_hour":        "Late-golden-hour sunlight raking across surfaces; warm amber highlights, long soft shadows.",
    "overcast_soft":      "Soft diffuse overcast daylight; even, shadowless illumination that reads true material colors.",
    "dramatic_spotlight": "Dramatic directional accent spotlighting; bold shadows and high contrast.",
    "night":              "Night scene lit only by the interior artificial lighting plan; warm pools of light, dark windows.",
}

MATERIAL_ACCENTS = {
    "wood":      "Accent material: warm natural oak / walnut wood on floors and feature surfaces.",
    "marble":    "Accent material: veined Calacatta or Carrara marble on counters and feature surfaces.",
    "concrete":  "Accent material: polished pigmented concrete on floors and select walls.",
    "linen":     "Accent material: natural unbleached linen on upholstery, drapery, and soft furnishings.",
    "brass":     "Accent material: brass and bronze hardware, lighting, frames, and decor details.",
    "leather":   "Accent material: rich saddle or oxblood leather on major upholstered pieces.",
    "terrazzo":  "Accent material: terrazzo with mixed-color aggregate on floors and select surfaces.",
}


def build_atmosphere_clause(
    lighting_tone: Optional[str] = None,
    color_temperature: Optional[int] = None,
    material_accent: Optional[str] = None,
) -> str:
    """Compose the additive lighting / color-temperature / material clause.

    color_temperature is Kelvin (2700-6500). We translate it into words as
    well as the number because image models follow "warm 2700K candle-like"
    far more reliably than a bare numeral.
    """
    parts: List[str] = []
    tone = LIGHTING_TONES.get((lighting_tone or "").lower())
    if tone:
        parts.append(tone)
    if color_temperature:
        k = max(2000, min(8000, int(color_temperature)))
        if k <= 3000:
            feel = "very warm, amber candle-like glow"
        elif k <= 3800:
            feel = "warm white, cozy residential tone"
        elif k <= 4800:
            feel = "neutral white, true-to-life colors"
        elif k <= 5800:
            feel = "daylight white, crisp and clean"
        else:
            feel = "cool white, slightly blue contemporary tone"
        parts.append(
            f"Overall light color temperature approximately {k}K ({feel}); "
            "apply this white balance consistently across the whole image."
        )
    accent = MATERIAL_ACCENTS.get((material_accent or "").lower())
    if accent:
        parts.append(accent)
    return (" " + " ".join(parts)) if parts else ""


# Room types for better context
ROOM_TYPES = {
    "living_room": {
        "id": "living_room",
        "name": "Living Room",
        "name_zh": "客廳",
        "context": "residential living room approximately 20-30 square meters, featuring a main seating area with sofa, coffee table, TV console or entertainment wall, area rug, and ambient plus accent lighting"
    },
    "bedroom": {
        "id": "bedroom",
        "name": "Bedroom",
        "name_zh": "臥室",
        "context": "residential bedroom approximately 12-20 square meters, featuring a queen or king bed with headboard, matching nightstands with table lamps, wardrobe or closet area, and soft warm ambient lighting"
    },
    "kitchen": {
        "id": "kitchen",
        "name": "Kitchen",
        "name_zh": "廚房",
        "context": "residential kitchen approximately 8-15 square meters, featuring upper and lower cabinetry, countertop workspace, built-in appliances including oven and cooktop, task lighting under cabinets, and a backsplash area"
    },
    "bathroom": {
        "id": "bathroom",
        "name": "Bathroom",
        "name_zh": "浴室",
        "context": "residential bathroom approximately 4-8 square meters, featuring a vanity with mirror and basin, walk-in shower or freestanding bathtub, wall and floor tiling, and recessed waterproof lighting"
    },
    "dining_room": {
        "id": "dining_room",
        "name": "Dining Room",
        "name_zh": "餐廳",
        "context": "residential dining area approximately 10-18 square meters, featuring a dining table seating 4-6 with chairs, overhead pendant or chandelier lighting, and a sideboard or buffet cabinet"
    },
    "home_office": {
        "id": "home_office",
        "name": "Home Office",
        "name_zh": "書房",
        "context": "residential home office approximately 8-12 square meters, featuring a work desk with ergonomic chair, bookshelves or wall-mounted shelving, task desk lamp, and organized cable management"
    },
    "balcony": {
        "id": "balcony",
        "name": "Balcony",
        "name_zh": "陽台",
        "context": "residential enclosed or open balcony approximately 4-10 square meters, featuring outdoor-rated seating with weather-resistant cushions, potted plants, and string lights or lantern lighting"
    }
}


class InteriorDesignService:
    """
    Interior Design Service using Gemini image generation.

    Supports:
    - Image + Text → Image (room redesign)
    - Text → Image (generate from description)
    - Multi-image Fusion (room + style reference)
    - Iterative Editing (multi-turn refinement)
    - Style Transfer (apply design styles)

    Auth priority:
    1. Vertex AI ADC (service account in Cloud Run, gcloud locally) — preferred
    2. GEMINI_API_KEY env var — fallback (requires valid key)
    """

    # Vertex AI endpoint (uses ADC / service account — no API key needed)
    VERTEX_BASE_URL = "https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/publishers/google/models/{model}:generateContent"
    # Google AI endpoint (requires API key)
    GENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    # gemini-2.5-flash-image is the current GA model that supports multimodal
    # image input + image output generation. The legacy gemini-2.0-flash-exp
    # alias was retired upstream and now returns HTTP 404 from both Vertex
    # and the Google AI endpoint, breaking RoomRedesign tabs 1-3 for paid
    # users (admin gets HTTP 500 "API error: 404").
    MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'GEMINI_API_KEY', '')
        self.vertex_project = getattr(settings, 'VERTEX_AI_PROJECT', '')
        # gemini-2.5-flash-image is only available in us-central1 (and global)
        # on Vertex AI; asia-east1 returns NOT_FOUND. Pin the GenAI location
        # via VERTEX_AI_GENAI_LOCATION (used elsewhere in the codebase) and
        # fall back to us-central1 rather than the legacy asia-east1 default.
        self.vertex_location = os.environ.get(
            "VERTEX_AI_GENAI_LOCATION",
            getattr(settings, 'VERTEX_AI_GENAI_LOCATION', None)
            or "us-central1",
        )
        self.static_dir = Path("/app/static/generated/interior")
        self.static_dir.mkdir(parents=True, exist_ok=True)

        # Conversation history for iterative editing
        self._conversations: Dict[str, List[Dict]] = {}

    async def _get_vertex_token(self) -> Optional[str]:
        """Get OAuth2 access token via ADC (Application Default Credentials)."""
        try:
            import google.auth
            import google.auth.transport.requests
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            credentials.refresh(google.auth.transport.requests.Request())
            return credentials.token
        except Exception as exc:
            logger.warning(f"[InteriorDesign] ADC token failed: {exc}")
            return None

    async def _get_headers_and_url(self) -> Tuple[Dict[str, str], str]:
        """
        Return (headers, base_url) choosing Vertex AI ADC if available,
        falling back to Google AI API key.
        """
        # Try Vertex AI ADC first
        if self.vertex_project:
            token = await self._get_vertex_token()
            if token:
                url = self.VERTEX_BASE_URL.format(
                    location=self.vertex_location,
                    project=self.vertex_project,
                    model=self.MODEL,
                )
                return {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}, url

        # Fallback: Google AI API key endpoint
        if self.api_key:
            url = f"{self.GENAI_BASE_URL}/models/{self.MODEL}:generateContent"
            return {"Content-Type": "application/json"}, url

        raise RuntimeError("No Gemini credentials available: set VERTEX_AI_PROJECT (ADC) or GEMINI_API_KEY")

    def _get_headers(self) -> Dict[str, str]:
        return {"Content-Type": "application/json"}

    @staticmethod
    def _extract_block_reason(data: Dict[str, Any]) -> Optional[str]:
        """Pull a human-meaningful reason out of a Gemini response that came
        back 200 but produced no image: candidate.finishReason and/or
        promptFeedback.blockReason. Returns None for a normal STOP finish
        (i.e. the model just chose to reply with text-only this time)."""
        feedback = data.get("promptFeedback") or {}
        block = feedback.get("blockReason")
        candidates = data.get("candidates") or []
        finish = candidates[0].get("finishReason") if candidates else None
        parts: List[str] = []
        if finish and finish not in ("STOP", "MAX_TOKENS"):
            parts.append(f"finishReason={finish}")
        if block:
            parts.append(f"blockReason={block}")
        return ", ".join(parts) if parts else None

    async def _generate_image(
        self,
        request_body: Dict[str, Any],
        prefix: str,
        attempts: int = 3,
    ) -> Dict[str, Any]:
        """POST a generateContent body and extract the image, retrying when the
        model returns a 200 with text-but-no-image.

        gemini-2.5-flash-image does NOT reliably emit an image on every call —
        at the temperatures we use it sometimes replies with only a text part
        (a description, a clarifying question, a soft refusal). A single shot
        therefore failed intermittently for the same input. We retry those
        empty responses; on the final miss we surface the real finishReason /
        blockReason instead of the generic "No image in response" so a safety
        block is distinguishable from a transient miss.

        Hard blocks (SAFETY / PROHIBITED / RECITATION / BLOCKLIST) won't change
        on retry, so we bail out of the loop early for those.
        """
        last_result: Dict[str, Any] = {"success": False, "error": "No image generated"}

        for attempt in range(attempts):
            try:
                headers, endpoint_url = await self._get_headers_and_url()
                params: Dict[str, str] = {}
                if "generativelanguage.googleapis.com" in endpoint_url and self.api_key:
                    params = {"key": self.api_key}

                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(
                        endpoint_url,
                        params=params,
                        headers=headers,
                        json=request_body,
                    )

                if response.status_code == 200:
                    data = response.json()
                    result = await self._process_image_response(data, prefix)
                    if result.get("success") and result.get("image_url"):
                        return result

                    # 200 but no image — figure out why and decide whether a
                    # retry could help.
                    reason = self._extract_block_reason(data)
                    last_result = {
                        "success": False,
                        "error": (
                            f"Image generation was blocked ({reason})."
                            if reason
                            else "The model did not return an image. Please try again."
                        ),
                        "finish_reason": reason,
                    }
                    if reason and any(
                        token in reason.upper()
                        for token in ("SAFETY", "PROHIBITED", "RECITATION", "BLOCKLIST")
                    ):
                        # Deterministic block — retrying wastes a call.
                        break
                    logger.warning(
                        "[InteriorDesign] %s: 200 but no image (reason=%s) — attempt %d/%d",
                        prefix, reason, attempt + 1, attempts,
                    )
                else:
                    error_text = response.text[:500]
                    logger.error("Gemini API error: %s - %s", response.status_code, error_text)
                    last_result = {
                        "success": False,
                        "error": f"API error: {response.status_code}",
                        "details": error_text,
                    }
                    # 4xx (bad request, auth, quota) won't fix on retry; only
                    # retry 5xx upstream blips.
                    if response.status_code < 500:
                        break

            except Exception as e:  # noqa: BLE001
                logger.error("[InteriorDesign] %s attempt %d failed: %s", prefix, attempt + 1, e)
                last_result = {"success": False, "error": str(e)}

            if attempt < attempts - 1:
                await asyncio.sleep(1.5 * (attempt + 1))

        return last_result

    async def _fetch_image_as_base64(self, image_url: str) -> Tuple[str, str]:
        """Fetch image from URL and return as base64 with mime type."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(image_url)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "image/jpeg")
                mime_type = content_type.split(";")[0]
                image_data = base64.b64encode(response.content).decode()
                return image_data, mime_type
            raise Exception(f"Failed to fetch image: {response.status_code}")

    def _save_generated_image(self, image_data: bytes, prefix: str = "design", content_type: str = "image/png") -> str:
        """Save generated image to durable public storage when available."""
        filename = f"{prefix}_{uuid.uuid4().hex[:8]}.png"

        try:
            from app.services.gcs_storage_service import get_gcs_storage
            gcs = get_gcs_storage()
            if gcs.enabled:
                return gcs.upload_public(
                    data=image_data,
                    blob_name=f"generated/interior/{filename}",
                    content_type=content_type or "image/png",
                )
        except Exception as exc:
            logger.warning("GCS interior upload failed; falling back to local static: %s", exc)

        filepath = self.static_dir / filename
        filepath.write_bytes(image_data)
        return f"/static/generated/interior/{filename}"

    async def get_styles(self) -> List[Dict[str, Any]]:
        """Get all available interior design styles."""
        return list(DESIGN_STYLES.values())

    async def get_room_types(self) -> List[Dict[str, Any]]:
        """Get all available room types."""
        return list(ROOM_TYPES.values())

    # =========================================================================
    # Core Design Functions
    # =========================================================================

    async def redesign_room(
        self,
        room_image_base64: Optional[str] = None,
        room_image_url: Optional[str] = None,
        prompt: str = "",
        style_id: Optional[str] = None,
        room_type: Optional[str] = None,
        keep_layout: bool = True,
        style_prompt_suffix: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Redesign a room based on image and text prompt.

        Image + Text → Image

        Args:
            room_image_base64: Base64-encoded room image
            room_image_url: URL of room image (alternative)
            prompt: Text description of desired changes
            style_id: Optional design style to apply (looked up in DESIGN_STYLES)
            room_type: Type of room for context
            keep_layout: Whether to preserve room layout
            style_prompt_suffix: Pre-resolved style prompt. When provided,
                bypasses the DESIGN_STYLES lookup — lets the caller resolve
                the style against EXTERIOR_STYLES / COMMERCIAL_STYLES (which
                live in tools.py) and pass the prompt through directly so
                non-residential style picks aren't silently dropped.

        Returns:
            Dict with redesigned image URL and description
        """
        # Get image as base64
        if room_image_url and not room_image_base64:
            try:
                room_image_base64, mime_type = await self._fetch_image_as_base64(room_image_url)
            except Exception as e:
                return {"success": False, "error": f"Failed to fetch image: {e}"}

        if not room_image_base64:
            return {"success": False, "error": "No room image provided"}

        # Determine mime type from base64
        mime_type = "image/jpeg"
        if room_image_base64.startswith("iVBOR"):
            mime_type = "image/png"

        # Build the prompt — photorealistic architectural visualization quality
        full_prompt = (
            "Redesign this room into a photorealistic interior design rendering. "
            "Output must look like a professional architectural visualization photograph "
            "with correct perspective, realistic material textures, and natural lighting. "
            "The room must be empty with no people, no person, no human figure, no silhouette. "
            "Do not include any luxury branded items. "
        )

        if keep_layout:
            full_prompt += "Preserve the existing window positions, door locations, and room geometry exactly. "

        if room_type and room_type in ROOM_TYPES:
            room_context = ROOM_TYPES[room_type]["context"]
            full_prompt += f"This is a {room_context}. "

        # Style resolution: caller-supplied suffix wins (covers exterior /
        # commercial catalogs in tools.py); otherwise fall back to the
        # residential DESIGN_STYLES dict here. Without the override path
        # an exterior/commercial style_id silently produced a generic
        # residential render — see room-redesign analysis 2026-05-27.
        if style_prompt_suffix:
            full_prompt += f"Apply {style_prompt_suffix}. "
        elif style_id and style_id in DESIGN_STYLES:
            style_suffix = DESIGN_STYLES[style_id]["prompt_suffix"]
            full_prompt += f"Apply {style_suffix}. "

        full_prompt += prompt

        request_body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"inline_data": {"mime_type": mime_type, "data": room_image_base64}},
                        {"text": full_prompt},
                    ],
                }
            ],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "temperature": 0.8,
            },
        }
        return await self._generate_image(request_body, "redesign")

    async def render_from_floorplan(
        self,
        floorplan_image_url: Optional[str] = None,
        floorplan_image_base64: Optional[str] = None,
        style_id: Optional[str] = None,
        room_type: Optional[str] = None,
        extra_prompt: str = "",
        lighting_tone: Optional[str] = None,
        color_temperature: Optional[int] = None,
        material_accent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Floor-plan image → photorealistic isometric interior render.

        Uses a floor-plan-specific primary prompt so Gemini isn't confused
        by the generic "redesign this room" instructions used in redesign_room().
        lighting_tone / color_temperature / material_accent are the 立體圖
        fine-tune knobs — additive atmosphere clauses, never structural.
        """
        pass  # credentials resolved dynamically via _get_headers_and_url()

        if floorplan_image_url and not floorplan_image_base64:
            try:
                floorplan_image_base64, _ = await self._fetch_image_as_base64(floorplan_image_url)
            except Exception as exc:
                return {"success": False, "error": f"Failed to fetch floor plan image: {exc}"}

        if not floorplan_image_base64:
            return {"success": False, "error": "No floor plan image provided"}

        mime_type = "image/png" if floorplan_image_base64.startswith("iVBOR") else "image/jpeg"

        # 2026-06-12 (owner): 立體圖 is a WHOLE-PLAN dollhouse — every room in
        # the plan must appear, furnished per its function. The old single-room
        # context ("residential living room 20-30 sqm with sofa...") made the
        # model zoom into one room; room_type is now only a focus hint.
        room_hint = ""
        if room_type and room_type in ROOM_TYPES:
            room_hint = (
                f"Give extra design attention to the {ROOM_TYPES[room_type]['name']}, "
                "but still render EVERY room shown in the plan. "
            )

        style_hint = ""
        if style_id and style_id in DESIGN_STYLES:
            style_hint = f"Apply this interior design style: {DESIGN_STYLES[style_id]['prompt_suffix']}. "

        # Atmosphere knobs default to soft natural daylight when unset.
        atmosphere = build_atmosphere_clause(lighting_tone, color_temperature, material_accent)
        light_default = "" if atmosphere else "soft natural daylight through the windows; "

        primary_prompt = (
            "The attached image is a 2D architectural floor plan (top-down blueprint). "
            "FIRST, read the plan carefully: identify every room and its label, every "
            "wall, door swing, and window opening, AND every furniture symbol (beds, "
            "sofas, tables, chairs, counters, fixtures) with its drawn position and size. "
            "THEN generate a single photorealistic isometric (45-degree bird's-eye) "
            "interior visualization that faithfully reflects exactly what you read. "
            "The camera MUST be tilted 45 degrees (dollhouse cutaway): walls have "
            "visible height (~2.8 m) with the nearer walls cut away — NOT a flat "
            "top-down plan view. "
            "STRICT anti-hallucination rules: match the EXACT room count, wall layout, "
            "and the number and placement of doors and windows shown in the plan. Show "
            "the WHOLE unit — every room in the plan must appear in the view, furnished "
            "according to its function (living room, dining, kitchen, bedrooms, "
            "bathrooms), so the unit reads as one coherent home. Place "
            "each piece of furniture in the SAME room and the SAME position as its symbol "
            "in the plan — do NOT add furniture that is not drawn, do NOT remove or "
            "relocate drawn furniture. Do NOT add or remove rooms, walls, doors or "
            "windows, and do NOT invent extra openings, spaces, levels or decorative "
            "features that are not drawn in the plan. "
            "Rules: walls should be approximately 2.8 m tall; use realistic materials "
            f"(hardwood or tile flooring, painted plaster walls); {light_default}"
            "no people, no dimension text, no measurement labels, no overlaid annotations. "
            "Output must look like a professional architectural render — correct depth, "
            "realistic shadows and reflections, high detail. "
            f"{room_hint}{style_hint}{atmosphere} {extra_prompt}"
        ).strip()

        request_body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"inline_data": {"mime_type": mime_type, "data": floorplan_image_base64}},
                        {"text": primary_prompt},
                    ],
                }
            ],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                # Lowered 0.7→0.5→0.4: less invention, closer adherence to
                # the plan (paired with the read-first furniture rules above).
                "temperature": 0.4,
            },
        }
        return await self._generate_image(request_body, "floorplan_render")

    async def render_realistic_preserve(
        self,
        image_url: Optional[str] = None,
        image_base64: Optional[str] = None,
        style_id: Optional[str] = None,
        structural_fidelity: int = 70,
        style_strength: int = 60,
        extra_prompt: str = "",
        lighting_tone: Optional[str] = None,
        color_temperature: Optional[int] = None,
        material_accent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """"保留結構" render — photorealize an existing design while respecting
        its structure, graded by two sliders (UI spec v1.0, 2026-06-09):

          - structural_fidelity (0-100): how strictly the AI must keep the
            original walls / layout / furniture positions. Higher = stricter.
          - style_strength (0-100): how strongly the chosen style is applied to
            materials / colors / lighting. 0 = keep original materials.

        The input is already a design (3D-model screenshot, SketchUp/clay/white
        model, draft, sketch, or photo); the output is a real-world photograph.
        Structure is never invented — only realism and (optionally) surface style.
        """
        if image_url and not image_base64:
            try:
                image_base64, _ = await self._fetch_image_as_base64(image_url)
            except Exception as exc:
                return {"success": False, "error": f"Failed to fetch image: {exc}"}

        if not image_base64:
            return {"success": False, "error": "No image provided"}

        mime_type = "image/png" if image_base64.startswith("iVBOR") else "image/jpeg"

        fidelity = max(0, min(100, int(structural_fidelity)))
        strength = max(0, min(100, int(style_strength)))

        if fidelity >= 80:
            structure_clause = (
                "Lock the architecture EXACTLY: keep every wall, window, door, "
                "structural element AND all furniture positions precisely as in the "
                "input. Do not move, add, or remove anything."
            )
        elif fidelity >= 50:
            structure_clause = (
                "Preserve the main structure — walls, windows, doors and the overall "
                "layout must match the input, and keep furniture placement. You may "
                "only subtly refine furniture styling, never its position."
            )
        else:
            structure_clause = (
                "Keep the general layout and structure recognizable from the input, "
                "but light adjustments to furniture styling and arrangement are allowed."
            )

        style_name = ""
        if style_id and style_id in DESIGN_STYLES:
            style_name = DESIGN_STYLES[style_id].get("prompt_suffix") or DESIGN_STYLES[style_id].get("name", "")
        if strength <= 20 or not style_name:
            style_clause = (
                "Keep the original materials, colors and textures from the input; "
                "only improve rendering realism."
            )
        elif strength <= 70:
            style_clause = (
                f"Moderately apply {style_name} to the materials, colors and lighting "
                "while keeping the original materials recognizable."
            )
        else:
            style_clause = (
                f"Fully apply {style_name} to the materials, finishes, colors and "
                "lighting — but never change the structure or furniture placement."
            )

        # Hard anti-hallucination invariant. Gemini image-edit has no
        # negative_prompt, so the "do NOT invent" rules must live in the
        # positive prompt. This is the strongest lever short of ControlNet.
        invariant = (
            "STRICT: reproduce ONLY what is in the input. Do NOT add, remove, move, "
            "duplicate, resize or reshape any wall, window, door, column, beam, "
            "staircase, room or furniture piece — keep their exact count, position and "
            "proportions and the room footprint. Do NOT invent extra rooms, openings, "
            "levels, windows, or decorative features that are not visible in the input. "
            "Do NOT change the camera viewpoint, framing or the number of objects."
        )
        # Additive atmosphere knobs (lighting / color temperature / material).
        # These restyle light and surfaces only, so they're safe alongside the
        # invariant — the user can fine-tune the mood without geometry drift.
        atmosphere = build_atmosphere_clause(lighting_tone, color_temperature, material_accent)

        primary_prompt = (
            "The attached image is an existing interior/architectural design. Convert "
            "it into a photorealistic real-world photograph, keeping the same camera "
            "angle and composition. "
            f"{structure_clause} {style_clause} {invariant} "
            "Render with physically accurate lighting, soft realistic shadows, correct "
            "reflections and global illumination, fine material/texture detail, and "
            f"natural depth of field.{atmosphere} Empty space: no people, no text, no "
            "labels, no watermark. "
            f"{extra_prompt}"
        ).strip()

        # Higher fidelity → lower temperature → less invention. Floor lowered to
        # 0.15 (was 0.3) so max-fidelity renders stay tightly faithful to the input.
        temperature = round(0.15 + (100 - fidelity) / 100 * 0.45, 2)

        request_body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"inline_data": {"mime_type": mime_type, "data": image_base64}},
                        {"text": primary_prompt},
                    ],
                }
            ],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "temperature": temperature,
            },
        }
        return await self._generate_image(request_body, "realistic_preserve")

    async def _read_plan_inventory(self, image_base64: str, mime_type: str) -> str:
        """Vision pass for 平面配置圖: read the uploaded sketch/plan/photo and
        return a concise textual inventory of rooms, furniture, and design
        information so the drawing pass reproduces what is actually in the
        image instead of guessing. Fail-open: returns "" on any error so the
        floor-plan generation never breaks on the analysis step.
        """
        analysis_prompt = (
            "You are an architectural draughtsman reading a floor-plan sketch, "
            "drawing, or interior photo. List, concisely and factually, ONLY what "
            "is visible in the image:\n"
            "1. Each room/space with its label (transcribe written labels exactly) "
            "and its position relative to the others (e.g. 'kitchen, top-left, "
            "adjacent to dining').\n"
            "2. Every piece of furniture and fixture and which room it is in and "
            "where within the room (e.g. 'double bed against the north wall').\n"
            "3. Doors, windows, and openings: how many and on which walls.\n"
            "4. Any written dimensions, annotations, or interior-design notes "
            "(materials, colors, styles) — transcribe them exactly.\n"
            "Do NOT guess at anything that is not visible. If something is "
            "ambiguous, describe it as drawn. Answer as a compact bullet list."
        )
        request_body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"inline_data": {"mime_type": mime_type, "data": image_base64}},
                        {"text": analysis_prompt},
                    ],
                }
            ],
            "generationConfig": {"responseModalities": ["TEXT"], "temperature": 0.1},
        }
        try:
            headers, endpoint_url = await self._get_headers_and_url()
            params: Dict[str, str] = {}
            if "generativelanguage.googleapis.com" in endpoint_url and self.api_key:
                params = {"key": self.api_key}
            async with httpx.AsyncClient(timeout=25.0) as client:
                response = await client.post(
                    endpoint_url, params=params, headers=headers, json=request_body,
                )
            if response.status_code != 200:
                logger.warning("[floorplan] inventory pass HTTP %s — skipping", response.status_code)
                return ""
            data = response.json()
            for part in (data.get("candidates") or [{}])[0].get("content", {}).get("parts", []):
                if part.get("text"):
                    return str(part["text"]).strip()[:3000]
        except Exception as exc:  # noqa: BLE001
            logger.warning("[floorplan] inventory pass failed (fail-open): %s", exc)
        return ""

    async def generate_floorplan(
        self,
        requirements: str = "",
        dimensions: Optional[str] = None,
        room_type: Optional[str] = None,
        sketch_image_url: Optional[str] = None,
        sketch_image_base64: Optional[str] = None,
        style_id: Optional[str] = None,
        palette: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a clean 2D architectural floor-plan drawing (平面配置圖).

        Two input modes (either or both):
          - Typed requirements / dimensions / room_type → draw a plan from scratch.
          - A hand sketch / rough plan image → redraw it as a clean scaled plan,
            preserving room positions and adjacencies.

        Optional style_id / palette ship the plan in color, with furniture and
        room fills tuned to the chosen interior style. Both blank → legacy
        white-background blueprint look.

        Unlike render_from_floorplan() (which produces a 3D render FROM a plan),
        this produces a flat top-down drawing as the OUTPUT — so the prompt
        explicitly forbids perspective / photorealism.
        """
        if sketch_image_url and not sketch_image_base64:
            try:
                sketch_image_base64, _ = await self._fetch_image_as_base64(sketch_image_url)
            except Exception as exc:
                return {"success": False, "error": f"Failed to fetch sketch image: {exc}"}

        # 2026-06-12 (owner): 平面配置圖 is the WHOLE-UNIT furniture/layout
        # plan an interior designer delivers — every functional area on one
        # drawing, used to review 動線. The previous single-room context
        # (ROOM_TYPES[..]["context"] = "residential living room 20-30 sqm
        # with sofa...") biased output to ONE room type; use the room-type
        # name only as a unit hint instead.
        room_hint = ""
        if room_type:
            rt = ROOM_TYPES.get(room_type)
            label = rt["name"] if rt else str(room_type)
            room_hint = f"Unit / space type: {label}. "
        dim_hint = f"Overall dimensions: {dimensions}. " if dimensions else ""

        # 2026-06-14 (owner): colored top-down plan. Style picks the furniture
        # vocabulary (Scandi pale oak vs. industrial dark steel etc.); palette
        # picks the room-fill family. Both optional → legacy B/W blueprint.
        style_color_hint = ""
        if style_id and style_id in DESIGN_STYLES:
            style_color_hint = (
                f"Furniture icons and material fills should read in this interior "
                f"design style: {DESIGN_STYLES[style_id]['name']} — "
                f"{DESIGN_STYLES[style_id]['prompt_suffix']}. "
            )

        palette_clauses = {
            "warm":    "Color palette — warm: cream walls (#F5EDD7), terracotta accents (#C6614F), oak wood floor fills (#B58A65), brass detailing.",
            "cool":    "Color palette — cool: pale grey walls (#D8DEE6), dusty-blue accents (#5C7FA4), light grey-washed wood floor fills (#A8AEB1), brushed-steel detailing.",
            "neutral": "Color palette — neutral: off-white walls (#EFEAE2), taupe accents (#B5A99A), pale oak floor fills (#CBB592), matte-black detailing.",
            "vibrant": "Color palette — vibrant: bold accent rooms in deep emerald (#1E5A4C) and mustard (#D6A24A), rich walnut floor fills (#5C3E2A), brass detailing.",
            "mono":    "Color palette — monochrome: soft white walls (#F2F2F2), charcoal accents (#3A3A3A), light grey floor fills (#C9C9C9), black hardware.",
        }
        palette_hint = palette_clauses.get(palette or "", "") if palette else ""

        color_directive = (
            "Render the plan IN COLOR using the palette above: fill each room with its "
            "designated floor color, tint walls with the wall color, and color the "
            "furniture icons to match the interior style. Wall lines remain crisp "
            "dark double-lines for readability. Background outside the unit stays "
            "white. "
            if palette_hint or style_color_hint
            else ""
        )

        base_prompt = (
            "Generate a clean, professional 2D architectural floor-plan drawing of "
            "the COMPLETE unit — a top-down orthographic plan covering ALL "
            "functional areas in the brief (living room, dining area, kitchen, every "
            "bedroom, bathrooms, study, balcony, storage as applicable). Never reduce "
            "the output to a single room unless the requirements explicitly describe "
            "only one room. Draw walls as solid dark double lines, doors as "
            "quarter-circle door swings, and windows as gaps with sill lines. Label "
            "each room with its name. Include furniture footprints (bed, sofa, dining "
            "table, kitchen counters, fixtures) drawn as simple top-down icons in "
            "EVERY room, matching each room's function. Use thin dimension lines. "
            "This must be a flat scaled top-down floor plan — NOT a 3D render, NOT a "
            "perspective view, NOT photorealistic. "
            "STRICT anti-hallucination: include ONLY the rooms, spaces, and furniture "
            "described in the brief or extracted from the uploaded sketch. Do NOT "
            "invent extra rooms, floors, levels, spaces, doors, windows, furniture, "
            "decorative elements, exterior surroundings, or text/annotations beyond "
            "what is asked. If the brief is short, keep the plan equally short — do "
            "not pad it with assumed rooms. "
            f"{style_color_hint}{palette_hint} {color_directive}"
            f"{room_hint}{dim_hint}{requirements}"
        ).strip()

        if sketch_image_base64:
            mime_type = "image/png" if sketch_image_base64.startswith("iVBOR") else "image/jpeg"
            # Read-then-draw: a separate low-temperature vision pass extracts
            # the rooms / furniture / annotations actually present in the
            # uploaded image, and the extracted inventory is pinned into the
            # drawing prompt. This is what makes the plan reproduce the real
            # furniture and design info instead of hallucinating a generic
            # layout (owner request 2026-06-12).
            inventory = await self._read_plan_inventory(sketch_image_base64, mime_type)
            inventory_clause = ""
            if inventory:
                inventory_clause = (
                    "A careful reading of the attached image found exactly the "
                    "following rooms, furniture, and design information:\n"
                    f"{inventory}\n"
                    "Reproduce EVERY listed room, furniture piece, and annotation in "
                    "the redrawn plan at its described location. Do NOT add furniture "
                    "or rooms that are not listed, and do NOT drop any listed item. "
                )
            full_prompt = (
                "The attached image is a floor-plan sketch, draft plan, or interior "
                "reference. Redraw it as a clean, scaled 2D architectural floor plan, "
                "preserving the room positions, proportions, and adjacencies shown — "
                "and faithfully reproducing the furniture placement and any written "
                "labels or design notes visible in the image. "
                + inventory_clause
                + base_prompt
            )
            parts = [
                {"inline_data": {"mime_type": mime_type, "data": sketch_image_base64}},
                {"text": full_prompt},
            ]
        else:
            parts = [{"text": base_prompt}]

        request_body = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                # 0.6→0.45: drafting precision; with the read-then-draw
                # inventory pinned in the prompt, lower temp = less invention.
                "temperature": 0.45,
            },
        }
        return await self._generate_image(request_body, "floorplan")

    async def generate_design(
        self,
        prompt: str,
        style_id: Optional[str] = None,
        room_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate interior design from text description only.

        Text → Image

        Args:
            prompt: Detailed text description of desired room
            style_id: Optional design style to apply
            room_type: Type of room to generate

        Returns:
            Dict with generated image URL and description
        """
        pass  # credentials resolved dynamically via _get_headers_and_url()

        # Build the full prompt
        full_prompt = (
            "Generate a photorealistic interior design architectural visualization image. "
            "The room must be empty with no people, no person, no human figure. "
            "Do not include any luxury branded items. "
        )

        if room_type and room_type in ROOM_TYPES:
            room_context = ROOM_TYPES[room_type]["context"]
            full_prompt += f"Create a {room_context}. "

        if style_id and style_id in DESIGN_STYLES:
            style_suffix = DESIGN_STYLES[style_id]["prompt_suffix"]
            full_prompt += f"Use {style_suffix}. "

        full_prompt += prompt
        full_prompt += " Professional interior architectural photography, correct perspective, realistic material textures, natural lighting."

        request_body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": full_prompt}],
                }
            ],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "temperature": 0.9,
            },
        }
        return await self._generate_image(request_body, "generate")

    async def fusion_design(
        self,
        room_image_base64: Optional[str] = None,
        room_image_url: Optional[str] = None,
        style_image_base64: Optional[str] = None,
        style_image_url: Optional[str] = None,
        prompt: str = ""
    ) -> Dict[str, Any]:
        """
        Combine room photo with style reference image.

        Multi-image Fusion: Room + Style Reference → Fused Result

        Args:
            room_image_base64: Base64-encoded room image
            room_image_url: URL of room image
            style_image_base64: Base64-encoded style reference
            style_image_url: URL of style reference image
            prompt: Additional instructions

        Returns:
            Dict with fused design image URL
        """
        pass  # credentials resolved dynamically via _get_headers_and_url()

        # Get room image
        if room_image_url and not room_image_base64:
            try:
                room_image_base64, room_mime = await self._fetch_image_as_base64(room_image_url)
            except Exception as e:
                return {"success": False, "error": f"Failed to fetch room image: {e}"}

        # Get style image
        if style_image_url and not style_image_base64:
            try:
                style_image_base64, style_mime = await self._fetch_image_as_base64(style_image_url)
            except Exception as e:
                return {"success": False, "error": f"Failed to fetch style image: {e}"}

        if not room_image_base64 or not style_image_base64:
            return {"success": False, "error": "Both room image and style reference are required"}

        # Determine mime types
        room_mime = "image/png" if room_image_base64.startswith("iVBOR") else "image/jpeg"
        style_mime = "image/png" if style_image_base64.startswith("iVBOR") else "image/jpeg"

        full_prompt = f"""I have two images:
1. First image: A room that needs to be redesigned
2. Second image: A style reference showing the desired design aesthetic

Please redesign the room in the first image using the style, colors, and design elements from the second image.
Keep the room layout and window positions from the first image.
Apply the furniture style, color palette, and decorative elements from the second image.

{prompt}

Generate a photorealistic result."""

        request_body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"inline_data": {"mime_type": room_mime, "data": room_image_base64}},
                        {"inline_data": {"mime_type": style_mime, "data": style_image_base64}},
                        {"text": full_prompt},
                    ],
                }
            ],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "temperature": 0.8,
            },
        }
        return await self._generate_image(request_body, "fusion")

    async def iterative_edit(
        self,
        conversation_id: str,
        prompt: str,
        image_base64: Optional[str] = None,
        image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Continue editing a design through multi-turn conversation.

        Iterative Editing: Continuous refinement through dialogue

        Args:
            conversation_id: ID for tracking conversation history
            prompt: Edit instruction for this turn
            image_base64: Optional new image to edit
            image_url: Optional URL of new image

        Returns:
            Dict with updated design and conversation state
        """
        pass  # credentials resolved dynamically via _get_headers_and_url()

        # Initialize or get conversation history
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []

        history = self._conversations[conversation_id]

        # Build user message parts
        user_parts = []

        # Add image if provided (for first turn or new image)
        if image_base64 or image_url:
            if image_url and not image_base64:
                try:
                    image_base64, mime_type = await self._fetch_image_as_base64(image_url)
                except Exception as e:
                    return {"success": False, "error": f"Failed to fetch image: {e}"}

            if image_base64:
                mime_type = "image/png" if image_base64.startswith("iVBOR") else "image/jpeg"
                user_parts.append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": image_base64
                    }
                })

        user_parts.append({"text": prompt})

        # Add to history
        history.append({
            "role": "user",
            "parts": user_parts
        })

        request_body = {
            "contents": history,
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "temperature": 0.7,
            },
            "systemInstruction": {
                "parts": [{
                    "text": "You are an expert interior designer. Help the user refine their room design through iterative edits. Generate updated images based on their requests. Keep previous changes unless specifically asked to revert."
                }]
            },
        }
        result = await self._generate_image(request_body, f"edit_{conversation_id[:8]}")

        if result.get("success"):
            # Add model response to history (text only, not the image)
            history.append({
                "role": "model",
                "parts": [{"text": result.get("description", "Design updated.")}]
            })

            # Limit history to last 10 turns
            if len(history) > 20:
                self._conversations[conversation_id] = history[-20:]

            result["conversation_id"] = conversation_id
            result["turn_count"] = len(history) // 2

        return result

    async def transfer_style(
        self,
        room_image_base64: Optional[str] = None,
        room_image_url: Optional[str] = None,
        style_id: str = "modern_minimalist"
    ) -> Dict[str, Any]:
        """
        Apply a specific design style to a room image.

        Style Transfer: Room + Style → Styled Room

        Args:
            room_image_base64: Base64-encoded room image
            room_image_url: URL of room image
            style_id: ID of design style to apply

        Returns:
            Dict with styled room image URL
        """
        if style_id not in DESIGN_STYLES:
            return {
                "success": False,
                "error": f"Unknown style: {style_id}. Available: {list(DESIGN_STYLES.keys())}"
            }

        style = DESIGN_STYLES[style_id]
        prompt = f"Transform this room to {style['name']} style. {style['description']}. {style['prompt_suffix']}. Keep the room layout and window positions unchanged. The room must be empty with no people, no person, no human figure. Do not include any luxury branded items."

        return await self.redesign_room(
            room_image_base64=room_image_base64,
            room_image_url=room_image_url,
            prompt=prompt,
            keep_layout=True
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _process_image_response(self, data: Dict, prefix: str) -> Dict[str, Any]:
        """Process Gemini response and extract/save generated image."""
        candidates = data.get("candidates", [])

        if not candidates:
            return {
                "success": False,
                "error": "No response generated"
            }

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])

        result = {
            "success": True,
            "description": "",
            "image_url": None
        }

        for part in parts:
            # Extract text description
            if "text" in part:
                result["description"] = part["text"]

            # Extract and save generated image
            if "inlineData" in part:
                inline_data = part["inlineData"]
                mime_type = inline_data.get("mimeType", "image/png")
                image_data = base64.b64decode(inline_data["data"])

                # Save to static directory
                result["image_url"] = self._save_generated_image(image_data, prefix, mime_type)
                result["mime_type"] = mime_type

        if not result["image_url"]:
            # Try alternate format
            for part in parts:
                if "inline_data" in part:
                    inline_data = part["inline_data"]
                    mime_type = inline_data.get("mime_type", "image/png")
                    image_data = base64.b64decode(inline_data["data"])
                    result["image_url"] = self._save_generated_image(image_data, prefix, mime_type)
                    result["mime_type"] = mime_type
                    break

        if not result["image_url"]:
            result["success"] = False
            result["error"] = "No image in response"
            result["raw_response"] = str(parts)[:500]

        return result

    def clear_conversation(self, conversation_id: str) -> bool:
        """Clear conversation history for iterative editing."""
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            return True
        return False


# Singleton instance
_interior_design_service: Optional[InteriorDesignService] = None


def get_interior_design_service() -> InteriorDesignService:
    """Get or create Interior Design service singleton."""
    global _interior_design_service
    if _interior_design_service is None:
        _interior_design_service = InteriorDesignService()
    return _interior_design_service
