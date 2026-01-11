"""
Workflow Generator Service - Prompt Chaining Implementation

Implements the Prompt Chaining Design workflow:

┌─────────────────────────────────────────────────────────────────┐
│  Step 1: Topic Definition                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  id: "luxury_watch"                                       │  │
│  │  category: "product_video"                                │  │
│  │  output_type: "video"  ← Determines final output type     │  │
│  │  subject: "luxury wristwatch"                             │  │
│  │  mood: "elegant, sophisticated, premium"                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                     │
│                           ▼                                     │
│  Step 2: Image Prompt (derived from topic)                      │
│  Step 3: AI Generate Image                                      │
│  Step 4: Route by output_type (video → I2V, image → done)       │
│  Step 5: Effect Prompt (for video)                              │
│  Step 6: Generate Video                                         │
└─────────────────────────────────────────────────────────────────┘

Supports all category flows:
- product_video: T2I (Wan) → I2V (Wan/fal.ai)
- interior_design: Wan Doodle → Gemini (rescue)
- style_transfer: T2I → I2V → V2V (GoEnhance)
- avatar: A2E.ai Avatar API
- t2i_showcase: Wan T2I (patterns/textures)
"""
import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from dataclasses import dataclass, field

from app.config.demo_topics import (
    TopicDefinition,
    TopicCategory,
    OutputType,
    get_all_topics,
    get_topics_by_category,
    get_topic_by_id,
    CATEGORY_OUTPUT_MAP,
)
from app.services.rescue_service import get_rescue_service
from app.services.interior_design_service import get_interior_design_service
from app.services.a2e_service import get_a2e_service
from app.services.pollo_ai import get_pollo_client
from app.providers.provider_router import get_provider_router, TaskType

logger = logging.getLogger(__name__)

# Static directory for generated materials
STATIC_DIR = Path("/app/static/generated")


@dataclass
class GenerationResult:
    """Result of a generation workflow."""
    success: bool
    topic_id: str
    category: TopicCategory
    output_type: OutputType
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    error: Optional[str] = None
    steps_completed: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "success": self.success,
            "topic_id": self.topic_id,
            "category": self.category.value,
            "output_type": self.output_type.value,
            "image_url": self.image_url,
            "video_url": self.video_url,
            "error": self.error,
            "steps_completed": self.steps_completed,
            "metadata": self.metadata,
            "duration_seconds": self.duration_seconds,
        }


class WorkflowGenerator:
    """
    Unified workflow generator implementing prompt chaining.

    Routes generation based on topic category:
    - product_video: Wan T2I → Wan/fal.ai I2V
    - interior_design: Wan Doodle → Gemini (rescue)
    - style_transfer: Wan T2I → I2V → GoEnhance V2V
    - avatar: A2E.ai Avatar API
    - t2i_showcase: Wan T2I (patterns/textures)
    """

    def __init__(self):
        self.rescue_service = None  # AI rescue service (Wan primary, fal.ai rescue)
        self.provider_router = None
        self.pollo = None
        self.avatar_service = None
        self.interior_service = None
        self._initialized = False

    def _init_services(self):
        """Initialize API services lazily."""
        if self._initialized:
            return

        self.rescue_service = get_rescue_service()
        self.provider_router = get_provider_router()
        self.pollo = get_pollo_client()
        self.avatar_service = get_a2e_service()
        self.interior_service = get_interior_design_service()
        self._initialized = True

    async def generate_from_topic(
        self,
        topic: TopicDefinition,
        save_locally: bool = True
    ) -> GenerationResult:
        """
        Main entry point: Generate content from a topic definition.

        This method implements the complete prompt chaining workflow:
        1. Build image prompt from topic
        2. Route to appropriate generator based on category
        3. If video output, chain to video generation
        4. Return final result

        Args:
            topic: TopicDefinition with all parameters
            save_locally: Whether to save files to static directory

        Returns:
            GenerationResult with URLs and metadata
        """
        self._init_services()
        start_time = datetime.now()

        logger.info(f"Starting workflow for topic: {topic.id}")
        logger.info(f"  Category: {topic.category.value}")
        logger.info(f"  Output Type: {topic.output_type.value}")

        # Route based on category
        category_handlers = {
            TopicCategory.PRODUCT_VIDEO: self._generate_product_video,
            TopicCategory.INTERIOR_DESIGN: self._generate_interior_design,
            TopicCategory.STYLE_TRANSFER: self._generate_style_transfer,
            TopicCategory.AVATAR: self._generate_avatar,
            TopicCategory.T2I_SHOWCASE: self._generate_t2i_showcase,
        }

        handler = category_handlers.get(topic.category)
        if not handler:
            return GenerationResult(
                success=False,
                topic_id=topic.id,
                category=topic.category,
                output_type=topic.output_type,
                error=f"Unknown category: {topic.category.value}"
            )

        try:
            result = await handler(topic, save_locally)
            result.duration_seconds = (datetime.now() - start_time).total_seconds()
            return result

        except Exception as e:
            logger.error(f"Workflow failed for {topic.id}: {e}")
            return GenerationResult(
                success=False,
                topic_id=topic.id,
                category=topic.category,
                output_type=topic.output_type,
                error=str(e),
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )

    # =========================================================================
    # PRODUCT VIDEO: T2I → I2V
    # =========================================================================

    async def _generate_product_video(
        self,
        topic: TopicDefinition,
        save_locally: bool
    ) -> GenerationResult:
        """
        Product Video workflow: Leonardo T2I → Pollo I2V

        Flow:
        1. Build image prompt from topic
        2. Generate image with Leonardo
        3. Build effect prompt from topic
        4. Generate video with Pollo AI
        """
        result = GenerationResult(
            success=False,
            topic_id=topic.id,
            category=topic.category,
            output_type=topic.output_type
        )

        # Step 1: Build image prompt
        image_prompt = topic.build_image_prompt()
        logger.info(f"Step 1: Image prompt built")
        logger.debug(f"  Prompt: {image_prompt[:100]}...")
        result.steps_completed.append("image_prompt_built")

        # Step 2: Generate image with rescue service (Wan primary, fal.ai rescue)
        logger.info(f"Step 2: Generating image with Wan...")
        image_result = await self.rescue_service.generate_image(
            prompt=image_prompt,
            width=1024,
            height=1024
        )

        if not image_result.get("success"):
            result.error = f"Image generation failed: {image_result.get('error', 'No images')}"
            return result

        image_url = image_result.get("image_url")
        if not image_url and image_result.get("images"):
            image_url = image_result["images"][0]["url"]
        result.image_url = image_url
        result.steps_completed.append("image_generated")
        logger.info(f"Step 2 complete: Image at {image_url[:50]}...")

        # Step 3: Build effect prompt
        effect_prompt = topic.build_effect_prompt()
        logger.info(f"Step 3: Effect prompt built")
        result.steps_completed.append("effect_prompt_built")

        # Step 4: Generate video with rescue service (Wan primary, fal.ai rescue)
        logger.info(f"Step 4: Generating video with rescue service...")
        video_result = await self.rescue_service.generate_video(
            image_url=image_url,
            prompt=effect_prompt,
            length=5
        )

        if not video_result.get("success"):
            result.error = f"Video generation failed: {video_result.get('error')}"
            # Still return image even if video fails
            result.success = True
            result.metadata["partial"] = True
            return result

        video_url = video_result.get("video_url")
        result.video_url = video_url
        result.steps_completed.append("video_generated")
        logger.info(f"Step 4 complete: Video at {video_url[:50] if video_url else 'N/A'}...")

        result.success = True
        result.metadata["model"] = video_result.get("model", "pixverse_v4.5")

        return result

    # =========================================================================
    # INTERIOR DESIGN: Gemini 2.5 Flash Image (T2I Only)
    # =========================================================================

    async def _generate_interior_design(
        self,
        topic: TopicDefinition,
        save_locally: bool
    ) -> GenerationResult:
        """
        Interior Design workflow: Gemini 2.5 Flash Image

        Flow:
        1. Build prompt from topic (room type + style)
        2. Generate image with Gemini
        3. Output: Static image (no video)
        """
        result = GenerationResult(
            success=False,
            topic_id=topic.id,
            category=topic.category,
            output_type=topic.output_type
        )

        # Step 1: Build prompt
        image_prompt = topic.build_image_prompt()
        logger.info(f"Step 1: Interior design prompt built")
        result.steps_completed.append("prompt_built")

        # Step 2: Generate with Gemini
        logger.info(f"Step 2: Generating interior design with Gemini...")

        # Extract room type and style from tags if available
        room_type = None
        style_id = None
        for tag in topic.tags:
            if tag in ["living_room", "bedroom", "kitchen", "bathroom", "dining_room", "home_office"]:
                room_type = tag
            if tag in ["modern_minimalist", "scandinavian", "japanese", "industrial", "coastal"]:
                style_id = tag

        design_result = await self.interior_service.generate_design(
            prompt=image_prompt,
            style_id=style_id,
            room_type=room_type
        )

        if not design_result.get("success"):
            result.error = f"Interior design generation failed: {design_result.get('error')}"
            return result

        image_url = design_result.get("image_url")
        result.image_url = image_url
        result.steps_completed.append("design_generated")
        result.metadata["description"] = design_result.get("description", "")

        logger.info(f"Step 2 complete: Design at {image_url}")

        result.success = True
        return result

    # =========================================================================
    # STYLE TRANSFER: T2I → I2V → V2V
    # =========================================================================

    async def _generate_style_transfer(
        self,
        topic: TopicDefinition,
        save_locally: bool
    ) -> GenerationResult:
        """
        Style Transfer workflow: Leonardo T2I → Pollo I2V → GoEnhance V2V

        Flow:
        1. Build image prompt
        2. Generate base image with Leonardo
        3. Generate base video with Pollo AI
        4. Apply style with GoEnhance V2V
        """
        result = GenerationResult(
            success=False,
            topic_id=topic.id,
            category=topic.category,
            output_type=topic.output_type
        )

        # Step 1: Build image prompt
        image_prompt = topic.build_image_prompt()
        logger.info(f"Step 1: Image prompt built")
        result.steps_completed.append("image_prompt_built")

        # Step 2: Generate image with rescue service (Wan primary, fal.ai rescue)
        logger.info(f"Step 2: Generating image...")
        image_result = await self.rescue_service.generate_image(
            prompt=image_prompt,
            width=1024,
            height=1024
        )

        if not image_result.get("success"):
            result.error = f"Image generation failed: {image_result.get('error')}"
            return result

        image_url = image_result.get("image_url")
        if not image_url and image_result.get("images"):
            image_url = image_result["images"][0]["url"]
        result.image_url = image_url
        result.steps_completed.append("image_generated")
        logger.info(f"Step 2 complete: Image generated")

        # Step 3: Generate base video with rescue service
        effect_prompt = topic.build_effect_prompt()
        logger.info(f"Step 3: Generating base video...")

        video_result = await self.rescue_service.generate_video(
            image_url=image_url,
            prompt=effect_prompt,
            length=5
        )

        if not video_result.get("success"):
            result.error = f"Video generation failed: {video_result.get('error')}"
            result.success = True  # Return image even if video fails
            result.metadata["partial"] = True
            return result

        base_video_url = video_result.get("video_url")
        result.steps_completed.append("base_video_generated")
        result.metadata["base_video_url"] = base_video_url
        logger.info(f"Step 3 complete: Base video generated")

        # Step 4: Apply style with ProviderRouter V2V
        style_id = topic.style_id or "anime"  # Default to anime style
        logger.info(f"Step 4: Applying style {style_id}...")

        from app.services.effects_service import get_style_prompt
        style_prompt = get_style_prompt(style_id) or effect_prompt

        style_result = await self.provider_router.route(
            TaskType.V2V,
            {
                "video_url": base_video_url,
                "prompt": style_prompt
            }
        )

        output_url = style_result.get("video_url") or style_result.get("output_url")
        if not output_url:
            # Use base video if style transfer fails
            result.video_url = base_video_url
            result.metadata["style_transfer_failed"] = True
            logger.warning(f"Style transfer failed, using base video")
        else:
            result.video_url = output_url
            result.steps_completed.append("style_applied")
            logger.info(f"Step 4 complete: Style applied")

        result.success = True
        result.metadata["style_id"] = style_id

        return result

    # =========================================================================
    # AVATAR: Pollo Avatar API
    # =========================================================================

    async def _generate_avatar(
        self,
        topic: TopicDefinition,
        save_locally: bool
    ) -> GenerationResult:
        """
        Avatar workflow: Pollo Avatar API

        Flow:
        1. Get avatar image and script from topic metadata
        2. Generate avatar video with Pollo Avatar
        """
        result = GenerationResult(
            success=False,
            topic_id=topic.id,
            category=topic.category,
            output_type=topic.output_type
        )

        # Get avatar parameters from metadata
        avatar_url = topic.metadata.get("avatar_url") or topic.image_prompt_template
        script = topic.metadata.get("script", "Welcome to our product showcase!")
        language = topic.language

        logger.info(f"Step 1: Avatar generation starting")
        logger.info(f"  Language: {language}")
        logger.info(f"  Script: {script[:50]}...")

        result.steps_completed.append("parameters_loaded")
        result.image_url = avatar_url

        # Generate avatar video
        logger.info(f"Step 2: Generating avatar video...")

        avatar_result = await self.avatar_service.generate_and_wait(
            image_url=avatar_url,
            script=script,
            language=language,
            duration=30,
            timeout=300,
            save_locally=save_locally
        )

        if not avatar_result.get("success"):
            result.error = f"Avatar generation failed: {avatar_result.get('error')}"
            return result

        result.video_url = avatar_result.get("video_url")
        result.steps_completed.append("avatar_generated")
        result.metadata["language"] = language
        result.metadata["script"] = script

        logger.info(f"Step 2 complete: Avatar video at {result.video_url}")

        result.success = True
        return result

    # =========================================================================
    # T2I SHOWCASE: Leonardo Pattern Generation
    # =========================================================================

    async def _generate_t2i_showcase(
        self,
        topic: TopicDefinition,
        save_locally: bool
    ) -> GenerationResult:
        """
        T2I Showcase workflow: Leonardo pattern/texture generation

        Flow:
        1. Build pattern prompt from topic
        2. Generate pattern with Leonardo
        3. Output: Static image (no video)
        """
        result = GenerationResult(
            success=False,
            topic_id=topic.id,
            category=topic.category,
            output_type=topic.output_type
        )

        # Step 1: Build prompt
        image_prompt = topic.build_image_prompt()
        pattern_style = topic.metadata.get("pattern_style", "seamless")
        logger.info(f"Step 1: Pattern prompt built (style: {pattern_style})")
        result.steps_completed.append("prompt_built")

        # Step 2: Generate pattern with rescue service
        logger.info(f"Step 2: Generating pattern with rescue service...")

        pattern_result = await self.rescue_service.generate_image(
            prompt=f"{image_prompt}, {pattern_style} pattern",
            width=1024,
            height=1024
        )

        if not pattern_result.get("success"):
            result.error = f"Pattern generation failed: {pattern_result.get('error')}"
            return result

        image_url = pattern_result.get("image_url")
        if not image_url and pattern_result.get("images"):
            image_url = pattern_result["images"][0]["url"]
        result.image_url = image_url
        result.steps_completed.append("pattern_generated")
        result.metadata["pattern_style"] = pattern_style

        logger.info(f"Step 2 complete: Pattern at {image_url[:50]}...")

        result.success = True
        return result

    # =========================================================================
    # BATCH GENERATION
    # =========================================================================

    async def generate_all_topics(
        self,
        categories: Optional[List[TopicCategory]] = None,
        concurrency: int = 2,
        save_locally: bool = True
    ) -> List[GenerationResult]:
        """
        Generate content for multiple topics.

        Args:
            categories: Optional list of categories to generate (None = all)
            concurrency: Number of concurrent generations (default 2)
            save_locally: Whether to save files locally

        Returns:
            List of GenerationResult for all topics
        """
        self._init_services()

        # Get topics to generate
        if categories:
            topics = []
            for cat in categories:
                topics.extend(get_topics_by_category(cat))
        else:
            topics = get_all_topics()

        logger.info(f"Starting batch generation for {len(topics)} topics")
        results = []

        # Process in batches for rate limiting
        for i in range(0, len(topics), concurrency):
            batch = topics[i:i + concurrency]
            logger.info(f"Processing batch {i // concurrency + 1} ({len(batch)} topics)")

            # Run batch concurrently
            batch_results = await asyncio.gather(
                *[self.generate_from_topic(t, save_locally) for t in batch],
                return_exceptions=True
            )

            for j, res in enumerate(batch_results):
                if isinstance(res, Exception):
                    results.append(GenerationResult(
                        success=False,
                        topic_id=batch[j].id,
                        category=batch[j].category,
                        output_type=batch[j].output_type,
                        error=str(res)
                    ))
                else:
                    results.append(res)

            # Rate limiting delay between batches
            if i + concurrency < len(topics):
                await asyncio.sleep(5)

        # Summary
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        logger.info(f"Batch generation complete: {successful} succeeded, {failed} failed")

        return results

    async def generate_by_category(
        self,
        category: TopicCategory,
        save_locally: bool = True
    ) -> List[GenerationResult]:
        """Generate all topics for a specific category."""
        return await self.generate_all_topics(
            categories=[category],
            save_locally=save_locally
        )


# Singleton instance
_workflow_generator: Optional[WorkflowGenerator] = None


def get_workflow_generator() -> WorkflowGenerator:
    """Get or create workflow generator singleton."""
    global _workflow_generator
    if _workflow_generator is None:
        _workflow_generator = WorkflowGenerator()
    return _workflow_generator


async def run_workflow(
    topic_id: Optional[str] = None,
    category: Optional[str] = None,
    save_locally: bool = True
) -> Dict[str, Any]:
    """
    Convenience function to run workflow.

    Args:
        topic_id: Generate specific topic by ID
        category: Generate all topics in category
        save_locally: Whether to save files locally

    Returns:
        Dict with results
    """
    generator = get_workflow_generator()

    if topic_id:
        topic = get_topic_by_id(topic_id)
        if not topic:
            return {"success": False, "error": f"Topic not found: {topic_id}"}
        result = await generator.generate_from_topic(topic, save_locally)
        return result.to_dict()

    elif category:
        try:
            cat = TopicCategory(category)
        except ValueError:
            return {"success": False, "error": f"Invalid category: {category}"}
        results = await generator.generate_by_category(cat, save_locally)
        return {
            "success": True,
            "category": category,
            "total": len(results),
            "succeeded": sum(1 for r in results if r.success),
            "results": [r.to_dict() for r in results]
        }

    else:
        results = await generator.generate_all_topics(save_locally=save_locally)
        return {
            "success": True,
            "total": len(results),
            "succeeded": sum(1 for r in results if r.success),
            "results": [r.to_dict() for r in results]
        }
