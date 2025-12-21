"""
Demo Generation Service
Handles demo creation, storage, and retrieval with prompt matching.

Flow:
1. User enters prompt (any language)
2. Normalize prompt and extract keywords
3. Search database for similar demos
4. If found: return closest match
5. If not found: generate new demo via GoEnhance, save to DB, return

Daily regeneration refreshes all demos with new styles.
"""
import asyncio
import logging
import random
from typing import Optional, List, Dict, Any, Tuple
from uuid import uuid4
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.demo import ImageDemo, DemoCategory, PromptCache
from app.services.goenhance import get_goenhance_client, GOENHANCE_STYLES
from app.services.prompt_matching import get_prompt_matching_service, PromptAnalysis

logger = logging.getLogger(__name__)


# Demo topics for each category (will be randomly selected for demo page)
DEMO_TOPICS = {
    "animals": [
        "A cute cat sitting on a windowsill",
        "Golden retriever playing in the park",
        "Majestic lion in the savanna",
        "Colorful tropical fish in coral reef",
        "Playful dolphins jumping over waves",
        "Red panda sleeping on bamboo branch",
        "Butterfly landing on a flower",
        "Arctic fox in snowy landscape",
        "Horse galloping through meadow",
        "Penguin family on Antarctic ice",
    ],
    "nature": [
        "Breathtaking sunset over the ocean",
        "Majestic waterfall in tropical rainforest",
        "Cherry blossoms in full bloom",
        "Northern lights over snowy mountains",
        "Crystal clear lake reflecting mountains",
        "Autumn forest with colorful leaves",
        "Misty morning in ancient forest",
        "Desert sand dunes at golden hour",
        "Starry night sky over mountain peak",
        "Rainbow appearing after rain",
    ],
    "urban": [
        "Neon-lit Tokyo street at night",
        "New York City skyline at sunset",
        "Cozy European cafe on cobblestone street",
        "Modern glass skyscraper reflecting clouds",
        "Busy night market with lanterns",
        "Paris Eiffel Tower at dusk",
        "Traditional Japanese temple in modern city",
        "Historic castle illuminated at night",
        "Rooftop bar overlooking city lights",
        "Underground subway station with motion blur",
    ],
    "people": [
        "Dancer performing elegant ballet pose",
        "Samurai warrior in traditional armor",
        "Chef preparing gourmet dish",
        "Astronaut floating in space with Earth view",
        "Street musician playing guitar",
        "Martial artist performing high kick",
        "Photographer capturing sunset moment",
        "Yoga practitioner in meditation pose",
        "Surfer riding a massive wave",
        "Artist painting on large canvas",
    ],
    "fantasy": [
        "Majestic dragon flying over castle",
        "Mystical unicorn in enchanted forest",
        "Wizard casting spell with glowing magic",
        "Fairy with glowing wings in moonlight",
        "Phoenix rising from flames",
        "Knight in shining armor on horseback",
        "Floating islands in magical sky",
        "Portal to another dimension opening",
        "Elf archer in mystical woodland",
        "Crystal cave with magical gems",
    ],
    "sci-fi": [
        "Futuristic city with flying vehicles",
        "Robot with human-like expressions",
        "Spaceship landing on alien planet",
        "Cyberpunk hacker with neon implants",
        "Space station orbiting distant planet",
        "Time travel portal with swirling energy",
        "Mech warrior in battle stance",
        "Holographic display of galaxy map",
        "Terraformed Mars colony settlement",
        "Laser battle in space between ships",
    ],
    "food": [
        "Gourmet sushi platter with fresh fish",
        "Steaming bowl of ramen with toppings",
        "Artisan pizza fresh from wood oven",
        "Colorful macarons in pastel shades",
        "Juicy burger with all the toppings",
        "Decadent chocolate cake with ganache",
        "Traditional dim sum in bamboo steamer",
        "Coffee latte art in ceramic cup",
        "Fresh croissant with butter and jam",
        "Ice cream sundae with toppings",
    ],
}


class DemoService:
    """
    Service for demo generation, storage, and retrieval.
    Handles the full flow from prompt to displayed demo.
    """

    def __init__(self):
        self.goenhance = get_goenhance_client()
        self.matcher = get_prompt_matching_service()

    async def get_or_create_demo(
        self,
        db: AsyncSession,
        prompt: str,
        preferred_style: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main entry point: Get existing demo or create new one.

        Args:
            db: Database session
            prompt: User's prompt (any language)
            preferred_style: Optional style preference

        Returns:
            Demo data with before/after images and match info
        """
        # 1. Normalize and analyze prompt
        analysis = self.matcher.normalize_prompt(prompt)

        # 2. Search for similar demos
        similar_demos = await self.matcher.find_similar_demos(
            db=db,
            prompt=prompt,
            limit=5,
            min_score=0.3
        )

        # 3. If found, return best match
        if similar_demos:
            best_match = similar_demos[0]
            demo = best_match["demo"]

            # Update view count
            await self._increment_popularity(db, demo.id)

            return {
                "success": True,
                "found_existing": True,
                "match_score": best_match["score"],
                "matched_keywords": best_match["matched_keywords"],
                "demo": {
                    "id": str(demo.id),
                    "prompt_original": demo.prompt_original,
                    "prompt_normalized": demo.prompt_normalized,
                    "image_before": demo.image_url_before,
                    "image_after": demo.image_url_after,
                    "style_name": demo.style_name,
                    "style_slug": demo.style_slug,
                    "category": demo.category_slug,
                }
            }

        # 4. No match found - generate new demo
        return await self._generate_and_save_demo(
            db=db,
            analysis=analysis,
            preferred_style=preferred_style
        )

    async def _generate_and_save_demo(
        self,
        db: AsyncSession,
        analysis: PromptAnalysis,
        preferred_style: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate new demo via GoEnhance and save to database"""

        # Select style (use preferred or random)
        style_id, style_info = self._select_style(analysis, preferred_style)

        # Need source video - use a placeholder for now
        # In production, you'd have a library of source videos per category
        source_video = await self._get_source_video(analysis.category)

        if not source_video:
            return {
                "success": False,
                "found_existing": False,
                "error": "No source video available for generation",
                "suggestion": "Please try a different prompt or style"
            }

        # Generate via GoEnhance
        logger.info(f"Generating demo: {analysis.normalized[:50]}... with style {style_info['name']}")

        result = await self.goenhance.generate_image_demo(
            source_video_url=source_video,
            model_id=style_id,
            prompt=analysis.normalized
        )

        if not result.get("success"):
            return {
                "success": False,
                "found_existing": False,
                "error": result.get("error", "Generation failed"),
                "suggestion": "Please try again later or use a different style"
            }

        # Save to database
        demo = ImageDemo(
            id=uuid4(),
            prompt_original=analysis.original,
            prompt_normalized=analysis.normalized,
            prompt_language=analysis.language,
            keywords=analysis.keywords,
            keywords_json={"extracted": analysis.keywords},
            category_slug=analysis.category,
            image_url_before=source_video,
            image_url_after=result.get("video_url"),  # Video URL for GIF-like effect
            thumbnail_url=result.get("thumbnail_url"),
            style_id=style_id,
            style_name=style_info["name"],
            style_slug=style_info["slug"],
            task_id=result.get("task_id"),
            generation_params={"prompt": analysis.normalized},
            status="completed",
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(days=1)  # Expire after 1 day
        )

        db.add(demo)
        await db.commit()

        logger.info(f"Demo saved: {demo.id}")

        return {
            "success": True,
            "found_existing": False,
            "match_score": 1.0,
            "generated_new": True,
            "demo": {
                "id": str(demo.id),
                "prompt_original": demo.prompt_original,
                "prompt_normalized": demo.prompt_normalized,
                "image_before": demo.image_url_before,
                "image_after": demo.image_url_after,
                "style_name": demo.style_name,
                "style_slug": demo.style_slug,
                "category": demo.category_slug,
            }
        }

    def _select_style(
        self,
        analysis: PromptAnalysis,
        preferred_style: Optional[str] = None
    ) -> Tuple[int, Dict[str, Any]]:
        """Select style for generation"""
        # If preferred style specified
        if preferred_style:
            for style_id, info in GOENHANCE_STYLES.items():
                if info["slug"] == preferred_style or info["name"].lower() == preferred_style.lower():
                    return style_id, info

        # If style detected from prompt
        if analysis.style:
            for style_id, info in GOENHANCE_STYLES.items():
                if info["slug"] == analysis.style:
                    return style_id, info

        # Random selection
        style_id = random.choice(list(GOENHANCE_STYLES.keys()))
        return style_id, GOENHANCE_STYLES[style_id]

    async def _get_source_video(self, category: Optional[str]) -> Optional[str]:
        """
        Get source video for transformation.
        In production, this would select from a library of videos per category.
        """
        # Placeholder videos - you need to provide real source videos
        source_videos = {
            "animals": "https://cdn.goenhance.ai/user/upload-data/video-to-video/333768e610e442d02e8030693def0b6e.mp4",
            "nature": "https://cdn.goenhance.ai/user/upload-data/video-to-video/333768e610e442d02e8030693def0b6e.mp4",
            "default": "https://cdn.goenhance.ai/user/upload-data/video-to-video/333768e610e442d02e8030693def0b6e.mp4",
        }

        return source_videos.get(category, source_videos["default"])

    async def _increment_popularity(self, db: AsyncSession, demo_id) -> None:
        """Increment demo popularity score"""
        await db.execute(
            update(ImageDemo)
            .where(ImageDemo.id == demo_id)
            .values(popularity_score=ImageDemo.popularity_score + 1)
        )
        await db.commit()

    async def get_random_demo_for_display(
        self,
        db: AsyncSession,
        category: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get random demo for displaying on demo page.
        Used for "Show me an example" functionality.
        """
        demo = await self.matcher.get_random_demo(db, category=category)

        if demo:
            return {
                "id": str(demo.id),
                "prompt": demo.prompt_original,
                "prompt_normalized": demo.prompt_normalized,
                "image_before": demo.image_url_before,
                "image_after": demo.image_url_after,
                "style_name": demo.style_name,
                "category": demo.category_slug,
            }

        # If no demos in DB, return a sample prompt
        if category and category in DEMO_TOPICS:
            topics = DEMO_TOPICS[category]
        else:
            all_topics = []
            for topics in DEMO_TOPICS.values():
                all_topics.extend(topics)
            topics = all_topics

        sample_prompt = random.choice(topics)
        sample_style = random.choice(list(GOENHANCE_STYLES.values()))

        return {
            "id": None,
            "prompt": sample_prompt,
            "prompt_normalized": sample_prompt.lower(),
            "image_before": None,
            "image_after": None,
            "style_name": sample_style["name"],
            "category": category,
            "is_sample": True  # Indicates this is a sample, not actual demo
        }

    async def regenerate_demos(
        self,
        db: AsyncSession,
        count_per_category: int = 15,
        styles_per_topic: int = 2
    ) -> Dict[str, Any]:
        """
        Regenerate demos for all categories.
        Called by daily scheduled task.
        """
        logger.info(f"Starting demo regeneration: {count_per_category} per category")

        results = {
            "started_at": datetime.utcnow().isoformat(),
            "categories": {},
            "total_generated": 0,
            "total_failed": 0
        }

        for category, topics in DEMO_TOPICS.items():
            category_results = {"generated": 0, "failed": 0, "demos": []}

            # Select random topics
            selected_topics = random.sample(topics, min(count_per_category, len(topics)))

            for topic in selected_topics:
                # Select random styles
                style_ids = random.sample(list(GOENHANCE_STYLES.keys()), min(styles_per_topic, len(GOENHANCE_STYLES)))

                for style_id in style_ids:
                    try:
                        analysis = self.matcher.normalize_prompt(topic)
                        analysis.category = category  # Force category

                        result = await self._generate_and_save_demo(
                            db=db,
                            analysis=analysis,
                            preferred_style=GOENHANCE_STYLES[style_id]["slug"]
                        )

                        if result.get("success"):
                            category_results["generated"] += 1
                            category_results["demos"].append(result.get("demo", {}).get("id"))
                        else:
                            category_results["failed"] += 1

                    except Exception as e:
                        logger.error(f"Failed to generate demo: {e}")
                        category_results["failed"] += 1

                    # Rate limiting - don't overwhelm the API
                    await asyncio.sleep(2)

            results["categories"][category] = category_results
            results["total_generated"] += category_results["generated"]
            results["total_failed"] += category_results["failed"]

        results["completed_at"] = datetime.utcnow().isoformat()
        logger.info(f"Demo regeneration complete: {results['total_generated']} generated, {results['total_failed']} failed")

        return results

    async def cleanup_expired_demos(self, db: AsyncSession) -> int:
        """Remove expired demos (older than 1 day)"""
        query = select(ImageDemo).where(
            and_(
                ImageDemo.expires_at < datetime.utcnow(),
                ImageDemo.is_active == True
            )
        )
        result = await db.execute(query)
        expired = result.scalars().all()

        count = len(expired)
        for demo in expired:
            demo.is_active = False

        await db.commit()
        logger.info(f"Cleaned up {count} expired demos")

        return count


# Singleton instance
_demo_service: Optional[DemoService] = None


def get_demo_service() -> DemoService:
    """Get or create demo service singleton"""
    global _demo_service
    if _demo_service is None:
        _demo_service = DemoService()
    return _demo_service
