"""
Seed local Material DB with visitor-facing demo fixtures.

These are NOT real AI generations — they point to public Unsplash CDN URLs.
The goal is to give visitors a working preset-browsing experience in the local
docker env without needing GCS/Vertex/PiAPI credentials.

For production, the real main_pregenerate.py flow replaces these.
"""
import asyncio
import hashlib
from uuid import uuid4

from sqlalchemy import select, delete

from app.core.database import AsyncSessionLocal
from app.models.material import Material, ToolType, MaterialSource, MaterialStatus


def _hash(tool: str, idx: int) -> str:
    return hashlib.sha256(f"demo-fixture:{tool}:{idx}".encode()).hexdigest()[:64]


FIXTURES = {
    "background_removal": [
        {
            "topic": "drinks",
            "prompt": "Bubble milk tea on clean background",
            "prompt_zh": "珍珠奶茶",
            "input": "https://images.unsplash.com/photo-1558857563-c0c6ee6ff8e4?w=800&q=80",
            "result": "https://images.unsplash.com/photo-1558857563-c0c6ee6ff8e4?w=800&q=80&auto=format&bg=fff",
        },
        {
            "topic": "snacks",
            "prompt": "Crispy fried chicken on clean background",
            "prompt_zh": "脆皮炸雞",
            "input": "https://images.unsplash.com/photo-1562967914-608f82629710?w=800&q=80",
            "result": "https://images.unsplash.com/photo-1562967914-608f82629710?w=800&q=80",
        },
        {
            "topic": "desserts",
            "prompt": "Mango shaved ice dessert on white background",
            "prompt_zh": "芒果冰",
            "input": "https://images.unsplash.com/photo-1563805042-7684c019e1cb?w=800&q=80",
            "result": "https://images.unsplash.com/photo-1563805042-7684c019e1cb?w=800&q=80",
        },
        {
            "topic": "packaging",
            "prompt": "Eco drink cup on clean background",
            "prompt_zh": "環保飲料杯",
            "input": "https://images.unsplash.com/photo-1558642084-fd07fae5282e?w=800&q=80",
            "result": "https://images.unsplash.com/photo-1558642084-fd07fae5282e?w=800&q=80",
        },
    ],
    "product_scene": [
        {
            "topic": "studio",
            "prompt": "Skincare bottle in minimalist studio scene",
            "prompt_zh": "極簡工作室保養品",
            "input": "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=800&q=80",
            "result": "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=800&q=80",
        },
        {
            "topic": "outdoor",
            "prompt": "Coffee bag in forest morning scene",
            "prompt_zh": "森林晨光咖啡包",
            "input": "https://images.unsplash.com/photo-1442512595331-e89e73853f31?w=800&q=80",
            "result": "https://images.unsplash.com/photo-1442512595331-e89e73853f31?w=800&q=80",
        },
        {
            "topic": "kitchen",
            "prompt": "Sauce bottle on marble kitchen counter",
            "prompt_zh": "大理石廚房醬料",
            "input": "https://images.unsplash.com/photo-1556910103-1c02745aae4d?w=800&q=80",
            "result": "https://images.unsplash.com/photo-1556910103-1c02745aae4d?w=800&q=80",
        },
        {
            "topic": "cafe",
            "prompt": "Artisan pastry on wooden cafe table",
            "prompt_zh": "木桌手工糕點",
            "input": "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=800&q=80",
            "result": "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=800&q=80",
        },
    ],
    "try_on": [
        {
            "topic": "dress",
            "prompt": "Floral summer dress",
            "prompt_zh": "碎花夏裙",
            "input": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=800&q=80",
            "result": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=800&q=80",
            "params": {"clothing_id": "dress-1", "clothing_type": "dress", "model_id": "female-1"},
        },
        {
            "topic": "tshirt",
            "prompt": "White cotton t-shirt",
            "prompt_zh": "白色純棉T恤",
            "input": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=800&q=80",
            "result": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=800&q=80",
            "params": {"clothing_id": "tshirt-1", "clothing_type": "top", "model_id": "female-1"},
        },
        {
            "topic": "jacket",
            "prompt": "Denim jacket",
            "prompt_zh": "丹寧外套",
            "input": "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=800&q=80",
            "result": "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=800&q=80",
            "params": {"clothing_id": "jacket-1", "clothing_type": "outerwear", "model_id": "female-1"},
        },
        {
            "topic": "blouse",
            "prompt": "White blouse",
            "prompt_zh": "白襯衫",
            "input": "https://images.unsplash.com/photo-1434389677669-e08b4cac3105?w=800&q=80",
            "result": "https://images.unsplash.com/photo-1434389677669-e08b4cac3105?w=800&q=80",
            "params": {"clothing_id": "blouse-1", "clothing_type": "top", "model_id": "female-1"},
        },
    ],
    "room_redesign": [
        {
            "topic": "living_room",
            "prompt": "Scandinavian living room",
            "prompt_zh": "北歐客廳",
            "input": "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=800&q=80",
            "result": "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=800&q=80",
            "params": {"room_id": "room-1", "room_type": "living_room", "style_id": "scandinavian"},
        },
        {
            "topic": "bedroom",
            "prompt": "Japanese minimalist bedroom",
            "prompt_zh": "日式極簡臥室",
            "input": "https://images.unsplash.com/photo-1616594039964-ae9021a400a0?w=800&q=80",
            "result": "https://images.unsplash.com/photo-1616594039964-ae9021a400a0?w=800&q=80",
            "params": {"room_id": "room-2", "room_type": "bedroom", "style_id": "japanese"},
        },
        {
            "topic": "kitchen",
            "prompt": "Modern minimalist kitchen",
            "prompt_zh": "現代極簡廚房",
            "input": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800&q=80",
            "result": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800&q=80",
            "params": {"room_id": "room-3", "room_type": "kitchen", "style_id": "modern_minimalist"},
        },
        {
            "topic": "bathroom",
            "prompt": "Industrial loft bathroom",
            "prompt_zh": "工業風浴室",
            "input": "https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=800&q=80",
            "result": "https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=800&q=80",
            "params": {"room_id": "room-4", "room_type": "bathroom", "style_id": "industrial"},
        },
    ],
    "short_video": [
        {
            "topic": "food",
            "prompt": "Bubble tea product reel",
            "prompt_zh": "珍奶短影片",
            "input": "https://images.unsplash.com/photo-1558857563-c0c6ee6ff8e4?w=800&q=80",
            "result_video": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        },
        {
            "topic": "fashion",
            "prompt": "Fashion show reel",
            "prompt_zh": "時尚短片",
            "input": "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=800&q=80",
            "result_video": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4",
        },
        {
            "topic": "product",
            "prompt": "Skincare product reveal",
            "prompt_zh": "保養品開箱",
            "input": "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=800&q=80",
            "result_video": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
        },
        {
            "topic": "lifestyle",
            "prompt": "Morning coffee routine",
            "prompt_zh": "早晨咖啡日常",
            "input": "https://images.unsplash.com/photo-1442512595331-e89e73853f31?w=800&q=80",
            "result_video": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4",
        },
    ],
    "ai_avatar": [
        {
            "topic": "presenter",
            "prompt": "Professional business presenter",
            "prompt_zh": "商務簡報人物",
            "input": "https://images.unsplash.com/photo-1508214751196-bcfd4ca60f91?w=800&q=80",
            "result_video": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4",
            "params": {"avatar_id": "avatar-1", "script_id": "script-1", "language": "en"},
        },
        {
            "topic": "teacher",
            "prompt": "Friendly teacher avatar",
            "prompt_zh": "友善老師虛擬人",
            "input": "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=800&q=80",
            "result_video": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyrides.mp4",
            "params": {"avatar_id": "avatar-2", "script_id": "script-2", "language": "en"},
        },
    ],
    "effect": [
        {
            "topic": "oil_painting",
            "prompt": "Oil painting style",
            "prompt_zh": "油畫風格",
            "input": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=800&q=80",
            "result": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=800&q=80",
            "params": {"style_id": "oil_painting"},
        },
        {
            "topic": "anime",
            "prompt": "Anime style portrait",
            "prompt_zh": "動漫風肖像",
            "input": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=800&q=80",
            "result": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=800&q=80",
            "params": {"style_id": "anime"},
        },
        {
            "topic": "cyberpunk",
            "prompt": "Cyberpunk neon style",
            "prompt_zh": "賽博龐克霓虹風",
            "input": "https://images.unsplash.com/photo-1518837695005-2083093ee35b?w=800&q=80",
            "result": "https://images.unsplash.com/photo-1518837695005-2083093ee35b?w=800&q=80",
            "params": {"style_id": "cyberpunk"},
        },
        {
            "topic": "watercolor",
            "prompt": "Watercolor illustration",
            "prompt_zh": "水彩插畫",
            "input": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=800&q=80",
            "result": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=800&q=80",
            "params": {"style_id": "watercolor"},
        },
    ],
}


async def main():
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(Material).where(Material.source == MaterialSource.SEED)
        )
        existing_rows = existing.scalars().all()
        if existing_rows:
            print(f"Deleting {len(existing_rows)} existing SEED rows...")
            await db.execute(delete(Material).where(Material.source == MaterialSource.SEED))
            await db.commit()

        total = 0
        for tool_type_str, entries in FIXTURES.items():
            tool_type = ToolType(tool_type_str)
            for idx, entry in enumerate(entries):
                material = Material(
                    id=uuid4(),
                    tool_type=tool_type,
                    topic=entry["topic"],
                    topic_zh=entry.get("topic_zh"),
                    prompt=entry["prompt"],
                    prompt_zh=entry.get("prompt_zh"),
                    language="en",
                    source=MaterialSource.SEED,
                    status=MaterialStatus.APPROVED,
                    is_active=True,
                    lookup_hash=_hash(tool_type_str, idx),
                    input_image_url=entry.get("input"),
                    result_image_url=entry.get("result"),
                    result_watermarked_url=entry.get("result") or entry.get("result_video"),
                    result_video_url=entry.get("result_video"),
                    result_thumbnail_url=entry.get("input"),
                    input_params=entry.get("params", {}),
                    quality_score=0.9,
                    tags=[tool_type_str, "demo-fixture"],
                )
                db.add(material)
                total += 1

        await db.commit()
        print(f"Seeded {total} demo fixture materials across {len(FIXTURES)} tool types.")


if __name__ == "__main__":
    asyncio.run(main())
