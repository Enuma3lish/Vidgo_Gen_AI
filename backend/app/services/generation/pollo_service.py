"""
Pollo AI Generation Service

Wraps Pollo AI API with the unified BaseGenerationService interface.
Specializes in Image-to-Video generation with multiple model options.
"""
import logging
from typing import Optional, List, Dict, Any

from app.services.base import BaseGenerationService, GenerationResult, GenerationType
from app.services.pollo_ai import PolloAIClient, POLLO_MODELS

logger = logging.getLogger(__name__)


class PolloGenerationService(BaseGenerationService):
    """
    Pollo AI service implementation.

    Specializes in:
    - High-quality image-to-video generation
    - Multiple model options (Pixverse, Kling, Luma)
    """

    def __init__(self, client: Optional[PolloAIClient] = None):
        self._client = client or PolloAIClient()

    @property
    def service_name(self) -> str:
        return "pollo_ai"

    @property
    def supported_types(self) -> List[GenerationType]:
        return [GenerationType.IMAGE_TO_VIDEO]

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get available I2V models"""
        return [
            {
                "id": model_id,
                "name": info["name"],
                "description": info["description"],
                "lengths": info["lengths"],
            }
            for model_id, info in POLLO_MODELS.items()
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
        Generate video from image using Pollo AI.

        Args:
            generation_type: Must be IMAGE_TO_VIDEO
            prompt: Motion/animation prompt
            source_image_url: Source image URL (required)
            style_id: Model ID (e.g., "pixverse_v4.5", "kling_v2")
            **kwargs: Additional parameters (length, negative_prompt)

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

        if generation_type != GenerationType.IMAGE_TO_VIDEO:
            return GenerationResult(
                success=False,
                generation_type=generation_type,
                error=f"Pollo AI only supports IMAGE_TO_VIDEO, not {generation_type}",
                service_name=self.service_name
            )

        try:
            return await self._generate_image_to_video(
                source_image_url=source_image_url,
                prompt=prompt or "smooth motion, cinematic quality",
                model=style_id or "pixverse_v4.5",
                **kwargs
            )

        except Exception as e:
            logger.error(f"Pollo AI generation error: {e}")
            return GenerationResult(
                success=False,
                generation_type=generation_type,
                error=str(e),
                service_name=self.service_name,
                source_image_url=source_image_url,
                prompt=prompt
            )

    async def _generate_image_to_video(
        self,
        source_image_url: str,
        prompt: str,
        model: str = "pixverse_v4.5",
        **kwargs
    ) -> GenerationResult:
        """Generate video from image"""
        length = kwargs.get("length", 5)
        negative_prompt = kwargs.get(
            "negative_prompt",
            "blurry, distorted, low quality, jerky motion"
        )

        model_info = POLLO_MODELS.get(model, POLLO_MODELS["pixverse_v4.5"])

        success, task_id, _ = await self._client.generate_video(
            image_url=source_image_url,
            prompt=prompt,
            model=model,
            negative_prompt=negative_prompt,
            length=length
        )

        if not success:
            return GenerationResult(
                success=False,
                generation_type=GenerationType.IMAGE_TO_VIDEO,
                error=task_id,
                service_name=self.service_name,
                source_image_url=source_image_url,
                prompt=prompt
            )

        return GenerationResult(
            success=True,
            generation_type=GenerationType.IMAGE_TO_VIDEO,
            task_id=task_id,
            status="processing",
            service_name=self.service_name,
            source_image_url=source_image_url,
            prompt=prompt,
            model_name=model_info["name"],
            duration_seconds=float(length),
            resolution="720p"
        )

    async def check_status(self, task_id: str) -> GenerationResult:
        """Check task status and get results"""
        try:
            result = await self._client.get_task_status(task_id)

            status = result.get("status", "").lower()

            if status == "succeed":
                return GenerationResult(
                    success=True,
                    generation_type=GenerationType.IMAGE_TO_VIDEO,
                    task_id=task_id,
                    status="completed",
                    video_url=result.get("video_url"),
                    service_name=self.service_name
                )
            elif status == "failed":
                return GenerationResult(
                    success=False,
                    generation_type=GenerationType.IMAGE_TO_VIDEO,
                    task_id=task_id,
                    status="failed",
                    error=result.get("error", "Video generation failed"),
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
            logger.error(f"Pollo AI status check error: {e}")
            return GenerationResult(
                success=False,
                generation_type=GenerationType.IMAGE_TO_VIDEO,
                task_id=task_id,
                status="error",
                error=str(e),
                service_name=self.service_name
            )


# Singleton instance
_pollo_service: Optional[PolloGenerationService] = None


def get_pollo_service() -> PolloGenerationService:
    """Get or create Pollo AI service singleton"""
    global _pollo_service
    if _pollo_service is None:
        _pollo_service = PolloGenerationService()
    return _pollo_service
