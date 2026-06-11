<script setup lang="ts">
/**
 * Isometric (立體圖) — isometric 3D "dollhouse" view from an uploaded image.
 *
 * Backend: POST /api/v1/interior/isometric (reuses render_from_floorplan, whose
 * prompt yields a 45° isometric interior visualization). service_type
 * interior_isometric (25 credits).
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useLocalized } from '@/composables'
import { toolsApi } from '@/api'
import { interiorApi, type DesignStyle, type RoomType } from '@/api/interior'
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
const styleId = ref('')
const roomType = ref('')
const customPrompt = ref('')

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)

const styles = ref<DesignStyle[]>([])
const roomTypes = ref<RoomType[]>([])
onMounted(async () => {
  try {
    styles.value = await interiorApi.getStyles()
    roomTypes.value = await interiorApi.getRoomTypes()
  } catch (e) {
    console.warn('[isometric] failed to load styles/room types:', e)
  }
})
const label = (s: { name: string; name_zh: string }) => (isZh.value ? s.name_zh : s.name)

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
      style_id: styleId.value || undefined,
      room_type: roomType.value || undefined,
      prompt: customPrompt.value.trim() || undefined,
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
      '上傳平面圖或空間照片,AI 生成 45° 等角立體圖(dollhouse 視角)。',
      'Upload a floor plan or room image — AI generates a 45° isometric 3D view (dollhouse).',
      '間取り図や空間写真をアップロードすると、AIが45°アイソメ立体図(ドールハウス)を生成します。',
      '평면도나 공간 사진을 올리면 AI가 45° 아이소메트릭 입체도(돌하우스)를 생성합니다.',
      'Sube un plano o foto del espacio; la IA genera una vista isométrica 3D de 45° (casa de muñecas).')"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="L('開始生成', 'Generate', '生成', '생성', 'Generar')"
    :generate-label-running="L('生成中…', 'Generating…', '生成中…', '생성 중…', 'Generando…')"
    :disabled="disabled"
    :disabled-reason="disabled ? L('請先上傳圖片。', 'Upload an image first.', '画像をアップロードしてください。', '이미지를 먼저 업로드하세요.', 'Sube primero una imagen.') : ''"
    :empty-hint="L('上傳圖片,立體圖會顯示在這裡。', 'Upload an image — your isometric view appears here.', '画像をアップロードすると、ここに立体図が表示されます。', '이미지를 올리면 여기에 입체도가 표시됩니다.', 'Sube una imagen; la vista isométrica aparecerá aquí.')"
    @generate="generate"
  >
    <template #inputs>
      <div>
        <label class="pp-field-label">{{ L('來源圖片 *', 'Source image *', '元画像 *', '원본 이미지 *', 'Imagen de origen *') }}</label>
        <ImageUploader
          tool-type="room_redesign"
          v-model="imageInput"
          :label="L('點擊或拖放平面圖', 'Click or drag a floor plan', 'クリックまたはドロップ', '클릭 또는 드롭', 'Haz clic o arrastra')"
        />
      </div>

      <div>
        <label class="pp-field-label">{{ L('設計風格（選填）', 'Design style (optional)', 'スタイル（任意）', '스타일 (선택)', 'Estilo (opcional)') }}</label>
        <select v-model="styleId" class="pp-select">
          <option value="">{{ L('— 預設 —', '— Default —', '— 既定 —', '— 기본 —', '— Predeterminado —') }}</option>
          <option v-for="s in styles" :key="s.id" :value="s.id">{{ label(s) }}</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ L('空間類型（選填）', 'Room type (optional)', '部屋タイプ（任意）', '공간 유형 (선택)', 'Tipo de habitación (opcional)') }}</label>
        <select v-model="roomType" class="pp-select">
          <option value="">{{ L('— 自動 —', '— Auto —', '— 自動 —', '— 자동 —', '— Auto —') }}</option>
          <option v-for="r in roomTypes" :key="r.id" :value="r.id">{{ label(r) }}</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ L('補充描述（選填）', 'Description (optional)', '説明（任意）', '설명 (선택)', 'Descripción (opcional)') }}</label>
        <textarea v-model="customPrompt" rows="3" maxlength="1000" class="pp-select" style="resize:vertical;"
          :placeholder="L('例：暖色木地板、大面採光。', 'e.g. warm wood floor, large windows.', '例：暖色の木製床、大きな窓。', '예: 따뜻한 원목 바닥, 큰 창.', 'p. ej.: suelo de madera cálido, ventanales.')"></textarea>
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
