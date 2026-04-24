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
from app.services.gcs_storage_service import GCSStorageService

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
# Cost-optimized limits: fewer demos for expensive tools, more for cheap ones.
# Cheap tools (T2I/I2I only, ~$0.005-0.01): higher counts
# Medium tools (Kling/Interior, ~$0.05): moderate counts
# Expensive tools (I2V/A2E, ~$0.05-0.30): minimal counts
TOOL_LIMITS = {
    "background_removal": 15,  # 1 API call each (RemBG), cheap → 5 topics × 3
    "effect": 15,              # 1 API call each (I2I), cheap → 3 sources × 5 styles
    "product_scene": 18,       # 1 API call (RemBG) + local composite → 6 products × 3 scenes
    "pattern_generate": 10,    # 1 API call each (T2I only), cheapest → 5 styles × 2
    "room_redesign": 20,       # 1 API call each (I2I), cheap → 4 rooms × 5 styles
    "try_on": 12,              # Kling API, medium cost → 3 models × 4 clothing
    "short_video": 8,          # I2V API, expensive → 2 per topic × 4 topics
    "ai_avatar": 8,            # A2E API, most expensive → 2 per category × 4 categories
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
        "url": "https://images.unsplash.com/photo-1615262239828-a4d49e6503ea?w=512&fit=crop&crop=faces"
    },
    "female-2": {
        "prompt": "Professional portrait of a Chinese woman in her early 30s, elegant makeup, warm expression, soft lighting, headshot, Asian face",
        "gender": "female",
        "name_zh": "雅婷",
        "name_en": "Ya-Ting",
        "url": "https://images.unsplash.com/photo-1615262239126-1931bdb03182?w=512&fit=crop&crop=faces"
    },
    "female-3": {
        "prompt": "Professional portrait of a young Chinese woman, business blazer, approachable smile, corporate headshot, Asian face",
        "gender": "female",
        "name_zh": "佳穎",
        "name_en": "Jia-Ying",
        "url": "https://images.unsplash.com/photo-1566589430181-a51c280be4b1?w=512&fit=crop&crop=faces"
    },
    "female-4": {
        "prompt": "Professional portrait of a Taiwanese woman, trendy style, friendly expression, modern headshot, Chinese face",
        "gender": "female",
        "name_zh": "淑芬",
        "name_en": "Shu-Fen",
        "url": "https://images.unsplash.com/photo-1614387256720-5b994a2bb8e5?w=512&fit=crop&crop=faces"
    },
    "male-1": {
        "prompt": "Professional portrait of an Asian man, plaid shirt, calm expression, studio portrait, Chinese face",
        "gender": "male",
        "name_zh": "志偉",
        "name_en": "Zhi-Wei",
        "url": "https://images.unsplash.com/photo-1681097561932-36d0df02b379?w=512&fit=crop&crop=faces"
    },
    "male-2": {
        "prompt": "Professional portrait of a Chinese man in his 30s, business suit, trustworthy smile, corporate headshot, Asian face",
        "gender": "male",
        "name_zh": "冠宇",
        "name_en": "Guan-Yu",
        "url": "https://images.unsplash.com/photo-1608908271310-57a24a9447db?w=512&fit=crop&crop=faces"
    },
    "male-3": {
        "prompt": "Professional portrait of a young Chinese man, friendly smile, casual professional headshot, Asian face",
        "gender": "male",
        "name_zh": "宗翰",
        "name_en": "Zong-Han",
        "url": "https://images.unsplash.com/photo-1633177188754-980c2a6b6266?w=512&fit=crop&crop=faces"
    },
    "male-4": {
        "prompt": "Professional portrait of a mature Chinese man, confident expression, business headshot, Asian face",
        "gender": "male",
        "name_zh": "家豪",
        "name_en": "Jia-Hao",
        "url": "https://images.unsplash.com/photo-1727605507453-dfe1e74abfbc?w=512&fit=crop&crop=faces"
    }
}

# Script definitions - DECOUPLED from avatars
# Organized by topic (matching topic_registry.py)
# IMPORTANT: Scripts must CLEARLY sell a PRODUCT (NOT service, NOT luxury)
# Focus: Citizen life products — everyday Taiwanese/Chinese consumer goods
# Most avatars should be Chinese (zh-TW) - VidGo targets Taiwan/SMB market
# 4 categories × 3 scripts = 12 scripts covering diverse daily life products:
# thermos, shampoo, tea, rice cooker, toothbrush, desk lamp, charger, detergent, baby bottle, face mask, earbuds, dried mango
# Generated by: scripts/generate_citizen_life_prompts.py
SCRIPT_MAPPING = {
    # Each category shows a DIFFERENT promotional technique for citizen life products
    # spokesperson: Origin story / brand storytelling (builds trust)
    "spokesperson": [
        {
            "id": "spokesperson-1",
            "text_en": "My father was an ironworker. He carried a cheap thermos every day and it always leaked. That is why I spent two years developing this vacuum bottle—double-wall stainless steel, keeps drinks hot for 12 hours. We have sold over 8000 since last year. Only 599. Try it risk-free with our 30-day money-back guarantee!",
            "text_zh": "我爸是做鐵工的，每天帶一個便宜保溫瓶，總是會漏水。所以我花了兩年研發這款真空保溫瓶——雙層不鏽鋼，保溫12小時。去年到現在賣超過8000個，只要599元。30天不滿意全額退費，放心試！"
        },
        {
            "id": "spokesperson-2",
            "preferred_gender": "female",  # Herbal shampoo / grandmother's recipe → female avatar
            "text_en": "My grandmother used to wash her hair with natural herbs from the mountains. At 80, she still had thick, beautiful hair. I turned her recipe into this shampoo—no silicone, no sulfate, just 12 kinds of herbal extracts. Over 3000 customers have switched to us this year. 399 per bottle. Your hair will thank you!",
            "text_zh": "阿嬤以前都用山上採的天然草本洗頭，80歲頭髮還是又黑又亮。我把她的配方做成了這瓶洗髮精——無矽靈、無硫酸鹽，12種草本精華。今年已經有超過3000位客人轉用。每瓶399元，你的頭髮會感謝你！"
        },
        {
            "id": "spokesperson-3",
            "preferred_gender": "male",  # Alishan tea farmer / heritage → male avatar
            "text_en": "My family has been growing tea in Alishan for three generations. Every spring I hand-pick the leaves at dawn when the dew is still fresh. This oolong goes through five stages of roasting over 72 hours. One sip and you will taste the mountain. 150 grams for 590. We ship same-day, vacuum-sealed for freshness!",
            "text_zh": "我家在阿里山種茶已經三代了。每年春天我天亮就上山手採，趁露水還在的時候。這款烏龍經過72小時五道烘焙。喝一口，你就能嚐到山的味道。150克只要590元，當天出貨、真空包裝鎖住鮮味！"
        }
    ],
    # product_intro: Social proof / before-after / demo technique (shows results)
    "product_intro": [
        {
            "id": "product-intro-1",
            "preferred_gender": "female",  # Rice cooker cooking demo → female avatar
            "text_en": "Check this out—I just put in rice, water, and pressed one button. 25 minutes later? Perfect fluffy rice, every single time. This smart cooker has 8 cooking modes, a non-stick inner pot, and a 24-hour timer. Over 1500 five-star reviews online. Only 1290 for restaurant-quality rice at home. Free shipping this week!",
            "text_zh": "你看——我只要放米、加水、按一個按鈕，25分鐘後就是粒粒分明的完美白飯，每次都一樣。這台智慧電子鍋有8種模式、不沾內鍋、24小時預約。網路上超過1500則五星評價。只要1290元，在家就能煮出餐廳等級的飯。本週免運費！"
        },
        {
            "id": "product-intro-2",
            "preferred_gender": "male",  # Toothbrush / dentist story → male avatar
            "text_en": "I used to brush for 30 seconds and call it done. Then my dentist said I had three cavities. I switched to this sonic toothbrush—40000 vibrations per minute, 2-minute smart timer, 30-day battery life. Six months later, zero cavities. 799 with two extra brush heads. Your teeth will thank you!",
            "text_zh": "以前我刷牙30秒就覺得好了，結果牙醫說我有三顆蛀牙。換了這支音波牙刷——每分鐘40000次震動、2分鐘智慧計時、充一次電用30天。半年後零蛀牙。799元附兩個替換刷頭，你的牙齒會感謝你！"
        },
        {
            "id": "product-intro-3",
            "text_en": "I compared 20 desk lamps before choosing this one. Zero flicker, adjustable color temperature from warm to cool, and a built-in USB charging port. My eyes stopped hurting after late-night work. 690 and it comes with a 2-year warranty. Over 800 students and remote workers recommend it. Light up your workspace!",
            "text_zh": "我比較了20款檯燈才選了這一台。零頻閃、色溫可調從暖光到白光、還有USB充電孔。加班到深夜眼睛不再痠痛。690元含兩年保固。超過800位學生和遠距工作者推薦。照亮你的工作空間！"
        }
    ],
    # customer_service: Trust-building / guarantee (reduces purchase anxiety)
    "customer_service": [
        {
            "id": "customer-service-1",
            "preferred_gender": "male",  # Charging cable / tech → male avatar
            "text_en": "Worried about buying a charging cable online? I understand. That is why every cable we sell goes through a 5000-bend test. If it breaks within one year, we replace it for free—no questions asked. Just message us on LINE with your order number. Over 10000 cables sold, replacement rate under 0.5 percent. 349 for a set of two!",
            "text_zh": "擔心網路買充電線踩雷？我懂。所以我們每條線都通過5000次彎折測試。一年內斷裂免費換新——不問原因。LINE傳訂單號碼就好。賣出超過10000條，換貨率不到0.5%。兩條一組只要349元！"
        },
        {
            "id": "customer-service-2",
            "preferred_gender": "female",  # Laundry detergent / baby safety → female avatar
            "text_en": "A lot of moms ask me: is this laundry detergent really safe for baby clothes? Let me answer. It is 99 percent plant-derived, dermatologist-tested, and free of fluorescent agents. We even have the SGS test report on our website. 2000ml for only 299. Perfect for the whole family. Questions? Message us anytime on LINE—we reply within 2 hours!",
            "text_zh": "很多媽媽問我：這瓶洗衣精洗寶寶衣服真的安全嗎？讓我來回答。99%植物萃取、皮膚科醫師測試、無螢光劑。SGS檢驗報告就在我們網站上。2000ml只要299元，全家都能用。有問題隨時LINE我們，2小時內回覆！"
        },
        {
            "id": "customer-service-3",
            "preferred_gender": "female",  # Baby bottle / new parent guidance → female avatar
            "text_en": "New parents, I know you have questions about our baby bottle. Here are the top three: Is it BPA-free? Yes, 100 percent. Does the anti-colic valve really work? 92 percent of parents say their baby had less gas. Can I sterilize it? Yes, it is heat-resistant up to 180 degrees. 490 per bottle. Free return within 7 days if baby does not like it!",
            "text_zh": "新手爸媽，我知道你們對奶瓶有很多問題。最常問的三個：不含BPA嗎？是的，100%。防脹氣閥真的有用嗎？92%的家長說寶寶脹氣減少了。可以消毒嗎？耐熱180度沒問題。每支490元。7天內寶寶不適應可免費退貨！"
        }
    ],
    # social_media: Interactive / viral hooks / emotional (drives shares)
    "social_media": [
        {
            "id": "social-media-1",
            "preferred_gender": "female",  # Face mask / beauty deal → female avatar
            "text_en": "Save this video right now! This is our best-selling hydrating face mask—normally 499 for a box of 10. But today only, buy one box get one free. That is 20 masks for 499! Last time we did this, we sold out in 3 hours. Follow us and turn on notifications so you never miss a deal. Link in bio!",
            "text_zh": "馬上存下這支影片！這是我們最暢銷的保濕面膜——原價一盒10片499元。但只限今天，買一送一。20片只要499！上次辦這個活動3小時就賣完了。追蹤我們開啟通知才不會錯過。連結在自介！"
        },
        {
            "id": "social-media-2",
            "preferred_gender": "male",  # Wireless earbuds / tech flash sale → male avatar
            "text_en": "Stop scrolling—you need to hear this. These wireless earbuds have 30-hour battery life, noise cancellation, and they are waterproof. The best part? Only 890. I have been using them for 6 months at the gym, on the bus, even in the rain. Flash sale ends tonight at midnight. Tap the link now before they sell out!",
            "text_zh": "先別滑了——你一定要聽聽這個。這副無線耳機續航30小時、有降噪、還防水。最棒的是只要890元。我已經用了6個月，健身房、公車上、甚至淋雨都沒問題。限時特賣今晚12點結束，趕快點連結，賣完就沒了！"
        },
        {
            "id": "social-media-3",
            "text_en": "I gave this dried mango to 10 coworkers without telling them the price. Every single one guessed it costs over 300. The real price? 169 for a big bag. Made in Pingtung from Irwin mangoes, no added sugar. Tag someone who loves mango! Buy 3 bags and get free shipping. Best office snack ever!",
            "text_zh": "我把這包芒果乾給10個同事吃，沒說價錢。每個人都猜超過300元。真正的價格？大包裝只要169元。屏東愛文芒果製作、無添加糖。標記一個愛吃芒果的朋友！買三包免運。辦公室最佳零嘴！"
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
            "url": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-1.png",
            "prompt": "Studio product photo of a clear cup of bubble milk tea with tapioca pearls, centered, clean white background, soft shadows, commercial photography, 8K",
            "prompt_zh": "棚拍產品照：透明杯珍珠奶茶與黑色珍珠，置中構圖，乾淨白底，柔和陰影，商業攝影，8K"
        },
        "product-2": {
            "name": "Canvas Tote Bag",
            "name_zh": "帆布托特包",
            "url": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-2.png",
            "prompt": "Studio product photo of a natural canvas tote bag with minimalist design, standing upright, clean white background, soft shadows, commercial photography, 8K",
            "prompt_zh": "棚拍產品照：自然色帆布托特包，簡約設計，直立擺放，乾淨白底，柔和陰影，商業攝影，8K"
        },
        "product-3": {
            "name": "Handmade Jewelry",
            "name_zh": "手工飾品",
            "url": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-3.png",
            "prompt": "Studio product photo of handmade silver earrings and bracelet set on velvet display, centered, clean white background, jewelry photography, 8K",
            "prompt_zh": "棚拍產品照：手工銀耳環與手鍊組合，絨布展示台，置中構圖，乾淨白底，飾品攝影，8K"
        },
        "product-4": {
            "name": "Skincare Serum",
            "name_zh": "保養精華液",
            "url": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-4.png",
            "prompt": "Studio product photo of a glass skincare serum bottle with dropper, clean cosmetics product style, white background, soft glow, 8K",
            "prompt_zh": "棚拍產品照：玻璃滴管保養精華液瓶，清新保養品風格，乾淨白底，柔光氛圍，8K"
        },
        "product-5": {
            "name": "Coffee Beans",
            "name_zh": "咖啡豆",
            "url": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-5.png",
            "prompt": "Studio product photo of a kraft paper bag of roasted coffee beans with some beans scattered around, centered, clean white background, food product photography, 8K",
            "prompt_zh": "棚拍產品照：牛皮紙袋裝烘焙咖啡豆，周圍散落數顆咖啡豆，置中構圖，乾淨白底，食品攝影，8K"
        },
        "product-6": {
            "name": "Espresso Machine",
            "name_zh": "義式咖啡機",
            "url": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-6.png",
            "prompt": "Studio product photo of a compact stainless steel espresso machine, front angle, clean white background, professional appliance advertising, 8K",
            "prompt_zh": "棚拍產品照：小型不鏽鋼義式咖啡機，正面角度，乾淨白底，家電廣告風格，8K"
        },
        "product-7": {
            "name": "Handmade Candle",
            "name_zh": "手工蠟燭",
            "url": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-7.png",
            "prompt": "Studio product photo of a handmade soy wax candle in glass jar, centered, clean white background, cozy product advertising, 8K",
            "prompt_zh": "棚拍產品照：玻璃罐手工大豆蠟燭，置中構圖，乾淨白底，溫馨產品廣告風格，8K"
        },
        "product-8": {
            "name": "Gift Box Set",
            "name_zh": "禮盒組合",
            "url": "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-8.png",
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
        },
        "spring": {
            "name": "Spring Sale",
            "name_zh": "春季特賣",
            "prompt": "fresh cherry blossom petals, bright spring sunlight, pastel pink and green, spring campaign"
        },
        "valentines": {
            "name": "Valentine's Day",
            "name_zh": "情人節",
            "prompt": "romantic rose petals, warm candlelight, red and pink hearts, satin ribbons, valentine campaign"
        },
        "black_friday": {
            "name": "Black Friday",
            "name_zh": "黑色星期五",
            "prompt": "sleek black surface, dramatic spotlight, neon sale tags, black and gold, retail promotion"
        },
        "christmas": {
            "name": "Christmas",
            "name_zh": "聖誕節",
            "prompt": "christmas pine branches, golden fairy lights, red ornaments, snow frost, warm holiday"
        },
        "new_year": {
            "name": "New Year",
            "name_zh": "新年",
            "prompt": "gold confetti, champagne, sparkling lights, black and gold, new year celebration"
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

_GCS_TRYON = "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon"

TRYON_MAPPING = {
    # Six frozen, human-reviewed full-body model photos (3 female + 3 male).
    # These URLs are stable — kept in sync with
    # backend/app/api/v1/tools.py TRYON_MODELS and the frontend preview list.
    "models": {
        "female-1": {"gender": "female", "url": f"{_GCS_TRYON}/models/female-1.png"},
        "female-2": {"gender": "female", "url": f"{_GCS_TRYON}/models/female-2.png"},
        "female-3": {"gender": "female", "url": f"{_GCS_TRYON}/models/female-3.png"},
        "male-1":   {"gender": "male",   "url": f"{_GCS_TRYON}/models/male-1.png"},
        "male-2":   {"gender": "male",   "url": f"{_GCS_TRYON}/models/male-2.png"},
        "male-3":   {"gender": "male",   "url": f"{_GCS_TRYON}/models/male-3.png"},
    },
    "clothing": {
        "tshirt": [
            {
                "id": "garment-tshirt",
                "name": "Plain White T-Shirt",
                "name_zh": "素色白T恤",
                "prompt": "plain white cotton crew neck t-shirt",
                "clothing_type": "general",
                "image_url": f"{_GCS_TRYON}/garments/garment-tshirt.png",
                "gender_restriction": None,
            },
        ],
        "dress": [
            {
                "id": "garment-dress",
                "name": "Floral Midi Dress",
                "name_zh": "花卉洋裝",
                "prompt": "floral summer midi dress",
                "clothing_type": "dress",
                "image_url": f"{_GCS_TRYON}/garments/garment-dress.png",
                "gender_restriction": "female",
            },
        ],
        "jacket": [
            {
                "id": "garment-jacket",
                "name": "Denim Jacket",
                "name_zh": "丹寧外套",
                "prompt": "blue denim casual jacket",
                "clothing_type": "general",
                "image_url": f"{_GCS_TRYON}/garments/garment-jacket.png",
                "gender_restriction": None,
            },
        ],
        "blouse": [
            {
                "id": "garment-blouse",
                "name": "Silk Blouse",
                "name_zh": "絲質襯衫",
                "prompt": "soft pink silk button-up blouse",
                "clothing_type": "general",
                "image_url": f"{_GCS_TRYON}/garments/garment-blouse.png",
                "gender_restriction": "female",
            },
        ],
        "sweater": [
            {
                "id": "garment-sweater",
                "name": "Knit Sweater",
                "name_zh": "針織毛衣",
                "prompt": "beige knit crew neck sweater",
                "clothing_type": "general",
                "image_url": f"{_GCS_TRYON}/garments/garment-sweater.png",
                "gender_restriction": None,
            },
        ],
        "coat": [
            {
                "id": "garment-coat",
                "name": "Trench Coat",
                "name_zh": "風衣外套",
                "prompt": "classic camel wool trench coat",
                "clothing_type": "general",
                "image_url": f"{_GCS_TRYON}/garments/garment-coat.png",
                "gender_restriction": None,
            },
        ],
    },
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
        },
        "3d": {
            "name": "3D",
            "name_zh": "3D圖案",
            "prompts": [
                {
                    "en": "3D embossed pattern for gift box and bakery packaging, raised geometric shapes, metallic finish, polished small-business brand",
                    "zh": "禮盒與烘焙包裝用3D浮雕圖案，凸起幾何形狀，金屬光澤，精緻小品牌風格"
                },
                {
                    "en": "3D isometric pattern for tech product branding, cubes and blocks, modern digital aesthetic",
                    "zh": "科技產品品牌用3D等角圖案，立方體與方塊，現代數位美學"
                }
            ]
        },
        "interior": {
            "name": "Interior",
            "name_zh": "室內裝飾圖案",
            "prompts": [
                {
                    "en": "Wallpaper pattern for cafe and restaurant interior, botanical leaves, earthy tones, cozy atmosphere",
                    "zh": "咖啡廳與餐廳室內壁紙圖案，植物葉片，大地色系，溫馨氛圍"
                },
                {
                    "en": "Tile pattern for bakery and dessert shop floor, geometric mosaic, pastel colors, vintage charm",
                    "zh": "烘焙與甜點店地板磁磚圖案，幾何馬賽克，粉彩色系，復古魅力"
                }
            ]
        },
        "mockup": {
            "name": "Mockup",
            "name_zh": "產品展示圖案",
            "prompts": [
                {
                    "en": "Product packaging mockup pattern for gift box and shopping bag, elegant brand identity, clean design",
                    "zh": "禮盒與購物袋產品包裝展示圖案，優雅品牌識別，乾淨設計"
                },
                {
                    "en": "Label and sticker mockup pattern for food and beverage products, round and rectangular shapes, craft style",
                    "zh": "食品與飲料產品標籤貼紙展示圖案，圓形與矩形，手作風格"
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
_GCS_PRODUCTS = "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products"

EFFECT_MAPPING = {
    # Source images reuse the 8 frozen curated product photos so every effect
    # pregen run starts from the same input — only the style I2I is random.
    "source_images": [
        {"product_id": "product-1", "name": "Bubble Tea",       "name_zh": "珍珠奶茶",  "url": f"{_GCS_PRODUCTS}/product-1.png", "topic": "drinks"},
        {"product_id": "product-2", "name": "Canvas Tote Bag",  "name_zh": "帆布托特包","url": f"{_GCS_PRODUCTS}/product-2.png", "topic": "accessories"},
        {"product_id": "product-3", "name": "Handmade Jewelry", "name_zh": "手工飾品",  "url": f"{_GCS_PRODUCTS}/product-3.png", "topic": "handmade"},
        {"product_id": "product-4", "name": "Skincare Serum",   "name_zh": "保養精華液","url": f"{_GCS_PRODUCTS}/product-4.png", "topic": "cosmetics"},
        {"product_id": "product-5", "name": "Coffee Beans",     "name_zh": "咖啡豆",    "url": f"{_GCS_PRODUCTS}/product-5.png", "topic": "food"},
        {"product_id": "product-6", "name": "Espresso Machine", "name_zh": "義式咖啡機","url": f"{_GCS_PRODUCTS}/product-6.png", "topic": "equipment"},
        {"product_id": "product-7", "name": "Handmade Candle",  "name_zh": "手工蠟燭",  "url": f"{_GCS_PRODUCTS}/product-7.png", "topic": "handmade"},
        {"product_id": "product-8", "name": "Gift Box Set",     "name_zh": "禮盒組合",  "url": f"{_GCS_PRODUCTS}/product-8.png", "topic": "gifts"},
    ],
    # Style IDs must match backend/app/services/effects_service.py VIDGO_STYLES
    "styles": {
        "anime":         {"name": "Anime",          "name_zh": "動漫風格", "prompt": "anime style illustration for social media and ads",                            "strength": 0.65},
        "ghibli":        {"name": "Ghibli",         "name_zh": "吉卜力風格", "prompt": "studio ghibli anime style for menu and cafe branding, hayao miyazaki",       "strength": 0.65},
        "cartoon":       {"name": "Cartoon",        "name_zh": "卡通風格", "prompt": "cartoon pixar 3d style for product ads and flyers",                           "strength": 0.60},
        "clay":          {"name": "Clay",           "name_zh": "黏土動畫", "prompt": "claymation stop motion clay style for product and food ads",                  "strength": 0.65},
        "cute_anime":    {"name": "Cute Anime",     "name_zh": "可愛動漫", "prompt": "cute kawaii anime style for social media and shop ads",                        "strength": 0.65},
        "oil_painting":  {"name": "Oil Painting",   "name_zh": "油畫風格", "prompt": "oil painting artistic style for brand and restaurant marketing",               "strength": 0.70},
        "watercolor":    {"name": "Watercolor",     "name_zh": "水彩風格", "prompt": "watercolor soft style for menu design and boutique branding",                  "strength": 0.65},
        "cyberpunk":     {"name": "Cyberpunk",      "name_zh": "賽博朋克", "prompt": "cyberpunk neon futuristic style for tech product ads",                         "strength": 0.65},
        "realistic":     {"name": "Realistic",      "name_zh": "寫實風格", "prompt": "realistic photorealistic style for product and food ads",                      "strength": 0.55},
        "cinematic":     {"name": "Cinematic",      "name_zh": "電影質感", "prompt": "cinematic movie style for brand and product video ads",                        "strength": 0.60},
        "anime_classic": {"name": "Anime Classic",  "name_zh": "經典動漫", "prompt": "classic anime style for menu and product marketing",                           "strength": 0.65},
    },
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
        # GCS storage — all Material URLs must resolve through here so nothing
        # stored in the DB depends on ephemeral Cloud Run filesystem or PiAPI
        # temp CDN URLs (14-day expiry).
        self.gcs = GCSStorageService()
        if not self.gcs.enabled:
            logger.warning(
                "GCS_BUCKET not set — Material URLs will remain as local/temp URLs. "
                "Set GCS_BUCKET env var before running pre-generation against production."
            )
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
        """No-op: TRYON_MAPPING["models"] already contains the frozen curated
        GCS URLs (see module-level TRYON_MAPPING). We no longer scan /static/
        or fall back to TRYON_FALLBACK_MODELS — that was the source of drift
        between pregen runs.
        """
        logger.info(
            "Using %d frozen curated try-on models from TRYON_MAPPING",
            len(TRYON_MAPPING.get("models", {})),
        )

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
        input_image_url: str = None,
        extra_context: str = "",
    ) -> str:
        """Generate unique lookup hash for Material.

        `extra_context` lets callers add tool-specific disambiguators that
        aren't captured by prompt/effect_prompt/input_image_url alone.
        For try_on this is the model_id — without it, two rows with the
        same clothing but different models collide on the same hash and
        get deduped, which is why regen produced only 4 try_on rows all
        for female-1 instead of the expected N models × M clothings.
        """
        content = (
            f"{tool_type}:{prompt}:{effect_prompt or ''}:"
            f"{input_image_url or ''}:{extra_context}"
        )
        return hashlib.sha256(content.encode()).hexdigest()[:64]

    # ========================================================================
    # AI AVATAR GENERATOR
    # ========================================================================

    async def generate_ai_avatar(self, limit: int = 10):
        """
        Generate AI Avatar videos using PiAPI Kling Avatar (F-017 fix).

        Previously used A2E with pre-created characters (anchor_id), but A2E's
        free-tier API returns HTTP 403 — characters cannot be listed without a
        Pro/Max subscription. Switched to PiAPI's Kling Avatar via the existing
        PiAPIProvider, which:
          1. Generates speech from the script via F5-TTS
          2. Sends portrait image + audio to Kling Avatar
          3. Returns a lip-synced talking-head video

        Source portraits are generated on-the-fly via PiAPI T2I (4 portraits,
        2 female + 2 male) and uploaded to GCS so Kling can fetch them.
        Frontend avatar_id mapping (female-1..2, male-1..2) is preserved.
        """
        logger.info("=" * 60)
        logger.info("AI AVATAR - Using PiAPI Kling Avatar (F-017 fix)")
        logger.info("=" * 60)

        self.stats["by_tool"]["ai_avatar"] = {"success": 0, "failed": 0}
        self.local_results["ai_avatar"] = []
        count = 0
        topic_counts: Dict[str, int] = {}

        # ─────────────────────────────────────────────────────────────────────
        # Step 1: Use dedicated head-and-shoulders avatar portraits from GCS.
        # These are separate from the full-body try-on models because Kling
        # Avatar's face detector rejects full-body input with "failed to
        # freeze point" — it needs a big, centered face.
        # ─────────────────────────────────────────────────────────────────────
        _GCS_AVATARS = "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/avatars"
        CURATED_AVATARS = [
            ("female-1", "female", f"{_GCS_AVATARS}/female-1.png"),
            ("female-2", "female", f"{_GCS_AVATARS}/female-2.png"),
            ("female-3", "female", f"{_GCS_AVATARS}/female-3.png"),
            ("male-1",   "male",   f"{_GCS_AVATARS}/male-1.png"),
            ("male-2",   "male",   f"{_GCS_AVATARS}/male-2.png"),
            ("male-3",   "male",   f"{_GCS_AVATARS}/male-3.png"),
        ]
        portraits: List[Dict[str, str]] = [
            {"avatar_id": aid, "gender": gender, "url": url}
            for aid, gender, url in CURATED_AVATARS
        ]
        logger.info(f"  Using {len(portraits)} curated avatar portraits from GCS")

        if not portraits:
            logger.error("No portraits generated — cannot proceed with ai_avatar")
            return

        male_portraits = [p for p in portraits if p["gender"] == "male"]
        female_portraits = [p for p in portraits if p["gender"] == "female"]
        logger.info(
            f"  Portraits ready: {len(female_portraits)} female, {len(male_portraits)} male"
        )

        # ─────────────────────────────────────────────────────────────────────
        # Step 2: Lazy import the PiAPI provider (avoids global import cost
        # when the script is imported for other tools)
        # ─────────────────────────────────────────────────────────────────────
        try:
            from app.providers.piapi_provider import PiAPIProvider
            piapi_provider = PiAPIProvider()
        except Exception as e:
            logger.error(f"Failed to instantiate PiAPIProvider: {e}")
            return

        # ─────────────────────────────────────────────────────────────────────
        # Step 3: Iterate scripts × languages × portraits, calling PiAPI's
        # Kling Avatar for each combination
        # ─────────────────────────────────────────────────────────────────────
        lang_order = ["zh-TW", "en"]
        portrait_idx_by_gender = {"male": 0, "female": 0}

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
                    avatar_gender = script.get("preferred_gender") or (
                        "female" if count % 2 == 0 else "male"
                    )
                    pool = female_portraits if avatar_gender == "female" else male_portraits
                    if not pool:
                        # If we somehow have no portraits of the requested gender,
                        # fall back to whatever we do have
                        pool = portraits
                    idx = portrait_idx_by_gender[avatar_gender] % max(len(pool), 1)
                    portrait = pool[idx]
                    portrait_idx_by_gender[avatar_gender] += 1

                    script_text = script["text_zh"] if language == "zh-TW" else script["text_en"]

                    logger.info(
                        f"[{count+1}] Avatar: {portrait['avatar_id']} ({avatar_gender}) | "
                        f"Topic: {topic} | Script: {script['id']} | Lang: {language}"
                    )
                    logger.info(f"  Script: {script_text[:60]}...")

                    start_time = time.time()

                    # Call PiAPI Kling Avatar via the provider (handles F5-TTS
                    # internally, then sends image + audio to Kling)
                    try:
                        result = await piapi_provider.generate_avatar(
                            {
                                "image_url": portrait["url"],
                                "script": script_text,
                                "language": language,
                                "mode": "std",
                            }
                        )
                    except Exception as e:
                        logger.error(f"  PiAPI Avatar exception: {e}")
                        self.stats["failed"] += 1
                        self.stats["by_tool"]["ai_avatar"]["failed"] += 1
                        count += 1
                        self._topic_mark_generated(topic_key, topic_counts)
                        continue

                    if not result.get("success"):
                        logger.error(f"  Failed: {result.get('error', 'Unknown')}")
                        self.stats["failed"] += 1
                        self.stats["by_tool"]["ai_avatar"]["failed"] += 1
                        count += 1
                        self._topic_mark_generated(topic_key, topic_counts)
                        continue

                    output = result.get("output") or {}
                    video_url = output.get("video_url")
                    if not video_url:
                        # Try nested Kling shape (works[].video.url)
                        works = output.get("works") or []
                        if works and isinstance(works[0], dict):
                            v_obj = works[0].get("video") or {}
                            if isinstance(v_obj, dict):
                                video_url = v_obj.get("url")
                            elif isinstance(v_obj, str):
                                video_url = v_obj

                    if not video_url:
                        logger.error(
                            f"  No video_url in PiAPI Avatar response: {output}"
                        )
                        self.stats["failed"] += 1
                        self.stats["by_tool"]["ai_avatar"]["failed"] += 1
                        count += 1
                        self._topic_mark_generated(topic_key, topic_counts)
                        continue

                    local_entry = {
                        "topic": topic,
                        "language": language,
                        "prompt": script_text,
                        "prompt_zh": script_text if language == "zh-TW" else None,
                        "prompt_en": script_text if language == "en" else None,
                        "input_image_url": portrait["url"],
                        "result_video_url": video_url,
                        # hash_context differentiates (avatar, script, language)
                        # combos so each one produces a unique lookup_hash row.
                        "hash_context": (
                            f"avatar={portrait['avatar_id']}:"
                            f"script={script['id']}:"
                            f"lang={language}"
                        ),
                        "input_params": {
                            "avatar_id": portrait["avatar_id"],
                            "voice_gender": portrait["gender"],
                            "script_id": script["id"],
                            "language": language,
                        },
                        "generation_steps": [
                            {
                                "step": 1,
                                "api": "piapi_kling_avatar",
                                "action": "avatar_generation",
                                "result_url": video_url,
                                "duration_ms": int((time.time() - start_time) * 1000),
                            }
                        ],
                        "generation_cost": 0.30,
                    }
                    self.local_results["ai_avatar"].append(local_entry)

                    logger.info(
                        f"  Success: {video_url[:80]} "
                        f"(avatar_id={portrait['avatar_id']}, gender={avatar_gender})"
                    )
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

                # Use I2I (image-to-image) so output is derived from the actual input room photo.
                # Style prompt only describes the desired art style — the room photo drives the content.
                style_prompt = f"{style_data['prompt']}, photorealistic interior design, architectural visualization, 8K"

                i2i = await self.piapi.image_to_image(
                    image_url=room_data["url"],
                    prompt=style_prompt,
                    strength=0.65  # preserves room structure while applying style
                )

                if not i2i.get("success"):
                    logger.error(f"  I2I Failed: {i2i.get('error')}")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["room_redesign"]["failed"] += 1
                    count += 1
                    self._topic_mark_generated(style_id, topic_counts)
                    continue

                result_image_url = i2i.get("image_url") or i2i.get("output", {}).get("image_url")
                if not result_image_url:
                    images = i2i.get("output", {}).get("images", [])
                    if images:
                        result_image_url = images[0].get("url") if isinstance(images[0], dict) else images[0]

                if not result_image_url:
                    logger.error("  No result URL in I2I response")
                    self.stats["failed"] += 1
                    self.stats["by_tool"]["room_redesign"]["failed"] += 1
                    count += 1
                    self._topic_mark_generated(style_id, topic_counts)
                    continue

                local_entry = {
                    "topic": room_data["room_type"],  # so topic matches selectedRoomType in frontend
                    "prompt": style_prompt,
                    "input_image_url": room_data["url"],  # actual room photo passed to I2I
                    "result_image_url": result_image_url,  # I2I output derived from input photo
                    "generation_steps": [
                        {"step": 1, "api": "piapi", "action": "i2i_style", "input_url": room_data["url"], "result_url": result_image_url}
                    ],
                    "input_params": {
                        "room_id": room_id,
                        "style_id": style_id,  # matches DESIGN_STYLES e.g. modern_minimalist, scandinavian
                        "room_type": room_data["room_type"]
                    },
                    "generation_cost": 0.005
                }
                self.local_results["room_redesign"].append(local_entry)

                logger.info(f"  Result: {result_image_url}")
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
        all_scenes = PRODUCT_SCENE_MAPPING["scenes"]
        # Apply --topics filter if provided
        if getattr(self, 'topic_filter', None):
            scenes = {k: v for k, v in all_scenes.items() if k in self.topic_filter}
            logger.info(f"  Filtered to {len(scenes)} scenes: {list(scenes.keys())}")
        else:
            scenes = all_scenes
        product_image_cache = {}
        topic_counts: Dict[str, int] = {}

        for prod_id, prod_data in products.items():
            if self.per_topic_limit is None and count >= limit:
                break

            product_prompt = prod_data.get("prompt")
            product_prompt_zh = prod_data.get("prompt_zh")

            # Use the frozen curated product image (no T2I step — deterministic input).
            # These PNGs were generated once, reviewed by a human, and uploaded to GCS
            # so every pregen run produces the same product.
            fixed_url = prod_data.get("url")
            if fixed_url:
                product_image_cache[prod_id] = fixed_url
            elif product_prompt and prod_id not in product_image_cache:
                logger.warning(
                    f"  No fixed URL for {prod_data['name']}, falling back to T2I (non-deterministic)"
                )
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

                    # F-018 fix: upload both to GCS before calling PiAPI.
                    # The old code relied on PUBLIC_APP_URL/static/... which is
                    # unreachable because the Cloud Run Job's ephemeral FS is
                    # separate from the backend service's. GCS is a single
                    # global bucket both containers can write/read.
                    #
                    # F-019 fix: Kling Virtual Try-On rejects any image whose
                    # smaller dimension is below 512px. The garment catalog
                    # contains ~400x533 thumbnails, so we upscale them here
                    # before upload. Models are already 1024+ but we pass the
                    # same min_dim for defense in depth — it's a no-op when the
                    # source is already big enough.
                    model_url = await self._local_to_gcs_for_piapi(
                        model_url, "image", min_dim=512
                    )
                    garment_url = await self._local_to_gcs_for_piapi(
                        garment_url, "image", min_dim=512
                    )

                    logger.info(f"  Model: {model_url[:60]}...")
                    logger.info(f"  Garment: {garment_url[:60]}...")

                    # Use REAL Virtual Try-On API (Kling AI via PiAPI)
                    # Model/garment are GCS URLs after F-018 fix — PiAPI can
                    # download them from the public bucket.
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
                        # hash_context makes each (model_id, clothing_id) pair produce
                        # a unique lookup_hash. Without this, all 4 combos with the same
                        # clothing but different models would collide and get deduped
                        # down to a single row — which is why our first try_on regen
                        # only produced 4 rows all for female-1.
                        "hash_context": f"model={model_id}",
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

            # Step 1: Resolve source image. If the entry has a frozen `url`
            # (curated GCS asset), use it directly — no T2I. Otherwise fall
            # back to T2I from prompt (legacy path, kept for safety).
            logger.info(f"[{count+1}] Source: {source['name']} ({source['name_zh']})")
            fixed_url = source.get("url")
            if fixed_url:
                source_image_url = fixed_url
                logger.info(f"  Using frozen source: {source_image_url}")
            else:
                logger.info(f"  Generating source image via T2I (no fixed url)...")
                t2i = await self.piapi.generate_image(
                    prompt=source.get("prompt", ""),
                    width=1024,
                    height=1024,
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
                    "prompt": f"{source['name']} | Style: {style_data['prompt']}",
                    "prompt_zh": f"{source['name_zh']} | 風格: {style_data['name_zh']}",
                    "effect_prompt": style_data["prompt"],
                    "input_image_url": source_image_url,  # Frozen product photo
                    "result_image_url": result_url,  # Styled version
                    "hash_context": f"product={source.get('product_id', source['name'])}",
                    "input_params": {
                        "product_id": source.get("product_id"),
                        "source_name": source["name"],
                        "style_id": style_id,
                        "style_name": style_data["name"],
                        "strength": style_data.get("strength", 0.65),
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

    async def _to_gcs_url(
        self,
        url: Optional[str],
        media_type: str = "image",
    ) -> Optional[str]:
        """
        Resolve any URL to a permanent GCS public URL before writing to the DB.

        Handles three cases:
        - Already a GCS URL (`https://storage.googleapis.com/...`) → return as-is.
        - Local `/static/...` path → read the file from `/app/static/...` on disk
          and upload the bytes directly to GCS.
        - External HTTP(S) URL (PiAPI temp, Pollo temp, etc.) → hand off to
          `gcs.persist_url()` which downloads and re-uploads.

        Returns None on any failure so the caller can decide whether to drop
        the field or fail the row entirely. Never returns `/static/...` and
        never returns a provider temp URL.
        """
        if not url:
            return None

        # Already persisted
        if url.startswith("https://storage.googleapis.com/"):
            return url

        # GCS not configured — surface the failure instead of writing a dead URL
        if not self.gcs.enabled:
            logger.error(
                f"  [GCS] Cannot persist {url[:80]} — GCS_BUCKET not configured"
            )
            return None

        try:
            # Local file → upload bytes directly
            if url.startswith("/static/"):
                from pathlib import Path as _P
                local_path = _P(f"/app{url}")
                if not local_path.exists():
                    logger.warning(
                        f"  [GCS] Local file missing, cannot persist: {local_path}"
                    )
                    return None
                data = local_path.read_bytes()
                ext = local_path.suffix or ".png"
                content_type = {
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".webp": "image/webp",
                    ".mp4": "video/mp4",
                    ".webm": "video/webm",
                    ".wav": "audio/wav",
                    ".mp3": "audio/mpeg",
                    ".glb": "model/gltf-binary",
                }.get(ext.lower(), "application/octet-stream")
                blob_name = f"generated/{media_type}/{local_path.stem}{ext}"
                public_url = self.gcs.upload_public(
                    data, blob_name, content_type=content_type
                )
                logger.info(f"  [GCS] Local → {blob_name}")
                return public_url

            # External URL → download + re-upload
            if url.startswith("http://") or url.startswith("https://"):
                public_url = await self.gcs.persist_url(
                    source_url=url,
                    media_type=media_type,
                )
                # persist_url returns the source URL unchanged on failure —
                # treat that as a failure so we never write a temp URL to DB.
                if public_url == url:
                    logger.warning(
                        f"  [GCS] persist_url returned source unchanged for {url[:80]}"
                    )
                    return None
                return public_url

        except Exception as e:
            logger.error(f"  [GCS] Failed to persist {url[:80]}: {e}")
            return None

        # Unknown scheme — refuse
        logger.warning(f"  [GCS] Unknown URL scheme, cannot persist: {url[:80]}")
        return None

    async def _local_to_gcs_for_piapi(
        self,
        url: str,
        media_type: str = "image",
        min_dim: int = 0,
    ) -> str:
        """
        Upload a local /static/* or /app/static/* file to GCS and return the
        public GCS URL, so external providers (PiAPI, Kling, Pollo) can
        actually fetch it. Optionally upscales images below `min_dim` pixels
        on their smaller side before upload.

        Context for F-018: the pre-generation pipeline writes files to the
        Cloud Run Job container's ephemeral /app/static/ filesystem. The
        PiAPI client then prepends PUBLIC_APP_URL and hands the URL to the
        Kling Try-On API. But `https://api.vidgo.co/static/...` resolves to
        the backend service container, which has a separate ephemeral FS
        and never saw those files. Result: PiAPI gets 404 and the try-on
        call fails with "failed to download input image".

        Context for F-019: Kling Virtual Try-On rejects images whose smaller
        dimension is below 512 pixels with "image dimension less than 512px".
        The garment catalog contains thumbnails at ~400x533. Pass min_dim=512
        to upscale (LANCZOS) before upload so Kling accepts them.

        Passthrough URLs (http(s) + GCS) are returned unchanged. Upload failures
        fall back to the original URL so the caller still produces a clear
        provider error rather than a silent hang.
        """
        if not url:
            return url
        if url.startswith("https://storage.googleapis.com/"):
            return url
        if url.startswith(("http://", "https://")):
            # Already a remote URL (garment preview from a CDN, etc.) — pass through
            return url
        # Normalize /app/static/... → /static/... so _to_gcs_url recognizes it
        normalized = url[len("/app"):] if url.startswith("/app/static/") else url
        if not normalized.startswith("/static/"):
            # Not a local path we know how to handle (e.g. base64 data URL)
            return url

        # Optional: upscale images that are too small for the provider's minimum.
        # Always uses a unique blob name so PiAPI / Kling can never hit a stale
        # CDN-cached version of a previous upload at the same URL (F-019 round 2).
        if min_dim > 0 and media_type == "image" and self.gcs.enabled:
            try:
                from pathlib import Path as _P
                from PIL import Image as _PImg
                import io as _io
                import uuid as _uuid

                local_path = _P(f"/app{normalized}")
                if local_path.exists():
                    with open(local_path, "rb") as f:
                        raw = f.read()
                    img = _PImg.open(_io.BytesIO(raw))
                    w, h = img.size
                    if min(w, h) < min_dim:
                        scale = min_dim / float(min(w, h))
                        new_w = int(round(w * scale))
                        new_h = int(round(h * scale))
                        if img.mode not in ("RGB", "RGBA"):
                            img = img.convert("RGB")
                        img = img.resize((new_w, new_h), _PImg.Resampling.LANCZOS)
                        ext = local_path.suffix.lower() or ".jpg"
                        fmt = "JPEG" if ext in (".jpg", ".jpeg") else "PNG"
                        if fmt == "JPEG" and img.mode == "RGBA":
                            img = img.convert("RGB")
                        buf = _io.BytesIO()
                        img.save(buf, format=fmt, quality=95)
                        data = buf.getvalue()
                        content_type = "image/jpeg" if fmt == "JPEG" else "image/png"
                        # Unique suffix prevents PiAPI / Kling from serving a
                        # stale edge-cached copy of the pre-upscale version.
                        suffix = _uuid.uuid4().hex[:8]
                        blob_name = (
                            f"generated/{media_type}/tryon/"
                            f"{local_path.stem}_{suffix}{ext}"
                        )
                        gcs_url = self.gcs.upload_public(
                            data, blob_name, content_type=content_type
                        )
                        logger.info(
                            f"  [Try-On] Upscaled {local_path.name} {w}x{h} → "
                            f"{new_w}x{new_h}, uploaded to {gcs_url[:80]}"
                        )
                        return gcs_url
                    else:
                        # Already big enough — still upload with a unique name to
                        # bypass any prior cached version at the canonical URL.
                        ext = local_path.suffix.lower() or ".jpg"
                        content_type = (
                            "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
                        )
                        suffix = _uuid.uuid4().hex[:8]
                        blob_name = (
                            f"generated/{media_type}/tryon/"
                            f"{local_path.stem}_{suffix}{ext}"
                        )
                        gcs_url = self.gcs.upload_public(
                            raw, blob_name, content_type=content_type
                        )
                        logger.info(
                            f"  [Try-On] Re-uploaded {local_path.name} "
                            f"({w}x{h}, already ≥ {min_dim}) to {gcs_url[:80]}"
                        )
                        return gcs_url
            except Exception as e:
                logger.warning(
                    f"  [Try-On] Upscale check failed for {url[:60]}: {e}, falling back"
                )

        # No upscale needed (or not an image) — delegate to _to_gcs_url
        gcs_url = await self._to_gcs_url(normalized, media_type)
        if gcs_url:
            logger.info(f"  [Try-On] Uploaded local asset to GCS: {url[:60]} → {gcs_url[:80]}")
            return gcs_url
        # Upload failed — return original so the caller can still try,
        # and we get a clearer error from the provider instead of silent fallback
        logger.warning(f"  [Try-On] GCS upload failed for {url[:60]}, using original URL")
        return url

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

            # Encode to PNG bytes in-memory (no local file) and upload to GCS.
            # Never return a /static/*.png path — production Cloud Run has
            # no persistent filesystem for /static/generated/.
            buf = io.BytesIO()
            watermarked_rgb.save(buf, format="PNG", quality=95)
            wm_bytes = buf.getvalue()

            if not self.gcs.enabled:
                logger.error(
                    "  [Watermark] GCS_BUCKET not configured — cannot upload "
                    "watermarked image, refusing to return a dead /static path"
                )
                return None

            blob_name = f"generated/watermarked/{abs_path.stem}_wm.png"
            public_url = self.gcs.upload_public(
                wm_bytes, blob_name, content_type="image/png"
            )
            logger.info(f"  Watermarked → {blob_name}")
            return public_url

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
                    input_image_url=entry.get("input_image_url"),
                    extra_context=entry.get("hash_context", ""),
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

                # Apply watermark to result images (for image-based tools).
                # This now returns a GCS URL directly — no more /static/*_wm.png.
                raw_result_image_url = entry.get("result_image_url")
                raw_result_video_url = entry.get("result_video_url")
                result_watermarked_url: Optional[str] = None

                if raw_result_image_url and raw_result_image_url.startswith("/static/"):
                    result_watermarked_url = await self._apply_watermark_to_local_image(
                        raw_result_image_url
                    )

                # Persist every URL we're about to write to the DB to GCS.
                # _to_gcs_url handles /static/ paths, temp CDN URLs, and no-ops
                # GCS URLs that are already persistent.
                raw_input_image_url = entry.get("input_image_url")
                input_image_url = await self._to_gcs_url(raw_input_image_url, "image")
                result_image_url = await self._to_gcs_url(raw_result_image_url, "image")
                result_video_url = await self._to_gcs_url(raw_result_video_url, "video")

                # Watermarked fallback: if we didn't make a watermark but we have
                # a persisted result image/video, fall back to that.
                if not result_watermarked_url:
                    result_watermarked_url = result_video_url or result_image_url

                # Refuse to write a row that has NO persistable result at all.
                # Better to fail loudly in logs than publish a dead row to the DB.
                if not result_image_url and not result_video_url:
                    logger.error(
                        f"  [{tool_name}] Refusing to store row {lookup_hash[:12]} "
                        f"— no persistable result URL (raw image={raw_result_image_url}, "
                        f"raw video={raw_result_video_url})"
                    )
                    continue

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
                    input_image_url=input_image_url,
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
        per_topic_limit: Optional[int] = None,
        topic_filter: Optional[List[str]] = None
    ):
        """Run pre-generation pipeline."""
        logger.info("=" * 60)
        logger.info("VidGo Main Pre-generation Pipeline")
        logger.info("=" * 60)
        self.per_topic_limit = per_topic_limit
        self.topic_filter = topic_filter
        if topic_filter:
            logger.info(f"Topic filter: {topic_filter}")

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
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete existing Material rows for the target tool before generating (clean slate)"
    )
    parser.add_argument(
        "--topics",
        type=str,
        default=None,
        help="Comma-separated topic/scene IDs to generate (e.g. 'spring,valentines,christmas'). Only generates these topics."
    )

    args = parser.parse_args()

    if args.clean and args.tool and not args.dry_run:
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
        target = tool_type_map.get(args.tool)
        if target is None:
            logger.error(f"--clean: unknown tool '{args.tool}'")
        else:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import delete as sa_delete
                res = await session.execute(
                    sa_delete(Material).where(Material.tool_type == target)
                )
                await session.commit()
                logger.info(f"--clean: deleted {res.rowcount} existing {args.tool} rows")

    topic_filter = None
    if args.topics:
        topic_filter = [t.strip() for t in args.topics.split(',') if t.strip()]
        logger.info(f"Topic filter: {topic_filter}")

    generator = VidGoPreGenerator()
    await generator.run(
        tool=args.tool if not args.all else None,
        limit=args.limit,
        dry_run=args.dry_run,
        per_topic_limit=args.per_topic_limit,
        topic_filter=topic_filter
    )


if __name__ == "__main__":
    asyncio.run(main())
