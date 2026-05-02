<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { commonImageDimensionRule, validateImageFileDimensions } from '@/utils/mediaValidation'

const { t, locale } = useI18n()

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
  const isZh = locale.value.startsWith('zh')
  const validFiles: File[] = []

  for (const file of files) {
    if (!allowed.includes(file.type)) {
      const label = allowed === AI_VIDEO_TYPES ? 'MP4, WebM, or MOV video' : 'JPG, PNG, or WebP image'
      emit('error', `File ${file.name} is not supported. Please choose a ${label}.`)
      continue
    }
    if (file.size > maxSize) {
      emit('error', `File ${file.name} exceeds maximum size of ${maxSize / 1024 / 1024}MB. Please choose a smaller file.`)
      continue
    }
    if (file.type.startsWith('image/')) {
      try {
        const dimensionError = await validateImageFileDimensions(file, commonImageDimensionRule, isZh)
        if (dimensionError) {
          emit('error', dimensionError)
          continue
        }
      } catch {
        emit('error', isZh ? '無法讀取圖片尺寸，請重新選擇圖片。' : 'Image dimensions could not be read. Please choose a different image.')
        continue
      }
    }
    validFiles.push(file)
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
      <p class="text-primary-400 font-semibold">Drop files here</p>
    </div>
  </div>
</template>
