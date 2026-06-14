"""
Base Provider Interface
All AI providers must implement this interface.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BaseProvider(ABC):
    """Abstract base class for all AI providers."""

    name: str = "base"

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is healthy and accessible."""
        pass

    @abstractmethod
    async def close(self):
        """Close any open connections."""
        pass

    def _log_request(self, task_type: str, params: Dict[str, Any]):
        """Log API request for debugging."""
        logger.info(f"[{self.name}] Request: {task_type} - {params.get('prompt', '')[:50]}...")

    def _log_response(self, task_type: str, success: bool, error: Optional[str] = None):
        """Log API response."""
        if success:
            logger.info(f"[{self.name}] Response: {task_type} - SUCCESS")
        else:
            logger.error(f"[{self.name}] Response: {task_type} - FAILED: {error}")


class ImageGenerationProvider(BaseProvider):
    """Provider that supports text-to-image generation."""

    @abstractmethod
    async def text_to_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate image from text prompt."""
        pass


class VideoGenerationProvider(BaseProvider):
    """Provider that supports video generation."""

    @abstractmethod
    async def image_to_video(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate video from image."""
        pass

    @abstractmethod
    async def text_to_video(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate video from text prompt."""
        pass


class StyleTransferProvider(BaseProvider):
    """Provider that supports style transfer."""

    @abstractmethod
    async def style_transfer(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Apply style transfer to video."""
        pass


class AvatarProvider(BaseProvider):
    """Provider that supports avatar generation."""

    @abstractmethod
    async def generate_avatar(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate avatar video with lip sync."""
        pass
