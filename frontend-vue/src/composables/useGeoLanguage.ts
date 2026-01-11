/**
 * Composable for IP-based language detection
 *
 * Automatically detects user's preferred language based on their IP location.
 * Called once on app initialization and stores the result in localStorage.
 *
 * Mapping:
 * - Taiwan, Hong Kong, Macau → zh-TW
 * - Japan → ja
 * - Korea → ko
 * - Spain & Latin America → es
 * - Others → en (default)
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import apiClient from '@/api/client'

const GEO_DETECTED_KEY = 'vidgo_geo_language_detected'
const LOCALE_KEY = 'vidgo_locale'

export function useGeoLanguage() {
  const { locale } = useI18n()
  const isDetecting = ref(false)
  const detectedLanguage = ref<string | null>(null)
  const detectedCountry = ref<string | null>(null)

  /**
   * Check if we've already detected language before
   */
  function hasDetected(): boolean {
    return localStorage.getItem(GEO_DETECTED_KEY) === 'true'
  }

  /**
   * Mark as detected (so we don't call API again)
   */
  function markDetected(): void {
    localStorage.setItem(GEO_DETECTED_KEY, 'true')
  }

  /**
   * Detect language based on user's IP
   * Only runs once per session/device
   */
  async function detectLanguage(): Promise<string> {
    // Skip if already detected
    if (hasDetected()) {
      const savedLocale = localStorage.getItem(LOCALE_KEY)
      if (savedLocale) {
        return savedLocale
      }
    }

    isDetecting.value = true

    try {
      const response = await apiClient.get('/api/v1/auth/geo-language')

      if (response.data && response.data.language) {
        detectedLanguage.value = response.data.language
        detectedCountry.value = response.data.country

        // Mark as detected to prevent future API calls
        markDetected()

        return response.data.language
      }
    } catch (error) {
      console.warn('Failed to detect language from IP:', error)
    } finally {
      isDetecting.value = false
    }

    // Default to English
    markDetected()
    return 'en'
  }

  /**
   * Initialize language detection on app start
   * Sets the locale if not already set by user
   */
  async function initLanguage(): Promise<void> {
    // Check if user has manually set a locale preference
    const userSetLocale = localStorage.getItem(LOCALE_KEY)
    if (userSetLocale) {
      locale.value = userSetLocale
      return
    }

    // Detect from IP
    const detected = await detectLanguage()

    // Only set if valid locale
    const validLocales = ['en', 'zh-TW', 'ja', 'ko', 'es']
    if (validLocales.includes(detected)) {
      locale.value = detected
      localStorage.setItem(LOCALE_KEY, detected)
    }
  }

  /**
   * Reset detection (for testing or user preference change)
   */
  function resetDetection(): void {
    localStorage.removeItem(GEO_DETECTED_KEY)
    localStorage.removeItem(LOCALE_KEY)
  }

  return {
    isDetecting,
    detectedLanguage,
    detectedCountry,
    detectLanguage,
    initLanguage,
    resetDetection,
    hasDetected
  }
}

export default useGeoLanguage
