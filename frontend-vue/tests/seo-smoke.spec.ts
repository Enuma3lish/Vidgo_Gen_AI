import { describe, it, expect, beforeEach } from 'vitest'
import { applySeo, buildAlternateLocales } from '@/composables/useSeo'

// Smoke test for the home-grown SEO head manager (we deliberately did NOT adopt
// @vueuse/head — see useSeo.ts). Locks in the T-04 fix: hreflang alternates must
// be DISTINCT per locale, and title/description/canonical must land in <head>.

const head = () => document.head

describe('seo-smoke', () => {
  beforeEach(() => {
    document.head.innerHTML = ''
    document.title = ''
  })

  it('sets title (with suffix), description, canonical, robots and og:title', () => {
    applySeo({
      title: 'Pricing',
      description: 'Plans and credits',
      canonical: 'https://vidgo.co/pricing',
    })
    expect(document.title).toBe('Pricing | VidGo AI')
    expect(head().querySelector('meta[name="description"]')?.getAttribute('content')).toBe('Plans and credits')
    expect(head().querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe('https://vidgo.co/pricing')
    expect(head().querySelector('meta[name="robots"]')?.getAttribute('content')).toBe('index, follow')
    expect(head().querySelector('meta[property="og:title"]')?.getAttribute('content')).toBe('Pricing | VidGo AI')
  })

  it('does not double-append the suffix when the title already names VidGo', () => {
    applySeo({ title: 'VidGo AI｜Home' })
    expect(document.title).toBe('VidGo AI｜Home')
  })

  it('honours noindex for private routes', () => {
    applySeo({ title: 'Admin', noindex: true })
    expect(head().querySelector('meta[name="robots"]')?.getAttribute('content')).toBe('noindex, nofollow')
  })

  it('emits one hreflang link per locale, each with a DISTINCT href (T-04)', () => {
    applySeo({
      title: 'Pricing',
      canonical: 'https://vidgo.co/pricing',
      alternateLocales: buildAlternateLocales('https://vidgo.co', '/pricing'),
    })
    const links = Array.from(head().querySelectorAll('link[rel="alternate"][hreflang]'))
    const hrefs = links.map((l) => l.getAttribute('href'))
    expect(links.length).toBe(6) // en, zh-TW, ja, ko, es + x-default
    expect(new Set(hrefs).size).toBe(hrefs.length) // every href is unique
  })

  it('buildAlternateLocales maps each locale to its own ?lang= URL', () => {
    const alts = buildAlternateLocales('https://vidgo.co', '/')
    const byLang = Object.fromEntries(alts.map((a) => [a.hreflang, a.href]))
    expect(byLang['en']).toBe('https://vidgo.co/?lang=en')
    expect(byLang['zh-TW']).toBe('https://vidgo.co/?lang=zh-TW')
    expect(byLang['ja']).toBe('https://vidgo.co/?lang=ja')
    expect(byLang['x-default']).toBe('https://vidgo.co/')
    expect(buildAlternateLocales('', '/')).toEqual([])
  })

  it('replaces the hreflang block across navigations (no stale leakage)', () => {
    applySeo({ title: 'A', alternateLocales: buildAlternateLocales('https://vidgo.co', '/a') })
    applySeo({ title: 'B', alternateLocales: buildAlternateLocales('https://vidgo.co', '/b') })
    const hrefs = Array.from(head().querySelectorAll('link[rel="alternate"][hreflang]')).map((l) =>
      l.getAttribute('href'),
    )
    expect(hrefs.every((h) => h!.includes('/b'))).toBe(true)
    expect(hrefs.some((h) => h!.includes('/a'))).toBe(false)
  })
})
