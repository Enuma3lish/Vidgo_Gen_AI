"""
Material System Pre-generation Script
Based on ARCHITECTURE_FINAL.md specification

This script implements the complete Material System pre-generation flow:
1. Generate topic-related prompts using Gemini
2. Generate source images using Leonardo/Gemini
3. Apply effects using GoEnhance for image tools
4. Store complete relationship chains to unified Material table

Usage:
    python -m scripts.material_pregenerate --tool background_removal --topic electronics --count 5
    python -m scripts.material_pregenerate --all --dry-run
"""
import asyncio
import argparse
import logging
import os
import sys
import uuid
import time
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSessionLocal
from app.models.material import Material, MaterialTopic, ToolType, MaterialSource, MaterialStatus, MATERIAL_TOPICS, AVATAR_SCRIPTS
from app.services.gemini_service import GeminiService
from app.services.pollo_avatar import PolloAvatarService, DEFAULT_AVATARS
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

settings = get_settings()

# Static directory for storing generated materials
STATIC_DIR = Path("/app/static/materials")


class MaterialPreGenerator:
    """
    Pre-generation service for Material System.

    Implements the complete flow:
    1. Generate prompts via Gemini
    2. Generate source images via Leonardo/Gemini
    3. Apply effects via GoEnhance
    4. Store with complete generation_steps chain
    """

    def __init__(self):
        self.gemini = GeminiService()
        self.leonardo_api_key = getattr(settings, 'LEONARDO_API_KEY', os.getenv('LEONARDO_API_KEY', ''))
        self.goenhance_api_key = getattr(settings, 'GOENHANCE_API_KEY', os.getenv('GOENHANCE_API_KEY', ''))
        self.pollo_api_key = getattr(settings, 'POLLO_API_KEY', os.getenv('POLLO_API_KEY', ''))
        self.avatar_service = PolloAvatarService()

        self.stats = {
            "prompts_generated": 0,
            "images_generated": 0,
            "effects_applied": 0,
            "avatars_generated": 0,
            "materials_saved": 0,
            "errors": []
        }

    async def validate_apis(self) -> Dict[str, bool]:
        """Validate API keys are configured"""
        return {
            "gemini": bool(self.gemini.api_key),
            "leonardo": bool(self.leonardo_api_key),
            "goenhance": bool(self.goenhance_api_key),
            "pollo": bool(self.pollo_api_key)
        }

    async def generate_prompts_for_tool(
        self,
        tool_type: ToolType,
        topic: str,
        count: int = 30
    ) -> List[str]:
        """
        Step 1: Generate topic-related prompts using Gemini.

        Args:
            tool_type: The tool type
            topic: Topic within the tool
            count: Number of prompts to generate

        Returns:
            List of generated prompts
        """
        logger.info(f"Generating {count} prompts for {tool_type.value}/{topic}")

        result = await self.gemini.generate_topic_prompts(
            tool=tool_type.value,
            topic=topic,
            count=count,
            language="en"
        )

        if result["success"]:
            self.stats["prompts_generated"] += len(result["prompts"])
            return result["prompts"]
        else:
            logger.error(f"Failed to generate prompts: {result.get('error')}")
            self.stats["errors"].append(f"Prompt generation failed: {result.get('error')}")
            return []

    async def generate_source_image(
        self,
        prompt: str,
        enhanced_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Step 2: Generate source image using Leonardo API.
        Falls back to Gemini if Leonardo fails.

        Args:
            prompt: The generation prompt
            enhanced_prompt: Optional enhanced version

        Returns:
            Dict with image_url, api_used, cost, duration_ms
        """
        start_time = time.time()
        generation_prompt = enhanced_prompt or prompt

        # Try Leonardo first
        if self.leonardo_api_key:
            result = await self._generate_with_leonardo(generation_prompt)
            if result["success"]:
                self.stats["images_generated"] += 1
                return {
                    "success": True,
                    "image_url": result["url"],
                    "api": "leonardo",
                    "model": result.get("model", "phoenix"),
                    "cost": result.get("cost", 0.01),
                    "duration_ms": int((time.time() - start_time) * 1000)
                }

        # Fallback to Gemini image generation
        if self.gemini.api_key:
            result = await self._generate_with_gemini(generation_prompt)
            if result["success"]:
                self.stats["images_generated"] += 1
                return {
                    "success": True,
                    "image_url": result["url"],
                    "api": "gemini",
                    "model": "imagen-3",
                    "cost": result.get("cost", 0.01),
                    "duration_ms": int((time.time() - start_time) * 1000)
                }

        return {"success": False, "error": "No image generation API available"}

    async def _generate_with_leonardo(self, prompt: str) -> Dict[str, Any]:
        """Generate image using Leonardo API"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Create generation
                response = await client.post(
                    "https://cloud.leonardo.ai/api/rest/v1/generations",
                    headers={
                        "Authorization": f"Bearer {self.leonardo_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "prompt": prompt,
                        "modelId": "6b645e3a-d64f-4341-a6d8-7a3690fbf042",  # Phoenix model
                        "width": 1024,
                        "height": 1024,
                        "num_images": 1,
                        "scheduler": "EULER_DISCRETE",
                        "presetStyle": "DYNAMIC"
                    }
                )

                if response.status_code != 200:
                    return {"success": False, "error": f"Leonardo error: {response.status_code}"}

                data = response.json()
                generation_id = data.get("sdGenerationJob", {}).get("generationId")

                if not generation_id:
                    return {"success": False, "error": "No generation ID returned"}

                # Poll for result
                for _ in range(30):
                    await asyncio.sleep(5)
                    status_response = await client.get(
                        f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}",
                        headers={"Authorization": f"Bearer {self.leonardo_api_key}"}
                    )

                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        images = status_data.get("generations_by_pk", {}).get("generated_images", [])
                        if images:
                            return {
                                "success": True,
                                "url": images[0].get("url"),
                                "model": "phoenix",
                                "cost": 0.01
                            }

                return {"success": False, "error": "Timeout waiting for Leonardo generation"}

        except Exception as e:
            logger.error(f"Leonardo API error: {e}")
            return {"success": False, "error": str(e)}

    async def _generate_with_gemini(self, prompt: str) -> Dict[str, Any]:
        """Generate image using Gemini Imagen 4.0 API"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict",
                    params={"key": self.gemini.api_key},
                    headers={"Content-Type": "application/json"},
                    json={
                        "instances": [{"prompt": prompt}],
                        "parameters": {
                            "sampleCount": 1,
                            "aspectRatio": "1:1"
                        }
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    predictions = data.get("predictions", [])
                    if predictions:
                        # Save base64 image to file
                        image_data = predictions[0].get("bytesBase64Encoded")
                        if image_data:
                            filename = f"gemini_{uuid.uuid4().hex[:8]}.jpg"
                            filepath = STATIC_DIR / filename
                            filepath.write_bytes(base64.b64decode(image_data))
                            return {
                                "success": True,
                                "url": f"/static/materials/{filename}",
                                "cost": 0.01
                            }

                return {"success": False, "error": f"Gemini Imagen error: {response.status_code}"}

        except Exception as e:
            logger.error(f"Gemini Imagen error: {e}")
            return {"success": False, "error": str(e)}

    async def apply_effect(
        self,
        tool_type: ToolType,
        source_image_url: str,
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Step 3: Apply tool-specific effect.

        Uses:
        - rembg for background removal (local, free)
        - GoEnhance for video style transfer

        Args:
            tool_type: The tool type (determines effect)
            source_image_url: URL or path of source image
            params: Additional parameters

        Returns:
            Dict with result_url, api_used, cost, duration_ms
        """
        start_time = time.time()

        if tool_type == ToolType.BACKGROUND_REMOVAL:
            # Use local rembg for background removal
            return await self._apply_rembg(source_image_url)

        elif tool_type in [ToolType.PRODUCT_SCENE, ToolType.ROOM_REDESIGN]:
            # These require more complex processing, skip for now
            return {"success": False, "skip": True, "reason": "Scene/redesign effects not yet implemented"}

        else:
            # Video tools don't need image effects
            return {"success": False, "skip": True, "reason": "Tool doesn't require image effect"}

    async def _apply_rembg(self, source_image_url: str) -> Dict[str, Any]:
        """Apply background removal using rembg (local, free)"""
        import time
        from rembg import remove
        from PIL import Image
        import io

        start_time = time.time()

        try:
            # Load image from local path or URL
            if source_image_url.startswith("/static/"):
                # Local file
                local_path = Path("/app") / source_image_url.lstrip("/")
                if not local_path.exists():
                    return {"success": False, "error": f"Image not found: {local_path}"}
                input_image = Image.open(local_path)
            else:
                # Remote URL
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(source_image_url)
                    if response.status_code != 200:
                        return {"success": False, "error": f"Failed to fetch image: {response.status_code}"}
                    input_image = Image.open(io.BytesIO(response.content))

            # Apply background removal
            output_image = remove(input_image)

            # Save result
            filename = f"rembg_{uuid.uuid4().hex[:8]}.png"
            filepath = STATIC_DIR / filename
            output_image.save(filepath, "PNG")

            self.stats["effects_applied"] += 1

            return {
                "success": True,
                "result_url": f"/static/materials/{filename}",
                "api": "rembg",
                "action": "remove-background",
                "cost": 0.0,  # Free local processing
                "duration_ms": int((time.time() - start_time) * 1000)
            }

        except Exception as e:
            logger.error(f"rembg error: {e}")
            return {"success": False, "error": str(e)}

    async def _call_goenhance(
        self,
        effect: str,
        image_url: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call GoEnhance API for a specific effect"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                endpoint = f"https://api.goenhance.ai/v1/images/{effect}"

                response = await client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {self.goenhance_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "image_url": image_url,
                        **params
                    }
                )

                if response.status_code != 200:
                    return {"success": False, "error": f"GoEnhance error: {response.status_code}"}

                data = response.json()
                task_id = data.get("task_id")

                if not task_id:
                    return {"success": False, "error": "No task ID returned"}

                # Poll for result
                for _ in range(30):
                    await asyncio.sleep(3)
                    status_response = await client.get(
                        f"https://api.goenhance.ai/v1/tasks/{task_id}",
                        headers={"Authorization": f"Bearer {self.goenhance_api_key}"}
                    )

                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        if status_data.get("status") == "completed":
                            return {
                                "success": True,
                                "url": status_data.get("result_url"),
                                "cost": 0.05
                            }
                        elif status_data.get("status") == "failed":
                            return {"success": False, "error": status_data.get("error", "Unknown error")}

                return {"success": False, "error": "Timeout waiting for GoEnhance"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def generate_avatar(
        self,
        script: str,
        language: str = "en",
        topic: str = "spokesperson"
    ) -> Dict[str, Any]:
        """
        Generate AI Avatar video with lip sync.

        Args:
            script: The text for the avatar to speak
            language: Language code ('en' or 'zh-TW')
            topic: Topic for selecting appropriate avatar image

        Returns:
            Dict with video_url, api_used, cost, duration_ms
        """
        if not self.pollo_api_key:
            return {"success": False, "error": "Pollo API key not configured"}

        start_time = time.time()

        try:
            # Get a default avatar image for the language
            import random
            avatars = DEFAULT_AVATARS.get(language, DEFAULT_AVATARS["en"])
            avatar_image = random.choice(avatars)

            # Generate avatar video
            result = await self.avatar_service.generate_and_wait(
                image_url=avatar_image,
                script=script,
                language=language,
                duration=30,
                timeout=300,
                save_locally=True
            )

            if result.get("success"):
                self.stats["avatars_generated"] += 1
                return {
                    "success": True,
                    "video_url": result.get("video_url"),
                    "remote_url": result.get("remote_url"),
                    "api": "pollo-avatar",
                    "model": "pollo-avatar",
                    "language": language,
                    "script": script,
                    "cost": 0.15,  # Avatar videos are more expensive
                    "duration_ms": int((time.time() - start_time) * 1000)
                }
            else:
                return {"success": False, "error": result.get("error", "Avatar generation failed")}

        except Exception as e:
            logger.error(f"Avatar generation error: {e}")
            return {"success": False, "error": str(e)}

    async def generate_video(
        self,
        prompt: str,
        source_image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate video using Pollo AI for short_video tool.

        Args:
            prompt: Video generation prompt
            source_image_url: Optional source image for image-to-video

        Returns:
            Dict with video_url, api_used, cost, duration_ms
        """
        if not self.pollo_api_key:
            return {"success": False, "error": "Pollo API key not configured"}

        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                # Create generation task
                response = await client.post(
                    "https://pollo.ai/api/platform/generation/pollo/pollo-v2-0",
                    headers={
                        "x-api-key": self.pollo_api_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "input": {
                            "prompt": prompt,
                            "length": 5,
                            "resolution": "720p",
                            "image_url": source_image_url
                        } if source_image_url else {
                            "prompt": prompt,
                            "length": 5,
                            "resolution": "720p"
                        }
                    }
                )

                if response.status_code != 200:
                    return {"success": False, "error": f"Pollo error: {response.status_code}"}

                data = response.json()
                task_id = data.get("id") or data.get("data", {}).get("taskId")

                if not task_id:
                    return {"success": False, "error": "No task ID returned"}

                logger.info(f"Pollo task created: {task_id}")

                # Poll for result
                for attempt in range(60):
                    await asyncio.sleep(5)

                    status_response = await client.get(
                        f"https://pollo.ai/api/platform/generation/{task_id}/status",
                        headers={"x-api-key": self.pollo_api_key}
                    )

                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        generations = status_data.get("data", {}).get("generations", [])

                        if generations:
                            gen = generations[0]
                            status = gen.get("status")

                            if status == "succeed":
                                video_url = gen.get("url")
                                if video_url:
                                    # Download and save locally
                                    video_response = await client.get(video_url)
                                    if video_response.status_code == 200:
                                        filename = f"video_{uuid.uuid4().hex[:8]}.mp4"
                                        filepath = STATIC_DIR / filename
                                        filepath.write_bytes(video_response.content)
                                        return {
                                            "success": True,
                                            "video_url": f"/static/materials/{filename}",
                                            "api": "pollo",
                                            "model": "pollo-v2-0",
                                            "cost": 0.10,
                                            "duration_ms": int((time.time() - start_time) * 1000)
                                        }
                            elif status == "failed":
                                return {"success": False, "error": gen.get("failMsg", "Generation failed")}

                return {"success": False, "error": "Timeout waiting for video generation"}

        except Exception as e:
            logger.error(f"Pollo video error: {e}")
            return {"success": False, "error": str(e)}

    async def save_material(
        self,
        session: AsyncSession,
        tool_type: ToolType,
        topic: str,
        prompt: str,
        enhanced_prompt: str,
        generation_steps: List[Dict],
        input_image_url: Optional[str],
        result_image_url: Optional[str],
        result_video_url: Optional[str],
        total_cost: float,
        language: str = "en"
    ) -> Material:
        """
        Step 4: Save material with complete generation chain.

        The generation_steps array maintains the relationship chain:
        prompt → source_image → effect_result
        """
        material = Material(
            tool_type=tool_type,
            topic=topic,
            language=language,
            tags=[topic, tool_type.value, language],
            source=MaterialSource.SEED,
            status=MaterialStatus.APPROVED,
            prompt=prompt,
            prompt_enhanced=enhanced_prompt,
            input_image_url=input_image_url,
            generation_steps=generation_steps,
            result_image_url=result_image_url,
            result_video_url=result_video_url,
            generation_cost_usd=total_cost,
            quality_score=0.85,
            is_active=True
        )

        # Generate title from prompt
        material.title_en = prompt[:100] if len(prompt) > 100 else prompt

        session.add(material)
        await session.commit()

        self.stats["materials_saved"] += 1
        logger.info(f"Saved material: {material.id} - {material.title_en[:50]}...")

        return material

    async def pregenerate_for_tool_topic(
        self,
        tool_type: ToolType,
        topic: str,
        count: int = 30,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Main pre-generation flow for a specific tool/topic combination.

        Implements the complete relationship chain:
        1. Generate prompts via Gemini
        2. For each prompt:
           a. Generate source image
           b. Apply effect (if applicable)
           c. Store with generation_steps
        """
        logger.info(f"=" * 60)
        logger.info(f"Pre-generating {count} materials for {tool_type.value}/{topic}")
        logger.info(f"=" * 60)

        # Step 1: Generate prompts
        prompts = await self.generate_prompts_for_tool(tool_type, topic, count)

        if not prompts:
            return {"success": False, "error": "Failed to generate prompts", "count": 0}

        logger.info(f"Generated {len(prompts)} prompts")

        if dry_run:
            logger.info("DRY RUN - Skipping image/video generation")
            return {"success": True, "prompts": prompts, "count": len(prompts)}

        # Ensure static directory exists
        STATIC_DIR.mkdir(parents=True, exist_ok=True)

        async with AsyncSessionLocal() as session:
            success_count = 0

            for i, prompt in enumerate(prompts):
                logger.info(f"\n[{i+1}/{len(prompts)}] Processing: {prompt[:50]}...")

                generation_steps = []
                total_cost = 0.0

                try:
                    # Enhance prompt
                    enhance_result = await self.gemini.enhance_prompt(prompt, category=topic)
                    enhanced = enhance_result.get("enhanced_prompt", prompt)

                    generation_steps.append({
                        "step": 1,
                        "api": "gemini",
                        "action": "enhance_prompt",
                        "input": {"prompt": prompt},
                        "output": {"enhanced_prompt": enhanced}
                    })

                    # Step 2: Generate content based on tool type
                    if tool_type == ToolType.AI_AVATAR:
                        # For AI Avatar, use pre-defined scripts (skip for now in prompt-based flow)
                        # Avatar generation happens in pregenerate_avatars method
                        logger.info(f"Skipping avatar in prompt-based flow - use pregenerate_avatars()")
                        continue

                    elif tool_type == ToolType.SHORT_VIDEO:
                        # For video, generate video directly
                        video_result = await self.generate_video(enhanced)

                        if video_result.get("success"):
                            generation_steps.append({
                                "step": 2,
                                "api": video_result["api"],
                                "action": "text_to_video",
                                "model": video_result.get("model"),
                                "input": {"prompt": enhanced},
                                "result_url": video_result["video_url"],
                                "cost": video_result["cost"],
                                "duration_ms": video_result["duration_ms"]
                            })
                            total_cost += video_result["cost"]

                            await self.save_material(
                                session=session,
                                tool_type=tool_type,
                                topic=topic,
                                prompt=prompt,
                                enhanced_prompt=enhanced,
                                generation_steps=generation_steps,
                                input_image_url=None,
                                result_image_url=None,
                                result_video_url=video_result["video_url"],
                                total_cost=total_cost
                            )
                            success_count += 1
                    else:
                        # For image tools, generate source image first
                        image_result = await self.generate_source_image(prompt, enhanced)

                        if not image_result.get("success"):
                            logger.warning(f"Failed to generate image: {image_result.get('error')}")
                            continue

                        source_image_url = image_result["image_url"]
                        total_cost += image_result["cost"]

                        generation_steps.append({
                            "step": 2,
                            "api": image_result["api"],
                            "action": "text_to_image",
                            "model": image_result.get("model"),
                            "input": {"prompt": enhanced},
                            "result_url": source_image_url,
                            "cost": image_result["cost"],
                            "duration_ms": image_result["duration_ms"]
                        })

                        # Step 3: Apply effect
                        result_image_url = source_image_url  # Default to source

                        effect_result = await self.apply_effect(tool_type, source_image_url)

                        if effect_result.get("success"):
                            result_image_url = effect_result["result_url"]
                            total_cost += effect_result["cost"]

                            generation_steps.append({
                                "step": 3,
                                "api": effect_result["api"],
                                "action": effect_result["action"],
                                "input": {"image_url": source_image_url},
                                "result_url": result_image_url,
                                "cost": effect_result["cost"],
                                "duration_ms": effect_result["duration_ms"]
                            })
                        elif not effect_result.get("skip"):
                            logger.warning(f"Effect failed: {effect_result.get('error')}")

                        # Step 4: Save material
                        await self.save_material(
                            session=session,
                            tool_type=tool_type,
                            topic=topic,
                            prompt=prompt,
                            enhanced_prompt=enhanced,
                            generation_steps=generation_steps,
                            input_image_url=source_image_url,
                            result_image_url=result_image_url,
                            result_video_url=None,
                            total_cost=total_cost
                        )
                        success_count += 1

                    # Rate limiting
                    await asyncio.sleep(2)

                except Exception as e:
                    logger.error(f"Error processing prompt: {e}")
                    self.stats["errors"].append(str(e))
                    continue

        return {
            "success": True,
            "count": success_count,
            "total_prompts": len(prompts)
        }

    async def pregenerate_avatars(
        self,
        languages: List[str] = None,
        topics: List[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Pre-generate AI Avatar videos for specified languages and topics.

        This creates language-specific avatar examples that are shown based on
        the user's selected UI language (zh-TW users see zh-TW avatars, etc.)

        Args:
            languages: Languages to generate for (default: ['en', 'zh-TW'])
            topics: Topics to generate (default: all avatar topics)
            dry_run: If True, only log what would be generated

        Returns:
            Dict with generation results
        """
        if languages is None:
            languages = ["en", "zh-TW"]

        if topics is None:
            topics = [t["topic_id"] for t in MATERIAL_TOPICS.get(ToolType.AI_AVATAR, [])]

        logger.info("=" * 60)
        logger.info(f"Pre-generating AI Avatar videos")
        logger.info(f"Languages: {languages}")
        logger.info(f"Topics: {topics}")
        logger.info("=" * 60)

        if dry_run:
            # Show what would be generated
            for lang in languages:
                lang_scripts = AVATAR_SCRIPTS.get(lang, {})
                for topic in topics:
                    topic_scripts = lang_scripts.get(topic, [])
                    logger.info(f"  Would generate {len(topic_scripts)} avatars for {lang}/{topic}")
            return {"success": True, "dry_run": True}

        # Ensure static directory exists
        STATIC_DIR.mkdir(parents=True, exist_ok=True)

        results = {}
        async with AsyncSessionLocal() as session:
            for lang in languages:
                lang_scripts = AVATAR_SCRIPTS.get(lang, {})
                results[lang] = {}

                for topic in topics:
                    topic_scripts = lang_scripts.get(topic, [])
                    success_count = 0

                    logger.info(f"\n[{lang}/{topic}] Generating {len(topic_scripts)} avatars...")

                    for i, script in enumerate(topic_scripts):
                        logger.info(f"  [{i+1}/{len(topic_scripts)}] {script[:50]}...")

                        try:
                            # Generate avatar video
                            avatar_result = await self.generate_avatar(
                                script=script,
                                language=lang,
                                topic=topic
                            )

                            if avatar_result.get("success"):
                                generation_steps = [{
                                    "step": 1,
                                    "api": "pollo-avatar",
                                    "action": "photo_to_avatar",
                                    "language": lang,
                                    "input": {"script": script},
                                    "result_url": avatar_result["video_url"],
                                    "cost": avatar_result["cost"],
                                    "duration_ms": avatar_result["duration_ms"]
                                }]

                                # Save material with language tag
                                await self.save_material(
                                    session=session,
                                    tool_type=ToolType.AI_AVATAR,
                                    topic=topic,
                                    prompt=script,
                                    enhanced_prompt=script,
                                    generation_steps=generation_steps,
                                    input_image_url=None,
                                    result_image_url=None,
                                    result_video_url=avatar_result["video_url"],
                                    total_cost=avatar_result["cost"],
                                    language=lang
                                )
                                success_count += 1
                            else:
                                logger.warning(f"  Avatar generation failed: {avatar_result.get('error')}")

                            # Rate limiting between avatar generations
                            await asyncio.sleep(3)

                        except Exception as e:
                            logger.error(f"  Error generating avatar: {e}")
                            self.stats["errors"].append(str(e))
                            continue

                    results[lang][topic] = {
                        "total": len(topic_scripts),
                        "success": success_count
                    }

        return {
            "success": True,
            "results": results,
            "stats": self.stats
        }

    async def pregenerate_all(
        self,
        count_per_topic: int = 30,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Pre-generate materials for all tools and topics.
        """
        results = {}

        for tool_type, topics in MATERIAL_TOPICS.items():
            for topic_config in topics:
                topic_id = topic_config["topic_id"]
                result = await self.pregenerate_for_tool_topic(
                    tool_type=tool_type,
                    topic=topic_id,
                    count=count_per_topic,
                    dry_run=dry_run
                )
                results[f"{tool_type.value}/{topic_id}"] = result

        return {
            "results": results,
            "stats": self.stats
        }


async def main():
    parser = argparse.ArgumentParser(description="Material System Pre-generation")
    parser.add_argument("--tool", type=str, help="Tool type (background_removal, product_scene, etc.)")
    parser.add_argument("--topic", type=str, help="Topic within the tool")
    parser.add_argument("--count", type=int, default=5, help="Number of materials to generate")
    parser.add_argument("--all", action="store_true", help="Generate for all tools/topics")
    parser.add_argument("--avatars", action="store_true", help="Generate AI Avatar examples for en and zh-TW")
    parser.add_argument("--avatar-lang", type=str, help="Specific language for avatars (en or zh-TW)")
    parser.add_argument("--dry-run", action="store_true", help="Only generate prompts, no images")
    parser.add_argument("--validate", action="store_true", help="Validate API keys only")

    args = parser.parse_args()

    generator = MaterialPreGenerator()

    # Validate APIs
    api_status = await generator.validate_apis()
    logger.info(f"API Status: {api_status}")

    if args.validate:
        return

    if args.avatars:
        # Generate AI Avatar examples
        languages = [args.avatar_lang] if args.avatar_lang else ["en", "zh-TW"]
        result = await generator.pregenerate_avatars(
            languages=languages,
            dry_run=args.dry_run
        )
    elif args.all:
        result = await generator.pregenerate_all(
            count_per_topic=args.count,
            dry_run=args.dry_run
        )
    elif args.tool and args.topic:
        try:
            tool_type = ToolType(args.tool)
        except ValueError:
            logger.error(f"Invalid tool type: {args.tool}")
            logger.info(f"Valid tools: {[t.value for t in ToolType]}")
            return

        result = await generator.pregenerate_for_tool_topic(
            tool_type=tool_type,
            topic=args.topic,
            count=args.count,
            dry_run=args.dry_run
        )
    else:
        parser.print_help()
        return

    logger.info("\n" + "=" * 60)
    logger.info("Pre-generation Complete")
    logger.info("=" * 60)
    logger.info(f"Stats: {generator.stats}")


if __name__ == "__main__":
    asyncio.run(main())
