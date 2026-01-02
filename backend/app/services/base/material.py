"""
Base Material Service Interface

Defines the interface for material/asset management including:
- Storage and retrieval of generated assets
- Material sufficiency checks
- User content collection
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MaterialType(str, Enum):
    """Types of materials/assets"""
    TOOL_SHOWCASE = "tool_showcase"      # Before/after tool demos
    DEMO_EXAMPLE = "demo_example"        # Inspiration gallery items
    IMAGE_DEMO = "image_demo"            # Style transformation demos
    DEMO_VIDEO = "demo_video"            # Video demos
    USER_GENERATED = "user_generated"    # Collected from user generations
    PROMPT_CACHE = "prompt_cache"        # Cached generation results


class MaterialStatus(str, Enum):
    """Status of material generation"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class MaterialRequirement:
    """Defines minimum material requirements for a category"""
    material_type: MaterialType
    category: str
    tool_id: Optional[str] = None
    min_count: int = 5
    min_featured: int = 1
    current_count: int = 0
    current_featured: int = 0

    @property
    def is_sufficient(self) -> bool:
        """Check if we have enough materials"""
        return self.current_count >= self.min_count and self.current_featured >= self.min_featured

    @property
    def missing_count(self) -> int:
        """How many more materials needed"""
        return max(0, self.min_count - self.current_count)

    @property
    def missing_featured(self) -> int:
        """How many more featured materials needed"""
        return max(0, self.min_featured - self.current_featured)


@dataclass
class MaterialItem:
    """Represents a single material/asset"""
    id: Optional[str] = None
    material_type: MaterialType = MaterialType.TOOL_SHOWCASE
    category: str = ""
    tool_id: Optional[str] = None

    # Content
    source_image_url: Optional[str] = None
    source_video_url: Optional[str] = None
    result_image_url: Optional[str] = None
    result_video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None

    # Metadata
    prompt: Optional[str] = None
    prompt_zh: Optional[str] = None
    title: Optional[str] = None
    title_zh: Optional[str] = None
    style_tags: List[str] = field(default_factory=list)

    # Generation info
    service_name: Optional[str] = None
    style_id: Optional[str] = None
    style_name: Optional[str] = None
    generation_params: Dict[str, Any] = field(default_factory=dict)

    # Status and scoring
    status: MaterialStatus = MaterialStatus.PENDING
    is_featured: bool = False
    is_active: bool = True
    quality_score: float = 0.8
    popularity_score: int = 0

    # Source tracking
    is_user_generated: bool = False
    user_id: Optional[str] = None
    source_generation_id: Optional[str] = None

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BaseMaterialService(ABC):
    """
    Abstract base class for material/asset management.

    Handles:
    - Checking material sufficiency
    - Storing generated materials
    - Collecting user-generated content
    - Retrieving materials for display
    """

    @abstractmethod
    async def check_sufficiency(
        self,
        material_type: MaterialType,
        category: Optional[str] = None,
        tool_id: Optional[str] = None
    ) -> MaterialRequirement:
        """
        Check if we have sufficient materials for a category.

        Args:
            material_type: Type of material to check
            category: Category to check (e.g., "edit_tools", "ecommerce")
            tool_id: Specific tool ID to check

        Returns:
            MaterialRequirement with current counts and sufficiency status
        """
        pass

    @abstractmethod
    async def get_all_requirements(self) -> List[MaterialRequirement]:
        """
        Get all material requirements with current status.

        Returns:
            List of MaterialRequirement for all categories/tools
        """
        pass

    @abstractmethod
    async def store_material(self, material: MaterialItem) -> Optional[str]:
        """
        Store a new material in the database.

        Args:
            material: MaterialItem to store

        Returns:
            ID of stored material, or None if failed
        """
        pass

    @abstractmethod
    async def update_material(
        self,
        material_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update an existing material.

        Args:
            material_id: ID of material to update
            updates: Dictionary of field updates

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    async def get_materials(
        self,
        material_type: MaterialType,
        category: Optional[str] = None,
        tool_id: Optional[str] = None,
        featured_only: bool = False,
        limit: int = 20,
        offset: int = 0
    ) -> List[MaterialItem]:
        """
        Retrieve materials with filtering.

        Args:
            material_type: Type of materials to retrieve
            category: Filter by category
            tool_id: Filter by tool ID
            featured_only: Only return featured materials
            limit: Maximum number to return
            offset: Offset for pagination

        Returns:
            List of MaterialItem
        """
        pass

    @abstractmethod
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
        """
        Collect high-quality user-generated content for material library.

        Only stores content that meets quality threshold and has proper
        source-to-result relationship.

        Args:
            source_image_url: Original input image
            result_image_url: Generated image (if any)
            result_video_url: Generated video (if any)
            prompt: Prompt used for generation
            user_id: User who created it
            generation_id: Reference to Generation record
            service_name: Service used for generation
            quality_threshold: Minimum quality score to collect

        Returns:
            ID of collected material, or None if not collected
        """
        pass

    @abstractmethod
    async def promote_to_showcase(
        self,
        material_id: str,
        tool_category: str,
        tool_id: str,
        review_notes: Optional[str] = None
    ) -> bool:
        """
        Promote a user-generated material to an official showcase.

        Args:
            material_id: ID of material to promote
            tool_category: Target tool category
            tool_id: Target tool ID
            review_notes: Optional admin notes

        Returns:
            True if successful
        """
        pass
