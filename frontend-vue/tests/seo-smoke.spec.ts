import { describe, it, expect, beforeEach } from 'vitest'
import { applySeo } from '@/composables/useSeo'

// Smoke test for the home-grown SEO head manager (we deliberately did NOT adopt
// @vueuse/head — see useSeo.ts). Verifies title/description/canonical/robots
// land in <head>, and locks in the 2026-06-15 single-canonical-URL policy: the
// router no longer emits per-locale ?lang= hreflang alternates (they contradicted
// the param-less canonical and produced GSC "Alternate page with proper canonical
// tag" exclusions), and applySeo() clears any stale hreflang each navigation.

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

  it('emits NO per-locale hreflang alternates (single canonical URL policy)', () => {
    applySeo({
      title: 'Pricing',
      canonical: 'https://vidgo.co/pricing',
    })
    const links = head().querySelectorAll('link[rel="alternate"][hreflang]')
    expect(links.length).toBe(0)
  })

  it('clears any stale hreflang already in <head> on the next applySeo', () => {
    // Simulate a leftover hreflang (e.g. injected by an old build or index.html).
    const stale = document.createElement('link')
    stale.setAttribute('rel', 'alternate')
    stale.setAttribute('hreflang', 'ja')
    stale.setAttribute('href', 'https://vidgo.co/?lang=ja')
    document.head.appendChild(stale)

    applySeo({ title: 'Pricing', canonical: 'https://vidgo.co/pricing' })
    expect(head().querySelectorAll('link[rel="alternate"][hreflang]').length).toBe(0)
  })
})
