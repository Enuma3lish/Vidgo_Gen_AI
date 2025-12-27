"""
Demo Page - AI Image & Video Generation Platform
Layout exactly like douhuiai.com
- Left fixed sidebar with expandable categories
- Top navigation bar
- Main content area with feature tiles
- Inspiration gallery
"""
import streamlit as st
from typing import Optional


# =============================================================================
# TRANSLATIONS (5 languages)
# =============================================================================
TRANSLATIONS = {
    "en": {
        "app_name": "Vidgo AI",
        "nav_home": "Home",
        "nav_ai_create": "AI Creation",
        "nav_api": "API",
        "nav_login": "Login",
        "nav_register": "Register",
        "btn_invite": "Invite Friends",
        "btn_daily": "Daily Points",
        "btn_recharge": "Recharge",

        # Sidebar Categories
        "cat_ai_create": "AI Creation",
        "cat_video": "Video Creation",
        "cat_editing": "Editing Apps",
        "cat_architecture": "Architecture",
        "cat_product": "Product & E-commerce",
        "cat_portrait": "Portrait Photo",
        "cat_batch": "Batch Generation",
        "cat_gallery": "My Works",

        # AI Creation Tools
        "tool_text_to_image": "Text to Image",
        "tool_image_repaint": "Image Repaint",
        "tool_partial_repaint": "Partial Repaint",
        "tool_image_fusion": "Image Fusion",
        "tool_line_art": "Line Art Generate",
        "tool_style_transfer": "Style Transfer",
        "tool_expand": "Image Expand",
        "tool_variation": "Image Variation",
        "tool_reference": "Reference Generate",
        "tool_controlnet": "ControlNet",
        "tool_pose": "Pose Control",
        "tool_depth": "Depth Control",
        "tool_canny": "Edge Control",

        # Video Tools
        "tool_text_to_video": "Text to Video",
        "tool_image_to_video": "Image to Video",
        "tool_video_extend": "Video Extend",
        "tool_video_upscale": "Video Upscale",
        "tool_lip_sync": "Lip Sync",
        "tool_video_style": "Video Style",

        # Editing Tools
        "tool_upscale": "HD Upscale",
        "tool_remove_bg": "Remove Background",
        "tool_colorize": "Colorize",
        "tool_restore": "Photo Restore",
        "tool_face_swap": "Face Swap",
        "tool_remove_object": "Remove Object",
        "tool_replace_bg": "Replace Background",
        "tool_vectorize": "Vectorize",

        # Portrait Tools
        "tool_id_photo": "ID Photo",
        "tool_ai_portrait": "AI Portrait",
        "tool_couple_photo": "Couple Photo",
        "tool_wedding": "Wedding Photo",
        "tool_cosplay": "Cosplay",

        # Feature Cards
        "feat_smart": "Smart Generate",
        "feat_smart_desc": "One-click AI creation",
        "feat_video": "Video Generation",
        "feat_video_desc": "Animate your images",
        "feat_portrait": "AI Portrait",
        "feat_portrait_desc": "Professional photos",
        "feat_3d": "3D Model",
        "feat_3d_desc": "Generate 3D assets",
        "feat_upscale": "HD Upscale",
        "feat_upscale_desc": "Enhance image quality",
        "feat_style": "Style Transfer",
        "feat_style_desc": "Transform art styles",

        # Generation
        "recent_use": "Recent Used",
        "start_create": "Start Creating",
        "upload_hint": "Upload up to 6 images",
        "prompt_placeholder": "Describe what you want to create...",
        "generate_btn": "Generate",
        "generating": "Generating...",

        # Inspiration
        "inspiration_title": "Inspiration Gallery",
        "topic_all": "All",
        "topic_anime": "Anime",
        "topic_realistic": "Realistic",
        "topic_fantasy": "Fantasy",
        "topic_landscape": "Landscape",
        "topic_portrait": "Portrait",
        "topic_3d": "3D Art",

        # Styles
        "style_anime": "Anime",
        "style_realistic": "Realistic",
        "style_3d": "3D Render",
        "style_artistic": "Artistic",
        "style_cyberpunk": "Cyberpunk",
        "style_watercolor": "Watercolor",
        "style_oil": "Oil Painting",
        "style_cinematic": "Cinematic",

        # Limits
        "limit_title": "Free Trial Limit Reached",
        "limit_message": "Sign up to continue creating!",
        "limit_register": "Register Free",
        "limit_login": "Login",
    },
    "zh-TW": {
        "app_name": "Vidgo AI",
        "nav_home": "首頁",
        "nav_ai_create": "AI創作",
        "nav_api": "API服務",
        "nav_login": "登入",
        "nav_register": "註冊",
        "btn_invite": "邀請好友",
        "btn_daily": "每日領點",
        "btn_recharge": "充值",

        "cat_ai_create": "AI創作",
        "cat_video": "視頻創作",
        "cat_editing": "編輯應用",
        "cat_architecture": "建築室內",
        "cat_product": "產品電商",
        "cat_portrait": "人像寫真",
        "cat_batch": "批量生成",
        "cat_gallery": "我的作品",

        "tool_text_to_image": "文字生圖",
        "tool_image_repaint": "圖片重繪",
        "tool_partial_repaint": "局部重繪",
        "tool_image_fusion": "圖片融合",
        "tool_line_art": "線稿生成",
        "tool_style_transfer": "風格轉換",
        "tool_expand": "圖片擴展",
        "tool_variation": "圖片變體",
        "tool_reference": "參考生成",
        "tool_controlnet": "ControlNet",
        "tool_pose": "姿態控制",
        "tool_depth": "深度控制",
        "tool_canny": "邊緣控制",

        "tool_text_to_video": "文字生視頻",
        "tool_image_to_video": "圖片生視頻",
        "tool_video_extend": "視頻延展",
        "tool_video_upscale": "視頻高清",
        "tool_lip_sync": "口型同步",
        "tool_video_style": "視頻風格",

        "tool_upscale": "高清放大",
        "tool_remove_bg": "背景去除",
        "tool_colorize": "圖片上色",
        "tool_restore": "照片修復",
        "tool_face_swap": "換臉",
        "tool_remove_object": "物體移除",
        "tool_replace_bg": "背景替換",
        "tool_vectorize": "矢量化",

        "tool_id_photo": "證件照",
        "tool_ai_portrait": "AI寫真",
        "tool_couple_photo": "情侶照",
        "tool_wedding": "婚紗照",
        "tool_cosplay": "Cosplay",

        "feat_smart": "智能生成",
        "feat_smart_desc": "一鍵AI創作",
        "feat_video": "視頻生成",
        "feat_video_desc": "讓圖片動起來",
        "feat_portrait": "AI寫真",
        "feat_portrait_desc": "專業人像照",
        "feat_3d": "3D模型",
        "feat_3d_desc": "生成3D素材",
        "feat_upscale": "高清放大",
        "feat_upscale_desc": "提升畫質",
        "feat_style": "風格轉換",
        "feat_style_desc": "轉換藝術風格",

        "recent_use": "最近使用",
        "start_create": "立即創作",
        "upload_hint": "單次最多上傳6張圖片",
        "prompt_placeholder": "描述你想創作的內容...",
        "generate_btn": "立即生成",
        "generating": "生成中...",

        "inspiration_title": "作品靈感",
        "topic_all": "全部",
        "topic_anime": "動漫",
        "topic_realistic": "寫實",
        "topic_fantasy": "奇幻",
        "topic_landscape": "風景",
        "topic_portrait": "人像",
        "topic_3d": "3D藝術",

        "style_anime": "動漫",
        "style_realistic": "寫實",
        "style_3d": "3D渲染",
        "style_artistic": "藝術",
        "style_cyberpunk": "賽博龐克",
        "style_watercolor": "水彩",
        "style_oil": "油畫",
        "style_cinematic": "電影感",

        "limit_title": "免費次數已用完",
        "limit_message": "註冊繼續創作！",
        "limit_register": "免費註冊",
        "limit_login": "登入",
    },
    "ja": {
        "app_name": "Vidgo AI",
        "nav_home": "ホーム",
        "nav_ai_create": "AI作成",
        "nav_api": "API",
        "nav_login": "ログイン",
        "nav_register": "登録",
        "btn_invite": "友達を招待",
        "btn_daily": "デイリーポイント",
        "btn_recharge": "チャージ",

        "cat_ai_create": "AI作成",
        "cat_video": "動画作成",
        "cat_editing": "編集アプリ",
        "cat_architecture": "建築",
        "cat_product": "商品・EC",
        "cat_portrait": "ポートレート",
        "cat_batch": "バッチ生成",
        "cat_gallery": "マイ作品",

        "tool_text_to_image": "テキスト→画像",
        "tool_image_repaint": "画像リペイント",
        "tool_partial_repaint": "部分リペイント",
        "tool_image_fusion": "画像合成",
        "tool_line_art": "線画生成",
        "tool_style_transfer": "スタイル変換",
        "tool_expand": "画像拡張",
        "tool_variation": "バリエーション",
        "tool_reference": "参照生成",
        "tool_controlnet": "ControlNet",
        "tool_pose": "ポーズ制御",
        "tool_depth": "深度制御",
        "tool_canny": "エッジ制御",

        "tool_text_to_video": "テキスト→動画",
        "tool_image_to_video": "画像→動画",
        "tool_video_extend": "動画延長",
        "tool_video_upscale": "動画HD化",
        "tool_lip_sync": "リップシンク",
        "tool_video_style": "動画スタイル",

        "tool_upscale": "HD拡大",
        "tool_remove_bg": "背景削除",
        "tool_colorize": "カラー化",
        "tool_restore": "写真修復",
        "tool_face_swap": "顔交換",
        "tool_remove_object": "オブジェクト削除",
        "tool_replace_bg": "背景置換",
        "tool_vectorize": "ベクター化",

        "tool_id_photo": "証明写真",
        "tool_ai_portrait": "AIポートレート",
        "tool_couple_photo": "カップル写真",
        "tool_wedding": "ウェディング",
        "tool_cosplay": "コスプレ",

        "feat_smart": "スマート生成",
        "feat_smart_desc": "ワンクリックAI作成",
        "feat_video": "動画生成",
        "feat_video_desc": "画像をアニメ化",
        "feat_portrait": "AIポートレート",
        "feat_portrait_desc": "プロ仕様の写真",
        "feat_3d": "3Dモデル",
        "feat_3d_desc": "3Dアセット生成",
        "feat_upscale": "HD拡大",
        "feat_upscale_desc": "画質向上",
        "feat_style": "スタイル変換",
        "feat_style_desc": "アートスタイル変換",

        "recent_use": "最近使用",
        "start_create": "作成開始",
        "upload_hint": "最大6枚アップロード可",
        "prompt_placeholder": "作りたいものを説明...",
        "generate_btn": "生成",
        "generating": "生成中...",

        "inspiration_title": "インスピレーション",
        "topic_all": "すべて",
        "topic_anime": "アニメ",
        "topic_realistic": "リアル",
        "topic_fantasy": "ファンタジー",
        "topic_landscape": "風景",
        "topic_portrait": "ポートレート",
        "topic_3d": "3Dアート",

        "style_anime": "アニメ",
        "style_realistic": "リアル",
        "style_3d": "3Dレンダー",
        "style_artistic": "アート",
        "style_cyberpunk": "サイバーパンク",
        "style_watercolor": "水彩画",
        "style_oil": "油絵",
        "style_cinematic": "シネマティック",

        "limit_title": "無料制限に達しました",
        "limit_message": "登録して続ける！",
        "limit_register": "無料登録",
        "limit_login": "ログイン",
    },
    "ko": {
        "app_name": "Vidgo AI",
        "nav_home": "홈",
        "nav_ai_create": "AI 생성",
        "nav_api": "API",
        "nav_login": "로그인",
        "nav_register": "회원가입",
        "btn_invite": "친구 초대",
        "btn_daily": "일일 포인트",
        "btn_recharge": "충전",

        "cat_ai_create": "AI 생성",
        "cat_video": "비디오 생성",
        "cat_editing": "편집 앱",
        "cat_architecture": "건축",
        "cat_product": "상품/이커머스",
        "cat_portrait": "인물 사진",
        "cat_batch": "일괄 생성",
        "cat_gallery": "내 작품",

        "tool_text_to_image": "텍스트→이미지",
        "tool_image_repaint": "이미지 리페인트",
        "tool_partial_repaint": "부분 리페인트",
        "tool_image_fusion": "이미지 합성",
        "tool_line_art": "선화 생성",
        "tool_style_transfer": "스타일 전환",
        "tool_expand": "이미지 확장",
        "tool_variation": "변형",
        "tool_reference": "참조 생성",
        "tool_controlnet": "ControlNet",
        "tool_pose": "포즈 제어",
        "tool_depth": "깊이 제어",
        "tool_canny": "엣지 제어",

        "tool_text_to_video": "텍스트→비디오",
        "tool_image_to_video": "이미지→비디오",
        "tool_video_extend": "비디오 연장",
        "tool_video_upscale": "비디오 HD",
        "tool_lip_sync": "립싱크",
        "tool_video_style": "비디오 스타일",

        "tool_upscale": "HD 업스케일",
        "tool_remove_bg": "배경 제거",
        "tool_colorize": "컬러화",
        "tool_restore": "사진 복원",
        "tool_face_swap": "얼굴 교체",
        "tool_remove_object": "객체 제거",
        "tool_replace_bg": "배경 교체",
        "tool_vectorize": "벡터화",

        "tool_id_photo": "증명사진",
        "tool_ai_portrait": "AI 인물사진",
        "tool_couple_photo": "커플 사진",
        "tool_wedding": "웨딩 사진",
        "tool_cosplay": "코스프레",

        "feat_smart": "스마트 생성",
        "feat_smart_desc": "원클릭 AI 생성",
        "feat_video": "비디오 생성",
        "feat_video_desc": "이미지 애니메이션",
        "feat_portrait": "AI 인물사진",
        "feat_portrait_desc": "프로 사진",
        "feat_3d": "3D 모델",
        "feat_3d_desc": "3D 에셋 생성",
        "feat_upscale": "HD 업스케일",
        "feat_upscale_desc": "화질 향상",
        "feat_style": "스타일 전환",
        "feat_style_desc": "아트 스타일 변환",

        "recent_use": "최근 사용",
        "start_create": "생성 시작",
        "upload_hint": "최대 6장 업로드 가능",
        "prompt_placeholder": "만들고 싶은 것을 설명...",
        "generate_btn": "생성",
        "generating": "생성 중...",

        "inspiration_title": "영감 갤러리",
        "topic_all": "전체",
        "topic_anime": "애니메이션",
        "topic_realistic": "사실적",
        "topic_fantasy": "판타지",
        "topic_landscape": "풍경",
        "topic_portrait": "인물",
        "topic_3d": "3D 아트",

        "style_anime": "애니메이션",
        "style_realistic": "사실적",
        "style_3d": "3D 렌더",
        "style_artistic": "예술적",
        "style_cyberpunk": "사이버펑크",
        "style_watercolor": "수채화",
        "style_oil": "유화",
        "style_cinematic": "시네마틱",

        "limit_title": "무료 한도 도달",
        "limit_message": "가입하여 계속!",
        "limit_register": "무료 가입",
        "limit_login": "로그인",
    },
    "es": {
        "app_name": "Vidgo AI",
        "nav_home": "Inicio",
        "nav_ai_create": "Crear IA",
        "nav_api": "API",
        "nav_login": "Iniciar",
        "nav_register": "Registro",
        "btn_invite": "Invitar Amigos",
        "btn_daily": "Puntos Diarios",
        "btn_recharge": "Recargar",

        "cat_ai_create": "Creación IA",
        "cat_video": "Crear Video",
        "cat_editing": "Apps Edición",
        "cat_architecture": "Arquitectura",
        "cat_product": "Producto/E-commerce",
        "cat_portrait": "Retrato",
        "cat_batch": "Generación Lotes",
        "cat_gallery": "Mis Obras",

        "tool_text_to_image": "Texto a Imagen",
        "tool_image_repaint": "Repintar Imagen",
        "tool_partial_repaint": "Repintado Parcial",
        "tool_image_fusion": "Fusión Imagen",
        "tool_line_art": "Generar Líneas",
        "tool_style_transfer": "Transferir Estilo",
        "tool_expand": "Expandir Imagen",
        "tool_variation": "Variación",
        "tool_reference": "Generar Referencia",
        "tool_controlnet": "ControlNet",
        "tool_pose": "Control Pose",
        "tool_depth": "Control Profundidad",
        "tool_canny": "Control Bordes",

        "tool_text_to_video": "Texto a Video",
        "tool_image_to_video": "Imagen a Video",
        "tool_video_extend": "Extender Video",
        "tool_video_upscale": "Video HD",
        "tool_lip_sync": "Sincronizar Labios",
        "tool_video_style": "Estilo Video",

        "tool_upscale": "HD Ampliar",
        "tool_remove_bg": "Quitar Fondo",
        "tool_colorize": "Colorear",
        "tool_restore": "Restaurar Foto",
        "tool_face_swap": "Cambiar Cara",
        "tool_remove_object": "Quitar Objeto",
        "tool_replace_bg": "Reemplazar Fondo",
        "tool_vectorize": "Vectorizar",

        "tool_id_photo": "Foto ID",
        "tool_ai_portrait": "Retrato IA",
        "tool_couple_photo": "Foto Pareja",
        "tool_wedding": "Foto Boda",
        "tool_cosplay": "Cosplay",

        "feat_smart": "Generar Inteligente",
        "feat_smart_desc": "Creación IA un clic",
        "feat_video": "Generar Video",
        "feat_video_desc": "Animar imágenes",
        "feat_portrait": "Retrato IA",
        "feat_portrait_desc": "Fotos profesionales",
        "feat_3d": "Modelo 3D",
        "feat_3d_desc": "Generar assets 3D",
        "feat_upscale": "HD Ampliar",
        "feat_upscale_desc": "Mejorar calidad",
        "feat_style": "Transferir Estilo",
        "feat_style_desc": "Transformar estilos",

        "recent_use": "Uso Reciente",
        "start_create": "Empezar a Crear",
        "upload_hint": "Máximo 6 imágenes",
        "prompt_placeholder": "Describe lo que quieres crear...",
        "generate_btn": "Generar",
        "generating": "Generando...",

        "inspiration_title": "Galería Inspiración",
        "topic_all": "Todo",
        "topic_anime": "Anime",
        "topic_realistic": "Realista",
        "topic_fantasy": "Fantasía",
        "topic_landscape": "Paisaje",
        "topic_portrait": "Retrato",
        "topic_3d": "Arte 3D",

        "style_anime": "Anime",
        "style_realistic": "Realista",
        "style_3d": "Render 3D",
        "style_artistic": "Artístico",
        "style_cyberpunk": "Cyberpunk",
        "style_watercolor": "Acuarela",
        "style_oil": "Óleo",
        "style_cinematic": "Cinematográfico",

        "limit_title": "Límite Alcanzado",
        "limit_message": "¡Regístrate para continuar!",
        "limit_register": "Registro Gratis",
        "limit_login": "Iniciar Sesión",
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
    lang = st.session_state.get("lang", "en")
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)


# =============================================================================
# DATA - Sidebar categories and tools
# =============================================================================
SIDEBAR_MENU = [
    {
        "id": "ai_create",
        "key": "cat_ai_create",
        "icon": "🎨",
        "tools": [
            {"id": "text_to_image", "key": "tool_text_to_image", "hot": True},
            {"id": "image_repaint", "key": "tool_image_repaint"},
            {"id": "partial_repaint", "key": "tool_partial_repaint", "new": True},
            {"id": "image_fusion", "key": "tool_image_fusion"},
            {"id": "line_art", "key": "tool_line_art"},
            {"id": "style_transfer", "key": "tool_style_transfer"},
            {"id": "expand", "key": "tool_expand"},
            {"id": "variation", "key": "tool_variation"},
            {"id": "reference", "key": "tool_reference", "new": True},
            {"id": "controlnet", "key": "tool_controlnet"},
            {"id": "pose", "key": "tool_pose"},
            {"id": "depth", "key": "tool_depth"},
            {"id": "canny", "key": "tool_canny"},
        ]
    },
    {
        "id": "video",
        "key": "cat_video",
        "icon": "🎬",
        "tools": [
            {"id": "text_to_video", "key": "tool_text_to_video", "new": True},
            {"id": "image_to_video", "key": "tool_image_to_video", "hot": True},
            {"id": "video_extend", "key": "tool_video_extend"},
            {"id": "video_upscale", "key": "tool_video_upscale"},
            {"id": "lip_sync", "key": "tool_lip_sync", "new": True},
            {"id": "video_style", "key": "tool_video_style"},
        ]
    },
    {
        "id": "editing",
        "key": "cat_editing",
        "icon": "✂️",
        "tools": [
            {"id": "upscale", "key": "tool_upscale", "hot": True},
            {"id": "remove_bg", "key": "tool_remove_bg"},
            {"id": "colorize", "key": "tool_colorize"},
            {"id": "restore", "key": "tool_restore"},
            {"id": "face_swap", "key": "tool_face_swap"},
            {"id": "remove_object", "key": "tool_remove_object", "new": True},
            {"id": "replace_bg", "key": "tool_replace_bg"},
            {"id": "vectorize", "key": "tool_vectorize"},
        ]
    },
    {
        "id": "architecture",
        "key": "cat_architecture",
        "icon": "🏠",
        "tools": []
    },
    {
        "id": "product",
        "key": "cat_product",
        "icon": "🛍️",
        "tools": []
    },
    {
        "id": "portrait",
        "key": "cat_portrait",
        "icon": "👤",
        "tools": [
            {"id": "id_photo", "key": "tool_id_photo"},
            {"id": "ai_portrait", "key": "tool_ai_portrait", "hot": True},
            {"id": "couple_photo", "key": "tool_couple_photo"},
            {"id": "wedding", "key": "tool_wedding"},
            {"id": "cosplay", "key": "tool_cosplay", "new": True},
        ]
    },
    {
        "id": "batch",
        "key": "cat_batch",
        "icon": "📦",
        "tools": []
    },
    {
        "id": "gallery",
        "key": "cat_gallery",
        "icon": "🖼️",
        "tools": []
    },
]

FEATURE_CARDS = [
    {"id": "smart", "icon": "🧠", "key": "feat_smart", "desc": "feat_smart_desc", "new": True},
    {"id": "video", "icon": "🎬", "key": "feat_video", "desc": "feat_video_desc", "hot": True},
    {"id": "portrait", "icon": "👤", "key": "feat_portrait", "desc": "feat_portrait_desc"},
    {"id": "3d", "icon": "📦", "key": "feat_3d", "desc": "feat_3d_desc", "new": True},
    {"id": "upscale", "icon": "🔍", "key": "feat_upscale", "desc": "feat_upscale_desc"},
    {"id": "style", "icon": "🎭", "key": "feat_style", "desc": "feat_style_desc"},
]

TOPICS = ["all", "anime", "realistic", "fantasy", "landscape", "portrait", "3d"]

IMAGES = {
    "all": [f"https://picsum.photos/seed/all{i}/300/400" for i in range(12)],
    "anime": [f"https://picsum.photos/seed/anime{i}/300/400" for i in range(8)],
    "realistic": [f"https://picsum.photos/seed/real{i}/300/400" for i in range(8)],
    "fantasy": [f"https://picsum.photos/seed/fan{i}/300/400" for i in range(8)],
    "landscape": [f"https://picsum.photos/seed/land{i}/400/280" for i in range(8)],
    "portrait": [f"https://picsum.photos/seed/port{i}/300/450" for i in range(8)],
    "3d": [f"https://picsum.photos/seed/3d{i}/300/300" for i in range(8)],
}

STYLES = [
    {"id": "anime", "icon": "🎨"},
    {"id": "realistic", "icon": "📷"},
    {"id": "3d", "icon": "🎮"},
    {"id": "artistic", "icon": "🖼️"},
    {"id": "cyberpunk", "icon": "🤖"},
    {"id": "watercolor", "icon": "💧"},
    {"id": "oil", "icon": "🎨"},
    {"id": "cinematic", "icon": "🎬"},
]

RATIOS = ["1:1", "4:3", "3:4", "16:9", "9:16"]


# =============================================================================
# CSS - Full page layout like douhuiai.com
# =============================================================================
def get_css():
    return """
<style>
/* Hide Streamlit defaults */
#MainMenu, footer, header, .stDeployButton,
[data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"] { display: none !important; }

/* Full page dark theme */
.stApp { background: #0d0d1a !important; }
.block-container {
    padding: 0 !important;
    max-width: 100% !important;
    margin: 0 !important;
}

/* Hide default sidebar */
section[data-testid="stSidebar"] { display: none !important; }

/* Main layout container */
.main-container {
    display: flex;
    min-height: 100vh;
}

/* LEFT SIDEBAR - Fixed */
.left-sidebar {
    width: 220px;
    min-width: 220px;
    background: linear-gradient(180deg, #12122a 0%, #0d0d1a 100%);
    border-right: 1px solid #2a2a4a;
    padding: 16px 0;
    position: fixed;
    left: 0;
    top: 0;
    height: 100vh;
    overflow-y: auto;
    z-index: 100;
}

.sidebar-logo {
    padding: 8px 16px 24px;
    font-size: 1.3rem;
    font-weight: 800;
    background: linear-gradient(135deg, #667eea, #764ba2);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.sidebar-category {
    padding: 10px 16px;
    color: #a0a0c0;
    font-size: 0.9rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 10px;
    transition: all 0.2s;
}

.sidebar-category:hover {
    background: rgba(102, 126, 234, 0.1);
    color: #fff;
}

.sidebar-category.active {
    background: rgba(102, 126, 234, 0.2);
    color: #667eea;
    border-left: 3px solid #667eea;
}

.sidebar-tools {
    padding-left: 40px;
    display: none;
}

.sidebar-tools.show {
    display: block;
}

.sidebar-tool {
    padding: 8px 16px;
    color: #888;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.2s;
}

.sidebar-tool:hover {
    color: #fff;
    background: rgba(102, 126, 234, 0.1);
}

.sidebar-tool.active {
    color: #667eea;
}

.badge-new {
    background: #10b981;
    color: #fff;
    font-size: 0.6rem;
    padding: 2px 6px;
    border-radius: 4px;
    margin-left: 6px;
}

.badge-hot {
    background: #ef4444;
    color: #fff;
    font-size: 0.6rem;
    padding: 2px 6px;
    border-radius: 4px;
    margin-left: 6px;
}

/* MAIN CONTENT - With left margin for sidebar */
.main-content {
    margin-left: 220px;
    flex: 1;
    padding: 0;
}

/* TOP NAVIGATION */
.top-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 24px;
    background: rgba(13, 13, 26, 0.95);
    border-bottom: 1px solid #2a2a4a;
    position: sticky;
    top: 0;
    z-index: 50;
}

.top-nav-left {
    display: flex;
    align-items: center;
    gap: 24px;
}

.top-nav-item {
    color: #a0a0c0;
    font-size: 0.9rem;
    cursor: pointer;
    padding: 8px 12px;
    border-radius: 8px;
    transition: all 0.2s;
}

.top-nav-item:hover {
    color: #fff;
    background: rgba(102, 126, 234, 0.1);
}

.top-nav-right {
    display: flex;
    align-items: center;
    gap: 12px;
}

.nav-btn {
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.2s;
}

.nav-btn-ghost {
    color: #a0a0c0;
    background: transparent;
    border: 1px solid #3a3a5a;
}

.nav-btn-ghost:hover {
    color: #fff;
    border-color: #667eea;
}

.nav-btn-primary {
    color: #fff;
    background: linear-gradient(135deg, #667eea, #764ba2);
    border: none;
}

/* CONTENT AREA */
.content-area {
    padding: 24px;
}

/* Feature Cards Grid */
.feature-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 32px;
}

.feature-card {
    background: linear-gradient(135deg, #1a1a35 0%, #12122a 100%);
    border: 1px solid #2a2a4a;
    border-radius: 16px;
    padding: 24px;
    cursor: pointer;
    transition: all 0.3s;
    position: relative;
    overflow: hidden;
}

.feature-card:hover {
    transform: translateY(-4px);
    border-color: #667eea;
    box-shadow: 0 8px 32px rgba(102, 126, 234, 0.2);
}

.feature-card-icon {
    font-size: 2.5rem;
    margin-bottom: 12px;
}

.feature-card-title {
    color: #fff;
    font-size: 1.1rem;
    font-weight: 600;
    margin-bottom: 8px;
}

.feature-card-desc {
    color: #888;
    font-size: 0.85rem;
}

.feature-card .badge-new,
.feature-card .badge-hot {
    position: absolute;
    top: 12px;
    right: 12px;
}

/* Inspiration Gallery */
.inspiration-section {
    margin-top: 32px;
}

.section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
}

.section-title {
    color: #fff;
    font-size: 1.2rem;
    font-weight: 600;
}

.topic-tabs {
    display: flex;
    gap: 8px;
}

.topic-tab {
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.2s;
    color: #888;
    background: #1a1a35;
    border: 1px solid transparent;
}

.topic-tab:hover {
    color: #fff;
    border-color: #3a3a5a;
}

.topic-tab.active {
    color: #fff;
    background: linear-gradient(135deg, #667eea, #764ba2);
}

/* Image Grid - Masonry style */
.image-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
}

.image-card {
    border-radius: 12px;
    overflow: hidden;
    cursor: pointer;
    transition: all 0.3s;
}

.image-card:hover {
    transform: scale(1.02);
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
}

.image-card img {
    width: 100%;
    display: block;
}

/* Generation Panel */
.gen-panel {
    background: #12122a;
    border: 1px solid #2a2a4a;
    border-radius: 16px;
    padding: 24px;
    margin-top: 32px;
}

.gen-title {
    color: #fff;
    font-size: 1.1rem;
    font-weight: 600;
    margin-bottom: 16px;
}

/* Streamlit overrides */
.stSelectbox > label { display: none !important; }
.stTextArea > label { display: none !important; }
div[data-testid="stVerticalBlock"] { gap: 0.5rem !important; }
</style>
"""


# =============================================================================
# COMPONENTS
# =============================================================================
def init():
    """Initialize session state"""
    defaults = {
        "lang": "en",
        "category": "ai_create",
        "tool": "text_to_image",
        "topic": "all",
        "style": "anime",
        "usage": 0,
        "expanded_cats": ["ai_create"],  # Which categories are expanded
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def render_sidebar_html():
    """Generate sidebar HTML"""
    html = f'''
    <div class="left-sidebar">
        <div class="sidebar-logo">🎨 {t("app_name")}</div>
    '''

    for cat in SIDEBAR_MENU:
        is_active = st.session_state.category == cat["id"]
        active_class = "active" if is_active else ""

        html += f'''
        <div class="sidebar-category {active_class}" onclick="window.location.href='?cat={cat["id"]}'">
            <span>{cat["icon"]}</span>
            <span>{t(cat["key"])}</span>
        </div>
        '''

        # Show tools if this category is active
        if is_active and cat["tools"]:
            html += '<div class="sidebar-tools show">'
            for tool in cat["tools"]:
                tool_active = "active" if st.session_state.tool == tool["id"] else ""
                badge = ""
                if tool.get("new"):
                    badge = '<span class="badge-new">NEW</span>'
                elif tool.get("hot"):
                    badge = '<span class="badge-hot">HOT</span>'
                html += f'''
                <div class="sidebar-tool {tool_active}">
                    {t(tool["key"])}{badge}
                </div>
                '''
            html += '</div>'

    html += '</div>'
    return html


def render_topnav_html():
    """Generate top navigation HTML"""
    lang_options = "".join([
        f'<option value="{k}" {"selected" if st.session_state.lang == k else ""}>{v}</option>'
        for k, v in LANGUAGES.items()
    ])

    return f'''
    <div class="top-nav">
        <div class="top-nav-left">
            <div class="top-nav-item">{t("nav_home")}</div>
            <div class="top-nav-item">{t("nav_ai_create")}</div>
            <div class="top-nav-item">{t("nav_api")}</div>
        </div>
        <div class="top-nav-right">
            <select style="background:#1a1a35;color:#fff;border:1px solid #3a3a5a;border-radius:8px;padding:6px 12px;font-size:0.85rem;">
                {lang_options}
            </select>
            <div class="nav-btn nav-btn-ghost">{t("btn_daily")}</div>
            <div class="nav-btn nav-btn-ghost">{t("btn_recharge")}</div>
            <div class="nav-btn nav-btn-ghost">{t("nav_login")}</div>
            <div class="nav-btn nav-btn-primary">{t("nav_register")}</div>
        </div>
    </div>
    '''


def render_feature_cards_html():
    """Generate feature cards HTML"""
    html = '<div class="feature-grid">'

    for card in FEATURE_CARDS:
        badge = ""
        if card.get("new"):
            badge = '<span class="badge-new">NEW</span>'
        elif card.get("hot"):
            badge = '<span class="badge-hot">HOT</span>'

        html += f'''
        <div class="feature-card">
            {badge}
            <div class="feature-card-icon">{card["icon"]}</div>
            <div class="feature-card-title">{t(card["key"])}</div>
            <div class="feature-card-desc">{t(card["desc"])}</div>
        </div>
        '''

    html += '</div>'
    return html


def render_inspiration_html():
    """Generate inspiration gallery HTML"""
    # Topic tabs
    topic_tabs = '<div class="topic-tabs">'
    for topic in TOPICS:
        active = "active" if st.session_state.topic == topic else ""
        topic_tabs += f'<div class="topic-tab {active}">{t(f"topic_{topic}")}</div>'
    topic_tabs += '</div>'

    # Image grid
    images = IMAGES.get(st.session_state.topic, IMAGES["all"])
    image_grid = '<div class="image-grid">'
    for img in images:
        image_grid += f'''
        <div class="image-card">
            <img src="{img}" alt="inspiration" loading="lazy">
        </div>
        '''
    image_grid += '</div>'

    return f'''
    <div class="inspiration-section">
        <div class="section-header">
            <div class="section-title">💡 {t("inspiration_title")}</div>
            {topic_tabs}
        </div>
        {image_grid}
    </div>
    '''


def render_sidebar():
    """Render sidebar with Streamlit components"""
    # Sidebar navigation using expanders
    st.markdown(f"""
    <div style="font-size:1.3rem;font-weight:800;background:linear-gradient(135deg,#667eea,#764ba2);
               -webkit-background-clip:text;-webkit-text-fill-color:transparent;padding:8px 0 16px;">
        🎨 {t('app_name')}
    </div>
    """, unsafe_allow_html=True)

    for cat in SIDEBAR_MENU:
        is_active = st.session_state.category == cat["id"]

        # Category button
        btn_type = "primary" if is_active else "secondary"
        if st.button(f"{cat['icon']} {t(cat['key'])}", key=f"cat_{cat['id']}",
                    use_container_width=True, type=btn_type):
            st.session_state.category = cat["id"]
            if cat["tools"]:
                st.session_state.tool = cat["tools"][0]["id"]
            st.rerun()

        # Show tools if active
        if is_active and cat["tools"]:
            for tool in cat["tools"]:
                tool_active = st.session_state.tool == tool["id"]
                label = f"  ├ {t(tool['key'])}"
                if tool.get("new"):
                    label += " 🆕"
                elif tool.get("hot"):
                    label += " 🔥"

                if st.button(label, key=f"tool_{tool['id']}", use_container_width=True,
                            type="primary" if tool_active else "secondary"):
                    st.session_state.tool = tool["id"]
                    st.rerun()


def render_topnav():
    """Render top navigation with Streamlit components"""
    cols = st.columns([1.5, 1, 1, 1, 1.5, 1, 1, 1.2])

    with cols[0]:
        st.markdown(f"""
        <div style="font-size:1.2rem;font-weight:700;color:#667eea;">
            🎨 {t('app_name')}
        </div>
        """, unsafe_allow_html=True)

    with cols[1]:
        if st.button(t("nav_home"), key="nav_home", use_container_width=True):
            st.session_state['landing_view'] = 'demo'
            st.rerun()

    with cols[2]:
        st.button(t("nav_ai_create"), key="nav_ai", use_container_width=True)

    with cols[3]:
        st.button(t("nav_api"), key="nav_api", use_container_width=True)

    with cols[4]:
        # Language dropdown
        lang_list = list(LANGUAGES.keys())
        idx = lang_list.index(st.session_state.lang) if st.session_state.lang in lang_list else 0
        new_lang = st.selectbox("🌐", options=lang_list, format_func=lambda x: LANGUAGES[x],
                               index=idx, key="lang_sel", label_visibility="collapsed")
        if new_lang != st.session_state.lang:
            st.session_state.lang = new_lang
            st.rerun()

    with cols[5]:
        st.button(t("btn_daily"), key="daily", use_container_width=True)

    with cols[6]:
        if st.button(t("nav_login"), key="login", use_container_width=True):
            st.session_state['landing_view'] = 'login'
            st.rerun()

    with cols[7]:
        if st.button(t("nav_register"), key="register", use_container_width=True, type="primary"):
            st.session_state['landing_view'] = 'register'
            st.rerun()


def render_feature_cards():
    """Render feature cards with Streamlit"""
    cols = st.columns(3)
    for i, card in enumerate(FEATURE_CARDS):
        with cols[i % 3]:
            badge = ""
            if card.get("new"):
                badge = "🆕 "
            elif card.get("hot"):
                badge = "🔥 "

            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#1a1a35,#12122a);border:1px solid #2a2a4a;
                       border-radius:16px;padding:20px;margin-bottom:16px;cursor:pointer;
                       transition:all 0.3s;">
                <div style="font-size:2rem;margin-bottom:8px;">{card["icon"]}</div>
                <div style="color:#fff;font-size:1rem;font-weight:600;">{badge}{t(card["key"])}</div>
                <div style="color:#888;font-size:0.8rem;margin-top:4px;">{t(card["desc"])}</div>
            </div>
            """, unsafe_allow_html=True)


def render_inspiration():
    """Render inspiration gallery"""
    st.markdown(f"### 💡 {t('inspiration_title')}")

    # Topic tabs
    cols = st.columns(len(TOPICS))
    for i, topic in enumerate(TOPICS):
        with cols[i]:
            is_active = st.session_state.topic == topic
            if st.button(t(f"topic_{topic}"), key=f"tp_{topic}", use_container_width=True,
                        type="primary" if is_active else "secondary"):
                st.session_state.topic = topic
                st.rerun()

    st.markdown("")

    # Image grid
    images = IMAGES.get(st.session_state.topic, IMAGES["all"])
    cols = st.columns(4)
    for i, img in enumerate(images):
        with cols[i % 4]:
            st.markdown(f'''
            <div style="margin-bottom:12px;border-radius:12px;overflow:hidden;cursor:pointer;
                       transition:all 0.3s;">
                <img src="{img}" style="width:100%;display:block;border-radius:12px;">
            </div>
            ''', unsafe_allow_html=True)


def render_generation(api_client):
    """Render generation panel"""
    # Get current tool info
    tool_info = None
    for cat in SIDEBAR_MENU:
        for ti in cat["tools"]:
            if ti["id"] == st.session_state.tool:
                tool_info = ti
                break

    if tool_info:
        st.markdown(f"### ✨ {t(tool_info['key'])}")
    else:
        st.markdown(f"### ✨ {t('tool_text_to_image')}")

    # Style selection for applicable tools
    if st.session_state.tool in ["text_to_image", "image_repaint", "style_transfer", "variation"]:
        st.markdown(f"**{t('style_anime')} / {t('style_realistic')} / ...**")
        cols = st.columns(4)
        for i, s in enumerate(STYLES[:4]):
            with cols[i]:
                sid = s["id"]
                if st.button(f"{s['icon']} {t(f'style_{sid}')}", key=f"st_{sid}",
                            use_container_width=True,
                            type="primary" if st.session_state.style == sid else "secondary"):
                    st.session_state.style = sid
                    st.rerun()

        cols = st.columns(4)
        for i, s in enumerate(STYLES[4:]):
            with cols[i]:
                sid = s["id"]
                if st.button(f"{s['icon']} {t(f'style_{sid}')}", key=f"st2_{sid}",
                            use_container_width=True,
                            type="primary" if st.session_state.style == sid else "secondary"):
                    st.session_state.style = sid
                    st.rerun()

    st.markdown("")
    st.selectbox("Ratio", RATIOS, key="ratio", label_visibility="collapsed")

    prompt = st.text_area("Prompt", placeholder=t("prompt_placeholder"),
                         height=100, key="prompt", label_visibility="collapsed")

    st.markdown("")
    if st.button(f"🚀 {t('generate_btn')}", key="gen", use_container_width=True, type="primary"):
        if prompt:
            do_generate(api_client, prompt)


def do_generate(api_client, prompt):
    """Execute generation"""
    if st.session_state.usage >= 2 and not st.session_state.get("user_id"):
        show_limit()
        return

    if api_client:
        mod = api_client.demo_moderate_prompt(prompt)
        if mod and not mod.get("is_safe", True):
            st.error("⚠️ Content not allowed")
            return

    with st.spinner(t("generating")):
        if api_client:
            result = api_client.demo_generate_image(prompt, style=st.session_state.style)
            if result and result.get("success"):
                st.session_state.gen_image = result.get("image_url")
                st.session_state.gen_original = result.get("original_url")
                st.session_state.gen_prompt = prompt
                st.session_state.usage += 1
                st.rerun()
            else:
                st.error("❌ Generation failed")
        else:
            st.warning("Backend not connected")


def render_result(api_client):
    """Render generation result"""
    if not st.session_state.get("gen_image"):
        return False

    st.markdown("### 🎨 Result")
    c1, c2 = st.columns([2, 1])

    with c1:
        st.image(st.session_state.gen_image, use_container_width=True)

    with c2:
        prompt_preview = st.session_state.gen_prompt[:80] + "..." if len(st.session_state.gen_prompt) > 80 else st.session_state.gen_prompt
        st.markdown(f'''
        <div style="background:#1a1a30;border-radius:8px;padding:12px;margin-bottom:12px;">
            <div style="color:#666;font-size:0.75rem;">Prompt</div>
            <div style="color:#fff;font-size:0.85rem;margin-top:4px;">{prompt_preview}</div>
        </div>
        ''', unsafe_allow_html=True)

        if st.button("🎬 Generate Video", key="vid", use_container_width=True, type="primary"):
            with st.spinner(t("generating")):
                if api_client:
                    res = api_client.demo_generate_video(
                        prompt=st.session_state.gen_prompt,
                        image_url=st.session_state.get("gen_original") or st.session_state.gen_image,
                        style=st.session_state.style
                    )
                    if res and res.get("success"):
                        st.session_state.gen_video = res
                        st.rerun()

        if st.button("🔄 Regenerate", key="regen", use_container_width=True):
            for k in ["gen_image", "gen_original", "gen_prompt", "gen_video"]:
                st.session_state.pop(k, None)
            st.rerun()

    if st.session_state.get("gen_video") and st.session_state.gen_video.get("video_url"):
        st.markdown("### 🎬 Video")
        import streamlit.components.v1 as components
        video_url = st.session_state.gen_video["video_url"]
        components.html(f'''
        <video autoplay loop muted playsinline style="width:100%;max-width:500px;border-radius:12px;">
            <source src="{video_url}" type="video/mp4">
        </video>
        ''', height=300)

    return True


def show_limit():
    """Show usage limit message"""
    st.markdown(f'''
    <div style="background:rgba(239,68,68,0.1);border:1px solid #ef4444;border-radius:16px;
               padding:40px;text-align:center;margin:20px 0;">
        <div style="color:#ef4444;font-size:1.3rem;font-weight:700;">⚠️ {t("limit_title")}</div>
        <div style="color:#888;margin:12px 0;">{t("limit_message")}</div>
    </div>
    ''', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button(t("limit_register"), type="primary", use_container_width=True):
            st.session_state["landing_view"] = "register"
            st.rerun()
    with c2:
        if st.button(t("limit_login"), use_container_width=True):
            st.session_state["landing_view"] = "login"
            st.rerun()


# =============================================================================
# MAIN PAGE - Layout like douhuiai.com
# =============================================================================
def show_demo_page(api_client=None):
    """Main demo page with sidebar layout like douhuiai.com"""
    init()

    # Inject CSS
    st.markdown(get_css(), unsafe_allow_html=True)

    # Create two-column layout: sidebar + main content
    sidebar_col, main_col = st.columns([1, 4])

    with sidebar_col:
        render_sidebar()

    with main_col:
        # Top navigation
        render_topnav()
        st.markdown("---")

        # Check usage limit
        if st.session_state.usage >= 2 and not st.session_state.get("user_id"):
            show_limit()
            return

        # Show result if exists
        if render_result(api_client):
            return

        # Feature cards
        render_feature_cards()

        # Inspiration gallery
        render_inspiration()

        st.markdown("---")

        # Generation panel
        render_generation(api_client)


if __name__ == "__main__":
    st.set_page_config(page_title="Vidgo AI", page_icon="🎨", layout="wide")
    show_demo_page()
