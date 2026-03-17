#!/usr/bin/env python3
"""
Seed demo data for VidGo platform.
Inserts sample materials, tool showcases, and a verified test user
so all tool pages and the landing page work without AI API keys.

Generates enough materials for each tool so the frontend looks complete:
- background_removal: 8 examples
- product_scene: 64 (8 products × 8 scenes)
- try_on: 36 (6 clothing × 6 models)
- room_redesign: 20 (4 rooms × 5 styles)
- short_video: 8 examples
- ai_avatar: 24 (8 avatars × 3 scripts)
- pattern_generate: 6 examples
- effect: 8 examples

Usage (inside container):
    python -m scripts.seed_demo_data

Usage (from host):
    docker exec vidgo_backend python -m scripts.seed_demo_data
"""
import asyncio
import hashlib
import sys
import uuid
import random

sys.path.insert(0, "/app")

from sqlalchemy import select, func, delete
from app.core.database import AsyncSessionLocal
from app.core import security
from app.models.user import User
from app.models.material import Material, ToolType, MaterialSource, MaterialStatus
from app.models.demo import ToolShowcase


# ── Verified test user ──────────────────────────────────────────────────
TEST_EMAIL = "demo@vidgo.ai"
TEST_PASSWORD = "Demo1234!"
ADMIN_EMAIL = "admin@vidgo.ai"
ADMIN_PASSWORD = "Admin1234!"


# =============================================================================
# UNSPLASH RESULT IMAGES (royalty-free placeholders for generated results)
# =============================================================================

# Generic result images pool - used as "generated" outputs
RESULT_IMAGES = [
    "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&q=80",
    "https://images.unsplash.com/photo-1491553895911-0055eca6402d?w=600&q=80",
    "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=600&q=80",
    "https://images.unsplash.com/photo-1483985988355-763728e1935b?w=600&q=80",
    "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=600&q=80",
    "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600&q=80",
    "https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=600&q=80",
    "https://images.unsplash.com/photo-1579783902614-a3fb3927b6a5?w=600&q=80",
    "https://images.unsplash.com/photo-1460661419201-fd4cecdf8a8b?w=600&q=80",
    "https://images.unsplash.com/photo-1534972195531-d756b9bfa9f2?w=600&q=80",
    "https://images.unsplash.com/photo-1524592094714-0f0654e20314?w=600&q=80",
    "https://images.unsplash.com/photo-1577803645773-f96470509666?w=600&q=80",
    "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=600&q=80",
    "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=600&q=80",
    "https://images.unsplash.com/photo-1618219908412-a29a1bb7b86e?w=600&q=80",
    "https://images.unsplash.com/photo-1556909172-54557c7e4fb7?w=600&q=80",
]

def _pick_result(idx: int) -> str:
    return RESULT_IMAGES[idx % len(RESULT_IMAGES)]


# =============================================================================
# BACKGROUND REMOVAL: 8 examples (matched by t.id / t.input_image_url)
# =============================================================================

BG_REMOVAL_ITEMS = [
    {"input": "https://images.unsplash.com/photo-1585386959984-a4155224a1ad?w=600&fit=crop",
     "result": "https://images.unsplash.com/photo-1585386959984-a4155224a1ad?w=600&fit=crop&bg=transparent",
     "prompt": "Remove background from skincare bottle", "prompt_zh": "保養品瓶去背", "topic": "packaging"},
    {"input": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&fit=crop",
     "result": "https://images.unsplash.com/photo-1546868871-af0de0ae72be?w=600&q=80",
     "prompt": "Remove background from watch photo", "prompt_zh": "手錶產品去背", "topic": "equipment"},
    {"input": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&fit=crop",
     "result": "https://images.unsplash.com/photo-1491553895911-0055eca6402d?w=600&q=80",
     "prompt": "Remove background from red sneakers", "prompt_zh": "紅色球鞋去背", "topic": "snacks"},
    {"input": "https://images.unsplash.com/photo-1491553895911-0055eca6402d?w=600&fit=crop",
     "result": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&q=80",
     "prompt": "Remove background from running shoes", "prompt_zh": "跑鞋去背", "topic": "drinks"},
    {"input": "https://images.unsplash.com/photo-1560343090-f0409e92791a?w=600&fit=crop",
     "result": "https://images.unsplash.com/photo-1560343090-f0409e92791a?w=600&fit=crop",
     "prompt": "Remove background from sneaker pair", "prompt_zh": "球鞋對去背", "topic": "desserts"},
    {"input": "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=600&fit=crop",
     "result": "https://images.unsplash.com/photo-1564466809058-bf4114d55352?w=600&q=80",
     "prompt": "Remove background from camera", "prompt_zh": "相機去背", "topic": "meals"},
    {"input": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&fit=crop",
     "result": "https://images.unsplash.com/photo-1572635196237-14b3f281503f?w=600&q=80",
     "prompt": "Remove background from headphones", "prompt_zh": "耳機去背", "topic": "signage"},
    {"input": "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=600&fit=crop",
     "result": "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=600&fit=crop",
     "prompt": "Remove background from cosmetics", "prompt_zh": "化妝品去背", "topic": "ingredients"},
]


# =============================================================================
# PRODUCT SCENE: 8 products × 8 scenes = 64 materials
# Frontend matches: input_params.product_id + input_params.scene_type
# =============================================================================

PRODUCTS = [
    {"id": "product-1", "name": "Bubble Tea", "name_zh": "珍珠奶茶",
     "url": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400&fit=crop"},
    {"id": "product-2", "name": "Canvas Tote Bag", "name_zh": "帆布托特包",
     "url": "https://images.unsplash.com/photo-1544816155-12df9643f363?w=400&fit=crop"},
    {"id": "product-3", "name": "Handmade Jewelry", "name_zh": "手工飾品",
     "url": "https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=400&fit=crop"},
    {"id": "product-4", "name": "Skincare Serum", "name_zh": "保養精華液",
     "url": "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=400&fit=crop"},
    {"id": "product-5", "name": "Coffee Beans", "name_zh": "咖啡豆",
     "url": "https://images.unsplash.com/photo-1447933601403-0c6688de566e?w=400&fit=crop"},
    {"id": "product-6", "name": "Espresso Machine", "name_zh": "義式咖啡機",
     "url": "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=400&fit=crop"},
    {"id": "product-7", "name": "Handmade Candle", "name_zh": "手工蠟燭",
     "url": "https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=400&fit=crop"},
    {"id": "product-8", "name": "Gift Box Set", "name_zh": "禮盒組合",
     "url": "https://images.unsplash.com/photo-1549465220-1a8b9238cd48?w=400&fit=crop"},
]

SCENES = [
    {"id": "studio", "name": "Studio", "name_zh": "攝影棚",
     "prompt": "professional studio lighting, white background, soft shadows"},
    {"id": "nature", "name": "Nature", "name_zh": "自然場景",
     "prompt": "natural outdoor setting, soft sunlight, greenery"},
    {"id": "elegant", "name": "Elegant", "name_zh": "質感場景",
     "prompt": "warm elegant background, cozy lighting, refined atmosphere"},
    {"id": "minimal", "name": "Minimal", "name_zh": "極簡風格",
     "prompt": "clean minimal white backdrop, simple composition"},
    {"id": "lifestyle", "name": "Lifestyle", "name_zh": "生活情境",
     "prompt": "cozy home environment, lifestyle context, warm lighting"},
    {"id": "urban", "name": "Urban", "name_zh": "都市街景",
     "prompt": "urban city street, modern architecture, stylish backdrop"},
    {"id": "seasonal", "name": "Seasonal", "name_zh": "季節",
     "prompt": "seasonal autumn leaves, warm golden hour lighting"},
    {"id": "holiday", "name": "Holiday", "name_zh": "節日",
     "prompt": "festive holiday decorations, warm celebration theme"},
]

# Scene result images (different angle per scene for variety)
SCENE_RESULTS = {
    "studio": "https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=600&q=80",
    "nature": "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?w=600&q=80",
    "elegant": "https://images.unsplash.com/photo-1524592094714-0f0654e20314?w=600&q=80",
    "minimal": "https://images.unsplash.com/photo-1557683316-973673baf926?w=600&q=80",
    "lifestyle": "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600&q=80",
    "urban": "https://images.unsplash.com/photo-1449824913935-59a10b8d2000?w=600&q=80",
    "seasonal": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=600&q=80",
    "holiday": "https://images.unsplash.com/photo-1513885535751-8b9238bd345a?w=600&q=80",
}


# =============================================================================
# TRY-ON: 6 clothing × 6 models = 36 materials
# Frontend matches: input_params.clothing_id + input_params.model_id
# =============================================================================

CLOTHING_ITEMS = [
    {"id": "c1", "label": "White Blouse", "label_zh": "白色襯衫", "type": "casual",
     "url": "https://images.unsplash.com/photo-1434389677669-e08b4cac3105?w=400&fit=crop"},
    {"id": "c2", "label": "Blue Dress", "label_zh": "藍色洋裝", "type": "dresses",
     "url": "https://images.unsplash.com/photo-1594938298603-c8148c4b4357?w=400&fit=crop"},
    {"id": "c3", "label": "Denim Jacket", "label_zh": "牛仔外套", "type": "outerwear",
     "url": "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=400&fit=crop"},
    {"id": "c4", "label": "Floral Dress", "label_zh": "碎花洋裝", "type": "dresses",
     "url": "https://images.unsplash.com/photo-1578587018452-892bacefd3f2?w=400&fit=crop"},
    {"id": "c5", "label": "Jeans", "label_zh": "牛仔褲", "type": "casual",
     "url": "https://images.unsplash.com/photo-1542272604-787c3835535d?w=400&fit=crop"},
    {"id": "c6", "label": "White T-Shirt", "label_zh": "白色T恤", "type": "sportswear",
     "url": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400&fit=crop"},
    {"id": "c7", "label": "Business Suit", "label_zh": "商務西裝", "type": "formal",
     "url": "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=400&fit=crop"},
    {"id": "c8", "label": "Leather Watch", "label_zh": "皮革手錶", "type": "accessories",
     "url": "https://images.unsplash.com/photo-1524592094714-0f0654e20314?w=400&fit=crop"},
]

MODEL_OPTIONS = [
    {"id": "female-1", "gender": "female",
     "url": "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=200&h=200&fit=crop&crop=face"},
    {"id": "female-2", "gender": "female",
     "url": "https://images.unsplash.com/photo-1508214751196-bcfd4ca60f91?w=200&h=200&fit=crop&crop=face"},
    {"id": "female-3", "gender": "female",
     "url": "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=200&h=200&fit=crop&crop=face"},
    {"id": "male-1", "gender": "male",
     "url": "https://images.unsplash.com/photo-1681097561932-36d0df02b379?w=200&h=200&fit=crop&crop=face"},
    {"id": "male-2", "gender": "male",
     "url": "https://images.unsplash.com/photo-1608908271310-57a24a9447db?w=200&h=200&fit=crop&crop=face"},
    {"id": "male-3", "gender": "male",
     "url": "https://images.unsplash.com/photo-1667127752169-74c7e4d8822f?w=200&h=200&fit=crop&crop=face"},
]

# Try-on result images pool
TRYON_RESULTS = [
    "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=600&q=80",
    "https://images.unsplash.com/photo-1483985988355-763728e1935b?w=600&q=80",
    "https://images.unsplash.com/photo-1509631179647-0177331693ae?w=600&q=80",
    "https://images.unsplash.com/photo-1539109136881-3be0616acf4b?w=600&q=80",
    "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=600&q=80",
    "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=600&q=80",
]

FEMALE_ONLY_TYPES = {"dresses"}


# =============================================================================
# ROOM REDESIGN: 4 rooms × 5 styles = 20 materials
# Frontend matches: input_params.room_id + input_params.room_type + input_params.style_id
# =============================================================================

ROOMS = [
    {"id": "room-1", "name": "Living Room", "room_type": "living_room",
     "url": "https://images.unsplash.com/photo-1554995207-c18c203602cb?w=800"},
    {"id": "room-2", "name": "Bedroom", "room_type": "bedroom",
     "url": "https://images.unsplash.com/photo-1616594039964-ae9021a400a0?w=800"},
    {"id": "room-3", "name": "Kitchen", "room_type": "kitchen",
     "url": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800"},
    {"id": "room-4", "name": "Bathroom", "room_type": "bathroom",
     "url": "https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=800"},
]

ROOM_STYLES = [
    {"id": "modern_minimalist", "name": "Modern Minimalist", "name_zh": "現代極簡"},
    {"id": "scandinavian", "name": "Scandinavian", "name_zh": "北歐風格"},
    {"id": "japanese", "name": "Japanese Zen", "name_zh": "日式禪風"},
    {"id": "industrial", "name": "Industrial", "name_zh": "工業風"},
    {"id": "mid_century_modern", "name": "Mid-Century Modern", "name_zh": "中世紀現代"},
]

ROOM_RESULT_MAPPING = {
    "living_room": [
        "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=600&q=80",
        "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?w=600&q=80",
        "https://images.unsplash.com/photo-1583847268964-b28ce8fba1f3?w=600&q=80",
        "https://images.unsplash.com/photo-1567016432779-094069958ea5?w=600&q=80",
        "https://images.unsplash.com/photo-1497366216548-37526070297c?w=600&q=80",
    ],
    "bedroom": [
        "https://images.unsplash.com/photo-1618219908412-a29a1bb7b86e?w=600&q=80",
        "https://images.unsplash.com/photo-1505693314120-0d443867891c?w=600&q=80",
        "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=600&q=80",
        "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=600&q=80",
        "https://images.unsplash.com/photo-1540518614846-7eded433c457?w=600&q=80",
    ],
    "kitchen": [
        "https://images.unsplash.com/photo-1556909172-54557c7e4fb7?w=600&q=80",
        "https://images.unsplash.com/photo-1556909212-d5b604d0c90d?w=600&q=80",
        "https://images.unsplash.com/photo-1556910103-1c02745aae4d?w=600&q=80",
        "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?w=600&q=80",
        "https://images.unsplash.com/photo-1556909190-eccf4a8bf97a?w=600&q=80",
    ],
    "bathroom": [
        "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600&q=80",
        "https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=600&q=80",
        "https://images.unsplash.com/photo-1600566752355-35792bedcfea?w=600&q=80",
        "https://images.unsplash.com/photo-1620626011761-996317b8d101?w=600&q=80",
        "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?w=600&q=80",
    ]
}


# =============================================================================
# SHORT VIDEO: 8 examples (matched by t.id)
# =============================================================================

SHORT_VIDEO_ITEMS = [
    {"input": "https://images.unsplash.com/photo-1522383225653-ed111181a951?w=600&fit=crop",
     "prompt": "Cherry blossom petals falling in slow motion, cinematic",
     "prompt_zh": "櫻花花瓣慢動作飄落，電影感", "topic": "promo", "motion": "zoom_in"},
    {"input": "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=600&fit=crop",
     "prompt": "Skincare product rotating on marble surface, studio lighting",
     "prompt_zh": "保養品在大理石上旋轉，攝影棚燈光", "topic": "product_showcase", "motion": "rotate"},
    {"input": "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=600&fit=crop",
     "prompt": "Coffee being poured into a glass cup, overhead view",
     "prompt_zh": "咖啡倒入玻璃杯，俯瞰角度", "topic": "tutorial", "motion": "pan_right"},
    {"input": "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=600&fit=crop",
     "prompt": "Fashion model walking on city street, golden hour",
     "prompt_zh": "時尚模特在城市街頭走秀，黃金時段", "topic": "brand_intro", "motion": "pan_left"},
    {"input": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=600&fit=crop",
     "prompt": "Mountain landscape with clouds moving, time lapse",
     "prompt_zh": "山景雲朵移動，縮時攝影", "topic": "promo", "motion": "zoom_out"},
    {"input": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=600&fit=crop",
     "prompt": "Bubble tea shop interior, warm lighting, cozy atmosphere",
     "prompt_zh": "珍奶店內部，溫暖燈光，舒適氛圍", "topic": "product_showcase", "motion": "auto"},
    {"input": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&fit=crop",
     "prompt": "Product showcase sneakers dynamic camera",
     "prompt_zh": "球鞋產品展示動態鏡頭", "topic": "tutorial", "motion": "zoom_in"},
    {"input": "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=600&fit=crop",
     "prompt": "Interior design room tour video",
     "prompt_zh": "室內設計房間導覽影片", "topic": "brand_intro", "motion": "pan_right"},
]


# =============================================================================
# AI AVATAR: 8 avatars × 3 scripts = 24 materials
# Frontend matches: input_params.avatar_id + input_params.script_id
# =============================================================================

AVATARS = [
    {"id": "female-1", "gender": "female", "name_zh": "怡君",
     "url": "https://images.unsplash.com/photo-1615262239828-a4d49e6503ea?w=512&fit=crop&crop=faces"},
    {"id": "female-2", "gender": "female", "name_zh": "雅婷",
     "url": "https://images.unsplash.com/photo-1615262239126-1931bdb03182?w=512&fit=crop&crop=faces"},
    {"id": "female-3", "gender": "female", "name_zh": "佳穎",
     "url": "https://images.unsplash.com/photo-1566589430181-a51c280be4b1?w=512&fit=crop&crop=faces"},
    {"id": "female-4", "gender": "female", "name_zh": "淑芬",
     "url": "https://images.unsplash.com/photo-1614387256720-5b994a2bb8e5?w=512&fit=crop&crop=faces"},
    {"id": "male-1", "gender": "male", "name_zh": "志偉",
     "url": "https://images.unsplash.com/photo-1681097561932-36d0df02b379?w=512&fit=crop&crop=faces"},
    {"id": "male-2", "gender": "male", "name_zh": "冠宇",
     "url": "https://images.unsplash.com/photo-1608908271310-57a24a9447db?w=512&fit=crop&crop=faces"},
    {"id": "male-3", "gender": "male", "name_zh": "宗翰",
     "url": "https://images.unsplash.com/photo-1633177188754-980c2a6b6266?w=512&fit=crop&crop=faces"},
    {"id": "male-4", "gender": "male", "name_zh": "家豪",
     "url": "https://images.unsplash.com/photo-1727605507453-dfe1e74abfbc?w=512&fit=crop&crop=faces"},
]

AVATAR_SCRIPTS = [
    {"id": "spokesperson-1", "category": "spokesperson",
     "text_zh": "保溫瓶品牌故事", "text_en": "Thermos brand story"},
    {"id": "spokesperson-2", "category": "spokesperson",
     "text_zh": "草本洗髮精故事", "text_en": "Herbal shampoo story"},
    {"id": "spokesperson-3", "category": "spokesperson",
     "text_zh": "阿里山茶故事", "text_en": "Alishan tea story"},
    {"id": "product-intro-1", "category": "product_intro",
     "text_zh": "智慧電子鍋介紹", "text_en": "Smart cooker intro"},
    {"id": "product-intro-2", "category": "product_intro",
     "text_zh": "音波牙刷介紹", "text_en": "Sonic toothbrush intro"},
    {"id": "product-intro-3", "category": "product_intro",
     "text_zh": "護眼檯燈介紹", "text_en": "Desk lamp intro"},
    {"id": "customer-service-1", "category": "customer_service",
     "text_zh": "充電線售後服務", "text_en": "Charging cable service"},
    {"id": "customer-service-2", "category": "customer_service",
     "text_zh": "洗衣精安全說明", "text_en": "Laundry detergent safety"},
    {"id": "customer-service-3", "category": "customer_service",
     "text_zh": "奶瓶常見問題", "text_en": "Baby bottle FAQ"},
    {"id": "social-media-1", "category": "social_media",
     "text_zh": "面膜限時優惠", "text_en": "Face mask flash sale"},
    {"id": "social-media-2", "category": "social_media",
     "text_zh": "無線耳機限時特賣", "text_en": "Earbuds flash sale"},
    {"id": "social-media-3", "category": "social_media",
     "text_zh": "芒果乾推薦", "text_en": "Dried mango recommendation"},
]

AVATAR_RESULT_IMAGES = [
    "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=600&q=80",
    "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=600&q=80",
    "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=600&q=80",
    "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=600&q=80",
]


# =============================================================================
# PATTERN GENERATE: 6 examples
# =============================================================================

PATTERN_ITEMS = [
    {"prompt": "Floral seamless pattern, spring colors", "prompt_zh": "花卉無縫圖案，春季色彩",
     "topic": "floral", "result": "https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=600&q=80"},
    {"prompt": "Geometric abstract pattern, bold colors", "prompt_zh": "幾何抽象圖案，大膽色彩",
     "topic": "geometric", "result": "https://images.unsplash.com/photo-1534120247760-c44c3e4a62f1?w=600&q=80"},
    {"prompt": "Seamless tileable pattern, clean lines", "prompt_zh": "無縫可拼接圖案，俐落線條",
     "topic": "seamless", "result": "https://images.unsplash.com/photo-1528459801416-a9e53bbf4e17?w=600&q=80"},
    {"prompt": "Traditional wave pattern, classic style", "prompt_zh": "傳統波浪圖案，經典風格",
     "topic": "traditional", "result": "https://images.unsplash.com/photo-1507908708918-778587c9e563?w=600&q=80"},
    {"prompt": "Abstract art pattern, luxury design", "prompt_zh": "抽象藝術圖案，奢華設計",
     "topic": "abstract", "result": "https://images.unsplash.com/photo-1534972195531-d756b9bfa9f2?w=600&q=80"},
    {"prompt": "3D rendered pattern, depth effect", "prompt_zh": "3D渲染圖案，立體效果",
     "topic": "3d", "result": "https://images.unsplash.com/photo-1557683316-973673baf926?w=600&q=80"},
    {"prompt": "Interior decorative pattern, warm tones", "prompt_zh": "室內裝飾圖案，暖色調",
     "topic": "interior", "result": "https://images.unsplash.com/photo-1579783902614-a3fb3927b6a5?w=600&q=80"},
    {"prompt": "Product mockup pattern, professional layout", "prompt_zh": "產品展示圖案，專業排版",
     "topic": "mockup", "result": "https://images.unsplash.com/photo-1460661419201-fd4cecdf8a8b?w=600&q=80"},
]


# =============================================================================
# EFFECT / STYLE TRANSFER: 8 examples
# =============================================================================

EFFECT_ITEMS = [
    {"input": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=600&q=80",
     "result": "https://images.unsplash.com/photo-1579783902614-a3fb3927b6a5?w=600&q=80",
     "prompt": "Oil painting style transfer", "prompt_zh": "油畫風格轉換",
     "topic": "oil_painting", "effect_prompt": "oil painting, masterpiece, brushstrokes"},
    {"input": "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?w=600&q=80",
     "result": "https://images.unsplash.com/photo-1460661419201-fd4cecdf8a8b?w=600&q=80",
     "prompt": "Watercolor landscape effect", "prompt_zh": "水彩風景效果",
     "topic": "watercolor", "effect_prompt": "watercolor painting, soft washes, delicate"},
    {"input": "https://images.unsplash.com/photo-1500964757637-c85e8a162699?w=600&q=80",
     "result": "https://images.unsplash.com/photo-1613376023733-0a73315d9b06?w=600&q=80",
     "prompt": "Anime illustration style", "prompt_zh": "動漫插畫風格",
     "topic": "anime", "effect_prompt": "anime style, cel shading, vibrant"},
    {"input": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&q=80",
     "result": "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600&q=80",
     "prompt": "Ghibli anime style", "prompt_zh": "吉卜力動漫風格",
     "topic": "ghibli", "effect_prompt": "studio ghibli style, hand-drawn, soft"},
    {"input": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&q=80",
     "result": "https://images.unsplash.com/photo-1533628635777-112b2239b1c7?w=600&q=80",
     "prompt": "Cartoon illustration style", "prompt_zh": "卡通插畫風格",
     "topic": "cartoon", "effect_prompt": "cartoon, bold outlines, flat colors"},
    {"input": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&q=80",
     "result": "https://images.unsplash.com/photo-1526498460520-4c246339dccb?w=600&q=80",
     "prompt": "Oil painting portrait style", "prompt_zh": "油畫肖像風格",
     "topic": "oil_painting", "effect_prompt": "oil painting portrait, classical, thick brushstrokes"},
    {"input": "https://images.unsplash.com/photo-1572635196237-14b3f281503f?w=600&q=80",
     "result": "https://images.unsplash.com/photo-1460661419201-fd4cecdf8a8b?w=600&q=80",
     "prompt": "Watercolor still life effect", "prompt_zh": "水彩靜物效果",
     "topic": "watercolor", "effect_prompt": "watercolor still life, soft edges, transparent washes"},
    {"input": "https://images.unsplash.com/photo-1515705576963-95cad62945b6?w=600&q=80",
     "result": "https://images.unsplash.com/photo-1534972195531-d756b9bfa9f2?w=600&q=80",
     "prompt": "Anime character style effect", "prompt_zh": "動漫角色風格",
     "topic": "anime", "effect_prompt": "anime character, detailed, colorful"},
]


# =============================================================================
# HASH HELPER
# =============================================================================

def _hash(tool_type: str, prompt: str, effect_prompt: str = None, extra: str = "") -> str:
    content = f"{tool_type}:{prompt}:{effect_prompt or ''}:{extra}"
    return hashlib.sha256(content.encode()).hexdigest()[:64]


# =============================================================================
# SEED FUNCTIONS
# =============================================================================

async def seed_users(db):
    """Create verified demo + admin users."""
    created = []
    for email, password, is_admin, name in [
        (TEST_EMAIL, TEST_PASSWORD, False, "Demo User"),
        (ADMIN_EMAIL, ADMIN_PASSWORD, True, "Admin"),
    ]:
        r = await db.execute(select(User).where(User.email == email))
        if r.scalar_one_or_none():
            print(f"  User {email} already exists")
            continue
        user = User(
            email=email,
            username=name.lower().replace(" ", ""),
            full_name=name,
            hashed_password=security.get_password_hash(password),
            is_active=True,
            is_superuser=is_admin,
            email_verified=True,
            subscription_credits=100,
            purchased_credits=50,
        )
        db.add(user)
        created.append(email)
    await db.commit()
    for e in created:
        print(f"  Created user: {e}")


async def seed_materials(db):
    """Insert comprehensive materials for all 8 tools.

    If materials already exist, deletes and re-seeds to ensure correct
    input_params matching for the frontend.
    """
    existing = await db.execute(select(func.count()).select_from(Material).where(Material.source == MaterialSource.SEED))
    count = existing.scalar() or 0
    if count >= 150:
        print(f"  Materials already has {count} seed rows (≥150), skipping re-seed")
        return 0

    # Delete old seed materials to re-seed with correct input_params
    if count > 0:
        await db.execute(delete(Material).where(Material.source == MaterialSource.SEED))
        await db.commit()
        print(f"  Deleted {count} old seed materials for re-seeding")

    inserted = 0

    # ── Background Removal (8) ─────────────────────────────────────────
    for i, item in enumerate(BG_REMOVAL_ITEMS):
        m = Material(
            id=uuid.uuid4(),
            lookup_hash=_hash("background_removal", item["prompt"], extra=str(i)),
            tool_type=ToolType.BACKGROUND_REMOVAL,
            topic=item["topic"],
            main_topic="Background Removal",
            prompt=item["prompt"], prompt_zh=item["prompt_zh"], prompt_en=item["prompt"],
            input_image_url=item["input"],
            result_image_url=item["result"],
            result_watermarked_url=item["result"],
            result_thumbnail_url=item["input"],
            status=MaterialStatus.APPROVED, source=MaterialSource.SEED,
            is_active=True, is_featured=(i == 0),
            quality_score=0.9, sort_order=i,
            tags=[item["topic"], "background_removal"],
            input_params={},
            title_en=item["prompt"], title_zh=item["prompt_zh"],
        )
        db.add(m)
        inserted += 1

    # ── Product Scene (8 products × 8 scenes = 64) ────────────────────
    for pi, product in enumerate(PRODUCTS):
        for si, scene in enumerate(SCENES):
            prompt = f"{product['name']} in {scene['name']} scene"
            prompt_zh = f"{product['name_zh']}在{scene['name_zh']}場景"
            result = SCENE_RESULTS.get(scene["id"], _pick_result(pi * 8 + si))
            m = Material(
                id=uuid.uuid4(),
                lookup_hash=_hash("product_scene", prompt, extra=f"{product['id']}_{scene['id']}"),
                tool_type=ToolType.PRODUCT_SCENE,
                topic=scene["id"],
                main_topic="Product Scene",
                prompt=prompt, prompt_zh=prompt_zh, prompt_en=prompt,
                input_image_url=product["url"],
                result_image_url=result,
                result_watermarked_url=result,
                result_thumbnail_url=result,
                status=MaterialStatus.APPROVED, source=MaterialSource.SEED,
                is_active=True, is_featured=(pi == 0 and si == 0),
                quality_score=0.9, sort_order=pi * 8 + si,
                tags=[scene["id"], "product_scene"],
                input_params={
                    "product_id": product["id"],
                    "scene_type": scene["id"],
                    "input_url": product["url"],
                },
                title_en=prompt, title_zh=prompt_zh,
            )
            db.add(m)
            inserted += 1

    # ── Try-On (6 clothing × 6 models = 36, skip female-only for males) ──
    for ci, clothing in enumerate(CLOTHING_ITEMS):
        for mi, model in enumerate(MODEL_OPTIONS):
            # Skip female-only clothing for male models
            if clothing["type"] in FEMALE_ONLY_TYPES and model["gender"] == "male":
                continue
            prompt = f"{clothing['label']} on {model['id']}"
            prompt_zh = f"{clothing['label_zh']}試穿{model['id']}"
            result = TRYON_RESULTS[(ci + mi) % len(TRYON_RESULTS)]
            m = Material(
                id=uuid.uuid4(),
                lookup_hash=_hash("try_on", prompt, extra=f"{clothing['id']}_{model['id']}"),
                tool_type=ToolType.TRY_ON,
                topic=clothing["type"],
                main_topic="Try On",
                prompt=prompt, prompt_zh=prompt_zh, prompt_en=prompt,
                input_image_url=clothing["url"],
                result_image_url=result,
                result_watermarked_url=result,
                result_thumbnail_url=result,
                status=MaterialStatus.APPROVED, source=MaterialSource.SEED,
                is_active=True, is_featured=(ci == 0 and mi == 0),
                quality_score=0.9, sort_order=ci * 6 + mi,
                tags=[clothing["type"], "try_on"],
                input_params={
                    "clothing_id": clothing["id"],
                    "model_id": model["id"],
                    "clothing_type": clothing["type"],
                    "gender_restriction": "female" if clothing["type"] in FEMALE_ONLY_TYPES else None,
                },
                title_en=prompt, title_zh=prompt_zh,
            )
            db.add(m)
            inserted += 1

    # ── Room Redesign (4 rooms × 5 styles = 20) ──────────────────────
    for ri, room in enumerate(ROOMS):
        for si, style in enumerate(ROOM_STYLES):
            prompt = f"{room['name']} in {style['name']} style"
            prompt_zh = f"{room['name']}{style['name_zh']}風格"
            room_imgs = ROOM_RESULT_MAPPING.get(room["room_type"], ROOM_RESULT_MAPPING["living_room"])
            result = room_imgs[si % len(room_imgs)]
            m = Material(
                id=uuid.uuid4(),
                lookup_hash=_hash("room_redesign", prompt, extra=f"{room['id']}_{style['id']}"),
                tool_type=ToolType.ROOM_REDESIGN,
                topic=room["room_type"],
                main_topic="Room Redesign",
                prompt=prompt, prompt_zh=prompt_zh, prompt_en=prompt,
                input_image_url=room["url"],
                result_image_url=result,
                result_watermarked_url=result,
                result_thumbnail_url=result,
                status=MaterialStatus.APPROVED, source=MaterialSource.SEED,
                is_active=True, is_featured=(ri == 0 and si == 0),
                quality_score=0.9, sort_order=ri * 5 + si,
                tags=[style["id"], "room_redesign", room["room_type"]],
                input_params={
                    "room_id": room["id"],
                    "room_type": room["room_type"],
                    "style_id": style["id"],
                    "input_url": room["url"],
                },
                title_en=prompt, title_zh=prompt_zh,
            )
            db.add(m)
            inserted += 1

    # ── Short Video (8) ───────────────────────────────────────────────
    for i, item in enumerate(SHORT_VIDEO_ITEMS):
        m = Material(
            id=uuid.uuid4(),
            lookup_hash=_hash("short_video", item["prompt"], extra=str(i)),
            tool_type=ToolType.SHORT_VIDEO,
            topic=item["topic"],
            main_topic="Short Video",
            prompt=item["prompt"], prompt_zh=item["prompt_zh"], prompt_en=item["prompt"],
            input_image_url=item["input"],
            result_image_url=item["input"],  # Use input as thumbnail
            result_video_url=item["input"],   # Placeholder (no real video)
            result_watermarked_url=item["input"],
            result_thumbnail_url=item["input"],
            status=MaterialStatus.APPROVED, source=MaterialSource.SEED,
            is_active=True, is_featured=(i == 0),
            quality_score=0.9, sort_order=i,
            tags=[item["topic"], "short_video"],
            input_params={"motion": item["motion"]},
            title_en=item["prompt"], title_zh=item["prompt_zh"],
        )
        db.add(m)
        inserted += 1

    # ── AI Avatar (8 avatars × 3 scripts = 24) ───────────────────────
    # Select 3 representative scripts for each avatar
    scripts_per_avatar = 3
    for ai, avatar in enumerate(AVATARS):
        for si in range(scripts_per_avatar):
            script = AVATAR_SCRIPTS[(ai + si * 4) % len(AVATAR_SCRIPTS)]
            prompt = f"{avatar['name_zh']} - {script['text_zh']}"
            prompt_en = f"Avatar {avatar['id']} - {script['text_en']}"
            result = AVATAR_RESULT_IMAGES[(ai + si) % len(AVATAR_RESULT_IMAGES)]
            m = Material(
                id=uuid.uuid4(),
                lookup_hash=_hash("ai_avatar", prompt, extra=f"{avatar['id']}_{script['id']}"),
                tool_type=ToolType.AI_AVATAR,
                topic=script["category"],
                main_topic="AI Avatar",
                prompt=prompt, prompt_zh=prompt, prompt_en=prompt_en,
                input_image_url=avatar["url"],
                result_image_url=result,
                result_video_url=result,  # Placeholder
                result_watermarked_url=result,
                result_thumbnail_url=avatar["url"],
                status=MaterialStatus.APPROVED, source=MaterialSource.SEED,
                is_active=True, is_featured=(ai == 0 and si == 0),
                quality_score=0.9, sort_order=ai * 3 + si,
                tags=[script["category"], "ai_avatar"],
                input_params={
                    "avatar_id": avatar["id"],
                    "script_id": script["id"],
                    "language": "zh-TW",
                },
                title_en=prompt_en, title_zh=prompt,
            )
            db.add(m)
            inserted += 1

    # ── Pattern Generate (6) ─────────────────────────────────────────
    for i, item in enumerate(PATTERN_ITEMS):
        m = Material(
            id=uuid.uuid4(),
            lookup_hash=_hash("pattern_generate", item["prompt"], extra=str(i)),
            tool_type=ToolType.PATTERN_GENERATE,
            topic=item["topic"],
            main_topic="Pattern Generate",
            prompt=item["prompt"], prompt_zh=item["prompt_zh"], prompt_en=item["prompt"],
            result_image_url=item["result"],
            result_watermarked_url=item["result"],
            result_thumbnail_url=item["result"],
            status=MaterialStatus.APPROVED, source=MaterialSource.SEED,
            is_active=True, is_featured=(i == 0),
            quality_score=0.9, sort_order=i,
            tags=[item["topic"], "pattern_generate"],
            input_params={},
            title_en=item["prompt"], title_zh=item["prompt_zh"],
        )
        db.add(m)
        inserted += 1

    # ── Effect / Style Transfer (8) ──────────────────────────────────
    for i, item in enumerate(EFFECT_ITEMS):
        m = Material(
            id=uuid.uuid4(),
            lookup_hash=_hash("effect", item["prompt"], item.get("effect_prompt"), str(i)),
            tool_type=ToolType.EFFECT,
            topic=item["topic"],
            main_topic="Effect",
            prompt=item["prompt"], prompt_zh=item["prompt_zh"], prompt_en=item["prompt"],
            effect_prompt=item.get("effect_prompt"),
            input_image_url=item["input"],
            result_image_url=item["result"],
            result_watermarked_url=item["result"],
            result_thumbnail_url=item["result"],
            status=MaterialStatus.APPROVED, source=MaterialSource.SEED,
            is_active=True, is_featured=(i == 0),
            quality_score=0.9, sort_order=i,
            tags=[item["topic"], "effect"],
            input_params={"style": item.get("effect_prompt", "")},
            title_en=item["prompt"], title_zh=item["prompt_zh"],
        )
        db.add(m)
        inserted += 1

    await db.commit()
    print(f"  Inserted {inserted} materials total:")
    print(f"    background_removal: {len(BG_REMOVAL_ITEMS)}")
    print(f"    product_scene: {len(PRODUCTS) * len(SCENES)}")
    tryon_count = sum(1 for c in CLOTHING_ITEMS for m in MODEL_OPTIONS
                      if not (c["type"] in FEMALE_ONLY_TYPES and m["gender"] == "male"))
    print(f"    try_on: {tryon_count}")
    print(f"    room_redesign: {len(ROOMS) * len(ROOM_STYLES)}")
    print(f"    short_video: {len(SHORT_VIDEO_ITEMS)}")
    print(f"    ai_avatar: {len(AVATARS) * scripts_per_avatar}")
    print(f"    pattern_generate: {len(PATTERN_ITEMS)}")
    print(f"    effect: {len(EFFECT_ITEMS)}")
    return inserted


async def seed_tool_showcases(db):
    """Insert tool showcases for landing page gallery."""
    existing = await db.execute(select(func.count()).select_from(ToolShowcase))
    count = existing.scalar() or 0
    if count > 0:
        print(f"  ToolShowcase table already has {count} rows, skipping")
        return 0

    showcase_data = [
        {"tool_category": "portrait", "tool_id": "virtual_try_on",
         "tool_name": "Virtual Try-On", "tool_name_zh": "AI試穿",
         "source_image_url": CLOTHING_ITEMS[0]["url"],
         "result_image_url": TRYON_RESULTS[0],
         "prompt": "White Blouse try-on", "prompt_zh": "白色襯衫試穿",
         "title": "AI Virtual Try-On", "title_zh": "AI虛擬試穿",
         "is_featured": True},
        {"tool_category": "ecommerce", "tool_id": "background_removal",
         "tool_name": "Background Removal", "tool_name_zh": "背景移除",
         "source_image_url": BG_REMOVAL_ITEMS[0]["input"],
         "result_image_url": BG_REMOVAL_ITEMS[0]["result"],
         "prompt": BG_REMOVAL_ITEMS[0]["prompt"], "prompt_zh": BG_REMOVAL_ITEMS[0]["prompt_zh"],
         "title": "Product Background Removal", "title_zh": "產品背景移除",
         "is_featured": True},
        {"tool_category": "ecommerce", "tool_id": "product_scene",
         "tool_name": "Product Scene", "tool_name_zh": "產品場景",
         "source_image_url": PRODUCTS[0]["url"],
         "result_image_url": SCENE_RESULTS["studio"],
         "prompt": "Bubble Tea in Studio scene", "prompt_zh": "珍珠奶茶攝影棚場景",
         "title": "Studio Product Shot", "title_zh": "攝影棚產品照",
         "is_featured": True},
        {"tool_category": "architecture", "tool_id": "room_redesign",
         "tool_name": "Room Redesign", "tool_name_zh": "房間重設計",
         "source_image_url": ROOMS[0]["url"],
         "result_image_url": ROOM_RESULT_MAPPING["living_room"][0],
         "prompt": "Modern minimalist living room", "prompt_zh": "現代極簡客廳",
         "title": "Modern Living Room", "title_zh": "現代客廳",
         "is_featured": True},
        {"tool_category": "edit_tools", "tool_id": "style_transfer",
         "tool_name": "Style Transfer", "tool_name_zh": "風格轉換",
         "source_image_url": EFFECT_ITEMS[0]["input"],
         "result_image_url": EFFECT_ITEMS[0]["result"],
         "prompt": EFFECT_ITEMS[0]["prompt"], "prompt_zh": EFFECT_ITEMS[0]["prompt_zh"],
         "title": "Oil Painting Effect", "title_zh": "油畫效果",
         "is_featured": True},
        {"tool_category": "ecommerce", "tool_id": "product_video",
         "tool_name": "Product Video", "tool_name_zh": "產品影片",
         "source_image_url": SHORT_VIDEO_ITEMS[0]["input"],
         "result_image_url": SHORT_VIDEO_ITEMS[0]["input"],
         "prompt": SHORT_VIDEO_ITEMS[0]["prompt"], "prompt_zh": SHORT_VIDEO_ITEMS[0]["prompt_zh"],
         "title": "Dynamic Product Video", "title_zh": "動態產品影片",
         "is_featured": True},
        {"tool_category": "portrait", "tool_id": "ai_avatar",
         "tool_name": "AI Avatar", "tool_name_zh": "AI虛擬分身",
         "source_image_url": AVATARS[0]["url"],
         "result_image_url": AVATAR_RESULT_IMAGES[0],
         "prompt": "Professional avatar video", "prompt_zh": "專業虛擬分身影片",
         "title": "Professional Avatar", "title_zh": "專業虛擬分身",
         "is_featured": True},
    ]

    inserted = 0
    for i, data in enumerate(showcase_data):
        sc = ToolShowcase(
            id=uuid.uuid4(),
            tool_category=data["tool_category"],
            tool_id=data["tool_id"],
            tool_name=data["tool_name"],
            tool_name_zh=data.get("tool_name_zh"),
            source_image_url=data.get("source_image_url"),
            result_image_url=data.get("result_image_url"),
            prompt=data.get("prompt"),
            prompt_zh=data.get("prompt_zh"),
            title=data.get("title"),
            title_zh=data.get("title_zh"),
            description=data.get("description", f"Sample showcase for {data['tool_name']}"),
            description_zh=data.get("description_zh", data.get("title_zh")),
            is_featured=data.get("is_featured", False),
            is_active=True,
            sort_order=i,
            quality_score=0.9,
            style_tags=[data["tool_category"], data["tool_id"]],
        )
        db.add(sc)
        inserted += 1

    await db.commit()
    print(f"  Inserted {inserted} tool showcases")
    return inserted


async def main():
    print("=== VidGo Demo Data Seeder (Comprehensive) ===")
    print()

    async with AsyncSessionLocal() as db:
        print("[1/3] Seeding users...")
        await seed_users(db)

        print("[2/3] Seeding materials (comprehensive)...")
        await seed_materials(db)

        print("[3/3] Seeding tool showcases...")
        await seed_tool_showcases(db)

    print()
    print("Done! Test accounts:")
    print(f"  Demo user: {TEST_EMAIL} / {TEST_PASSWORD}")
    print(f"  Admin:     {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print()
    print("All tool pages should now show preset content with correct matching.")


if __name__ == "__main__":
    asyncio.run(main())
