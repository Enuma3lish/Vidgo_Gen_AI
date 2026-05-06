import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { getStoredLocale, persistLocale } from '@/utils/locales'

export interface Toast {
  id: number
  message: string
  type: 'success' | 'error' | 'warning' | 'info'
  duration?: number
}

export const useUIStore = defineStore('ui', () => {
  // State
  const locale = ref(getStoredLocale())
  const theme = ref<'dark' | 'light'>('dark')
  const sidebarOpen = ref(false)
  const globalLoading = ref(false)
  const toasts = ref<Toast[]>([])

  let toastId = 0

  // Watch locale changes
  watch(locale, (newLocale) => {
    persistLocale(newLocale)
  })

  // Actions
  function setLocale(newLocale: string) {
    locale.value = persistLocale(newLocale)
    document.documentElement.lang = locale.value
  }

  function changeLanguageAndSync(newLocale: string) {
    setLocale(newLocale)
    window.dispatchEvent(new CustomEvent('vidgo:locale-changed', { detail: { locale: locale.value } }))
  }

  function setTheme(newTheme: 'dark' | 'light') {
    theme.value = newTheme
    document.documentElement.classList.toggle('dark', newTheme === 'dark')
  }

  function toggleSidebar() {
    sidebarOpen.value = !sidebarOpen.value
  }

  function setGlobalLoading(loading: boolean) {
    globalLoading.value = loading
  }

  function showToast(message: string, type: Toast['type'] = 'info', duration = 3000) {
    const id = ++toastId
    const toast: Toast = { id, message, type, duration }
    toasts.value.push(toast)

    if (duration > 0) {
      setTimeout(() => {
        removeToast(id)
      }, duration)
    }

    return id
  }

  function removeToast(id: number) {
    const index = toasts.value.findIndex(t => t.id === id)
    if (index !== -1) {
      toasts.value.splice(index, 1)
    }
  }

  function showSuccess(message: string) {
    return showToast(message, 'success')
  }

  function showError(message: string) {
    return showToast(message, 'error', 5000)
  }

  function showWarning(message: string) {
    return showToast(message, 'warning')
  }

  function showInfo(message: string) {
    return showToast(message, 'info')
  }

  return {
    // State
    locale,
    theme,
    sidebarOpen,
    globalLoading,
    toasts,
    // Actions
    setLocale,
    changeLanguageAndSync,
    setTheme,
    toggleSidebar,
    setGlobalLoading,
    showToast,
    removeToast,
    showSuccess,
    showError,
    showWarning,
    showInfo
  }
})
