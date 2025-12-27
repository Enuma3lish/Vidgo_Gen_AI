# PictaFlux - AI Image Generation Platform Plan

## Project Overview

Transform VidGo into **PictaFlux** - a visually stunning AI image generation platform inspired by [豆绘AI](https://www.douhuiai.com/).

| Item | Details |
|------|---------|
| **Project Name** | PictaFlux (Vidgo_AI) |
| **Frontend** | Streamlit (keep existing) |
| **Key Advantage** | 5 Languages: EN, ZH, JA, KO, ES |
| **Exclusions** | No Model Training, No DeepSeek |
| **New Feature** | Developer API Service |
| **Goal** | Eye-catching design that attracts users at first sight |

---

## Design Philosophy

### First Impression Matters

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   "Users decide in 3 seconds whether to stay or leave"         │
│                                                                 │
│   Key Elements:                                                 │
│   ✦ Hero section with stunning AI-generated showcase           │
│   ✦ Smooth animations and transitions                          │
│   ✦ Dark mode with vibrant accent colors                       │
│   ✦ Live demo that generates in real-time                      │
│   ✦ Floating gallery of best generations                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Color Palette

```
Primary:      #6366F1 (Indigo)     - Main actions, highlights
Secondary:    #8B5CF6 (Purple)     - Accents, gradients
Background:   #0F0F23 (Dark Navy)  - Main background
Surface:      #1A1A2E (Dark Blue)  - Cards, panels
Accent:       #F472B6 (Pink)       - Special highlights
Success:      #10B981 (Emerald)    - Completed states
Text:         #E2E8F0 (Light Gray) - Primary text
```

---

## Homepage Design

### Hero Section (Above the Fold)

```
┌─────────────────────────────────────────────────────────────────┐
│  [Logo] PictaFlux                    [EN ▼] [Login] [Sign Up]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│         ✨ Create Stunning AI Art in Seconds ✨                 │
│                                                                 │
│    "Transform your imagination into breathtaking visuals"      │
│                                                                 │
│    ┌─────────────────────────────────────────────────────┐     │
│    │  🎨 Describe your vision...                         │     │
│    │  ________________________________________________   │     │
│    │                                                     │     │
│    │  Style: [Anime ▼]  Ratio: [1:1 ▼]  [✨ Generate]   │     │
│    └─────────────────────────────────────────────────────┘     │
│                                                                 │
│    ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐            │
│    │  IMG 1  │ │  IMG 2  │ │  IMG 3  │ │  IMG 4  │  ← Auto    │
│    │ (anime) │ │(realism)│ │ (3D)    │ │(artistic)│   Scroll  │
│    └─────────┘ └─────────┘ └─────────┘ └─────────┘            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Feature Showcase Section

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                    🚀 What You Can Create                       │
│                                                                 │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │
│  │   🖼️ IMAGE    │  │   🎬 VIDEO    │  │   🎨 STYLES   │       │
│  │               │  │               │  │               │       │
│  │ Text-to-Image │  │ Image-to-Video│  │ Style Transfer│       │
│  │ AI Generation │  │ Animation     │  │ 15+ Styles    │       │
│  │               │  │               │  │               │       │
│  │  [Try Now →]  │  │  [Try Now →]  │  │  [Try Now →]  │       │
│  └───────────────┘  └───────────────┘  └───────────────┘       │
│                                                                 │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │
│  │   ⬆️ UPSCALE  │  │   🔄 ENHANCE  │  │   🌐 API      │       │
│  │               │  │               │  │               │       │
│  │ 2x/4x Upscale │  │ Video Effects │  │ Developer API │       │
│  │ HD Quality    │  │ V2V Transform │  │ Build Apps    │       │
│  │               │  │               │  │               │       │
│  │  [Try Now →]  │  │  [Try Now →]  │  │  [Docs →]    │       │
│  └───────────────┘  └───────────────┘  └───────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Live Gallery Section

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│              🌟 Community Creations (Live Feed)                 │
│                                                                 │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐      │
│  │     │ │     │ │     │ │     │ │     │ │     │ │     │      │
│  │ IMG │ │ IMG │ │ IMG │ │ IMG │ │ IMG │ │ IMG │ │ IMG │  →   │
│  │     │ │     │ │     │ │     │ │     │ │     │ │     │      │
│  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘      │
│                     ← Auto-scrolling Masonry Grid →            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Page Structure

### 1. Homepage (`/`)
- Hero with live generation demo
- Feature cards with hover effects
- Community gallery
- Pricing preview
- Language selector (prominent)

### 2. Generate Page (`/generate`)
- **Text-to-Image** tab
- **Image-to-Image** tab (style transfer)
- **Image-to-Video** tab
- Real-time progress with animations
- Result gallery with download/share

### 3. Gallery Page (`/gallery`)
- User's generation history
- Filter by type (image/video)
- Collections/Favorites
- Public gallery (community)

### 4. Pricing Page (`/pricing`)
- Tier comparison table
- Credit packages
- API pricing
- FAQ

### 5. API Documentation (`/api`)
- Interactive API explorer
- Code examples (Python, JavaScript, cURL)
- API key management
- Usage dashboard

### 6. Profile Page (`/profile`)
- User settings
- Language preference
- Credit balance
- API keys

---

## Feature List

### Phase 1: Core Platform (MVP)

| Feature | Description | API Endpoint |
|---------|-------------|--------------|
| Text-to-Image | Generate images from text prompts | `POST /api/v1/generate/image` |
| Style Transfer | Apply artistic styles to images | `POST /api/v1/generate/style` |
| Image-to-Video | Animate static images | `POST /api/v1/generate/video` |
| Video Enhance | Apply V2V effects | `POST /api/v1/generate/enhance` |
| Upscale | 2x/4x image upscaling | `POST /api/v1/generate/upscale` |

### Phase 2: User Features

| Feature | Description |
|---------|-------------|
| Generation History | View all past generations |
| Collections | Organize favorites |
| Credits System | Purchase and use credits |
| Share | Share creations publicly |

### Phase 3: Developer API

| Feature | Description |
|---------|-------------|
| API Keys | Create/manage API keys |
| REST API | Full generation API access |
| Webhooks | Callbacks on completion |
| Rate Limits | Tier-based limits |
| Usage Stats | API analytics dashboard |

---

## Streamlit UI Enhancements

### Custom CSS for Eye-Catching Design

```python
# Custom theme with gradients and animations
st.markdown("""
<style>
/* Dark theme with gradient background */
.stApp {
    background: linear-gradient(135deg, #0F0F23 0%, #1A1A2E 100%);
}

/* Glowing buttons */
.stButton > button {
    background: linear-gradient(90deg, #6366F1, #8B5CF6);
    border: none;
    border-radius: 12px;
    color: white;
    font-weight: 600;
    box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
    transition: all 0.3s ease;
}

.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(99, 102, 241, 0.6);
}

/* Card-style containers */
.generation-card {
    background: rgba(26, 26, 46, 0.8);
    border: 1px solid rgba(99, 102, 241, 0.2);
    border-radius: 16px;
    padding: 24px;
    backdrop-filter: blur(10px);
}

/* Animated gradient text */
.hero-title {
    background: linear-gradient(90deg, #6366F1, #F472B6, #6366F1);
    background-size: 200% auto;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: gradient 3s linear infinite;
}

@keyframes gradient {
    0% { background-position: 0% center; }
    100% { background-position: 200% center; }
}

/* Floating animation for gallery */
@keyframes float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-10px); }
}

.gallery-item {
    animation: float 3s ease-in-out infinite;
}
</style>
""", unsafe_allow_html=True)
```

### Components to Build

| Component | Purpose |
|-----------|---------|
| `HeroSection` | Animated hero with live demo |
| `FeatureCard` | Hover-effect feature cards |
| `GenerationPanel` | Main generation interface |
| `GalleryGrid` | Masonry-style image grid |
| `LanguageSelector` | 5-language dropdown |
| `CreditDisplay` | Animated credit counter |
| `ProgressBar` | Custom animated progress |
| `StylePicker` | Visual style selector |

---

## i18n (5 Languages)

### Implementation

```python
# translations.py
TRANSLATIONS = {
    "en": {
        "hero_title": "Create Stunning AI Art in Seconds",
        "hero_subtitle": "Transform your imagination into breathtaking visuals",
        "generate_btn": "Generate",
        "styles": "Styles",
        ...
    },
    "zh": {
        "hero_title": "秒速创作惊艳AI艺术",
        "hero_subtitle": "将你的想象变成惊艳的视觉作品",
        "generate_btn": "生成",
        "styles": "风格",
        ...
    },
    "ja": {
        "hero_title": "秒速でAIアートを作成",
        "hero_subtitle": "あなたの想像を息をのむようなビジュアルに",
        "generate_btn": "生成",
        "styles": "スタイル",
        ...
    },
    "ko": {
        "hero_title": "몇 초 만에 멋진 AI 아트 제작",
        "hero_subtitle": "상상을 놀라운 비주얼로 변환",
        "generate_btn": "생성",
        "styles": "스타일",
        ...
    },
    "es": {
        "hero_title": "Crea Arte IA Impresionante en Segundos",
        "hero_subtitle": "Transforma tu imaginación en visuales impresionantes",
        "generate_btn": "Generar",
        "styles": "Estilos",
        ...
    }
}
```

### Language Selector UI

```
┌─────────────────┐
│  🌐 EN ▼        │
├─────────────────┤
│  🇺🇸 English    │
│  🇨🇳 简体中文    │
│  🇯🇵 日本語     │
│  🇰🇷 한국어     │
│  🇪🇸 Español   │
└─────────────────┘
```

---

## Developer API

### API Key System

```
┌─────────────────────────────────────────────────────────────────┐
│  🔑 API Keys                                           [+ New]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Name: Production Key                                     │   │
│  │ Key:  pk_live_xxxx...xxxx (click to copy)               │   │
│  │ Created: Dec 27, 2024                                    │   │
│  │ Last Used: 2 hours ago                                   │   │
│  │ Requests: 1,234 this month                               │   │
│  │                                           [Revoke]       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### API Documentation Page

```
┌─────────────────────────────────────────────────────────────────┐
│  📚 API Documentation                                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Getting Started] [Authentication] [Endpoints] [Examples]     │
│                                                                 │
│  ## Text-to-Image Generation                                    │
│                                                                 │
│  ```bash                                                        │
│  curl -X POST https://api.pictaflux.com/v1/generate/image \    │
│    -H "Authorization: Bearer YOUR_API_KEY" \                   │
│    -H "Content-Type: application/json" \                       │
│    -d '{                                                        │
│      "prompt": "A beautiful sunset over mountains",            │
│      "style": "realistic",                                      │
│      "aspect_ratio": "16:9"                                     │
│    }'                                                           │
│  ```                                                            │
│                                                                 │
│  [Python] [JavaScript] [cURL]                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Development Timeline

### Estimated Hours (1 Person, 8h/day, with Claude Code)

| Phase | Task | Hours | Days |
|-------|------|-------|------|
| **Phase 1** | **UI Redesign & Core Features** | **40h** | **5 days** |
| 1.1 | Custom CSS/Theme (dark mode, gradients, animations) | 4h | 0.5 |
| 1.2 | Hero section with live demo | 4h | 0.5 |
| 1.3 | Feature showcase cards | 3h | 0.375 |
| 1.4 | Generation page redesign | 8h | 1 |
| 1.5 | Style picker with visual previews | 4h | 0.5 |
| 1.6 | Gallery page with masonry grid | 6h | 0.75 |
| 1.7 | i18n system + 5 language translations | 6h | 0.75 |
| 1.8 | Language selector component | 2h | 0.25 |
| 1.9 | Mobile responsive fixes | 3h | 0.375 |
| | | | |
| **Phase 2** | **Backend Enhancements** | **24h** | **3 days** |
| 2.1 | Generation history table + endpoints | 4h | 0.5 |
| 2.2 | Collections/Favorites system | 4h | 0.5 |
| 2.3 | Credit system (balance, transactions) | 6h | 0.75 |
| 2.4 | API key management | 4h | 0.5 |
| 2.5 | Rate limiting middleware | 3h | 0.375 |
| 2.6 | Public API endpoints | 3h | 0.375 |
| | | | |
| **Phase 3** | **Developer API** | **20h** | **2.5 days** |
| 3.1 | API authentication (key-based) | 3h | 0.375 |
| 3.2 | Generation API endpoints | 4h | 0.5 |
| 3.3 | Webhook system | 4h | 0.5 |
| 3.4 | API documentation page (Streamlit) | 4h | 0.5 |
| 3.5 | Usage analytics dashboard | 3h | 0.375 |
| 3.6 | Python SDK (basic) | 2h | 0.25 |
| | | | |
| **Phase 4** | **Polish & Deploy** | **16h** | **2 days** |
| 4.1 | Performance optimization | 4h | 0.5 |
| 4.2 | Error handling & user feedback | 3h | 0.375 |
| 4.3 | Loading states & animations | 3h | 0.375 |
| 4.4 | Testing (manual + basic automated) | 4h | 0.5 |
| 4.5 | Docker & deployment updates | 2h | 0.25 |
| | | | |
| **TOTAL** | | **100h** | **12.5 days** |

---

## Summary

```
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│  📅 Total Development Time: ~12-13 working days (100 hours)   │
│                                                                │
│  Week 1 (Days 1-5):  UI Redesign + Core Features              │
│  Week 2 (Days 6-8):  Backend + Credits + History              │
│  Week 3 (Days 9-11): Developer API + Documentation           │
│  Week 3 (Days 12-13): Polish + Deploy                         │
│                                                                │
│  🎯 Key Deliverables:                                          │
│  ✦ Eye-catching dark theme with animations                    │
│  ✦ 5 language support (EN, ZH, JA, KO, ES)                   │
│  ✦ Full Developer API with documentation                      │
│  ✦ Credit system for monetization                             │
│  ✦ Generation history & collections                           │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Next Steps

1. [ ] Review and approve this plan
2. [ ] Start Phase 1.1 - Custom CSS/Theme
3. [ ] Create component library for Streamlit
4. [ ] Begin hero section implementation

---

*Created: December 27, 2024*
