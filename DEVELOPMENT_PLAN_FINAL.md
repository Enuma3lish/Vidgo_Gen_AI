# VidGo Development Plan (Final v2)

> **Version**: 2.0  
> **Updated**: 2025/01/01  
> **Based on**: ARCHITECTURE_FINAL.md  

---

## Project Summary

| Item | Details |
|------|---------|
| **Project** | VidGo - AI 電商 & 室內視覺工具平台 |
| **Target Launch** | January 2025 |
| **Total Hours** | 187 hours (~24 working days) |
| **Initial Monthly Cost** | $150-200 USD |
| **Break-even Point** | 10-15 paid users |
| **Main Features** | 一鍵白底圖、商品場景圖、AI試穿、毛坯精裝、短影片 |
| **Frontend** | Vue 3 + Tailwind CSS + TypeScript |
| **Backend** | FastAPI + PostgreSQL + Redis + Celery |
| **Material System** | 960 pre-generated examples (5 tools × 6-8 topics × 30 each) |
| **Landing Page** | 9 sections (Hero, Features, How It Works, Examples, Comparison, Testimonials, Pricing, FAQ, CTA) |

---

## White-Label API Strategy

> **Important**: All external APIs are white-labeled as VidGo's own features. Users experience seamless VidGo branding without seeing underlying provider names.

### API Mapping Table

| VidGo Feature | Internal Service | API Provider | Status |
|---------------|------------------|--------------|--------|
| **VidGo Video** | Video generation | Leonardo AI | ✅ Active |
| **VidGo Image** | Image generation (Imagen 4.0) | Google Gemini | ✅ Active |
| **VidGo Style Effects** | V2V transformation | GoEnhance API | ✅ Active |
| **VidGo HD Enhance** | 4K upscale | GoEnhance API | ✅ Active |
| **VidGo Video Pro** | Advanced video models | Pollo AI | ✅ Active |
| **VidGo AI Avatar** | Photo-to-avatar, lip sync | Pollo AI | ✅ Active (EN, zh-TW) |
| **VidGo 數位人** | AI Digital Human | Pollo AI + TTS | ✅ Active |
| **VidGo 台語配音** | Taiwanese TTS | ATEN AI Voice | ⏳ Pending |
| **VidGo 台語代言人** | Taiwanese Avatar | ATEN + Pollo | ⏳ Pending |
| **VidGo BG Removal** | Background removal | rembg (local) | ✅ Active |
| **VidGo Content Safety** | Moderation | Google Gemini | ✅ Active |
| **VidGo Smart Prompt** | Prompt enhancement | Google Gemini | ✅ Active |

### Language Support

| Feature | EN | zh-TW | 日本語 | 한국어 | Español | 台語 |
|---------|----|----|----|----|----|----|
| Video Generation | ✅ | ✅ | ✅ | ✅ | ✅ | ⏳ |
| AI Avatar | ✅ | ✅ | ✅ | ✅ | ✅ | ⏳ |
| TTS Voice | ✅ | ✅ | ✅ | ✅ | ✅ | ⏳ ATEN |

> **Note**: 台語 (Taiwanese Hokkien) support pending ATEN AI Voice API integration.

---

## Service Tiers

### 定價方案（首月半價促銷）

| 方案 | 原價 | 促銷價 | 每日生成 | 主要功能 |
|------|------|--------|----------|----------|
| **Demo** | $0 | $0 | 5 次 (一次性) | 浮水印、僅從素材庫選擇、不可下載 |
| **Starter** | NT$329 | **NT$165**/月 | 30 次/天 | 1080P、優先生成、電郵支援 |
| **Pro** ⭐ | NT$649 | **NT$325**/月 | **無限次** | 1080P、批量處理、台語優先、專屬客服、7 天退款 |
| **Pro+** | NT$1099 | **NT$550**/月 | **無限次** | 4K、最優先處理、API 接入、專屬帳號經理、客製化 |

### 促銷機制
- ✓ 首月半價優惠
- ✓ 7 天不滿意全額退款
- ✓ 隨時可取消訂閱
- ✓ 本月優惠剩餘名額：動態顯示

### 免費試用機制
- 全站每日免費額度：100 次
- 每人免費試用：5 次（未登入用 IP 識別）
- 首頁可直接試做（無需註冊）

---

## Development Timeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DEVELOPMENT TIMELINE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Phase 1: Core Infrastructure (4h) ✅ COMPLETE                              │
│  ────────────────────────────────                                           │
│                                                                              │
│  Phase 2: Smart Demo + Gemini (15h) ✅ COMPLETE                             │
│  ──────────────────────────────────                                         │
│                                                                              │
│  Phase 2.5: Material System (12h) 🆕 NEW                                    │
│  ────────────────────────────────────                                       │
│  │ Material DB + Seed Script + Watermark + Demo Restrictions                │
│                                                                              │
│  Phase 3: Leonardo AI Integration (18h) ✅ COMPLETE                         │
│  ───────────────────────────────────────                                    │
│                                                                              │
│  Phase 4: VidGo Effects - GoEnhance (12h) ✅ COMPLETE                       │
│  ────────────────────────────────────────                                   │
│                                                                              │
│  Phase 5: Streamlit UI (10h) ✅ COMPLETE (Legacy)                           │
│  ───────────────────────────────────────────────                            │
│                                                                              │
│  Phase 5.1: Vue 3 Frontend Migration (35h) 🔄 UPDATED                       │
│  ──────────────────────────────────────────────────                         │
│  │ Full directory structure + API layer + Stores + Composables              │
│  │ 5 Tool pages + Dashboard + Admin panel                                   │
│                                                                              │
│  Phase 5.2: Landing Page Implementation (12h) 🆕 NEW                        │
│  ────────────────────────────────────────────────                           │
│  │ Hero + Demo Panel + Case Studies + Testimonials + Pricing                │
│  │ Free Quota System + Promo Urgency Counter                                │
│                                                                              │
│  Phase 6: Payment Integration (20h) ⏳ PENDING                              │
│  ─────────────────────────────────────────────                              │
│                                                                              │
│  Phase 7: i18n (6h) ✅ COMPLETE                                             │
│  ─────────────────────────                                                  │
│                                                                              │
│  Phase 8: Admin Dashboard (14h) 🔄 UPDATED                                  │
│  ─────────────────────────────────────────                                  │
│  │ Real-time stats + User management + Material review + Charts             │
│                                                                              │
│  Phase 9: Security + Deploy (12h) ⏳ PENDING                                │
│  ──────────────────────────────────────────                                 │
│                                                                              │
│  Phase 10: Email Verification (6h) ⏳ PENDING                               │
│  ─────────────────────────────────────────                                  │
│                                                                              │
│  Phase 11: Weekly Credit System (4h) ⏳ PENDING                             │
│  ──────────────────────────────────────────                                 │
│                                                                              │
│                          🚀 LAUNCH                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase Checklist

### Phase 1: Core Infrastructure (4h) ✅ COMPLETE

- [x] FastAPI project setup with async support
- [x] PostgreSQL database with async SQLAlchemy
- [x] Redis configuration for caching
- [x] JWT authentication with access + refresh tokens
- [x] User model with email verification fields
- [x] Plans & Promotions system

---

### Phase 2: Smart Demo + Content Moderation (15h) ✅ COMPLETE

- [x] Google Gemini API integration
- [x] Content moderation (18+/illegal detection)
- [x] Prompt enhancement
- [x] Redis-based block cache
- [x] Multi-language support

---

### Phase 2.5: Material System (12h) 🆕 NEW

#### Core Logic - Pre-generation & User Tier Rules

##### 6.0.1 Pre-generation Flow (Service Startup)

Before frontend starts, system auto-generates topic-related materials:

```
┌─────────────────────────────────────────────────────────────────┐
│                    STARTUP PRE-GENERATION                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Step 1: Generate Topic Prompts                                │
│   ─────────────────────────────                                 │
│   For each tool × topic combination:                            │
│   → Use Gemini to create 30 topic-related prompts               │
│   → Store prompts in MaterialTopic table                        │
│                                                                  │
│   Step 2: Generate Source Images (Leonardo/Gemini)              │
│   ───────────────────────────────────────────────               │
│   For each prompt:                                              │
│   → Call Leonardo/Gemini API to generate image                  │
│   → This image is PRIMARY (related to prompt, not random)       │
│   → Store: prompt → generated_image relationship                │
│                                                                  │
│   Step 3: Apply Tool Effects (Conditional)                      │
│   ─────────────────────────────────────────                     │
│   IF tool is Image Effect (remove-bg, product-scene, etc):      │
│      → Apply GoEnhance/Leonardo API to source image             │
│      → Store: source_image → effect_result relationship         │
│   ELSE IF tool is Text-to-Video:                                │
│      → Call Pollo AI with prompt                                │
│      → Store: prompt → result_video relationship                │
│                                                                  │
│   Step 4: Store Complete Chain                                  │
│   ────────────────────────────                                  │
│   Material DB entry:                                            │
│   {                                                             │
│     primary_key: prompt (Gemini-generated description)          │
│     input_image_url: source image (from Step 2)                 │
│     result_image_url: effect result (from Step 3)               │
│     result_video_url: video result (if applicable)              │
│     generation_steps: [step1, step2, step3...] (full chain)     │
│   }                                                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

##### 6.0.2 User Tier Logic

```
┌─────────────────────────────────────────────────────────────────┐
│                       USER TIER LOGIC                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ DEMO TIER (Free) - READ ONLY                            │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │                                                          │    │
│  │ 1. User clicks "Try Demo"                               │    │
│  │ 2. System randomly picks material from DB               │    │
│  │ 3. Display: prompt + before/after (watermarked)         │    │
│  │ 4. NEVER call generation APIs                           │    │
│  │ 5. Block download, show upgrade prompt                  │    │
│  │                                                          │    │
│  │ Technical: SELECT random FROM materials WHERE tool=X    │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ PAID TIER (Starter/Pro/Pro+) - API ACCESS               │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │                                                          │    │
│  │ 1. User uploads image + provides prompt                 │    │
│  │ 2. Content Moderation (Gemini):                         │    │
│  │    → Check for illegal/18+ content                      │    │
│  │    → Generate description of uploaded image             │    │
│  │ 3. Call generation API (Leonardo/GoEnhance/Pollo)       │    │
│  │ 4. Store result to Material DB:                         │    │
│  │    → primary_key: Gemini description of image           │    │
│  │    → prompt: user's effect prompt                       │    │
│  │    → result: generated image/video                      │    │
│  │ 5. This becomes example for Demo users                  │    │
│  │ 6. User downloads without watermark                     │    │
│  │                                                          │    │
│  │ IMPORTANT: Paid users NEVER read from Material DB       │    │
│  │            They always call APIs directly               │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

##### 6.0.3 Material Relationship Chains

All materials maintain complete relationship chains (not random picks):

```
Example 1: Background Removal Tool
──────────────────────────────────
Prompt: "White sneaker product photo for e-commerce"
        ↓ (Leonardo API)
Source Image: sneaker_original.jpg
        ↓ (GoEnhance remove-bg)
Result Image: sneaker_transparent.png

Stored as:
{
  primary_key: "White sneaker product photo for e-commerce"
  input_image_url: "/static/sneaker_original.jpg"
  result_image_url: "/static/sneaker_transparent.png"
  generation_steps: [
    {"step": 1, "api": "leonardo", "action": "text-to-image"},
    {"step": 2, "api": "goenhance", "action": "remove-background"}
  ]
}

Example 2: User Upload (Paid Tier)
──────────────────────────────────
User uploads: custom_bag.jpg
User prompt: "Place on marble counter with plants"

System flow:
1. Gemini describes: "Brown leather handbag, vintage style"
2. Gemini checks: No illegal content ✓
3. GoEnhance: composite with scene
4. Store result

Stored as:
{
  primary_key: "Brown leather handbag, vintage style"  ← Gemini description
  prompt: "Place on marble counter with plants"       ← User prompt
  input_image_url: "/static/user_bag_123.jpg"
  result_image_url: "/static/bag_marble_scene.jpg"
  source: "user"
  user_id: "xxx"
}
```

#### Database Models
- [ ] Material model with generation_steps tracking
- [ ] UserMaterialView for personalization
- [ ] MaterialTopic configuration table
- [ ] Update User model for material relations

```python
# Material model key fields
class Material(Base):
    id: UUID
    tool_type: Enum[5 tools]
    topic: str
    tags: List[str]
    source: Enum['seed', 'user', 'admin']
    status: Enum['pending', 'approved', 'rejected', 'featured']
    
    prompt: str
    input_image_url: str
    input_params: JSON
    generation_steps: JSON  # 記錄每一步 API 呼叫
    
    result_image_url: str
    result_video_url: str
    result_watermarked_url: str
    
    view_count: int
    use_count: int
    generation_cost_usd: float
```

#### Seed Script
- [ ] Material configuration for all 5 tools
- [ ] Topic definitions (8 topics × 30 prompts each)
- [ ] MaterialGeneratorService class
- [ ] Leonardo API integration (Relaxed Mode)
- [ ] GoEnhance API integration
- [ ] Pollo AI Fashion integration
- [ ] ATEN TTS integration
- [ ] Multi-step generation pipelines:

| Tool | Step 1 | Step 2 | Step 3 |
|------|--------|--------|--------|
| Background Removal | Leonardo generate | Leonardo remove-bg | - |
| Product Scene | Leonardo product | Leonardo remove-bg | GoEnhance composite |
| AI Try-On | Leonardo garment | Pollo Fashion | GoEnhance HD |
| Room Redesign | Leonardo bare room | GoEnhance style | - |
| Short Video | Leonardo image | Leonardo Motion | ATEN TTS + merge |

#### Watermark Service
- [ ] Image watermark (PIL)
- [ ] Video watermark (FFmpeg)
- [ ] Configurable text, opacity, position
- [ ] Upload to CDN after processing

#### Demo User Restrictions
- [ ] Block custom prompt input
- [ ] Return only watermarked results
- [ ] Block download endpoint with upgrade prompt
- [ ] Track material views for personalization

#### User Content Collection
- [ ] MaterialCollectorService
- [ ] Auto-collect from paid user generations
- [ ] Quality scoring (threshold: 0.7)
- [ ] Admin notification for review

#### API Endpoints
- [ ] GET `/api/v1/demo/materials` - Personalized random materials
- [ ] POST `/api/v1/demo/generate` - Demo generate (material_id required)
- [ ] GET `/api/v1/inspiration` - Public inspiration gallery

#### Estimated Resources
| Item | Count | Cost |
|------|-------|------|
| Total Materials | 960 | - |
| Leonardo API calls | ~1500 | $15 |
| GoEnhance API calls | ~500 | $25 |
| Pollo AI calls | ~200 | $20 |
| ATEN TTS calls | ~120 | $6 |
| **Total Seed Cost** | | **~$66** |

---

### Phase 3: Leonardo AI + Prompt Caching (18h) ✅ COMPLETE

- [x] Leonardo API client
- [x] Text-to-Image generation (Phoenix model)
- [x] Image-to-Video generation (Motion SVD)
- [x] Relaxed Mode for cost optimization
- [x] Prompt similarity caching (85% threshold)

---

### Phase 4: VidGo Effects - GoEnhance (12h) ✅ COMPLETE

- [x] GoEnhance API client
- [x] Style transformation effects
- [x] 4K upscale capabilities
- [x] Video enhancement
- [x] Access control (paid users only)

---

### Phase 5.1: Vue 3 Frontend Migration (35h) 🔄 UPDATED

#### Project Setup (4h)
- [ ] Initialize Vue 3 + Vite + TypeScript
- [ ] Configure Tailwind CSS with Dark Tech theme
- [ ] Set up Vue Router with guards
- [ ] Configure Pinia stores
- [ ] Set up Vue I18n for 5 languages
- [ ] Install dependencies (Headless UI, Heroicons, FilePond, Swiper)

#### Directory Structure
```
frontend/src/
├── api/           # 8 API modules
├── components/
│   ├── atoms/     # 10 components
│   ├── molecules/ # 16 components
│   ├── organisms/ # 15 components
│   └── templates/ # 5 layouts
├── composables/   # 10 composables
├── stores/        # 5 stores
├── views/         # 20+ pages
├── router/
├── utils/
└── types/
```

#### API Layer (3h)
- [ ] Axios instance with interceptors
- [ ] Token refresh logic
- [ ] Error handling with Toast
- [ ] auth.ts - Authentication API
- [ ] tools.ts - 5 Tool APIs
- [ ] materials.ts - Material API
- [ ] credits.ts - Credits API
- [ ] upload.ts - Upload API (chunked)
- [ ] tasks.ts - Task status API
- [ ] admin.ts - Admin API

#### Pinia Stores (3h)
- [ ] auth.ts - User authentication state
  - Getters: isLoggedIn, isDemo, isPaid, canDownload, canCustomPrompt
  - Actions: login, register, verifyEmail, refreshTokens, logout
- [ ] credits.ts - Credits state
  - Getters: totalCredits, resetCountdown
  - Actions: fetchBalance, estimateCost, deductLocal
- [ ] generation.ts - Generation task state
  - Actions: startTask, connectWebSocket, cancelTask
- [ ] ui.ts - UI state (loading, modals, toast)
- [ ] admin.ts - Admin dashboard state

#### Composables (4h)
- [ ] useAuth.ts - Authentication logic
- [ ] useUpload.ts - Chunked upload (1MB chunks)
- [ ] useTask.ts - Task polling + WebSocket fallback
- [ ] useCredits.ts - Credit management
- [ ] useMaterials.ts - Material fetching with Demo mode
- [ ] useWebSocket.ts - WebSocket connection
- [ ] useToast.ts - Toast notifications
- [ ] useModal.ts - Modal control
- [ ] useI18n.ts - i18n wrapper
- [ ] useResponsive.ts - Responsive breakpoints

#### Atom Components (2h)
- [ ] BaseButton.vue (primary, secondary, ghost variants)
- [ ] BaseInput.vue
- [ ] BaseSelect.vue
- [ ] BaseSlider.vue (range input with tooltip)
- [ ] BaseToggle.vue
- [ ] BaseTooltip.vue
- [ ] BaseBadge.vue
- [ ] BaseSpinner.vue
- [ ] BaseIcon.vue
- [ ] GlassCard.vue (glassmorphism effect)

#### Molecule Components (4h)
- [ ] UploadZone.vue (FilePond wrapper, drag & drop)
- [ ] ImagePreview.vue
- [ ] VideoPlayer.vue
- [ ] BeforeAfterSlider.vue
- [ ] ProgressBar.vue (task progress)
- [ ] CreditBadge.vue (header credit display)
- [ ] PlanCard.vue (pricing page)
- [ ] MaterialCard.vue (inspiration gallery)
- [ ] TemplateCard.vue (scene/style selection)
- [ ] VoiceCard.vue (TTS voice selection)
- [ ] ModelCard.vue (try-on model selection)
- [ ] StyleCard.vue (room style selection)
- [ ] ToastNotification.vue
- [ ] ConfirmModal.vue
- [ ] UpgradePrompt.vue (Demo user upgrade CTA)
- [ ] PointsWarningModal.vue

#### Organism Components (3h)
- [ ] TheHeader.vue (fixed, transparent → blur on scroll)
- [ ] TheFooter.vue
- [ ] TheSidebar.vue (dashboard navigation)
- [ ] UserMenu.vue (avatar dropdown)
- [ ] LangSwitcher.vue
- [ ] ToolPanel.vue (tool settings panel)
- [ ] ResultGallery.vue (generated results grid)
- [ ] TemplateCarousel.vue (Swiper)
- [ ] ModelSelector.vue (filter + grid)
- [ ] VoiceSelector.vue
- [ ] ScriptEditor.vue (textarea + AI enhance)
- [ ] ParameterPanel.vue (sliders group)
- [ ] InspirationGrid.vue
- [ ] WorksHistory.vue
- [ ] AdminStatsCard.vue

#### Template Layouts (2h)
- [ ] MainLayout.vue (Header + Content + Footer)
- [ ] ToolLayout.vue (Left Canvas + Right Panel)
- [ ] DashboardLayout.vue (Sidebar + Content)
- [ ] AuthLayout.vue (Centered card)
- [ ] AdminLayout.vue (Admin sidebar + Content)

#### Landing Page (2h)
- [ ] Home.vue
  - Hero section (gradient + particles)
  - Feature cards (5 tools)
  - Before/After showcase
  - Testimonials
  - Pricing preview
  - CTA section

#### Auth Pages (2h)
- [ ] Login.vue
- [ ] Register.vue
- [ ] VerifyEmail.vue (6-digit code input)
- [ ] ForgotPassword.vue
- [ ] ResetPassword.vue

#### Dashboard Pages (2h)
- [ ] Dashboard.vue (feature entry + recent works)
- [ ] MyWorks.vue (history with filters)
- [ ] Profile.vue (settings)
- [ ] Subscription.vue (plan management)

#### 5 Tool Pages (6h)

##### BackgroundRemoval.vue
- [ ] UploadZone (batch up to 10)
- [ ] Background type selector (white/transparent/gray/custom)
- [ ] Auto-enhance toggle
- [ ] ResultGrid with BeforeAfterSlider
- [ ] Batch download button

##### ProductScene.vue
- [ ] Upload area
- [ ] TemplateCarousel (15 scenes)
- [ ] Parameter sliders (light, size, shadow)
- [ ] VariantGrid (4-8 variants)
- [ ] Regenerate button

##### TryOn.vue
- [ ] Two-column upload (garment + model)
- [ ] ModelSelector with filters
- [ ] Background options
- [ ] AngleTab (front/side/back)
- [ ] ExtendToVideo button

##### RoomRedesign.vue
- [ ] Upload zone
- [ ] StyleCardLarge grid (12 styles)
- [ ] Parameters (hardscape, furnishing, lighting)
- [ ] BeforeAfterCompare (full width)
- [ ] Variant thumbnails

##### ShortVideo.vue
- [ ] Source selector (My Works / Upload)
- [ ] ScriptEditor with AI optimize
- [ ] VoiceSelector (4 voices)
- [ ] VideoPreview player
- [ ] Download button

#### Additional Pages (2h)
- [ ] Pricing.vue (plan comparison table)
- [ ] Inspiration.vue (public gallery)
- [ ] NotFound.vue (404)

#### Router Configuration (1h)
- [ ] Route definitions (all pages)
- [ ] Route guards (auth, admin)
- [ ] Redirect logic

---

### Phase 5.2: Landing Page Implementation (12h) 🆕 NEW

> **Design Source**: Figma `VIDGO廣告生成AI平台.make`  
> **Style**: Dark Tech Theme (#1E1B4B background)

#### 共用組件 (2h)

##### Section Badge
```vue
<SectionBadge icon="✨" text="功能特色" />
```
- [ ] 帶圖標和綠色小圓點的膠囊標籤

##### Gradient Heading
```vue
<GradientHeading 
  prefix="強大功能，" 
  highlight="一應俱全" 
/>
```
- [ ] 支援漸層高亮文字

##### Stats Card
```vue
<StatsCard value="10K+" label="活躍用戶" color="purple" />
```
- [ ] 玻璃擬態卡片 + 漸層數字

#### Section 1: Hero (1.5h)
- [ ] Badge: "✨ AI 驅動的廣告生成平台 ●"
- [ ] H1 漸層文字: "AI 自動生成" / "高效能影片廣告"
- [ ] Subtitle + Highlight (橘色漸層)
- [ ] Primary CTA: "立即免費試用 ✨" (紫→粉漸層)
- [ ] Secondary CTA: "▶ 觀看示範" (outline)
- [ ] 3 Stats Cards (10K+ / 80% / 3x)
- [ ] 背景星空粒子動畫 (optional)

#### Section 2: Features (1.5h)
- [ ] Badge: "● 功能特色"
- [ ] H2: "強大功能，一應俱全"
- [ ] 6 Feature Cards (2×3 grid)
  - [ ] AI 智能生成 (Blue bar)
  - [ ] 快速製作 (Orange bar)
  - [ ] 精準投放 (Green bar)
  - [ ] 數據分析 (Pink bar)
  - [ ] 多語言支援 (Cyan bar)
  - [ ] 團隊協作 (Red bar)
- [ ] 每張卡片: Icon circle + gradient bar + title + description

#### Section 3: How It Works (1.5h)
- [ ] Badge: "✨ 如何運作"
- [ ] H2: "四步驟輕鬆完成"
- [ ] Vertical Timeline with 4 steps:
  - [ ] Step 01: 上傳素材 (Cyan circle)
  - [ ] Step 02: AI 生成 (Purple circle)
  - [ ] Step 03: 客製化調整 (Purple-Pink circle)
  - [ ] Step 04: 匯出投放 (Pink circle)
- [ ] 連接線 (漸層)
- [ ] CTA: "開始免費試用 →" (漸層按鈕)

#### Section 4: Examples Gallery (2h) ⭐ 重要
- [ ] Badge: "作品展示"
- [ ] H2: "AI 生成的精彩範例"
- [ ] Subtitle: "查看各種類型的影片廣告範例，體驗 AI 的創作能力"
- [ ] Filter Tabs (7 個):
  - [ ] 全部 (active state: blue bg)
  - [ ] 電商
  - [ ] 社群
  - [ ] 品牌
  - [ ] 應用程式
  - [ ] 促銷
  - [ ] 服務
- [ ] 6 Example Cards (2×3 grid):
  - [ ] 縮圖 (16:9 aspect ratio)
  - [ ] Category badge (左上): "✨ 電商"
  - [ ] Duration badge (右上): "15 秒"
  - [ ] Hover: Play overlay
  - [ ] Title + Description
- [ ] CTA: "查看更多範例" (outline button)
- [ ] Category filter logic (動態過濾)

#### Section 5: Comparison (1h)
- [ ] Badge: "前後對比"
- [ ] H2: "傳統 vs AI 智能製作"
- [ ] Two comparison cards:
  - [ ] 傳統方式 (❌ icons, 灰底)
  - [ ] VIDGO AI (✅ icons, 推薦 badge)
- [ ] Bottom stats: 95% / 90% / 3x

#### Section 6: Testimonials (1.5h)
- [ ] Badge: "客戶見證"
- [ ] H2: "超過 10,000+ 企業的信賴選擇"
- [ ] 6 Testimonial Cards (2×3 grid):
  - [ ] Quote icon (金色引號)
  - [ ] 5 star rating
  - [ ] Quote text
  - [ ] Avatar + Name + Title + Company
- [ ] Bottom stats: 4.9/5 | 10K+ | 500K+ | 98%

#### Section 7: Pricing (1.5h)
- [ ] Badge: "⭐ 定價方案"
- [ ] H2: "選擇適合您的完美方案"
- [ ] 3 Pricing Cards:
  - [ ] 入門版 NT$49/月
  - [ ] 專業版 NT$149/月 (最受歡迎, 漸層邊框)
  - [ ] 企業版 NT$499/月
- [ ] Feature checkmarks (teal)
- [ ] CTA buttons (gradient for featured)

#### Section 8: FAQ (1h)
- [ ] Badge: "⊙ 常見問題"
- [ ] H2: "常見問題解答" (部分漸層)
- [ ] 10 Accordion items:
  - [ ] VIDGO 是如何運作的？
  - [ ] 我需要具備影片製作經驗嗎？
  - [ ] 生成一個影片需要多長時間？
  - [ ] 我可以自訂影片的風格和內容嗎？
  - [ ] 支援哪些影片格式和尺寸？
  - [ ] 免費試用包含哪些功能？
  - [ ] 如何收費？可以隨時取消嗎？
  - [ ] 我的數據和影片內容安全嗎？
  - [ ] 支援團隊協作功能嗎？
  - [ ] 如果遇到問題，可以獲得什麼支援？
- [ ] Support CTA: "還有其他問題？" [聯繫客服團隊]

#### Section 9: Final CTA (0.5h)
- [ ] Icon (✨ in gradient circle)
- [ ] H2: "準備好開始了嗎？"
- [ ] Trust badges: 無需信用卡 | 14天免費試用 | 隨時取消
- [ ] CTAs: [立即免費試用 →] [聯繫銷售團隊]
- [ ] Social proof: "🚀 超過 500+ 企業選擇 VIDGO"
- [ ] Client logos placeholder (5 個)

#### Footer (0.5h)
- [ ] Logo + Description + Social icons
- [ ] 4 Column links:
  - [ ] 產品: 功能特色, 定價方案, API 文檔, 更新日誌
  - [ ] 公司: 關於我們, 部落格, 職涯機會, 聯絡我們
  - [ ] 資源: 說明中心, 教學影片, 範例模板, 社群論壇
  - [ ] 法律: 隱私政策, 服務條款, Cookie 政策, 版權聲明
- [ ] Copyright line

---

### Phase 6: Payment Integration (20h) ⏳ PENDING

- [ ] ECPay credit card
- [ ] ECPay ATM/convenience store
- [ ] ECPay LINE Pay
- [ ] Paddle international
- [ ] Webhook handlers
- [ ] Receipt generation
- [ ] Subscription management

---

### Phase 7: i18n (6h) ✅ COMPLETE

- [x] English (en)
- [x] Japanese (ja)
- [x] Traditional Chinese (zh-TW)
- [x] Korean (ko)
- [x] Spanish (es)

---

### Phase 8: Admin Dashboard (14h) 🔄 UPDATED

#### Backend Service (4h)
- [ ] AdminDashboardService class
- [ ] get_online_stats() - Redis ZCARD
- [ ] get_online_by_tier() - Redis Hash
- [ ] get_today_stats() - DB aggregation
- [ ] get_week_stats()
- [ ] get_month_revenue()
- [ ] get_system_health()
- [ ] get_generation_trend(days)
- [ ] get_revenue_trend(months)
- [ ] get_user_growth_trend(days)

#### Session Tracker (2h)
- [ ] SessionTracker class
- [ ] heartbeat(user_id, plan) - Update Redis
- [ ] cleanup_expired() - Remove stale sessions
- [ ] Redis structures:
  - `online_users` (Sorted Set)
  - `user_plans` (Hash)
  - `online_users_by_tier` (Hash)
  - `active_users_today` (HyperLogLog)

#### Backend API Endpoints (4h)
- [ ] GET `/api/v1/admin/stats/online`
- [ ] GET `/api/v1/admin/stats/users-by-tier`
- [ ] GET `/api/v1/admin/stats/dashboard`
- [ ] GET `/api/v1/admin/charts/generations`
- [ ] GET `/api/v1/admin/charts/revenue`
- [ ] GET `/api/v1/admin/charts/users-growth`
- [ ] GET `/api/v1/admin/users` (paginated, searchable)
- [ ] GET `/api/v1/admin/users/{id}`
- [ ] POST `/api/v1/admin/users/{id}/ban`
- [ ] POST `/api/v1/admin/users/{id}/credits`
- [ ] GET `/api/v1/admin/materials` (paginated, filterable)
- [ ] POST `/api/v1/admin/materials/{id}/review`
- [ ] GET `/api/v1/admin/moderation/queue`
- [ ] GET/POST/DELETE `/api/v1/admin/moderation/block-cache`
- [ ] GET `/api/v1/admin/health`
- [ ] GET `/api/v1/admin/logs/credit-resets`
- [ ] WS `/api/v1/admin/ws/realtime` (5s interval)
- [ ] POST `/api/v1/session/heartbeat`

#### Frontend Admin Pages (4h)
- [ ] AdminDashboard.vue
  - Online users card (real-time)
  - Today stats cards
  - Generation trend chart
  - Revenue trend chart
  - System health indicators
- [ ] AdminUsers.vue
  - User table with search
  - User detail modal
  - Ban/Unban buttons
  - Credit adjustment form
- [ ] AdminMaterials.vue
  - Material grid with filters
  - Review modal (approve/reject/feature)
  - Bulk actions
- [ ] AdminModeration.vue
  - Pending queue list
  - Quick review actions
  - Block cache management
- [ ] AdminRevenue.vue
  - Revenue charts
  - Subscription breakdown
  - Top-up statistics
- [ ] AdminSystem.vue
  - Service health status
  - API latency
  - Worker status
  - Recent credit reset logs

---

### Phase 9: Security + Deploy (12h) ⏳ PENDING

- [ ] Rate limiting (100 req/min/IP)
- [ ] CORS whitelist
- [ ] Input validation (enhanced)
- [ ] SQL injection prevention
- [ ] XSS protection (CSP headers)
- [ ] Production Docker setup
- [ ] Nginx configuration
- [ ] SSL/TLS setup
- [ ] Monitoring (Sentry)
- [ ] Backup automation

---

### Phase 10: Email Verification System (6h) ⏳ PENDING

- [ ] 6-digit code generation
- [ ] Redis storage (15-min TTL)
- [ ] Max 3 verification attempts
- [ ] Max 5 resend requests/hour
- [ ] Email templates (multi-language)
- [ ] SMTP integration

---

### Phase 11: Weekly Credit System (4h) ⏳ PENDING

- [ ] Add `weekly_credits` to Plan model
- [ ] Add `credits_reset_at` to User model
- [ ] Celery Beat configuration
- [ ] Weekly reset task (Monday 00:00 UTC)
- [ ] Credit transaction logging
- [ ] Email notification (optional)

---

## API Summary

| Category | Count |
|----------|-------|
| Auth | 8 |
| User | 5 |
| Tools (5 tools) | 15 |
| Upload | 4 |
| Tasks | 3 |
| Materials/Demo | 3 |
| Credits | 5 |
| Templates/Voices | 4 |
| Payments | 5 |
| Admin | 18 |
| Session | 1 |
| **Total** | **71** |

---

## Project Structure (Final)

```
vidgo/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── auth.py
│   │   │       ├── users.py
│   │   │       ├── tools.py
│   │   │       ├── materials.py
│   │   │       ├── demo.py
│   │   │       ├── credits.py
│   │   │       ├── upload.py
│   │   │       ├── tasks.py
│   │   │       ├── templates.py
│   │   │       ├── voices.py
│   │   │       ├── payments.py
│   │   │       ├── admin.py
│   │   │       └── session.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── security.py
│   │   │   └── redis.py
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── material.py
│   │   │   ├── billing.py
│   │   │   └── generation.py
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── leonardo.py
│   │   │   ├── goenhance.py
│   │   │   ├── pollo_ai.py
│   │   │   ├── aten_tts.py
│   │   │   ├── gemini_service.py
│   │   │   ├── material_generator.py
│   │   │   ├── material_collector.py
│   │   │   ├── watermark.py
│   │   │   ├── session_tracker.py
│   │   │   ├── admin_dashboard.py
│   │   │   └── credit_service.py
│   │   └── tasks/
│   │       ├── celery_app.py
│   │       ├── generation.py
│   │       ├── credit_reset.py
│   │       └── cleanup.py
│   ├── scripts/
│   │   └── seed_materials.py
│   ├── alembic/
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   │   ├── atoms/
│   │   │   ├── molecules/
│   │   │   ├── organisms/
│   │   │   └── templates/
│   │   ├── composables/
│   │   ├── stores/
│   │   ├── views/
│   │   │   ├── auth/
│   │   │   ├── dashboard/
│   │   │   ├── tools/
│   │   │   └── admin/
│   │   ├── router/
│   │   ├── utils/
│   │   └── types/
│   ├── public/
│   │   └── locales/
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── package.json
│
├── docker-compose.yml
├── nginx.conf
├── ARCHITECTURE_FINAL.md
├── DEVELOPMENT_PLAN_FINAL.md
└── README.md
```

---

## Hours Summary

| Phase | Hours | Status |
|-------|-------|--------|
| Phase 1: Core Infrastructure | 4 | ✅ |
| Phase 2: Smart Demo + Gemini | 15 | ✅ |
| Phase 2.5: Material System | 12 | 🆕 |
| Phase 3: Leonardo AI | 18 | ✅ |
| Phase 4: GoEnhance | 12 | ✅ |
| Phase 5: Streamlit (Legacy) | 10 | ✅ |
| Phase 5.1: Vue 3 Frontend | 35 | 🔄 |
| Phase 6: Payment | 20 | ⏳ |
| Phase 7: i18n | 6 | ✅ |
| Phase 8: Admin Dashboard | 14 | 🔄 |
| Phase 9: Security + Deploy | 12 | ⏳ |
| Phase 10: Email Verification | 6 | ⏳ |
| Phase 11: Weekly Credits | 4 | ⏳ |
| **Total** | **175h** | |

---

## Risk & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| API rate limits | High | Use Relaxed Mode, implement retry logic |
| High seed cost | Medium | Batch processing, monitor costs |
| Demo abuse | Medium | Rate limit, watermark, block cache |
| WebSocket scaling | Low | Fallback to polling |
| CDN costs | Low | Aggressive caching, compression |

---

## Launch Checklist

- [ ] All 5 tools functional
- [ ] 960 materials seeded
- [ ] Demo restrictions working
- [ ] Payment flow tested
- [ ] Admin dashboard functional
- [ ] i18n complete
- [ ] Mobile responsive
- [ ] Performance optimized
- [ ] Security audit passed
- [ ] Monitoring configured
- [ ] Backup tested
- [ ] DNS configured
- [ ] SSL certificate active

---

*Document Version: 2.0*  
*Last Updated: 2025/01/01*
