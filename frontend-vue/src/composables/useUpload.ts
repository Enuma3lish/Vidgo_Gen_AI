import { ref, readonly } from 'vue'

export interface UploadState {
  file: File | null
  preview: string | null
  progress: number
  isUploading: boolean
  error: string | null
}

const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB
const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const ALLOWED_VIDEO_TYPES = ['video/mp4', 'video/webm']

export function useUpload(options?: {
  maxSize?: number
  allowedTypes?: string[]
  onUpload?: (file: File) => Promise<string>
}) {
  const maxSize = options?.maxSize || MAX_FILE_SIZE
  const allowedTypes = options?.allowedTypes || [...ALLOWED_IMAGE_TYPES, ...ALLOWED_VIDEO_TYPES]

  const state = ref<UploadState>({
    file: null,
    preview: null,
    progress: 0,
    isUploading: false,
    error: null
  })

  function validateFile(file: File): string | null {
    if (!allowedTypes.includes(file.type)) {
      return `File type not allowed. Allowed: ${allowedTypes.join(', ')}`
    }
    if (file.size > maxSize) {
      return `File too large. Max size: ${Math.round(maxSize / 1024 / 1024)}MB`
    }
    return null
  }

  function createPreview(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result as string)
      reader.onerror = reject
      reader.readAsDataURL(file)
    })
  }

  async function selectFile(file: File): Promise<boolean> {
    state.value.error = null

    const validationError = validateFile(file)
    if (validationError) {
      state.value.error = validationError
      return false
    }

    state.value.file = file
    state.value.preview = await createPreview(file)
    return true
  }

  async function upload(): Promise<string | null> {
    if (!state.value.file || !options?.onUpload) {
      return null
    }

    state.value.isUploading = true
    state.value.error = null
    state.value.progress = 0

    try {
      const url = await options.onUpload(state.value.file)
      state.value.progress = 100
      return url
    } catch (e: any) {
      state.value.error = e.message || 'Upload failed'
      return null
    } finally {
      state.value.isUploading = false
    }
  }

  function reset() {
    if (state.value.preview) {
      URL.revokeObjectURL(state.value.preview)
    }
    state.value = {
      file: null,
      preview: null,
      progress: 0,
      isUploading: false,
      error: null
    }
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault()
    const files = event.dataTransfer?.files
    if (files && files.length > 0) {
      selectFile(files[0])
    }
  }

  function handleInputChange(event: Event) {
    const target = event.target as HTMLInputElement
    const files = target.files
    if (files && files.length > 0) {
      selectFile(files[0])
    }
  }

  return {
    state: readonly(state),
    selectFile,
    upload,
    reset,
    handleDrop,
    handleInputChange
  }
}
