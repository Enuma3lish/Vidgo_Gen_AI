#!/usr/bin/env python3
"""
Audit Material DB: prompt confidence, topic correctness, Ads-only for Effect.

Checks:
1. All materials have valid topic (matches topic_registry for that tool)
2. Effect tool: effect_prompt should be Ads-oriented, NOT creative
3. Prompt correctness and consistency
"""
import asyncio
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.material import Material, ToolType
from app.config.topic_registry import TOOL_TOPICS, get_topic_ids_for_tool

# Ads-related keywords (effect should contain these)
ADS_KEYWORDS = ["ads", "ad", "advertisement", "menu", "branding", "marketing", "social media", "flyer", "product", "retail", "shop", "cafe", "restaurant", "promo", "e-commerce", "電商", "廣告", "菜單", "品牌", "社群", "行銷", "促銷"]

# Creative-only keywords (effect should NOT emphasize these without Ads context)
CREATIVE_ONLY = ["artistic expression", "creative art", "personal art", "純藝術", "藝術創作"]


async def audit():
    print("=" * 70)
    print("Material DB Audit: Prompts, Topic Correctness, Ads-only for Effect")
    print("=" * 70)

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

    print(f"\nTotal active materials with results: {len(materials)}")

    # Group by tool_type
    by_tool = {}
    for m in materials:
        tt = m.tool_type.value if hasattr(m.tool_type, "value") else str(m.tool_type)
        by_tool.setdefault(tt, []).append(m)

    # Valid topics per tool
    valid_topics = {}
    for tool in TOOL_TOPICS:
        valid_topics[tool] = set(get_topic_ids_for_tool(tool))

    issues = []
    effect_ads_check = {"ok": 0, "no_ads_keyword": 0, "creative_only": 0}

    for tt, mats in sorted(by_tool.items()):
        print(f"\n--- {tt} ({len(mats)} materials) ---")
        valid = valid_topics.get(tt, set())

        for m in mats:
            # Topic check
            if valid and m.topic not in valid:
                issues.append({"tool": tt, "id": str(m.id), "issue": "topic_mismatch", "topic": m.topic, "valid": list(valid)[:5]})

            # Effect-specific: Ads-only check
            if tt == "effect" and m.effect_prompt:
                ep_lower = (m.effect_prompt or "").lower()
                has_ads = any(kw in ep_lower for kw in ["ads", "ad", "menu", "branding", "marketing", "social", "flyer", "product", "retail", "shop", "cafe", "restaurant", "promo", "電商", "廣告", "菜單", "品牌", "社群", "行銷", "促銷", "business", "small business"])
                has_creative_only = any(kw in ep_lower for kw in ["artistic expression", "creative art", "personal art", "純藝術"])
                if has_creative_only and not has_ads:
                    effect_ads_check["creative_only"] += 1
                    issues.append({"tool": tt, "id": str(m.id), "issue": "effect_creative_only", "effect_prompt": (m.effect_prompt or "")[:80]})
                elif not has_ads:
                    effect_ads_check["no_ads_keyword"] += 1
                    issues.append({"tool": tt, "id": str(m.id), "issue": "effect_not_ads", "effect_prompt": (m.effect_prompt or "")[:80]})
                else:
                    effect_ads_check["ok"] += 1

        # Summary for this tool
        invalid_topics = [m for m in mats if valid and m.topic not in valid]
        if invalid_topics:
            print(f"  Topic mismatches: {len(invalid_topics)} (valid: {list(valid)})")
        else:
            print(f"  Topics: OK (valid set: {list(valid)[:8]}...)")

    # Effect Ads summary
    if "effect" in by_tool:
        print(f"\n--- Effect Ads Check ---")
        print(f"  OK (Ads-oriented): {effect_ads_check['ok']}")
        print(f"  No Ads keyword: {effect_ads_check['no_ads_keyword']}")
        print(f"  Creative-only (bad): {effect_ads_check['creative_only']}")

    # Report issues
    print(f"\n--- Issues ({len(issues)}) ---")
    for i in issues[:20]:
        print(f"  [{i['tool']}] {i['issue']}: {i.get('topic', i.get('effect_prompt', ''))[:60]}")
    if len(issues) > 20:
        print(f"  ... and {len(issues) - 20} more")

    print("\n" + "=" * 70)
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(audit()))
