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


def show_demo_input(api_client):
    """Show demo prompt input and result based on selected feature"""
    feature = st.session_state.get('selected_feature', 'clothing')
    lang = st.session_state.get('selected_language', 'en')

    # Translations
    translations = {
        "en": {
            "try_clothing": "👗 Try Clothing Transform",
            "try_advanced": "✨ Try Advanced Effects",
            "clothing_desc": "Describe the clothing style you want to transform to",
            "advanced_desc": "Describe the scene you want to transform",
            "generate": "Generate Demo",
            "clear": "Clear",
        },
        "zh-TW": {
            "try_clothing": "👗 試試換裝特效",
            "try_advanced": "✨ 試試進階特效",
            "clothing_desc": "描述你想要轉換的服裝風格",
            "advanced_desc": "描述你想要轉換的場景",
            "generate": "生成展示",
            "clear": "清除",
        },
        "ja": {
            "try_clothing": "👗 着せ替えを試す",
            "try_advanced": "✨ エフェクトを試す",
            "clothing_desc": "変換したい衣装スタイルを説明してください",
            "advanced_desc": "変換したいシーンを説明してください",
            "generate": "デモ生成",
            "clear": "クリア",
        },
        "ko": {
            "try_clothing": "👗 의상 변환 체험",
            "try_advanced": "✨ 고급 효과 체험",
            "clothing_desc": "변환하고 싶은 의상 스타일을 설명하세요",
            "advanced_desc": "변환하고 싶은 장면을 설명하세요",
            "generate": "데모 생성",
            "clear": "지우기",
        },
        "es": {
            "try_clothing": "👗 Prueba Transformación de Ropa",
            "try_advanced": "✨ Prueba Efectos Avanzados",
            "clothing_desc": "Describe el estilo de ropa que quieres transformar",
            "advanced_desc": "Describe la escena que quieres transformar",
            "generate": "Generar Demo",
            "clear": "Limpiar",
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

    # Initialize selected sample in session state
    if 'selected_sample' not in st.session_state:
        st.session_state.selected_sample = ""

    # Prompt input - full width
    default_value = st.session_state.selected_sample if st.session_state.selected_sample else ""
    prompt = st.text_area(
        feature_desc,
        value=default_value,
        placeholder=f"Example: {sample_prompts[0]}",
        height=100
    )

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
            if st.button(t['clear'], use_container_width=True):
                st.session_state.selected_sample = ""
                st.rerun()

    if generate_clicked and prompt:
        with st.spinner("Processing your prompt..."):
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

            # Analyze prompt
            if api_client:
                analysis = api_client.demo_analyze_prompt(prompt)
                if analysis:
                    st.markdown(f"""
                        <div class="result-card result-success">
                            <h4>Prompt Analysis</h4>
                            <p><strong>Detected Language:</strong> {analysis.get('language', 'en')}</p>
                            <p><strong>Normalized:</strong> {analysis.get('normalized', prompt)}</p>
                            <p><strong>Keywords:</strong> {', '.join(analysis.get('keywords', []))}</p>
                            <p><strong>Category:</strong> {analysis.get('category', 'general')}</p>
                            <p><strong>Confidence:</strong> {analysis.get('confidence', 0.8):.0%}</p>
                        </div>
                    """, unsafe_allow_html=True)

            # Extract style from prompt (style buttons add "{style_name} style" to prompt)
            style_slug = None
            detected_style = "Auto"
            for s in styles:
                style_name = s.get("name", "")
                if style_name.lower() in prompt.lower():
                    style_slug = s.get("slug")
                    detected_style = style_name
                    break

            if api_client:
                result = api_client.demo_search(prompt, style=style_slug)
                if result:
                    if result.get("error"):
                        st.error(result.get("detail", "Error processing request"))
                    elif result.get("success"):
                        demo = result.get("demo", {})
                        show_demo_result(demo, result.get("match_score", 0))
            else:
                # Show sample result when API unavailable
                show_sample_result(prompt, detected_style)


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
    Show demo generation preview with simulated generation process.
    Uses pre-generated content from database to simulate the generation flow.
    Ready for GoEnhance API integration when available.
    """
    feature = st.session_state.get('selected_feature', 'clothing')
    lang = st.session_state.get('selected_language', 'en')

    # Translations
    translations = {
        "en": {
            "title": "🎬 See It In Action",
            "description": "Watch how our AI transforms your ideas into stunning visuals",
            "generate_btn": "▶️ Generate Demo",
            "generating": "Generating...",
            "step1": "📝 Processing prompt...",
            "step2": "🎨 Generating image with AI...",
            "step3": "🎬 Creating video (5 sec)...",
            "complete": "✅ Generation Complete!",
            "prompt_label": "Prompt Used:",
            "style_label": "Style Applied:",
            "before": "Before",
            "after": "After",
            "video": "Generated Video",
            "api_note": "Demo mode - Using pre-generated samples",
        },
        "zh-TW": {
            "title": "🎬 實際效果展示",
            "description": "觀看我們的 AI 如何將你的想法轉化為令人驚艷的視覺效果",
            "generate_btn": "▶️ 生成展示",
            "generating": "生成中...",
            "step1": "📝 處理提示詞...",
            "step2": "🎨 AI 生成圖片中...",
            "step3": "🎬 創建影片 (5 秒)...",
            "complete": "✅ 生成完成！",
            "prompt_label": "使用的提示詞：",
            "style_label": "套用的風格：",
            "before": "之前",
            "after": "之後",
            "video": "生成的影片",
            "api_note": "展示模式 - 使用預先生成的樣本",
        },
        "ja": {
            "title": "🎬 実際の効果を見る",
            "description": "AIがあなたのアイデアを素晴らしいビジュアルに変換する様子をご覧ください",
            "generate_btn": "▶️ デモを生成",
            "generating": "生成中...",
            "step1": "📝 プロンプトを処理中...",
            "step2": "🎨 AIで画像を生成中...",
            "step3": "🎬 動画を作成中 (5秒)...",
            "complete": "✅ 生成完了！",
            "prompt_label": "使用したプロンプト：",
            "style_label": "適用したスタイル：",
            "before": "ビフォー",
            "after": "アフター",
            "video": "生成された動画",
            "api_note": "デモモード - 事前生成サンプルを使用",
        },
        "ko": {
            "title": "🎬 실제 효과 보기",
            "description": "AI가 당신의 아이디어를 놀라운 비주얼로 변환하는 과정을 확인하세요",
            "generate_btn": "▶️ 데모 생성",
            "generating": "생성 중...",
            "step1": "📝 프롬프트 처리 중...",
            "step2": "🎨 AI로 이미지 생성 중...",
            "step3": "🎬 동영상 생성 중 (5초)...",
            "complete": "✅ 생성 완료!",
            "prompt_label": "사용된 프롬프트:",
            "style_label": "적용된 스타일:",
            "before": "이전",
            "after": "이후",
            "video": "생성된 동영상",
            "api_note": "데모 모드 - 사전 생성된 샘플 사용",
        },
        "es": {
            "title": "🎬 Véalo en Acción",
            "description": "Observe cómo nuestra IA transforma sus ideas en visuales impresionantes",
            "generate_btn": "▶️ Generar Demo",
            "generating": "Generando...",
            "step1": "📝 Procesando prompt...",
            "step2": "🎨 Generando imagen con IA...",
            "step3": "🎬 Creando video (5 seg)...",
            "complete": "✅ ¡Generación Completa!",
            "prompt_label": "Prompt Usado:",
            "style_label": "Estilo Aplicado:",
            "before": "Antes",
            "after": "Después",
            "video": "Video Generado",
            "api_note": "Modo demo - Usando muestras pre-generadas",
        },
    }
    t = translations.get(lang, translations["en"])

    st.markdown(f"### {t['title']}")
    st.markdown(f"<p style='color: #9CA3AF;'>{t['description']}</p>", unsafe_allow_html=True)

    # Get sample prompt and style based on selected feature
    if feature == "clothing":
        prompts = CLOTHING_PROMPTS.get(lang, CLOTHING_PROMPTS["en"])
        styles = CLOTHING_STYLES
    else:
        prompts = ADVANCED_PROMPTS.get(lang, ADVANCED_PROMPTS["en"])
        styles = ADVANCED_STYLES

    # Use session state for demo generation
    if 'demo_generated' not in st.session_state:
        st.session_state.demo_generated = False
    if 'demo_generating' not in st.session_state:
        st.session_state.demo_generating = False

    # Pre-generated demo data (mock - will be replaced with DB data)
    # TODO: Load from database when GoEnhance API integration is complete
    demo_data = {
        "clothing": {
            "prompt": prompts[0] if prompts else "Transform into elegant dress",
            "style": styles[0].get("name", "Casual Wear") if styles else "Casual Wear",
            "image_before": None,  # Will be URL from database
            "image_after": None,   # Will be URL from database
            "video_url": None,     # Will be URL from database (5 sec video)
        },
        "advanced": {
            "prompt": prompts[0] if prompts else "A cute cat playing",
            "style": styles[0].get("name", "Japanese Anime") if styles else "Japanese Anime",
            "image_before": None,
            "image_after": None,
            "video_url": None,
        }
    }
    current_demo = demo_data.get(feature, demo_data["clothing"])

    # Generate button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button(t['generate_btn'], key="generate_demo_preview", use_container_width=True, type="primary"):
            st.session_state.demo_generating = True
            st.session_state.demo_generated = False
            st.rerun()

    # Show generation progress
    if st.session_state.demo_generating:
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Step 1: Processing prompt
        status_text.markdown(f"**{t['step1']}**")
        progress_bar.progress(20)
        import time
        time.sleep(0.5)

        # Step 2: Generating image
        status_text.markdown(f"**{t['step2']}**")
        progress_bar.progress(50)
        time.sleep(0.8)

        # Step 3: Creating video
        status_text.markdown(f"**{t['step3']}**")
        progress_bar.progress(80)
        time.sleep(0.7)

        # Complete
        progress_bar.progress(100)
        status_text.markdown(f"**{t['complete']}**")
        time.sleep(0.3)

        st.session_state.demo_generating = False
        st.session_state.demo_generated = True
        st.rerun()

    # Show generated result
    if st.session_state.demo_generated:
        st.success(t['complete'])

        # Info about demo mode
        st.info(f"ℹ️ {t['api_note']}")

        # Show prompt and style used
        st.markdown(f"""
            <div class="result-card" style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border: 2px solid #667eea; border-radius: 15px; padding: 20px; margin: 15px 0;">
                <p><strong>{t['prompt_label']}</strong> {current_demo['prompt']}</p>
                <p><strong>{t['style_label']}</strong> {current_demo['style']}</p>
            </div>
        """, unsafe_allow_html=True)

        # Before/After images
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"**{t['before']}**")
            if current_demo.get('image_before'):
                st.image(current_demo['image_before'], use_container_width=True)
            else:
                st.markdown("""
                    <div style="background: linear-gradient(135deg, #2d2d44 0%, #1a1a2e 100%);
                                padding: 80px 20px; text-align: center; border-radius: 15px;
                                border: 2px dashed #444;">
                        <span style="font-size: 3rem;">🖼️</span>
                        <p style="color: #9CA3AF; margin-top: 10px;">Original Image</p>
                        <p style="color: #666; font-size: 0.8rem;">(DB integration pending)</p>
                    </div>
                """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"**{t['after']}**")
            if current_demo.get('image_after'):
                st.image(current_demo['image_after'], use_container_width=True)
            else:
                st.markdown("""
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                padding: 80px 20px; text-align: center; border-radius: 15px;
                                border: 2px solid #f093fb;">
                        <span style="font-size: 3rem;">✨</span>
                        <p style="color: white; margin-top: 10px;">Transformed Image</p>
                        <p style="color: rgba(255,255,255,0.7); font-size: 0.8rem;">(GoEnhance API)</p>
                    </div>
                """, unsafe_allow_html=True)

        # Video preview
        st.markdown(f"**{t['video']}** (5 sec)")
        if current_demo.get('video_url'):
            st.video(current_demo['video_url'])
        else:
            st.markdown("""
                <div style="background: linear-gradient(135deg, #0f3460 0%, #16213e 100%);
                            padding: 60px 20px; text-align: center; border-radius: 15px;
                            border: 2px solid #1a5f7a; margin-top: 10px;">
                    <span style="font-size: 3rem;">🎬</span>
                    <p style="color: white; margin-top: 10px;">5 Second Video Preview</p>
                    <p style="color: #9CA3AF; font-size: 0.9rem;">▶️ Video will appear here when generated</p>
                    <p style="color: #666; font-size: 0.8rem;">(Video generation pending DB integration)</p>
                </div>
            """, unsafe_allow_html=True)

        # Reset button
        if st.button("🔄 Try Another", key="reset_demo"):
            st.session_state.demo_generated = False
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
    """Show videos for a selected category"""
    st.markdown("---")

    # Back button
    if st.button(translations['back'], key="back_to_categories"):
        st.session_state.selected_category = None
        st.rerun()

    # Fetch videos from API
    if api_client:
        with st.spinner(translations['loading']):
            result = api_client.demo_get_category_videos(category_slug, limit=10)
    else:
        result = None

    if result and result.get('videos'):
        videos = result['videos']
        category_name = result.get('category_name', category_slug.title())

        st.markdown(f"### 🎬 {translations['videos_in']} {category_name}")
        st.markdown(f"*{len(videos)} videos*")

        # Display videos in a grid (2 columns)
        for i in range(0, len(videos), 2):
            cols = st.columns(2)

            for j, col in enumerate(cols):
                idx = i + j
                if idx < len(videos):
                    video = videos[idx]
                    with col:
                        # Video card
                        st.markdown(f"""
                            <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                                        border-radius: 15px; padding: 15px; margin-bottom: 15px;
                                        border: 2px solid #333;">
                                <h4 style="color: #fff; margin: 0 0 10px 0;">{video.get('title', 'Demo Video')}</h4>
                                <p style="color: #9CA3AF; font-size: 0.9rem; margin: 0 0 10px 0;">
                                    {video.get('prompt', '')[:100]}...
                                </p>
                                <p style="color: #667eea; font-size: 0.8rem;">
                                    ⏱️ {video.get('duration_seconds', 5)}s
                                    {f" | 🎨 {video.get('style')}" if video.get('style') else ""}
                                </p>
                            </div>
                        """, unsafe_allow_html=True)

                        # Show video if URL exists
                        if video.get('video_url'):
                            try:
                                st.video(video['video_url'])
                            except Exception:
                                # Show thumbnail if video fails
                                if video.get('thumbnail_url'):
                                    st.image(video['thumbnail_url'], use_container_width=True)
                                else:
                                    st.info("Video preview unavailable")
                        elif video.get('thumbnail_url'):
                            st.image(video['thumbnail_url'], use_container_width=True)
                        else:
                            # Placeholder
                            st.markdown("""
                                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                            padding: 60px 20px; text-align: center; border-radius: 10px;">
                                    <span style="font-size: 2rem;">🎬</span>
                                    <p style="color: white;">Video Preview</p>
                                </div>
                            """, unsafe_allow_html=True)
    else:
        # No videos found - show placeholder
        st.info(f"ℹ️ {translations['no_videos']}")

        # Show sample placeholders
        st.markdown("### 🎬 Sample Videos (Coming Soon)")
        cols = st.columns(3)
        for i, col in enumerate(cols):
            with col:
                st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #2d2d44 0%, #1a1a2e 100%);
                                padding: 60px 20px; text-align: center; border-radius: 15px;
                                border: 2px dashed #444; margin-bottom: 10px;">
                        <span style="font-size: 2.5rem;">🎬</span>
                        <p style="color: #9CA3AF; margin-top: 10px;">Sample Video {i+1}</p>
                        <p style="color: #666; font-size: 0.8rem;">5 seconds</p>
                    </div>
                """, unsafe_allow_html=True)


def show_upgrade_cta():
    """Show upgrade call-to-action"""
    st.markdown("---")
    st.markdown("""
        <div class="upgrade-banner">
            <div class="upgrade-text">
                Want unlimited access? Upgrade to Pro for full features!
            </div>
            <br>
            <a href="#" style="color: white; text-decoration: none; background: rgba(0,0,0,0.3); padding: 10px 30px; border-radius: 20px;">
                View Plans
            </a>
        </div>
    """, unsafe_allow_html=True)


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
