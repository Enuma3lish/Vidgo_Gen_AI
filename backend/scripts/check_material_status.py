#!/usr/bin/env python3
"""
Material DB status check.

Checks all 8 tools for minimum required examples with results.
Exit 0 if enough examples per tool, else exit 1.

Usage:
    python -m scripts.check_material_status
    python -m scripts.check_material_status --min 3
    python -m scripts.check_material_status --tool ai_avatar
    python -m scripts.check_material_status --quiet
"""
import asyncio
import argparse
import sys

sys.path.insert(0, "/app")

# Required tools - must have minimum examples for service to start
REQUIRED_TOOLS_MIN = {
    "product_scene": 3,
    "effect": 3,
    "background_removal": 3,
    "ai_avatar": 3,
}

# Optional tools - nice to have, won't block startup
OPTIONAL_TOOLS_MIN = {
    "short_video": 3,  # Requires Pollo credits - optional until funded
    "room_redesign": 2,
    "pattern_generate": 2,
    "try_on": 2,
}

# Combined for display/filtering
MIN_PER_TOOL = {**REQUIRED_TOOLS_MIN, **OPTIONAL_TOOLS_MIN}
REQUIRED_TOOLS = list(REQUIRED_TOOLS_MIN.keys())


async def check(tool_filter: str = None) -> dict:
    """Returns counts per tool type."""
    from sqlalchemy import select, func, and_, or_
    from app.core.database import AsyncSessionLocal
    from app.models.material import Material

    async with AsyncSessionLocal() as db:
        query = (
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
        result = await db.execute(query)
        rows = result.all()

    counts = {}
    for row in rows:
        tt = row.tool_type.value if hasattr(row.tool_type, "value") else str(row.tool_type)
        counts[tt] = row.cnt
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Material DB status. Exit 0 when enough.")
    parser.add_argument("--min", type=int, default=0, help="Override min examples per tool (0 = use defaults)")
    parser.add_argument("--tool", type=str, default=None, help="Check only a specific tool")
    parser.add_argument("--quiet", action="store_true", help="No output")
    args = parser.parse_args()

    try:
        counts = asyncio.run(check(args.tool))
    except Exception as e:
        print(f"Check failed: {e}", file=sys.stderr)
        return 1

    # When checking a specific tool, use that tool's minimum
    if args.tool:
        tools_to_check = [args.tool]
    else:
        tools_to_check = REQUIRED_TOOLS

    enough = True

    # Check required tools (block startup if not enough)
    for tool in tools_to_check:
        c = counts.get(tool, 0)
        min_required = args.min if args.min > 0 else MIN_PER_TOOL.get(tool, 3)
        if c < min_required:
            enough = False
        if not args.quiet:
            ok = "OK" if c >= min_required else "WAIT"
            print(f"  {tool}: {c}/{min_required} [{ok}]")

    # Show optional tools status (info only, don't block startup)
    if not args.tool and not args.quiet:
        for tool, min_req in OPTIONAL_TOOLS_MIN.items():
            c = counts.get(tool, 0)
            status = "OK" if c >= min_req else "OPTIONAL"
            print(f"  {tool}: {c}/{min_req} [{status}]")

    if not args.quiet:
        total = sum(counts.values())
        print(f"  Total materials: {total}")

    return 0 if enough else 1


if __name__ == "__main__":
    sys.exit(main())
