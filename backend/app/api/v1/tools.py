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
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import uuid
from pathlib import Path
from PIL import Image
import httpx
from io import BytesIO

from app.services.effects_service import VIDGO_STYLES, get_style_by_id, get_style_prompt
from app.services.a2e_service import get_a2e_service, A2E_VOICES
from app.services.rescue_service import get_rescue_service
from app.providers.provider_router import get_provider_router, TaskType
from app.api.deps import get_current_user_optional, get_db, is_subscribed_user
from app.models.user_generation import UserGeneration
from app.models.material import Material, ToolType
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class RemoveBackgroundRequest(BaseModel):
    """Remove background from image"""
    image_url: HttpUrl
    output_format: str = "png"  # png (transparent) or white


class RemoveBackgroundBatchRequest(BaseModel):
    """Batch remove background"""
    image_urls: List[HttpUrl]
    output_format: str = "png"


class ProductSceneRequest(BaseModel):
    """Generate product in new scene"""
    product_image_url: HttpUrl
    scene_type: str = "studio"  # studio, nature, elegant, minimal, lifestyle
    custom_prompt: Optional[str] = None


class TryOnRequest(BaseModel):
    """AI Try-On - virtual clothing try-on"""
    garment_image_url: HttpUrl
    model_image_url: Optional[HttpUrl] = None  # Use preset model if None
    model_id: Optional[str] = None  # Preset model ID
    angle: str = "front"  # front, side, back
    background: str = "white"  # white, transparent, studio


class RoomRedesignRequest(BaseModel):
    """Room Redesign - transform room style"""
    room_image_url: HttpUrl
    style: str = "modern"  # modern, nordic, japanese, industrial, minimalist, luxury
    custom_prompt: Optional[str] = None
    preserve_structure: bool = True


class ShortVideoRequest(BaseModel):
    """Short Video - image to video with optional TTS"""
    image_url: HttpUrl
    motion_strength: int = 5  # 1-10
    style: Optional[str] = None  # Optional style transformation
    script: Optional[str] = None  # Optional TTS script
    voice_id: Optional[str] = None  # TTS voice ID


class AvatarRequest(BaseModel):
    """AI Avatar - Photo-to-Avatar with lip sync"""
    image_url: HttpUrl  # Clear headshot photo
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
INTERIOR_STYLES = [
    {"id": "modern", "name": "Modern", "name_zh": "現代風格", "preview_url": "/static/interior/modern.jpg",
     "prompt": "modern interior design, clean lines, contemporary furniture, neutral colors"},
    {"id": "nordic", "name": "Nordic", "name_zh": "北歐風格", "preview_url": "/static/interior/nordic.jpg",
     "prompt": "scandinavian nordic interior, light wood, white walls, minimalist cozy"},
    {"id": "japanese", "name": "Japanese", "name_zh": "日式風格", "preview_url": "/static/interior/japanese.jpg",
     "prompt": "japanese zen interior, tatami, natural materials, minimal elegant"},
    {"id": "industrial", "name": "Industrial", "name_zh": "工業風", "preview_url": "/static/interior/industrial.jpg",
     "prompt": "industrial loft style, exposed brick, metal pipes, concrete floors"},
    {"id": "minimalist", "name": "Minimalist", "name_zh": "極簡主義", "preview_url": "/static/interior/minimalist.jpg",
     "prompt": "minimalist interior, white space, essential furniture only, clean design"},
    {"id": "luxury", "name": "Luxury", "name_zh": "奢華風格", "preview_url": "/static/interior/luxury.jpg",
     "prompt": "luxury interior design, premium materials, gold accents, elegant sophisticated"},
    {"id": "bohemian", "name": "Bohemian", "name_zh": "波希米亞", "preview_url": "/static/interior/bohemian.jpg",
     "prompt": "bohemian boho interior, colorful textiles, plants, eclectic warm"},
    {"id": "coastal", "name": "Coastal", "name_zh": "海岸風格", "preview_url": "/static/interior/coastal.jpg",
     "prompt": "coastal beach house interior, white blue colors, nautical elements, breezy"},
]

# Preset models for Try-On
TRYON_MODELS = [
    {"id": "female_01", "name": "Female Model 1", "name_zh": "女模特 1",
     "preview_url": "/static/models/female_01.jpg", "gender": "female", "body_type": "slim"},
    {"id": "female_02", "name": "Female Model 2", "name_zh": "女模特 2",
     "preview_url": "/static/models/female_02.jpg", "gender": "female", "body_type": "average"},
    {"id": "female_03", "name": "Female Model 3", "name_zh": "女模特 3",
     "preview_url": "/static/models/female_03.jpg", "gender": "female", "body_type": "plus"},
    {"id": "male_01", "name": "Male Model 1", "name_zh": "男模特 1",
     "preview_url": "/static/models/male_01.jpg", "gender": "male", "body_type": "slim"},
    {"id": "male_02", "name": "Male Model 2", "name_zh": "男模特 2",
     "preview_url": "/static/models/male_02.jpg", "gender": "male", "body_type": "average"},
    {"id": "male_03", "name": "Male Model 3", "name_zh": "男模特 3",
     "preview_url": "/static/models/male_03.jpg", "gender": "male", "body_type": "athletic"},
]

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
    # ========== DEMO USER: Use pre-generated Material DB ==========
    if not is_subscribed_user(current_user):
        logger.info("Demo user: Looking up pre-generated background removal result")
        
        result = await db.execute(
            select(Material)
            .where(Material.tool_type == ToolType.BACKGROUND_REMOVAL)
            .where(Material.is_active == True)
            .limit(1)
        )
        material = result.scalars().first()
        
        if material:
            result_url = material.result_watermarked_url or material.result_image_url
            return ToolResponse(
                success=True,
                result_url=result_url,
                credits_used=0,
                cached=True,
                message="Demo result (watermarked)"
            )
        else:
            return ToolResponse(
                success=False,
                message="No pre-generated examples available. Please subscribe."
            )
    
    # ========== SUBSCRIBER: Real-time Generation ==========
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
                credits_used=3,
            )
            db.add(user_gen)
            await db.commit()
            
            return ToolResponse(
                success=True,
                result_url=result_url,
                credits_used=3,
                message="Background removed successfully"
            )
        else:
            return ToolResponse(
                success=False,
                message=result.get("error", "Background removal failed")
            )
    except Exception as e:
        logger.error(f"Background removal error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/remove-bg/batch", response_model=ToolResponse)
async def remove_background_batch(
    request: RemoveBackgroundBatchRequest,
    current_user=Depends(get_current_user_optional)
):
    """
    Batch remove background from multiple images.
    Maximum 10 images per request.

    Credits: 3 per image
    """
    if len(request.image_urls) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 images per batch")

    results = []
    credits_used = 0
    provider_router = get_provider_router()

    for image_url in request.image_urls:
        try:
            # Use provider router for background removal (GoEnhance)
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
    
    # ========== DEMO USER: Use pre-generated Material DB ==========
    if not is_subscribed_user(current_user):
        logger.info(f"Demo user: Looking up pre-generated result for scene={request.scene_type}")
        
        # Find matching pre-generated material
        result = await db.execute(
            select(Material)
            .where(Material.tool_type == ToolType.PRODUCT_SCENE)
            .where(Material.topic == request.scene_type)
            .where(Material.is_active == True)
            .limit(1)
        )
        material = result.scalars().first()
        
        if material:
            # Return watermarked result for demo users
            result_url = material.result_watermarked_url or material.result_image_url
            return ToolResponse(
                success=True,
                result_url=result_url,
                credits_used=0,  # Demo users don't use credits
                cached=True,
                message="Demo result (watermarked)"
            )
        else:
            return ToolResponse(
                success=False,
                message="No pre-generated examples available. Please subscribe for custom generation."
            )
    
    # ========== SUBSCRIBER: Real-time I2I Generation ==========
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
            TaskType.TEXT_TO_IMAGE,
            {"prompt": full_prompt}
        )
        if not t2i_result.get("success"):
            raise Exception(f"Scene generation failed: {t2i_result.get('error')}")
            
        scene_url = t2i_result["output"]["image_url"]
        
        # Step 3: Composite (Local PIL processing)
        logger.info("Step 3: Compositing...")
        async with httpx.AsyncClient() as client:
            p_resp = await client.get(product_no_bg_url)
            s_resp = await client.get(scene_url)
            
            p_img = Image.open(BytesIO(p_resp.content)).convert("RGBA")
            s_img = Image.open(BytesIO(s_resp.content)).convert("RGBA")
            
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
        db.add(user_gen)
        await db.commit()
        
        return ToolResponse(
            success=True,
            result_url=result_url,
            credits_used=10,
            message="Product scene generated successfully (subscriber)"
        )
        
    except Exception as e:
        logger.error(f"Product scene error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    # ========== DEMO USER: Use pre-generated Material DB ==========
    if not is_subscribed_user(current_user):
        logger.info("Demo user: Looking up pre-generated try-on result")
        
        result = await db.execute(
            select(Material)
            .where(Material.tool_type == ToolType.TRY_ON)
            .where(Material.is_active == True)
            .limit(1)
        )
        material = result.scalars().first()
        
        if material:
            result_url = material.result_watermarked_url or material.result_image_url
            return ToolResponse(
                success=True,
                result_url=result_url,
                credits_used=0,
                cached=True,
                message="Demo result (watermarked)"
            )
        else:
            return ToolResponse(
                success=False,
                message="No pre-generated examples available. Please subscribe."
            )
    
    # ========== SUBSCRIBER: Real-time Generation ==========
    logger.info(f"Subscriber: Starting real-time Try-On")
    
    try:
        # Determine model image URL
        model_url = None
        if request.model_image_url:
            model_url = str(request.model_image_url)
        elif request.model_id:
             # Look for matching model in config
             # Frontend passes "female-1", "male-1" etc.
             # We should map to backend path if not provided
             # Try /static/models/...
             gender = "female" if "female" in request.model_id else "male"
             model_url = f"/static/models/{gender}/{request.model_id}.png"
             # If using full URL service (PIAPI), and running locally in docker,
             # we might need to rely on the Client handling local paths.
             # PiAPIClient._resolve_image_input does this.

        # Route via PIAPI Client directly for specialized Try-On
        from scripts.services.piapi_client import PiAPIClient
        piapi = PiAPIClient()
        
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
        db.add(user_gen)
        await db.commit()
        
        return ToolResponse(
            success=True,
            result_url=result_url,
            credits_used=15,
            message="Virtual try-on successful"
        )

    except Exception as e:
        logger.error(f"Try-On error: {e}")
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
    # ========== DEMO USER: Use pre-generated Material DB ==========
    if not is_subscribed_user(current_user):
        logger.info(f"Demo user: Looking up pre-generated room redesign for style={request.style}")
        
        result = await db.execute(
            select(Material)
            .where(Material.tool_type == ToolType.ROOM_REDESIGN)
            .where(Material.topic == request.style)
            .where(Material.is_active == True)
            .limit(1)
        )
        material = result.scalars().first()
        
        if material:
            result_url = material.result_watermarked_url or material.result_image_url
            return ToolResponse(
                success=True,
                result_url=result_url,
                credits_used=0,
                cached=True,
                message="Demo result (watermarked)"
            )
        else:
            return ToolResponse(
                success=False,
                message="No pre-generated examples available. Please subscribe."
            )
    
    # ========== SUBSCRIBER: Real-time Generation ==========
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
            db.add(user_gen)
            await db.commit()
            
            return ToolResponse(
                success=True,
                result_url=output_url,
                credits_used=20,
                message="Room redesign successful"
            )
        else:
            return ToolResponse(
                success=False,
                message=result.get("error", "Room redesign failed")
            )
    except Exception as e:
        logger.error(f"Room Redesign error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    # ========== DEMO USER: Use pre-generated Material DB ==========
    if not is_subscribed_user(current_user):
        logger.info("Demo user: Looking up pre-generated short video result")
        
        result = await db.execute(
            select(Material)
            .where(Material.tool_type == ToolType.SHORT_VIDEO)
            .where(Material.is_active == True)
            .limit(1)
        )
        material = result.scalars().first()
        
        if material:
            result_url = material.result_watermarked_url or material.result_video_url
            return ToolResponse(
                success=True,
                result_url=result_url,
                credits_used=0,
                cached=True,
                message="Demo result (watermarked)"
            )
        else:
            return ToolResponse(
                success=False,
                message="No pre-generated examples available. Please subscribe."
            )
    
    # ========== SUBSCRIBER: Real-time Generation ==========
    try:
        credits_used = 25
        
        # Use Provider Router for standard I2V
        provider_router = get_provider_router()
        task_params = {
            "image_url": str(request.image_url),
            "prompt": "Natural camera motion, smooth animation", # Default prompt if none provided
            "motion_score": request.motion_strength # specific param for some providers
        }
        
        # If script provided, it might be an avatar video or TTS? 
        # Short Video tool usually just animates the image.
        # If script is present, maybe use it as prompting guidance?
        # For now, stick to standard animation.
        
        result = await provider_router.route(
            TaskType.IMAGE_TO_VIDEO,
            task_params
        )

        if not result.get("success"):
            return ToolResponse(
                success=False,
                message=result.get("error", "Video generation failed")
            )

        video_url = result.get("video_url") or result.get("output", {}).get("video_url") or result.get("output_url")

        # Optional: Apply style transformation (Video-to-Video)
        if request.style and video_url:
            style_prompt = get_style_prompt(request.style)
            if style_prompt:
                style_result = await provider_router.route(
                    TaskType.V2V,
                    {"video_url": video_url, "prompt": style_prompt}
                )
                output_url = style_result.get("video_url") or style_result.get("output_url") or style_result.get("output", {}).get("video_url")
                if output_url:
                    video_url = output_url
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
            db.add(user_gen)
            await db.commit()

            return ToolResponse(
                success=True,
                result_url=video_url,
                credits_used=credits_used,
                message="Short video generated successfully"
            )
        else:
            return ToolResponse(
                success=False,
                message="Video generation returned no URL"
            )

    except Exception as e:
        logger.error(f"Short video error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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

    # ========== DEMO USER: Use pre-generated Material DB ==========
    if not is_subscribed_user(current_user):
        logger.info("Demo user: Looking up pre-generated avatar result")
        
        result = await db.execute(
            select(Material)
            .where(Material.tool_type == ToolType.AI_AVATAR)
            .where(Material.is_active == True)
            .limit(1)
        )
        material = result.scalars().first()
        
        if material:
            result_url = material.result_watermarked_url or material.result_video_url
            return ToolResponse(
                success=True,
                result_url=result_url,
                credits_used=0,
                cached=True,
                message="Demo result (watermarked)"
            )
        else:
            return ToolResponse(
                success=False,
                message="No pre-generated examples available. Please subscribe."
            )
    
    # ========== SUBSCRIBER: Real-time Generation ==========
    try:
        # Validate language
        if request.language not in ["en", "zh-TW", "ja", "ko"]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported language: {request.language}. Supported: en, zh-TW, ja, ko"
            )

        # Validate duration
        if request.duration < 5 or request.duration > 120:
            raise HTTPException(
                status_code=400,
                detail="Duration must be between 5 and 120 seconds"
            )

        avatar_service = get_a2e_service()

        logger.info(f"Calling A2E.ai Avatar API for subscriber: {request.script[:50]}...")

        result = await avatar_service.generate_and_wait(
            image_url=str(request.image_url),
            script=request.script,
            language=request.language,
            voice_id=request.voice_id,
            duration=request.duration,
            timeout=300,
            save_locally=True
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
                    "api": "a2e-avatar",
                    "action": "photo_to_avatar",
                    "language": request.language
                },
                credits_used=30,
            )
            db.add(user_gen)
            await db.commit()

            return ToolResponse(
                success=True,
                result_url=video_url,
                credits_used=30,
                message=f"Avatar video generated successfully in {request.language}"
            )
        else:
            return ToolResponse(
                success=False,
                message=result.get("error", "Avatar generation failed")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Avatar generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    Get available A2E avatar characters.
    
    Frontend should use these characters instead of fixed Unsplash images.
    Each character includes:
    - _id: Anchor ID for generation
    - name: Character name
    - video_cover: Preview image URL
    - lang: Supported language(s)
    
    Characters are organized by gender where possible.
    """
    from scripts.services import A2EClient
    import os
    
    try:
        a2e = A2EClient(os.getenv("A2E_API_KEY", ""))
        characters = await a2e.get_characters()
        
        if not characters:
            return {"success": False, "characters": [], "error": "No characters available"}
        
        # Organize by gender (detect from name)
        female_chars = []
        male_chars = []
        other_chars = []
        
        for char in characters:
            name_lower = (char.get("name") or "").lower()
            char_info = {
                "id": char.get("_id"),
                "name": char.get("name"),
                "preview_url": char.get("video_cover"),
                "lang": char.get("lang", "en")
            }
            
            if any(kw in name_lower for kw in ["女", "female", "woman", "girl", "小美", "小雅", "小玲"]):
                char_info["gender"] = "female"
                female_chars.append(char_info)
            elif any(kw in name_lower for kw in ["男", "male", "man", "guy", "建明", "志偉", "俊傑"]):
                char_info["gender"] = "male"
                male_chars.append(char_info)
            else:
                char_info["gender"] = "unknown"
                other_chars.append(char_info)
        
        # Limit to reasonable number for UI
        return {
            "success": True,
            "female": female_chars[:6],
            "male": male_chars[:6],
            "other": other_chars[:6],
            "total": len(characters)
        }
    except Exception as e:
        logger.error(f"Failed to get A2E characters: {e}")
        return {"success": False, "characters": [], "error": str(e)}


# ============================================================================
# Image-to-Image Transform
# ============================================================================

class ImageTransformRequest(BaseModel):
    """Image-to-Image transformation using PiAPI Flux"""
    image_url: HttpUrl
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
    # ========== DEMO USER: Use pre-generated Material DB ==========
    if not is_subscribed_user(current_user):
        logger.info("Demo user: Looking up pre-generated effect result for I2I")

        result = await db.execute(
            select(Material)
            .where(Material.tool_type == ToolType.EFFECT)
            .where(Material.is_active == True)
            .limit(1)
        )
        material = result.scalars().first()

        if material:
            result_url = material.result_watermarked_url or material.result_image_url
            return ToolResponse(
                success=True,
                result_url=result_url,
                credits_used=0,
                cached=True,
                message="Demo result (watermarked). Subscribe for custom I2I transformations."
            )
        else:
            return ToolResponse(
                success=False,
                message="No pre-generated examples available. Please subscribe."
            )

    # ========== SUBSCRIBER: Real-time I2I Generation ==========
    from app.services.tier_config import get_credit_cost, get_user_tier

    tier = get_user_tier(current_user)
    cost = get_credit_cost("i2i", current_user)

    if current_user.total_credits < cost:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "insufficient_credits",
                "message": "Insufficient credits",
                "required": cost,
                "current": current_user.total_credits,
            }
        )

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
            db.add(user_gen)

            # Deduct credits
            current_user.total_credits -= cost
            await db.commit()

            return ToolResponse(
                success=True,
                result_url=result_url,
                credits_used=cost,
                message="Image transformed successfully"
            )
        else:
            return ToolResponse(
                success=False,
                message=result.get("error", "Image transformation failed")
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image transform error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    models = TRYON_MODELS
    if gender:
        models = [m for m in models if m["gender"] == gender]
    if body_type:
        models = [m for m in models if m["body_type"] == body_type]
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
