<script setup lang="ts">
/**
 * ImageUpscale — PiAPI-style playground (Deploy 4, 2026-05-24).
 * Backed by /api/v1/tools/upscale (PiAPI image-toolkit super-resolution).
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized } from '@/composables'
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

const imageInput = ref<string | undefined>(undefined)
const scale = ref<2 | 4 | 8>(2)

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)

const disabled = computed(() => !imageInput.value)
// Backend tools.py upscale handler is flat 10 credits regardless of scale
// (line ~3963 CREDIT_COST=10, no scale-based variation, no per-scale
// service_pricing row). Frontend previously advertised 20/30 for 4x/8x —
// pre-pricing-v2.1 draft that never landed in the backend. Showing the
// true 10 to match what's actually deducted.
const creditCost = computed(() => 10)

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
  statusText.value = isZh.value ? '提升中…' : 'Upscaling…'
  resultUrl.value = null
  try {
    const url = await ensureImageUrl()
    if (!url) { status.value = 'error'; uiStore.showError(L('圖片上傳失敗', 'Image upload failed', '画像アップロード失敗', '이미지 업로드 실패', 'Subida fallida')); return }
    const result = await toolsApi.upscale(url, scale.value)
    if (result.success && (result.image_url || result.result_url)) {
      resultUrl.value = result.image_url || result.result_url || null
      status.value = 'done'
      statusText.value = isZh.value ? '完成' : 'Done'
      if (result.credits_used) creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success') || 'Success')
    } else {
      status.value = 'error'
      uiStore.showError((result as any).message || (result as any).error || (isZh.value ? '提升失敗' : 'Upscale failed'))
    }
  } catch (e: any) {
    status.value = 'error'
    uiStore.showError(extractApiError(e, isZh.value ? '提升失敗' : 'Upscale failed'))
  }
}

function gotoPricing() { router.push('/pricing') }
</script>

<template>
  <PiapiPlayground
    :eta-seconds="30"
    :title="isZh ? '圖片高清放大' : 'Image Upscale (Super Resolution)'"
    :subtitle="isZh
      ? '把任何圖片放大 2x、4x、8x，保留邊緣與細節。'
      : 'Upscale any image by 2x, 4x, or 8x while preserving edges and detail.'"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="isZh ? '開始放大' : 'Upscale'"
    :generate-label-running="isZh ? '處理中…' : 'Upscaling…'"
    :disabled="disabled || isDemoUser"
    @generate="generate"
  >
    <template #inputs>
      <div>
        <label class="pp-field-label">{{ isZh ? '模型 *' : 'Model *' }}</label>
        <select class="pp-select" disabled>
          <option>Image Upscale (Super Resolution) — Qubico image-toolkit</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '任務類型 *' : 'Task Type *' }}</label>
        <select class="pp-select" disabled>
          <option>upscale</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '圖片 *' : 'Image *' }}</label>
        <ImageUploader
          tool-type="upscale"
          v-model="imageInput"
          :label="isZh ? '點擊或拖放 JPG / PNG（最大 2048×2048）' : 'Click or drag JPG / PNG (max 2048×2048)'"
        />
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '放大倍率 *' : 'Scale *' }}</label>
        <div class="grid grid-cols-3 gap-1.5">
          <button
            v-for="opt in [2, 4, 8] as const"
            :key="opt"
            type="button"
            @click="scale = opt"
            class="py-2 rounded-lg text-xs font-medium transition-colors"
            :style="scale === opt
              ? 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color: #fff;'
              : 'background: #0a0a0f; color: #94949f; border: 1px solid rgba(255,255,255,0.08);'"
          >{{ opt }}x</button>
        </div>
        <p class="pp-field-help">{{ isZh ? '倍率越高，輸出像素越多，點數消耗越高。' : 'Higher scales use more pixels and cost more credits.' }}</p>
      </div>

      <p v-if="isDemoUser" class="pp-field-help" style="color: #fbbf24;">
        {{ isZh ? '訂閱後即可使用。' : 'Subscribe to use this tool.' }}
        <button @click="gotoPricing" class="underline ml-1">{{ isZh ? '查看方案' : 'View Plans' }} →</button>
      </p>
    </template>

    <template v-if="resultUrl" #result>
      <img :src="resultUrl" alt="Upscaled" class="max-w-full max-h-[520px] object-contain rounded-lg" />
    </template>

    <template v-if="resultUrl" #result-actions>
      <button @click="downloadAsset(resultUrl!, `vidgo_upscale_${scale}x_${Date.now()}.png`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >📥 {{ isZh ? '下載' : 'Download' }}</button>
    </template>

    <template #examples>
      <ExampleGallery tool-key="image-upscale" />
    </template>
  </PiapiPlayground>
</template>
