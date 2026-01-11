"""
VidGo Effects Service - White-labeled wrapper for PiAPI Wan API.

User-Facing Names:
- VidGo Style Effects (PiAPI Wan Style Transfer)
- VidGo HD Enhance (PiAPI Wan Upscale)
- VidGo Video Pro (PiAPI Wan Video Enhancement)

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
from app.providers import ProviderRouter, TaskType
from app.services.credit_service import CreditService

settings = get_settings()


# Unified style effects for VidGo (white-labeled)
# This is the single source of truth for all styles across the application
#
VIDGO_STYLES = [
    # === Artistic styles ===
    {
        "id": "anime",
        "name": "VidGo Anime",
        "name_zh": "動漫風格",
        "category": "artistic",
        "preview_url": "https://cdn.pixabay.com/photo/2022/08/09/16/19/anime-7375400_640.jpg",
        "prompt": "anime style"
    },
    {
        "id": "ghibli",
        "name": "VidGo Ghibli",
        "name_zh": "吉卜力風格",
        "category": "artistic",
        "preview_url": "https://cdn.pixabay.com/photo/2020/06/14/03/55/anime-5296573_640.jpg",
        "prompt": "studio ghibli anime style, hayao miyazaki"
    },
    {
        "id": "cartoon",
        "name": "VidGo Cartoon",
        "name_zh": "卡通風格",
        "category": "artistic",
        "preview_url": "https://cdn.pixabay.com/photo/2017/07/03/20/17/colorful-2468874_640.jpg",
        "prompt": "cartoon pixar 3d animation style"
    },
    {
        "id": "clay",
        "name": "VidGo Clay",
        "name_zh": "黏土動畫",
        "category": "artistic",
        "preview_url": "https://cdn.pixabay.com/photo/2018/03/07/17/36/clay-3206587_640.jpg",
        "prompt": "claymation stop motion clay animation style"
    },
    {
        "id": "cute_anime",
        "name": "VidGo Cute Anime",
        "name_zh": "可愛動漫",
        "category": "artistic",
        "preview_url": "https://cdn.pixabay.com/photo/2022/12/01/15/38/ai-generated-7629380_640.jpg",
        "prompt": "cute kawaii anime style"
    },
    {
        "id": "oil_painting",
        "name": "VidGo Oil Painting",
        "name_zh": "油畫風格",
        "category": "artistic",
        "preview_url": "https://images.unsplash.com/photo-1579783902614-a3fb3927b6a5?w=400&h=300&fit=crop",
        "prompt": "oil painting artistic van gogh style"
    },
    {
        "id": "watercolor",
        "name": "VidGo Watercolor",
        "name_zh": "水彩風格",
        "category": "artistic",
        "preview_url": "https://images.unsplash.com/photo-1460661419201-fd4cecdf8a8b?w=400&h=300&fit=crop",
        "prompt": "watercolor painting soft artistic style"
    },
    # === Modern styles ===
    {
        "id": "cyberpunk",
        "name": "VidGo Cyberpunk",
        "name_zh": "賽博朋克",
        "category": "modern",
        "preview_url": "https://images.unsplash.com/photo-1515705576963-95cad62945b6?w=400&h=300&fit=crop",
        "prompt": "cyberpunk neon futuristic sci-fi style"
    },
    {
        "id": "realistic",
        "name": "VidGo Realistic",
        "name_zh": "寫實風格",
        "category": "modern",
        "preview_url": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400&h=300&fit=crop",
        "prompt": "realistic photorealistic high quality style"
    },
    # === Professional styles ===
    {
        "id": "cinematic",
        "name": "VidGo Cinematic",
        "name_zh": "電影質感",
        "category": "professional",
        "preview_url": "https://images.unsplash.com/photo-1485846234645-a62644f84728?w=400&h=300&fit=crop",
        "prompt": "cinematic movie film hollywood style"
    },
    {
        "id": "anime_classic",
        "name": "VidGo Anime Classic",
        "name_zh": "經典動漫",
        "category": "professional",
        "preview_url": "https://images.unsplash.com/photo-1613376023733-0a73315d9b06?w=400&h=300&fit=crop",
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

# Helper function to get style prompt for a style
def get_style_prompt(style_id: str) -> Optional[str]:
    """Get style prompt for a style"""
    style = get_style_by_id(style_id)
    if style:
        return style.get("prompt")
    return None


class VidGoEffectsService:
    """VidGo Effects service wrapper for PiAPI Wan API."""

    def __init__(self, db: AsyncSession, router: Optional[ProviderRouter] = None):
        self.db = db
        self.router = router or ProviderRouter()

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
        Apply style effect to image using PiAPI Wan API.

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
            # Use PiAPI with the style's prompt from unified definition
            prompt = style_def.get("prompt", "artistic style")
            result = await self.router.route(
                TaskType.T2I,
                {
                    "prompt": prompt,
                    "image_url": image_url,
                    "strength": intensity
                }
            )

            output_url = result.get("image_url") or result.get("output_url")
            if output_url:
                # Deduct credits
                credit_service = CreditService(self.db)
                await credit_service.deduct_credits(
                    user_id=user_id,
                    amount=8,  # vidgo_style costs 8 credits
                    service_type=service_type,
                    description=f"VidGo Style Effects - {style_id}"
                )

                return True, {
                    "output_url": output_url,
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
        Upscale image to 4K resolution using PiAPI Wan.

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
            # Use PiAPI for upscaling
            result = await self.router.route(
                TaskType.UPSCALE,
                {
                    "image_url": image_url,
                    "scale": 4 if target_resolution == "4k" else 2
                }
            )

            output_url = result.get("image_url") or result.get("output_url")
            if output_url:
                # Deduct credits
                credit_service = CreditService(self.db)
                await credit_service.deduct_credits(
                    user_id=user_id,
                    amount=10,  # vidgo_hd_enhance costs 10 credits
                    service_type=service_type,
                    description=f"VidGo HD Enhance - {target_resolution}"
                )

                return True, {
                    "output_url": output_url,
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
        Enhance video quality using PiAPI Wan API.

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
            # Call PiAPI V2V for video enhancement
            result = await self.router.route(
                TaskType.V2V,
                {
                    "video_url": video_url,
                    "prompt": "high quality enhanced video"
                }
            )

            output_url = result.get("video_url") or result.get("output_url")
            if output_url:
                # Deduct credits
                credit_service = CreditService(self.db)
                await credit_service.deduct_credits(
                    user_id=user_id,
                    amount=12,  # vidgo_video_pro costs 12 credits
                    service_type=service_type,
                    description=f"VidGo Video Pro - {enhancement_type}"
                )

                return True, {
                    "output_url": output_url,
                    "enhancement": enhancement_type,
                    "credits_used": 12
                }
            else:
                return False, {"error": result.get("error", "Video enhancement failed")}

        except Exception as e:
            return False, {"error": str(e)}
