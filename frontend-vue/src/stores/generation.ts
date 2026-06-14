import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type GenerationStatus = 'idle' | 'uploading' | 'processing' | 'polling' | 'completed' | 'failed'

export interface GenerationTask {
  id: string
  toolType: string
  status: GenerationStatus
  progress: number
  inputImageUrl?: string
  resultImageUrl?: string
  resultVideoUrl?: string
  error?: string
  startedAt: Date
  completedAt?: Date
  creditCost: number
}

export const useGenerationStore = defineStore('generation', () => {
  // State
  const currentTask = ref<GenerationTask | null>(null)
  const taskHistory = ref<GenerationTask[]>([])
  const pollingInterval = ref<ReturnType<typeof setInterval> | null>(null)

  // Computed
  const isProcessing = computed(() =>
    currentTask.value?.status === 'uploading' ||
    currentTask.value?.status === 'processing' ||
    currentTask.value?.status === 'polling'
  )

  const isCompleted = computed(() => currentTask.value?.status === 'completed')
  const isFailed = computed(() => currentTask.value?.status === 'failed')

  const currentProgress = computed(() => currentTask.value?.progress || 0)

  // Actions
  function startTask(toolType: string, creditCost: number): string {
    const taskId = `gen_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    currentTask.value = {
      id: taskId,
      toolType,
      status: 'uploading',
      progress: 0,
      startedAt: new Date(),
      creditCost
    }

    return taskId
  }

  function updateStatus(status: GenerationStatus, progress?: number) {
    if (!currentTask.value) return

    currentTask.value.status = status

    if (progress !== undefined) {
      currentTask.value.progress = progress
    }

    // Auto-progress based on status
    if (status === 'uploading') {
      currentTask.value.progress = 10
    } else if (status === 'processing') {
      currentTask.value.progress = 30
    } else if (status === 'polling') {
      // Progress will be updated externally
    } else if (status === 'completed') {
      currentTask.value.progress = 100
      currentTask.value.completedAt = new Date()
    } else if (status === 'failed') {
      stopPolling()
    }
  }

  function setInputImage(url: string) {
    if (currentTask.value) {
      currentTask.value.inputImageUrl = url
    }
  }

  function setResult(imageUrl?: string, videoUrl?: string) {
    if (!currentTask.value) return

    currentTask.value.resultImageUrl = imageUrl
    currentTask.value.resultVideoUrl = videoUrl
    currentTask.value.status = 'completed'
    currentTask.value.progress = 100
    currentTask.value.completedAt = new Date()

    // Add to history
    taskHistory.value.unshift({ ...currentTask.value })

    // Keep only last 20 tasks
    if (taskHistory.value.length > 20) {
      taskHistory.value = taskHistory.value.slice(0, 20)
    }

    stopPolling()
  }

  function setError(error: string) {
    if (currentTask.value) {
      currentTask.value.error = error
      currentTask.value.status = 'failed'
    }
    stopPolling()
  }

  function startPolling(
    pollFn: () => Promise<{ status: string; progress?: number; result?: any }>,
    intervalMs: number = 2000
  ) {
    stopPolling()

    pollingInterval.value = setInterval(async () => {
      try {
        const response = await pollFn()

        if (response.progress !== undefined) {
          updateStatus('polling', response.progress)
        }

        if (response.status === 'completed' && response.result) {
          setResult(response.result.image_url, response.result.video_url)
        } else if (response.status === 'failed') {
          setError(response.result?.error || 'Generation failed')
        }
      } catch (error: any) {
        setError(error.message || 'Polling failed')
      }
    }, intervalMs)
  }

  function stopPolling() {
    if (pollingInterval.value) {
      clearInterval(pollingInterval.value)
      pollingInterval.value = null
    }
  }

  function reset() {
    stopPolling()
    currentTask.value = null
  }

  function clearHistory() {
    taskHistory.value = []
  }

  return {
    // State
    currentTask,
    taskHistory,

    // Computed
    isProcessing,
    isCompleted,
    isFailed,
    currentProgress,

    // Actions
    startTask,
    updateStatus,
    setInputImage,
    setResult,
    setError,
    startPolling,
    stopPolling,
    reset,
    clearHistory
  }
})
