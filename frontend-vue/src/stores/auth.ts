import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api'
import type { User, LoginRequest, RegisterRequest, VerifyCodeRequest } from '@/api'
import { safeLocalStorage, safeSessionStorage } from '@/utils/safeStorage'

export const useAuthStore = defineStore('auth', () => {
  // State
  const user = ref<User | null>(null)
  const accessToken = ref<string | null>(safeLocalStorage.getItem('access_token'))
  const refreshToken = ref<string | null>(safeLocalStorage.getItem('refresh_token'))
  const loading = ref(false)
  const error = ref<string | null>(null)
  const pendingEmail = ref<string | null>(null)

  // Getters
  const isAuthenticated = computed(() => !!accessToken.value && !!user.value)
  const isVerified = computed(() => user.value?.email_verified ?? false)
  const isAdmin = computed(() => Boolean(user.value?.is_superuser || user.value?.is_admin))

  // Actions
  async function login(data: LoginRequest) {
    loading.value = true
    error.value = null
    try {
      const response = await authApi.login(data)
      const access = (response as { tokens?: { access: string }; access_token?: string }).tokens?.access
        ?? (response as { access_token?: string }).access_token
      const refresh = (response as { tokens?: { refresh: string }; refresh_token?: string }).tokens?.refresh
        ?? (response as { refresh_token?: string }).refresh_token
      if (access && refresh) setTokens(access, refresh)
      user.value = response.user
      if (isAdmin.value) {
        const { useCreditsStore } = await import('./credits')
        useCreditsStore().clearBalance()
      } else {
        try {
          const { useCreditsStore } = await import('./credits')
          await useCreditsStore().fetchBalance()
        } catch (e) {
          console.warn('[auth.login] credits fetch failed (non-fatal):', e)
        }
      }
      return response
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      error.value = e.response?.data?.detail || 'Login failed'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function register(data: RegisterRequest) {
    loading.value = true
    error.value = null
    try {
      const response = await authApi.register(data)
      pendingEmail.value = data.email
      safeSessionStorage.setItem('pendingVerifyEmail', data.email)
      return response
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      error.value = e.response?.data?.detail || 'Registration failed'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function verifyCode(data: VerifyCodeRequest) {
    loading.value = true
    error.value = null
    try {
      const response = await authApi.verifyCode(data)
      const access = (response as { tokens?: { access: string }; access_token?: string }).tokens?.access
        ?? (response as { access_token?: string }).access_token
      const refresh = (response as { tokens?: { refresh: string }; refresh_token?: string }).tokens?.refresh
        ?? (response as { refresh_token?: string }).refresh_token
      if (access && refresh) setTokens(access, refresh)
      user.value = response.user
      pendingEmail.value = null
      // Fetch the freshly-granted signup bonus credits so the UI shows
      // the correct balance immediately after email verification (without
      // requiring a page refresh or password reset).
      if (user.value && !isAdmin.value) {
        try {
          const { useCreditsStore } = await import('./credits')
          await useCreditsStore().fetchBalance()
        } catch (e) {
          console.warn('[auth.verifyCode] credits fetch failed (non-fatal):', e)
        }
      } else if (user.value && isAdmin.value) {
        const { useCreditsStore } = await import('./credits')
        useCreditsStore().clearBalance()
      }
      return response
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      error.value = e.response?.data?.detail || 'Verification failed'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function resendCode(email: string) {
    loading.value = true
    error.value = null
    try {
      return await authApi.resendCode(email)
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      error.value = e.response?.data?.detail || 'Failed to resend code'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchUser() {
    if (!accessToken.value) return null
    try {
      user.value = await authApi.getMe()
      return user.value
    } catch {
      logout()
      return null
    }
  }

  function setTokens(access: string, refresh: string) {
    accessToken.value = access
    refreshToken.value = refresh
    safeLocalStorage.setItem('access_token', access)
    safeLocalStorage.setItem('refresh_token', refresh)
  }

  function logout() {
    user.value = null
    accessToken.value = null
    refreshToken.value = null
    safeLocalStorage.removeItem('access_token')
    safeLocalStorage.removeItem('refresh_token')
  }

  function clearError() {
    error.value = null
  }

  // Initialize - fetch user if token exists
  async function init() {
    if (accessToken.value) {
      await fetchUser()
      if (user.value && isAdmin.value) {
        const { useCreditsStore } = await import('./credits')
        useCreditsStore().clearBalance()
      } else if (user.value) {
        try {
          const { useCreditsStore } = await import('./credits')
          await useCreditsStore().fetchBalance()
        } catch (e) {
          console.warn('[auth.init] credits fetch failed (non-fatal):', e)
        }
      }
    }
  }

  return {
    // State
    user,
    accessToken,
    refreshToken,
    loading,
    error,
    pendingEmail,
    // Getters
    isAuthenticated,
    isVerified,
    isAdmin,
    // Actions
    login,
    register,
    verifyCode,
    resendCode,
    fetchUser,
    logout,
    clearError,
    init
  }
})
