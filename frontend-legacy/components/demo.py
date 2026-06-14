"""
Demo Page - AI Image & Video Generation Platform
完全複製 douhuiai.com 風格設計

特色:
- 淺色主題 (白色/奶油色背景)
- 綠色強調色
- 左側固定分類選單
- 頂部橫幅輪播區
- 水平分類標籤 (帶 GO 按鈕)
- 彩色圖標功能卡片網格
- 免費版/實驗版徽章
"""
import streamlit as st
from typing import Optional
import streamlit.components.v1 as components
import textwrap


# =============================================================================
# TRANSLATIONS (5 languages)
# =============================================================================
TRANSLATIONS = {
    "en": {
        "app_name": "Vidgo AI",
        "nav_home": "Home",
        "nav_pricing": "Pricing",
        "nav_api": "API",
        "nav_login": "Login",
        "nav_register": "Register",

        # Main Categories
        "cat_ai_create": "AI Creation",
        "cat_editing": "Editing Apps",
        "cat_video": "Video Creation",
        "cat_architecture": "Architecture",
        "cat_product": "E-commerce",
        "cat_portrait": "Portrait",

        # AI Creation Tools
        "tool_text_to_image": "Text to Image",
        "tool_text_to_image_desc": "Generate images from text",
        "tool_ai_smart": "AI Smart Create",
        "tool_ai_smart_desc": "Understand and create",
        "tool_image_repaint": "Image Repaint",
        "tool_image_repaint_desc": "Redraw with AI",
        "tool_free_create": "Free Create",
        "tool_free_create_desc": "Try for free",
        "tool_flux": "Flux Create",
        "tool_flux_desc": "Photorealistic",
        "tool_sdxl": "SDXL Create",
        "tool_sdxl_desc": "High detail",
        "tool_ai_out": "AI Outpaint",
        "tool_ai_out_desc": "Expand images",
        "tool_banana": "N-banana Pro",
        "tool_banana_desc": "Fast generation",
        "tool_universal": "Universal Edit",
        "tool_universal_desc": "Quick editing",
        "tool_3d_model": "3D Model",
        "tool_3d_model_desc": "Image to 3D",
        "tool_kontext": "F.1 Kontext Max",
        "tool_kontext_desc": "Complex commands",
        "tool_multi_mode": "Multi-mode",
        "tool_multi_mode_desc": "Combined generation",
        "tool_chinese": "Chinese Poster",
        "tool_chinese_desc": "Chinese text support",

        # Badges
        "badge_free": "Free",
        "badge_beta": "Beta",
        "badge_hot": "Hot",
        "badge_new": "New",

        # Banner
        "banner_title": "PS Fusion - One-Click Perfect Integration",
        "banner_desc": "Intelligent recognition, automatic matching",

        # Sidebar
        "sidebar_history": "History",
        "sidebar_favorites": "Favorites",
        "sidebar_settings": "Settings",
    },
    "zh-TW": {
        "app_name": "豆绘AI",
        "nav_home": "首頁",
        "nav_pricing": "定價",
        "nav_api": "API",
        "nav_login": "登入",
        "nav_register": "註冊",

        # Main Categories
        "cat_ai_create": "AI創作",
        "cat_editing": "編輯應用",
        "cat_video": "視頻創作",
        "cat_architecture": "建築室內",
        "cat_product": "產品電商",
        "cat_portrait": "人像寫真",

        # AI Creation Tools
        "tool_text_to_image": "文生圖",
        "tool_text_to_image_desc": "一句話生成圖片",
        "tool_ai_smart": "AI智能創作",
        "tool_ai_smart_desc": "語義理解創作",
        "tool_image_repaint": "圖片重繪",
        "tool_image_repaint_desc": "以圖改圖更穩",
        "tool_free_create": "免費創作",
        "tool_free_create_desc": "限時免費體驗",
        "tool_flux": "Flux創作",
        "tool_flux_desc": "寫實光影更強",
        "tool_sdxl": "SDXL創作",
        "tool_sdxl_desc": "細節豐富感強",
        "tool_ai_out": "AI智能出圖",
        "tool_ai_out_desc": "對話式一鍵改圖",
        "tool_banana": "N-banana Pro創作",
        "tool_banana_desc": "高速出圖低成本",
        "tool_universal": "萬能改圖",
        "tool_universal_desc": "秒改局部更快",
        "tool_3d_model": "圖轉3D模型",
        "tool_3d_model_desc": "單圖生成3D",
        "tool_kontext": "F.1 Kontext Max",
        "tool_kontext_desc": "複合指令更強",
        "tool_multi_mode": "多模態出圖",
        "tool_multi_mode_desc": "文圖混合生成",
        "tool_chinese": "中文海報",
        "tool_chinese_desc": "中文模板一鍵排版",

        # Badges
        "badge_free": "免費版",
        "badge_beta": "實驗版",
        "badge_hot": "熱門",
        "badge_new": "新功能",

        # Banner
        "banner_title": "PS融圖 一鍵完美嵌入",
        "banner_desc": "智能識別，自動匹配",

        # Sidebar
        "sidebar_history": "歷史記錄",
        "sidebar_favorites": "我的收藏",
        "sidebar_settings": "設定",
    },
    "ja": {
        "app_name": "Vidgo AI",
        "nav_home": "ホーム",
        "nav_pricing": "料金",
        "nav_api": "API",
        "nav_login": "ログイン",
        "nav_register": "登録",

        "cat_ai_create": "AI作成",
        "cat_editing": "編集アプリ",
        "cat_video": "動画作成",
        "cat_architecture": "建築",
        "cat_product": "EC商品",
        "cat_portrait": "ポートレート",

        "tool_text_to_image": "テキスト→画像",
        "tool_text_to_image_desc": "テキストから画像生成",
        "tool_ai_smart": "AIスマート作成",
        "tool_ai_smart_desc": "意味理解で作成",
        "tool_image_repaint": "画像リペイント",
        "tool_image_repaint_desc": "画像から再描画",
        "tool_free_create": "無料作成",
        "tool_free_create_desc": "無料体験",
        "tool_flux": "Flux作成",
        "tool_flux_desc": "フォトリアル",
        "tool_sdxl": "SDXL作成",
        "tool_sdxl_desc": "高ディテール",
        "tool_ai_out": "AI出力",
        "tool_ai_out_desc": "画像拡張",
        "tool_banana": "N-banana Pro",
        "tool_banana_desc": "高速生成",
        "tool_universal": "万能編集",
        "tool_universal_desc": "クイック編集",
        "tool_3d_model": "3Dモデル",
        "tool_3d_model_desc": "画像→3D",
        "tool_kontext": "F.1 Kontext Max",
        "tool_kontext_desc": "複合コマンド",
        "tool_multi_mode": "マルチモード",
        "tool_multi_mode_desc": "複合生成",
        "tool_chinese": "中国語ポスター",
        "tool_chinese_desc": "中国語対応",

        "badge_free": "無料",
        "badge_beta": "ベータ",
        "badge_hot": "人気",
        "badge_new": "新機能",

        "banner_title": "PS融合 - ワンクリック完璧統合",
        "banner_desc": "スマート認識、自動マッチング",

        "sidebar_history": "履歴",
        "sidebar_favorites": "お気に入り",
        "sidebar_settings": "設定",
    },
    "ko": {
        "app_name": "Vidgo AI",
        "nav_home": "홈",
        "nav_pricing": "가격",
        "nav_api": "API",
        "nav_login": "로그인",
        "nav_register": "회원가입",

        "cat_ai_create": "AI 생성",
        "cat_editing": "편집 앱",
        "cat_video": "비디오 생성",
        "cat_architecture": "건축",
        "cat_product": "이커머스",
        "cat_portrait": "인물사진",

        "tool_text_to_image": "텍스트→이미지",
        "tool_text_to_image_desc": "텍스트로 이미지 생성",
        "tool_ai_smart": "AI 스마트 생성",
        "tool_ai_smart_desc": "의미 이해 생성",
        "tool_image_repaint": "이미지 리페인트",
        "tool_image_repaint_desc": "이미지 재생성",
        "tool_free_create": "무료 생성",
        "tool_free_create_desc": "무료 체험",
        "tool_flux": "Flux 생성",
        "tool_flux_desc": "사실적",
        "tool_sdxl": "SDXL 생성",
        "tool_sdxl_desc": "고해상도",
        "tool_ai_out": "AI 출력",
        "tool_ai_out_desc": "이미지 확장",
        "tool_banana": "N-banana Pro",
        "tool_banana_desc": "빠른 생성",
        "tool_universal": "만능 편집",
        "tool_universal_desc": "빠른 편집",
        "tool_3d_model": "3D 모델",
        "tool_3d_model_desc": "이미지→3D",
        "tool_kontext": "F.1 Kontext Max",
        "tool_kontext_desc": "복합 명령",
        "tool_multi_mode": "멀티모드",
        "tool_multi_mode_desc": "복합 생성",
        "tool_chinese": "중국어 포스터",
        "tool_chinese_desc": "중국어 지원",

        "badge_free": "무료",
        "badge_beta": "베타",
        "badge_hot": "인기",
        "badge_new": "신규",

        "banner_title": "PS 융합 - 원클릭 완벽 통합",
        "banner_desc": "스마트 인식, 자동 매칭",

        "sidebar_history": "기록",
        "sidebar_favorites": "즐겨찾기",
        "sidebar_settings": "설정",
    },
    "es": {
        "app_name": "Vidgo AI",
        "nav_home": "Inicio",
        "nav_pricing": "Precios",
        "nav_api": "API",
        "nav_login": "Iniciar",
        "nav_register": "Registro",

        "cat_ai_create": "Creación IA",
        "cat_editing": "Apps Edición",
        "cat_video": "Crear Video",
        "cat_architecture": "Arquitectura",
        "cat_product": "E-commerce",
        "cat_portrait": "Retrato",

        "tool_text_to_image": "Texto a Imagen",
        "tool_text_to_image_desc": "Generar desde texto",
        "tool_ai_smart": "IA Inteligente",
        "tool_ai_smart_desc": "Creación semántica",
        "tool_image_repaint": "Repintar Imagen",
        "tool_image_repaint_desc": "Redibujar con IA",
        "tool_free_create": "Crear Gratis",
        "tool_free_create_desc": "Prueba gratuita",
        "tool_flux": "Crear Flux",
        "tool_flux_desc": "Fotorrealista",
        "tool_sdxl": "Crear SDXL",
        "tool_sdxl_desc": "Alto detalle",
        "tool_ai_out": "IA Expandir",
        "tool_ai_out_desc": "Expandir imagen",
        "tool_banana": "N-banana Pro",
        "tool_banana_desc": "Generación rápida",
        "tool_universal": "Edición Universal",
        "tool_universal_desc": "Edición rápida",
        "tool_3d_model": "Modelo 3D",
        "tool_3d_model_desc": "Imagen a 3D",
        "tool_kontext": "F.1 Kontext Max",
        "tool_kontext_desc": "Comandos complejos",
        "tool_multi_mode": "Multi-modo",
        "tool_multi_mode_desc": "Generación combinada",
        "tool_chinese": "Póster Chino",
        "tool_chinese_desc": "Soporte chino",

        "badge_free": "Gratis",
        "badge_beta": "Beta",
        "badge_hot": "Popular",
        "badge_new": "Nuevo",

        "banner_title": "Fusión PS - Integración Perfecta",
        "banner_desc": "Reconocimiento inteligente",

        "sidebar_history": "Historial",
        "sidebar_favorites": "Favoritos",
        "sidebar_settings": "Ajustes",
    },
}

LANGUAGES = {
    "en": "🇺🇸 EN",
    "zh-TW": "🇹🇼 繁中",
    "ja": "🇯🇵 JP",
    "ko": "🇰🇷 KR",
    "es": "🇪🇸 ES",
}


def t(key: str) -> str:
    lang = st.session_state.get("lang", "zh-TW")
    return TRANSLATIONS.get(lang, TRANSLATIONS["zh-TW"]).get(key, key)


# =============================================================================
# DATA - Categories and Tools (matching douhuiai.com exactly)
# =============================================================================
MAIN_CATEGORIES = [
    {"id": "ai_create", "key": "cat_ai_create", "icon": "🎨", "color": "#10B981"},
    {"id": "editing", "key": "cat_editing", "icon": "✂️", "color": "#F59E0B"},
    {"id": "video", "key": "cat_video", "icon": "🎬", "color": "#8B5CF6"},
    {"id": "architecture", "key": "cat_architecture", "icon": "🏠", "color": "#06B6D4"},
    {"id": "product", "key": "cat_product", "icon": "🛍️", "color": "#EC4899"},
    {"id": "portrait", "key": "cat_portrait", "icon": "👤", "color": "#F97316"},
]

# Feature cards for each category - matching douhuiai.com layout
FEATURE_CARDS = {
    "ai_create": [
        {"id": "text_to_image", "key": "tool_text_to_image", "desc": "tool_text_to_image_desc", "color": "#EF4444", "badge": None},
        {"id": "ai_smart", "key": "tool_ai_smart", "desc": "tool_ai_smart_desc", "color": "#F59E0B", "badge": None},
        {"id": "image_repaint", "key": "tool_image_repaint", "desc": "tool_image_repaint_desc", "color": "#F97316", "badge": "beta"},
        {"id": "free_create", "key": "tool_free_create", "desc": "tool_free_create_desc", "color": "#10B981", "badge": "free"},
        {"id": "flux", "key": "tool_flux", "desc": "tool_flux_desc", "color": "#6366F1", "badge": None},
        {"id": "sdxl", "key": "tool_sdxl", "desc": "tool_sdxl_desc", "color": "#8B5CF6", "badge": "beta"},
        {"id": "ai_out", "key": "tool_ai_out", "desc": "tool_ai_out_desc", "color": "#EC4899", "badge": None},
        {"id": "banana", "key": "tool_banana", "desc": "tool_banana_desc", "color": "#14B8A6", "badge": "beta"},
        {"id": "universal", "key": "tool_universal", "desc": "tool_universal_desc", "color": "#F59E0B", "badge": "beta"},
        {"id": "3d_model", "key": "tool_3d_model", "desc": "tool_3d_model_desc", "color": "#06B6D4", "badge": "beta"},
        {"id": "kontext", "key": "tool_kontext", "desc": "tool_kontext_desc", "color": "#6366F1", "badge": "beta"},
        {"id": "multi_mode", "key": "tool_multi_mode", "desc": "tool_multi_mode_desc", "color": "#8B5CF6", "badge": "beta"},
        {"id": "chinese", "key": "tool_chinese", "desc": "tool_chinese_desc", "color": "#22C55E", "badge": "beta"},
    ],
    "editing": [
        {"id": "remove_bg", "key": "tool_text_to_image", "desc": "tool_text_to_image_desc", "color": "#EF4444", "badge": None},
        {"id": "upscale", "key": "tool_ai_smart", "desc": "tool_ai_smart_desc", "color": "#F59E0B", "badge": None},
    ],
    "video": [
        {"id": "i2v", "key": "tool_text_to_image", "desc": "tool_text_to_image_desc", "color": "#8B5CF6", "badge": "hot"},
        {"id": "t2v", "key": "tool_ai_smart", "desc": "tool_ai_smart_desc", "color": "#EC4899", "badge": "new"},
    ],
}

# Sidebar menu items
SIDEBAR_MENU = [
    {"id": "ai_create", "key": "cat_ai_create", "icon": "🎨"},
    {"id": "editing", "key": "cat_editing", "icon": "✂️"},
    {"id": "video", "key": "cat_video", "icon": "🎬"},
    {"id": "architecture", "key": "cat_architecture", "icon": "🏠"},
    {"id": "product", "key": "cat_product", "icon": "🛍️"},
    {"id": "portrait", "key": "cat_portrait", "icon": "👤"},
    {"id": "divider", "key": "", "icon": ""},
    {"id": "history", "key": "sidebar_history", "icon": "📋"},
    {"id": "favorites", "key": "sidebar_favorites", "icon": "⭐"},
    {"id": "settings", "key": "sidebar_settings", "icon": "⚙️"},
]


# =============================================================================
# CSS - 完全複製 douhuiai.com 淺色主題
# =============================================================================
def get_css():
    return """
<style>
/* Hide Streamlit defaults */
#MainMenu, footer, header, .stDeployButton,
[data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"] { display: none !important; }

/* Light theme - douhuiai.com style */
.stApp {
    background: #F8F9FA !important;
}

.block-container {
    padding: 0 !important;
    max-width: 100% !important;
    margin: 0 !important;
}

/* Hide default sidebar */
section[data-testid="stSidebar"] { display: none !important; }

/* ============================================
   Main Layout Container
   ============================================ */
.main-layout {
    display: flex;
    min-height: 100vh;
    background: #F8F9FA;
}

/* ============================================
   Left Sidebar - douhuiai style
   ============================================ */
.left-sidebar {
    width: 200px;
    min-width: 200px;
    background: #FFFFFF;
    border-right: 1px solid #E5E7EB;
    padding: 16px 0;
    position: fixed;
    left: 0;
    top: 0;
    height: 100vh;
    overflow-y: auto;
    z-index: 100;
}

.sidebar-logo {
    padding: 12px 20px 24px;
    font-size: 1.2rem;
    font-weight: 700;
    color: #10B981;
    display: flex;
    align-items: center;
    gap: 8px;
}

.sidebar-item {
    padding: 12px 20px;
    color: #6B7280;
    font-size: 0.9rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 12px;
    transition: all 0.2s;
    border-left: 3px solid transparent;
}

.sidebar-item:hover {
    background: #F3F4F6;
    color: #111827;
}

.sidebar-item.active {
    background: linear-gradient(90deg, rgba(16, 185, 129, 0.1) 0%, transparent 100%);
    color: #10B981;
    border-left-color: #10B981;
    font-weight: 600;
}

.sidebar-divider {
    height: 1px;
    background: #E5E7EB;
    margin: 16px 20px;
}

/* ============================================
   Main Content Area
   ============================================ */
.main-content {
    margin-left: 200px;
    flex: 1;
    padding: 0;
    background: #F8F9FA;
}

/* ============================================
   Top Banner / Slider Area
   ============================================ */
.banner-area {
    background: linear-gradient(135deg, #F0FDF4 0%, #ECFDF5 100%);
    border-radius: 16px;
    padding: 24px;
    margin: 20px;
    display: flex;
    align-items: center;
    gap: 24px;
    border: 1px solid #D1FAE5;
}

.banner-image {
    width: 300px;
    height: 180px;
    border-radius: 12px;
    background: linear-gradient(135deg, #E0E7FF 0%, #C7D2FE 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
}

.banner-content {
    flex: 1;
}

.banner-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: #111827;
    margin-bottom: 8px;
}

.banner-desc {
    color: #6B7280;
    font-size: 0.9rem;
    margin-bottom: 16px;
}

.banner-btn {
    display: inline-block;
    background: #10B981;
    color: white;
    padding: 10px 24px;
    border-radius: 8px;
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
}

.banner-btn:hover {
    background: #059669;
}

/* ============================================
   Category Tabs - with GO button
   ============================================ */
.category-tabs {
    display: flex;
    gap: 16px;
    padding: 0 20px;
    margin-bottom: 24px;
    overflow-x: auto;
}

.category-tab {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 20px;
    background: white;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
}

.category-tab:hover {
    border-color: #10B981;
    box-shadow: 0 2px 8px rgba(16, 185, 129, 0.1);
}

.category-tab.active {
    border-color: #10B981;
    background: linear-gradient(135deg, #F0FDF4 0%, #FFFFFF 100%);
}

.category-tab-icon {
    font-size: 1.2rem;
}

.category-tab-text {
    font-size: 0.9rem;
    color: #374151;
    font-weight: 500;
}

.category-tab-go {
    background: #10B981;
    color: white;
    font-size: 0.7rem;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 600;
}

/* ============================================
   Feature Cards Grid - douhuiai style
   ============================================ */
.feature-grid {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 16px;
    padding: 0 20px;
}

.feature-card {
    background: white;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 20px;
    cursor: pointer;
    transition: all 0.2s;
    position: relative;
}

.feature-card:hover {
    border-color: #10B981;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
    transform: translateY(-2px);
}

.feature-card-icon {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
    margin-bottom: 12px;
}

.feature-card-title {
    font-size: 0.95rem;
    font-weight: 600;
    color: #111827;
    margin-bottom: 4px;
}

.feature-card-desc {
    font-size: 0.8rem;
    color: #9CA3AF;
}

.feature-card-badge {
    position: absolute;
    top: 12px;
    right: 12px;
    font-size: 0.65rem;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 600;
}

.badge-free {
    background: #D1FAE5;
    color: #059669;
}

.badge-beta {
    background: #FEF3C7;
    color: #D97706;
}

.badge-hot {
    background: #FEE2E2;
    color: #DC2626;
}

.badge-new {
    background: #DBEAFE;
    color: #2563EB;
}

/* ============================================
   Top Navigation Bar
   ============================================ */
.top-nav {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding: 12px 24px;
    background: white;
    border-bottom: 1px solid #E5E7EB;
    gap: 16px;
}

.nav-btn {
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.2s;
}

.nav-btn-ghost {
    color: #6B7280;
    background: transparent;
}

.nav-btn-ghost:hover {
    color: #111827;
    background: #F3F4F6;
}

.nav-btn-primary {
    color: white;
    background: #10B981;
}

.nav-btn-primary:hover {
    background: #059669;
}

/* Responsive */
@media (max-width: 1200px) {
    .feature-grid {
        grid-template-columns: repeat(4, 1fr);
    }
}

@media (max-width: 900px) {
    .feature-grid {
        grid-template-columns: repeat(3, 1fr);
    }
}

@media (max-width: 600px) {
    .feature-grid {
        grid-template-columns: repeat(2, 1fr);
    }
    .left-sidebar {
        display: none;
    }
    .main-content {
        margin-left: 0;
    }
}

/* Streamlit button overrides for light theme */
.stButton > button {
    border-radius: 8px !important;
}

.stButton > button[kind="primary"] {
    background: #10B981 !important;
    border-color: #10B981 !important;
}

.stButton > button[kind="primary"]:hover {
    background: #059669 !important;
    border-color: #059669 !important;
}

.stButton > button[kind="secondary"] {
    background: white !important;
    border-color: #E5E7EB !important;
    color: #374151 !important;
}

.stButton > button[kind="secondary"]:hover {
    border-color: #10B981 !important;
    color: #10B981 !important;
}

/* Text colors for light theme */
h1, h2, h3, h4, h5, h6 {
    color: #111827 !important;
}

p, span, div {
    color: #374151;
}
</style>
"""


# =============================================================================
# COMPONENTS
# =============================================================================
def init():
    """Initialize session state"""
    defaults = {
        "lang": "zh-TW",
        "category": "ai_create",
        "tool": "text_to_image",
        "usage": 0,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def render_sidebar():
    """Render left sidebar - douhuiai style"""
    # Logo
    # Logo
    app_name = t('app_name')
    st.markdown(f"""
<div style="padding:12px 0 20px;text-align:center;">
    <span style="font-size:1.3rem;font-weight:700;color:#10B981;">
        🎨 {app_name}
    </span>
</div>""".strip(), unsafe_allow_html=True)

    # Menu items
    for item in SIDEBAR_MENU:
        if item["id"] == "divider":
            st.markdown("<hr style='margin:16px 0;border:none;border-top:1px solid #E5E7EB;'>", unsafe_allow_html=True)
            continue

        is_active = st.session_state.category == item["id"]
        btn_type = "primary" if is_active else "secondary"

        if st.button(f"{item['icon']} {t(item['key'])}", key=f"side_{item['id']}",
                    use_container_width=True, type=btn_type):
            st.session_state.category = item["id"]
            st.rerun()


def render_topnav():
    """Render top navigation"""
    cols = st.columns([4, 1, 1, 1, 1.2])

    with cols[1]:
        lang_list = list(LANGUAGES.keys())
        idx = lang_list.index(st.session_state.lang) if st.session_state.lang in lang_list else 0
        new_lang = st.selectbox("🌐", options=lang_list, format_func=lambda x: LANGUAGES[x],
                               index=idx, key="lang_sel", label_visibility="collapsed")
        if new_lang != st.session_state.lang:
            st.session_state.lang = new_lang
            st.rerun()

    with cols[2]:
        st.button(t("nav_pricing"), key="nav_pricing", use_container_width=True)

    with cols[3]:
        st.button(t("nav_login"), key="nav_login", use_container_width=True)

    with cols[4]:
        st.button(t("nav_register"), key="nav_register", use_container_width=True, type="primary")


def render_banner():
    """Render top banner area"""
    html = f"""
    <div style="background:linear-gradient(135deg, #F0FDF4 0%, #ECFDF5 100%);
                border-radius:16px;padding:24px;margin-bottom:24px;
                display:flex;align-items:center;gap:24px;border:1px solid #D1FAE5;">
        <div style="width:280px;height:160px;border-radius:12px;
                    background:linear-gradient(135deg, #E0E7FF 0%, #C7D2FE 100%);
                    display:flex;align-items:center;justify-content:center;overflow:hidden;">
            <img src="https://picsum.photos/seed/banner/280/160" style="width:100%;height:100%;object-fit:cover;border-radius:12px;">
        </div>
        <div style="flex:1;">
            <div style="font-size:1.4rem;font-weight:700;color:#111827;margin-bottom:8px;">
                {t('banner_title')}
            </div>
            <div style="color:#6B7280;font-size:0.9rem;margin-bottom:16px;">
                {t('banner_desc')}
            </div>
        </div>
    </div>
    """
    st.markdown(textwrap.dedent(html), unsafe_allow_html=True)


def render_category_tabs():
    """Render horizontal category tabs with GO buttons"""
    cols = st.columns(len(MAIN_CATEGORIES))

    for i, cat in enumerate(MAIN_CATEGORIES):
        with cols[i]:
            is_active = st.session_state.category == cat["id"]
            btn_type = "primary" if is_active else "secondary"

            if st.button(f"{cat['icon']} {t(cat['key'])} GO", key=f"tab_{cat['id']}",
                        use_container_width=True, type=btn_type):
                st.session_state.category = cat["id"]
                st.rerun()


def render_feature_cards():
    """Render feature cards grid - douhuiai style"""
    current_cat = st.session_state.category
    cards = FEATURE_CARDS.get(current_cat, FEATURE_CARDS["ai_create"])

    # Create rows of cards (6 per row on large screens)
    num_cols = 6
    rows = [cards[i:i+num_cols] for i in range(0, len(cards), num_cols)]

    for row in rows:
        cols = st.columns(num_cols)
        for i, card in enumerate(row):
            with cols[i]:
                # Badge HTML
                badge_html = ""
                if card.get("badge") == "free":
                    badge_html = f'<span style="position:absolute;top:12px;right:12px;background:#D1FAE5;color:#059669;font-size:0.65rem;padding:2px 8px;border-radius:4px;font-weight:600;">{t("badge_free")}</span>'
                elif card.get("badge") == "beta":
                    badge_html = f'<span style="position:absolute;top:12px;right:12px;background:#FEF3C7;color:#D97706;font-size:0.65rem;padding:2px 8px;border-radius:4px;font-weight:600;">{t("badge_beta")}</span>'
                elif card.get("badge") == "hot":
                    badge_html = f'<span style="position:absolute;top:12px;right:12px;background:#FEE2E2;color:#DC2626;font-size:0.65rem;padding:2px 8px;border-radius:4px;font-weight:600;">{t("badge_hot")}</span>'
                elif card.get("badge") == "new":
                    badge_html = f'<span style="position:absolute;top:12px;right:12px;background:#DBEAFE;color:#2563EB;font-size:0.65rem;padding:2px 8px;border-radius:4px;font-weight:600;">{t("badge_new")}</span>'

                # Construct HTML without main indentation to ensure no Markdown code block triggers
                card_key = t(card['key'])
                card_desc = t(card['desc'])
                
                html = f"""
<div style="background:white;border:1px solid #E5E7EB;border-radius:12px;
            padding:20px;cursor:pointer;transition:all 0.2s;position:relative;
            min-height:120px;margin-bottom:16px;"
     onmouseover="this.style.borderColor='#10B981';this.style.transform='translateY(-2px)';this.style.boxShadow='0 4px 12px rgba(0,0,0,0.08)';"
     onmouseout="this.style.borderColor='#E5E7EB';this.style.transform='translateY(0)';this.style.boxShadow='none';">
    {badge_html}
    <div style="width:40px;height:40px;border-radius:10px;background:{card['color']};
                display:flex;align-items:center;justify-content:center;margin-bottom:12px;">
        <span style="color:white;font-size:1.1rem;">✨</span>
    </div>
    <div style="font-size:0.95rem;font-weight:600;color:#111827;margin-bottom:4px;">
        {card_key}
    </div>
    <div style="font-size:0.8rem;color:#9CA3AF;">
        {card_desc}
    </div>
</div>"""
                st.markdown(html.strip(), unsafe_allow_html=True)


def render_generation_panel(api_client):
    """Render the generation input panel"""
    st.markdown("---")
    st.markdown("### ✨ 開始創作")

    prompt = st.text_area(
        "輸入提示詞",
        placeholder="描述你想創作的內容...",
        height=100,
        key="gen_prompt",
        label_visibility="collapsed"
    )

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("🚀 立即生成", key="generate", use_container_width=True, type="primary"):
            if prompt and api_client:
                with st.spinner("生成中..."):
                    result = api_client.demo_generate_image(prompt)
                    if result and result.get("success"):
                        st.session_state.gen_image = result.get("image_url")
                        st.session_state.gen_prompt = prompt
                        st.rerun()

    # Show result if exists
    if st.session_state.get("gen_image"):
        st.markdown("### 🎨 生成結果")
        st.image(st.session_state.gen_image, use_container_width=True)


# =============================================================================
# MAIN PAGE
# =============================================================================
def show_demo_page(api_client=None):
    """Main demo page - douhuiai.com style"""
    init()

    # Inject CSS
    st.markdown(get_css(), unsafe_allow_html=True)

    # Two-column layout: sidebar + main
    sidebar_col, main_col = st.columns([1, 5])

    with sidebar_col:
        render_sidebar()

    with main_col:
        # Top navigation
        render_topnav()

        st.markdown("")

        # Banner area
        render_banner()

        # Category tabs with GO buttons
        render_category_tabs()

        st.markdown("")

        # Feature cards grid
        render_feature_cards()

        # Generation panel
        render_generation_panel(api_client)


if __name__ == "__main__":
    st.set_page_config(
        page_title="Vidgo AI",
        page_icon="🎨",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    show_demo_page()
