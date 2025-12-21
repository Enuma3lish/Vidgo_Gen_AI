#!/usr/bin/env python3
"""
Database Seeding Script for Demo Videos
Loads generated demos from JSON and inserts into PostgreSQL.

Usage:
    cd backend
    uv run python scripts/seed_demos.py --input demos_output.json
    uv run python scripts/seed_demos.py --input demos_output.json --clear  # Clear existing first
"""
import asyncio
import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
from uuid import uuid4

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.demo import DemoCategory, DemoVideo, Base

settings = get_settings()


# Category definitions with icons
CATEGORIES = [
    {"name": "Animals", "slug": "animals", "icon": "🐾", "description": "Cute pets and wildlife", "sort_order": 1},
    {"name": "Nature", "slug": "nature", "icon": "🌿", "description": "Landscapes and natural wonders", "sort_order": 2},
    {"name": "Urban", "slug": "urban", "icon": "🏙️", "description": "City life and architecture", "sort_order": 3},
    {"name": "People", "slug": "people", "icon": "👤", "description": "Human activities and portraits", "sort_order": 4},
    {"name": "Fantasy", "slug": "fantasy", "icon": "🧙", "description": "Magical and mythical scenes", "sort_order": 5},
    {"name": "Sci-Fi", "slug": "sci-fi", "icon": "🚀", "description": "Futuristic and space themes", "sort_order": 6},
    {"name": "Food", "slug": "food", "icon": "🍕", "description": "Delicious culinary creations", "sort_order": 7},
    {"name": "Abstract", "slug": "abstract", "icon": "🎨", "description": "Artistic and abstract visuals", "sort_order": 8},
    {"name": "Sports", "slug": "sports", "icon": "⚽", "description": "Athletic action and fitness", "sort_order": 9},
    {"name": "Music", "slug": "music", "icon": "🎵", "description": "Musical performances and vibes", "sort_order": 10},
    {"name": "Seasonal", "slug": "seasonal", "icon": "🎄", "description": "Holiday and seasonal themes", "sort_order": 11},
    {"name": "Architecture", "slug": "architecture", "icon": "🏛️", "description": "Buildings and structures", "sort_order": 12},
    {"name": "Vehicles", "slug": "vehicles", "icon": "🚗", "description": "Cars, planes, and transport", "sort_order": 13},
]


async def create_database_tables(engine):
    """Create all tables if they don't exist"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables created/verified")


async def clear_demo_data(session: AsyncSession):
    """Clear existing demo data"""
    await session.execute(text("DELETE FROM demo_views"))
    await session.execute(text("DELETE FROM demo_videos"))
    await session.execute(text("DELETE FROM demo_categories"))
    await session.commit()
    print("🗑️  Cleared existing demo data")


async def seed_categories(session: AsyncSession) -> Dict[str, str]:
    """Seed demo categories and return slug -> id mapping"""
    category_map = {}

    for cat_data in CATEGORIES:
        category = DemoCategory(
            id=uuid4(),
            name=cat_data["name"],
            slug=cat_data["slug"],
            description=cat_data["description"],
            icon=cat_data["icon"],
            sort_order=cat_data["sort_order"],
            is_active=True
        )
        session.add(category)
        category_map[cat_data["slug"]] = category.id

    await session.commit()
    print(f"✅ Seeded {len(CATEGORIES)} categories")
    return category_map


async def seed_demos(
    session: AsyncSession,
    demos: List[Dict[str, Any]],
    category_map: Dict[str, str]
):
    """Seed demo videos from generated data"""
    count = 0
    skipped = 0

    for demo in demos:
        # Skip failed demos
        if demo.get("status") not in ["completed", "dry_run"]:
            skipped += 1
            continue

        # Get category ID
        category_slug = demo.get("category", "").lower().replace("-", "_")
        category_id = category_map.get(category_slug)

        # Create demo video record
        demo_video = DemoVideo(
            id=uuid4(),
            title=demo.get("title", "Untitled Demo")[:255],
            description=f"{demo.get('style_description', '')} transformation of: {demo.get('prompt', '')}"[:500],
            prompt=demo.get("prompt", "")[:1000],
            keywords=demo.get("keywords", []),
            category_id=category_id,
            video_url=demo.get("video_url_before", ""),
            video_url_watermarked=demo.get("video_url_after") or demo.get("video_url_before", ""),
            thumbnail_url=demo.get("thumbnail_url"),
            duration_seconds=5.0,
            resolution="720p",
            style=demo.get("style_slug", ""),
            source_service="goenhance",
            generation_params=json.dumps({
                "style_id": demo.get("style_id"),
                "style_name": demo.get("style_name"),
                "task_id": demo.get("task_id"),
            }),
            popularity_score=0,
            quality_score=0.8,
            is_featured=count < 20,  # First 20 are featured
            is_active=True
        )
        session.add(demo_video)
        count += 1

    await session.commit()
    print(f"✅ Seeded {count} demo videos (skipped {skipped} failed)")


async def seed_sample_demos(session: AsyncSession, category_map: Dict[str, str]):
    """
    Seed sample demo data when no JSON input is provided.
    Uses placeholder URLs for testing.
    """
    from scripts.generate_demos import DEMO_TOPICS, GOENHANCE_STYLES
    import random

    sample_videos = [
        "https://cdn.goenhance.ai/user/upload-data/video-to-video/333768e610e442d02e8030693def0b6e.mp4",
        # Add more sample video URLs here
    ]

    count = 0
    for category, topics in DEMO_TOPICS.items():
        category_id = category_map.get(category)

        for topic in topics[:5]:  # 5 per category for samples
            style = random.choice(GOENHANCE_STYLES)
            video_url = random.choice(sample_videos)

            demo_video = DemoVideo(
                id=uuid4(),
                title=f"{topic['prompt'][:50]} - {style['name']}"[:255],
                description=f"Demo: {style['description']}"[:500],
                prompt=topic["prompt"],
                keywords=topic["keywords"] + [style["slug"]],
                category_id=category_id,
                video_url=video_url,
                video_url_watermarked=video_url,
                thumbnail_url=None,
                duration_seconds=5.0,
                resolution="720p",
                style=style["slug"],
                source_service="goenhance",
                generation_params=json.dumps({"style_id": style["id"], "sample": True}),
                popularity_score=random.randint(0, 100),
                quality_score=random.uniform(0.6, 1.0),
                is_featured=count < 10,
                is_active=True
            )
            session.add(demo_video)
            count += 1

    await session.commit()
    print(f"✅ Seeded {count} sample demo videos")


async def main():
    parser = argparse.ArgumentParser(description="Seed demo videos into database")
    parser.add_argument("--input", type=str, help="Input JSON file from generate_demos.py")
    parser.add_argument("--clear", action="store_true", help="Clear existing data first")
    parser.add_argument("--samples", action="store_true", help="Seed sample data without JSON")

    args = parser.parse_args()

    # Create engine and session
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print(f"\n🗄️  Database: {settings.DATABASE_URL.split('@')[-1]}")

    async with async_session() as session:
        # Create tables
        await create_database_tables(engine)

        # Clear if requested
        if args.clear:
            await clear_demo_data(session)

        # Seed categories
        category_map = await seed_categories(session)

        # Seed demos from JSON or samples
        if args.input:
            input_path = Path(args.input)
            if not input_path.exists():
                print(f"❌ File not found: {input_path}")
                return

            with open(input_path) as f:
                data = json.load(f)

            demos = data.get("demos", [])
            print(f"\n📂 Loading {len(demos)} demos from {input_path}")
            await seed_demos(session, demos, category_map)

        elif args.samples:
            print("\n🎲 Generating sample data...")
            await seed_sample_demos(session, category_map)

        else:
            print("\n⚠️  No input specified. Use --input or --samples")
            print("   Example: uv run python scripts/seed_demos.py --samples")

    await engine.dispose()
    print("\n✨ Done!")


if __name__ == "__main__":
    asyncio.run(main())
