<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { userApi } from '@/api/user'
import type { UserGeneration } from '@/api/user'
import ShareToSocialModal from '@/components/social/ShareToSocialModal.vue'

const { t } = useI18n()
const authStore = useAuthStore()

const selectedFilter = ref('all')
const showExpired = ref(true)   // 是否顯示已過期的作品（歷史記錄）
const works = ref<UserGeneration[]>([])
const loading = ref(false)
const totalWorks = ref(0)
const currentPage = ref(1)
const perPage = 20

const filters = [
  { id: 'all', label: '全部' },
  { id: 'background_removal', label: '去背' },
  { id: 'product_scene', label: '商品場景' },
  { id: 'try_on', label: '虛擬試穿' },
  { id: 'room_redesign', label: '室內設計' },
  { id: 'short_video', label: '短影音' },
  { id: 'ai_avatar', label: 'AI 頭像' },
  { id: 'pattern_generate', label: '圖案設計' },
  { id: 'effect', label: '風格特效' }
]

// Social media sharing
const showShareModal = ref(false)
const shareTarget = ref<UserGeneration | null>(null)

const isSubscribed = computed(() => {
  const plan = authStore.user?.plan_type
  return plan && plan !== 'free' && plan !== 'demo'
})

async function fetchWorks() {
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

onMounted(fetchWorks)

watch([selectedFilter, showExpired], () => {
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
  return new Date(dateStr).toLocaleDateString('zh-TW')
}

function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString('zh-TW')
}

/** 取得過期倒數文字 */
function getExpiryLabel(work: UserGeneration): string {
  if (work.media_expired) return '已過期'
  if (!work.expires_at) return ''
  const hours = work.hours_until_expiry ?? 0
  const days = work.days_until_expiry ?? 0
  if (hours <= 0) return '即將過期'
  if (hours < 24) return `${hours} 小時後過期`
  if (days <= 3) return `${days} 天後過期`
  return `${days} 天後過期`
}

/** 過期倒數的顏色 */
function getExpiryColor(work: UserGeneration): string {
  if (work.media_expired) return '#ff5050'
  const hours = work.hours_until_expiry ?? 999
  if (hours <= 24) return '#ff8c00'   // 橘色警告
  if (hours <= 72) return '#ffd700'   // 黃色提醒
  return '#4a7bb5'                     // 正常藍色
}

/** 取得工具類型的中文名稱 */
function getToolName(toolType: string): string {
  const names: Record<string, string> = {
    background_removal: '去背工具',
    product_scene: '商品場景',
    try_on: '虛擬試穿',
    room_redesign: '室內設計',
    short_video: '短影音',
    ai_avatar: 'AI 頭像',
    pattern_generate: '圖案設計',
    effect: '風格特效',
  }
  return names[toolType] || toolType.replace(/_/g, ' ')
}

/** 取得生成參數的可讀摘要 */
function getParamsSummary(work: UserGeneration): string[] {
  const params = work.input_params || {}
  const summary: string[] = []
  if (params.style) summary.push(`風格：${params.style}`)
  if (params.prompt) summary.push(`提示詞：${String(params.prompt).slice(0, 50)}${String(params.prompt).length > 50 ? '...' : ''}`)
  if (params.model) summary.push(`模型：${params.model}`)
  if (params.scene) summary.push(`場景：${params.scene}`)
  if (params.room_type) summary.push(`房型：${params.room_type}`)
  if (params.garment_type) summary.push(`服裝類型：${params.garment_type}`)
  return summary
}

async function downloadWork() {
  if (!selectedWork.value) return
  if (selectedWork.value.media_expired) {
    alert('此作品的媒體檔案已過期（超過14天），無法下載。\n您仍可查看生成記錄。')
    return
  }
  const url = selectedWork.value.result_video_url || selectedWork.value.result_image_url
  if (!url) return
  const link = document.createElement('a')
  link.href = url
  link.download = `${selectedWork.value.tool_type}-${selectedWork.value.id}.${isVideo(selectedWork.value) ? 'mp4' : 'png'}`
  link.target = '_blank'
  link.click()
}

async function deleteWork() {
  if (!selectedWork.value) return
  if (!confirm('確定要刪除此作品嗎？此操作無法復原，包含生成記錄。')) return
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
    alert('此作品的媒體檔案已過期，無法發布至社交媒體。')
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
  <div class="min-h-screen pt-24 pb-20" style="background: #f7f8fa;">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

      <!-- Header -->
      <div class="mb-8 flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 class="text-3xl font-bold mb-2" style="color: #e8f4ff;">我的作品庫</h1>
          <p style="color: #6b9ab8;">瀏覽並管理您的 AI 創作內容 · 媒體檔案保存 14 天</p>
        </div>
        <div class="flex items-center gap-3">
          <!-- 顯示過期作品切換 -->
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" v-model="showExpired" class="w-4 h-4 accent-cyan-400" />
            <span class="text-sm" style="color: #a8c8e8;">顯示歷史記錄</span>
          </label>
          <router-link
            to="/dashboard/social-accounts"
            class="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border transition-all"
            style="background: rgba(0,184,230,0.05); border-color: rgba(0,184,230,0.2); color: #00b8e6;"
          >
            📡 社交媒體帳號
          </router-link>
        </div>
      </div>

      <!-- 保存政策說明 Banner -->
      <div class="mb-6 p-4 rounded-xl flex items-start gap-3"
           style="background: rgba(0,184,230,0.05); border: 1px solid rgba(0,184,230,0.15);">
        <span class="text-lg flex-shrink-0">💾</span>
        <div>
          <p class="text-sm font-medium mb-1" style="color: #e8f4ff;">媒體保存政策</p>
          <p class="text-xs" style="color: #6b9ab8;">
            AI 生成的媒體檔案（圖片/影片）保存 <strong style="color: #00b8e6;">14 天</strong>，超過後將自動清除媒體 URL，但
            <strong style="color: #a8c8e8;">生成記錄永久保留</strong>（包含工具類型、參數設定、使用點數等）。
            請在期限內下載您的作品。
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
        <p style="color: #6b9ab8;">載入作品中...</p>
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
              : 'background: #ffffff; border: 1px solid rgba(0,0,0,0.08);'"
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
                <span class="text-xs font-medium" style="color: #ff5050;">媒體已過期</span>
                <span class="text-xs" style="color: #6b9ab8;">記錄已保留</span>
              </div>
              <!-- 正常：顯示縮圖 -->
              <template v-else>
                <img
                  v-if="getThumbnail(work)"
                  :src="getThumbnail(work)"
                  :alt="work.tool_type"
                  class="w-full h-full object-cover"
                />
                <div v-else class="w-full h-full flex items-center justify-center text-4xl"
                     style="background: rgba(0,184,230,0.05);">
                  🎨
                </div>
                <div v-if="isVideo(work)"
                     class="absolute top-2 right-2 text-xs px-2 py-1 rounded-full font-medium"
                     style="background: rgba(0,0,0,0.7); color: #00b8e6;">
                  ▶ 影片
                </div>
                <div class="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
                     style="background: rgba(10,22,40,0.7);">
                  <button class="px-4 py-2 rounded-lg text-sm font-medium"
                          style="background: linear-gradient(135deg, #00b8e6, #0066cc); color: white;">
                    查看
                  </button>
                </div>
              </template>
            </div>

            <!-- Info + Actions -->
            <div class="p-4">
              <p class="text-sm font-medium capitalize mb-1" style="color: #e8f4ff;">
                {{ getToolName(work.tool_type) }}
              </p>
              <div class="flex items-center justify-between text-xs mb-2" style="color: #4a7bb5;">
                <span>{{ formatDate(work.created_at) }}</span>
                <span>{{ work.credits_used }} 點</span>
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
                  {{ work.media_expired ? '📋 記錄' : '查看' }}
                </button>
                <button
                  v-if="isSubscribed && !work.media_expired"
                  @click="openShareModal(work)"
                  class="flex-1 py-1.5 rounded-lg text-xs font-medium transition-all"
                  style="background: rgba(0,184,230,0.1); color: #00b8e6; border: 1px solid rgba(22,119,255,0.15);"
                  title="發布至社交媒體"
                >
                  📡 發布
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
            上一頁
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
            下一頁
          </button>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="card text-center py-12">
        <span class="text-5xl block mb-4">🔍</span>
        <h3 class="text-lg font-medium mb-2" style="color: #e8f4ff;">尚無作品</h3>
        <p style="color: #6b9ab8;">嘗試其他篩選條件或建立新內容</p>
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
             style="background: #ffffff; border: 1px solid rgba(22,119,255,0.15);">
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
              <h3 class="text-xl font-bold mb-2" style="color: #e8f4ff;">媒體已過期</h3>
              <p class="text-sm" style="color: #6b9ab8;">
                此作品的媒體檔案已超過 14 天保存期限，已自動清除。<br>
                以下是完整的生成記錄，永久保存。
              </p>
            </div>

            <!-- 生成記錄卡片 -->
            <div class="rounded-xl p-5 mb-4" style="background: rgba(0,184,230,0.05); border: 1px solid rgba(0,0,0,0.08);">
              <h4 class="text-sm font-semibold mb-4 flex items-center gap-2" style="color: #00b8e6;">
                <span>🔧</span> 生成記錄
              </h4>
              <div class="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <span class="block text-xs mb-1" style="color: #4a7bb5;">工具</span>
                  <span style="color: #e8f4ff;">{{ getToolName(selectedWork.tool_type) }}</span>
                </div>
                <div>
                  <span class="block text-xs mb-1" style="color: #4a7bb5;">建立時間</span>
                  <span style="color: #e8f4ff;">{{ formatDateTime(selectedWork.created_at) }}</span>
                </div>
                <div>
                  <span class="block text-xs mb-1" style="color: #4a7bb5;">使用點數</span>
                  <span style="color: #e8f4ff;">{{ selectedWork.credits_used }} 點</span>
                </div>
                <div v-if="selectedWork.expires_at">
                  <span class="block text-xs mb-1" style="color: #4a7bb5;">過期時間</span>
                  <span style="color: #ff8080;">{{ formatDateTime(selectedWork.expires_at) }}</span>
                </div>
              </div>
            </div>

            <!-- 輸入文字 -->
            <div v-if="selectedWork.input_text"
                 class="rounded-xl p-4 mb-4"
                 style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06);">
              <h4 class="text-xs font-semibold mb-2" style="color: #4a7bb5;">輸入文字 / 提示詞</h4>
              <p class="text-sm" style="color: #a8c8e8;">{{ selectedWork.input_text }}</p>
            </div>

            <!-- 生成參數 -->
            <div v-if="getParamsSummary(selectedWork).length > 0"
                 class="rounded-xl p-4 mb-4"
                 style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06);">
              <h4 class="text-xs font-semibold mb-3" style="color: #4a7bb5;">生成參數</h4>
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
                {{ deleting ? '刪除中...' : '🗑 刪除記錄' }}
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
                style="background: #f7f8fa;"
              />
              <img
                v-else
                :src="getThumbnail(selectedWork)"
                :alt="selectedWork.tool_type"
                class="w-full h-full object-contain"
                style="background: #f7f8fa;"
              />
            </div>

            <!-- Info -->
            <div class="p-6">
              <h3 class="text-lg font-bold mb-2" style="color: #e8f4ff;">
                {{ getToolName(selectedWork.tool_type) }}
              </h3>
              <div class="flex items-center gap-4 text-sm mb-3" style="color: #6b9ab8;">
                <span>建立於：{{ formatDate(selectedWork.created_at) }}</span>
                <span>使用點數：{{ selectedWork.credits_used }}</span>
              </div>

              <!-- 過期倒數提示 -->
              <div v-if="selectedWork.expires_at && !selectedWork.media_expired"
                   class="mb-4 px-3 py-2 rounded-lg text-sm flex items-center gap-2"
                   :style="`background: ${getExpiryColor(selectedWork)}18; color: ${getExpiryColor(selectedWork)};`">
                <span>⏳</span>
                <span>
                  媒體保存剩餘：<strong>{{ getExpiryLabel(selectedWork) }}</strong>
                  （{{ formatDateTime(selectedWork.expires_at) }} 後清除）
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

                <!-- 發布至社交媒體（付費會員） -->
                <button
                  v-if="isSubscribed"
                  @click="openShareModal(selectedWork)"
                  class="flex-1 py-2.5 rounded-xl font-medium text-sm transition-all border"
                  style="background: rgba(0,184,230,0.1); border-color: rgba(0,184,230,0.3); color: #00b8e6;"
                >
                  📡 發布至社交媒體
                </button>
                <router-link
                  v-else
                  to="/pricing"
                  @click="closeModal"
                  class="flex-1 py-2.5 rounded-xl font-medium text-sm transition-all border text-center"
                  style="background: rgba(255,165,0,0.1); border-color: rgba(255,165,0,0.3); color: #ffa500;"
                >
                  🔒 升級以發布
                </router-link>

                <!-- 刪除 -->
                <button
                  @click="deleteWork"
                  :disabled="deleting"
                  class="py-2.5 px-4 rounded-xl font-medium text-sm transition-all border disabled:opacity-50"
                  style="background: transparent; border-color: rgba(255,80,80,0.3); color: #ff5050;"
                >
                  {{ deleting ? '刪除中...' : t('common.delete') }}
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
