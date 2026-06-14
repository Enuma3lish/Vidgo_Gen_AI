<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useLocalized } from '@/composables'
import { commonImageDimensionRule, isAllowedImageFile, normalizeImageFileForUpload } from '@/utils/mediaValidation'

const { t } = useI18n()
// 5-language inline picker — fixes ja/ko/es fall-through (BUG-017).
const { L } = useLocalized()

const props = defineProps<{
  accept?: string
  multiple?: boolean
  maxSize?: number
}>()

const emit = defineEmits<{
  (e: 'files', files: File[]): void
  (e: 'files-selected', files: File[]): void
  (e: 'error', message: string): void
}>()

const isDragging = ref(false)
const inputRef = ref<HTMLInputElement | null>(null)

function handleDragOver(e: DragEvent) {
  e.preventDefault()
  isDragging.value = true
}

function handleDragLeave() {
  isDragging.value = false
}

async function handleDrop(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false

  const files = e.dataTransfer?.files
  if (files) {
    await processFiles(Array.from(files))
  }
}

async function handleFileSelect(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files) {
    if (!(await processFiles(Array.from(target.files)))) {
      target.value = ''
    }
  }
}

const AI_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const AI_VIDEO_TYPES = ['video/mp4', 'video/webm', 'video/quicktime']

function allowedTypes() {
  const accept = props.accept || '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp'
  if (accept.includes('video')) return AI_VIDEO_TYPES
  return AI_IMAGE_TYPES
}

async function processFiles(files: File[]): Promise<boolean> {
  const maxSize = props.maxSize || 20 * 1024 * 1024
  const allowed = allowedTypes()
  const mb = maxSize / 1024 / 1024
  const validFiles: File[] = []

  for (const file of files) {
    if (allowed === AI_IMAGE_TYPES ? !isAllowedImageFile(file) : !allowed.includes(file.type)) {
      const label = allowed === AI_VIDEO_TYPES
        ? L('MP4、WebM 或 MOV 影片', 'MP4, WebM, or MOV video', 'MP4、WebMまたはMOV動画', 'MP4, WebM 또는 MOV 동영상', 'Video MP4, WebM o MOV')
        : L('JPG、PNG 或 WebP 圖片', 'JPG, PNG, or WebP image', 'JPG、PNGまたはWebP画像', 'JPG, PNG 또는 WebP 이미지', 'Imagen JPG, PNG o WebP')
      emit('error', L(
        `檔案 ${file.name} 不支援，請選擇 ${label}。`,
        `File ${file.name} is not supported. Please choose a ${label}.`,
        `ファイル ${file.name} はサポートされていません。${label} を選択してください。`,
        `${file.name} 파일은 지원되지 않습니다. ${label}을(를) 선택해 주세요.`,
        `El archivo ${file.name} no es compatible. Elige ${label}.`,
      ))
      continue
    }
    if (allowed === AI_VIDEO_TYPES && file.size > maxSize) {
      emit('error', L(
        `檔案 ${file.name} 超過 ${mb}MB，請選擇較小的檔案。`,
        `File ${file.name} exceeds maximum size of ${mb}MB. Please choose a smaller file.`,
        `ファイル ${file.name} は ${mb}MB を超えています。より小さいファイルを選択してください。`,
        `${file.name} 파일이 ${mb}MB를 초과합니다. 더 작은 파일을 선택해 주세요.`,
        `El archivo ${file.name} supera ${mb}MB. Elige uno más pequeño.`,
      ))
      continue
    }
    let uploadFile = file
    if (allowed === AI_IMAGE_TYPES) {
      try {
        uploadFile = await normalizeImageFileForUpload(file, commonImageDimensionRule, { maxSizeMb: mb })
      } catch {
        emit('error', L('無法處理圖片尺寸或壓縮，請重新選擇圖片。', 'Image could not be resized or compressed. Please choose a different image.', '画像のリサイズまたは圧縮ができません。別の画像を選んでください。', '이미지 리사이즈 또는 압축에 실패했습니다. 다른 이미지를 선택해 주세요.', 'No se pudo redimensionar o comprimir. Elige otra imagen.'))
        continue
      }
      if (uploadFile.size > maxSize) {
        emit('error', L(
          `圖片 ${file.name} 壓縮後仍超過 ${mb}MB，請選擇其他圖片。`,
          `Image ${file.name} is still over ${mb}MB after compression. Please choose a different image.`,
          `画像 ${file.name} は圧縮後も ${mb}MB を超えています。別の画像を選択してください。`,
          `이미지 ${file.name}이(가) 압축 후에도 ${mb}MB를 초과합니다. 다른 이미지를 선택해 주세요.`,
          `La imagen ${file.name} sigue superando ${mb}MB tras la compresión. Elige otra.`,
        ))
        continue
      }
    }
    validFiles.push(uploadFile)
  }

  if (validFiles.length > 0) {
    const payload = props.multiple ? validFiles : [validFiles[0]]
    emit('files', payload)
    emit('files-selected', payload)
    return true
  }
  return false
}

function triggerFileSelect() {
  inputRef.value?.click()
}
</script>

<template>
  <div
    @dragover="handleDragOver"
    @dragleave="handleDragLeave"
    @drop="handleDrop"
    @click="triggerFileSelect"
    class="relative border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-200"
    :class="[
      isDragging
        ? 'border-primary-500 bg-primary-500/10'
        : 'border-gray-200 hover:border-blue-400/50 hover:bg-blue-50/30'
    ]"
  >
    <input
      ref="inputRef"
      type="file"
      :accept="accept || '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp'"
      :multiple="multiple"
      class="hidden"
      @change="handleFileSelect"
    />

    <div class="flex flex-col items-center gap-4">
      <!-- Icon -->
      <div class="w-16 h-16 rounded-2xl bg-primary-500/10 flex items-center justify-center">
        <svg class="w-8 h-8 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
      </div>

      <!-- Text -->
      <div>
        <p class="text-white font-medium mb-1">{{ t('common.dragDrop') }}</p>
        <p class="text-gray-500 text-sm">{{ t('common.supportedFormats') }}</p>
        <p class="text-gray-500 text-sm">{{ t('common.maxSize') }}</p>
      </div>
    </div>

    <!-- Drag overlay -->
    <div
      v-if="isDragging"
      class="absolute inset-0 bg-primary-500/20 rounded-2xl flex items-center justify-center"
    >
      <p class="text-primary-400 font-semibold">{{ t('common.dropFilesHere') }}</p>
    </div>
  </div>
</template>
