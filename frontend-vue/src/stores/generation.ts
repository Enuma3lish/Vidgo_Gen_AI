import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '@/api/client'

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
  estimatedSeconds?: number
}

// Estimated generation time per tool type (seconds)
const TOOL_ETA: Record<string, number> = {
  background_removal: 15,
  product_scene: 30,
  try_on: 45,
  room_redesign: 60,
  short_video: 120,
  ai_avatar: 180,
  pattern_generate: 25,
  effect: 20,
}

export const useGenerationStore = defineStore('generation', () => {
  // State
  const currentTask = ref<GenerationTask | null>(null)
  const taskHistory = ref<GenerationTask[]>([])
  const pollingInterval = ref<ReturnType<typeof setInterval> | null>(null)
  const pollingRetryCount = ref(0)
  const MAX_POLL_RETRIES = 3

  // Computed
  const isProcessing = computed(() =>
    currentTask.value?.status === 'uploading' ||
    currentTask.value?.status === 'processing' ||
    currentTask.value?.status === 'polling'
  )

  const isCompleted = computed(() => currentTask.value?.status === 'completed')
  const isFailed = computed(() => currentTask.value?.status === 'failed')

  const currentProgress = computed(() => currentTask.value?.progress || 0)

  const activeGenerations = computed(() =>
    taskHistory.value.filter(t =>
      t.status === 'uploading' || t.status === 'processing' || t.status === 'polling'
    )
  )

  const estimatedTimeRemaining = computed(() => {
    if (!currentTask.value || !isProcessing.value) return null
    const eta = currentTask.value.estimatedSeconds || 60
    const elapsed = (Date.now() - currentTask.value.startedAt.getTime()) / 1000
    const remaining = Math.max(0, eta - elapsed)
    return Math.ceil(remaining)
  })

  // Actions
  function startTask(toolType: string, creditCost: number): string {
    const taskId = `gen_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    currentTask.value = {
      id: taskId,
      toolType,
      status: 'uploading',
      progress: 0,
      startedAt: new Date(),
      creditCost,
      estimatedSeconds: TOOL_ETA[toolType] || 60,
    }

    pollingRetryCount.value = 0
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
    pollingRetryCount.value = 0

    pollingInterval.value = setInterval(async () => {
      try {
        const response = await pollFn()
        pollingRetryCount.value = 0 // Reset on success

        if (response.progress !== undefined) {
          updateStatus('polling', response.progress)
        }

        if (response.status === 'completed' && response.result) {
          setResult(response.result.image_url, response.result.video_url)
        } else if (response.status === 'failed') {
          setError(response.result?.error || 'Generation failed')
        }
      } catch (error: any) {
        pollingRetryCount.value++
        if (pollingRetryCount.value >= MAX_POLL_RETRIES) {
          setError(error.message || 'Polling failed after retries')
        }
        // Otherwise silently retry on next interval
      }
    }, intervalMs)
  }

  /**
   * Poll the backend generation status endpoint directly.
   * Usage: pollGenerationStatus('task-uuid-123')
   */
  function pollGenerationStatus(taskId: string, intervalMs: number = 2000) {
    updateStatus('polling', 30)

    startPolling(async () => {
      const { data } = await apiClient.get(`/api/v1/generate/status/${taskId}`)
      return {
        status: data.status,
        progress: data.progress,
        result: data.result,
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
    activeGenerations,
    estimatedTimeRemaining,

    // Actions
    startTask,
    updateStatus,
    setInputImage,
    setResult,
    setError,
    startPolling,
    pollGenerationStatus,
    stopPolling,
    reset,
    clearHistory
  }
})
