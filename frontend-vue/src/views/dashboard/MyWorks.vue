<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { userApi } from '@/api/user'
import type { UserGeneration } from '@/api/user'

const { t } = useI18n()

const selectedFilter = ref('all')
const works = ref<UserGeneration[]>([])
const loading = ref(false)
const totalWorks = ref(0)
const currentPage = ref(1)
const perPage = 20

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
</script>

<template>
  <div class="min-h-screen pt-24 pb-20">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-3xl font-bold text-white mb-2">{{ t('nav.myWorks') }}</h1>
        <p class="text-gray-400">Browse and manage your generated content</p>
      </div>

      <!-- Filters -->
      <div class="flex flex-wrap gap-2 mb-8">
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

      <!-- Loading State -->
      <div v-if="loading" class="card text-center py-12">
        <div class="animate-spin w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full mx-auto mb-4"></div>
        <p class="text-gray-400">Loading your works...</p>
      </div>

      <!-- Works Grid -->
      <div v-else-if="works.length > 0">
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          <div
            v-for="work in works"
            :key="work.id"
            @click="openWork(work)"
            class="card p-0 overflow-hidden group cursor-pointer hover:border-primary-500/50 transition-all"
          >
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
      <div v-else class="card text-center py-12">
        <span class="text-5xl block mb-4">🔍</span>
        <h3 class="text-lg font-medium text-white mb-2">No works found</h3>
        <p class="text-gray-400">Try a different filter or create new content</p>
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
  </div>
</template>
