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
import uuid as uid_module
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.demo import ToolShowcase
from app.models.material import Material, ToolType, MaterialSource, MaterialStatus
from app.services.pollo_ai import PolloAIClient, get_pollo_client
from app.services.rescue_service import get_rescue_service
from app.services.a2e_service import A2EAvatarService, get_a2e_service
from app.services.watermark import WatermarkService, get_watermark_service
from app.providers.provider_router import get_provider_router, TaskType

logger = logging.getLogger(__name__)


# =============================================================================
# MATERIAL DEFINITIONS
# =============================================================================

# Avatar images per topic category
AVATAR_IMAGES = {
    "ecommerce": [
        "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=512",  # Professional business woman
        "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=512",  # Business man in suit
    ],
    "social": [
        "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=512",  # Young influencer woman
        "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=512",  # Young influencer man
    ],
    "brand": [
        "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=512",  # Professional woman
        "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=512",  # Professional man
    ],
    "app": [
        "https://images.unsplash.com/photo-1580489944761-15a19d654956?w=512",  # Tech-savvy woman
        "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=512",  # Young tech man
    ],
    "promo": [
        "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=512",  # Enthusiastic woman
        "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=512",  # Enthusiastic man
    ],
    "service": [
        "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=512",  # Service professional woman
        "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=512",  # Service professional man
    ]
}

# Landing Page Examples - 6 per topic with related avatars (to avoid repetition)
LANDING_EXAMPLES = {
    "ecommerce": {
        "name_en": "E-commerce",
        "name_zh": "電商廣告",
        "examples": [
            {
                "prompt_en": "Professional e-commerce product video, luxury wristwatch on marble surface, elegant lighting, premium brand feel",
                "prompt_zh": "專業電商產品影片，奢華手錶在大理石表面，優雅燈光，高端品牌質感",
                "avatar_en": "Introducing our premium luxury watch collection. Crafted with precision and elegance, this timepiece is perfect for those who appreciate fine craftsmanship.",
                "avatar_zh": "為您介紹我們的頂級奢華手錶系列。精工打造，優雅設計，適合品味獨特的您。"
            },
            {
                "prompt_en": "Premium skincare product showcase, elegant cream jar on white background, soft studio lighting",
                "prompt_zh": "高端護膚產品展示，精緻乳霜瓶在白色背景，柔和攝影棚燈光",
                "avatar_en": "Discover our revolutionary skincare line. Each product is formulated with the finest ingredients to give you radiant, youthful skin.",
                "avatar_zh": "探索我們革命性的護膚系列。每款產品都採用頂級成分，讓您擁有光彩照人的年輕肌膚。"
            },
            {
                "prompt_en": "Fashion accessories display, designer handbag with gold details, luxury boutique setting",
                "prompt_zh": "時尚配件展示，設計師手袋配金色細節，奢華精品店環境",
                "avatar_en": "Elevate your style with our exclusive designer collection. Each piece tells a story of elegance and sophistication.",
                "avatar_zh": "用我們的獨家設計師系列提升您的品味。每件作品都訴說著優雅與精緻的故事。"
            },
            {
                "prompt_en": "Electronic gadget showcase, wireless earbuds in charging case, sleek minimalist design",
                "prompt_zh": "電子產品展示，無線耳機在充電盒中，簡約時尚設計",
                "avatar_en": "Experience crystal-clear audio with our latest wireless earbuds. Designed for music lovers who demand the best.",
                "avatar_zh": "體驗我們最新無線耳機的水晶般清晰音質。專為追求極致的音樂愛好者設計。"
            },
            {
                "prompt_en": "Gourmet coffee beans in premium packaging, artisanal coffee brand, warm rustic ambiance",
                "prompt_zh": "精品咖啡豆高級包裝，手工咖啡品牌，溫暖鄉村風情",
                "avatar_en": "Awaken your senses with our artisanal coffee collection. Sourced from the finest estates around the world.",
                "avatar_zh": "用我們的手工咖啡系列喚醒您的感官。精選自世界各地最優質的莊園。"
            },
            {
                "prompt_en": "Smart home device display, modern voice assistant speaker, futuristic home environment",
                "prompt_zh": "智能家居設備展示，現代語音助手音箱，未來感家居環境",
                "avatar_en": "Transform your home with our smart assistant. Control everything with just your voice.",
                "avatar_zh": "用我們的智能助手改變您的家。只需語音即可控制一切。"
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
                "prompt_en": "Food photography content, artisan pasta dish, rustic Italian restaurant ambiance",
                "prompt_zh": "美食攝影內容，手工義大利麵料理，鄉村義大利餐廳氛圍",
                "avatar_en": "Foodies, this one is for you! The most authentic Italian pasta you'll ever taste!",
                "avatar_zh": "美食家們，這是為你們準備的！最正宗的義大利麵，讓您難以忘懷！"
            }
        ]
    },
    "brand": {
        "name_en": "Brand Promotion",
        "name_zh": "品牌推廣",
        "examples": [
            {
                "prompt_en": "Corporate brand video, modern office environment, professional team collaboration",
                "prompt_zh": "企業品牌影片，現代辦公環境，專業團隊協作",
                "avatar_en": "At our company, innovation meets excellence. We're dedicated to delivering outstanding results for every client.",
                "avatar_zh": "在我們公司，創新與卓越相遇。我們致力於為每位客戶提供卓越的成果。"
            },
            {
                "prompt_en": "Tech startup showcase, innovative product launch, futuristic design elements",
                "prompt_zh": "科技新創展示，創新產品發布，未來感設計元素",
                "avatar_en": "Introducing our groundbreaking technology that will revolutionize the industry.",
                "avatar_zh": "為您介紹我們將徹底改變行業的突破性技術。"
            },
            {
                "prompt_en": "Sustainable business showcase, eco-friendly products, green environment",
                "prompt_zh": "永續企業展示，環保產品，綠色環境",
                "avatar_en": "Sustainability is at the heart of everything we do. Join us in making a difference.",
                "avatar_zh": "永續發展是我們一切行動的核心。加入我們，一起創造改變。"
            },
            {
                "prompt_en": "Luxury hotel brand, elegant lobby with chandelier, premium hospitality",
                "prompt_zh": "豪華酒店品牌，優雅大廳配水晶吊燈，頂級款待服務",
                "avatar_en": "Welcome to our five-star hotel. Experience luxury and comfort like never before.",
                "avatar_zh": "歡迎來到我們的五星級酒店。體驗前所未有的奢華與舒適。"
            },
            {
                "prompt_en": "Fashion brand identity, runway show highlights, haute couture aesthetics",
                "prompt_zh": "時尚品牌形象，時裝秀精華，高級訂製美學",
                "avatar_en": "Fashion is art. Our new collection redefines elegance for the modern era.",
                "avatar_zh": "時尚即藝術。我們的新系列為現代時代重新定義優雅。"
            },
            {
                "prompt_en": "Financial services brand, trustworthy advisors, sophisticated office space",
                "prompt_zh": "金融服務品牌，值得信賴的顧問，精緻辦公空間",
                "avatar_en": "Your financial future matters. Let our experts guide you to success.",
                "avatar_zh": "您的財務未來很重要。讓我們的專家引導您走向成功。"
            }
        ]
    },
    "app": {
        "name_en": "App Promotion",
        "name_zh": "應用推廣",
        "examples": [
            {
                "prompt_en": "Mobile app showcase, smartphone displaying app interface, modern UI design",
                "prompt_zh": "手機應用展示，智慧型手機顯示應用介面，現代UI設計",
                "avatar_en": "Download our app today and experience the future of productivity!",
                "avatar_zh": "立即下載我們的應用程式，體驗生產力的未來！"
            },
            {
                "prompt_en": "Gaming app promotion, exciting game graphics, immersive gaming experience",
                "prompt_zh": "遊戲應用推廣，精彩遊戲畫面，沉浸式遊戲體驗",
                "avatar_en": "Ready for adventure? Our new game will take you to worlds beyond imagination!",
                "avatar_zh": "準備好冒險了嗎？我們的新遊戲將帶您進入超乎想像的世界！"
            },
            {
                "prompt_en": "Finance app showcase, clean interface showing charts and analytics",
                "prompt_zh": "金融應用展示，乾淨介面顯示圖表和分析",
                "avatar_en": "Take control of your finances with our smart money management app.",
                "avatar_zh": "用我們的智能理財應用掌控您的財務。"
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
                "prompt_en": "Loyalty rewards program, golden membership card, exclusive benefits",
                "prompt_zh": "忠誠獎勵計劃，金色會員卡，專屬福利",
                "avatar_en": "Join our VIP program and enjoy exclusive rewards and discounts!",
                "avatar_zh": "加入我們的VIP計劃，享受獨家獎勵和折扣！"
            },
            {
                "prompt_en": "Bundle deal promotion, multiple products grouped together, value showcase",
                "prompt_zh": "組合優惠促銷，多款產品組合，價值展示",
                "avatar_en": "Get more for less with our exclusive bundle deals! Save up to 40%!",
                "avatar_zh": "用我們的獨家組合優惠花更少買更多！最高省40%！"
            }
        ]
    },
    "service": {
        "name_en": "Service Intro",
        "name_zh": "服務介紹",
        "examples": [
            {
                "prompt_en": "Professional consulting service, business meeting scene, confident presentation",
                "prompt_zh": "專業顧問服務，商務會議場景，自信簡報",
                "avatar_en": "Our expert consultants are here to help your business grow and succeed.",
                "avatar_zh": "我們的專家顧問在這裡幫助您的企業成長和成功。"
            },
            {
                "prompt_en": "Healthcare service intro, modern clinic environment, caring professionals",
                "prompt_zh": "醫療服務介紹，現代診所環境，關懷專業人員",
                "avatar_en": "Your health is our priority. Experience world-class care at our facility.",
                "avatar_zh": "您的健康是我們的首要任務。在我們的機構體驗世界級的照護。"
            },
            {
                "prompt_en": "Education service, online learning platform, engaging course content",
                "prompt_zh": "教育服務，線上學習平台，引人入勝的課程內容",
                "avatar_en": "Learn from the best! Our expert-led courses will help you master new skills.",
                "avatar_zh": "向最優秀的人學習！我們的專家課程將幫助您掌握新技能。"
            },
            {
                "prompt_en": "Legal services introduction, professional law office, trustworthy attorneys",
                "prompt_zh": "法律服務介紹，專業律師事務所，值得信賴的律師",
                "avatar_en": "Protect your rights with our experienced legal team. We're here for you.",
                "avatar_zh": "讓我們經驗豐富的法律團隊保護您的權益。我們在這裡為您服務。"
            },
            {
                "prompt_en": "IT support services, tech team solving problems, efficient solutions",
                "prompt_zh": "IT支援服務，技術團隊解決問題，高效解決方案",
                "avatar_en": "Technical issues? Our IT experts provide fast, reliable support 24/7.",
                "avatar_zh": "技術問題？我們的IT專家全天候提供快速可靠的支援。"
            },
            {
                "prompt_en": "Real estate services, beautiful property showcase, professional agent",
                "prompt_zh": "房地產服務，精美房產展示，專業經紀人",
                "avatar_en": "Find your dream home with our expert real estate team. Let's start today!",
                "avatar_zh": "讓我們專業的房地產團隊幫您找到夢想中的家。今天就開始吧！"
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
    {"title": "Watch Background Removal", "title_zh": "手錶去背", "source_prompt": "Luxury wristwatch on cluttered desk", "effect": "background_removal", "tool_id": "remove_background", "style_tags": ["background_removal"]},
    {"title": "Sneaker Background Removal", "title_zh": "運動鞋去背", "source_prompt": "White sneaker on grass outdoor", "effect": "background_removal", "tool_id": "remove_background", "style_tags": ["background_removal"]},
    {"title": "Perfume Studio Scene", "title_zh": "香水攝影棚場景", "source_prompt": "Elegant perfume bottle, plain background", "effect": "scene_generation", "tool_id": "product_scene", "style_tags": ["studio"], "scene": "studio"},
    {"title": "Skincare Nature Scene", "title_zh": "護膚品自然場景", "source_prompt": "Skincare cream jar, minimal background", "effect": "scene_generation", "tool_id": "product_scene", "style_tags": ["nature"], "scene": "nature"},
    {"title": "Jewelry Luxury Scene", "title_zh": "珠寶奢華場景", "source_prompt": "Diamond ring on white background", "effect": "scene_generation", "tool_id": "product_scene", "style_tags": ["luxury"], "scene": "luxury"},
    {"title": "Headphones Minimal Scene", "title_zh": "耳機極簡場景", "source_prompt": "Wireless headphones, simple background", "effect": "scene_generation", "tool_id": "product_scene", "style_tags": ["minimal"], "scene": "minimal"}
]

# Video Style Examples - create video then apply style effect
VIDEO_EXAMPLES = [
    {"title": "Anime Style", "title_zh": "動漫風格", "source_prompt": "Cherry blossom tree in spring, gentle breeze", "style_id": "anime", "model_id": 2000, "style_tags": ["anime"]},
    {"title": "Ghibli Style", "title_zh": "吉卜力風格", "source_prompt": "Cozy cottage by lake at sunset", "style_id": "ghibli", "model_id": 1033, "style_tags": ["ghibli"]},
    {"title": "Cyberpunk Style", "title_zh": "賽博朋克風格", "source_prompt": "City street at night with neon lights", "style_id": "cyberpunk", "model_id": 2008, "style_tags": ["cyberpunk"]},
    {"title": "Oil Painting", "title_zh": "油畫效果", "source_prompt": "Golden wheat field at sunset", "style_id": "oil_painting", "model_id": 2006, "style_tags": ["oil_painting"]},
    {"title": "Cinematic Look", "title_zh": "電影質感", "source_prompt": "Ocean waves on rocky shore, dramatic clouds", "style_id": "cinematic", "model_id": 2010, "style_tags": ["cinematic"]}
]

# AI Avatar Examples - product/service ad scripts
AVATAR_EXAMPLES = [
    {"title": "E-commerce Launch", "title_zh": "電商產品發布", "language": "en", "avatar_url": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=512", "script": "Introducing our revolutionary smart watch collection! With advanced health tracking and stunning design.", "style_tags": ["ecommerce", "english"]},
    {"title": "Tech Startup Pitch", "title_zh": "科技創業簡報", "language": "en", "avatar_url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=512", "script": "Welcome to the future of productivity! Our AI-powered app automates repetitive tasks.", "style_tags": ["tech", "english"]},
    {"title": "Skincare Brand", "title_zh": "護膚品牌大使", "language": "en", "avatar_url": "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=512", "script": "Discover the secret to radiant skin with our organic skincare line.", "style_tags": ["beauty", "english"]},
    {"title": "手機產品介紹", "title_zh": "手機產品介紹", "language": "zh-TW", "avatar_url": "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=512", "script": "歡迎了解我們最新推出的旗艦手機！搭載先進的AI攝影系統。", "style_tags": ["tech", "chinese"]},
    {"title": "餐廳美食推薦", "title_zh": "餐廳美食推薦", "language": "zh-TW", "avatar_url": "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=512", "script": "歡迎來到我們的米其林餐廳！精選最新鮮的食材，由頂級主廚精心烹調。", "style_tags": ["food", "chinese"]},
    {"title": "線上課程推廣", "title_zh": "線上課程推廣", "language": "zh-TW", "avatar_url": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=512", "script": "想要在家也能學習新技能嗎？我們的線上課程平台提供上千門專業課程。", "style_tags": ["education", "chinese"]}
]

# Scene prompts for product scene generation
SCENE_PROMPTS = {
    "studio": "professional photography studio, dramatic lighting, black backdrop",
    "nature": "natural wooden surface, fresh green leaves and flowers, soft daylight",
    "luxury": "white marble surface with gold accents, elegant lighting",
    "minimal": "pure white background, floating product with subtle shadow",
    "lifestyle": "cozy home desk with morning sunlight, warm atmosphere"
}


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

    async def check_materials_exist(
        self,
        session: AsyncSession,
        category: str,
        min_count: int = 3
    ) -> bool:
        """Check if enough materials exist for a category."""
        if category == 'landing':
            # Landing materials are stored in Material table with SHORT_VIDEO and AI_AVATAR types
            landing_topics = ["ecommerce", "social", "brand", "app", "promo", "service"]

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
        else:
            # Other categories use ToolShowcase table
            result = await session.execute(
                select(func.count(ToolShowcase.id))
                .where(ToolShowcase.tool_category == category)
                .where(ToolShowcase.is_active == True)
            )
            count = result.scalar() or 0
            logger.info(f"Category '{category}' has {count} materials (min: {min_count})")
            return count >= min_count

    async def check_all_materials(self, session: AsyncSession) -> Dict[str, bool]:
        """Check material status for all categories."""
        categories = {
            'landing': 6,      # 6 topics
            'pattern': 10,     # 10 patterns
            'product': 6,      # 6 product examples
            'video': 5,        # 5 video styles
            'avatar': 6        # 6 avatar examples
        }

        status = {}
        for category, min_count in categories.items():
            status[category] = await self.check_materials_exist(session, category, min_count)

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

            for category, exists in status.items():
                results['checked'].append(category)

                if exists and not force:
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

        landing_topics = ["ecommerce", "social", "brand", "app", "promo", "service"]

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

        sort_order = 0
        for topic_key, topic_data in LANDING_EXAMPLES.items():
            for idx, example in enumerate(topic_data['examples']):
                try:
                    # Generate product video
                    prompt_zh = example['prompt_zh']
                    prompt_en = example['prompt_en']

                    image_result = await self.rescue_service.generate_image(
                        prompt=prompt_zh,
                        width=1024,
                        height=1024
                    )

                    if not image_result.get('success'):
                        logger.error(f"Image generation failed for {topic_key}")
                        continue

                    image_url = image_result.get('image_url')
                    if not image_url and image_result.get('images'):
                        image_url = image_result['images'][0]['url']

                    # Convert to video using Pollo AI
                    success, task_id, _ = await self.pollo.generate_video(
                        image_url=image_url,
                        prompt=prompt_zh,
                        length=5
                    )

                    video_url = None
                    if success:
                        video_result = await self.pollo.wait_for_completion(task_id, timeout=180)
                        if video_result.get('status') == 'succeed':
                            video_url = video_result.get('video_url')

                    if video_url:
                        # Generate lookup hash for preset-only mode
                        lookup_hash = Material.generate_lookup_hash(
                            tool_type=ToolType.SHORT_VIDEO.value,
                            prompt=prompt_zh
                        )

                        # Save SHORT_VIDEO material
                        # In PRESET-ONLY mode, result_watermarked_url = result_video_url
                        # (all outputs are watermarked by default)
                        video_material = Material(
                            tool_type=ToolType.SHORT_VIDEO,
                            topic=topic_key,
                            language="zh-TW",
                            tags=[topic_key, "landing"],
                            source=MaterialSource.SEED,
                            status=MaterialStatus.APPROVED,
                            prompt=prompt_zh,
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
                        session.add(video_material)
                        await session.commit()
                        logger.info(f"Generated SHORT_VIDEO: {topic_key} #{idx+1}")

                    # Generate avatars for both languages using topic-appropriate images
                    avatar_images = AVATAR_IMAGES.get(topic_key, AVATAR_IMAGES["ecommerce"])
                    avatar_image = avatar_images[idx % len(avatar_images)]  # Alternate between available images

                    for lang, avatar_key in [("en", "avatar_en"), ("zh-TW", "avatar_zh")]:
                        avatar_script = example[avatar_key]
                        avatar_result = await self.avatar_service.generate_and_wait(
                            image_url=avatar_image,
                            script=avatar_script,
                            language=lang,
                            duration=30,
                            timeout=300
                        )

                        if avatar_result.get('success'):
                            avatar_video_url = avatar_result['video_url']
                            # Generate lookup hash for preset-only mode
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
                            session.add(avatar_material)
                            await session.commit()
                            logger.info(f"Generated AI_AVATAR ({lang}): {topic_key} #{idx+1}")

                        await asyncio.sleep(5)  # Rate limiting

                    sort_order += 1
                    await asyncio.sleep(5)  # Rate limiting

                except Exception as e:
                    logger.error(f"Error generating landing {topic_key}: {e}")
                    continue

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
                    length=5
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
