#!/usr/bin/env python3
"""
Material DB Watcher - Check status and wait until examples are enough.

When Material DB is ready:
  - If examples are enough → exit 0 (full stack services start)
  - Else → keep waiting, check again

Usage:
  python -m scripts.wait_for_materials --wait
  python -m scripts.wait_for_materials --wait --generate   # Run pregen if empty
"""
import asyncio
import argparse
import logging
import subprocess
import sys
import time

sys.path.insert(0, "/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Required tools - must have minimum examples for service to start
MIN_PER_TOOL = {
    "product_scene": 3,
    "effect": 3,
    "background_removal": 3,
    "short_video": 3,
    "ai_avatar": 3,
}
REQUIRED_TOOLS = list(MIN_PER_TOOL.keys())
# Optional: room_redesign, pattern_generate, try_on (don't block startup)


async def wait_for_db(max_wait: int = 120) -> bool:
    from sqlalchemy import text
    from app.core.database import engine

    start = time.time()
    while (time.time() - start) < max_wait:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            await asyncio.sleep(2)
    return False


async def check_status() -> tuple[bool, dict]:
    """Check if Material DB has enough examples. Returns (enough, counts)."""
    from sqlalchemy import select, func, and_, or_
    from app.core.database import AsyncSessionLocal
    from app.models.material import Material

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Material.tool_type, func.count(Material.id).label("cnt"))
            .where(
                and_(
                    Material.is_active == True,
                    or_(
                        Material.result_image_url.isnot(None),
                        Material.result_video_url.isnot(None),
                    ),
                )
            )
            .group_by(Material.tool_type)
        )
        rows = result.all()

    counts = {}
    for row in rows:
        tt = row.tool_type.value if hasattr(row.tool_type, "value") else str(row.tool_type)
        counts[tt] = row.cnt

    enough = True
    for tool in REQUIRED_TOOLS:
        c = counts.get(tool, 0)
        m = MIN_PER_TOOL[tool]
        status = "OK" if c >= m else "WAIT"
        logger.info("  %s: %d/%d [%s]", tool, c, m, status)
        if c < m:
            enough = False

    return enough, counts


def run_pregenerate(timeout: int = 7200) -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "scripts.main_pregenerate", "--all"],
        cwd="/app",
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode == 0


async def main() -> int:
    if __import__("os").environ.get("SKIP_MATERIAL_WATCHER") == "true":
        print("SKIP_MATERIAL_WATCHER=true - skipping, exit 0")
        return 0

    parser = argparse.ArgumentParser(description="Check Material DB status. Exit 0 when enough examples.")
    parser.add_argument("--wait", action="store_true", help="Keep waiting until enough")
    parser.add_argument("--generate", action="store_true", help="Run main_pregenerate --all when empty")
    parser.add_argument("--timeout", type=int, default=10800, help="Max wait seconds (default: 10800)")
    parser.add_argument("--interval", type=int, default=30, help="Check interval seconds (default: 30)")
    args = parser.parse_args()

    logger.info("Waiting for Material DB...")
    if not await wait_for_db():
        logger.error("Material DB not reachable")
        return 1
    logger.info("Material DB ready")

    logger.info("Running migrations...")
    r = subprocess.run(["alembic", "upgrade", "head"], cwd="/app", capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        logger.error("Migrations failed")
        return 1

    subprocess.run([sys.executable, "-m", "scripts.seed_service_pricing"], cwd="/app", capture_output=True, timeout=30)

    start = time.time()
    generated = False

    while True:
        logger.info("Checking Material DB status...")
        enough, counts = await check_status()

        if enough:
            logger.info("Examples enough - full stack services can start")
            return 0

        elapsed = time.time() - start
        if elapsed >= args.timeout:
            logger.error("Timeout. Examples not enough.")
            return 1

        total = sum(counts.get(t, 0) for t in REQUIRED_TOOLS)
        if args.generate and total == 0 and not generated:
            logger.info("DB empty - running main_pregenerate --all...")
            run_pregenerate(timeout=min(7200, args.timeout - int(elapsed)))
            generated = True
            continue

        if not args.wait:
            logger.warning("Examples not enough. Use --wait to keep waiting.")
            return 1

        logger.info("Waiting %ds (timeout in %ds)...", args.interval, int(args.timeout - elapsed))
        await asyncio.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
