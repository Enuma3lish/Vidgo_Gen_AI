<script setup lang="ts">
/**
 * RenderEnhancer — improve & upscale architectural renders
 * (mnml.ai/app/render-enhancer parity).
 *
 * Two-stage pipeline built entirely on existing endpoints:
 *   Stage 1 (optional "AI detail enhance"): /api/v1/tools/room-redesign in
 *     'magic' mode with a fixed photoreal-enhancement prompt at low strength
 *     so geometry is preserved while materials/lighting/detail are improved.
 *   Stage 2: /api/v1/tools/upscale (PiAPI image-toolkit super-resolution) to
 *     2x / 4x / 8x.
 * With the enhance toggle off it is a pure upscale. Dedicated single-purpose
 * page per the owner directive (one topic per page).
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized, useGenerationTask } from '@/composables'
import { toolsApi } from '@/api'
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
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { L } = useLocalized()
const { isDemoUser } = useDemoMode()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

const imageInput = ref<string | undefined>(undefined)
const scale = ref<2 | 4>(2)
const aiEnhance = ref<boolean>(true)
const creativity = ref<number>(0.45) // maps to room-redesign styleStrength

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)

const disabled = computed(() => !imageInput.value)
// Credit cost comes from the backend ServicePricing API (GET /credits/pricing)
// via the credits store — never hardcoded. The whole operation is ONE billed
// call now: render_enhance (20) with AI enhance on, image_upscale (3) for a
// plain upscale. The numbers here are only pre-fetch fallbacks. (P0-1: the old
// 35/15 display never matched the real two-call deduction of 23/3.)
const creditCost = computed(() =>
  creditsStore.getServiceCost(aiEnhance.value ? 'render_enhance' : 'image_upscale', aiEnhance.value ? 20 : 3))

// P0-2: single source of truth for the in-flight task — recovers on timeout
// (background poll) and on page refresh (resume()).
const task = useGenerationTask('render_enhance')
function renderTaskResult(r: any) {
  if (r && r.success && (r.image_url || r.result_url)) {
    resultUrl.value = r.image_url || r.result_url || null
    status.value = 'done'
    statusText.value = L('完成', 'Done', '完了', '완료', 'Listo')
    if (r.credits_used) creditsStore.deductCredits(r.credits_used)
  }
}
watch(() => task.result.value, (r) => renderTaskResult(r))
watch(() => task.phase.value, (p) => {
  if (p === 'error') {
    status.value = 'error'
    uiStore.showError(task.error.value || (isZh.value ? '處理失敗' : 'Processing failed'))
  }
})
onMounted(() => {
  creditsStore.ensurePricing()
  if (task.resume()) {
    status.value = 'running'
    statusText.value = L('正在恢復先前的處理…', 'Resuming your previous job…', '前回の処理を復元中…', '이전 작업을 복구하는 중…', 'Reanudando tu trabajo…')
  }
})
const disabledReason = computed(() => disabled.value
  ? L('請先上傳要優化的渲染圖。', 'Upload the render you want to enhance first.', '高画質化するレンダーをアップロードしてください。', '향상할 렌더를 먼저 업로드하세요.', 'Sube primero el render que quieres mejorar.')
  : '')
// Two-stage (enhance + upscale) takes longer than a plain upscale — reflect
// that so the wait doesn't feel like a hang.
const etaLabel = computed(() => aiEnhance.value
  ? L('預計約 60–120 秒（增強＋放大）', 'Usually ~60–120s (enhance + upscale)', '約60〜120秒（強化＋拡大）', '약 60~120초 (향상＋확대)', '~60–120 s (mejora + ampliación)')
  : L('預計約 20–40 秒', 'Usually ~20–40s', '約20〜40秒', '약 20~40초', '~20–40 s'))

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
  resultUrl.value = null

  // Upload BEFORE the task wrapper so the upload isn't tagged with the
  // generation's client_task_id.
  const workingUrl = await ensureImageUrl()
  if (!workingUrl) { status.value = 'error'; uiStore.showError(L('圖片上傳失敗', 'Image upload failed', '画像アップロード失敗', '이미지 업로드 실패', 'Subida fallida')); return }

  // Single billed call: backend runs enhance (optional) + upscale and
  // charges ONCE (render_enhance 20 / image_upscale 3) — display == deduction.
  statusText.value = aiEnhance.value
    ? L('AI 細節增強 + 放大中…', 'Enhancing + upscaling…', 'ディテール強化＋拡大中…', '디테일 향상＋업스케일 중…', 'Mejorando y ampliando…')
    : L(`放大 ${scale.value}x 中…`, `Upscaling ${scale.value}x…`, `${scale.value}x拡大中…`, `${scale.value}x 업스케일 중…`, `Ampliando ${scale.value}x…`)

  let result: any
  try {
    result = await task.run((cid) => toolsApi.renderEnhance({
      imageUrl: workingUrl,
      scale: scale.value,
      aiEnhance: aiEnhance.value,
      creativity: creativity.value,
    }, cid))
  } catch (e: any) {
    status.value = 'error'
    uiStore.showError(extractApiError(e, isZh.value ? '處理失敗' : 'Processing failed'))
    return
  }

  if (result === null) {
    // Timed out client-side but backend still running — DON'T error.
    status.value = 'running'
    statusText.value = L('仍在處理中，完成後會存入「我的作品」。', 'Still processing — it will be saved to My Works when done.', '処理中です。完了後「マイ作品」に保存されます。', '처리 중입니다. 완료되면 내 작품에 저장됩니다.', 'Procesando; se guardará en Mis Trabajos.')
    return
  }

  if (handleCardRequired(result, uiStore, router, isZh.value)) { status.value = 'idle'; statusText.value = ''; return }
  if (result.success && (result.image_url || result.result_url)) {
    renderTaskResult(result)
    uiStore.showSuccess(t('common.success') || 'Success')
  } else {
    status.value = 'error'
    uiStore.showError((result as any).message || (result as any).error || (isZh.value ? '處理失敗' : 'Processing failed'))
  }
}

function gotoPricing() { router.push('/pricing') }
</script>

<template>
  <PiapiPlayground
    :eta-seconds="60"
    :title="L('渲染圖優化放大', 'Render Enhancer', 'レンダー高画質化', '렌더 향상', 'Mejora de renders')"
    :subtitle="L(
      '上傳低品質渲染（Lumion / Enscape / V-Ray / SketchUp 等），AI 提升細節並放大至高解析度。',
      'Upload a low-quality render (Lumion / Enscape / V-Ray / SketchUp …) — AI adds detail and upscales to high resolution.',
      '低品質レンダー（Lumion / Enscape / V-Ray / SketchUp 等）をアップロード、AIがディテールを強化し高解像度化。',
      '저품질 렌더(Lumion / Enscape / V-Ray / SketchUp 등)를 올리면 AI가 디테일을 더하고 고해상도로 확대합니다.',
      'Sube un render de baja calidad (Lumion / Enscape / V-Ray / SketchUp…); la IA añade detalle y lo amplía.')"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="L('開始優化', 'Enhance', '高画質化', '향상', 'Mejorar')"
    :generate-label-running="L('處理中…', 'Processing…', '処理中…', '처리 중…', 'Procesando…')"
    :disabled="disabled || isDemoUser"
    :disabled-reason="disabledReason"
    :eta-label="etaLabel"
    :empty-hint="L('上傳渲染圖後，優化結果會顯示在這裡。', 'Upload a render — the enhanced result will appear here.', 'レンダーをアップロードすると、ここに結果が表示されます。', '렌더를 올리면 향상된 결과가 여기에 표시됩니다.', 'Sube un render; el resultado mejorado aparecerá aquí.')"
    @generate="generate"
  >
    <template #inputs>
      <div>
        <label class="pp-field-label">{{ L('渲染圖 *', 'Render image *', 'レンダー画像 *', '렌더 이미지 *', 'Render *') }}</label>
        <ImageUploader
          tool-type="upscale"
          v-model="imageInput"
          :label="L('點擊或拖放 JPG / PNG（最大 2048×2048）', 'Click or drag JPG / PNG (max 2048×2048)', 'クリックまたはドロップ', '클릭 또는 드롭', 'Haz clic o arrastra')"
        />
        <p class="pp-field-help">{{ L('支援 Lumion / Enscape / V-Ray / SketchUp 等輸出的渲染圖。最大 2048×2048。', 'Works with renders from Lumion / Enscape / V-Ray / SketchUp, etc. Max 2048×2048.', 'Lumion / Enscape / V-Ray / SketchUp などのレンダーに対応。最大 2048×2048。', 'Lumion / Enscape / V-Ray / SketchUp 등의 렌더 지원. 최대 2048×2048.', 'Compatible con renders de Lumion / Enscape / V-Ray / SketchUp, etc. Máx. 2048×2048.') }}</p>
      </div>

      <div>
        <label class="pp-field-label flex items-center justify-between">
          <span>{{ L('AI 細節增強', 'AI Detail Enhance', 'AIディテール強化', 'AI 디테일 향상', 'Mejora de detalle IA') }}</span>
          <input type="checkbox" v-model="aiEnhance" style="accent-color:#a78bfa; width:16px; height:16px;" />
        </label>
        <p class="pp-field-help">{{ L('保留結構，提升材質、光影與細節真實感（關閉則只做放大）。', 'Preserves geometry while improving materials, lighting and realism (off = upscale only).', '構造を保持しつつ材質・光・リアルさを向上（オフは拡大のみ）。', '구조를 유지하며 재질·조명·사실감 향상 (끄면 확대만).', 'Conserva la geometría y mejora materiales e iluminación (off = solo ampliar).') }}</p>
      </div>

      <div v-if="aiEnhance">
        <label class="pp-field-label">{{ L('創意程度', 'Creativity', '創造性', '창의성', 'Creatividad') }}
          <span class="ml-2" style="color:#a78bfa">{{ Math.round(creativity * 100) }}%</span>
        </label>
        <input type="range" min="0.2" max="0.7" step="0.05" v-model.number="creativity" class="w-full" style="accent-color:#a78bfa" />
        <p class="pp-field-help">{{ L('越低越貼近原圖，越高 AI 重繪越多。', 'Lower stays faithful to the source; higher lets AI repaint more.', '低いほど忠実、高いほどAIが描き直す。', '낮을수록 원본 충실, 높을수록 AI가 더 다시 그림.', 'Menor = más fiel; mayor = más repintado por IA.') }}</p>
      </div>

      <div>
        <label class="pp-field-label">{{ L('放大倍率', 'Upscale', '拡大倍率', '확대 배율', 'Ampliación') }}</label>
        <div class="grid grid-cols-2 gap-1.5">
          <button v-for="opt in [2, 4] as const" :key="opt" type="button" @click="scale = opt"
            class="py-2 rounded-lg text-xs font-medium transition-colors"
            :style="scale === opt
              ? 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color:#fff;'
              : 'background:#0a0a0f; color:#94949f; border:1px solid rgba(255,255,255,0.08);'"
          >{{ opt }}x</button>
        </div>
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
        :before-label="L('原始', 'Before', 'オリジナル', '원본', 'Antes')"
        :after-label="L('優化後', 'Enhanced', '高画質化後', '향상 후', 'Mejorado')"
      />
      <img v-else :src="resultUrl" alt="Enhanced" class="max-w-full max-h-[520px] object-contain rounded-lg" />
    </template>

    <template v-if="resultUrl" #result-actions>
      <button @click="downloadAsset(resultUrl!, `vidgo_render_enhanced_${scale}x_${Date.now()}.png`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
      >📥 {{ L('下載', 'Download', 'ダウンロード', '다운로드', 'Descargar') }}</button>
    </template>

    <template #examples>
      <ExampleGallery tool-key="image-upscale" />
    </template>
  </PiapiPlayground>
</template>
