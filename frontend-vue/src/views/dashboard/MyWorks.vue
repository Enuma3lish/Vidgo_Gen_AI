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

watch(selectedFilter, () => {
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
  return work.result_image_url || work.result_video_url || work.input_image_url || ''
}

function isVideo(work: UserGeneration): boolean {
  return !!work.result_video_url
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('zh-TW')
}

async function downloadWork() {
  if (!selectedWork.value) return
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
  shareTarget.value = work
  showShareModal.value = true
  // Close detail modal if open
  selectedWork.value = null
}

function closeShareModal() {
  showShareModal.value = false
  shareTarget.value = null
}
</script>

<template>
  <div class="min-h-screen pt-24 pb-20" style="background: #0a1628;">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Header -->
      <div class="mb-8 flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 class="text-3xl font-bold mb-2" style="color: #e8f4ff;">{{ t('nav.myWorks') }}</h1>
          <p style="color: #6b9ab8;">瀏覽並管理您的 AI 創作內容</p>
        </div>
        <router-link
          to="/dashboard/social-accounts"
          class="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border transition-all"
          style="background: rgba(0,184,230,0.05); border-color: rgba(0,184,230,0.2); color: #00b8e6;"
        >
          📡 社交媒體帳號
        </router-link>
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
            style="background: #0f1f3d; border: 1px solid rgba(0,184,230,0.1);"
            @mouseover="($event.currentTarget as HTMLElement).style.borderColor = 'rgba(0,184,230,0.3)'"
            @mouseleave="($event.currentTarget as HTMLElement).style.borderColor = 'rgba(0,184,230,0.1)'"
          >
            <!-- Thumbnail -->
            <div class="aspect-square relative" @click="openWork(work)">
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
            </div>

            <!-- Info + Actions -->
            <div class="p-4">
              <p class="text-sm font-medium capitalize mb-1" style="color: #e8f4ff;">
                {{ work.tool_type.replace(/_/g, ' ') }}
              </p>
              <div class="flex items-center justify-between text-xs mb-3" style="color: #4a7bb5;">
                <span>{{ formatDate(work.created_at) }}</span>
                <span>{{ work.credits_used }} 點</span>
              </div>

              <!-- Action Buttons -->
              <div class="flex gap-2">
                <button
                  @click="openWork(work)"
                  class="flex-1 py-1.5 rounded-lg text-xs font-medium transition-all border"
                  style="background: transparent; border-color: rgba(0,184,230,0.2); color: #00b8e6;"
                >
                  查看
                </button>
                <button
                  v-if="isSubscribed"
                  @click="openShareModal(work)"
                  class="flex-1 py-1.5 rounded-lg text-xs font-medium transition-all"
                  style="background: rgba(0,184,230,0.1); color: #00b8e6; border: 1px solid rgba(0,184,230,0.2);"
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

    <!-- Detail Modal -->
    <Teleport to="body">
      <div
        v-if="selectedWork"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        style="background: rgba(0,0,0,0.85);"
        @click.self="closeModal"
      >
        <div class="relative rounded-2xl max-w-3xl w-full max-h-[90vh] overflow-hidden"
             style="background: #0f1f3d; border: 1px solid rgba(0,184,230,0.2);">
          <!-- Close Button -->
          <button
            @click="closeModal"
            class="absolute top-4 right-4 z-10 w-10 h-10 rounded-full flex items-center justify-center transition-colors"
            style="background: rgba(255,255,255,0.1); color: #a8c8e8;"
          >
            ✕
          </button>

          <!-- Image / Video -->
          <div class="aspect-square max-h-[60vh] overflow-hidden">
            <video
              v-if="isVideo(selectedWork)"
              :src="selectedWork.result_video_url!"
              controls
              class="w-full h-full object-contain"
              style="background: #0a1628;"
            />
            <img
              v-else
              :src="getThumbnail(selectedWork)"
              :alt="selectedWork.tool_type"
              class="w-full h-full object-contain"
              style="background: #0a1628;"
            />
          </div>

          <!-- Info -->
          <div class="p-6">
            <h3 class="text-xl font-semibold capitalize mb-2" style="color: #e8f4ff;">
              {{ selectedWork.tool_type.replace(/_/g, ' ') }}
            </h3>
            <div class="flex items-center gap-4 text-sm mb-4" style="color: #6b9ab8;">
              <span>建立於：{{ formatDate(selectedWork.created_at) }}</span>
              <span>使用點數：{{ selectedWork.credits_used }}</span>
            </div>
            <p v-if="selectedWork.input_text" class="text-sm mb-6 line-clamp-2" style="color: #a8c8e8;">
              {{ selectedWork.input_text }}
            </p>

            <div class="flex gap-3 flex-wrap">
              <button @click="downloadWork"
                      class="flex-1 py-2.5 rounded-xl font-medium text-sm transition-all"
                      style="background: linear-gradient(135deg, #00b8e6, #0066cc); color: white;">
                ⬇ {{ t('common.download') }}
              </button>

              <!-- Share to Social Button (Subscribers Only) -->
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
