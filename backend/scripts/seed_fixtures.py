#!/usr/bin/env python3
"""
Seed Fixtures - Load pre-built example materials into DB instantly.

This script loads static fixture data (pre-generated SMB-focused examples)
into the Material DB. It completes in <2 seconds, providing instant content
for visitors while background generation fills in the rest.

Fixtures are SMB-aligned: food, daily products, store scenes, etc.
No luxury items (watches, jewelry, perfume).

Usage:
    python -m scripts.seed_fixtures
    python -m scripts.seed_fixtures --force  # Overwrite existing fixtures
"""
import asyncio
import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, "/app")

from sqlalchemy import select, func
from app.core.database import AsyncSessionLocal
from app.models.material import Material, ToolType, MaterialSource, MaterialStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Fixture data directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURES_FILE = FIXTURES_DIR / "seed_materials.json"


def generate_fixture_data() -> list[dict]:
    """
    Generate SMB-focused fixture records for all 8 tools.
    These use placeholder image URLs that should be replaced with real
    pre-generated assets hosted on CDN/S3.

    Each tool gets 3-5 fixture examples with realistic prompts.
    """
    fixtures = []

    # Helper to create a fixture record
    def make(tool_type: str, topic: str, topic_zh: str, prompt: str, prompt_zh: str,
             input_image_url: str = None, result_image_url: str = None,
             result_video_url: str = None, tags: list = None):
        lookup_hash = hashlib.sha256(
            f"{tool_type}:fixture:{prompt}".encode()
        ).hexdigest()[:64]
        fixtures.append({
            "tool_type": tool_type,
            "topic": topic,
            "topic_zh": topic_zh,
            "main_topic": "SMB Examples",
            "main_topic_zh": "中小企業範例",
            "prompt": prompt,
            "prompt_zh": prompt_zh,
            "source": "seed",
            "status": "approved",
            "is_active": True,
            "is_featured": True,
            "quality_score": 0.9,
            "tags": tags or [],
            "lookup_hash": lookup_hash,
            "input_image_url": input_image_url,
            "result_image_url": result_image_url,
            "result_video_url": result_video_url,
        })

    # === Background Removal ===
    make("background_removal", "drinks", "飲料",
         "A cup of bubble tea with tapioca pearls on cafe counter",
         "珍珠奶茶杯放在咖啡廳櫃台上",
         tags=["bubble_tea", "drinks", "cafe"])
    make("background_removal", "snacks", "小吃",
         "Crispy fried chicken pieces in a paper bag",
         "酥脆炸雞塊放在紙袋中",
         tags=["fried_chicken", "snacks", "food"])
    make("background_removal", "desserts", "甜點",
         "Fresh pineapple cake on a ceramic plate",
         "新鮮鳳梨酥放在陶瓷盤上",
         tags=["pineapple_cake", "desserts", "bakery"])
    make("background_removal", "packaging", "包裝外帶",
         "Eco-friendly kraft paper packaging with ribbon",
         "環保牛皮紙包裝附緞帶",
         tags=["packaging", "eco", "gift"])

    # === Product Scene ===
    make("product_scene", "studio", "攝影棚",
         "Stainless steel thermos bottle on clean white surface with soft studio lighting",
         "不鏽鋼保溫瓶放在白色桌面上，柔和攝影棚燈光",
         tags=["thermos", "studio", "product"])
    make("product_scene", "nature", "自然場景",
         "Herbal shampoo bottle surrounded by green leaves and morning dew",
         "草本洗髮精瓶子被綠葉和晨露環繞",
         tags=["shampoo", "nature", "beauty"])
    make("product_scene", "lifestyle", "生活情境",
         "Ceramic tea set on wooden tray in cozy living room",
         "陶瓷茶具放在木托盤上，溫馨客廳場景",
         tags=["tea_set", "lifestyle", "home"])
    make("product_scene", "minimal", "極簡風格",
         "Handmade soap bar on marble surface with minimal styling",
         "手工皂放在大理石桌面，極簡風格",
         tags=["soap", "minimal", "handmade"])

    # === Try-On ===
    make("try_on", "casual", "休閒服飾",
         "White cotton T-shirt with simple logo print",
         "白色棉質T恤搭配簡約標誌印花",
         tags=["tshirt", "casual", "basic"])
    make("try_on", "formal", "正式服飾",
         "Professional work apron for cafe barista",
         "咖啡師專業工作圍裙",
         tags=["apron", "work", "cafe"])
    make("try_on", "sportswear", "運動服飾",
         "Lightweight running jacket in bright colors",
         "輕量慢跑外套，亮色系",
         tags=["jacket", "running", "sport"])

    # === Room Redesign ===
    make("room_redesign", "kitchen", "廚房",
         "Small cafe kitchen with warm wooden accents and open shelving",
         "小型咖啡廳廚房，溫暖木質裝飾和開放式層架",
         tags=["cafe", "kitchen", "warm"])
    make("room_redesign", "living_room", "客廳",
         "Bakery display area with glass cases and rustic decor",
         "麵包店展示區，玻璃展示櫃和鄉村風裝飾",
         tags=["bakery", "display", "rustic"])
    make("room_redesign", "bathroom", "浴室",
         "Hair salon wash station with modern minimalist design",
         "髮廊洗頭區，現代極簡設計",
         tags=["salon", "modern", "wash"])

    # === Short Video ===
    make("short_video", "product_showcase", "產品展示",
         "Bubble tea being prepared step by step, adding ice and tapioca pearls",
         "珍珠奶茶製作過程，加入冰塊和珍珠",
         tags=["bubble_tea", "preparation", "video"])
    make("short_video", "promo", "促銷廣告",
         "Night market food stall with sizzling food and steam rising",
         "夜市美食攤位，滋滋作響的食物和升起的蒸氣",
         tags=["night_market", "food", "promo"])
    make("short_video", "brand_intro", "品牌介紹",
         "Cozy cafe interior tour showing warm ambiance and fresh pastries",
         "溫馨咖啡廳內部導覽，展示溫暖氛圍和新鮮糕點",
         tags=["cafe", "tour", "brand"])

    # === AI Avatar ===
    make("ai_avatar", "spokesperson", "品牌代言人",
         "Store owner greeting customers warmly",
         "店主熱情迎接顧客",
         tags=["greeting", "store_owner", "avatar"])
    make("ai_avatar", "product_intro", "產品介紹",
         "Presenter introducing new seasonal menu items",
         "主持人介紹新的季節性菜單品項",
         tags=["menu", "seasonal", "intro"])
    make("ai_avatar", "social_media", "社群媒體",
         "Social media host sharing daily specials and deals",
         "社群媒體主持人分享每日特餐和優惠",
         tags=["social", "deals", "daily"])

    # === Pattern Generate ===
    make("pattern_generate", "seamless", "無縫圖案",
         "Simple repeating pattern of coffee cups and beans for cafe packaging",
         "簡單重複的咖啡杯和咖啡豆圖案，適用於咖啡廳包裝",
         tags=["coffee", "pattern", "packaging"])
    make("pattern_generate", "floral", "花卉圖案",
         "Delicate floral pattern for handmade soap packaging",
         "精緻花卉圖案，適用於手工皂包裝",
         tags=["floral", "soap", "packaging"])

    # === Effect (Style Transfer) ===
    make("effect", "anime", "動漫風格",
         "Local cafe storefront transformed into anime style",
         "在地咖啡廳店面轉換為動漫風格",
         tags=["anime", "cafe", "storefront"])
    make("effect", "ghibli", "吉卜力風格",
         "Night market scene in Studio Ghibli art style",
         "夜市場景轉換為吉卜力工作室藝術風格",
         tags=["ghibli", "night_market", "art"])
    make("effect", "watercolor", "水彩風格",
         "Product flat lay in watercolor painting style",
         "產品平拍照轉換為水彩畫風格",
         tags=["watercolor", "product", "art"])

    return fixtures


async def seed_fixtures(force: bool = False):
    """Load fixture data into Material DB."""
    async with AsyncSessionLocal() as db:
        # Check if fixtures already loaded
        result = await db.execute(
            select(func.count()).select_from(Material).where(
                Material.main_topic == "SMB Examples",
                Material.is_active == True,
            )
        )
        existing_count = result.scalar() or 0

        if existing_count > 0 and not force:
            logger.info(f"Seed fixtures already loaded ({existing_count} records). Use --force to overwrite.")
            return

        fixtures = generate_fixture_data()
        loaded = 0

        for fix in fixtures:
            # Skip if lookup_hash already exists
            existing = await db.execute(
                select(Material).where(Material.lookup_hash == fix["lookup_hash"])
            )
            if existing.scalar_one_or_none() is not None:
                continue

            material = Material(
                id=uuid4(),
                tool_type=ToolType(fix["tool_type"]),
                topic=fix["topic"],
                topic_zh=fix.get("topic_zh"),
                main_topic=fix["main_topic"],
                main_topic_zh=fix.get("main_topic_zh"),
                prompt=fix["prompt"],
                prompt_zh=fix.get("prompt_zh"),
                source=MaterialSource.SEED,
                status=MaterialStatus.APPROVED,
                is_active=fix.get("is_active", True),
                is_featured=fix.get("is_featured", False),
                quality_score=fix.get("quality_score", 0.8),
                tags=fix.get("tags", []),
                lookup_hash=fix["lookup_hash"],
                input_image_url=fix.get("input_image_url"),
                result_image_url=fix.get("result_image_url"),
                result_video_url=fix.get("result_video_url"),
            )
            db.add(material)
            loaded += 1

        await db.commit()
        logger.info(f"Seed fixtures loaded: {loaded} new records ({existing_count} already existed)")


async def main():
    parser = argparse.ArgumentParser(description="Load seed fixture materials")
    parser.add_argument("--force", action="store_true", help="Overwrite existing fixtures")
    args = parser.parse_args()

    await seed_fixtures(force=args.force)


if __name__ == "__main__":
    asyncio.run(main())
