"""
Leonardo AI API Client
Image generation and Image-to-Video transformation.
API Docs: https://docs.leonardo.ai/
"""
import asyncio
import logging
from typing import Optional, Dict, Any, Tuple
import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# Available Leonardo models for different use cases
LEONARDO_MODELS = {
    # Image generation models
    "phoenix": {
        "id": "6b645e3a-d64f-4341-a6d8-7a3690fbf042",
        "name": "Leonardo Phoenix",
        "description": "Best quality, creative images"
    },
    "kino_xl": {
        "id": "aa77f04e-3eec-4034-9c07-d0f619684628",
        "name": "Leonardo Kino XL",
        "description": "Cinematic, high-quality images"
    },
    "lightning_xl": {
        "id": "b24e16ff-06e3-43eb-8d33-4416c2d75876",
        "name": "Leonardo Lightning XL",
        "description": "Fast generation, good quality"
    },
    "diffusion_xl": {
        "id": "1e60896f-3c26-4296-8ecc-53e2afecc132",
        "name": "Leonardo Diffusion XL",
        "description": "Balanced quality and speed"
    },
    # Video generation model
    "motion": {
        "id": "motion",
        "name": "Leonardo Motion",
        "description": "Image-to-Video generation"
    }
}


class LeonardoClient:
    """
    Leonardo AI API Client

    Supports:
    - Text-to-Image generation
    - Image-to-Video generation (Motion)
    """

    BASE_URL = "https://cloud.leonardo.ai/api/rest/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'LEONARDO_API_KEY', '')
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    # =========================================================================
    # Text-to-Image Generation
    # =========================================================================

    async def generate_image(
        self,
        prompt: str,
        model: str = "phoenix",
        width: int = 1024,
        height: int = 768,
        num_images: int = 1,
        negative_prompt: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Generate image from text prompt.

        Args:
            prompt: Text description of the image
            model: Model key from LEONARDO_MODELS
            width: Image width (default 1024)
            height: Image height (default 768)
            num_images: Number of images to generate
            negative_prompt: What to avoid in the image

        Returns:
            Tuple of (success, generation_id or error, None)
        """
        if not self.api_key:
            return False, "Leonardo API key not configured", None

        model_info = LEONARDO_MODELS.get(model, LEONARDO_MODELS["phoenix"])
        model_id = model_info["id"]

        payload = {
            "prompt": prompt,
            "modelId": model_id,
            "width": width,
            "height": height,
            "num_images": num_images,
            "alchemy": True
        }

        # PhotoReal is not compatible with Phoenix model
        if model != "phoenix":
            payload["photoReal"] = True
            payload["photoRealVersion"] = "v2"

        if negative_prompt:
            payload["negative_prompt"] = negative_prompt

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/generations",
                    headers=self.headers,
                    json=payload
                )

                if response.status_code == 200:
                    data = response.json()
                    generation_id = data.get("sdGenerationJob", {}).get("generationId")
                    if generation_id:
                        logger.info(f"Leonardo image generation started: {generation_id}")
                        return True, generation_id, None
                    else:
                        return False, "No generation ID returned", None
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"Leonardo image generation failed: {error_msg}")
                    return False, error_msg, None

        except Exception as e:
            logger.error(f"Leonardo image generation error: {e}")
            return False, str(e), None

    async def get_generation_result(self, generation_id: str) -> Dict[str, Any]:
        """
        Get image generation result.

        Returns:
            Dict with status, images when complete
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/generations/{generation_id}",
                    headers=self.headers
                )

                if response.status_code == 200:
                    data = response.json()
                    generations = data.get("generations_by_pk", {})
                    status = generations.get("status", "PENDING")
                    images = generations.get("generated_images", [])

                    image_urls = [img.get("url") for img in images if img.get("url")]
                    image_ids = [img.get("id") for img in images if img.get("id")]

                    return {
                        "success": True,
                        "status": status,
                        "images": image_urls,
                        "image_url": image_urls[0] if image_urls else None,
                        "image_id": image_ids[0] if image_ids else None,
                        "raw": data
                    }
                else:
                    return {
                        "success": False,
                        "status": "error",
                        "error": f"HTTP {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"Get generation result error: {e}")
            return {"success": False, "status": "error", "error": str(e)}

    async def generate_image_and_wait(
        self,
        prompt: str,
        model: str = "phoenix",
        width: int = 1024,
        height: int = 768,
        timeout: int = 120,
        poll_interval: int = 3
    ) -> Dict[str, Any]:
        """
        Generate image and wait for completion.

        Returns:
            Dict with image_url on success
        """
        success, generation_id, _ = await self.generate_image(
            prompt=prompt,
            model=model,
            width=width,
            height=height
        )

        if not success:
            return {"success": False, "error": generation_id}

        elapsed = 0
        while elapsed < timeout:
            result = await self.get_generation_result(generation_id)
            status = result.get("status", "").upper()

            if status == "COMPLETE":
                return {
                    "success": True,
                    "generation_id": generation_id,
                    "image_url": result.get("image_url"),
                    "image_id": result.get("image_id"),
                    "images": result.get("images", []),
                    "prompt": prompt,
                    "model": model
                }
            elif status == "FAILED":
                return {
                    "success": False,
                    "generation_id": generation_id,
                    "error": "Image generation failed"
                }

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        return {"success": False, "generation_id": generation_id, "error": "Image generation timed out"}

    # =========================================================================
    # Image-to-Video Generation (Motion)
    # =========================================================================

    async def generate_video(
        self,
        image_id: str,
        motion_strength: int = 5,
        is_public: bool = False
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Generate video from an existing Leonardo image.

        Args:
            image_id: ID of the source image (from Leonardo generation)
            motion_strength: Motion intensity (1-10)
            is_public: Whether the video is public

        Returns:
            Tuple of (success, generation_id or error, None)
        """
        if not self.api_key:
            return False, "Leonardo API key not configured", None

        payload = {
            "imageId": image_id,
            "motionStrength": motion_strength,
            "isPublic": is_public
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/generations-motion-svd",
                    headers=self.headers,
                    json=payload
                )

                if response.status_code == 200:
                    data = response.json()
                    generation_id = data.get("motionSvdGenerationJob", {}).get("generationId")
                    if generation_id:
                        logger.info(f"Leonardo motion generation started: {generation_id}")
                        return True, generation_id, None
                    else:
                        return False, "No generation ID returned", None
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"Leonardo motion generation failed: {error_msg}")
                    return False, error_msg, None

        except Exception as e:
            logger.error(f"Leonardo motion generation error: {e}")
            return False, str(e), None

    async def generate_video_from_url(
        self,
        image_url: str,
        motion_strength: int = 5
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Generate video from an external image URL.
        First uploads the image, then generates motion.

        Args:
            image_url: URL of the source image
            motion_strength: Motion intensity (1-10)

        Returns:
            Tuple of (success, generation_id or error, None)
        """
        if not self.api_key:
            return False, "Leonardo API key not configured", None

        payload = {
            "imageUrl": image_url,
            "motionStrength": motion_strength,
            "isPublic": False
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/generations-motion-svd",
                    headers=self.headers,
                    json=payload
                )

                if response.status_code == 200:
                    data = response.json()
                    generation_id = data.get("motionSvdGenerationJob", {}).get("generationId")
                    if generation_id:
                        logger.info(f"Leonardo motion generation started: {generation_id}")
                        return True, generation_id, None
                    else:
                        return False, "No generation ID returned", None
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"Leonardo motion generation failed: {error_msg}")
                    return False, error_msg, None

        except Exception as e:
            logger.error(f"Leonardo motion generation error: {e}")
            return False, str(e), None

    async def get_motion_result(self, generation_id: str) -> Dict[str, Any]:
        """
        Get motion/video generation result.

        Returns:
            Dict with status, video_url when complete
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/generations/{generation_id}",
                    headers=self.headers
                )

                if response.status_code == 200:
                    data = response.json()
                    generations = data.get("generations_by_pk", {})
                    status = generations.get("status", "PENDING")

                    # Get generated images which may contain motion video
                    images = generations.get("generated_images", [])
                    video_url = None
                    image_url = None

                    for img in images:
                        if img.get("motionMP4URL"):
                            video_url = img.get("motionMP4URL")
                        if img.get("url"):
                            image_url = img.get("url")

                    return {
                        "success": True,
                        "status": status,
                        "video_url": video_url,
                        "image_url": image_url,
                        "raw": data
                    }
                else:
                    return {
                        "success": False,
                        "status": "error",
                        "error": f"HTTP {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"Get motion result error: {e}")
            return {"success": False, "status": "error", "error": str(e)}

    async def generate_video_and_wait(
        self,
        image_url: str,
        motion_strength: int = 5,
        timeout: int = 300,
        poll_interval: int = 5
    ) -> Dict[str, Any]:
        """
        Generate video from image URL and wait for completion.

        Args:
            image_url: Source image URL
            motion_strength: Motion intensity (1-10)
            timeout: Max wait time in seconds
            poll_interval: Seconds between status checks

        Returns:
            Dict with video_url on success
        """
        success, generation_id, _ = await self.generate_video_from_url(
            image_url=image_url,
            motion_strength=motion_strength
        )

        if not success:
            return {"success": False, "error": generation_id}

        elapsed = 0
        while elapsed < timeout:
            result = await self.get_motion_result(generation_id)
            status = result.get("status", "").upper()

            if status == "COMPLETE":
                return {
                    "success": True,
                    "generation_id": generation_id,
                    "video_url": result.get("video_url"),
                    "image_url": result.get("image_url"),
                    "motion_strength": motion_strength
                }
            elif status == "FAILED":
                return {
                    "success": False,
                    "generation_id": generation_id,
                    "error": "Video generation failed"
                }

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        return {"success": False, "generation_id": generation_id, "error": "Video generation timed out"}

    async def generate_video_with_id_and_wait(
        self,
        image_id: str,
        motion_strength: int = 5,
        timeout: int = 300,
        poll_interval: int = 5
    ) -> Dict[str, Any]:
        """
        Generate video from image ID and wait for completion.

        Args:
            image_id: Leonardo image ID
            motion_strength: Motion intensity (1-10)
            timeout: Max wait time in seconds
            poll_interval: Seconds between status checks

        Returns:
            Dict with video_url on success
        """
        success, generation_id, _ = await self.generate_video(
            image_id=image_id,
            motion_strength=motion_strength
        )

        if not success:
            return {"success": False, "error": generation_id}

        elapsed = 0
        while elapsed < timeout:
            result = await self.get_motion_result(generation_id)
            status = result.get("status", "").upper()

            if status == "COMPLETE":
                return {
                    "success": True,
                    "generation_id": generation_id,
                    "video_url": result.get("video_url"),
                    "image_url": result.get("image_url"),
                    "motion_strength": motion_strength
                }
            elif status == "FAILED":
                return {
                    "success": False,
                    "generation_id": generation_id,
                    "error": "Video generation failed"
                }

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        return {"success": False, "generation_id": generation_id, "error": "Video generation timed out"}

    # =========================================================================
    # Full Pipeline: Text -> Image -> Video
    # =========================================================================

    async def generate_product_video(
        self,
        prompt: str,
        model: str = "phoenix",
        motion_strength: int = 5,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """
        Full pipeline: Generate image from prompt, then create video.

        Args:
            prompt: Text description for the product image
            model: Image generation model
            motion_strength: Motion intensity for video
            timeout: Max wait time for each step

        Returns:
            Dict with image_url and video_url on success
        """
        # Step 1: Generate image
        logger.info(f"Step 1: Generating image for prompt: {prompt}")
        image_result = await self.generate_image_and_wait(
            prompt=prompt,
            model=model,
            timeout=timeout
        )

        if not image_result.get("success"):
            return {
                "success": False,
                "step": "image_generation",
                "error": image_result.get("error", "Image generation failed")
            }

        image_url = image_result.get("image_url")
        image_id = image_result.get("image_id")
        logger.info(f"Image generated: {image_url} (ID: {image_id})")

        # Step 2: Generate video from image using image_id
        if not image_id:
            return {
                "success": True,
                "step": "video_generation_skipped",
                "image_url": image_url,
                "video_url": None,
                "error": "No image ID available for video generation"
            }

        logger.info(f"Step 2: Generating video from image ID: {image_id}")
        video_result = await self.generate_video_with_id_and_wait(
            image_id=image_id,
            motion_strength=motion_strength,
            timeout=timeout
        )

        if not video_result.get("success"):
            return {
                "success": False,
                "step": "video_generation",
                "image_url": image_url,
                "error": video_result.get("error", "Video generation failed")
            }

        return {
            "success": True,
            "prompt": prompt,
            "image_url": image_url,
            "video_url": video_result.get("video_url"),
            "model": model,
            "motion_strength": motion_strength
        }

    # =========================================================================
    # Utility Methods
    # =========================================================================

    async def get_user_info(self) -> Dict[str, Any]:
        """Get current user info and credits"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/me",
                    headers=self.headers
                )

                if response.status_code == 200:
                    data = response.json()
                    user_details = data.get("user_details", [{}])[0]
                    return {
                        "success": True,
                        "user_id": user_details.get("user", {}).get("id"),
                        "username": user_details.get("user", {}).get("username"),
                        "api_credits": user_details.get("apiConcurrencySlots", 0),
                        "subscription_tokens": user_details.get("subscriptionTokens", 0),
                        "api_subscription_tokens": user_details.get("apiSubscriptionTokens", 0)
                    }
                else:
                    return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            return {"success": False, "error": str(e)}


# Singleton instance
_leonardo_client: Optional[LeonardoClient] = None


def get_leonardo_client() -> LeonardoClient:
    """Get or create Leonardo client singleton"""
    global _leonardo_client
    if _leonardo_client is None:
        _leonardo_client = LeonardoClient()
    return _leonardo_client
