<script setup lang="ts">
/**
 * Templates Gallery — Pippit-style browsable cards.
 *
 * Added 2026-05-24 (owner directive — match pippit.ai/templates/ai-interior-design
 * presentation while leveraging our existing /api/v1/tools/room-redesign engine).
 * Each card shows a style preview + name; click deeplinks into the matching
 * dedicated tool page with the style pre-filled.
 *
 * 2026-06-12 — interior, exterior, and commercial are now SEPARATE PAGES
 * (owner directive: never mix interior and exterior on one page; each tool
 * in the interior group and the exterior group is its own page). The old
 * in-page 3-tab switcher was removed; this component is rendered by three
 * routes that pin the `spaceKind` prop:
 *   /tools/interior-templates   → spaceKind='interior'
 *   /tools/exterior-templates   → spaceKind='exterior'
 *   /tools/commercial-templates → spaceKind='commercial'
 *
 * Color palette intentionally matches the rest of the tools UI (#0f0f17 panels,
 * violet→indigo gradient accents, etc.) — owner directive 2026-05-24:
 * "ui color like before but change ux like piapi."
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useLocalized } from '@/composables'
import apiClient from '@/api/client'

const { locale } = useI18n()
const router = useRouter()
const { L } = useLocalized()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

type SpaceKind = 'interior' | 'exterior' | 'commercial'

// Pinned per route — see the route entries in router/index.ts.
const props = withDefaults(defineProps<{ spaceKind?: SpaceKind }>(), { spaceKind: 'interior' })
const spaceKind = computed<SpaceKind>(() =>
  props.spaceKind === 'exterior' || props.spaceKind === 'commercial' ? props.spaceKind : 'interior')

interface StyleCard {
  id: string
  name: string
  name_zh: string
  prompt: string
  preview_url?: string
}

const styles = ref<StyleCard[]>([])
const isLoading = ref(false)

// Track preview URLs that 404'd at runtime so we can fall back to the
// branded gradient placeholder instead of leaving a broken-image icon.
const failedPreviews = ref<Set<string>>(new Set())
function markPreviewFailed(card: StyleCard) {
  failedPreviews.value = new Set(failedPreviews.value).add(card.id)
}

async function loadStyles() {
  isLoading.value = true
  try {
    const resp = await apiClient.get(`/api/v1/tools/templates/interior-styles?space_kind=${spaceKind.value}`)
    styles.value = (resp.data || []) as StyleCard[]
  } catch (e) {
    console.warn(`[templates] failed to load ${spaceKind.value}:`, e)
  } finally {
    isLoading.value = false
  }
}

// Each space-kind has its own dedicated tool page (2026-06-03 split), so
// route the click to the matching page with the style pre-filled.
const PAGE_BY_KIND: Record<SpaceKind, string> = {
  interior: '/tools/room-redesign',
  exterior: '/tools/exterior-ai',
  commercial: '/tools/commercial-space',
}
function openStyle(card: StyleCard) {
  router.push({ path: PAGE_BY_KIND[spaceKind.value], query: { style: card.id } })
}

// Sibling template galleries — navigation links only; the galleries
// themselves never share a page.
const siblingLinks = computed(() => ([
  { kind: 'interior' as const,   to: '/tools/interior-templates',   label: '🛋️ ' + L('室內範本', 'Interior', 'インテリア', '인테리어', 'Interior') },
  { kind: 'exterior' as const,   to: '/tools/exterior-templates',   label: '🏛️ ' + L('建築外觀範本', 'Exterior', '建築外観', '건축 외관', 'Exterior') },
  { kind: 'commercial' as const, to: '/tools/commercial-templates', label: '🏪 ' + L('商業空間範本', 'Commercial', '商業空間', '상업 공간', 'Comercial') },
].filter((s) => s.kind !== spaceKind.value)))

const pageTitle = computed(() => {
  if (spaceKind.value === 'exterior') {
    return L('AI 建築外觀範本', 'AI Exterior Design Templates', 'AI建築外観テンプレート', 'AI 건축 외관 템플릿', 'Plantillas de Diseño Exterior con IA')
  }
  if (spaceKind.value === 'commercial') {
    return L('AI 商業空間範本', 'AI Commercial Space Templates', 'AI商業空間テンプレート', 'AI 상업 공간 템플릿', 'Plantillas de Espacios Comerciales con IA')
  }
  return L('AI 室內設計範本', 'AI Interior Design Templates', 'AIインテリアデザインテンプレート', 'AI 인테리어 디자인 템플릿', 'Plantillas de Diseño de Interiores con IA')
})

const pageSubtitle = computed(() => {
  if (spaceKind.value === 'exterior') {
    return L('挑選一個外觀風格範本，上傳你的建築照片，AI 立刻生成外觀提案。', 'Pick an exterior style template, upload your building photo, and let AI generate a facade proposal instantly.', '外観スタイルを選び、建物の写真をアップロードすると、AIが即座に提案を生成します。', '외관 스타일 템플릿을 선택하고 건물 사진을 올리면 AI가 즉시 제안을 생성합니다.', 'Elige una plantilla exterior, sube la foto del edificio y la IA genera una propuesta al instante.')
  }
  if (spaceKind.value === 'commercial') {
    return L('挑選一個商業空間範本，上傳你的空間照片，AI 立刻生成設計提案。', 'Pick a commercial style template, upload your space photo, and let AI generate a design proposal instantly.', '商業空間スタイルを選び、写真をアップロードすると、AIが即座に提案を生成します。', '상업 공간 템플릿을 선택하고 사진을 올리면 AI가 즉시 제안을 생성합니다.', 'Elige una plantilla comercial, sube la foto y la IA genera una propuesta al instante.')
  }
  return L('挑選一個風格範本，上傳你的房間照片，AI 立刻幫你生成設計提案。', 'Pick a style template, upload your room photo, and let AI generate a design proposal instantly.', 'スタイルテンプレートを選び、部屋の写真をアップロードすると、AIが即座にデザイン提案を生成します。', '스타일 템플릿을 선택하고 방 사진을 업로드하면 AI가 즉시 디자인 제안을 생성합니다.', 'Elige una plantilla, sube la foto de tu habitación y deja que la IA genere una propuesta de diseño al instante.')
})

// Fallback preview when the catalog entry has no preview_url, or when the
// referenced asset 404'd at runtime. Returning null swaps the <img> for the
// neutral gradient placeholder so the grid never shows a broken-image icon.
function previewUrl(card: StyleCard): string | null {
  if (!card.preview_url) return null
  if (failedPreviews.value.has(card.id)) return null
  if (card.preview_url.startsWith('http')) return card.preview_url
  return card.preview_url
}

onMounted(() => loadStyles())
</script>

<template>
  <div class="min-h-screen" style="background: #0a0a0f;">
    <!-- Hero — pt-24 clears the 64px fixed AppHeader (was pt-12 → clipped). -->
    <section class="px-4 sm:px-6 lg:px-8 pt-24 pb-6 max-w-7xl mx-auto">
      <div class="text-center space-y-3">
        <p class="text-xs font-mono tracking-[0.3em] uppercase" style="color: #a78bfa;">
          {{ L('範本庫', 'TEMPLATES', 'テンプレート', '템플릿', 'PLANTILLAS') }}
        </p>
        <h1 class="text-4xl sm:text-5xl font-bold" style="color: #f5f5fa;">
          {{ pageTitle }}
        </h1>
        <p class="text-base max-w-2xl mx-auto" style="color: #94949f;">
          {{ pageSubtitle }}
        </p>
      </div>
    </section>

    <!-- Sibling galleries — navigation only; each gallery is its own page -->
    <section class="px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
      <div class="flex gap-2 justify-center mb-8 flex-wrap">
        <RouterLink
          v-for="s in siblingLinks"
          :key="s.kind"
          :to="s.to"
          class="px-5 py-2.5 rounded-full text-sm font-semibold transition-all flex items-center gap-2"
          style="background: #141420; color: #94949f; border: 1px solid rgba(255,255,255,0.08);"
        >{{ s.label }} →</RouterLink>
      </div>
    </section>

    <!-- Grid -->
    <section class="px-4 sm:px-6 lg:px-8 pb-16 max-w-7xl mx-auto">
      <div v-if="isLoading" class="flex justify-center py-16">
        <div class="animate-spin w-10 h-10 border-2 rounded-full" style="border-color: #a78bfa; border-top-color: transparent;"></div>
      </div>

      <div v-else-if="styles.length === 0" class="text-center py-16" style="color: #94949f;">
        {{ L('暫無範本', 'No templates yet', 'テンプレートがありません', '템플릿이 없습니다', 'Sin plantillas todavía') }}
      </div>

      <div v-else class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 sm:gap-5">
        <button
          v-for="card in styles"
          :key="card.id"
          @click="openStyle(card)"
          class="group text-left rounded-2xl overflow-hidden transition-all hover:scale-[1.02]"
          style="background: #141420; border: 1px solid rgba(255,255,255,0.06);"
        >
          <!-- Preview tile -->
          <div class="aspect-[4/5] relative overflow-hidden" style="background: linear-gradient(135deg, rgba(124,58,237,0.15) 0%, rgba(244,114,182,0.1) 100%);">
            <!-- BUG-017: backend catalog only ships zh/en; ja/ko/es fall through to English for card.name / card.name_zh. -->
            <img
              v-if="previewUrl(card)"
              :src="previewUrl(card)!"
              :alt="isZh ? card.name_zh : card.name"
              class="w-full h-full object-cover transition-transform duration-300 group-hover:scale-110"
              loading="lazy"
              @error="markPreviewFailed(card)"
            />
            <div
              v-else
              class="absolute inset-0 flex items-center justify-center text-center px-4"
              style="background: linear-gradient(135deg, rgba(124,58,237,0.25), rgba(168,85,247,0.15));"
            >
              <span class="text-4xl">🏠</span>
            </div>
            <!-- Hover overlay with CTA -->
            <div
              class="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-4"
              style="background: linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0) 60%);"
            >
              <span class="text-sm font-semibold px-3 py-1.5 rounded-full" style="background: #7c3aed; color: #fff;">
                {{ L('使用此風格 →', 'Use this style →', 'このスタイルを使う →', '이 스타일 사용 →', 'Usar este estilo →') }}
              </span>
            </div>
          </div>
          <!-- Card body -->
          <div class="p-4">
            <!-- BUG-017: backend catalog only ships zh/en; ja/ko/es fall through to English. -->
            <p class="font-semibold text-sm" style="color: #f5f5fa;">
              {{ isZh ? card.name_zh : card.name }}
            </p>
            <p class="text-[11px] mt-1 line-clamp-2" style="color: #94949f;">
              {{ card.prompt.split(',').slice(0, 4).join(', ') }}
            </p>
          </div>
        </button>
      </div>

      <p class="text-center text-xs mt-10" style="color: #6b6b7a;">
        {{ L(`共 ${styles.length} 個範本`, `${styles.length} templates`, `${styles.length}個のテンプレート`, `${styles.length}개 템플릿`, `${styles.length} plantillas`) }}
      </p>
    </section>
  </div>
</template>
