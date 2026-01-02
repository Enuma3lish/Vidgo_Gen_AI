"""
User Content Collector

Automatically collects high-quality user generations for the material library.
Integrates with the generation pipeline to capture before/after relationships.
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.base import GenerationResult, GenerationType
from app.models.billing import Generation
from .library import MaterialLibraryService

logger = logging.getLogger(__name__)


class UserContentCollector:
    """
    Collects user-generated content for the material library.

    Workflow:
    1. User makes a generation request
    2. Generation completes successfully
    3. Collector evaluates quality and relevance
    4. High-quality content is stored for potential showcase use
    """

    # Minimum quality threshold for collection
    MIN_QUALITY_THRESHOLD = 0.6

    # Categories that benefit from user content
    COLLECTION_PRIORITIES = {
        "product": 1.2,      # Product photos are very valuable
        "fashion": 1.1,
        "portrait": 1.1,
        "architecture": 1.0,
        "food": 1.0,
        "general": 0.8,
    }

    def __init__(self, db: AsyncSession):
        self.db = db
        self.material_library = MaterialLibraryService(db)

    async def on_generation_complete(
        self,
        generation_id: str,
        result: GenerationResult,
        user_id: str,
        category_hint: Optional[str] = None
    ) -> Optional[str]:
        """
        Called when a generation completes successfully.
        Evaluates and potentially collects the content.

        Args:
            generation_id: ID of the Generation record
            result: GenerationResult from the generation service
            user_id: User who created the generation
            category_hint: Optional category hint for classification

        Returns:
            Material ID if collected, None otherwise
        """
        if not result.success:
            return None

        # Must have source image for before/after relationship
        if not result.source_image_url:
            logger.debug("Skipping: no source image for before/after")
            return None

        # Must have result
        if not result.image_url and not result.video_url:
            logger.debug("Skipping: no result output")
            return None

        # Evaluate quality
        quality_score = await self._evaluate_quality(result, category_hint)

        if quality_score < self.MIN_QUALITY_THRESHOLD:
            logger.debug(f"Skipping: quality {quality_score:.2f} below threshold")
            return None

        # Collect the content
        try:
            material_id = await self.material_library.collect_user_content(
                source_image_url=result.source_image_url,
                result_image_url=result.image_url,
                result_video_url=result.video_url,
                prompt=result.prompt or "",
                user_id=user_id,
                generation_id=generation_id,
                service_name=result.service_name,
                quality_threshold=self.MIN_QUALITY_THRESHOLD
            )

            if material_id:
                logger.info(f"Collected user content: {material_id} (quality: {quality_score:.2f})")

                # Update generation record with collection status
                await self._mark_generation_collected(generation_id, material_id)

            return material_id

        except Exception as e:
            logger.error(f"Failed to collect user content: {e}")
            return None

    async def _evaluate_quality(
        self,
        result: GenerationResult,
        category_hint: Optional[str] = None
    ) -> float:
        """
        Evaluate quality of a generation result.

        Factors considered:
        - Generation success
        - Has proper before/after relationship
        - Category priority
        - Service reliability

        Returns:
            Quality score 0.0 - 1.0
        """
        score = 0.5  # Base score

        # Boost for having both image and video
        if result.image_url and result.video_url:
            score += 0.2

        # Boost for having source relationship
        if result.source_image_url:
            score += 0.15

        # Boost for having prompt
        if result.prompt and len(result.prompt) > 10:
            score += 0.1

        # Category priority boost
        category = category_hint or "general"
        priority = self.COLLECTION_PRIORITIES.get(category, 0.8)
        score *= priority

        # Service reliability boost
        reliable_services = ["leonardo", "pollo_ai", "goenhance"]
        if result.service_name in reliable_services:
            score += 0.05

        return min(1.0, score)

    async def _mark_generation_collected(
        self,
        generation_id: str,
        material_id: str
    ) -> None:
        """Mark a generation as collected in the database"""
        try:
            generation = await self.db.get(Generation, generation_id)
            if generation:
                generation.generation_params = {
                    **(generation.generation_params or {}),
                    "collected_as_material": material_id,
                    "collected_at": datetime.utcnow().isoformat()
                }
                await self.db.commit()
        except Exception as e:
            logger.error(f"Failed to mark generation collected: {e}")

    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about collected user content"""
        from sqlalchemy import func
        from app.models.demo import ToolShowcase

        # Count user-generated materials
        query = select(func.count(ToolShowcase.id)).where(
            ToolShowcase.is_user_generated == True
        )
        result = await self.db.execute(query)
        total_collected = result.scalar() or 0

        # Count promoted (active) materials
        promoted_query = select(func.count(ToolShowcase.id)).where(
            ToolShowcase.is_user_generated == True,
            ToolShowcase.is_active == True
        )
        promoted_result = await self.db.execute(promoted_query)
        total_promoted = promoted_result.scalar() or 0

        # Count pending review
        pending_review = total_collected - total_promoted

        return {
            "total_collected": total_collected,
            "total_promoted": total_promoted,
            "pending_review": pending_review,
            "quality_threshold": self.MIN_QUALITY_THRESHOLD
        }


# Dependency injection helper
async def get_content_collector(db: AsyncSession) -> UserContentCollector:
    """Get UserContentCollector instance"""
    return UserContentCollector(db)
