import { describe, it, expect } from 'vitest'
import en from '@/locales/en.json'
import zhTW from '@/locales/zh-TW.json'
import ja from '@/locales/ja.json'
import ko from '@/locales/ko.json'
import es from '@/locales/es.json'

// Every locale must expose exactly the same key paths as the English source of
// truth. A missing key falls back to English at runtime (a silent, untranslated
// string shipped to users); an extra key is dead translation work. This test
// fails loudly with the exact diff so the gap is fixed at PR time.

type Json = Record<string, unknown>

function flatten(obj: Json, prefix = ''): string[] {
  const keys: string[] = []
  for (const [k, v] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${k}` : k
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      keys.push(...flatten(v as Json, path))
    } else {
      keys.push(path)
    }
  }
  return keys
}

const reference = flatten(en as Json)
const referenceSet = new Set(reference)
const locales: Record<string, Json> = {
  'zh-TW': zhTW as Json,
  ja: ja as Json,
  ko: ko as Json,
  es: es as Json,
}

describe('locale-key-coverage', () => {
  it('en.json has a meaningful number of keys', () => {
    expect(reference.length).toBeGreaterThan(100)
  })

  for (const [name, messages] of Object.entries(locales)) {
    it(`${name}.json has exactly the same keys as en.json`, () => {
      const keys = flatten(messages)
      const keySet = new Set(keys)
      const missing = reference.filter((k) => !keySet.has(k))
      const extra = keys.filter((k) => !referenceSet.has(k))
      expect({ missing, extra }).toEqual({ missing: [], extra: [] })
    })
  }
})
