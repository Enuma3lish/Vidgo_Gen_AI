"""
Material Lookup Service for PRESET-ONLY Mode

This service handles all material lookups from the Material DB.
In preset-only mode:
- ALL users (subscribed and non-subscribed) use this service
- NO external API calls are made during user sessions
- ALL results are watermarked
- Downloads are BLOCKED for everyone
"""
import logging
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from app.models.material import Material, ToolType, MaterialStatus

logger = logging.getLogger(__name__)


class MaterialLookupService:
    """
    Service for looking up pre-generated materials by hash.

    PRESET-ONLY MODE:
    - All generation requests are resolved from Material DB
    - No external API calls
    - Returns watermarked URLs only
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def lookup_by_hash(self, lookup_hash: str) -> Optional[Material]:
        """
        Look up material by its lookup hash.

        Args:
            lookup_hash: SHA256 hash of (tool_type + prompt + effect_prompt + input_image_id)

        Returns:
            Material if found, None otherwise
        """
        from sqlalchemy import or_

        # PRESET-ONLY MODE: Accept materials with any result URL
        result = await self.db.execute(
            select(Material).where(
                and_(
                    Material.lookup_hash == lookup_hash,
                    Material.is_active == True,
                    or_(
                        Material.result_watermarked_url.isnot(None),
                        Material.result_video_url.isnot(None),
                        Material.result_image_url.isnot(None)
                    )
                )
            )
        )
        return result.scalar_one_or_none()

    async def lookup_by_id(self, material_id: str) -> Optional[Material]:
        """
        Look up material by its UUID.

        Args:
            material_id: UUID of the material

        Returns:
            Material if found, None otherwise
        """
        result = await self.db.execute(
            select(Material).where(
                and_(
                    Material.id == material_id,
                    Material.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()

    async def lookup_by_preset(
        self,
        tool_type: str,
        prompt: str,
        effect_prompt: Optional[str] = None,
        input_image_id: Optional[str] = None
    ) -> Optional[Material]:
        """
        Look up material by preset parameters.

        Generates the lookup hash and queries the Material DB.

        Args:
            tool_type: Tool type (e.g., "short_video", "room_redesign")
            prompt: Main prompt text
            effect_prompt: Optional effect/style prompt
            input_image_id: Optional input image identifier

        Returns:
            Material with watermarked result if found, None otherwise
        """
        lookup_hash = Material.generate_lookup_hash(
            tool_type=tool_type,
            prompt=prompt,
            effect_prompt=effect_prompt,
            input_image_id=input_image_id
        )
        return await self.lookup_by_hash(lookup_hash)

    async def get_presets_for_tool(
        self,
        tool_type: str,
        topic: Optional[str] = None,
        limit: int = 20,
        product_id: Optional[str] = None,
        platform: Optional[str] = None,
        role: Optional[str] = None,
    ) -> List[Material]:
        """
        Get available presets for a tool.

        Args:
            tool_type: Tool type to get presets for
            topic: Optional topic filter
            limit: Maximum number of presets to return
            product_id: Optional product_id filter (matches input_params->>'product_id')
            platform: Optional Material.platform filter (e.g. 'instagram')
            role: Optional Material.role filter (e.g. 'creator')

        Returns:
            List of Material presets with results (watermarked preferred, fallback to original)
        """
        try:
            tool_enum = ToolType(tool_type)
        except ValueError:
            logger.warning(f"Invalid tool type: {tool_type}")
            return []

        # PRESET-ONLY MODE: Accept materials with any non-empty result URL
        # isnot(None) alone is insufficient — empty strings ("") also pass; use != "" too.
        def _has_url(col):
            return and_(col.isnot(None), col != "")

        conditions = [
            Material.tool_type == tool_enum,
            Material.is_active == True,
            Material.status.in_([MaterialStatus.APPROVED, MaterialStatus.FEATURED]),
            or_(
                _has_url(Material.result_watermarked_url),
                _has_url(Material.result_video_url),
                _has_url(Material.result_image_url),
            ),
            or_(Material.input_params["readiness_seed"].astext.is_(None), Material.input_params["readiness_seed"].astext != "true"),
            or_(Material.input_params["reused_generated_media"].astext.is_(None), Material.input_params["reused_generated_media"].astext != "true"),
            # Exclude user-session demo generations that leaked into public
            # presets: the homepage try_on surfaced visitors' own "garment-user"
            # uploads (often arbitrary Unsplash URLs) instead of curated pairs.
            # Curated try_on presets always carry a real garment id
            # (garment-coat, garment-tshirt, …), never the garment-user marker,
            # so this is a no-op for every other tool (clothing_id is NULL).
            or_(
                Material.input_params["clothing_id"].astext.is_(None),
                Material.input_params["clothing_id"].astext != "garment-user",
            ),
            or_(
                Material.prompt.is_(None),
                and_(
                    ~Material.prompt.ilike("VidGo readiness%"),
                    ~Material.prompt.ilike("VidGo landing%"),
                ),
            ),
            or_(
                Material.prompt_zh.is_(None),
                and_(
                    ~Material.prompt_zh.ilike("VidGo readiness%"),
                    ~Material.prompt_zh.ilike("VidGo landing%"),
                ),
            ),
        ]

        if topic:
            conditions.append(Material.topic == topic)

        if platform:
            conditions.append(Material.platform == platform)
        if role:
            conditions.append(Material.role == role)

        if product_id:
            # Each tool stores its primary selector under a different key in
            # input_params. Get this wrong and the WHERE clause matches no
            # rows, so callers fall back to a random preset — which is how
            # selecting an Asian female try-on model could surface a male
            # foreign one. Keep this in sync with DemoCacheService._get_from_db.
            if tool_enum == ToolType.AI_AVATAR:
                selector_key = "avatar_id"
            elif tool_enum == ToolType.TRY_ON:
                selector_key = "model_id"
            else:
                selector_key = "product_id"
            conditions.append(Material.input_params[selector_key].astext == product_id)

        from sqlalchemy import case as sa_case
        featured_first = sa_case(
            (Material.status == MaterialStatus.FEATURED, 0), else_=1
        )
        result = await self.db.execute(
            select(Material)
            .where(and_(*conditions))
            .order_by(featured_first, Material.sort_order, Material.quality_score.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_random_preset(
        self,
        tool_type: str,
        topic: Optional[str] = None,
        exclude_ids: Optional[List[str]] = None
    ) -> Optional[Material]:
        """
        Get a random preset for a tool, optionally excluding already-viewed ones.

        Args:
            tool_type: Tool type
            topic: Optional topic filter
            exclude_ids: List of material IDs to exclude

        Returns:
            Random Material preset or None if no presets available
        """
        from sqlalchemy.sql.expression import func
        from sqlalchemy import or_

        try:
            tool_enum = ToolType(tool_type)
        except ValueError:
            return None

        # PRESET-ONLY MODE: Accept materials with any result URL
        conditions = [
            Material.tool_type == tool_enum,
            Material.is_active == True,
            Material.status.in_([MaterialStatus.APPROVED, MaterialStatus.FEATURED]),
            or_(
                Material.result_watermarked_url.isnot(None),
                Material.result_video_url.isnot(None),
                Material.result_image_url.isnot(None)
            )
        ]

        if topic:
            conditions.append(Material.topic == topic)

        if exclude_ids:
            conditions.append(Material.id.notin_(exclude_ids))

        result = await self.db.execute(
            select(Material)
            .where(and_(*conditions))
            .order_by(func.random())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def increment_use_count(self, material_id: str) -> None:
        """
        Increment the use count for a material.

        Args:
            material_id: UUID of the material
        """
        material = await self.lookup_by_id(material_id)
        if material:
            material.use_count = (material.use_count or 0) + 1
            await self.db.commit()


def get_material_lookup_service(db: AsyncSession) -> MaterialLookupService:
    """Factory function to create MaterialLookupService instance."""
    return MaterialLookupService(db)
