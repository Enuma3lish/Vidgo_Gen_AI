#!/usr/bin/env python3
"""
Seed Materials When DB Is Empty

When Material DB has no entries for any of the 8 tools, this script runs
the pre-generation pipeline to populate with fixed prompts.

FLOW:
- product_scene: Use PRODUCT_SCENE_MAPPING (product x scene) -> T2I -> Remove BG -> Composite
- effect: Use EFFECT_MAPPING (source prompt x style) -> T2I source -> I2I style transfer
- background_removal: Use BACKGROUND_REMOVAL_MAPPING (topic x prompt) -> T2I -> PiAPI Remove BG
- room_redesign: Use room type x design style -> I2I room transformation
- short_video: Use content type x product -> T2I -> I2V
- ai_avatar: Use avatar x script -> TTS -> Lipsync
- pattern_generate: Use pattern style x application -> T2I pattern
- try_on: Use clothing x model -> Virtual Try-On API (requires model_library)

Usage:
    python -m scripts.seed_materials_if_empty
    python -m scripts.seed_materials_if_empty --force  # Re-run even if DB has some
    python -m scripts.seed_materials_if_empty --clean --tool ai_avatar  # Delete old + re-seed
    python -m scripts.seed_materials_if_empty --clean  # Delete ALL tools + re-seed
"""
import asyncio
import argparse
import logging
import os
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select, func, delete
from app.core.database import AsyncSessionLocal
from app.models.material import Material, ToolType

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# All 8 tools we seed for try-play (try_on last because it needs model_library).
# Set env SKIP_TRY_ON=1 to exclude try_on when PiAPI/Kling Virtual Try-On returns 500.
SEED_TOOLS = [
    "product_scene",
    "effect",
    "background_removal",
    "room_redesign",
    "short_video",
    "ai_avatar",
    "pattern_generate",
    "try_on",
]


def _get_seed_tools():
    """Return SEED_TOOLS, excluding try_on if SKIP_TRY_ON is set."""
    if os.environ.get("SKIP_TRY_ON"):
        return [t for t in SEED_TOOLS if t != "try_on"]
    return list(SEED_TOOLS)

# Per-tool limits for seed - enough for landing gallery and tool try-play
SEED_LIMITS = {
    "product_scene": 32,       # 8 products x 4 scenes - landing + tool presets
    "effect": 40,              # 8 sources x 5 styles - landing + tool presets
    "background_removal": 24,  # 8 topics x 3 prompts - landing + tool presets
    "room_redesign": 20,       # 4 rooms x 5 styles
    "short_video": 20,         # 4 content types x 5 products
    "ai_avatar": 24,           # 8 avatars x 3 scripts (subset)
    "pattern_generate": 20,    # 5 styles x 4 applications
    "try_on": 24,              # 6 clothing x 4 models (needs model_library first)
}


async def get_material_count(db, tool_type: str) -> int:
    """Count materials for a tool type."""
    result = await db.execute(
        select(func.count()).select_from(Material).where(
            Material.tool_type == ToolType(tool_type),
            Material.is_active == True,
        )
    )
    return result.scalar() or 0


async def delete_materials_for_tool(db, tool_type: str) -> int:
    """Delete all materials for a tool type. Returns count deleted."""
    count = await get_material_count(db, tool_type)
    if count == 0:
        return 0

    await db.execute(
        delete(Material).where(Material.tool_type == ToolType(tool_type))
    )
    await db.commit()
    logger.info(f"[{tool_type}] Deleted {count} old materials")
    return count


async def main():
    parser = argparse.ArgumentParser(description="Seed Materials when DB is empty")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run seed even if DB already has materials (will add more)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete existing materials before re-seeding (use with --tool to target specific tool)",
    )
    parser.add_argument(
        "--tool",
        type=str,
        choices=SEED_TOOLS,
        help="Only seed a specific tool (e.g. --tool ai_avatar)",
    )
    args = parser.parse_args()

    # Determine which tools to process (when no --tool, respect SKIP_TRY_ON)
    target_tools = [args.tool] if args.tool else _get_seed_tools()
    if not args.tool and os.environ.get("SKIP_TRY_ON"):
        logger.info("SKIP_TRY_ON is set: excluding try_on from this run (PiAPI/Kling may be unavailable).")

    # Clean mode: delete old materials first
    if args.clean:
        async with AsyncSessionLocal() as db:
            for tool in target_tools:
                deleted = await delete_materials_for_tool(db, tool)
                if deleted > 0:
                    logger.info(f"[{tool}] Cleaned {deleted} materials, ready for re-seed")
                else:
                    logger.info(f"[{tool}] No materials to clean")

    async with AsyncSessionLocal() as db:
        tools_to_seed = []
        for tool in target_tools:
            count = await get_material_count(db, tool)
            if count == 0 or args.force or args.clean:
                tools_to_seed.append((tool, count))
            else:
                logger.info(f"[{tool}] Already has {count} materials, skipping")

    if not tools_to_seed:
        logger.info("All tools have materials. Nothing to seed.")
        return

    # Import and run pregenerator
    from scripts.main_pregenerate import VidGoPreGenerator

    gen = VidGoPreGenerator()

    # Generate model_library first if try_on is in the list (try_on depends on it)
    if any(tool == "try_on" for tool, _ in tools_to_seed):
        logger.info("Generating model_library (required for try_on)...")
        try:
            await gen.generate_model_library(limit=6)
            logger.info("  Done: model_library")
        except Exception as e:
            logger.error(f"  Failed: model_library - {e}")

    for tool, prev_count in tools_to_seed:
        limit = SEED_LIMITS.get(tool, 20)
        logger.info(f"Seeding {tool} (prev: {prev_count}, limit: {limit})...")
        try:
            if tool == "product_scene":
                await gen.generate_product_scene(limit=limit)
            elif tool == "effect":
                await gen.generate_effect(limit=limit)
            elif tool == "background_removal":
                await gen.generate_background_removal(limit=limit)
            elif tool == "room_redesign":
                await gen.generate_room_redesign(limit=limit)
            elif tool == "short_video":
                await gen.generate_short_video(limit=limit)
            elif tool == "ai_avatar":
                await gen.generate_ai_avatar(limit=limit)
            elif tool == "pattern_generate":
                await gen.generate_pattern(limit=limit)
            elif tool == "try_on":
                await gen.generate_try_on(limit=limit)
            logger.info(f"  Done: {tool}")
        except Exception as e:
            logger.error(f"  Failed: {tool} - {e}")


if __name__ == "__main__":
    asyncio.run(main())
