<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { computed } from 'vue'
import { useAuthStore } from '@/stores'
const { t } = useI18n()
const authStore = useAuthStore()

interface FooterCol { titleKey: string; links: { to?: string; href?: string; key: string }[] }

const cols: FooterCol[] = [
  {
    titleKey: 'lp.categories.fashionAI',
    links: [
      { to: '/tools/try-on',      key: 'lp.allTools.tryOn.name' },
      { to: '/tools/short-video', key: 'lp.allTools.fashionReels.name' },
      { to: '/gallery',           key: 'gallery.title' },
    ],
  },
  {
    titleKey: 'lp.categories.ecommerceAI',
    links: [
      { to: '/tools/product-scene',      key: 'lp.allTools.productAnyshoot.name' },
      { to: '/tools/background-removal', key: 'lp.allTools.bgRemoval.name' },
      { to: '/tools/upscale',            key: 'lp.allTools.hdUpscale.name' },
      { to: '/tools/room-redesign',      key: 'lp.allTools.roomRedesign.name' },
    ],
  },
  {
    titleKey: 'footer.company',
    links: [
      { href: '#',         key: 'footer.about' },
      { to: '/pricing',    key: 'footer.pricing' },
      { href: '#',         key: 'footer.contact' },
      { href: '#',         key: 'footer.blog' },
      { href: '#',         key: 'footer.affiliate' },
    ],
  },
  {
    titleKey: 'footer.legal',
    links: [
      { href: '#', key: 'footer.terms' },
      { href: '#', key: 'footer.privacy' },
      { href: '#', key: 'footer.cookies' },
      { href: '#', key: 'footer.refunds' },
    ],
  },
]

const visibleCols = computed(() =>
  cols.map(col => ({
    ...col,
    links: authStore.isAdmin ? col.links.filter(link => link.to !== '/gallery') : col.links,
  })).filter(col => col.links.length > 0)
)
</script>

<template>
  <footer style="background: var(--bg-section-alt); border-top: 1px solid rgba(255,255,255,0.06);">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
      <div class="grid grid-cols-2 md:grid-cols-6 gap-10">
        <!-- Brand -->
        <div class="col-span-2">
          <RouterLink to="/" class="flex items-center gap-2.5 mb-4 group">
            <div class="relative w-8 h-8 flex-shrink-0 transition-all duration-300 group-hover:scale-105 group-hover:shadow-[0_0_16px_rgba(245,158,11,0.40)]" style="border-radius: 9px; background: #f59e0b;">
              <svg class="absolute inset-0 w-full h-full" viewBox="0 0 32 32" fill="none">
                <path d="M9 10.5 L16 21 L23 10.5" stroke="#0a0a0a" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
            <span class="text-[15px] font-bold leading-none" style="font-family: 'Syne', sans-serif; color: var(--text-primary); letter-spacing: 0;">Vidgo<span style="color: #f59e0b;">AI</span></span>
          </RouterLink>
          <p class="text-sm leading-relaxed max-w-xs mb-6 text-secondary">{{ t('footer.tagline') }}</p>
          <div class="flex items-center gap-2">
            <a href="#" aria-label="Twitter"
               class="w-9 h-9 rounded-full flex items-center justify-center transition-all duration-200"
               style="background: rgba(255,255,255,0.04); color: var(--text-secondary); border: 1px solid rgba(255,255,255,0.06);"
               @mouseenter="($event.currentTarget as HTMLElement).style.background='rgba(245,158,11,0.12)'; ($event.currentTarget as HTMLElement).style.color='#fbbf24'; ($event.currentTarget as HTMLElement).style.borderColor='rgba(245,158,11,0.30)'"
               @mouseleave="($event.currentTarget as HTMLElement).style.background='rgba(255,255,255,0.04)'; ($event.currentTarget as HTMLElement).style.color='var(--text-secondary)'; ($event.currentTarget as HTMLElement).style.borderColor='rgba(255,255,255,0.06)'">
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M8.29 20.251c7.547 0 11.675-6.253 11.675-11.675 0-.178 0-.355-.012-.53A8.348 8.348 0 0022 5.92a8.19 8.19 0 01-2.357.646 4.118 4.118 0 001.804-2.27 8.224 8.224 0 01-2.605.996 4.107 4.107 0 00-6.993 3.743 11.65 11.65 0 01-8.457-4.287 4.106 4.106 0 001.27 5.477A4.072 4.072 0 012.8 9.713v.052a4.105 4.105 0 003.292 4.022 4.095 4.095 0 01-1.853.07 4.108 4.108 0 003.834 2.85A8.233 8.233 0 012 18.407a11.616 11.616 0 006.29 1.84"/></svg>
            </a>
            <a href="#" aria-label="Instagram"
               class="w-9 h-9 rounded-full flex items-center justify-center transition-all duration-200"
               style="background: rgba(255,255,255,0.04); color: var(--text-secondary); border: 1px solid rgba(255,255,255,0.06);"
               @mouseenter="($event.currentTarget as HTMLElement).style.background='rgba(245,158,11,0.12)'; ($event.currentTarget as HTMLElement).style.color='#fbbf24'; ($event.currentTarget as HTMLElement).style.borderColor='rgba(245,158,11,0.30)'"
               @mouseleave="($event.currentTarget as HTMLElement).style.background='rgba(255,255,255,0.04)'; ($event.currentTarget as HTMLElement).style.color='var(--text-secondary)'; ($event.currentTarget as HTMLElement).style.borderColor='rgba(255,255,255,0.06)'">
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path fill-rule="evenodd" d="M12.315 2c2.43 0 2.784.013 3.808.06 1.064.049 1.791.218 2.427.465a4.902 4.902 0 011.772 1.153 4.902 4.902 0 011.153 1.772c.247.636.416 1.363.465 2.427.048 1.067.06 1.407.06 4.123v.08c0 2.643-.012 2.987-.06 4.043-.049 1.064-.218 1.791-.465 2.427a4.902 4.902 0 01-1.153 1.772 4.902 4.902 0 01-1.772 1.153c-.636.247-1.363.416-2.427.465-1.067.048-1.407.06-4.123.06h-.08c-2.643 0-2.987-.012-4.043-.06-1.064-.049-1.791-.218-2.427-.465a4.902 4.902 0 01-1.772-1.153 4.902 4.902 0 01-1.153-1.772c-.247-.636-.416-1.363-.465-2.427-.047-1.024-.06-1.379-.06-3.808v-.63c0-2.43.013-2.784.06-3.808.049-1.064.218-1.791.465-2.427a4.902 4.902 0 011.153-1.772A4.902 4.902 0 015.45 2.525c.636-.247 1.363-.416 2.427-.465C8.901 2.013 9.256 2 11.685 2h.63zm-.081 1.802h-.468c-2.456 0-2.784.011-3.807.058-.975.045-1.504.207-1.857.344-.467.182-.8.398-1.15.748-.35.35-.566.683-.748 1.15-.137.353-.3.882-.344 1.857-.047 1.023-.058 1.351-.058 3.807v.468c0 2.456.011 2.784.058 3.807.045.975.207 1.504.344 1.857.182.466.399.8.748 1.15.35.35.683.566 1.15.748.353.137.882.3 1.857.344 1.054.048 1.37.058 4.041.058h.08c2.597 0 2.917-.01 3.96-.058.976-.045 1.505-.207 1.858-.344.466-.182.8-.398 1.15-.748.35-.35.566-.683.748-1.15.137-.353.3-.882.344-1.857.048-1.055.058-1.37.058-4.041v-.08c0-2.597-.01-2.917-.058-3.96-.045-.976-.207-1.505-.344-1.858a3.097 3.097 0 00-.748-1.15 3.098 3.098 0 00-1.15-.748c-.353-.137-.882-.3-1.857-.344-1.023-.047-1.351-.058-3.807-.058zM12 6.865a5.135 5.135 0 110 10.27 5.135 5.135 0 010-10.27zm0 1.802a3.333 3.333 0 100 6.666 3.333 3.333 0 000-6.666zm5.338-3.205a1.2 1.2 0 110 2.4 1.2 1.2 0 010-2.4z" clip-rule="evenodd"/></svg>
            </a>
          </div>
        </div>

        <div v-for="col in visibleCols" :key="col.titleKey">
          <h4 class="font-semibold mb-4 text-sm" style="color: var(--text-primary);">{{ t(col.titleKey) }}</h4>
          <ul class="space-y-2.5">
            <li v-for="link in col.links" :key="link.key">
              <RouterLink v-if="link.to" :to="link.to" class="text-sm transition-colors text-secondary hover:text-primary-300"
                style="color: var(--text-secondary);"
                @mouseenter="($event.target as HTMLElement).style.color='#fbbf24'"
                @mouseleave="($event.target as HTMLElement).style.color='var(--text-secondary)'">
                {{ t(link.key) }}
              </RouterLink>
              <a v-else :href="link.href" class="text-sm transition-colors"
                 style="color: var(--text-secondary);"
                 @mouseenter="($event.target as HTMLElement).style.color='#69b1ff'"
                 @mouseleave="($event.target as HTMLElement).style.color='var(--text-secondary)'">
                {{ t(link.key) }}
              </a>
            </li>
          </ul>
        </div>
      </div>

      <!-- Bottom Bar -->
      <div class="mt-12 pt-8 flex flex-col md:flex-row items-center justify-between gap-4" style="border-top: 1px solid rgba(255,255,255,0.06);">
        <p class="text-sm text-muted">{{ '\u00A9' }} 2025 VidGo AI. All rights reserved.</p>
        <div class="flex items-center gap-3">
          <span class="badge">{{ t('footer.securePayment') }}</span>
        </div>
      </div>
    </div>
  </footer>
</template>
