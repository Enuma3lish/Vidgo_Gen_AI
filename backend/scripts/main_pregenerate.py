#!/usr/bin/env python3
"""
VidGo Main Pre-generation Pipeline
===================================

This is the UNIFIED pre-generation script that merges:
- pregenerate.py (original flow-based approach)
- pregenerate_mapping.py (mapping-based approach)

WORKFLOW:
=========
1. CLI parses arguments (--tool, --limit, --dry-run, --all)
2. Initialize API clients (PiAPI, Pollo, A2E)
3. Run selected generator(s) based on tool mappings
4. Store results locally first, then batch to DB
5. Cleanup temp files and print summary

SUPPORTED TOOLS (8 total):
==========================
- ai_avatar: Avatar × Script × Language → A2E → Video
- background_removal: Prompt → T2I → PiAPI Remove BG → PNG
- room_redesign: Room × Style → T2I → Styled Room
- short_video: Prompt → Pollo T2V → Video
- product_scene: Product × Scene → T2I → Product in Scene
- try_on: Model × Clothing (gender restrictions) → T2I → Model wearing Clothing
- pattern_generate: Style × Prompt → T2I → Seamless Pattern
- effect: Source Image → T2I → I2I Style Transfer → Styled Image

Usage:
    python -m scripts.main_pregenerate --tool ai_avatar --limit 10
    python -m scripts.main_pregenerate --tool try_on --limit 50
    python -m scripts.main_pregenerate --tool effect --limit 15
    python -m scripts.main_pregenerate --all --limit 20
    python -m scripts.main_pregenerate --dry-run
"""
import asyncio
import argparse
import hashlib
import logging
import os
import sys
import time
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add app to path
sys.path.insert(0, "/app")

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.material import Material, ToolType, MaterialSource, MaterialStatus
from app.core.config import get_settings

# Import Topic Registry - Single Source of Truth for topics
from app.config.topic_registry import (
    TOOL_TOPICS,
    get_topics_for_tool,
    get_topic_ids_for_tool,
    get_landing_topics,
    get_landing_topic_ids,
)

# Import service clients
import httpx
from scripts.services import PiAPIClient, PolloClient, A2EClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)
settings = get_settings()
SHORT_VIDEO_LENGTH = int(getattr(settings, "SHORT_VIDEO_LENGTH", 8))

# Tool-specific limits when running --all: ensures enough examples for customers
# Effect: 8 sources × 5 styles = 40 | Try-on: ~6 models × ~10 clothing (male skips female-only)
TOOL_LIMITS = {
    "effect": 40,           # 8 sources × 5 styles
    "try_on": 70,           # 6 models × clothing (male skips dresses/blouse/scarf)
    "product_scene": 32,    # 8 products × 4 scenes (subset for demo)
    "short_video": 24,      # 4 topics × 6 prompts
    "background_removal": 24,  # 8 topics × 3 prompts
    "room_redesign": 24,    # 4 rooms × 6 styles
    "pattern_generate": 10, # 5 styles × 2 prompts
    "ai_avatar": 24,        # 4 topics × 3 scripts × 2 languages
}


# ============================================================================
# TEMP LOCAL STORAGE
# ============================================================================

TEMP_DIR = Path("/app/static/temp_pregenerate")


def ensure_temp_dir():
    """Ensure temp directory exists."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


def cleanup_temp_dir():
    """Remove temp directory after storing to DB."""
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
        logger.info(f"Cleaned up temp directory: {TEMP_DIR}")


# ============================================================================
# AI AVATAR MAPPINGS
# ============================================================================

# Avatar definitions - SYNCED with frontend AIAvatar.vue (Asian/Chinese, color, free Unsplash)
# Any avatar can read any script. URLs must match frontend FEMALE_AVATAR_URLS / MALE_AVATAR_URLS.
AVATAR_MAPPING = {
    "female-1": {
        "prompt": "Professional portrait of a young Taiwanese woman, natural makeup, confident smile, studio lighting, headshot, Chinese face",
        "gender": "female",
        "name_zh": "怡君",
        "name_en": "Yi-Jun",
        "url": "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=512&fit=crop&crop=faces"
    },
    "female-2": {
        "prompt": "Professional portrait of a Chinese woman in her early 30s, elegant makeup, warm expression, soft lighting, headshot, Asian face",
        "gender": "female",
        "name_zh": "雅婷",
        "name_en": "Ya-Ting",
        "url": "https://images.unsplash.com/photo-1524504388940-b1c1722653e6?w=512&fit=crop&crop=faces"
    },
    "female-3": {
        "prompt": "Professional portrait of a young Chinese woman, business blazer, approachable smile, corporate headshot, Asian face",
        "gender": "female",
        "name_zh": "佳穎",
        "name_en": "Jia-Ying",
        "url": "https://images.unsplash.com/photo-1534751516642-a1af1ef26a56?w=512&fit=crop&crop=faces"
    },
    "female-4": {
        "prompt": "Professional portrait of a Taiwanese woman, trendy style, friendly expression, modern headshot, Chinese face",
        "gender": "female",
        "name_zh": "淑芬",
        "name_en": "Shu-Fen",
        "url": "https://images.unsplash.com/photo-1544006943-0e92b9a3b95d?w=512&fit=crop&crop=faces"
    },
    "male-1": {
        "prompt": "Professional portrait of an Asian man, plaid shirt, calm expression, studio portrait, Chinese face",
        "gender": "male",
        "name_zh": "志偉",
        "name_en": "Zhi-Wei",
        "url": "https://images.unsplash.com/photo-1758600431229-191932ccee81?w=512&fit=crop&crop=faces"
    },
    "male-2": {
        "prompt": "Professional portrait of a Chinese man in his 30s, business suit, trustworthy smile, corporate headshot, Asian face",
        "gender": "male",
        "name_zh": "冠宇",
        "name_en": "Guan-Yu",
        "url": "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=512&fit=crop&crop=faces"
    },
    "male-3": {
        "prompt": "Professional portrait of a young Chinese man, friendly smile, casual professional headshot, Asian face",
        "gender": "male",
        "name_zh": "宗翰",
        "name_en": "Zong-Han",
        "url": "https://images.unsplash.com/photo-1600486914327-2f364e2d7731?w=512&fit=crop&crop=faces"
    },
    "male-4": {
        "prompt": "Professional portrait of a mature Chinese man, confident expression, business headshot, Asian face",
        "gender": "male",
        "name_zh": "家豪",
        "name_en": "Jia-Hao",
        "url": "https://images.unsplash.com/photo-1552375816-4b96b919e67a?w=512&fit=crop&crop=faces"
    }
}

# Script definitions - DECOUPLED from avatars
# Organized by topic (matching topic_registry.py)
# IMPORTANT: Scripts must CLEARLY sell a product or service (target: small businesses, SMB)
# Most avatars should be Chinese (zh-TW) - VidGo targets Taiwan/SMB market
# 4 categories × 3 scripts = 12 scripts covering diverse daily life scenarios:
# food/drinks, bakery, beauty, education, fitness, flowers, candles, etc.
SCRIPT_MAPPING = {
    # Each category shows a DIFFERENT promotional technique for small business
    # spokesperson: Origin story / brand storytelling (builds trust)
    "spokesperson": [
        {
            "id": "spokesperson-1",
            "text_en": "I started this bubble tea shop 3 years ago with one recipe from my grandmother. Today we sell over 500 cups a day. Our secret? Real milk, hand-cooked pearls, no shortcuts. Come taste the difference—first cup free for new customers!",
            "text_zh": "三年前我用阿嬤的一個配方開了這家珍珠奶茶店。現在每天賣超過500杯。我們的秘訣？鮮奶、手煮珍珠、不偷工減料。來嚐嚐看有什麼不同——新客人第一杯免費！"
        },
        {
            "id": "spokesperson-2",
            "text_en": "Every morning at 5 AM, I bake these matcha cream rolls fresh. Only 50 per day because I refuse to use preservatives. When they are gone, they are gone. That is why our customers line up before we open. Come try one before today's batch sells out!",
            "text_zh": "每天早上五點，我親手烤製這些抹茶生乳捲。因為堅持不加防腐劑，每日限量50條。賣完就沒有了，這就是為什麼客人都在開店前排隊。快來嚐一條，今天的很快就賣完了！"
        },
        {
            "id": "spokesperson-3",
            "preferred_gender": "female",  # Nail salon / beauty → female avatar
            "text_en": "My customers always ask: how do you make nails look this good? Let me show you. This is our signature aurora cat-eye gel. Three layers, hand-painted gradient. It takes me 90 minutes per set. Book this week and get a free nail art upgrade worth 300!",
            "text_zh": "客人常問我：怎麼做出這麼美的指甲？讓我示範一下。這是我們的招牌極光貓眼凝膠，三層手繪漸層，每一組要90分鐘。本週預約送價值300元的美甲升級！"
        }
    ],
    # product_intro: Social proof / before-after / demo technique (shows results)
    "product_intro": [
        {
            "id": "product-intro-1",
            "text_en": "See this phone case? Customers said it survived a drop from a second-floor balcony. We tested it ourselves—dropped it 50 times. Still perfect. Military-grade protection, only 399. No wonder it is our best-seller with over 2000 five-star reviews!",
            "text_zh": "看這個手機殼？客人說它從二樓陽台掉下來都沒事。我們自己測試過——摔了50次，完好如初。軍規防護，只要399元。難怪它是我們的暢銷品，超過2000則五星評價！"
        },
        {
            "id": "product-intro-2",
            "preferred_gender": "female",  # Skincare testimonial ("my skin") → female avatar
            "text_en": "Left side: my skin one month ago. Right side: today. The only thing I changed was this serum. 100% plant-based, no alcohol, safe for sensitive skin. 599 for 30ml—that is less than 20 per day. Your skin deserves this. Free shipping over 1000!",
            "text_zh": "左邊是一個月前的我的皮膚，右邊是今天。唯一的改變就是這瓶精華液。100%植萃、無酒精、敏感肌也能用。30ml只要599元，每天不到20元。你的肌膚值得擁有。滿千免運！"
        },
        {
            "id": "product-intro-3",
            "text_en": "I make each candle by hand using soy wax and essential oils. This lavender one takes 48 hours to cure. Smell it once and you will understand why 80% of my customers reorder. Only 280 each. Light one up tonight and feel the difference!",
            "text_zh": "每一顆蠟燭都是我用大豆蠟和精油手工製作的。這款薰衣草需要48小時熟成。聞一次你就知道為什麼八成的客人都會回購。每顆只要280元。今晚點一顆，感受不一樣的品質！"
        }
    ],
    # customer_service: Trust-building / guarantee (reduces purchase anxiety)
    "customer_service": [
        {
            "id": "customer-service-1",
            "text_en": "Got your order and something is not right? Do not worry at all. Send us a photo on LINE and we will fix it within 24 hours—exchange, refund, or reship. That is our promise. We have handled over 5000 orders and our satisfaction rate is 99.2%!",
            "text_zh": "收到商品有問題嗎？完全不用擔心！LINE我們傳張照片，24小時內處理完畢——換貨、退款、重寄都可以。這是我們的承諾。超過5000筆訂單，滿意度99.2%！"
        },
        {
            "id": "customer-service-2",
            "text_en": "Welcome to our pet grooming studio! Before your first visit, let me explain how we work. We spend 15 minutes just letting your pet get comfortable. No rushing, no stress. That is why nervous dogs love coming back. Book a trial grooming for only 399!",
            "text_zh": "歡迎來到我們的寵物美容工作室！第一次來之前讓我說明一下。我們會花15分鐘讓毛孩先適應環境，不趕時間、零壓力。所以怕生的狗狗都喜歡回來。體驗價只要399元！"
        },
        {
            "id": "customer-service-3",
            "text_en": "Three things that make our repair shop different: one, we diagnose for free. Two, we only charge if we fix it. Three, every repair comes with a 90-day warranty. Fair and simple. Bring your phone in today—most repairs done in under one hour!",
            "text_zh": "我們維修店有三個不同：第一，免費檢測。第二，修不好不收費。第三，每次維修都有90天保固。公平、簡單。今天就帶手機來——大部分維修一小時內完成！"
        }
    ],
    # social_media: Interactive / viral hooks / emotional (drives shares)
    "social_media": [
        {
            "id": "social-media-1",
            "text_en": "Save this video! Show it at checkout and get buy-one-get-one-free on all drinks today only. We do this every Tuesday—follow us so you never miss it. Last week 200 people used this deal. Do not miss out this time!",
            "text_zh": "存下這支影片！結帳時出示就能全品項飲料買一送一，限今天。每週二都有這個活動——追蹤我們才不會錯過。上週有200人使用了這個優惠，這次別再錯過了！"
        },
        {
            "id": "social-media-2",
            "preferred_gender": "female",  # Flower shop / emotional Mother's Day → female avatar
            "text_en": "A customer sent me this photo—she gave our flower box to her mom and her mom cried happy tears. That is why I do this. Mother's Day carnation boxes, handwrapped with love, only 680. Order by Friday for free delivery. Let us make someone smile together!",
            "text_zh": "一位客人傳了這張照片給我——她把我們的花禮盒送給媽媽，媽媽感動到流淚。這就是我做這行的原因。母親節康乃馨禮盒，用心手作包裝，只要680元。週五前預訂免運。一起讓人微笑吧！"
        },
        {
            "id": "social-media-3",
            "text_en": "Parents keep asking what their kids did in class today, so I started filming. Look at this—your child painted this in just one hour! Summer art classes, only 350 per session. Groups of 3 save 20%. Tag a parent who needs to see this!",
            "text_zh": "家長一直問小朋友今天上課做了什麼，所以我開始拍攝了。看這個——你的孩子一小時就畫出了這幅作品！暑假美術課，每堂只要350元。三人同行八折。標記一位需要看到這個的家長！"
        }
    ]
}


# ============================================================================
# BACKGROUND REMOVAL MAPPING
# ============================================================================

BACKGROUND_REMOVAL_MAPPING = {
    "drinks": {
        "prompts": [
            "A cup of bubble milk tea with tapioca pearls on white background, food photography, appetizing, studio lighting",
            "Fresh fruit tea with lemon and passion fruit in clear cup on white background, drink photography",
            "Iced coffee latte with cream swirl in transparent cup on white background, beverage product shot"
        ]
    },
    "snacks": {
        "prompts": [
            "Crispy fried chicken cutlet on white background, Taiwanese street food, appetizing food photography",
            "Grilled squid skewer on white background, night market snack, food product shot",
            "Scallion pancake on white background, golden crispy, traditional Taiwanese snack photography"
        ]
    },
    "desserts": {
        "prompts": [
            "Mango shaved ice dessert on white background, colorful toppings, food photography",
            "Egg tart pastry on white background, golden crust, bakery product photography",
            "Pineapple cake on white background, traditional Taiwanese pastry, product shot"
        ]
    },
    "meals": {
        "prompts": [
            "Braised pork rice bento box on white background, Taiwanese comfort food, appetizing",
            "Beef noodle soup bowl on white background, food photography, steaming hot",
            "Fried rice plate on white background, Chinese restaurant style, food product shot"
        ]
    },
    "packaging": {
        "prompts": [
            "Takeout paper bag with logo on white background, food delivery packaging, product shot",
            "Eco-friendly drink cup with straw on white background, beverage packaging photography",
            "Food container lunch box on white background, takeout packaging, clean product photo"
        ]
    },
    "equipment": {
        "prompts": [
            "Bubble tea sealing machine on white background, drink shop equipment, product photography",
            "Commercial blender on white background, restaurant kitchen equipment, clean product shot",
            "Point of sale tablet register on white background, shop equipment photography"
        ]
    },
    "signage": {
        "prompts": [
            "LED menu board display on white background, restaurant signage, product photography",
            "Wooden A-frame chalkboard sign on white background, cafe menu board, product shot",
            "Neon open sign on white background, shop signage, glowing product photography"
        ]
    },
    "ingredients": {
        "prompts": [
            "Fresh tapioca pearls in bowl on white background, bubble tea ingredient, food photography",
            "Assorted tea leaves in wooden scoop on white background, tea ingredient product shot",
            "Fresh fruits arranged on white background, mango strawberry kiwi, food ingredient shot"
        ]
    }
}


# ============================================================================
# ROOM REDESIGN MAPPING
# ============================================================================

# Room redesign: use same room IDs/URLs as frontend defaultRooms and same style IDs as /api/v1/interior/styles (DESIGN_STYLES)
# so demo matching (room_id + room_type + style_id) works.
ROOM_REDESIGN_MAPPING = {
    "room_types": {
        "room-1": {
            "name": "Living Room",
            "name_zh": "客廳",
            "url": "https://images.unsplash.com/photo-1554995207-c18c203602cb?w=800",
            "room_type": "living_room"
        },
        "room-2": {
            "name": "Bedroom",
            "name_zh": "臥室",
            "url": "https://images.unsplash.com/photo-1616594039964-ae9021a400a0?w=800",
            "room_type": "bedroom"
        },
        "room-3": {
            "name": "Kitchen",
            "name_zh": "廚房",
            "url": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800",
            "room_type": "kitchen"
        },
        "room-4": {
            "name": "Bathroom",
            "name_zh": "浴室",
            "url": "https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=800",
            "room_type": "bathroom"
        }
    },
    # Style IDs must match DESIGN_STYLES in interior_design_service (frontend /api/v1/interior/styles)
    "styles": None  # Filled from DESIGN_STYLES in generate_room_redesign
}


# ============================================================================
# PRODUCT SCENE MAPPING
# ============================================================================

PRODUCT_SCENE_MAPPING = {
    "products": {
        "product-1": {
            "name": "Bubble Tea",
            "name_zh": "珍珠奶茶",
            "prompt": "Studio product photo of a clear cup of bubble milk tea with tapioca pearls, centered, clean white background, soft shadows, commercial photography, 8K",
            "prompt_zh": "棚拍產品照：透明杯珍珠奶茶與黑色珍珠，置中構圖，乾淨白底，柔和陰影，商業攝影，8K"
        },
        "product-2": {
            "name": "Canvas Tote Bag",
            "name_zh": "帆布托特包",
            "prompt": "Studio product photo of a natural canvas tote bag with minimalist design, standing upright, clean white background, soft shadows, commercial photography, 8K",
            "prompt_zh": "棚拍產品照：自然色帆布托特包，簡約設計，直立擺放，乾淨白底，柔和陰影，商業攝影，8K"
        },
        "product-3": {
            "name": "Handmade Jewelry",
            "name_zh": "手工飾品",
            "prompt": "Studio product photo of handmade silver earrings and bracelet set on velvet display, centered, clean white background, jewelry photography, 8K",
            "prompt_zh": "棚拍產品照：手工銀耳環與手鍊組合，絨布展示台，置中構圖，乾淨白底，飾品攝影，8K"
        },
        "product-4": {
            "name": "Skincare Serum",
            "name_zh": "保養精華液",
            "prompt": "Studio product photo of a glass skincare serum bottle with dropper, clean cosmetics product style, white background, soft glow, 8K",
            "prompt_zh": "棚拍產品照：玻璃滴管保養精華液瓶，清新保養品風格，乾淨白底，柔光氛圍，8K"
        },
        "product-5": {
            "name": "Coffee Beans",
            "name_zh": "咖啡豆",
            "prompt": "Studio product photo of a kraft paper bag of roasted coffee beans with some beans scattered around, centered, clean white background, food product photography, 8K",
            "prompt_zh": "棚拍產品照：牛皮紙袋裝烘焙咖啡豆，周圍散落數顆咖啡豆，置中構圖，乾淨白底，食品攝影，8K"
        },
        "product-6": {
            "name": "Espresso Machine",
            "name_zh": "義式咖啡機",
            "prompt": "Studio product photo of a compact stainless steel espresso machine, front angle, clean white background, professional appliance advertising, 8K",
            "prompt_zh": "棚拍產品照：小型不鏽鋼義式咖啡機，正面角度，乾淨白底，家電廣告風格，8K"
        },
        "product-7": {
            "name": "Handmade Candle",
            "name_zh": "手工蠟燭",
            "prompt": "Studio product photo of a handmade soy wax candle in glass jar, centered, clean white background, cozy product advertising, 8K",
            "prompt_zh": "棚拍產品照：玻璃罐手工大豆蠟燭，置中構圖，乾淨白底，溫馨產品廣告風格，8K"
        },
        "product-8": {
            "name": "Gift Box Set",
            "name_zh": "禮盒組合",
            "prompt": "Studio product photo of an elegant gift box set with ribbon bow, assorted small items inside, centered, clean white background, gift product advertising, 8K",
            "prompt_zh": "棚拍產品照：精美禮盒組合附蝴蝶結緞帶，內含多樣小物，置中構圖，乾淨白底，禮品廣告風格，8K"
        }
    },
    "scenes": {
        "studio": {
            "name": "Studio",
            "name_zh": "攝影棚",
            "prompt": "professional studio lighting, solid color background, product photography"
        },
        "nature": {
            "name": "Nature",
            "name_zh": "自然",
            "prompt": "outdoor nature setting, sunlight, leaves, natural environment"
        },
        "elegant": {
            "name": "Elegant",
            "name_zh": "質感",
            "prompt": "warm elegant background, cozy lighting, refined atmosphere"
        },
        "minimal": {
            "name": "Minimal",
            "name_zh": "極簡",
            "prompt": "minimalist abstract background, soft shadows, clean composition"
        },
        "lifestyle": {
            "name": "Lifestyle",
            "name_zh": "生活風格",
            "prompt": "lifestyle home setting, cozy atmosphere, everyday context"
        },
        "urban": {
            "name": "Urban",
            "name_zh": "都市",
            "prompt": "urban city backdrop, modern architecture, street style"
        },
        "seasonal": {
            "name": "Seasonal",
            "name_zh": "季節",
            "prompt": "seasonal autumn leaves background, warm colors, cozy feeling"
        },
        "holiday": {
            "name": "Holiday",
            "name_zh": "節日",
            "prompt": "festive holiday decoration background, christmas lights, celebration"
        }
    }
}


# ============================================================================
# SHORT VIDEO MAPPING
# ============================================================================
#
# TARGET: Small businesses (SMB) selling everyday products/services—NOT luxury.
# Prompts must clearly show product type and use case (e.g., bubble tea, fried
# chicken, small shop, local brand). Explain what kind of service we provide.
#
# Topics MUST match topic_registry.py:
# product_showcase, brand_intro, tutorial, promo

SHORT_VIDEO_MAPPING = {
    "product_showcase": {
        "name": "Product Showcase",
        "name_zh": "產品展示",
        "prompts": [
            {
                "en": "Cinematic close-up of bubble milk tea being poured, tapioca pearls swirling, appetizing, 4K quality",
                "zh": "電影級珍珠奶茶沖泡特寫，珍珠旋轉，令人垂涎，4K品質"
            },
            {
                "en": "Fresh fried chicken cutlet being sliced open, steam rising, crispy golden crust, food commercial",
                "zh": "新鮮炸雞排切開特寫，蒸氣上升，金黃酥脆外皮，美食廣告"
            },
            {
                "en": "Colorful fruit tea with ice cubes and fresh fruits, condensation drops on cup, refreshing drink ad",
                "zh": "色彩繽紛水果茶加冰塊和新鮮水果，杯身水珠，清涼飲料廣告"
            },
            {
                "en": "Smartphone rotating on a clean pedestal, studio lighting, tech product showcase",
                "zh": "智慧型手機在底座上旋轉，攝影棚打光，科技產品展示"
            },
            {
                "en": "Running sneakers on clean studio floor, dynamic spotlight, sporty product commercial",
                "zh": "跑步運動鞋在乾淨棚拍地面上，動感聚光，運動產品廣告"
            },
            {
                "en": "Glass skincare serum bottle with soft glow, clean beauty product showcase, small business",
                "zh": "玻璃保養精華瓶柔光呈現，美妝產品展示，小店風格"
            }
        ]
    },
    "brand_intro": {
        "name": "Brand Introduction",
        "name_zh": "品牌介紹",
        "prompts": [
            {
                "en": "Cozy drink shop interior, barista preparing beverage behind counter, warm lighting, brand story",
                "zh": "溫馨飲料店內景，店員在吧台準備飲品，溫暖光線，品牌故事"
            },
            {
                "en": "Night market food stall, chef cooking with wok fire, authentic street food atmosphere, brand video",
                "zh": "夜市小吃攤，廚師鍋火翻炒，道地街頭美食氛圍，品牌影片"
            },
            {
                "en": "Small bakery kitchen, fresh bread coming out of oven, artisan craftsmanship, warm atmosphere",
                "zh": "小型烘焙廚房，新鮮麵包出爐，手工匠心，溫暖氛圍"
            },
            {
                "en": "Modern tech startup office, team collaborating around prototypes, clean minimal brand intro",
                "zh": "現代科技新創辦公室，團隊圍繞原型協作，清爽極簡品牌介紹"
            },
            {
                "en": "Cosmetics studio with glass bottles and soft light, small business beauty brand introduction",
                "zh": "美妝工作室玻璃瓶與柔光氛圍，美妝小店品牌介紹"
            },
            {
                "en": "Furniture showroom with modern sofa and warm lighting, lifestyle brand introduction",
                "zh": "家具展示間現代沙發與暖光氛圍，生活風格品牌介紹"
            }
        ]
    },
    "tutorial": {
        "name": "Tutorial",
        "name_zh": "教學影片",
        "prompts": [
            {
                "en": "Step by step bubble tea preparation, adding tapioca and milk, clear instruction video style",
                "zh": "珍珠奶茶製作步驟，加入珍珠和牛奶，清晰教學影片風格"
            },
            {
                "en": "Cooking tutorial, stir frying noodles in wok, step by step food preparation video",
                "zh": "烹飪教學，鍋中翻炒麵條，步驟式食物準備影片"
            },
            {
                "en": "Cake decorating tutorial, piping cream on dessert, close-up bakery tutorial video",
                "zh": "蛋糕裝飾教學，在甜點上擠奶油，特寫烘焙教學影片"
            },
            {
                "en": "Skincare routine tutorial, applying serum and moisturizer, clean bathroom counter, step by step",
                "zh": "保養步驟教學，塗抹精華與乳霜，乾淨洗手台，逐步示範"
            },
            {
                "en": "New gadget unboxing tutorial, hands opening smart device box, close-up product setup",
                "zh": "新品開箱教學，雙手拆開智慧裝置包裝，產品設定特寫"
            }
        ]
    },
    "promo": {
        "name": "Promotion",
        "name_zh": "促銷廣告",
        "prompts": [
            {
                "en": "Buy one get one free drink promotion, two cups of colorful beverages, festive discount graphics",
                "zh": "買一送一飲料促銷，兩杯色彩繽紛飲品，節慶折扣圖形"
            },
            {
                "en": "New menu item launch, delicious food reveal with spotlight, appetizing anticipation",
                "zh": "新菜單品項上市，聚光燈下美食揭幕，令人期待的美味"
            },
            {
                "en": "Summer special cold drinks promotion, ice and fruits splashing, refreshing seasonal offer",
                "zh": "夏季特飲促銷，冰塊和水果飛濺，清涼季節性優惠"
            },
            {
                "en": "Limited-time sneaker sale, dynamic motion graphics, sporty lifestyle promotion",
                "zh": "限時運動鞋特賣，動感圖形，運動生活風促銷"
            },
            {
                "en": "Home appliance discount event, modern espresso machine in spotlight, limited-time offer",
                "zh": "家電折扣活動，現代義式咖啡機聚光展示，限時優惠"
            }
        ]
    }
}


# ============================================================================
# TRY-ON MAPPING
# ============================================================================

# NOTE: input_image_url = CLOTHING preview image (shown in left panel)
#       result_image_url = model wearing the clothing (shown in right panel)
#
# GENDER RESTRICTIONS (must make sense):
#   - gender_restriction="female" = only female models (e.g. dresses, blouse)
#   - Male models SKIP female-only items (no men in wedding dress, etc.)
#   - Female models can wear all items (unisex + female-only)
#
# MODEL REQUIREMENTS FOR KLING AI VIRTUAL TRY-ON:
# - Full body shot (head to at least waist visible)
# - Clear visibility of upper body/torso
# - Neutral pose with arms at sides or slightly bent
# - Plain or minimal background
# - Good lighting, no harsh shadows on body
# - Model wearing simple base clothing (t-shirt or tank top)
#
# We use AI-generated models to ensure consistent quality and
# compliance with Kling AI's requirements.

# Model photo prompts for AI generation (PiAPI T2I)
# These prompts generate full-body fashion model photos suitable for virtual try-on
MODEL_GENERATION_PROMPTS = {
    "female": [
        {
            "id": "female-fullbody-1",
            "prompt": "Professional full body fashion photography of a young Asian woman, standing pose with arms relaxed at sides, wearing simple white fitted tank top and light blue jeans, neutral gray studio background, soft even lighting, 3/4 body shot showing from head to knees, clear visibility of upper body and torso, fashion model pose, high quality, 8K",
            "description": "Young Asian woman - casual white tank top"
        },
        {
            "id": "female-fullbody-2",
            "prompt": "Full body fashion photo of a Caucasian woman in her 20s, relaxed standing pose, wearing plain black t-shirt and beige pants, white studio background, professional lighting, full body visible from head to feet, fashion catalog style, high resolution",
            "description": "Caucasian woman - black t-shirt"
        },
        {
            "id": "female-fullbody-3",
            "prompt": "Professional model photography of a young woman with medium brown skin, standing confidently, wearing simple gray fitted top and dark jeans, clean white background, soft studio lighting, full body shot, arms naturally at sides, fashion portrait, 8K quality",
            "description": "Diverse woman - gray fitted top"
        }
    ],
    "male": [
        {
            "id": "male-fullbody-1",
            "prompt": "Professional full body fashion photography of a young Asian man, standing pose with relaxed posture, wearing plain white crew neck t-shirt and navy blue chinos, neutral gray studio background, even lighting, 3/4 body shot from head to knees, clear torso visibility, fashion model look, high quality, 8K",
            "description": "Young Asian man - white t-shirt"
        },
        {
            "id": "male-fullbody-2",
            "prompt": "Full body fashion photo of a Caucasian man in his late 20s, confident standing pose, wearing simple black polo shirt and khaki pants, white studio background, professional photography lighting, full body visible, catalog style, high resolution",
            "description": "Caucasian man - black polo"
        },
        {
            "id": "male-fullbody-3",
            "prompt": "Professional model photography of a man with athletic build, standing naturally, wearing fitted gray t-shirt and dark denim jeans, clean white background, soft studio lighting, full body shot showing head to feet, arms relaxed, fashion portrait style, 8K",
            "description": "Athletic man - gray t-shirt"
        }
    ]
}

# Generated model library - populated by generate_model_library()
# Format: {"female-fullbody-1": {"gender": "female", "url": "/static/models/..."}}
GENERATED_MODEL_LIBRARY = {}

# Fallback: Original Unsplash URLs (facial close-ups) - used when no generated models available
# These will NOT work well with Kling AI Virtual Try-On but provide backward compatibility
TRYON_FALLBACK_MODELS = {
    "female-1": {
        "gender": "female",
        "url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=512",
        "note": "Facial close-up - may fail with Kling AI Try-On"
    },
    "female-2": {
        "gender": "female",
        "url": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=512",
        "note": "Facial close-up - may fail with Kling AI Try-On"
    },
    "male-1": {
        "gender": "male",
        "url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=512",
        "note": "Facial close-up - may fail with Kling AI Try-On"
    }
}

TRYON_MAPPING = {
    # Models will be populated dynamically from GENERATED_MODEL_LIBRARY or fallback
    "models": {},
    "clothing": {
        "casual": [
            {
                "id": "casual-1",
                "name": "Casual Tank Top",
                "name_zh": "休閒背心套裝",
                "prompt": "black casual tank top with shorts, athletic style",
                "clothing_type": "general",
                "image_url": "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=400",
                "gender_restriction": None
            },
            {
                "id": "casual-2",
                "name": "Denim Jacket",
                "name_zh": "牛仔外套",
                "prompt": "blue denim jacket, casual style",
                "clothing_type": "general",
                "image_url": "https://images.unsplash.com/photo-1576995853123-5a10305d93c0?w=400",
                "gender_restriction": None
            }
        ],
        "formal": [
            {
                "id": "formal-1",
                "name": "Winter Coat",
                "name_zh": "冬季大衣",
                "prompt": "elegant beige winter coat, professional style",
                "clothing_type": "general",
                "image_url": "https://images.unsplash.com/photo-1539533018447-63fcce2678e4?w=400",
                "gender_restriction": None
            },
            {
                "id": "formal-2",
                "name": "Silk Scarf",
                "name_zh": "絲巾",
                "prompt": "elegant silk scarf, fashion accessory",
                "clothing_type": "general",
                "image_url": "https://images.unsplash.com/photo-1584030373081-f37b7bb4fa8e?w=400",
                "gender_restriction": "female"  # Female-only item
            }
        ],
        "sportswear": [
            {
                "id": "sportswear-1",
                "name": "Athletic Jacket",
                "name_zh": "運動夾克",
                "prompt": "green athletic jacket, outdoor sportswear",
                "clothing_type": "general",
                "image_url": "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=400",
                "gender_restriction": None
            },
            {
                "id": "sportswear-2",
                "name": "Sun Hat",
                "name_zh": "遮陽帽",
                "prompt": "stylish sun hat, summer accessory",
                "clothing_type": "general",
                "image_url": "https://images.unsplash.com/photo-1521369909029-2afed882baee?w=400",
                "gender_restriction": None
            }
        ],
        "outerwear": [
            {
                "id": "outerwear-1",
                "name": "Trench Coat",
                "name_zh": "風衣外套",
                "prompt": "classic beige trench coat, timeless style",
                "clothing_type": "general",
                "image_url": "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=400",
                "gender_restriction": None
            },
            {
                "id": "outerwear-2",
                "name": "Puffer Jacket",
                "name_zh": "羽絨外套",
                "prompt": "warm puffer jacket, winter style",
                "clothing_type": "general",
                "image_url": "https://images.unsplash.com/photo-1544022613-e87ca75a784a?w=400",
                "gender_restriction": None
            }
        ],
        "accessories": [
            {
                "id": "accessories-1",
                "name": "Sunglasses",
                "name_zh": "太陽眼鏡",
                "prompt": "fashionable sunglasses, summer style",
                "clothing_type": "general",
                "image_url": "https://images.unsplash.com/photo-1511499767150-a48a237f0083?w=400",
                "gender_restriction": None
            },
            {
                "id": "accessories-2",
                "name": "Watch",
                "name_zh": "手錶",
                "prompt": "classic wristwatch, everyday accessory",
                "clothing_type": "general",
                "image_url": "https://images.unsplash.com/photo-1524592094714-0f0654e20314?w=400",
                "gender_restriction": None
            }
        ],
        "dresses": [
            {
                "id": "dresses-1",
                "name": "Summer Dress",
                "name_zh": "夏季洋裝",
                "prompt": "red floral summer dress, feminine style",
                "clothing_type": "dress",
                "image_url": "https://images.unsplash.com/photo-1572804013427-4d7ca7268217?w=400",
                "gender_restriction": "female"  # Only female models
            },
            {
                "id": "dresses-2",
                "name": "Elegant Blouse",
                "name_zh": "優雅襯衫",
                "prompt": "elegant blouse, casual chic style",
                "clothing_type": "general",
                "image_url": "https://images.unsplash.com/photo-1564257631407-4deb1f99d992?w=400",
                "gender_restriction": "female"  # Female-only item
            }
        ]
    }
}


# ============================================================================
# PATTERN GENERATE MAPPING
# ============================================================================

# Pattern designs for common business use: packaging, branding, textiles, menus, social media
PATTERN_GENERATE_MAPPING = {
    "styles": {
        "seamless": {
            "name": "Seamless",
            "name_zh": "無縫圖案",
            "prompts": [
                {
                    "en": "Elegant floral pattern for packaging and gift wrap, rose and navy, brand-friendly, seamless tile",
                    "zh": "禮品包裝與品牌用優雅花卉圖案，玫瑰與深藍色，無縫磁磚"
                },
                {
                    "en": "Japanese wave pattern for menu border and restaurant branding, navy and white, seamless",
                    "zh": "菜單邊框與餐飲品牌用日式波浪紋，深藍與白，無縫重複"
                }
            ]
        },
        "floral": {
            "name": "Floral",
            "name_zh": "花卉圖案",
            "prompts": [
                {
                    "en": "Cherry blossom pattern for cafe and bakery branding, soft pink and white, social media ready",
                    "zh": "咖啡廳與烘焙品牌用水彩櫻花圖案，粉白色，適合社群貼文"
                },
                {
                    "en": "Tropical palm pattern for beverage and summer promo, green and gold, packaging and ads",
                    "zh": "飲料與夏季促銷用熱帶棕櫚無縫圖案，綠金配色，包裝與廣告"
                }
            ]
        },
        "geometric": {
            "name": "Geometric",
            "name_zh": "幾何圖案",
            "prompts": [
                {
                    "en": "Modern geometric pattern for tech and retail branding, triangles black and gold, professional look",
                    "zh": "科技與零售品牌用現代幾何圖案，黑金三角形，高級感"
                },
                {
                    "en": "Art deco golden lines for shop product packaging and decor, hexagonal, seamless",
                    "zh": "商品包裝與店面裝飾用裝飾藝術金線圖案，六角形，無縫"
                }
            ]
        },
        "abstract": {
            "name": "Abstract",
            "name_zh": "抽象圖案",
            "prompts": [
                {
                    "en": "Marble texture pattern for cosmetics and skincare packaging, gold veins, professional brand",
                    "zh": "美妝保養品包裝用大理石紋理圖案，金色紋路，品牌感"
                },
                {
                    "en": "Vibrant abstract pattern for social media posts and flyers, watercolor style, small business",
                    "zh": "社群貼文與傳單用鮮豔抽象圖案，水彩風格，小商家適用"
                }
            ]
        },
        "traditional": {
            "name": "Traditional",
            "name_zh": "傳統紋樣",
            "prompts": [
                {
                    "en": "Chinese cloud pattern for restaurant and festival branding, red and gold, auspicious",
                    "zh": "餐飲與節慶品牌用中國雲紋，紅金配色，吉祥設計"
                },
                {
                    "en": "Japanese wave pattern for tea and beverage packaging, blue gradient, traditional motif",
                    "zh": "茶飲與飲料包裝用日式青海波紋，藍色漸層，傳統紋樣"
                }
            ]
        }
    }
}


# ============================================================================
# EFFECT (STYLE TRANSFER) MAPPING
# ============================================================================
#
# RELATIONSHIP (CRITICAL): Do NOT use another prompt to generate a "corresponding"
# image. Flow: (1) T2I generates source image from prompt, (2) Call Effect API
# with that EXISTING image + style prompt for I2I transform, (3) Store result.
# The example IS the transformation of the SAME image—input and output are
# linked by the same source. Style prompts describe ONLY art style, NOT products.
#
EFFECT_MAPPING = {
    "source_images": [
        {
            "name": "Bubble Tea",
            "name_zh": "珍珠奶茶",
            "prompt": "A cup of bubble milk tea with tapioca pearls, appetizing food photography, studio lighting, white background",
            "topic": "drinks"
        },
        {
            "name": "Fried Chicken",
            "name_zh": "炸雞排",
            "prompt": "Crispy fried chicken cutlet on a plate, Taiwanese street food photography, studio lighting",
            "topic": "snacks"
        },
        {
            "name": "Fruit Tea",
            "name_zh": "水果茶",
            "prompt": "Colorful fresh fruit tea in clear cup with ice, refreshing drink photography, studio lighting",
            "topic": "drinks"
        },
        {
            "name": "Handmade Candle",
            "name_zh": "手工蠟燭",
            "prompt": "Artisan handmade soy candle in glass jar, clean studio product photo, white background, soft shadow",
            "topic": "handmade"
        },
        {
            "name": "Canvas Tote Bag",
            "name_zh": "帆布托特包",
            "prompt": "Canvas tote bag with minimalist design, clean studio product photo, white background, soft shadow",
            "topic": "accessories"
        },
        {
            "name": "Skincare Serum",
            "name_zh": "保養精華液",
            "prompt": "Glass skincare serum bottle with dropper, clean cosmetics product photo, white background",
            "topic": "cosmetics"
        },
        {
            "name": "Coffee Beans",
            "name_zh": "咖啡豆",
            "prompt": "Fresh roasted coffee beans in kraft paper bag, artisan coffee product photo, white background",
            "topic": "food"
        },
        {
            "name": "Gift Box Set",
            "name_zh": "禮盒組合",
            "prompt": "Elegant gift box set with ribbon bow, boutique packaging product photo, white background",
            "topic": "gifts"
        }
    ],
    "styles": {
        "anime": {
            "name": "Anime",
            "name_zh": "動漫風格",
            "prompt": "anime style illustration for social media and ads, eye-catching for small business",
            "strength": 0.65
        },
        "ghibli": {
            "name": "Ghibli",
            "name_zh": "吉卜力風格",
            "prompt": "studio ghibli anime style for menu and cafe branding, hayao miyazaki",
            "strength": 0.65
        },
        "cartoon": {
            "name": "Cartoon",
            "name_zh": "卡通風格",
            "prompt": "cartoon pixar 3d style for product ads and flyers, family-friendly business",
            "strength": 0.60
        },
        "oil_painting": {
            "name": "Oil Painting",
            "name_zh": "油畫風格",
            "prompt": "oil painting artistic style for brand and restaurant marketing",
            "strength": 0.70
        },
        "watercolor": {
            "name": "Watercolor",
            "name_zh": "水彩風格",
            "prompt": "watercolor soft style for menu design and boutique branding",
            "strength": 0.65
        }
    }
}


# ============================================================================
# MAIN GENERATOR CLASS
# ============================================================================

class VidGoPreGenerator:
    """
    Unified VidGo Pre-generation Pipeline.

    Supports all 8 tools with mapping-based approach:
    - ai_avatar
    - background_removal
    - room_redesign
    - short_video
    - product_scene
    - try_on
    - pattern_generate
    - model_library (NEW: generates full-body model photos for try-on)
    """

    # Directory for generated model photos
    MODEL_LIBRARY_DIR = Path("/app/static/models")
    # Directory for cached try-on garment images (local copy so we can serve as URL or base64)
    TRYON_GARMENTS_DIR = Path("/app/static/tryon_garments")

    def __init__(self):
        # Initialize API clients
        self.piapi = PiAPIClient(os.getenv("PIAPI_KEY", ""))
        self.pollo = PolloClient(os.getenv("POLLO_API_KEY", ""))
        self.a2e = A2EClient(os.getenv("A2E_API_KEY", ""))
        # Ensure model library and try-on garments directories exist
        self.MODEL_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        self.TRYON_GARMENTS_DIR.mkdir(parents=True, exist_ok=True)

        # Load existing model library
        self._load_model_library()
        self.per_topic_limit: Optional[int] = None
        # Stats tracking
        self.stats = {"success": 0, "failed": 0, "by_tool": {}}

        # Local results storage (batch to DB after generation)
        self.local_results: Dict[str, List[Dict]] = {}

    def _topic_can_generate(self, topic_key: str, topic_counts: Dict[str, int], limit: int, total_count: int) -> bool:
        """Check if we can generate another example for a topic."""
        if self.per_topic_limit is None:
            return total_count < limit
        return topic_counts.get(topic_key, 0) < self.per_topic_limit

    def _topic_mark_generated(self, topic_key: str, topic_counts: Dict[str, int]) -> None:
        topic_counts[topic_key] = topic_counts.get(topic_key, 0) + 1

    async def _ensure_garment_local(self, cloth: Dict[str, Any]) -> str:
        """
        Download try-on garment image to local storage so we can send it as our URL
        (with PUBLIC_APP_URL) or as base64. Returns local path if cached, else original URL.
        """
        cloth_id = cloth.get("id", "")
        remote_url = cloth.get("image_url", "")
        if not remote_url or not cloth_id:
            return remote_url or ""
        # Safe filename from cloth id (e.g. casual-1 -> casual-1.jpg)
        ext = ".jpg"
        if ".png" in remote_url.lower():
            ext = ".png"
        local_path = self.TRYON_GARMENTS_DIR / f"{cloth_id}{ext}"
        if local_path.exists():
            return str(local_path)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(remote_url)
                r.raise_for_status()
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(r.content)
            logger.debug(f"Cached garment {cloth_id} to {local_path}")
        except Exception as e:
            logger.warning(f"Could not cache garment {cloth_id}: {e}, using remote URL")
            return remote_url
        return str(local_path)

    def _load_model_library(self):
        """Load existing model photos from disk into GENERATED_MODEL_LIBRARY."""
        global GENERATED_MODEL_LIBRARY, TRYON_MAPPING

        GENERATED_MODEL_LIBRARY.clear()
        model_dir = self.MODEL_LIBRARY_DIR

        if not model_dir.exists():
            logger.info("Model library directory does not exist, will use fallback models")
            TRYON_MAPPING["models"] = TRYON_FALLBACK_MODELS.copy()
            return

        # Scan for existing model images
        for gender in ["female", "male"]:
            gender_dir = model_dir / gender
            if gender_dir.exists():
                for img_file in gender_dir.glob("*.png"):
                    model_id = img_file.stem  # e.g., "female-fullbody-1"
                    GENERATED_MODEL_LIBRARY[model_id] = {
                        "gender": gender,
                        "url": f"/static/models/{gender}/{img_file.name}",
                        "local_path": str(img_file)
                    }
                    logger.debug(f"Loaded model: {model_id}")

        if GENERATED_MODEL_LIBRARY:
            logger.info(f"Loaded {len(GENERATED_MODEL_LIBRARY)} models from library")
            # Update TRYON_MAPPING with generated models
            TRYON_MAPPING["models"] = GENERATED_MODEL_LIBRARY.copy()
        else:
            logger.info("No generated models found, using fallback models")
            TRYON_MAPPING["models"] = TRYON_FALLBACK_MODELS.copy()

    async def check_apis(self) -> Dict[str, bool]:
        """Check which APIs are configured."""
        return {
            "piapi": bool(os.getenv("PIAPI_KEY")),
            "pollo": bool(os.getenv("POLLO_API_KEY")),
            "a2e": bool(os.getenv("A2E_API_KEY")),
        }

    def _generate_lookup_hash(
        self,
        tool_type: str,
        prompt: str,
        effect_prompt: str = None,
        input_image_url: str = None
    ) -> str:
        """Generate unique lookup hash for Material."""
        content = f"{tool_type}:{prompt}:{effect_prompt or ''}:{input_image_url or ''}"
        return hashlib.sha256(content.encode()).hexdigest()[:64]

    # ========================================================================
    # AI AVATAR GENERATOR
    # ========================================================================

    async def generate_ai_avatar(self, limit: int = 10):
        """
        Generate AI Avatar videos.

        Uses A2E API with pre-created characters (anchors).
        Iterates through available characters × scripts × languages.
        """
        logger.info("=" * 60)
        logger.info("AI AVATAR - Using A2E Pre-created Characters")
        logger.info("=" * 60)

        self.stats["by_tool"]["ai_avatar"] = {"success": 0, "failed": 0}
        self.local_results["ai_avatar"] = []
        count = 0
        topic_counts: Dict[str, int] = {}

        # Get available characters from A2E
        characters = await self.a2e.get_characters()
        if not characters:
            logger.error("No A2E characters available! Create characters via A2E web interface first.")
            return

        logger.info(f"Found {len(characters)} A2E characters")
        for char in characters[:3]:
            logger.info(f"  - {char.get('_id')}: {char.get('name')}")

        # Partition characters by gender (name must match face: male name on male face, female on female)
        # Names must match AVATAR_MAPPING: female avatars = female names, male = male names
        FEMALE_NAMES = [
            "女", "female", "woman", "girl",
            "怡君", "雅婷", "佳穎", "淑芬", "美玲", "雅琪", "怡萱", "欣怡", "雯婷", "筱涵",
            "小美", "小雅", "小玲", "小萱", "小婷", "小芬", "小琪", "小涵", "小敏", "小慧",
            "詩涵", "宜蓁", "心怡", "佳慧", "婉婷", "靜怡", "雅文", "思穎", "珮瑜", "曉雯",
            "yi-jun", "ya-ting", "jia-ying", "shu-fen",
        ]
        MALE_NAMES = [
            "男", "male", "man", "guy",
            "志偉", "冠宇", "宗翰", "家豪", "承恩", "柏翰", "宇軒", "俊宏", "建宏", "明哲",
            "建明", "俊傑", "志豪", "冠廷", "柏均", "彥廷", "育成", "嘉偉", "信宏", "政翰",
            "小明", "小偉", "小豪", "小杰", "小軒", "小翰", "小宏", "小凱", "小龍", "小剛",
            "zhi-wei", "guan-yu", "zong-han", "jia-hao",
        ]

        def _char_gender(char):
            name = (char.get("name") or "").lower()
            if any(kw in name for kw in FEMALE_NAMES):
                return "female"
            if any(kw in name for kw in MALE_NAMES):
                return "male"
            return "female" if hash(char.get("_id", "")) % 2 == 0 else "male"

        male_chars = [c for c in characters if _char_gender(c) == "male"]
        female_chars = [c for c in characters if _char_gender(c) == "female"]
        if not male_chars:
            male_chars = characters[: (len(characters) + 1) // 2]
        if not female_chars:
            female_chars = characters[len(male_chars):]
        logger.info(f"  Male characters: {len(male_chars)}, Female: {len(female_chars)}")

        # Most AI Avatars must be Chinese (zh-TW) - VidGo targets SMB/Taiwan market
        # Language order: zh-TW first, then en
        lang_order = ["zh-TW", "en"]

        char_index_by_gender = {"male": 0, "female": 0}

        for topic, scripts in SCRIPT_MAPPING.items():
            if self.per_topic_limit is None and count >= limit:
                break

            for script in scripts:
                if self.per_topic_limit is None and count >= limit:
                    break

                for language in lang_order:
                    topic_key = f"{topic}:{language}"
                    if not self._topic_can_generate(topic_key, topic_counts, limit, count):
                        break

                    # Use script's preferred_gender if set (e.g. nail salon → female),
                    # otherwise alternate male/female for variety
                    avatar_gender = script.get("preferred_gender") or ("female" if count % 2 == 0 else "male")
                    pool = female_chars if avatar_gender == "female" else male_chars
                    idx = char_index_by_gender[avatar_gender] % max(len(pool), 1)
                    char = pool[idx] if pool else characters[count % len(characters)]
                    char_index_by_gender[avatar_gender] += 1

                    anchor_id = char.get("_id")
                    input_image_url = char.get("video_cover")

                    script_text = script["text_zh"] if language == "zh-TW" else script["text_en"]

                    logger.info(f"[{count+1}] Character: {char.get('name')} (gender={avatar_gender}) | Topic: {topic} | Script: {script['id']} | Lang: {language}")
                    logger.info(f"  Script: {script_text[:40]}...")

                    start_time = time.time()

                    # Call A2E API with gender for voice matching
                    result = await self.a2e.generate_avatar(
                        script=script_text,
                        language=language,
                        anchor_id=anchor_id,
                        gender=avatar_gender,  # Pass gender for TTS voice matching
                        save_locally=True
                    )

                    if not result["success"]:
                        logger.error(f"  Failed: {result.get('error', 'Unknown')}")
                        self.stats["failed"] += 1
                        self.stats["by_tool"]["ai_avatar"]["failed"] += 1
                        count += 1
                        self._topic_mark_generated(topic_key, topic_counts)
                        continue

                    # Generate frontend-compatible avatar_id — cycle through 1..4
                    gender_count = sum(1 for e in self.local_results.get("ai_avatar", [])
                                      if e.get("input_params", {}).get("voice_gender") == avatar_gender)
                    frontend_avatar_id = f"{avatar_gender}-{(gender_count % 4) + 1}"  # female-1..4, male-1..4 cycling
                    
                    # Store locally - input_image_url matches the character used
                    # Ensure input_image_url is not empty (5C: avatar image consistency)
                    avatar_input_image = result.get("input_image_url") or input_image_url
                    if not avatar_input_image:
                        avatar_input_image = char.get("avatar") or char.get("video_cover") or ""
                        logger.warning("  No input_image_url for avatar, using character thumbnail")

                    local_entry = {
                        "avatar_id": anchor_id,
                        "script_id": script["id"],
                        "topic": topic,
                        "language": language,
                        "prompt": script_text,
                        "prompt_zh": script_text if language == "zh-TW" else None,
                        "prompt_en": script_text if language == "en" else None,
                        "input_image_url": avatar_input_image,
                        "result_video_url": result["video_url"],
                        "input_params": {
                            "anchor_id": anchor_id,
                            "character_name": char.get("name"),
                            "script_id": script["id"],
                            "language": language,
                            # NEW: Frontend-compatible fields
                            "avatar_id": frontend_avatar_id,
                            "voice_gender": avatar_gender
                        },
                        "generation_steps": [{
                            "step": 1,
                            "api": "a2e",
                            "action": "avatar_generation",
                            "result_url": result["video_url"],
                            "duration_ms": int((time.time() - start_time) * 1000)
                        }],
                        "generation_cost": 0.10
                    }
                    self.local_results["ai_avatar"].append(local_entry)

                    logger.info(f"  Success: {result['video_url']} (avatar_id={frontend_avatar_id}, gender={avatar_gender})")
                    self.stats["success"] += 1
                    self.stats["by_tool"]["ai_avatar"]["success"] += 1
                    count += 1
                    self._topic_mark_generated(topic_key, topic_counts)
                    await asyncio.sleep(2)

        await self._store_local_to_db("ai_avatar")

    # ========================================================================
    # BACKGROUND REMOVAL GENERATOR
    # ========================================================================

    async def generate_background_removal(self, limit: int = 10):
        """
        Generate Background Removal examples.

        Flow: Prompt → T2I → PiAPI Remove BG → Transparent PNG
        """
        logger.info("=" * 60)
        logger.info("BACKGROUND REMOVAL - T2I + Rembg")
        logger.info("=" * 60)

        self.stats["by_tool"]["background_removal"] = {"success": 0, "failed": 0}
        self.local_results["background_removal"] = []
        count = 0
        topic_counts: Dict[str, int] = {}

        for topic, topic_data in BACKGROUND_REMOVAL_MAPPING.items():
            if self.per_topic_limit is None and count >= limit:
                break

            for prompt in topic_data["prompts"]:
                if not self._topic_can_generate(topic, topic_counts, limit, count):
                    break

                logger.info(f"[{count+1}] Topic: {topic}")
                logger.info(f"  Prompt: {prompt[:50]}...")

                # Step 1: Generate source image
                logger.info("  Step 1: T2I...")
                t2i = await self.piapi.generate_image(prompt=prompt, width=1024, height=1024)

                if not t2i["success"]:
                    logger.error(f"  T2I Failed: {t2i.get('error')}")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["background_removal"]["failed"] += 1
                    count += 1
                    self._topic_mark_generated(topic, topic_counts)
                    continue

                source_url = t2i["image_url"]
                logger.info(f"  Source: {source_url}")

                # Step 2: Remove background via PiAPI
                logger.info("  Step 2: Remove BG (PiAPI)...")
                rembg_result = await self.piapi.remove_background(source_url)

                if not rembg_result["success"]:
                    logger.error(f"  Remove BG Failed: {rembg_result.get('error')}")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["background_removal"]["failed"] += 1
                    count += 1
                    self._topic_mark_generated(topic, topic_counts)
                    continue

                result_url = rembg_result["image_url"]

                # Store locally
                local_entry = {
                    "topic": topic,
                    "prompt": prompt,
                    "input_image_url": source_url,
                    "result_image_url": result_url,
                    "generation_steps": [
                        {"step": 1, "api": "piapi", "action": "t2i", "result_url": source_url},
                        {"step": 2, "api": "piapi", "action": "remove_bg", "result_url": result_url}
                    ],
                    "generation_cost": 0.005
                }
                self.local_results["background_removal"].append(local_entry)

                logger.info(f"  Result: {result_url}")
                self.stats["success"] += 1
                self.stats["by_tool"]["background_removal"]["success"] += 1
                count += 1
                self._topic_mark_generated(topic, topic_counts)
                await asyncio.sleep(2)

        await self._store_local_to_db("background_removal")

    # ========================================================================
    # ROOM REDESIGN GENERATOR
    # ========================================================================

    async def generate_room_redesign(self, limit: int = 10):
        """
        Generate Room Redesign examples.

        Combinations: Room × Style (style IDs match DESIGN_STYLES from interior API
        so frontend room+roomType+style matching works).
        Total: 4 rooms × N styles (from DESIGN_STYLES)
        """
        from app.services.interior_design_service import DESIGN_STYLES

        logger.info("=" * 60)
        logger.info("ROOM REDESIGN - Room × Style (DESIGN_STYLES ids)")
        logger.info("=" * 60)

        self.stats["by_tool"]["room_redesign"] = {"success": 0, "failed": 0}
        self.local_results["room_redesign"] = []
        count = 0
        topic_counts: Dict[str, int] = {}

        room_types = ROOM_REDESIGN_MAPPING["room_types"]
        # Use DESIGN_STYLES so stored style_id matches frontend /api/v1/interior/styles
        styles = {sid: {"name": s["name"], "prompt": s["prompt_suffix"]} for sid, s in DESIGN_STYLES.items()}

        for room_id, room_data in room_types.items():
            if self.per_topic_limit is None and count >= limit:
                break

            for style_id, style_data in styles.items():
                if not self._topic_can_generate(style_id, topic_counts, limit, count):
                    break

                logger.info(f"[{count+1}] Room: {room_data['name']} -> Style: {style_data['name']}")

                prompt = f"Photorealistic interior design of a {room_data['name'].lower()}, {style_data['prompt']}, architectural visualization, professional rendering, 8K"

                t2i = await self.piapi.generate_image(prompt=prompt)

                if not t2i["success"]:
                    logger.error(f"  Failed: {t2i.get('error')}")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["room_redesign"]["failed"] += 1
                    count += 1
                    self._topic_mark_generated(style_id, topic_counts)
                    continue

                local_entry = {
                    "topic": room_data["room_type"],  # so topic matches selectedRoomType in frontend
                    "prompt": prompt,
                    "input_image_url": room_data["url"],
                    "result_image_url": t2i["image_url"],
                    "input_params": {
                        "room_id": room_id,
                        "style_id": style_id,  # matches DESIGN_STYLES e.g. modern_minimalist, scandinavian
                        "room_type": room_data["room_type"]
                    },
                    "generation_cost": 0.005
                }
                self.local_results["room_redesign"].append(local_entry)

                logger.info(f"  Result: {t2i['image_url']}")
                self.stats["success"] += 1
                self.stats["by_tool"]["room_redesign"]["success"] += 1
                count += 1
                self._topic_mark_generated(style_id, topic_counts)
                await asyncio.sleep(2)

        await self._store_local_to_db("room_redesign")

    # ========================================================================
    # SHORT VIDEO GENERATOR
    # ========================================================================

    async def generate_short_video(self, limit: int = 10):
        """
        Generate Short Video examples.

        Flow: Prompt → T2I → I2V → Video
        
        This provides both a before image and an after video for proper
        before/after display in the frontend.

        Each motion type gets its own examples to showcase the effect.
        Prompts are bilingual (en/zh) for proper display in frontend.
        """
        logger.info("=" * 60)
        logger.info("SHORT VIDEO - T2I + I2V with Motion Types")
        logger.info("=" * 60)

        self.stats["by_tool"]["short_video"] = {"success": 0, "failed": 0}
        self.local_results["short_video"] = []
        count = 0
        topic_counts: Dict[str, int] = {}
        pollo_disabled = False  # Set True after repeated "Not enough credits" from Pollo

        # Iterate through each motion type
        for motion_id, motion_data in SHORT_VIDEO_MAPPING.items():
            if self.per_topic_limit is None and count >= limit:
                break

            motion_name = motion_data["name"]
            motion_name_zh = motion_data["name_zh"]

            for prompt_data in motion_data["prompts"]:
                if not self._topic_can_generate(motion_id, topic_counts, limit, count):
                    break

                prompt_en = prompt_data["en"]
                prompt_zh = prompt_data["zh"]

                logger.info(f"[{count+1}] Motion: {motion_name} ({motion_id})")
                logger.info(f"  Prompt (EN): {prompt_en[:50]}...")
                logger.info(f"  Prompt (ZH): {prompt_zh[:30]}...")

                # Step 1: Generate T2I image first (for before/after display)
                logger.info("  Step 1: T2I...")
                t2i = await self.piapi.generate_image(prompt=prompt_en, width=1024, height=1024)

                if not t2i["success"]:
                    logger.error(f"  T2I Failed: {t2i.get('error')}")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["short_video"]["failed"] += 1
                    count += 1
                    self._topic_mark_generated(motion_id, topic_counts)
                    continue

                source_image_url = t2i["image_url"]  # local path for storage
                remote_image_url = t2i.get("remote_url", source_image_url)  # remote URL for Pollo
                logger.info(f"  Source image: {source_image_url}")

                # Step 2: Convert T2I image to video using I2V
                # Pollo first; fallback to PiAPI Wan I2V when Pollo is out of credits
                logger.info(f"  Step 2: I2V ({'PiAPI Wan' if pollo_disabled else 'Pollo → PiAPI fallback'})...")
                result = None
                i2v_api = "pollo"
                if not pollo_disabled:
                    result = await self.pollo.generate_video(
                        prompt=prompt_en,
                        image_url=remote_image_url,
                        length=SHORT_VIDEO_LENGTH
                    )
                    if not result["success"]:
                        err = result.get("error", "")
                        if "Not enough credits" in err or "403" in err:
                            logger.warning("  Pollo credits exhausted - switching to PiAPI Wan I2V for remaining videos")
                            pollo_disabled = True
                        else:
                            logger.error(f"  Pollo I2V failed: {err}")

                if pollo_disabled or (result and not result["success"]):
                    logger.info("  Trying PiAPI Wan I2V as fallback...")
                    result = await self.piapi.image_to_video(
                        image_url=remote_image_url,
                        prompt=prompt_en
                    )
                    i2v_api = "piapi_wan"

                if not result or not result["success"]:
                    logger.error(f"  I2V Failed (both providers): {result.get('error') if result else 'No result'}")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["short_video"]["failed"] += 1
                    count += 1
                    self._topic_mark_generated(motion_id, topic_counts)
                    continue

                local_entry = {
                    "topic": motion_id,
                    "prompt": prompt_en,
                    "prompt_zh": prompt_zh,
                    "input_image_url": source_image_url,
                    "result_video_url": result["video_url"],
                    "generation_steps": [
                        {"step": 1, "api": "piapi", "action": "t2i", "result_url": source_image_url},
                        {"step": 2, "api": i2v_api, "action": "i2v", "result_url": result["video_url"]}
                    ],
                    "generation_cost": 0.12,  # T2I + I2V cost
                    "metadata": {
                        "motion": motion_id,
                        "motion_name": motion_name,
                        "motion_name_zh": motion_name_zh
                    }
                }
                self.local_results["short_video"].append(local_entry)

                logger.info(f"  Result: {result['video_url']}")
                self.stats["success"] += 1
                self.stats["by_tool"]["short_video"]["success"] += 1
                count += 1
                self._topic_mark_generated(motion_id, topic_counts)
                await asyncio.sleep(5)

        await self._store_local_to_db("short_video")

    # ========================================================================
    # PRODUCT SCENE GENERATOR
    # ========================================================================

    async def generate_product_scene(self, limit: int = 10):
        """
        Generate Product Scene examples.

        Combinations: Product × Scene
        Total: 8 products × 8 scenes = 64
        """
        logger.info("=" * 60)
        logger.info("PRODUCT SCENE - Product × Scene")
        logger.info("=" * 60)

        self.stats["by_tool"]["product_scene"] = {"success": 0, "failed": 0}
        self.local_results["product_scene"] = []
        count = 0

        products = PRODUCT_SCENE_MAPPING["products"]
        scenes = PRODUCT_SCENE_MAPPING["scenes"]
        product_image_cache = {}
        topic_counts: Dict[str, int] = {}

        for prod_id, prod_data in products.items():
            if self.per_topic_limit is None and count >= limit:
                break

            product_prompt = prod_data.get("prompt")
            product_prompt_zh = prod_data.get("prompt_zh")

            # Generate product image from prompt once per product
            if product_prompt and prod_id not in product_image_cache:
                logger.info(f"  Generating product image from prompt: {prod_data['name']}")
                t2i_product = await self.piapi.generate_image(
                    prompt=product_prompt,
                    width=1024,
                    height=1024
                )

                if not t2i_product.get("success"):
                    logger.warning(f"  Product T2I failed: {t2i_product.get('error')}, skipping product...")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["product_scene"]["failed"] += 1
                    continue

                product_image_cache[prod_id] = t2i_product.get("image_url")

            for scene_id, scene_data in scenes.items():
                if not self._topic_can_generate(scene_id, topic_counts, limit, count):
                    break

                logger.info(f"[{count+1}] Product: {prod_data['name']} -> Scene: {scene_data['name']}")

                # TRUE Product Scene: 3-step process
                # 1. Remove background from product image
                # 2. Generate new scene background with T2I
                # 3. Composite product onto scene using PIL

                product_url = product_image_cache.get(prod_id) or prod_data.get("url")
                if not product_url:
                    logger.warning("  No product image available (missing prompt and url), skipping...")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["product_scene"]["failed"] += 1
                    count += 1
                    self._topic_mark_generated(scene_id, topic_counts)
                    continue

                # Step 1: Remove product background using PiAPI
                logger.info("  Step 1: Removing product background (PiAPI)...")
                rembg_result = await self.piapi.remove_background(product_url)

                if not rembg_result["success"]:
                    logger.warning(f"  Remove BG failed: {rembg_result.get('error')}, skipping...")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["product_scene"]["failed"] += 1
                    count += 1
                    self._topic_mark_generated(scene_id, topic_counts)
                    continue

                product_no_bg_url = rembg_result["image_url"]
                logger.info(f"  Product (no bg): {product_no_bg_url}")

                # Step 2: Generate scene background image
                logger.info("  Step 2: Generating scene background...")
                scene_prompt = f"{scene_data['prompt']}, empty background for product placement, professional studio lighting, commercial photography, 8K quality"
                t2i = await self.piapi.generate_image(prompt=scene_prompt, width=1024, height=1024)

                if not t2i["success"]:
                    logger.warning(f"  Scene T2I failed: {t2i.get('error')}, skipping...")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["product_scene"]["failed"] += 1
                    count += 1
                    self._topic_mark_generated(scene_id, topic_counts)
                    continue

                scene_url = t2i["image_url"]
                logger.info(f"  Scene background: {scene_url}")

                # Step 3: Composite product onto scene using PIL
                logger.info("  Step 3: Compositing product onto scene...")
                composite_result = await self._composite_product_scene(
                    product_no_bg_url, scene_url, prod_data["name"]
                )

                if not composite_result["success"]:
                    logger.warning(f"  Compositing failed: {composite_result.get('error')}, using scene as result...")
                    result_url = scene_url
                else:
                    result_url = composite_result["image_url"]
                    logger.info(f"  Composited: {result_url}")

                generation_steps = []
                step_num = 1
                if product_prompt:
                    generation_steps.append({
                        "step": step_num,
                        "action": "t2i_product",
                        "prompt": product_prompt,
                        "result": product_url
                    })
                    step_num += 1

                generation_steps.extend([
                    {"step": step_num, "action": "remove_bg", "result": product_no_bg_url},
                    {"step": step_num + 1, "action": "t2i_scene", "result": scene_url},
                    {"step": step_num + 2, "action": "composite", "result": result_url}
                ])

                local_entry = {
                    "topic": scene_id,
                    "prompt": f"{product_prompt} | Scene: {scene_prompt}" if product_prompt else scene_prompt,
                    "prompt_zh": f"{product_prompt_zh} | 場景: {scene_data['name_zh']}" if product_prompt_zh else None,
                    "input_image_url": product_url,  # Original product image
                    "result_image_url": result_url,  # Product in new scene
                    "input_params": {
                        "product_id": prod_id,
                        "product_name": prod_data["name"],
                        "product_prompt": product_prompt,
                        "scene_type": scene_id,
                        "scene_name": scene_data["name"],
                        "scene_prompt": scene_prompt,
                        "method": "piapi_remove_bg"
                    },
                    "generation_steps": generation_steps,
                    "generation_cost": 0.015  # Rembg + T2I + composite
                }
                self.local_results["product_scene"].append(local_entry)

                logger.info(f"  Success: {result_url}")
                self.stats["success"] += 1
                self.stats["by_tool"]["product_scene"]["success"] += 1
                count += 1
                self._topic_mark_generated(scene_id, topic_counts)
                await asyncio.sleep(2)

        await self._store_local_to_db("product_scene")

    async def _composite_product_scene(
        self,
        product_no_bg_url: str,
        scene_url: str,
        product_name: str
    ) -> dict:
        """
        Composite a transparent product image onto a scene background.
        
        Args:
            product_no_bg_url: URL/path to product image with transparent background
            scene_url: URL/path to scene background image
            product_name: Name of product for logging
            
        Returns:
            {"success": True, "image_url": str} or {"success": False, "error": str}
        """
        from PIL import Image
        import requests
        from io import BytesIO
        import uuid
        from pathlib import Path
        
        try:
            # Load product image (with transparent background)
            if product_no_bg_url.startswith("/static"):
                product_path = f"/app{product_no_bg_url}"
                product_img = Image.open(product_path).convert("RGBA")
            else:
                response = requests.get(product_no_bg_url)
                product_img = Image.open(BytesIO(response.content)).convert("RGBA")
            
            # Load scene background
            if scene_url.startswith("/static"):
                scene_path = f"/app{scene_url}"
                scene_img = Image.open(scene_path).convert("RGBA")
            else:
                response = requests.get(scene_url)
                scene_img = Image.open(BytesIO(response.content)).convert("RGBA")
            
            # Resize product to fit nicely in scene (60% of scene width, centered)
            scene_w, scene_h = scene_img.size
            target_w = int(scene_w * 0.6)
            
            prod_w, prod_h = product_img.size
            scale = target_w / prod_w
            new_w = target_w
            new_h = int(prod_h * scale)
            
            # Ensure product doesn't exceed scene height
            if new_h > scene_h * 0.8:
                scale = (scene_h * 0.8) / prod_h
                new_h = int(prod_h * scale)
                new_w = int(prod_w * scale)
            
            product_resized = product_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            # Center product on scene
            x_offset = (scene_w - new_w) // 2
            y_offset = (scene_h - new_h) // 2
            
            # Composite: paste product onto scene using alpha channel
            scene_img.paste(product_resized, (x_offset, y_offset), product_resized)
            
            # Convert back to RGB for saving as PNG (no alpha)
            final_img = scene_img.convert("RGB")
            
            # Save result
            output_dir = Path("/app/static/generated")
            output_dir.mkdir(parents=True, exist_ok=True)
            filename = f"product_scene_{uuid.uuid4().hex[:8]}.png"
            output_path = output_dir / filename
            final_img.save(output_path, "PNG", quality=95)
            
            result_url = f"/static/generated/{filename}"
            logger.info(f"  [Composite] Saved: {result_url}")
            return {"success": True, "image_url": result_url}
            
        except Exception as e:
            logger.error(f"  [Composite] Error: {e}")
            return {"success": False, "error": str(e)}

    # ========================================================================
    # TRY-ON GENERATOR
    # ========================================================================

    async def generate_try_on(self, limit: int = 10):
        """
        Generate Try-On examples using REAL Virtual Try-On API.

        Uses PiAPI's Kling AI Try-On API to actually overlay clothing
        onto model photos - NOT just generating images from text.

        Combinations: Model × Clothing (with gender restrictions)
        - Dresses/skirts: female models only
        - General clothing: any model

        IMPORTANT:
        - input_image_url = CLOTHING preview (what user selects)
        - result_image_url = model wearing clothing (REAL try-on result)

        MODEL LIBRARY:
        - Uses AI-generated full-body models from /static/models/
        - Models are uploaded to file hosting for PiAPI to access
        - Falls back to T2I if Kling AI Try-On fails
        """
        logger.info("=" * 60)
        logger.info("TRY-ON - Using Kling AI Virtual Try-On API")
        logger.info("=" * 60)

        # Reload model library in case it was just generated
        self._load_model_library()

        self.stats["by_tool"]["try_on"] = {"success": 0, "failed": 0}
        self.local_results["try_on"] = []
        count = 0
        topic_counts: Dict[str, int] = {}

        models = TRYON_MAPPING["models"]
        clothing = TRYON_MAPPING["clothing"]

        if not models:
            logger.error("No models available! Run model_library first.")
            return

        logger.info(f"Using {len(models)} models from library")
        for mid, mdata in models.items():
            logger.info(f"  - {mid}: {mdata.get('url', 'N/A')[:50]}...")

        for model_id, model_data in models.items():
            if self.per_topic_limit is None and count >= limit:
                break

            for topic, clothes in clothing.items():
                if not self._topic_can_generate(topic, topic_counts, limit, count):
                    break

                for cloth in clothes:
                    if not self._topic_can_generate(topic, topic_counts, limit, count):
                        break

                    # Check gender restriction:
                    # - Male models skip female-only items
                    # - Female models can wear ALL items (no restriction)
                    gender_restriction = cloth.get("gender_restriction")
                    model_gender = model_data["gender"]
                    if model_gender == "male" and gender_restriction == "female":
                        logger.info(f"  Skipping: {cloth['name']} is female-only, model is male")
                        continue

                    logger.info(f"[{count+1}] Model: {model_id} ({model_data['gender']}) -> Clothing: {cloth['name']} (Topic: {topic})")

                    # Get model image URL (local path for base64 or PUBLIC_APP_URL)
                    model_url = model_data["url"]
                    if model_url.startswith("/static/"):
                        model_url = model_data.get("local_path") or f"/app{model_url}"

                    # Prefer local garment image so PiAPI can get our URL (PUBLIC_APP_URL) or base64
                    garment_url = await self._ensure_garment_local(cloth)

                    logger.info(f"  Model: {model_url[:60]}...")
                    logger.info(f"  Garment: {garment_url[:60]}...")

                    # Use REAL Virtual Try-On API (Kling AI via PiAPI)
                    # Model/garment sent as local path -> base64 or PUBLIC_APP_URL URL
                    tryon_result = await self.piapi.virtual_try_on(
                        model_image_url=model_url,
                        garment_image_url=garment_url
                    )

                    if not tryon_result.get("success"):
                        logger.error(f"  Try-On Failed: {tryon_result.get('error')}")
                        logger.warning("  Kling AI unavailable, skipping this combination (no fallback to preserve person identity)")
                        self.stats["failed"] += 1
                        self.stats["by_tool"]["try_on"]["failed"] += 1
                        count += 1
                        self._topic_mark_generated(topic, topic_counts)
                        continue

                    # Extract result image URL
                    result_url = tryon_result.get("image_url") or tryon_result.get("output", {}).get("image_url")
                    if not result_url:
                        # Try to get from images array
                        images = tryon_result.get("output", {}).get("images", [])
                        if images:
                            result_url = images[0].get("url") if isinstance(images[0], dict) else images[0]

                    if not result_url:
                        logger.error("  No result URL in response")
                        self.stats["failed"] += 1
                        self.stats["by_tool"]["try_on"]["failed"] += 1
                        count += 1
                        self._topic_mark_generated(topic, topic_counts)
                        continue

                    # IMPORTANT: input_image_url is the CLOTHING preview image
                    local_entry = {
                        "topic": topic,
                        "prompt": cloth["name"],
                        "prompt_zh": cloth.get("name_zh", cloth["name"]),
                        "input_image_url": cloth["image_url"],  # CLOTHING preview
                        "result_image_url": result_url,   # Model wearing clothing (REAL try-on)
                        "input_params": {
                            "model_id": model_id,
                            "model_url": model_data["url"],
                            "clothing_id": cloth["id"],
                            "clothing_type": cloth.get("clothing_type", "general"),
                            "gender_restriction": gender_restriction
                        },
                        "style_tags": [topic, cloth.get("clothing_type", "general")],
                        "generation_cost": 0.07  # Kling AI Try-On cost: $0.07 per image
                    }
                    self.local_results["try_on"].append(local_entry)

                    logger.info(f"  Success: {result_url}")
                    self.stats["success"] += 1
                    self.stats["by_tool"]["try_on"]["success"] += 1
                    count += 1
                    self._topic_mark_generated(topic, topic_counts)
                    await asyncio.sleep(2)  # Rate limiting for Kling API

        await self._store_local_to_db("try_on")

    # ========================================================================
    # PATTERN GENERATOR
    # ========================================================================

    async def generate_pattern(self, limit: int = 10):
        """
        Generate Pattern designs.

        Combinations: Style × Prompt
        Total: 5 styles × 2 prompts = 10
        """
        logger.info("=" * 60)
        logger.info("PATTERN GENERATE - Style × Prompt")
        logger.info("=" * 60)

        self.stats["by_tool"]["pattern_generate"] = {"success": 0, "failed": 0}
        self.local_results["pattern_generate"] = []
        count = 0
        topic_counts: Dict[str, int] = {}

        styles = PATTERN_GENERATE_MAPPING["styles"]

        for style_id, style_data in styles.items():
            if self.per_topic_limit is None and count >= limit:
                break

            for prompt_data in style_data["prompts"]:
                if not self._topic_can_generate(style_id, topic_counts, limit, count):
                    break

                prompt_en = prompt_data["en"]
                prompt_zh = prompt_data["zh"]

                logger.info(f"[{count+1}] Style: {style_data['name']} ({style_id})")
                logger.info(f"  Prompt: {prompt_en[:50]}...")

                full_prompt = f"Seamless pattern design, {prompt_en}, tileable, high quality, 8K"

                t2i = await self.piapi.generate_image(prompt=full_prompt, width=1024, height=1024)

                if not t2i["success"]:
                    logger.error(f"  T2I Failed: {t2i.get('error')}")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["pattern_generate"]["failed"] += 1
                    count += 1
                    self._topic_mark_generated(style_id, topic_counts)
                    continue

                local_entry = {
                    "topic": style_id,
                    "prompt": prompt_en,
                    "prompt_zh": prompt_zh,
                    "result_image_url": t2i["image_url"],
                    "input_params": {
                        "style_id": style_id,
                        "style_name": style_data["name"]
                    },
                    "style_tags": [style_id, "pattern", "seamless"],
                    "generation_cost": 0.005
                }
                self.local_results["pattern_generate"].append(local_entry)

                logger.info(f"  Success: {t2i['image_url']}")
                self.stats["success"] += 1
                self.stats["by_tool"]["pattern_generate"]["success"] += 1
                count += 1
                self._topic_mark_generated(style_id, topic_counts)
                await asyncio.sleep(1)

        await self._store_local_to_db("pattern_generate")

    # ========================================================================
    # EFFECT (STYLE TRANSFER) GENERATOR
    # ========================================================================

    async def generate_effect(self, limit: int = 10):
        """
        Generate Effect (Style Transfer) examples.

        Flow: T2I (source image) → I2I (style transfer) → Styled result
        IMPORTANT—Example correspondence: We use the EXISTING T2I result as
        input to Effect API. We do NOT generate another image with a different
        prompt. The I2I step transforms the SAME product image into the styled
        version. input_image_url = T2I output; result_image_url = I2I output.

        - Style prompts ONLY describe art style, NOT the product
        - I2I strength 0.6-0.7 preserves product identity
        """
        logger.info("=" * 60)
        logger.info("EFFECT - T2I + I2I Style Transfer")
        logger.info("=" * 60)

        self.stats["by_tool"]["effect"] = {"success": 0, "failed": 0}
        self.local_results["effect"] = []
        count = 0
        topic_counts: Dict[str, int] = {}

        source_images = EFFECT_MAPPING["source_images"]
        styles = EFFECT_MAPPING["styles"]

        for source in source_images:
            if self.per_topic_limit is None and count >= limit:
                break
            if self.per_topic_limit is not None:
                all_topics_filled = all(
                    topic_counts.get(style_id, 0) >= self.per_topic_limit
                    for style_id in styles.keys()
                )
                if all_topics_filled:
                    logger.info("All style topics reached per-topic limit, stopping effect generation.")
                    break

            # Step 1: Generate source image with T2I
            logger.info(f"[{count+1}] Source: {source['name']} ({source['name_zh']})")
            logger.info(f"  Generating source image...")

            t2i = await self.piapi.generate_image(
                prompt=source["prompt"],
                width=1024,
                height=1024
            )

            if not t2i["success"]:
                logger.error(f"  T2I Failed: {t2i.get('error')}")
                self.stats["failed"] += 1
                self.stats["by_tool"]["effect"]["failed"] += 1
                continue

            source_image_url = t2i["image_url"]
            logger.info(f"  Source image: {source_image_url}")

            # Step 2: Apply each style via I2I
            for style_id, style_data in styles.items():
                if not self._topic_can_generate(style_id, topic_counts, limit, count):
                    break

                logger.info(f"  Applying style: {style_data['name']} ({style_id})")

                # I2I style transfer - style prompt only describes art style
                i2i_result = await self.piapi.image_to_image(
                    image_url=source_image_url,
                    prompt=style_data["prompt"],
                    strength=style_data.get("strength", 0.65)
                )

                if not i2i_result.get("success"):
                    logger.error(f"  I2I Failed: {i2i_result.get('error')}")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["effect"]["failed"] += 1
                    count += 1
                    self._topic_mark_generated(style_id, topic_counts)
                    continue

                result_url = i2i_result.get("image_url") or i2i_result.get("output", {}).get("image_url")
                if not result_url:
                    images = i2i_result.get("output", {}).get("images", [])
                    if images:
                        result_url = images[0].get("url") if isinstance(images[0], dict) else images[0]

                if not result_url:
                    logger.error("  No result URL in I2I response")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["effect"]["failed"] += 1
                    count += 1
                    self._topic_mark_generated(style_id, topic_counts)
                    continue

                local_entry = {
                    "topic": style_id,
                    "prompt": f"{source['prompt']} | Style: {style_data['prompt']}",
                    "prompt_zh": f"{source['name_zh']} | 風格: {style_data['name_zh']}",
                    "effect_prompt": style_data["prompt"],
                    "input_image_url": source_image_url,  # Original product photo
                    "result_image_url": result_url,  # Styled version (same product)
                    "input_params": {
                        "source_name": source["name"],
                        "style_id": style_id,
                        "style_name": style_data["name"],
                        "strength": style_data.get("strength", 0.65)
                    },
                    "generation_steps": [
                        {"step": 1, "api": "piapi", "action": "t2i", "result_url": source_image_url},
                        {"step": 2, "api": "piapi", "action": "i2i_style", "result_url": result_url}
                    ],
                    "style_tags": [style_id, "effect", "style_transfer"],
                    "generation_cost": 0.01  # T2I + I2I cost
                }
                self.local_results["effect"].append(local_entry)

                logger.info(f"  Success: {result_url}")
                self.stats["success"] += 1
                self.stats["by_tool"]["effect"]["success"] += 1
                count += 1
                self._topic_mark_generated(style_id, topic_counts)
                await asyncio.sleep(2)

            if self.per_topic_limit is not None:
                all_topics_filled = all(
                    topic_counts.get(style_id, 0) >= self.per_topic_limit
                    for style_id in styles.keys()
                )
                if all_topics_filled:
                    logger.info("All style topics reached per-topic limit, stopping effect generation.")
                    break

        await self._store_local_to_db("effect")

    # ========================================================================
    # MODEL LIBRARY GENERATOR (NEW)
    # ========================================================================

    async def generate_model_library(self, limit: int = 6):
        """
        Generate full-body model photos for Virtual Try-On.

        This creates a library of AI-generated model photos that meet
        Kling AI Virtual Try-On requirements:
        - Full body shot (head to at least waist visible)
        - Clear visibility of upper body/torso
        - Neutral pose with arms at sides
        - Plain background
        - Simple base clothing

        These models are stored locally and reused for all try-on generations.

        Args:
            limit: Total number of models to generate (split between male/female)
        """
        logger.info("=" * 60)
        logger.info("MODEL LIBRARY - AI-Generated Full Body Models")
        logger.info("For Kling AI Virtual Try-On compatibility")
        logger.info("=" * 60)

        self.stats["by_tool"]["model_library"] = {"success": 0, "failed": 0}
        count = 0

        for gender, prompts in MODEL_GENERATION_PROMPTS.items():
            gender_dir = self.MODEL_LIBRARY_DIR / gender
            gender_dir.mkdir(parents=True, exist_ok=True)

            for i, prompt_data in enumerate(prompts): # Added enumerate to get index 'i'
                if count >= limit:
                    break

                # Save to disk with frontend-aligned naming (female-1, male-1)
                model_id_base = f"{gender}-{i+1}" # New model_id for filename and library key
                filename = f"{model_id_base}.png"
                output_path = gender_dir / filename # Use output_path for consistency

                # Skip if already exists
                if output_path.exists():
                    logger.info(f"[{count+1}] Model {model_id_base} already exists, skipping")
                    # Make sure it's in the library
                    GENERATED_MODEL_LIBRARY[model_id_base] = { # Use model_id_base here
                        "gender": gender,
                        "url": f"/static/models/{gender}/{model_id_base}.png", # Use model_id_base here
                        "local_path": str(output_path)
                    }
                    self.stats["success"] += 1 # Count as success if skipped but exists
                    count += 1
                    continue

                logger.info(f"[{count+1}] Generating: {prompt_data['description']}")
                logger.info(f"  ID: {model_id_base}")

                # Generate with PiAPI T2I - use portrait dimensions (taller than wide)
                t2i = await self.piapi.generate_image(
                    prompt=prompt_data["prompt"],
                    width=768,   # Portrait width
                    height=1152  # Portrait height (3:2 aspect ratio, taller)
                )

                if not t2i["success"]:
                    logger.error(f"  Failed: {t2i.get('error')}")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["model_library"]["failed"] += 1
                    count += 1
                    continue

                # Move/copy to model library
                source_url = t2i["image_url"]
                if source_url.startswith("/static/generated/"):
                    source_path = Path(f"/app{source_url}")
                    if source_path.exists():
                        shutil.copy(source_path, output_path)
                        logger.info(f"  Saved to: {output_path}")
                    else:
                        logger.error(f"  Source file not found: {source_path}")
                        self.stats["failed"] += 1
                        self.stats["by_tool"]["model_library"]["failed"] += 1
                        count += 1
                        continue
                else:
                    # Download from remote URL
                    try:
                        import httpx
                        async with httpx.AsyncClient() as client:
                            response = await client.get(source_url, follow_redirects=True)
                            if response.status_code == 200:
                                output_path.write_bytes(response.content)
                                logger.info(f"  Downloaded to: {output_path}")
                            else:
                                logger.error(f"  Download failed: HTTP {response.status_code}")
                                continue
                    except Exception as e:
                        logger.error(f"  Download failed: {e}")
                        continue

                # Add to library
                # Add to library
                GENERATED_MODEL_LIBRARY[model_id_base] = {
                    "gender": gender,
                    "url": f"/static/models/{gender}/{model_id_base}.png",
                    "local_path": str(output_path)
                }

                logger.info(f"  Success: Model {model_id_base} added to library")
                self.stats["success"] += 1
                self.stats["by_tool"]["model_library"]["success"] += 1
                count += 1
                await asyncio.sleep(2)

        # Update TRYON_MAPPING with new models
        if GENERATED_MODEL_LIBRARY:
            TRYON_MAPPING["models"] = GENERATED_MODEL_LIBRARY.copy()
            logger.info(f"\nModel library now has {len(GENERATED_MODEL_LIBRARY)} models")
        else:
            logger.warning("No models generated, using fallback models")
            TRYON_MAPPING["models"] = TRYON_FALLBACK_MODELS.copy()

    # ========================================================================
    # DATABASE STORAGE
    # ========================================================================

    async def _apply_watermark_to_local_image(self, image_path: str) -> Optional[str]:
        """
        Apply watermark to a local image file.
        
        Args:
            image_path: Path to the local image (e.g., /static/generated/xxx.png)
            
        Returns:
            Path to the watermarked image, or None if failed
        """
        from PIL import Image, ImageDraw, ImageFont
        import io
        from pathlib import Path
        
        try:
            # Convert static path to absolute path
            if image_path.startswith("/static/"):
                abs_path = Path(f"/app{image_path}")
            else:
                abs_path = Path(image_path)
            
            if not abs_path.exists():
                logger.warning(f"Image not found for watermarking: {abs_path}")
                return None
            
            # Read image
            with open(abs_path, "rb") as f:
                image_data = f.read()
            
            # Open and convert to RGBA
            image = Image.open(io.BytesIO(image_data)).convert("RGBA")
            width, height = image.size
            
            # Create watermark overlay
            watermark = Image.new("RGBA", image.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(watermark)
            
            watermark_text = "Vidgo AI"
            font_size = max(24, int(height / 20))  # Scale font with image size
            opacity = 0.7
            
            # Try to use a nice font
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
            except OSError:
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)
                except OSError:
                    font = ImageFont.load_default()
            
            # Get text size
            bbox = draw.textbbox((0, 0), watermark_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Position: bottom right with padding
            padding = 20
            x = width - text_width - padding
            y = height - text_height - padding
            
            # Draw shadow
            shadow_offset = 2
            shadow_color = (0, 0, 0, int(255 * opacity * 0.7))
            draw.text((x + shadow_offset, y + shadow_offset), watermark_text, font=font, fill=shadow_color)
            
            # Draw text
            text_color = (255, 255, 255, int(255 * opacity))
            draw.text((x, y), watermark_text, font=font, fill=text_color)
            
            # Composite
            watermarked = Image.alpha_composite(image, watermark)
            watermarked_rgb = watermarked.convert("RGB")
            
            # Save watermarked version with _wm suffix
            wm_path = abs_path.parent / f"{abs_path.stem}_wm{abs_path.suffix}"
            watermarked_rgb.save(wm_path, quality=95)
            
            # Return the static path
            wm_static_path = str(wm_path).replace("/app", "")
            logger.info(f"  Watermarked: {wm_static_path}")
            return wm_static_path
            
        except Exception as e:
            logger.error(f"Failed to apply watermark: {e}")
            return None

    async def _store_local_to_db(self, tool_name: str):
        """Store locally collected results to database with watermarks applied."""
        tool_type_map = {
            "ai_avatar": ToolType.AI_AVATAR,
            "background_removal": ToolType.BACKGROUND_REMOVAL,
            "room_redesign": ToolType.ROOM_REDESIGN,
            "short_video": ToolType.SHORT_VIDEO,
            "product_scene": ToolType.PRODUCT_SCENE,
            "try_on": ToolType.TRY_ON,
            "pattern_generate": ToolType.PATTERN_GENERATE,
            "effect": ToolType.EFFECT,
        }

        if tool_name not in self.local_results:
            return

        entries = self.local_results[tool_name]
        if not entries:
            logger.info(f"No entries to store for {tool_name}")
            return

        logger.info(f"Storing {len(entries)} {tool_name} entries to database...")

        async with AsyncSessionLocal() as session:
            stored_count = 0
            for entry in entries:
                lookup_hash = self._generate_lookup_hash(
                    tool_type=tool_name,
                    prompt=entry["prompt"],
                    effect_prompt=entry.get("effect_prompt"),
                    input_image_url=entry.get("input_image_url")
                )

                # Check if already exists
                existing = await session.execute(
                    select(Material).where(Material.lookup_hash == lookup_hash)
                )
                if existing.scalar_one_or_none():
                    logger.debug(f"  Already exists: {lookup_hash[:16]}...")
                    continue

                # Merge metadata into input_params if exists
                input_params = entry.get("input_params", {})
                if entry.get("metadata"):
                    input_params.update(entry["metadata"])

                # Apply watermark to result images (for image-based tools)
                result_image_url = entry.get("result_image_url")
                result_video_url = entry.get("result_video_url")
                result_watermarked_url = None
                
                # For images stored locally, apply watermark
                if result_image_url and result_image_url.startswith("/static/"):
                    result_watermarked_url = await self._apply_watermark_to_local_image(result_image_url)
                
                # For videos, use the video URL as watermarked (video watermarking is more complex)
                # In preset-only mode, videos are displayed directly without download
                if not result_watermarked_url:
                    result_watermarked_url = result_video_url or result_image_url

                material = Material(
                    lookup_hash=lookup_hash,
                    tool_type=tool_type_map[tool_name],
                    topic=entry["topic"],
                    language=entry.get("language", "en"),
                    source=MaterialSource.SEED,
                    status=MaterialStatus.APPROVED,
                    prompt=entry["prompt"],
                    prompt_zh=entry.get("prompt_zh"),
                    effect_prompt=entry.get("effect_prompt"),
                    effect_prompt_zh=entry.get("effect_prompt_zh"),
                    input_image_url=entry.get("input_image_url"),
                    input_params=input_params,
                    generation_steps=entry.get("generation_steps", []),
                    generation_cost_usd=entry.get("generation_cost", 0),
                    result_image_url=result_image_url,
                    result_video_url=result_video_url,
                    result_watermarked_url=result_watermarked_url,
                    tags=entry.get("style_tags", []),
                    quality_score=0.9,
                    is_featured=True,
                    is_active=True
                )
                session.add(material)
                stored_count += 1

            await session.commit()
            logger.info(f"  Stored {stored_count} new entries")

        # Clear local results after storing
        self.local_results[tool_name] = []

    # ========================================================================
    # MAIN ENTRY
    # ========================================================================

    async def run(
        self,
        tool: Optional[str] = None,
        limit: int = 10,
        dry_run: bool = False,
        per_topic_limit: Optional[int] = None
    ):
        """Run pre-generation pipeline."""
        logger.info("=" * 60)
        logger.info("VidGo Main Pre-generation Pipeline")
        logger.info("=" * 60)
        self.per_topic_limit = per_topic_limit

        # Check APIs
        api_status = await self.check_apis()
        logger.info(f"API Status: {api_status}")

        if dry_run:
            logger.info("[DRY RUN] Would generate materials but not calling APIs")
            logger.info("Available tools:")
            for t in ["ai_avatar", "background_removal", "room_redesign",
                      "short_video", "product_scene", "try_on", "pattern_generate",
                      "effect", "model_library"]:
                logger.info(f"  - {t}")
            logger.info("\nModel Library Status:")
            logger.info(f"  Generated models: {len(GENERATED_MODEL_LIBRARY)}")
            logger.info(f"  Using fallback: {len(GENERATED_MODEL_LIBRARY) == 0}")
            return

        # Ensure temp directory
        ensure_temp_dir()

        # Tool mapping
        tools = {
            "model_library": self.generate_model_library,  # Run first to generate models
            "ai_avatar": self.generate_ai_avatar,
            "background_removal": self.generate_background_removal,
            "room_redesign": self.generate_room_redesign,
            "short_video": self.generate_short_video,
            "product_scene": self.generate_product_scene,
            "try_on": self.generate_try_on,
            "pattern_generate": self.generate_pattern,
            "effect": self.generate_effect,
        }

        if tool:
            if tool in tools:
                # Special handling: if running try_on, ensure model library exists first
                if tool == "try_on" and len(GENERATED_MODEL_LIBRARY) == 0:
                    logger.info("No model library found, generating models first...")
                    await self.generate_model_library(limit=6)

                await tools[tool](limit=limit)
            else:
                logger.error(f"Unknown tool: {tool}")
                logger.info(f"Available tools: {list(tools.keys())}")
        else:
            # Run all tools (model_library first, then others)
            # Generate model library first so try_on can use it
            await self.generate_model_library(limit=6)

            for name, func in tools.items():
                if name == "model_library":
                    continue  # Already ran
                try:
                    tool_limit = TOOL_LIMITS.get(name, limit)
                    await func(limit=tool_limit)
                except Exception as e:
                    logger.error(f"Error in {name}: {e}")

        # Cleanup temp
        cleanup_temp_dir()

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Success: {self.stats['success']}")
        logger.info(f"Total Failed: {self.stats['failed']}")
        for tool_name, tool_stats in self.stats["by_tool"].items():
            logger.info(f"  {tool_name}: {tool_stats['success']} success, {tool_stats['failed']} failed")


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(
        description="VidGo Main Pre-generation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m scripts.main_pregenerate --tool model_library --limit 6
    python -m scripts.main_pregenerate --tool try_on --limit 50
    python -m scripts.main_pregenerate --tool ai_avatar --limit 10
    python -m scripts.main_pregenerate --all --limit 20
    python -m scripts.main_pregenerate --dry-run

Available tools:
    model_library      - Generate full-body model photos for try-on
    ai_avatar          - AI Avatar videos (avatar × script × language)
    background_removal - Background removal (T2I → PiAPI remove_bg)
    room_redesign      - Room redesign (room × style)
    short_video        - Short videos (Pollo T2V)
    product_scene      - Product scenes (product × scene)
    try_on             - Virtual try-on (model × clothing) - uses model_library
    pattern_generate   - Pattern designs (style × prompt)
    effect             - Style transfer (T2I → I2I artistic style)

Workflow for Virtual Try-On:
    1. First run: python -m scripts.main_pregenerate --tool model_library
       This generates AI full-body model photos that meet Kling AI requirements.

    2. Then run: python -m scripts.main_pregenerate --tool try_on
       This uses the generated models for real virtual try-on.

    Note: Running --tool try_on without model_library will auto-generate models first.
        """
    )
    parser.add_argument(
        "--tool",
        type=str,
        help="Specific tool to generate (see list above)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max materials per tool (total) when --per-topic-limit is not set (default: 10)"
    )
    parser.add_argument(
        "--per-topic-limit",
        type=int,
        default=None,
        help="Max materials per topic (overrides --limit behavior for topic-based tools)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without calling APIs"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate all tools"
    )

    args = parser.parse_args()

    generator = VidGoPreGenerator()
    await generator.run(
        tool=args.tool if not args.all else None,
        limit=args.limit,
        dry_run=args.dry_run,
        per_topic_limit=args.per_topic_limit
    )


if __name__ == "__main__":
    asyncio.run(main())
