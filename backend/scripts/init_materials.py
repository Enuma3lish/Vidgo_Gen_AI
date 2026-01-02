"""
Material Initialization Script

This script is run during environment setup to:
1. Check if we have sufficient showcase materials
2. Generate missing showcases using real APIs if needed
3. Skip generation if materials are already sufficient

Usage:
    # Check status only
    python -m scripts.init_materials --check

    # Generate missing materials
    python -m scripts.init_materials --generate

    # Generate with limit
    python -m scripts.init_materials --generate --limit 10

    # Force regenerate all (clears existing)
    python -m scripts.init_materials --force --generate

    # Dry run (show what would be generated)
    python -m scripts.init_materials --generate --dry-run

    # Generate for specific category
    python -m scripts.init_materials --generate --category ecommerce
"""
import asyncio
import sys
import argparse
import logging
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, "/app")

from sqlalchemy import delete
from app.core.database import AsyncSessionLocal
from app.models.demo import ToolShowcase
from app.services.material.library import MaterialLibraryService
from app.services.material.generator import RealShowcaseGenerator, GenerationProgress
from app.services.material.requirements import MATERIAL_REQUIREMENTS, get_total_required_showcases

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_header(title: str):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_progress(progress: GenerationProgress):
    """Print generation progress"""
    completed = progress.completed
    failed = progress.failed
    total = progress.total_tasks
    current = progress.current_task or "Done"

    pct = (completed + failed) / total * 100 if total > 0 else 100

    print(f"\r  Progress: [{completed}/{total}] {pct:.0f}% - {current}", end="", flush=True)


async def check_material_status() -> dict:
    """Check current material status"""
    async with AsyncSessionLocal() as session:
        library = MaterialLibraryService(session)

        # Get all requirements
        requirements = await library.get_all_requirements()

        # Get missing materials
        missing = await library.get_missing_materials()

        # Calculate totals
        total_required = sum(r.min_count for r in requirements)
        total_current = sum(r.current_count for r in requirements)
        total_missing = sum(r.missing_count for r in requirements)

        # Calculate sufficiency percentage
        sufficiency_pct = (total_current / total_required * 100) if total_required > 0 else 0

        return {
            "requirements": requirements,
            "missing": missing,
            "total_required": total_required,
            "total_current": total_current,
            "total_missing": total_missing,
            "sufficiency_pct": sufficiency_pct,
            "is_sufficient": total_missing == 0
        }


async def print_status_report():
    """Print detailed status report"""
    status = await check_material_status()

    print_header("Material Library Status")

    print(f"\n  Total Required:    {status['total_required']} showcases")
    print(f"  Currently Have:    {status['total_current']} showcases")
    print(f"  Missing:           {status['total_missing']} showcases")
    print(f"  Sufficiency:       {status['sufficiency_pct']:.1f}%")

    if status['is_sufficient']:
        print("\n  ✓ Material library is SUFFICIENT - no generation needed")
    else:
        print("\n  ✗ Material library is INSUFFICIENT - generation needed")

        print("\n  Missing by category:")
        for item in status['missing']:
            print(f"    - {item['category']}/{item['tool_id']}: "
                  f"need {item['missing_count']} more ({item['generation_type']})")

    return status


async def clear_existing_showcases():
    """Clear all existing showcases"""
    async with AsyncSessionLocal() as session:
        await session.execute(delete(ToolShowcase))
        await session.commit()
        logger.info("Cleared all existing showcases")


async def generate_materials(
    category: str = None,
    tool_id: str = None,
    limit: int = None,
    dry_run: bool = False
):
    """Generate missing materials"""
    async with AsyncSessionLocal() as session:
        generator = RealShowcaseGenerator(
            db=session,
            on_progress=print_progress
        )

        progress = await generator.generate_missing_showcases(
            category=category,
            tool_id=tool_id,
            limit=limit,
            dry_run=dry_run
        )

        print()  # New line after progress
        return progress


async def main():
    parser = argparse.ArgumentParser(
        description="Initialize and manage material library",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Check status:           python -m scripts.init_materials --check
  Generate missing:       python -m scripts.init_materials --generate
  Generate with limit:    python -m scripts.init_materials --generate --limit 10
  Force regenerate all:   python -m scripts.init_materials --force --generate
  Dry run:                python -m scripts.init_materials --generate --dry-run
        """
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="Check material status only (no generation)"
    )

    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate missing materials"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regenerate (clears existing materials first)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without actually doing it"
    )

    parser.add_argument(
        "--category",
        type=str,
        help="Only process specific category (edit_tools, ecommerce, architecture, portrait)"
    )

    parser.add_argument(
        "--tool",
        type=str,
        help="Only process specific tool ID"
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of showcases to generate"
    )

    parser.add_argument(
        "--skip-if-sufficient",
        action="store_true",
        default=True,
        help="Skip generation if materials are already sufficient (default)"
    )

    args = parser.parse_args()

    print_header("VidGo Material Library Initialization")
    print(f"  Timestamp: {datetime.now().isoformat()}")

    # Always show status first
    status = await print_status_report()

    # If only checking, exit here
    if args.check and not args.generate:
        return 0 if status['is_sufficient'] else 1

    # If not generating, exit
    if not args.generate:
        print("\n  Use --generate to create missing materials")
        print("  Use --check for status check only")
        return 0

    # Check if we should skip generation
    if status['is_sufficient'] and not args.force:
        print("\n  ✓ Materials are sufficient, skipping generation")
        print("    Use --force to regenerate anyway")
        return 0

    # Clear existing if force mode
    if args.force:
        print_header("Clearing Existing Materials")
        await clear_existing_showcases()

    # Generate materials
    print_header("Generating Showcases")

    if args.dry_run:
        print("  ** DRY RUN MODE - No actual API calls **\n")

    progress = await generate_materials(
        category=args.category,
        tool_id=args.tool,
        limit=args.limit,
        dry_run=args.dry_run
    )

    # Print summary
    print_header("Generation Summary")
    print(f"  Total Tasks:      {progress.total_tasks}")
    print(f"  Completed:        {progress.completed}")
    print(f"  Failed:           {progress.failed}")
    print(f"  Skipped:          {progress.skipped}")
    print(f"  Success Rate:     {progress.success_rate:.1%}")

    if progress.errors:
        print("\n  Errors:")
        for error in progress.errors[:10]:  # Show first 10 errors
            print(f"    - {error}")
        if len(progress.errors) > 10:
            print(f"    ... and {len(progress.errors) - 10} more errors")

    # Final status
    if not args.dry_run:
        print("\n  Final Status:")
        await print_status_report()

    return 0 if progress.failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
