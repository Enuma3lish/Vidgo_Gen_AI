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
import { LOCALE_STORAGE_KEY, SUPPORTED_LOCALES, normalizeLocale, persistLocale } from '@/utils/locales'
import { safeLocalStorage } from '@/utils/safeStorage'

const GEO_DETECTED_KEY = 'vidgo_geo_language_detected'
// Must match the key used by main.ts + stores/ui.ts (LanguageSelector).
// Previously this file used a different key ('vidgo_locale'), which caused
// F-005: manual language selection would survive reload via main.ts init,
// but then initLanguage() would override it from its own separate key.
const LOCALE_KEY = LOCALE_STORAGE_KEY

export function useGeoLanguage() {
  const { locale } = useI18n()
  const isDetecting = ref(false)
  const detectedLanguage = ref<string | null>(null)
  const detectedCountry = ref<string | null>(null)

  /**
   * Check if we've already detected language before
   */
  function hasDetected(): boolean {
    return safeLocalStorage.getItem(GEO_DETECTED_KEY) === 'true'
  }

  /**
   * Mark as detected (so we don't call API again)
   */
  function markDetected(): void {
    safeLocalStorage.setItem(GEO_DETECTED_KEY, 'true')
  }

  /**
   * Detect language based on user's IP
   * Only runs once per session/device
   */
  async function detectLanguage(): Promise<string> {
    // Skip if already detected
    if (hasDetected()) {
      const savedLocale = safeLocalStorage.getItem(LOCALE_KEY)
      if (savedLocale) {
        return normalizeLocale(savedLocale)
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

        return normalizeLocale(response.data.language)
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
    const userSetLocale = safeLocalStorage.getItem(LOCALE_KEY)
    if (userSetLocale) {
      locale.value = persistLocale(userSetLocale)
      return
    }

    // Detect from IP
    const detected = await detectLanguage()

    // Only set if valid locale
    if ((SUPPORTED_LOCALES as readonly string[]).includes(detected)) {
      locale.value = persistLocale(detected)
    }
  }

  /**
   * Reset detection (for testing or user preference change)
   */
  function resetDetection(): void {
    safeLocalStorage.removeItem(GEO_DETECTED_KEY)
    safeLocalStorage.removeItem(LOCALE_KEY)
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
