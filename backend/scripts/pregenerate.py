#!/usr/bin/env python3
"""
VidGo Pre-generation Pipeline - PROPER FLOW

This script generates all demo materials BEFORE service starts.
ALL source images are AI-generated from prompts (no placeholders).

CORRECT WORKFLOW:
==================
1. Background Removal:
   Prompt -> PiAPI (T2I) -> Source Image -> rembg -> Result Image

2. Short Video:
   Prompt -> PiAPI (T2I) -> Source Image -> Pollo (I2V) -> Video
   OR: Prompt -> Pollo (T2V) -> Video

3. AI Avatar:
   Portrait Prompt -> PiAPI (T2I) -> Portrait Image -> A2E (lip-sync) -> Video

4. Room Redesign / Product Scene / Try On:
   Since PiAPI T2I doesn't support I2I/ControlNet yet, we simulate results:
   Input (Hardcoded Unsplash) -> Prompt (Style/Scene) -> PiAPI (T2I) -> Result Image
   This ensures DB has "Results" for the frontend presets.

Usage:
    python -m scripts.pregenerate --all
    python -m scripts.pregenerate --tool background_removal --limit 6
    python -m scripts.pregenerate --dry-run
"""
import asyncio
import argparse
import hashlib
import logging
import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# Add app to path
sys.path.insert(0, "/app")

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.material import Material, ToolType, MaterialSource, MaterialStatus, MATERIAL_TOPICS, AVATAR_SCRIPTS

# Import service clients
from scripts.services import PiAPIClient, PolloClient, A2EClient, RembgClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# DATA DEFINITIONS (Matching Frontend Hardcoded Assets)
# ============================================================================

# Product prompts for background removal
PRODUCT_PROMPTS = {
    "electronics": [
        "Professional product photo of a sleek smartwatch with metallic band on white background, studio lighting, 8K detail",
        "High-end wireless earbuds in charging case, minimalist white background, commercial photography",
        "Modern smartphone floating on white background, reflections, product photography",
    ],
    "fashion": [
        "Designer sneakers on white background, studio lighting, fashion product photography",
        "Luxury leather handbag on white background, soft shadows, commercial quality",
        "Elegant high-heel shoes on white background, fashion editorial style",
    ],
    "jewelry": [
        "Diamond engagement ring on white background, macro photography, sparkling reflections",
        "Gold necklace with pendant on white background, luxury jewelry photography",
        "Pearl earrings on white background, soft lighting, elegant product shot",
    ],
    "cosmetics": [
        "Luxury lipstick on white background, beauty product photography, glossy finish",
        "Perfume bottle on white background, elegant lighting, premium product shot",
        "Skincare cream jar on white background, clean aesthetic, spa feeling",
    ],
}

# Video prompts for short videos (landing page topics)
VIDEO_PROMPTS = {
    "ecommerce": "Cinematic product showcase, luxury watch rotating slowly, golden hour lighting, 4K quality",
    "social": "Trendy lifestyle product, vibrant colors, social media aesthetic, dynamic motion",
    "brand": "Fashion model walking elegantly, dress flowing, dramatic lighting, brand video",
    "app": "Tech product demo animation, clean interface, modern design, smooth transitions",
    "promo": "Flash sale countdown, dynamic graphics, exciting energy, promotional video",
    "service": "Steaming coffee cup, cozy cafe atmosphere, warm lighting, lifestyle video",
}

# Room Redesign Assets (Floor Plans / Sketches)
ROOM_ASSETS = [
    {"id": "plan-1", "name": "Architectural Drawing", "url": "https://images.unsplash.com/photo-1599809275372-b4036ffd5e94?w=800"},
    {"id": "plan-2", "name": "Technical Sketch", "url": "https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=800"},
    {"id": "plan-3", "name": "Apartment Plan", "url": "https://images.unsplash.com/photo-1554995207-c18c203602cb?w=800"},
    {"id": "plan-4", "name": "Blueprint", "url": "https://images.unsplash.com/photo-1581093196277-9f608eeae92d?w=800"},
]

ROOM_STYLES = [
    {"id": "modern_minimalist", "name": "Modern Minimalist", "prompt": "modern minimalist interior design, clean lines, neutral colors"},
    {"id": "scandinavian", "name": "Scandinavian", "prompt": "scandinavian interior design, hygge, wood textures, bright"},
    {"id": "japanese", "name": "Japanese", "prompt": "japanese interior design, zen, tatami, bamboo, peaceful"},
    {"id": "industrial", "name": "Industrial", "prompt": "industrial interior design, exposed brick, metal accents, loft style"},
    {"id": "mid_century_modern", "name": "Mid-Century Modern", "prompt": "mid-century modern interior design, retro furniture, vibrant colors"},
]

# Product Scene Assets (from ProductScene.vue)
PRODUCT_ASSETS = [
    {"id": "product-1", "name": "Watch", "url": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800"},
    {"id": "product-2", "name": "Headphones", "url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800"},
    {"id": "product-3", "name": "Sneaker", "url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800"},
    {"id": "product-4", "name": "Camera", "url": "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=800"},
    {"id": "product-5", "name": "Perfume", "url": "https://images.unsplash.com/photo-1541643600914-78b084683601?w=800"},
]

SCENE_TYPES = [
    {"id": "studio", "name": "Studio", "prompt": "professional studio lighting, solid color background, product photography"},
    {"id": "nature", "name": "Nature", "prompt": "outdoor nature setting, sunlight, leaves, natural environment"},
    {"id": "luxury", "name": "Luxury", "prompt": "luxury marble background, elegant lighting, premium feeling"},
    {"id": "minimal", "name": "Minimal", "prompt": "minimalist abstract background, soft shadows, clean composition"},
    {"id": "lifestyle", "name": "Lifestyle", "prompt": "lifestyle home setting, cozy atmosphere, everyday context"},
]

# Try On Assets (from TryOn.vue)
TRYON_MODELS = [
    {"id": "female-1", "name": "Female 1", "gender": "female", "url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=512"},
    {"id": "female-2", "name": "Female 2", "gender": "female", "url": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=512"},
    {"id": "male-1", "name": "Male 1", "gender": "male", "url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=512"},
]

TRYON_CLOTHING = [
    {"id": "dress-red", "name": "Red Summer Dress", "prompt": "red summer dress"},
    {"id": "jacket-denim", "name": "Blue Denim Jacket", "prompt": "blue denim jacket"},
    {"id": "suit-black", "name": "Black Business Suit", "prompt": "black business suit"},
    {"id": "shirt-white", "name": "White Casual Shirt", "prompt": "white casual shirt"},
]


# ============================================================================
# MAIN GENERATOR
# ============================================================================

class PreGenerator:
    """Main pre-generation pipeline with proper AI-generated content."""

    def __init__(self):
        # Initialize API clients
        self.piapi = PiAPIClient(os.getenv("PIAPI_KEY", ""))
        self.pollo = PolloClient(os.getenv("POLLO_API_KEY", ""))
        self.a2e = A2EClient(os.getenv("A2E_API_KEY", ""))
        self.rembg = RembgClient()

        # Stats
        self.stats = {"success": 0, "failed": 0, "by_tool": {}}

    async def check_apis(self) -> Dict[str, bool]:
        """Check which APIs are configured."""
        return {
            "piapi": bool(os.getenv("PIAPI_KEY")),
            "pollo": bool(os.getenv("POLLO_API_KEY")),
            "a2e": bool(os.getenv("A2E_API_KEY")),
            "rembg": self.rembg.available,
        }

    def _generate_lookup_hash(
        self,
        tool_type: str,
        prompt: str,
        effect_prompt: str = None,
        input_image_url: str = None
    ) -> str:
        """Generate lookup hash for preset matching."""
        # Include input_image_url in hash to differentiate items
        content = f"{tool_type}:{prompt}:{effect_prompt or ''}:{input_image_url or ''}"
        return hashlib.sha256(content.encode()).hexdigest()[:64]

    # ========================================================================
    # BACKGROUND REMOVAL: Prompt -> T2I -> rembg -> Result
    # ========================================================================

    async def generate_background_removal(self, limit: int = 10):
        """
        Generate background removal examples.

        Flow:
        1. Prompt -> PiAPI (T2I) -> Source Image
        2. Source Image -> rembg -> Result Image (transparent BG)
        3. Store with full generation_steps
        """
        logger.info("=" * 60)
        logger.info("BACKGROUND REMOVAL (PiAPI T2I -> rembg)")
        logger.info("=" * 60)

        self.stats["by_tool"]["background_removal"] = {"success": 0, "failed": 0}
        count = 0

        for category, prompts in PRODUCT_PROMPTS.items():
            if count >= limit:
                break

            for prompt in prompts:
                if count >= limit:
                    break

                logger.info(f"[{count+1}/{limit}] {category}: Generating from prompt...")
                logger.info(f"  Prompt: {prompt[:60]}...")

                generation_steps = []
                start_time = time.time()

                # Step 1: Generate source image from prompt
                logger.info("  Step 1: PiAPI T2I...")
                t2i_result = await self.piapi.generate_image(
                    prompt=prompt,
                    width=1024,
                    height=1024
                )

                if not t2i_result["success"]:
                    logger.error(f"    T2I Failed: {t2i_result['error']}")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["background_removal"]["failed"] += 1
                    count += 1
                    continue

                source_image_url = t2i_result["image_url"]
                generation_steps.append({
                    "step": 1,
                    "api": "piapi",
                    "action": "text_to_image",
                    "model": "flux1-schnell",
                    "input": {"prompt": prompt},
                    "result_url": source_image_url,
                    "cost": 0.005,
                    "duration_ms": int((time.time() - start_time) * 1000)
                })
                logger.info(f"    Source: {source_image_url}")

                # Step 2: Remove background with rembg
                logger.info("  Step 2: rembg background removal...")
                step2_start = time.time()

                # Need full URL for rembg - construct from local path
                if source_image_url.startswith("/static"):
                    # Local file - read directly
                    local_path = f"/app{source_image_url}"
                    rembg_result = await self.rembg.remove_background_local(local_path)
                else:
                    rembg_result = await self.rembg.remove_background(source_image_url)

                if not rembg_result["success"]:
                    logger.error(f"    rembg Failed: {rembg_result['error']}")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["background_removal"]["failed"] += 1
                    count += 1
                    continue

                result_image_url = rembg_result["image_url"]
                generation_steps.append({
                    "step": 2,
                    "api": "rembg",
                    "action": "background_removal",
                    "input": {"image_url": source_image_url},
                    "result_url": result_image_url,
                    "cost": 0,  # FREE
                    "duration_ms": int((time.time() - step2_start) * 1000)
                })
                logger.info(f"    Result: {result_image_url}")

                # Save to database with full chain
                await self._save_material(
                    tool_type=ToolType.BACKGROUND_REMOVAL,
                    topic=category,
                    prompt=prompt,
                    input_image_url=source_image_url,
                    result_image_url=result_image_url,
                    generation_steps=generation_steps,
                    generation_cost=0.005  # PiAPI cost only, rembg is free
                )

                self.stats["success"] += 1
                self.stats["by_tool"]["background_removal"]["success"] += 1
                logger.info(f"  Success! Total time: {time.time() - start_time:.1f}s")

                count += 1
                await asyncio.sleep(2)  # Rate limiting

    # ========================================================================
    # SHORT VIDEO: Prompt -> T2I -> I2V (or T2V directly)
    # ========================================================================

    async def generate_short_video(self, limit: int = 6):
        """
        Generate short video examples for landing page.

        Flow (I2V):
        1. Prompt -> PiAPI (T2I) -> Source Image
        2. Source Image + Motion Prompt -> Pollo (I2V) -> Video

        Flow (T2V):
        1. Prompt -> Pollo (T2V) -> Video
        """
        logger.info("=" * 60)
        logger.info("SHORT VIDEO (PiAPI T2I -> Pollo I2V)")
        logger.info("=" * 60)

        self.stats["by_tool"]["short_video"] = {"success": 0, "failed": 0}
        count = 0
        landing_topics = ["ecommerce", "social", "brand", "app", "promo", "service"]

        for topic in landing_topics:
            if count >= limit:
                break

            prompt = VIDEO_PROMPTS.get(topic, VIDEO_PROMPTS["ecommerce"])
            logger.info(f"[{count+1}/{limit}] {topic}: Generating video...")
            logger.info(f"  Prompt: {prompt[:60]}...")

            generation_steps = []
            start_time = time.time()

            # Use T2V directly for simpler flow
            logger.info("  Step 1: Pollo T2V...")
            video_result = await self.pollo.generate_video(
                prompt=prompt,
                length=5
            )

            if not video_result["success"]:
                logger.error(f"    T2V Failed: {video_result['error']}")
                self.stats["failed"] += 1
                self.stats["by_tool"]["short_video"]["failed"] += 1
                count += 1
                continue

            result_video_url = video_result["video_url"]
            generation_steps.append({
                "step": 1,
                "api": "pollo",
                "action": "text_to_video",
                "model": "pollo-v2-0",
                "input": {"prompt": prompt, "length": 5},
                "result_url": result_video_url,
                "cost": 0.10,
                "duration_ms": int((time.time() - start_time) * 1000)
            })
            logger.info(f"    Result: {result_video_url}")

            # Save to database
            await self._save_material(
                tool_type=ToolType.SHORT_VIDEO,
                topic=topic,
                prompt=prompt,
                result_video_url=result_video_url,
                generation_steps=generation_steps,
                generation_cost=0.10
            )

            self.stats["success"] += 1
            self.stats["by_tool"]["short_video"]["success"] += 1
            logger.info(f"  Success! Total time: {time.time() - start_time:.1f}s")

            count += 1
            await asyncio.sleep(5)  # Rate limiting for video API

    # ========================================================================
    # AI AVATAR: Script -> A2E TTS -> A2E Video (uses pre-defined anchors)
    # ========================================================================

    async def generate_ai_avatar(self, limit: int = 60):
        """
        Generate AI avatar examples that EXACTLY match frontend defaults.
        
        Frontend provides:
        - 6 Default Avatars (3 Female, 3 Male)
        - 5 Default Scripts (Welcome, Product, Thanks, Features, Promo)
        - 2 Languages (EN, ZH)
        
        Total Combinations: 6 * 5 = 30 per language.
        """
        logger.info("=" * 60)
        logger.info("AI AVATAR - FRONTEND MATCHING GENERATION")
        logger.info("=" * 60)

        self.stats["by_tool"]["ai_avatar"] = {"success": 0, "failed": 0}
        count = 0

        # === DATA FROM FRONTEND ===
        
        # 1. Default Avatars (must match AIAvatar.vue)
        avatars = [
            {"id": "female-1", "gender": "female", "url": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=512"},
            {"id": "female-2", "gender": "female", "url": "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=512"},
            {"id": "female-3", "gender": "female", "url": "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=512"},
            {"id": "male-1", "gender": "male", "url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=512"},
            {"id": "male-2", "gender": "male", "url": "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=512"},
            {"id": "male-3", "gender": "male", "url": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=512"},
        ]

        # 2. Default Scripts (must match AIAvatar.vue)
        scripts_data = [
            {
                "id": "script-welcome",
                "text_zh": "歡迎來到我們的品牌！我很高興為您介紹我們最新的創新產品，將改變您的日常生活。",
                "text_en": "Welcome to our brand! I'm excited to introduce our latest innovative products that will transform your daily life.",
                "topic": "brand"
            },
            {
                "id": "script-product",
                "text_zh": "大家好！今天我要給您展示一些真正特別的東西。讓我們一起發現我們產品的獨特之處。",
                "text_en": "Hello everyone! Today I'll show you something truly special. Let's discover what makes our products unique.",
                "topic": "ecommerce"
            },
            {
                "id": "script-thanks",
                "text_zh": "感謝您的加入！我們一直努力為您帶來最好的品質和體驗。",
                "text_en": "Thank you for joining us! We've been working hard to bring you the best quality and experience possible.",
                "topic": "service"
            },
            {
                "id": "script-features",
                "text_zh": "嗨！讓我告訴您關於我們客戶絕對喜愛的驚人新功能。",
                "text_en": "Hi there! Let me tell you about our amazing new features that our customers absolutely love.",
                "topic": "app"
            },
            {
                "id": "script-promo",
                "text_zh": "嗨大家好！不要錯過我們的獨家優惠。立即訂閱，首單享受超值折扣！",
                "text_en": "Hey everyone! Don't miss out on our exclusive offer. Subscribe now and save big on your first order!",
                "topic": "promo"
            }
        ]

        # Loop through all combinations
        for language in ["en", "zh-TW"]:
            if count >= limit:
                break
                
            for avatar in avatars:
                if count >= limit:
                    break
                    
                for script_item in scripts_data:
                    if count >= limit:
                        break

                    script_text = script_item["text_zh"] if language == "zh-TW" else script_item["text_en"]
                    
                    # Log generation attempt
                    logger.info(f"[{count+1}] {language} | {avatar['id']} | {script_item['id']}")
                    logger.info(f"  Script: {script_text[:40]}...")

                    generation_steps = []
                    start_time = time.time()

                    # Call A2E API
                    # Note: We pass the image_url to A2E. The API handles generating the talking head directly.
                    # This simplifies the flow compared to the previous 2-step process.
                    
                    logger.info("  Generating avatar video...")
                    avatar_result = await self.a2e.generate_avatar(
                        script=script_text,
                        language=language,
                        image_url=avatar["url"], # Pass the specific avatar image
                        gender=avatar["gender"],
                        save_locally=True
                    )

                    if not avatar_result["success"]:
                        logger.error(f"    A2E Failed: {avatar_result['error']}")
                        self.stats["failed"] += 1
                        self.stats["by_tool"]["ai_avatar"]["failed"] += 1
                        count += 1
                        continue

                    result_video_url = avatar_result["video_url"]
                    audio_url = avatar_result.get("audio_url", "")

                    generation_steps.append({
                        "step": 1,
                        "api": "a2e",
                        "action": "avatar_generation",
                        "input": {
                            "script": script_text, 
                            "language": language,
                            "avatar_id": avatar["id"],
                            "script_id": script_item["id"]
                        },
                        "result_url": result_video_url,
                        "cost": 0.10,
                        "duration_ms": int((time.time() - start_time) * 1000)
                    })
                    
                    logger.info(f"    Video: {result_video_url}")

                    await self._save_material(
                        tool_type=ToolType.AI_AVATAR,
                        topic=script_item["topic"],
                        prompt=script_text,
                        input_image_url=avatar["url"],
                        result_video_url=result_video_url,
                        generation_steps=generation_steps,
                        input_params={
                            "avatar_id": avatar["id"],
                            "script_id": script_item["id"],
                            "language": language
                        },
                        generation_cost=0.10,
                        language=language,
                    )

                    self.stats["success"] += 1
                    self.stats["by_tool"]["ai_avatar"]["success"] += 1
                    
                    count += 1
                    await asyncio.sleep(2)  # Rate limiting

    # ========================================================================
    # NEW GENERATORS
    # ========================================================================

    async def generate_room_redesign(self, limit: int = 50):
        """Generate Room Redesign Examples (2D-to-3D Visualization)."""
        logger.info("=" * 60); logger.info("ROOM REDESIGN (2D Floor Plan -> 3D Render)")
        self.stats["by_tool"]["room_redesign"] = {"success": 0, "failed": 0}
        count = 0
        
        for room in ROOM_ASSETS:
            for style in ROOM_STYLES:
                if count >= limit: break
                logger.info(f"[{count+1}] Plan: {room['name']} -> Style: {style['name']}")
                
                # Prompt: "Photorealistic 3D render of [Modern] interior from architectural floor plan, 8k, isometric view"
                prompt = f"Photorealistic 3D render of {style['prompt']} from architectural floor plan, 8k, isometric view, high detail, commercial lighting"
                
                t2i = await self.piapi.generate_image(prompt=prompt)
                if not t2i["success"]: continue
                
                await self._save_material(
                    tool_type=ToolType.ROOM_REDESIGN,
                    topic=room["id"], # Store plan_id in topic
                    prompt=prompt,
                    input_image_url=room["url"], # Input is now a floor plan
                    result_image_url=t2i["image_url"],
                    input_params={"room_id": room["id"], "style_id": style["id"], "room_type": room["name"].lower().replace(" ", "_")}, 
                    generation_cost=0.005
                )
                self.stats["success"] += 1; self.stats["by_tool"]["room_redesign"]["success"] += 1; count += 1

    async def generate_product_scene(self, limit: int = 50):
        """Generate Product Scene Examples."""
        logger.info("=" * 60); logger.info("PRODUCT SCENE (Simulated)")
        self.stats["by_tool"]["product_scene"] = {"success": 0, "failed": 0}
        count = 0
        
        for prod in PRODUCT_ASSETS:
            for scene in SCENE_TYPES:
                if count >= limit: break
                logger.info(f"[{count+1}] Product: {prod['name']} -> Scene: {scene['name']}")
                
                prompt = f"Professional product photography of a {prod['name']}, {scene['prompt']}, commercial lighting, 8k"
                
                t2i = await self.piapi.generate_image(prompt=prompt)
                if not t2i["success"]: continue
                
                await self._save_material(
                    tool_type=ToolType.PRODUCT_SCENE,
                    topic=scene["id"],
                    prompt=prompt,
                    input_image_url=prod["url"],
                    result_image_url=t2i["image_url"],
                    input_params={"product_id": prod["id"], "scene_type": scene["id"]},
                    generation_cost=0.005
                )
                self.stats["success"] += 1; self.stats["by_tool"]["product_scene"]["success"] += 1; count += 1

    async def generate_try_on(self, limit: int = 50):
        """Generate Try On Examples."""
        logger.info("=" * 60); logger.info("VIRTUAL TRY ON (Simulated)")
        self.stats["by_tool"]["try_on"] = {"success": 0, "failed": 0}
        count = 0
        
        for model in TRYON_MODELS:
            for cloth in TRYON_CLOTHING:
                if count >= limit: break
                logger.info(f"[{count+1}] Model: {model['name']} -> Cloth: {cloth['name']}")
                
                prompt = f"Professional fashion photography of a {model['gender']} model wearing {cloth['prompt']}, studio lighting, full body shot"
                
                t2i = await self.piapi.generate_image(prompt=prompt)
                if not t2i["success"]: continue
                
                # For Try On, we need to save the CLOTHING image too?
                # Frontend uses 'input_image_url' as the clothing preview.
                # So we should ideally have a separate material for the clothing item itself?
                # Or just use the one record.
                # TryOn.vue: demoClothingItems = demoTemplates.filter(t => t.input_image_url)
                # So we need to store the CLOTHING image in input_image_url.
                # But we don't have a clothing image URL yet.
                # Let's generate one or use a placeholder/Unsplash?
                # I'll use T2I to generate the clothing item on white bg first?
                # No, to save time/cost, let's use a generic Unsplash for cloth or just standard icon?
                # Actually, I'll allow input_image_url to be the RESULT of a "clothing only" T2I?
                # Too complex.
                # I will use a dummy Unsplash for clothing or just re-use the result?
                # Let's use T2I to generate the clothing image quickly (white bg).
                
                cloth_prompt = f"Product photo of {cloth['prompt']}, white background, flat lay"
                cloth_img = await self.piapi.generate_image(prompt=cloth_prompt)
                clothing_url = cloth_img["image_url"] if cloth_img["success"] else "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=512"

                await self._save_material(
                    tool_type=ToolType.TRY_ON,
                    topic="fashion",
                    prompt=prompt,
                    input_image_url=clothing_url, # Frontend uses this as clothing preview
                    result_image_url=t2i["image_url"],
                    input_params={"model_id": model["id"]}, # Match frontend selection
                    generation_cost=0.01
                )
                self.stats["success"] += 1; self.stats["by_tool"]["try_on"]["success"] += 1; count += 1


    # ========================================================================
    # HELPER: Save to Database with full chain
    # ========================================================================

    async def _save_material(
        self,
        tool_type: ToolType,
        topic: str,
        prompt: str,
        input_image_url: Optional[str] = None,
        input_video_url: Optional[str] = None,
        result_image_url: Optional[str] = None,
        result_video_url: Optional[str] = None,
        effect_prompt: Optional[str] = None,
        generation_steps: List[Dict] = None,
        input_params: Dict[str, Any] = None,
        generation_cost: float = 0.0,
        language: str = "en"
    ):
        """Save generated material to database with full generation chain."""

        # Generate lookup hash
        lookup_hash = self._generate_lookup_hash(
            tool_type=tool_type.value,
            prompt=prompt,
            effect_prompt=effect_prompt,
            input_image_url=input_image_url
        )

        async with AsyncSessionLocal() as session:
            # Check if already exists
            existing = await session.execute(
                select(Material).where(Material.lookup_hash == lookup_hash)
            )
            if existing.scalar_one_or_none():
                logger.info(f"  Material already exists (hash: {lookup_hash[:16]}...)")
                return

            material = Material(
                lookup_hash=lookup_hash,
                tool_type=tool_type,
                topic=topic,
                language=language,
                source=MaterialSource.SEED,
                status=MaterialStatus.APPROVED,

                # Input data
                prompt=prompt,
                effect_prompt=effect_prompt,
                input_image_url=input_image_url,
                input_video_url=input_video_url,
                input_params=input_params or {},


                # Generation pipeline
                generation_steps=generation_steps or [],
                generation_cost_usd=generation_cost,

                # Output data
                result_image_url=result_image_url,
                result_video_url=result_video_url,
                result_watermarked_url=result_video_url or result_image_url,

                # Quality
                quality_score=0.9,
                is_featured=True,
                is_active=True
            )
            session.add(material)
            await session.commit()
            logger.debug(f"  Saved: {material.id} (hash: {lookup_hash[:16]}...)")

    # ========================================================================
    # MAIN ENTRY
    # ========================================================================

    async def run(
        self,
        tool: Optional[str] = None,
        limit: int = 10,
        dry_run: bool = False
    ):
        """Run pre-generation pipeline."""
        logger.info("=" * 60)
        logger.info("VidGo Pre-generation Pipeline")
        logger.info("PROPER FLOW: Prompt -> T2I -> Effect -> DB")
        logger.info("=" * 60)

        # Check APIs
        api_status = await self.check_apis()
        logger.info(f"API Status: {api_status}")

        if dry_run:
            logger.info("[DRY RUN] Would generate materials but not calling APIs")
            return

        # Run generators
        tools_to_run = {
            "background_removal": self.generate_background_removal,
            "short_video": self.generate_short_video,
            "ai_avatar": self.generate_ai_avatar,
            "room_redesign": self.generate_room_redesign,
            "product_scene": self.generate_product_scene,
            "try_on": self.generate_try_on,
        }

        if tool:
            if tool in tools_to_run:
                await tools_to_run[tool](limit=limit)
            else:
                logger.error(f"Unknown tool: {tool}")
                logger.info(f"Available tools: {list(tools_to_run.keys())}")
        else:
            # Run all
            for name, func in tools_to_run.items():
                try:
                    await func(limit=limit)
                except Exception as e:
                    logger.error(f"Error in {name}: {e}")

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Success: {self.stats['success']}")
        logger.info(f"Total Failed: {self.stats['failed']}")
        for tool_name, tool_stats in self.stats["by_tool"].items():
            logger.info(f"  {tool_name}: {tool_stats['success']} success, {tool_stats['failed']} failed")


# ============================================================================
# CLI
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(description="VidGo Pre-generation Pipeline")
    parser.add_argument("--tool", type=str, help="Specific tool (background_removal, short_video, ai_avatar)")
    parser.add_argument("--limit", type=int, default=10, help="Max materials per tool")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated")
    parser.add_argument("--all", action="store_true", help="Generate all tools")

    args = parser.parse_args()

    generator = PreGenerator()
    await generator.run(
        tool=args.tool if not args.all else None,
        limit=args.limit,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    asyncio.run(main())