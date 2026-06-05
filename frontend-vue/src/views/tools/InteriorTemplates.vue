<script setup lang="ts">
/**
 * Interior Templates Gallery — Pippit-style browsable cards.
 *
 * Added 2026-05-24 (owner directive — match pippit.ai/templates/ai-interior-design
 * presentation while leveraging our existing /api/v1/tools/room-redesign engine).
 * Each card shows a style preview + name. Click deeplinks into RoomRedesign with
 * `?style=<id>&space_kind=<interior|exterior|commercial>` so the picker is
 * pre-filled and the user only needs to upload a photo.
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

interface StyleCard {
  id: string
  name: string
  name_zh: string
  prompt: string
  preview_url?: string
}

const activeTab = ref<SpaceKind>('interior')
// Static 3-tab enum — label resolved per-render via L() in template for full i18n
// (zh / en / ja / ko / es). See template line ~119.
const tabOptions: Array<{ id: SpaceKind; emoji: string }> = [
  { id: 'interior',   emoji: '🛋️' },
  { id: 'commercial', emoji: '🏪' },
  { id: 'exterior',   emoji: '🏛️' },
]

function tabLabel(kind: SpaceKind): string {
  switch (kind) {
    case 'interior':   return L('室內',     'Interior',   'インテリア', '인테리어',   'Interior')
    case 'commercial': return L('商業空間', 'Commercial', '商業空間',   '상업 공간',  'Comercial')
    case 'exterior':   return L('建築外觀', 'Exterior',   '建築外観',   '건축 외관',  'Exterior')
  }
}

const styles = ref<Record<SpaceKind, StyleCard[]>>({
  interior: [],
  commercial: [],
  exterior: [],
})
const isLoading = ref<Record<SpaceKind, boolean>>({ interior: false, commercial: false, exterior: false })

// Track preview URLs that 404'd at runtime so we can fall back to the
// branded gradient placeholder instead of leaving a broken-image icon.
const failedPreviews = ref<Set<string>>(new Set())
function markPreviewFailed(card: StyleCard) {
  failedPreviews.value = new Set(failedPreviews.value).add(card.id)
}

async function loadStyles(kind: SpaceKind) {
  if (styles.value[kind].length > 0 || isLoading.value[kind]) return
  isLoading.value[kind] = true
  try {
    const resp = await apiClient.get(`/api/v1/tools/templates/interior-styles?space_kind=${kind}`)
    styles.value[kind] = (resp.data || []) as StyleCard[]
  } catch (e) {
    console.warn(`[interior-templates] failed to load ${kind}:`, e)
  } finally {
    isLoading.value[kind] = false
  }
}

function selectTab(kind: SpaceKind) {
  activeTab.value = kind
  void loadStyles(kind)
}

// Each space-kind now has its own dedicated tool page (2026-06-03 split), so
// route the click to the matching page with the style pre-filled instead of
// the old all-in-one RoomRedesign + space_kind query.
const PAGE_BY_KIND: Record<SpaceKind, string> = {
  interior: '/tools/room-redesign',
  exterior: '/tools/exterior-ai',
  commercial: '/tools/commercial-space',
}
function openStyle(card: StyleCard) {
  router.push({ path: PAGE_BY_KIND[activeTab.value], query: { style: card.id } })
}

// Fallback preview when the catalog entry has no preview_url, or when the
// referenced asset 404'd at runtime. Returning null swaps the <img> for the
// neutral gradient placeholder so the grid never shows a broken-image icon.
function previewUrl(card: StyleCard): string | null {
  if (!card.preview_url) return null
  if (failedPreviews.value.has(card.id)) return null
  if (card.preview_url.startsWith('http')) return card.preview_url
  return card.preview_url
}

onMounted(() => loadStyles('interior'))
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
          {{ L('AI 室內設計範本', 'AI Interior Design Templates', 'AIインテリアデザインテンプレート', 'AI 인테리어 디자인 템플릿', 'Plantillas de Diseño de Interiores con IA') }}
        </h1>
        <p class="text-base max-w-2xl mx-auto" style="color: #94949f;">
          {{ L('挑選一個風格範本，上傳你的房間照片，AI 立刻幫你生成設計提案。', 'Pick a style template, upload your room photo, and let AI generate a design proposal instantly.', 'スタイルテンプレートを選び、部屋の写真をアップロードすると、AIが即座にデザイン提案を生成します。', '스타일 템플릿을 선택하고 방 사진을 업로드하면 AI가 즉시 디자인 제안을 생성합니다.', 'Elige una plantilla, sube la foto de tu habitación y deja que la IA genere una propuesta de diseño al instante.') }}
        </p>
      </div>
    </section>

    <!-- Tabs -->
    <section class="px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
      <div class="flex gap-2 justify-center mb-8 flex-wrap">
        <button
          v-for="tab in tabOptions"
          :key="tab.id"
          @click="selectTab(tab.id)"
          class="px-5 py-2.5 rounded-full text-sm font-semibold transition-all flex items-center gap-2"
          :style="activeTab === tab.id
            ? 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color: #fff;'
            : 'background: #141420; color: #94949f; border: 1px solid rgba(255,255,255,0.08);'"
        >
          <span>{{ tab.emoji }}</span>
          {{ tabLabel(tab.id) }}
        </button>
      </div>
    </section>

    <!-- Grid -->
    <section class="px-4 sm:px-6 lg:px-8 pb-16 max-w-7xl mx-auto">
      <div v-if="isLoading[activeTab]" class="flex justify-center py-16">
        <div class="animate-spin w-10 h-10 border-2 rounded-full" style="border-color: #a78bfa; border-top-color: transparent;"></div>
      </div>

      <div v-else-if="styles[activeTab].length === 0" class="text-center py-16" style="color: #94949f;">
        {{ L('暫無範本', 'No templates yet', 'テンプレートがありません', '템플릿이 없습니다', 'Sin plantillas todavía') }}
      </div>

      <div v-else class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 sm:gap-5">
        <button
          v-for="card in styles[activeTab]"
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
        {{ L(`共 ${styles[activeTab].length} 個範本`, `${styles[activeTab].length} templates`, `${styles[activeTab].length}個のテンプレート`, `${styles[activeTab].length}개 템플릿`, `${styles[activeTab].length} plantillas`) }}
      </p>
    </section>
  </div>
</template>
