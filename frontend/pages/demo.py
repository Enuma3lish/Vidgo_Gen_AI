"""
Demo Page - AI Clothing Transform & GoEnhance Effects Showcase
VidGo - Smart Demo Engine with Multi-language Support

Features:
- AI Clothing Transformation demos
- GoEnhance style effects showcase
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


# Sample demo data (fallback when API is unavailable)
SAMPLE_STYLES = [
    {"id": 122, "name": "Japanese Anime", "slug": "japanese-anime"},
    {"id": 124, "name": "Pixar Style", "slug": "pixar-style"},
    {"id": 132, "name": "Makoto Shinkai", "slug": "makoto-shinkai"},
    {"id": 179, "name": "Cyberpunk", "slug": "cyberpunk"},
    {"id": 134, "name": "Watercolor", "slug": "watercolor"},
    {"id": 127, "name": "Oil Painting", "slug": "oil-painting"},
]

SAMPLE_CATEGORIES = [
    {"slug": "animals", "name": "Animals", "topic_count": 10},
    {"slug": "nature", "name": "Nature", "topic_count": 10},
    {"slug": "urban", "name": "Urban", "topic_count": 10},
    {"slug": "people", "name": "People", "topic_count": 10},
    {"slug": "fantasy", "name": "Fantasy", "topic_count": 10},
    {"slug": "sci-fi", "name": "Sci-Fi", "topic_count": 10},
]

SAMPLE_PROMPTS = {
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


def show_demo_header():
    """Show demo page header"""
    st.markdown(get_demo_css(), unsafe_allow_html=True)

    st.markdown("""
        <h1 class="demo-header">VidGo AI Demo</h1>
        <p class="demo-subtitle">
            Experience AI-powered video transformation with clothing effects and GoEnhance styles
        </p>
    """, unsafe_allow_html=True)


def show_feature_cards():
    """Show main feature cards"""
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
            <div class="feature-card">
                <div class="feature-icon">👗</div>
                <div class="feature-title">AI Clothing Transform</div>
                <div class="feature-desc">
                    Transform clothing styles in your videos with AI magic.
                    Change outfits, styles, and looks instantly.
                </div>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
            <div class="feature-card">
                <div class="feature-icon">✨</div>
                <div class="feature-title">GoEnhance Effects</div>
                <div class="feature-desc">
                    Apply stunning artistic styles to your videos.
                    Anime, Pixar, Cyberpunk, Watercolor and more!
                </div>
            </div>
        """, unsafe_allow_html=True)


def show_style_gallery(api_client):
    """Show available styles gallery"""
    st.markdown("### Available Styles")

    # Try to get styles from API, fallback to samples
    styles = api_client.demo_get_styles() if api_client else SAMPLE_STYLES
    if not styles:
        styles = SAMPLE_STYLES

    cols = st.columns(6)
    style_icons = ["🎨", "🎬", "🌸", "🤖", "🎭", "🖼️", "🌊", "⚡", "🔮", "🎪", "🌈", "🎮"]

    for i, style in enumerate(styles[:12]):
        with cols[i % 6]:
            icon = style_icons[i % len(style_icons)]
            st.markdown(f"""
                <div class="style-card">
                    <div style="font-size: 2rem;">{icon}</div>
                    <div class="style-name">{style.get('name', 'Style')}</div>
                </div>
            """, unsafe_allow_html=True)


def show_language_selector():
    """Show multi-language support badges"""
    st.markdown("### Supported Languages")

    languages = {
        "en": ("English", True),
        "zh-TW": ("繁體中文", True),
        "ja": ("日本語", True),
        "ko": ("한국어", True),
        "es": ("Español", True),
    }

    badges_html = ""
    for code, (name, active) in languages.items():
        badge_class = "lang-badge-active" if active else "lang-badge-inactive"
        badges_html += f'<span class="lang-badge {badge_class}">{name}</span>'

    st.markdown(f'<div style="text-align: center;">{badges_html}</div>', unsafe_allow_html=True)


def show_demo_input(api_client):
    """Show demo prompt input and result"""
    st.markdown("### Try It Now")

    # Language selection
    lang = st.selectbox(
        "Select prompt language",
        options=["en", "zh-TW", "ja", "ko", "es"],
        format_func=lambda x: {
            "en": "English",
            "zh-TW": "繁體中文",
            "ja": "日本語",
            "ko": "한국어",
            "es": "Español"
        }.get(x, x)
    )

    # Sample prompts for selected language
    sample_prompts = SAMPLE_PROMPTS.get(lang, SAMPLE_PROMPTS["en"])

    col1, col2 = st.columns([3, 1])

    with col1:
        # Prompt input
        prompt = st.text_area(
            "Enter your prompt",
            placeholder=f"Example: {sample_prompts[0]}",
            height=100,
            key="demo_prompt"
        )

    with col2:
        st.markdown("**Quick Examples:**")
        for i, sample in enumerate(sample_prompts[:3]):
            if st.button(f"Try #{i+1}", key=f"sample_{i}"):
                st.session_state.demo_prompt = sample
                st.rerun()

    # Style selection
    styles = api_client.demo_get_styles() if api_client else SAMPLE_STYLES
    if not styles:
        styles = SAMPLE_STYLES

    style_options = ["Auto"] + [s.get("name", "Style") for s in styles]
    selected_style = st.selectbox("Select style (optional)", options=style_options)

    # Generate button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        generate_clicked = st.button(
            "Generate Demo",
            type="primary",
            use_container_width=True
        )

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

            # Search for demo
            style_slug = None
            if selected_style != "Auto":
                for s in styles:
                    if s.get("name") == selected_style:
                        style_slug = s.get("slug")
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
                show_sample_result(prompt, selected_style)


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


def show_categories(api_client):
    """Show demo categories"""
    st.markdown("### Explore Categories")

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

    cols = st.columns(len(categories))
    for i, cat in enumerate(categories):
        with cols[i]:
            icon = category_icons.get(cat.get("slug", ""), "📁")
            st.markdown(f"""
                <div class="style-card">
                    <div style="font-size: 2rem;">{icon}</div>
                    <div class="style-name">{cat.get('name', 'Category')}</div>
                    <div style="color: #667eea; font-size: 0.9rem;">
                        {cat.get('topic_count', 0)} topics
                    </div>
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
    show_feature_cards()

    st.markdown("---")
    show_language_selector()

    st.markdown("---")
    show_demo_input(api_client)

    st.markdown("---")
    show_style_gallery(api_client)

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
