import { onBeforeUnmount, watch } from 'vue'
import apiClient from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const HEARTBEAT_INTERVAL_MS = 45_000

let timer: number | null = null
let isStarted = false
let isSending = false

export function useSessionHeartbeat() {
  const authStore = useAuthStore()

  async function sendHeartbeat() {
    if (isSending) return
    isSending = true
    try {
      await apiClient.post('/api/v1/session/heartbeat')
    } catch (error) {
      console.warn('[session] heartbeat failed:', error)
    } finally {
      isSending = false
    }
  }

  function handleVisibilityChange() {
    if (document.visibilityState === 'visible') {
      void sendHeartbeat()
    }
  }

  function startHeartbeat() {
    if (isStarted) return
    isStarted = true

    void sendHeartbeat()
    timer = window.setInterval(() => {
      if (document.visibilityState !== 'hidden') {
        void sendHeartbeat()
      }
    }, HEARTBEAT_INTERVAL_MS)

    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('focus', handleVisibilityChange)
  }

  function stopHeartbeat() {
    if (timer) {
      window.clearInterval(timer)
      timer = null
    }
    document.removeEventListener('visibilitychange', handleVisibilityChange)
    window.removeEventListener('focus', handleVisibilityChange)
    isStarted = false
  }

  watch(
    () => `${authStore.user?.id || 'anonymous'}:${authStore.accessToken || ''}`,
    () => {
      if (isStarted) {
        void sendHeartbeat()
      }
    }
  )

  onBeforeUnmount(stopHeartbeat)

  return {
    startHeartbeat,
    stopHeartbeat,
    sendHeartbeat,
  }
}