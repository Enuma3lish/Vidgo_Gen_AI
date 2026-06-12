<script setup lang="ts">
/**
 * Recolor (商品換色) — change a product's color, keep everything else.
 *
 * Added 2026-06-12 (owner request): the 商品換色 hub tile previously pointed
 * at /tools/pattern-generate (a pattern generator, not a recolor tool).
 * Backend: POST /api/v1/tools/recolor — Flux Kontext I2I with a strict
 * "modify ONLY the color" envelope (shape / texture / logo / background /
 * lighting locked). 15 credits.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized } from '@/composables'
import { toolsApi } from '@/api'
import PiapiPlayground from '@/components/tools/PiapiPlayground.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
import BeforeAfterSlider from '@/components/tools/BeforeAfterSlider.vue'
import { dataURItoBlob } from '@/utils/dataUri'
import { downloadAsset } from '@/utils/downloadAsset'
import { extractApiError } from '@/utils/apiError'
import { handleCardRequired } from '@/utils/toolGate'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { L } = useLocalized()
const { isDemoUser } = useDemoMode()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

const imageInput = ref<string | undefined>(undefined)
const targetPart = ref('')
const customColor = ref('')
const customPrompt = ref('')

// Preset swatches — `prompt` is the English color sent to the model;
// label is localized for display.
interface Swatch { id: string; hex: string; prompt: string; zh: string; en: string }
const swatches: Swatch[] = [
  { id: 'black',  hex: '#1a1a1a', prompt: 'matte black',        zh: '經典黑', en: 'Black' },
  { id: 'white',  hex: '#f5f5f0', prompt: 'pure white',         zh: '純淨白', en: 'White' },
  { id: 'red',    hex: '#c0392b', prompt: 'deep red',           zh: '正紅',   en: 'Red' },
  { id: 'orange', hex: '#e67e22', prompt: 'vibrant orange',     zh: '活力橘', en: 'Orange' },
  { id: 'yellow', hex: '#f1c40f', prompt: 'warm yellow',        zh: '暖黃',   en: 'Yellow' },
  { id: 'green',  hex: '#27602f', prompt: 'forest green',       zh: '森林綠', en: 'Green' },
  { id: 'blue',   hex: '#2c5f8a', prompt: 'classic blue',       zh: '經典藍', en: 'Blue' },
  { id: 'navy',   hex: '#1f2a44', prompt: 'navy blue',          zh: '海軍藍', en: 'Navy' },
  { id: 'purple', hex: '#6f42c1', prompt: 'rich purple',        zh: '深紫',   en: 'Purple' },
  { id: 'pink',   hex: '#e8a0bf', prompt: 'soft pink',          zh: '櫻花粉', en: 'Pink' },
  { id: 'brown',  hex: '#7b5239', prompt: 'caramel brown',      zh: '焦糖棕', en: 'Brown' },
  { id: 'grey',   hex: '#8a8a8a', prompt: 'neutral grey',       zh: '霧灰',   en: 'Grey' },
]
const selectedSwatchId = ref<string>('')
function pickSwatch(s: Swatch) {
  selectedSwatchId.value = s.id
  customColor.value = ''
  resultUrl.value = null
}

const effectiveColor = computed(() => {
  if (customColor.value.trim()) return customColor.value.trim()
  const s = swatches.find((x) => x.id === selectedSwatchId.value)
  return s ? s.prompt : ''
})

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)

const creditCost = computed(() => 15)
const disabled = computed(() => !imageInput.value || !effectiveColor.value)
const disabledReason = computed(() => {
  if (!imageInput.value) return L('請先上傳商品照片。', 'Upload a product photo first.', '商品写真をアップロードしてください。', '제품 사진을 먼저 업로드하세요.', 'Sube primero una foto del producto.')
  if (!effectiveColor.value) return L('請選擇或輸入目標顏色。', 'Pick or type a target color.', '色を選択または入力してください。', '색상을 선택하거나 입력하세요.', 'Elige o escribe un color.')
  return ''
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
  statusText.value = L('換色中… 約 20–60 秒', 'Recoloring… ~20–60s', '色変更中… 約20〜60秒', '색 변경 중… 약 20~60초', 'Recoloreando… ~20–60 s')
  resultUrl.value = null
  try {
    const url = await ensureImageUrl()
    if (!url) { status.value = 'error'; uiStore.showError(L('圖片上傳失敗', 'Image upload failed', '画像アップロード失敗', '이미지 업로드 실패', 'Subida fallida')); return }
    const result = await toolsApi.recolor(url, {
      targetColor: effectiveColor.value,
      targetPart: targetPart.value.trim() || undefined,
      customPrompt: customPrompt.value.trim() || undefined,
    })
    if (handleCardRequired(result, uiStore, router, isZh.value)) {
      status.value = 'idle'; statusText.value = ''; return
    }
    if (result.success && (result.image_url || result.result_url)) {
      const u = result.image_url || result.result_url || ''
      resultUrl.value = u.startsWith('http') ? u : `${window.location.origin}${u}`
      status.value = 'done'
      statusText.value = L('完成', 'Done', '完了', '완료', 'Listo')
      if (result.credits_used) creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success') || 'Success')
    } else {
      status.value = 'error'
      uiStore.showError((result as any).message || (result as any).error || (isZh.value ? '換色失敗' : 'Recolor failed'))
    }
  } catch (e: any) {
    status.value = 'error'
    uiStore.showError(extractApiError(e, isZh.value ? '換色失敗' : 'Recolor failed'))
  }
}

function gotoPricing() { router.push('/pricing') }
</script>

<template>
  <PiapiPlayground
    :eta-seconds="40"
    :title="L('商品換色', 'Product Recolor', '商品カラー変更', '제품 색상 변경', 'Recolorear producto')"
    :subtitle="L(
      '上傳商品照片並選擇目標顏色,AI 只改變顏色 — 形狀、材質、Logo、背景與光影完全不變。',
      'Upload a product photo and pick a target color — AI changes ONLY the color; shape, texture, logo, background and lighting stay identical.',
      '商品写真をアップロードして色を選ぶと、AIは色だけを変更します — 形・質感・ロゴ・背景はそのまま。',
      '제품 사진을 올리고 색상을 고르면 AI가 색상만 바꿉니다 — 형태·질감·로고·배경은 그대로.',
      'Sube una foto del producto y elige un color: la IA cambia SOLO el color.')"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="L('開始換色', 'Recolor', '色を変更', '색 변경', 'Recolorear')"
    :generate-label-running="L('換色中…', 'Recoloring…', '変更中…', '변경 중…', 'Recoloreando…')"
    :disabled="disabled || isDemoUser"
    :disabled-reason="disabledReason"
    :empty-hint="L('上傳商品照並選擇顏色,結果會顯示在這裡。', 'Upload a product photo and pick a color — the result appears here.', '商品写真をアップロードして色を選ぶと、結果がここに表示されます。', '제품 사진을 올리고 색상을 선택하면 결과가 여기에 표시됩니다.', 'Sube una foto y elige un color; el resultado aparecerá aquí.')"
    @generate="generate"
  >
    <template #inputs>
      <div>
        <label class="pp-field-label">{{ L('商品照片 *', 'Product Photo *', '商品写真 *', '제품 사진 *', 'Foto del producto *') }}</label>
        <ImageUploader
          tool-type="upscale"
          v-model="imageInput"
          :label="L('點擊或拖放商品照片', 'Click or drag a product photo', 'クリックまたはドロップ', '클릭 또는 드롭', 'Haz clic o arrastra')"
        />
      </div>

      <div>
        <label class="pp-field-label">{{ L('目標顏色 *', 'Target Color *', '目標カラー *', '목표 색상 *', 'Color objetivo *') }}</label>
        <div class="grid grid-cols-6 gap-2">
          <button
            v-for="s in swatches"
            :key="s.id"
            type="button"
            @click="pickSwatch(s)"
            class="rounded-lg overflow-hidden text-center transition-all"
            :style="selectedSwatchId === s.id && !customColor.trim()
              ? 'border: 2px solid #a78bfa; box-shadow: 0 0 0 2px rgba(124,58,237,0.35);'
              : 'border: 1px solid rgba(255,255,255,0.10);'"
          >
            <div class="h-8" :style="{ background: s.hex }"></div>
            <p class="text-[10px] py-0.5" style="color:#94949f;">{{ isZh ? s.zh : s.en }}</p>
          </button>
        </div>
        <input v-model="customColor" type="text" maxlength="60" class="pp-input mt-2"
               :placeholder="L('或自行輸入顏色：例如 霧霾藍、#ff5733', 'Or type a color: e.g. dusty blue, #ff5733', '色を入力：例 くすみブルー、#ff5733', '직접 입력: 예 더스티 블루, #ff5733', 'O escribe un color: ej. azul empolvado, #ff5733')" />
        <p class="pp-field-help">{{ L('輸入文字顏色會覆蓋上方色票選擇。', 'Typing a color overrides the swatch selection.', '入力した色はスウォッチ選択より優先されます。', '입력한 색상이 스와치 선택보다 우선합니다.', 'El texto tiene prioridad sobre la muestra.') }}</p>
      </div>

      <div>
        <label class="pp-field-label">{{ L('換色部位（選填）', 'Part to recolor (optional)', '変更する部位（任意）', '변경할 부위 (선택)', 'Parte a recolorear (opcional)') }}</label>
        <input v-model="targetPart" type="text" maxlength="120" class="pp-input"
               :placeholder="L('例：帽 T 的帽子、瓶蓋、鞋帶。留空 = 整個商品', 'e.g. the hood, the bottle cap, the laces. Empty = whole product', '例：フード、ボトルキャップ。空欄＝商品全体', '예: 후드, 병뚜껑. 비우면 제품 전체', 'ej.: la capucha, el tapón. Vacío = todo el producto')" />
      </div>

      <div>
        <label class="pp-field-label">{{ L('補充說明（選填）', 'Notes (optional)', '補足（任意）', '추가 설명 (선택)', 'Notas (opcional)') }}</label>
        <textarea v-model="customPrompt" rows="2" maxlength="500" class="pp-textarea"
          :placeholder="L('例：保持金屬拉鍊原色。', 'e.g. keep the metal zipper in its original color.', '例：金属ファスナーは元の色のまま。', '예: 금속 지퍼는 원래 색 유지.', 'ej.: mantener la cremallera metálica en su color original.')"></textarea>
      </div>

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
        :before-label="L('原色', 'Before', '元の色', '원본', 'Antes')"
        :after-label="L('換色後', 'After', '変更後', '변경 후', 'Después')"
      />
      <img v-else :src="resultUrl" alt="Recolored" class="max-w-full max-h-[520px] object-contain rounded-lg" />
    </template>

    <template v-if="resultUrl" #result-actions>
      <button @click="downloadAsset(resultUrl!, `vidgo_recolor_${Date.now()}.png`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
      >📥 {{ L('下載', 'Download', 'ダウンロード', '다운로드', 'Descargar') }}</button>
      <button @click="generate"
        class="px-3 py-1.5 rounded text-xs font-medium ml-2"
        style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
      >🔄 {{ L('重新生成', 'Regenerate', '再生成', '다시 생성', 'Regenerar') }}</button>
    </template>
  </PiapiPlayground>
</template>
