import axios from 'axios'
import type { AxiosInstance, AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

// Create axios instance
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor - add auth token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
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

    // If 401 and not already retrying
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        try {
          const response = await axios.post(`${API_BASE_URL}/api/v1/auth/refresh`, {
            refresh: refreshToken
          })

          const { access, refresh: newRefreshToken } = response.data
          localStorage.setItem('access_token', access)
          if (newRefreshToken) {
            localStorage.setItem('refresh_token', newRefreshToken)
          }

          // Sync Pinia auth store with new tokens
          try {
            const { useAuthStore } = await import('@/stores/auth')
            const authStore = useAuthStore()
            authStore.accessToken = access
            if (newRefreshToken) authStore.refreshToken = newRefreshToken
          } catch { /* store not ready yet */ }

          // Retry original request with new token
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${access}`
          }
          return apiClient(originalRequest)
        } catch (refreshError) {
          // Refresh failed - logout user
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          window.location.href = '/auth/login'
          return Promise.reject(refreshError)
        }
      }
    }

    return Promise.reject(error)
  }
)

export default apiClient
