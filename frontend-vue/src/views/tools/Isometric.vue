<script setup lang="ts">
/**
 * Isometric (立體圖) — one-click 45° dollhouse view from an uploaded floor plan.
 *
 * UX simplified 2026-06-14 (owner request "Isometric just lets the floor plan
 * become more 3D"): the only input is the floor-plan upload. Style / room /
 * atmosphere / free prompt were removed — the backend
 * render_from_floorplan() prompt already locks the result to the plan's
 * layout, so the previous knobs were noise.
 *
 * Backend: POST /api/v1/interior/isometric (25 credits).
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useLocalized } from '@/composables'
import { toolsApi } from '@/api'
import { interiorApi } from '@/api/interior'
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
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

const imageInput = ref<string | undefined>(undefined)

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)

const creditCost = computed(() => 25)
const disabled = computed(() => !imageInput.value)

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
  statusText.value = L('生成中… 約 30–90 秒', 'Generating… ~30–90s', '生成中… 約30〜90秒', '생성 중… 약 30~90초', 'Generando… ~30–90 s')
  resultUrl.value = null
  try {
    const url = await ensureImageUrl()
    if (!url) { status.value = 'error'; uiStore.showError(L('圖片上傳失敗', 'Image upload failed', '画像アップロード失敗', '이미지 업로드 실패', 'Subida fallida')); return }
    const result = await interiorApi.isometric({
      image_url: url,
      language: isZh.value ? 'zh' : 'en',
    })
    if (handleCardRequired(result, uiStore, router, isZh.value)) {
      status.value = 'idle'; statusText.value = ''; return
    }
    if (result.success && result.image_url) {
      const u = result.image_url
      resultUrl.value = u.startsWith('http') ? u : `${window.location.origin}${u}`
      status.value = 'done'
      statusText.value = L('完成', 'Done', '完了', '완료', 'Listo')
      if (result.credits_used) creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success') || 'Success')
    } else {
      status.value = 'error'
      uiStore.showError((result as any).message || (result as any).error || (isZh.value ? '生成失敗' : 'Generation failed'))
    }
  } catch (e: any) {
    status.value = 'error'
    uiStore.showError(extractApiError(e, isZh.value ? '生成失敗' : 'Generation failed'))
  }
}
</script>

<template>
  <PiapiPlayground
    :eta-seconds="60"
    :title="L('立體圖', 'Isometric View', '立体図', '입체도', 'Vista isométrica')"
    :subtitle="L(
      '上傳平面配置圖,AI 一鍵生成整個空間的 45° 等角立體圖(dollhouse 視角) — 每個房間都會依用途呈現,結構完全照原圖。',
      'Upload a floor plan — AI generates a 45° isometric dollhouse view of the WHOLE unit in one click; layout and rooms stay faithful to the source.',
      '間取り図をアップロードすると、AIが45°アイソメ立体図(ドールハウス)を1クリックで生成。元の構造を忠実に再現します。',
      '평면도를 올리면 AI가 45° 아이소메트릭 입체도(돌하우스)를 한 번에 생성합니다. 원본 구조를 그대로 유지합니다.',
      'Sube un plano; la IA genera con un clic una vista isométrica de 45° (casa de muñecas) fiel al diseño original.')"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="L('開始生成', 'Generate', '生成', '생성', 'Generar')"
    :generate-label-running="L('生成中…', 'Generating…', '生成中…', '생성 중…', 'Generando…')"
    :disabled="disabled"
    :disabled-reason="disabled ? L('請先上傳平面圖。', 'Upload a floor plan first.', '間取り図をアップロードしてください。', '평면도를 먼저 업로드하세요.', 'Sube primero el plano.') : ''"
    :empty-hint="L('上傳平面圖,立體圖會顯示在這裡。', 'Upload a floor plan — your isometric view appears here.', '間取り図をアップロードすると、ここに立体図が表示されます。', '평면도를 올리면 여기에 입체도가 표시됩니다.', 'Sube un plano; la vista isométrica aparecerá aquí.')"
    @generate="generate"
  >
    <template #inputs>
      <div>
        <label class="pp-field-label">{{ L('平面配置圖 *', 'Floor plan *', '間取り図 *', '평면도 *', 'Plano *') }}</label>
        <ImageUploader
          tool-type="room_redesign"
          v-model="imageInput"
          :label="L('點擊或拖放平面圖', 'Click or drag a floor plan', 'クリックまたはドロップ', '클릭 또는 드롭', 'Haz clic o arrastra')"
        />
        <p class="pp-field-help">{{ L('一鍵生成 — 不需要其他設定。平面圖上的房間、牆與家具配置都會原樣保留。', 'One-click — no other settings needed. Rooms, walls and furniture from the plan are kept as-is.', '1クリックで生成 — 他の設定は不要。間取り図の部屋・壁・家具配置はそのまま保持されます。', '한 번의 클릭으로 생성 — 다른 설정은 필요 없습니다. 평면도의 방·벽·가구 배치가 그대로 유지됩니다.', 'Un clic — sin más ajustes. Habitaciones, muros y muebles del plano se mantienen.') }}</p>
      </div>
    </template>

    <template v-if="resultUrl" #result>
      <BeforeAfterSlider
        v-if="imageInput"
        :before-image="imageInput"
        :after-image="resultUrl"
        :before-label="L('平面圖', 'Plan', '間取り図', '평면도', 'Plano')"
        :after-label="L('立體圖', 'Isometric', '立体図', '입체도', 'Isométrica')"
      />
      <img v-else :src="resultUrl" alt="Isometric" class="max-w-full max-h-[520px] object-contain rounded-lg" />
    </template>

    <template v-if="resultUrl" #result-actions>
      <button @click="downloadAsset(resultUrl!, `vidgo_isometric_${Date.now()}.png`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
      >📥 {{ L('下載', 'Download', 'ダウンロード', '다운로드', 'Descargar') }}</button>
    </template>

    <template #examples>
      <ExampleGallery tool-key="isometric" />
    </template>
  </PiapiPlayground>
</template>
