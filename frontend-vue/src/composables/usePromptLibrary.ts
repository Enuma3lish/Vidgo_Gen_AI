import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import library from '@/data/prompt_library.json'

/**
 * Curated prompt library — locked to a fixed set of presets so demo and paid
 * users cannot inject free-form prompts (anti-hallucination + safety).
 *
 * Schema (v2): each preset carries a SHORT label in five locales (en/zh/ja/
 * ko/es) plus the canonical full prompt text in English and Traditional
 * Chinese. The dropdown shows label[currentLocale]; the canonical text sent
 * to the model is `zh` for any zh-* locale and `en` for everything else.
 *
 * Backend validates the supplied `prompt_id` server-side, so a client cannot
 * submit a prompt id that isn't in this file.
 */
export type LocaleKey = 'en' | 'zh' | 'ja' | 'ko' | 'es'

export type PromptLabel = Record<LocaleKey, string>

export type PromptItem = {
  id: string
  label: PromptLabel
  en: string
  zh: string
}

type ToolEntry = {
  label: PromptLabel
  prompts: PromptItem[]
}

type Library = {
  _meta?: Record<string, unknown>
  tools: Record<string, ToolEntry>
}

const lib = library as unknown as Library

export type PromptToolKey =
  | 'product_scene'
  | 'room_redesign'
  | 'short_video'
  | 'ai_avatar'
  | 'pattern_generate'

function normalizeLocale(raw: string): LocaleKey {
  const l = String(raw || '').toLowerCase()
  if (l.startsWith('zh')) return 'zh'
  if (l.startsWith('ja')) return 'ja'
  if (l.startsWith('ko')) return 'ko'
  if (l.startsWith('es')) return 'es'
  return 'en'
}

/**
 * The full prompt actually sent to the model is only available in en or zh
 * (the two languages the upstream image / video / TTS providers handle most
 * reliably). For any other UI locale we still submit the English text — the
 * dropdown label stays in the user's UI locale so they recognize it.
 */
function submissionLocale(uiLocale: LocaleKey): 'en' | 'zh' {
  return uiLocale === 'zh' ? 'zh' : 'en'
}

export function usePromptLibrary(toolKey: PromptToolKey) {
  const { locale } = useI18n()

  const entry = lib.tools[toolKey]
  if (!entry) {
    // Soft-fail so a missing key never crashes the page.
    return {
      prompts: computed(() => [] as PromptItem[]),
      options: computed(() => [] as { id: string; label: string; value: string; full: string }[]),
      labelFor: (_id: string) => '',
      promptFor: (_id: string) => '',
      submissionLocale: computed<'en' | 'zh'>(() => 'en'),
    }
  }

  const uiLocale = computed<LocaleKey>(() => normalizeLocale(String(locale.value)))
  const submitLang = computed<'en' | 'zh'>(() => submissionLocale(uiLocale.value))

  const prompts = computed<PromptItem[]>(() => entry.prompts)

  const options = computed(() =>
    entry.prompts.map((p) => {
      // Show the short label in the user's UI locale; fall back to en.
      const text = p.label?.[uiLocale.value] || p.label?.en || p.id
      return {
        id: p.id,
        label: text,
        value: p.id,
        full: submitLang.value === 'zh' ? p.zh : p.en,
      }
    })
  )

  function promptFor(id: string): string {
    const found = entry.prompts.find((p) => p.id === id)
    if (!found) return ''
    return submitLang.value === 'zh' ? found.zh : found.en
  }

  function labelFor(id: string): string {
    const found = entry.prompts.find((p) => p.id === id)
    if (!found) return ''
    return found.label?.[uiLocale.value] || found.label?.en || id
  }

  return {
    prompts,
    options,
    promptFor,
    labelFor,
    submissionLocale: submitLang,
  }
}
