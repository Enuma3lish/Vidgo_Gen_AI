#!/usr/bin/env python3
"""
Startup Check Script for VidGo Platform

This script validates that all required demo materials and prompt templates
are ready before allowing the service to start.

IMPORTANT: The service will NOT start if:
- Demo templates are missing cached results
- Required materials are not generated
- Database is not accessible

Usage:
    python -m scripts.startup_check [--wait] [--timeout 300] [--generate]

Options:
    --wait      Wait for materials to be ready instead of failing immediately
    --timeout   Maximum wait time in seconds (default: 300)
    --generate  Generate missing materials if found
    --min-templates  Minimum templates required per group (default: 3)
"""
import asyncio
import argparse
import sys
import time
import logging
from datetime import datetime
from typing import Dict, List, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def check_database_connection() -> bool:
    """Check if database is accessible."""
    try:
        from app.core.database import engine
        from sqlalchemy import text

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("✅ Database connection: OK")
        return True
    except Exception as e:
        logger.error(f"❌ Database connection: FAILED - {e}")
        return False


async def check_prompt_templates(min_per_group: int = 3) -> Tuple[bool, Dict[str, int]]:
    """
    Check if all prompt template groups have minimum required cached templates.

    Args:
        min_per_group: Minimum number of cached templates required per group

    Returns:
        Tuple of (all_ready: bool, group_counts: dict)
    """
    try:
        from app.core.database import AsyncSessionLocal
        from app.models.prompt_template import PromptTemplate, PromptGroup
        from sqlalchemy import select, func, and_

        async with AsyncSessionLocal() as db:
            # Count cached templates per group
            result = await db.execute(
                select(
                    PromptTemplate.group,
                    func.count(PromptTemplate.id).label("count")
                ).where(
                    and_(
                        PromptTemplate.is_active == True,
                        PromptTemplate.is_default == True,
                        PromptTemplate.is_cached == True,
                    )
                ).group_by(PromptTemplate.group)
            )

            group_counts = {row.group.value: row.count for row in result.all()}

            # Check each required group
            required_groups = [
                PromptGroup.BACKGROUND_REMOVAL,
                PromptGroup.BACKGROUND_CHANGE,
                PromptGroup.PRODUCT_EFFECT,
                PromptGroup.ROOM_REDESIGN,
                PromptGroup.IMAGE_TO_VIDEO,
                PromptGroup.STYLE_TRANSFER,
            ]

            all_ready = True
            for group in required_groups:
                count = group_counts.get(group.value, 0)
                if count < min_per_group:
                    logger.warning(
                        f"⚠️  Group '{group.value}': {count}/{min_per_group} cached templates"
                    )
                    all_ready = False
                else:
                    logger.info(
                        f"✅ Group '{group.value}': {count} cached templates"
                    )

            return all_ready, group_counts

    except Exception as e:
        logger.error(f"❌ Prompt template check failed: {e}")
        return False, {}


async def check_materials() -> Tuple[bool, Dict[str, int]]:
    """
    Check if materials are seeded and have results.

    Returns:
        Tuple of (all_ready: bool, tool_counts: dict)
    """
    try:
        from app.core.database import AsyncSessionLocal
        from app.models.material import Material, ToolType
        from sqlalchemy import select, func, and_, or_

        async with AsyncSessionLocal() as db:
            # Count materials with results per tool type
            result = await db.execute(
                select(
                    Material.tool_type,
                    func.count(Material.id).label("count")
                ).where(
                    and_(
                        Material.is_active == True,
                        or_(
                            Material.result_image_url.isnot(None),
                            Material.result_video_url.isnot(None),
                        )
                    )
                ).group_by(Material.tool_type)
            )

            tool_counts = {row.tool_type.value: row.count for row in result.all()}

            # Minimum required materials per tool
            # Critical tools (must have): BACKGROUND_REMOVAL, SHORT_VIDEO
            # Optional tools (nice to have): PRODUCT_SCENE, TRY_ON, ROOM_REDESIGN, AI_AVATAR
            min_required = {
                ToolType.BACKGROUND_REMOVAL: 1,  # Required: landing page
                ToolType.SHORT_VIDEO: 1,          # Required: landing page
            }

            # Optional tools - log but don't block startup
            optional_tools = {
                ToolType.PRODUCT_SCENE: 0,
                ToolType.TRY_ON: 0,
                ToolType.ROOM_REDESIGN: 0,
                ToolType.AI_AVATAR: 0,
            }

            all_ready = True

            # Check required tools
            for tool, min_count in min_required.items():
                count = tool_counts.get(tool.value, 0)
                if count < min_count:
                    logger.warning(
                        f"⚠️  Tool '{tool.value}': {count}/{min_count} materials ready (REQUIRED)"
                    )
                    all_ready = False
                else:
                    logger.info(
                        f"✅ Tool '{tool.value}': {count} materials ready"
                    )

            # Log optional tools (info only, don't block startup)
            for tool, _ in optional_tools.items():
                count = tool_counts.get(tool.value, 0)
                if count > 0:
                    logger.info(f"✅ Tool '{tool.value}': {count} materials ready")
                else:
                    logger.info(f"ℹ️  Tool '{tool.value}': 0 materials (optional)")

            return all_ready, tool_counts

    except Exception as e:
        logger.error(f"❌ Material check failed: {e}")
        return False, {}


async def generate_missing_materials():
    """Generate missing demo materials and templates."""
    try:
        from app.core.database import AsyncSessionLocal
        from app.services.prompt_generator import PromptGeneratorService

        logger.info("🔄 Generating missing materials...")

        async with AsyncSessionLocal() as db:
            service = PromptGeneratorService(db)
            counts = await service.seed_default_prompts()
            logger.info(f"✅ Seeded prompts: {counts}")

        # Additional material generation would go here
        # This could call the material generator service

        return True
    except Exception as e:
        logger.error(f"❌ Material generation failed: {e}")
        return False


async def run_startup_check(
    wait: bool = False,
    timeout: int = 300,
    generate: bool = False,
    min_templates: int = 3,
) -> bool:
    """
    Run all startup checks.

    Args:
        wait: Wait for checks to pass instead of failing immediately
        timeout: Maximum wait time in seconds
        generate: Generate missing materials if found
        min_templates: Minimum templates required per group

    Returns:
        True if all checks pass, False otherwise
    """
    start_time = time.time()

    logger.info("=" * 60)
    logger.info("VidGo Startup Check")
    logger.info("=" * 60)
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info(f"Wait mode: {wait}")
    logger.info(f"Timeout: {timeout}s")
    logger.info(f"Auto-generate: {generate}")
    logger.info(f"Min templates per group: {min_templates}")
    logger.info("=" * 60)

    while True:
        elapsed = time.time() - start_time

        if elapsed > timeout:
            logger.error(f"❌ Startup check timed out after {timeout}s")
            return False

        # Check database
        db_ok = await check_database_connection()
        if not db_ok:
            if wait:
                logger.info("⏳ Waiting for database...")
                await asyncio.sleep(5)
                continue
            else:
                return False

        # Generate materials if requested
        if generate:
            await generate_missing_materials()

        # Check prompt templates
        logger.info("\n--- Prompt Template Check ---")
        templates_ok, template_counts = await check_prompt_templates(min_templates)

        # Check materials
        logger.info("\n--- Material Check ---")
        materials_ok, material_counts = await check_materials()

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("Startup Check Summary")
        logger.info("=" * 60)
        logger.info(f"Database: {'✅ OK' if db_ok else '❌ FAILED'}")
        logger.info(f"Prompt Templates: {'✅ OK' if templates_ok else '⚠️  INCOMPLETE'}")
        logger.info(f"Materials: {'✅ OK' if materials_ok else '⚠️  INCOMPLETE'}")

        all_ok = db_ok and templates_ok and materials_ok

        if all_ok:
            logger.info("\n✅ All startup checks passed!")
            logger.info("=" * 60)
            return True
        elif wait:
            logger.info(f"\n⏳ Not all checks passed. Waiting... ({int(elapsed)}/{timeout}s)")
            await asyncio.sleep(10)
        else:
            logger.error("\n❌ Startup checks failed!")
            logger.error("Service cannot start without required materials.")
            logger.error("Run with --generate to create missing materials.")
            logger.error("Run with --wait to wait for materials to be ready.")
            logger.info("=" * 60)
            return False


def main():
    parser = argparse.ArgumentParser(
        description="VidGo Startup Check - Validates demo materials before service start"
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for materials to be ready instead of failing immediately"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Maximum wait time in seconds (default: 300)"
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate missing materials if found"
    )
    parser.add_argument(
        "--min-templates",
        type=int,
        default=3,
        help="Minimum cached templates required per group (default: 3)"
    )

    args = parser.parse_args()

    success = asyncio.run(
        run_startup_check(
            wait=args.wait,
            timeout=args.timeout,
            generate=args.generate,
            min_templates=args.min_templates,
        )
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
