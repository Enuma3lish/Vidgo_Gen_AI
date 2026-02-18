<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { userApi } from '@/api/user'
import type { UserGeneration } from '@/api/user'
import { SocialShareModal } from '@/components/molecules'

const { t } = useI18n()
const router = useRouter()

const selectedFilter = ref('all')
const works = ref<UserGeneration[]>([])
const loading = ref(false)
const totalWorks = ref(0)
const currentPage = ref(1)
const perPage = 20

// Sort
const sortOrder = ref<'newest' | 'oldest'>('newest')

// Bulk select
const selectedIds = ref<Set<string>>(new Set())
const bulkDeleting = ref(false)

const allSelected = computed(() => {
  return works.value.length > 0 && works.value.every(w => selectedIds.value.has(w.id))
})

function toggleSelectAll() {
  if (allSelected.value) {
    selectedIds.value.clear()
  } else {
    works.value.forEach(w => selectedIds.value.add(w.id))
  }
  // Trigger reactivity
  selectedIds.value = new Set(selectedIds.value)
}

function toggleSelect(id: string) {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
  selectedIds.value = new Set(selectedIds.value)
}

async function deleteSelected() {
  if (selectedIds.value.size === 0) return
  bulkDeleting.value = true
  try {
    const ids = Array.from(selectedIds.value)
    await Promise.all(ids.map(id => userApi.deleteGeneration(id)))
    selectedIds.value = new Set()
    await fetchWorks()
  } catch {
    // Handle error silently
  } finally {
    bulkDeleting.value = false
  }
}

const filters = [
  { id: 'all', label: 'All' },
  { id: 'background_removal', label: 'Background Removal' },
  { id: 'product_scene', label: 'Product Scene' },
  { id: 'try_on', label: 'Virtual Try-On' },
  { id: 'room_redesign', label: 'Room Redesign' },
  { id: 'short_video', label: 'Short Video' },
  { id: 'ai_avatar', label: 'AI Avatar' },
  { id: 'pattern_generate', label: 'Pattern Design' },
  { id: 'effect', label: 'Style Effects' }
]

const sortedWorks = computed(() => {
  const list = [...works.value]
  if (sortOrder.value === 'oldest') {
    list.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
  } else {
    list.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  }
  return list
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
  selectedIds.value = new Set()
  fetchWorks()
})

const totalPages = computed(() => Math.ceil(totalWorks.value / perPage))

function changePage(page: number) {
  if (page < 1 || page > totalPages.value) return
  currentPage.value = page
  selectedIds.value = new Set()
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
  return new Date(dateStr).toLocaleDateString()
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

// Social share modal
const showShareModal = ref(false)
const shareUrl = ref('')

function shareWork() {
  if (!selectedWork.value) return
  const url = selectedWork.value.result_video_url || selectedWork.value.result_image_url
  if (url) {
    shareUrl.value = url
    showShareModal.value = true
  }
}

// Skeleton placeholder count
const skeletonCount = 8
</script>

<template>
  <div class="min-h-screen pt-24 pb-20">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-3xl font-bold text-white mb-2">{{ t('nav.myWorks') }}</h1>
        <p class="text-gray-400">Browse and manage your generated content</p>
      </div>

      <!-- Filters + Sort + Bulk Actions -->
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div class="flex flex-wrap gap-2">
          <button
            v-for="filter in filters"
            :key="filter.id"
            @click="selectedFilter = filter.id"
            class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="selectedFilter === filter.id
              ? 'bg-primary-500 text-white'
              : 'bg-dark-800 text-gray-400 hover:text-white'"
          >
            {{ filter.label }}
          </button>
        </div>

        <div class="flex items-center gap-3">
          <!-- Sort Dropdown -->
          <select
            v-model="sortOrder"
            class="bg-dark-800 border border-dark-600 text-gray-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500"
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
          </select>

          <!-- Bulk Delete Button -->
          <button
            v-if="selectedIds.size > 0"
            @click="deleteSelected"
            :disabled="bulkDeleting"
            class="px-4 py-2 rounded-lg text-sm font-medium bg-red-500/20 text-red-400 hover:bg-red-500/30 hover:text-red-300 transition-colors disabled:opacity-50"
          >
            {{ bulkDeleting ? 'Deleting...' : `Delete (${selectedIds.size})` }}
          </button>
        </div>
      </div>

      <!-- Select All Checkbox (shown when works exist and not loading) -->
      <div v-if="!loading && works.length > 0" class="flex items-center gap-3 mb-4">
        <label class="flex items-center gap-2 cursor-pointer text-sm text-gray-400 hover:text-white transition-colors">
          <input
            type="checkbox"
            :checked="allSelected"
            @change="toggleSelectAll"
            class="w-4 h-4 rounded border-dark-600 bg-dark-800 text-primary-500 focus:ring-primary-500 focus:ring-offset-0 cursor-pointer"
          />
          Select all
        </label>
        <span v-if="selectedIds.size > 0" class="text-xs text-gray-500">
          {{ selectedIds.size }} selected
        </span>
      </div>

      <!-- Loading Skeleton -->
      <div v-if="loading" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
        <div
          v-for="i in skeletonCount"
          :key="'skeleton-' + i"
          class="rounded-xl overflow-hidden border border-dark-700 bg-dark-800"
        >
          <div class="aspect-square bg-dark-700 animate-pulse" />
          <div class="p-4 space-y-3">
            <div class="h-4 bg-dark-700 rounded animate-pulse w-3/4" />
            <div class="flex justify-between">
              <div class="h-3 bg-dark-700 rounded animate-pulse w-1/3" />
              <div class="h-3 bg-dark-700 rounded animate-pulse w-1/4" />
            </div>
          </div>
        </div>
      </div>

      <!-- Works Grid -->
      <div v-else-if="works.length > 0">
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          <div
            v-for="work in sortedWorks"
            :key="work.id"
            class="card p-0 overflow-hidden group cursor-pointer hover:border-primary-500/50 transition-all relative"
          >
            <!-- Bulk Select Checkbox -->
            <div class="absolute top-2 left-2 z-10" @click.stop>
              <input
                type="checkbox"
                :checked="selectedIds.has(work.id)"
                @change="toggleSelect(work.id)"
                class="w-4 h-4 rounded border-dark-500 bg-dark-800/80 text-primary-500 focus:ring-primary-500 focus:ring-offset-0 cursor-pointer"
              />
            </div>

            <div @click="openWork(work)">
              <div class="aspect-square relative">
                <img
                  v-if="getThumbnail(work)"
                  :src="getThumbnail(work)"
                  :alt="work.tool_type"
                  class="w-full h-full object-cover"
                />
                <div v-else class="w-full h-full bg-dark-700 flex items-center justify-center">
                  <span class="text-gray-500 text-sm">No preview</span>
                </div>
                <div v-if="isVideo(work)" class="absolute top-2 right-2 bg-dark-900/80 text-white text-xs px-2 py-1 rounded">
                  Video
                </div>
                <div class="absolute inset-0 bg-dark-900/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                  <button class="btn-primary text-sm px-4 py-2">View</button>
                </div>
              </div>
              <div class="p-4">
                <p class="text-sm text-white font-medium capitalize mb-1">
                  {{ work.tool_type.replace(/_/g, ' ') }}
                </p>
                <div class="flex items-center justify-between text-xs text-gray-500">
                  <span>{{ formatDate(work.created_at) }}</span>
                  <span>{{ work.credits_used }} credits</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-center gap-2 mt-8">
          <button
            @click="changePage(currentPage - 1)"
            :disabled="currentPage <= 1"
            class="px-3 py-1 rounded bg-dark-800 text-gray-400 hover:text-white disabled:opacity-50"
          >
            Prev
          </button>
          <span class="text-gray-400 text-sm">
            {{ currentPage }} / {{ totalPages }}
          </span>
          <button
            @click="changePage(currentPage + 1)"
            :disabled="currentPage >= totalPages"
            class="px-3 py-1 rounded bg-dark-800 text-gray-400 hover:text-white disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="card text-center py-16 px-6">
        <div class="w-20 h-20 mx-auto mb-6 rounded-2xl bg-dark-700 flex items-center justify-center">
          <svg class="w-10 h-10 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </div>
        <h3 class="text-xl font-semibold text-white mb-2">No works yet</h3>
        <p class="text-gray-400 mb-8 max-w-md mx-auto">
          You haven't created any content yet. Get started with one of our AI tools to generate images, videos, and more.
        </p>
        <div class="flex flex-wrap justify-center gap-3">
          <button
            @click="router.push('/tools/product-scene')"
            class="btn-primary px-6 py-2.5"
          >
            Create Product Scene
          </button>
          <button
            @click="router.push('/tools/short-video')"
            class="px-6 py-2.5 rounded-xl border border-dark-600 text-gray-300 hover:text-white hover:border-primary-400 transition-colors"
          >
            Make a Short Video
          </button>
          <button
            @click="router.push('/')"
            class="px-6 py-2.5 rounded-xl border border-dark-600 text-gray-300 hover:text-white hover:border-primary-400 transition-colors"
          >
            Browse All Tools
          </button>
        </div>
      </div>
    </div>

    <!-- Detail Modal -->
    <Teleport to="body">
      <div
        v-if="selectedWork"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @click.self="closeModal"
      >
        <div class="absolute inset-0 bg-dark-900/80 backdrop-blur-sm" @click="closeModal" />

        <div class="relative bg-dark-800 rounded-2xl max-w-3xl w-full max-h-[90vh] overflow-hidden">
          <!-- Close Button -->
          <button
            @click="closeModal"
            class="absolute top-4 right-4 z-10 w-10 h-10 bg-dark-900/80 rounded-full flex items-center justify-center text-gray-400 hover:text-white"
          >
            ✕
          </button>

          <!-- Image / Video -->
          <div class="aspect-square max-h-[60vh] overflow-hidden">
            <video
              v-if="isVideo(selectedWork)"
              :src="selectedWork.result_video_url!"
              controls
              class="w-full h-full object-contain bg-dark-900"
            />
            <img
              v-else
              :src="getThumbnail(selectedWork)"
              :alt="selectedWork.tool_type"
              class="w-full h-full object-contain bg-dark-900"
            />
          </div>

          <!-- Info -->
          <div class="p-6">
            <h3 class="text-xl font-semibold text-white capitalize mb-2">
              {{ selectedWork.tool_type.replace(/_/g, ' ') }}
            </h3>
            <div class="flex items-center gap-4 text-sm text-gray-400 mb-4">
              <span>Created: {{ formatDate(selectedWork.created_at) }}</span>
              <span>Credits used: {{ selectedWork.credits_used }}</span>
            </div>
            <p v-if="selectedWork.input_text" class="text-sm text-gray-300 mb-6 line-clamp-2">
              {{ selectedWork.input_text }}
            </p>

            <div class="flex gap-3">
              <button @click="downloadWork" class="btn-primary flex-1">
                {{ t('common.download') }}
              </button>
              <button
                @click="shareWork"
                class="btn-ghost text-primary-400 hover:text-primary-300 hover:bg-primary-500/10"
              >
                <svg class="w-5 h-5 inline-block mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                </svg>
                Share
              </button>
              <button
                @click="deleteWork"
                :disabled="deleting"
                class="btn-ghost text-red-400 hover:text-red-300 hover:bg-red-500/10"
              >
                {{ deleting ? 'Deleting...' : t('common.delete') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Social Share Modal -->
    <SocialShareModal
      :visible="showShareModal"
      :content-url="shareUrl"
      :content-type="selectedWork && isVideo(selectedWork) ? 'video' : 'image'"
      @close="showShareModal = false"
    />
  </div>
</template>
