
import streamlit as st
import base64
from typing import Dict, Any
import textwrap

def load_css():
    """Load the custom CSS file"""
    try:
        with open('frontend/assets/style.css') as f:
            css = f.read()
            st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Failed to load CSS: {e}")

def render_header(user: Dict[str, Any] = None, current_lang: str = "en", supported_langs: Dict = None):
    """
    Renders the custom sticky header.
    """
    logo_html = """
    <a href="#" class="vidgo-logo">
        <span style="color:var(--vidgo-primary)">V</span>idGo AI
    </a>
    """

    nav_html = """
    <div class="vidgo-nav">
        <a href="#" class="vidgo-nav-item active">首頁 (Home)</a>
        <a href="#" class="vidgo-nav-item">AI創作 (Creation)</a>
        <a href="#" class="vidgo-nav-item">作品庫 (Gallery)</a>
    </div>
    """

    if user:
        user_section = f"""
        <div class="vidgo-btn vidgo-btn-light">👤 {user.get('username', 'User')}</div>
        """
    else:
        user_section = """
        <a href="#" class="vidgo-btn vidgo-btn-light" onclick="parent.window.location.reload()">登入 (Login)</a>
        <a href="#" class="vidgo-btn vidgo-btn-primary">註冊 (Register)</a>
        """

    lang_display = supported_langs.get(current_lang, "English") if supported_langs else current_lang

    html = f"""
<div class="vidgo-header">
    <div class="vidgo-logo-section">
        {logo_html.strip()}
        {nav_html.strip()}
    </div>
    <div class="vidgo-header-right">
        <span style="font-size:12px; color:#666;">{lang_display}</span>
        {user_section.strip()}
    </div>
</div>
""".strip()

    st.markdown(html, unsafe_allow_html=True)

def render_sidebar_custom():
    """
    Renders the fixed left sidebar using HTML.
    """
    sidebar_html = """
<div class="vidgo-sidebar">
    <a href="#" class="vidgo-sidebar-item active">
        <div class="vidgo-sidebar-icon">🎨</div>
        <div class="vidgo-sidebar-text">創作</div>
    </a>
    <a href="#" class="vidgo-sidebar-item">
        <div class="vidgo-sidebar-icon">✏️</div>
        <div class="vidgo-sidebar-text">編輯</div>
    </a>
    <a href="#" class="vidgo-sidebar-item">
        <div class="vidgo-sidebar-icon">🎬</div>
        <div class="vidgo-sidebar-text">視頻</div>
    </a>
    <a href="#" class="vidgo-sidebar-item">
        <div class="vidgo-sidebar-icon">🏠</div>
        <div class="vidgo-sidebar-text">建築</div>
    </a>
    <a href="#" class="vidgo-sidebar-item">
        <div class="vidgo-sidebar-icon">🛒</div>
        <div class="vidgo-sidebar-text">電商</div>
    </a>
    <a href="#" class="vidgo-sidebar-item">
        <div class="vidgo-sidebar-icon">👤</div>
        <div class="vidgo-sidebar-text">人像</div>
    </a>
    <a href="#" class="vidgo-sidebar-item">
        <div class="vidgo-sidebar-icon">📁</div>
        <div class="vidgo-sidebar-text">作品</div>
    </a>
    <div style="flex-grow:1"></div>
    <a href="#" class="vidgo-sidebar-item">
        <div class="vidgo-sidebar-icon">⚙️</div>
    </a>
</div>
""".strip()
    st.markdown(sidebar_html, unsafe_allow_html=True)

def render_feature_card(title, description, icon, key=None, on_click=None):
    """
    Renders a feature card.
    """
    with st.container():
        html = f"""
<div class="feature-card">
    <div class="feature-icon">{icon}</div>
    <div class="feature-title">{title}</div>
    <div class="feature-desc">{description}</div>
</div>
""".strip()
        st.markdown(html, unsafe_allow_html=True)
        st.button("Open", key=key, use_container_width=True)

def render_hero_input():
    """
    Renders the large input box area.
    """
    st.markdown('<div style="margin-bottom: 20px;"></div>', unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### Creative Studio")
        prompt = st.text_area("Describe what you want to create...", height=100, label_visibility="collapsed")

        c1, c2 = st.columns([1, 5])
        with c1:
            st.button("Generate", type="primary")

    with col2:
        st.info("🚀 **Pro Tip**: Try 'Cyberpunk city at night' for amazing results!")
