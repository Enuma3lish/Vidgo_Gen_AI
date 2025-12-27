"""
Demo Page - AI Clothing Transform & Advanced Effects Showcase
VidGo - Smart Demo Engine with Multi-language Support

Features:
- AI Clothing Transformation demos
- Advanced style effects showcase
- Multi-language prompt support (EN, ZH-TW, JA, KO, ES)
- Real-time content moderation with block cache
"""
import streamlit as st
from typing import Optional, Dict, Any, List
import time


def get_demo_css() -> str:
    """Get CSS styles for demo page"""
    return """
    <style>
        /* Demo Page Header */
        .demo-header {
            font-size: 2.5rem;
            font-weight: 800;
            text-align: center;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .demo-subtitle {
            font-size: 1.2rem;
            text-align: center;
            color: #6B7280;
            margin-bottom: 2rem;
        }

        /* Feature Cards */
        .feature-card {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            border-radius: 20px;
            padding: 30px;
            margin: 15px 0;
            border: 2px solid #333;
            transition: all 0.3s ease;
        }

        .feature-card:hover {
            border-color: #667eea;
            transform: translateY(-5px);
            box-shadow: 0 10px 40px rgba(102, 126, 234, 0.3);
        }

        .feature-icon {
            font-size: 3rem;
            margin-bottom: 15px;
        }

        .feature-title {
            font-size: 1.5rem;
            font-weight: 700;
            color: #FFFFFF;
            margin-bottom: 10px;
        }

        .feature-desc {
            color: #9CA3AF;
            font-size: 1rem;
            line-height: 1.6;
        }

        /* Demo Preview */
        .demo-preview {
            background: #1a1a2e;
            border-radius: 15px;
            padding: 20px;
            margin: 20px 0;
        }

        .before-after-container {
            display: flex;
            gap: 20px;
            justify-content: center;
            align-items: center;
        }

        .before-after-label {
            font-size: 0.9rem;
            color: #9CA3AF;
            text-align: center;
            margin-bottom: 10px;
        }

        /* Style Gallery */
        .style-card {
            background: linear-gradient(145deg, #1e1e30 0%, #252542 100%);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            border: 1px solid #333;
            transition: all 0.3s ease;
        }

        .style-card:hover {
            border-color: #f093fb;
            transform: scale(1.05);
        }

        .style-name {
            font-weight: 600;
            color: #FFFFFF;
            margin-top: 10px;
        }

        /* Prompt Input Area */
        .prompt-area {
            background: linear-gradient(135deg, #1a1a2e 0%, #0f0f1a 100%);
            border-radius: 20px;
            padding: 30px;
            margin: 20px 0;
            border: 2px solid #333;
        }

        /* Language Badge */
        .lang-badge {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
            margin: 5px;
        }

        .lang-badge-active {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }

        .lang-badge-inactive {
            background: #2d2d44;
            color: #9CA3AF;
        }

        /* Result Card */
        .result-card {
            background: linear-gradient(135deg, #0f3460 0%, #16213e 100%);
            border-radius: 15px;
            padding: 25px;
            margin: 20px 0;
            border: 2px solid #1a5f7a;
        }

        .result-success {
            border-color: #10B981;
            background: linear-gradient(135deg, #064e3b 0%, #065f46 100%);
        }

        .result-error {
            border-color: #EF4444;
            background: linear-gradient(135deg, #7f1d1d 0%, #991b1b 100%);
        }

        /* CTA Button */
        .cta-button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 40px;
            border-radius: 30px;
            font-size: 1.1rem;
            font-weight: 700;
            border: none;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .cta-button:hover {
            transform: scale(1.05);
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
        }

        /* Stats Card */
        .stats-card {
            background: #1a1a2e;
            border-radius: 10px;
            padding: 15px;
            text-align: center;
        }

        .stats-number {
            font-size: 2rem;
            font-weight: 800;
            color: #667eea;
        }

        .stats-label {
            color: #9CA3AF;
            font-size: 0.9rem;
        }

        /* Upgrade Banner */
        .upgrade-banner {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            border-radius: 15px;
            padding: 25px;
            text-align: center;
            margin: 30px 0;
        }

        .upgrade-text {
            color: white;
            font-size: 1.2rem;
            font-weight: 600;
        }
    </style>
    """


# ==========================================
# CLOTHING TRANSFORM - Styles and Prompts
# ==========================================
CLOTHING_STYLES = [
    {"id": 1, "name": "Casual Wear", "slug": "casual-wear"},
    {"id": 2, "name": "Formal Suit", "slug": "formal-suit"},
    {"id": 3, "name": "Evening Dress", "slug": "evening-dress"},
    {"id": 4, "name": "Streetwear", "slug": "streetwear"},
    {"id": 5, "name": "Vintage Style", "slug": "vintage-style"},
    {"id": 6, "name": "Sporty Look", "slug": "sporty-look"},
]

# Quick example for each clothing style (multi-language)
CLOTHING_STYLE_EXAMPLES = {
    "en": {
        "Casual Wear": "Relaxed jeans and white t-shirt",
        "Formal Suit": "Navy blue business suit",
        "Evening Dress": "Elegant black evening gown",
        "Streetwear": "Trendy hoodie and sneakers",
        "Vintage Style": "1950s retro dress",
        "Sporty Look": "Athletic wear with trainers",
    },
    "zh-TW": {
        "Casual Wear": "輕鬆牛仔褲配白T恤",
        "Formal Suit": "深藍色商務西裝",
        "Evening Dress": "優雅黑色晚禮服",
        "Streetwear": "時尚連帽衫配球鞋",
        "Vintage Style": "1950年代復古洋裝",
        "Sporty Look": "運動服配運動鞋",
    },
    "ja": {
        "Casual Wear": "リラックスジーンズと白Tシャツ",
        "Formal Suit": "ネイビーブルーのビジネススーツ",
        "Evening Dress": "エレガントな黒のイブニングドレス",
        "Streetwear": "トレンディなパーカーとスニーカー",
        "Vintage Style": "1950年代のレトロドレス",
        "Sporty Look": "トレーナー付きアスレチックウェア",
    },
    "ko": {
        "Casual Wear": "편안한 청바지와 흰색 티셔츠",
        "Formal Suit": "네이비 블루 비즈니스 정장",
        "Evening Dress": "우아한 블랙 이브닝 드레스",
        "Streetwear": "트렌디한 후드티와 스니커즈",
        "Vintage Style": "1950년대 레트로 드레스",
        "Sporty Look": "운동복과 트레이너",
    },
    "es": {
        "Casual Wear": "Jeans relajados y camiseta blanca",
        "Formal Suit": "Traje de negocios azul marino",
        "Evening Dress": "Elegante vestido de noche negro",
        "Streetwear": "Sudadera con capucha y zapatillas",
        "Vintage Style": "Vestido retro de los años 50",
        "Sporty Look": "Ropa deportiva con zapatillas",
    },
}

CLOTHING_PROMPTS = {
    "en": [
        "Transform into a elegant black evening dress",
        "Change outfit to casual summer wear",
        "Apply formal business suit style",
        "Transform to trendy streetwear look",
    ],
    "zh-TW": [
        "換成優雅的黑色晚禮服",
        "換成休閒夏日穿搭",
        "換成正式商務西裝",
        "換成時尚街頭風格",
    ],
    "ja": [
        "エレガントな黒のイブニングドレスに変身",
        "カジュアルな夏服に着替え",
        "フォーマルなビジネススーツスタイルに",
        "トレンディなストリートウェアに変身",
    ],
    "ko": [
        "우아한 블랙 이브닝 드레스로 변신",
        "캐주얼 여름 옷으로 변경",
        "정장 비즈니스 슈트 스타일 적용",
        "트렌디한 스트리트 패션으로 변신",
    ],
    "es": [
        "Transformar en un elegante vestido de noche negro",
        "Cambiar a ropa casual de verano",
        "Aplicar estilo de traje formal de negocios",
        "Transformar a look streetwear moderno",
    ],
}

# ==========================================
# ADVANCED EFFECTS - Styles and Prompts
# ==========================================
ADVANCED_STYLES = [
    {"id": 122, "name": "Japanese Anime", "slug": "japanese-anime"},
    {"id": 124, "name": "Pixar Style", "slug": "pixar-style"},
    {"id": 132, "name": "Makoto Shinkai", "slug": "makoto-shinkai"},
    {"id": 179, "name": "Cyberpunk", "slug": "cyberpunk"},
    {"id": 134, "name": "Watercolor", "slug": "watercolor"},
    {"id": 127, "name": "Oil Painting", "slug": "oil-painting"},
]

# Quick example for each advanced style (multi-language)
ADVANCED_STYLE_EXAMPLES = {
    "en": {
        "Japanese Anime": "A girl with big eyes in school uniform",
        "Pixar Style": "A cute robot exploring the city",
        "Makoto Shinkai": "Sunset clouds over Tokyo skyline",
        "Cyberpunk": "Neon-lit streets with flying cars",
        "Watercolor": "Flowers blooming in spring garden",
        "Oil Painting": "Portrait of a noble lady",
    },
    "zh-TW": {
        "Japanese Anime": "穿著校服的大眼睛女孩",
        "Pixar Style": "探索城市的可愛機器人",
        "Makoto Shinkai": "東京天際線上的夕陽雲彩",
        "Cyberpunk": "霓虹燈街道與飛行汽車",
        "Watercolor": "春天花園裡盛開的花朵",
        "Oil Painting": "貴族夫人的肖像畫",
    },
    "ja": {
        "Japanese Anime": "制服姿の大きな目の女の子",
        "Pixar Style": "街を探検するかわいいロボット",
        "Makoto Shinkai": "東京のスカイラインに沈む夕日の雲",
        "Cyberpunk": "フライングカーのあるネオン街",
        "Watercolor": "春の庭に咲く花々",
        "Oil Painting": "貴婦人の肖像画",
    },
    "ko": {
        "Japanese Anime": "교복을 입은 큰 눈의 소녀",
        "Pixar Style": "도시를 탐험하는 귀여운 로봇",
        "Makoto Shinkai": "도쿄 스카이라인 위의 석양 구름",
        "Cyberpunk": "비행 자동차가 있는 네온 거리",
        "Watercolor": "봄 정원에 피는 꽃들",
        "Oil Painting": "귀족 여인의 초상화",
    },
    "es": {
        "Japanese Anime": "Chica de ojos grandes en uniforme escolar",
        "Pixar Style": "Robot lindo explorando la ciudad",
        "Makoto Shinkai": "Nubes del atardecer sobre Tokio",
        "Cyberpunk": "Calles de neón con autos voladores",
        "Watercolor": "Flores floreciendo en jardín primaveral",
        "Oil Painting": "Retrato de una dama noble",
    },
}

ADVANCED_PROMPTS = {
    "en": [
        "A cute cat playing with yarn",
        "Sunset over the ocean waves",
        "Cyberpunk city at night",
        "Dragon flying over mountains",
    ],
    "zh-TW": [
        "可愛的貓咪在玩毛線球",
        "海浪上的日落美景",
        "夜晚的賽博龐克城市",
        "飛越群山的巨龍",
    ],
    "ja": [
        "毛糸で遊ぶかわいい猫",
        "海に沈む夕日",
        "夜のサイバーパンクシティ",
        "山を飛ぶドラゴン",
    ],
    "ko": [
        "실뭉치를 가지고 노는 귀여운 고양이",
        "바다 위의 일몰",
        "밤의 사이버펑크 도시",
        "산 위를 나는 용",
    ],
    "es": [
        "Un lindo gato jugando con hilo",
        "Atardecer sobre las olas del mar",
        "Ciudad cyberpunk de noche",
        "Dragón volando sobre montañas",
    ],
}

# Legacy compatibility
SAMPLE_STYLES = ADVANCED_STYLES
SAMPLE_PROMPTS = ADVANCED_PROMPTS

SAMPLE_CATEGORIES = [
    {"slug": "animals", "name": "Animals", "topic_count": 10},
    {"slug": "nature", "name": "Nature", "topic_count": 10},
    {"slug": "urban", "name": "Urban", "topic_count": 10},
    {"slug": "people", "name": "People", "topic_count": 10},
    {"slug": "fantasy", "name": "Fantasy", "topic_count": 10},
    {"slug": "sci-fi", "name": "Sci-Fi", "topic_count": 10},
]


def show_demo_header():
    """Show demo page header"""
    st.markdown(get_demo_css(), unsafe_allow_html=True)

    st.markdown("""
        <h1 class="demo-header">VidGo AI Demo</h1>
        <p class="demo-subtitle">
            Experience AI-powered video transformation with clothing effects and advanced styles
        </p>
    """, unsafe_allow_html=True)


def show_feature_cards(api_client=None):
    """Show main feature cards with selection"""
    # Initialize selected feature in session state
    if 'selected_feature' not in st.session_state:
        st.session_state.selected_feature = "clothing"  # Default to clothing

    lang = st.session_state.get('selected_language', 'en')

    # Translations for feature cards
    translations = {
        "en": {
            "clothing_title": "AI Clothing Transform",
            "clothing_desc": "Transform clothing styles in your videos with AI magic. Change outfits, styles, and looks instantly.",
            "advanced_title": "Advanced Effects",
            "advanced_desc": "Apply stunning artistic styles to your videos. Anime, Pixar, Cyberpunk, Watercolor and more!",
            "select_clothing": "Select Clothing Transform",
            "select_advanced": "Select Advanced Effects",
        },
        "zh-TW": {
            "clothing_title": "AI 換裝特效",
            "clothing_desc": "用 AI 魔法轉換你影片中的服裝風格。即時更換服裝、風格和造型。",
            "advanced_title": "進階特效",
            "advanced_desc": "為你的影片套用令人驚艷的藝術風格。動漫、皮克斯、賽博龐克、水彩等！",
            "select_clothing": "選擇換裝特效",
            "select_advanced": "選擇進階特效",
        },
        "ja": {
            "clothing_title": "AI 着せ替え",
            "clothing_desc": "AIマジックで動画の衣装スタイルを変換。衣装、スタイル、ルックを即座に変更。",
            "advanced_title": "アドバンスエフェクト",
            "advanced_desc": "動画に素晴らしいアートスタイルを適用。アニメ、ピクサー、サイバーパンク、水彩画など！",
            "select_clothing": "着せ替えを選択",
            "select_advanced": "エフェクトを選択",
        },
        "ko": {
            "clothing_title": "AI 의상 변환",
            "clothing_desc": "AI 마법으로 영상 속 의상 스타일을 변환하세요. 의상, 스타일, 룩을 즉시 변경.",
            "advanced_title": "고급 효과",
            "advanced_desc": "영상에 멋진 아트 스타일을 적용하세요. 애니메이션, 픽사, 사이버펑크, 수채화 등!",
            "select_clothing": "의상 변환 선택",
            "select_advanced": "고급 효과 선택",
        },
        "es": {
            "clothing_title": "Transformación de Ropa IA",
            "clothing_desc": "Transforma estilos de ropa en tus videos con magia IA. Cambia atuendos, estilos y looks al instante.",
            "advanced_title": "Efectos Avanzados",
            "advanced_desc": "Aplica impresionantes estilos artísticos a tus videos. ¡Anime, Pixar, Cyberpunk, Acuarela y más!",
            "select_clothing": "Seleccionar Ropa",
            "select_advanced": "Seleccionar Efectos",
        },
    }
    t = translations.get(lang, translations["en"])

    col1, col2 = st.columns(2)

    with col1:
        is_selected = st.session_state.selected_feature == "clothing"
        border_color = "#667eea" if is_selected else "#333"
        badge = "✓" if is_selected else ""

        st.markdown(f"""
            <div class="feature-card" style="border-color: {border_color}; {'box-shadow: 0 10px 40px rgba(102, 126, 234, 0.3);' if is_selected else ''}">
                <div class="feature-icon">👗</div>
                <div class="feature-title">{t['clothing_title']} {badge}</div>
                <div class="feature-desc">{t['clothing_desc']}</div>
            </div>
        """, unsafe_allow_html=True)
        if st.button(t['select_clothing'], key="btn_clothing", use_container_width=True,
                     type="primary" if is_selected else "secondary"):
            st.session_state.selected_feature = "clothing"
            st.session_state.selected_sample = ""
            st.rerun()

    with col2:
        is_selected = st.session_state.selected_feature == "advanced"
        border_color = "#f093fb" if is_selected else "#333"
        badge = "✓" if is_selected else ""

        st.markdown(f"""
            <div class="feature-card" style="border-color: {border_color}; {'box-shadow: 0 10px 40px rgba(240, 147, 251, 0.3);' if is_selected else ''}">
                <div class="feature-icon">✨</div>
                <div class="feature-title">{t['advanced_title']} {badge}</div>
                <div class="feature-desc">{t['advanced_desc']}</div>
            </div>
        """, unsafe_allow_html=True)
        if st.button(t['select_advanced'], key="btn_advanced", use_container_width=True,
                     type="primary" if is_selected else "secondary"):
            st.session_state.selected_feature = "advanced"
            st.session_state.selected_sample = ""
            st.rerun()


def show_style_gallery(api_client=None):
    """Show clickable style gallery based on selected feature with examples"""
    feature = st.session_state.get('selected_feature', 'clothing')
    lang = st.session_state.get('selected_language', 'en')

    # Translations
    titles = {
        "en": {"clothing": "👗 Click a Clothing Style:", "advanced": "✨ Click an Art Style:"},
        "zh-TW": {"clothing": "👗 點擊選擇服裝風格：", "advanced": "✨ 點擊選擇藝術風格："},
        "ja": {"clothing": "👗 衣装スタイルをクリック：", "advanced": "✨ アートスタイルをクリック："},
        "ko": {"clothing": "👗 의상 스타일 클릭：", "advanced": "✨ 아트 스타일 클릭："},
        "es": {"clothing": "👗 Clic en Estilo de Ropa:", "advanced": "✨ Clic en Estilo Artístico:"},
    }
    t = titles.get(lang, titles["en"])

    if feature == "clothing":
        st.markdown(f"### {t['clothing']}")
        styles = CLOTHING_STYLES
        style_icons = ["👔", "👗", "🎀", "👕", "🧥", "👟"]
        style_examples = CLOTHING_STYLE_EXAMPLES.get(lang, CLOTHING_STYLE_EXAMPLES["en"])
    else:
        st.markdown(f"### {t['advanced']}")
        styles = api_client.demo_get_styles() if api_client else ADVANCED_STYLES
        if not styles:
            styles = ADVANCED_STYLES
        style_icons = ["🎨", "🎬", "🌸", "🤖", "🎭", "🖼️"]
        style_examples = ADVANCED_STYLE_EXAMPLES.get(lang, ADVANCED_STYLE_EXAMPLES["en"])

    cols = st.columns(6)
    for i, style in enumerate(styles[:6]):
        with cols[i % 6]:
            icon = style_icons[i % len(style_icons)]
            style_name = style.get('name', 'Style')

            # Style button
            if st.button(f"{icon} {style_name}", key=f"style_{feature}_{i}", use_container_width=True):
                # Set the example prompt for this style
                example = style_examples.get(style_name, style_name)
                st.session_state.selected_sample = example
                st.rerun()

            # Show example below each style button
            example = style_examples.get(style_name, "")
            if example:
                st.caption(f"💡 {example}")


def show_language_selector():
    """Show clickable language selector"""
    lang = st.session_state.get('selected_language', 'en')

    titles = {
        "en": "🌐 Select Language",
        "zh-TW": "🌐 選擇語言",
        "ja": "🌐 言語を選択",
        "ko": "🌐 언어 선택",
        "es": "🌐 Seleccionar Idioma",
    }
    st.markdown(f"### {titles.get(lang, titles['en'])}")

    # Initialize selected language in session state
    if 'selected_language' not in st.session_state:
        st.session_state.selected_language = "en"

    languages = {
        "en": "English",
        "zh-TW": "繁體中文",
        "ja": "日本語",
        "ko": "한국어",
        "es": "Español",
    }

    cols = st.columns(5)
    for i, (code, name) in enumerate(languages.items()):
        with cols[i]:
            is_selected = st.session_state.selected_language == code
            if st.button(
                f"{'✓ ' if is_selected else ''}{name}",
                key=f"lang_{code}",
                use_container_width=True,
                type="primary" if is_selected else "secondary"
            ):
                st.session_state.selected_language = code
                st.session_state.selected_sample = ""  # Clear sample when language changes
                st.rerun()


def check_usage_limit() -> bool:
    """
    Check if unregistered user has exceeded usage limit (2 times).
    Returns True if user can still use, False if limit exceeded.
    """
    # Initialize usage count in session state
    if 'demo_usage_count' not in st.session_state:
        st.session_state.demo_usage_count = 0

    # Check if user is logged in (has user_id in session)
    is_logged_in = st.session_state.get('user_id') is not None

    # Logged in users have unlimited access
    if is_logged_in:
        return True

    # Unregistered users limited to 2 uses
    return st.session_state.demo_usage_count < 2


def increment_usage_count():
    """Increment the usage count for unregistered users"""
    if 'demo_usage_count' not in st.session_state:
        st.session_state.demo_usage_count = 0
    st.session_state.demo_usage_count += 1


def show_usage_limit_warning():
    """Show warning when usage limit is reached"""
    lang = st.session_state.get('selected_language', 'en')

    warnings = {
        "en": {
            "title": "Usage Limit Reached",
            "message": "You've used your 2 free demo tries. Register or login to continue using all features!",
            "register": "Register Now",
            "login": "Login",
        },
        "zh-TW": {
            "title": "使用次數已達上限",
            "message": "您已使用完 2 次免費試用。請註冊或登入以繼續使用所有功能！",
            "register": "立即註冊",
            "login": "登入",
        },
        "ja": {
            "title": "利用制限に達しました",
            "message": "2回の無料体験を使い切りました。すべての機能を使い続けるには、登録またはログインしてください！",
            "register": "今すぐ登録",
            "login": "ログイン",
        },
        "ko": {
            "title": "사용 한도 도달",
            "message": "2회 무료 체험을 모두 사용하셨습니다. 모든 기능을 계속 사용하려면 등록 또는 로그인하세요!",
            "register": "지금 등록",
            "login": "로그인",
        },
        "es": {
            "title": "Límite de Uso Alcanzado",
            "message": "Has usado tus 2 pruebas de demostración gratuitas. ¡Regístrate o inicia sesión para continuar usando todas las funciones!",
            "register": "Registrar Ahora",
            "login": "Iniciar Sesión",
        },
    }
    t = warnings.get(lang, warnings["en"])

    st.markdown(f"""
        <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                    border-radius: 15px; padding: 25px; text-align: center; margin: 20px 0;">
            <h3 style="color: white; margin: 0 0 15px 0;">{t['title']}</h3>
            <p style="color: white; margin: 0 0 20px 0;">{t['message']}</p>
        </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button(t['register'], key="register_btn", type="primary", use_container_width=True):
            st.session_state['landing_view'] = 'register'
            st.rerun()
    with col2:
        if st.button(t['login'], key="login_btn", use_container_width=True):
            st.session_state['landing_view'] = 'login'
            st.rerun()


def show_demo_input(api_client):
    """
    Show demo prompt input and generate image.
    This is the "Generate Demo" feature - generates image with watermark only.
    """
    # Check usage limit for unregistered users
    if not check_usage_limit():
        show_usage_limit_warning()
        return

    feature = st.session_state.get('selected_feature', 'clothing')
    lang = st.session_state.get('selected_language', 'en')

    # Available styles for image generation
    IMAGE_STYLES = [
        {"id": "anime", "name": "Anime", "slug": "anime"},
        {"id": "pixar", "name": "Pixar/3D", "slug": "pixar"},
        {"id": "realistic", "name": "Realistic", "slug": "realistic"},
        {"id": "watercolor", "name": "Watercolor", "slug": "watercolor"},
        {"id": "oil_painting", "name": "Oil Painting", "slug": "oil_painting"},
        {"id": "cyberpunk", "name": "Cyberpunk", "slug": "cyberpunk"},
        {"id": "cinematic", "name": "Cinematic", "slug": "cinematic"},
        {"id": "clay", "name": "Clay/Claymation", "slug": "clay"},
    ]

    # Translations
    translations = {
        "en": {
            "try_clothing": "👗 Try Clothing Transform",
            "try_advanced": "✨ Try Advanced Effects",
            "clothing_desc": "Describe the clothing style you want to transform to",
            "advanced_desc": "Describe the scene you want to create",
            "generate": "Generate Demo",
            "clear": "Clear",
            "generating": "Generating image... (~30-60 seconds)",
            "image_ready": "Image Generated!",
            "error": "Generation Failed",
            "style_label": "Select Style:",
        },
        "zh-TW": {
            "try_clothing": "👗 試試換裝特效",
            "try_advanced": "✨ 試試進階特效",
            "clothing_desc": "描述你想要轉換的服裝風格",
            "advanced_desc": "描述你想要創建的場景",
            "generate": "生成展示",
            "clear": "清除",
            "generating": "生成圖片中... (~30-60 秒)",
            "image_ready": "圖片生成完成！",
            "error": "生成失敗",
            "style_label": "選擇風格：",
        },
        "ja": {
            "try_clothing": "👗 着せ替えを試す",
            "try_advanced": "✨ エフェクトを試す",
            "clothing_desc": "変換したい衣装スタイルを説明してください",
            "advanced_desc": "作成したいシーンを説明してください",
            "generate": "デモ生成",
            "clear": "クリア",
            "generating": "画像を生成中... (~30-60秒)",
            "image_ready": "画像生成完了！",
            "error": "生成失敗",
            "style_label": "スタイルを選択：",
        },
        "ko": {
            "try_clothing": "👗 의상 변환 체험",
            "try_advanced": "✨ 고급 효과 체험",
            "clothing_desc": "변환하고 싶은 의상 스타일을 설명하세요",
            "advanced_desc": "만들고 싶은 장면을 설명하세요",
            "generate": "데모 생성",
            "clear": "지우기",
            "generating": "이미지 생성 중... (~30-60초)",
            "image_ready": "이미지 생성 완료!",
            "error": "생성 실패",
            "style_label": "스타일 선택：",
        },
        "es": {
            "try_clothing": "👗 Prueba Transformación de Ropa",
            "try_advanced": "✨ Prueba Efectos Avanzados",
            "clothing_desc": "Describe el estilo de ropa que quieres transformar",
            "advanced_desc": "Describe la escena que quieres crear",
            "generate": "Generar Demo",
            "clear": "Limpiar",
            "generating": "Generando imagen... (~30-60 segundos)",
            "image_ready": "Imagen Generada!",
            "error": "Generación Fallida",
            "style_label": "Seleccionar Estilo:",
        },
    }
    t = translations.get(lang, translations["en"])

    # Show feature-specific title
    if feature == "clothing":
        st.markdown(f"### {t['try_clothing']}")
        feature_desc = t['clothing_desc']
        prompts_dict = CLOTHING_PROMPTS
        styles = CLOTHING_STYLES
    else:
        st.markdown(f"### {t['try_advanced']}")
        feature_desc = t['advanced_desc']
        prompts_dict = ADVANCED_PROMPTS
        styles = api_client.demo_get_styles() if api_client else ADVANCED_STYLES
        if not styles:
            styles = ADVANCED_STYLES

    sample_prompts = prompts_dict.get(lang, prompts_dict["en"])

    # Initialize session state
    if 'prompt_input' not in st.session_state:
        st.session_state.prompt_input = ""
    if 'selected_sample' not in st.session_state:
        st.session_state.selected_sample = ""
    if 'generated_image_url' not in st.session_state:
        st.session_state.generated_image_url = None
    if 'generated_original_url' not in st.session_state:
        st.session_state.generated_original_url = None  # Original image for video generation
    if 'generated_prompt' not in st.session_state:
        st.session_state.generated_prompt = ""
    if 'generated_style' not in st.session_state:
        st.session_state.generated_style = None

    # Check if sample was just selected (needs to update prompt)
    if st.session_state.selected_sample and st.session_state.selected_sample != st.session_state.prompt_input:
        st.session_state.prompt_input = st.session_state.selected_sample
        st.session_state.selected_sample = ""  # Clear after applying

    # Prompt input and style selection
    col_prompt, col_style = st.columns([3, 1])

    with col_prompt:
        prompt = st.text_area(
            feature_desc,
            key="prompt_input",
            placeholder=f"Example: {sample_prompts[0]}",
            height=100
        )

    with col_style:
        st.markdown(f"**{t['style_label']}**")
        selected_style_idx = st.selectbox(
            t['style_label'],
            range(len(IMAGE_STYLES)),
            format_func=lambda x: IMAGE_STYLES[x]["name"],
            key="selected_style",
            label_visibility="collapsed"
        )
        selected_style = IMAGE_STYLES[selected_style_idx]
        style_slug = selected_style["slug"]

        # Show style preview
        st.caption(f"Style: {selected_style['name']}")

    # Clear callback function
    def clear_demo_state():
        st.session_state.selected_sample = ""
        st.session_state.generated_image_url = None
        st.session_state.generated_original_url = None
        st.session_state.generated_prompt = ""
        st.session_state.generated_style = None
        st.session_state.video_result = None
        # Use del instead of assignment for widget-bound keys
        if 'prompt_input' in st.session_state:
            del st.session_state['prompt_input']
        if 'selected_style' in st.session_state:
            del st.session_state['selected_style']

    # Generate and Clear buttons
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            generate_clicked = st.button(
                t['generate'],
                type="primary",
                use_container_width=True
            )
        with btn_col2:
            if st.button(t['clear'], use_container_width=True, on_click=clear_demo_state):
                st.rerun()

    if generate_clicked and prompt:
        # First check moderation
        if api_client:
            mod_result = api_client.demo_moderate_prompt(prompt)
            if mod_result and not mod_result.get("is_safe", True):
                st.markdown(f"""
                    <div class="result-card result-error">
                        <h4>Content Not Allowed</h4>
                        <p>{mod_result.get('reason', 'Content blocked by moderation')}</p>
                    </div>
                """, unsafe_allow_html=True)
                return

        # Generate image only
        with st.spinner(t['generating']):
            if api_client:
                result = api_client.demo_generate_image(prompt, style=style_slug)

                if result and result.get("success"):
                    st.session_state.generated_image_url = result.get("image_url")
                    st.session_state.generated_original_url = result.get("original_url")  # For video generation
                    st.session_state.generated_prompt = prompt
                    st.session_state.generated_style = style_slug
                    # Increment usage count for unregistered users
                    increment_usage_count()
                    st.success(t['image_ready'])
                    st.rerun()
                else:
                    st.error(f"{t['error']}: {result.get('error', 'Unknown error') if result else 'API connection failed'}")
            else:
                st.warning("Backend API not connected.")

    # Show generated image if available
    if st.session_state.generated_image_url:
        st.markdown("---")
        st.markdown(f"### {t['image_ready']}")

        col1, col2 = st.columns([2, 1])
        with col1:
            st.image(st.session_state.generated_image_url, use_container_width=True)
        with col2:
            st.markdown(f"""
                <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                           border: 2px solid #667eea; border-radius: 15px; padding: 20px;">
                    <p><strong>Prompt:</strong></p>
                    <p style="color: #9CA3AF; font-size: 0.9rem;">{st.session_state.generated_prompt}</p>
                    <p style="color: #667eea; margin-top: 15px;">
                        <strong>Next:</strong> Click "See It In Action" below to create a video from this image!
                    </p>
                </div>
            """, unsafe_allow_html=True)


def show_demo_result(demo: Dict[str, Any], match_score: float):
    """Show demo generation result"""
    st.markdown("### Result")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<p class="before-after-label">Before</p>', unsafe_allow_html=True)
        if demo.get("image_before"):
            st.image(demo["image_before"], use_container_width=True)
        else:
            st.info("Source image will appear here")

    with col2:
        st.markdown('<p class="before-after-label">After</p>', unsafe_allow_html=True)
        if demo.get("image_after"):
            st.image(demo["image_after"], use_container_width=True)
        else:
            st.info("Transformed result will appear here")

    # Details
    st.markdown(f"""
        <div class="result-card result-success">
            <h4>Transformation Complete</h4>
            <p><strong>Style Applied:</strong> {demo.get('style_name', 'Auto')}</p>
            <p><strong>Match Score:</strong> {match_score:.0%}</p>
            <p><strong>Category:</strong> {demo.get('category', 'general')}</p>
        </div>
    """, unsafe_allow_html=True)


def show_sample_result(prompt: str, style: str):
    """Show sample result when API is unavailable"""
    st.markdown("### Demo Result (Sample)")

    st.info("Backend API is not connected. Showing sample result.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<p class="before-after-label">Before</p>', unsafe_allow_html=True)
        st.markdown("""
            <div style="background: #2d2d44; padding: 100px 20px; text-align: center; border-radius: 10px;">
                <span style="font-size: 4rem;">🖼️</span>
                <p style="color: #9CA3AF;">Source Image</p>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown('<p class="before-after-label">After</p>', unsafe_allow_html=True)
        st.markdown("""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 100px 20px; text-align: center; border-radius: 10px;">
                <span style="font-size: 4rem;">✨</span>
                <p style="color: white;">Transformed Result</p>
            </div>
        """, unsafe_allow_html=True)

    st.markdown(f"""
        <div class="result-card result-success">
            <h4>Sample Transformation</h4>
            <p><strong>Your Prompt:</strong> {prompt}</p>
            <p><strong>Style:</strong> {style}</p>
            <p><em>Connect to backend to see real results!</em></p>
        </div>
    """, unsafe_allow_html=True)


def show_demo_generation_preview(api_client):
    """
    Show "See It In Action" - generate video from pre-generated image.
    Uses the image from "Generate Demo" (Step 1) to create video.
    """
    lang = st.session_state.get('selected_language', 'en')

    # Translations
    translations = {
        "en": {
            "title": "🎬 See It In Action",
            "description": "Transform your generated image into a video (~1-3 minutes)",
            "no_image": "First generate an image using 'Generate Demo' above",
            "generate_btn": "▶️ Create Video",
            "generating": "Creating video from your image... (~1-3 minutes)",
            "complete": "✅ Video Created!",
            "error": "❌ Video Generation Failed",
            "image": "Source Image",
            "video": "Generated Video",
            "try_again": "🔄 Try Another",
        },
        "zh-TW": {
            "title": "🎬 實際效果展示",
            "description": "將你生成的圖片轉換為影片 (~1-3 分鐘)",
            "no_image": "請先使用上方的「生成展示」生成圖片",
            "generate_btn": "▶️ 創建影片",
            "generating": "正在從你的圖片創建影片... (~1-3 分鐘)",
            "complete": "✅ 影片創建完成！",
            "error": "❌ 影片生成失敗",
            "image": "來源圖片",
            "video": "生成的影片",
            "try_again": "🔄 再試一次",
        },
        "ja": {
            "title": "🎬 実際の効果を見る",
            "description": "生成した画像を動画に変換します (~1-3分)",
            "no_image": "まず上の「デモ生成」で画像を生成してください",
            "generate_btn": "▶️ 動画作成",
            "generating": "画像から動画を作成中... (~1-3分)",
            "complete": "✅ 動画作成完了！",
            "error": "❌ 動画生成失敗",
            "image": "ソース画像",
            "video": "生成された動画",
            "try_again": "🔄 もう一度試す",
        },
        "ko": {
            "title": "🎬 실제 효과 보기",
            "description": "생성된 이미지를 동영상으로 변환합니다 (~1-3분)",
            "no_image": "먼저 위의 '데모 생성'으로 이미지를 생성하세요",
            "generate_btn": "▶️ 동영상 만들기",
            "generating": "이미지에서 동영상 생성 중... (~1-3분)",
            "complete": "✅ 동영상 생성 완료!",
            "error": "❌ 동영상 생성 실패",
            "image": "원본 이미지",
            "video": "생성된 동영상",
            "try_again": "🔄 다시 시도",
        },
        "es": {
            "title": "🎬 Véalo en Acción",
            "description": "Transforma tu imagen generada en video (~1-3 minutos)",
            "no_image": "Primero genera una imagen usando 'Generar Demo' arriba",
            "generate_btn": "▶️ Crear Video",
            "generating": "Creando video desde tu imagen... (~1-3 minutos)",
            "complete": "✅ ¡Video Creado!",
            "error": "❌ Generación de Video Fallida",
            "image": "Imagen de Origen",
            "video": "Video Generado",
            "try_again": "🔄 Intentar Otro",
        },
    }
    t = translations.get(lang, translations["en"])

    st.markdown(f"### {t['title']}")
    st.markdown(f"<p style='color: #9CA3AF;'>{t['description']}</p>", unsafe_allow_html=True)

    # Initialize session state
    if 'video_result' not in st.session_state:
        st.session_state.video_result = None

    # Check if we have a generated image from Step 1
    if not st.session_state.get('generated_image_url'):
        st.info(f"ℹ️ {t['no_image']}")
        return

    # Show the source image
    st.markdown(f"**{t['image']}**")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.image(st.session_state.generated_image_url, use_container_width=True)
    with col2:
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                       border: 2px solid #333; border-radius: 15px; padding: 20px;">
                <p><strong>Prompt:</strong></p>
                <p style="color: #9CA3AF;">{st.session_state.generated_prompt}</p>
            </div>
        """, unsafe_allow_html=True)

        # Generate video button
        if st.button(t['generate_btn'], type="primary", use_container_width=True):
            with st.spinner(t['generating']):
                if api_client:
                    # Use original_url (without watermark) for video generation
                    image_for_video = st.session_state.get('generated_original_url') or st.session_state.generated_image_url
                    result = api_client.demo_generate_video(
                        prompt=st.session_state.generated_prompt,
                        image_url=image_for_video,
                        style=st.session_state.generated_style
                    )

                    if result:
                        st.session_state.video_result = result
                        st.rerun()
                    else:
                        st.error("API connection failed.")
                else:
                    st.warning("Backend API not connected.")

    # Show video result if available
    if st.session_state.video_result:
        result = st.session_state.video_result

        if result.get("success"):
            st.success(t['complete'])

            # Show video in a smaller container with autoplay and loop
            st.markdown(f"**{t['video']}**")
            if result.get("video_url"):
                import streamlit.components.v1 as components

                # Custom HTML video player with autoplay, loop, and smooth playback
                video_url = result["video_url"]
                video_html = f"""
                <div style="display: flex; justify-content: center; padding: 10px;">
                    <div style="max-width: 400px; width: 100%;">
                        <video
                            autoplay
                            loop
                            muted
                            playsinline
                            style="width: 100%; border-radius: 12px; box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);"
                        >
                            <source src="{video_url}" type="video/mp4">
                        </video>
                        <p style="text-align: center; color: #9CA3AF; font-size: 0.85rem; margin-top: 10px;">
                            Demo video - upgrade to download full quality videos
                        </p>
                    </div>
                </div>
                """
                components.html(video_html, height=320)
            else:
                st.info("Video URL not available")

            # Show steps (collapsed by default)
            steps = result.get("steps", [])
            if steps:
                with st.expander("Pipeline Details", expanded=False):
                    for step in steps:
                        status_icon = "✅" if step.get("status") == "completed" else "⏭️" if step.get("status") == "skipped" else "❌"
                        st.markdown(f"- {status_icon} {step.get('name', 'Step')}: {step.get('status', 'unknown')}")

        else:
            st.error(f"{t['error']}: {result.get('error', 'Unknown error')}")

        # Reset callback function
        def reset_video_demo():
            st.session_state.video_result = None
            st.session_state.generated_image_url = None
            st.session_state.generated_original_url = None
            st.session_state.generated_prompt = ""
            st.session_state.generated_style = None
            if 'prompt_input' in st.session_state:
                del st.session_state['prompt_input']
            if 'selected_style' in st.session_state:
                del st.session_state['selected_style']

        # Reset button
        if st.button(t['try_again'], key="reset_video", on_click=reset_video_demo):
            st.rerun()


def show_categories(api_client):
    """Show demo categories with clickable icons"""
    lang = st.session_state.get('selected_language', 'en')

    # Translations
    translations = {
        "en": {
            "title": "Explore Categories",
            "click_to_view": "Click to view videos",
            "videos_in": "Videos in",
            "no_videos": "No videos available yet. Coming soon!",
            "loading": "Loading videos...",
            "back": "← Back to Categories",
        },
        "zh-TW": {
            "title": "探索類別",
            "click_to_view": "點擊查看影片",
            "videos_in": "影片類別：",
            "no_videos": "目前沒有影片，即將推出！",
            "loading": "載入影片中...",
            "back": "← 返回類別",
        },
        "ja": {
            "title": "カテゴリを探索",
            "click_to_view": "クリックして動画を見る",
            "videos_in": "動画カテゴリ：",
            "no_videos": "まだ動画がありません。近日公開！",
            "loading": "動画を読み込み中...",
            "back": "← カテゴリに戻る",
        },
        "ko": {
            "title": "카테고리 탐색",
            "click_to_view": "클릭하여 동영상 보기",
            "videos_in": "동영상 카테고리:",
            "no_videos": "아직 동영상이 없습니다. 곧 출시됩니다!",
            "loading": "동영상 로딩 중...",
            "back": "← 카테고리로 돌아가기",
        },
        "es": {
            "title": "Explorar Categorías",
            "click_to_view": "Clic para ver videos",
            "videos_in": "Videos en",
            "no_videos": "No hay videos disponibles. ¡Próximamente!",
            "loading": "Cargando videos...",
            "back": "← Volver a Categorías",
        },
    }
    t = translations.get(lang, translations["en"])

    # Initialize selected category in session state
    if 'selected_category' not in st.session_state:
        st.session_state.selected_category = None

    st.markdown(f"### {t['title']}")

    categories = api_client.demo_get_categories() if api_client else SAMPLE_CATEGORIES
    if not categories:
        categories = SAMPLE_CATEGORIES

    category_icons = {
        "animals": "🐱",
        "nature": "🌿",
        "urban": "🏙️",
        "people": "👤",
        "fantasy": "🐉",
        "sci-fi": "🚀",
        "food": "🍜",
    }

    # Show category buttons
    cols = st.columns(len(categories))
    for i, cat in enumerate(categories):
        with cols[i]:
            slug = cat.get("slug", "")
            icon = category_icons.get(slug, "📁")
            name = cat.get('name', 'Category')
            is_selected = st.session_state.selected_category == slug

            if st.button(
                f"{icon} {name}",
                key=f"cat_{slug}",
                use_container_width=True,
                type="primary" if is_selected else "secondary"
            ):
                if st.session_state.selected_category == slug:
                    # Clicking again deselects
                    st.session_state.selected_category = None
                else:
                    st.session_state.selected_category = slug
                st.rerun()

    # Show videos for selected category
    if st.session_state.selected_category:
        show_category_videos(api_client, st.session_state.selected_category, t)


def show_category_videos(api_client, category_slug: str, translations: dict):
    """
    Show auto-play videos for a selected category.
    Fetches 3 random videos and plays them with 1 second delay between each.
    """
    st.markdown("---")

    # Back button
    if st.button(translations['back'], key="back_to_categories"):
        st.session_state.selected_category = None
        st.session_state.category_videos = None
        st.rerun()

    # Fetch 3 random videos from API
    if api_client:
        with st.spinner(translations['loading']):
            result = api_client.demo_get_random_category_videos(category_slug, count=3)
    else:
        result = None

    if result and result.get('videos'):
        import streamlit.components.v1 as components
        import random

        videos = result['videos']
        category_name = result.get('category_name', category_slug.title())

        st.markdown(f"### 🎬 {translations['videos_in']} {category_name}")
        st.markdown(f"*Showing {len(videos)} random videos with auto-play*")

        # Get video URLs
        video_urls = [v.get('video_url') for v in videos if v.get('video_url')]

        if video_urls:
            # Generate unique IDs for this session
            video_id_base = f"vid_{random.randint(1000, 9999)}"

            # Build HTML with embedded JavaScript for staggered autoplay
            video_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{
                        margin: 0;
                        padding: 5px;
                        background: transparent;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    }}
                    .video-container {{
                        display: flex;
                        gap: 10px;
                        justify-content: center;
                        align-items: flex-start;
                    }}
                    .video-item {{
                        flex: 1;
                        max-width: 220px;
                        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                        border-radius: 10px;
                        padding: 8px;
                        border: 2px solid #667eea;
                    }}
                    .video-item video {{
                        width: 100%;
                        height: 130px;
                        object-fit: cover;
                        border-radius: 8px;
                        opacity: 0;
                        transition: opacity 0.5s ease-in;
                    }}
                    .video-item video.playing {{
                        opacity: 1;
                    }}
                    .video-info {{
                        padding: 5px 0 0 0;
                        text-align: center;
                    }}
                    .video-prompt {{
                        color: #9CA3AF;
                        font-size: 0.7rem;
                        margin: 0;
                        overflow: hidden;
                        text-overflow: ellipsis;
                        white-space: nowrap;
                    }}
                    .video-label {{
                        text-align: center;
                        color: #667eea;
                        font-size: 0.65rem;
                        font-weight: 600;
                        margin-top: 3px;
                    }}
                </style>
            </head>
            <body>
                <div class="video-container">
            """

            for i, video in enumerate(videos[:3]):
                url = video.get('video_url', '')
                prompt = video.get('prompt', '')[:30] + '...' if len(video.get('prompt', '')) > 30 else video.get('prompt', '')
                video_html += f"""
                    <div class="video-item">
                        <video id="{video_id_base}_{i}" muted loop playsinline>
                            <source src="{url}" type="video/mp4">
                        </video>
                        <div class="video-info">
                            <p class="video-prompt">{prompt}</p>
                            <div class="video-label">Video {i+1}</div>
                        </div>
                    </div>
                """

            video_html += f"""
                </div>

                <script>
                    // Staggered autoplay with 1 second delay between each video
                    const delays = [0, 1000, 2000];
                    const videoCount = {len(video_urls[:3])};

                    for (let i = 0; i < videoCount; i++) {{
                        setTimeout(function() {{
                            const video = document.getElementById("{video_id_base}_" + i);
                            if (video) {{
                                video.classList.add('playing');
                                video.play().catch(function(e) {{
                                    console.log('Autoplay prevented for video ' + i);
                                    video.classList.add('playing');
                                }});
                            }}
                        }}, delays[i]);
                    }}
                </script>
            </body>
            </html>
            """

            # Use components.html to render with JavaScript execution - compact height
            components.html(video_html, height=220, scrolling=False)

        else:
            st.warning("No video URLs available")

    else:
        # No videos found - show "More Effect Video" section with 3 different styles
        show_more_effect_videos(api_client, category_slug, translations)


def show_more_effect_videos(api_client, category_slug: str, translations: dict):
    """
    Show 'More Effect Video' section with 3 different effect styles for the same topic.
    Each video shows the same topic rendered in a different style (Anime, Pixar, Realistic).
    """
    lang = st.session_state.get('selected_language', 'en')

    # Effect styles to showcase
    effect_styles = [
        {"name": "Anime Style", "slug": "anime", "icon": "🎨", "color": "#f093fb"},
        {"name": "Pixar/3D Style", "slug": "pixar", "icon": "🎬", "color": "#667eea"},
        {"name": "Realistic Style", "slug": "realistic", "icon": "📷", "color": "#10B981"},
    ]

    # Translations for this section
    section_titles = {
        "en": "More Effect Videos",
        "zh-TW": "更多特效影片",
        "ja": "もっとエフェクト動画",
        "ko": "더 많은 효과 동영상",
        "es": "Más Videos de Efectos",
    }

    descriptions = {
        "en": "Same topic, 3 different artistic styles",
        "zh-TW": "同一主題，3 種不同藝術風格",
        "ja": "同じトピック、3つの異なるアートスタイル",
        "ko": "같은 주제, 3가지 다른 예술 스타일",
        "es": "Mismo tema, 3 estilos artísticos diferentes",
    }

    st.markdown(f"### ✨ {section_titles.get(lang, section_titles['en'])}")
    st.caption(descriptions.get(lang, descriptions['en']))

    # Sample topic for the category
    sample_topics = {
        "animals": "A cute cat playing",
        "nature": "Beautiful sunset over ocean",
        "urban": "Neon city streets at night",
        "people": "Dancer performing elegantly",
        "fantasy": "Magical dragon in the sky",
        "sci-fi": "Futuristic spaceship landing",
        "food": "Delicious gourmet meal",
    }
    topic = sample_topics.get(category_slug, "A beautiful scene")

    # Display 3 effect style cards
    cols = st.columns(3)
    for i, style in enumerate(effect_styles):
        with cols[i]:
            st.markdown(f"""
                <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                            border-radius: 15px; padding: 20px; text-align: center;
                            border: 2px solid {style['color']}; margin-bottom: 10px;
                            min-height: 200px;">
                    <span style="font-size: 3rem;">{style['icon']}</span>
                    <h4 style="color: {style['color']}; margin: 15px 0 10px 0;">{style['name']}</h4>
                    <p style="color: #9CA3AF; font-size: 0.85rem; margin: 0;">
                        {topic}
                    </p>
                    <p style="color: #666; font-size: 0.75rem; margin-top: 10px;">
                        ⏱️ 5 seconds | 🎥 720p
                    </p>
                </div>
            """, unsafe_allow_html=True)

            # Placeholder video or actual video if available
            st.markdown(f"""
                <div style="background: linear-gradient(135deg, {style['color']}20 0%, {style['color']}10 100%);
                            padding: 40px 20px; text-align: center; border-radius: 10px;
                            border: 2px dashed {style['color']}40;">
                    <span style="font-size: 2rem;">🎬</span>
                    <p style="color: {style['color']}; margin-top: 10px; font-weight: 600;">
                        {style['name']}
                    </p>
                    <p style="color: #9CA3AF; font-size: 0.8rem;">
                        Effect preview
                    </p>
                </div>
            """, unsafe_allow_html=True)

    # Show message about generating videos
    st.info("💡 Click 'Generate Demo' above to create your own videos with these effect styles!")


def show_upgrade_cta():
    """Show upgrade call-to-action with working View Plans button"""
    st.markdown("---")
    st.markdown("""
        <div class="upgrade-banner">
            <div class="upgrade-text">
                Want unlimited access? Upgrade to Pro for full features!
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Use Streamlit button for navigation
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("View Plans", key="view_plans_btn", type="primary", use_container_width=True):
            # For non-authenticated users (landing page)
            st.session_state['landing_view'] = 'plans'
            # For authenticated users (sidebar navigation)
            st.session_state['selected_page'] = 'Plans'
            st.rerun()


def show_demo_stats(api_client):
    """Show demo page statistics"""
    st.markdown("### Platform Stats")

    # Try to get block cache stats
    stats = None
    if api_client:
        stats = api_client.demo_get_block_cache_stats()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("""
            <div class="stats-card">
                <div class="stats-number">12+</div>
                <div class="stats-label">Styles Available</div>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
            <div class="stats-card">
                <div class="stats-number">5</div>
                <div class="stats-label">Languages Supported</div>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        blocked_count = stats.get("total_blocked_words", 200) if stats else 200
        st.markdown(f"""
            <div class="stats-card">
                <div class="stats-number">{blocked_count}+</div>
                <div class="stats-label">Content Filters</div>
            </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown("""
            <div class="stats-card">
                <div class="stats-number">7</div>
                <div class="stats-label">Categories</div>
            </div>
        """, unsafe_allow_html=True)


def show_demo_page(api_client=None):
    """Main demo page entry point"""
    show_demo_header()
    show_feature_cards(api_client)

    st.markdown("---")
    show_style_gallery(api_client)

    st.markdown("---")
    show_demo_input(api_client)

    st.markdown("---")
    show_demo_generation_preview(api_client)

    st.markdown("---")
    show_categories(api_client)

    st.markdown("---")
    show_demo_stats(api_client)

    show_upgrade_cta()


# For standalone testing
if __name__ == "__main__":
    st.set_page_config(
        page_title="VidGo Demo",
        page_icon="🎬",
        layout="wide"
    )
    show_demo_page()
