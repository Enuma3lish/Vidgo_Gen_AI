"""
AI Service Rescue Mechanism
Wrapper around ProviderRouter with automatic failover.

Architecture (following vidgo-backend-architecture.md):
- T2I: PiAPI/Wan (primary) → Pollo (backup)
- I2V: PiAPI/Wan (primary) → Pollo (backup)
- T2V: PiAPI/Wan (primary) → Pollo (backup)
- Interior: PiAPI/Wan Doodle (primary) → Gemini (backup)
- V2V: GoEnhance only (no backup)
- Avatar: A2E.ai only (no backup)
- Background Removal: GoEnhance (local rembg)
"""
import logging
from typing import Optional, Dict, Any

from app.providers.provider_router import get_provider_router, TaskType

logger = logging.getLogger(__name__)


class AIServiceWithRescue:
    """
    AI Service wrapper with automatic rescue fallback.

    This is a wrapper around ProviderRouter that provides a simpler interface
    for common AI generation tasks with automatic failover.
    """

    def __init__(self):
        self._router = None

    @property
    def router(self):
        if self._router is None:
            self._router = get_provider_router()
        return self._router

    # =========================================================================
    # TEXT-TO-IMAGE (T2I): PiAPI/Wan primary → Pollo backup
    # =========================================================================

    async def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        user_tier: str = "starter",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate image from text prompt.
        Primary: PiAPI (Wan)
        Backup: Pollo.ai

        Args:
            prompt: Text description of image to generate
            width: Image width (default 1024)
            height: Image height (default 1024)
            user_tier: User subscription tier (starter, pro, pro_plus)

        Returns:
            Dict with success, image_url, service_used, rescue_used
        """
        logger.info(f"T2I request: {prompt[:100]}...")

        try:
            result = await self.router.route(
                TaskType.T2I,
                {
                    "prompt": prompt,
                    "size": f"{width}*{height}"
                },
                user_tier=user_tier
            )

            if result.get("success"):
                output = result.get("output", {})
                image_url = output.get("image_url")
                images = output.get("images", [])
                if not image_url and images:
                    image_url = images[0].get("url")

                return {
                    "success": True,
                    "image_url": image_url,
                    "images": images,
                    "service_used": "piapi" if not result.get("used_backup") else result.get("backup_provider"),
                    "rescue_used": result.get("backup_provider") if result.get("used_backup") else None,
                    "model": "wan2.5-t2i"
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Generation failed"),
                    "service_used": None,
                    "rescue_used": None
                }

        except Exception as e:
            logger.error(f"T2I error: {e}")
            return {
                "success": False,
                "error": str(e),
                "service_used": None,
                "rescue_used": None
            }

    # =========================================================================
    # IMAGE-TO-VIDEO (I2V): PiAPI/Wan primary → Pollo backup
    # =========================================================================

    async def generate_video(
        self,
        image_url: str,
        prompt: str,
        length: int = 5,
        timeout: int = 300,
        user_tier: str = "starter",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate video from image.
        Primary: PiAPI (Wan I2V)
        Backup: Pollo.ai

        Args:
            image_url: URL of source image
            prompt: Animation/motion description
            length: Video length in seconds
            timeout: Max wait time
            user_tier: User subscription tier (starter, pro, pro_plus)

        Returns:
            Dict with success, video_url, service_used, rescue_used
        """
        logger.info(f"I2V request: image={image_url[:60]}..., prompt={prompt[:50]}...")

        try:
            result = await self.router.route(
                TaskType.I2V,
                {
                    "image_url": image_url,
                    "prompt": prompt,
                    "duration": length
                },
                user_tier=user_tier
            )

            if result.get("success"):
                output = result.get("output", {})
                video_url = output.get("video_url")

                return {
                    "success": True,
                    "video_url": video_url,
                    "task_id": result.get("task_id"),
                    "service_used": "piapi" if not result.get("used_backup") else result.get("backup_provider"),
                    "rescue_used": result.get("backup_provider") if result.get("used_backup") else None,
                    "model": "wan2.6-i2v"
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Generation failed"),
                    "service_used": None,
                    "rescue_used": None
                }

        except Exception as e:
            logger.error(f"I2V error: {e}")
            return {
                "success": False,
                "error": str(e),
                "service_used": None,
                "rescue_used": None
            }

    # =========================================================================
    # INTERIOR DESIGN: PiAPI/Wan Doodle primary → Gemini backup
    # =========================================================================

    async def interior_design(
        self,
        image_url: Optional[str] = None,
        image_base64: Optional[str] = None,
        prompt: str = "",
        style_id: Optional[str] = None,
        room_type: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate interior design.
        Primary: PiAPI (Wan Doodle)
        Backup: Gemini

        Args:
            image_url: URL of room image
            image_base64: Base64-encoded room image
            prompt: Design description
            style_id: Design style ID
            room_type: Type of room

        Returns:
            Dict with success, image_url, service_used, rescue_used
        """
        logger.info(f"Interior design request: style={style_id}, room={room_type}")

        try:
            result = await self.router.route(
                TaskType.INTERIOR,
                {
                    "image_url": image_url,
                    "prompt": prompt,
                    "style": style_id or "modern",
                    "room_type": room_type or "living_room"
                }
            )

            if result.get("success"):
                output = result.get("output", {})
                image_url = output.get("image_url")
                description = output.get("description")

                return {
                    "success": True,
                    "image_url": image_url,
                    "description": description,
                    "service_used": "piapi" if not result.get("used_backup") else result.get("backup_provider"),
                    "rescue_used": result.get("backup_provider") if result.get("used_backup") else None
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Generation failed"),
                    "service_used": None,
                    "rescue_used": None
                }

        except Exception as e:
            logger.error(f"Interior design error: {e}")
            return {
                "success": False,
                "error": str(e),
                "service_used": None,
                "rescue_used": None
            }

    # =========================================================================
    # Service Status Check
    # =========================================================================

    async def check_service_status(self) -> Dict[str, Any]:
        """
        Check status of all AI services.

        Returns:
            Dict with status of each service
        """
        return await self.router.check_service_status()


# Singleton instance
_rescue_service: Optional[AIServiceWithRescue] = None


def get_rescue_service() -> AIServiceWithRescue:
    """Get or create rescue service singleton."""
    global _rescue_service
    if _rescue_service is None:
        _rescue_service = AIServiceWithRescue()
    return _rescue_service
