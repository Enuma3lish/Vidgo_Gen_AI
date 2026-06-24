<script setup lang="ts">
/**
 * CommercialSpace — AI design for commercial interiors (restaurant, retail,
 * hotel, office, café, gym). Split out of the former all-in-one RoomRedesign
 * page (owner directive 2026-06-03: "interior design should divide, not all in
 * one page"). Reuses /api/v1/tools/room-redesign with space_kind='commercial';
 * backend unchanged.
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized, useGenerationTask } from '@/composables'
import { toolsApi } from '@/api'
import apiClient from '@/api/client'
import PiapiPlayground from '@/components/tools/PiapiPlayground.vue'
import ExampleGallery from '@/components/tools/ExampleGallery.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
import BeforeAfterSlider from '@/components/tools/BeforeAfterSlider.vue'
import { dataURItoBlob } from '@/utils/dataUri'
import { downloadAsset } from '@/utils/downloadAsset'
import { extractApiError } from '@/utils/apiError'
import { handleCardRequired } from '@/utils/toolGate'

const { t, locale } = useI18n()
const router = useRouter()
const route = useRoute()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { L } = useLocalized()
const { isDemoUser } = useDemoMode()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

type Mode = 'redesign' | 'stage' | 'magic'
const mode = ref<Mode>('redesign')
const imageInput = ref<string | undefined>(undefined)
const selectedStyle = ref<string>('')
const customPrompt = ref<string>('')
const styleStrength = ref<number>(0.7)

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)

// P0-2: single source of truth for the in-flight task — recovers on timeout
// (background poll) and on page refresh (resume()).
const task = useGenerationTask('commercial_space')
function renderTaskResult(r: any) {
  if (r && r.success && (r.image_url || r.result_url)) {
    const u = r.image_url || r.result_url || ''
    resultUrl.value = u.startsWith('http') ? u : `${window.location.origin}${u}`
    status.value = 'done'
    statusText.value = L('完成', 'Done', '完了', '완료', 'Listo')
    if (r.credits_used) creditsStore.deductCredits(r.credits_used)
  }
}
watch(() => task.result.value, (r) => renderTaskResult(r))
watch(() => task.phase.value, (p) => {
  if (p === 'error') {
    status.value = 'error'
    uiStore.showError(task.error.value || (isZh.value ? '生成失敗' : 'Generation failed'))
  }
})

interface StyleCard { id: string; name: string; name_zh: string }
const styles = ref<StyleCard[]>([])

onMounted(async () => {
  if (task.resume()) {
    status.value = 'running'
    statusText.value = L('正在恢復先前的生成…', 'Resuming your previous generation…', '前回の生成を復元中…', '이전 생성을 복구하는 중…', 'Reanudando tu generación…')
  }
  try {
    const resp = await apiClient.get('/api/v1/tools/templates/interior-styles?space_kind=commercial')
    styles.value = (resp.data || []) as StyleCard[]
  } catch (e) {
    console.warn('[commercial-space] failed to load commercial styles:', e)
  }
  // Templates-gallery deeplink (?style=<id>) pre-fills the picker.
  const qStyle = String(route.query.style || '').trim()
  if (qStyle) selectedStyle.value = qStyle
})

const disabled = computed(() => {
  if (!imageInput.value) return true
  if (mode.value === 'magic') return !customPrompt.value.trim()
  return !selectedStyle.value
})
const creditCost = computed(() => 20)
const disabledReason = computed(() => {
  if (!disabled.value) return ''
  if (!imageInput.value) return L('請先上傳空間照片。', 'Upload a space photo first.', '空間写真をアップロードしてください。', '공간 사진을 먼저 업로드하세요.', 'Sube primero una foto del espacio.')
  if (mode.value === 'magic') return L('魔法模式請先輸入描述。', 'Magic mode needs a description.', 'マジックモードは説明が必要です。', '매직 모드는 설명이 필요합니다.', 'El modo mágico necesita una descripción.')
  return L('請選擇一個商業風格。', 'Pick a commercial style to continue.', '商業スタイルを選択してください。', '상업 스타일을 선택하세요.', 'Elige un estilo comercial.')
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
  if (disabled.value || status.value === 'running') return
  status.value = 'running'
  statusText.value = L('生成中… 通常需要 30 秒至 2 分鐘', 'Generating… typically 30s to 2 minutes', '生成中… 通常30秒〜2分', '생성 중… 보통 30초~2분', 'Generando… 30 s a 2 min')
  resultUrl.value = null

  // Upload BEFORE the task wrapper (must not carry the client id).
  const url = await ensureImageUrl()
  if (!url) { status.value = 'error'; uiStore.showError(L('圖片上傳失敗', 'Image upload failed', '画像アップロード失敗', '이미지 업로드 실패', 'Subida fallida')); return }

  let result: any
  try {
    result = await task.run((cid) => toolsApi.roomRedesign(url, mode.value === 'magic' ? '' : selectedStyle.value, customPrompt.value.trim() || undefined, undefined, undefined, {
      mode: mode.value,
      spaceKind: 'commercial',
      styleStrength: styleStrength.value,
    }, cid))
  } catch (e: any) {
    status.value = 'error'
    uiStore.showError(extractApiError(e, isZh.value ? '生成失敗' : 'Generation failed'))
    return
  }

  if (result === null) {
    status.value = 'running'
    statusText.value = L('仍在生成中，完成後會存入「我的作品」。', 'Still generating — it will be saved to My Works when done.', '生成中です。完了後「マイ作品」に保存されます。', '생성 중입니다. 완료되면 내 작품에 저장됩니다.', 'Generando; se guardará en Mis Trabajos.')
    return
  }
  if (handleCardRequired(result, uiStore, router, isZh.value)) {
    status.value = 'idle'; statusText.value = ''; return
  }
  if (result.success && (result.image_url || result.result_url)) {
    renderTaskResult(result)
    uiStore.showSuccess(t('common.success') || 'Success')
  } else {
    status.value = 'error'
    uiStore.showError((result as any).message || (result as any).error || (isZh.value ? '生成失敗' : 'Generation failed'))
  }
}

function gotoPricing() { router.push('/pricing') }
</script>

<template>
  <PiapiPlayground
    :eta-seconds="60"
    :title="L('商業空間設計', 'Commercial Space Design', '商業空間デザイン', '상업 공간 디자인', 'Diseño de espacios comerciales')"
    :subtitle="L(
      '上傳餐廳、零售、飯店、辦公室、咖啡廳或健身房空間照片，AI 換上專業商業設計風格。',
      'Upload a restaurant, retail, hotel, office, café, or gym space — AI restyles it with professional commercial design.',
      'レストラン・小売・ホテル・オフィス・カフェ・ジムの空間をアップロード、AIがプロの商業デザインに。',
      '레스토랑·리테일·호텔·오피스·카페·짐 공간을 올리면 AI가 전문 상업 디자인으로 바꿉니다.',
      'Sube un restaurante, tienda, hotel, oficina, café o gimnasio; la IA lo rediseña profesionalmente.')"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="L('開始生成', 'Generate', '生成', '생성', 'Generar')"
    :generate-label-running="L('生成中…', 'Generating…', '生成中…', '생성 중…', 'Generando…')"
    :disabled="disabled || isDemoUser"
    :disabled-reason="disabledReason"
    :eta-label="L('預計約 30–90 秒', 'Usually ~30–90s', '約30〜90秒', '약 30~90초', 'Normalmente ~30–90 s')"
    :empty-hint="L('上傳空間照片並選擇風格，渲染結果會顯示在這裡。', 'Upload a space photo and pick a style — your render will appear here.', '空間写真をアップロードしスタイルを選ぶと、ここに結果が表示されます。', '공간 사진을 올리고 스타일을 선택하면 여기에 결과가 표시됩니다.', 'Sube una foto y elige un estilo; el render aparecerá aquí.')"
    @generate="generate"
  >
    <template #inputs>
      <div>
        <label class="pp-field-label">{{ L('模式', 'Mode', 'モード', '모드', 'Modo') }}</label>
        <div class="grid grid-cols-3 gap-1.5">
          <button v-for="opt in [
              { id: 'redesign' as const, label: L('改造', 'Redesign', 'リデザイン', '리디자인', 'Rediseño') },
              { id: 'stage' as const,    label: L('佈置', 'Stage', 'ステージング', '스테이징', 'Staging') },
              { id: 'magic' as const,    label: L('魔法', 'Magic', 'マジック', '매직', 'Mágico') },
            ]" :key="opt.id" type="button" @click="mode = opt.id"
            class="py-2 rounded-lg text-xs font-medium transition-colors"
            :style="mode === opt.id
              ? 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color:#fff;'
              : 'background:#0a0a0f; color:#94949f; border:1px solid rgba(255,255,255,0.08);'"
          >{{ opt.label }}</button>
        </div>
      </div>

      <div>
        <label class="pp-field-label">{{ L('空間照片 *', 'Space photo *', '空間写真 *', '공간 사진 *', 'Foto *') }}</label>
        <ImageUploader
          tool-type="room_redesign"
          v-model="imageInput"
          :label="L('點擊或拖放空間照片', 'Click or drag a space photo', 'クリックまたはドロップ', '클릭 또는 드롭', 'Haz clic o arrastra')"
        />
        <p class="pp-field-help">{{ L('支援 JPG / PNG / WebP。建議使用清晰、能看到整體空間的照片。', 'Supports JPG / PNG / WebP. Use a clear photo showing the whole space.', 'JPG / PNG / WebP 対応。空間全体が写った鮮明な写真を推奨。', 'JPG / PNG / WebP 지원. 공간 전체가 보이는 선명한 사진을 권장.', 'Admite JPG / PNG / WebP. Usa una foto nítida de todo el espacio.') }}</p>
      </div>

      <div v-if="mode !== 'magic'">
        <label class="pp-field-label">{{ L('商業風格 *', 'Commercial Style *', '商業スタイル *', '상업 스타일 *', 'Estilo *') }} <span style="color:#6b6b7a">({{ styles.length }})</span></label>
        <select v-model="selectedStyle" class="pp-select">
          <option value="">{{ L('— 請選擇 —', '— Select —', '— 選択 —', '— 선택 —', '— Seleccionar —') }}</option>
          <option v-for="s in styles" :key="s.id" :value="s.id">{{ isZh ? s.name_zh : s.name }}</option>
        </select>
      </div>

      <div v-if="mode === 'magic'">
        <label class="pp-field-label">{{ L('描述你想要的空間', 'Describe the space you want', '欲しい空間を記述', '원하는 공간 설명', 'Describe el espacio') }}</label>
        <textarea v-model="customPrompt" rows="4" maxlength="2000"
          :placeholder="L('例：精品咖啡廳，水磨石吧台，暖色吊燈，木質座位，綠植點綴。', 'e.g. specialty coffee shop, terrazzo bar counter, warm pendant lights, wood seating, accent greenery.', '例：スペシャルティカフェ、テラゾーカウンター、暖色ペンダント照明、木の座席。', '예: 스페셜티 카페, 테라조 바, 따뜻한 펜던트 조명, 우드 좌석.', 'Ej: cafetería de especialidad, barra de terrazo, luces cálidas, asientos de madera.')"
          class="pp-select" style="resize:vertical;"></textarea>
      </div>

      <div v-if="mode !== 'magic'">
        <label class="pp-field-label">{{ L('風格強度', 'Style Strength', 'スタイル強度', '스타일 강도', 'Fuerza') }}
          <span class="ml-2" style="color:#a78bfa">{{ Math.round(styleStrength * 100) }}%</span>
        </label>
        <input type="range" min="0.3" max="1" step="0.05" v-model.number="styleStrength" class="w-full" style="accent-color:#a78bfa" />
      </div>

      <p class="pp-field-help">{{ mode === 'stage'
        ? L('佈置：空店面 → AI 自動配置家具陳設。', 'Stage: empty space → AI furnishes & merchandises it.', 'ステージング：空店舗 → AIが家具配置。', '스테이징: 빈 공간 → AI가 가구 배치.', 'Staging: espacio vacío → la IA lo amuebla.')
        : mode === 'magic'
        ? L('魔法：你的描述會原封不動傳給 AI。', 'Magic: your description goes to the AI verbatim.', 'マジック：説明はそのままAIへ。', '매직: 설명이 그대로 AI로.', 'Mágico: tu descripción va literal a la IA.')
        : L('改造：保留結構，換上選定的商業設計風格。', 'Redesign: preserve structure, apply the selected commercial style.', 'リデザイン：構造を保持し商業スタイルを適用。', '리디자인: 구조 유지, 선택한 상업 스타일 적용.', 'Rediseño: conserva la estructura y aplica el estilo.') }}</p>

      <p v-if="isDemoUser" class="pp-field-help" style="color:#fbbf24;">
        {{ L('訂閱後即可使用。', 'Subscribe to use this tool.', 'サブスクで利用可能。', '구독 후 사용 가능.', 'Suscríbete para usar.') }}
        <button @click="gotoPricing" class="underline ml-1">{{ L('查看方案', 'View Plans', 'プランを見る', '플랜 보기', 'Ver planes') }} →</button>
      </p>
    </template>

    <template v-if="resultUrl" #result>
      <BeforeAfterSlider
        v-if="imageInput"
        :before-image="imageInput"
        :after-image="resultUrl"
        :before-label="L('原始', 'Before', 'オリジナル', '원본', 'Antes')"
        :after-label="L('AI 渲染', 'After', 'AI後', 'AI 후', 'Después')"
      />
      <img v-else :src="resultUrl" alt="Commercial" class="max-w-full max-h-[520px] object-contain rounded-lg" />
    </template>

    <template v-if="resultUrl" #result-actions>
      <button @click="downloadAsset(resultUrl!, `vidgo_commercial_${Date.now()}.png`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
      >📥 {{ L('下載', 'Download', 'ダウンロード', '다운로드', 'Descargar') }}</button>
    </template>

    <template #examples>
      <ExampleGallery tool-key="room-redesign" />
    </template>
  </PiapiPlayground>
</template>
