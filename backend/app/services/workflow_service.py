"""
Unified Workflow Service for VidGo Platform

Handles complete generation workflows following the Architecture pipeline:
1. Text-to-Image (T2I): Wan AI → Image
2. Image-to-Video (I2V): Image → Pollo AI → Video
3. Video-to-Video (V2V): Video → GoEnhance → Styled Video
4. Avatar Generation: Image + Script → A2E.ai → Avatar Video

All results are stored in the Material DB with:
- prompt: Main generation prompt
- effect_prompt: Effect/enhancement prompt (nullable)
- main_topic: Category (e.g., "產品電商")
- topic: Sub-topic (e.g., "AI product designed")
- result: Image/Video URL
"""
import asyncio
import hashlib
import logging
import uuid
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.models.material import Material, ToolType, MaterialSource, MaterialStatus
from app.services.a2e_service import get_a2e_service, A2EAvatarService
from app.services.rescue_service import get_rescue_service
from app.services.pollo_ai import get_pollo_client, PolloAIClient
from app.providers.provider_router import get_provider_router, TaskType

logger = logging.getLogger(__name__)


# Topic definitions with prompts
WORKFLOW_TOPICS = {
    "產品電商": {
        "en": "Product E-commerce",
        "topics": {
            "luxury_watch": {
                "en": "Luxury Watch Ads",
                "zh": "奢華手錶廣告",
                "prompts": [
                    "A luxurious gold wristwatch on a marble surface with dramatic lighting, professional product photography",
                    "Premium Swiss watch with diamond bezel, elegant black leather strap, on velvet display",
                    "Modern smartwatch with rose gold case, fitness tracking display, lifestyle shot",
                ]
            },
            "skincare": {
                "en": "Skincare Products",
                "zh": "護膚產品",
                "prompts": [
                    "Premium skincare serum bottle with golden droplets, soft pink background, beauty product photography",
                    "Organic face cream jar with natural ingredients, fresh flowers and leaves decoration",
                    "Anti-aging moisturizer with hyaluronic acid, clean white aesthetic, spa atmosphere",
                ]
            },
            "beverage": {
                "en": "Beverage Ads",
                "zh": "飲料廣告",
                "prompts": [
                    "A beautiful young woman drinking iced black tea at a sunny park, refreshing summer vibes, lifestyle advertisement",
                    "Premium craft beer in a frosted glass, golden bubbles, rustic wooden bar setting",
                    "Fresh fruit smoothie with strawberries and bananas, healthy lifestyle, bright colors",
                ]
            },
            "fashion": {
                "en": "Fashion Accessories",
                "zh": "時尚配飾",
                "prompts": [
                    "Designer handbag in burgundy leather, gold chain details, luxury boutique setting",
                    "Elegant silk scarf with floral pattern, flowing fabric, spring fashion shoot",
                    "Premium sunglasses with tortoise frame, beach sunset reflection, summer vibes",
                ]
            }
        }
    },
    "AI視頻創作": {
        "en": "AI Video Creation",
        "topics": {
            "nature_scenes": {
                "en": "Nature Scenes",
                "zh": "自然場景",
                "prompts": [
                    "Serene mountain lake at sunrise, mist rising from water, golden hour lighting, cinematic 4K",
                    "Cherry blossom trees in full bloom, gentle breeze, petals falling, Japanese garden",
                    "Ocean waves crashing on rocky shore, dramatic clouds, sunset colors, aerial view",
                ]
            },
            "urban_timelapse": {
                "en": "Urban Timelapse",
                "zh": "城市縮時",
                "prompts": [
                    "Busy city intersection at night, neon lights, car trails, cyberpunk atmosphere",
                    "Modern skyscraper district, glass facades reflecting clouds, time-lapse sunrise",
                    "Traditional night market with lanterns, crowd walking, food stalls, Asian city",
                ]
            },
            "food_showcase": {
                "en": "Food Showcase",
                "zh": "美食展示",
                "prompts": [
                    "Gourmet sushi platter, fresh salmon and tuna, Japanese restaurant setting, appetizing",
                    "Italian pasta with truffle sauce, steam rising, rustic wooden table, fine dining",
                    "Artisan chocolate dessert, melting chocolate drizzle, elegant plating, dark background",
                ]
            }
        }
    },
    "室內設計": {
        "en": "Interior Design",
        "topics": {
            "modern_living": {
                "en": "Modern Living Room",
                "zh": "現代客廳",
                "prompts": [
                    "Minimalist living room with floor-to-ceiling windows, white sofa, natural light, Scandinavian design",
                    "Luxury penthouse living area, city skyline view, modern art on walls, designer furniture",
                    "Cozy reading corner with built-in bookshelves, warm lighting, mid-century modern chair",
                ]
            },
            "kitchen_design": {
                "en": "Kitchen Design",
                "zh": "廚房設計",
                "prompts": [
                    "Open concept kitchen with marble island, brass fixtures, professional appliances, luxury home",
                    "Rustic farmhouse kitchen with wooden beams, copper pots, fresh herbs, warm atmosphere",
                    "Modern minimalist kitchen, white cabinets, hidden appliances, clean lines, natural light",
                ]
            }
        }
    }
}

# Video style effects for V2V
VIDEO_STYLES = {
    "anime": {"model_id": 2000, "name": "Anime Style", "zh": "動漫風格"},
    "ghibli": {"model_id": 1033, "name": "Ghibli Style", "zh": "吉卜力風格"},
    "cyberpunk": {"model_id": 2008, "name": "Cyberpunk", "zh": "賽博朋克"},
    "oil_painting": {"model_id": 2006, "name": "Oil Painting", "zh": "油畫效果"},
    "cinematic": {"model_id": 2010, "name": "Cinematic", "zh": "電影質感"},
    "watercolor": {"model_id": 2004, "name": "Watercolor", "zh": "水彩風格"},
}


class WorkflowService:
    """
    Unified workflow service for all generation pipelines.

    Workflows:
    1. T2I: Text → Wan AI → Image
    2. I2V: Text → Wan AI → Image → Pollo AI → Video
    3. V2V: Text → Wan AI → Image → Pollo AI → Video → GoEnhance → Styled Video
    4. Avatar: Script → A2E.ai → Avatar Video
    """

    def __init__(self):
        self.rescue_service = None
        self.provider_router = None
        self.pollo: Optional[PolloAIClient] = None
        self.a2e: Optional[A2EAvatarService] = None
        self._initialized = False

    def _init_services(self):
        """Initialize API services lazily."""
        if self._initialized:
            return
        self.rescue_service = get_rescue_service()
        self.provider_router = get_provider_router()
        self.pollo = get_pollo_client()
        self.a2e = get_a2e_service()
        self._initialized = True

    async def translate_prompt(self, prompt: str, target_lang: str = "en") -> str:
        """
        Translate prompt using Gemini API.

        Args:
            prompt: Text to translate
            target_lang: Target language code (en, zh-TW)

        Returns:
            Translated text
        """
        if not settings.GEMINI_API_KEY:
            logger.warning("Gemini API key not configured, skipping translation")
            return prompt

        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            # Use gemini-2.0-flash (gemini-1.5 models are deprecated)
            model = genai.GenerativeModel('gemini-2.0-flash')

            lang_name = "English" if target_lang == "en" else "Traditional Chinese (Taiwan)"
            response = await model.generate_content_async(
                f"Translate the following text to {lang_name}. Only return the translation, no explanations:\n\n{prompt}"
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return prompt

    async def detect_language(self, text: str) -> str:
        """Detect language of text (returns 'en', 'zh-TW', or 'other')"""
        # Simple detection based on character sets
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        if chinese_chars > len(text) * 0.3:
            return "zh-TW"
        elif text.isascii() or chinese_chars < len(text) * 0.1:
            return "en"
        return "other"

    async def check_duplicate(
        self,
        session: AsyncSession,
        prompt: str,
        effect_prompt: Optional[str] = None
    ) -> Optional[Material]:
        """Check if material with same prompt+effect already exists"""
        query = select(Material).where(
            and_(
                Material.prompt == prompt,
                Material.effect_prompt == effect_prompt if effect_prompt else Material.effect_prompt.is_(None)
            )
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def generate_text_to_image(
        self,
        prompt: str,
        main_topic: str = None,
        topic: str = None,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        save_to_db: bool = True
    ) -> Dict[str, Any]:
        """
        Text-to-Image workflow using Wan AI.

        Args:
            prompt: Generation prompt
            main_topic: Main category (e.g., "產品電商")
            topic: Sub-topic (e.g., "luxury_watch")
            negative_prompt: What to avoid
            width: Image width
            height: Image height
            save_to_db: Whether to save result to database

        Returns:
            Dict with success status and image URL
        """
        self._init_services()

        # Detect and translate prompt if needed
        lang = await self.detect_language(prompt)
        prompt_en = prompt if lang == "en" else await self.translate_prompt(prompt, "en")
        prompt_zh = prompt if lang == "zh-TW" else await self.translate_prompt(prompt, "zh-TW")

        # Generate image with rescue service
        result = await self.rescue_service.generate_image(
            prompt=prompt,
            width=width,
            height=height
        )

        if not result.get("success"):
            return result

        image_url = result.get("image_url")
        if not image_url and result.get("images"):
            image_url = result["images"][0]["url"]
        if not image_url:
            return {"success": False, "error": "No image generated"}

        # Save to database
        if save_to_db:
            async with AsyncSessionLocal() as session:
                # Check for duplicate
                existing = await self.check_duplicate(session, prompt)
                if existing:
                    logger.info(f"Material already exists for prompt: {prompt[:50]}...")
                    return {
                        "success": True,
                        "image_url": existing.result_image_url,
                        "material_id": str(existing.id),
                        "is_duplicate": True
                    }

                material = Material(
                    tool_type=ToolType.PRODUCT_SCENE,
                    main_topic=main_topic,
                    main_topic_zh=WORKFLOW_TOPICS.get(main_topic, {}).get("zh", main_topic),
                    topic=topic or "general",
                    topic_zh=WORKFLOW_TOPICS.get(main_topic, {}).get("topics", {}).get(topic, {}).get("zh"),
                    language=lang,
                    prompt=prompt,
                    prompt_en=prompt_en,
                    prompt_zh=prompt_zh,
                    result_image_url=image_url,
                    source=MaterialSource.SEED,
                    status=MaterialStatus.APPROVED,
                    generation_steps=[{
                        "step": 1,
                        "api": "wan",
                        "action": "text_to_image",
                        "model": result.get("model", DEFAULT_MODEL),
                        "prompt": prompt,
                        "result_url": image_url
                    }],
                    is_active=True
                )
                session.add(material)
                await session.commit()
                await session.refresh(material)

                return {
                    "success": True,
                    "image_url": image_url,
                    "material_id": str(material.id),
                    "prompt_en": prompt_en,
                    "prompt_zh": prompt_zh
                }

        return {
            "success": True,
            "image_url": image_url,
            "prompt_en": prompt_en,
            "prompt_zh": prompt_zh
        }

    async def generate_image_to_video(
        self,
        prompt: str,
        main_topic: str = None,
        topic: str = None,
        video_length: int = 5,
        save_to_db: bool = True
    ) -> Dict[str, Any]:
        """
        Image-to-Video workflow: Text → Wan AI → Image → Pollo AI → Video

        Args:
            prompt: Generation prompt for the image
            main_topic: Main category
            topic: Sub-topic
            video_length: Video length in seconds (5 or 10)
            save_to_db: Whether to save result to database

        Returns:
            Dict with success status and video URL
        """
        self._init_services()

        # Step 1: Generate image
        image_result = await self.generate_text_to_image(
            prompt=prompt,
            main_topic=main_topic,
            topic=topic,
            save_to_db=False  # We'll save the final video
        )

        if not image_result.get("success"):
            return image_result

        image_url = image_result["image_url"]
        prompt_en = image_result.get("prompt_en", prompt)
        prompt_zh = image_result.get("prompt_zh", prompt)

        # Step 2: Convert to video
        success, task_id, _ = await self.pollo.generate_video(
            image_url=image_url,
            prompt=prompt,
            length=video_length
        )

        if not success:
            return {"success": False, "error": task_id}

        # Wait for video completion
        video_result = await self.pollo.wait_for_completion(task_id, timeout=180)
        if video_result.get("status") != "succeed":
            return {"success": False, "error": video_result.get("error", "Video generation failed")}

        video_url = video_result.get("video_url")
        if not video_url:
            return {"success": False, "error": "No video URL returned"}

        # Save to database
        if save_to_db:
            async with AsyncSessionLocal() as session:
                existing = await self.check_duplicate(session, prompt)
                if existing:
                    return {
                        "success": True,
                        "video_url": existing.result_video_url,
                        "material_id": str(existing.id),
                        "is_duplicate": True
                    }

                lang = await self.detect_language(prompt)
                material = Material(
                    tool_type=ToolType.SHORT_VIDEO,
                    main_topic=main_topic,
                    main_topic_zh=WORKFLOW_TOPICS.get(main_topic, {}).get("en", main_topic),
                    topic=topic or "general",
                    language=lang,
                    prompt=prompt,
                    prompt_en=prompt_en,
                    prompt_zh=prompt_zh,
                    input_image_url=image_url,
                    result_video_url=video_url,
                    duration_seconds=video_length,
                    source=MaterialSource.SEED,
                    status=MaterialStatus.APPROVED,
                    generation_steps=[
                        {
                            "step": 1,
                            "api": "wan",
                            "action": "text_to_image",
                            "prompt": prompt,
                            "result_url": image_url
                        },
                        {
                            "step": 2,
                            "api": "pollo",
                            "action": "image_to_video",
                            "length": video_length,
                            "result_url": video_url
                        }
                    ],
                    is_active=True
                )
                session.add(material)
                await session.commit()
                await session.refresh(material)

                return {
                    "success": True,
                    "image_url": image_url,
                    "video_url": video_url,
                    "material_id": str(material.id)
                }

        return {
            "success": True,
            "image_url": image_url,
            "video_url": video_url
        }

    async def generate_video_to_video(
        self,
        prompt: str,
        style: str = "anime",
        main_topic: str = None,
        topic: str = None,
        video_length: int = 5,
        save_to_db: bool = True
    ) -> Dict[str, Any]:
        """
        Video-to-Video workflow: Text → Image → Video → Style Effect

        Args:
            prompt: Generation prompt (e.g., "A beautiful young woman drinking black tea at park")
            style: Video style to apply (anime, ghibli, cyberpunk, etc.)
            main_topic: Main category
            topic: Sub-topic
            video_length: Base video length
            save_to_db: Whether to save result

        Returns:
            Dict with success status and styled video URL
        """
        self._init_services()

        # Get style config
        style_config = VIDEO_STYLES.get(style, VIDEO_STYLES["anime"])
        effect_prompt = f"Apply {style_config['name']} style transformation"
        effect_prompt_zh = f"套用{style_config['zh']}風格轉換"

        # Step 1-2: Generate video
        video_result = await self.generate_image_to_video(
            prompt=prompt,
            main_topic=main_topic,
            topic=topic,
            video_length=video_length,
            save_to_db=False
        )

        if not video_result.get("success"):
            return video_result

        source_video_url = video_result["video_url"]
        image_url = video_result.get("image_url")
        prompt_en = video_result.get("prompt_en", prompt)
        prompt_zh = video_result.get("prompt_zh", prompt)

        # Step 3: Apply style effect with ProviderRouter V2V
        from app.services.effects_service import get_style_prompt
        style_prompt_text = get_style_prompt(style) or effect_prompt
        style_result = await self.provider_router.route(
            TaskType.V2V,
            {
                "video_url": source_video_url,
                "prompt": style_prompt_text
            }
        )

        styled_video_url = style_result.get("video_url") or style_result.get("output_url") or source_video_url

        # Save to database
        if save_to_db:
            async with AsyncSessionLocal() as session:
                existing = await self.check_duplicate(session, prompt, effect_prompt)
                if existing:
                    return {
                        "success": True,
                        "video_url": existing.result_video_url,
                        "material_id": str(existing.id),
                        "is_duplicate": True
                    }

                lang = await self.detect_language(prompt)
                material = Material(
                    tool_type=ToolType.SHORT_VIDEO,
                    main_topic=main_topic,
                    topic=topic or "general",
                    language=lang,
                    prompt=prompt,
                    prompt_en=prompt_en,
                    prompt_zh=prompt_zh,
                    effect_prompt=effect_prompt,
                    effect_prompt_zh=effect_prompt_zh,
                    input_image_url=image_url,
                    input_video_url=source_video_url,
                    result_video_url=styled_video_url,
                    duration_seconds=video_length,
                    tags=[style, style_config["name"]],
                    source=MaterialSource.SEED,
                    status=MaterialStatus.APPROVED,
                    generation_steps=[
                        {
                            "step": 1,
                            "api": "wan",
                            "action": "text_to_image",
                            "prompt": prompt,
                            "result_url": image_url
                        },
                        {
                            "step": 2,
                            "api": "pollo",
                            "action": "image_to_video",
                            "length": video_length,
                            "result_url": source_video_url
                        },
                        {
                            "step": 3,
                            "api": "goenhance",
                            "action": "video_to_video",
                            "style": style,
                            "model_id": style_config["model_id"],
                            "result_url": styled_video_url
                        }
                    ],
                    is_active=True
                )
                session.add(material)
                await session.commit()
                await session.refresh(material)

                return {
                    "success": True,
                    "source_video_url": source_video_url,
                    "styled_video_url": styled_video_url,
                    "style": style,
                    "material_id": str(material.id)
                }

        return {
            "success": True,
            "source_video_url": source_video_url,
            "styled_video_url": styled_video_url,
            "style": style
        }

    async def generate_avatar(
        self,
        script: str,
        image_url: str = None,
        language: str = "en",
        main_topic: str = None,
        topic: str = None,
        save_to_db: bool = True
    ) -> Dict[str, Any]:
        """
        Avatar generation workflow using A2E.ai.

        Args:
            script: Text script for avatar to speak
            image_url: Avatar image URL (uses default if not provided)
            language: Script language (en, zh-TW)
            main_topic: Main category
            topic: Sub-topic
            save_to_db: Whether to save result

        Returns:
            Dict with success status and avatar video URL
        """
        self._init_services()

        # Use default avatar if not provided
        if not image_url:
            default_avatars = self.a2e.get_default_avatars(language)
            image_url = default_avatars[0] if default_avatars else None

        if not image_url:
            return {"success": False, "error": "No avatar image available"}

        # Translate script if needed
        lang = await self.detect_language(script)
        script_en = script if lang == "en" else await self.translate_prompt(script, "en")
        script_zh = script if lang == "zh-TW" else await self.translate_prompt(script, "zh-TW")

        # Generate avatar video
        result = await self.a2e.generate_and_wait(
            image_url=image_url,
            script=script,
            language=language,
            timeout=300
        )

        if not result.get("success"):
            return result

        video_url = result.get("video_url")

        # Save to database
        if save_to_db:
            async with AsyncSessionLocal() as session:
                existing = await self.check_duplicate(session, script)
                if existing:
                    return {
                        "success": True,
                        "video_url": existing.result_video_url,
                        "material_id": str(existing.id),
                        "is_duplicate": True
                    }

                material = Material(
                    tool_type=ToolType.AI_AVATAR,
                    main_topic=main_topic or "AI Avatar",
                    topic=topic or "spokesperson",
                    language=language,
                    prompt=script,
                    prompt_en=script_en,
                    prompt_zh=script_zh,
                    input_image_url=image_url,
                    result_video_url=video_url,
                    source=MaterialSource.SEED,
                    status=MaterialStatus.APPROVED,
                    generation_steps=[{
                        "step": 1,
                        "api": "a2e",
                        "action": "avatar_generation",
                        "language": language,
                        "image_url": image_url,
                        "result_url": video_url
                    }],
                    is_active=True
                )
                session.add(material)
                await session.commit()
                await session.refresh(material)

                return {
                    "success": True,
                    "video_url": video_url,
                    "material_id": str(material.id)
                }

        return {
            "success": True,
            "video_url": video_url
        }

    async def generate_from_topic(
        self,
        main_topic: str,
        topic: str,
        workflow_type: str = "i2v",
        style: str = None,
        count: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Generate materials for a specific topic.

        Args:
            main_topic: Main category (e.g., "產品電商")
            topic: Sub-topic (e.g., "luxury_watch")
            workflow_type: t2i, i2v, v2v, avatar
            style: Video style for v2v workflow
            count: Number of materials to generate

        Returns:
            List of generation results
        """
        topic_config = WORKFLOW_TOPICS.get(main_topic, {}).get("topics", {}).get(topic, {})
        prompts = topic_config.get("prompts", [])

        if not prompts:
            return [{"success": False, "error": f"No prompts defined for topic: {main_topic}/{topic}"}]

        results = []
        for i, prompt in enumerate(prompts[:count]):
            logger.info(f"Generating {workflow_type} for topic {topic}: {prompt[:50]}...")

            if workflow_type == "t2i":
                result = await self.generate_text_to_image(
                    prompt=prompt,
                    main_topic=main_topic,
                    topic=topic
                )
            elif workflow_type == "i2v":
                result = await self.generate_image_to_video(
                    prompt=prompt,
                    main_topic=main_topic,
                    topic=topic
                )
            elif workflow_type == "v2v":
                result = await self.generate_video_to_video(
                    prompt=prompt,
                    style=style or "anime",
                    main_topic=main_topic,
                    topic=topic
                )
            elif workflow_type == "avatar":
                result = await self.generate_avatar(
                    script=prompt,
                    main_topic=main_topic,
                    topic=topic
                )
            else:
                result = {"success": False, "error": f"Unknown workflow type: {workflow_type}"}

            results.append(result)

            # Rate limiting
            await asyncio.sleep(2)

        return results

    async def store_user_material(
        self,
        prompt: str,
        result_url: str,
        tool_type: ToolType,
        user_id: str = None,
        effect_prompt: str = None,
        main_topic: str = None,
        topic: str = None
    ) -> Dict[str, Any]:
        """
        Store user-generated material to enrich the Material DB.

        Args:
            prompt: User's generation prompt
            result_url: Generated image/video URL
            tool_type: Type of generation
            user_id: User's ID (optional)
            effect_prompt: Effect prompt if any
            main_topic: Category
            topic: Sub-topic

        Returns:
            Dict with material_id
        """
        # Detect and translate prompt
        lang = await self.detect_language(prompt)

        # Translate if not in English or Chinese
        if lang == "other":
            prompt_en = await self.translate_prompt(prompt, "en")
            prompt_zh = await self.translate_prompt(prompt, "zh-TW")
        else:
            prompt_en = prompt if lang == "en" else await self.translate_prompt(prompt, "en")
            prompt_zh = prompt if lang == "zh-TW" else await self.translate_prompt(prompt, "zh-TW")

        async with AsyncSessionLocal() as session:
            # Check duplicate
            existing = await self.check_duplicate(session, prompt, effect_prompt)
            if existing:
                return {
                    "success": True,
                    "material_id": str(existing.id),
                    "is_duplicate": True
                }

            material = Material(
                tool_type=tool_type,
                main_topic=main_topic or "User Generated",
                topic=topic or "general",
                language=lang if lang != "other" else "en",
                prompt=prompt,
                prompt_en=prompt_en,
                prompt_zh=prompt_zh,
                effect_prompt=effect_prompt,
                result_image_url=result_url if "image" in str(tool_type).lower() else None,
                result_video_url=result_url if "video" in str(tool_type).lower() or "avatar" in str(tool_type).lower() else None,
                source=MaterialSource.USER,
                source_user_id=uuid.UUID(user_id) if user_id else None,
                status=MaterialStatus.PENDING,  # User content needs review
                is_active=False  # Inactive until approved
            )
            session.add(material)
            await session.commit()
            await session.refresh(material)

            return {
                "success": True,
                "material_id": str(material.id),
                "prompt_en": prompt_en,
                "prompt_zh": prompt_zh
            }


# Singleton instance
_workflow_service: Optional[WorkflowService] = None


def get_workflow_service() -> WorkflowService:
    """Get or create workflow service singleton"""
    global _workflow_service
    if _workflow_service is None:
        _workflow_service = WorkflowService()
    return _workflow_service
