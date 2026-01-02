"""
GoEnhance Generation Service

Wraps GoEnhance API with the unified BaseGenerationService interface.
Supports:
- Text-to-Image (Nano Banana)
- Image-to-Image (Style Transfer via V2V)
- Video-to-Video (Style Transfer)
"""
import asyncio
import logging
from typing import Optional, List, Dict, Any

from app.services.base import BaseGenerationService, GenerationResult, GenerationType
from app.services.goenhance import GoEnhanceClient, GOENHANCE_STYLES

logger = logging.getLogger(__name__)


# Map VidGo style IDs to GoEnhance model IDs
VIDGO_TO_GOENHANCE_STYLE = {
    "anime": 2000,
    "anime_v3": 1016,
    "gpt_anime": 1033,
    "cute_anime": 5,
    "pixar": 2004,
    "clay": 2005,
    "oil_painting": 2006,
    "watercolor": 2007,
    "cyberpunk": 2008,
    "realistic": 2009,
    "cinematic": 2010,
    "cartoon": 2004,  # Use Pixar for cartoon
    "3d": 2005,       # Use Clay for 3D
    "sketch": 2007,   # Use Watercolor for sketch (closest)
    "vintage": 2010,  # Use Cinematic for vintage
    "product": 2009,  # Use Realistic for product
}


class GoEnhanceGenerationService(BaseGenerationService):
    """
    GoEnhance service implementation.

    Specializes in:
    - Fast text-to-image generation (Nano Banana)
    - Style transfer for images and videos
    """

    def __init__(self, client: Optional[GoEnhanceClient] = None):
        self._client = client or GoEnhanceClient()

    @property
    def service_name(self) -> str:
        return "goenhance"

    @property
    def supported_types(self) -> List[GenerationType]:
        return [
            GenerationType.TEXT_TO_IMAGE,
            GenerationType.IMAGE_TO_IMAGE,
            GenerationType.VIDEO_TO_VIDEO,
        ]

    def get_available_styles(self) -> List[Dict[str, Any]]:
        """Get available style options"""
        return [
            {
                "id": style_id,
                "goenhance_id": ge_id,
                "name": GOENHANCE_STYLES.get(ge_id, {}).get("name", style_id),
                "slug": GOENHANCE_STYLES.get(ge_id, {}).get("slug", style_id),
            }
            for style_id, ge_id in VIDGO_TO_GOENHANCE_STYLE.items()
        ]

    async def generate(
        self,
        generation_type: GenerationType,
        prompt: Optional[str] = None,
        source_image_url: Optional[str] = None,
        source_video_url: Optional[str] = None,
        style_id: Optional[str] = None,
        **kwargs
    ) -> GenerationResult:
        """
        Generate content using GoEnhance API.

        Args:
            generation_type: Type of generation
            prompt: Text prompt
            source_image_url: Source image for transformations
            source_video_url: Source video for V2V
            style_id: VidGo style ID (e.g., "anime", "oil_painting")
            **kwargs: Additional parameters (intensity, duration, resolution)

        Returns:
            GenerationResult
        """
        # Validate inputs
        error = self._validate_inputs(generation_type, prompt, source_image_url, source_video_url)
        if error:
            return GenerationResult(
                success=False,
                generation_type=generation_type,
                error=error,
                service_name=self.service_name
            )

        try:
            if generation_type == GenerationType.TEXT_TO_IMAGE:
                return await self._generate_text_to_image(prompt, style_id, **kwargs)

            elif generation_type == GenerationType.IMAGE_TO_IMAGE:
                return await self._generate_image_to_image(
                    source_image_url, prompt, style_id, **kwargs
                )

            elif generation_type == GenerationType.VIDEO_TO_VIDEO:
                return await self._generate_video_to_video(
                    source_video_url, prompt, style_id, **kwargs
                )

            else:
                return GenerationResult(
                    success=False,
                    generation_type=generation_type,
                    error=f"Unsupported generation type: {generation_type}",
                    service_name=self.service_name
                )

        except Exception as e:
            logger.error(f"GoEnhance generation error: {e}")
            return GenerationResult(
                success=False,
                generation_type=generation_type,
                error=str(e),
                service_name=self.service_name
            )

    async def _generate_text_to_image(
        self,
        prompt: str,
        style_id: Optional[str] = None,
        **kwargs
    ) -> GenerationResult:
        """Generate image from text using Nano Banana"""
        style_prompt = None
        if style_id:
            style_prompt = style_id.replace("_", " ")

        success, task_id, _ = await self._client.generate_image(prompt, style_prompt)

        if not success:
            return GenerationResult(
                success=False,
                generation_type=GenerationType.TEXT_TO_IMAGE,
                error=task_id,
                service_name=self.service_name,
                prompt=prompt
            )

        return GenerationResult(
            success=True,
            generation_type=GenerationType.TEXT_TO_IMAGE,
            task_id=task_id,
            status="processing",
            service_name=self.service_name,
            prompt=prompt,
            style_id=style_id
        )

    async def _generate_image_to_image(
        self,
        source_image_url: str,
        prompt: Optional[str],
        style_id: Optional[str],
        **kwargs
    ) -> GenerationResult:
        """
        Generate styled image from source image.

        Note: GoEnhance doesn't have direct image-to-image API.
        We create a short video from the image, apply style, then extract frame.
        For now, we use the video_url as output (first frame is effectively the styled image).
        """
        # Get GoEnhance model ID from VidGo style ID
        model_id = VIDGO_TO_GOENHANCE_STYLE.get(style_id, 2000)

        # For image-to-image, we need to convert to video first
        # This is a limitation - in production, consider using a different service
        # or implementing frame extraction

        # For demo purposes, we'll use the V2V endpoint with a static "video"
        # The result's first frame serves as our styled image

        duration = kwargs.get("duration", 3)  # Minimum duration
        resolution = kwargs.get("resolution", "720p")

        success, task_id, _ = await self._client.generate_v2v(
            video_url=source_image_url,  # Some V2V APIs accept images
            model_id=model_id,
            duration=duration,
            prompt=prompt,
            resolution=resolution
        )

        if not success:
            return GenerationResult(
                success=False,
                generation_type=GenerationType.IMAGE_TO_IMAGE,
                error=task_id,
                service_name=self.service_name,
                source_image_url=source_image_url,
                prompt=prompt,
                style_id=style_id
            )

        style_info = GOENHANCE_STYLES.get(model_id, {})

        return GenerationResult(
            success=True,
            generation_type=GenerationType.IMAGE_TO_IMAGE,
            task_id=task_id,
            status="processing",
            service_name=self.service_name,
            source_image_url=source_image_url,
            prompt=prompt,
            style_id=style_id,
            style_name=style_info.get("name"),
            model_name=style_info.get("slug")
        )

    async def _generate_video_to_video(
        self,
        source_video_url: str,
        prompt: Optional[str],
        style_id: Optional[str],
        **kwargs
    ) -> GenerationResult:
        """Apply style transformation to video"""
        model_id = VIDGO_TO_GOENHANCE_STYLE.get(style_id, 2000)
        duration = kwargs.get("duration", 5)
        resolution = kwargs.get("resolution", "720p")

        success, task_id, _ = await self._client.generate_v2v(
            video_url=source_video_url,
            model_id=model_id,
            duration=duration,
            prompt=prompt,
            resolution=resolution
        )

        if not success:
            return GenerationResult(
                success=False,
                generation_type=GenerationType.VIDEO_TO_VIDEO,
                error=task_id,
                service_name=self.service_name,
                source_video_url=source_video_url,
                prompt=prompt,
                style_id=style_id
            )

        style_info = GOENHANCE_STYLES.get(model_id, {})

        return GenerationResult(
            success=True,
            generation_type=GenerationType.VIDEO_TO_VIDEO,
            task_id=task_id,
            status="processing",
            service_name=self.service_name,
            source_video_url=source_video_url,
            prompt=prompt,
            style_id=style_id,
            style_name=style_info.get("name"),
            model_name=style_info.get("slug"),
            duration_seconds=duration,
            resolution=resolution
        )

    async def check_status(self, task_id: str) -> GenerationResult:
        """Check task status and get results"""
        try:
            # Try image result first
            img_result = await self._client.get_image_result(task_id)

            if img_result.get("status") == "success" and img_result.get("image_url"):
                return GenerationResult(
                    success=True,
                    generation_type=GenerationType.TEXT_TO_IMAGE,
                    task_id=task_id,
                    status="completed",
                    image_url=img_result.get("image_url"),
                    service_name=self.service_name
                )

            # Try video/V2V result
            v2v_result = await self._client.get_task_status(task_id)

            status = v2v_result.get("status", "unknown")

            if status == "completed":
                return GenerationResult(
                    success=True,
                    generation_type=GenerationType.VIDEO_TO_VIDEO,
                    task_id=task_id,
                    status="completed",
                    video_url=v2v_result.get("video_url"),
                    thumbnail_url=v2v_result.get("thumbnail_url"),
                    service_name=self.service_name
                )
            elif status in ["failed", "error"]:
                return GenerationResult(
                    success=False,
                    generation_type=GenerationType.VIDEO_TO_VIDEO,
                    task_id=task_id,
                    status="failed",
                    error=v2v_result.get("error", "Generation failed"),
                    service_name=self.service_name
                )
            else:
                return GenerationResult(
                    success=True,
                    generation_type=GenerationType.VIDEO_TO_VIDEO,
                    task_id=task_id,
                    status="processing",
                    service_name=self.service_name
                )

        except Exception as e:
            logger.error(f"GoEnhance status check error: {e}")
            return GenerationResult(
                success=False,
                generation_type=GenerationType.TEXT_TO_IMAGE,
                task_id=task_id,
                status="error",
                error=str(e),
                service_name=self.service_name
            )


# Singleton instance
_goenhance_service: Optional[GoEnhanceGenerationService] = None


def get_goenhance_service() -> GoEnhanceGenerationService:
    """Get or create GoEnhance service singleton"""
    global _goenhance_service
    if _goenhance_service is None:
        _goenhance_service = GoEnhanceGenerationService()
    return _goenhance_service
