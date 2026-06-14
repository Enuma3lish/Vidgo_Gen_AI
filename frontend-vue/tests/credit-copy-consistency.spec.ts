import { describe, it, expect } from 'vitest'
import en from '@/locales/en.json'
import zhTW from '@/locales/zh-TW.json'
import ja from '@/locales/ja.json'
import ko from '@/locales/ko.json'
import es from '@/locales/es.json'

// The new-user welcome bonus is quoted in several places across the auth flow.
// Every one of those strings, in every locale, must name the SAME number of
// free credits. This guards against the copy drifting out of sync — e.g. the
// hero promising "40 free credits" while the register button still says "50".
// If the bonus changes, update EXPECTED_CREDITS and every locale together.

const LOCALES: Record<string, unknown> = { en, 'zh-TW': zhTW, ja, ko, es }

const WELCOME_CREDIT_KEYS = [
  'auth.freeCreditsTitle',
  'auth.signUpFree',
  'auth.perk1',
  'auth.registerSubtitle2',
  'auth.promotionCodePlaceholder',
  'auth.promotionCodeHint',
  'auth.registerBtn',
]
const EXPECTED_CREDITS = '40'

function get(obj: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>((acc, key) => {
    if (acc && typeof acc === 'object') return (acc as Record<string, unknown>)[key]
    return undefined
  }, obj)
}

describe('credit-copy-consistency', () => {
  for (const [locale, messages] of Object.entries(LOCALES)) {
    for (const key of WELCOME_CREDIT_KEYS) {
      it(`${locale} → ${key} quotes ${EXPECTED_CREDITS} free credits`, () => {
        const value = get(messages, key)
        expect(typeof value, `${locale}:${key} should be a string`).toBe('string')
        expect(value as string).toContain(EXPECTED_CREDITS)
      })
    }
  }
})
