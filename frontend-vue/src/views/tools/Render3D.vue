<script setup lang="ts">
/**
 * Render3D (3D 效果圖 / 細化) — photorealistic interior render of an uploaded
 * floor plan, isometric, or room photo.
 *
 * UX rebuilt 2026-06-14 (owner spec): default to 細化模式 — the uploaded
 * image's STYLE and FURNITURE LAYOUT are locked, the user only tunes
 * lighting + per-surface texture (floor / ceiling / wall) with sensible
 * defaults. Magic mode unlocks a free-prompt textarea (layout still locked).
 *
 *   render      → photorealistic image only
 *   simulation  → 4 light×material variants of the same locked space
 *   video       → render + Kling 3.0/Omni growth animation
 *   video_3d    → + Trellis2 interactive .glb model
 *
 * Backend: POST /api/v1/interior/floorplan-to-video
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUIStore, useCreditsStore } from '@/stores'
import { useLocalized } from '@/composables'
import { toolsApi } from '@/api'
import {
  interiorApi,
  type FloorplanTier,
  type GrowthTier,
  type InteriorLightingTone,
  type SurfaceFloor,
  type SurfaceCeiling,
  type SurfaceWall,
  type SimulationVariant,
} from '@/api/interior'
import PiapiPlayground from '@/components/tools/PiapiPlayground.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
import ThreeViewer from '@/components/tools/ThreeViewer.vue'
import BeforeAfterSlider from '@/components/tools/BeforeAfterSlider.vue'
import { extractApiError } from '@/utils/apiError'
import { dataURItoBlob } from '@/utils/dataUri'
import { downloadAsset } from '@/utils/downloadAsset'

const { t, locale } = useI18n()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { L } = useLocalized()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

// ─── State ───────────────────────────────────────────────────────────
const imageInput = ref<string | undefined>(undefined)
const resultTier = ref<GrowthTier>('render')

// Mode: 細化 (detail, default) = layout & style locked, only surfaces + light.
//       魔法 (magic)            = free-prompt unlocked, layout still locked.
const magicMode = ref(false)

// Per-surface texture presets (細化 mode). Defaults applied so a first-time
// user can hit Generate without picking anything.
const surfaceFloor = ref<SurfaceFloor>('oak')
const surfaceCeiling = ref<SurfaceCeiling>('white')
const surfaceWall = ref<SurfaceWall>('white')

// Lighting preset (both modes).
const lightingTone = ref<InteriorLightingTone>('daylight')

// Magic-mode free prompt.
const magicPrompt = ref('')

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const renderImageUrl = ref<string | null>(null)
const videoUrl = ref<string | null>(null)
const modelUrl = ref<string | null>(null)
const simulationVariants = ref<SimulationVariant[]>([])
const expandedSimUrl = ref<string | null>(null)

// ─── Catalog (tiers) from the backend ────────────────────────────────
const tiers = ref<FloorplanTier[]>([])
onMounted(async () => {
  try {
    const opts = await interiorApi.getFloorplanOptions()
    tiers.value = opts.tiers || []
  } catch {
    tiers.value = []
  }
})

// ─── Validation + cost ───────────────────────────────────────────────
const disabled = computed(() => !imageInput.value)
const isRunning = computed(() => status.value === 'running')
const isVideoTier = computed(() => resultTier.value === 'video' || resultTier.value === 'video_3d')
const isSimulationTier = computed(() => resultTier.value === 'simulation')

const creditCost = computed(() => {
  // Backend-published cost wins; the fallbacks below mirror the constants in
  // backend/app/api/v1/interior.py so the UI never shows a stale price.
  const tier = tiers.value.find(tt => tt.id === resultTier.value)
  if (tier) return tier.credits
  switch (resultTier.value) {
    case 'video_3d':  return 750
    case 'video':     return 600
    case 'simulation': return 140
    default:           return 40
  }
})

async function ensureImageUrl(): Promise<string | null> {
  if (!imageInput.value) return null
  if (!imageInput.value.startsWith('data:')) return imageInput.value
  const blob = dataURItoBlob(imageInput.value)
  if (!blob) return null
  const up = await toolsApi.uploadImage(blob as File)
  return up.url
}

async function generate() {
  if (disabled.value || isRunning.value) return
  status.value = 'running'
  statusText.value =
    resultTier.value === 'render'
      ? L('生成中… 約 30–90 秒', 'Generating… ~30–90s', '生成中… 約30〜90秒', '생성 중… 약 30~90초', 'Generando… ~30–90 s')
      : resultTier.value === 'simulation'
        ? L('同時生成 4 種光線+材質變體… 約 60–150 秒', 'Rendering 4 light×material variants… ~60–150s', '4種類のバリエーションを生成中… 約60〜150秒', '4가지 변형 동시 생성 중… 약 60~150초', 'Renderizando 4 variantes… ~60–150 s')
        : resultTier.value === 'video_3d'
          ? L('生成中… 影片 + 3D 模型約需 10-25 分鐘', 'Generating… video + 3D model, ~10-25 min', '生成中… 動画 + 3Dモデル、約10〜25分', '생성 중… 영상 + 3D 모델, 약 10~25분', 'Generando… vídeo + modelo 3D, ~10-25 min')
          : L('生成中… Kling 3.0 影片約需 8-20 分鐘', 'Generating… Kling 3.0 video, ~8-20 min', '生成中… Kling 3.0 動画、約8〜20分', '생성 중… Kling 3.0 영상, 약 8~20분', 'Generando… vídeo Kling 3.0, ~8-20 min')
  renderImageUrl.value = null
  videoUrl.value = null
  modelUrl.value = null
  simulationVariants.value = []

  try {
    const imageUrl = await ensureImageUrl()
    if (!imageUrl) {
      status.value = 'error'
      uiStore.showError(L('圖片上傳失敗', 'Image upload failed', '画像アップロード失敗', '이미지 업로드 실패', 'Subida fallida'))
      return
    }

    const result = await interiorApi.floorplanToVideo({
      image_url: imageUrl,
      result_tier: resultTier.value,
      // Layout is ALWAYS locked under the new UX — preserve_original=true
      // applies to detail mode AND magic mode (magic only loosens style/materials).
      preserve_original: true,
      magic_mode: magicMode.value,
      surface_floor: surfaceFloor.value,
      surface_ceiling: surfaceCeiling.value,
      surface_wall: surfaceWall.value,
      lighting_tone: lightingTone.value,
      prompt: magicMode.value ? (magicPrompt.value.trim() || undefined) : undefined,
      language: isZh.value ? 'zh' : 'en',
    })

    const okSimulation = isSimulationTier.value && (result?.simulation_variants?.length || 0) > 0
    const okVideo = isVideoTier.value && !!result.video_url
    const okRender = !isSimulationTier.value && !isVideoTier.value && !!result.render_image_url
    const ok = result?.success && (okSimulation || okVideo || okRender)
    if (ok) {
      renderImageUrl.value = result.render_image_url || null
      videoUrl.value = result.video_url || null
      modelUrl.value = result.model_url || null
      simulationVariants.value = result.simulation_variants || []
      status.value = 'done'
      statusText.value = L('完成', 'Done', '完了', '완료', 'Listo')
      if (result.credits_used) creditsStore.deductCredits(result.credits_used)
      if (resultTier.value === 'video_3d' && !result.model_url) {
        uiStore.showError(L(
          '影片已生成,但 3D 模型建立失敗,已退回 3D 部分點數。',
          'Video generated, but the 3D model failed — the 3D portion was refunded.',
          '動画は生成されましたが、3Dモデルの作成に失敗しました。3D分のクレジットは返却済みです。',
          '영상은 생성되었지만 3D 모델 생성에 실패하여 3D 부분 크레딧을 환불했습니다.',
          'Vídeo generado, pero el modelo 3D falló — se reembolsó la parte 3D.',
        ))
      } else {
        uiStore.showSuccess(t('common.success') || 'Success')
      }
    } else {
      status.value = 'error'
      statusText.value = L('生成失敗', 'Failed', '生成失敗', '생성 실패', 'Generación fallida')
      uiStore.showError(result?.error || L('生成失敗', 'Generation failed', '生成に失敗しました', '생성에 실패했습니다', 'La generación falló'))
    }
  } catch (e: any) {
    status.value = 'error'
    statusText.value = L('錯誤', 'Error', 'エラー', '오류', 'Error')
    uiStore.showError(extractApiError(e, L('生成失敗', 'Generation failed', '生成に失敗しました', '생성에 실패했습니다', 'La generación falló')))
  }
}

const pageTitle = computed(() => L('3D 效果圖（細化）', '3D Render (Refine)', '3D 効果図（詳細化）', '3D 효과도 (디테일)', 'Render 3D (refinado)'))
const pageSubtitle = computed(() => L(
  '上傳平面配置圖、立體圖或房間照片 — AI 會鎖定原始配置與家具,只依您挑的光線與牆/地/天花板材質進行寫實渲染;切換到魔法模式可自由 prompt。',
  'Upload a floor plan, isometric, or room photo — AI locks the original layout and furniture and only restyles light + floor/ceiling/wall textures. Switch to magic mode for free prompting.',
  '間取り図やレンダリングをアップロード — AIが元のレイアウトと家具を固定し、光と床/天井/壁の素材だけを再スタイル化。マジックモードで自由プロンプトも可能。',
  '평면도나 방 사진을 올리면 AI가 원래 배치와 가구를 잠그고 조명·바닥/천장/벽 재질만 다시 스타일링합니다. 매직 모드에서 자유 프롬프트도 가능합니다.',
  'Sube un plano o foto; la IA bloquea la distribución y muebles, y solo reestiliza luz + texturas. Modo mágico para escribir libremente.',
))
const hasResult = computed(() => {
  if (isSimulationTier.value) return simulationVariants.value.length > 0
  if (isVideoTier.value) return !!videoUrl.value
  return !!renderImageUrl.value
})
</script>

<template>
  <PiapiPlayground
    :eta-seconds="resultTier === 'render' ? 60 : resultTier === 'simulation' ? 120 : resultTier === 'video_3d' ? 1200 : 720"
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="L('開始生成', 'Generate', '生成開始', '생성 시작', 'Generar')"
    :generate-label-running="L('生成中…', 'Generating…', '生成中…', '생성 중…', 'Generando…')"
    :disabled="disabled"
    @generate="generate"
  >
    <template #inputs>
      <!-- What this page supports (owner request 2026-06-16): make the four
           output tiers explicit so users know the page does more than a still. -->
      <div class="rounded-lg px-3 py-2.5 text-[11px] leading-relaxed"
        style="background: rgba(124,58,237,0.08); border:1px solid rgba(124,58,237,0.2); color:#c4b5fd;">
        <div class="font-semibold mb-1" style="color:#ddd6fe;">{{ L('本頁支援', 'This page supports', 'このページの機能', '이 페이지가 지원', 'Esta página admite') }}</div>
        <ul class="space-y-0.5" style="list-style:none; padding:0; margin:0;">
          <li>🖼️ {{ L('3D 效果圖（細化）— 鎖定原配置,只調光線與材質的寫實渲染', '3D render (refine) — photorealistic, layout locked, light + materials only', '3D効果図(詳細化)— レイアウト固定で光と素材のみ', '3D 효과도(디테일) — 배치 고정, 조명·재질만', 'Render 3D (refinado) — distribución bloqueada') }}</li>
          <li>🎚️ {{ L('4 種光線 × 材質模擬,一次比較', '4 lighting × material simulations to compare', '4種のライト×素材シミュレーション', '4가지 조명×재질 시뮬레이션', '4 simulaciones de luz × material') }}</li>
          <li>🎬 {{ L('成長影片 — 由平面「長出」3D 房間（Kling 3.0/Omni）', 'Growth video — the plan “grows” into the 3D room (Kling 3.0/Omni)', '成長動画 — 平面が3D空間へ(Kling 3.0/Omni)', '성장 영상 — 평면이 3D로(Kling 3.0/Omni)', 'Vídeo de crecimiento (Kling 3.0/Omni)') }}</li>
          <li>🧊 {{ L('可旋轉 3D 模型（Trellis2 .glb,360° 檢視）', 'Rotatable 3D model (Trellis2 .glb, 360° view)', '回転可能な3Dモデル(Trellis2 .glb)', '회전 가능한 3D 모델(Trellis2 .glb)', 'Modelo 3D giratorio (Trellis2 .glb)') }}</li>
        </ul>
      </div>

      <div>
        <label class="pp-field-label">{{ L('平面圖 / 房間照片 *', 'Floor plan / room photo *', '間取り図・部屋写真 *', '평면도 / 방 사진 *', 'Plano / foto *') }}</label>
        <ImageUploader
          tool-type="room_redesign"
          v-model="imageInput"
          :label="L('點擊或拖放圖片', 'Click or drag an image', 'クリックまたはドラッグ', '클릭 또는 드래그', 'Haz clic o arrastra')"
        />
      </div>

      <div>
        <label class="pp-field-label">{{ L('想要的結果 *', 'What result do you want? *', '希望する結果 *', '원하는 결과 *', '¿Qué resultado quieres? *') }}</label>
        <select v-model="resultTier" class="pp-select">
          <option value="render">{{ L('3D 效果圖（單張）', '3D render (single image)', '3D効果図（1枚）', '3D 효과도 (단일)', 'Render 3D (única)') }}</option>
          <option value="simulation">{{ L('模擬演示 / 試色（一次 4 張變體）', 'Simulation / Try colors (4 variants in one call)', 'シミュレーション（4種類のバリエーション）', '시뮬레이션 / 시험 (4가지 변형)', 'Simulación / Prueba (4 variantes)') }}</option>
          <option value="video">{{ L('效果圖 + 成長動畫影片', 'Render + growth video', '効果図 + 成長アニメ動画', '효과도 + 성장 영상', 'Render + vídeo de crecimiento') }}</option>
          <option value="video_3d">{{ L('效果圖 + 影片 + 可旋轉 3D 模型', 'Render + video + rotatable 3D model', '効果図 + 動画 + 回転可能3Dモデル', '효과도 + 영상 + 회전 3D 모델', 'Render + vídeo + modelo 3D giratorio') }}</option>
        </select>
        <p class="pp-field-help">
          {{
            resultTier === 'render'      ? L('單張寫實 3D 渲染,速度最快、點數最省。', 'A single photoreal render — fastest and cheapest.', '1枚のフォトリアル3Dレンダー。最速・最安。', '단일 사실적 렌더 — 가장 빠르고 저렴.', 'Un único render fotorrealista: lo más rápido y económico.')
          : resultTier === 'simulation'  ? L('同一空間 4 種光線+材質組合,一次比對「早晨」「黃昏」「陰天」「金色時刻」。', 'Four light×material combos of the SAME space side-by-side: morning, evening, overcast, golden hour.', '同じ空間を「朝」「夕方」「曇天」「ゴールデンアワー」の4パターンで生成。', '동일 공간을 아침/저녁/흐림/골든아워 4가지로 동시 생성.', '4 combinaciones luz×material del mismo espacio: mañana, tarde, nublado, hora dorada.')
          : resultTier === 'video_3d'    ? L('效果圖 + 影片 + Trellis2 .glb 模型,可 360° 旋轉。', 'Render + video + a Trellis2 .glb model you can rotate 360°.', '効果図 + 動画 + 360°回転できる Trellis2 .glb モデル。', '효과도 + 영상 + 360° 회전 가능한 Trellis2 .glb 모델.', 'Render + vídeo + modelo .glb Trellis2 girable 360°.')
                                         : L('效果圖 + Kling 3.0 含音訊的成長動畫影片。', 'Render + Kling 3.0 growth animation with audio.', '効果図 + 音声付き Kling 3.0 成長アニメ。', '효과도 + 오디오 포함 Kling 3.0 성장 애니메이션.', 'Render + animación de crecimiento Kling 3.0 con audio.')
          }}
        </p>
      </div>

      <!-- 細化 / 魔法 mode toggle -->
      <div>
        <label class="pp-field-label">{{ L('編輯模式', 'Edit Mode', '編集モード', '편집 모드', 'Modo de edición') }}</label>
        <div class="grid grid-cols-2 gap-2">
          <button type="button" @click="magicMode = false"
            class="p-3 rounded-lg text-left transition-colors"
            :style="!magicMode
              ? 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color:#fff;'
              : 'background:#0a0a0f; color:#94949f; border:1px solid rgba(255,255,255,0.08);'"
          >
            <div class="text-[13px] font-semibold mb-1">{{ !magicMode ? '✓ ' : '' }}{{ L('細化模式', 'Refine', '詳細モード', '디테일', 'Detalle') }}</div>
            <div class="text-[11px] leading-snug opacity-80">{{ L('鎖定家具配置與風格,只調光與牆/地/天花板材質。', 'Lock layout & style; only tweak light + floor/ceiling/wall textures.', 'レイアウトとスタイルを固定、光と床/天井/壁の素材だけ調整。', '레이아웃·스타일 잠금, 조명·바닥/천장/벽 재질만 조정.', 'Bloquea distribución y estilo; ajusta solo luz y texturas.') }}</div>
          </button>
          <button type="button" @click="magicMode = true"
            class="p-3 rounded-lg text-left transition-colors"
            :style="magicMode
              ? 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color:#fff;'
              : 'background:#0a0a0f; color:#94949f; border:1px solid rgba(255,255,255,0.08);'"
          >
            <div class="text-[13px] font-semibold mb-1">{{ magicMode ? '✓ ' : '' }}{{ L('魔法模式', 'Magic Mode', 'マジックモード', '매직 모드', 'Modo mágico') }}</div>
            <div class="text-[11px] leading-snug opacity-80">{{ L('自由 prompt 重新風格化;家具配置仍鎖定,不會憑空長出。', 'Free prompt restyling; furniture layout still locked, never invented.', '自由プロンプトで再スタイル化。家具配置は固定で創作しない。', '자유 프롬프트로 재스타일링. 가구 배치는 고정.', 'Re-estilizado con prompt libre; los muebles siguen bloqueados.') }}</div>
          </button>
        </div>
      </div>

      <!-- Lighting preset (both modes) -->
      <div>
        <label class="pp-field-label">{{ L('光線氛圍', 'Lighting', '照明', '조명', 'Iluminación') }}</label>
        <select v-model="lightingTone" class="pp-select">
          <option value="daylight">{{ L('自然日光', 'Natural daylight', '自然光', '자연광', 'Luz natural') }}</option>
          <option value="warm_evening">{{ L('暖色傍晚', 'Warm evening', '暖色夕方', '따뜻한 저녁', 'Atardecer cálido') }}</option>
          <option value="golden_hour">{{ L('金色時刻', 'Golden hour', 'ゴールデンアワー', '골든아워', 'Hora dorada') }}</option>
          <option value="overcast_soft">{{ L('陰天柔光', 'Overcast soft', '曇り柔光', '흐린 부드러움', 'Nublado suave') }}</option>
          <option value="dramatic_spotlight">{{ L('戲劇聚光', 'Dramatic spotlight', 'ドラマチック', '드라마틱', 'Foco dramático') }}</option>
          <option value="night">{{ L('夜景', 'Night', '夜景', '야간', 'Nocturno') }}</option>
        </select>
      </div>

      <!-- Surface presets (細化 mode only) -->
      <template v-if="!magicMode">
        <div>
          <label class="pp-field-label">{{ L('地板材質', 'Floor texture', '床素材', '바닥 재질', 'Suelo') }}</label>
          <select v-model="surfaceFloor" class="pp-select">
            <option value="oak">{{ L('暖色橡木地板', 'Warm oak hardwood', '暖色オーク', '웜 오크', 'Roble cálido') }}</option>
            <option value="walnut">{{ L('深色胡桃木地板', 'Dark walnut hardwood', 'ダークウォルナット', '다크 월넛', 'Nogal oscuro') }}</option>
            <option value="marble">{{ L('白色大理石', 'White marble', '白大理石', '화이트 마블', 'Mármol blanco') }}</option>
            <option value="concrete">{{ L('拋光水泥', 'Polished concrete', '磨きコンクリート', '폴리시드 콘크리트', 'Hormigón pulido') }}</option>
            <option value="terrazzo">{{ L('磨石子（Terrazzo）', 'Terrazzo', 'テラゾー', '테라조', 'Terrazo') }}</option>
            <option value="tile">{{ L('啞光瓷磚', 'Matte porcelain tile', 'マット磁器タイル', '매트 포세린 타일', 'Porcelánico mate') }}</option>
          </select>
        </div>
        <div>
          <label class="pp-field-label">{{ L('天花板', 'Ceiling', '天井', '천장', 'Techo') }}</label>
          <select v-model="surfaceCeiling" class="pp-select">
            <option value="white">{{ L('純白', 'White', '白', '화이트', 'Blanco') }}</option>
            <option value="warm_white">{{ L('暖白', 'Warm white', '暖白', '웜 화이트', 'Blanco cálido') }}</option>
            <option value="exposed_beam">{{ L('裸露木樑', 'Exposed wood beams', '露出木梁', '노출 목재 빔', 'Vigas de madera') }}</option>
            <option value="industrial">{{ L('工業裸頂', 'Industrial exposed', '工業むき出し', '인더스트리얼', 'Industrial') }}</option>
          </select>
        </div>
        <div>
          <label class="pp-field-label">{{ L('牆面', 'Walls', '壁', '벽', 'Paredes') }}</label>
          <select v-model="surfaceWall" class="pp-select">
            <option value="white">{{ L('純白漆', 'White paint', '白塗装', '화이트 페인트', 'Pintura blanca') }}</option>
            <option value="warm_grey">{{ L('暖灰石灰漆', 'Warm grey limewash', 'ウォームグレーライムウォッシュ', '웜 그레이 라임워시', 'Cal gris cálido') }}</option>
            <option value="feature_brick">{{ L('磚牆主牆', 'Feature brick wall', 'レンガアクセント', '벽돌 포인트벽', 'Muro de ladrillo') }}</option>
            <option value="wood_panel">{{ L('木板主牆', 'Wood-panel feature wall', '木パネル', '우드 패널', 'Panel de madera') }}</option>
          </select>
        </div>
      </template>

      <!-- Magic mode free prompt -->
      <template v-else>
        <div>
          <label class="pp-field-label">{{ L('Prompt（魔法模式）', 'Prompt (magic mode)', 'プロンプト（マジック）', '프롬프트 (매직)', 'Prompt (mágico)') }}</label>
          <textarea v-model="magicPrompt" rows="4" maxlength="1000" class="pp-textarea"
            :placeholder="L('描述您想要的風格、材質、氛圍。例：日式侘寂、米色亞麻、藤編家具、紙燈籠。家具配置會自動保留。', 'Describe the style, materials, mood you want. e.g.: Japandi wabi-sabi, beige linen, rattan, paper lanterns. Layout stays locked automatically.', 'スタイル・素材・雰囲気を自由に。例：和モダン、麻、籐、和紙照明。レイアウトは固定されます。', '원하는 스타일·재질·분위기. 예: 와비사비, 베이지 린넨, 라탄, 종이 등. 배치는 자동 잠금.', 'Describe estilo, materiales, atmósfera. p. ej.: japandi, lino beige, ratán, faroles. La distribución queda bloqueada.')"></textarea>
          <p class="pp-field-help">{{ L('魔法模式仍然鎖定家具與牆面配置 — 不會憑空長出新門窗或家具,只會重新風格化現有空間。', 'Magic mode still locks walls and furniture — no invented doors, windows, or pieces; only restyles what is already there.', 'マジックモードでも壁と家具は固定。新たな扉・窓・家具は生成されず、既存空間の再スタイル化のみ。', '매직 모드도 벽·가구를 잠급니다. 새 문/창/가구 생성 없이 기존 공간만 재스타일링.', 'El modo mágico bloquea muros y muebles: no inventa, solo re-estiliza lo existente.') }}</p>
        </div>
      </template>
    </template>

    <template v-if="hasResult" #result>
      <!-- Simulation tier: 4-up grid -->
      <template v-if="isSimulationTier && simulationVariants.length">
        <div class="grid grid-cols-2 gap-2 w-full max-w-[640px]">
          <div v-for="v in simulationVariants" :key="v.image_url" class="flex flex-col items-center">
            <img :src="v.image_url" :alt="v.label" loading="lazy"
              @click="expandedSimUrl = v.image_url"
              class="w-full h-auto object-cover rounded-md cursor-zoom-in"
              style="border:1px solid rgba(124,58,237,0.25);" />
            <span class="text-[11px] mt-1" style="color:#94949f;">{{ v.label }}</span>
          </div>
        </div>
        <div v-if="expandedSimUrl" @click="expandedSimUrl = null"
          class="fixed inset-0 z-50 flex items-center justify-center cursor-zoom-out"
          style="background:rgba(0,0,0,0.85);">
          <img :src="expandedSimUrl" class="max-w-[92vw] max-h-[92vh] object-contain" />
        </div>
      </template>
      <!-- Render-only tier: before/after comparison (or plain image) -->
      <template v-else-if="!isVideoTier && renderImageUrl">
        <BeforeAfterSlider
          v-if="imageInput"
          :before-image="imageInput"
          :after-image="renderImageUrl"
          :before-label="L('原始圖片', 'Before', '元画像', '원본', 'Antes')"
          :after-label="L('渲染結果', 'After', 'レンダー', '렌더', 'Después')"
        />
        <img v-else :src="renderImageUrl" alt="3D render"
          class="max-w-full max-h-[520px] object-contain rounded-lg" />
      </template>
      <!-- Video tiers: video + render + optional 3D model -->
      <div v-else class="flex flex-col gap-3 w-full items-center">
        <video v-if="videoUrl" :src="videoUrl" class="max-w-full max-h-[420px] rounded-lg" controls autoplay loop muted />
        <div class="flex flex-wrap gap-3 justify-center w-full">
          <div v-if="renderImageUrl" class="flex flex-col items-center">
            <span class="text-[11px] mb-1" style="color:#94949f;">{{ L('3D 效果圖', '3D render', '3D効果図', '3D 효과도', 'Render 3D') }}</span>
            <img :src="renderImageUrl" class="max-h-[200px] rounded-md" style="border:1px solid rgba(124,58,237,0.25);" />
          </div>
          <div v-if="modelUrl" class="flex flex-col items-center">
            <span class="text-[11px] mb-1" style="color:#94949f;">{{ L('可旋轉 3D 模型', 'Rotatable 3D model', '回転可能な3Dモデル', '회전 가능한 3D 모델', 'Modelo 3D giratorio') }}</span>
            <ThreeViewer :model-url="modelUrl" :auto-rotate="true" :width="320" :height="220" />
          </div>
        </div>
      </div>
    </template>

    <template v-if="hasResult" #result-actions>
      <template v-if="isSimulationTier && simulationVariants.length">
        <button v-for="(v, idx) in simulationVariants" :key="v.image_url"
          @click="downloadAsset(v.image_url, `vidgo_simulation_${idx+1}_${Date.now()}.png`)"
          class="px-2 py-1.5 rounded text-xs font-medium"
          style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
        >📥 {{ idx + 1 }}</button>
      </template>
      <button v-if="!isSimulationTier && !isVideoTier && renderImageUrl"
        @click="downloadAsset(renderImageUrl!, `vidgo_render3d_${Date.now()}.png`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
      >📥 {{ L('下載', 'Download', 'ダウンロード', '다운로드', 'Descargar') }}</button>
      <button v-if="videoUrl"
        @click="downloadAsset(videoUrl!, `vidgo_render3d_${Date.now()}.mp4`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
      >📥 {{ L('下載影片', 'Download video', '動画をダウンロード', '영상 다운로드', 'Descargar vídeo') }}</button>
      <button v-if="modelUrl"
        @click="downloadAsset(modelUrl!, `vidgo_model_${Date.now()}.glb`)"
        class="px-3 py-1.5 rounded text-xs font-medium ml-2"
        style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
      >📦 {{ L('下載 3D (.glb)', 'Download 3D (.glb)', '3Dをダウンロード (.glb)', '3D 다운로드 (.glb)', 'Descargar 3D (.glb)') }}</button>
      <button @click="generate"
        class="px-3 py-1.5 rounded text-xs font-medium ml-2"
        style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
      >🔄 {{ L('重新生成', 'Regenerate', '再生成', '다시 생성', 'Regenerar') }}</button>
    </template>
  </PiapiPlayground>
</template>
