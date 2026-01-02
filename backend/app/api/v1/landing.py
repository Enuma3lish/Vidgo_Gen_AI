"""
Landing Page API - Public endpoints for landing page content
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import random

router = APIRouter()


# ============== Schemas ==============

class StatItem(BaseModel):
    value: str
    label: str
    color: str


class LandingStats(BaseModel):
    users: StatItem
    time_saved: StatItem
    conversion: StatItem


class FeatureItem(BaseModel):
    id: str
    icon: str
    gradient: str
    title: str
    title_zh: str
    description: str
    description_zh: str


class ExampleItem(BaseModel):
    id: str
    category: str
    category_label: str
    duration: str
    title: str
    title_zh: str
    description: str
    description_zh: str
    thumbnail: str
    video_url: Optional[str] = None


class TestimonialItem(BaseModel):
    id: str
    name: str
    title: str
    company: str
    company_type: str
    avatar: Optional[str]
    rating: int
    quote: str
    quote_zh: str


class PricingPlan(BaseModel):
    id: str
    name: str
    name_zh: str
    price: int
    original_price: int
    currency: str
    period: str
    description: str
    description_zh: str
    features: List[str]
    features_zh: List[str]
    is_featured: bool
    badge: Optional[str] = None


class FAQItem(BaseModel):
    id: str
    question: str
    question_zh: str
    answer: str
    answer_zh: str


class ContactForm(BaseModel):
    name: str
    email: str
    company: Optional[str]
    message: str


# ============== Static Data ==============

LANDING_STATS = LandingStats(
    users=StatItem(value="10K+", label="Active Users", color="purple"),
    time_saved=StatItem(value="80%", label="Time Saved", color="cyan"),
    conversion=StatItem(value="3x", label="Conversion Rate", color="pink")
)

FEATURES = [
    FeatureItem(
        id="ai_generation",
        icon="sparkles",
        gradient="blue",
        title="AI Smart Generation",
        title_zh="AI 智能生成",
        description="Advanced AI technology automatically analyzes your needs and generates professional video ads that match your brand",
        description_zh="先進的 AI 技術自動分析您的需求，生成符合品牌調性的專業影片廣告"
    ),
    FeatureItem(
        id="fast_create",
        icon="zap",
        gradient="orange",
        title="Fast Creation",
        title_zh="快速製作",
        description="Complete video ad production in just 3 minutes, dramatically reducing traditional production time",
        description_zh="只需 3 分鐘即可完成影片廣告製作，大幅縮短傳統製作流程"
    ),
    FeatureItem(
        id="precision_targeting",
        icon="target",
        gradient="green",
        title="Precision Targeting",
        title_zh="精準投放",
        description="Intelligent analysis of target audience to optimize ad content for higher click and conversion rates",
        description_zh="智能分析目標受眾，優化廣告內容以提升點擊率和轉換率"
    ),
    FeatureItem(
        id="data_analytics",
        icon="chart-bar",
        gradient="pink",
        title="Data Analytics",
        title_zh="數據分析",
        description="Real-time tracking of ad performance with deep data analysis and optimization suggestions",
        description_zh="即時追蹤廣告成效，提供深度數據分析和優化建議"
    ),
    FeatureItem(
        id="multilingual",
        icon="globe",
        gradient="cyan",
        title="Multi-language Support",
        title_zh="多語言支援",
        description="Support for 30+ languages, easily expand to global markets",
        description_zh="支援 30+ 種語言，輕鬆拓展全球市場"
    ),
    FeatureItem(
        id="team_collab",
        icon="users",
        gradient="red",
        title="Team Collaboration",
        title_zh="團隊協作",
        description="Support multi-person collaboration to create perfect ad content together",
        description_zh="支援多人協作，讓團隊共同打造完美廣告內容"
    )
]

EXAMPLES = [
    ExampleItem(
        id="ex1",
        category="ecommerce",
        category_label="電商",
        duration="15 秒",
        title="E-commerce Product Ad",
        title_zh="電商產品廣告",
        description="Product showcase video for e-commerce platforms",
        description_zh="適合電商平台的產品展示影片",
        thumbnail="https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&h=400&fit=crop"
    ),
    ExampleItem(
        id="ex2",
        category="social",
        category_label="社群",
        duration="10 秒",
        title="Social Media Short Video",
        title_zh="社群媒體短影片",
        description="Eye-catching shorts for Instagram and TikTok",
        description_zh="Instagram、TikTok 專用的吸睛短片",
        thumbnail="https://images.unsplash.com/photo-1611162616305-c69b3fa7fbe0?w=600&h=400&fit=crop"
    ),
    ExampleItem(
        id="ex3",
        category="brand",
        category_label="品牌",
        duration="30 秒",
        title="Brand Story Video",
        title_zh="品牌形象影片",
        description="Showcase enterprise value and brand story",
        description_zh="展現企業價值與品牌故事",
        thumbnail="https://images.unsplash.com/photo-1552664730-d307ca884978?w=600&h=400&fit=crop"
    ),
    ExampleItem(
        id="ex4",
        category="app",
        category_label="應用程式",
        duration="20 秒",
        title="App Promotion Video",
        title_zh="App 推廣影片",
        description="Highlight core app features",
        description_zh="突顯應用程式核心功能",
        thumbnail="https://images.unsplash.com/photo-1512941937669-90a1b58e7e9c?w=600&h=400&fit=crop"
    ),
    ExampleItem(
        id="ex5",
        category="promo",
        category_label="促銷",
        duration="12 秒",
        title="Promotional Video",
        title_zh="促銷活動影片",
        description="Limited-time offers and promotional campaigns",
        description_zh="限時優惠與促銷活動宣傳",
        thumbnail="https://images.unsplash.com/photo-1607083206869-4c7672e72a8a?w=600&h=400&fit=crop"
    ),
    ExampleItem(
        id="ex6",
        category="service",
        category_label="服務",
        duration="25 秒",
        title="Service Introduction Video",
        title_zh="服務介紹影片",
        description="Professional service showcase and explanation",
        description_zh="專業服務展示與說明",
        thumbnail="https://images.unsplash.com/photo-1556761175-5973dc0f32e7?w=600&h=400&fit=crop"
    )
]

TESTIMONIALS = [
    TestimonialItem(
        id="t1",
        name="陳建華",
        title="行銷總監",
        company="數位行銷公司",
        company_type="Digital Marketing",
        avatar=None,
        rating=5,
        quote="VIDGO significantly improved our ad production efficiency. What used to take weeks now takes just minutes, and the quality exceeds expectations.",
        quote_zh="VIDGO 大幅提升了我們的廣告製作效率。原本需要數週的工作，現在只需幾分鐘就能完成，而且品質超出預期。"
    ),
    TestimonialItem(
        id="t2",
        name="林雅婷",
        title="創意總監",
        company="品牌策略公司",
        company_type="Brand Strategy",
        avatar=None,
        rating=5,
        quote="The quality of AI-generated videos exceeded expectations. Our clients were amazed by the efficiency and creativity.",
        quote_zh="AI 生成的影片質量超出預期，客戶都對我們的效率和創意讚不絕口。"
    ),
    TestimonialItem(
        id="t3",
        name="王大明",
        title="執行長",
        company="電商平台",
        company_type="E-commerce",
        avatar=None,
        rating=5,
        quote="After using VIDGO, our ad conversion rate increased by 3x. This is truly a revolutionary tool.",
        quote_zh="使用 VIDGO 後，我們的廣告轉換率提升了 3 倍。這真的是革命性的工具。"
    ),
    TestimonialItem(
        id="t4",
        name="張美玲",
        title="社群經理",
        company="新創公司",
        company_type="Startup",
        avatar=None,
        rating=5,
        quote="As a small team, we couldn't afford professional video production. VIDGO solved this problem and our content looks very professional.",
        quote_zh="作為小團隊，我們沒有預算請專業團隊製作影片。VIDGO 解決了這個問題，我們的內容看起來非常專業。"
    ),
    TestimonialItem(
        id="t5",
        name="李俊傑",
        title="數位行銷專員",
        company="廣告代理商",
        company_type="Ad Agency",
        avatar=None,
        rating=5,
        quote="The multi-language support feature is very practical. We can now serve global clients without complex localization processes.",
        quote_zh="多語言支援功能非常實用，我們現在能夠服務全球客戶，而不需要複雜的在地化流程。"
    ),
    TestimonialItem(
        id="t6",
        name="黃淑芬",
        title="產品經理",
        company="SaaS 公司",
        company_type="SaaS",
        avatar=None,
        rating=5,
        quote="The data analytics feature helps us continuously optimize our ad strategy. We can see what works and adjust in real-time.",
        quote_zh="數據分析功能幫助我們持續優化廣告策略，可以即時看到什麼效果好並即時調整。"
    )
]

PRICING_PLANS = [
    PricingPlan(
        id="starter",
        name="Starter",
        name_zh="入門版",
        price=165,
        original_price=329,
        currency="NT$",
        period="month",
        description="For individual creators and small businesses",
        description_zh="個人創作者與小型企業",
        features=[
            "10 videos/month",
            "720p HD quality",
            "Basic AI templates",
            "Free music library",
            "Social media formats",
            "Email support"
        ],
        features_zh=[
            "每月 10 個影片",
            "720p 高清畫質",
            "基礎 AI 模板",
            "免費音樂庫",
            "社群媒體格式",
            "電子郵件支援"
        ],
        is_featured=False
    ),
    PricingPlan(
        id="pro",
        name="Professional",
        name_zh="專業版",
        price=325,
        original_price=649,
        currency="NT$",
        period="month",
        description="For growing business teams",
        description_zh="成長中的企業團隊",
        features=[
            "50 videos/month",
            "1080p Full HD quality",
            "Advanced AI templates",
            "Complete music library",
            "All platform formats",
            "Priority support",
            "Brand customization",
            "Team collaboration (5 users)"
        ],
        features_zh=[
            "每月 50 個影片",
            "1080p 全高清畫質",
            "進階 AI 模板",
            "完整音樂庫",
            "所有平台格式",
            "優先客服支援",
            "品牌客製化",
            "團隊協作 (5人)"
        ],
        is_featured=True,
        badge="最受歡迎"
    ),
    PricingPlan(
        id="enterprise",
        name="Enterprise",
        name_zh="企業版",
        price=550,
        original_price=1099,
        currency="NT$",
        period="month",
        description="For large enterprises and agencies",
        description_zh="大型企業與代理商",
        features=[
            "Unlimited videos",
            "4K Ultra HD quality",
            "Custom AI models",
            "Licensed music library",
            "Multi-brand management",
            "Dedicated account manager",
            "API integration",
            "Unlimited team members",
            "White-label solution"
        ],
        features_zh=[
            "無限制影片",
            "4K 超高清畫質",
            "自訂 AI 模型",
            "版權音樂庫",
            "多品牌管理",
            "專屬客戶經理",
            "API 整合",
            "無限團隊成員",
            "白標方案"
        ],
        is_featured=False
    )
]

FAQ_ITEMS = [
    FAQItem(
        id="faq1",
        question="How does VIDGO work?",
        question_zh="VIDGO 是如何運作的？",
        answer="VIDGO uses advanced AI technology to automatically analyze your uploaded materials and requirements, then generates professional video ads. Simply upload your product images or videos, select a style template, and the AI will do the rest.",
        answer_zh="VIDGO 使用先進的 AI 技術自動分析您上傳的素材和需求，然後生成專業的影片廣告。只需上傳您的產品圖片或影片，選擇風格模板，AI 就會完成其餘工作。"
    ),
    FAQItem(
        id="faq2",
        question="Do I need video production experience?",
        question_zh="我需要具備影片製作經驗嗎？",
        answer="No experience needed! VIDGO is designed for everyone. Our intuitive interface and AI-powered tools make video creation as simple as uploading photos and clicking a button.",
        answer_zh="不需要任何經驗！VIDGO 專為所有人設計。我們直觀的介面和 AI 工具讓影片製作像上傳照片和點擊按鈕一樣簡單。"
    ),
    FAQItem(
        id="faq3",
        question="How long does it take to generate a video?",
        question_zh="生成一個影片需要多長時間？",
        answer="Most videos are generated within 1-5 minutes depending on complexity and length. Short social media clips typically take about 1 minute, while longer brand videos may take up to 5 minutes.",
        answer_zh="大多數影片在 1-5 分鐘內生成，取決於複雜度和長度。短社群媒體片段通常約 1 分鐘，較長的品牌影片可能需要 5 分鐘。"
    ),
    FAQItem(
        id="faq4",
        question="Can I customize the video style and content?",
        question_zh="我可以自訂影片的風格和內容嗎？",
        answer="Absolutely! You can customize templates, colors, fonts, music, and text. Paid users can also use custom prompts for more personalized results.",
        answer_zh="當然可以！您可以自訂模板、顏色、字體、音樂和文字。付費用戶還可以使用自訂提示詞獲得更個性化的結果。"
    ),
    FAQItem(
        id="faq5",
        question="What video formats and sizes are supported?",
        question_zh="支援哪些影片格式和尺寸？",
        answer="We support all major formats including MP4, MOV, and WebM. Sizes include 16:9 (YouTube), 9:16 (TikTok/Reels), 1:1 (Instagram), and 4:5 (Facebook).",
        answer_zh="我們支援所有主流格式，包括 MP4、MOV 和 WebM。尺寸包括 16:9 (YouTube)、9:16 (TikTok/Reels)、1:1 (Instagram) 和 4:5 (Facebook)。"
    ),
    FAQItem(
        id="faq6",
        question="What's included in the free trial?",
        question_zh="免費試用包含哪些功能？",
        answer="Free trial includes 5 video generations with watermark, access to basic templates, and 720p output quality. It's a great way to experience our AI capabilities before subscribing.",
        answer_zh="免費試用包含 5 次帶浮水印的影片生成，可存取基礎模板和 720p 輸出品質。這是訂閱前體驗我們 AI 能力的好方法。"
    ),
    FAQItem(
        id="faq7",
        question="How do you charge? Can I cancel anytime?",
        question_zh="如何收費？可以隨時取消嗎？",
        answer="We offer monthly subscriptions with no long-term commitment. You can upgrade, downgrade, or cancel anytime. First month is 50% off, and we offer 7-day full refund guarantee.",
        answer_zh="我們提供月訂閱方案，無長期合約。您可以隨時升級、降級或取消。首月享半價優惠，並提供 7 天全額退款保證。"
    ),
    FAQItem(
        id="faq8",
        question="Is my data and video content secure?",
        question_zh="我的數據和影片內容安全嗎？",
        answer="Yes, security is our top priority. All data is encrypted, stored securely, and never shared with third parties. You retain full ownership of your content.",
        answer_zh="是的，安全是我們的首要任務。所有數據都經過加密，安全儲存，絕不與第三方共享。您保留內容的完全所有權。"
    ),
    FAQItem(
        id="faq9",
        question="Do you support team collaboration?",
        question_zh="支援團隊協作功能嗎？",
        answer="Yes! Pro plans include team collaboration for up to 5 members, and Enterprise plans support unlimited team members with role-based permissions.",
        answer_zh="是的！專業版方案包含最多 5 人的團隊協作，企業版方案支援無限團隊成員並可設定角色權限。"
    ),
    FAQItem(
        id="faq10",
        question="What support is available if I have issues?",
        question_zh="如果遇到問題，可以獲得什麼支援？",
        answer="We offer email support for all users, priority chat support for Pro users, and dedicated account managers for Enterprise users. We also have a comprehensive help center and video tutorials.",
        answer_zh="我們為所有用戶提供電子郵件支援，Pro 用戶享有優先聊天支援，企業用戶有專屬客戶經理。我們還有完整的說明中心和教學影片。"
    )
]


# ============== Endpoints ==============

@router.get("/stats", response_model=LandingStats)
async def get_landing_stats():
    """Get landing page statistics (10K+, 80%, 3x)"""
    return LANDING_STATS


@router.get("/features", response_model=List[FeatureItem])
async def get_features():
    """Get feature list for landing page"""
    return FEATURES


@router.get("/examples", response_model=List[ExampleItem])
async def get_examples(category: Optional[str] = Query(None)):
    """
    Get example videos for landing page

    Categories: ecommerce, social, brand, app, promo, service
    """
    if category and category != "all":
        return [ex for ex in EXAMPLES if ex.category == category]
    return EXAMPLES


@router.get("/testimonials", response_model=List[TestimonialItem])
async def get_testimonials():
    """Get customer testimonials"""
    return TESTIMONIALS


@router.get("/pricing", response_model=List[PricingPlan])
async def get_pricing():
    """Get pricing plans with promotional pricing"""
    return PRICING_PLANS


@router.get("/faq", response_model=List[FAQItem])
async def get_faq():
    """Get FAQ items"""
    return FAQ_ITEMS


@router.post("/contact")
async def submit_contact_form(form: ContactForm):
    """Submit contact form"""
    # TODO: Save to database and send notification
    return {"success": True, "message": "Contact form submitted successfully"}


@router.post("/demo-generate")
async def demo_generate():
    """
    Landing page demo generation (no login required)
    Counts against daily free quota
    """
    # TODO: Implement with quota check
    return {
        "success": True,
        "message": "Demo generation started",
        "task_id": f"demo_{random.randint(1000, 9999)}"
    }
