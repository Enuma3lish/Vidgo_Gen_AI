<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { apiClient } from '@/api'

interface Props {
  taskId: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  progress: number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  completed: [resultUrl: string]
  failed: [error: string]
}>()

const internalStatus = ref(props.status)
const internalProgress = ref(props.progress)
const pollingTimer = ref<ReturnType<typeof setInterval> | null>(null)
const errorMessage = ref('')

const statusText = computed(() => {
  switch (internalStatus.value) {
    case 'queued':
      return '排隊中...'
    case 'processing':
      return `生成中... ${internalProgress.value}%`
    case 'completed':
      return '完成!'
    case 'failed':
      return '失敗'
    default:
      return ''
  }
})

const statusColor = computed(() => {
  switch (internalStatus.value) {
    case 'queued':
      return 'text-yellow-400'
    case 'processing':
      return 'text-blue-400'
    case 'completed':
      return 'text-green-400'
    case 'failed':
      return 'text-red-400'
    default:
      return 'text-gray-400'
  }
})

const progressBarColor = computed(() => {
  switch (internalStatus.value) {
    case 'queued':
      return 'bg-yellow-500'
    case 'processing':
      return 'bg-gradient-to-r from-blue-500 to-purple-500'
    case 'completed':
      return 'bg-green-500'
    case 'failed':
      return 'bg-red-500'
    default:
      return 'bg-gray-500'
  }
})

const isActive = computed(() =>
  internalStatus.value === 'queued' || internalStatus.value === 'processing'
)

async function pollStatus() {
  if (!props.taskId) return

  try {
    const response = await apiClient.get(`/api/v1/generate/status/${props.taskId}`)
    const data = response.data

    if (data.status) {
      internalStatus.value = data.status
    }
    if (data.progress !== undefined) {
      internalProgress.value = data.progress
    }

    if (data.status === 'completed') {
      stopPolling()
      emit('completed', data.result_url || '')
    } else if (data.status === 'failed') {
      stopPolling()
      errorMessage.value = data.error || 'Generation failed'
      emit('failed', errorMessage.value)
    }
  } catch (err: unknown) {
    const e = err as { response?: { data?: { detail?: string } }; message?: string }
    errorMessage.value = e.response?.data?.detail || e.message || 'Polling failed'
  }
}

function startPolling() {
  stopPolling()
  pollingTimer.value = setInterval(pollStatus, 3000)
}

function stopPolling() {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
    pollingTimer.value = null
  }
}

// Watch for external status/progress changes
watch(() => props.status, (val) => {
  internalStatus.value = val
})

watch(() => props.progress, (val) => {
  internalProgress.value = val
})

// Start/stop polling based on active state
watch(isActive, (active) => {
  if (active && props.taskId) {
    startPolling()
  } else {
    stopPolling()
  }
}, { immediate: true })

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<template>
  <div class="w-full rounded-xl bg-dark-800 border border-dark-600 p-6">
    <!-- Status Header -->
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-3">
        <!-- Animated spinner for active states -->
        <div v-if="isActive" class="w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
        <!-- Check icon for completed -->
        <svg v-else-if="internalStatus === 'completed'" class="w-5 h-5 text-green-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
          <polyline points="22 4 12 14.01 9 11.01" />
        </svg>
        <!-- X icon for failed -->
        <svg v-else-if="internalStatus === 'failed'" class="w-5 h-5 text-red-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="15" y1="9" x2="9" y2="15" />
          <line x1="9" y1="9" x2="15" y2="15" />
        </svg>

        <span class="font-semibold text-white" :class="statusColor">{{ statusText }}</span>
      </div>
      <span class="text-sm text-gray-500 font-mono">{{ internalProgress }}%</span>
    </div>

    <!-- Progress Bar -->
    <div class="w-full h-3 bg-dark-700 rounded-full overflow-hidden mb-4">
      <div
        class="h-full rounded-full transition-all duration-500 ease-out"
        :class="[progressBarColor, { 'animate-pulse': internalStatus === 'queued' }]"
        :style="{ width: `${internalProgress}%` }"
      />
    </div>

    <!-- Estimated Time -->
    <div v-if="isActive" class="flex items-center gap-2 text-sm text-gray-400">
      <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </svg>
      <span>預估時間：約 3-8 分鐘</span>
    </div>

    <!-- Error Message -->
    <div v-if="internalStatus === 'failed' && errorMessage" class="mt-3 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
      <p class="text-sm text-red-400">{{ errorMessage }}</p>
    </div>

    <!-- Task ID -->
    <div class="mt-3 text-xs text-gray-600">
      Task ID: {{ taskId }}
    </div>
  </div>
</template>
