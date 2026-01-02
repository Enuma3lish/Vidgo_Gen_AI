import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api'
import type { User, LoginRequest, RegisterRequest, VerifyCodeRequest } from '@/api'

export const useAuthStore = defineStore('auth', () => {
  // State
  const user = ref<User | null>(null)
  const accessToken = ref<string | null>(localStorage.getItem('access_token'))
  const refreshToken = ref<string | null>(localStorage.getItem('refresh_token'))
  const loading = ref(false)
  const error = ref<string | null>(null)
  const pendingEmail = ref<string | null>(null)

  // Getters
  const isAuthenticated = computed(() => !!accessToken.value && !!user.value)
  const isVerified = computed(() => user.value?.is_verified ?? false)
  const isAdmin = computed(() => user.value?.is_admin ?? false)

  // Actions
  async function login(data: LoginRequest) {
    loading.value = true
    error.value = null
    try {
      const response = await authApi.login(data)
      setTokens(response.access_token, response.refresh_token)
      user.value = response.user
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
      setTokens(response.access_token, response.refresh_token)
      user.value = response.user
      pendingEmail.value = null
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
    localStorage.setItem('access_token', access)
    localStorage.setItem('refresh_token', refresh)
  }

  function logout() {
    user.value = null
    accessToken.value = null
    refreshToken.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  function clearError() {
    error.value = null
  }

  // Initialize - fetch user if token exists
  async function init() {
    if (accessToken.value) {
      await fetchUser()
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
