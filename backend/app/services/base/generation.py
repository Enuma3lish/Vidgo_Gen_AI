"""
Base Generation Service Interface

Provides a unified interface for all AI generation services (GoEnhance, Leonardo, Pollo AI, etc.)
This abstraction allows easy swapping of providers and consistent error handling.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class GenerationType(str, Enum):
    """Types of AI generation operations"""
    TEXT_TO_IMAGE = "text_to_image"
    IMAGE_TO_IMAGE = "image_to_image"  # Style transfer, effects
    IMAGE_TO_VIDEO = "image_to_video"
    VIDEO_TO_VIDEO = "video_to_video"  # Style transfer on video
    IMAGE_UPSCALE = "image_upscale"
    VIDEO_UPSCALE = "video_upscale"


@dataclass
class GenerationResult:
    """Standardized result from any generation service"""
    success: bool
    generation_type: GenerationType

    # Output URLs
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None

    # Task tracking
    task_id: Optional[str] = None
    status: str = "pending"  # pending, processing, completed, failed

    # Input tracking (for material collection)
    source_image_url: Optional[str] = None
    source_video_url: Optional[str] = None
    prompt: Optional[str] = None
    prompt_enhanced: Optional[str] = None

    # Metadata
    service_name: str = ""
    model_name: Optional[str] = None
    style_id: Optional[str] = None
    style_name: Optional[str] = None
    duration_seconds: Optional[float] = None
    resolution: Optional[str] = None

    # Cost tracking
    credits_used: float = 0.0
    api_cost_usd: float = 0.0

    # Error handling
    error: Optional[str] = None
    error_code: Optional[str] = None

    # Raw response for debugging
    raw_response: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "success": self.success,
            "generation_type": self.generation_type.value,
            "image_url": self.image_url,
            "video_url": self.video_url,
            "thumbnail_url": self.thumbnail_url,
            "task_id": self.task_id,
            "status": self.status,
            "source_image_url": self.source_image_url,
            "source_video_url": self.source_video_url,
            "prompt": self.prompt,
            "service_name": self.service_name,
            "model_name": self.model_name,
            "style_id": self.style_id,
            "style_name": self.style_name,
            "duration_seconds": self.duration_seconds,
            "resolution": self.resolution,
            "credits_used": self.credits_used,
            "error": self.error,
        }


class BaseGenerationService(ABC):
    """
    Abstract base class for all AI generation services.

    Implementations: GoEnhanceService, LeonardoService, PolloAIService
    """

    @property
    @abstractmethod
    def service_name(self) -> str:
        """Return the service identifier (e.g., 'goenhance', 'leonardo', 'pollo_ai')"""
        pass

    @property
    @abstractmethod
    def supported_types(self) -> List[GenerationType]:
        """Return list of supported generation types"""
        pass

    @abstractmethod
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
        Unified generation method.

        Args:
            generation_type: Type of generation to perform
            prompt: Text prompt for generation
            source_image_url: Source image for transformations
            source_video_url: Source video for transformations
            style_id: Style/model ID for style transfer
            **kwargs: Additional service-specific parameters

        Returns:
            GenerationResult with output URLs and metadata
        """
        pass

    @abstractmethod
    async def check_status(self, task_id: str) -> GenerationResult:
        """
        Check status of an async generation task.

        Args:
            task_id: Task ID from initial generation call

        Returns:
            GenerationResult with current status and output if complete
        """
        pass

    async def generate_and_wait(
        self,
        generation_type: GenerationType,
        prompt: Optional[str] = None,
        source_image_url: Optional[str] = None,
        source_video_url: Optional[str] = None,
        style_id: Optional[str] = None,
        timeout: int = 300,
        poll_interval: int = 5,
        **kwargs
    ) -> GenerationResult:
        """
        Generate and wait for completion.
        Default implementation uses generate() + check_status() polling.
        Override for services with native blocking support.

        Args:
            generation_type: Type of generation
            prompt: Text prompt
            source_image_url: Source image URL
            source_video_url: Source video URL
            style_id: Style ID
            timeout: Max wait time in seconds
            poll_interval: Seconds between status checks
            **kwargs: Additional parameters

        Returns:
            Final GenerationResult
        """
        import asyncio

        result = await self.generate(
            generation_type=generation_type,
            prompt=prompt,
            source_image_url=source_image_url,
            source_video_url=source_video_url,
            style_id=style_id,
            **kwargs
        )

        if not result.success or not result.task_id:
            return result

        elapsed = 0
        while elapsed < timeout:
            status_result = await self.check_status(result.task_id)

            if status_result.status == "completed":
                # Merge input data with output
                status_result.source_image_url = source_image_url
                status_result.source_video_url = source_video_url
                status_result.prompt = prompt
                return status_result
            elif status_result.status == "failed":
                return status_result

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        return GenerationResult(
            success=False,
            generation_type=generation_type,
            task_id=result.task_id,
            status="timeout",
            error=f"Generation timed out after {timeout}s",
            service_name=self.service_name,
            source_image_url=source_image_url,
            prompt=prompt,
        )

    def _validate_inputs(
        self,
        generation_type: GenerationType,
        prompt: Optional[str],
        source_image_url: Optional[str],
        source_video_url: Optional[str]
    ) -> Optional[str]:
        """
        Validate inputs for a generation type.

        Returns:
            Error message if validation fails, None if valid
        """
        if generation_type not in self.supported_types:
            return f"Generation type {generation_type.value} not supported by {self.service_name}"

        if generation_type == GenerationType.TEXT_TO_IMAGE:
            if not prompt:
                return "Prompt is required for text-to-image generation"

        elif generation_type == GenerationType.IMAGE_TO_IMAGE:
            if not source_image_url:
                return "Source image URL is required for image-to-image transformation"

        elif generation_type == GenerationType.IMAGE_TO_VIDEO:
            if not source_image_url:
                return "Source image URL is required for image-to-video generation"

        elif generation_type == GenerationType.VIDEO_TO_VIDEO:
            if not source_video_url:
                return "Source video URL is required for video-to-video transformation"

        return None
