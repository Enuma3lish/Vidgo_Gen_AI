/**
 * Composable for language-aware field selection
 *
 * When API returns both `field` and `field_zh` (or other language suffixes),
 * this composable helps select the correct one based on current locale.
 *
 * Example:
 *   const { getLocalizedField } = useLocalized()
 *   const title = getLocalizedField(example, 'title')  // Returns 'title' or 'title_zh'
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

export function useLocalized() {
  const { locale } = useI18n()

  /**
   * Get the language suffix for the current locale
   */
  const languageSuffix = computed(() => {
    switch (locale.value) {
      case 'zh-TW':
        return '_zh'
      case 'ja':
        return '_ja'
      case 'ko':
        return '_ko'
      case 'es':
        return '_es'
      default:
        return ''  // English is the default (no suffix)
    }
  })

  /**
   * Get a localized field value from an object
   * Falls back to English (base field) if localized version is not available
   *
   * @param obj The object containing the fields
   * @param fieldName The base field name (e.g., 'title', 'prompt', 'description')
   * @returns The localized value, or the base value if localized not available
   */
  function getLocalizedField<T extends Record<string, any>>(
    obj: T,
    fieldName: string
  ): string {
    if (!obj) return ''

    // Try localized field first (e.g., 'title_zh')
    const localizedFieldName = fieldName + languageSuffix.value
    if (localizedFieldName !== fieldName && obj[localizedFieldName]) {
      return obj[localizedFieldName]
    }

    // Fall back to base field (English)
    return obj[fieldName] || ''
  }

  /**
   * Check if current locale is Chinese
   */
  const isChinese = computed(() => locale.value === 'zh-TW')

  /**
   * Check if current locale is English
   */
  const isEnglish = computed(() => locale.value === 'en')

  return {
    locale,
    languageSuffix,
    getLocalizedField,
    isChinese,
    isEnglish
  }
}

export default useLocalized
