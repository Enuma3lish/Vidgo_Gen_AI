"""
Unified Material Generator Service

Consolidates all showcase/example generation into a single service:
- Landing Page: Video examples with AI Avatars
- Pattern Design: Pattern examples (seamless, floral, geometric, etc.)
- Product Photos: Before/after with real API effects
- AI Video: Video style transformation examples
- AI Avatar: Product/service ad examples

Features:
- Checks if materials exist in DB before generating
- Runs automatically on service startup
- Can generate specific categories or all
- Proper before/after flow using real APIs
"""
import asyncio
import logging
import base64
import time
import uuid as uid_module
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import select, delete, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.demo import ToolShowcase
from app.models.material import Material, ToolType, MaterialSource, MaterialStatus
from app.services.pollo_ai import PolloAIClient, get_pollo_client
from app.services.rescue_service import get_rescue_service
from app.services.a2e_service import A2EAvatarService, get_a2e_service
from app.services.watermark import WatermarkService, get_watermark_service
from app.providers.provider_router import get_provider_router, TaskType
from app.core.config import get_settings
from app.config.topic_registry import get_topic_ids_for_tool, get_landing_topic_ids

logger = logging.getLogger(__name__)
settings = get_settings()
SHORT_VIDEO_LENGTH = int(getattr(settings, "SHORT_VIDEO_LENGTH", 8))
LANDING_GEN_CONCURRENCY = int(getattr(settings, "LANDING_GEN_CONCURRENCY", 2))
LANDING_GEN_SLEEP_SECONDS = int(getattr(settings, "LANDING_GEN_SLEEP_SECONDS", 5))


# =============================================================================
# MATERIAL DEFINITIONS
# =============================================================================

# Avatar images per topic category - SYNCED with frontend AIAvatar.vue (Asian/Chinese, color)
AVATAR_IMAGES_BY_GENDER = {
    "female": {
        "professional": [
            "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=512&fit=crop&crop=faces",
            "https://images.unsplash.com/photo-1534751516642-a1af1ef26a56?w=512&fit=crop&crop=faces",
        ],
        "young": [
            "https://images.unsplash.com/photo-1524504388940-b1c1722653e6?w=512&fit=crop&crop=faces",
            "https://images.unsplash.com/photo-1544006943-0e92b9a3b95d?w=512&fit=crop&crop=faces",
        ],
        "business": [
            "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=512&fit=crop&crop=faces",
            "https://images.unsplash.com/photo-1534751516642-a1af1ef26a56?w=512&fit=crop&crop=faces",
        ]
    },
    "male": {
        "professional": [
            "https://images.unsplash.com/photo-1758600431229-191932ccee81?w=512&fit=crop&crop=faces",
            "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=512&fit=crop&crop=faces",
        ],
        "young": [
            "https://images.unsplash.com/photo-1600486914327-2f364e2d7731?w=512&fit=crop&crop=faces",
            "https://images.unsplash.com/photo-1552375816-4b96b919e67a?w=512&fit=crop&crop=faces",
        ],
        "business": [
            "https://images.unsplash.com/photo-1758600431229-191932ccee81?w=512&fit=crop&crop=faces",
            "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=512&fit=crop&crop=faces",
        ]
    }
}

# Legacy structure maintained for backward compatibility (maps topic to gender-style pairs)
# Format: topic -> [(gender, style), ...]
AVATAR_IMAGE_TOPIC_MAPPING = {
    "ecommerce": [("female", "professional"), ("male", "professional")],
    "social": [("female", "young"), ("male", "young")],
    "brand": [("female", "business"), ("male", "business")],
    "app": [("female", "professional"), ("male", "young")],
    "promo": [("female", "young"), ("male", "young")],
    "service": [("female", "professional"), ("male", "professional")]
}

# Landing Page Examples - 6 per topic with related avatars (to avoid repetition)
LANDING_EXAMPLES = {
    "ecommerce": {
        "name_en": "E-commerce",
        "name_zh": "電商廣告",
        "examples": [
            {
                "prompt_en": "Student backpack with multiple compartments, durable and lightweight design, bright colorful style",
                "prompt_zh": "學生書包配多層收納，耐用輕量設計，鮮豔色彩風格",
                "avatar_en": "Perfect for students! This backpack has enough space for all your books and supplies, designed for comfort and style.",
                "avatar_zh": "學生最佳選擇！這款書包有充足空間放書本和用品，兼具舒適與時尚。"
            },
            {
                "prompt_en": "Stainless steel thermos bottle, keeps drinks hot or cold, practical daily item",
                "prompt_zh": "不鏽鋼保溫杯，保溫保冷效果好，實用日常用品",
                "avatar_en": "Stay hydrated throughout the day! This thermos keeps your drinks at the perfect temperature for hours.",
                "avatar_zh": "整天保持水分！這款保溫杯讓您的飲品長時間維持完美溫度。"
            },
            {
                "prompt_en": "Compact folding umbrella, windproof and waterproof, convenient to carry",
                "prompt_zh": "輕巧折疊雨傘，防風防水，方便攜帶",
                "avatar_en": "Don't let the rain stop you! This compact umbrella fits in any bag and keeps you dry in any weather.",
                "avatar_zh": "別讓雨天阻擋你！這款輕巧雨傘放進任何包包，任何天氣都能保持乾爽。"
            },
            {
                "prompt_en": "USB charging cable, fast charging and durable, compatible with multiple devices",
                "prompt_zh": "USB充電線，快速充電耐用，相容多種裝置",
                "avatar_en": "Never run out of battery! This fast-charging cable is durable and works with all your devices.",
                "avatar_zh": "電池永不耗盡！這款快充線耐用且適用於您的所有裝置。"
            },
            {
                "prompt_en": "Instant coffee packets, convenient and affordable, perfect for busy mornings",
                "prompt_zh": "即溶咖啡包，方便實惠，忙碌早晨的完美選擇",
                "avatar_en": "Quick and delicious coffee! Just add hot water and enjoy your perfect cup in seconds.",
                "avatar_zh": "快速美味的咖啡！只需加熱水，幾秒鐘就能享受完美的一杯。"
            },
            {
                "prompt_en": "Digital alarm clock with LED display, simple and practical, reliable wake-up tool",
                "prompt_zh": "LED顯示數位鬧鐘，簡單實用，可靠的叫醒工具",
                "avatar_en": "Wake up on time every day! This reliable alarm clock has a clear display and multiple alarm settings.",
                "avatar_zh": "每天準時起床！這款可靠鬧鐘有清晰顯示和多組鬧鈴設定。"
            }
        ]
    },
    "social": {
        "name_en": "Social Media",
        "name_zh": "社群媒體",
        "examples": [
            {
                "prompt_en": "Trendy social media content, colorful smoothie bowl, flat lay photography style",
                "prompt_zh": "時尚社群媒體內容，繽紛果昔碗，俯拍攝影風格",
                "avatar_en": "Welcome to my channel! Today I'm sharing my favorite healthy breakfast recipe that will energize your whole day!",
                "avatar_zh": "歡迎來到我的頻道！今天分享我最愛的健康早餐食譜，讓您活力滿滿一整天！"
            },
            {
                "prompt_en": "Fitness motivation content, workout equipment and healthy snacks, energetic atmosphere",
                "prompt_zh": "健身勵志內容，運動器材與健康零食，充滿活力氛圍",
                "avatar_en": "Ready to transform your fitness journey? Join me for daily workout tips and motivation!",
                "avatar_zh": "準備好改變您的健身之旅了嗎？跟我一起每天學習運動技巧和獲得動力！"
            },
            {
                "prompt_en": "Travel vlog style, stunning sunset beach scene, wanderlust aesthetic",
                "prompt_zh": "旅行Vlog風格，壯麗日落海灘場景，旅行美學",
                "avatar_en": "Come explore the world with me! This hidden paradise is absolutely breathtaking!",
                "avatar_zh": "跟我一起探索世界！這個隱藏的天堂真是美得令人窒息！"
            },
            {
                "prompt_en": "Lifestyle content, cozy reading nook with warm lighting, hygge aesthetic",
                "prompt_zh": "生活風格內容，溫馨閱讀角落搭配溫暖燈光，北歐舒適美學",
                "avatar_en": "Let's create the perfect cozy corner for your home! Books, blankets, and good vibes only!",
                "avatar_zh": "讓我們為您的家創造完美的舒適角落！書籍、毛毯，只有好心情！"
            },
            {
                "prompt_en": "Beauty tutorial style, makeup products neatly arranged, professional vanity setup",
                "prompt_zh": "美妝教學風格，化妝品整齊排列，專業化妝台設置",
                "avatar_en": "Get ready with me! I'll show you this season's hottest makeup trends!",
                "avatar_zh": "跟我一起準備！我會向您展示這一季最熱門的妝容趨勢！"
            },
            {
                "prompt_en": "Home-cooked bento box, healthy lunch meal prep, convenient daily food",
                "prompt_zh": "家庭便當盒，健康午餐備餐，方便的日常飲食",
                "avatar_en": "Meal prepping made easy! Here's my go-to bento recipe that's both delicious and nutritious!",
                "avatar_zh": "簡單備餐教學！這是我最常做的便當食譜，既美味又營養！"
            }
        ]
    },
    "brand": {
        "name_en": "Brand Promotion",
        "name_zh": "品牌推廣",
        "examples": [
            {
                "prompt_en": "Community store showcase, friendly neighborhood shop, local business spirit",
                "prompt_zh": "社區小店展示，親切鄰里商店，在地商業精神",
                "avatar_en": "Supporting local businesses makes our community stronger. Visit your neighborhood stores today!",
                "avatar_zh": "支持在地商家讓我們的社區更強大。今天就去您的社區小店逛逛！"
            },
            {
                "prompt_en": "Tutoring center showcase, students studying happily, educational success stories",
                "prompt_zh": "補習班展示，學生快樂學習，教育成功案例",
                "avatar_en": "Help your child excel in school! Our experienced teachers provide personalized tutoring.",
                "avatar_zh": "幫助您的孩子在學校裡脫穎而出！我們經驗豐富的教師提供個人化輔導。"
            },
            {
                "prompt_en": "Sustainable business showcase, eco-friendly products, green environment",
                "prompt_zh": "永續企業展示，環保產品，綠色環境",
                "avatar_en": "Sustainability is at the heart of everything we do. Join us in making a difference.",
                "avatar_zh": "永續發展是我們一切行動的核心。加入我們，一起創造改變。"
            },
            {
                "prompt_en": "Cozy guesthouse, warm hospitality, comfortable accommodation",
                "prompt_zh": "溫馨民宿，溫暖款待，舒適住宿環境",
                "avatar_en": "Welcome to our family-run guesthouse. Experience the warmth of home away from home.",
                "avatar_zh": "歡迎來到我們的家庭民宿。體驗家一般的溫馨感覺。"
            },
            {
                "prompt_en": "Clothing store showcase, trendy apparel display, affordable fashion",
                "prompt_zh": "服飾店展示，時尚服飾陳列，平價時尚",
                "avatar_en": "Update your wardrobe with our latest collection! Quality fashion at honest prices.",
                "avatar_zh": "用我們的最新系列更新您的衣櫥！優質時尚，實在價格。"
            },
            {
                "prompt_en": "Convenience store, everyday essentials, friendly service",
                "prompt_zh": "便利商店，日常生活必需品，親切服務",
                "avatar_en": "We're here 24/7 for all your daily needs. Your neighborhood convenience store!",
                "avatar_zh": "我們全天候為您的日常需求服務。您的鄰里便利商店！"
            }
        ]
    },
    "app": {
        "name_en": "App Promotion",
        "name_zh": "應用推廣",
        "examples": [
            {
                "prompt_en": "Expense tracking app, budget management interface, practical finance tool",
                "prompt_zh": "記帳應用程式，預算管理介面，實用理財工具",
                "avatar_en": "Keep track of your spending easily! Our app helps you save money every day.",
                "avatar_zh": "輕鬆記錄每筆花費！我們的應用幫助您每天省錢。"
            },
            {
                "prompt_en": "Bus arrival app, real-time public transport info, convenient commuting tool",
                "prompt_zh": "公車到站應用，即時交通資訊，方便通勤工具",
                "avatar_en": "Never miss your bus again! Check arrival times in real-time and plan your commute.",
                "avatar_zh": "再也不會錯過公車！即時查看到站時間，規劃您的通勤。"
            },
            {
                "prompt_en": "Receipt lottery app, invoice scanning and prize checking, practical daily tool",
                "prompt_zh": "發票對獎應用，發票掃描對獎功能，實用日常工具",
                "avatar_en": "Check your receipts and win prizes! Scan invoices instantly and never miss a reward.",
                "avatar_zh": "對獎發票贏獎品！即時掃描發票，不錯過任何獲獎機會。"
            },
            {
                "prompt_en": "Health tracking app, fitness statistics dashboard, motivational design",
                "prompt_zh": "健康追蹤應用，健身統計儀表板，激勵設計",
                "avatar_en": "Your health journey starts here. Track, improve, and celebrate your progress!",
                "avatar_zh": "您的健康旅程從這裡開始。追蹤、改善，並慶祝您的進步！"
            },
            {
                "prompt_en": "Social networking app, chat interface with colorful bubbles, friendly design",
                "prompt_zh": "社交網絡應用，彩色氣泡聊天介面，友善設計",
                "avatar_en": "Connect with friends and family like never before. Download now!",
                "avatar_zh": "以前所未有的方式與親友聯繫。立即下載！"
            },
            {
                "prompt_en": "E-learning app, interactive course modules, student success stories",
                "prompt_zh": "線上學習應用，互動課程模組，學生成功故事",
                "avatar_en": "Learn anything, anywhere, anytime. Start your learning journey today!",
                "avatar_zh": "隨時隨地學習任何知識。今天就開始您的學習之旅！"
            }
        ]
    },
    "promo": {
        "name_en": "Promotional",
        "name_zh": "活動促銷",
        "examples": [
            {
                "prompt_en": "Sale promotion video, exciting discount graphics, festive atmosphere",
                "prompt_zh": "促銷活動影片，精彩折扣圖形，節慶氛圍",
                "avatar_en": "Don't miss our biggest sale of the year! Up to 50% off on all items!",
                "avatar_zh": "不要錯過我們年度最大特賣！全場商品最高五折優惠！"
            },
            {
                "prompt_en": "New product launch, dramatic reveal, spotlight effect",
                "prompt_zh": "新品發布，戲劇性揭幕，聚光燈效果",
                "avatar_en": "The wait is over! Introducing our most innovative product yet!",
                "avatar_zh": "等待結束！為您介紹我們迄今最創新的產品！"
            },
            {
                "prompt_en": "Seasonal campaign, holiday themed decorations, warm festive mood",
                "prompt_zh": "季節性活動，節日主題裝飾，溫暖節慶氛圍",
                "avatar_en": "Celebrate the season with our special holiday collection!",
                "avatar_zh": "用我們的節日特別系列慶祝這個季節！"
            },
            {
                "prompt_en": "Flash sale countdown, urgent timer display, dynamic energy",
                "prompt_zh": "限時特賣倒計時，緊急計時器顯示，動態能量",
                "avatar_en": "Only 24 hours left! Grab these deals before they're gone!",
                "avatar_zh": "只剩24小時！趕快搶購這些優惠，錯過就沒有了！"
            },
            {
                "prompt_en": "Points collection program, reward card, customer loyalty benefits",
                "prompt_zh": "集點活動計劃，集點卡片，顧客忠誠度優惠",
                "avatar_en": "Collect points with every purchase! Redeem for great rewards and discounts.",
                "avatar_zh": "每次購買都能集點！兌換超值獎勵和折扣。"
            },
            {
                "prompt_en": "Buy one get one free promotion, special offer display, great value deals",
                "prompt_zh": "買一送一促銷，特別優惠展示，超值劃算",
                "avatar_en": "Double the value! Buy one get one free on selected items. Limited time only!",
                "avatar_zh": "加倍超值！選定商品買一送一。限時優惠！"
            }
        ]
    },
    "service": {
        "name_en": "Service Intro",
        "name_zh": "服務介紹",
        "examples": [
            {
                "prompt_en": "Tutoring service, student learning scene, friendly teacher",
                "prompt_zh": "家教服務，學生學習場景，友善老師",
                "avatar_en": "Professional tutoring to help students excel. Flexible schedule, proven results!",
                "avatar_zh": "專業家教服務幫助學生優異表現。彈性時間，實證成效！"
            },
            {
                "prompt_en": "Clinic appointment service, friendly reception, convenient booking",
                "prompt_zh": "診所掛號服務，親切櫃台，方便預約",
                "avatar_en": "Easy online appointment booking! Visit our clinic for quality healthcare.",
                "avatar_zh": "輕鬆線上掛號！到我們診所享受優質醫療服務。"
            },
            {
                "prompt_en": "Education service, online learning platform, engaging course content",
                "prompt_zh": "教育服務，線上學習平台，引人入勝的課程內容",
                "avatar_en": "Learn from the best! Our expert-led courses will help you master new skills.",
                "avatar_zh": "向最優秀的人學習！我們的專家課程將幫助您掌握新技能。"
            },
            {
                "prompt_en": "Home repair service, handyman fixing issues, reliable solutions",
                "prompt_zh": "居家修繕服務，師傅維修問題，可靠解決方案",
                "avatar_en": "Leaky faucet? Broken door? Our skilled team handles all home repairs!",
                "avatar_zh": "水龍頭漏水？門壞了？我們熟練的團隊處理所有居家修繕！"
            },
            {
                "prompt_en": "Computer repair service, tech fixing laptop, affordable pricing",
                "prompt_zh": "電腦維修服務，技師修理筆電，親民價格",
                "avatar_en": "Slow computer? Virus problems? We fix all computer issues quickly!",
                "avatar_zh": "電腦很慢？病毒問題？我們快速修復所有電腦問題！"
            },
            {
                "prompt_en": "Rental apartment service, cozy room viewing, affordable housing",
                "prompt_zh": "租屋服務，溫馨房間瀏覽，經濟實惠住宅",
                "avatar_en": "Looking for a place to rent? Browse our affordable apartments today!",
                "avatar_zh": "在找租屋嗎？立即瀏覽我們經濟實惠的公寓！"
            }
        ]
    }
}

# Pattern Design Examples - 2 per style
PATTERN_EXAMPLES = [
    {"style": "seamless", "prompt": "Elegant rose gold and marble seamless pattern", "title": "Rose Gold Marble", "title_zh": "玫瑰金大理石"},
    {"style": "seamless", "prompt": "Modern geometric hexagon seamless pattern", "title": "Hexagon Grid", "title_zh": "六邊形網格"},
    {"style": "floral", "prompt": "Vintage botanical floral pattern with roses", "title": "Vintage Roses", "title_zh": "復古玫瑰"},
    {"style": "floral", "prompt": "Tropical leaves and flowers pattern", "title": "Tropical Flora", "title_zh": "熱帶花卉"},
    {"style": "geometric", "prompt": "Art deco geometric gold pattern", "title": "Art Deco Gold", "title_zh": "裝飾藝術金色"},
    {"style": "geometric", "prompt": "Minimalist triangles pattern", "title": "Minimal Triangles", "title_zh": "極簡三角形"},
    {"style": "abstract", "prompt": "Watercolor abstract fluid pattern", "title": "Fluid Watercolor", "title_zh": "流動水彩"},
    {"style": "abstract", "prompt": "Bold abstract brushstroke pattern", "title": "Bold Strokes", "title_zh": "大膽筆觸"},
    {"style": "traditional", "prompt": "Chinese cloud motif pattern", "title": "Chinese Clouds", "title_zh": "中式雲紋"},
    {"style": "traditional", "prompt": "Japanese wave pattern", "title": "Japanese Waves", "title_zh": "日式波浪"}
]

# Product Photos Examples - generate then apply effect
PRODUCT_EXAMPLES = [
    {"title": "Candle Background Removal", "title_zh": "蠟燭去背", "source_prompt": "Handmade soy candle on wooden table", "effect": "background_removal", "tool_id": "remove_background", "style_tags": ["background_removal"]},
    {"title": "Tote Bag Background Removal", "title_zh": "托特包去背", "source_prompt": "Canvas tote bag on grass outdoor", "effect": "background_removal", "tool_id": "remove_background", "style_tags": ["background_removal"]},
    {"title": "Skincare Studio Scene", "title_zh": "護膚品攝影棚場景", "source_prompt": "Skincare serum bottle, plain background", "effect": "scene_generation", "tool_id": "product_scene", "style_tags": ["studio"], "scene": "studio"},
    {"title": "Skincare Nature Scene", "title_zh": "護膚品自然場景", "source_prompt": "Skincare cream jar, minimal background", "effect": "scene_generation", "tool_id": "product_scene", "style_tags": ["nature"], "scene": "nature"},
    {"title": "Jewelry Elegant Scene", "title_zh": "飾品質感場景", "source_prompt": "Handmade jewelry on white background", "effect": "scene_generation", "tool_id": "product_scene", "style_tags": ["elegant"], "scene": "elegant"},
    {"title": "Coffee Beans Minimal Scene", "title_zh": "咖啡豆極簡場景", "source_prompt": "Coffee beans in kraft bag, simple background", "effect": "scene_generation", "tool_id": "product_scene", "style_tags": ["minimal"], "scene": "minimal"}
]

# Video Style Examples - create video then apply style effect
VIDEO_EXAMPLES = [
    {"title": "Anime Style", "title_zh": "動漫風格", "source_prompt": "Cherry blossom tree in spring, gentle breeze", "style_id": "anime", "model_id": 2000, "style_tags": ["anime"]},
    {"title": "Ghibli Style", "title_zh": "吉卜力風格", "source_prompt": "Cozy cottage by lake at sunset", "style_id": "ghibli", "model_id": 1033, "style_tags": ["ghibli"]},
    {"title": "Cyberpunk Style", "title_zh": "賽博朋克風格", "source_prompt": "City street at night with neon lights", "style_id": "cyberpunk", "model_id": 2008, "style_tags": ["cyberpunk"]},
    {"title": "Oil Painting", "title_zh": "油畫效果", "source_prompt": "Golden wheat field at sunset", "style_id": "oil_painting", "model_id": 2006, "style_tags": ["oil_painting"]},
    {"title": "Cinematic Look", "title_zh": "電影質感", "source_prompt": "Ocean waves on rocky shore, dramatic clouds", "style_id": "cinematic", "model_id": 2010, "style_tags": ["cinematic"]}
]

# AI Avatar Examples - SYNCED with frontend avatars (Asian/Chinese, color)
AVATAR_EXAMPLES = [
    {"title": "E-commerce Launch", "title_zh": "電商產品發布", "language": "en", "avatar_url": "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=512&fit=crop&crop=faces", "script": "Introducing our revolutionary smart watch collection! With advanced health tracking and stunning design.", "style_tags": ["ecommerce", "english"]},
    {"title": "Tech Startup Pitch", "title_zh": "科技創業簡報", "language": "en", "avatar_url": "https://images.unsplash.com/photo-1758600431229-191932ccee81?w=512&fit=crop&crop=faces", "script": "Welcome to the future of productivity! Our AI-powered app automates repetitive tasks.", "style_tags": ["tech", "english"]},
    {"title": "Skincare Brand", "title_zh": "護膚品牌大使", "language": "en", "avatar_url": "https://images.unsplash.com/photo-1534751516642-a1af1ef26a56?w=512&fit=crop&crop=faces", "script": "Discover the secret to radiant skin with our organic skincare line.", "style_tags": ["beauty", "english"]},
    {"title": "手機產品介紹", "title_zh": "手機產品介紹", "language": "zh-TW", "avatar_url": "https://images.unsplash.com/photo-1758600431229-191932ccee81?w=512&fit=crop&crop=faces", "script": "歡迎了解我們最新推出的旗艦手機！搭載先進的AI攝影系統。", "style_tags": ["tech", "chinese"]},
    {"title": "餐廳美食推薦", "title_zh": "餐廳美食推薦", "language": "zh-TW", "avatar_url": "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=512&fit=crop&crop=faces", "script": "歡迎來到我們的米其林餐廳！精選最新鮮的食材，由頂級主廚精心烹調。", "style_tags": ["food", "chinese"]},
    {"title": "線上課程推廣", "title_zh": "線上課程推廣", "language": "zh-TW", "avatar_url": "https://images.unsplash.com/photo-1524504388940-b1c1722653e6?w=512&fit=crop&crop=faces", "script": "想要在家也能學習新技能嗎？我們的線上課程平台提供上千門專業課程。", "style_tags": ["education", "chinese"]}
]

# Scene prompts for product scene generation
SCENE_PROMPTS = {
    "studio": "professional photography studio, dramatic lighting, black backdrop",
    "nature": "natural wooden surface, fresh green leaves and flowers, soft daylight",
    "elegant": "white marble surface with gold accents, elegant lighting",
    "minimal": "pure white background, floating product with subtle shadow",
    "lifestyle": "cozy home desk with morning sunlight, warm atmosphere"
}


# =============================================================================
# HELPER FUNCTIONS FOR GENDER CONSISTENCY
# =============================================================================

def assign_voice_for_example(language: str, index: int) -> tuple[str, str]:
    """
    Assign voice ID for an example, alternating between genders.
    
    Args:
        language: Language code (e.g., "en", "zh-TW")
        index: Example index (0-based)
        
    Returns:
        Tuple of (voice_id, gender)
    """
    from app.services.a2e_service import A2E_VOICES
    
    voices = A2E_VOICES.get(language, A2E_VOICES["en"])
    voice = voices[index % len(voices)]
    return voice["id"], voice["gender"]


def select_avatar_by_gender(gender: str, style: str = "professional") -> str:
    """
    Select avatar image URL based on gender and style.
    
    Args:
        gender: Gender ("male" or "female")
        style: Avatar style ("professional", "young", or "business")
        
    Returns:
        Avatar image URL
    """
    import random
    
    # Default to professional if style not found
    available_styles = AVATAR_IMAGES_BY_GENDER.get(gender, AVATAR_IMAGES_BY_GENDER["female"])
    images = available_styles.get(style, available_styles["professional"])
    
    return random.choice(images)


def get_avatar_for_topic_example(topic: str, index: int) -> str:
    """
    Get avatar image for a specific topic and example index.
    Uses gender-style mapping to ensure variety.
    
    Args:
        topic: Topic key (e.g., "ecommerce", "social")
        index: Example index (0-based)
        
    Returns:
        Avatar image URL
    """
    # Get gender-style pairs for this topic
    gender_style_pairs = AVATAR_IMAGE_TOPIC_MAPPING.get(
        topic,
        AVATAR_IMAGE_TOPIC_MAPPING["ecommerce"]
    )
    
    # Select gender-style pair based on index
    gender, style = gender_style_pairs[index % len(gender_style_pairs)]
    
    return select_avatar_by_gender(gender, style)


class MaterialGenerator:
    """
    Unified material generation service.

    Generates showcase materials for all topics:
    - landing: Landing page video examples with avatars
    - pattern: Pattern design examples
    - product: Product photo examples with effects
    - video: Video style transformation examples
    - avatar: AI avatar examples

    AI Services:
    - Text-to-Image: GoEnhance Nano Banana / Provider Router
    - Image-to-Video: Pollo AI
    - Avatar Generation: A2E.ai (lip-sync)
    - Video Style Transfer: GoEnhance V2V
    """

    def __init__(self):
        self.pollo: Optional[PolloAIClient] = None
        self.avatar_service: Optional[A2EAvatarService] = None
        self.provider_router = None
        self.rescue_service = None
        self.watermark_service: Optional[WatermarkService] = None

    def _init_services(self):
        """Initialize API services lazily."""
        if not self.pollo:
            self.pollo = get_pollo_client()
        if not self.avatar_service:
            self.avatar_service = get_a2e_service()
        if not self.provider_router:
            self.provider_router = get_provider_router()
        if not self.rescue_service:
            self.rescue_service = get_rescue_service()
        if not self.watermark_service:
            self.watermark_service = get_watermark_service()

    async def _count_by_topic(
        self,
        session: AsyncSession,
        tool_type: ToolType,
        topics: List[str]
    ) -> Dict[str, int]:
        result = await session.execute(
            select(Material.topic, func.count(Material.id))
            .where(Material.tool_type == tool_type)
            .where(Material.is_active == True)
            .where(Material.topic.in_(topics))
            .group_by(Material.topic)
        )
        counts = {row[0]: row[1] for row in result.all()}
        for topic in topics:
            counts.setdefault(topic, 0)
        return counts

    async def _count_missing_prompts(
        self,
        session: AsyncSession,
        tool_type: ToolType,
        topics: Optional[List[str]] = None
    ) -> int:
        query = (
            select(func.count(Material.id))
            .where(Material.tool_type == tool_type)
            .where(Material.is_active == True)
            .where(or_(Material.prompt == None, Material.prompt == ""))
        )
        if topics:
            query = query.where(Material.topic.in_(topics))
        result = await session.execute(query)
        return result.scalar() or 0

    async def _count_missing_prompt_zh(
        self,
        session: AsyncSession,
        tool_type: ToolType,
        topics: Optional[List[str]] = None
    ) -> int:
        query = (
            select(func.count(Material.id))
            .where(Material.tool_type == tool_type)
            .where(Material.is_active == True)
            .where(Material.language.like("zh%"))
            .where(or_(Material.prompt_zh == None, Material.prompt_zh == ""))
        )
        if topics:
            query = query.where(Material.topic.in_(topics))
        result = await session.execute(query)
        return result.scalar() or 0

    async def check_materials_exist(
        self,
        session: AsyncSession,
        category: str,
        min_count: int = 3
    ) -> bool:
        """Check if enough materials exist for a category."""
        if category == 'landing':
            # Landing materials are stored in Material table with SHORT_VIDEO and AI_AVATAR types
            # Topics must match LANDING_EXAMPLES keys used in _generate_landing_materials()
            landing_topics = get_landing_topic_ids()

            # Check for SHORT_VIDEO materials
            video_result = await session.execute(
                select(func.count(Material.id))
                .where(Material.tool_type == ToolType.SHORT_VIDEO)
                .where(Material.topic.in_(landing_topics))
                .where(Material.is_active == True)
            )
            video_count = video_result.scalar() or 0

            # Check for AI_AVATAR materials
            avatar_result = await session.execute(
                select(func.count(Material.id))
                .where(Material.tool_type == ToolType.AI_AVATAR)
                .where(Material.topic.in_(landing_topics))
                .where(Material.is_active == True)
            )
            avatar_count = avatar_result.scalar() or 0

            logger.info(f"Landing: {video_count} videos, {avatar_count} avatars (min: {min_count} each)")
            return video_count >= min_count and avatar_count >= min_count
        elif category == 'pattern':
            # Pattern/effect materials - check BACKGROUND_REMOVAL
            result = await session.execute(
                select(func.count(Material.id))
                .where(Material.tool_type == ToolType.BACKGROUND_REMOVAL)
                .where(Material.is_active == True)
            )
            count = result.scalar() or 0
            logger.info(f"Pattern (background_removal): {count} materials (min: {min_count})")
            return count >= min_count
        elif category == 'product':
            # Product materials - check PRODUCT_SCENE
            result = await session.execute(
                select(func.count(Material.id))
                .where(Material.tool_type == ToolType.PRODUCT_SCENE)
                .where(Material.is_active == True)
            )
            count = result.scalar() or 0
            logger.info(f"Product (product_scene): {count} materials (min: {min_count})")
            return count >= min_count
        elif category == 'video':
            # Video materials - check SHORT_VIDEO
            result = await session.execute(
                select(func.count(Material.id))
                .where(Material.tool_type == ToolType.SHORT_VIDEO)
                .where(Material.is_active == True)
            )
            count = result.scalar() or 0
            logger.info(f"Video (short_video): {count} materials (min: {min_count})")
            return count >= min_count
        elif category == 'avatar':
            # Avatar materials - check AI_AVATAR
            result = await session.execute(
                select(func.count(Material.id))
                .where(Material.tool_type == ToolType.AI_AVATAR)
                .where(Material.is_active == True)
            )
            count = result.scalar() or 0
            logger.info(f"Avatar (ai_avatar): {count} materials (min: {min_count})")
            return count >= min_count
        else:
            # Fallback to ToolShowcase table for legacy categories
            result = await session.execute(
                select(func.count(ToolShowcase.id))
                .where(ToolShowcase.tool_category == category)
                .where(ToolShowcase.is_active == True)
            )
            count = result.scalar() or 0
            logger.info(f"Category '{category}' has {count} materials (min: {min_count})")
            return count >= min_count

    async def check_all_materials(self, session: AsyncSession) -> Dict[str, Dict[str, Any]]:
        """Check material status with per-topic coverage and prompt validation."""
        status: Dict[str, Dict[str, Any]] = {}

        landing_topics = get_landing_topic_ids()
        landing_video_counts = await self._count_by_topic(session, ToolType.SHORT_VIDEO, landing_topics)
        landing_avatar_counts = await self._count_by_topic(session, ToolType.AI_AVATAR, landing_topics)

        LANDING_VIDEO_PER_TOPIC = 6
        LANDING_AVATAR_PER_TOPIC = 12  # 6 examples × 2 languages

        landing_missing_videos = [t for t, c in landing_video_counts.items() if c < LANDING_VIDEO_PER_TOPIC]
        landing_missing_avatars = [t for t, c in landing_avatar_counts.items() if c < LANDING_AVATAR_PER_TOPIC]

        landing_prompt_missing = (
            await self._count_missing_prompts(session, ToolType.SHORT_VIDEO, landing_topics)
            + await self._count_missing_prompts(session, ToolType.AI_AVATAR, landing_topics)
        )
        landing_prompt_zh_missing = await self._count_missing_prompt_zh(session, ToolType.AI_AVATAR, landing_topics)

        status["landing"] = {
            "ready": len(landing_missing_videos) == 0 and len(landing_missing_avatars) == 0 and landing_prompt_missing == 0 and landing_prompt_zh_missing == 0,
            "missing_topics": {
                "videos": landing_missing_videos,
                "avatars": landing_missing_avatars
            },
            "counts": {
                "videos": landing_video_counts,
                "avatars": landing_avatar_counts
            },
            "prompt_issues": {
                "missing_prompt": landing_prompt_missing,
                "missing_prompt_zh": landing_prompt_zh_missing
            }
        }

        # Per-topic coverage for core tools
        MIN_PER_TOPIC_DEFAULT = 1
        tool_checks = {
            "pattern": (ToolType.BACKGROUND_REMOVAL, get_topic_ids_for_tool("background_removal")),
            "product": (ToolType.PRODUCT_SCENE, get_topic_ids_for_tool("product_scene")),
            "video": (ToolType.SHORT_VIDEO, get_topic_ids_for_tool("short_video")),
            "avatar": (ToolType.AI_AVATAR, get_topic_ids_for_tool("ai_avatar")),
            "effect": (ToolType.EFFECT, get_topic_ids_for_tool("effect"))
        }

        EFFECT_MIN_PER_STYLE = 3

        for category, (tool_type, topics) in tool_checks.items():
            if not topics:
                continue

            counts = await self._count_by_topic(session, tool_type, topics)
            min_per_topic = EFFECT_MIN_PER_STYLE if category == "effect" else MIN_PER_TOPIC_DEFAULT
            missing_topics = [t for t, c in counts.items() if c < min_per_topic]

            prompt_missing = await self._count_missing_prompts(session, tool_type, topics)
            prompt_zh_missing = await self._count_missing_prompt_zh(session, tool_type, topics)

            status[category] = {
                "ready": len(missing_topics) == 0 and prompt_missing == 0 and prompt_zh_missing == 0,
                "missing_topics": missing_topics,
                "counts": counts,
                "prompt_issues": {
                    "missing_prompt": prompt_missing,
                    "missing_prompt_zh": prompt_zh_missing
                }
            }

        return status

    async def generate_missing_materials(self, force: bool = False) -> Dict[str, Any]:
        """
        Generate materials for categories that are missing or incomplete.

        Args:
            force: If True, regenerate all materials even if they exist

        Returns:
            Dict with generation results
        """
        self._init_services()
        results = {
            'checked': [],
            'generated': [],
            'skipped': [],
            'failed': []
        }

        async with AsyncSessionLocal() as session:
            if force:
                logger.info("Force regeneration enabled - generating all materials")

            status = await self.check_all_materials(session)
            generatable = {"landing", "pattern", "product", "video", "avatar"}

            for category, info in status.items():
                if category not in generatable:
                    continue
                results['checked'].append(category)

                ready = info.get("ready", False) if isinstance(info, dict) else bool(info)
                if ready and not force:
                    logger.info(f"Category '{category}' already has materials, skipping")
                    results['skipped'].append(category)
                    continue

                try:
                    logger.info(f"Generating materials for '{category}'...")

                    if category == 'landing':
                        await self._generate_landing_materials(session)
                    elif category == 'pattern':
                        await self._generate_pattern_materials(session)
                    elif category == 'product':
                        await self._generate_product_materials(session)
                    elif category == 'video':
                        await self._generate_video_materials(session)
                    elif category == 'avatar':
                        await self._generate_avatar_materials(session)

                    results['generated'].append(category)

                except Exception as e:
                    logger.error(f"Failed to generate '{category}': {e}")
                    results['failed'].append({'category': category, 'error': str(e)})

        return results

    async def _generate_landing_materials(self, session: AsyncSession):
        """Generate landing page video examples with avatars into Material table."""
        logger.info("Generating landing page materials into Material table...")

        landing_topics = get_landing_topic_ids()

        # Clear old landing materials from Material table
        await session.execute(
            delete(Material)
            .where(Material.tool_type == ToolType.SHORT_VIDEO)
            .where(Material.topic.in_(landing_topics))
        )
        await session.execute(
            delete(Material)
            .where(Material.tool_type == ToolType.AI_AVATAR)
            .where(Material.topic.in_(landing_topics))
        )
        await session.commit()

        sem = asyncio.Semaphore(max(LANDING_GEN_CONCURRENCY, 1))
        topic_items = list(LANDING_EXAMPLES.items())

        async def _process_example(topic_key: str, topic_data: Dict[str, Any], idx: int, example: Dict[str, Any], topic_sort_index: int):
            async with sem:
                try:
                    prompt_zh = example['prompt_zh']
                    prompt_en = example['prompt_en']
                    sort_order = (topic_sort_index * 100) + idx

                    img_start = time.monotonic()
                    image_result = await self.rescue_service.generate_image(
                        prompt=prompt_zh,
                        width=1024,
                        height=1024
                    )
                    img_elapsed = time.monotonic() - img_start
                    logger.info(f"Landing {topic_key} #{idx+1} image gen: {img_elapsed:.1f}s")

                    if not image_result.get('success'):
                        logger.error(f"Image generation failed for {topic_key}")
                        return

                    image_url = image_result.get('image_url')
                    if not image_url and image_result.get('images'):
                        image_url = image_result['images'][0]['url']

                    vid_start = time.monotonic()
                    success, task_id, _ = await self.pollo.generate_video(
                        image_url=image_url,
                        prompt=prompt_zh,
                        length=SHORT_VIDEO_LENGTH
                    )

                    video_url = None
                    if success:
                        video_result = await self.pollo.wait_for_completion(task_id, timeout=180)
                        if video_result.get('status') == 'succeed':
                            video_url = video_result.get('video_url')

                    vid_elapsed = time.monotonic() - vid_start
                    logger.info(f"Landing {topic_key} #{idx+1} video gen: {vid_elapsed:.1f}s")

                    async with AsyncSessionLocal() as task_session:
                        if video_url:
                            lookup_hash = Material.generate_lookup_hash(
                                tool_type=ToolType.SHORT_VIDEO.value,
                                prompt=prompt_zh
                            )

                            video_material = Material(
                                tool_type=ToolType.SHORT_VIDEO,
                                topic=topic_key,
                                language="zh-TW",
                                tags=[topic_key, "landing"],
                                source=MaterialSource.SEED,
                                status=MaterialStatus.APPROVED,
                                prompt=prompt_zh,
                                prompt_zh=prompt_zh,
                                prompt_en=prompt_en,
                                prompt_enhanced=prompt_en,
                                input_image_url=image_url,
                                result_video_url=video_url,
                                result_watermarked_url=video_url,  # PRESET-ONLY: same as original
                                lookup_hash=lookup_hash,
                                title_en=topic_data['name_en'],
                                title_zh=topic_data['name_zh'],
                                quality_score=0.9,
                                sort_order=sort_order,
                                is_featured=True,
                                is_active=True
                            )
                            task_session.add(video_material)
                            await task_session.commit()
                            logger.info(f"Generated SHORT_VIDEO: {topic_key} #{idx+1}")

                        avatar_image_pairs = AVATAR_IMAGE_TOPIC_MAPPING.get(
                            topic_key,
                            AVATAR_IMAGE_TOPIC_MAPPING["ecommerce"]
                        )
                        avatar_candidates = []
                        for gender, style in avatar_image_pairs:
                            avatar_candidates.extend(
                                AVATAR_IMAGES_BY_GENDER.get(gender, {}).get(style, [])
                            )
                        if not avatar_candidates:
                            avatar_candidates = AVATAR_IMAGES_BY_GENDER["female"]["professional"]
                        avatar_image = avatar_candidates[idx % len(avatar_candidates)]

                        for lang, avatar_key in [("en", "avatar_en"), ("zh-TW", "avatar_zh")]:
                            avatar_script = example[avatar_key]
                            avatar_start = time.monotonic()
                            avatar_result = await self.avatar_service.generate_and_wait(
                                image_url=avatar_image,
                                script=avatar_script,
                                language=lang,
                                duration=30,
                                timeout=300
                            )
                            avatar_elapsed = time.monotonic() - avatar_start
                            logger.info(f"Landing {topic_key} #{idx+1} avatar {lang}: {avatar_elapsed:.1f}s")

                            if avatar_result.get('success'):
                                avatar_video_url = avatar_result['video_url']
                                avatar_lookup_hash = Material.generate_lookup_hash(
                                    tool_type=ToolType.AI_AVATAR.value,
                                    prompt=avatar_script
                                )

                                avatar_material = Material(
                                    tool_type=ToolType.AI_AVATAR,
                                    topic=topic_key,
                                    language=lang,
                                    tags=[topic_key, "landing", "avatar"],
                                    source=MaterialSource.SEED,
                                    status=MaterialStatus.APPROVED,
                                    prompt=avatar_script,
                                    prompt_zh=avatar_script if lang.startswith("zh") else None,
                                    prompt_en=avatar_script if lang == "en" else None,
                                    result_video_url=avatar_video_url,
                                    result_watermarked_url=avatar_video_url,  # PRESET-ONLY: same as original
                                    lookup_hash=avatar_lookup_hash,
                                    title_en=f"{topic_data['name_en']} Avatar",
                                    title_zh=f"{topic_data['name_zh']} 數位人",
                                    quality_score=0.9,
                                    sort_order=sort_order,
                                    is_featured=True,
                                    is_active=True
                                )
                                task_session.add(avatar_material)
                                await task_session.commit()
                                logger.info(f"Generated AI_AVATAR ({lang}): {topic_key} #{idx+1}")

                            await asyncio.sleep(LANDING_GEN_SLEEP_SECONDS)

                        await asyncio.sleep(LANDING_GEN_SLEEP_SECONDS)

                except Exception as e:
                    logger.error(f"Error generating landing {topic_key}: {e}")

        tasks = []
        for topic_sort_index, (topic_key, topic_data) in enumerate(topic_items):
            for idx, example in enumerate(topic_data['examples']):
                tasks.append(_process_example(topic_key, topic_data, idx, example, topic_sort_index))

        await asyncio.gather(*tasks)

    async def _generate_pattern_materials(self, session: AsyncSession):
        """Generate pattern design examples using GoEnhance T2I."""
        logger.info("Generating pattern materials with GoEnhance T2I...")

        await session.execute(
            delete(ToolShowcase).where(ToolShowcase.tool_category == 'pattern')
        )
        await session.commit()

        for idx, example in enumerate(PATTERN_EXAMPLES):
            try:
                # Use rescue service for T2I
                full_prompt = f"{example['prompt']}, {example['style']} pattern, seamless, high quality, detailed"
                result = await self.rescue_service.generate_image(
                    prompt=full_prompt,
                    width=1024,
                    height=1024
                )

                image_url = result.get('image_url')
                if not image_url and result.get('images'):
                    image_url = result['images'][0]['url']

                if result.get('success') and image_url:

                    showcase = ToolShowcase(
                        tool_category='pattern',
                        tool_id='pattern_generate',
                        tool_name='Pattern Generate',
                        tool_name_zh='圖案生成',
                        prompt=example['prompt'],
                        prompt_zh=example['prompt'],
                        result_image_url=image_url,
                        title=example['title'],
                        title_zh=example['title_zh'],
                        style_tags=[example['style']],
                        is_featured=True,
                        is_active=True,
                        sort_order=idx,
                        source_service='goenhance'
                    )
                    session.add(showcase)
                    await session.commit()

                    logger.info(f"Generated pattern: {example['title']}")

                await asyncio.sleep(3)

            except Exception as e:
                logger.error(f"Error generating pattern {example['title']}: {e}")

    async def _generate_product_materials(self, session: AsyncSession):
        """Generate product photo examples with real before/after using GoEnhance."""
        logger.info("Generating product materials with GoEnhance...")

        await session.execute(
            delete(ToolShowcase).where(ToolShowcase.tool_category == 'product')
        )
        await session.commit()

        for idx, example in enumerate(PRODUCT_EXAMPLES):
            try:
                # Generate source image using rescue service
                source_result = await self.rescue_service.generate_image(
                    prompt=example['source_prompt'],
                    width=1024,
                    height=1024
                )

                if not source_result.get('success'):
                    continue

                source_url = source_result.get('image_url')
                if not source_url and source_result.get('images'):
                    source_url = source_result['images'][0]['url']
                result_url = None

                await asyncio.sleep(3)

                # Apply effect using ProviderRouter
                if example['effect'] == 'background_removal':
                    # Use ProviderRouter for background removal
                    effect_result = await self.provider_router.route(
                        TaskType.BACKGROUND_REMOVAL,
                        {"image_url": source_url}
                    )
                    output = effect_result.get('output', {})
                    if effect_result.get('success'):
                        result_url = output.get('image_url') or effect_result.get('image_url')

                elif example['effect'] == 'scene_generation':
                    scene = example.get('scene', 'studio')
                    scene_prompt = SCENE_PROMPTS.get(scene, SCENE_PROMPTS['studio'])
                    product_desc = example['source_prompt'].split(',')[0]
                    full_prompt = f"{product_desc} placed in {scene_prompt}"

                    effect_result = await self.rescue_service.generate_image(
                        prompt=full_prompt,
                        width=1024,
                        height=1024
                    )
                    if effect_result.get('success'):
                        result_url = effect_result.get('image_url')
                        if not result_url and effect_result.get('images'):
                            result_url = effect_result['images'][0]['url']

                if result_url:
                    showcase = ToolShowcase(
                        tool_category='product',
                        tool_id=example['tool_id'],
                        tool_name='Product Enhancement',
                        tool_name_zh='產品增強',
                        prompt=example['source_prompt'],
                        prompt_zh=example['title_zh'],
                        source_image_url=source_url,
                        result_image_url=result_url,
                        title=example['title'],
                        title_zh=example['title_zh'],
                        style_tags=example['style_tags'],
                        is_featured=True,
                        is_active=True,
                        sort_order=idx,
                        source_service='goenhance'
                    )
                    session.add(showcase)
                    await session.commit()

                    logger.info(f"Generated product: {example['title']}")

                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Error generating product {example['title']}: {e}")

    async def _generate_video_materials(self, session: AsyncSession):
        """Generate video style transformation examples."""
        logger.info("Generating video materials...")

        await session.execute(
            delete(ToolShowcase).where(ToolShowcase.tool_category == 'video')
        )
        await session.commit()

        for idx, example in enumerate(VIDEO_EXAMPLES):
            try:
                # Generate source image using rescue service
                image_result = await self.rescue_service.generate_image(
                    prompt=example['source_prompt'],
                    width=1024,
                    height=1024
                )

                if not image_result.get('success'):
                    continue

                image_url = image_result.get('image_url')
                if not image_url and image_result.get('images'):
                    image_url = image_result['images'][0]['url']

                await asyncio.sleep(3)

                # Convert to video using Pollo AI
                success, task_id, _ = await self.pollo.generate_video(
                    image_url=image_url,
                    prompt=example['source_prompt'],
                    length=SHORT_VIDEO_LENGTH
                )

                if not success:
                    continue

                video_result = await self.pollo.wait_for_completion(task_id, timeout=180)
                if video_result.get('status') != 'succeed':
                    continue

                source_video_url = video_result['video_url']

                await asyncio.sleep(5)

                # Apply style effect using ProviderRouter V2V
                from app.services.effects_service import get_style_prompt
                style_prompt = get_style_prompt(example['style_id'])
                style_result = await self.provider_router.route(
                    TaskType.V2V,
                    {
                        "video_url": source_video_url,
                        "prompt": style_prompt or example['source_prompt']
                    }
                )

                result_video_url = style_result.get('video_url') or style_result.get('output_url')

                showcase = ToolShowcase(
                    tool_category='video',
                    tool_id='video_transform',
                    tool_name='Video Style Transform',
                    tool_name_zh='影片風格轉換',
                    prompt=example['source_prompt'],
                    prompt_zh=example['title_zh'],
                    source_image_url=image_url,
                    source_video_url=source_video_url,
                    result_video_url=result_video_url or source_video_url,
                    title=example['title'],
                    title_zh=example['title_zh'],
                    style_tags=example['style_tags'],
                    is_featured=True,
                    is_active=True,
                    sort_order=idx,
                    source_service='goenhance'
                )
                session.add(showcase)
                await session.commit()

                logger.info(f"Generated video: {example['title']}")

                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Error generating video {example['title']}: {e}")

    async def _generate_avatar_materials(self, session: AsyncSession):
        """Generate AI avatar examples with product/service ads using A2E.ai."""
        logger.info("Generating avatar materials with A2E.ai...")

        await session.execute(
            delete(ToolShowcase).where(ToolShowcase.tool_category == 'avatar')
        )
        await session.commit()

        for idx, example in enumerate(AVATAR_EXAMPLES):
            try:
                result = await self.avatar_service.generate_and_wait(
                    image_url=example['avatar_url'],
                    script=example['script'],
                    language=example['language'],
                    duration=30,
                    timeout=300
                )

                if result.get('success'):
                    showcase = ToolShowcase(
                        tool_category='avatar',
                        tool_id='ai_avatar',
                        tool_name='AI Avatar',
                        tool_name_zh='AI 數位人',
                        prompt=example['script'],
                        prompt_zh=example['script'] if example['language'] == 'zh-TW' else None,
                        source_image_url=example['avatar_url'],
                        result_video_url=result['video_url'],
                        title=example['title'],
                        title_zh=example['title_zh'],
                        style_tags=example['style_tags'],
                        is_featured=True,
                        is_active=True,
                        sort_order=idx,
                        source_service='a2e'
                    )
                    session.add(showcase)
                    await session.commit()

                    logger.info(f"Generated avatar: {example['title']}")

                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Error generating avatar {example['title']}: {e}")


# Singleton instance
_material_generator: Optional[MaterialGenerator] = None


def get_material_generator() -> MaterialGenerator:
    """Get or create material generator singleton."""
    global _material_generator
    if _material_generator is None:
        _material_generator = MaterialGenerator()
    return _material_generator


async def check_and_generate_materials(force: bool = False) -> Dict[str, Any]:
    """
    Main entry point for material generation.
    Called on service startup to ensure all materials exist.

    Args:
        force: If True, regenerate all materials

    Returns:
        Generation results
    """
    generator = get_material_generator()
    return await generator.generate_missing_materials(force=force)
