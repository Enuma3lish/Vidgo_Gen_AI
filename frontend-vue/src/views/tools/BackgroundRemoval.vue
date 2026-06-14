<script setup lang="ts">
/**
 * BackgroundRemoval — PiAPI-style playground (Deploy 4, 2026-05-24).
 *
 * Backed by /api/v1/tools/remove-bg. Output format dropdown lets the
 * user pick alpha PNG / white bg / black bg / colored bg / AI-generated
 * scene bg. Single image only — the batch endpoint keeps its own UI on
 * /tools/bg-removal-batch (unchanged in this deploy).
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized, useExamplePrefill } from '@/composables'
import { toolsApi } from '@/api'
import PiapiPlayground from '@/components/tools/PiapiPlayground.vue'
import ExampleGallery from '@/components/tools/ExampleGallery.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
import { dataURItoBlob } from '@/utils/dataUri'
import { downloadAsset } from '@/utils/downloadAsset'
import { extractApiError } from '@/utils/apiError'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { L } = useLocalized()
const { isDemoUser } = useDemoMode()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

type BgMode = 'png' | 'white' | 'black' | 'color' | 'ai'
const bgMode = ref<BgMode>('png')
const backgroundColor = ref('#ffffff')
const aiBackgroundPrompt = ref('')

const imageInput = ref<string | undefined>(undefined)

// Gallery deeplink — only the source image matters for BG removal, but if a
// prompt was passed treat it as an AI-replace-background prompt.
useExamplePrefill({
  onImage: (url) => { imageInput.value = url },
  onPrompt: (p) => {
    if (p) {
      aiBackgroundPrompt.value = p
      bgMode.value = 'ai'
    }
  },
  onError: () => uiStore.showError(L(
    '範例素材已過期,請改用其他範例或上傳自有圖片。',
    'This example is no longer available. Pick another or upload your own image.',
    'この例は利用できなくなりました。別の例を選ぶか、画像をアップロードしてください。',
    '이 예제는 더 이상 사용할 수 없습니다. 다른 예제를 선택하거나 이미지를 업로드하세요.',
    'Este ejemplo ya no está disponible. Elige otro o sube tu propia imagen.',
  )),
})

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)

const disabled = computed(() => {
  if (!imageInput.value) return true
  if (bgMode.value === 'ai' && !aiBackgroundPrompt.value.trim()) return true
  return false
})
// VidGo 3.0 扣點表 — background removal = 2 credits (~$0.001 upstream),
// flat regardless of mode. Matches tools.py remove-bg handler.
const creditCost = computed(() => 2)

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
  if (isDemoUser.value) {
    uiStore.showInfo(L('請訂閱以使用此工具', 'Please subscribe to use this tool', 'サブスク登録してください', '구독해 주세요', 'Suscríbete'))
    return
  }
  status.value = 'running'
  statusText.value = isZh.value ? '處理中…' : 'Processing…'
  resultUrl.value = null
  try {
    const url = await ensureImageUrl()
    if (!url) { status.value = 'error'; uiStore.showError(L('圖片上傳失敗', 'Image upload failed', '画像アップロード失敗', '이미지 업로드 실패', 'Subida fallida')); return }

    // Backend remove-bg API takes output_format = 'png' | 'white' | 'black'
    // plus optional backgroundColor / backgroundImageUrl / aiBackgroundPrompt.
    // Map our 'color' / 'ai' UI modes onto the right backend opts.
    const opts: any = {}
    let outputFormat: 'png' | 'white' | 'black' = 'png'
    if (bgMode.value === 'white') outputFormat = 'white'
    else if (bgMode.value === 'black') outputFormat = 'black'
    else if (bgMode.value === 'color') opts.backgroundColor = backgroundColor.value
    else if (bgMode.value === 'ai') opts.aiBackgroundPrompt = aiBackgroundPrompt.value.trim()

    const result = await toolsApi.removeBackground(url, outputFormat, opts)
    if (result.success && (result.image_url || result.result_url)) {
      resultUrl.value = result.image_url || result.result_url || null
      status.value = 'done'
      statusText.value = isZh.value ? '完成' : 'Done'
      if (result.credits_used) creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success') || 'Success')
    } else {
      status.value = 'error'
      uiStore.showError((result as any).message || (result as any).error || (isZh.value ? '處理失敗' : 'Failed'))
    }
  } catch (e: any) {
    status.value = 'error'
    uiStore.showError(extractApiError(e, isZh.value ? '處理失敗' : 'Failed'))
  }
}

function gotoPricing() { router.push('/pricing') }
</script>

<template>
  <PiapiPlayground
    :eta-seconds="20"
    :title="isZh ? '圖片去背 / 換景' : 'Image Background Remove'"
    :subtitle="isZh
      ? '一鍵移除背景，輸出透明 PNG、白底、黑底、純色，或讓 AI 生成全新場景。'
      : 'One-click background removal. Output transparent PNG, white, black, solid color, or let AI generate a new scene.'"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="isZh ? '開始處理' : 'Generate'"
    :generate-label-running="isZh ? '處理中…' : 'Processing…'"
    :disabled="disabled || isDemoUser"
    @generate="generate"
  >
    <template #inputs>
      <div>
        <label class="pp-field-label">{{ isZh ? '模型 *' : 'Model *' }}</label>
        <select class="pp-select" disabled>
          <option>Qubico image-toolkit · background-remove</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '任務類型 *' : 'Task Type *' }}</label>
        <select class="pp-select" disabled>
          <option>remove-bg</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '圖片 *' : 'Image *' }}</label>
        <ImageUploader
          tool-type="background_removal"
          v-model="imageInput"
          :label="isZh ? '點擊或拖放圖片' : 'Click or drag an image'"
        />
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '背景輸出 *' : 'Background Output *' }}</label>
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
          <button v-for="opt in [
            { id: 'png' as const,   labelZh: '透明 PNG',  labelEn: 'Transparent' },
            { id: 'white' as const, labelZh: '純白',      labelEn: 'White' },
            { id: 'black' as const, labelZh: '純黑',      labelEn: 'Black' },
            { id: 'color' as const, labelZh: '自選色',    labelEn: 'Solid Color' },
            { id: 'ai' as const,    labelZh: 'AI 生成場景', labelEn: 'AI Scene' },
          ]" :key="opt.id" type="button" @click="bgMode = opt.id"
            class="py-2 rounded text-xs font-medium"
            :style="bgMode === opt.id
              ? 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color: #fff;'
              : 'background: #0a0a0f; color: #94949f; border: 1px solid rgba(255,255,255,0.08);'"
          >{{ isZh ? opt.labelZh : opt.labelEn }}</button>
        </div>
      </div>

      <div v-if="bgMode === 'color'">
        <label class="pp-field-label">{{ isZh ? '背景顏色' : 'Background Color' }}</label>
        <input v-model="backgroundColor" type="color" class="w-full h-10 rounded" style="background: #0a0a0f; border: 1px solid rgba(255,255,255,0.08);" />
      </div>

      <div v-if="bgMode === 'ai'">
        <label class="pp-field-label">{{ isZh ? 'AI 場景描述 *' : 'AI Scene Prompt *' }}</label>
        <textarea v-model="aiBackgroundPrompt" rows="3" maxlength="500" class="pp-textarea"
          :placeholder="isZh ? '例：木質吧檯、暖色燈光、自然散景' : 'e.g. wooden bar counter, warm lighting, natural bokeh'"></textarea>
        <p class="pp-field-help">{{ isZh ? '提示會原封不動傳給 AI。' : 'Your prompt reaches the model verbatim.' }}</p>
      </div>

      <p v-if="isDemoUser" class="pp-field-help" style="color: #fbbf24;">
        {{ isZh ? '訂閱後即可使用。' : 'Subscribe to use this tool.' }}
        <button @click="gotoPricing" class="underline ml-1">{{ isZh ? '查看方案' : 'View Plans' }} →</button>
      </p>
    </template>

    <template v-if="resultUrl" #result>
      <img :src="resultUrl" alt="Result" class="max-w-full max-h-[520px] object-contain rounded-lg" style="background: repeating-conic-gradient(#2a2a3a 0% 25%, #1a1a2a 0% 50%) 50% / 20px 20px;" />
    </template>

    <template v-if="resultUrl" #result-actions>
      <button @click="downloadAsset(resultUrl!, `vidgo_bg_${Date.now()}.png`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >📥 {{ isZh ? '下載' : 'Download' }}</button>
    </template>

    <template #examples>
      <ExampleGallery tool-key="background-removal" />
    </template>
  </PiapiPlayground>
</template>
