import axios from 'axios'
import type { AxiosInstance, AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import { safeLocalStorage } from '@/utils/safeStorage'

// P0-2: per-request correlation id forwarded as the X-Client-Task-Id header.
declare module 'axios' {
  // eslint-disable-next-line @typescript-eslint/no-empty-interface
  export interface AxiosRequestConfig {
    clientTaskId?: string
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

// Create axios instance
// NOTE: Timeout is 15 minutes because subscriber-tier generation endpoints
// (avatar / try_on / room_redesign / short_video) are synchronous and the
// underlying providers (PiAPI Kling Avatar + F5-TTS, Pollo I2V, Vertex Veo)
// regularly take 2-8 minutes per call, with Kling Avatar peaking around
// 10 minutes when PiAPI's F5-TTS path falls back to tts-1 and then waits
// on Kling lip-sync. A shorter ceiling cancels the request from the client
// even though the backend keeps running, leaving the user with a stuck
// "處理中..." UI that never resolves.
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 900000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor - add auth token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = safeLocalStorage.getItem('access_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    const locale = safeLocalStorage.getItem('locale') || safeLocalStorage.getItem('vidgo-locale') || navigator.language || 'en'
    if (config.headers) {
      config.headers['Accept-Language'] = locale
    }
    // P0-2: a generation call may set `clientTaskId` on its request config;
    // forward it as X-Client-Task-Id so the backend stamps it onto the
    // UserGeneration / PendingProviderTask, letting the client poll
    // GET /api/v1/user/tasks/{id} to recover a timed-out / refreshed task.
    const clientTaskId = (config as any).clientTaskId
    if (clientTaskId && config.headers) {
      config.headers['X-Client-Task-Id'] = clientTaskId
    }
    return config
  },
  (error: AxiosError) => {
    return Promise.reject(error)
  }
)

// Response interceptor - handle non-JSON responses and token refresh
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    // Guard against nginx returning index.html instead of JSON (misconfigured proxy)
    const contentType = response.headers['content-type'] || ''
    if (
      response.config.headers?.['Content-Type'] === 'application/json' &&
      !contentType.includes('application/json') &&
      typeof response.data === 'string' &&
      response.data.startsWith('<!') // HTML response
    ) {
      return Promise.reject(
        Object.assign(new Error('API returned non-JSON response. The backend may be unreachable.'), {
          response: { ...response, data: { detail: 'Service temporarily unavailable. Please try again.' } },
        })
      )
    }
    return response
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    // Normalize structured backend errors. Backend may return:
    //   { detail: { error_code, message } }
    // Flatten so existing UI code that reads `data.detail` still gets a
    // human-readable string, while preserving error_code on data.error_code.
    try {
      const data: any = error.response?.data
      if (data && typeof data === 'object' && data.detail && typeof data.detail === 'object') {
        const d = data.detail as Record<string, unknown>
        if (typeof d.message === 'string') {
          if (typeof d.error_code === 'string' && !data.error_code) {
            data.error_code = d.error_code
          }
          data.detail = d.message
        }
      }
    } catch { /* noop */ }

    // If 401 and not already retrying
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      const refreshToken = safeLocalStorage.getItem('refresh_token')
      if (refreshToken) {
        try {
          // Single in-flight refresh: when many requests fire in parallel and
          // all 401, only the first should hit /auth/refresh; the others
          // await the same promise. Without this, N parallel requests cause
          // N refresh calls, and the refresh-token rotation on the backend
          // invalidates earlier ones, logging the user out.
          const access = await getOrStartTokenRefresh(refreshToken)

          // Retry original request with new token
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${access}`
          }
          return apiClient(originalRequest)
        } catch (refreshError) {
          // Refresh failed - logout user
          safeLocalStorage.removeItem('access_token')
          safeLocalStorage.removeItem('refresh_token')
          window.location.href = '/auth/login'
          return Promise.reject(refreshError)
        }
      }
    }

    return Promise.reject(error)
  }
)

// Shared in-flight refresh promise to coalesce concurrent 401s.
let _refreshInFlight: Promise<string> | null = null

async function getOrStartTokenRefresh(refreshToken: string): Promise<string> {
  if (_refreshInFlight) return _refreshInFlight
  _refreshInFlight = (async () => {
    try {
      const response = await axios.post(`${API_BASE_URL}/api/v1/auth/refresh`, {
        refresh: refreshToken,
      })
      const { access, refresh: newRefreshToken } = response.data
      safeLocalStorage.setItem('access_token', access)
      if (newRefreshToken) {
        safeLocalStorage.setItem('refresh_token', newRefreshToken)
      }
      try {
        const { useAuthStore } = await import('@/stores/auth')
        const authStore = useAuthStore()
        authStore.accessToken = access
        if (newRefreshToken) authStore.refreshToken = newRefreshToken
      } catch {
        /* store not ready yet */
      }
      return access as string
    } finally {
      _refreshInFlight = null
    }
  })()
  return _refreshInFlight
}

export default apiClient
