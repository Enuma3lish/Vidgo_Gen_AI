"""
Prompt Generator Service for VidGo Platform

This service handles:
1. Generating context-aware prompts based on tool/topic
2. Storing prompts and results in PostgreSQL
3. Serving cached results for demo/non-subscribed users
4. Reducing API calls by reusing pre-generated content

Key Features:
- Topic-aware prompt generation (e.g., background_change → "remove background from shoes")
- Multi-language support
- Before/after result caching
- Access control based on subscription tier
"""
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import select, and_, or_, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.models.prompt_template import (
    PromptTemplate,
    PromptTemplateUsage,
    PromptGroup,
    PromptSubTopic,
    GROUP_DISPLAY_NAMES,
    SUB_TOPIC_DISPLAY_NAMES,
)
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


# === Demo Images for Unsubscribed Users ===
# High-quality stock images from Unsplash for demo purposes
DEMO_IMAGES = {
    "product": [
        "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800",  # Watch
        "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800",  # Headphones
        "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800",    # Sneaker
        "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=800",  # Camera
        "https://images.unsplash.com/photo-1541643600914-78b084683601?w=800",  # Perfume
    ],
    "fashion": [
        "https://images.unsplash.com/photo-1434389677669-e08b4cac3105?w=800",  # Dress
        "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=800",  # Jacket
        "https://images.unsplash.com/photo-1594938298603-c8148c4dae35?w=800",  # T-shirt
        "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=800",    # Coat
        "https://images.unsplash.com/photo-1560243563-062bfc001d68?w=800",    # Fashion items
    ],
    "interior": [
        "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=800",  # Living room
        "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?w=800",  # Kitchen
        "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=800",  # Bedroom
        "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800",  # Modern room
        "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=800",  # Dining room
    ],
    "avatar": [
        "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=800",  # Woman portrait 1
        "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800",  # Man portrait 1
        "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=800",  # Woman portrait 2
        "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=800",  # Man portrait 2
        "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=800",  # Fashion portrait
    ],
}

# === Predefined Prompt Templates by Group (5 per group for demo users) ===
DEFAULT_PROMPTS = {
    PromptGroup.BACKGROUND_REMOVAL: {
        "prompts": [
            {
                "prompt_en": "Remove the background from this product image",
                "prompt_zh": "移除這張產品圖片的背景",
                "sub_topic": PromptSubTopic.TRANSPARENT,
                "keywords": ["remove", "background", "transparent", "product"],
                "input_image_url": DEMO_IMAGES["product"][0],
            },
            {
                "prompt_en": "Remove background and create transparent PNG",
                "prompt_zh": "移除背景並創建透明PNG圖片",
                "sub_topic": PromptSubTopic.TRANSPARENT,
                "keywords": ["remove", "background", "transparent", "png"],
                "input_image_url": DEMO_IMAGES["product"][1],
            },
            {
                "prompt_en": "Remove background from shoes image",
                "prompt_zh": "移除鞋子圖片的背景",
                "sub_topic": PromptSubTopic.TRANSPARENT,
                "keywords": ["remove", "background", "shoes", "footwear"],
                "input_image_url": DEMO_IMAGES["product"][2],
            },
            {
                "prompt_en": "Create clean product cutout with transparent background",
                "prompt_zh": "創建乾淨的產品剪影，透明背景",
                "sub_topic": PromptSubTopic.TRANSPARENT,
                "keywords": ["cutout", "clean", "transparent", "product"],
                "input_image_url": DEMO_IMAGES["product"][3],
            },
            {
                "prompt_en": "Extract product from background for e-commerce",
                "prompt_zh": "為電商提取產品，移除背景",
                "sub_topic": PromptSubTopic.TRANSPARENT,
                "keywords": ["extract", "ecommerce", "background", "removal"],
                "input_image_url": DEMO_IMAGES["product"][4],
            },
        ],
        "api_endpoint": "/api/v1/tools/background-removal",
        "api_provider": "goenhance",
    },
    PromptGroup.BACKGROUND_CHANGE: {
        "prompts": [
            {
                "prompt_en": "Place this product on a professional studio background with soft lighting",
                "prompt_zh": "將此產品放在專業攝影棚背景上，柔和燈光",
                "sub_topic": PromptSubTopic.STUDIO_BACKGROUND,
                "keywords": ["studio", "professional", "lighting", "product"],
                "input_image_url": DEMO_IMAGES["product"][0],
            },
            {
                "prompt_en": "Create outdoor nature scene with this product on wooden table",
                "prompt_zh": "為此產品創建戶外自然場景，放在木桌上",
                "sub_topic": PromptSubTopic.NATURE_BACKGROUND,
                "keywords": ["nature", "outdoor", "wooden", "table"],
                "input_image_url": DEMO_IMAGES["product"][1],
            },
            {
                "prompt_en": "Place product on luxury marble surface with elegant lighting",
                "prompt_zh": "將產品放在奢華大理石表面上，優雅燈光",
                "sub_topic": PromptSubTopic.LUXURY_BACKGROUND,
                "keywords": ["marble", "luxury", "elegant", "lighting"],
                "input_image_url": DEMO_IMAGES["product"][2],
            },
            {
                "prompt_en": "Create minimalist white background with subtle shadows",
                "prompt_zh": "創建極簡白色背景，微妙陰影",
                "sub_topic": PromptSubTopic.WHITE_BACKGROUND,
                "keywords": ["minimalist", "white", "shadows", "clean"],
                "input_image_url": DEMO_IMAGES["product"][3],
            },
            {
                "prompt_en": "Place product in modern lifestyle setting with plants",
                "prompt_zh": "將產品放在現代生活場景中，搭配綠植",
                "sub_topic": PromptSubTopic.NATURE_BACKGROUND,
                "keywords": ["lifestyle", "modern", "plants", "setting"],
                "input_image_url": DEMO_IMAGES["product"][4],
            },
        ],
        "api_endpoint": "/api/v1/tools/product-scene",
        "api_provider": "piapi",
    },
    PromptGroup.PRODUCT_EFFECT: {
        "prompts": [
            {
                "prompt_en": "Change the color of this product to elegant rose gold",
                "prompt_zh": "將此產品的顏色更改為優雅的玫瑰金",
                "sub_topic": PromptSubTopic.COLOR_CHANGE,
                "keywords": ["color", "change", "rose gold", "elegant"],
                "input_image_url": DEMO_IMAGES["product"][0],
            },
            {
                "prompt_en": "Apply matte black finish to this product",
                "prompt_zh": "為此產品應用啞光黑色效果",
                "sub_topic": PromptSubTopic.MATERIAL_CHANGE,
                "keywords": ["matte", "black", "finish", "product"],
                "input_image_url": DEMO_IMAGES["product"][1],
            },
            {
                "prompt_en": "Add chrome metallic effect with reflections",
                "prompt_zh": "添加鉻金屬效果與反射",
                "sub_topic": PromptSubTopic.MATERIAL_CHANGE,
                "keywords": ["chrome", "metallic", "reflections", "effect"],
                "input_image_url": DEMO_IMAGES["product"][2],
            },
            {
                "prompt_en": "Create dramatic studio lighting with sharp shadows",
                "prompt_zh": "創建戲劇性攝影棚燈光與銳利陰影",
                "sub_topic": PromptSubTopic.LIGHTING_CHANGE,
                "keywords": ["dramatic", "lighting", "shadows", "studio"],
                "input_image_url": DEMO_IMAGES["product"][3],
            },
            {
                "prompt_en": "Add holographic rainbow effect to product surface",
                "prompt_zh": "為產品表面添加全息彩虹效果",
                "sub_topic": PromptSubTopic.MATERIAL_CHANGE,
                "keywords": ["holographic", "rainbow", "effect", "surface"],
                "input_image_url": DEMO_IMAGES["product"][4],
            },
        ],
        "api_endpoint": "/api/v1/tools/product-effect",
        "api_provider": "piapi",
    },
    PromptGroup.ROOM_REDESIGN: {
        "prompts": [
            {
                "prompt_en": "Transform this room into modern minimalist style with clean lines",
                "prompt_zh": "將此房間轉變為現代極簡風格，簡潔線條",
                "sub_topic": PromptSubTopic.MODERN_STYLE,
                "keywords": ["modern", "minimalist", "clean", "lines"],
                "input_image_url": DEMO_IMAGES["interior"][0],
            },
            {
                "prompt_en": "Redesign this room in Nordic style with light wood and white tones",
                "prompt_zh": "以北歐風格重新設計此房間，淺色木質與白色調",
                "sub_topic": PromptSubTopic.NORDIC_STYLE,
                "keywords": ["nordic", "wood", "white", "scandinavian"],
                "input_image_url": DEMO_IMAGES["interior"][1],
            },
            {
                "prompt_en": "Transform into Japanese zen style with tatami and shoji screens",
                "prompt_zh": "轉變為日式禪風，榻榻米與障子門",
                "sub_topic": PromptSubTopic.JAPANESE_STYLE,
                "keywords": ["japanese", "zen", "tatami", "shoji"],
                "input_image_url": DEMO_IMAGES["interior"][2],
            },
            {
                "prompt_en": "Create industrial loft style with exposed brick and metal",
                "prompt_zh": "創建工業風閣樓風格，裸露磚牆與金屬",
                "sub_topic": PromptSubTopic.INDUSTRIAL_STYLE,
                "keywords": ["industrial", "loft", "brick", "metal"],
                "input_image_url": DEMO_IMAGES["interior"][3],
            },
            {
                "prompt_en": "Transform into luxury contemporary style with elegant furniture",
                "prompt_zh": "轉變為奢華當代風格，優雅家具",
                "sub_topic": PromptSubTopic.MODERN_STYLE,
                "keywords": ["luxury", "contemporary", "elegant", "furniture"],
                "input_image_url": DEMO_IMAGES["interior"][4],
            },
        ],
        "api_endpoint": "/api/v1/interior/redesign",
        "api_provider": "piapi",
    },
    PromptGroup.IMAGE_TO_VIDEO: {
        "prompts": [
            {
                "prompt_en": "Create smooth zoom in animation focusing on the product",
                "prompt_zh": "創建流暢的放大動畫，聚焦於產品",
                "sub_topic": PromptSubTopic.ZOOM_IN,
                "keywords": ["zoom", "smooth", "focus", "animation"],
                "input_image_url": DEMO_IMAGES["product"][0],
            },
            {
                "prompt_en": "Add cinematic slow motion with dramatic lighting effects",
                "prompt_zh": "添加電影級慢動作與戲劇性燈光效果",
                "sub_topic": PromptSubTopic.CINEMATIC,
                "keywords": ["cinematic", "slow motion", "dramatic", "lighting"],
                "input_image_url": DEMO_IMAGES["product"][1],
            },
            {
                "prompt_en": "Create 360 degree rotation animation of the product",
                "prompt_zh": "創建產品360度旋轉動畫",
                "sub_topic": PromptSubTopic.ROTATE,
                "keywords": ["rotation", "360", "product", "animation"],
                "input_image_url": DEMO_IMAGES["product"][2],
            },
            {
                "prompt_en": "Add gentle floating motion with particle effects",
                "prompt_zh": "添加輕柔漂浮動作與粒子效果",
                "sub_topic": PromptSubTopic.CINEMATIC,
                "keywords": ["floating", "particles", "gentle", "motion"],
                "input_image_url": DEMO_IMAGES["product"][3],
            },
            {
                "prompt_en": "Create dynamic camera movement around the scene",
                "prompt_zh": "創建場景周圍的動態相機運動",
                "sub_topic": PromptSubTopic.CINEMATIC,
                "keywords": ["camera", "dynamic", "movement", "scene"],
                "input_image_url": DEMO_IMAGES["product"][4],
            },
        ],
        "api_endpoint": "/api/v1/video/image-to-video",
        "api_provider": "piapi",
    },
    PromptGroup.STYLE_TRANSFER: {
        "prompts": [
            {
                "prompt_en": "Transform this video into anime style with vibrant colors",
                "prompt_zh": "將此視頻轉換為動漫風格，鮮豔色彩",
                "sub_topic": PromptSubTopic.DEFAULT,
                "keywords": ["anime", "vibrant", "colors", "transform"],
                "input_video_url": None,  # User provides video
            },
            {
                "prompt_en": "Apply Studio Ghibli animation style to this video",
                "prompt_zh": "將吉卜力工作室動畫風格應用於此視頻",
                "sub_topic": PromptSubTopic.DEFAULT,
                "keywords": ["ghibli", "animation", "studio", "style"],
                "input_video_url": None,
            },
            {
                "prompt_en": "Convert to watercolor painting artistic style",
                "prompt_zh": "轉換為水彩畫藝術風格",
                "sub_topic": PromptSubTopic.DEFAULT,
                "keywords": ["watercolor", "artistic", "painting", "style"],
                "input_video_url": None,
            },
            {
                "prompt_en": "Apply cyberpunk neon style with glowing effects",
                "prompt_zh": "應用賽博朋克霓虹風格與發光效果",
                "sub_topic": PromptSubTopic.DEFAULT,
                "keywords": ["cyberpunk", "neon", "glowing", "effects"],
                "input_video_url": None,
            },
            {
                "prompt_en": "Transform into oil painting masterpiece style",
                "prompt_zh": "轉換為油畫傑作風格",
                "sub_topic": PromptSubTopic.DEFAULT,
                "keywords": ["oil painting", "masterpiece", "artistic", "style"],
                "input_video_url": None,
            },
        ],
        "api_endpoint": "/api/v1/video/style-transfer",
        "api_provider": "goenhance",
    },
    PromptGroup.AI_AVATAR: {
        "prompts": [
            {
                "prompt_en": "Welcome to our brand! I'm excited to introduce our latest innovative products that will transform your daily life.",
                "prompt_zh": "歡迎來到我們的品牌！我很高興為您介紹我們最新的創新產品，將改變您的日常生活。",
                "sub_topic": PromptSubTopic.DEFAULT,
                "keywords": ["welcome", "brand", "introduce", "products"],
                "input_image_url": DEMO_IMAGES["avatar"][0],
            },
            {
                "prompt_en": "Hello everyone! Today I'll show you something truly special. Let's discover what makes our products unique.",
                "prompt_zh": "大家好！今天我要給您展示一些真正特別的東西。讓我們一起發現我們產品的獨特之處。",
                "sub_topic": PromptSubTopic.DEFAULT,
                "keywords": ["hello", "special", "unique", "discover"],
                "input_image_url": DEMO_IMAGES["avatar"][1],
            },
            {
                "prompt_en": "Thank you for joining us! We've been working hard to bring you the best quality and experience possible.",
                "prompt_zh": "感謝您的加入！我們一直努力為您帶來最好的品質和體驗。",
                "sub_topic": PromptSubTopic.DEFAULT,
                "keywords": ["thank you", "quality", "experience", "best"],
                "input_image_url": DEMO_IMAGES["avatar"][2],
            },
            {
                "prompt_en": "Hi there! Let me tell you about our amazing new features that our customers absolutely love.",
                "prompt_zh": "嗨！讓我告訴您關於我們客戶絕對喜愛的驚人新功能。",
                "sub_topic": PromptSubTopic.DEFAULT,
                "keywords": ["features", "amazing", "customers", "love"],
                "input_image_url": DEMO_IMAGES["avatar"][3],
            },
            {
                "prompt_en": "Hey everyone! Don't miss out on our exclusive offer. Subscribe now and save big on your first order!",
                "prompt_zh": "嗨大家好！不要錯過我們的獨家優惠。立即訂閱，首單享受超值折扣！",
                "sub_topic": PromptSubTopic.DEFAULT,
                "keywords": ["offer", "exclusive", "subscribe", "save"],
                "input_image_url": DEMO_IMAGES["avatar"][4],
            },
        ],
        "api_endpoint": "/api/v1/avatar/generate",
        "api_provider": "a2e",
    },
}


class PromptGeneratorService:
    """
    Service for generating, storing, and retrieving prompt templates.

    Features:
    - Context-aware prompt generation based on tool/topic
    - PostgreSQL storage for prompts and results
    - Cache management for demo users
    - Access control based on subscription tier
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # PROMPT GENERATION
    # =========================================================================

    def generate_prompt_hash(self, prompt: str, group: PromptGroup, sub_topic: PromptSubTopic) -> str:
        """Generate a unique hash for a prompt."""
        normalized = f"{prompt.lower().strip()}:{group.value}:{sub_topic.value}"
        return hashlib.sha256(normalized.encode()).hexdigest()

    async def generate_prompt(
        self,
        group: PromptGroup,
        sub_topic: Optional[PromptSubTopic] = None,
        language: str = "en",
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a context-aware prompt based on group and sub_topic.

        Args:
            group: Main prompt group (e.g., BACKGROUND_CHANGE)
            sub_topic: Optional sub-topic for more specific prompts
            language: Language code (en, zh-TW, ja, ko, es)
            context: Optional context like product type, style preferences

        Returns:
            Dict with prompt text and metadata
        """
        sub_topic = sub_topic or PromptSubTopic.DEFAULT

        # Check for existing templates
        templates = await self.get_templates_by_group(group, sub_topic, language)

        if templates:
            # Return a random template from existing ones
            import random
            template = random.choice(templates)
            return {
                "prompt": template.prompt,
                "prompt_localized": getattr(template, f"prompt_{language[:2]}", template.prompt_en),
                "group": group.value,
                "sub_topic": sub_topic.value,
                "template_id": str(template.id),
                "has_cached_result": template.is_cached,
                "cached_result": {
                    "input_image_url": template.input_image_url,
                    "result_image_url": template.result_image_url,
                    "result_video_url": template.result_video_url,
                } if template.is_cached else None,
            }

        # Generate new prompt from defaults
        if group in DEFAULT_PROMPTS:
            prompts = DEFAULT_PROMPTS[group]["prompts"]
            for p in prompts:
                if sub_topic == p.get("sub_topic", PromptSubTopic.DEFAULT):
                    return {
                        "prompt": p["prompt_en"],
                        "prompt_localized": p.get(f"prompt_{language[:2]}", p["prompt_en"]),
                        "group": group.value,
                        "sub_topic": sub_topic.value,
                        "template_id": None,
                        "has_cached_result": False,
                    }

        # Fallback
        return {
            "prompt": "",
            "group": group.value,
            "sub_topic": sub_topic.value,
            "template_id": None,
            "has_cached_result": False,
        }

    # =========================================================================
    # TEMPLATE CRUD OPERATIONS
    # =========================================================================

    async def create_template(
        self,
        prompt: str,
        group: PromptGroup,
        sub_topic: PromptSubTopic = PromptSubTopic.DEFAULT,
        prompt_translations: Optional[Dict[str, str]] = None,
        input_data: Optional[Dict[str, Any]] = None,
        result_data: Optional[Dict[str, Any]] = None,
        api_info: Optional[Dict[str, str]] = None,
        is_default: bool = True,
        **kwargs,
    ) -> PromptTemplate:
        """
        Create a new prompt template and store in PostgreSQL.

        Args:
            prompt: The main prompt text
            group: Prompt group category
            sub_topic: Sub-topic within the group
            prompt_translations: Dict of language translations
            input_data: Before/source data (images, videos)
            result_data: After/result data (generated content)
            api_info: API endpoint and provider info
            is_default: Whether available for demo users

        Returns:
            Created PromptTemplate instance
        """
        prompt_hash = self.generate_prompt_hash(prompt, group, sub_topic)

        # Check if already exists
        existing = await self.get_template_by_hash(prompt_hash, group, sub_topic)
        if existing:
            logger.info(f"Template already exists: {prompt_hash[:16]}...")
            return existing

        translations = prompt_translations or {}
        input_data = input_data or {}
        result_data = result_data or {}
        api_info = api_info or DEFAULT_PROMPTS.get(group, {})

        template = PromptTemplate(
            prompt_hash=prompt_hash,
            prompt=prompt,
            prompt_normalized=prompt.lower().strip(),
            prompt_en=translations.get("en", prompt),
            prompt_zh=translations.get("zh"),
            prompt_ja=translations.get("ja"),
            prompt_ko=translations.get("ko"),
            prompt_es=translations.get("es"),
            group=group,
            sub_topic=sub_topic,
            group_display_en=GROUP_DISPLAY_NAMES.get(group, {}).get("en"),
            group_display_zh=GROUP_DISPLAY_NAMES.get(group, {}).get("zh"),
            sub_topic_display_en=SUB_TOPIC_DISPLAY_NAMES.get(sub_topic, {}).get("en"),
            sub_topic_display_zh=SUB_TOPIC_DISPLAY_NAMES.get(sub_topic, {}).get("zh"),
            keywords=kwargs.get("keywords", []),
            tags=kwargs.get("tags", []),
            input_image_url=input_data.get("image_url"),
            input_video_url=input_data.get("video_url"),
            input_params=input_data.get("params", {}),
            result_image_url=result_data.get("image_url"),
            result_video_url=result_data.get("video_url"),
            result_thumbnail_url=result_data.get("thumbnail_url"),
            result_watermarked_url=result_data.get("watermarked_url"),
            result_params=result_data.get("params", {}),
            api_endpoint=api_info.get("api_endpoint"),
            api_provider=api_info.get("api_provider"),
            api_model=api_info.get("api_model"),
            is_default=is_default,
            is_cached=bool(result_data.get("image_url") or result_data.get("video_url")),
            **{k: v for k, v in kwargs.items() if k not in ["keywords", "tags"]},
        )

        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)

        logger.info(f"Created template: {group.value}/{sub_topic.value} - {prompt[:50]}...")
        return template

    async def get_template_by_hash(
        self,
        prompt_hash: str,
        group: PromptGroup,
        sub_topic: PromptSubTopic,
    ) -> Optional[PromptTemplate]:
        """Get a template by its unique hash."""
        result = await self.db.execute(
            select(PromptTemplate).where(
                and_(
                    PromptTemplate.prompt_hash == prompt_hash,
                    PromptTemplate.group == group,
                    PromptTemplate.sub_topic == sub_topic,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_template_by_id(self, template_id: str) -> Optional[PromptTemplate]:
        """Get a template by ID."""
        result = await self.db.execute(
            select(PromptTemplate).where(PromptTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    async def get_templates_by_group(
        self,
        group: PromptGroup,
        sub_topic: Optional[PromptSubTopic] = None,
        language: str = "en",
        limit: int = 10,
        include_premium: bool = False,
    ) -> List[PromptTemplate]:
        """
        Get templates filtered by group and optionally sub_topic.

        Args:
            group: Main prompt group
            sub_topic: Optional sub-topic filter
            language: Preferred language for sorting
            limit: Maximum number of results
            include_premium: Include premium templates

        Returns:
            List of matching templates
        """
        query = select(PromptTemplate).where(
            and_(
                PromptTemplate.group == group,
                PromptTemplate.is_active == True,
            )
        )

        if sub_topic:
            query = query.where(PromptTemplate.sub_topic == sub_topic)

        if not include_premium:
            query = query.where(PromptTemplate.is_default == True)

        query = query.order_by(
            PromptTemplate.popularity_score.desc(),
            PromptTemplate.quality_score.desc(),
        ).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_default_templates_for_demo(
        self,
        group: PromptGroup,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Get default templates with cached results for demo/non-subscribed users.
        This helps reduce API calls by serving pre-generated content.

        Args:
            group: The prompt group to get templates for
            limit: Maximum number of templates

        Returns:
            List of templates with cached results
        """
        result = await self.db.execute(
            select(PromptTemplate).where(
                and_(
                    PromptTemplate.group == group,
                    PromptTemplate.is_active == True,
                    PromptTemplate.is_default == True,
                    PromptTemplate.is_cached == True,
                )
            ).order_by(
                PromptTemplate.popularity_score.desc(),
            ).limit(limit)
        )

        templates = result.scalars().all()

        return [
            {
                "id": str(t.id),
                "prompt": t.prompt,
                "prompt_zh": t.prompt_zh,
                "group": t.group.value,
                "sub_topic": t.sub_topic.value,
                "input_image_url": t.input_image_url,
                "result_image_url": t.result_image_url,
                "result_video_url": t.result_video_url,
                "result_thumbnail_url": t.result_thumbnail_url,
                "result_watermarked_url": t.result_watermarked_url,
                "title_en": t.title_en,
                "title_zh": t.title_zh,
            }
            for t in templates
        ]

    # =========================================================================
    # RESULT CACHING
    # =========================================================================

    async def cache_result(
        self,
        template_id: str,
        input_data: Dict[str, Any],
        result_data: Dict[str, Any],
        generation_time_ms: int = 0,
        cost_usd: float = 0.0,
    ) -> PromptTemplate:
        """
        Cache the generation result for a template.

        Args:
            template_id: Template ID to update
            input_data: Input/before data
            result_data: Generated result data
            generation_time_ms: Generation duration
            cost_usd: API cost

        Returns:
            Updated template
        """
        template = await self.get_template_by_id(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        # Update template with cached result
        template.input_image_url = input_data.get("image_url", template.input_image_url)
        template.input_video_url = input_data.get("video_url", template.input_video_url)
        template.input_params = input_data.get("params", template.input_params)

        template.result_image_url = result_data.get("image_url")
        template.result_video_url = result_data.get("video_url")
        template.result_thumbnail_url = result_data.get("thumbnail_url")
        template.result_watermarked_url = result_data.get("watermarked_url")
        template.result_params = result_data.get("params", {})

        template.is_cached = True
        template.cache_expires_at = datetime.utcnow() + timedelta(days=30)

        # Update statistics
        template.success_count = (template.success_count or 0) + 1
        template.avg_generation_time_ms = generation_time_ms
        template.total_cost_usd = (template.total_cost_usd or 0.0) + cost_usd

        await self.db.commit()
        await self.db.refresh(template)

        logger.info(f"Cached result for template: {template_id}")
        return template

    async def get_cached_result(
        self,
        group: PromptGroup,
        prompt: str,
        sub_topic: Optional[PromptSubTopic] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a cached result for a prompt if available.

        Args:
            group: Prompt group
            prompt: The prompt text to match
            sub_topic: Optional sub-topic

        Returns:
            Cached result data or None
        """
        sub_topic = sub_topic or PromptSubTopic.DEFAULT
        prompt_hash = self.generate_prompt_hash(prompt, group, sub_topic)

        template = await self.get_template_by_hash(prompt_hash, group, sub_topic)

        if template and template.is_cached:
            # Check if cache is still valid
            if template.cache_expires_at and template.cache_expires_at < datetime.utcnow():
                return None

            return {
                "template_id": str(template.id),
                "prompt": template.prompt,
                "input_image_url": template.input_image_url,
                "input_video_url": template.input_video_url,
                "result_image_url": template.result_image_url,
                "result_video_url": template.result_video_url,
                "result_thumbnail_url": template.result_thumbnail_url,
                "result_watermarked_url": template.result_watermarked_url,
                "cached_at": template.updated_at,
            }

        return None

    # =========================================================================
    # USAGE TRACKING
    # =========================================================================

    async def record_usage(
        self,
        template_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        source_page: str = "tool_page",
        user_tier: str = "free",
        used_cached: bool = True,
        was_successful: bool = True,
        generation_time_ms: Optional[int] = None,
        custom_prompt: Optional[str] = None,
        custom_params: Optional[Dict[str, Any]] = None,
    ) -> PromptTemplateUsage:
        """
        Record usage of a prompt template.

        Args:
            template_id: Template that was used
            user_id: User ID (if logged in)
            session_id: Session ID (for anonymous users)
            source_page: Page where template was used
            user_tier: User's subscription tier
            used_cached: Whether cached result was served
            was_successful: Whether generation succeeded
            generation_time_ms: Generation duration
            custom_prompt: Custom prompt if user modified it
            custom_params: Custom parameters used

        Returns:
            Created usage record
        """
        usage = PromptTemplateUsage(
            template_id=template_id,
            user_id=user_id,
            session_id=session_id,
            source_page=source_page,
            user_tier=user_tier,
            used_cached=used_cached,
            was_successful=was_successful,
            generation_time_ms=generation_time_ms,
            custom_prompt=custom_prompt,
            custom_params=custom_params or {},
        )

        self.db.add(usage)

        # Update template statistics
        await self.db.execute(
            update(PromptTemplate)
            .where(PromptTemplate.id == template_id)
            .values(
                usage_count=PromptTemplate.usage_count + 1,
                popularity_score=PromptTemplate.popularity_score + 1,
                last_used_at=datetime.utcnow(),
            )
        )

        await self.db.commit()
        await self.db.refresh(usage)

        return usage

    # =========================================================================
    # PROMPT MATCHING
    # =========================================================================

    async def find_similar_template(
        self,
        prompt: str,
        group: PromptGroup,
        threshold: float = 0.7,
    ) -> Optional[PromptTemplate]:
        """
        Find a similar cached template using keyword matching.

        Args:
            prompt: Input prompt to match
            group: Prompt group to search in
            threshold: Similarity threshold (0-1)

        Returns:
            Best matching template or None
        """
        # Extract keywords from input prompt
        words = set(prompt.lower().split())

        # Get all templates in the group
        templates = await self.get_templates_by_group(group, limit=50)

        best_match = None
        best_score = 0.0

        for template in templates:
            if not template.keywords:
                continue

            # Calculate Jaccard similarity
            template_words = set(template.keywords)
            intersection = len(words & template_words)
            union = len(words | template_words)

            if union > 0:
                score = intersection / union
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = template

        return best_match

    # =========================================================================
    # BATCH OPERATIONS
    # =========================================================================

    async def seed_default_prompts(self) -> Dict[str, int]:
        """
        Seed the database with default prompts from DEFAULT_PROMPTS.

        Returns:
            Dict with count of created templates per group
        """
        counts = {}

        for group, config in DEFAULT_PROMPTS.items():
            count = 0
            for prompt_data in config["prompts"]:
                try:
                    await self.create_template(
                        prompt=prompt_data["prompt_en"],
                        group=group,
                        sub_topic=prompt_data.get("sub_topic", PromptSubTopic.DEFAULT),
                        prompt_translations={
                            "en": prompt_data["prompt_en"],
                            "zh": prompt_data.get("prompt_zh"),
                        },
                        keywords=prompt_data.get("keywords", []),
                        api_info=config,
                        is_default=True,
                    )
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to seed prompt: {e}")

            counts[group.value] = count
            logger.info(f"Seeded {count} prompts for {group.value}")

        return counts

    async def get_all_groups(self) -> List[Dict[str, Any]]:
        """
        Get all available prompt groups with their display names.

        Returns:
            List of group information dicts
        """
        result = await self.db.execute(
            select(
                PromptTemplate.group,
                func.count(PromptTemplate.id).label("count"),
            )
            .where(PromptTemplate.is_active == True)
            .group_by(PromptTemplate.group)
        )

        group_counts = {row.group: row.count for row in result.all()}

        return [
            {
                "group": group.value,
                "display_en": GROUP_DISPLAY_NAMES.get(group, {}).get("en", group.value),
                "display_zh": GROUP_DISPLAY_NAMES.get(group, {}).get("zh", group.value),
                "template_count": group_counts.get(group, 0),
            }
            for group in PromptGroup
        ]

    async def get_sub_topics_for_group(self, group: PromptGroup) -> List[Dict[str, Any]]:
        """
        Get all sub-topics available for a group.

        Args:
            group: The prompt group

        Returns:
            List of sub-topic information dicts
        """
        result = await self.db.execute(
            select(
                PromptTemplate.sub_topic,
                func.count(PromptTemplate.id).label("count"),
            )
            .where(
                and_(
                    PromptTemplate.group == group,
                    PromptTemplate.is_active == True,
                )
            )
            .group_by(PromptTemplate.sub_topic)
        )

        sub_topic_counts = {row.sub_topic: row.count for row in result.all()}

        return [
            {
                "sub_topic": st.value,
                "display_en": SUB_TOPIC_DISPLAY_NAMES.get(st, {}).get("en", st.value),
                "display_zh": SUB_TOPIC_DISPLAY_NAMES.get(st, {}).get("zh", st.value),
                "template_count": sub_topic_counts.get(st, 0),
            }
            for st in PromptSubTopic
            if sub_topic_counts.get(st, 0) > 0
        ]


# === Helper Functions ===

def get_prompt_generator_service(db: AsyncSession) -> PromptGeneratorService:
    """Factory function to create PromptGeneratorService instance."""
    return PromptGeneratorService(db)
