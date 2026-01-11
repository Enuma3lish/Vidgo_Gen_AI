"""
Demo Generation Service
Handles demo creation, storage, and retrieval with prompt matching.

Full Pipeline Flow ("See It In Action"):
1. User enters prompt → PiAPI Wan (text-to-image)
2. Generated image → Pollo AI (image-to-video)
3. Generated video → PiAPI Wan VACE (video enhancement with style)

Pre-generated Demos ("Explore Categories"):
- Demos are pre-generated for each category with multiple styles
- Stored in PostgreSQL for instant retrieval
- Randomly selected to save API credits

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

from app.models.demo import ImageDemo, DemoCategory, DemoVideo, PromptCache
from app.services.pollo_ai import get_pollo_client, POLLO_MODELS
from app.services.prompt_matching import get_prompt_matching_service, PromptAnalysis
from app.services.watermark import get_watermark_service
from app.providers import ProviderRouter, TaskType

logger = logging.getLogger(__name__)

# Style definitions for demo generation (replaces GOENHANCE_STYLES)
DEMO_STYLES = {
    "anime": {"name": "Anime Style", "slug": "anime", "prompt": "anime style"},
    "realistic": {"name": "Realistic", "slug": "realistic", "prompt": "realistic photorealistic"},
    "cinematic": {"name": "Cinematic", "slug": "cinematic", "prompt": "cinematic movie style"},
    "cartoon": {"name": "Cartoon", "slug": "cartoon", "prompt": "cartoon style"},
    "watercolor": {"name": "Watercolor", "slug": "watercolor", "prompt": "watercolor painting style"},
}

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
    Handles the full pipeline from prompt to displayed demo.

    Pipeline:
    1. PiAPI Wan: Text → Image
    2. Pollo AI: Image → Video
    3. PiAPI Wan VACE: Video → Enhanced Video (optional)
    """

    def __init__(self):
        self.router = ProviderRouter()
        self.pollo = get_pollo_client()
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
        """
        Generate new demo using the full pipeline and save to database.

        Pipeline:
        1. PiAPI Wan: Prompt → Image
        2. Pollo AI Pixverse: Image → Video
        3. PiAPI Wan VACE: Video → Enhanced Video (optional)
        """
        # Select style for generation
        style_id, style_info = self._select_style(analysis, preferred_style)

        logger.info(f"Starting demo pipeline: {analysis.normalized[:50]}...")
        logger.info(f"Selected style: {style_info['name']}")

        # =========================================
        # Step 1: Generate Image (PiAPI Wan T2I)
        # =========================================
        logger.info("Step 1: Generating image with PiAPI Wan...")

        try:
            image_result = await self.router.route(
                TaskType.T2I,
                {"prompt": f"{analysis.normalized}, {style_info.get('prompt', '')}"}
            )
        except Exception as e:
            return {
                "success": False,
                "found_existing": False,
                "error": f"Image generation failed: {str(e)}",
                "suggestion": "Please try again with a different prompt"
            }

        if not image_result.get("success") and not image_result.get("image_url"):
            return {
                "success": False,
                "found_existing": False,
                "error": f"Image generation failed: {image_result.get('error')}",
                "suggestion": "Please try again with a different prompt"
            }

        image_url = image_result.get("image_url") or image_result.get("output_url")
        logger.info(f"Step 1 complete: Image generated at {image_url}")

        # =========================================
        # Step 2: Generate Video (Pollo AI)
        # =========================================
        logger.info("Step 2: Generating video with Pollo AI...")

        video_result = await self.pollo.generate_and_wait(
            image_url=image_url,
            prompt=analysis.normalized,
            model="pixverse_v4.5",
            timeout=300
        )

        if not video_result.get("success"):
            # Even if video fails, we still have the image - save partial result
            logger.warning(f"Video generation failed: {video_result.get('error')}")
            video_url = None
        else:
            video_url = video_result.get("video_url")
            logger.info(f"Step 2 complete: Video generated at {video_url}")

        # =========================================
        # Step 3: Enhance Video (PiAPI Wan VACE) - Optional
        # =========================================
        enhanced_video_url = None
        if video_url:
            logger.info(f"Step 3: Enhancing video with PiAPI Wan VACE ({style_info['name']})...")

            try:
                enhance_result = await self.router.route(
                    TaskType.V2V,
                    {
                        "video_url": video_url,
                        "prompt": f"{analysis.normalized}, {style_info.get('prompt', '')}"
                    }
                )

                if enhance_result.get("video_url") or enhance_result.get("output_url"):
                    enhanced_video_url = enhance_result.get("video_url") or enhance_result.get("output_url")
                    logger.info(f"Step 3 complete: Enhanced video at {enhanced_video_url}")
                else:
                    logger.warning("Video enhancement failed, using original video")
                    enhanced_video_url = video_url
            except Exception as e:
                logger.warning(f"Video enhancement failed: {e}")
                # Use original video if enhancement fails
                enhanced_video_url = video_url

        # =========================================
        # Save to database
        # =========================================
        demo = ImageDemo(
            id=uuid4(),
            prompt_original=analysis.original,
            prompt_normalized=analysis.normalized,
            prompt_language=analysis.language,
            keywords=analysis.keywords,
            keywords_json={"extracted": analysis.keywords},
            category_slug=analysis.category,
            image_url_before=image_url,  # Original generated image
            image_url_after=enhanced_video_url or video_url,  # Enhanced or original video
            thumbnail_url=image_url,  # Use image as thumbnail
            style_id=style_id,
            style_name=style_info["name"],
            style_slug=style_info["slug"],
            task_id=image_result.get("task_id"),
            generation_params={
                "prompt": analysis.normalized,
                "pipeline": "nano_banana_to_pixverse_to_v2v",
                "image_url": image_url,
                "video_url": video_url,
                "enhanced_video_url": enhanced_video_url
            },
            status="completed",
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(days=7)  # Expire after 7 days
        )

        db.add(demo)
        await db.commit()

        logger.info(f"Demo pipeline complete! Saved as: {demo.id}")

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
                "video_url": video_url,
                "enhanced_video_url": enhanced_video_url,
                "style_name": demo.style_name,
                "style_slug": demo.style_slug,
                "category": demo.category_slug,
            }
        }

    def _select_style(
        self,
        analysis: PromptAnalysis,
        preferred_style: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Select style for generation"""
        # If preferred style specified
        if preferred_style:
            for style_id, info in DEMO_STYLES.items():
                if info["slug"] == preferred_style or info["name"].lower() == preferred_style.lower():
                    return style_id, info

        # If style detected from prompt
        if analysis.style:
            for style_id, info in DEMO_STYLES.items():
                if info["slug"] == analysis.style:
                    return style_id, info

        # Random selection
        style_id = random.choice(list(DEMO_STYLES.keys()))
        return style_id, DEMO_STYLES[style_id]

    async def generate_image_only(
        self,
        prompt: str,
        style_slug: Optional[str] = None,
        add_watermark: bool = True
    ) -> Dict[str, Any]:
        """
        Generate image only (with watermark) for "Generate Demo" feature.
        This is Step 1 of the demo flow.

        Args:
            prompt: User's prompt text
            style_slug: Optional style for image generation
            add_watermark: Whether to add watermark (default True for demos)

        Returns:
            Dict with image_url (watermarked if add_watermark=True)
        """
        logger.info(f"Generating image only: {prompt[:50]}...")

        # Select style
        style_info = DEMO_STYLES.get("anime", {"name": "Anime Style", "slug": "anime", "prompt": "anime style"})

        if style_slug:
            for sid, info in DEMO_STYLES.items():
                if info["slug"] == style_slug:
                    style_info = info
                    break

        # Generate image with PiAPI Wan T2I
        try:
            image_result = await self.router.route(
                TaskType.T2I,
                {"prompt": f"{prompt}, {style_info.get('prompt', '')}"}
            )
        except Exception as e:
            return {
                "success": False,
                "error": f"Image generation failed: {str(e)}"
            }

        image_url = image_result.get("image_url") or image_result.get("output_url")
        if not image_url:
            return {
                "success": False,
                "error": f"Image generation failed: {image_result.get('error')}"
            }

        original_url = image_url
        logger.info(f"Image generated: {image_url}")

        # Add watermark for demo images
        if add_watermark and image_url:
            watermark_service = get_watermark_service()
            success, watermarked_url, _ = await watermark_service.add_watermark_to_image_url(
                image_url,
                watermark_text="VidGo Demo"
            )
            if success and watermarked_url:
                image_url = watermarked_url
                logger.info("Watermark added to image")

        return {
            "success": True,
            "image_url": image_url,
            "original_url": original_url,  # Keep original for video generation
            "style_name": style_info["name"],
            "style_slug": style_info["slug"]
        }

    async def generate_video_from_image(
        self,
        prompt: str,
        image_url: Optional[str] = None,
        style_slug: Optional[str] = None,
        skip_v2v: bool = True
    ) -> Dict[str, Any]:
        """
        Generate video from an existing image for "See It In Action" feature.
        This is Step 2 of the demo flow.

        If image_url is not provided, generates a new image first.

        Args:
            prompt: User's prompt text (for video motion description)
            image_url: Pre-generated image URL (from Step 1)
            style_slug: Optional style for V2V enhancement
            skip_v2v: Skip V2V enhancement (default True for current version)

        Returns:
            Dict with video_url
        """
        logger.info(f"Generating video from image: {prompt[:50]}...")

        # Select style
        style_info = DEMO_STYLES.get("anime", {"name": "Anime Style", "slug": "anime", "prompt": "anime style"})

        if style_slug:
            for sid, info in DEMO_STYLES.items():
                if info["slug"] == style_slug:
                    style_info = info
                    break

        result = {
            "success": False,
            "prompt": prompt,
            "style_name": style_info["name"],
            "style_slug": style_info["slug"],
            "steps": []
        }

        # =========================================
        # Step 1: Generate Image if not provided
        # =========================================
        if not image_url:
            logger.info("No image provided, generating new image...")
            result["steps"].append({"step": 1, "name": "Image Generation", "status": "in_progress"})

            try:
                image_result = await self.router.route(
                    TaskType.T2I,
                    {"prompt": f"{prompt}, {style_info.get('prompt', '')}"}
                )
                image_url = image_result.get("image_url") or image_result.get("output_url")
                if not image_url:
                    result["steps"][-1]["status"] = "failed"
                    result["error"] = f"Image generation failed: {image_result.get('error')}"
                    return result
            except Exception as e:
                result["steps"][-1]["status"] = "failed"
                result["error"] = f"Image generation failed: {str(e)}"
                return result

            result["steps"][-1]["status"] = "completed"
            logger.info(f"Image generated: {image_url}")
        else:
            logger.info(f"Using provided image: {image_url}")
            result["steps"].append({"step": 1, "name": "Image (Pre-generated)", "status": "completed"})

        result["image_url"] = image_url

        # =========================================
        # Step 2: Generate Video (Pollo AI)
        # =========================================
        logger.info("Generating video with Pollo AI...")
        result["steps"].append({"step": 2, "name": "Video Generation", "status": "in_progress"})

        video_result = await self.pollo.generate_and_wait(
            image_url=image_url,
            prompt=prompt,
            model="pixverse_v4.5",
            timeout=300
        )

        if not video_result.get("success"):
            result["steps"][-1]["status"] = "failed"
            result["error"] = f"Video generation failed: {video_result.get('error')}"
            # Still return partial success with image
            result["success"] = True
            result["partial"] = True
            return result

        video_url = video_result.get("video_url")
        result["video_url"] = video_url
        result["steps"][-1]["status"] = "completed"
        logger.info(f"Video generated: {video_url}")

        # =========================================
        # Step 3: Enhance Video (PiAPI Wan VACE) - Optional
        # Current version: skip_v2v=True by default
        # =========================================
        if not skip_v2v and video_url:
            logger.info(f"Enhancing video with PiAPI Wan VACE ({style_info['name']})...")
            result["steps"].append({"step": 3, "name": "Video Enhancement", "status": "in_progress"})

            try:
                enhance_result = await self.router.route(
                    TaskType.V2V,
                    {
                        "video_url": video_url,
                        "prompt": f"{prompt}, {style_info.get('prompt', '')}"
                    }
                )

                enhanced_url = enhance_result.get("video_url") or enhance_result.get("output_url")
                if enhanced_url:
                    result["enhanced_video_url"] = enhanced_url
                    result["steps"][-1]["status"] = "completed"
                    logger.info(f"Video enhanced: {result['enhanced_video_url']}")
                else:
                    result["steps"][-1]["status"] = "skipped"
                    logger.warning("V2V enhancement failed, using original video")
            except Exception as e:
                result["steps"][-1]["status"] = "skipped"
                logger.warning(f"V2V enhancement failed: {e}, using original video")

        result["success"] = True
        logger.info("Video generation complete!")
        return result

    async def generate_demo_realtime(
        self,
        prompt: str,
        style_slug: Optional[str] = None,
        skip_v2v: bool = True
    ) -> Dict[str, Any]:
        """
        Legacy method - calls generate_video_from_image for backward compatibility.
        """
        return await self.generate_video_from_image(
            prompt=prompt,
            image_url=None,
            style_slug=style_slug,
            skip_v2v=skip_v2v
        )

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
        sample_style = random.choice(list(DEMO_STYLES.values()))

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
                style_ids = random.sample(list(DEMO_STYLES.keys()), min(styles_per_topic, len(DEMO_STYLES)))

                for style_id in style_ids:
                    try:
                        analysis = self.matcher.normalize_prompt(topic)
                        analysis.category = category  # Force category

                        result = await self._generate_and_save_demo(
                            db=db,
                            analysis=analysis,
                            preferred_style=DEMO_STYLES[style_id]["slug"]
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

    # =========================================================================
    # Category Video Methods (Explore Categories)
    # =========================================================================

    async def get_category_video_count(
        self,
        db: AsyncSession,
        category_slug: str
    ) -> int:
        """Get count of active videos for a category"""
        query = select(func.count(DemoVideo.id)).where(
            and_(
                DemoVideo.category_slug == category_slug,
                DemoVideo.is_active == True
            )
        )
        result = await db.execute(query)
        return result.scalar() or 0

    async def get_random_category_videos(
        self,
        db: AsyncSession,
        category_slug: str,
        count: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get random videos for a category for Explore Categories display.

        Args:
            db: Database session
            category_slug: Category slug (e.g., "animals", "nature")
            count: Number of videos to return (default 3)

        Returns:
            List of video dictionaries
        """
        query = select(DemoVideo).where(
            and_(
                DemoVideo.category_slug == category_slug,
                DemoVideo.is_active == True
            )
        ).order_by(func.random()).limit(count)

        result = await db.execute(query)
        videos = result.scalars().all()

        return [
            {
                "id": str(v.id),
                "title": v.title,
                "prompt": v.prompt,
                "video_url": v.video_url,
                "thumbnail_url": v.thumbnail_url or v.image_url,
                "duration": v.duration_seconds,
                "style": v.style,
                "category": v.category_slug
            }
            for v in videos
        ]

    async def generate_category_video(
        self,
        db: AsyncSession,
        prompt: str,
        category_slug: str,
        style_slug: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a single video for a category and save to database.

        Args:
            db: Database session
            prompt: Prompt for video generation
            category_slug: Category this video belongs to
            style_slug: Optional style for image generation

        Returns:
            Dict with video info or error
        """
        logger.info(f"Generating category video: {prompt[:50]}... [{category_slug}]")

        # Step 1: Generate image (without watermark for video)
        try:
            style_prompt = ""
            if style_slug and style_slug in DEMO_STYLES:
                style_prompt = DEMO_STYLES[style_slug].get("prompt", "")

            image_result = await self.router.route(
                TaskType.T2I,
                {"prompt": f"{prompt}, {style_prompt}".strip(", ")}
            )
        except Exception as e:
            return {
                "success": False,
                "error": f"Image generation failed: {str(e)}"
            }

        image_url = image_result.get("image_url") or image_result.get("output_url")
        if not image_url:
            return {
                "success": False,
                "error": f"Image generation failed: {image_result.get('error')}"
            }
        logger.info(f"Image generated: {image_url}")

        # Step 2: Generate video (5 seconds)
        video_result = await self.pollo.generate_and_wait(
            image_url=image_url,
            prompt=prompt,
            model="pixverse_v4.5",
            timeout=300
        )

        if not video_result.get("success"):
            return {
                "success": False,
                "error": f"Video generation failed: {video_result.get('error')}"
            }

        video_url = video_result.get("video_url")
        logger.info(f"Video generated: {video_url}")

        # Step 3: Save to database
        video = DemoVideo(
            id=uuid4(),
            title=prompt[:100],
            prompt=prompt,
            category_slug=category_slug,
            image_url=image_url,
            video_url=video_url,
            thumbnail_url=image_url,
            duration_seconds=5.0,
            style=style_slug,
            style_slug=style_slug,
            source_service="pollo_ai",
            generation_params={
                "prompt": prompt,
                "style": style_slug,
                "model": "pixverse_v4.5"
            },
            is_active=True
        )

        db.add(video)
        await db.commit()

        logger.info(f"Category video saved: {video.id}")

        return {
            "success": True,
            "video_id": str(video.id),
            "video_url": video_url,
            "image_url": image_url,
            "prompt": prompt,
            "category": category_slug
        }

    async def generate_category_videos_batch(
        self,
        db: AsyncSession,
        category_slug: str,
        prompts: List[str],
        target_count: int = 30
    ) -> Dict[str, Any]:
        """
        Generate multiple videos for a category.
        Will stop when target_count is reached.

        Args:
            db: Database session
            category_slug: Category to generate for
            prompts: List of prompts to use
            target_count: Target number of videos (default 30)

        Returns:
            Dict with generation results
        """
        current_count = await self.get_category_video_count(db, category_slug)

        if current_count >= target_count:
            return {
                "success": True,
                "message": f"Category {category_slug} already has {current_count} videos",
                "generated": 0,
                "total": current_count
            }

        to_generate = min(len(prompts), target_count - current_count)
        generated = 0
        failed = 0

        for i, prompt in enumerate(prompts[:to_generate]):
            try:
                result = await self.generate_category_video(
                    db=db,
                    prompt=prompt,
                    category_slug=category_slug
                )

                if result.get("success"):
                    generated += 1
                else:
                    failed += 1
                    logger.warning(f"Failed to generate video {i+1}: {result.get('error')}")

                # Rate limiting - 2 second delay between generations
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Error generating video {i+1}: {e}")
                failed += 1

        final_count = await self.get_category_video_count(db, category_slug)

        return {
            "success": True,
            "message": f"Generated {generated} videos for {category_slug}",
            "generated": generated,
            "failed": failed,
            "total": final_count
        }


# Singleton instance
_demo_service: Optional[DemoService] = None


def get_demo_service() -> DemoService:
    """Get or create demo service singleton"""
    global _demo_service
    if _demo_service is None:
        _demo_service = DemoService()
    return _demo_service
