"""
Seed script for unified Material model
Based on ARCHITECTURE_FINAL.md specification

Seeds:
- Material topics for all 5 tools
- Initial featured materials (placeholders)

Run: python -m scripts.seed_materials
"""
import asyncio
import argparse
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, delete

from app.core.config import settings
from app.models.material import Material, MaterialTopic, ToolType, MaterialSource, MaterialStatus


# Topic definitions per tool (per ARCHITECTURE_FINAL.md)
TOOL_TOPICS = {
    ToolType.BACKGROUND_REMOVAL: [
        {"topic_id": "fashion", "topic_name_en": "Fashion & Apparel", "topic_name_zh": "時尚服飾", "icon": "shirt"},
        {"topic_id": "electronics", "topic_name_en": "Electronics", "topic_name_zh": "電子產品", "icon": "smartphone"},
        {"topic_id": "jewelry", "topic_name_en": "Jewelry & Accessories", "topic_name_zh": "珠寶飾品", "icon": "gem"},
        {"topic_id": "home", "topic_name_en": "Home & Living", "topic_name_zh": "居家用品", "icon": "home"},
        {"topic_id": "beauty", "topic_name_en": "Beauty & Cosmetics", "topic_name_zh": "美妝護膚", "icon": "sparkles"},
        {"topic_id": "food", "topic_name_en": "Food & Beverage", "topic_name_zh": "食品飲料", "icon": "utensils"},
    ],
    ToolType.PRODUCT_SCENE: [
        {"topic_id": "lifestyle", "topic_name_en": "Lifestyle", "topic_name_zh": "生活風格", "icon": "coffee"},
        {"topic_id": "nature", "topic_name_en": "Nature & Outdoor", "topic_name_zh": "自然戶外", "icon": "leaf"},
        {"topic_id": "studio", "topic_name_en": "Studio Setup", "topic_name_zh": "攝影棚", "icon": "camera"},
        {"topic_id": "modern", "topic_name_en": "Modern Interior", "topic_name_zh": "現代室內", "icon": "building"},
        {"topic_id": "minimalist", "topic_name_en": "Minimalist", "topic_name_zh": "極簡風格", "icon": "square"},
        {"topic_id": "luxury", "topic_name_en": "Luxury", "topic_name_zh": "奢華風格", "icon": "crown"},
    ],
    ToolType.TRY_ON: [
        {"topic_id": "casual", "topic_name_en": "Casual Wear", "topic_name_zh": "休閒服飾", "icon": "tshirt"},
        {"topic_id": "formal", "topic_name_en": "Formal Wear", "topic_name_zh": "正裝", "icon": "briefcase"},
        {"topic_id": "sportswear", "topic_name_en": "Sportswear", "topic_name_zh": "運動服飾", "icon": "dumbbell"},
        {"topic_id": "outerwear", "topic_name_en": "Outerwear", "topic_name_zh": "外套", "icon": "coat"},
        {"topic_id": "dresses", "topic_name_en": "Dresses", "topic_name_zh": "洋裝", "icon": "dress"},
        {"topic_id": "accessories", "topic_name_en": "Accessories", "topic_name_zh": "配飾", "icon": "watch"},
    ],
    ToolType.ROOM_REDESIGN: [
        {"topic_id": "living_room", "topic_name_en": "Living Room", "topic_name_zh": "客廳", "icon": "sofa"},
        {"topic_id": "bedroom", "topic_name_en": "Bedroom", "topic_name_zh": "臥室", "icon": "bed"},
        {"topic_id": "kitchen", "topic_name_en": "Kitchen", "topic_name_zh": "廚房", "icon": "utensils"},
        {"topic_id": "bathroom", "topic_name_en": "Bathroom", "topic_name_zh": "浴室", "icon": "bath"},
        {"topic_id": "office", "topic_name_en": "Home Office", "topic_name_zh": "書房", "icon": "desk"},
        {"topic_id": "dining", "topic_name_en": "Dining Room", "topic_name_zh": "餐廳", "icon": "table"},
    ],
    ToolType.SHORT_VIDEO: [
        {"topic_id": "product_intro", "topic_name_en": "Product Introduction", "topic_name_zh": "產品介紹", "icon": "play"},
        {"topic_id": "tutorial", "topic_name_en": "Tutorial", "topic_name_zh": "教學", "icon": "book"},
        {"topic_id": "promotion", "topic_name_en": "Promotion", "topic_name_zh": "促銷宣傳", "icon": "megaphone"},
        {"topic_id": "storytelling", "topic_name_en": "Brand Story", "topic_name_zh": "品牌故事", "icon": "book-open"},
        {"topic_id": "comparison", "topic_name_en": "Comparison", "topic_name_zh": "產品對比", "icon": "scale"},
        {"topic_id": "unboxing", "topic_name_en": "Unboxing", "topic_name_zh": "開箱", "icon": "box"},
    ],
}

# Sample materials for each tool (placeholder data)
SAMPLE_MATERIALS = [
    {
        "tool_type": ToolType.BACKGROUND_REMOVAL,
        "topic": "fashion",
        "prompt": "Professional white background product shot",
        "title_en": "Fashion Item - Clean Background",
        "title_zh": "時尚單品 - 純淨背景",
        "result_image_url": "https://via.placeholder.com/800x600/ffffff/333333?text=Background+Removed",
        "status": MaterialStatus.FEATURED,
        "is_featured": True,
    },
    {
        "tool_type": ToolType.PRODUCT_SCENE,
        "topic": "lifestyle",
        "prompt": "Coffee table lifestyle scene with morning light",
        "title_en": "Lifestyle Product Scene",
        "title_zh": "生活風格場景",
        "result_image_url": "https://via.placeholder.com/800x600/f5f5dc/333333?text=Product+Scene",
        "status": MaterialStatus.FEATURED,
        "is_featured": True,
    },
    {
        "tool_type": ToolType.TRY_ON,
        "topic": "casual",
        "prompt": "Casual t-shirt try-on with model",
        "title_en": "Casual Wear Try-On",
        "title_zh": "休閒服飾試穿",
        "result_image_url": "https://via.placeholder.com/800x600/e6e6fa/333333?text=AI+Try-On",
        "status": MaterialStatus.FEATURED,
        "is_featured": True,
    },
    {
        "tool_type": ToolType.ROOM_REDESIGN,
        "topic": "living_room",
        "prompt": "Modern minimalist living room redesign",
        "title_en": "Living Room Makeover",
        "title_zh": "客廳改造",
        "result_image_url": "https://via.placeholder.com/800x600/f0f8ff/333333?text=Room+Redesign",
        "status": MaterialStatus.FEATURED,
        "is_featured": True,
    },
    {
        "tool_type": ToolType.SHORT_VIDEO,
        "topic": "product_intro",
        "prompt": "30-second product introduction video",
        "title_en": "Product Introduction Video",
        "title_zh": "產品介紹影片",
        "result_video_url": "https://via.placeholder.com/800x600/ffe4e1/333333?text=Short+Video",
        "result_thumbnail_url": "https://via.placeholder.com/400x300/ffe4e1/333333?text=Thumbnail",
        "status": MaterialStatus.FEATURED,
        "is_featured": True,
    },
]


async def seed_topics(session: AsyncSession, clear: bool = False):
    """Seed material topics for all tools"""
    print("Seeding material topics...")

    if clear:
        await session.execute(delete(MaterialTopic))
        print("  Cleared existing topics")

    count = 0
    for tool_type, topics in TOOL_TOPICS.items():
        for i, topic_data in enumerate(topics):
            topic = MaterialTopic(
                id=uuid.uuid4(),
                tool_type=tool_type,  # Pass enum member, SQLAlchemy handles conversion
                topic_id=topic_data["topic_id"],
                topic_name_en=topic_data["topic_name_en"],
                topic_name_zh=topic_data.get("topic_name_zh"),
                icon=topic_data.get("icon"),
                target_count=30,
                sort_order=i,
                is_active=True
            )
            session.add(topic)
            count += 1

    await session.commit()
    print(f"  Seeded {count} topics across {len(TOOL_TOPICS)} tools")


async def seed_sample_materials(session: AsyncSession, clear: bool = False):
    """Seed sample materials for demonstration"""
    print("Seeding sample materials...")

    if clear:
        await session.execute(delete(Material))
        print("  Cleared existing materials")

    count = 0
    for material_data in SAMPLE_MATERIALS:
        material = Material(
            id=uuid.uuid4(),
            tool_type=material_data["tool_type"],  # Pass enum member, SQLAlchemy handles conversion
            topic=material_data["topic"],
            prompt=material_data["prompt"],
            title_en=material_data["title_en"],
            title_zh=material_data.get("title_zh"),
            source=MaterialSource.SEED,  # Pass enum member, SQLAlchemy handles conversion
            status=material_data["status"],  # Pass enum member, SQLAlchemy handles conversion
            is_featured=material_data.get("is_featured", False),
            result_image_url=material_data.get("result_image_url"),
            result_video_url=material_data.get("result_video_url"),
            result_thumbnail_url=material_data.get("result_thumbnail_url"),
            quality_score=0.9,
            sort_order=count,
            is_active=True
        )
        session.add(material)
        count += 1

    await session.commit()
    print(f"  Seeded {count} sample materials")


async def check_status(session: AsyncSession):
    """Check current material status"""
    print("\nMaterial Status Check:")
    print("-" * 40)

    # Count topics
    topic_result = await session.execute(select(MaterialTopic))
    topics = topic_result.scalars().all()
    print(f"Topics: {len(topics)}")

    # Count materials by tool
    for tool_type in ToolType:
        result = await session.execute(
            select(Material).where(Material.tool_type == tool_type.value)
        )
        materials = result.scalars().all()
        featured = len([m for m in materials if m.is_featured])
        print(f"  {tool_type.value}: {len(materials)} total, {featured} featured")

    print("-" * 40)


async def main():
    parser = argparse.ArgumentParser(description="Seed unified Material model")
    parser.add_argument("--clear", action="store_true", help="Clear existing data before seeding")
    parser.add_argument("--topics-only", action="store_true", help="Only seed topics")
    parser.add_argument("--check", action="store_true", help="Only check status")
    args = parser.parse_args()

    # Create async engine
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        if args.check:
            await check_status(session)
            return

        await seed_topics(session, clear=args.clear)

        if not args.topics_only:
            await seed_sample_materials(session, clear=args.clear)

        await check_status(session)

    await engine.dispose()
    print("\nMaterial seeding complete!")


if __name__ == "__main__":
    asyncio.run(main())
