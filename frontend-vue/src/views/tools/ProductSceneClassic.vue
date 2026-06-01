<script setup lang="ts">
/**
 * ProductScene (Classic generator) — PiAPI-style playground (Deploy 4).
 *
 * Backed by /api/v1/tools/product-scene. Routes a product image + a
 * scene template (studio / nature / elegant / minimal / lifestyle / etc.)
 * OR a custom prompt to Flux Kontext I2I. The Kontext I2I path is what
 * preserves the product silhouette / label / color through the restyling.
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized } from '@/composables'
import { toolsApi } from '@/api'
import apiClient from '@/api/client'
import PiapiPlayground from '@/components/tools/PiapiPlayground.vue'
import ExampleGallery from '@/components/tools/ExampleGallery.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
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

interface SceneTemplate { id: string; name: string; name_zh: string; preview_url?: string; prompt?: string }
const sceneTemplates = ref<SceneTemplate[]>([])

const productImage = ref<string | undefined>(undefined)
const sceneType = ref<string>('studio')
const customPrompt = ref('')
const mode = ref<'preset' | 'custom'>('preset')

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)

const disabled = computed(() => {
  if (!productImage.value) return true
  if (mode.value === 'custom') return !customPrompt.value.trim()
  return !sceneType.value
})
const creditCost = computed(() => 10)

async function loadScenes() {
  try {
    const resp = await apiClient.get('/api/v1/tools/templates/scenes')
    sceneTemplates.value = (resp.data || []) as SceneTemplate[]
  } catch (e) {
    console.warn('[product-scene] failed to load scene templates', e)
  }
}
onMounted(loadScenes)

async function ensureImageUrl(): Promise<string | null> {
  if (!productImage.value) return null
  if (!productImage.value.startsWith('data:')) return productImage.value
  const blob = dataURItoBlob(productImage.value)
  if (!blob) return null
  const up = await toolsApi.uploadImage(blob as File)
  return up.url
}

async function generate() {
  if (disabled.value || status.value === 'running') return
  // Backend governs access: a free account gets the cached example for a
  // catalog scene (preset); a custom prompt returns
  // 'subscription_card_required', handled below.
  status.value = 'running'
  statusText.value = isZh.value ? '生成中…' : 'Generating…'
  resultUrl.value = null
  try {
    const url = await ensureImageUrl()
    if (!url) { status.value = 'error'; uiStore.showError(L('圖片上傳失敗', 'Image upload failed', '画像アップロード失敗', '이미지 업로드 실패', 'Subida fallida')); return }
    const result = await toolsApi.productScene(
      url,
      mode.value === 'preset' ? sceneType.value : 'custom',
      mode.value === 'custom' ? customPrompt.value.trim() : undefined,
      undefined,
      undefined,
      undefined,
      String(locale.value || ''),
    )
    if (handleCardRequired(result, uiStore, router, isZh.value)) {
      status.value = 'idle'
      return
    }
    if (result.success && (result.image_url || result.result_url)) {
      resultUrl.value = result.image_url || result.result_url || null
      status.value = 'done'
      statusText.value = isZh.value ? '完成' : 'Done'
      if (result.credits_used) creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success') || 'Success')
    } else {
      status.value = 'error'
      uiStore.showError((result as any).message || (result as any).error || (isZh.value ? '生成失敗' : 'Failed'))
    }
  } catch (e: any) {
    status.value = 'error'
    uiStore.showError(extractApiError(e, isZh.value ? '生成失敗' : 'Failed'))
  }
}

function gotoPricing() { router.push('/pricing') }
</script>

<template>
  <PiapiPlayground
    :eta-seconds="40"
    :title="isZh ? '商品場景圖' : 'Product Scene'"
    :subtitle="isZh
      ? '上傳商品照片，AI 把產品放進新場景（攝影棚、自然、優雅、極簡、生活風或自訂）。保留產品標籤與顏色不變形。'
      : 'Upload a product photo; AI places the product into a new scene (studio / nature / elegant / minimal / lifestyle / custom). Label and color preserved.'"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="isZh ? '生成場景' : 'Generate'"
    :generate-label-running="isZh ? '生成中…' : 'Generating…'"
    :disabled="disabled"
    @generate="generate"
  >
    <template #inputs>
      <div>
        <label class="pp-field-label">{{ isZh ? '模型 *' : 'Model *' }}</label>
        <select class="pp-select" disabled>
          <option>Flux Kontext I2I (product-preserving)</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '任務類型 *' : 'Task Type *' }}</label>
        <select class="pp-select" disabled>
          <option>img2img · kontext</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '商品照片 *' : 'Product Photo *' }}</label>
        <ImageUploader
          tool-type="product_scene"
          v-model="productImage"
          :label="isZh ? '點擊或拖放商品照片' : 'Click or drag a product photo'"
        />
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '場景方式 *' : 'Scene Source *' }}</label>
        <div class="grid grid-cols-2 gap-1.5">
          <button v-for="opt in [
            { id: 'preset' as const, labelZh: '預設場景', labelEn: 'Preset' },
            { id: 'custom' as const, labelZh: '自訂提示詞', labelEn: 'Custom Prompt' },
          ]" :key="opt.id" type="button" @click="mode = opt.id"
            class="py-2 rounded text-xs font-medium"
            :style="mode === opt.id
              ? 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color: #fff;'
              : 'background: #0a0a0f; color: #94949f; border: 1px solid rgba(255,255,255,0.08);'"
          >{{ isZh ? opt.labelZh : opt.labelEn }}</button>
        </div>
      </div>

      <div v-if="mode === 'preset'">
        <label class="pp-field-label">{{ isZh ? '預設場景' : 'Preset Scene' }}</label>
        <select v-model="sceneType" class="pp-select">
          <option v-for="s in sceneTemplates" :key="s.id" :value="s.id">
            {{ isZh ? s.name_zh : s.name }}
          </option>
        </select>
      </div>

      <div v-if="mode === 'custom'">
        <label class="pp-field-label">{{ isZh ? '自訂場景描述 *' : 'Custom Scene Prompt *' }}</label>
        <textarea v-model="customPrompt" rows="4" maxlength="300" class="pp-textarea"
          :placeholder="isZh ? '例：木質吧檯、暖色 Edison 燈、背景輕微散景' : 'e.g. wooden bar counter, warm Edison-bulb lighting, subtle background bokeh'"></textarea>
        <p class="pp-field-help">{{ isZh ? '提示會原封不動傳給 Kontext I2I。' : 'Your prompt reaches Kontext I2I verbatim.' }}</p>
      </div>

      <p v-if="isDemoUser" class="pp-field-help" style="color: #fbbf24;">
        {{ isZh
          ? '免費帳號可用內建場景生成範例；自訂提示詞需訂閱並綁定信用卡。'
          : 'Free accounts can render the built-in scenes as examples; custom prompts require a subscription with a bound card.' }}
        <button @click="gotoPricing" class="underline ml-1">{{ isZh ? '查看方案' : 'View Plans' }} →</button>
      </p>
    </template>

    <template v-if="resultUrl" #result>
      <img :src="resultUrl" alt="Product Scene" class="max-w-full max-h-[520px] object-contain rounded-lg" />
    </template>

    <template v-if="resultUrl" #result-actions>
      <button @click="downloadAsset(resultUrl!, `vidgo_scene_${Date.now()}.png`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >📥 {{ isZh ? '下載' : 'Download' }}</button>
    </template>

    <template #examples>
      <ExampleGallery tool-key="product-scene-classic" />
    </template>
  </PiapiPlayground>
</template>
