"""
VidGo Effects Service - White-labeled wrapper for GoEnhance API.

User-Facing Names:
- VidGo Style Effects (GoEnhance Style Transfer)
- VidGo HD Enhance (GoEnhance 4K Upscale)
- VidGo Video Pro (GoEnhance Video Enhancement)

Access Control:
- Subscribers only (Starter/Pro/Pro+)
- Demo users cannot access
"""
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.models.user import User
from app.models.billing import Plan, ServicePricing
from app.services.goenhance import GoEnhanceClient
from app.services.credit_service import CreditService

settings = get_settings()


# Unified style effects with VERIFIED GoEnhance model IDs (white-labeled)
# This is the single source of truth for all styles across the application
# Model IDs verified from GoEnhance API /video2video/modellist
#
# Available GoEnhance Models:
#   1016: Anime Style 3 (v4)
#   1033: GPT Anime Style (v4) - closest to Ghibli
#   5: Cute Anime Style (v1)
#   2: Anime Style 2 (v1)
#   2000: Anime Style (v5) - main anime
#   2004: Pixar Style (v5) - cartoon/3D
#   2005: Clay Style (v5)
#   2006: Oil Painting (v5)
#   2007: Watercolor (v5)
#   2008: Cyberpunk (v5)
#   2009: Realistic (v5)
#   2010: Cinematic (v5)
#
VIDGO_STYLES = [
    # === Artistic styles ===
    {
        "id": "anime",
        "name": "VidGo Anime",
        "name_zh": "動漫風格",
        "category": "artistic",
        "preview_url": "/static/previews/anime.jpg",
        "goenhance_model_id": 2000,  # Anime Style v5 ✓
        "prompt": "anime style"
    },
    {
        "id": "ghibli",
        "name": "VidGo Ghibli",
        "name_zh": "吉卜力風格",
        "category": "artistic",
        "preview_url": "/static/previews/ghibli.jpg",
        "goenhance_model_id": 1033,  # GPT Anime Style - closest to Ghibli! FIXED
        "prompt": "studio ghibli anime style, hayao miyazaki"
    },
    {
        "id": "cartoon",
        "name": "VidGo Cartoon",
        "name_zh": "卡通風格",
        "category": "artistic",
        "preview_url": "/static/previews/cartoon.jpg",
        "goenhance_model_id": 2004,  # Pixar Style v5 ✓
        "prompt": "cartoon pixar 3d animation style"
    },
    {
        "id": "clay",
        "name": "VidGo Clay",
        "name_zh": "黏土動畫",
        "category": "artistic",
        "preview_url": "/static/previews/clay.jpg",
        "goenhance_model_id": 2005,  # Clay Style v5 ✓ FIXED from 2003
        "prompt": "claymation stop motion clay animation style"
    },
    {
        "id": "cute_anime",
        "name": "VidGo Cute Anime",
        "name_zh": "可愛動漫",
        "category": "artistic",
        "preview_url": "/static/previews/cute_anime.jpg",
        "goenhance_model_id": 5,  # Cute Anime Style v1 ✓
        "prompt": "cute kawaii anime style"
    },
    {
        "id": "oil_painting",
        "name": "VidGo Oil Painting",
        "name_zh": "油畫風格",
        "category": "artistic",
        "preview_url": "/static/previews/oil_painting.jpg",
        "goenhance_model_id": 2006,  # Oil Painting v5 ✓ FIXED from 1005
        "prompt": "oil painting artistic van gogh style"
    },
    {
        "id": "watercolor",
        "name": "VidGo Watercolor",
        "name_zh": "水彩風格",
        "category": "artistic",
        "preview_url": "/static/previews/watercolor.jpg",
        "goenhance_model_id": 2007,  # Watercolor v5 ✓ FIXED from 1031
        "prompt": "watercolor painting soft artistic style"
    },
    # === Modern styles ===
    {
        "id": "cyberpunk",
        "name": "VidGo Cyberpunk",
        "name_zh": "賽博朋克",
        "category": "modern",
        "preview_url": "/static/previews/cyberpunk.jpg",
        "goenhance_model_id": 2008,  # Cyberpunk v5 ✓ FIXED from 1013
        "prompt": "cyberpunk neon futuristic sci-fi style"
    },
    {
        "id": "realistic",
        "name": "VidGo Realistic",
        "name_zh": "寫實風格",
        "category": "modern",
        "preview_url": "/static/previews/realistic.jpg",
        "goenhance_model_id": 2009,  # Realistic v5 ✓
        "prompt": "realistic photorealistic high quality style"
    },
    # === Professional styles ===
    {
        "id": "cinematic",
        "name": "VidGo Cinematic",
        "name_zh": "電影質感",
        "category": "professional",
        "preview_url": "/static/previews/cinematic.jpg",
        "goenhance_model_id": 2010,  # Cinematic v5 ✓ FIXED from 1016
        "prompt": "cinematic movie film hollywood style"
    },
    {
        "id": "anime_classic",
        "name": "VidGo Anime Classic",
        "name_zh": "經典動漫",
        "category": "professional",
        "preview_url": "/static/previews/anime_classic.jpg",
        "goenhance_model_id": 1016,  # Anime Style 3 v4 ✓
        "prompt": "classic anime high quality style"
    },
]

# Helper function to get style by ID
def get_style_by_id(style_id: str) -> Optional[Dict[str, Any]]:
    """Get style definition by ID"""
    for style in VIDGO_STYLES:
        if style["id"] == style_id:
            return style
    return None

# Helper function to get GoEnhance model ID for a style
def get_goenhance_model_id(style_id: str) -> Optional[int]:
    """Get GoEnhance model ID for a style"""
    style = get_style_by_id(style_id)
    if style:
        return style.get("goenhance_model_id")
    return None


class VidGoEffectsService:
    """VidGo Effects service wrapper for GoEnhance API."""

    def __init__(self, db: AsyncSession, goenhance_client: Optional[GoEnhanceClient] = None):
        self.db = db
        self.goenhance = goenhance_client or GoEnhanceClient()

    async def check_access(self, user_id: str, service_type: str) -> Tuple[bool, str]:
        """
        Check if user can access VidGo Effects.

        Returns:
            Tuple of (has_access, message)
        """
        # Get user and plan
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return False, "User not found"

        # Get user's plan
        plan = None
        if user.current_plan_id:
            plan_result = await self.db.execute(
                select(Plan).where(Plan.id == user.current_plan_id)
            )
            plan = plan_result.scalar_one_or_none()

        # Demo users cannot access VidGo Effects
        if not plan or plan.name == "demo":
            return False, "VidGo Effects requires a paid subscription (Starter, Pro, or Pro+)"

        # Check if plan has effects access
        if not plan.can_use_effects:
            return False, "Your plan does not include VidGo Effects"

        # Get service pricing to check subscribers_only
        pricing_result = await self.db.execute(
            select(ServicePricing).where(
                ServicePricing.service_type == service_type,
                ServicePricing.is_active == True
            )
        )
        pricing = pricing_result.scalar_one_or_none()

        if not pricing:
            return False, "Service not found"

        if pricing.subscribers_only and (not plan or plan.name == "demo"):
            return False, "This feature requires a paid subscription"

        # Check credit balance
        credit_service = CreditService(self.db)
        balance = await credit_service.get_balance(str(user_id))

        if balance["total"] < pricing.credit_cost:
            return False, f"Insufficient credits. Need {pricing.credit_cost}, have {balance['total']}"

        return True, "OK"

    def get_available_styles(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get available style effects."""
        if category:
            return [s for s in VIDGO_STYLES if s["category"] == category]
        return VIDGO_STYLES

    async def apply_style(
        self,
        user_id: str,
        image_url: str,
        style_id: str,
        intensity: float = 1.0
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Apply style effect to image using GoEnhance v2v API.

        Args:
            user_id: User ID
            image_url: URL of the input image
            style_id: Style effect ID
            intensity: Effect intensity (0.0 to 1.0)

        Returns:
            Tuple of (success, result_or_error)
        """
        service_type = "vidgo_style"

        # Check access
        has_access, message = await self.check_access(user_id, service_type)
        if not has_access:
            return False, {"error": message}

        # Validate style using unified style definition
        style_def = get_style_by_id(style_id)
        if not style_def:
            valid_styles = [s["id"] for s in VIDGO_STYLES]
            return False, {"error": f"Invalid style. Available: {', '.join(valid_styles)}"}

        try:
            # Use GoEnhance with the style's prompt from unified definition
            prompt = style_def.get("prompt", "artistic style")
            result = await self.goenhance.generate_image_and_wait(
                prompt=prompt,
                image_url=image_url,
                strength=intensity
            )

            if result.get("status") == "completed":
                # Deduct credits
                credit_service = CreditService(self.db)
                await credit_service.deduct_credits(
                    user_id=user_id,
                    amount=8,  # vidgo_style costs 8 credits
                    service_type=service_type,
                    description=f"VidGo Style Effects - {style_id}"
                )

                return True, {
                    "output_url": result.get("image_url"),
                    "style": style_id,
                    "credits_used": 8
                }
            else:
                return False, {"error": result.get("error", "Style transformation failed")}

        except Exception as e:
            return False, {"error": str(e)}

    async def hd_enhance(
        self,
        user_id: str,
        image_url: str,
        target_resolution: str = "4k"
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Upscale image to 4K resolution using GoEnhance.

        Args:
            user_id: User ID
            image_url: URL of the input image
            target_resolution: Target resolution (2k, 4k)

        Returns:
            Tuple of (success, result_or_error)
        """
        service_type = "vidgo_hd_enhance"

        # Check access
        has_access, message = await self.check_access(user_id, service_type)
        if not has_access:
            return False, {"error": message}

        try:
            # Use GoEnhance enhance_video for upscaling
            # The enhance_video method can handle upscaling
            result = await self.goenhance.enhance_video(
                video_url=image_url,  # Works with images too
                upscale=4 if target_resolution == "4k" else 2
            )

            if result.get("status") == "completed":
                # Deduct credits
                credit_service = CreditService(self.db)
                await credit_service.deduct_credits(
                    user_id=user_id,
                    amount=10,  # vidgo_hd_enhance costs 10 credits
                    service_type=service_type,
                    description=f"VidGo HD Enhance - {target_resolution}"
                )

                return True, {
                    "output_url": result.get("video_url") or result.get("output_url"),
                    "resolution": target_resolution,
                    "credits_used": 10
                }
            else:
                return False, {"error": result.get("error", "HD enhancement failed")}

        except Exception as e:
            return False, {"error": str(e)}

    async def video_enhance(
        self,
        user_id: str,
        video_url: str,
        enhancement_type: str = "quality"
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Enhance video quality using GoEnhance API.

        Args:
            user_id: User ID
            video_url: URL of the input video
            enhancement_type: Type of enhancement (quality, stabilize, denoise)

        Returns:
            Tuple of (success, result_or_error)
        """
        service_type = "vidgo_video_pro"

        # Check access - Pro plans only
        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            return False, {"error": "User not found"}

        plan = None
        if user.current_plan_id:
            plan_result = await self.db.execute(
                select(Plan).where(Plan.id == user.current_plan_id)
            )
            plan = plan_result.scalar_one_or_none()

        # Video Pro requires Pro or Pro+ plan
        if not plan or plan.name not in ["pro", "pro_plus"]:
            return False, {"error": "VidGo Video Pro requires Pro or Pro+ subscription"}

        has_access, message = await self.check_access(user_id, service_type)
        if not has_access:
            return False, {"error": message}

        try:
            # Call GoEnhance enhance_video API
            result = await self.goenhance.enhance_video(
                video_url=video_url,
                upscale=2 if enhancement_type == "quality" else 1
            )

            if result.get("status") == "completed":
                # Deduct credits
                credit_service = CreditService(self.db)
                await credit_service.deduct_credits(
                    user_id=user_id,
                    amount=12,  # vidgo_video_pro costs 12 credits
                    service_type=service_type,
                    description=f"VidGo Video Pro - {enhancement_type}"
                )

                return True, {
                    "output_url": result.get("video_url") or result.get("output_url"),
                    "enhancement": enhancement_type,
                    "credits_used": 12
                }
            else:
                return False, {"error": result.get("error", "Video enhancement failed")}

        except Exception as e:
            return False, {"error": str(e)}
