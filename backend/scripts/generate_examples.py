"""
Pre-generate Examples for VidGo AI Platform

This script runs BEFORE the service starts to generate real AI examples:
1. Generate images using Leonardo AI
2. Convert images to videos using Leonardo Motion (5-8 sec)
3. Apply style effects using GoEnhance
4. Store results in database for display

Usage:
    python scripts/generate_examples.py

Note: This uses API credits. Run only when needed.
"""
import asyncio
import os
import sys
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.core.config import get_settings
from app.models.demo import ToolShowcase, DemoVideo
from app.services.leonardo_service import LeonardoService
from app.services.goenhance_service import GoEnhanceService, STYLE_MODELS

settings = get_settings()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Example prompts for each category
EXAMPLE_PROMPTS = {
    "product": [
        {
            "title": "智能去背",
            "title_en": "Background Removal",
            "prompt": "Professional product photo of a luxury watch on white background",
            "tool_id": "remove_background",
            "tool_category": "product"
        },
        {
            "title": "場景生成 - 奢華風格",
            "title_en": "Scene Generation - Luxury",
            "prompt": "Professional product photo of red sneakers in luxury marble setting",
            "tool_id": "generate_scene",
            "tool_category": "product",
            "scene": "luxury"
        },
        {
            "title": "場景生成 - 自然風格",
            "title_en": "Scene Generation - Nature",
            "prompt": "Wireless headphones product photo in natural outdoor setting with plants",
            "tool_id": "generate_scene",
            "tool_category": "product",
            "scene": "nature"
        }
    ],
    "video": [
        {
            "title": "圖轉影片",
            "title_en": "Image to Video",
            "prompt": "Beautiful mountain landscape with clouds moving, cinematic",
            "tool_id": "image_to_video",
            "tool_category": "video"
        },
        {
            "title": "吉卜力風格轉換",
            "title_en": "Ghibli Style Transform",
            "prompt": "Scenic countryside landscape with rolling hills",
            "tool_id": "video_transform",
            "tool_category": "video",
            "style": "ghibli"
        },
        {
            "title": "動漫風格轉換",
            "title_en": "Anime Style Transform",
            "prompt": "Forest path with sunlight filtering through trees",
            "tool_id": "video_transform",
            "tool_category": "video",
            "style": "anime"
        }
    ],
    "pattern": [
        {
            "title": "花卉圖案生成",
            "title_en": "Floral Pattern",
            "prompt": "Elegant seamless floral pattern with roses and peonies, soft colors",
            "tool_id": "pattern_generate",
            "tool_category": "pattern"
        },
        {
            "title": "幾何圖案設計",
            "title_en": "Geometric Pattern",
            "prompt": "Modern geometric seamless pattern, gold and navy colors, art deco",
            "tool_id": "pattern_generate",
            "tool_category": "pattern"
        }
    ]
}


class ExampleGenerator:
    """Generate real AI examples using Leonardo and GoEnhance APIs"""

    def __init__(self):
        self.leonardo = LeonardoService()
        self.goenhance = GoEnhanceService()
        self.engine = None
        self.session_factory = None

    async def init_db(self):
        """Initialize database connection"""
        database_url = settings.DATABASE_URL
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        self.engine = create_async_engine(database_url, echo=False)
        self.session_factory = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        logger.info("Database connection initialized")

    async def generate_image(self, prompt: str) -> Optional[str]:
        """Generate image using Leonardo AI"""
        try:
            logger.info(f"Generating image: {prompt[:50]}...")
            result = await self.leonardo.generate_image(
                prompt=prompt,
                width=1024,
                height=1024,
                num_images=1,
                use_cache=False  # Don't use cache for seed data
            )

            if result.get("success"):
                images = result.get("images", [])
                if images:
                    image_url = images[0].get("url")
                    logger.info(f"Image generated: {image_url[:50]}...")
                    return image_url
            else:
                logger.error(f"Image generation failed: {result.get('error')}")
        except Exception as e:
            logger.error(f"Image generation error: {e}")
        return None

    async def remove_background(self, image_url: str) -> Optional[str]:
        """Remove background using rembg"""
        try:
            logger.info(f"Removing background...")
            result = await self.leonardo.remove_background(
                image_url=image_url,
                use_cache=False
            )

            if result.get("success"):
                return result.get("image_url")
            else:
                logger.error(f"Background removal failed: {result.get('error')}")
        except Exception as e:
            logger.error(f"Background removal error: {e}")
        return None

    async def generate_scene(self, image_url: str, scene_prompt: str) -> Optional[str]:
        """Generate product in scene using Leonardo"""
        try:
            logger.info(f"Generating scene: {scene_prompt[:50]}...")
            result = await self.leonardo.generate_product_scene(
                product_image_url=image_url,
                scene_prompt=scene_prompt,
                use_cache=False
            )

            if result.get("success"):
                images = result.get("images", [])
                if images:
                    return images[0].get("url")
            else:
                logger.error(f"Scene generation failed: {result.get('error')}")
        except Exception as e:
            logger.error(f"Scene generation error: {e}")
        return None

    async def image_to_video(self, image_url: str, motion_strength: int = 5) -> Optional[str]:
        """Convert image to video using Leonardo Motion"""
        try:
            logger.info(f"Converting image to video...")
            result = await self.leonardo.image_to_video(
                image_url=image_url,
                motion_strength=motion_strength,
                use_cache=False
            )

            if result.get("success"):
                return result.get("video_url")
            else:
                logger.error(f"Image to video failed: {result.get('error')}")
        except Exception as e:
            logger.error(f"Image to video error: {e}")
        return None

    async def apply_style(self, video_url: str, style: str) -> Optional[str]:
        """Apply style effect using GoEnhance"""
        try:
            style_info = STYLE_MODELS.get(style)
            if not style_info:
                logger.error(f"Unknown style: {style}")
                return None

            model_id = style_info["id"]
            logger.info(f"Applying {style} style (model {model_id})...")

            result = await self.goenhance.video_to_video(
                video_url=video_url,
                model_id=model_id,
                prompt=f"{style} style, high quality",
                use_cache=False
            )

            if result.get("success"):
                return result.get("video_url")
            else:
                logger.error(f"Style application failed: {result.get('error')}")
        except Exception as e:
            logger.error(f"Style application error: {e}")
        return None

    async def save_showcase(
        self,
        session: AsyncSession,
        tool_category: str,
        tool_id: str,
        title: str,
        title_en: str,
        prompt: str,
        source_image_url: str,
        result_image_url: Optional[str] = None,
        result_video_url: Optional[str] = None,
        style: Optional[str] = None
    ) -> None:
        """Save generated example to database"""
        try:
            showcase = ToolShowcase(
                tool_category=tool_category,
                tool_id=tool_id,
                tool_name=title_en,
                tool_name_zh=title,
                source_image_url=source_image_url,
                prompt=prompt,
                prompt_zh=prompt,
                result_image_url=result_image_url,
                result_video_url=result_video_url,
                title=title,
                title_zh=title,
                style_tags=[style] if style else [],
                source_service="leonardo" if not style else "goenhance",
                is_featured=True,
                is_active=True
            )
            session.add(showcase)
            await session.commit()
            logger.info(f"Saved showcase: {title}")
        except Exception as e:
            logger.error(f"Failed to save showcase: {e}")
            await session.rollback()

    async def generate_product_examples(self, session: AsyncSession) -> None:
        """Generate product-related examples"""
        logger.info("=== Generating Product Examples ===")

        for example in EXAMPLE_PROMPTS["product"]:
            try:
                # Generate source image
                source_image = await self.generate_image(example["prompt"])
                if not source_image:
                    continue

                # Process based on tool type
                if example["tool_id"] == "remove_background":
                    result_image = await self.remove_background(source_image)
                    if result_image:
                        await self.save_showcase(
                            session,
                            example["tool_category"],
                            example["tool_id"],
                            example["title"],
                            example["title_en"],
                            example["prompt"],
                            source_image,
                            result_image_url=result_image
                        )

                elif example["tool_id"] == "generate_scene":
                    scene = example.get("scene", "studio")
                    scene_prompts = {
                        "studio": "professional studio lighting, white background",
                        "luxury": "luxury marble surface, gold accents, premium setting",
                        "nature": "natural outdoor setting, soft sunlight, greenery"
                    }
                    result_image = await self.generate_scene(
                        source_image,
                        scene_prompts.get(scene, scene_prompts["studio"])
                    )
                    if result_image:
                        await self.save_showcase(
                            session,
                            example["tool_category"],
                            example["tool_id"],
                            example["title"],
                            example["title_en"],
                            example["prompt"],
                            source_image,
                            result_image_url=result_image
                        )

                # Small delay to avoid rate limiting
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Error generating product example: {e}")

    async def generate_video_examples(self, session: AsyncSession) -> None:
        """Generate video-related examples"""
        logger.info("=== Generating Video Examples ===")

        for example in EXAMPLE_PROMPTS["video"]:
            try:
                # Generate source image
                source_image = await self.generate_image(example["prompt"])
                if not source_image:
                    continue

                # Convert to video
                video_url = await self.image_to_video(source_image, motion_strength=5)
                if not video_url:
                    continue

                # Apply style if specified
                result_video = video_url
                style = example.get("style")
                if style:
                    styled_video = await self.apply_style(video_url, style)
                    if styled_video:
                        result_video = styled_video

                await self.save_showcase(
                    session,
                    example["tool_category"],
                    example["tool_id"],
                    example["title"],
                    example["title_en"],
                    example["prompt"],
                    source_image,
                    result_video_url=result_video,
                    style=style
                )

                # Delay to avoid rate limiting
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Error generating video example: {e}")

    async def generate_pattern_examples(self, session: AsyncSession) -> None:
        """Generate pattern examples"""
        logger.info("=== Generating Pattern Examples ===")

        for example in EXAMPLE_PROMPTS["pattern"]:
            try:
                # Generate pattern image
                result = await self.leonardo.generate_pattern(
                    prompt=example["prompt"],
                    style="seamless",
                    use_cache=False
                )

                if result.get("success"):
                    images = result.get("images", [])
                    if images:
                        await self.save_showcase(
                            session,
                            example["tool_category"],
                            example["tool_id"],
                            example["title"],
                            example["title_en"],
                            example["prompt"],
                            source_image_url=images[0].get("url"),
                            result_image_url=images[0].get("url")
                        )

                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Error generating pattern example: {e}")

    async def run(self) -> None:
        """Run full example generation"""
        logger.info("Starting example generation...")

        await self.init_db()

        async with self.session_factory() as session:
            # Clear old examples
            logger.info("Clearing old showcases...")
            await session.execute(
                ToolShowcase.__table__.delete().where(
                    ToolShowcase.is_user_generated == False
                )
            )
            await session.commit()

            # Generate new examples
            await self.generate_product_examples(session)
            await self.generate_video_examples(session)
            await self.generate_pattern_examples(session)

        logger.info("Example generation complete!")


async def main():
    generator = ExampleGenerator()
    await generator.run()


if __name__ == "__main__":
    asyncio.run(main())
