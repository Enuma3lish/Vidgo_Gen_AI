<script setup lang="ts">
/**
 * FloorplanToVideo — "floor plan grows into a 3D room" pipeline.
 *
 *   [2D floor plan] → Gemini analysis → 3D render → Kling 3.0/Omni growth
 *   animation (first→last frame) → (optional) Trellis2 interactive 3D model.
 *
 * Backend: POST /api/v1/interior/floorplan-to-video  (streams a 25s heartbeat
 * then the final JSON — axios parses it transparently). The user chooses the
 * result tier (video | video_3d); credits scale with the choice.
 *
 * Layout mirrors ShortVideo.vue (PiapiPlayground: left config / right result).
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUIStore, useCreditsStore } from '@/stores'
import { useLocalized } from '@/composables'
import { toolsApi } from '@/api'
import { interiorApi, type FloorplanTier, type GrowthTier } from '@/api/interior'
import PiapiPlayground from '@/components/tools/PiapiPlayground.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
import ThreeViewer from '@/components/tools/ThreeViewer.vue'
import { extractApiError } from '@/utils/apiError'
import { dataURItoBlob } from '@/utils/dataUri'
import { downloadAsset } from '@/utils/downloadAsset'

const { t, locale } = useI18n()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { L } = useLocalized()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

// ─── State ───────────────────────────────────────────────────────────
const floorplanInput = ref<string | undefined>(undefined)   // data URI from ImageUploader
const styleId = ref<string>('modern_minimalist')
const roomType = ref<string>('living_room')
const resultTier = ref<GrowthTier>('video')
const prompt = ref('')

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const renderImageUrl = ref<string | null>(null)
const videoUrl = ref<string | null>(null)
const modelUrl = ref<string | null>(null)

// ─── Catalogs (styles / room types / tiers) from the backend ─────────
const styles = ref<Array<{ id: string; name: string; name_zh: string }>>([])
const roomTypes = ref<Array<{ id: string; name: string; name_zh: string }>>([])
const tiers = ref<FloorplanTier[]>([])

onMounted(async () => {
  try {
    const opts = await interiorApi.getFloorplanOptions()
    styles.value = opts.styles || []
    roomTypes.value = opts.room_types || []
    tiers.value = opts.tiers || []
  } catch {
    // Non-fatal: fall back to a minimal hardcoded set so the page still works.
    tiers.value = [
      { id: 'video',    name: 'Growth Video',            name_zh: '平面圖長出房間影片', description: '', service_type: 'interior_growth_video',    credits: 800, outputs: [] },
      { id: 'video_3d', name: 'Growth Video + 3D Model', name_zh: '成長影片 + 3D 模型',  description: '', service_type: 'interior_growth_video_3d', credits: 950, outputs: [] },
    ]
  }
})

// ─── Validation + cost ───────────────────────────────────────────────
const disabled = computed(() => !floorplanInput.value)
const isRunning = computed(() => status.value === 'running')

const creditCost = computed(() => {
  const tier = tiers.value.find(tt => tt.id === resultTier.value)
  if (tier) return tier.credits
  return resultTier.value === 'video_3d' ? 950 : 800   // fallback
})

const styleLabel = (s: { name: string; name_zh: string }) => (isZh.value ? s.name_zh : s.name)

// ─── Helpers ─────────────────────────────────────────────────────────
async function ensureFloorplanUrl(): Promise<string | null> {
  if (!floorplanInput.value) return null
  if (!floorplanInput.value.startsWith('data:')) return floorplanInput.value
  const blob = dataURItoBlob(floorplanInput.value)
  if (!blob) return null
  const up = await toolsApi.uploadImage(blob as File)
  return up.url
}

// ─── Generate ────────────────────────────────────────────────────────
async function generate() {
  if (disabled.value || isRunning.value) return
  status.value = 'running'
  statusText.value = isZh.value
    ? (resultTier.value === 'video_3d' ? '生成中… 影片 + 3D 模型約需 10-25 分鐘' : '生成中… Kling 3.0 影片約需 8-20 分鐘')
    : (resultTier.value === 'video_3d' ? 'Generating… video + 3D model, ~10-25 min' : 'Generating… Kling 3.0 video, ~8-20 min')
  renderImageUrl.value = null
  videoUrl.value = null
  modelUrl.value = null

  try {
    const imageUrl = await ensureFloorplanUrl()
    if (!imageUrl) {
      status.value = 'error'
      uiStore.showError(L('平面圖上傳失敗', 'Floor plan upload failed', '間取り図アップロード失敗', '평면도 업로드 실패', 'Subida del plano fallida'))
      return
    }

    const result = await interiorApi.floorplanToVideo({
      image_url: imageUrl,
      style_id: styleId.value,
      room_type: roomType.value,
      prompt: prompt.value.trim() || undefined,
      result_tier: resultTier.value,
      language: isZh.value ? 'zh' : 'en',
    })

    if (result?.success && result.video_url) {
      renderImageUrl.value = result.render_image_url || null
      videoUrl.value = result.video_url
      modelUrl.value = result.model_url || null
      status.value = 'done'
      statusText.value = isZh.value ? '完成' : 'Done'
      if (result.credits_used) creditsStore.deductCredits(result.credits_used)
      // The 3D add-on can soft-fail while the video still succeeds.
      if (resultTier.value === 'video_3d' && !result.model_url) {
        uiStore.showError(isZh.value
          ? '影片已生成，但 3D 模型建立失敗，已退回 3D 部分點數。'
          : 'Video generated, but the 3D model failed — the 3D portion was refunded.')
      } else {
        uiStore.showSuccess(t('common.success') || 'Success')
      }
    } else {
      status.value = 'error'
      statusText.value = isZh.value ? '生成失敗' : 'Failed'
      uiStore.showError(result?.error || (isZh.value ? '生成失敗' : 'Generation failed'))
    }
  } catch (e: any) {
    status.value = 'error'
    statusText.value = isZh.value ? '錯誤' : 'Error'
    uiStore.showError(extractApiError(e, isZh.value ? '生成失敗' : 'Generation failed'))
  }
}

const pageTitle = computed(() => (isZh.value ? '平面圖長出 3D 房間' : 'Floor Plan → 3D Room'))
const pageSubtitle = computed(() => (isZh.value
  ? '上傳 2D 平面圖，AI 分析格局並渲染成 3D 實景，再用 Kling 3.0 生成「拔地而起」的成長動畫。'
  : 'Upload a 2D floor plan; AI analyses the layout, renders a photoreal 3D room, then Kling 3.0 animates it growing up from the plan.'))
</script>

<template>
  <PiapiPlayground
    :eta-seconds="resultTier === 'video_3d' ? 1200 : 720"
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="isZh ? '開始生成' : 'Generate'"
    :generate-label-running="isZh ? '生成中…' : 'Generating…'"
    :disabled="disabled"
    @generate="generate"
  >
    <template #inputs>
      <!-- Floor plan upload -->
      <div>
        <label class="pp-field-label">{{ isZh ? '2D 平面圖 *' : '2D Floor Plan *' }}</label>
        <ImageUploader
          tool-type="room_redesign"
          v-model="floorplanInput"
          :label="isZh ? '點擊或拖放平面圖' : 'Click or drag a floor plan'"
        />
      </div>

      <!-- Result tier — the user's choice of "what do you want?" -->
      <div>
        <label class="pp-field-label">{{ isZh ? '想要的結果 *' : 'What result do you want? *' }}</label>
        <select v-model="resultTier" class="pp-select">
          <option value="video">{{ isZh ? '成長動畫影片 (Kling 3.0)' : 'Growth video (Kling 3.0)' }}</option>
          <option value="video_3d">{{ isZh ? '成長影片 + 可旋轉 3D 模型' : 'Growth video + rotatable 3D model' }}</option>
        </select>
        <p class="pp-field-help">
          {{ resultTier === 'video_3d'
            ? (isZh ? '影片 + Trellis2 3D 模型 (.glb)，可用滑鼠 360° 旋轉檢視。' : 'Video + a Trellis2 .glb model you can rotate 360°.')
            : (isZh ? '平面圖渲染 + Kling 3.0 含音訊的成長動畫影片。' : 'Floor-plan render + Kling 3.0 growth animation with audio.') }}
        </p>
      </div>

      <!-- Style -->
      <div>
        <label class="pp-field-label">{{ isZh ? '設計風格' : 'Design Style' }}</label>
        <select v-model="styleId" class="pp-select">
          <option v-for="s in styles" :key="s.id" :value="s.id">{{ styleLabel(s) }}</option>
        </select>
      </div>

      <!-- Room type -->
      <div>
        <label class="pp-field-label">{{ isZh ? '空間類型' : 'Room Type' }}</label>
        <select v-model="roomType" class="pp-select">
          <option v-for="r in roomTypes" :key="r.id" :value="r.id">{{ styleLabel(r) }}</option>
        </select>
      </div>

      <!-- Optional extra prompt -->
      <div>
        <label class="pp-field-label">{{ isZh ? '補充描述（選填）' : 'Extra description (optional)' }}</label>
        <textarea
          v-model="prompt"
          rows="3"
          maxlength="1000"
          class="pp-textarea"
          :placeholder="isZh ? '例：暖色木地板、大面採光、3.2 米挑高。' : 'e.g. warm wood floor, large windows, 3.2m ceiling.'"
        ></textarea>
        <p class="pp-field-help">{{ isZh ? '影片引擎固定為 Kling 3.0 / Omni（首尾幀生長動畫）。' : 'Video engine is fixed to Kling 3.0 / Omni (first→last-frame growth).' }}</p>
      </div>
    </template>

    <template v-if="videoUrl" #result>
      <div class="flex flex-col gap-3 w-full items-center">
        <video :src="videoUrl" class="max-w-full max-h-[420px] rounded-lg" controls autoplay loop muted />
        <div class="flex flex-wrap gap-3 justify-center w-full">
          <div v-if="renderImageUrl" class="flex flex-col items-center">
            <span class="text-[11px] mb-1" style="color:#94949f;">{{ isZh ? '3D 渲染（結尾幀）' : '3D render (end frame)' }}</span>
            <img :src="renderImageUrl" class="max-h-[200px] rounded-md" style="border:1px solid rgba(124,58,237,0.25);" />
          </div>
          <div v-if="modelUrl" class="flex flex-col items-center">
            <span class="text-[11px] mb-1" style="color:#94949f;">{{ isZh ? '可旋轉 3D 模型' : 'Rotatable 3D model' }}</span>
            <ThreeViewer :model-url="modelUrl" :auto-rotate="true" :width="320" :height="220" />
          </div>
        </div>
      </div>
    </template>

    <template v-if="videoUrl" #result-actions>
      <button
        @click="downloadAsset(videoUrl!, `vidgo_floorplan_${Date.now()}.mp4`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >📥 {{ isZh ? '下載影片' : 'Download video' }}</button>
      <button
        v-if="modelUrl"
        @click="downloadAsset(modelUrl!, `vidgo_model_${Date.now()}.glb`)"
        class="px-3 py-1.5 rounded text-xs font-medium ml-2"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >📦 {{ isZh ? '下載 3D (.glb)' : 'Download 3D (.glb)' }}</button>
      <button
        @click="generate"
        class="px-3 py-1.5 rounded text-xs font-medium ml-2"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >🔄 {{ isZh ? '重新生成' : 'Regenerate' }}</button>
    </template>
  </PiapiPlayground>
</template>
