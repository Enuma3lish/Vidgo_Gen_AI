/**
 * Minimal SEO head manager — sets document.title and the common meta tags
 * (description, canonical, Open Graph, Twitter Card, hreflang) without
 * depending on @vueuse/head or unhead. Installed package weight is zero;
 * router.afterEach calls applySeo() and any view can override at runtime.
 *
 * Why no library: the project's vue-tsc / vite stack doesn't currently ship
 * @vueuse/head, and SEO metadata only needs to land in the final HTML at
 * navigation time — there is no DOM-effect we need beyond setAttribute().
 */

import { SUPPORTED_LOCALES } from '@/utils/locales'

export interface SeoInput {
  title?: string
  description?: string
  canonical?: string
  image?: string
  type?: 'website' | 'article'
  noindex?: boolean
  locale?: string
  alternateLocales?: Array<{ hreflang: string; href: string }>
}

const DEFAULTS = {
  siteName: 'VidGo AI',
  titleSuffix: ' | VidGo AI',
  description:
    'VidGo AI — AI product photography, background removal, short video, interior design and AI digital human in one platform.',
  image: 'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/landing/og-cover.jpg',
}

function upsertMeta(selector: string, attrs: Record<string, string>) {
  let el = document.head.querySelector<HTMLMetaElement>(selector)
  if (!el) {
    el = document.createElement('meta')
    Object.entries(attrs).forEach(([k, v]) => {
      if (k !== 'content') el!.setAttribute(k, v)
    })
    document.head.appendChild(el)
  }
  el.setAttribute('content', attrs.content)
}

function upsertLink(rel: string, href: string, extra: Record<string, string> = {}) {
  // hreflang links need to be uniquely keyed by hreflang, not just rel.
  const selector = extra.hreflang
    ? `link[rel="${rel}"][hreflang="${extra.hreflang}"]`
    : `link[rel="${rel}"]`
  let el = document.head.querySelector<HTMLLinkElement>(selector)
  if (!el) {
    el = document.createElement('link')
    el.setAttribute('rel', rel)
    Object.entries(extra).forEach(([k, v]) => el!.setAttribute(k, v))
    document.head.appendChild(el)
  }
  el.setAttribute('href', href)
}

function removeAllHreflang() {
  document.head.querySelectorAll('link[rel="alternate"][hreflang]').forEach((el) => el.remove())
}

export function applySeo(input: SeoInput) {
  const title = input.title
    ? input.title.endsWith(DEFAULTS.siteName) || /VidGo/i.test(input.title)
      ? input.title
      : input.title + DEFAULTS.titleSuffix
    : DEFAULTS.siteName
  document.title = title

  const description = input.description || DEFAULTS.description
  upsertMeta('meta[name="description"]', { name: 'description', content: description })

  if (input.canonical) {
    upsertLink('canonical', input.canonical)
  }

  upsertMeta('meta[property="og:title"]', { property: 'og:title', content: title })
  upsertMeta('meta[property="og:description"]', { property: 'og:description', content: description })
  upsertMeta('meta[property="og:site_name"]', { property: 'og:site_name', content: DEFAULTS.siteName })
  upsertMeta('meta[property="og:type"]', { property: 'og:type', content: input.type || 'website' })
  upsertMeta('meta[property="og:image"]', { property: 'og:image', content: input.image || DEFAULTS.image })
  if (input.canonical) {
    upsertMeta('meta[property="og:url"]', { property: 'og:url', content: input.canonical })
  }

  upsertMeta('meta[name="twitter:card"]', { name: 'twitter:card', content: 'summary_large_image' })
  upsertMeta('meta[name="twitter:title"]', { name: 'twitter:title', content: title })
  upsertMeta('meta[name="twitter:description"]', { name: 'twitter:description', content: description })
  upsertMeta('meta[name="twitter:image"]', { name: 'twitter:image', content: input.image || DEFAULTS.image })

  upsertMeta('meta[name="robots"]', {
    name: 'robots',
    content: input.noindex ? 'noindex, nofollow' : 'index, follow',
  })

  // Replace any prior hreflang block with the route's alternates so removed
  // languages disappear from <head> instead of leaking across navigation.
  removeAllHreflang()
  if (input.alternateLocales && input.alternateLocales.length) {
    input.alternateLocales.forEach((alt) => {
      upsertLink('alternate', alt.href, { hreflang: alt.hreflang })
    })
  }

  if (input.locale) {
    document.documentElement.setAttribute('lang', input.locale)
  }
}

/**
 * Build the hreflang alternates for a given path.
 *
 * Each supported locale MUST resolve to its own distinct URL (via a `?lang=`
 * query). Emitting the same href for every hreflang — the previous behaviour —
 * is invalid per Google's spec and is silently ignored, so the five language
 * variants were invisible to search engines (T-04). An `x-default` entry points
 * at the canonical, param-less URL for unmatched locales.
 *
 * The matching `?lang=` is honoured at app boot by getInitialLocale(), so these
 * URLs serve genuinely different content rather than being SEO-only decoration.
 */
export function buildAlternateLocales(
  origin: string,
  path: string,
): Array<{ hreflang: string; href: string }> {
  if (!origin) return []
  const base = origin + (path || '/')
  const sep = base.includes('?') ? '&' : '?'
  const alternates: Array<{ hreflang: string; href: string }> = SUPPORTED_LOCALES.map((code) => ({
    hreflang: code,
    href: `${base}${sep}lang=${code}`,
  }))
  alternates.push({ hreflang: 'x-default', href: base })
  return alternates
}
