"""
Public hero-demo-pair endpoint — reads the curated BEFORE/AFTER pairs
that drive the landing page hero rotation.

Kept separate from the admin router so it can stay unauthenticated
(homepage anonymous traffic) while the regeneration / write paths sit
behind /admin/hero/* with require_admin().
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.hero_demo_pair import HeroDemoPair

router = APIRouter(prefix="/hero", tags=["hero"])


def _serialize(row: HeroDemoPair) -> Dict[str, Any]:
    return {
        "tool_type": row.tool_type,
        "slug": row.slug,
        "before_url": row.before_url,
        "after_url": row.after_url,
        "label_en": row.label_en,
        "label_zh": row.label_zh,
        "display_order": row.display_order,
    }


@router.get("/pairs")
async def public_hero_pairs(db: AsyncSession = Depends(get_db)) -> Dict[str, List[Dict[str, Any]]]:
    """Return all hero pairs that have an AFTER image generated.

    Excludes pairs with NULL after_url so the landing page never renders
    a half-baked demo. The frontend overlays a static FALLBACK (the
    LandingPage.vue constant) as a last resort when this endpoint returns
    empty — handy for fresh deploys before the admin has run the
    regeneration step.
    """
    rows = (
        await db.execute(
            select(HeroDemoPair)
            .where(HeroDemoPair.after_url.is_not(None))
            .order_by(
                HeroDemoPair.tool_type,
                HeroDemoPair.display_order,
                HeroDemoPair.id,
            )
        )
    ).scalars().all()
    return {"pairs": [_serialize(r) for r in rows]}
