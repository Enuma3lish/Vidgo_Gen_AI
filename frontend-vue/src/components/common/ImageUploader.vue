<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
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
const isDragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const rule = computed(() => imageDimensionRuleForTool(props.toolType))

function triggerUpload() {
  fileInput.value?.click()
}

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
    uploadError.value = isZh
      ? `不支援的圖片格式（${file.type || '未知'}），請改用 ${ALLOWED_IMAGE_EXT_LABEL} 格式重新上傳。`
      : `Unsupported image format (${file.type || 'unknown'}). Please re-upload as ${ALLOWED_IMAGE_EXT_LABEL}.`
    return false
  }

  let uploadFile = file
  try {
    uploadFile = await normalizeImageFileForUpload(file, rule.value, { maxSizeMb: MAX_IMAGE_SIZE_MB })
  } catch (error: any) {
    uploadError.value = isZh
      ? '無法處理圖片尺寸或壓縮，請改用 JPG / PNG / WebP 重新上傳。'
      : (error?.message || 'Image could not be resized or compressed. Please re-upload as JPG, PNG, or WebP.')
    return false
  }

  if (uploadFile.size > MAX_SIZE_BYTES) {
    uploadError.value = isZh
      ? `圖片壓縮後仍超過 ${MAX_IMAGE_SIZE_MB}MB，請改用 ${ALLOWED_IMAGE_EXT_LABEL} 格式重新上傳。`
      : `Image is still over ${MAX_IMAGE_SIZE_MB}MB after compression. Please re-upload as ${ALLOWED_IMAGE_EXT_LABEL}.`
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
  <div
    class="relative rounded-xl border-2 border-dashed transition-all cursor-pointer overflow-hidden group"
    :class="[
      isDragging ? 'border-primary-500 bg-primary-500/10' : 'border-gray-600 hover:border-gray-500 bg-dark-700',
      height
    ]"
    @click="triggerUpload"
    @dragover.prevent="isDragging = true"
    @dragleave.prevent="isDragging = false"
    @drop.prevent="handleDrop"
  >
    <input
      ref="fileInput"
      type="file"
      accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
      class="hidden"
      @change="handleFile"
    />

    <!-- Preview -->
    <div v-if="modelValue" class="absolute inset-0">
      <img :src="modelValue" class="w-full h-full object-contain" alt="Preview" />
      <div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
        <span class="text-white font-medium">{{ isZh ? '更換圖片' : 'Change Image' }}</span>
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
        {{ label || (isZh ? '點擊或拖放圖片' : 'Click or drop image here') }}
      </p>
      <p class="text-xs text-gray-500 mt-1">
        JPG, PNG, WebP · {{ isZh ? '自動調整尺寸與壓縮' : 'auto resize and compression' }}
      </p>
    </div>

    <!-- Error message -->
    <div v-if="uploadError" class="absolute bottom-2 left-2 right-2 bg-red-500/90 text-white text-xs font-medium rounded-lg px-3 py-2 text-center">
      {{ uploadError }}
    </div>
  </div>
</template>
