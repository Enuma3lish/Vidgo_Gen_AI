"""
Avatar Pre-generation at Service Startup

This script is called when the backend service starts.
It checks if avatar examples exist for each language (EN, zh-TW)
and generates them if missing.

Usage:
    Called automatically at service startup
    Or manually: python -m scripts.startup_avatars
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func
from app.core.database import AsyncSessionLocal
from app.models.material import Material, ToolType, MaterialStatus, MaterialSource, AVATAR_SCRIPTS, MATERIAL_TOPICS
from app.services.pollo_avatar import PolloAvatarService, DEFAULT_AVATARS
from app.core.config import get_settings
import uuid
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

settings = get_settings()

# Static directory for storing generated materials
STATIC_DIR = Path("/app/static/materials")

# Minimum avatars required per language per topic
MIN_AVATARS_PER_TOPIC = 2


async def check_avatar_sufficiency() -> dict:
    """
    Check if we have enough avatar examples for each language/topic.

    Returns:
        Dict with missing counts per language/topic
    """
    async with AsyncSessionLocal() as session:
        missing = {}

        for lang in ["en", "zh-TW"]:
            missing[lang] = {}
            lang_scripts = AVATAR_SCRIPTS.get(lang, {})

            for topic in lang_scripts.keys():
                # Count existing avatars for this language/topic
                query = select(func.count(Material.id)).where(
                    Material.tool_type == ToolType.AI_AVATAR,
                    Material.language == lang,
                    Material.topic == topic,
                    Material.status == MaterialStatus.APPROVED,
                    Material.is_active == True,
                    Material.result_video_url.isnot(None)
                )
                result = await session.execute(query)
                current_count = result.scalar() or 0

                needed = max(0, MIN_AVATARS_PER_TOPIC - current_count)
                if needed > 0:
                    missing[lang][topic] = {
                        "current": current_count,
                        "needed": needed,
                        "scripts": lang_scripts[topic][:needed]  # Get scripts to generate
                    }

        return missing


async def generate_missing_avatars(missing: dict) -> dict:
    """
    Generate missing avatar examples.

    Args:
        missing: Dict from check_avatar_sufficiency

    Returns:
        Dict with generation results
    """
    avatar_service = PolloAvatarService()
    results = {"generated": 0, "failed": 0, "skipped": 0}

    # Ensure static directory exists
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    async with AsyncSessionLocal() as session:
        for lang, topics in missing.items():
            for topic, info in topics.items():
                logger.info(f"Generating {info['needed']} avatars for {lang}/{topic}")

                for script in info["scripts"]:
                    try:
                        # Get a random avatar image for this language
                        import random
                        avatars = DEFAULT_AVATARS.get(lang, DEFAULT_AVATARS["en"])
                        avatar_image = random.choice(avatars)

                        logger.info(f"  Generating: {script[:50]}...")

                        # Generate avatar video (Pollo v2-0 only accepts 5 or 10 seconds)
                        result = await avatar_service.generate_and_wait(
                            image_url=avatar_image,
                            script=script,
                            language=lang,
                            duration=5,  # Use 5 seconds for pre-generated avatars
                            timeout=300,
                            save_locally=True
                        )

                        if result.get("success"):
                            # Save to material DB
                            material = Material(
                                tool_type=ToolType.AI_AVATAR,
                                topic=topic,
                                language=lang,
                                tags=[topic, "ai_avatar", lang, "seed"],
                                source=MaterialSource.SEED,
                                status=MaterialStatus.APPROVED,
                                prompt=script,
                                prompt_enhanced=script,
                                input_image_url=avatar_image,
                                generation_steps=[{
                                    "step": 1,
                                    "api": "pollo-avatar",
                                    "action": "photo_to_avatar",
                                    "language": lang,
                                    "input": {"script": script, "image": avatar_image},
                                    "result_url": result["video_url"],
                                    "cost": 0.15
                                }],
                                result_video_url=result["video_url"],
                                generation_cost_usd=0.15,
                                quality_score=0.9,
                                is_active=True
                            )

                            # Set language-specific title
                            if lang == "zh-TW":
                                material.title_zh = script[:100]
                                material.title_en = f"Avatar: {topic}"
                            else:
                                material.title_en = script[:100]

                            session.add(material)
                            await session.commit()

                            results["generated"] += 1
                            logger.info(f"  ✓ Avatar saved: {material.id}")
                        else:
                            results["failed"] += 1
                            logger.warning(f"  ✗ Failed: {result.get('error')}")

                        # Rate limiting
                        await asyncio.sleep(3)

                    except Exception as e:
                        logger.error(f"  ✗ Error: {e}")
                        results["failed"] += 1
                        continue

    return results


async def run_startup_avatar_check():
    """
    Main function called at service startup.
    Checks and generates missing avatar examples.
    """
    logger.info("=" * 60)
    logger.info("AVATAR PRE-GENERATION CHECK")
    logger.info("=" * 60)

    # Check what's missing
    missing = await check_avatar_sufficiency()

    # Count total missing
    total_missing = sum(
        info["needed"]
        for lang_topics in missing.values()
        for info in lang_topics.values()
    )

    if total_missing == 0:
        logger.info("✓ All avatar examples are sufficient. No generation needed.")
        return {"status": "sufficient", "missing": 0}

    logger.info(f"Missing {total_missing} avatar examples. Starting generation...")

    # Show what's missing
    for lang, topics in missing.items():
        if topics:
            logger.info(f"\n{lang}:")
            for topic, info in topics.items():
                logger.info(f"  - {topic}: need {info['needed']} more (have {info['current']})")

    # Generate missing avatars
    results = await generate_missing_avatars(missing)

    logger.info("\n" + "=" * 60)
    logger.info("AVATAR PRE-GENERATION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Generated: {results['generated']}")
    logger.info(f"Failed: {results['failed']}")

    return {
        "status": "generated",
        "missing": total_missing,
        "results": results
    }


if __name__ == "__main__":
    asyncio.run(run_startup_avatar_check())
