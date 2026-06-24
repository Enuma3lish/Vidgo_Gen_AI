<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useLocalized } from '@/composables'
import { useAuthStore } from '@/stores/auth'
import { userApi } from '@/api/user'
import type { UserGeneration } from '@/api/user'
import ShareToSocialModal from '@/components/social/ShareToSocialModal.vue'

const { t, locale } = useI18n()
const { L } = useLocalized()
const router = useRouter()
const authStore = useAuthStore()

const selectedFilter = ref('all')
const showExpired = ref(true)   // 是否顯示已過期的作品（歷史記錄）
const works = ref<UserGeneration[]>([])
const loading = ref(false)
const totalWorks = ref(0)
const currentPage = ref(1)
const perPage = 20

const toolTranslationKeys: Record<string, string> = {
  all: 'dashboard.myWorks.filters.all',
  background_removal: 'dashboard.myWorks.filters.background_removal',
  product_scene: 'dashboard.myWorks.filters.product_scene',
  try_on: 'dashboard.myWorks.filters.try_on',
  room_redesign: 'dashboard.myWorks.filters.room_redesign',
  short_video: 'dashboard.myWorks.filters.short_video',
  ai_avatar: 'dashboard.myWorks.filters.ai_avatar',
  pattern_generate: 'dashboard.myWorks.filters.pattern_generate',
  effect: 'dashboard.myWorks.filters.effect',
}

const filterDefinitions = Object.keys(toolTranslationKeys).map(id => ({ id }))
const filters = computed(() => filterDefinitions.map(filter => ({
  id: filter.id,
  label: t(toolTranslationKeys[filter.id]),
})))

// Social media sharing
const showShareModal = ref(false)
const shareTarget = ref<UserGeneration | null>(null)

const isSubscribed = computed(() => {
  if (authStore.isAdmin) return true
  const plan = authStore.user?.plan_type
  return plan && plan !== 'free' && plan !== 'demo'
})

async function fetchWorks() {
  if (authStore.isAdmin) return
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      page: currentPage.value,
      per_page: perPage,
      show_expired: showExpired.value,
    }
    if (selectedFilter.value !== 'all') {
      params.tool_type = selectedFilter.value
    }
    const { data } = await userApi.getGenerations(params as any)
    works.value = data.items
    totalWorks.value = data.total
  } catch {
    works.value = []
    totalWorks.value = 0
  } finally {
    loading.value = false
  }
}

async function redirectAdminAway(): Promise<boolean> {
  if (!authStore.user && authStore.accessToken) {
    try { await authStore.fetchUser() } catch { /* route guard handles unauthenticated users */ }
  }
  if (authStore.isAdmin) {
    await router.replace({ name: 'admin-dashboard' })
    return true
  }
  return false
}

onMounted(async () => {
  if (await redirectAdminAway()) return
  await fetchWorks()
})

watch(() => authStore.isAdmin, (isAdmin) => {
  if (isAdmin) {
    router.replace({ name: 'admin-dashboard' })
  }
}, { immediate: true })

watch([selectedFilter, showExpired], () => {
  if (authStore.isAdmin) return
  currentPage.value = 1
  fetchWorks()
})

const totalPages = computed(() => Math.ceil(totalWorks.value / perPage))

function changePage(page: number) {
  if (page < 1 || page > totalPages.value) return
  currentPage.value = page
  fetchWorks()
}

const selectedWork = ref<UserGeneration | null>(null)
const deleting = ref(false)

function openWork(work: UserGeneration) {
  selectedWork.value = work
}

function closeModal() {
  selectedWork.value = null
}

function getThumbnail(work: UserGeneration): string {
  if (work.media_expired) return ''
  return work.result_image_url || work.result_video_url || work.input_image_url || ''
}

function isVideo(work: UserGeneration): boolean {
  return !!work.result_video_url && !work.media_expired
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(locale.value)
}

function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString(locale.value)
}

/** 取得過期倒數文字 */
function getExpiryLabel(work: UserGeneration): string {
  if (work.media_expired) return t('dashboard.myWorks.expiry.expired')
  if (!work.expires_at) return ''
  const hours = work.hours_until_expiry ?? 0
  const days = work.days_until_expiry ?? 0
  if (hours <= 0) return t('dashboard.myWorks.expiry.soon')
  if (hours < 24) return t('dashboard.myWorks.expiry.hours', { hours })
  return t('dashboard.myWorks.expiry.days', { days })
}

/** 過期倒數的顏色 */
function getExpiryColor(work: UserGeneration): string {
  if (work.media_expired) return '#ff5050'
  const hours = work.hours_until_expiry ?? 999
  if (hours <= 24) return '#ff8c00'   // 橘色警告
  if (hours <= 72) return '#ffd700'   // 黃色提醒
  return '#4a7bb5'                     // 正常藍色
}

// Many distinct tools are persisted under a broad tool_type, which collapsed
// them to one gallery label (e.g. RoomRedesign / LandscapeAI / ExteriorAI /
// CommercialSpace / SketchToRender all → "毛胚屋/線稿秒渲染"; upscale / recolor /
// render-enhance / claymation all → "風格特效"). Disambiguate from the saved
// input_params (space_kind / tool / action) so the gallery shows the actual
// source tool. Falls back to the broad tool_type label for everything else.
function getToolName(work: { tool_type: string; input_params?: Record<string, unknown> | null }): string {
  const tt = work.tool_type
  const p = (work.input_params || {}) as Record<string, unknown>
  if (tt === 'room_redesign') {
    const sk = String(p.space_kind || 'interior')
    if (sk === 'exterior') return L('建築外觀渲染', 'Exterior Render', '建築外観レンダリング', '건축 외관 렌더링', 'Render de exteriores')
    if (sk === 'commercial') return L('商業空間設計', 'Commercial Space', '商業空間デザイン', '상업 공간 디자인', 'Espacio comercial')
    if (sk === 'landscape') return L('景觀設計', 'Landscape Design', '景観デザイン', '조경 디자인', 'Diseño de paisaje')
    return L('室內設計渲染', 'Interior Redesign', 'インテリアデザイン', '인테리어 리디자인', 'Rediseño de interiores')
  }
  if (tt === 'effect') {
    const hint = String(p.tool || p.action || '')
    if (hint === 'upscale') return L('圖片高清放大', 'HD Upscale', '高画質化', '고화질 확대', 'Mejora HD')
    if (hint === 'render_enhance') return L('渲染圖優化', 'Render Enhance', 'レンダー高画質化', '렌더 향상', 'Mejora de render')
    if (hint === 'recolor') return L('商品換色', 'Product Recolor', '商品の色変更', '제품 색상 변경', 'Recolorear producto')
    if (hint === 'claymation') return L('黏土風', 'Claymation', 'クレイ風', '클레이풍', 'Claymation')
    if (hint === 'video_background_remove') return L('影片去背', 'Video BG Remove', '動画背景除去', '영상 배경 제거', 'Quitar fondo de vídeo')
    return L('風格特效', 'Style Effect', 'スタイルエフェクト', '스타일 효과', 'Efecto de estilo')
  }
  const key = toolTranslationKeys[tt]
  return key ? t(key) : tt.replace(/_/g, ' ')
}

/** 取得生成參數的可讀摘要 */
function getParamsSummary(work: UserGeneration): string[] {
  const params = work.input_params || {}
  const summary: string[] = []
  if (params.style) summary.push(`${t('dashboard.myWorks.params.style')}：${params.style}`)
  if (params.prompt) summary.push(`${t('dashboard.myWorks.params.prompt')}：${String(params.prompt).slice(0, 50)}${String(params.prompt).length > 50 ? '...' : ''}`)
  if (params.model) summary.push(`${t('dashboard.myWorks.params.model')}：${params.model}`)
  if (params.scene) summary.push(`${t('dashboard.myWorks.params.scene')}：${params.scene}`)
  if (params.room_type) summary.push(`${t('dashboard.myWorks.params.roomType')}：${params.room_type}`)
  if (params.garment_type) summary.push(`${t('dashboard.myWorks.params.garmentType')}：${params.garment_type}`)
  return summary
}

async function downloadWork() {
  if (!selectedWork.value) return
  if (selectedWork.value.media_expired) {
    alert(t('dashboard.myWorks.downloadExpired'))
    return
  }
  const url = selectedWork.value.result_video_url || selectedWork.value.result_image_url
  if (!url) return
  try {
    await userApi.downloadGeneration(selectedWork.value.id)
  } catch (err: any) {
    alert(err?.response?.data?.detail || t('dashboard.myWorks.downloadExpired'))
    return
  }
  const link = document.createElement('a')
  link.href = url
  link.download = `${selectedWork.value.tool_type}-${selectedWork.value.id}.${isVideo(selectedWork.value) ? 'mp4' : 'png'}`
  link.target = '_blank'
  link.click()
}

async function deleteWork() {
  if (!selectedWork.value) return
  if (!confirm(t('dashboard.myWorks.deleteConfirm'))) return
  deleting.value = true
  try {
    await userApi.deleteGeneration(selectedWork.value.id)
    closeModal()
    await fetchWorks()
  } catch {
    // Handle error silently
  } finally {
    deleting.value = false
  }
}

function openShareModal(work: UserGeneration) {
  if (work.media_expired) {
    alert(t('dashboard.myWorks.shareExpired'))
    return
  }
  shareTarget.value = work
  showShareModal.value = true
  selectedWork.value = null
}

function closeShareModal() {
  showShareModal.value = false
  shareTarget.value = null
}
</script>

<template>
  <div class="min-h-screen pt-24 pb-20" style="background: #09090b;">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

      <!-- Header -->
      <div class="mb-8 flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 class="text-3xl font-bold mb-2" style="color: #e8f4ff;">{{ t('dashboard.myWorks.title') }}</h1>
          <p style="color: #6b9ab8;">{{ t('dashboard.myWorks.subtitle') }}</p>
        </div>
        <div class="flex items-center gap-3">
          <!-- 顯示過期作品切換 -->
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" v-model="showExpired" class="w-4 h-4 accent-cyan-400" />
            <span class="text-sm" style="color: #a8c8e8;">{{ t('dashboard.myWorks.showHistory') }}</span>
          </label>
          <router-link
            to="/dashboard/share-links"
            class="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border transition-all"
            style="background: rgba(0,184,230,0.05); border-color: rgba(0,184,230,0.2); color: #00b8e6;"
          >
            🔗 {{ t('dashboard.myWorks.socialAccounts') }}
          </router-link>
        </div>
      </div>

      <!-- 保存政策說明 Banner -->
      <div class="mb-6 p-4 rounded-xl flex items-start gap-3"
           style="background: rgba(0,184,230,0.05); border: 1px solid rgba(0,184,230,0.15);">
        <span class="text-lg flex-shrink-0">💾</span>
        <div>
          <p class="text-sm font-medium mb-1" style="color: #e8f4ff;">{{ t('dashboard.myWorks.mediaPolicyTitle') }}</p>
          <p class="text-xs" style="color: #6b9ab8;">
            {{ t('dashboard.myWorks.mediaPolicyCopy', { days: 14 }) }}
          </p>
        </div>
      </div>

      <!-- Filters -->
      <div class="flex flex-wrap gap-2 mb-8">
        <button
          v-for="filter in filters"
          :key="filter.id"
          @click="selectedFilter = filter.id"
          class="px-4 py-2 rounded-lg text-sm font-medium transition-all"
          :style="selectedFilter === filter.id
            ? 'background: linear-gradient(135deg, #00b8e6, #0066cc); color: white;'
            : 'background: rgba(255,255,255,0.05); color: #a8c8e8; border: 1px solid rgba(255,255,255,0.08);'"
        >
          {{ filter.label }}
        </button>
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="card text-center py-12">
        <div class="animate-spin w-8 h-8 border-2 border-t-transparent rounded-full mx-auto mb-4"
             style="border-color: #00b8e6; border-top-color: transparent;"></div>
        <p style="color: #6b9ab8;">{{ t('dashboard.myWorks.loading') }}</p>
      </div>

      <!-- Works Grid -->
      <div v-else-if="works.length > 0">
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          <div
            v-for="work in works"
            :key="work.id"
            class="rounded-2xl overflow-hidden group cursor-pointer transition-all"
            :style="work.media_expired
              ? 'background: #0c1830; border: 1px solid rgba(255,80,80,0.15); opacity: 0.85;'
              : 'background: #141420; border: 1px solid rgba(255,255,255,0.06);'"
            @mouseover="($event.currentTarget as HTMLElement).style.borderColor = work.media_expired ? 'rgba(255,80,80,0.3)' : 'rgba(0,184,230,0.3)'"
            @mouseleave="($event.currentTarget as HTMLElement).style.borderColor = work.media_expired ? 'rgba(255,80,80,0.15)' : 'rgba(0,184,230,0.1)'"
          >
            <!-- Thumbnail / Expired Placeholder -->
            <div class="aspect-square relative" @click="openWork(work)">
              <!-- 已過期：顯示歷史記錄圖示 -->
              <div v-if="work.media_expired"
                   class="w-full h-full flex flex-col items-center justify-center gap-2"
                   style="background: rgba(255,80,80,0.05);">
                <span class="text-4xl">📋</span>
                <span class="text-xs font-medium" style="color: #ff5050;">{{ t('dashboard.myWorks.mediaExpired') }}</span>
                <span class="text-xs" style="color: #6b9ab8;">{{ t('dashboard.myWorks.recordKept') }}</span>
              </div>
              <!-- 正常：顯示縮圖。BUG-001: video results were trying to
                   render `result_video_url` inside an <img>, which always
                   fails because browsers can't decode video URLs as image
                   sources. Render a <video> with poster + preload metadata
                   so the browser shows the first frame as the thumbnail
                   (falls back to the input image when the video itself
                   doesn't have a poster yet). -->
              <template v-else>
                <video
                  v-if="isVideo(work) && work.result_video_url"
                  :src="work.result_video_url"
                  :poster="work.input_image_url || undefined"
                  class="w-full h-full object-cover"
                  muted
                  playsinline
                  preload="metadata"
                />
                <img
                  v-else-if="getThumbnail(work)"
                  :src="getThumbnail(work)"
                  :alt="work.tool_type"
                  class="w-full h-full object-cover"
                  loading="lazy"
                />
                <div v-else class="w-full h-full flex items-center justify-center text-4xl"
                     style="background: rgba(0,184,230,0.05);">
                  🎨
                </div>
                <div v-if="isVideo(work)"
                     class="absolute top-2 right-2 text-xs px-2 py-1 rounded-full font-medium"
                     style="background: rgba(0,0,0,0.7); color: #00b8e6;">
                  ▶ {{ t('dashboard.myWorks.video') }}
                </div>
                <div class="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
                     style="background: rgba(10,22,40,0.7);">
                  <button class="px-4 py-2 rounded-lg text-sm font-medium"
                          style="background: linear-gradient(135deg, #00b8e6, #0066cc); color: white;">
                    {{ t('dashboard.myWorks.view') }}
                  </button>
                </div>
              </template>
            </div>

            <!-- Info + Actions -->
            <div class="p-4">
              <p class="text-sm font-medium capitalize mb-1" style="color: #e8f4ff;">
                {{ getToolName(work) }}
              </p>
              <div class="flex items-center justify-between text-xs mb-2" style="color: #4a7bb5;">
                <span>{{ formatDate(work.created_at) }}</span>
                <span>{{ t('dashboard.myWorks.creditsUsedShort', { credits: work.credits_used }) }}</span>
              </div>

              <!-- 過期倒數 / 已過期標示 -->
              <div v-if="work.expires_at || work.media_expired"
                   class="text-xs mb-3 px-2 py-1 rounded-lg flex items-center gap-1"
                   :style="`background: ${getExpiryColor(work)}18; color: ${getExpiryColor(work)};`">
                <span>{{ work.media_expired ? '🗂' : '⏳' }}</span>
                <span>{{ getExpiryLabel(work) }}</span>
              </div>

              <!-- Action Buttons -->
              <div class="flex gap-2">
                <button
                  @click="openWork(work)"
                  class="flex-1 py-1.5 rounded-lg text-xs font-medium transition-all border"
                  :style="work.media_expired
                    ? 'background: transparent; border-color: rgba(255,80,80,0.2); color: #ff8080;'
                    : 'background: transparent; border-color: rgba(0,184,230,0.2); color: #00b8e6;'"
                >
                  {{ work.media_expired ? `📋 ${t('dashboard.myWorks.record')}` : t('dashboard.myWorks.view') }}
                </button>
                <button
                  v-if="isSubscribed && !work.media_expired"
                  @click="openShareModal(work)"
                  class="flex-1 py-1.5 rounded-lg text-xs font-medium transition-all"
                  style="background: rgba(0,184,230,0.1); color: #00b8e6; border: 1px solid rgba(22,119,255,0.15);"
                  :title="t('dashboard.myWorks.publishSocial')"
                >
                  🔗 {{ t('dashboard.myWorks.publishShort') }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-center gap-2 mt-8">
          <button
            @click="changePage(currentPage - 1)"
            :disabled="currentPage <= 1"
            class="px-4 py-2 rounded-lg text-sm transition-all disabled:opacity-50"
            style="background: rgba(255,255,255,0.05); color: #a8c8e8; border: 1px solid rgba(255,255,255,0.08);"
          >
            {{ t('dashboard.myWorks.previous') }}
          </button>
          <span class="text-sm px-3" style="color: #6b9ab8;">
            {{ currentPage }} / {{ totalPages }}
          </span>
          <button
            @click="changePage(currentPage + 1)"
            :disabled="currentPage >= totalPages"
            class="px-4 py-2 rounded-lg text-sm transition-all disabled:opacity-50"
            style="background: rgba(255,255,255,0.05); color: #a8c8e8; border: 1px solid rgba(255,255,255,0.08);"
          >
            {{ t('dashboard.myWorks.next') }}
          </button>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="card text-center py-12">
        <span class="text-5xl block mb-4">🔍</span>
        <h3 class="text-lg font-medium mb-2" style="color: #e8f4ff;">{{ t('dashboard.myWorks.emptyTitle') }}</h3>
        <p style="color: #6b9ab8;">{{ t('dashboard.myWorks.emptyDesc') }}</p>
      </div>
    </div>

    <!-- ── Detail Modal ─────────────────────────────────────────────────── -->
    <Teleport to="body">
      <div
        v-if="selectedWork"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        style="background: rgba(0,0,0,0.85);"
        @click.self="closeModal"
      >
        <div class="relative rounded-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto"
             style="background: #141420; border: 1px solid rgba(22,119,255,0.15);">
          <!-- Close Button -->
          <button
            @click="closeModal"
            class="absolute top-4 right-4 z-10 w-10 h-10 rounded-full flex items-center justify-center transition-colors"
            style="background: rgba(255,255,255,0.1); color: #a8c8e8;"
          >
            ✕
          </button>

          <!-- ── 媒體已過期：顯示生成記錄 ── -->
          <div v-if="selectedWork.media_expired" class="p-8">
            <div class="text-center mb-6">
              <span class="text-6xl block mb-4">📋</span>
              <h3 class="text-xl font-bold mb-2" style="color: #e8f4ff;">{{ t('dashboard.myWorks.expiredTitle') }}</h3>
              <p class="text-sm" style="color: #6b9ab8;">
                {{ t('dashboard.myWorks.expiredDesc', { days: 14 }) }}
              </p>
            </div>

            <!-- 生成記錄卡片 -->
            <div class="rounded-xl p-5 mb-4" style="background: rgba(0,184,230,0.05); border: 1px solid rgba(0,0,0,0.08);">
              <h4 class="text-sm font-semibold mb-4 flex items-center gap-2" style="color: #00b8e6;">
                <span>🔧</span> {{ t('dashboard.myWorks.generationRecord') }}
              </h4>
              <div class="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <span class="block text-xs mb-1" style="color: #4a7bb5;">{{ t('dashboard.myWorks.tool') }}</span>
                  <span style="color: #e8f4ff;">{{ getToolName(selectedWork) }}</span>
                </div>
                <div>
                  <span class="block text-xs mb-1" style="color: #4a7bb5;">{{ t('dashboard.myWorks.createdAt') }}</span>
                  <span style="color: #e8f4ff;">{{ formatDateTime(selectedWork.created_at) }}</span>
                </div>
                <div>
                  <span class="block text-xs mb-1" style="color: #4a7bb5;">{{ t('dashboard.myWorks.creditsUsed') }}</span>
                  <span style="color: #e8f4ff;">{{ t('dashboard.myWorks.creditsUsedShort', { credits: selectedWork.credits_used }) }}</span>
                </div>
                <div v-if="selectedWork.expires_at">
                  <span class="block text-xs mb-1" style="color: #4a7bb5;">{{ t('dashboard.myWorks.expiryTime') }}</span>
                  <span style="color: #ff8080;">{{ formatDateTime(selectedWork.expires_at) }}</span>
                </div>
              </div>
            </div>

            <!-- 輸入文字 -->
            <div v-if="selectedWork.input_text"
                 class="rounded-xl p-4 mb-4"
                 style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06);">
              <h4 class="text-xs font-semibold mb-2" style="color: #4a7bb5;">{{ t('dashboard.myWorks.inputTextTitle') }}</h4>
              <p class="text-sm" style="color: #a8c8e8;">{{ selectedWork.input_text }}</p>
            </div>

            <!-- 生成參數 -->
            <div v-if="getParamsSummary(selectedWork).length > 0"
                 class="rounded-xl p-4 mb-4"
                 style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06);">
              <h4 class="text-xs font-semibold mb-3" style="color: #4a7bb5;">{{ t('dashboard.myWorks.paramsTitle') }}</h4>
              <div class="space-y-1">
                <p v-for="param in getParamsSummary(selectedWork)" :key="param"
                   class="text-sm" style="color: #a8c8e8;">
                  {{ param }}
                </p>
              </div>
            </div>

            <!-- 刪除按鈕 -->
            <div class="flex justify-end">
              <button
                @click="deleteWork"
                :disabled="deleting"
                class="py-2.5 px-6 rounded-xl font-medium text-sm transition-all border disabled:opacity-50"
                style="background: transparent; border-color: rgba(255,80,80,0.3); color: #ff5050;"
              >
                {{ deleting ? t('dashboard.myWorks.deleting') : `🗑 ${t('dashboard.myWorks.deleteRecord')}` }}
              </button>
            </div>
          </div>

          <!-- ── 媒體正常：顯示預覽 ── -->
          <template v-else>
            <!-- Image / Video -->
            <div class="aspect-square max-h-[60vh] overflow-hidden">
              <video
                v-if="isVideo(selectedWork)"
                :src="selectedWork.result_video_url!"
                controls
                class="w-full h-full object-contain"
                style="background: #0f0f17;"
              />
              <img
                v-else
                :src="getThumbnail(selectedWork)"
                :alt="selectedWork.tool_type"
                class="w-full h-full object-contain"
                style="background: #0f0f17;"
              />
            </div>

            <!-- Info -->
            <div class="p-6">
              <h3 class="text-lg font-bold mb-2" style="color: #e8f4ff;">
                {{ getToolName(selectedWork) }}
              </h3>
              <div class="flex items-center gap-4 text-sm mb-3" style="color: #6b9ab8;">
                <span>{{ t('dashboard.myWorks.createdOn', { date: formatDate(selectedWork.created_at) }) }}</span>
                <span>{{ t('dashboard.myWorks.creditsUsedInline', { credits: selectedWork.credits_used }) }}</span>
              </div>

              <!-- 過期倒數提示 -->
              <div v-if="selectedWork.expires_at && !selectedWork.media_expired"
                   class="mb-4 px-3 py-2 rounded-lg text-sm flex items-center gap-2"
                   :style="`background: ${getExpiryColor(selectedWork)}18; color: ${getExpiryColor(selectedWork)};`">
                <span>⏳</span>
                <span>
                  {{ t('dashboard.myWorks.mediaRetentionRemaining') }} <strong>{{ getExpiryLabel(selectedWork) }}</strong>
                  ({{ t('dashboard.myWorks.clearedAfter', { date: formatDateTime(selectedWork.expires_at) }) }})
                </span>
              </div>

              <p v-if="selectedWork.input_text" class="text-sm mb-5 line-clamp-2" style="color: #a8c8e8;">
                {{ selectedWork.input_text }}
              </p>

              <div class="flex gap-3 flex-wrap">
                <!-- 下載 -->
                <button @click="downloadWork"
                        class="flex-1 py-2.5 rounded-xl font-medium text-sm transition-all"
                        style="background: linear-gradient(135deg, #00b8e6, #0066cc); color: white;">
                  ⬇ {{ t('common.download') }}
                </button>

                <!-- 分享作品連結（付費會員） -->
                <button
                  v-if="isSubscribed"
                  @click="openShareModal(selectedWork)"
                  class="flex-1 py-2.5 rounded-xl font-medium text-sm transition-all border"
                  style="background: rgba(0,184,230,0.1); border-color: rgba(0,184,230,0.3); color: #00b8e6;"
                >
                  🔗 {{ t('dashboard.myWorks.publishSocial') }}
                </button>
                <router-link
                  v-else
                  to="/pricing"
                  @click="closeModal"
                  class="flex-1 py-2.5 rounded-xl font-medium text-sm transition-all border text-center"
                  style="background: rgba(255,165,0,0.1); border-color: rgba(255,165,0,0.3); color: #ffa500;"
                >
                  🔒 {{ t('dashboard.myWorks.upgradeToPublish') }}
                </router-link>

                <!-- 刪除 -->
                <button
                  @click="deleteWork"
                  :disabled="deleting"
                  class="py-2.5 px-4 rounded-xl font-medium text-sm transition-all border disabled:opacity-50"
                  style="background: transparent; border-color: rgba(255,80,80,0.3); color: #ff5050;"
                >
                  {{ deleting ? t('dashboard.myWorks.deleting') : t('common.delete') }}
                </button>
              </div>
            </div>
          </template>
        </div>
      </div>
    </Teleport>

    <!-- Share to Social Modal -->
    <ShareToSocialModal
      v-if="showShareModal && shareTarget"
      :generation-id="shareTarget.id"
      :tool-type="shareTarget.tool_type"
      :is-video="isVideo(shareTarget)"
      :media-url="shareTarget.result_video_url || shareTarget.result_image_url || undefined"
      @close="closeShareModal"
    />
  </div>
</template>
