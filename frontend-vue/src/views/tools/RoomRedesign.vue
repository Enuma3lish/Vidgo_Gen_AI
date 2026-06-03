<script setup lang="ts">
/**
 * RoomRedesign — ReRoom.ai-style refactor (2026-05-24).
 *
 * Owner directive: "interior design please reference https://tw.reroom.ai/
 * and please deep dive it." Layout strategy mirrors ReRoom's "inspire first,
 * generator second" approach:
 *
 *   ┌──── Hero with before/after slider ──────────────────────┐
 *   │ "室內渲染，你所想像的任何風格"                            │
 *   │ [免費試用]  [查看方案]                                   │
 *   ├─────────────────────────────────────────────────────────┤
 *   │  Generator (single clean form, login-gated)             │
 *   │  ┌──── Upload ────┬──── Result preview ───┐             │
 *   │  │ drag a photo   │ before/after slider   │             │
 *   │  │ mode: redesign │                       │             │
 *   │  │      / stage   │                       │             │
 *   │  │      / magic   │                       │             │
 *   │  │ style: pick    │                       │             │
 *   │  │ [Generate]     │                       │             │
 *   │  └────────────────┴───────────────────────┘             │
 *   ├─────────────────────────────────────────────────────────┤
 *   │ Latest renders portfolio grid (40+ examples from        │
 *   │ Templates Gallery — clicking pre-fills the form above)  │
 *   ├─────────────────────────────────────────────────────────┤
 *   │ How it works (4-step explainer)                         │
 *   │ FAQ                                                     │
 *   └─────────────────────────────────────────────────────────┘
 *
 * Hidden behind a small "more modes" dropdown: the old generate / 3D /
 * styleTransfer / transform tabs. Default flow is the simple redesign +
 * stage + magic — matching ReRoom's minimal-form expectation.
 *
 * Colors preserved per owner directive: #0a0a0f bg, #141420 panels,
 * #7c3aed→#a78bfa violet accents, #f5f5fa/#94949f text. Only the SHAPE
 * changes — palette stays.
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized } from '@/composables'
import { demoApi, toolsApi } from '@/api'
import BeforeAfterSlider from '@/components/tools/BeforeAfterSlider.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
import ExampleGallery from '@/components/tools/ExampleGallery.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import apiClient from '@/api/client'
import { extractApiError } from '@/utils/apiError'
import { handleCardRequired } from '@/utils/toolGate'

const { t, locale } = useI18n()
const router = useRouter()
const route = useRoute()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { isDemoUser } = useDemoMode()
const { L } = useLocalized()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

// ─── State ────────────────────────────────────────────────────────────
type Mode = 'redesign' | 'stage' | 'magic'
type SpaceKind = 'interior' | 'exterior' | 'commercial'

const mode = ref<Mode>('redesign')
const spaceKind = ref<SpaceKind>('interior')
const uploadedImage = ref<string | undefined>(undefined)
const uploadedFile = ref<File | null>(null)
const selectedStyle = ref<string>('')
const customPrompt = ref<string>('')          // magic-mode prompt
const styleStrength = ref<number>(0.7)
const lightingTone = ref<'' | 'daylight' | 'warm_evening' | 'dramatic_spotlight' | 'golden_hour' | 'moody'>('')
const materialAccent = ref<'' | 'wood' | 'marble' | 'concrete' | 'linen' | 'brass' | 'leather' | 'terrazzo'>('')

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultImage = ref<string | null>(null)

// ─── Style catalog (loaded from backend) ─────────────────────────────
interface StyleCard { id: string; name: string; name_zh: string; preview_url?: string; prompt?: string }
const styles = ref<Record<SpaceKind, StyleCard[]>>({ interior: [], commercial: [], exterior: [] })

async function loadStyles(kind: SpaceKind) {
  if (styles.value[kind].length > 0) return
  try {
    const resp = await apiClient.get(`/api/v1/tools/templates/interior-styles?space_kind=${kind}`)
    styles.value[kind] = (resp.data || []) as StyleCard[]
  } catch (e) {
    console.warn(`[room-redesign] failed to load ${kind} styles:`, e)
  }
}

// Disable Generate when required inputs are missing.
const disabled = computed(() => {
  if (!uploadedFile.value) return true
  if (mode.value === 'magic') return !customPrompt.value.trim()
  return !selectedStyle.value
})
const creditCost = computed(() => 20)
const isRunning = computed(() => status.value === 'running')

// ─── Generate (3 paths: redesign | stage | magic) ────────────────────
async function generate() {
  if (disabled.value || isRunning.value) return
  // Backend governs access: a free account gets the cached example for a
  // style-only (preset) redesign; a custom prompt or Magic mode returns
  // 'subscription_card_required', handled below.

  status.value = 'running'
  statusText.value = L('生成中… 通常需要 30 秒至 2 分鐘', 'Generating… typically 30s to 2 minutes', '生成中… 通常30秒〜2分かかります', '생성 중… 보통 30초~2분 소요', 'Generando… normalmente de 30 s a 2 min')
  resultImage.value = null

  try {
    // All three modes route through the subscriber endpoint
    // /tools/room-redesign so they share the provider_router fallback
    // chain (PiAPI Kontext primary → Vertex backup) and respect the
    // full RoomRedesignRequest contract (styleStrength, space_kind,
    // lighting/material chips, variation_count). Previously redesign +
    // stage went to /interior/demo/redesign which uses Gemini-only with
    // no fallback — that path produced inconsistent results (sometimes
    // unchanged input, sometimes text-only) and silently dropped the
    // styleStrength slider, the exterior/commercial style catalogs,
    // and the variation_count knob.
    const uploaded = await demoApi.uploadImage(uploadedFile.value!)
    const result = await toolsApi.roomRedesign(
      uploaded.url,
      mode.value === 'magic' ? '' : selectedStyle.value,
      customPrompt.value.trim(),
      undefined,
      undefined,
      {
        mode: mode.value,
        spaceKind: spaceKind.value,
        styleStrength: styleStrength.value,
        lightingTone: lightingTone.value || undefined,
        materialAccent: materialAccent.value || undefined,
      },
    )
    if (handleCardRequired(result, uiStore, router, isZh.value)) {
      status.value = 'idle'
      statusText.value = ''
      return
    }
    if (result.success && (result.image_url || result.result_url)) {
      const u = result.image_url || result.result_url || ''
      resultImage.value = u.startsWith('http') ? u : `${window.location.origin}${u}`
      status.value = 'done'
      statusText.value = L('完成', 'Done', '完了', '완료', 'Listo')
      if (result.credits_used) creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success') || 'Success')
    } else {
      status.value = 'error'
      statusText.value = L('生成失敗', 'Failed', '生成失敗', '생성 실패', 'Generación fallida')
      uiStore.showError((result as any).message || (result as any).error || 'Generation failed.')
    }
  } catch (e: any) {
    status.value = 'error'
    statusText.value = L('錯誤', 'Error', 'エラー', '오류', 'Error')
    uiStore.showError(extractApiError(e, L('生成失敗', 'Generation failed', '生成失敗', '생성 실패', 'Generación fallida')))
  }
}

function handleRoomFileSelected(file: File | null) {
  uploadedFile.value = file
}

// Pre-fill from query params (Templates Gallery deeplink). This page is now
// interior-only — exterior and commercial each have their own dedicated page
// (/tools/exterior-ai, /tools/commercial-space), so forward any old deeplink
// or bookmark that still carries space_kind=exterior|commercial to the right
// tool instead of silently ignoring it.
async function applyDeeplink() {
  const qStyle = String(route.query.style || '').trim()
  const qSpaceKind = String(route.query.space_kind || '').trim()
  if (qSpaceKind === 'exterior') {
    router.replace({ path: '/tools/exterior-ai', query: qStyle ? { style: qStyle } : {} })
    return
  }
  if (qSpaceKind === 'commercial') {
    router.replace({ path: '/tools/commercial-space', query: qStyle ? { style: qStyle } : {} })
    return
  }
  if (qStyle) selectedStyle.value = qStyle
}

// Portfolio grid — interior styles only (exterior/commercial moved to their
// own pages).
const portfolioGrid = computed<StyleCard[]>(() => styles.value.interior)

function pickFromPortfolio(card: StyleCard) {
  selectedStyle.value = card.id
  mode.value = 'redesign'
  // scroll to upload form
  window.scrollTo({ top: 600, behavior: 'smooth' })
}

onMounted(async () => {
  await loadStyles('interior')
  await applyDeeplink()
})

function gotoPricing() { router.push('/pricing') }
function gotoTemplates() { router.push('/tools/interior-templates') }
function scrollToGenerator() {
  // Plain DOM access — Vue template can't reference `document` directly
  // under vue-tsc strict mode, so we proxy through a script-side helper.
  const el = (globalThis as any).document?.querySelector?.('#generator')
  if (el) el.scrollIntoView({ behavior: 'smooth' })
}

// Demo before/after sample for the hero. Pulled from /demo/presets so the
// hero always shows a real, existing example — the previous hard-coded
// `vidgo-media-vidgo-ai/demo/interior_before.jpg` pair was 403ing (the
// `demo/` folder was never populated in prod), which collapsed the slider
// into stacked broken-image icons (audit 2026-05-26).
const heroBefore = ref<string>('')
const heroAfter  = ref<string>('')

onMounted(async () => {
  try {
    const { data } = await apiClient.get('/api/v1/demo/presets/room_redesign', { params: { limit: 1 } })
    const first = (data?.presets || [])[0]
    if (first) {
      heroBefore.value = first.input_image_url || ''
      heroAfter.value  = first.result_watermarked_url || first.result_image_url || ''
    }
  } catch {
    // Leave slider hidden if the lookup fails — better than broken images.
  }
})
</script>

<template>
  <div class="min-h-screen" style="background: #0a0a0f;">
    <!-- Unified full-screen loading overlay (same as every other tool). -->
    <LoadingOverlay :show="isRunning" :eta-seconds="60" :title="statusText || undefined" />
    <!-- ═══ HERO with before/after slider ═══════════════════════════════ -->
    <!-- pt-24 clears the 64px fixed AppHeader (was pt-12 → title clipped). -->
    <section class="px-4 sm:px-6 lg:px-8 pt-24 pb-10 max-w-7xl mx-auto">
      <div class="grid grid-cols-1 lg:grid-cols-[1fr_1.2fr] gap-8 items-center">
        <div>
          <p class="text-xs font-mono tracking-[0.3em] uppercase mb-3" style="color: #a78bfa;">
            {{ L('AI 室內渲染', 'AI INTERIOR RENDERING', 'AIインテリアレンダリング', 'AI 인테리어 렌더링', 'RENDERIZADO IA') }}
          </p>
          <h1 class="text-4xl sm:text-5xl font-bold leading-tight mb-4" style="color: #f5f5fa;">
            {{ L('室內渲染，你所想像的任何風格', 'Interior rendering, in any style you imagine', 'インテリアレンダリング、思い描くどんなスタイルでも', '인테리어 렌더링, 상상하는 모든 스타일', 'Renderizado interior, en cualquier estilo que imagines') }}
          </h1>
          <p class="text-base mb-6" style="color: #94949f;">
            {{ L('以驚豔的建築與室內渲染打動客戶。將靈感化為作品，讓每個概念發光。', 'Impress clients with stunning architectural renders. Transform inspiration into work — make every concept shine.', '驚きの建築インテリアレンダリングで顧客を魅了。インスピレーションを作品に。', '놀라운 건축 인테리어 렌더링으로 고객을 사로잡으세요. 영감을 작품으로.', 'Impresiona a tus clientes con renderizados impactantes.') }}
          </p>
          <div class="flex flex-wrap gap-3">
            <button
              @click="scrollToGenerator"
              class="px-6 py-3 rounded-xl font-semibold text-sm"
              style="background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color: #fff;"
            >
              {{ L('免費試用', 'Try for free', '無料で試す', '무료 체험', 'Prueba gratis') }}
            </button>
            <button
              @click="gotoTemplates"
              class="px-6 py-3 rounded-xl font-semibold text-sm"
              style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
            >
              {{ L('瀏覽範本', 'Browse Templates', 'テンプレートを見る', '템플릿 보기', 'Ver plantillas') }}
            </button>
            <button
              @click="gotoPricing"
              class="px-6 py-3 rounded-xl font-semibold text-sm"
              style="background: transparent; color: #94949f; border: 1px solid rgba(255,255,255,0.08);"
            >
              {{ L('查看方案', 'View Plans', 'プランを見る', '플랜 보기', 'Ver planes') }}
            </button>
          </div>
        </div>

        <!-- Before/After slider (proof of quality). Only render once we've
             fetched a real preset — empty URLs render two broken-image icons
             stacked on top of each other (audit 2026-05-26). -->
        <div
          v-if="heroBefore && heroAfter"
          class="rounded-2xl overflow-hidden"
          style="background: #141420; border: 1px solid rgba(255,255,255,0.06);"
        >
          <BeforeAfterSlider
            :before-image="heroBefore"
            :after-image="heroAfter"
            :before-label="L('原始', 'Before', 'オリジナル', '원본', 'Antes')"
            :after-label="L('AI 渲染', 'After AI', 'AI後', 'AI 후', 'Después')"
          />
        </div>
        <div
          v-else
          class="rounded-2xl flex items-center justify-center text-xs"
          style="background: #141420; border: 1px solid rgba(255,255,255,0.06); min-height: 280px; color: #94949f;"
        >
          {{ L('載入範例中…', 'Loading example…', 'サンプルを読み込み中…', '예시 로딩 중…', 'Cargando ejemplo…') }}
        </div>
      </div>
    </section>

    <!-- ═══ GENERATOR (single clean form) ═══════════════════════════════ -->
    <section id="generator" class="px-4 sm:px-6 lg:px-8 pb-12 max-w-7xl mx-auto">
      <div class="grid grid-cols-1 lg:grid-cols-[420px_1fr] gap-6">
        <!-- Left: Inputs -->
        <aside class="rounded-2xl p-5 space-y-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <!-- Cross-link to the sibling interior/exterior tools so users can
               jump to the right dedicated page (this page is interior-only). -->
          <div class="flex flex-wrap gap-1.5">
            <RouterLink to="/tools/exterior-ai" class="text-[11px] px-2.5 py-1 rounded-full" style="background:#0a0a0f; color:#94949f; border:1px solid rgba(255,255,255,0.08);">
              🏛️ {{ L('建築外觀', 'Exterior', '外観', '외관', 'Exterior') }}
            </RouterLink>
            <RouterLink to="/tools/commercial-space" class="text-[11px] px-2.5 py-1 rounded-full" style="background:#0a0a0f; color:#94949f; border:1px solid rgba(255,255,255,0.08);">
              🏪 {{ L('商業空間', 'Commercial', '商業空間', '상업 공간', 'Comercial') }}
            </RouterLink>
            <RouterLink to="/tools/sketch-to-render" class="text-[11px] px-2.5 py-1 rounded-full" style="background:#0a0a0f; color:#94949f; border:1px solid rgba(255,255,255,0.08);">
              ✏️ {{ L('草圖轉渲染', 'Sketch', 'スケッチ', '스케치', 'Boceto') }}
            </RouterLink>
          </div>

          <!-- Mode tabs -->
          <div>
            <p class="text-[11px] font-mono tracking-wider uppercase mb-2" style="color: #94949f;">
              {{ L('模式', 'Mode', 'モード', '모드', 'Modo') }}
            </p>
            <div class="grid grid-cols-3 gap-1.5">
              <button
                v-for="opt in [
                  { id: 'redesign' as const, label: L('改造', 'Redesign', 'リデザイン', '리디자인', 'Rediseño') },
                  { id: 'stage' as const,    label: L('佈置', 'Stage', 'ステージング', '스테이징', 'Staging') },
                  { id: 'magic' as const,    label: L('魔法', 'Magic', 'マジック', '매직', 'Mágico') },
                ]"
                :key="opt.id"
                type="button"
                @click="mode = opt.id"
                class="py-2 rounded-lg text-xs font-medium transition-colors"
                :style="mode === opt.id
                  ? 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color: #fff;'
                  : 'background: #0a0a0f; color: #94949f; border: 1px solid rgba(255,255,255,0.08);'"
              >{{ opt.label }}</button>
            </div>
            <p class="text-[11px] mt-1.5" style="color: #6b6b7a;">
              {{ mode === 'redesign'
                ? L('改造現有空間，保留結構', 'Restyle existing space, preserve structure', '既存空間を改造、構造維持', '기존 공간 개조, 구조 유지', 'Rediseña conservando la estructura')
                : mode === 'stage'
                ? L('空房間 → AI 自動佈置家具', 'Empty room → AI furnishes it', '空室 → AIが家具配置', '빈 방 → AI 가구 배치', 'Habitación vacía → AI amuebla')
                : L('用一段話描述你想要的房間', 'Describe the room you want in plain text', '欲しい部屋を一文で記述', '원하는 방을 한 문단으로 설명', 'Describe la habitación en texto') }}
            </p>
          </div>

          <!-- Upload -->
          <div>
            <p class="text-[11px] font-mono tracking-wider uppercase mb-2" style="color: #94949f;">
              {{ L('上傳房間照片', 'Upload Room Photo', '部屋の写真をアップロード', '방 사진 업로드', 'Sube foto de la habitación') }}
            </p>
            <ImageUploader
              tool-type="room_redesign"
              v-model="uploadedImage"
              :label="L('點擊或拖放照片', 'Click or drag a photo', 'クリックまたはドロップ', '클릭 또는 드롭', 'Haz clic o arrastra')"
              @file-selected="handleRoomFileSelected"
            />
          </div>

          <!-- Style picker (hidden in magic mode) -->
          <div v-if="mode !== 'magic'">
            <p class="text-[11px] font-mono tracking-wider uppercase mb-2" style="color: #94949f;">
              {{ L('設計風格', 'Design Style', 'デザインスタイル', '디자인 스타일', 'Estilo') }}
              <span class="ml-2" style="color: #6b6b7a;">({{ styles[spaceKind].length }})</span>
            </p>
            <select
              v-model="selectedStyle"
              class="w-full rounded-lg px-3 py-2.5 text-sm"
              style="background: #0a0a0f; color: #f5f5fa; border: 1px solid rgba(255,255,255,0.08);"
            >
              <option value="">{{ L('— 請選擇 —', '— Select —', '— 選択 —', '— 선택 —', '— Seleccionar —') }}</option>
              <option v-for="s in styles[spaceKind]" :key="s.id" :value="s.id">
                <!-- Backend StyleCard only ships name + name_zh; ja/ko/es fall through to English (BUG-017, backend out of scope). -->
                {{ isZh ? s.name_zh : s.name }}
              </option>
            </select>
          </div>

          <!-- Magic prompt textarea -->
          <div v-if="mode === 'magic'">
            <p class="text-[11px] font-mono tracking-wider uppercase mb-2" style="color: #94949f;">
              {{ L('描述你想要的房間', 'Describe the room you want', '欲しい部屋を記述', '원하는 방을 설명', 'Describe la habitación') }}
            </p>
            <textarea
              v-model="customPrompt"
              rows="5"
              maxlength="2000"
              :placeholder="L('例：把這間客廳改成北歐風，淺色木地板，灰色亞麻沙發，黃銅落地燈，下午自然光。', 'e.g. Redesign this living room in Scandinavian style — pale oak floors, grey linen sofa, brass floor lamp, soft afternoon daylight.', '例：このリビングを北欧スタイルに、淡いオーク床、グレーリネンソファ、ブラスフロアランプ、午後の自然光。', '예: 이 거실을 북유럽 스타일로, 옅은 오크 바닥, 회색 리넨 소파, 황동 플로어 램프, 부드러운 오후 햇살.', 'Ej: Rediseña esta sala en estilo escandinavo.')"
              class="w-full rounded-lg p-3 text-sm"
              style="background: #0a0a0f; color: #f5f5fa; border: 1px solid rgba(255,255,255,0.08);"
            ></textarea>
            <p class="text-[11px] mt-1" style="color: #6b6b7a;">
              {{ L('魔法模式：你的描述會原封不動傳給 AI，風格選項與材質燈光按鈕都不會生效。', 'Magic mode: your description goes to the AI verbatim. Style picker, lighting, and material chips are ignored.', 'マジックモード：説明はそのままAIに渡されます。', '매직 모드: 설명이 그대로 AI에 전달됩니다.', 'Modo mágico: tu descripción va literal a la IA.') }}
            </p>
          </div>

          <!-- Strength slider (redesign / stage only) -->
          <div v-if="mode !== 'magic'">
            <p class="text-[11px] font-mono tracking-wider uppercase mb-2" style="color: #94949f;">
              {{ L('風格強度', 'Style Strength', 'スタイル強度', '스타일 강도', 'Fuerza del estilo') }}
              <span class="ml-2" style="color: #a78bfa;">{{ Math.round(styleStrength * 100) }}%</span>
            </p>
            <input
              type="range"
              min="0.3"
              max="1"
              step="0.05"
              v-model.number="styleStrength"
              class="w-full"
              style="accent-color: #a78bfa;"
            />
            <div class="flex justify-between text-[10px] mt-0.5" style="color: #6b6b7a;">
              <span>{{ L('保留原貌', 'Preserve', '保持', '보존', 'Conservar') }}</span>
              <span>{{ L('完全重塑', 'Reinvent', '完全再構築', '완전 재구성', 'Reinventar') }}</span>
            </div>
          </div>

          <!-- Cost badge — extracted from the button (was "Generate (X cr)")
               2026-05-25 to match the PiapiPlayground pattern. Keeps the
               button copy a clean action verb while still surfacing the
               per-run cost prominently. -->
          <div
            v-if="creditCost !== undefined"
            class="flex items-center justify-between rounded-xl px-3 py-2"
            style="background: rgba(124,58,237,0.10); border: 1px solid rgba(124,58,237,0.25);"
          >
            <span class="text-xs font-medium" style="color: #c4b5fd;">
              {{ L('單次消耗', 'Cost per run', '1回コスト', '1회 비용', 'Coste por uso') }}
            </span>
            <span class="text-sm font-bold tabular-nums" style="color: #fff;">
              {{ creditCost }}
              <span class="text-xs opacity-70 font-normal ml-0.5">{{ L('點', 'credits', 'クレジット', '크레딧', 'créditos') }}</span>
            </span>
          </div>

          <!-- Generate -->
          <button
            @click="generate"
            :disabled="disabled || isRunning"
            class="w-full py-3 rounded-xl font-semibold text-sm transition-all"
            :style="(disabled || isRunning)
              ? 'background: rgba(124,58,237,0.4); color: rgba(255,255,255,0.6); cursor: not-allowed;'
              : 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color: #fff; box-shadow: 0 6px 20px rgba(124,58,237,0.35);'"
          >
            <span v-if="isRunning" class="inline-flex items-center gap-2 justify-center">
              <svg class="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              {{ L('生成中…', 'Generating…', '生成中…', '생성 중…', 'Generando…') }}
            </span>
            <span v-else>{{ L('開始生成', 'Generate', '生成', '생성', 'Generar') }}</span>
          </button>

          <p v-if="isDemoUser" class="text-[11px]" style="color: #fbbf24;">
            {{ L('免費帳號可用預設風格生成範例；自訂提示詞或 Magic 模式需訂閱並綁定信用卡。', 'Free accounts can render the preset styles as examples; custom prompts or Magic mode require a subscription with a bound card.', '無料アカウントはプリセットの例を生成できます。カスタムは要サブスク＋カード登録。', '무료 계정은 프리셋 예시를 생성할 수 있습니다. 맞춤 프롬프트는 구독+카드 등록 필요.', 'Las cuentas gratuitas pueden generar los ejemplos preestablecidos; los prompts personalizados requieren suscripción con tarjeta.') }}
            <button @click="gotoPricing" class="underline ml-1">{{ L('查看方案', 'View Plans', 'プランを見る', '플랜 보기', 'Ver planes') }} →</button>
          </p>
        </aside>

        <!-- Right: Result preview -->
        <main class="rounded-2xl p-5 flex flex-col" style="background: #0f0f17; border: 1px solid rgba(255,255,255,0.06); min-height: 480px;">
          <div class="flex items-center justify-between mb-4">
            <span
              class="px-3 py-1 rounded-full text-xs font-medium border"
              :style="status === 'running' ? 'background: rgba(168,85,247,0.15); color: #c4b5fd; border-color: rgba(168,85,247,0.3);'
                : status === 'done' ? 'background: rgba(16,185,129,0.15); color: #6ee7b7; border-color: rgba(16,185,129,0.3);'
                : status === 'error' ? 'background: rgba(239,68,68,0.15); color: #fca5a5; border-color: rgba(239,68,68,0.3);'
                : 'background: rgba(255,255,255,0.06); color: #94949f; border-color: rgba(255,255,255,0.08);'"
            >
              {{ statusText || (status === 'idle' ? L('待機中', 'Idle', '待機中', '대기 중', 'Inactivo') : status) }}
            </span>
          </div>

          <div class="flex-1 rounded-xl overflow-hidden flex items-center justify-center" style="background: #0a0a0f; border: 1px dashed rgba(255,255,255,0.08); min-height: 360px;">
            <BeforeAfterSlider
              v-if="resultImage && uploadedImage"
              :before-image="uploadedImage"
              :after-image="resultImage"
              :before-label="L('原始', 'Before', 'オリジナル', '원본', 'Antes')"
              :after-label="L('AI 渲染', 'After', 'AI後', 'AI 후', 'Después')"
            />
            <div v-else class="text-center px-6 py-10">
              <p class="text-5xl mb-3 opacity-40">🏠</p>
              <p class="text-sm" style="color: #94949f;">
                {{ L('上傳房間照片並選擇風格後，渲染結果會出現在這裡。', 'Upload a room photo and pick a style — the rendered result will appear here.', '部屋の写真をアップロードしてスタイルを選ぶと、結果がここに表示されます。', '방 사진을 업로드하고 스타일을 선택하면 결과가 여기에 표시됩니다.', 'Sube una foto y elige un estilo; el resultado aparecerá aquí.') }}
              </p>
            </div>
          </div>
        </main>
      </div>
    </section>

    <!-- ═══ PORTFOLIO grid — clicking pre-fills the form ═════════════════ -->
    <section class="px-4 sm:px-6 lg:px-8 pb-12 max-w-7xl mx-auto">
      <div class="flex items-end justify-between mb-5">
        <div>
          <h2 class="text-2xl sm:text-3xl font-bold" style="color: #f5f5fa;">
            {{ L('最新渲染作品', 'Latest Rendered Work', '最新レンダリング作品', '최신 렌더링 작품', 'Trabajos Recientes') }}
          </h2>
          <p class="text-sm mt-1" style="color: #94949f;">
            {{ L(`${portfolioGrid.length} 個範本，點擊任意一個套用到上方的編輯器。`, `${portfolioGrid.length} templates — click any to apply to the editor above.`, `${portfolioGrid.length}個のテンプレート、クリックして上のエディタに適用。`, `${portfolioGrid.length}개의 템플릿, 클릭해 위 편집기에 적용.`, `${portfolioGrid.length} plantillas; haz clic para aplicar.`) }}
          </p>
        </div>
        <button @click="gotoTemplates" class="text-xs font-medium" style="color: #c4b5fd;">
          {{ L('查看全部 →', 'View All →', 'すべて見る →', '전체 보기 →', 'Ver todo →') }}
        </button>
      </div>
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3 sm:gap-4">
        <button
          v-for="card in portfolioGrid.slice(0, 20)"
          :key="card.id"
          @click="pickFromPortfolio(card)"
          class="group rounded-xl overflow-hidden text-left"
          style="background: #141420; border: 1px solid rgba(255,255,255,0.06);"
        >
          <div class="aspect-[4/5] relative overflow-hidden" style="background: linear-gradient(135deg, rgba(124,58,237,0.15), rgba(244,114,182,0.1));">
            <img
              v-if="card.preview_url"
              :src="card.preview_url"
              :alt="(isZh ? card.name_zh : card.name)"
              class="w-full h-full object-cover transition-transform group-hover:scale-105"
              loading="lazy"
              @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }"
            />
            <div v-else class="absolute inset-0 flex items-center justify-center text-3xl">🏠</div>
          </div>
          <div class="p-3">
            <p class="text-xs font-semibold" style="color: #f5f5fa;">
              <!-- Backend StyleCard only ships name + name_zh; ja/ko/es fall through to English (BUG-017, backend out of scope). -->
              {{ isZh ? card.name_zh : card.name }}
            </p>
          </div>
        </button>
      </div>
    </section>

    <!-- ═══ How it works ════════════════════════════════════════════════ -->
    <section class="px-4 sm:px-6 lg:px-8 pb-12 max-w-7xl mx-auto">
      <h2 class="text-xl font-semibold mb-5" style="color: #f5f5fa;">
        {{ L('運作方式', 'How It Works', '使い方', '작동 방식', 'Cómo funciona') }}
      </h2>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div
          v-for="(step, i) in [
            L('上傳房間照片或草圖', 'Upload a room photo or sketch', '部屋の写真かスケッチをアップロード', '방 사진이나 스케치 업로드', 'Sube una foto o boceto'),
            L('選擇模式與風格（或用文字描述）', 'Pick a mode + style (or describe in text)', 'モードとスタイルを選択（テキストで記述も可）', '모드와 스타일 선택 (또는 텍스트로 설명)', 'Elige un modo y estilo (o descríbelo)'),
            L('微調強度、燈光、材質', 'Adjust strength, lighting, material', '強度、照明、素材を調整', '강도, 조명, 재질 조정', 'Ajusta fuerza, iluminación y material'),
            L('生成並下載提案級渲染', 'Generate & download proposal-grade renders', '生成して提案レベルの画像をダウンロード', '생성 후 제안용 렌더링 다운로드', 'Genera y descarga renders profesionales'),
          ]"
          :key="i"
          class="rounded-xl p-4"
          style="background: #141420; border: 1px solid rgba(255,255,255,0.06);"
        >
          <p class="text-xs font-mono mb-1" style="color: #a78bfa;">0{{ i + 1 }}</p>
          <p class="text-sm" style="color: #f5f5fa;">
            {{ step }}
          </p>
        </div>
      </div>
    </section>

    <section class="px-4 sm:px-6 lg:px-8 pb-16 max-w-7xl mx-auto">
      <ExampleGallery tool-key="room-redesign" />
    </section>
  </div>
</template>
