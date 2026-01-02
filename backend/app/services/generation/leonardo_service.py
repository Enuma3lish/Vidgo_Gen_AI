"""
Leonardo AI Generation Service

Wraps Leonardo AI API with the unified BaseGenerationService interface.
Supports:
- Text-to-Image generation (Phoenix, Kino XL, Lightning XL)
- Image-to-Video (Motion)
"""
import logging
from typing import Optional, List, Dict, Any

from app.services.base import BaseGenerationService, GenerationResult, GenerationType
from app.services.leonardo import LeonardoClient

logger = logging.getLogger(__name__)


# Leonardo model configurations
LEONARDO_MODELS = {
    "phoenix": {
        "name": "Leonardo Phoenix",
        "description": "Best quality, creative images",
        "type": "image"
    },
    "kino_xl": {
        "name": "Leonardo Kino XL",
        "description": "Cinematic, high-quality",
        "type": "image"
    },
    "lightning_xl": {
        "name": "Leonardo Lightning XL",
        "description": "Fast generation",
        "type": "image"
    },
    "diffusion_xl": {
        "name": "Leonardo Diffusion XL",
        "description": "Balanced quality/speed",
        "type": "image"
    },
    "motion": {
        "name": "Leonardo Motion",
        "description": "Image-to-Video generation",
        "type": "video"
    }
}


class LeonardoGenerationService(BaseGenerationService):
    """
    Leonardo AI service implementation.

    Specializes in:
    - High-quality text-to-image generation
    - Image-to-video with Leonardo Motion
    """

    def __init__(self, client: Optional[LeonardoClient] = None):
        self._client = client or LeonardoClient()

    @property
    def service_name(self) -> str:
        return "leonardo"

    @property
    def supported_types(self) -> List[GenerationType]:
        return [
            GenerationType.TEXT_TO_IMAGE,
            GenerationType.IMAGE_TO_VIDEO,
        ]

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get available models"""
        return [
            {"id": model_id, **info}
            for model_id, info in LEONARDO_MODELS.items()
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
        Generate content using Leonardo AI.

        Args:
            generation_type: TEXT_TO_IMAGE or IMAGE_TO_VIDEO
            prompt: Text prompt
            source_image_url: Source image for I2V
            style_id: Model ID (e.g., "phoenix", "kino_xl")
            **kwargs: Additional parameters (width, height, motion_strength)

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
                return await self._generate_text_to_image(
                    prompt=prompt,
                    model=style_id or "phoenix",
                    **kwargs
                )

            elif generation_type == GenerationType.IMAGE_TO_VIDEO:
                return await self._generate_image_to_video(
                    source_image_url=source_image_url,
                    prompt=prompt,
                    **kwargs
                )

            else:
                return GenerationResult(
                    success=False,
                    generation_type=generation_type,
                    error=f"Unsupported generation type: {generation_type}",
                    service_name=self.service_name
                )

        except Exception as e:
            logger.error(f"Leonardo generation error: {e}")
            return GenerationResult(
                success=False,
                generation_type=generation_type,
                error=str(e),
                service_name=self.service_name,
                source_image_url=source_image_url,
                prompt=prompt
            )

    async def _generate_text_to_image(
        self,
        prompt: str,
        model: str = "phoenix",
        **kwargs
    ) -> GenerationResult:
        """Generate image from text"""
        width = kwargs.get("width", 1024)
        height = kwargs.get("height", 768)
        negative_prompt = kwargs.get("negative_prompt")

        model_info = LEONARDO_MODELS.get(model, LEONARDO_MODELS["phoenix"])

        result = await self._client.generate_image_and_wait(
            prompt=prompt,
            model=model,
            width=width,
            height=height,
            negative_prompt=negative_prompt,
            timeout=kwargs.get("timeout", 120)
        )

        if result.get("success"):
            return GenerationResult(
                success=True,
                generation_type=GenerationType.TEXT_TO_IMAGE,
                task_id=result.get("generation_id"),
                status="completed",
                image_url=result.get("image_url"),
                service_name=self.service_name,
                prompt=prompt,
                model_name=model_info["name"],
                resolution=f"{width}x{height}",
                raw_response=result
            )
        else:
            return GenerationResult(
                success=False,
                generation_type=GenerationType.TEXT_TO_IMAGE,
                error=result.get("error", "Image generation failed"),
                service_name=self.service_name,
                prompt=prompt
            )

    async def _generate_image_to_video(
        self,
        source_image_url: str,
        prompt: Optional[str] = None,
        **kwargs
    ) -> GenerationResult:
        """Generate video from image using Leonardo Motion"""
        motion_strength = kwargs.get("motion_strength", 5)

        # Generate video from external image URL
        result = await self._client.generate_video_from_url(
            image_url=source_image_url,
            motion_strength=motion_strength
        )

        if result.get("success"):
            return GenerationResult(
                success=True,
                generation_type=GenerationType.IMAGE_TO_VIDEO,
                task_id=result.get("generation_id"),
                status="processing",
                service_name=self.service_name,
                source_image_url=source_image_url,
                prompt=prompt,
                model_name="Leonardo Motion"
            )
        else:
            return GenerationResult(
                success=False,
                generation_type=GenerationType.IMAGE_TO_VIDEO,
                error=result.get("error", "Video generation failed"),
                service_name=self.service_name,
                source_image_url=source_image_url,
                prompt=prompt
            )

    async def check_status(self, task_id: str) -> GenerationResult:
        """Check task status and get results"""
        try:
            # Check motion result for video
            result = await self._client.get_motion_result(task_id)

            status = result.get("status", "").upper()

            if status == "COMPLETE":
                return GenerationResult(
                    success=True,
                    generation_type=GenerationType.IMAGE_TO_VIDEO,
                    task_id=task_id,
                    status="completed",
                    video_url=result.get("video_url"),
                    service_name=self.service_name
                )
            elif status == "FAILED":
                return GenerationResult(
                    success=False,
                    generation_type=GenerationType.IMAGE_TO_VIDEO,
                    task_id=task_id,
                    status="failed",
                    error="Video generation failed",
                    service_name=self.service_name
                )
            else:
                return GenerationResult(
                    success=True,
                    generation_type=GenerationType.IMAGE_TO_VIDEO,
                    task_id=task_id,
                    status="processing",
                    service_name=self.service_name
                )

        except Exception as e:
            logger.error(f"Leonardo status check error: {e}")
            return GenerationResult(
                success=False,
                generation_type=GenerationType.IMAGE_TO_VIDEO,
                task_id=task_id,
                status="error",
                error=str(e),
                service_name=self.service_name
            )

    async def generate_product_video(
        self,
        prompt: str,
        model: str = "phoenix",
        motion_strength: int = 5,
        timeout: int = 300
    ) -> GenerationResult:
        """
        Full pipeline: Text -> Image -> Video

        Generates an image from prompt, then converts to video.
        This is the complete product video generation workflow.

        Args:
            prompt: Product description
            model: Image model to use
            motion_strength: Video motion intensity
            timeout: Max wait time

        Returns:
            GenerationResult with both image_url and video_url
        """
        # Step 1: Generate image
        image_result = await self._generate_text_to_image(
            prompt=prompt,
            model=model,
            width=1024,
            height=576,  # 16:9 for video
            timeout=120
        )

        if not image_result.success:
            return image_result

        image_url = image_result.image_url

        # Step 2: Generate video from image
        video_result = await self.generate_and_wait(
            generation_type=GenerationType.IMAGE_TO_VIDEO,
            source_image_url=image_url,
            prompt=prompt,
            motion_strength=motion_strength,
            timeout=timeout
        )

        if video_result.success:
            # Merge results
            video_result.image_url = image_url
            video_result.prompt = prompt

        return video_result


# Singleton instance
_leonardo_service: Optional[LeonardoGenerationService] = None


def get_leonardo_service() -> LeonardoGenerationService:
    """Get or create Leonardo service singleton"""
    global _leonardo_service
    if _leonardo_service is None:
        _leonardo_service = LeonardoGenerationService()
    return _leonardo_service
