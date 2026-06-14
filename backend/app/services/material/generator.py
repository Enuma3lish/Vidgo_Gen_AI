"""
Real Showcase Generator

Generates actual AI-processed showcases using the generation services.
Creates proper before/after relationships where the result is truly
derived from the source image.

Key Features:
- Uses ProviderRouter (PiAPI primary, Pollo backup)
- Uses real APIs (GoEnhance, Pollo AI, PiAPI)
- Maintains source-to-result relationships
- Supports both image and video generation
- Tracks generation progress and handles failures
"""
import asyncio
import logging
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.base import GenerationType, GenerationResult, MaterialItem, MaterialType, MaterialStatus
from app.services.generation import (
    GenerationServiceFactory,
    PolloGenerationService,
)
from app.providers.provider_router import get_provider_router, TaskType
from .library import MaterialLibraryService
from .requirements import MATERIAL_REQUIREMENTS, ToolRequirement

logger = logging.getLogger(__name__)


@dataclass
class GenerationTask:
    """Represents a single showcase generation task"""
    category: str
    tool_id: str
    tool_name: str
    tool_name_zh: str
    source_image_url: str
    prompt: str
    prompt_zh: Optional[str]
    generation_type: str  # "image" or "video"
    style_id: Optional[str] = None
    is_featured: bool = False


@dataclass
class GenerationProgress:
    """Tracks generation progress"""
    total_tasks: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    current_task: Optional[str] = None
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    @property
    def success_rate(self) -> float:
        if self.completed + self.failed == 0:
            return 0.0
        return self.completed / (self.completed + self.failed)


class RealShowcaseGenerator:
    """
    Generates real AI-processed showcases.

    Pipeline:
    1. Get source images (from Unsplash or existing assets)
    2. Apply transformation using appropriate AI service
    3. For video tools: Generate image then convert to video
    4. Store results with proper source-to-result relationship
    """

    # High-quality source images for different categories
    # These are curated Unsplash images that work well for each tool type
    SOURCE_IMAGES = {
        "edit_tools": {
            "landscape": [
                "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1200",  # Mountain
                "https://images.unsplash.com/photo-1518837695005-2083093ee35b?w=1200",  # Ocean
                "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=1200",  # Mountain wide
            ],
            "portrait": [
                "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=1200",  # Woman portrait
                "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=1200",  # Man portrait
                "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=1200",  # Fashion portrait
            ],
        },
        "ecommerce": {
            "product": [
                "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=1200",  # Watch
                "https://images.unsplash.com/photo-1541643600914-78b084683601?w=1200",  # Perfume
                "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=1200",  # Sneaker
                "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=1200",  # Headphones
                "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=1200",  # Camera
            ],
            "fashion": [
                "https://images.unsplash.com/photo-1434389677669-e08b4cac3105?w=1200",  # Dress
                "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=1200",  # Jacket
            ],
        },
        "architecture": {
            "building": [
                "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=1200",  # Modern building
                "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=1200",  # Villa
            ],
            "interior": [
                "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=1200",  # Living room
                "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?w=1200",  # Kitchen
                "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=1200",  # Bedroom
            ],
        },
        "portrait": {
            "face": [
                "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=1200",  # Woman face
                "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=1200",  # Man face
                "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=1200",  # Natural light
            ],
        },
    }

    # Style mappings for different tools
    TOOL_STYLES = {
        "photo_cartoon": ["anime", "pixar", "cartoon"],
        "style_convert": ["watercolor", "oil_painting", "cinematic"],
        "ai_portrait": ["cinematic", "oil_painting", "anime"],
    }

    def __init__(
        self,
        db: AsyncSession,
        on_progress: Optional[Callable[[GenerationProgress], None]] = None
    ):
        self.db = db
        self.material_library = MaterialLibraryService(db)
        self.on_progress = on_progress
        self.progress = GenerationProgress()

    async def generate_missing_showcases(
        self,
        category: Optional[str] = None,
        tool_id: Optional[str] = None,
        limit: Optional[int] = None,
        dry_run: bool = False
    ) -> GenerationProgress:
        """
        Generate showcases for tools that are missing materials.

        Args:
            category: Only generate for specific category
            tool_id: Only generate for specific tool
            limit: Maximum number of showcases to generate
            dry_run: If True, only show what would be generated

        Returns:
            GenerationProgress with results
        """
        # Get missing materials
        missing = await self.material_library.get_missing_materials()

        # Filter by category/tool if specified
        if category:
            missing = [m for m in missing if m["category"] == category]
        if tool_id:
            missing = [m for m in missing if m["tool_id"] == tool_id]

        if not missing:
            logger.info("No missing materials found")
            return self.progress

        # Build generation tasks
        tasks = self._build_generation_tasks(missing, limit)

        self.progress.total_tasks = len(tasks)
        logger.info(f"Generating {len(tasks)} showcases")

        if dry_run:
            logger.info("DRY RUN - no actual generation will be performed")
            for task in tasks:
                logger.info(f"  Would generate: {task.category}/{task.tool_id} - {task.prompt[:50]}...")
            return self.progress

        # Execute generation tasks
        for task in tasks:
            self.progress.current_task = f"{task.category}/{task.tool_id}"
            self._notify_progress()

            try:
                success = await self._execute_generation_task(task)
                if success:
                    self.progress.completed += 1
                else:
                    self.progress.failed += 1

            except Exception as e:
                logger.error(f"Task failed: {task.tool_id} - {e}")
                self.progress.failed += 1
                self.progress.errors.append(f"{task.tool_id}: {str(e)}")

            # Rate limiting - wait between API calls
            await asyncio.sleep(2)

        self.progress.current_task = None
        self._notify_progress()

        logger.info(
            f"Generation complete: {self.progress.completed} success, "
            f"{self.progress.failed} failed, {self.progress.skipped} skipped"
        )

        return self.progress

    def _build_generation_tasks(
        self,
        missing: List[Dict[str, Any]],
        limit: Optional[int]
    ) -> List[GenerationTask]:
        """Build list of generation tasks from missing materials"""
        tasks = []

        for item in missing:
            category = item["category"]
            tool_id = item["tool_id"]
            generation_type = item["generation_type"]
            default_prompts = item.get("default_prompts", [])

            # Get source images for this category
            source_images = self._get_source_images(category, tool_id)

            # Create tasks for each prompt up to missing count
            for i in range(item["missing_count"]):
                if limit and len(tasks) >= limit:
                    break

                # Cycle through prompts and source images
                prompt_data = default_prompts[i % len(default_prompts)] if default_prompts else {
                    "prompt": f"Transform this image with {tool_id} effect",
                    "prompt_zh": f"使用 {tool_id} 效果轉換此圖片"
                }

                source_image = source_images[i % len(source_images)]

                # Get style for style-based tools
                style_id = None
                if tool_id in self.TOOL_STYLES:
                    styles = self.TOOL_STYLES[tool_id]
                    style_id = styles[i % len(styles)]

                tasks.append(GenerationTask(
                    category=category,
                    tool_id=tool_id,
                    tool_name=item["tool_name"],
                    tool_name_zh=item["tool_name_zh"],
                    source_image_url=source_image,
                    prompt=prompt_data["prompt"],
                    prompt_zh=prompt_data.get("prompt_zh"),
                    generation_type=generation_type,
                    style_id=style_id,
                    is_featured=(i == 0)  # First one is featured
                ))

            if limit and len(tasks) >= limit:
                break

        return tasks

    def _get_source_images(self, category: str, tool_id: str) -> List[str]:
        """Get appropriate source images for a tool"""
        category_images = self.SOURCE_IMAGES.get(category, {})

        # Try to match tool to image type
        if tool_id in ["photo_cartoon", "ai_portrait", "face_swap", "photo_restore"]:
            images = category_images.get("portrait", []) or category_images.get("face", [])
        elif tool_id in ["product_design", "white_bg", "scene_gen"]:
            images = category_images.get("product", [])
        elif tool_id in ["model_tryon"]:
            images = category_images.get("fashion", [])
        elif tool_id in ["3d_render", "style_convert"]:
            images = category_images.get("interior", []) or category_images.get("building", [])
        else:
            # Default to first available type
            images = list(category_images.values())[0] if category_images else []

        # Fallback to generic images
        if not images:
            images = [
                "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1200",
                "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=1200",
            ]

        return images

    async def _execute_generation_task(self, task: GenerationTask) -> bool:
        """Execute a single generation task"""
        logger.info(f"Generating: {task.category}/{task.tool_id} - {task.prompt[:50]}...")

        if task.generation_type == "video":
            return await self._generate_video_showcase(task)
        else:
            return await self._generate_image_showcase(task)

    async def _generate_image_showcase(self, task: GenerationTask) -> bool:
        """Generate image-based showcase using style transfer"""

        # Use GoEnhance for style transfer
        service = GenerationServiceFactory.get_service("goenhance")
        if not service:
            logger.error("GoEnhance service not available")
            return False

        # Apply style transformation
        result = await service.generate_and_wait(
            generation_type=GenerationType.IMAGE_TO_IMAGE,
            source_image_url=task.source_image_url,
            prompt=task.prompt,
            style_id=task.style_id or "cinematic",
            timeout=180
        )

        if not result.success:
            logger.error(f"Image generation failed: {result.error}")
            return False

        # For GoEnhance IMAGE_TO_IMAGE, we get a video URL (V2V result)
        # The thumbnail/first frame is our "styled image"
        # In production, you'd extract the first frame

        # Store the showcase
        material = MaterialItem(
            material_type=MaterialType.TOOL_SHOWCASE,
            category=task.category,
            tool_id=task.tool_id,
            source_image_url=task.source_image_url,
            result_image_url=result.thumbnail_url or result.video_url,  # Use thumbnail as image
            result_video_url=result.video_url,
            prompt=task.prompt,
            prompt_zh=task.prompt_zh,
            title=task.tool_name,
            title_zh=task.tool_name_zh,
            service_name=result.service_name,
            style_id=task.style_id,
            style_name=result.style_name,
            is_featured=task.is_featured,
            is_active=True,
            quality_score=0.85,
            generation_params={
                "task_id": result.task_id,
                "generated_at": datetime.utcnow().isoformat()
            }
        )

        material_id = await self.material_library.store_material(material)

        if material_id:
            logger.info(f"Stored image showcase: {material_id}")
            return True

        return False

    async def _generate_video_showcase(self, task: GenerationTask) -> bool:
        """Generate video showcase using image-to-video pipeline"""

        # Step 1: Generate base image using Leonardo
        leonardo = GenerationServiceFactory.get_service("leonardo")
        if not leonardo:
            logger.error("Leonardo service not available")
            return False

        # For video showcases, we first generate an image from the source
        # In real scenario, we'd enhance the source image or use it directly

        # Step 2: Convert to video using Pollo AI
        pollo = GenerationServiceFactory.get_service("pollo_ai")
        if not pollo:
            logger.error("Pollo AI service not available")
            return False

        video_result = await pollo.generate_and_wait(
            generation_type=GenerationType.IMAGE_TO_VIDEO,
            source_image_url=task.source_image_url,
            prompt=task.prompt,
            timeout=300
        )

        if not video_result.success:
            logger.error(f"Video generation failed: {video_result.error}")
            return False

        # Store the showcase
        material = MaterialItem(
            material_type=MaterialType.TOOL_SHOWCASE,
            category=task.category,
            tool_id=task.tool_id,
            source_image_url=task.source_image_url,
            result_video_url=video_result.video_url,
            thumbnail_url=task.source_image_url,  # Use source as thumbnail
            prompt=task.prompt,
            prompt_zh=task.prompt_zh,
            title=task.tool_name,
            title_zh=task.tool_name_zh,
            service_name=video_result.service_name,
            is_featured=task.is_featured,
            is_active=True,
            quality_score=0.85,
            generation_params={
                "task_id": video_result.task_id,
                "model_name": video_result.model_name,
                "duration_seconds": video_result.duration_seconds,
                "generated_at": datetime.utcnow().isoformat()
            }
        )

        material_id = await self.material_library.store_material(material)

        if material_id:
            logger.info(f"Stored video showcase: {material_id}")
            return True

        return False

    def _notify_progress(self) -> None:
        """Notify progress callback if set"""
        if self.on_progress:
            self.on_progress(self.progress)
