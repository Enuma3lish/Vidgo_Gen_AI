"""
Material Library Service

Implements BaseMaterialService for managing tool showcases, demo examples,
and user-generated content.
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.base import BaseMaterialService, MaterialType, MaterialStatus, MaterialItem, MaterialRequirement
from app.models.demo import ToolShowcase, DemoExample, ImageDemo, DemoVideo, PromptCache
from .requirements import MATERIAL_REQUIREMENTS, get_tool_requirements

logger = logging.getLogger(__name__)


class MaterialLibraryService(BaseMaterialService):
    """
    Material Library implementation.

    Manages:
    - Tool showcases (before/after examples)
    - Demo examples (inspiration gallery)
    - User-generated content collection
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_sufficiency(
        self,
        material_type: MaterialType,
        category: Optional[str] = None,
        tool_id: Optional[str] = None
    ) -> MaterialRequirement:
        """Check if we have sufficient materials for a category/tool"""

        if material_type == MaterialType.TOOL_SHOWCASE:
            return await self._check_showcase_sufficiency(category, tool_id)
        elif material_type == MaterialType.DEMO_EXAMPLE:
            return await self._check_example_sufficiency(category)
        else:
            # For other types, return basic count
            return MaterialRequirement(
                material_type=material_type,
                category=category or "all",
                tool_id=tool_id,
                min_count=1,
                current_count=0
            )

    async def _check_showcase_sufficiency(
        self,
        category: Optional[str],
        tool_id: Optional[str]
    ) -> MaterialRequirement:
        """Check tool showcase sufficiency"""
        # Get requirements
        requirements = get_tool_requirements(category, tool_id)

        if not requirements:
            return MaterialRequirement(
                material_type=MaterialType.TOOL_SHOWCASE,
                category=category or "unknown",
                tool_id=tool_id,
                min_count=0,
                current_count=0
            )

        # For single tool check
        if tool_id and len(requirements) == 1:
            req = requirements[0]

            # Count existing showcases
            query = select(func.count(ToolShowcase.id)).where(
                and_(
                    ToolShowcase.tool_id == tool_id,
                    ToolShowcase.is_active == True,
                    ToolShowcase.result_image_url.isnot(None) |
                    ToolShowcase.result_video_url.isnot(None)
                )
            )
            result = await self.db.execute(query)
            current_count = result.scalar() or 0

            # Count featured
            featured_query = select(func.count(ToolShowcase.id)).where(
                and_(
                    ToolShowcase.tool_id == tool_id,
                    ToolShowcase.is_active == True,
                    ToolShowcase.is_featured == True,
                    ToolShowcase.result_image_url.isnot(None) |
                    ToolShowcase.result_video_url.isnot(None)
                )
            )
            featured_result = await self.db.execute(featured_query)
            current_featured = featured_result.scalar() or 0

            return MaterialRequirement(
                material_type=MaterialType.TOOL_SHOWCASE,
                category=category or "unknown",
                tool_id=tool_id,
                min_count=req.min_showcases,
                min_featured=req.min_featured,
                current_count=current_count,
                current_featured=current_featured
            )

        # For category or all tools
        total_min = sum(r.min_showcases for r in requirements)
        total_featured_min = sum(r.min_featured for r in requirements)

        # Count all showcases in category
        query = select(func.count(ToolShowcase.id)).where(
            and_(
                ToolShowcase.is_active == True,
                ToolShowcase.result_image_url.isnot(None) |
                ToolShowcase.result_video_url.isnot(None)
            )
        )
        if category:
            query = query.where(ToolShowcase.tool_category == category)

        result = await self.db.execute(query)
        current_count = result.scalar() or 0

        return MaterialRequirement(
            material_type=MaterialType.TOOL_SHOWCASE,
            category=category or "all",
            tool_id=tool_id,
            min_count=total_min,
            min_featured=total_featured_min,
            current_count=current_count
        )

    async def _check_example_sufficiency(self, category: Optional[str]) -> MaterialRequirement:
        """Check demo example sufficiency"""
        # Count examples
        query = select(func.count(DemoExample.id)).where(DemoExample.is_active == True)
        if category:
            query = query.where(DemoExample.topic == category)

        result = await self.db.execute(query)
        current_count = result.scalar() or 0

        # Default: 10 examples per topic
        min_count = 10 if category else 50

        return MaterialRequirement(
            material_type=MaterialType.DEMO_EXAMPLE,
            category=category or "all",
            min_count=min_count,
            current_count=current_count
        )

    async def get_all_requirements(self) -> List[MaterialRequirement]:
        """Get all material requirements with current status"""
        requirements = []

        for category_id, category in MATERIAL_REQUIREMENTS.items():
            for tool in category.tools:
                req = await self.check_sufficiency(
                    MaterialType.TOOL_SHOWCASE,
                    category_id,
                    tool.tool_id
                )
                requirements.append(req)

        return requirements

    async def get_missing_materials(self) -> List[Dict[str, Any]]:
        """Get list of materials that need to be generated"""
        missing = []

        for category_id, category in MATERIAL_REQUIREMENTS.items():
            for tool in category.tools:
                req = await self.check_sufficiency(
                    MaterialType.TOOL_SHOWCASE,
                    category_id,
                    tool.tool_id
                )

                if not req.is_sufficient:
                    missing.append({
                        "category": category_id,
                        "category_name": category.category_name,
                        "category_name_zh": category.category_name_zh,
                        "tool_id": tool.tool_id,
                        "tool_name": tool.tool_name,
                        "tool_name_zh": tool.tool_name_zh,
                        "generation_type": tool.generation_type,
                        "missing_count": req.missing_count,
                        "missing_featured": req.missing_featured,
                        "default_prompts": tool.default_prompts,
                    })

        return missing

    async def store_material(self, material: MaterialItem) -> Optional[str]:
        """Store a new material in the database"""
        try:
            if material.material_type == MaterialType.TOOL_SHOWCASE:
                return await self._store_showcase(material)
            elif material.material_type == MaterialType.DEMO_EXAMPLE:
                return await self._store_example(material)
            elif material.material_type == MaterialType.USER_GENERATED:
                return await self._store_user_content(material)
            else:
                logger.warning(f"Unknown material type: {material.material_type}")
                return None

        except Exception as e:
            logger.error(f"Failed to store material: {e}")
            await self.db.rollback()
            return None

    async def _store_showcase(self, material: MaterialItem) -> Optional[str]:
        """Store a tool showcase"""
        showcase = ToolShowcase(
            tool_category=material.category,
            tool_id=material.tool_id or "",
            tool_name=material.title or "",
            tool_name_zh=material.title_zh,
            source_image_url=material.source_image_url or "",
            prompt=material.prompt or "",
            prompt_zh=material.prompt_zh,
            result_image_url=material.result_image_url,
            result_video_url=material.result_video_url,
            result_thumbnail_url=material.thumbnail_url,
            title=material.title,
            title_zh=material.title_zh,
            style_tags=material.style_tags,
            source_service=material.service_name or "unknown",
            generation_params=material.generation_params,
            is_user_generated=material.is_user_generated,
            user_id=uuid.UUID(material.user_id) if material.user_id else None,
            is_featured=material.is_featured,
            is_active=material.is_active,
            quality_score=material.quality_score
        )

        self.db.add(showcase)
        await self.db.commit()
        await self.db.refresh(showcase)

        return str(showcase.id)

    async def _store_example(self, material: MaterialItem) -> Optional[str]:
        """Store a demo example"""
        example = DemoExample(
            topic=material.category,
            prompt=material.prompt or "",
            image_url=material.result_image_url or material.source_image_url or "",
            video_url=material.result_video_url,
            thumbnail_url=material.thumbnail_url,
            title=material.title,
            title_zh=material.title_zh,
            style_tags=material.style_tags,
            source_service=material.service_name or "unknown",
            is_featured=material.is_featured,
            is_active=material.is_active,
            quality_score=material.quality_score
        )

        self.db.add(example)
        await self.db.commit()
        await self.db.refresh(example)

        return str(example.id)

    async def _store_user_content(self, material: MaterialItem) -> Optional[str]:
        """Store user-generated content for potential showcase use"""
        # Store as inactive showcase that can be promoted later
        material.is_active = False  # Needs review before activation
        material.is_user_generated = True
        return await self._store_showcase(material)

    async def update_material(
        self,
        material_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update an existing material"""
        try:
            # Determine material type by checking tables
            showcase = await self.db.get(ToolShowcase, uuid.UUID(material_id))
            if showcase:
                for key, value in updates.items():
                    if hasattr(showcase, key):
                        setattr(showcase, key, value)
                await self.db.commit()
                return True

            example = await self.db.get(DemoExample, uuid.UUID(material_id))
            if example:
                for key, value in updates.items():
                    if hasattr(example, key):
                        setattr(example, key, value)
                await self.db.commit()
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to update material {material_id}: {e}")
            await self.db.rollback()
            return False

    async def get_materials(
        self,
        material_type: MaterialType,
        category: Optional[str] = None,
        tool_id: Optional[str] = None,
        featured_only: bool = False,
        limit: int = 20,
        offset: int = 0
    ) -> List[MaterialItem]:
        """Retrieve materials with filtering"""

        if material_type == MaterialType.TOOL_SHOWCASE:
            return await self._get_showcases(category, tool_id, featured_only, limit, offset)
        elif material_type == MaterialType.DEMO_EXAMPLE:
            return await self._get_examples(category, featured_only, limit, offset)
        else:
            return []

    async def _get_showcases(
        self,
        category: Optional[str],
        tool_id: Optional[str],
        featured_only: bool,
        limit: int,
        offset: int
    ) -> List[MaterialItem]:
        """Get tool showcases"""
        query = select(ToolShowcase).where(ToolShowcase.is_active == True)

        if category:
            query = query.where(ToolShowcase.tool_category == category)
        if tool_id:
            query = query.where(ToolShowcase.tool_id == tool_id)
        if featured_only:
            query = query.where(ToolShowcase.is_featured == True)

        query = query.order_by(ToolShowcase.sort_order, ToolShowcase.created_at.desc())
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        showcases = result.scalars().all()

        return [
            MaterialItem(
                id=str(s.id),
                material_type=MaterialType.TOOL_SHOWCASE,
                category=s.tool_category,
                tool_id=s.tool_id,
                source_image_url=s.source_image_url,
                result_image_url=s.result_image_url,
                result_video_url=s.result_video_url,
                thumbnail_url=s.result_thumbnail_url,
                prompt=s.prompt,
                prompt_zh=s.prompt_zh,
                title=s.title,
                title_zh=s.title_zh,
                style_tags=s.style_tags or [],
                service_name=s.source_service,
                status=MaterialStatus.COMPLETED if (s.result_image_url or s.result_video_url) else MaterialStatus.PENDING,
                is_featured=s.is_featured,
                is_active=s.is_active,
                is_user_generated=s.is_user_generated,
                user_id=str(s.user_id) if s.user_id else None,
                quality_score=s.quality_score,
                popularity_score=s.popularity_score,
                created_at=s.created_at,
                updated_at=s.updated_at
            )
            for s in showcases
        ]

    async def _get_examples(
        self,
        category: Optional[str],
        featured_only: bool,
        limit: int,
        offset: int
    ) -> List[MaterialItem]:
        """Get demo examples"""
        query = select(DemoExample).where(DemoExample.is_active == True)

        if category:
            query = query.where(DemoExample.topic == category)
        if featured_only:
            query = query.where(DemoExample.is_featured == True)

        query = query.order_by(DemoExample.sort_order, DemoExample.popularity_score.desc())
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        examples = result.scalars().all()

        return [
            MaterialItem(
                id=str(e.id),
                material_type=MaterialType.DEMO_EXAMPLE,
                category=e.topic,
                result_image_url=e.image_url,
                result_video_url=e.video_url,
                thumbnail_url=e.thumbnail_url,
                prompt=e.prompt,
                title=e.title,
                title_zh=e.title_zh,
                style_tags=e.style_tags or [],
                service_name=e.source_service,
                status=MaterialStatus.COMPLETED,
                is_featured=e.is_featured,
                is_active=e.is_active,
                quality_score=e.quality_score,
                popularity_score=e.popularity_score,
                created_at=e.created_at,
                updated_at=e.updated_at
            )
            for e in examples
        ]

    async def collect_user_content(
        self,
        source_image_url: str,
        result_image_url: Optional[str],
        result_video_url: Optional[str],
        prompt: str,
        user_id: str,
        generation_id: str,
        service_name: str,
        quality_threshold: float = 0.7
    ) -> Optional[str]:
        """Collect high-quality user-generated content"""

        # Only collect if we have a proper before/after relationship
        if not source_image_url:
            logger.debug("Skipping collection: no source image")
            return None

        if not result_image_url and not result_video_url:
            logger.debug("Skipping collection: no result")
            return None

        # TODO: Implement quality scoring
        # For now, collect all with threshold check
        quality_score = 0.8  # Default score

        if quality_score < quality_threshold:
            logger.debug(f"Skipping collection: quality {quality_score} < threshold {quality_threshold}")
            return None

        material = MaterialItem(
            material_type=MaterialType.USER_GENERATED,
            category="user_generated",
            source_image_url=source_image_url,
            result_image_url=result_image_url,
            result_video_url=result_video_url,
            prompt=prompt,
            service_name=service_name,
            is_user_generated=True,
            user_id=user_id,
            source_generation_id=generation_id,
            quality_score=quality_score,
            is_active=False,  # Needs review
            is_featured=False
        )

        return await self.store_material(material)

    async def promote_to_showcase(
        self,
        material_id: str,
        tool_category: str,
        tool_id: str,
        review_notes: Optional[str] = None
    ) -> bool:
        """Promote user-generated content to official showcase"""
        try:
            showcase = await self.db.get(ToolShowcase, uuid.UUID(material_id))

            if not showcase:
                logger.warning(f"Material not found: {material_id}")
                return False

            if not showcase.is_user_generated:
                logger.warning(f"Material is not user-generated: {material_id}")
                return False

            # Update to official showcase
            showcase.tool_category = tool_category
            showcase.tool_id = tool_id
            showcase.is_active = True
            showcase.is_featured = False  # Can be featured later

            if review_notes:
                showcase.generation_params = {
                    **(showcase.generation_params or {}),
                    "review_notes": review_notes,
                    "promoted_at": datetime.utcnow().isoformat()
                }

            await self.db.commit()
            logger.info(f"Promoted material {material_id} to showcase for {tool_category}/{tool_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to promote material: {e}")
            await self.db.rollback()
            return False


# Dependency injection helper
async def get_material_library(db: AsyncSession) -> MaterialLibraryService:
    """Get MaterialLibraryService instance"""
    return MaterialLibraryService(db)
