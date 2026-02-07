#!/usr/bin/env python3
"""
Replace non-ads materials: selectively delete only non-conforming materials,
then optionally run pregenerate to fill gaps.

Ads scope: common purpose (food, general product) — NOT luxury.
Non-conforming:
- effect: effect_prompt lacks ads keywords
- short_video: prompt contains luxury/premium
- ai_avatar: prompt contains luxury/premium (scripts are in SCRIPT_MAPPING; stored prompt checked)

Usage:
  python -m scripts.replace_non_ads_materials              # Dry-run: report only
  python -m scripts.replace_non_ads_materials --delete     # Soft-delete non-conforming
  python -m scripts.replace_non_ads_materials --delete --pregenerate  # Delete + run pregen
"""
import argparse
import asyncio
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select, update
from app.core.database import AsyncSessionLocal
from app.models.material import Material, ToolType

# Ads-related keywords (effect should contain these)
ADS_KEYWORDS = [
    "ads", "ad", "advertisement", "menu", "branding", "marketing", "social media",
    "flyer", "product", "retail", "shop", "cafe", "restaurant", "promo", "e-commerce",
    "電商", "廣告", "菜單", "品牌", "社群", "行銷", "促銷", "business", "small business"
]

# Luxury/premium keywords — materials with these should be replaced (common ads focus)
LUXURY_KEYWORDS = [
    "luxury", "premium", "high-end", "高端", "奢華", "精品", "奢華美妝",
    "premium beauty", "luxury cosmetics", "minimal luxury", "頂級", "高端美妝"
]


def _effect_non_conforming(m) -> bool:
    """Effect: non-conforming if effect_prompt lacks ads context."""
    ep = (m.effect_prompt or "").lower()
    if not ep:
        return True  # No effect_prompt is non-conforming
    return not any(kw in ep for kw in [k.lower() for k in ADS_KEYWORDS])


def _short_video_non_conforming(m) -> bool:
    """Short video: non-conforming if prompt has luxury focus."""
    p = (m.prompt or "") + (m.prompt_zh or "")
    p_lower = p.lower()
    return any(kw in p_lower for kw in LUXURY_KEYWORDS)


def _ai_avatar_non_conforming(m) -> bool:
    """AI Avatar: non-conforming if prompt has luxury focus."""
    p = (m.prompt or "") + (m.prompt_zh or "")
    p_lower = p.lower()
    return any(kw in p_lower for kw in LUXURY_KEYWORDS)


async def find_non_conforming(dry_run: bool = True):
    """Find non-conforming materials. Returns list of (tool_type, material_id, reason)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Material)
            .where(Material.is_active == True)
            .where(
                (Material.result_image_url.isnot(None))
                | (Material.result_watermarked_url.isnot(None))
                | (Material.result_video_url.isnot(None))
            )
        )
        materials = result.scalars().all()

    to_delete = []
    for m in materials:
        tt = m.tool_type.value if hasattr(m.tool_type, "value") else str(m.tool_type)
        if tt == "effect":
            if _effect_non_conforming(m):
                to_delete.append((tt, str(m.id), "effect_prompt lacks ads context"))
        elif tt == "short_video":
            if _short_video_non_conforming(m):
                to_delete.append((tt, str(m.id), "prompt has luxury/premium focus"))
        elif tt == "ai_avatar":
            if _ai_avatar_non_conforming(m):
                to_delete.append((tt, str(m.id), "prompt has luxury/premium focus"))

    return to_delete


async def soft_delete_materials(ids_to_delete: list[str]):
    """Soft-delete materials by setting is_active=False."""
    if not ids_to_delete:
        return 0
    import uuid
    uuids = []
    for s in ids_to_delete:
        try:
            uuids.append(uuid.UUID(s))
        except (ValueError, TypeError):
            pass
    if not uuids:
        return 0
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            update(Material).where(Material.id.in_(uuids)).values(is_active=False)
        )
        await db.commit()
        return r.rowcount


async def main():
    parser = argparse.ArgumentParser(description="Replace non-ads materials (selective delete)")
    parser.add_argument("--delete", action="store_true", help="Actually soft-delete non-conforming materials")
    parser.add_argument("--pregenerate", action="store_true", help="Run pregenerate after delete (effect, short_video, ai_avatar)")
    args = parser.parse_args()

    print("=" * 70)
    print("Replace Non-Ads Materials — Common Purpose (Food, General Product), NOT Luxury")
    print("=" * 70)

    to_delete = await find_non_conforming(dry_run=True)
    if not to_delete:
        print("\nNo non-conforming materials found. All materials conform to Ads (common use) focus.")
        print("=" * 70)
        return 0

    # Group by tool
    by_tool = {}
    for tt, mid, reason in to_delete:
        by_tool.setdefault(tt, []).append((mid, reason))

    print(f"\nNon-conforming materials to replace: {len(to_delete)}")
    for tt in sorted(by_tool.keys()):
        items = by_tool[tt]
        print(f"  {tt}: {len(items)}")
        for mid, reason in items[:5]:
            print(f"    - {mid[:8]}... ({reason})")
        if len(items) > 5:
            print(f"    ... and {len(items) - 5} more")

    if not args.delete:
        print("\n[DRY-RUN] No changes made. Use --delete to soft-delete these materials.")
        print("Then run: docker compose --profile tools run --rm pregenerate python -m scripts.main_pregenerate --tool effect --limit 40")
        print("         (and similarly for short_video, ai_avatar)")
        print("=" * 70)
        return 0

    ids = [mid for _, mid, _ in to_delete]
    deleted = await soft_delete_materials(ids)
    print(f"\nSoft-deleted {deleted} materials (is_active=False).")

    if args.pregenerate:
        print("\nRunning pregenerate for effect, short_video, ai_avatar...")
        # Subprocess to run pregenerate
        import subprocess
        for tool in ["effect", "short_video", "ai_avatar"]:
            cmd = ["python", "-m", "scripts.main_pregenerate", "--tool", tool, "--limit", "40"]
            try:
                subprocess.run(cmd, cwd="/app", check=True)
            except subprocess.CalledProcessError as e:
                print(f"  Warning: pregenerate {tool} failed: {e}")

    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
