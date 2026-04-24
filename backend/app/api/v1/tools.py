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
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
import uuid
from pathlib import Path
from PIL import Image, ImageOps
import httpx
from io import BytesIO

from app.services.effects_service import VIDGO_STYLES, get_style_by_id, get_style_prompt
from app.services.rescue_service import get_rescue_service
from app.providers.provider_router import get_provider_router, TaskType
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
import logging
import os
import hashlib

logger = logging.getLogger(__name__)

PRODUCT_SCENE_MAX_DIMENSION = 1536


async def _maybe_recycle_for_demo(
    db: AsyncSession,
    user_gen: UserGeneration,
    tool_type: ToolType,
    topic: str = "_all",
    prompt: str = "",
    input_image_url: str | None = None,
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

    Flow: check the DB for an existing (tool, effect_or_topic, input_url)
    row via lookup_hash → fall back to generic topic match → otherwise run
    on-demand generation against the user's chosen input + effect, cache the
    result, and return it.
    """
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


async def _refund_credits(db: AsyncSession, user, amount: int, service_type: str):
    """Refund credits on operation failure."""
    try:
        if getattr(user, "is_superuser", False):
            logger.info(
                "Skipping refund for superuser %s on failed %s; no credits were deducted",
                user.id,
                service_type,
            )
            return
        credit_svc = CreditService(db)
        await credit_svc.add_credits(
            user_id=str(user.id),
            amount=amount,
            credit_type="subscription",
            transaction_type="refund",
            description=f"Refund: {service_type} failed",
        )
        logger.info(f"Refunded {amount} credits to user {user.id} for failed {service_type}")
    except Exception as e:
        logger.error(f"Failed to refund {amount} credits to user {user.id}: {e}")


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

    Admin (superuser) accounts bypass credit checks — they can use all
    tools without needing credits.  A zero-cost transaction is still
    recorded for auditing.
    """
    # Admins bypass credit checks entirely
    if getattr(user, "is_superuser", False):
        return True, None

    # Check concurrent generation limit first
    ok, err = await _check_concurrent_limit(db, user)
    if not ok:
        return False, err

    credit_svc = CreditService(db, redis_client)
    has_enough = await credit_svc.check_sufficient(str(user.id), amount)
    if not has_enough:
        return False, f"Insufficient credits. Need {amount} credits."
    success, result = await credit_svc.deduct_credits(
        user_id=str(user.id),
        amount=amount,
        service_type=service_type,
    )
    if not success:
        return False, result.get("error", "Credit deduction failed")
    return True, None


# ============================================================================
# Request/Response Models
# ============================================================================

class RemoveBackgroundRequest(BaseModel):
    """Remove background from image"""
    image_url: str = Field(..., description="Publicly reachable image URL to process.")
    output_format: str = Field("png", description="Output background mode: 'png' for transparent output or 'white' for a white backdrop.")


class RemoveBackgroundBatchRequest(BaseModel):
    """Batch remove background"""
    image_urls: List[str] = Field(..., description="List of publicly reachable image URLs to process. Maximum 10 per request.")
    output_format: str = Field("png", description="Output background mode for every image in the batch.")


class ProductSceneRequest(BaseModel):
    """Generate product in new scene"""
    product_image_url: Optional[str] = Field(None, description="Primary product image URL. Use this or image_url.")
    image_url: Optional[str] = Field(None, description="Alias for product_image_url for client compatibility.")
    product_id: Optional[str] = Field(None, description="Optional preset product identifier used to match a cached demo example.")
    scene_type: str = Field(
        "studio",
        description="Named preset scene. Valid values: studio, nature, elegant, minimal, lifestyle, urban, seasonal, holiday, spring, valentines, black_friday, christmas, new_year.",
    )
    custom_prompt: Optional[str] = Field(
        None,
        description="Optional full natural-language scene prompt. When provided, it overrides scene_type unless template_id is also set.",
    )
    template_id: Optional[str] = Field(
        None,
        description="Optional template identifier. Highest priority override for scene generation; takes precedence over both custom_prompt and scene_type.",
    )

    def get_product_url(self) -> str:
        url = self.product_image_url or self.image_url
        if not url:
            raise ValueError("product_image_url or image_url is required")
        return _resolve_public_url(url)


class TryOnRequest(BaseModel):
    """AI Try-On - virtual clothing try-on"""
    garment_image_url: Optional[str] = Field(None, description="Garment image URL to place on the model. Use this or image_url.")
    image_url: Optional[str] = Field(None, description="Alias for garment_image_url for client compatibility.")
    model_image_url: Optional[str] = Field(None, description="Optional explicit model image URL. If omitted, the API falls back to model_id or a preset model.")
    model_id: Optional[str] = Field(None, description="Optional preset model identifier such as female-1 or male-1.")
    angle: str = Field("front", description="Target garment view angle: front, side, or back.")
    background: str = Field("white", description="Requested background for the try-on result: white, transparent, or studio.")
    template_id: Optional[str] = Field(None, description="Optional style template that controls the try-on scene or background.")

    def get_garment_url(self) -> str:
        url = self.garment_image_url or self.image_url
        if not url:
            raise ValueError("garment_image_url or image_url is required")
        return _resolve_public_url(url)


class RoomRedesignRequest(BaseModel):
    """Room Redesign - transform room style"""
    room_image_url: Optional[str] = Field(None, description="Source room image URL. Use this or image_url.")
    image_url: Optional[str] = Field(None, description="Alias for room_image_url for client compatibility.")
    style: str = Field("modern", description="Preset redesign style. Common values include modern, nordic, japanese, industrial, minimalist, and luxury.")
    custom_prompt: Optional[str] = Field(None, description="Optional detailed redesign instruction that supplements or overrides the preset style description.")
    preserve_structure: bool = Field(True, description="Keep the original room layout and architectural structure while changing the design style.")

    def get_room_url(self) -> str:
        url = self.room_image_url or self.image_url
        if not url:
            raise ValueError("room_image_url or image_url is required")
        return _resolve_public_url(url)


class ShortVideoRequest(BaseModel):
    """Short Video - image to video with optional TTS"""
    image_url: str = Field(..., description="Input image URL used as the starting frame for video generation.")
    motion_strength: int = Field(5, ge=1, le=10, description="Motion intensity from 1 to 10. Higher values produce more camera or object movement.")
    model_id: Optional[str] = Field(None, description="Optional image-to-video model identifier such as pixverse_v4.5, pixverse_v5, kling_v2, kling_v1.5, or luma_ray2.")
    style: Optional[str] = Field(None, description="Optional visual style or effect hint to steer the motion result.")
    script: Optional[str] = Field(None, description="Optional narration script for text-to-speech voice-over.")
    voice_id: Optional[str] = Field(None, description="Optional voice identifier for TTS narration.")


class AvatarRequest(BaseModel):
    """AI Avatar - Photo-to-Avatar with lip sync"""
    image_url: str = Field(..., description="Clear frontal headshot URL used to generate the speaking avatar.")
    script: str = Field(..., description="Exact speech content for the avatar to say. Write complete spoken sentences.")
    language: str = Field("en", description="Speech language code, for example 'en' or 'zh-TW'.")
    voice_id: Optional[str] = Field(None, description="Optional voice identifier. If omitted, the first supported voice for the selected language is used.")
    duration: int = Field(30, ge=1, le=120, description="Target video duration in seconds.")
    aspect_ratio: str = Field("9:16", description="Target video aspect ratio: 9:16, 16:9, or 1:1.")
    resolution: str = Field("720p", description="Output resolution: 720p or 1080p.")


class ToolResponse(BaseModel):
    """Standard tool response"""
    success: bool
    result_url: Optional[str] = None
    results: Optional[List[Dict]] = None
    credits_used: int = 0
    message: Optional[str] = None
    cached: bool = False
    # Demo before/after pair — set when returning a pre-generated example
    is_demo: bool = False
    demo_input_url: Optional[str] = None   # "before" image from the pre-generated example
    demo_prompt: Optional[str] = None      # prompt used to generate the example


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
]

# Preset models for Try-On (IDs match frontend: "female-1", "male-1" etc.)
TRYON_MODELS = {
    "female-1": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/female-1.png",
    "female-2": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/female-2.png",
    "female-3": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/female-3.png",
    "male-1": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/male-1.png",
    "male-2": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/male-2.png",
    "male-3": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models/male-3.png",
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
    {"id": "room_redesign", "name": "Raw Space / Sketch Instant Render", "name_zh": "毛胚屋/線稿秒渲染", "endpoint": "/tools/room-redesign", "method": "POST",
     "description": "Transform raw spaces or sketches into photorealistic interior renders"},
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
            
            # Save to UserGeneration
            user_gen = UserGeneration(
                user_id=current_user.id,
                tool_type=ToolType.BACKGROUND_REMOVAL,
                input_image_url=str(request.image_url),
                input_params={"output_format": request.output_format},
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
            return ToolResponse(
                success=False,
                message=result.get("error", "Background removal failed")
            )
    except Exception as e:
        logger.error(f"Background removal error: {e}")
        await _refund_credits(db, current_user, CREDIT_COST, "background_removal")
        return ToolResponse(
            success=False,
            message=f"Generation failed: {str(e)}"
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

    # Check plan-level batch processing permission
    allowed, err, _ = await _check_plan_feature(db, current_user, "batch_processing", "batch processing")
    if not allowed:
        raise HTTPException(status_code=403, detail=err)

    total_cost = len(request.image_urls) * 3
    credit_service = CreditService(db)
    balance = await credit_service.get_balance(str(current_user.id))
    if balance["total"] < total_cost:
        raise HTTPException(status_code=403, detail=f"Insufficient credits. Need {total_cost}, have {balance['total']}")

    results = []
    credits_used = 0
    provider_router = get_provider_router()

    for image_url in request.image_urls:
        try:
            # Use provider router for background removal (PiAPI)
            result = await provider_router.route(
                TaskType.BACKGROUND_REMOVAL,
                {"image_url": str(image_url)}
            )
            if result.get("success"):
                output = result.get("output", {})
                results.append({
                    "input_url": str(image_url),
                    "result_url": output.get("image_url"),
                    "success": True
                })
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

    Scene type priority: template_id > custom_prompt > scene_type
    Scene types: studio, nature, elegant, minimal, lifestyle, urban, seasonal, holiday, spring, valentines, black_friday, christmas, new_year
    Credits: 10 per generation
    """
    # Resolve scene prompt — template_id takes priority, then custom_prompt, then scene_type
    scene_prompt: Optional[str] = None
    if request.template_id:
        from app.services.template_prompt_service import resolve_template_prompt
        scene_prompt = await resolve_template_prompt(db, request.template_id)
        if not scene_prompt:
            raise HTTPException(status_code=400, detail="Template not found or inactive.")

    if not scene_prompt:
        scene = next((s for s in SCENE_TEMPLATES if s["id"] == request.scene_type), None)
        if not scene and not request.custom_prompt:
            valid_ids = ", ".join(s["id"] for s in SCENE_TEMPLATES)
            raise HTTPException(
                status_code=400,
                detail=f"Unknown scene_type '{request.scene_type}'. Valid options: {valid_ids}, or provide custom_prompt.",
            )
        scene_prompt = request.custom_prompt or scene["prompt"]
    
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
    
    try:
        provider_router = get_provider_router()
        product_url = str(request.get_product_url())

        # Step 1: Remove background
        logger.info("Step 1: Removing product background...")
        rembg_result = await provider_router.route(
            TaskType.BACKGROUND_REMOVAL,
            {"image_url": product_url}
        )
        if not rembg_result.get("success"):
            raise Exception(f"Background removal failed: {rembg_result.get('error')}")
        
        product_no_bg_url = rembg_result["output"]["image_url"]

        # Step 2: Generate scene background
        logger.info("Step 2: Generating scene background...")
        full_prompt = f"{scene_prompt}, scene background only with clear open area for product compositing, no product or object in center, photorealistic high-resolution commercial photography"
        
        t2i_result = await provider_router.route(
            TaskType.T2I,
            {"prompt": full_prompt}
        )
        if not t2i_result.get("success"):
            raise Exception(f"Scene generation failed: {t2i_result.get('error')}")
            
        scene_url = t2i_result["output"]["image_url"]
        
        # Step 3: Composite with bounded memory usage so large provider outputs
        # do not OOM the Cloud Run instance.
        logger.info("Step 3: Compositing...")
        composite_result = await _composite_product_scene(product_no_bg_url, scene_url)
        if not composite_result.get("success"):
            raise Exception(f"Product compositing failed: {composite_result.get('error')}")

        result_url = composite_result["image_url"]

        # Save to UserGeneration
        user_gen = UserGeneration(
            user_id=current_user.id,
            tool_type=ToolType.PRODUCT_SCENE,
            input_image_url=str(request.get_product_url()),
            input_params={"scene_type": request.scene_type, "custom_prompt": request.custom_prompt},
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
            input_params={"scene_type": request.scene_type},
        )

        await db.commit()

        return ToolResponse(
            success=True,
            result_url=result_url,
            credits_used=10,
            message="Product scene generated successfully (subscriber)"
        )
        
    except Exception as e:
        logger.error(f"Product scene error: {e}")
        await _refund_credits(db, current_user, CREDIT_COST, "product_scene")
        return ToolResponse(
            success=False,
            message=f"Generation failed: {str(e)}"
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
        
        result = await piapi.virtual_try_on(
             model_image_url=model_url,
             garment_image_url=garment_url
        )
        
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

        # Save to UserGeneration
        user_gen = UserGeneration(
            user_id=current_user.id,
            tool_type=ToolType.TRY_ON,
            input_image_url=str(request.get_garment_url()),
            input_params={
                "model_id": request.model_id,
                "model_image_url": str(request.model_image_url) if request.model_image_url else None,
                "angle": request.angle
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
        logger.error(f"Try-On error: {e}")
        await _refund_credits(db, current_user, CREDIT_COST, "virtual_try_on")
        return ToolResponse(
            success=False,
            message=f"Try-On generation failed: {str(e)}"
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
    # ========== DEMO USER: Return cached demo example ==========
    if not is_subscribed_user(current_user):
        try:
            user_room = str(request.get_room_url())
        except ValueError:
            user_room = None
        interior_match = next((s for s in INTERIOR_STYLES if s["id"] == request.style), None)
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

    interior = next((s for s in INTERIOR_STYLES if s["id"] == request.style), None)
    if not interior:
        interior = INTERIOR_STYLES[0]

    style_prompt = request.custom_prompt or interior["prompt"]

    try:
        router = get_provider_router()
        result = await router.route(
            TaskType.INTERIOR,
            {
                "image_url": str(request.get_room_url()),  # already resolved in get_room_url
                "prompt": style_prompt,
                "style": request.style,
                "preserve_structure": request.preserve_structure
            }
        )

        output_url = result.get("image_url") or result.get("output_url") or (result.get("output", {}).get("image_url") if isinstance(result.get("output"), dict) else None)
        
        if output_url:
            # Save to UserGeneration
            user_gen = UserGeneration(
                user_id=current_user.id,
                tool_type=ToolType.ROOM_REDESIGN,
                input_image_url=str(request.get_room_url()),
                input_params={
                    "style": request.style,
                    "custom_prompt": request.custom_prompt,
                    "preserve_structure": request.preserve_structure
                },
                result_image_url=output_url,
                credits_used=20,
            )
            user_gen.set_expiry()
            db.add(user_gen)

            # Recycle for demo gallery
            await _maybe_recycle_for_demo(
                db, user_gen, ToolType.ROOM_REDESIGN,
                topic=request.style or "modern",
                prompt=f"Room redesign: {request.style}",
                input_image_url=str(request.get_room_url()),
                result_image_url=output_url,
                input_params={"style": request.style},
            )

            await db.commit()

            return ToolResponse(
                success=True,
                result_url=output_url,
                credits_used=20,
                message="Room redesign successful"
            )
        else:
            await _refund_credits(db, current_user, CREDIT_COST, "room_redesign")
            return ToolResponse(
                success=False,
                message=result.get("error", "Room redesign failed")
            )
    except Exception as e:
        logger.error(f"Room Redesign error: {e}")
        await _refund_credits(db, current_user, CREDIT_COST, "room_redesign")
        return ToolResponse(
            success=False,
            message=f"Generation failed: {str(e)}"
        )


# ============================================================================
# Tool 5: Short Video
# ============================================================================

@router.post("/short-video", response_model=ToolResponse)
async def generate_short_video(
    request: ShortVideoRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional)
):
    """
    Generate short video from image.
    
    USER TIER LOGIC:
    - Demo users: Return pre-generated result from Material DB
    - Subscribers: Real-time video generation + save to UserGeneration

    Credits: 25-35 (varies by features used)
    """
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

        task_params = {
            "image_url": _resolve_public_url(str(request.image_url)),
            "prompt": motion_desc,
            "duration": 5
        }

        if request.model_id:
            task_params["model"] = request.model_id

        result = await provider_router.route(
            TaskType.I2V,
            task_params
        )

        if not result.get("success"):
            await _refund_credits(db, current_user, CREDIT_COST, "short_video")
            return ToolResponse(
                success=False,
                message=result.get("error", "Video generation failed")
            )

        video_url = result.get("video_url") or result.get("output", {}).get("video_url") or result.get("output_url")

        # Optional: Apply style transformation (Video-to-Video)
        # Requires can_use_effects plan feature
        apply_style = False
        if request.style and video_url:
            effects_ok, _, _ = await _check_plan_feature(
                db, current_user, "can_use_effects", "video style effects"
            )
            apply_style = effects_ok

        if apply_style and request.style and video_url:
            style_prompt = get_style_prompt(request.style)
            if style_prompt:
                style_result = await provider_router.route(
                    TaskType.V2V,
                    {"video_url": video_url, "prompt": style_prompt}
                )
                output_url = style_result.get("video_url") or style_result.get("output_url") or style_result.get("output", {}).get("video_url")
                if output_url:
                    video_url = output_url
                    # Deduct extra 5 credits for style transfer
                    extra_ok, _ = await _check_and_deduct_credits(db, current_user, 5, "short_video_style")
                    if extra_ok:
                        credits_used += 5

        if video_url:
            # Save to UserGeneration
            user_gen = UserGeneration(
                user_id=current_user.id,
                tool_type=ToolType.SHORT_VIDEO,
                input_image_url=str(request.image_url),
                input_params={"motion_strength": request.motion_strength, "style": request.style, "model_id": request.model_id},
                result_video_url=video_url,
                credits_used=credits_used,
            )
            user_gen.set_expiry()
            db.add(user_gen)

            # Recycle for demo gallery
            await _maybe_recycle_for_demo(
                db, user_gen, ToolType.SHORT_VIDEO,
                topic="product_showcase", prompt="User short video",
                input_image_url=str(request.image_url),
                result_video_url=video_url,
            )

            await db.commit()

            return ToolResponse(
                success=True,
                result_url=video_url,
                credits_used=credits_used,
                message="Short video generated successfully"
            )
        else:
            await _refund_credits(db, current_user, CREDIT_COST, "short_video")
            return ToolResponse(
                success=False,
                message="Video generation returned no URL"
            )

    except Exception as e:
        logger.error(f"Short video error: {e}")
        await _refund_credits(db, current_user, CREDIT_COST, "short_video")
        return ToolResponse(
            success=False,
            message=f"Generation failed: {str(e)}"
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


@router.post("/video-transform", response_model=ToolResponse)
async def video_transform(
    request: VideoTransformRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional)
):
    """
    Apply style transfer to a video.

    Uses PiAPI Wan VACE video-to-video.
    Credits: 35 per generation
    """
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
        result = await router_instance.route(
            TaskType.V2V,
            {
                "video_url": request.video_url,
                "prompt": request.prompt,
                "style": request.style,
            }
        )

        if result.get("success"):
            output = result.get("output", {})
            video_url = output.get("video_url")

            generation = UserGeneration(
                user_id=current_user.id,
                tool_type=ToolType.SHORT_VIDEO,
                input_video_url=request.video_url,
                input_params={"prompt": request.prompt, "style": request.style},
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
            return ToolResponse(success=False, message=result.get("error", "Video transform failed"))
    except Exception as e:
        logger.error(f"Video transform error: {e}")
        await _refund_credits(db, current_user, CREDIT_COST, "video_transform")
        return ToolResponse(success=False, message=f"Generation failed: {str(e)}")


# ============================================================================
# Image Upscale — PiAPI image-toolkit
# ============================================================================

class UpscaleRequest(BaseModel):
    """Upscale image to higher resolution"""
    image_url: str
    scale: int = 2  # 2x or 4x


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
            return ToolResponse(success=False, message=result.get("error", "Upscale failed"))
    except Exception as e:
        logger.error(f"Upscale error: {e}")
        await _refund_credits(db, current_user, CREDIT_COST, "upscale")
        return ToolResponse(success=False, message=f"Upscale failed: {str(e)}")


# ============================================================================
# Tool 6: AI Avatar
# ============================================================================

@router.post("/avatar", response_model=ToolResponse)
async def generate_avatar_video(
    request: AvatarRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional)
):
    """
    Generate AI Avatar video from photo with lip sync.
    
    USER TIER LOGIC:
    - Demo users: Return pre-generated result from Material DB
    - Subscribers: Real-time avatar generation + save to UserGeneration

    Supported languages: 'en' (English), 'zh-TW' (Traditional Chinese)
    Credits: 30 per generation
    """
    from app.models.material import MaterialSource, MaterialStatus

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

    CREDIT_COST = 30
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
            }
        )

        if result.get("success"):
            output = result.get("output", {})
            video_url = output.get("video_url") or result.get("video_url")

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
        logger.error(f"Avatar generation error: {e}")
        await _refund_credits(db, current_user, CREDIT_COST, "ai_avatar")
        return ToolResponse(
            success=False,
            message=f"Generation failed: {str(e)}"
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
        result = await provider_router.route(
            TaskType.I2I,
            {
                "image_url": _resolve_public_url(str(request.image_url)),
                "prompt": request.prompt,
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
                input_text=request.prompt,
                input_params={
                    "strength": request.strength,
                    "negative_prompt": request.negative_prompt,
                    "mode": "i2i_transform",
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
        logger.error(f"Image transform error: {e}")
        await _refund_credits(db, current_user, cost, "image_transform")
        return ToolResponse(
            success=False,
            message=f"Generation failed: {str(e)}"
        )


# ============================================================================
# Template & Resource Endpoints
# ============================================================================

@router.get("/templates/scenes")
async def get_scene_templates():
    """Get available scene templates for Product Scene tool"""
    return SCENE_TEMPLATES


@router.get("/templates/interior-styles")
async def get_interior_styles():
    """Get available interior styles for Room Redesign tool"""
    return INTERIOR_STYLES


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
