import { defineStore } from 'pinia'
import apiClient from '@/api/client'

export interface PublicBrandingSettings {
  logo_url: string | null
  logo_url_dark: string | null
  favicon_url: string | null
  brand_name: string | null
  brand_tagline_zh: string | null
  brand_tagline_en: string | null
  // Pricing-page editable copy (added 2026-05-23 — backend already
  // serialised these via /admin/branding/public but the store was dropping
  // them, so AdminBranding saves had no public effect).
  pricing_intro_title_zh: string | null
  pricing_intro_title_en: string | null
  pricing_intro_body_zh: string | null
  pricing_intro_body_en: string | null
  pricing_footnote_zh: string | null
  pricing_footnote_en: string | null
}

// Default admin-editable branding fields fall through to NULL until the
// admin uploads. The AppHeader renders its built-in SVG mark when
// logo_url is null so the site never goes "logo-less" mid-load.
const EMPTY: PublicBrandingSettings = {
  logo_url: null,
  logo_url_dark: null,
  favicon_url: null,
  brand_name: null,
  brand_tagline_zh: null,
  brand_tagline_en: null,
  pricing_intro_title_zh: null,
  pricing_intro_title_en: null,
  pricing_intro_body_zh: null,
  pricing_intro_body_en: null,
  pricing_footnote_zh: null,
  pricing_footnote_en: null,
}

export const useBrandingStore = defineStore('branding', {
  state: () => ({
    settings: { ...EMPTY } as PublicBrandingSettings,
    loaded: false,
    loading: false,
  }),
  getters: {
    // True once we've successfully reached /admin/branding/public, even if
    // the row's columns are all NULL (the admin hasn't uploaded yet).
    hasLogo: (state) => Boolean(state.settings.logo_url),
    hasDarkLogo: (state) => Boolean(state.settings.logo_url_dark),
    hasFavicon: (state) => Boolean(state.settings.favicon_url),
  },
  actions: {
    async fetch(force = false) {
      if (this.loading) return
      if (this.loaded && !force) return
      this.loading = true
      try {
        const response = await apiClient.get('/api/v1/admin/branding/public')
        const merged = { ...EMPTY, ...(response.data?.settings || {}) }
        this.settings = merged
        this.loaded = true
        // Mirror the favicon onto the <link rel="icon"> so swapping it
        // through admin actually changes the browser-tab icon without a
        // full page reload.
        if (typeof document !== 'undefined' && merged.favicon_url) {
          let link = document.querySelector<HTMLLinkElement>("link[rel='icon']")
          if (!link) {
            link = document.createElement('link')
            link.rel = 'icon'
            document.head.appendChild(link)
          }
          link.href = merged.favicon_url
        }
      } catch (err) {
        // Public branding is non-critical — fall through to the in-app
        // SVG mark so a transient backend error doesn't block render.
        console.warn('[branding] failed to load public settings:', err)
      } finally {
        this.loading = false
      }
    },
    // Called by the admin Branding page after a successful save so the
    // live header refreshes without a hard reload.
    apply(settings: Partial<PublicBrandingSettings>) {
      this.settings = { ...this.settings, ...settings }
      this.loaded = true
      if (typeof document !== 'undefined' && settings.favicon_url) {
        let link = document.querySelector<HTMLLinkElement>("link[rel='icon']")
        if (!link) {
          link = document.createElement('link')
          link.rel = 'icon'
          document.head.appendChild(link)
        }
        link.href = settings.favicon_url
      }
    },
  },
})
