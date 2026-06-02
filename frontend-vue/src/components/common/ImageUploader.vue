<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useLocalized } from '@/composables'
import {
  imageDimensionRuleForTool,
  isAllowedImageFile,
  normalizeImageFileForUpload,
  ALLOWED_IMAGE_EXT_LABEL,
  MAX_IMAGE_SIZE_MB,
} from '@/utils/mediaValidation'

const props = defineProps({
  modelValue: {
    type: String,
    default: null
  },
  label: {
    type: String,
    default: ''
  },
  height: {
    type: String,
    default: 'h-64'
  },
  // Optional tool slug (e.g. "ai_avatar", "room_redesign", "try_on") so
  // the uploader can apply the same per-tool dimension/aspect rules that
  // the backend `/api/v1/demo/upload` validator enforces. When omitted we
  // fall back to the common rule.
  toolType: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue', 'file-selected'])
const { locale } = useI18n()
const isZh = locale.value.startsWith('zh')
// 5-language inline picker — fixes ja/ko/es fall-through (BUG-017).
const { L } = useLocalized()
const isDragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

// Unique id per instance so the parent <label for=...> targets the correct
// input even when multiple uploaders coexist on the same page.
const inputId = `vidgo-uploader-${Math.random().toString(36).slice(2, 11)}`

const rule = computed(() => imageDimensionRuleForTool(props.toolType))

async function handleFile(event: Event) {
  const target = event.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    if (!(await processFile(target.files[0]))) {
      target.value = ''
    }
  }
}

async function handleDrop(event: DragEvent) {
  isDragging.value = false
  if (event.dataTransfer?.files && event.dataTransfer.files.length > 0) {
    await processFile(event.dataTransfer.files[0])
  }
}

const MAX_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
const uploadError = ref('')

async function processFile(file: File): Promise<boolean> {
  uploadError.value = ''

  if (!isAllowedImageFile(file)) {
    const unknown = L('未知', 'unknown', '不明', '알 수 없음', 'desconocido')
    uploadError.value = L(
      `不支援的圖片格式（${file.type || unknown}），請改用 ${ALLOWED_IMAGE_EXT_LABEL} 格式重新上傳。`,
      `Unsupported image format (${file.type || unknown}). Please re-upload as ${ALLOWED_IMAGE_EXT_LABEL}.`,
      `対応していない画像形式（${file.type || unknown}）です。${ALLOWED_IMAGE_EXT_LABEL} 形式で再アップロードしてください。`,
      `지원하지 않는 이미지 형식(${file.type || unknown})입니다. ${ALLOWED_IMAGE_EXT_LABEL} 형식으로 다시 업로드해 주세요.`,
      `Formato de imagen no compatible (${file.type || unknown}). Vuelve a subirla como ${ALLOWED_IMAGE_EXT_LABEL}.`,
    )
    return false
  }

  let uploadFile = file
  try {
    uploadFile = await normalizeImageFileForUpload(file, rule.value, { maxSizeMb: MAX_IMAGE_SIZE_MB })
  } catch (error: any) {
    uploadError.value = L(
      '無法處理圖片尺寸或壓縮，請改用 JPG / PNG / WebP 重新上傳。',
      error?.message || 'Image could not be resized or compressed. Please re-upload as JPG, PNG, or WebP.',
      '画像のサイズ変更または圧縮に失敗しました。JPG / PNG / WebP で再アップロードしてください。',
      '이미지 크기 조정 또는 압축에 실패했습니다. JPG / PNG / WebP 형식으로 다시 업로드해 주세요.',
      'No se pudo redimensionar o comprimir la imagen. Vuelve a subirla como JPG, PNG o WebP.',
    )
    return false
  }

  if (uploadFile.size > MAX_SIZE_BYTES) {
    uploadError.value = L(
      `圖片壓縮後仍超過 ${MAX_IMAGE_SIZE_MB}MB，請改用 ${ALLOWED_IMAGE_EXT_LABEL} 格式重新上傳。`,
      `Image is still over ${MAX_IMAGE_SIZE_MB}MB after compression. Please re-upload as ${ALLOWED_IMAGE_EXT_LABEL}.`,
      `圧縮後も ${MAX_IMAGE_SIZE_MB}MB を超えています。${ALLOWED_IMAGE_EXT_LABEL} 形式で再アップロードしてください。`,
      `압축 후에도 ${MAX_IMAGE_SIZE_MB}MB를 초과합니다. ${ALLOWED_IMAGE_EXT_LABEL} 형식으로 다시 업로드해 주세요.`,
      `La imagen sigue superando ${MAX_IMAGE_SIZE_MB}MB tras la compresión. Vuelve a subirla como ${ALLOWED_IMAGE_EXT_LABEL}.`,
    )
    return false
  }

  const reader = new FileReader()
  reader.onload = (e) => {
    const result = e.target?.result as string
    emit('update:modelValue', result)
    emit('file-selected', uploadFile)
  }
  reader.readAsDataURL(uploadFile)
  return true
}
</script>

<template>
  <!-- Use a <label> as the click target so the browser natively forwards
       the tap to the hidden file input. iOS Safari and several mobile
       browsers refuse to open the OS file picker when triggered by a
       programmatic `.click()` on a `display:none` input — wrapping with
       `<label for=fileInput>` (or wrapping the input inside the label)
       fixes the issue without any JS click forwarding. -->
  <label
    :for="inputId"
    class="relative rounded-xl border-2 border-dashed transition-all cursor-pointer overflow-hidden group block"
    :class="[
      isDragging ? 'border-primary-500 bg-primary-500/10' : 'border-gray-600 hover:border-gray-500 bg-dark-700',
      height
    ]"
    @dragover.prevent="isDragging = true"
    @dragleave.prevent="isDragging = false"
    @drop.prevent="handleDrop"
  >
    <!-- Visually hidden but still receives the native click forwarded by
         the parent <label>. `display:none` breaks the forward on iOS Safari,
         so use the opacity / position pattern instead. -->
    <input
      :id="inputId"
      ref="fileInput"
      type="file"
      accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
      class="absolute inset-0 w-px h-px opacity-0 pointer-events-none"
      @change="handleFile"
    />

    <!-- Preview -->
    <div v-if="modelValue" class="absolute inset-0">
      <img :src="modelValue" class="w-full h-full object-contain" alt="Preview" />
      <div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
        <span class="text-white font-medium">{{ L('更換圖片', 'Change Image', '画像を変更', '이미지 변경', 'Cambiar imagen') }}</span>
      </div>
    </div>

    <!-- Upload Placeholder -->
    <div v-else class="absolute inset-0 flex flex-col items-center justify-center text-gray-400">
      <div class="w-12 h-12 mb-3 rounded-full bg-dark-600 flex items-center justify-center group-hover:bg-dark-500 transition-colors">
        <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
      </div>
      <p class="font-medium text-center px-4">
        {{ label || L('點擊或拖放圖片', 'Click or drop image here', 'クリックまたは画像をドロップ', '클릭 또는 이미지 드롭', 'Toca o arrastra una imagen') }}
      </p>
      <p class="text-xs text-gray-500 mt-1">
        JPG, PNG, WebP · {{ L('自動調整尺寸與壓縮', 'auto resize and compression', '自動リサイズ＆圧縮', '자동 리사이즈 및 압축', 'redimensión y compresión automáticas') }}
      </p>
    </div>

    <!-- Error message -->
    <div v-if="uploadError" class="absolute bottom-2 left-2 right-2 bg-red-500/90 text-white text-xs font-medium rounded-lg px-3 py-2 text-center">
      {{ uploadError }}
    </div>
  </label>
</template>
