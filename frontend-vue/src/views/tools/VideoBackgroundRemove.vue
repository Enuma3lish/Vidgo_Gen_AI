<script setup lang="ts">
/**
 * VideoBackgroundRemove — PiAPI-style playground (2026-05-24).
 *
 * Single-model tool — Qubico video-toolkit's background-remove task. Per
 * the stability probe, this is the only Qubico video endpoint we shipped
 * (upscale + watermark-remove failed the probe and were dropped).
 *
 * Layout: matches piapi.ai/zh-TW/video-remove-background. Left column has
 * the model dropdown (1 option), video upload, invert toggle. Right
 * column shows status + result video player.
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized, useGenerationTask } from '@/composables'
import { toolsApi, uploadsApi } from '@/api'
import PiapiPlayground from '@/components/tools/PiapiPlayground.vue'
import ExampleGallery from '@/components/tools/ExampleGallery.vue'
import { downloadAsset } from '@/utils/downloadAsset'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { L } = useLocalized()
const { isDemoUser } = useDemoMode()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

const videoFile = ref<File | null>(null)
const videoPreviewUrl = ref<string | null>(null)
const invertOutput = ref(false)

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)

const disabled = computed(() => !videoFile.value)
const creditCost = computed(() => 50)

function handleFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const f = input.files?.[0]
  if (!f) return
  // PiAPI constraint: MP4 only, max 20MB, max 1024x2048, 10-2000 frames
  if (!f.type.startsWith('video/')) {
    uiStore.showError(L('請上傳影片檔', 'Please upload a video file', '動画ファイルを選択', '동영상 파일 선택', 'Sube un video'))
    return
  }
  if (f.size > 20 * 1024 * 1024) {
    uiStore.showError(L('檔案超過 20 MB 上限', 'File exceeds the 20 MB limit', '20MB上限を超えています', '20MB 한도 초과', 'Excede el límite de 20 MB'))
    return
  }
  videoFile.value = f
  videoPreviewUrl.value = URL.createObjectURL(f)
  resultUrl.value = null
}

// P0-2: single source of truth for the in-flight task — recovers on timeout
// (background poll) and on page refresh (resume()).
const task = useGenerationTask('video_bg_remove')
function renderTaskResult(r: any) {
  if (r && r.success && (r.video_url || r.result_url)) {
    resultUrl.value = r.video_url || r.result_url || null
    status.value = 'done'
    statusText.value = isZh.value ? '完成' : 'Done'
    if (r.credits_used) creditsStore.deductCredits(r.credits_used)
  }
}
watch(() => task.result.value, (r) => renderTaskResult(r))
watch(() => task.phase.value, (p) => {
  if (p === 'error') {
    status.value = 'error'
    statusText.value = isZh.value ? '處理失敗' : 'Failed'
    uiStore.showError(task.error.value || (isZh.value ? '處理失敗' : 'Processing failed'))
  }
})
onMounted(() => {
  if (task.resume()) {
    status.value = 'running'
    statusText.value = isZh.value ? '正在恢復先前的處理…' : 'Resuming your previous job…'
  }
})

async function generate() {
  if (disabled.value || status.value === 'running') return
  if (isDemoUser.value) {
    uiStore.showInfo(L('請訂閱以使用此工具', 'Please subscribe to use this tool', 'サブスク登録してください', '구독해 주세요', 'Suscríbete'))
    return
  }
  status.value = 'running'
  resultUrl.value = null

  // Upload + normalize BEFORE the task wrapper (the upload must not carry the
  // generation's client_task_id). PiAPI rejects base64; backend needs a public
  // URL — normalizeVideo transcodes to a known-good MP4 in GCS.
  let publicUrl: string
  try {
    statusText.value = isZh.value ? '上傳並正規化影片…' : 'Uploading & normalizing video…'
    const normalized = await uploadsApi.normalizeVideo(videoFile.value!)
    publicUrl = normalized.video_url
    if (!publicUrl) throw new Error('upload returned no url')
  } catch (e: any) {
    status.value = 'error'
    statusText.value = isZh.value ? '錯誤' : 'Error'
    uiStore.showError(e?.message || (isZh.value ? '處理失敗' : 'Processing failed'))
    return
  }
  statusText.value = isZh.value ? '處理中…通常需要 1-3 分鐘' : 'Processing… typically 1-3 minutes'

  let result: any
  try {
    result = await task.run((cid) => toolsApi.videoBackgroundRemove(publicUrl, { invertOutput: invertOutput.value }, cid))
  } catch (e: any) {
    status.value = 'error'
    statusText.value = isZh.value ? '錯誤' : 'Error'
    uiStore.showError(e?.message || (isZh.value ? '處理失敗' : 'Processing failed'))
    return
  }

  if (result === null) {
    // Timed out client-side but the backend is still running — DON'T error.
    status.value = 'running'
    statusText.value = isZh.value ? '仍在處理中，完成後會存入「我的作品」。' : 'Still processing — it will be saved to My Works when done.'
    return
  }

  if (result.success && (result.video_url || result.result_url)) {
    renderTaskResult(result)
    uiStore.showSuccess(t('common.success') || 'Success')
  } else {
    status.value = 'error'
    statusText.value = isZh.value ? '處理失敗' : 'Failed'
    uiStore.showError((result as any).message || (result as any).error || (isZh.value ? '處理失敗' : 'Processing failed'))
  }
}

function gotoPricing() { router.push('/pricing') }
</script>

<template>
  <PiapiPlayground
    :eta-seconds="120"
    :title="isZh ? '影片去背' : 'Video Background Remove'"
    :subtitle="isZh
      ? '上傳影片，AI 自動移除背景並產生具透明通道的影片。Qubico video-toolkit 提供，每幀計費 (~$0.0004/frame)。'
      : 'Upload a video and AI removes the background, returning an alpha-channel MP4. Powered by Qubico video-toolkit (~$0.0004 / frame upstream).'"
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
          <option>Qubico Video Background Remove — {{ isZh ? '影片背景移除' : 'Video Background Removal' }}</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '任務類型 *' : 'Task Type *' }}</label>
        <select class="pp-select" disabled>
          <option>background-remove</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ isZh ? '影片 *' : 'Video *' }}</label>
        <input
          type="file"
          accept="video/mp4"
          class="pp-input"
          @change="handleFileChange"
        />
        <p class="pp-field-help">
          {{ L('MP4 格式 · 最大 20 MB · 10-2000 幀 · 最大 1024×2048。', 'MP4 only · max 20 MB · 10-2000 frames · max 1024×2048.', 'MP4のみ · 最大20MB · 10-2000フレーム · 最大1024×2048。', 'MP4 전용 · 최대 20MB · 10-2000프레임 · 최대 1024×2048.', 'Solo MP4 · máx 20 MB · 10-2000 frames · máx 1024×2048.') }}
        </p>
        <video v-if="videoPreviewUrl" :src="videoPreviewUrl" class="w-full mt-2 rounded-lg" controls />
      </div>

      <div class="flex items-center justify-between">
        <span class="pp-field-label" style="margin-bottom: 0;">{{ isZh ? '反向輸出（返回背景而非主體）' : 'Invert Output (return background instead of subject)' }}</span>
        <label class="cursor-pointer">
          <input type="checkbox" v-model="invertOutput" class="sr-only peer" />
          <div
            class="w-10 h-6 rounded-full transition-colors"
            :style="invertOutput ? 'background: #7c3aed;' : 'background: rgba(255,255,255,0.12);'"
          >
            <div
              class="w-5 h-5 rounded-full transition-transform mt-0.5"
              :style="invertOutput ? 'background: #fff; transform: translateX(1.25rem);' : 'background: #fff; transform: translateX(0.125rem);'"
            ></div>
          </div>
        </label>
      </div>

      <p v-if="isDemoUser" class="pp-field-help" style="color: #fbbf24;">
        {{ isZh ? '訂閱後即可使用此工具。' : 'Subscribe to generate your own results.' }}
        <button @click="gotoPricing" class="underline ml-1">{{ isZh ? '查看方案' : 'View Plans' }} →</button>
      </p>
    </template>

    <template v-if="resultUrl" #result>
      <video :src="resultUrl" class="max-w-full max-h-[520px] rounded-lg" controls />
    </template>

    <template v-if="resultUrl" #result-actions>
      <button
        @click="downloadAsset(resultUrl!, `vidgo_vbg_${Date.now()}.mp4`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >📥 {{ isZh ? '下載' : 'Download' }}</button>
    </template>

    <template #examples>
      <ExampleGallery tool-key="video-bg-remove" />
    </template>
  </PiapiPlayground>
</template>
