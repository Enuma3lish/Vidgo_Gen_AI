"""
VidGo AI - Frontend Application
Simple layout with sidebar navigation
"""
import streamlit as st
import random
import requests
from typing import List, Dict, Any

# Backend API configuration
BACKEND_URL = "http://backend:8000"  # Docker internal URL

def fetch_inspiration_examples(topic: str = None, limit: int = 30) -> List[Dict[str, Any]]:
    """Fetch inspiration examples from backend API."""
    try:
        params = {"limit": limit}
        if topic and topic != "all":
            params["topic"] = topic

        response = requests.get(f"{BACKEND_URL}/api/v1/demo/inspiration", params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return data.get("examples", [])
    except Exception as e:
        st.session_state.api_error = str(e)
    return []

def fetch_topics() -> List[str]:
    """Fetch available topics from backend API."""
    try:
        response = requests.get(f"{BACKEND_URL}/api/v1/demo/inspiration", params={"limit": 1}, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return data.get("topics", [])
    except Exception:
        pass
    return ["product", "food", "fashion", "interior", "portrait", "art", "video"]


def fetch_tool_showcases(tool_category: str, tool_id: str = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch tool showcases from backend API."""
    try:
        params = {"limit": limit}
        if tool_id:
            params["tool_id"] = tool_id
        response = requests.get(f"{BACKEND_URL}/api/v1/demo/tool-showcases/{tool_category}", params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return data.get("showcases", [])
    except Exception as e:
        st.session_state.api_error = str(e)
    return []


def save_user_showcase(tool_category: str, tool_id: str, source_image_url: str, prompt: str,
                       result_image_url: str = None, result_video_url: str = None) -> bool:
    """Save user-generated result as a showcase example."""
    try:
        payload = {
            "tool_category": tool_category,
            "tool_id": tool_id,
            "source_image_url": source_image_url,
            "prompt": prompt,
            "result_image_url": result_image_url,
            "result_video_url": result_video_url
        }
        response = requests.post(f"{BACKEND_URL}/api/v1/demo/tool-showcases/save", json=payload, timeout=5)
        if response.status_code == 200:
            return response.json().get("success", False)
    except Exception:
        pass
    return False


def render_autoplay_video(video_url: str, height: int = 300):
    """Render an auto-playing, muted, looping video using HTML5 video tag."""
    video_html = f'''
    <video width="100%" height="{height}" autoplay muted loop playsinline
           style="border-radius: 8px; object-fit: cover;">
        <source src="{video_url}" type="video/mp4">
        Your browser does not support the video tag.
    </video>
    '''
    st.markdown(video_html, unsafe_allow_html=True)


def render_showcase_result(showcase: dict, height: int = 180, lang: str = "en"):
    """
    Render a showcase result (image or video).
    Shows placeholder if no result is available yet.
    """
    if showcase.get("result_video_url"):
        render_autoplay_video(showcase["result_video_url"], height=height)
    elif showcase.get("result_image_url"):
        st.image(showcase["result_image_url"], use_container_width=True)
    else:
        # No result yet - show placeholder
        placeholder_text = "🔄 正在生成..." if lang == "zh" else "🔄 Generating..."
        st.markdown(
            f'''<div style="
                height: {height}px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 14px;
                text-align: center;
                padding: 20px;
            ">{placeholder_text}</div>''',
            unsafe_allow_html=True
        )


def scroll_to_top():
    """Inject JavaScript to scroll to top of page in Streamlit's iframe environment."""
    js = '''
    <script>
        // Try multiple methods for Streamlit iframe environment
        try {
            // Method 1: Target the main Streamlit container
            const mainContainer = window.parent.document.querySelector('[data-testid="stAppViewContainer"]');
            if (mainContainer) {
                mainContainer.scrollTo({top: 0, behavior: 'smooth'});
            }
            // Method 2: Target the main document body
            window.parent.document.documentElement.scrollTo({top: 0, behavior: 'smooth'});
            window.parent.document.body.scrollTo({top: 0, behavior: 'smooth'});
            // Method 3: Fallback to current window
            window.scrollTo({top: 0, behavior: 'smooth'});
            document.documentElement.scrollTo({top: 0, behavior: 'smooth'});
        } catch(e) {
            // Fallback if cross-origin issues
            window.scrollTo({top: 0, behavior: 'smooth'});
        }
    </script>
    '''
    st.markdown(js, unsafe_allow_html=True)


# Page configuration - MUST be first
st.set_page_config(
    page_title="VidGo AI",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Language options
LANGUAGES = {
    "zh": "中文",
    "en": "English",
    "ja": "日本語",
    "ko": "한국어",
    "es": "Español"
}

# Style tags translations
STYLE_TAGS_TRANSLATIONS = {
    "zh": [
        "視頻", "推薦", "人物寫真", "寫實攝影", "動漫卡通", "海報插畫",
        "動漫二次元", "電商設計", "中國風", "女生", "男生", "室內家居",
        "建築景觀", "玩具手辦", "繪畫藝術", "產品設計", "遊戲CG",
        "自然人文", "3D立體", "logo/UI", "白色背景", "動物植物",
        "玄幻魔幻", "科幻未來"
    ],
    "en": [
        "Video", "Featured", "Portrait", "Photography", "Anime", "Poster",
        "2D Anime", "E-commerce", "Chinese Style", "Female", "Male", "Interior",
        "Architecture", "Toys", "Art", "Product", "Game CG",
        "Nature", "3D", "Logo/UI", "White BG", "Animals",
        "Fantasy", "Sci-Fi"
    ],
    "ja": [
        "動画", "おすすめ", "ポートレート", "写真", "アニメ", "ポスター",
        "2Dアニメ", "EC", "中国風", "女性", "男性", "インテリア",
        "建築", "フィギュア", "アート", "製品", "ゲームCG",
        "自然", "3D", "ロゴ/UI", "白背景", "動物",
        "ファンタジー", "SF"
    ],
    "ko": [
        "비디오", "추천", "인물", "사진", "애니메이션", "포스터",
        "2D애니", "이커머스", "중국풍", "여성", "남성", "인테리어",
        "건축", "피규어", "아트", "제품", "게임CG",
        "자연", "3D", "로고/UI", "흰배경", "동물",
        "판타지", "SF"
    ],
    "es": [
        "Video", "Destacado", "Retrato", "Fotografía", "Anime", "Póster",
        "Anime 2D", "E-commerce", "Estilo Chino", "Mujer", "Hombre", "Interior",
        "Arquitectura", "Juguetes", "Arte", "Producto", "Game CG",
        "Naturaleza", "3D", "Logo/UI", "Fondo Blanco", "Animales",
        "Fantasía", "Sci-Fi"
    ]
}

# Translations
TRANSLATIONS = {
    "zh": {
        "title": "VidGo AI",
        "tagline": "AI產品廣告視頻生成平台",
        "hero_title": "用文字或圖片，創建產品廣告視頻",
        "hero_subtitle": "上傳產品圖片或輸入描述，AI自動生成專業廣告視頻",
        "create_video": "創建產品廣告視頻",
        "text_to_video": "文字生成視頻",
        "image_to_video": "圖片生成視頻",
        "text_to_image": "文字生成圖片",
        "product_video": "產品廣告視頻",
        "share_to_social": "分享到社交媒體",
        "download_video": "下載視頻",
        "watermark_notice": "Demo版本包含浮水印，升級後移除",
        "subscription_page": "訂閱方案",
        "choose_plan": "選擇適合您的方案",
        "monthly": "月付",
        "yearly": "年付 (省20%)",
        "most_popular": "最受歡迎",
        "best_value": "最佳價值",
        "select_plan": "選擇方案",
        "current": "當前方案",
        "features_included": "包含功能",
        "payment_pending": "付款系統即將上線",
        "ai_creation": "AI創作",
        "editing_apps": "編輯工具",
        "video_creation": "視頻創作",
        "architecture": "建築室內",
        "ecommerce": "產品電商",
        "portrait": "人像寫真",
        "my_works": "我的作品",
        "inspiration": "作品靈感",
        "all": "全部",
        "flux_creation": "Flux創作",
        "smart_creation": "智能創作",
        "image_tools": "圖片工具",
        "photo_studio": "照相館",
        "product_ecom": "產品電商",
        "architecture_interior": "建築室內",
        "video_tools": "視頻工具",
        "prompt_desc": "產品描述",
        "enter_prompt": "描述您的產品特點、風格、場景...",
        "ai_continue": "AI優化描述",
        "mode_select": "視頻風格",
        "general_mode": "通用廣告",
        "pro_mode": "電商展示",
        "chinese_enhance": "品牌故事",
        "flux_mode": "創意動態",
        "reference_image": "產品圖片",
        "upload_ref": "上傳產品圖片（推薦）",
        "image_size": "視頻比例",
        "adaptive_size": "自適應",
        "output_count": "生成數量",
        "start_generate": "生成視頻",
        "generating": "AI正在創建您的產品視頻...",
        "use_prompt": "使用此描述",
        "language": "語言",
        "subscribe": "訂閱方案",
        "free_plan": "免費版",
        "pro_plan": "專業版",
        "enterprise_plan": "企業版",
        "current_plan": "當前方案",
        "upgrade": "升級",
        "credits": "點數",
        "unlimited": "無限",
        "login": "登入",
        "register": "註冊",
        "logout": "登出",
        "welcome": "歡迎",
        "guest": "訪客",
        "or": "或",
        "step1": "第一步：上傳產品圖或輸入描述",
        "step2": "第二步：選擇視頻風格",
        "step3": "第三步：AI生成專業視頻",
        "why_choose": "為什麼選擇 VidGo AI？",
        "feature_fast": "快速生成",
        "feature_fast_desc": "60秒內生成專業產品視頻",
        "feature_pro": "專業品質",
        "feature_pro_desc": "媲美專業廣告公司的視頻效果",
        "feature_easy": "簡單易用",
        "feature_easy_desc": "無需視頻編輯經驗，一鍵生成",
        "feature_cost": "成本低廉",
        "feature_cost_desc": "比傳統廣告製作節省90%成本",
        "more_tools": "更多AI工具",
    },
    "en": {
        "title": "VidGo AI",
        "tagline": "AI Product Ads Video Generator",
        "hero_title": "Create Product Ads Videos from Text or Images",
        "hero_subtitle": "Upload product image or describe it, AI generates professional ad videos",
        "create_video": "Create Product Ads Video",
        "text_to_video": "Text to Video",
        "image_to_video": "Image to Video",
        "text_to_image": "Text to Image",
        "product_video": "Product Ads Video",
        "share_to_social": "Share to Social Media",
        "download_video": "Download Video",
        "watermark_notice": "Demo includes watermark, upgrade to remove",
        "subscription_page": "Subscription Plans",
        "choose_plan": "Choose your plan",
        "monthly": "Monthly",
        "yearly": "Yearly (Save 20%)",
        "most_popular": "Most Popular",
        "best_value": "Best Value",
        "select_plan": "Select Plan",
        "current": "Current",
        "features_included": "Features Included",
        "payment_pending": "Payment system coming soon",
        "ai_creation": "AI Creation",
        "editing_apps": "Edit Tools",
        "video_creation": "Video Creation",
        "architecture": "Architecture",
        "ecommerce": "E-commerce",
        "portrait": "Portrait",
        "my_works": "My Works",
        "inspiration": "Inspiration",
        "all": "All",
        "flux_creation": "Flux",
        "smart_creation": "Smart",
        "image_tools": "Image Tools",
        "photo_studio": "Photo Studio",
        "product_ecom": "E-commerce",
        "architecture_interior": "Architecture",
        "video_tools": "Video",
        "prompt_desc": "Product Description",
        "enter_prompt": "Describe your product features, style, scene...",
        "ai_continue": "AI Enhance",
        "mode_select": "Video Style",
        "general_mode": "General Ad",
        "pro_mode": "E-commerce",
        "chinese_enhance": "Brand Story",
        "flux_mode": "Creative",
        "reference_image": "Product Image",
        "upload_ref": "Upload product image (recommended)",
        "image_size": "Video Ratio",
        "adaptive_size": "Adaptive",
        "output_count": "Output Count",
        "start_generate": "Generate Video",
        "generating": "AI is creating your product video...",
        "use_prompt": "Use this",
        "language": "Language",
        "subscribe": "Subscribe",
        "free_plan": "Free",
        "pro_plan": "Pro",
        "enterprise_plan": "Enterprise",
        "current_plan": "Current Plan",
        "upgrade": "Upgrade",
        "credits": "Credits",
        "unlimited": "Unlimited",
        "login": "Login",
        "register": "Register",
        "logout": "Logout",
        "welcome": "Welcome",
        "guest": "Guest",
        "or": "or",
        "step1": "Step 1: Upload image or enter description",
        "step2": "Step 2: Choose video style",
        "step3": "Step 3: AI generates professional video",
        "why_choose": "Why Choose VidGo AI?",
        "feature_fast": "Fast Generation",
        "feature_fast_desc": "Professional product video in 60 seconds",
        "feature_pro": "Professional Quality",
        "feature_pro_desc": "Studio-quality video output",
        "feature_easy": "Easy to Use",
        "feature_easy_desc": "No video editing experience needed",
        "feature_cost": "Cost Effective",
        "feature_cost_desc": "Save 90% vs traditional video production",
        "more_tools": "More AI Tools",
    },
    "ja": {
        "title": "VidGo AI",
        "ai_creation": "AI創作",
        "editing_apps": "編集アプリ",
        "video_creation": "動画作成",
        "architecture": "建築",
        "ecommerce": "EC",
        "portrait": "ポートレート",
        "my_works": "マイワーク",
        "inspiration": "インスピレーション",
        "all": "すべて",
        "prompt_desc": "説明",
        "enter_prompt": "説明を入力",
        "start_generate": "生成",
        "generating": "生成中...",
        "subscribe": "購読",
        "free_plan": "無料",
        "pro_plan": "プロ",
        "enterprise_plan": "企業",
        "current_plan": "現在のプラン",
        "upgrade": "アップグレード",
        "credits": "クレジット",
        "unlimited": "無制限",
        "login": "ログイン",
        "register": "登録",
        "logout": "ログアウト",
        "welcome": "ようこそ",
        "guest": "ゲスト",
    },
    "ko": {
        "title": "VidGo AI",
        "ai_creation": "AI 창작",
        "editing_apps": "편집 앱",
        "video_creation": "비디오 제작",
        "architecture": "건축",
        "ecommerce": "이커머스",
        "portrait": "인물",
        "my_works": "내 작품",
        "inspiration": "영감 갤러리",
        "all": "전체",
        "prompt_desc": "설명",
        "enter_prompt": "설명 입력",
        "start_generate": "생성",
        "generating": "생성 중...",
        "subscribe": "구독",
        "free_plan": "무료",
        "pro_plan": "프로",
        "enterprise_plan": "기업",
        "current_plan": "현재 플랜",
        "upgrade": "업그레이드",
        "credits": "크레딧",
        "unlimited": "무제한",
        "login": "로그인",
        "register": "가입",
        "logout": "로그아웃",
        "welcome": "환영합니다",
        "guest": "게스트",
    },
    "es": {
        "title": "VidGo AI",
        "ai_creation": "Creación IA",
        "editing_apps": "Apps de Edición",
        "video_creation": "Crear Video",
        "architecture": "Arquitectura",
        "ecommerce": "E-commerce",
        "portrait": "Retrato",
        "my_works": "Mis Obras",
        "inspiration": "Galería de Inspiración",
        "all": "Todo",
        "prompt_desc": "Descripción",
        "enter_prompt": "Ingresa descripción",
        "start_generate": "Generar",
        "generating": "Generando...",
        "subscribe": "Suscribirse",
        "free_plan": "Gratis",
        "pro_plan": "Pro",
        "enterprise_plan": "Empresa",
        "current_plan": "Plan Actual",
        "upgrade": "Mejorar",
        "credits": "Créditos",
        "unlimited": "Ilimitado",
        "login": "Iniciar sesión",
        "register": "Registrar",
        "logout": "Cerrar sesión",
        "welcome": "Bienvenido",
        "guest": "Invitado",
    }
}

# Base style tags (Chinese as key for image matching)
STYLE_TAGS_BASE = [
    "視頻", "推薦", "人物寫真", "寫實攝影", "動漫卡通", "海報插畫",
    "動漫二次元", "電商設計", "中國風", "女生", "男生", "室內家居",
    "建築景觀", "玩具手辦", "繪畫藝術", "產品設計", "遊戲CG",
    "自然人文", "3D立體", "logo/UI", "白色背景", "動物植物",
    "玄幻魔幻", "科幻未來"
]

# Sample inspiration images with categories and tags
INSPIRATION_IMAGES = [
    {"url": "https://picsum.photos/seed/img1/300/400", "prompt": "未来城市夜景 cyberpunk", "category": "flux_creation", "tags": ["科幻未來", "3D立體"], "likes": 2453},
    {"url": "https://picsum.photos/seed/img2/300/350", "prompt": "梦幻森林精灵", "category": "flux_creation", "tags": ["玄幻魔幻", "繪畫藝術"], "likes": 1876},
    {"url": "https://picsum.photos/seed/img3/300/300", "prompt": "科幻机器人战士", "category": "flux_creation", "tags": ["科幻未來", "遊戲CG"], "likes": 3201},
    {"url": "https://picsum.photos/seed/img4/300/380", "prompt": "古风仙侠美女", "category": "smart_creation", "tags": ["中國風", "女生", "人物寫真"], "likes": 4532},
    {"url": "https://picsum.photos/seed/img5/300/320", "prompt": "赛博朋克街道", "category": "smart_creation", "tags": ["科幻未來", "3D立體"], "likes": 2108},
    {"url": "https://picsum.photos/seed/img6/300/400", "prompt": "水墨山水画", "category": "smart_creation", "tags": ["中國風", "繪畫藝術", "自然人文"], "likes": 1654},
    {"url": "https://picsum.photos/seed/img7/300/300", "prompt": "高清放大效果", "category": "image_tools", "tags": ["寫實攝影"], "likes": 2987},
    {"url": "https://picsum.photos/seed/img8/300/350", "prompt": "AI抠图背景替换", "category": "image_tools", "tags": ["電商設計", "白色背景"], "likes": 3456},
    {"url": "https://picsum.photos/seed/img9/300/400", "prompt": "AI证件照", "category": "photo_studio", "tags": ["人物寫真", "寫實攝影"], "likes": 1234},
    {"url": "https://picsum.photos/seed/img10/300/380", "prompt": "老照片修复上色", "category": "photo_studio", "tags": ["人物寫真"], "likes": 4123},
    {"url": "https://picsum.photos/seed/img11/300/300", "prompt": "产品白底图", "category": "product_ecom", "tags": ["電商設計", "白色背景", "產品設計"], "likes": 1890},
    {"url": "https://picsum.photos/seed/img12/300/350", "prompt": "场景化产品展示", "category": "product_ecom", "tags": ["電商設計", "產品設計"], "likes": 2567},
    {"url": "https://picsum.photos/seed/img13/300/320", "prompt": "模特试衣效果", "category": "product_ecom", "tags": ["電商設計", "女生"], "likes": 3100},
    {"url": "https://picsum.photos/seed/img14/300/400", "prompt": "现代简约室内", "category": "architecture_interior", "tags": ["室內家居", "3D立體"], "likes": 2800},
    {"url": "https://picsum.photos/seed/img15/300/350", "prompt": "3D建筑渲染", "category": "architecture_interior", "tags": ["建築景觀", "3D立體"], "likes": 3200},
    {"url": "https://picsum.photos/seed/img16/300/300", "prompt": "文生视频效果", "category": "video_tools", "tags": ["視頻"], "likes": 4500},
    {"url": "https://picsum.photos/seed/img17/300/380", "prompt": "图生视频转换", "category": "video_tools", "tags": ["視頻"], "likes": 3800},
    {"url": "https://picsum.photos/seed/img18/300/350", "prompt": "动漫美少女", "category": "smart_creation", "tags": ["動漫卡通", "動漫二次元", "女生"], "likes": 5200},
    {"url": "https://picsum.photos/seed/img19/300/400", "prompt": "游戏角色设计", "category": "smart_creation", "tags": ["遊戲CG", "玄幻魔幻"], "likes": 4100},
    {"url": "https://picsum.photos/seed/img20/300/320", "prompt": "可爱猫咪插画", "category": "smart_creation", "tags": ["動物植物", "動漫卡通"], "likes": 3900},
    {"url": "https://picsum.photos/seed/img21/300/380", "prompt": "海报设计", "category": "smart_creation", "tags": ["海報插畫", "電商設計"], "likes": 2700},
    {"url": "https://picsum.photos/seed/img22/300/300", "prompt": "Logo设计", "category": "image_tools", "tags": ["logo/UI", "產品設計"], "likes": 3100},
    {"url": "https://picsum.photos/seed/img23/300/350", "prompt": "帅气男生写真", "category": "photo_studio", "tags": ["男生", "人物寫真", "寫實攝影"], "likes": 2900},
    {"url": "https://picsum.photos/seed/img24/300/400", "prompt": "玩具手办展示", "category": "product_ecom", "tags": ["玩具手辦", "3D立體"], "likes": 3500},
]

# Auto-detect system language from browser
def detect_system_language():
    """Detect system language preference from browser."""
    # Default mappings for common browser language codes
    lang_mapping = {
        "zh": "zh", "zh-TW": "zh", "zh-CN": "zh", "zh-HK": "zh",
        "en": "en", "en-US": "en", "en-GB": "en",
        "ja": "ja", "ja-JP": "ja",
        "ko": "ko", "ko-KR": "ko",
        "es": "es", "es-ES": "es", "es-MX": "es",
    }
    # Try to get from query params or default to zh
    try:
        # In Streamlit, we can use experimental get_query_params
        params = st.query_params
        if "lang" in params:
            lang = params["lang"]
            return lang_mapping.get(lang, lang) if lang in LANGUAGES else "zh"
    except Exception:
        pass
    return "zh"

# Initialize session state
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Product Ads Video"  # Main feature is Product Ads Video
if 'language' not in st.session_state:
    st.session_state.language = detect_system_language()
if 'inspiration_category' not in st.session_state:
    st.session_state.inspiration_category = "all"
if 'selected_tag' not in st.session_state:
    st.session_state.selected_tag = None
if 'selected_tag_index' not in st.session_state:
    st.session_state.selected_tag_index = None
if 'user_plan' not in st.session_state:
    st.session_state.user_plan = "demo"  # Demo plan (free)
if 'credits' not in st.session_state:
    st.session_state.credits = 2  # Demo users get 2 credits (1 image + 1 video)
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'show_login' not in st.session_state:
    st.session_state.show_login = False
if 'show_register' not in st.session_state:
    st.session_state.show_register = False
if 'selected_tool' not in st.session_state:
    st.session_state.selected_tool = None
if 'tool_category' not in st.session_state:
    st.session_state.tool_category = None

# Get translation
def t(key):
    lang_dict = TRANSLATIONS.get(st.session_state.language, TRANSLATIONS["en"])
    return lang_dict.get(key, TRANSLATIONS["en"].get(key, key))

# Custom CSS for dark theme like DeeVid.ai
st.markdown("""
<style>
    /* Dark theme styling like DeeVid.ai */
    .stApp {
        background: linear-gradient(180deg, #0a0a0f 0%, #12121a 100%);
    }

    /* Globe language selector */
    .language-selector {
        display: flex;
        align-items: center;
        gap: 8px;
        cursor: pointer;
    }

    /* Hero gradient text */
    .hero-gradient {
        background: linear-gradient(90deg, #3CA2F6 0%, #6366f1 50%, #a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    /* Feature cards */
    .feature-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 24px;
        transition: all 0.3s ease;
    }
    .feature-card:hover {
        border-color: #3CA2F6;
        transform: translateY(-4px);
    }

    /* CTA Button styling */
    .cta-button {
        background: linear-gradient(90deg, #3CA2F6 0%, #6366f1 100%);
        color: white;
        padding: 16px 32px;
        border-radius: 12px;
        font-weight: 600;
        text-decoration: none;
        display: inline-block;
        transition: all 0.3s ease;
    }
    .cta-button:hover {
        transform: scale(1.05);
        box-shadow: 0 0 30px rgba(60, 162, 246, 0.4);
    }

    /* Hide default streamlit sidebar header */
    [data-testid="stSidebarNav"] {
        display: none;
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: #0a0a0f;
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }

    /* Video showcase cards */
    .showcase-card {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }
</style>
""", unsafe_allow_html=True)

# Sidebar navigation
with st.sidebar:
    # Logo and brand
    st.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <h1 style="margin: 0; font-size: 28px;">
            <span style="color: #3CA2F6;">VidGo</span> AI
        </h1>
        <p style="color: #888; font-size: 12px; margin-top: 4px;">AI Ad Video Generator</p>
    </div>
    """, unsafe_allow_html=True)

    # Login/Register Section
    if st.session_state.logged_in:
        st.markdown(f"👤 {t('welcome')}, **{st.session_state.username}**")
        if st.button(f"🚪 {t('logout')}", key="logout_btn", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.rerun()
    else:
        login_cols = st.columns(2)
        with login_cols[0]:
            if st.button(f"{t('login')}", key="login_btn", use_container_width=True):
                st.session_state.show_login = True
                st.session_state.show_register = False
                st.rerun()
        with login_cols[1]:
            if st.button(f"{t('register')}", key="register_btn", use_container_width=True, type="primary"):
                st.session_state.show_register = True
                st.session_state.show_login = False
                st.rerun()

    st.markdown("---")

    # Globe Language Selector (like DeeVid.ai)
    st.markdown("🌐", help="Select Language")
    language_options = list(LANGUAGES.values())
    language_codes = list(LANGUAGES.keys())
    current_lang_idx = language_codes.index(st.session_state.language) if st.session_state.language in language_codes else 0
    selected_lang = st.selectbox(
        "Language",
        options=language_options,
        index=current_lang_idx,
        label_visibility="collapsed",
        key="lang_select"
    )
    # Update language if changed
    new_lang_code = language_codes[language_options.index(selected_lang)]
    if new_lang_code != st.session_state.language:
        st.session_state.language = new_lang_code
        st.rerun()

    st.markdown("---")

    # Navigation - Main features
    menu_items = [
        ("🎬", "Product Ads Video", t("product_video") if "product_video" in TRANSLATIONS.get(st.session_state.language, {}) else "Product Ads Video"),
        ("📸", "AI Headshot", "AI 大頭貼" if st.session_state.language == "zh" else "AI Headshot"),
        ("🖼️", "Image to Video", t("image_to_video") if "image_to_video" in TRANSLATIONS.get(st.session_state.language, {}) else "Image to Video"),
        ("✍️", "Text to Video", t("text_to_video") if "text_to_video" in TRANSLATIONS.get(st.session_state.language, {}) else "Text to Video"),
    ]

    for icon, key, label in menu_items:
        btn_type = "primary" if st.session_state.current_page == key else "secondary"
        if st.button(f"{icon} {label}", key=f"nav_{key}", use_container_width=True, type=btn_type):
            st.session_state.current_page = key
            st.rerun()

    st.markdown("---")

    # More Tools Section
    st.markdown(f"**{t('more_tools') if 'more_tools' in TRANSLATIONS.get(st.session_state.language, {}) else 'More Tools'}**")

    more_items = [
        ("🎨", "AI Creation", t("ai_creation")),
        ("✏️", "Editing Apps", t("editing_apps")),
        ("🛒", "E-commerce", t("ecommerce")),
        ("🏠", "Architecture", t("architecture")),
        ("👤", "Portrait", t("portrait")),
    ]

    for icon, key, label in more_items:
        btn_type = "primary" if st.session_state.current_page == key else "secondary"
        if st.button(f"{icon} {label}", key=f"nav_{key}", use_container_width=True, type=btn_type):
            st.session_state.current_page = key
            st.rerun()

    st.markdown("---")

    # Subscription info
    if st.session_state.user_plan == "demo":
        st.caption(f"💎 {t('free_plan')} | {st.session_state.credits} {t('credits')}")
        if st.button(f"⬆️ {t('upgrade')}", key="upgrade_btn", use_container_width=True, type="primary"):
            st.session_state.current_page = "Subscription"
            st.rerun()
    else:
        st.caption(f"⭐ {st.session_state.user_plan.title()} | {st.session_state.credits} {t('credits')}")

    st.markdown("---")
    st.caption("© 2024 VidGo AI")

# Main content based on selection
current = st.session_state.current_page

# ============ LOGIN/REGISTER DIALOGS ============
# Show Login Form
if st.session_state.get('show_login', False):
    scroll_to_top()  # Scroll to top when login form is shown
    st.markdown("---")
    login_container = st.container()
    with login_container:
        col_left, col_center, col_right = st.columns([1, 2, 1])
        with col_center:
            with st.form("login_form", clear_on_submit=False):
                st.markdown(f"### 🔑 {t('login')}")
                login_email = st.text_input("Email", key="login_email_input")
                login_password = st.text_input("Password", type="password", key="login_password_input")

                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    login_submitted = st.form_submit_button(t('login'), use_container_width=True, type="primary")
                with btn_col2:
                    cancel_submitted = st.form_submit_button("Cancel", use_container_width=True)

                if login_submitted:
                    if login_email and login_password:
                        # TODO: Call backend API for authentication
                        st.session_state.logged_in = True
                        st.session_state.username = login_email.split('@')[0]
                        st.session_state.show_login = False
                        st.rerun()
                    else:
                        st.error("Please fill in all fields")

                if cancel_submitted:
                    st.session_state.show_login = False
                    st.rerun()
    st.markdown("---")

# Show Register Form
if st.session_state.get('show_register', False):
    scroll_to_top()  # Scroll to top when register form is shown
    st.markdown("---")
    register_container = st.container()
    with register_container:
        col_left, col_center, col_right = st.columns([1, 2, 1])
        with col_center:
            with st.form("register_form", clear_on_submit=False):
                st.markdown(f"### 📝 {t('register')}")
                reg_email = st.text_input("Email", key="reg_email_input")
                reg_password = st.text_input("Password", type="password", key="reg_password_input")
                reg_confirm = st.text_input("Confirm Password", type="password", key="reg_confirm_input")

                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    register_submitted = st.form_submit_button(t('register'), use_container_width=True, type="primary")
                with btn_col2:
                    cancel_reg_submitted = st.form_submit_button("Cancel", use_container_width=True)

                if register_submitted:
                    if reg_email and reg_password and reg_confirm:
                        if reg_password == reg_confirm:
                            # TODO: Call backend API for registration
                            st.session_state.logged_in = True
                            st.session_state.username = reg_email.split('@')[0]
                            st.session_state.show_register = False
                            st.success("Registration successful!")
                            st.rerun()
                        else:
                            st.error("Passwords do not match")
                    else:
                        st.error("Please fill in all fields")

                if cancel_reg_submitted:
                    st.session_state.show_register = False
                    st.rerun()
    st.markdown("---")

# ============ MAIN FEATURE: Product Ads Video Creation ============
if current == "Product Ads Video":
    # DeeVid.ai Style Hero Section
    hero_title_zh = "AI 廣告影片生成器"
    hero_subtitle_zh = "在幾分鐘內創建高投報率 AI 廣告影片"
    hero_desc_zh = "無需攝影師、無需製作團隊、無需繁瑣的影片剪輯。用AI簡單創建專業產品廣告影片。"

    hero_title_en = "AI Ad Video Generator"
    hero_subtitle_en = "Create high-ROI AI ad videos in minutes"
    hero_desc_en = "No camera, no team, no editing hassle. Create professional product ad videos with AI."

    is_zh = st.session_state.language == "zh"

    st.markdown(f"""
    <div style="text-align: center; padding: 40px 20px 20px 20px;">
        <h1 style="font-size: 48px; font-weight: 700; margin-bottom: 16px;">
            <span class="hero-gradient">{hero_title_zh if is_zh else hero_title_en}</span>
        </h1>
        <p style="font-size: 24px; color: #3CA2F6; margin-bottom: 12px; font-weight: 500;">
            {hero_subtitle_zh if is_zh else hero_subtitle_en}
        </p>
        <p style="font-size: 16px; color: #888; max-width: 600px; margin: 0 auto 30px auto;">
            {hero_desc_zh if is_zh else hero_desc_en}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # CTA Button
    cta_col1, cta_col2, cta_col3 = st.columns([1, 2, 1])
    with cta_col2:
        if st.button(
            f"🚀 {'生成第一支廣告影片' if is_zh else 'Create Your First Ad Video'}",
            type="primary",
            use_container_width=True,
            key="hero_cta"
        ):
            st.session_state.show_creator = True

    st.markdown("<br>", unsafe_allow_html=True)

    # Feature highlights (like DeeVid.ai)
    st.markdown(f"""
    <div style="display: flex; justify-content: center; gap: 40px; margin: 30px 0; flex-wrap: wrap;">
        <div style="text-align: center;">
            <div style="font-size: 32px; margin-bottom: 8px;">⚡</div>
            <div style="color: #fff; font-weight: 500;">{'60秒生成' if is_zh else '60s Generation'}</div>
        </div>
        <div style="text-align: center;">
            <div style="font-size: 32px; margin-bottom: 8px;">🎯</div>
            <div style="color: #fff; font-weight: 500;">{'專業品質' if is_zh else 'Pro Quality'}</div>
        </div>
        <div style="text-align: center;">
            <div style="font-size: 32px; margin-bottom: 8px;">💰</div>
            <div style="color: #fff; font-weight: 500;">{'節省90%成本' if is_zh else 'Save 90%'}</div>
        </div>
        <div style="text-align: center;">
            <div style="font-size: 32px; margin-bottom: 8px;">🎨</div>
            <div style="color: #fff; font-weight: 500;">{'完全創意控制' if is_zh else 'Full Creative Control'}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Two main options: Image to Video, Text to Video (removed Text to Image for simplicity like DeeVid)
    tab1, tab2 = st.tabs([
        f"🖼️ {'圖片轉影片' if is_zh else 'Image to Video'}",
        f"✍️ {'文字轉影片' if is_zh else 'Text to Video'}"
    ])

    with tab1:
        # Image to Video
        st.markdown(f"### {t('step1') if 'step1' in TRANSLATIONS.get(st.session_state.language, {}) else 'Step 1: Upload product image'}")

        col1, col2 = st.columns([2, 1])
        with col1:
            uploaded_file = st.file_uploader(
                t("upload_ref"),
                type=['png', 'jpg', 'jpeg', 'webp'],
                help="Upload your product image for best results"
            )

            if uploaded_file:
                st.image(uploaded_file, caption="Your Product Image", use_container_width=True)

            # Optional description
            st.markdown(f"**{t('prompt_desc')}** (Optional)")
            prompt_img = st.text_area(
                "Additional description",
                height=80,
                placeholder="Add motion effects, camera angles, background...",
                label_visibility="collapsed",
                key="prompt_img"
            )

        with col2:
            st.markdown(f"### {t('step2') if 'step2' in TRANSLATIONS.get(st.session_state.language, {}) else 'Step 2: Choose style'}")
            video_style_img = st.selectbox(
                t("mode_select"),
                [t("general_mode"), t("pro_mode"), t("chinese_enhance") if "chinese_enhance" in TRANSLATIONS.get(st.session_state.language, {}) else "Brand Story", t("flux_mode")],
                label_visibility="collapsed",
                key="style_img"
            )

            st.markdown(f"**{t('image_size')}**")
            ratio_img = st.selectbox("Ratio", ["16:9 (Landscape)", "9:16 (Portrait)", "1:1 (Square)"], label_visibility="collapsed", key="ratio_img")

            st.markdown(f"**{t('output_count')}**")
            count_img = st.number_input("Count", min_value=1, max_value=4, value=1, label_visibility="collapsed", key="count_img")

        st.markdown("---")
        if st.button(f"🎬 {t('start_generate')}", type="primary", use_container_width=True, key="gen_img"):
            if not uploaded_file:
                st.warning("Please upload a product image first!")
            elif st.session_state.credits > 0:
                st.session_state.credits -= 1
                with st.spinner(t("generating")):
                    st.success(t("generating"))
                    st.info("Video will appear here when ready..." + (" (with watermark)" if st.session_state.user_plan == "demo" else ""))

                    # Social Media Sharing Section
                    st.markdown(f"#### 📤 {t('share_to_social') if 'share_to_social' in TRANSLATIONS.get(st.session_state.language, {}) else 'Share to Social Media'}")
                    share_cols = st.columns(5)
                    with share_cols[0]:
                        st.button("📥 Download", key="dl_i2v", use_container_width=True)
                    with share_cols[1]:
                        st.button("📸 Instagram", key="ig_i2v", use_container_width=True)
                    with share_cols[2]:
                        st.button("🎵 TikTok", key="tt_i2v", use_container_width=True)
                    with share_cols[3]:
                        st.button("▶️ YouTube", key="yt_i2v", use_container_width=True)
                    with share_cols[4]:
                        st.button("📘 Facebook", key="fb_i2v", use_container_width=True)
            else:
                st.error("No credits! Please upgrade.")

    with tab2:
        # Text to Video
        st.markdown(f"### {'第一步：描述您的產品' if is_zh else 'Step 1: Describe your product'}")

        col1, col2 = st.columns([2, 1])
        with col1:
            default_prompt = st.session_state.get("selected_prompt", "")
            prompt_text = st.text_area(
                t("prompt_desc"),
                value=default_prompt,
                height=150,
                placeholder="描述您的產品特點、風格、場景..." if is_zh else "Describe your product features, style, scene...",
                key="prompt_t2v"
            )
            st.button(f"🤖 {'AI優化描述' if is_zh else 'AI Enhance'}", key="ai_enhance_text")

        with col2:
            st.markdown(f"### {'第二步：選擇影片風格' if is_zh else 'Step 2: Choose style'}")
            video_style = st.selectbox(
                t("mode_select"),
                [t("general_mode"), t("pro_mode"), t("chinese_enhance") if "chinese_enhance" in TRANSLATIONS.get(st.session_state.language, {}) else "Brand Story", t("flux_mode")],
                label_visibility="collapsed",
                key="style_t2v"
            )

            st.markdown(f"**{'影片比例' if is_zh else 'Video Ratio'}**")
            ratio = st.selectbox("Ratio", ["16:9 (Landscape)", "9:16 (Portrait)", "1:1 (Square)"], label_visibility="collapsed", key="ratio_text")

            st.markdown(f"**{'生成數量' if is_zh else 'Output Count'}**")
            count_text = st.number_input("Count", min_value=1, max_value=4, value=1, label_visibility="collapsed", key="count_text")

        st.markdown("---")
        if st.button(f"🎬 {'生成影片' if is_zh else 'Generate Video'}", type="primary", use_container_width=True, key="gen_text"):
            if st.session_state.credits > 0:
                st.session_state.credits -= 1
                with st.spinner(t("generating")):
                    st.success(t("generating"))
                    st.info(("影片生成中..." if is_zh else "Video will appear here when ready...") + (" (含浮水印)" if st.session_state.user_plan == "demo" and is_zh else " (with watermark)" if st.session_state.user_plan == "demo" else ""))

                    # Social Media Sharing Section
                    st.markdown(f"#### 📤 {'分享到社交媒體' if is_zh else 'Share to Social Media'}")
                    share_cols = st.columns(5)
                    with share_cols[0]:
                        st.button("📥 Download", key="dl_t2v", use_container_width=True)
                    with share_cols[1]:
                        st.button("📸 Instagram", key="ig_t2v", use_container_width=True)
                    with share_cols[2]:
                        st.button("🎵 TikTok", key="tt_t2v", use_container_width=True)
                    with share_cols[3]:
                        st.button("▶️ YouTube", key="yt_t2v", use_container_width=True)
                    with share_cols[4]:
                        st.button("📘 Facebook", key="fb_t2v", use_container_width=True)
            else:
                st.error("No credits! Please upgrade." if not is_zh else "點數不足！請升級。")

    # Why Choose Us Section
    st.markdown("---")
    st.markdown(f"### {t('why_choose') if 'why_choose' in TRANSLATIONS.get(st.session_state.language, {}) else 'Why Choose VidGo AI?'}")

    feat_cols = st.columns(4)
    features = [
        ("⚡", t("feature_fast") if "feature_fast" in TRANSLATIONS.get(st.session_state.language, {}) else "Fast", t("feature_fast_desc") if "feature_fast_desc" in TRANSLATIONS.get(st.session_state.language, {}) else "60 seconds"),
        ("🎯", t("feature_pro") if "feature_pro" in TRANSLATIONS.get(st.session_state.language, {}) else "Professional", t("feature_pro_desc") if "feature_pro_desc" in TRANSLATIONS.get(st.session_state.language, {}) else "Studio quality"),
        ("✨", t("feature_easy") if "feature_easy" in TRANSLATIONS.get(st.session_state.language, {}) else "Easy", t("feature_easy_desc") if "feature_easy_desc" in TRANSLATIONS.get(st.session_state.language, {}) else "No experience needed"),
        ("💰", t("feature_cost") if "feature_cost" in TRANSLATIONS.get(st.session_state.language, {}) else "Affordable", t("feature_cost_desc") if "feature_cost_desc" in TRANSLATIONS.get(st.session_state.language, {}) else "Save 90%"),
    ]
    for idx, (icon, title, desc) in enumerate(features):
        with feat_cols[idx]:
            st.markdown(f"#### {icon} {title}")
            st.caption(desc)

    # Sample Videos / Inspiration - Connected to Backend API
    st.markdown("---")
    st.markdown(f"### ✨ {t('inspiration')}")
    st.caption("See the full workflow: Image → Prompt → Video (auto-plays on scroll)" if st.session_state.language != "zh" else "查看完整流程：圖片 → 提示詞 → 視頻（滾動自動播放）")

    # Fetch showcases from backend API
    # Note: tool_id "product_design" matches seed_tool_showcases.py
    product_showcases = fetch_tool_showcases("ecommerce", "product_design", limit=5)

    if product_showcases:
        for idx, showcase in enumerate(product_showcases):
            with st.container():
                st.markdown(f"#### {showcase.get('title_zh') if st.session_state.language == 'zh' else showcase.get('title', f'Example {idx+1}')}")

                # Three-column flow: Source Image → Prompt → Result Video
                flow_cols = st.columns([1, 1, 2])

                with flow_cols[0]:
                    st.markdown("**1. Source Image**" if st.session_state.language != "zh" else "**1. 原始圖片**")
                    source_img = showcase.get("source_image_url")
                    if source_img:
                        st.image(source_img, use_container_width=True)

                with flow_cols[1]:
                    st.markdown("**2. Prompt**" if st.session_state.language != "zh" else "**2. 提示詞**")
                    prompt_text = showcase.get("prompt_zh") if st.session_state.language == "zh" else showcase.get("prompt", "")
                    st.info(prompt_text)

                    # Style tags
                    tags = showcase.get("style_tags", [])
                    if tags:
                        st.markdown(" ".join([f"`{tag}`" for tag in tags[:4]]))

                with flow_cols[2]:
                    st.markdown("**3. Generated Video**" if st.session_state.language != "zh" else "**3. 生成視頻**")
                    render_showcase_result(showcase, height=200, lang=st.session_state.language)

                # Use this style button
                if st.button(f"📋 Use This Style" if st.session_state.language != "zh" else "📋 使用此風格", key=f"use_showcase_{idx}", use_container_width=False):
                    st.session_state.selected_prompt = showcase.get("prompt", "")
                    st.rerun()

                st.markdown("---")
    else:
        # Fallback if API fails
        st.info("Loading showcases..." if st.session_state.language != "zh" else "載入展示中...")
        sample_cols = st.columns(4)
        samples = [
            {"url": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=400", "title": "Luxury Watch", "style": "E-commerce"},
            {"url": "https://images.unsplash.com/photo-1541643600914-78b084683601?w=400", "title": "Perfume Ad", "style": "Romantic"},
            {"url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=400", "title": "Sneaker", "style": "Dynamic"},
            {"url": "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=400", "title": "Coffee", "style": "Lifestyle"},
        ]
        for idx, sample in enumerate(samples):
            with sample_cols[idx]:
                st.image(sample["url"], use_container_width=True)
                st.caption(f"**{sample['title']}**")
                st.caption(f"Style: {sample['style']}")

# ============ AI HEADSHOT (Professional Portrait Generator) ============
elif current == "AI Headshot":
    is_zh = st.session_state.language == "zh"

    # Hero Section for AI Headshot
    st.markdown(f"""
    <div style="text-align: center; padding: 40px 20px 20px 20px;">
        <h1 style="font-size: 42px; font-weight: 700; margin-bottom: 16px;">
            <span class="hero-gradient">{'AI 專業大頭貼生成器' if is_zh else 'AI Professional Headshot Generator'}</span>
        </h1>
        <p style="font-size: 20px; color: #3CA2F6; margin-bottom: 12px; font-weight: 500;">
            {'10分鐘內獲得專業級大頭貼' if is_zh else 'Get Professional Headshots in 10 Minutes'}
        </p>
        <p style="font-size: 16px; color: #888; max-width: 600px; margin: 0 auto 30px auto;">
            {'上傳您的照片，AI自動生成專業商務大頭貼。適用於LinkedIn、履歷、社交媒體等。' if is_zh else 'Upload your photo, AI generates professional business headshots. Perfect for LinkedIn, resume, social media.'}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Feature highlights
    st.markdown(f"""
    <div style="display: flex; justify-content: center; gap: 40px; margin: 20px 0 40px 0; flex-wrap: wrap;">
        <div style="text-align: center;">
            <div style="font-size: 28px; margin-bottom: 8px;">⚡</div>
            <div style="color: #fff; font-weight: 500;">{'10分鐘完成' if is_zh else '10 Min'}</div>
        </div>
        <div style="text-align: center;">
            <div style="font-size: 28px; margin-bottom: 8px;">👔</div>
            <div style="color: #fff; font-weight: 500;">{'商務專業' if is_zh else 'Business Pro'}</div>
        </div>
        <div style="text-align: center;">
            <div style="font-size: 28px; margin-bottom: 8px;">🎨</div>
            <div style="color: #fff; font-weight: 500;">{'多種風格' if is_zh else 'Multiple Styles'}</div>
        </div>
        <div style="text-align: center;">
            <div style="font-size: 28px; margin-bottom: 8px;">💼</div>
            <div style="color: #fff; font-weight: 500;">{'LinkedIn適用' if is_zh else 'LinkedIn Ready'}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Main upload and generation area
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown(f"### {'📷 上傳您的照片' if is_zh else '📷 Upload Your Photo'}")
        st.caption("{'建議使用正面清晰的照片，光線充足' if is_zh else 'Use a clear front-facing photo with good lighting'}" if is_zh else "Use a clear front-facing photo with good lighting")

        uploaded_headshot = st.file_uploader(
            "上傳照片" if is_zh else "Upload Photo",
            type=['png', 'jpg', 'jpeg'],
            help="支援 JPG, PNG 格式" if is_zh else "Supports JPG, PNG formats",
            key="headshot_upload"
        )

        if uploaded_headshot:
            st.image(uploaded_headshot, caption="您的照片" if is_zh else "Your Photo", use_container_width=True)

    with col2:
        st.markdown(f"### {'🎨 選擇風格' if is_zh else '🎨 Choose Style'}")

        # Style options
        headshot_styles = {
            "business": ("👔", "商務正式" if is_zh else "Business Formal", "專業西裝，適合LinkedIn和履歷" if is_zh else "Professional suit, perfect for LinkedIn"),
            "creative": ("🎨", "創意休閒" if is_zh else "Creative Casual", "輕鬆自然，適合創意產業" if is_zh else "Relaxed natural, for creative industries"),
            "corporate": ("🏢", "企業形象" if is_zh else "Corporate", "正式企業風格" if is_zh else "Formal corporate style"),
            "startup": ("🚀", "新創風格" if is_zh else "Startup Style", "現代科技感" if is_zh else "Modern tech vibe"),
        }

        if "headshot_style" not in st.session_state:
            st.session_state.headshot_style = "business"

        style_cols = st.columns(2)
        for idx, (style_key, (icon, name, desc)) in enumerate(headshot_styles.items()):
            with style_cols[idx % 2]:
                btn_type = "primary" if st.session_state.headshot_style == style_key else "secondary"
                if st.button(f"{icon} {name}", key=f"hs_style_{style_key}", use_container_width=True, type=btn_type):
                    st.session_state.headshot_style = style_key
                    st.rerun()
                st.caption(desc)

        st.markdown("---")

        # Background options
        st.markdown(f"**{'背景顏色' if is_zh else 'Background Color'}**")
        bg_options = ["純白" if is_zh else "White", "淺灰" if is_zh else "Light Gray", "深藍" if is_zh else "Navy Blue", "漸層" if is_zh else "Gradient"]
        bg_color = st.selectbox("Background", bg_options, label_visibility="collapsed", key="hs_bg")

        # Output count
        st.markdown(f"**{'生成數量' if is_zh else 'Number of Photos'}**")
        hs_count = st.number_input("Count", min_value=1, max_value=8, value=4, label_visibility="collapsed", key="hs_count")

    st.markdown("---")

    # Generate button
    gen_col1, gen_col2, gen_col3 = st.columns([1, 2, 1])
    with gen_col2:
        if st.button(
            f"📸 {'生成專業大頭貼' if is_zh else 'Generate Professional Headshots'}",
            type="primary",
            use_container_width=True,
            key="gen_headshot"
        ):
            if not uploaded_headshot:
                st.warning("請先上傳照片！" if is_zh else "Please upload a photo first!")
            elif st.session_state.credits > 0:
                st.session_state.credits -= 1
                with st.spinner("AI正在生成您的專業大頭貼..." if is_zh else "AI is generating your professional headshots..."):
                    # Demo output
                    st.success("生成完成！" if is_zh else "Generation complete!")

                    # Show demo results
                    st.markdown(f"### {'生成結果' if is_zh else 'Generated Results'}")
                    result_cols = st.columns(4)
                    demo_headshots = [
                        "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=300&h=300&fit=crop",
                        "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=300&h=300&fit=crop",
                        "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=300&h=300&fit=crop",
                        "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=300&h=300&fit=crop",
                    ]
                    for idx, img_url in enumerate(demo_headshots):
                        with result_cols[idx]:
                            st.image(img_url, use_container_width=True)
                            st.button("📥", key=f"dl_hs_{idx}", help="Download" if not is_zh else "下載")

                    # Download all button
                    st.button(
                        f"📥 {'下載全部' if is_zh else 'Download All'}",
                        use_container_width=True,
                        key="dl_all_hs"
                    )
            else:
                st.error("點數不足！請升級方案。" if is_zh else "No credits! Please upgrade.")

    # Sample results section
    st.markdown("---")
    st.markdown(f"### {'✨ 範例展示' if is_zh else '✨ Sample Results'}")
    st.caption("AI生成的專業大頭貼範例" if is_zh else "Examples of AI-generated professional headshots")

    sample_cols = st.columns(6)
    sample_headshots = [
        {"url": "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=200&h=200&fit=crop", "style": "Business"},
        {"url": "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=200&h=200&fit=crop", "style": "Creative"},
        {"url": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=200&h=200&fit=crop", "style": "Corporate"},
        {"url": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=200&h=200&fit=crop", "style": "Startup"},
        {"url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=200&h=200&fit=crop", "style": "Business"},
        {"url": "https://images.unsplash.com/photo-1573497019940-1c28c88b4f3e?w=200&h=200&fit=crop", "style": "Creative"},
    ]
    for idx, sample in enumerate(sample_headshots):
        with sample_cols[idx]:
            st.image(sample["url"], use_container_width=True)
            st.caption(sample["style"])

# ============ AI Creation (Supplementary) ============
elif current == "AI Creation":
    st.header(f"🎨 {t('ai_creation')}")
    st.caption(f"{t('more_tools') if 'more_tools' in TRANSLATIONS.get(st.session_state.language, {}) else 'More AI creative tools'}")

    col1, col2 = st.columns([2, 1])

    # Initialize video style state if not exists
    if "ai_creation_style" not in st.session_state:
        st.session_state.ai_creation_style = "general"

    with col1:
        st.subheader(t("prompt_desc"))
        default_prompt = st.session_state.get("selected_prompt", "")
        prompt = st.text_area(t("enter_prompt"), value=default_prompt, height=120,
                              placeholder="Describe what you want to create...")

        st.button(f"🤖 {t('ai_continue')}")

        st.subheader(t("mode_select"))
        c1, c2, c3, c4 = st.columns(4)

        # Video style buttons with state tracking
        style_options = [
            ("general", t("general_mode")),
            ("pro", t("pro_mode")),
            ("chinese", t("chinese_enhance") if "chinese_enhance" in TRANSLATIONS.get(st.session_state.language, {}) else "CN+"),
            ("flux", t("flux_mode"))
        ]

        with c1:
            if st.button(style_options[0][1], type="primary" if st.session_state.ai_creation_style == "general" else "secondary", use_container_width=True, key="style_general"):
                st.session_state.ai_creation_style = "general"
                st.rerun()
        with c2:
            if st.button(style_options[1][1], type="primary" if st.session_state.ai_creation_style == "pro" else "secondary", use_container_width=True, key="style_pro"):
                st.session_state.ai_creation_style = "pro"
                st.rerun()
        with c3:
            if st.button(style_options[2][1], type="primary" if st.session_state.ai_creation_style == "chinese" else "secondary", use_container_width=True, key="style_chinese"):
                st.session_state.ai_creation_style = "chinese"
                st.rerun()
        with c4:
            if st.button(style_options[3][1], type="primary" if st.session_state.ai_creation_style == "flux" else "secondary", use_container_width=True, key="style_flux"):
                st.session_state.ai_creation_style = "flux"
                st.rerun()

        st.subheader(t("reference_image"))
        st.file_uploader(t("upload_ref"), type=['png', 'jpg', 'jpeg'])

    with col2:
        st.subheader(t("image_size"))
        st.selectbox("Size", [t("adaptive_size"), "1:1", "16:9", "9:16", "4:3"], label_visibility="collapsed")

        st.subheader(t("output_count"))
        st.number_input("Count", min_value=1, max_value=4, value=1, label_visibility="collapsed")

        st.markdown("---")
        if st.button(f"🎨 {t('start_generate')}", type="primary", use_container_width=True):
            if st.session_state.credits > 0:
                st.session_state.credits -= 1
                st.success(t("generating"))
            else:
                st.error("No credits remaining! Please upgrade your plan.")

    # Inspiration Gallery Section - Connected to Backend API
    st.markdown("---")
    st.markdown(f"## ✨ {t('inspiration')}")

    # Topic category translations
    topic_labels = {
        "all": {"zh": "全部", "en": "All"},
        "product": {"zh": "產品", "en": "Product"},
        "food": {"zh": "美食", "en": "Food"},
        "fashion": {"zh": "時尚", "en": "Fashion"},
        "interior": {"zh": "室內設計", "en": "Interior"},
        "portrait": {"zh": "人像", "en": "Portrait"},
        "art": {"zh": "藝術", "en": "Art"},
        "video": {"zh": "視頻", "en": "Video"},
    }

    # Topic categories from backend
    categories = [
        ("all", topic_labels["all"].get(st.session_state.language, "All")),
        ("product", topic_labels["product"].get(st.session_state.language, "Product")),
        ("food", topic_labels["food"].get(st.session_state.language, "Food")),
        ("fashion", topic_labels["fashion"].get(st.session_state.language, "Fashion")),
        ("interior", topic_labels["interior"].get(st.session_state.language, "Interior")),
        ("portrait", topic_labels["portrait"].get(st.session_state.language, "Portrait")),
        ("art", topic_labels["art"].get(st.session_state.language, "Art")),
        ("video", topic_labels["video"].get(st.session_state.language, "Video")),
    ]

    cat_cols = st.columns(len(categories))
    for idx, (cat_key, cat_label) in enumerate(categories):
        with cat_cols[idx]:
            btn_type = "primary" if st.session_state.inspiration_category == cat_key else "secondary"
            if st.button(cat_label, key=f"cat_{cat_key}", use_container_width=True, type=btn_type):
                st.session_state.inspiration_category = cat_key
                st.session_state.selected_tag_index = None
                st.rerun()

    st.markdown("")

    # Fetch examples from backend API
    current_topic = st.session_state.inspiration_category if st.session_state.inspiration_category != "all" else None
    api_examples = fetch_inspiration_examples(topic=current_topic, limit=30)

    # Show API connection status
    if hasattr(st.session_state, 'api_error') and st.session_state.api_error:
        st.warning(f"Using cached data. API: {st.session_state.api_error}")

    # Display examples in masonry-style grid (5 columns)
    if api_examples:
        cols = st.columns(5)
        for idx, example in enumerate(api_examples):
            with cols[idx % 5]:
                # Display image
                img_url = example.get("image_url") or example.get("thumbnail_url")
                if img_url:
                    st.image(img_url, use_container_width=True)

                # Title and prompt
                title = example.get("title", "")
                if st.session_state.language == "zh" and example.get("title_zh"):
                    title = example.get("title_zh")
                st.caption(f"**{title}**" if title else "")

                prompt = example.get("prompt", "")
                if len(prompt) > 50:
                    prompt = prompt[:50] + "..."
                st.caption(f"📝 {prompt}")

                # Style tags
                tags = example.get("style_tags", [])
                if tags:
                    tag_text = " ".join([f"`{t}`" for t in tags[:3]])
                    st.markdown(tag_text, unsafe_allow_html=True)

                # Action buttons
                col_a, col_b = st.columns(2)
                with col_a:
                    # Random popularity for demo
                    likes = random.randint(100, 5000)
                    st.button(f"❤️ {likes}", key=f"like_{idx}", use_container_width=True)
                with col_b:
                    if st.button("📋 Use", key=f"use_{idx}", use_container_width=True, help=t("use_prompt")):
                        st.session_state.selected_prompt = example.get("prompt", "")
                        st.rerun()
                st.markdown("")
    else:
        # Fallback to static examples if API fails
        st.info("Loading examples..." if st.session_state.language != "zh" else "載入中...")
        fallback_examples = [
            {"url": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=400", "title": "Luxury Watch", "prompt": "Luxury watch with golden details on black velvet"},
            {"url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400", "title": "Premium Headphones", "prompt": "Premium wireless headphones on marble surface"},
            {"url": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=400", "title": "Gourmet Burger", "prompt": "Gourmet burger with melting cheese and fresh vegetables"},
            {"url": "https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?w=400", "title": "Living Room", "prompt": "Modern minimalist living room with natural light"},
            {"url": "https://images.unsplash.com/photo-1541701494587-cb58502866ab?w=400", "title": "Abstract Art", "prompt": "Abstract digital art with vibrant colors"},
        ]
        cols = st.columns(5)
        for idx, ex in enumerate(fallback_examples):
            with cols[idx % 5]:
                st.image(ex["url"], use_container_width=True)
                st.caption(f"**{ex['title']}**")
                st.caption(f"📝 {ex['prompt']}")
                if st.button("📋 Use", key=f"fallback_use_{idx}", use_container_width=True):
                    st.session_state.selected_prompt = ex["prompt"]
                    st.rerun()

elif current == "Editing Apps":
    # Check if a tool is selected
    if st.session_state.selected_tool and st.session_state.tool_category == "edit":
        # Tool detail page
        tool = st.session_state.selected_tool

        # Back button
        if st.button("← Back" if st.session_state.language != "zh" else "← 返回", key="back_edit"):
            st.session_state.selected_tool = None
            st.session_state.tool_category = None
            st.rerun()

        st.header(f"{tool['icon']} {tool['label_zh'] if st.session_state.language == 'zh' else tool['label_en']}")
        st.markdown("---")

        # Tool interface
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown(f"### {'上傳圖片' if st.session_state.language == 'zh' else 'Upload Image'}")
            uploaded = st.file_uploader(
                "Upload" if st.session_state.language != "zh" else "上傳",
                type=['png', 'jpg', 'jpeg', 'webp'],
                key=f"upload_{tool['id']}"
            )
            if uploaded:
                st.image(uploaded, caption="Your Image", use_container_width=True)

            # Tool-specific options
            if tool['id'] == 'hd_upscale':
                st.markdown(f"### {'放大倍數' if st.session_state.language == 'zh' else 'Upscale Factor'}")
                scale = st.select_slider("Scale", options=["2x", "4x", "8x"], value="4x")
            elif tool['id'] == 'change_bg':
                st.markdown(f"### {'選擇背景' if st.session_state.language == 'zh' else 'Choose Background'}")
                bg_type = st.radio("Background", ["White", "Transparent", "Custom Color", "Upload"], horizontal=True)
                if bg_type == "Custom Color":
                    st.color_picker("Color", "#ffffff")
            elif tool['id'] == 'ai_cutout':
                st.markdown(f"### {'摳圖模式' if st.session_state.language == 'zh' else 'Cutout Mode'}")
                mode = st.radio("Mode", ["Auto", "Portrait", "Product", "Object"], horizontal=True)

        with col2:
            st.markdown(f"### {'使用說明' if st.session_state.language == 'zh' else 'How to Use'}")
            instructions = {
                'universal_edit': ["1. Upload your image", "2. Describe what to change", "3. Click Generate"],
                'hd_upscale': ["1. Upload image (max 5MB)", "2. Select upscale factor", "3. Click Enhance"],
                'ai_cutout': ["1. Upload image", "2. Select mode", "3. AI auto-removes background"],
                'change_bg': ["1. Upload image", "2. Choose new background", "3. Click Apply"],
                'photo_cartoon': ["1. Upload portrait photo", "2. Select cartoon style", "3. Click Transform"],
                'ai_expand': ["1. Upload image", "2. Select expansion direction", "3. AI fills the gaps"],
            }
            for step in instructions.get(tool['id'], ["Upload image", "Configure settings", "Generate"]):
                st.markdown(f"• {step}")

            st.markdown("---")
            st.markdown(f"**{'消耗點數' if st.session_state.language == 'zh' else 'Credits Cost'}**: {tool.get('credits', 3)}")

        st.markdown("---")
        if st.button(f"🚀 {'開始處理' if st.session_state.language == 'zh' else 'Process'}", type="primary", use_container_width=True):
            if not uploaded:
                st.warning("Please upload an image first!" if st.session_state.language != "zh" else "請先上傳圖片！")
            elif st.session_state.credits > 0:
                st.session_state.credits -= tool.get('credits', 3)
                with st.spinner("Processing..." if st.session_state.language != "zh" else "處理中..."):
                    st.success("Done!" if st.session_state.language != "zh" else "完成！")
                    st.image("https://picsum.photos/seed/result1/800/600", caption="Result", use_container_width=True)
            else:
                st.error("No credits! Please upgrade." if st.session_state.language != "zh" else "點數不足！請升級方案。")
    else:
        # Tool list page
        st.header(f"✏️ {t('editing_apps')}")
        st.caption("Professional image editing tools powered by AI" if st.session_state.language != "zh" else "專業AI圖片編輯工具")

        st.markdown("---")

        cols = st.columns(3)
        edit_tools = [
            {"id": "universal_edit", "icon": "🔧", "label_zh": "萬能改圖", "label_en": "Universal Edit", "desc_zh": "AI智能修改圖片任意細節", "desc_en": "AI-powered image editing", "credits": 5},
            {"id": "hd_upscale", "icon": "🔍", "label_zh": "高清放大", "label_en": "HD Upscale", "desc_zh": "圖片清晰度提升至4K/8K", "desc_en": "Enhance image to 4K/8K quality", "credits": 3},
            {"id": "ai_cutout", "icon": "✂️", "label_zh": "AI摳圖", "label_en": "AI Cutout", "desc_zh": "一鍵去除背景", "desc_en": "Remove background instantly", "credits": 2},
            {"id": "change_bg", "icon": "🖼️", "label_zh": "換背景", "label_en": "Change BG", "desc_zh": "更換任意背景顏色或圖片", "desc_en": "Replace background with any color or image", "credits": 3},
            {"id": "photo_cartoon", "icon": "🎭", "label_zh": "真人轉漫畫", "label_en": "Photo to Cartoon", "desc_zh": "將照片轉換為各種漫畫風格", "desc_en": "Transform photos to cartoon styles", "credits": 4},
            {"id": "ai_expand", "icon": "📐", "label_zh": "AI擴圖", "label_en": "AI Expand", "desc_zh": "智能擴展圖片邊界", "desc_en": "Intelligently expand image borders", "credits": 4},
        ]
        for i, tool in enumerate(edit_tools):
            label = tool['label_zh'] if st.session_state.language == "zh" else tool['label_en']
            desc = tool['desc_zh'] if st.session_state.language == "zh" else tool['desc_en']
            with cols[i % 3]:
                st.markdown(f"### {tool['icon']} {label}")
                st.caption(desc)
                st.caption(f"💰 {tool['credits']} credits")
                if st.button("Open" if st.session_state.language != "zh" else "開啟", key=f"edit_{i}", use_container_width=True):
                    st.session_state.selected_tool = tool
                    st.session_state.tool_category = "edit"
                    st.rerun()
                st.markdown("")

        # Showcase Examples from API
        st.markdown("---")
        st.markdown(f"### ✨ {'範例展示' if st.session_state.language == 'zh' else 'Examples'}")

        edit_showcases = fetch_tool_showcases("edit_tools", limit=6)
        if edit_showcases:
            showcase_cols = st.columns(3)
            for idx, showcase in enumerate(edit_showcases):
                with showcase_cols[idx % 3]:
                    # Before/After flow
                    st.markdown(f"**{showcase.get('title_zh') if st.session_state.language == 'zh' else showcase.get('title', '')}**")

                    before_after = st.columns(2)
                    with before_after[0]:
                        st.caption("Before" if st.session_state.language != "zh" else "原圖")
                        if showcase.get("source_image_url"):
                            st.image(showcase["source_image_url"], use_container_width=True)
                    with before_after[1]:
                        st.caption("After" if st.session_state.language != "zh" else "效果")
                        render_showcase_result(showcase, height=180, lang=st.session_state.language)

                    # Prompt
                    prompt = showcase.get("prompt_zh") if st.session_state.language == "zh" else showcase.get("prompt", "")
                    if len(prompt) > 60:
                        prompt = prompt[:60] + "..."
                    st.caption(f"📝 {prompt}")
                    st.markdown("")

elif current == "Video Creation":
    st.header(f"🎬 {t('video_creation')}")
    cols = st.columns(3)
    features = [
        ("🎬", "文生視頻", "Text to Video"),
        ("🖼️", "圖生視頻", "Image to Video"),
        ("✨", "視頻特效", "Video Effects"),
        ("📈", "視頻增強", "Video Upscale"),
    ]
    for i, (icon, label_zh, label_en) in enumerate(features):
        label = label_zh if st.session_state.language == "zh" else label_en
        with cols[i % 3]:
            st.markdown(f"### {icon} {label}")
            st.button("Open" if st.session_state.language != "zh" else "開啟", key=f"video_{i}", use_container_width=True)

elif current == "Architecture":
    # Check if a tool is selected
    if st.session_state.selected_tool and st.session_state.tool_category == "arch":
        tool = st.session_state.selected_tool

        if st.button("← Back" if st.session_state.language != "zh" else "← 返回", key="back_arch"):
            st.session_state.selected_tool = None
            st.session_state.tool_category = None
            st.rerun()

        st.header(f"{tool['icon']} {tool['label_zh'] if st.session_state.language == 'zh' else tool['label_en']}")
        st.markdown("---")

        col1, col2 = st.columns([2, 1])

        with col1:
            if tool['id'] in ['ai_concept', '3d_render', 'style_convert']:
                st.markdown(f"### {'上傳草圖或照片' if st.session_state.language == 'zh' else 'Upload Sketch or Photo'}")
                uploaded = st.file_uploader("Upload", type=['png', 'jpg', 'jpeg', 'webp'], key=f"upload_{tool['id']}")
                if uploaded:
                    st.image(uploaded, caption="Your Input", use_container_width=True)
            else:
                st.markdown(f"### {'上傳平面圖' if st.session_state.language == 'zh' else 'Upload Floor Plan'}")
                uploaded = st.file_uploader("Upload", type=['png', 'jpg', 'jpeg', 'webp', 'pdf'], key=f"upload_{tool['id']}")
                if uploaded:
                    st.image(uploaded, caption="Your Floor Plan", use_container_width=True)

            # Tool-specific options
            if tool['id'] == 'ai_concept':
                st.markdown(f"### {'概念描述' if st.session_state.language == 'zh' else 'Concept Description'}")
                concept = st.text_area("Describe your vision", placeholder="e.g., Modern minimalist villa with floor-to-ceiling windows...")
                st.markdown(f"### {'建築風格' if st.session_state.language == 'zh' else 'Architecture Style'}")
                arch_style = st.selectbox("Style", ["Modern", "Contemporary", "Traditional", "Industrial", "Scandinavian", "Japanese"])
            elif tool['id'] == '3d_render':
                st.markdown(f"### {'渲染設置' if st.session_state.language == 'zh' else 'Render Settings'}")
                render_style = st.selectbox("Render Style", ["Photorealistic", "Sketch", "Watercolor", "Technical"])
                lighting = st.select_slider("Time of Day", options=["Dawn", "Morning", "Noon", "Sunset", "Night"])
            elif tool['id'] == 'style_convert':
                st.markdown(f"### {'目標風格' if st.session_state.language == 'zh' else 'Target Style'}")
                target_style = st.selectbox("Convert to", ["Modern", "Art Deco", "Victorian", "Minimalist", "Industrial", "Mediterranean"])
            elif tool['id'] == 'floor_plan':
                st.markdown(f"### {'輸出選項' if st.session_state.language == 'zh' else 'Output Options'}")
                output_type = st.radio("Output Type", ["2D Colored", "3D View", "Furniture Layout"], horizontal=True)

        with col2:
            st.markdown(f"### {'使用說明' if st.session_state.language == 'zh' else 'How to Use'}")
            instructions = {
                'ai_concept': ["1. Upload sketch/photo", "2. Describe your vision", "3. AI generates concept"],
                '3d_render': ["1. Upload design image", "2. Set render options", "3. Get photorealistic render"],
                'style_convert': ["1. Upload building photo", "2. Select target style", "3. See transformation"],
                'floor_plan': ["1. Upload floor plan", "2. Select output type", "3. Get enhanced visualization"],
            }
            for step in instructions.get(tool['id'], ["Upload", "Configure", "Generate"]):
                st.markdown(f"• {step}")

            st.markdown("---")
            st.markdown(f"**{'消耗點數' if st.session_state.language == 'zh' else 'Credits Cost'}**: {tool.get('credits', 8)}")

            st.markdown(f"### {'範例' if st.session_state.language == 'zh' else 'Examples'}")
            st.image(f"https://picsum.photos/seed/arch{tool['id']}/200/150", use_container_width=True)

        st.markdown("---")
        if st.button(f"🚀 {'生成' if st.session_state.language == 'zh' else 'Generate'}", type="primary", use_container_width=True):
            if not uploaded:
                st.warning("Please upload an image!" if st.session_state.language != "zh" else "請先上傳圖片！")
            elif st.session_state.credits > 0:
                st.session_state.credits -= tool.get('credits', 8)
                with st.spinner("Rendering..." if st.session_state.language != "zh" else "渲染中..."):
                    st.success("Done!" if st.session_state.language != "zh" else "完成！")
                    st.image("https://picsum.photos/seed/archresult/800/500", caption="Result", use_container_width=True)
            else:
                st.error("No credits!" if st.session_state.language != "zh" else "點數不足！")
    else:
        st.header(f"🏠 {t('architecture')}")
        st.caption("Architecture & interior design tools" if st.session_state.language != "zh" else "建築室內設計工具")
        st.markdown("---")

        cols = st.columns(3)
        arch_tools = [
            {"id": "ai_concept", "icon": "🏗️", "label_zh": "AI概念圖", "label_en": "AI Concept", "desc_zh": "從草圖生成建築概念效果圖", "desc_en": "Generate concept from sketch", "credits": 8},
            {"id": "3d_render", "icon": "🎯", "label_zh": "3D渲染", "label_en": "3D Render", "desc_zh": "將設計轉換為逼真3D效果圖", "desc_en": "Convert design to photorealistic 3D", "credits": 10},
            {"id": "style_convert", "icon": "🎨", "label_zh": "風格轉換", "label_en": "Style Convert", "desc_zh": "將建築轉換為不同風格", "desc_en": "Transform to different architectural style", "credits": 6},
            {"id": "floor_plan", "icon": "📐", "label_zh": "彩平圖", "label_en": "Floor Plan", "desc_zh": "美化平面圖並添加家具佈局", "desc_en": "Enhance floor plans with furniture", "credits": 5},
        ]
        for i, tool in enumerate(arch_tools):
            label = tool['label_zh'] if st.session_state.language == "zh" else tool['label_en']
            desc = tool['desc_zh'] if st.session_state.language == "zh" else tool['desc_en']
            with cols[i % 3]:
                st.markdown(f"### {tool['icon']} {label}")
                st.caption(desc)
                st.caption(f"💰 {tool['credits']} credits")
                if st.button("Open" if st.session_state.language != "zh" else "開啟", key=f"arch_{i}", use_container_width=True):
                    st.session_state.selected_tool = tool
                    st.session_state.tool_category = "arch"
                    st.rerun()
                st.markdown("")

        # Showcase Examples from API
        st.markdown("---")
        st.markdown(f"### ✨ {'範例展示' if st.session_state.language == 'zh' else 'Examples'}")

        arch_showcases = fetch_tool_showcases("architecture", limit=6)
        if arch_showcases:
            for idx, showcase in enumerate(arch_showcases):
                with st.container():
                    st.markdown(f"#### {showcase.get('title_zh') if st.session_state.language == 'zh' else showcase.get('title', f'Example {idx+1}')}")

                    flow_cols = st.columns([1, 1, 2])
                    with flow_cols[0]:
                        st.markdown("**Original**" if st.session_state.language != "zh" else "**原圖**")
                        if showcase.get("source_image_url"):
                            st.image(showcase["source_image_url"], use_container_width=True)

                    with flow_cols[1]:
                        st.markdown("**Prompt**" if st.session_state.language != "zh" else "**描述**")
                        prompt_text = showcase.get("prompt_zh") if st.session_state.language == "zh" else showcase.get("prompt", "")
                        st.info(prompt_text)
                        tags = showcase.get("style_tags", [])
                        if tags:
                            st.markdown(" ".join([f"`{tag}`" for tag in tags[:3]]))

                    with flow_cols[2]:
                        st.markdown("**Result**" if st.session_state.language != "zh" else "**效果**")
                        render_showcase_result(showcase, height=180, lang=st.session_state.language)

                    st.markdown("---")

elif current == "E-commerce":
    # Check if a tool is selected
    if st.session_state.selected_tool and st.session_state.tool_category == "ecom":
        tool = st.session_state.selected_tool

        if st.button("← Back" if st.session_state.language != "zh" else "← 返回", key="back_ecom"):
            st.session_state.selected_tool = None
            st.session_state.tool_category = None
            st.rerun()

        st.header(f"{tool['icon']} {tool['label_zh'] if st.session_state.language == 'zh' else tool['label_en']}")
        st.markdown("---")

        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown(f"### {'上傳產品圖' if st.session_state.language == 'zh' else 'Upload Product Image'}")
            uploaded = st.file_uploader("Upload", type=['png', 'jpg', 'jpeg', 'webp'], key=f"upload_{tool['id']}")
            if uploaded:
                st.image(uploaded, caption="Your Product", use_container_width=True)

            # Tool-specific options
            if tool['id'] == 'white_bg':
                st.markdown(f"### {'背景選項' if st.session_state.language == 'zh' else 'Background Options'}")
                bg_opt = st.radio("Background", ["Pure White", "Light Gray", "Transparent"], horizontal=True)
            elif tool['id'] == 'scene_gen':
                st.markdown(f"### {'場景描述' if st.session_state.language == 'zh' else 'Scene Description'}")
                scene = st.text_area("Describe the scene", placeholder="e.g., Modern living room, wooden table, natural light...")
                st.markdown(f"### {'場景風格' if st.session_state.language == 'zh' else 'Scene Style'}")
                style = st.selectbox("Style", ["Modern", "Minimalist", "Luxury", "Natural", "Studio"])
            elif tool['id'] == 'model_tryon':
                st.markdown(f"### {'模特選擇' if st.session_state.language == 'zh' else 'Model Selection'}")
                model_type = st.selectbox("Model Type", ["Female - Asian", "Female - Western", "Male - Asian", "Male - Western"])
                pose = st.selectbox("Pose", ["Standing Front", "Standing Side", "Casual", "Walking"])
            elif tool['id'] == 'product_design':
                st.markdown(f"### {'設計描述' if st.session_state.language == 'zh' else 'Design Description'}")
                desc = st.text_area("Describe modifications", placeholder="e.g., Change color to blue, add gold trim...")

        with col2:
            st.markdown(f"### {'使用說明' if st.session_state.language == 'zh' else 'How to Use'}")
            instructions = {
                'product_design': ["1. Upload product image", "2. Describe design changes", "3. AI generates variations"],
                'white_bg': ["1. Upload product image", "2. Select background type", "3. Get clean white background"],
                'scene_gen': ["1. Upload product", "2. Describe scene", "3. AI places product in scene"],
                'model_tryon': ["1. Upload clothing", "2. Select model type", "3. See clothing on model"],
            }
            for step in instructions.get(tool['id'], ["Upload image", "Configure", "Generate"]):
                st.markdown(f"• {step}")

            st.markdown("---")
            st.markdown(f"**{'消耗點數' if st.session_state.language == 'zh' else 'Credits Cost'}**: {tool.get('credits', 5)}")

            # Sample results
            st.markdown(f"### {'範例結果' if st.session_state.language == 'zh' else 'Sample Results'}")
            sample_cols = st.columns(2)
            with sample_cols[0]:
                st.image(f"https://picsum.photos/seed/{tool['id']}1/150/150", use_container_width=True)
            with sample_cols[1]:
                st.image(f"https://picsum.photos/seed/{tool['id']}2/150/150", use_container_width=True)

        st.markdown("---")
        if st.button(f"🚀 {'生成' if st.session_state.language == 'zh' else 'Generate'}", type="primary", use_container_width=True):
            if not uploaded:
                st.warning("Please upload a product image!" if st.session_state.language != "zh" else "請先上傳產品圖片！")
            elif st.session_state.credits > 0:
                st.session_state.credits -= tool.get('credits', 5)
                with st.spinner("Generating..." if st.session_state.language != "zh" else "生成中..."):
                    st.success("Done!" if st.session_state.language != "zh" else "完成！")
                    result_cols = st.columns(2)
                    with result_cols[0]:
                        st.image("https://picsum.photos/seed/ecomresult1/400/400", caption="Result 1", use_container_width=True)
                    with result_cols[1]:
                        st.image("https://picsum.photos/seed/ecomresult2/400/400", caption="Result 2", use_container_width=True)
            else:
                st.error("No credits!" if st.session_state.language != "zh" else "點數不足！")
    else:
        st.header(f"🛒 {t('ecommerce')}")
        st.caption("E-commerce product image tools" if st.session_state.language != "zh" else "電商產品圖片工具")
        st.markdown("---")

        cols = st.columns(3)
        ecom_tools = [
            {"id": "product_design", "icon": "🎁", "label_zh": "AI產品設計", "label_en": "Product Design", "desc_zh": "AI智能生成產品設計變體", "desc_en": "AI-powered product design variations", "credits": 6},
            {"id": "white_bg", "icon": "⬜", "label_zh": "一鍵白底圖", "label_en": "White BG", "desc_zh": "自動去背景生成純白底圖", "desc_en": "Auto remove background, pure white", "credits": 2},
            {"id": "scene_gen", "icon": "🖼️", "label_zh": "場景圖生成", "label_en": "Scene Gen", "desc_zh": "將產品放入任意場景", "desc_en": "Place product in any scene", "credits": 5},
            {"id": "model_tryon", "icon": "👔", "label_zh": "模特試衣", "label_en": "Model Try-on", "desc_zh": "AI模特展示服裝效果", "desc_en": "AI model wearing your clothes", "credits": 8},
        ]
        for i, tool in enumerate(ecom_tools):
            label = tool['label_zh'] if st.session_state.language == "zh" else tool['label_en']
            desc = tool['desc_zh'] if st.session_state.language == "zh" else tool['desc_en']
            with cols[i % 3]:
                st.markdown(f"### {tool['icon']} {label}")
                st.caption(desc)
                st.caption(f"💰 {tool['credits']} credits")
                if st.button("Open" if st.session_state.language != "zh" else "開啟", key=f"ecom_{i}", use_container_width=True):
                    st.session_state.selected_tool = tool
                    st.session_state.tool_category = "ecom"
                    st.rerun()
                st.markdown("")

        # Showcase Examples from API
        st.markdown("---")
        st.markdown(f"### ✨ {'範例展示' if st.session_state.language == 'zh' else 'Examples'}")
        st.caption("See the full workflow: Product Image → Prompt → Video" if st.session_state.language != "zh" else "查看完整流程：產品圖 → 提示詞 → 視頻")

        ecom_showcases = fetch_tool_showcases("ecommerce", limit=6)
        if ecom_showcases:
            for idx, showcase in enumerate(ecom_showcases):
                with st.container():
                    st.markdown(f"#### {showcase.get('title_zh') if st.session_state.language == 'zh' else showcase.get('title', f'Example {idx+1}')}")

                    flow_cols = st.columns([1, 1, 2])
                    with flow_cols[0]:
                        st.markdown("**1. Product**" if st.session_state.language != "zh" else "**1. 產品**")
                        if showcase.get("source_image_url"):
                            st.image(showcase["source_image_url"], use_container_width=True)

                    with flow_cols[1]:
                        st.markdown("**2. Prompt**" if st.session_state.language != "zh" else "**2. 描述**")
                        prompt_text = showcase.get("prompt_zh") if st.session_state.language == "zh" else showcase.get("prompt", "")
                        st.info(prompt_text)
                        tags = showcase.get("style_tags", [])
                        if tags:
                            st.markdown(" ".join([f"`{tag}`" for tag in tags[:3]]))

                    with flow_cols[2]:
                        st.markdown("**3. Result**" if st.session_state.language != "zh" else "**3. 效果**")
                        render_showcase_result(showcase, height=180, lang=st.session_state.language)

                    if st.button("Use This Style" if st.session_state.language != "zh" else "使用此風格", key=f"ecom_use_{idx}"):
                        st.session_state.selected_prompt = showcase.get("prompt", "")
                        st.rerun()

                    st.markdown("---")

elif current == "Portrait":
    # Check if a tool is selected
    if st.session_state.selected_tool and st.session_state.tool_category == "portrait":
        tool = st.session_state.selected_tool

        if st.button("← Back" if st.session_state.language != "zh" else "← 返回", key="back_portrait"):
            st.session_state.selected_tool = None
            st.session_state.tool_category = None
            st.rerun()

        st.header(f"{tool['icon']} {tool['label_zh'] if st.session_state.language == 'zh' else tool['label_en']}")
        st.markdown("---")

        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown(f"### {'上傳照片' if st.session_state.language == 'zh' else 'Upload Photo'}")
            uploaded = st.file_uploader("Upload", type=['png', 'jpg', 'jpeg', 'webp'], key=f"upload_{tool['id']}")
            if uploaded:
                st.image(uploaded, caption="Your Photo", use_container_width=True)

            # Tool-specific options
            if tool['id'] == 'face_swap':
                st.markdown(f"### {'目標照片' if st.session_state.language == 'zh' else 'Target Photo'}")
                target = st.file_uploader("Upload target face", type=['png', 'jpg', 'jpeg'], key="target_face")
                if target:
                    st.image(target, caption="Target Face", use_container_width=True)
            elif tool['id'] == 'photo_restore':
                st.markdown(f"### {'修復選項' if st.session_state.language == 'zh' else 'Restoration Options'}")
                restore_opts = st.multiselect("Options", ["Remove scratches", "Colorize", "Enhance faces", "Remove noise"])
            elif tool['id'] == 'ai_portrait':
                st.markdown(f"### {'風格選擇' if st.session_state.language == 'zh' else 'Style Selection'}")
                portrait_style = st.selectbox("Style", ["Professional", "Artistic", "Anime", "Oil Painting", "Watercolor", "Cyberpunk"])
                st.markdown(f"### {'背景' if st.session_state.language == 'zh' else 'Background'}")
                bg = st.selectbox("Background", ["Studio", "Nature", "Urban", "Abstract", "Custom"])
            elif tool['id'] == 'id_photo':
                st.markdown(f"### {'證件照規格' if st.session_state.language == 'zh' else 'ID Photo Specs'}")
                id_type = st.selectbox("Type", ["Passport (35x45mm)", "Visa (51x51mm)", "Driver License", "Resume (25x35mm)", "Custom"])
                bg_color = st.radio("Background", ["White", "Blue", "Red"], horizontal=True)

        with col2:
            st.markdown(f"### {'使用說明' if st.session_state.language == 'zh' else 'How to Use'}")
            instructions = {
                'face_swap': ["1. Upload your photo", "2. Upload target face", "3. AI swaps the faces"],
                'photo_restore': ["1. Upload old photo", "2. Select restoration options", "3. AI restores the photo"],
                'ai_portrait': ["1. Upload portrait photo", "2. Select artistic style", "3. Get AI-enhanced portrait"],
                'id_photo': ["1. Upload clear face photo", "2. Select ID type & background", "3. Get standard ID photo"],
            }
            for step in instructions.get(tool['id'], ["Upload", "Configure", "Generate"]):
                st.markdown(f"• {step}")

            st.markdown("---")
            st.markdown(f"**{'消耗點數' if st.session_state.language == 'zh' else 'Credits Cost'}**: {tool.get('credits', 4)}")

            st.markdown(f"### {'效果預覽' if st.session_state.language == 'zh' else 'Preview'}")
            preview_cols = st.columns(2)
            with preview_cols[0]:
                st.caption("Before")
                st.image(f"https://picsum.photos/seed/before{tool['id']}/100/100", use_container_width=True)
            with preview_cols[1]:
                st.caption("After")
                st.image(f"https://picsum.photos/seed/after{tool['id']}/100/100", use_container_width=True)

        st.markdown("---")
        if st.button(f"🚀 {'生成' if st.session_state.language == 'zh' else 'Generate'}", type="primary", use_container_width=True):
            if not uploaded:
                st.warning("Please upload a photo!" if st.session_state.language != "zh" else "請先上傳照片！")
            elif st.session_state.credits > 0:
                st.session_state.credits -= tool.get('credits', 4)
                with st.spinner("Processing..." if st.session_state.language != "zh" else "處理中..."):
                    st.success("Done!" if st.session_state.language != "zh" else "完成！")
                    st.image("https://picsum.photos/seed/portraitresult/400/500", caption="Result", use_container_width=True)

                    # Download option for ID photos
                    if tool['id'] == 'id_photo':
                        st.download_button("Download ID Photo", data=b"placeholder", file_name="id_photo.jpg", mime="image/jpeg")
            else:
                st.error("No credits!" if st.session_state.language != "zh" else "點數不足！")
    else:
        st.header(f"👤 {t('portrait')}")
        st.caption("Portrait and photo enhancement tools" if st.session_state.language != "zh" else "人像照片處理工具")
        st.markdown("---")

        cols = st.columns(3)
        portrait_tools = [
            {"id": "face_swap", "icon": "😊", "label_zh": "人像換臉", "label_en": "Face Swap", "desc_zh": "AI智能換臉技術", "desc_en": "AI-powered face swapping", "credits": 5},
            {"id": "photo_restore", "icon": "🖼️", "label_zh": "老照片修復", "label_en": "Photo Restore", "desc_zh": "修復老舊照片並上色", "desc_en": "Restore and colorize old photos", "credits": 4},
            {"id": "ai_portrait", "icon": "📷", "label_zh": "AI寫真", "label_en": "AI Portrait", "desc_zh": "生成藝術風格人像照", "desc_en": "Generate artistic portrait photos", "credits": 6},
            {"id": "id_photo", "icon": "🪪", "label_zh": "AI證件照", "label_en": "ID Photo", "desc_zh": "生成標準證件照", "desc_en": "Generate standard ID photos", "credits": 2},
        ]
        for i, tool in enumerate(portrait_tools):
            label = tool['label_zh'] if st.session_state.language == "zh" else tool['label_en']
            desc = tool['desc_zh'] if st.session_state.language == "zh" else tool['desc_en']
            with cols[i % 3]:
                st.markdown(f"### {tool['icon']} {label}")
                st.caption(desc)
                st.caption(f"💰 {tool['credits']} credits")
                if st.button("Open" if st.session_state.language != "zh" else "開啟", key=f"portrait_{i}", use_container_width=True):
                    st.session_state.selected_tool = tool
                    st.session_state.tool_category = "portrait"
                    st.rerun()
                st.markdown("")

        # Showcase Examples from API
        st.markdown("---")
        st.markdown(f"### ✨ {'範例展示' if st.session_state.language == 'zh' else 'Examples'}")

        portrait_showcases = fetch_tool_showcases("portrait", limit=6)
        if portrait_showcases:
            for idx, showcase in enumerate(portrait_showcases):
                with st.container():
                    st.markdown(f"#### {showcase.get('title_zh') if st.session_state.language == 'zh' else showcase.get('title', f'Example {idx+1}')}")

                    flow_cols = st.columns([1, 1, 2])
                    with flow_cols[0]:
                        st.markdown("**Original**" if st.session_state.language != "zh" else "**原圖**")
                        if showcase.get("source_image_url"):
                            st.image(showcase["source_image_url"], use_container_width=True)

                    with flow_cols[1]:
                        st.markdown("**Style**" if st.session_state.language != "zh" else "**風格**")
                        prompt_text = showcase.get("prompt_zh") if st.session_state.language == "zh" else showcase.get("prompt", "")
                        st.info(prompt_text)
                        tags = showcase.get("style_tags", [])
                        if tags:
                            st.markdown(" ".join([f"`{tag}`" for tag in tags[:3]]))

                    with flow_cols[2]:
                        st.markdown("**Result**" if st.session_state.language != "zh" else "**效果**")
                        render_showcase_result(showcase, height=180, lang=st.session_state.language)

                    st.markdown("---")

elif current == "My Works":
    st.header(f"📁 {t('my_works')}")
    msg = "📁 No works yet. Start creating!" if st.session_state.language != "zh" else "📁 暫無作品，開始創作吧！"
    st.info(msg)
    btn_text = "🎨 Start Creating" if st.session_state.language != "zh" else "🎨 開始創作"
    if st.button(btn_text):
        st.session_state.current_page = "AI Creation"
        st.rerun()

# ============ SUBSCRIPTION PAGE ============
elif current == "Subscription":
    st.header(f"💎 {t('subscription_page') if 'subscription_page' in TRANSLATIONS.get(st.session_state.language, {}) else 'Subscription Plans'}")
    st.markdown(f"*{t('choose_plan') if 'choose_plan' in TRANSLATIONS.get(st.session_state.language, {}) else 'Choose the plan that fits your needs'}*")

    # Payment pending notice
    st.info(f"🚧 {t('payment_pending') if 'payment_pending' in TRANSLATIONS.get(st.session_state.language, {}) else 'Payment system coming soon - Plans preview only'}")

    st.markdown("---")

    # Billing toggle
    billing_options = [
        t('monthly') if 'monthly' in TRANSLATIONS.get(st.session_state.language, {}) else "Monthly",
        t('yearly') if 'yearly' in TRANSLATIONS.get(st.session_state.language, {}) else "Yearly (Save 20%)"
    ]
    billing_period = st.radio("Billing", billing_options, horizontal=True, label_visibility="collapsed")
    is_yearly = billing_period == billing_options[1]

    st.markdown("")

    # Plan data
    plans = [
        {
            "name": "Demo",
            "slug": "demo",
            "icon": "🎁",
            "price_monthly": 0,
            "price_yearly": 0,
            "credits": 2,
            "features": [
                "2 free credits",
                "720p resolution",
                "Watermark on outputs",
                "Leonardo AI only",
                "Standard queue"
            ],
            "features_zh": [
                "2個免費點數",
                "720p 解析度",
                "輸出含浮水印",
                "僅支援 Leonardo AI",
                "標準隊列"
            ],
            "is_popular": False,
            "is_current": st.session_state.user_plan == "demo"
        },
        {
            "name": "Starter",
            "slug": "starter",
            "icon": "🚀",
            "price_monthly": 299,
            "price_yearly": 2870,
            "credits": 100,
            "features": [
                "100 credits/month",
                "1080p resolution",
                "No watermark",
                "Leonardo + Pollo AI",
                "30 Pollo videos/month",
                "Standard queue"
            ],
            "features_zh": [
                "每月100點數",
                "1080p 解析度",
                "無浮水印",
                "Leonardo + Pollo AI",
                "每月30個Pollo視頻",
                "標準隊列"
            ],
            "is_popular": False,
            "is_current": st.session_state.user_plan == "starter"
        },
        {
            "name": "Pro",
            "slug": "pro",
            "icon": "⭐",
            "price_monthly": 599,
            "price_yearly": 5750,
            "credits": 250,
            "features": [
                "250 credits/month",
                "4K resolution",
                "No watermark",
                "All AI services",
                "50 Pollo videos/month",
                "Priority queue",
                "10% topup discount"
            ],
            "features_zh": [
                "每月250點數",
                "4K 解析度",
                "無浮水印",
                "所有AI服務",
                "每月50個Pollo視頻",
                "優先隊列",
                "加購9折優惠"
            ],
            "is_popular": True,
            "is_current": st.session_state.user_plan == "pro"
        },
        {
            "name": "Pro+",
            "slug": "pro_plus",
            "icon": "👑",
            "price_monthly": 999,
            "price_yearly": 9590,
            "credits": 500,
            "features": [
                "500 credits/month",
                "4K resolution",
                "No watermark",
                "All AI services",
                "100 Pollo videos/month",
                "Priority queue",
                "20% topup discount",
                "Dedicated support"
            ],
            "features_zh": [
                "每月500點數",
                "4K 解析度",
                "無浮水印",
                "所有AI服務",
                "每月100個Pollo視頻",
                "優先隊列",
                "加購8折優惠",
                "專屬客服"
            ],
            "is_popular": False,
            "is_current": st.session_state.user_plan == "pro_plus"
        }
    ]

    # Display plan cards
    plan_cols = st.columns(4)

    for idx, plan in enumerate(plans):
        with plan_cols[idx]:
            # Card styling
            if plan["is_popular"]:
                st.markdown(f"**🔥 {t('most_popular') if 'most_popular' in TRANSLATIONS.get(st.session_state.language, {}) else 'Most Popular'}**")
            else:
                st.markdown("")

            # Plan header
            st.markdown(f"### {plan['icon']} {plan['name']}")

            # Price
            price = plan["price_yearly"] if is_yearly else plan["price_monthly"]
            if price == 0:
                price_text = "Free" if st.session_state.language != "zh" else "免費"
            else:
                period_text = "/year" if is_yearly else "/mo"
                period_text_zh = "/年" if is_yearly else "/月"
                price_text = f"NT${price}{period_text_zh if st.session_state.language == 'zh' else period_text}"

            st.markdown(f"## {price_text}")
            st.caption(f"💰 {plan['credits']} {t('credits')}")

            st.markdown("---")

            # Features
            features = plan["features_zh"] if st.session_state.language == "zh" else plan["features"]
            for feature in features:
                st.markdown(f"✅ {feature}")

            st.markdown("")

            # Button
            if plan["is_current"]:
                st.button(
                    f"✓ {t('current') if 'current' in TRANSLATIONS.get(st.session_state.language, {}) else 'Current'}",
                    key=f"plan_{plan['slug']}",
                    use_container_width=True,
                    disabled=True
                )
            else:
                if st.button(
                    f"{t('select_plan') if 'select_plan' in TRANSLATIONS.get(st.session_state.language, {}) else 'Select Plan'}",
                    key=f"plan_{plan['slug']}",
                    use_container_width=True,
                    type="primary" if plan["is_popular"] else "secondary"
                ):
                    # TODO: Integrate with payment system
                    st.info(f"🚧 {t('payment_pending') if 'payment_pending' in TRANSLATIONS.get(st.session_state.language, {}) else 'Payment system coming soon'}")

    # Credit Packages Section
    st.markdown("---")
    st.markdown(f"### 💎 {'加購點數包' if st.session_state.language == 'zh' else 'Credit Packages'}")
    st.caption('購買額外點數以滿足您的需求' if st.session_state.language == 'zh' else 'Purchase additional credits when you need more')

    packages = [
        {"name": "Small", "name_zh": "小包", "credits": 50, "price": 150, "bonus": 0},
        {"name": "Medium", "name_zh": "中包", "credits": 100, "price": 250, "bonus": 10, "popular": True},
        {"name": "Large", "name_zh": "大包", "credits": 200, "price": 400, "bonus": 30, "best_value": True},
        {"name": "Enterprise", "name_zh": "企業包", "credits": 500, "price": 800, "bonus": 100},
    ]

    pkg_cols = st.columns(4)
    for idx, pkg in enumerate(packages):
        with pkg_cols[idx]:
            pkg_name = pkg["name_zh"] if st.session_state.language == "zh" else pkg["name"]

            if pkg.get("popular"):
                st.markdown(f"**🔥 {'最受歡迎' if st.session_state.language == 'zh' else 'Popular'}**")
            elif pkg.get("best_value"):
                st.markdown(f"**💎 {'最佳價值' if st.session_state.language == 'zh' else 'Best Value'}**")
            else:
                st.markdown("")

            st.markdown(f"### {pkg_name}")
            st.markdown(f"## NT${pkg['price']}")

            total_credits = pkg["credits"] + pkg["bonus"]
            st.caption(f"💰 {pkg['credits']} + {pkg['bonus']} bonus = **{total_credits}** credits")

            if st.button(
                f"{'購買' if st.session_state.language == 'zh' else 'Buy'}",
                key=f"pkg_{pkg['name']}",
                use_container_width=True,
                type="primary" if pkg.get("popular") or pkg.get("best_value") else "secondary"
            ):
                st.info(f"🚧 {t('payment_pending') if 'payment_pending' in TRANSLATIONS.get(st.session_state.language, {}) else 'Payment system coming soon'}")

