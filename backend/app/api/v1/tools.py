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
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
import uuid
from pathlib import Path
from PIL import Image
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
            status=MaterialStatus.PENDING,  # Needs admin approval
            is_active=False,  # Not visible until approved
            input_params=input_params or {},
        )
        db.add(material)
        # Don't commit here — let the caller's commit handle it
        logger.info(f"[Recycle] Flagged user generation for demo review: {tool_type.value}/{topic}")
    except Exception as e:
        logger.debug(f"[Recycle] Skip: {e}")


async def _demo_response(
    db: AsyncSession,
    tool_type: str,
    topic: str | None = None,
    cta: str = "Subscribe for custom generation.",
):
    """Get cached demo or generate one via real API on first visit."""
    try:
        redis = await get_redis()
    except Exception:
        redis = None
    demo = await DemoCacheService(db, redis).get_or_generate(tool_type, topic)
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


async def _refund_credits(db: AsyncSession, user, amount: int, service_type: str):
    """Refund credits on operation failure."""
    try:
        credit_svc = CreditService(db)
        await credit_svc.add_credits(
            user_id=str(user.id),
            amount=amount,
            credit_type="subscription",
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
    Returns (allowed: bool, error_msg: str | None, plan_features: dict | None)"""
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
    Returns (allowed: bool, error_msg: str | None)"""
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
    Returns (ok: bool, error_msg: str | None)"""
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
    image_url: str
    output_format: str = "png"  # png (transparent) or white


class RemoveBackgroundBatchRequest(BaseModel):
    """Batch remove background"""
    image_urls: List[str]
    output_format: str = "png"


class ProductSceneRequest(BaseModel):
    """Generate product in new scene"""
    product_image_url: str
    scene_type: str = "studio"  # studio, nature, elegant, minimal, lifestyle
    custom_prompt: Optional[str] = None


class TryOnRequest(BaseModel):
    """AI Try-On - virtual clothing try-on"""
    garment_image_url: str
    model_image_url: Optional[str] = None  # Use preset model if None
    model_id: Optional[str] = None  # Preset model ID
    angle: str = "front"  # front, side, back
    background: str = "white"  # white, transparent, studio


class RoomRedesignRequest(BaseModel):
    """Room Redesign - transform room style"""
    room_image_url: str
    style: str = "modern"  # modern, nordic, japanese, industrial, minimalist, luxury
    custom_prompt: Optional[str] = None
    preserve_structure: bool = True


class ShortVideoRequest(BaseModel):
    """Short Video - image to video with optional TTS"""
    image_url: str
    motion_strength: int = 5  # 1-10
    style: Optional[str] = None  # Optional style transformation
    script: Optional[str] = None  # Optional TTS script
    voice_id: Optional[str] = None  # TTS voice ID


class AvatarRequest(BaseModel):
    """AI Avatar - Photo-to-Avatar with lip sync"""
    image_url: str  # Clear headshot photo
    script: str  # Text for the avatar to speak
    language: str = "en"  # Language code: 'en' or 'zh-TW'
    voice_id: Optional[str] = None  # Voice ID (defaults to first voice for language)
    duration: int = 30  # Target duration in seconds (max 120)
    aspect_ratio: str = "9:16"  # Video aspect ratio: '9:16', '16:9', '1:1'
    resolution: str = "720p"  # Resolution: '720p' or '1080p'


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
     "prompt": "professional studio lighting, white background, soft shadows, commercial photography"},
    {"id": "nature", "name": "Nature", "name_zh": "自然風景", "preview_url": "/static/scenes/nature.jpg",
     "prompt": "natural outdoor setting, soft sunlight, greenery, organic environment"},
    {"id": "elegant", "name": "Elegant", "name_zh": "質感場景", "preview_url": "/static/scenes/elegant.jpg",
     "prompt": "warm elegant background, cozy lighting, refined atmosphere"},
    {"id": "minimal", "name": "Minimal", "name_zh": "極簡風格", "preview_url": "/static/scenes/minimal.jpg",
     "prompt": "clean minimal white backdrop, simple composition, modern aesthetic"},
    {"id": "lifestyle", "name": "Lifestyle", "name_zh": "生活情境", "preview_url": "/static/scenes/lifestyle.jpg",
     "prompt": "cozy home environment, lifestyle context, warm lighting, lived-in feel"},
    {"id": "beach", "name": "Beach", "name_zh": "海灘", "preview_url": "/static/scenes/beach.jpg",
     "prompt": "beach seaside setting, ocean waves, sandy shore, summer vibes"},
    {"id": "urban", "name": "Urban", "name_zh": "都市街景", "preview_url": "/static/scenes/urban.jpg",
     "prompt": "urban city street, modern architecture, stylish metropolitan backdrop"},
    {"id": "garden", "name": "Garden", "name_zh": "花園", "preview_url": "/static/scenes/garden.jpg",
     "prompt": "beautiful garden setting, flowers blooming, natural green environment"},
]

# Interior design styles for Room Redesign
# IDs must match DESIGN_STYLES keys in interior_design_service.py so demo Material DB lookup works
INTERIOR_STYLES = [
    {"id": "modern_minimalist", "name": "Modern Minimalist", "name_zh": "現代極簡", "preview_url": "/static/interior/modern_minimalist.jpg",
     "prompt": "modern minimalist style, clean lines, neutral color palette, minimal furniture, open space, natural light, contemporary design"},
    {"id": "scandinavian", "name": "Scandinavian", "name_zh": "北歐風格", "preview_url": "/static/interior/scandinavian.jpg",
     "prompt": "scandinavian nordic style, light wood furniture, white walls, cozy textiles, hygge atmosphere, functional design, natural materials"},
    {"id": "japanese", "name": "Japanese Zen", "name_zh": "日式禪風", "preview_url": "/static/interior/japanese.jpg",
     "prompt": "japanese zen style, tatami mats, shoji screens, natural wood, bamboo elements, zen simplicity, peaceful atmosphere, minimalist"},
    {"id": "industrial", "name": "Industrial", "name_zh": "工業風", "preview_url": "/static/interior/industrial.jpg",
     "prompt": "industrial style, exposed brick walls, metal accents, raw textures, urban loft, concrete floors, vintage factory elements"},
    {"id": "bohemian", "name": "Bohemian", "name_zh": "波西米亞", "preview_url": "/static/interior/bohemian.jpg",
     "prompt": "bohemian boho style, eclectic patterns, rich vibrant colors, layered textiles, macrame, plants, artistic free-spirited decor"},
    {"id": "mediterranean", "name": "Mediterranean", "name_zh": "地中海風格", "preview_url": "/static/interior/mediterranean.jpg",
     "prompt": "mediterranean style, terracotta tiles, blue and white accents, arched doorways, rustic charm, natural stone, warm sunlit atmosphere"},
    {"id": "mid_century_modern", "name": "Mid-Century Modern", "name_zh": "中世紀現代", "preview_url": "/static/interior/mid_century_modern.jpg",
     "prompt": "mid-century modern style, organic curved furniture, retro 1950s 1960s design, bold accent colors, teak wood, iconic furniture pieces"},
    {"id": "coastal", "name": "Coastal", "name_zh": "海岸風格", "preview_url": "/static/interior/coastal.jpg",
     "prompt": "coastal beach style, blue and white color palette, nautical elements, light airy atmosphere, rattan furniture, seaside decor"},
    {"id": "farmhouse", "name": "Farmhouse", "name_zh": "農舍風格", "preview_url": "/static/interior/farmhouse.jpg",
     "prompt": "farmhouse country style, rustic reclaimed wood, vintage accents, shiplap walls, cozy warmth, antique furniture, country charm"},
    {"id": "art_deco", "name": "Art Deco", "name_zh": "裝飾藝術", "preview_url": "/static/interior/art_deco.jpg",
     "prompt": "art deco style, geometric patterns, gold and black accents, luxurious materials, velvet, mirrors, glamorous sophisticated design"},
]

# Preset models for Try-On (IDs match frontend: "female-1", "male-1" etc.)
TRYON_MODELS = {
    "female-1": "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=512&fit=crop",
    "female-2": "https://images.unsplash.com/photo-1508214751196-bcfd4ca60f91?w=512&fit=crop",
    "female-3": "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=512&fit=crop",
    "male-1": "https://images.unsplash.com/photo-1681097561932-36d0df02b379?w=512&fit=crop",
    "male-2": "https://images.unsplash.com/photo-1608908271310-57a24a9447db?w=512&fit=crop",
    "male-3": "https://images.unsplash.com/photo-1667127752169-74c7e4d8822f?w=512&fit=crop&crop=face",
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
        return await _demo_response(db, ToolType.BACKGROUND_REMOVAL, cta="Subscribe to process your own images.")

    # ========== SUBSCRIBER: Real-time Generation ==========
    CREDIT_COST = 3
    ok, err = await _check_and_deduct_credits(db, current_user, CREDIT_COST, "background_removal")
    if not ok:
        return ToolResponse(success=False, message=err)

    try:
        provider_router = get_provider_router()
        result = await provider_router.route(
            TaskType.BACKGROUND_REMOVAL,
            {"image_url": str(request.image_url)}
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

    Scene types: studio, nature, elegant, minimal, lifestyle, beach, urban, garden
    Credits: 10 per generation
    """
    # Get scene prompt from templates
    scene = next((s for s in SCENE_TEMPLATES if s["id"] == request.scene_type), None)
    if not scene:
        scene = SCENE_TEMPLATES[0]  # Default to studio

    scene_prompt = request.custom_prompt or scene["prompt"]
    
    # ========== DEMO USER: Return cached demo example ==========
    if not is_subscribed_user(current_user):
        return await _demo_response(db, ToolType.PRODUCT_SCENE, topic=request.scene_type, cta="Subscribe to generate custom scenes.")

    # ========== SUBSCRIBER: Real-time I2I Generation ==========
    CREDIT_COST = 10
    ok, err = await _check_and_deduct_credits(db, current_user, CREDIT_COST, "product_scene")
    if not ok:
        return ToolResponse(success=False, message=err)

    logger.info(f"Subscriber: Starting 3-step I2I generation for {request.product_image_url}")
    
    try:
        provider_router = get_provider_router()
        product_url = str(request.product_image_url)

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
        full_prompt = f"{scene_prompt}, empty background for product placement, professional studio lighting, high-end commercial photography, 8K quality"
        
        t2i_result = await provider_router.route(
            TaskType.T2I,
            {"prompt": full_prompt}
        )
        if not t2i_result.get("success"):
            raise Exception(f"Scene generation failed: {t2i_result.get('error')}")
            
        scene_url = t2i_result["output"]["image_url"]
        
        # Step 3: Composite (Local PIL processing)
        logger.info("Step 3: Compositing...")

        async def _load_image(url: str) -> Image.Image:
            """Load image from local path or remote URL."""
            if url.startswith("/static") or url.startswith("static"):
                local_path = Path("/app") / url.lstrip("/")
                return Image.open(local_path)
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as c:
                resp = await c.get(url)
                resp.raise_for_status()
                return Image.open(BytesIO(resp.content))

        p_img = (await _load_image(product_no_bg_url)).convert("RGBA")
        s_img = (await _load_image(scene_url)).convert("RGBA")

        # Smart Placement Logic
        scene_w, scene_h = s_img.size
        target_w = int(scene_w * 0.6)
        prod_w, prod_h = p_img.size
        scale = target_w / prod_w
        new_w = target_w
        new_h = int(prod_h * scale)

        if new_h > scene_h * 0.8:
            scale = (scene_h * 0.8) / prod_h
            new_h = int(prod_h * scale)
            new_w = int(prod_w * scale)

        p_resized = p_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        x_off = (scene_w - new_w) // 2
        y_off = (scene_h - new_h) // 2

        s_img.paste(p_resized, (x_off, y_off), p_resized)
        final_img = s_img.convert("RGB")

        # Save final result
        output_dir = Path("/app/static/user_generated")
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"product_scene_{uuid.uuid4().hex[:8]}.png"
        final_path = output_dir / filename
        final_img.save(final_path, "PNG", quality=95)

        result_url = f"/static/user_generated/{filename}"

        # Save to UserGeneration
        user_gen = UserGeneration(
            user_id=current_user.id,
            tool_type=ToolType.PRODUCT_SCENE,
            input_image_url=str(request.product_image_url),
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
            input_image_url=str(request.product_image_url),
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
        # Load product image (with transparent background)
        if product_no_bg_url.startswith("/static"):
            product_path = f"/app{product_no_bg_url}"
            product_img = Image.open(product_path).convert("RGBA")
        else:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(product_no_bg_url)
                product_img = Image.open(BytesIO(response.content)).convert("RGBA")
        
        # Load scene background
        if scene_url.startswith("/static"):
            scene_path = f"/app{scene_url}"
            scene_img = Image.open(scene_path).convert("RGBA")
        else:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(scene_url)
                scene_img = Image.open(BytesIO(response.content)).convert("RGBA")
        
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
        
        # Composite: paste product onto scene using alpha channel
        scene_img.paste(product_resized, (x_offset, y_offset), product_resized)
        
        # Convert back to RGB for saving as PNG (no alpha)
        final_img = scene_img.convert("RGB")
        
        # Save result
        output_dir = Path("/app/static/generated")
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"product_scene_{uuid.uuid4().hex[:8]}.png"
        output_path = output_dir / filename
        final_img.save(output_path, "PNG", quality=95)
        
        result_url = f"/static/generated/{filename}"
        logger.info(f"[Composite] Saved: {result_url}")
        return {"success": True, "image_url": result_url}
        
    except Exception as e:
        logger.error(f"[Composite] Error: {e}")
        return {"success": False, "error": str(e)}


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
        return await _demo_response(db, ToolType.TRY_ON, cta="Subscribe to try on your own garments.")

    # ========== SUBSCRIBER: Real-time Generation ==========
    CREDIT_COST = 15
    ok, err = await _check_and_deduct_credits(db, current_user, CREDIT_COST, "virtual_try_on")
    if not ok:
        return ToolResponse(success=False, message=err)

    logger.info(f"Subscriber: Starting real-time Try-On")
    
    try:
        # Determine model image URL
        model_url = None
        if request.model_image_url:
            model_url = str(request.model_image_url)
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
             garment_image_url=str(request.garment_image_url)
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
            input_image_url=str(request.garment_image_url),
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
            input_image_url=str(request.garment_image_url),
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
        return await _demo_response(db, ToolType.ROOM_REDESIGN, topic=request.style, cta="Subscribe to redesign your own rooms.")

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
                "image_url": str(request.room_image_url),
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
                input_image_url=str(request.room_image_url),
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
                input_image_url=str(request.room_image_url),
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
        return await _demo_response(db, ToolType.SHORT_VIDEO, cta="Subscribe to create your own videos.")

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
            motion_desc = "subtle gentle camera motion, slow smooth pan"
        elif strength <= 7:
            motion_desc = "natural camera motion, smooth animation"
        else:
            motion_desc = "dynamic energetic camera motion, dramatic zoom and movement"

        task_params = {
            "image_url": str(request.image_url),
            "prompt": motion_desc,
            "duration": 5
        }

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
                input_params={"motion_strength": request.motion_strength, "style": request.style},
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


# ============================================================================
# Text-to-Video — PiAPI Wan 2.6 T2V
# ============================================================================

class TextToVideoRequest(BaseModel):
    """Generate video from text prompt"""
    prompt: str
    duration: int = 5  # 5, 10, or 15 seconds
    resolution: str = "1080P"  # 720P or 1080P
    aspect_ratio: str = "16:9"  # 16:9, 9:16, 1:1


@router.post("/text-to-video", response_model=ToolResponse)
async def text_to_video(
    request: TextToVideoRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional)
):
    """
    Generate video from text description.

    Uses PiAPI Wan 2.6 text-to-video.
    Credits: 30 per generation
    """
    if not is_subscribed_user(current_user):
        return await _demo_response(db, ToolType.SHORT_VIDEO, cta="Subscribe to generate custom videos.")

    CREDIT_COST = 30
    ok, err = await _check_and_deduct_credits(db, current_user, CREDIT_COST, "text_to_video")
    if not ok:
        return ToolResponse(success=False, message=err)

    try:
        router_instance = get_provider_router()
        result = await router_instance.route(
            TaskType.T2V,
            {
                "prompt": request.prompt,
                "duration": request.duration,
                "resolution": request.resolution,
                "aspect_ratio": request.aspect_ratio,
            }
        )

        if result.get("success"):
            output = result.get("output", {})
            video_url = output.get("video_url")

            generation = UserGeneration(
                user_id=current_user.id,
                tool_type=ToolType.SHORT_VIDEO,
                input_text=request.prompt,
                input_params={"duration": request.duration, "resolution": request.resolution, "aspect_ratio": request.aspect_ratio},
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
                message="Video generated successfully"
            )
        else:
            await _refund_credits(db, current_user, CREDIT_COST, "text_to_video")
            return ToolResponse(success=False, message=result.get("error", "Video generation failed"))
    except Exception as e:
        logger.error(f"Text-to-video error: {e}")
        await _refund_credits(db, current_user, CREDIT_COST, "text_to_video")
        return ToolResponse(success=False, message=f"Generation failed: {str(e)}")


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
        return await _demo_response(db, ToolType.SHORT_VIDEO, cta="Subscribe for video style transfer.")

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
        return await _demo_response(db, ToolType.EFFECT, cta="Subscribe for HD upscale.")

    CREDIT_COST = 10
    ok, err = await _check_and_deduct_credits(db, current_user, CREDIT_COST, "upscale")
    if not ok:
        return ToolResponse(success=False, message=err)

    try:
        router_instance = get_provider_router()
        result = await router_instance.route(
            TaskType.UPSCALE,
            {
                "image_url": request.image_url,
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
        return await _demo_response(db, ToolType.AI_AVATAR, cta="Subscribe to create your own avatars.")

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
                "image_url": str(request.image_url),
                "script": request.script,
                "language": request.language,
                "voice_id": request.voice_id,
                "duration": request.duration,
            }
        )

        if result.get("success"):
            video_url = result.get("video_url")

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
        return await _demo_response(db, ToolType.EFFECT, cta="Subscribe for custom I2I transformations.")

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
                "image_url": str(request.image_url),
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
