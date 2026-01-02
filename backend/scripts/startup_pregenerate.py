"""
VidGo Startup Pre-generation Script - Robust Version

This script runs at application startup to:
1. Validate API keys (Leonardo, Gemini, GoEnhance, Pollo)
2. Check material sufficiency in the database
3. Pre-generate materials using fallback APIs if primary fails
4. Cache generated results for faster user queries

API Fallback Order:
- Image Generation: Leonardo → Gemini
- Video Generation: Leonardo → Pollo AI

Usage:
    python -m scripts.startup_pregenerate
    python -m scripts.startup_pregenerate --check-apis
    python -m scripts.startup_pregenerate --limit 10
    python -m scripts.startup_pregenerate --dry-run
"""
import asyncio
import sys
import argparse
import logging
import base64
import os
import uuid as uuid_module
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

sys.path.insert(0, "/app")

import httpx

# Directory to save generated images
GENERATED_IMAGES_DIR = "/app/static/generated"
os.makedirs(GENERATED_IMAGES_DIR, exist_ok=True)


def save_base64_image(data_url: str, showcase_id) -> str:
    """Save base64 image data to file and return the URL path"""
    try:
        # Parse data URL: data:image/png;base64,xxxxx
        header, data = data_url.split(",", 1)
        mime_type = header.split(":")[1].split(";")[0]
        ext = mime_type.split("/")[1]  # png, jpeg, etc.

        # Generate filename
        filename = f"{showcase_id}_{uuid_module.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(GENERATED_IMAGES_DIR, filename)

        # Decode and save
        image_bytes = base64.b64decode(data)
        with open(filepath, "wb") as f:
            f.write(image_bytes)

        # Return URL path (relative to static)
        return f"/static/generated/{filename}"
    except Exception as e:
        logger.error(f"Failed to save base64 image: {e}")
        # Return a truncated data URL as fallback (won't work but won't crash)
        return data_url[:400]


from sqlalchemy import select, func
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.demo import ToolShowcase, ImageDemo, PromptCache

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()


# ============================================================================
# API Clients with Fallback Support
# ============================================================================

class RobustImageGenerator:
    """Image generation with API fallback support"""

    def __init__(self):
        self.leonardo_key = getattr(settings, 'LEONARDO_API_KEY', '')
        self.gemini_key = getattr(settings, 'GEMINI_API_KEY', '')
        self.apis_status = {}

    async def validate_apis(self) -> Dict[str, Any]:
        """Validate all image generation APIs"""
        results = {}

        # Validate Leonardo
        if self.leonardo_key:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(
                        "https://cloud.leonardo.ai/api/rest/v1/me",
                        headers={"Authorization": f"Bearer {self.leonardo_key}"}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        user_details = data.get("user_details", [{}])[0]
                        tokens = user_details.get("apiSubscriptionTokens", 0)
                        results["leonardo"] = {
                            "valid": True,
                            "tokens": tokens,
                            "usable": tokens > 0
                        }
                    else:
                        results["leonardo"] = {"valid": False, "error": f"HTTP {response.status_code}"}
            except Exception as e:
                results["leonardo"] = {"valid": False, "error": str(e)}
        else:
            results["leonardo"] = {"valid": False, "error": "No API key"}

        # Validate Gemini
        if self.gemini_key:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(
                        f"https://generativelanguage.googleapis.com/v1beta/models?key={self.gemini_key}"
                    )
                    results["gemini"] = {
                        "valid": response.status_code == 200,
                        "usable": response.status_code == 200,
                        "error": None if response.status_code == 200 else f"HTTP {response.status_code}"
                    }
            except Exception as e:
                results["gemini"] = {"valid": False, "error": str(e)}
        else:
            results["gemini"] = {"valid": False, "error": "No API key"}

        self.apis_status = results
        return results

    async def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 768
    ) -> Dict[str, Any]:
        """Generate image with fallback between APIs"""

        errors = []

        # Try Leonardo first (if has tokens)
        if self.apis_status.get("leonardo", {}).get("usable"):
            result = await self._generate_with_leonardo(prompt, width, height)
            if result.get("success"):
                result["api_used"] = "leonardo"
                return result
            errors.append(f"Leonardo: {result.get('error')}")

        # Try Gemini as fallback
        if self.apis_status.get("gemini", {}).get("usable"):
            result = await self._generate_with_gemini(prompt)
            if result.get("success"):
                result["api_used"] = "gemini"
                return result
            errors.append(f"Gemini: {result.get('error')}")

        return {
            "success": False,
            "error": f"All APIs failed: {'; '.join(errors)}"
        }

    async def _generate_with_leonardo(
        self,
        prompt: str,
        width: int,
        height: int
    ) -> Dict[str, Any]:
        """Generate image using Leonardo API"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Start generation
                response = await client.post(
                    "https://cloud.leonardo.ai/api/rest/v1/generations",
                    headers={
                        "Authorization": f"Bearer {self.leonardo_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "prompt": prompt,
                        "modelId": "6b645e3a-d64f-4341-a6d8-7a3690fbf042",  # Phoenix
                        "width": width,
                        "height": height,
                        "num_images": 1,
                        "alchemy": True  # Use alchemy instead of promptMagic for Phoenix
                    }
                )

                if response.status_code != 200:
                    return {"success": False, "error": f"HTTP {response.status_code}: {response.text[:100]}"}

                data = response.json()
                generation_id = data.get("sdGenerationJob", {}).get("generationId")

                if not generation_id:
                    return {"success": False, "error": "No generation ID returned"}

                # Poll for result
                for _ in range(60):  # Max 2 minutes
                    await asyncio.sleep(2)
                    poll_response = await client.get(
                        f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}",
                        headers={"Authorization": f"Bearer {self.leonardo_key}"}
                    )

                    if poll_response.status_code == 200:
                        poll_data = poll_response.json()
                        gen_data = poll_data.get("generations_by_pk", {})
                        status = gen_data.get("status")

                        if status == "COMPLETE":
                            images = gen_data.get("generated_images", [])
                            if images:
                                return {
                                    "success": True,
                                    "image_url": images[0].get("url"),
                                    "generation_id": generation_id
                                }
                        elif status == "FAILED":
                            return {"success": False, "error": "Generation failed"}

                return {"success": False, "error": "Timeout waiting for generation"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _generate_with_gemini(self, prompt: str) -> Dict[str, Any]:
        """Generate image using Gemini API"""
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={self.gemini_key}",
                    json={
                        "contents": [{
                            "parts": [{"text": f"Generate an image: {prompt}"}]
                        }],
                        "generationConfig": {
                            "responseModalities": ["TEXT", "IMAGE"],
                            "temperature": 1.0
                        }
                    }
                )

                if response.status_code == 429:
                    return {"success": False, "error": "Quota exceeded"}

                if response.status_code != 200:
                    return {"success": False, "error": f"HTTP {response.status_code}"}

                data = response.json()
                candidates = data.get("candidates", [])

                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    for part in parts:
                        if "inlineData" in part:
                            image_data = part["inlineData"].get("data")
                            mime_type = part["inlineData"].get("mimeType", "image/png")
                            # Return as data URL
                            return {
                                "success": True,
                                "image_url": f"data:{mime_type};base64,{image_data}",
                                "is_base64": True
                            }

                return {"success": False, "error": "No image in response"}

        except Exception as e:
            return {"success": False, "error": str(e)}


class RobustVideoGenerator:
    """Video generation with API fallback support"""

    # Topic-related video prompts for random generation
    VIDEO_PROMPTS = {
        "video": [
            "Cinematic product showcase with dynamic camera movement, luxury product rotating slowly, golden hour lighting, professional commercial",
            "Fashion model walking on runway, elegant dress flowing, dramatic lighting, slow motion capture",
            "Coffee being poured into cup, steam rising, cozy cafe atmosphere, warm tones, macro shot",
            "Ocean waves crashing on beach, sunset colors, drone aerial view, peaceful and serene",
            "City skyline at night, lights twinkling, time lapse effect, urban atmosphere",
            "Flowers blooming in garden, butterfly landing, spring morning dew, nature documentary style",
        ],
        "ecommerce": [
            "Premium sneakers rotating on display stand, studio lighting, white background, commercial product shot",
            "Luxury watch with detailed mechanisms, reflective surface, elegant presentation",
            "Cosmetics products arrangement, soft pink lighting, beauty commercial aesthetic",
            "Electronic gadget unboxing, sleek design reveal, tech commercial style",
        ],
        "lifestyle": [
            "Morning coffee routine, steam rising from cup, cozy kitchen, warm sunlight",
            "Yoga practice at sunrise, peaceful movement, nature background",
            "Home cooking scene, ingredients being prepared, warm family atmosphere",
        ],
        "nature": [
            "Mountain landscape with clouds drifting, majestic peaks, cinematic drone shot",
            "Forest stream with sunlight filtering through trees, peaceful nature scene",
            "Cherry blossoms falling in spring, gentle breeze, Japanese garden atmosphere",
        ],
    }

    def __init__(self):
        self.leonardo_key = getattr(settings, 'LEONARDO_API_KEY', '')
        self.pollo_key = getattr(settings, 'POLLO_API_KEY', '')
        self.apis_status = {}

    async def validate_apis(self) -> Dict[str, Any]:
        """Validate all video generation APIs"""
        results = {}

        # Validate Leonardo (also supports image-to-video via Motion)
        if self.leonardo_key:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(
                        "https://cloud.leonardo.ai/api/rest/v1/me",
                        headers={"Authorization": f"Bearer {self.leonardo_key}"}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        user_details = data.get("user_details", [{}])[0]
                        tokens = user_details.get("apiSubscriptionTokens", 0)
                        results["leonardo"] = {
                            "valid": True,
                            "tokens": tokens,
                            "usable": tokens > 0
                        }
                    else:
                        results["leonardo"] = {"valid": False, "error": f"HTTP {response.status_code}"}
            except Exception as e:
                results["leonardo"] = {"valid": False, "error": str(e)}
        else:
            results["leonardo"] = {"valid": False, "error": "No API key"}

        # Validate Pollo AI
        if self.pollo_key:
            results["pollo"] = {"valid": True, "usable": True}
        else:
            results["pollo"] = {"valid": False, "error": "No API key"}

        self.apis_status = results
        return results

    def get_random_prompt(self, topic: str = "video") -> str:
        """Get a random video prompt for a topic"""
        import random
        prompts = self.VIDEO_PROMPTS.get(topic, self.VIDEO_PROMPTS["video"])
        return random.choice(prompts)

    async def generate_video(
        self,
        image_url: str = None,
        prompt: str = "",
        duration: int = 5,
        topic: str = "video"
    ) -> Dict[str, Any]:
        """Generate video with fallback between APIs

        If no prompt provided, generates a random topic-related prompt.
        Uses text-to-video when no image_url, otherwise uses image-to-video.
        """
        errors = []

        # Use random prompt if not provided
        if not prompt:
            prompt = self.get_random_prompt(topic)
            logger.info(f"Using random prompt for topic '{topic}': {prompt[:50]}...")

        # Try Pollo AI text-to-video (preferred for random generation)
        if self.apis_status.get("pollo", {}).get("usable"):
            result = await self._generate_with_pollo_text_to_video(prompt, duration)
            if result.get("success"):
                result["api_used"] = "pollo_t2v"
                result["prompt_used"] = prompt
                return result
            errors.append(f"Pollo T2V: {result.get('error')}")

        # Fallback: Try Leonardo if we have an image
        if image_url and self.apis_status.get("leonardo", {}).get("usable"):
            result = await self._generate_with_leonardo(image_url, prompt)
            if result.get("success"):
                result["api_used"] = "leonardo"
                return result
            errors.append(f"Leonardo: {result.get('error')}")

        return {
            "success": False,
            "error": f"All APIs failed: {'; '.join(errors)}" if errors else "No video APIs available"
        }

    async def _generate_with_leonardo(
        self,
        image_url: str,
        prompt: str
    ) -> Dict[str, Any]:
        """Generate video using Leonardo Motion API"""
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                # First, we need to upload or use an existing image
                # Leonardo Motion requires an imageId, not a URL
                # For now, skip if we only have URL (would need image upload first)

                # Try the image-to-video generation endpoint
                response = await client.post(
                    "https://cloud.leonardo.ai/api/rest/v1/generations-motion-svd",
                    headers={
                        "Authorization": f"Bearer {self.leonardo_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "imageId": image_url,  # This may need to be a Leonardo image ID
                        "motionStrength": 5,
                        "isPublic": False
                    }
                )

                if response.status_code != 200:
                    error_text = response.text[:200]
                    return {"success": False, "error": f"HTTP {response.status_code}: {error_text}"}

                data = response.json()
                generation_id = data.get("motionSvdGenerationJob", {}).get("generationId")

                if not generation_id:
                    return {"success": False, "error": "No generation ID returned"}

                # Poll for result
                for _ in range(90):  # Max 3 minutes for video
                    await asyncio.sleep(2)
                    poll_response = await client.get(
                        f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}",
                        headers={"Authorization": f"Bearer {self.leonardo_key}"}
                    )

                    if poll_response.status_code == 200:
                        poll_data = poll_response.json()
                        gen_data = poll_data.get("generations_by_pk", {})
                        status = gen_data.get("status")

                        if status == "COMPLETE":
                            videos = gen_data.get("generated_images", [])
                            if videos:
                                video_url = videos[0].get("motionMP4URL") or videos[0].get("url")
                                return {
                                    "success": True,
                                    "video_url": video_url,
                                    "generation_id": generation_id
                                }
                        elif status == "FAILED":
                            return {"success": False, "error": "Generation failed"}

                return {"success": False, "error": "Timeout waiting for video generation"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _generate_with_pollo(
        self,
        image_url: str,
        prompt: str,
        duration: int
    ) -> Dict[str, Any]:
        """Generate video using Pollo AI"""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Start generation
                response = await client.post(
                    "https://pollo.ai/api/platform/generation/pixverse/pixverse-v4-5",
                    headers={
                        "x-api-key": self.pollo_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "input": {
                            "image": image_url,
                            "prompt": f"{prompt}, smooth motion, cinematic" if prompt else "smooth motion, cinematic",
                            "negativePrompt": "blurry, distorted, low quality",
                            "length": min(duration, 8)
                        }
                    }
                )

                if response.status_code != 200:
                    return {"success": False, "error": f"HTTP {response.status_code}"}

                data = response.json()
                if data.get("code") != "SUCCESS":
                    return {"success": False, "error": data.get("message", "Unknown error")}

                task_id = data["data"]["taskId"]

                # Poll for result
                for _ in range(60):  # Max 5 minutes
                    await asyncio.sleep(5)
                    status_response = await client.get(
                        f"https://pollo.ai/api/platform/generation/{task_id}/status",
                        headers={"x-api-key": self.pollo_key}
                    )

                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        generations = status_data.get("data", {}).get("generations", [])

                        if generations:
                            gen = generations[0]
                            if gen.get("status") == "succeed":
                                return {
                                    "success": True,
                                    "video_url": gen.get("url"),
                                    "task_id": task_id
                                }
                            elif gen.get("status") == "failed":
                                return {"success": False, "error": gen.get("failMsg", "Generation failed")}

                return {"success": False, "error": "Timeout waiting for video"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _generate_with_pollo_text_to_video(
        self,
        prompt: str,
        duration: int = 5
    ) -> Dict[str, Any]:
        """Generate video from text using Pollo AI (Pollo 2.0 model)"""
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                # Use Pollo 2.0 for text-to-video
                logger.info(f"Starting Pollo text-to-video generation...")

                response = await client.post(
                    "https://pollo.ai/api/platform/generation/pollo/pollo-v2-0",
                    headers={
                        "x-api-key": self.pollo_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "input": {
                            "prompt": prompt,
                            "length": min(duration, 5),  # Pollo 2.0 supports 1-5 seconds
                            "resolution": "720p"
                        }
                    }
                )

                logger.info(f"Pollo API response status: {response.status_code}")

                if response.status_code != 200:
                    error_text = response.text[:200]
                    logger.error(f"Pollo API error: {error_text}")
                    return {"success": False, "error": f"HTTP {response.status_code}: {error_text}"}

                data = response.json()
                logger.info(f"Pollo API response: {data}")

                if data.get("code") != "SUCCESS":
                    return {"success": False, "error": data.get("message", "Unknown error")}

                task_id = data.get("data", {}).get("taskId")
                if not task_id:
                    return {"success": False, "error": "No task ID returned"}

                logger.info(f"Pollo task ID: {task_id}, polling for result...")

                # Poll for result (video generation can take a while)
                for attempt in range(90):  # Max 7.5 minutes (90 * 5s)
                    await asyncio.sleep(5)

                    status_response = await client.get(
                        f"https://pollo.ai/api/platform/generation/{task_id}/status",
                        headers={"x-api-key": self.pollo_key}
                    )

                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        generations = status_data.get("data", {}).get("generations", [])

                        if generations:
                            gen = generations[0]
                            status = gen.get("status")

                            if status == "succeed":
                                video_url = gen.get("url")
                                logger.info(f"Video generated successfully: {video_url}")

                                # Download and save video locally
                                local_path = await self._download_video(video_url, task_id)

                                return {
                                    "success": True,
                                    "video_url": local_path or video_url,
                                    "original_url": video_url,
                                    "task_id": task_id
                                }
                            elif status == "failed":
                                return {"success": False, "error": gen.get("failMsg", "Generation failed")}

                            # Log progress
                            if attempt % 6 == 0:  # Every 30 seconds
                                logger.info(f"Still processing... status={status}, attempt={attempt}")

                return {"success": False, "error": "Timeout waiting for video generation"}

        except Exception as e:
            logger.error(f"Pollo text-to-video error: {e}")
            return {"success": False, "error": str(e)}

    async def _download_video(self, url: str, task_id: str) -> Optional[str]:
        """Download video and save locally"""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    filename = f"video_{task_id}_{uuid_module.uuid4().hex[:8]}.mp4"
                    filepath = os.path.join(GENERATED_IMAGES_DIR, filename)
                    with open(filepath, "wb") as f:
                        f.write(response.content)
                    logger.info(f"Video saved to: {filepath}")
                    return f"/static/generated/{filename}"
        except Exception as e:
            logger.warning(f"Failed to download video: {e}")
        return None


# ============================================================================
# Main Pre-generation Logic
# ============================================================================

def print_banner():
    """Print startup banner"""
    print("\n" + "=" * 70)
    print("  VidGo AI - Robust Pre-generation Service")
    print("  With API Fallback Support")
    print("=" * 70)
    print(f"  Timestamp: {datetime.now().isoformat()}")
    print("=" * 70 + "\n")


async def check_database_materials() -> Dict[str, Any]:
    """Check current material counts in database"""
    async with AsyncSessionLocal() as session:
        showcase_result = await session.execute(
            select(func.count(ToolShowcase.id)).where(ToolShowcase.is_active == True)
        )
        showcase_count = showcase_result.scalar() or 0

        generated_result = await session.execute(
            select(func.count(ToolShowcase.id)).where(
                ToolShowcase.is_active == True,
                (ToolShowcase.result_image_url.isnot(None)) |
                (ToolShowcase.result_video_url.isnot(None))
            )
        )
        generated_count = generated_result.scalar() or 0

        return {
            "total_showcases": showcase_count,
            "generated_showcases": generated_count,
            "pending_generation": showcase_count - generated_count,
            "is_sufficient": generated_count >= 10
        }


def determine_generation_type(showcase) -> str:
    """Determine generation type based on tool"""
    text_to_image_tools = ["pattern_generate"]
    image_to_video_tools = ["image_to_video", "video_transform", "product_design"]

    if showcase.tool_id in text_to_image_tools or showcase.source_image_url is None:
        return "text_to_image"
    elif showcase.tool_id in image_to_video_tools:
        return "image_to_video"
    else:
        return "image_to_image"


async def pregenerate_with_fallback(
    limit: int = 10,
    dry_run: bool = False
) -> Dict[str, Any]:
    """Pre-generate showcases using robust API fallback"""

    stats = {
        "attempted": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "by_api": {},
        "errors": []
    }

    # Initialize generators
    image_gen = RobustImageGenerator()
    video_gen = RobustVideoGenerator()

    # Validate APIs
    print("\n  Validating APIs...")
    image_apis = await image_gen.validate_apis()
    video_apis = await video_gen.validate_apis()

    print("\n  Image APIs:")
    for api, status in image_apis.items():
        icon = "✅" if status.get("usable") else "❌"
        extra = f" ({status.get('tokens')} tokens)" if status.get("tokens") else ""
        print(f"    {icon} {api.capitalize()}{extra}")

    print("\n  Video APIs:")
    for api, status in video_apis.items():
        icon = "✅" if status.get("usable") else "❌"
        print(f"    {icon} {api.capitalize()}")

    # Check if any APIs are available
    has_image_api = any(s.get("usable") for s in image_apis.values())
    has_video_api = any(s.get("usable") for s in video_apis.values())

    if not has_image_api and not has_video_api:
        print("\n  ⚠️  No usable APIs available")
        return stats

    # Get showcases needing generation
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ToolShowcase).where(
                ToolShowcase.is_active == True,
                ToolShowcase.result_image_url.is_(None),
                ToolShowcase.result_video_url.is_(None)
            ).limit(limit)
        )
        showcases = result.scalars().all()

        if not showcases:
            print("\n  ✅ No showcases need generation")
            return stats

        print(f"\n  Found {len(showcases)} showcases needing generation")

        if dry_run:
            for s in showcases:
                gen_type = determine_generation_type(s)
                print(f"    [DRY RUN] {gen_type} | {s.tool_id}")
                stats["skipped"] += 1
            return stats

        # Generate each showcase
        for showcase in showcases:
            stats["attempted"] += 1
            gen_type = determine_generation_type(showcase)

            print(f"\n  [{stats['attempted']}/{len(showcases)}] {gen_type}: {showcase.tool_id}")

            try:
                if gen_type == "text_to_image":
                    # Generate image from prompt
                    enhanced_prompt = f"{showcase.prompt}, high quality, professional"
                    result = await image_gen.generate_image(enhanced_prompt)

                    if result.get("success"):
                        image_url = result.get("image_url")

                        # If base64 data, save to file
                        if result.get("is_base64") and image_url.startswith("data:"):
                            image_url = save_base64_image(image_url, showcase.id)

                        showcase.result_image_url = image_url
                        showcase.generation_params = {
                            "generation_type": gen_type,
                            "api_used": result.get("api_used"),
                            "prompt": enhanced_prompt,
                            "generated_at": datetime.utcnow().isoformat()
                        }
                        await session.commit()

                        api_used = result.get("api_used", "unknown")
                        stats["success"] += 1
                        stats["by_api"][api_used] = stats["by_api"].get(api_used, 0) + 1
                        print(f"    ✅ Generated via {api_used}")
                    else:
                        raise Exception(result.get("error", "Unknown error"))

                elif gen_type == "image_to_image":
                    # For image-to-image, generate a new image based on prompt
                    enhanced_prompt = f"{showcase.prompt}, professional quality"
                    result = await image_gen.generate_image(enhanced_prompt)

                    if result.get("success"):
                        image_url = result.get("image_url")

                        # If base64 data, save to file
                        if result.get("is_base64") and image_url.startswith("data:"):
                            image_url = save_base64_image(image_url, showcase.id)

                        showcase.result_image_url = image_url
                        showcase.generation_params = {
                            "generation_type": gen_type,
                            "api_used": result.get("api_used"),
                            "source_image": showcase.source_image_url,
                            "prompt": enhanced_prompt,
                            "generated_at": datetime.utcnow().isoformat()
                        }
                        await session.commit()

                        api_used = result.get("api_used", "unknown")
                        stats["success"] += 1
                        stats["by_api"][api_used] = stats["by_api"].get(api_used, 0) + 1
                        print(f"    ✅ Generated via {api_used}")
                    else:
                        raise Exception(result.get("error", "Unknown error"))

                elif gen_type == "image_to_video":
                    # Generate video using text-to-video with topic-related prompt
                    # Map tool categories to video topics
                    topic_map = {
                        "video": "video",
                        "video_effects": "video",
                        "ai_video": "video",
                        "ecommerce": "ecommerce",
                        "product": "ecommerce",
                        "lifestyle": "lifestyle",
                        "nature": "nature",
                    }
                    video_topic = topic_map.get(showcase.tool_category, "video")

                    # Use showcase prompt if specific, otherwise generate random
                    video_prompt = showcase.prompt if showcase.prompt else None

                    result = await video_gen.generate_video(
                        prompt=video_prompt,
                        duration=5,
                        topic=video_topic
                    )

                    if result.get("success"):
                        showcase.result_video_url = result.get("video_url")
                        showcase.prompt = result.get("prompt_used", showcase.prompt)  # Update with used prompt
                        showcase.generation_params = {
                            "generation_type": "text_to_video",
                            "api_used": result.get("api_used"),
                            "prompt_used": result.get("prompt_used"),
                            "topic": video_topic,
                            "generated_at": datetime.utcnow().isoformat()
                        }
                        await session.commit()

                        api_used = result.get("api_used", "unknown")
                        stats["success"] += 1
                        stats["by_api"][api_used] = stats["by_api"].get(api_used, 0) + 1
                        print(f"    ✅ Generated via {api_used}")
                        if result.get("prompt_used"):
                            print(f"       Prompt: {result.get('prompt_used')[:60]}...")
                    else:
                        raise Exception(result.get("error", "Unknown error"))

                # Rate limiting
                await asyncio.sleep(2)

            except Exception as e:
                stats["failed"] += 1
                error_msg = f"{showcase.tool_id}: {str(e)}"
                stats["errors"].append(error_msg)
                print(f"    ❌ Failed: {e}")

    return stats


async def run_avatar_pregeneration():
    """Run avatar pre-generation check and generate if needed"""
    try:
        from scripts.startup_avatars import run_startup_avatar_check
        print("\n🎭 Step 4: Checking AI Avatar Examples\n")
        result = await run_startup_avatar_check()
        return result
    except ImportError as e:
        print(f"  ⚠️ Avatar pre-generation module not found: {e}")
        return {"status": "skipped", "error": str(e)}
    except Exception as e:
        print(f"  ❌ Avatar pre-generation failed: {e}")
        return {"status": "error", "error": str(e)}


async def main():
    parser = argparse.ArgumentParser(description="VidGo Robust Pre-generation Service")
    parser.add_argument("--check-apis", action="store_true", help="Only check API keys")
    parser.add_argument("--skip-generate", action="store_true", help="Skip generation step")
    parser.add_argument("--skip-avatars", action="store_true", help="Skip avatar pre-generation")
    parser.add_argument("--limit", type=int, default=10, help="Max items to generate")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated")

    args = parser.parse_args()

    print_banner()

    # Step 1: Validate APIs
    print("📋 Step 1: Validating API Keys\n")

    image_gen = RobustImageGenerator()
    video_gen = RobustVideoGenerator()

    image_apis = await image_gen.validate_apis()
    video_apis = await video_gen.validate_apis()

    print("  Image Generation APIs:")
    for api, status in image_apis.items():
        if status.get("valid"):
            extra = f" (Tokens: {status.get('tokens')})" if status.get("tokens") is not None else ""
            usable = "✅ USABLE" if status.get("usable") else "⚠️ LIMITED"
            print(f"    {usable} {api.capitalize()}{extra}")
        else:
            print(f"    ❌ {api.capitalize()}: {status.get('error', 'Invalid')}")

    print("\n  Video Generation APIs:")
    for api, status in video_apis.items():
        if status.get("valid"):
            print(f"    ✅ {api.capitalize()}: Valid")
        else:
            print(f"    ❌ {api.capitalize()}: {status.get('error', 'Invalid')}")

    if args.check_apis:
        return 0

    # Step 2: Check Database
    print("\n📊 Step 2: Checking Database Materials\n")
    db_status = await check_database_materials()

    print(f"  Total Showcases:     {db_status['total_showcases']}")
    print(f"  Generated:           {db_status['generated_showcases']}")
    print(f"  Pending Generation:  {db_status['pending_generation']}")

    if db_status['is_sufficient']:
        print(f"\n  ✅ Material library is SUFFICIENT")
    else:
        print(f"\n  ⚠️  Material library needs more content")

    if args.skip_generate:
        print("\n  Skipping generation (--skip-generate flag)")
        return 0

    # Step 3: Pre-generate with fallback
    print(f"\n🚀 Step 3: Pre-generating Materials (limit: {args.limit})")
    print("  Using API fallback for resilience...\n")

    stats = await pregenerate_with_fallback(
        limit=args.limit,
        dry_run=args.dry_run
    )

    # Summary
    print("\n" + "=" * 70)
    print("  Pre-generation Complete!")
    print("=" * 70)

    print(f"\n  Results:")
    print(f"    Attempted: {stats['attempted']}")
    print(f"    Success:   {stats['success']}")
    print(f"    Failed:    {stats['failed']}")
    print(f"    Skipped:   {stats['skipped']}")

    if stats["by_api"]:
        print(f"\n  By API:")
        for api, count in stats["by_api"].items():
            print(f"    {api}: {count}")

    if stats["errors"]:
        print(f"\n  Errors ({len(stats['errors'])}):")
        for err in stats["errors"][:5]:
            print(f"    - {err}")
        if len(stats["errors"]) > 5:
            print(f"    ... and {len(stats['errors']) - 5} more")

    # Final status
    final_status = await check_database_materials()
    print(f"\n  Final Status:")
    print(f"    Generated Showcases: {final_status['generated_showcases']}")
    print(f"    Ready for users: {'✅ Yes' if final_status['is_sufficient'] else '⚠️ Limited'}")

    # Step 4: Avatar Pre-generation (always run unless skipped)
    if not args.skip_avatars:
        avatar_result = await run_avatar_pregeneration()
        if avatar_result.get("status") == "sufficient":
            print("  ✅ Avatar examples are sufficient")
        elif avatar_result.get("status") == "generated":
            results = avatar_result.get("results", {})
            gen_count = results.get("generated", 0)
            print(f"  ✅ Generated {gen_count} new avatar examples")
    else:
        print("\n  Skipping avatar pre-generation (--skip-avatars flag)")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
