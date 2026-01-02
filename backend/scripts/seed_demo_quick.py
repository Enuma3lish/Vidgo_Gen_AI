"""
Quick seed script for demo examples with high-quality Unsplash images.
This creates sample data immediately without API calls.
"""
import asyncio
import sys
sys.path.insert(0, "/app")

from sqlalchemy import select, delete
from app.core.database import AsyncSessionLocal
from app.models.demo import DemoExample

# Sample demo examples with high-quality Unsplash images
DEMO_EXAMPLES = [
    # ============ Product / E-commerce ============
    {
        "topic": "product",
        "topic_zh": "產品",
        "topic_en": "Product",
        "prompt": "Luxury watch with golden details on black velvet, studio lighting",
        "title": "Luxury Watch",
        "title_zh": "豪華腕錶",
        "image_url": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800",
        "style_tags": ["奢華", "手錶", "金色"],
        "popularity_score": 4521,
        "is_featured": True
    },
    {
        "topic": "product",
        "topic_zh": "產品",
        "topic_en": "Product",
        "prompt": "Premium wireless headphones on marble surface, soft studio lighting",
        "title": "Premium Headphones",
        "title_zh": "高端無線耳機",
        "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800",
        "style_tags": ["科技", "音樂", "高端"],
        "popularity_score": 3892
    },
    {
        "topic": "product",
        "topic_zh": "產品",
        "topic_en": "Product",
        "prompt": "Modern smartphone floating with holographic display effects",
        "title": "Smartphone Pro",
        "title_zh": "智能手機",
        "image_url": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=800",
        "style_tags": ["科技", "3D", "未來"],
        "popularity_score": 5123
    },
    {
        "topic": "product",
        "topic_zh": "產品",
        "topic_en": "Product",
        "prompt": "Elegant perfume bottle with crystal reflections, luxury setting",
        "title": "Luxury Perfume",
        "title_zh": "奢華香水",
        "image_url": "https://images.unsplash.com/photo-1541643600914-78b084683601?w=800",
        "style_tags": ["香水", "奢華", "玻璃"],
        "popularity_score": 2890
    },
    {
        "topic": "product",
        "topic_zh": "產品",
        "topic_en": "Product",
        "prompt": "Stylish sunglasses on white background, product photography",
        "title": "Designer Sunglasses",
        "title_zh": "設計師太陽鏡",
        "image_url": "https://images.unsplash.com/photo-1572635196237-14b3f281503f?w=800",
        "style_tags": ["配件", "時尚", "白底"],
        "popularity_score": 3456
    },
    {
        "topic": "product",
        "topic_zh": "產品",
        "topic_en": "Product",
        "prompt": "Modern laptop on wooden desk, morning sunlight, minimalist workspace",
        "title": "MacBook Workspace",
        "title_zh": "筆電工作區",
        "image_url": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=800",
        "style_tags": ["科技", "辦公", "極簡"],
        "popularity_score": 4234
    },

    # ============ Food ============
    {
        "topic": "food",
        "topic_zh": "美食",
        "topic_en": "Food",
        "prompt": "Gourmet burger with melting cheese, fresh vegetables, dramatic lighting",
        "title": "Gourmet Burger",
        "title_zh": "精緻漢堡",
        "image_url": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=800",
        "style_tags": ["漢堡", "美食", "餐飲"],
        "popularity_score": 5678,
        "is_featured": True
    },
    {
        "topic": "food",
        "topic_zh": "美食",
        "topic_en": "Food",
        "prompt": "Colorful sushi platter with wasabi and ginger, Japanese cuisine",
        "title": "Sushi Platter",
        "title_zh": "壽司拼盤",
        "image_url": "https://images.unsplash.com/photo-1579871494447-9811cf80d66c?w=800",
        "style_tags": ["日本", "壽司", "海鮮"],
        "popularity_score": 4890
    },
    {
        "topic": "food",
        "topic_zh": "美食",
        "topic_en": "Food",
        "prompt": "Artisan coffee with latte art, cozy cafe atmosphere",
        "title": "Latte Art Coffee",
        "title_zh": "拿鐵藝術咖啡",
        "image_url": "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=800",
        "style_tags": ["咖啡", "藝術", "生活"],
        "popularity_score": 3567
    },
    {
        "topic": "food",
        "topic_zh": "美食",
        "topic_en": "Food",
        "prompt": "Fresh pizza with melting mozzarella, Italian cuisine",
        "title": "Italian Pizza",
        "title_zh": "意式披薩",
        "image_url": "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=800",
        "style_tags": ["披薩", "意大利", "起司"],
        "popularity_score": 4123
    },
    {
        "topic": "food",
        "topic_zh": "美食",
        "topic_en": "Food",
        "prompt": "Chocolate cake with berries, dessert photography",
        "title": "Chocolate Cake",
        "title_zh": "巧克力蛋糕",
        "image_url": "https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=800",
        "style_tags": ["甜點", "巧克力", "蛋糕"],
        "popularity_score": 3890
    },

    # ============ Fashion ============
    {
        "topic": "fashion",
        "topic_zh": "時尚",
        "topic_en": "Fashion",
        "prompt": "Stylish sneakers with neon accents, street fashion",
        "title": "Neon Sneakers",
        "title_zh": "霓虹運動鞋",
        "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800",
        "style_tags": ["鞋子", "潮流", "霓虹"],
        "popularity_score": 5234,
        "is_featured": True
    },
    {
        "topic": "fashion",
        "topic_zh": "時尚",
        "topic_en": "Fashion",
        "prompt": "Designer handbag on minimalist background, luxury fashion",
        "title": "Designer Bag",
        "title_zh": "設計師手袋",
        "image_url": "https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=800",
        "style_tags": ["包包", "奢華", "設計"],
        "popularity_score": 4567
    },
    {
        "topic": "fashion",
        "topic_zh": "時尚",
        "topic_en": "Fashion",
        "prompt": "Elegant evening dress, fashion model, studio lighting",
        "title": "Evening Dress",
        "title_zh": "晚禮服",
        "image_url": "https://images.unsplash.com/photo-1518611012118-696072aa579a?w=800",
        "style_tags": ["禮服", "優雅", "時尚"],
        "popularity_score": 4890
    },
    {
        "topic": "fashion",
        "topic_zh": "時尚",
        "topic_en": "Fashion",
        "prompt": "Vintage denim jacket, casual street style",
        "title": "Denim Style",
        "title_zh": "牛仔風格",
        "image_url": "https://images.unsplash.com/photo-1576995853123-5a10305d93c0?w=800",
        "style_tags": ["牛仔", "休閒", "街頭"],
        "popularity_score": 3456
    },

    # ============ Interior ============
    {
        "topic": "interior",
        "topic_zh": "室內設計",
        "topic_en": "Interior",
        "prompt": "Modern minimalist living room with natural light, Scandinavian design",
        "title": "Minimalist Living Room",
        "title_zh": "極簡客廳",
        "image_url": "https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?w=800",
        "style_tags": ["客廳", "極簡", "北歐"],
        "popularity_score": 6789,
        "is_featured": True
    },
    {
        "topic": "interior",
        "topic_zh": "室內設計",
        "topic_en": "Interior",
        "prompt": "Cozy bedroom with warm lighting and indoor plants",
        "title": "Cozy Bedroom",
        "title_zh": "溫馨臥室",
        "image_url": "https://images.unsplash.com/photo-1616594039964-ae9021a400a0?w=800",
        "style_tags": ["臥室", "溫馨", "植物"],
        "popularity_score": 5678
    },
    {
        "topic": "interior",
        "topic_zh": "室內設計",
        "topic_en": "Interior",
        "prompt": "Scandinavian kitchen with marble countertops, modern appliances",
        "title": "Nordic Kitchen",
        "title_zh": "北歐廚房",
        "image_url": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800",
        "style_tags": ["廚房", "北歐", "大理石"],
        "popularity_score": 4890
    },
    {
        "topic": "interior",
        "topic_zh": "室內設計",
        "topic_en": "Interior",
        "prompt": "Modern bathroom with freestanding bathtub, spa atmosphere",
        "title": "Spa Bathroom",
        "title_zh": "水療浴室",
        "image_url": "https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=800",
        "style_tags": ["浴室", "水療", "現代"],
        "popularity_score": 4234
    },
    {
        "topic": "interior",
        "topic_zh": "室內設計",
        "topic_en": "Interior",
        "prompt": "Home office with wooden desk, natural lighting, plants",
        "title": "Home Office",
        "title_zh": "居家辦公室",
        "image_url": "https://images.unsplash.com/photo-1593062096033-9a26b09da705?w=800",
        "style_tags": ["辦公", "居家", "自然"],
        "popularity_score": 3890
    },

    # ============ Portrait ============
    {
        "topic": "portrait",
        "topic_zh": "人像",
        "topic_en": "Portrait",
        "prompt": "Professional business portrait, natural lighting, confident pose",
        "title": "Business Portrait",
        "title_zh": "商務人像",
        "image_url": "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=800",
        "style_tags": ["商務", "專業", "肖像"],
        "popularity_score": 4567,
        "is_featured": True
    },
    {
        "topic": "portrait",
        "topic_zh": "人像",
        "topic_en": "Portrait",
        "prompt": "Creative portrait with colorful studio lighting effects",
        "title": "Creative Portrait",
        "title_zh": "創意人像",
        "image_url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800",
        "style_tags": ["創意", "色彩", "藝術"],
        "popularity_score": 5234
    },
    {
        "topic": "portrait",
        "topic_zh": "人像",
        "topic_en": "Portrait",
        "prompt": "Natural outdoor portrait, golden hour lighting",
        "title": "Golden Hour Portrait",
        "title_zh": "黃金時刻人像",
        "image_url": "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=800",
        "style_tags": ["戶外", "自然光", "溫暖"],
        "popularity_score": 4890
    },
    {
        "topic": "portrait",
        "topic_zh": "人像",
        "topic_en": "Portrait",
        "prompt": "Fashion model portrait, high-end editorial style",
        "title": "Fashion Portrait",
        "title_zh": "時尚人像",
        "image_url": "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=800",
        "style_tags": ["時尚", "模特", "編輯"],
        "popularity_score": 5678
    },

    # ============ Art / Creative ============
    {
        "topic": "art",
        "topic_zh": "藝術",
        "topic_en": "Art",
        "prompt": "Abstract digital art with vibrant colors and fluid shapes",
        "title": "Abstract Fluid Art",
        "title_zh": "抽象流體藝術",
        "image_url": "https://images.unsplash.com/photo-1541701494587-cb58502866ab?w=800",
        "style_tags": ["抽象", "色彩", "流體"],
        "popularity_score": 7890,
        "is_featured": True
    },
    {
        "topic": "art",
        "topic_zh": "藝術",
        "topic_en": "Art",
        "prompt": "Cyberpunk cityscape with neon lights and rain reflections",
        "title": "Cyberpunk City",
        "title_zh": "賽博朋克城市",
        "image_url": "https://images.unsplash.com/photo-1519608487953-e999c86e7455?w=800",
        "style_tags": ["賽博朋克", "霓虹", "城市"],
        "popularity_score": 8901,
        "is_featured": True
    },
    {
        "topic": "art",
        "topic_zh": "藝術",
        "topic_en": "Art",
        "prompt": "Surreal landscape with floating islands and waterfalls",
        "title": "Surreal Landscape",
        "title_zh": "超現實風景",
        "image_url": "https://images.unsplash.com/photo-1518837695005-2083093ee35b?w=800",
        "style_tags": ["超現實", "風景", "夢幻"],
        "popularity_score": 6543
    },
    {
        "topic": "art",
        "topic_zh": "藝術",
        "topic_en": "Art",
        "prompt": "Geometric patterns with gradient colors, modern art",
        "title": "Geometric Art",
        "title_zh": "幾何藝術",
        "image_url": "https://images.unsplash.com/photo-1550684376-efcbd6e3f031?w=800",
        "style_tags": ["幾何", "漸變", "現代"],
        "popularity_score": 5234
    },
    {
        "topic": "art",
        "topic_zh": "藝術",
        "topic_en": "Art",
        "prompt": "Digital illustration of fantasy forest with magical creatures",
        "title": "Fantasy Forest",
        "title_zh": "奇幻森林",
        "image_url": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=800",
        "style_tags": ["奇幻", "森林", "插畫"],
        "popularity_score": 5890
    },

    # ============ Video Examples ============
    {
        "topic": "video",
        "topic_zh": "視頻",
        "topic_en": "Video",
        "prompt": "Product showcase video with smooth camera movement and lighting",
        "title": "Product Showcase",
        "title_zh": "產品展示",
        "image_url": "https://images.unsplash.com/photo-1492619375914-88005aa9e8fb?w=800",
        "style_tags": ["產品", "展示", "動態"],
        "popularity_score": 5432,
        "is_featured": True
    },
    {
        "topic": "video",
        "topic_zh": "視頻",
        "topic_en": "Video",
        "prompt": "Cinematic drone footage of mountain landscape at sunset",
        "title": "Drone Landscape",
        "title_zh": "航拍風景",
        "image_url": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=800",
        "style_tags": ["航拍", "風景", "日落"],
        "popularity_score": 6234
    },
    {
        "topic": "video",
        "topic_zh": "視頻",
        "topic_en": "Video",
        "prompt": "Social media ad video with dynamic text animations",
        "title": "Social Media Ad",
        "title_zh": "社交媒體廣告",
        "image_url": "https://images.unsplash.com/photo-1611162616305-c69b3fa7fbe0?w=800",
        "style_tags": ["廣告", "社交", "動態"],
        "popularity_score": 4567
    },
    {
        "topic": "video",
        "topic_zh": "視頻",
        "topic_en": "Video",
        "prompt": "Food commercial with appetizing close-up shots",
        "title": "Food Commercial",
        "title_zh": "美食廣告",
        "image_url": "https://images.unsplash.com/photo-1476224203421-9ac39bcb3327?w=800",
        "style_tags": ["美食", "特寫", "廣告"],
        "popularity_score": 5123
    },
]


async def seed_demo_examples(clear_existing: bool = False):
    """Seed demo examples with high-quality images.

    Args:
        clear_existing: If True, delete all existing examples first
    """
    async with AsyncSessionLocal() as session:
        print("Seeding demo examples...")

        # Optionally clear existing data
        if clear_existing:
            print("  Clearing existing examples...")
            await session.execute(delete(DemoExample))
            await session.commit()
            print("  Cleared!")

        # Check existing count
        result = await session.execute(select(DemoExample))
        existing = result.scalars().all()
        print(f"  Found {len(existing)} existing examples")

        # Add new examples
        created = 0
        for data in DEMO_EXAMPLES:
            # Check if similar prompt exists
            check = await session.execute(
                select(DemoExample).where(
                    DemoExample.prompt == data["prompt"]
                )
            )
            if check.scalar_one_or_none():
                continue

            example = DemoExample(
                topic=data["topic"],
                topic_zh=data.get("topic_zh"),
                topic_en=data.get("topic_en"),
                prompt=data["prompt"],
                title=data.get("title"),
                title_zh=data.get("title_zh"),
                image_url=data["image_url"],
                video_url=data.get("video_url"),
                style_tags=data.get("style_tags", []),
                popularity_score=data.get("popularity_score", 0),
                is_featured=data.get("is_featured", False)
            )
            session.add(example)
            created += 1

        await session.commit()
        print(f"  Created {created} new demo examples")
        print("Done!")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="Clear existing examples before seeding")
    args = parser.parse_args()
    asyncio.run(seed_demo_examples(clear_existing=args.clear))
