<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const selectedFilter = ref('all')
const works = ref([
  { id: 1, type: 'background_removal', thumbnail: 'https://picsum.photos/seed/w1/400/400', created: '2024-01-15', credits: 5 },
  { id: 2, type: 'product_scene', thumbnail: 'https://picsum.photos/seed/w2/400/400', created: '2024-01-14', credits: 10 },
  { id: 3, type: 'room_redesign', thumbnail: 'https://picsum.photos/seed/w3/400/400', created: '2024-01-14', credits: 15 },
  { id: 4, type: 'try_on', thumbnail: 'https://picsum.photos/seed/w4/400/400', created: '2024-01-13', credits: 10 },
  { id: 5, type: 'short_video', thumbnail: 'https://picsum.photos/seed/w5/400/400', created: '2024-01-12', credits: 25 },
  { id: 6, type: 'background_removal', thumbnail: 'https://picsum.photos/seed/w6/400/400', created: '2024-01-11', credits: 5 }
])

const filters = [
  { id: 'all', label: 'All' },
  { id: 'background_removal', label: 'Background Removal' },
  { id: 'product_scene', label: 'Product Scene' },
  { id: 'try_on', label: 'Virtual Try-On' },
  { id: 'room_redesign', label: 'Room Redesign' },
  { id: 'short_video', label: 'Short Video' }
]

const filteredWorks = computed(() => {
  if (selectedFilter.value === 'all') return works.value
  return works.value.filter(w => w.type === selectedFilter.value)
})

const selectedWork = ref<typeof works.value[0] | null>(null)

function openWork(work: typeof works.value[0]) {
  selectedWork.value = work
}

function closeModal() {
  selectedWork.value = null
}

function downloadWork() {
  if (!selectedWork.value) return
  const link = document.createElement('a')
  link.href = selectedWork.value.thumbnail
  link.download = `${selectedWork.value.type}-${selectedWork.value.id}.png`
  link.click()
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

      <!-- Works Grid -->
      <div v-if="filteredWorks.length > 0" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
        <div
          v-for="work in filteredWorks"
          :key="work.id"
          @click="openWork(work)"
          class="card p-0 overflow-hidden group cursor-pointer hover:border-primary-500/50 transition-all"
        >
          <div class="aspect-square relative">
            <img
              :src="work.thumbnail"
              :alt="work.type"
              class="w-full h-full object-cover"
            />
            <div class="absolute inset-0 bg-dark-900/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
              <button class="btn-primary text-sm px-4 py-2">View</button>
            </div>
          </div>
          <div class="p-4">
            <p class="text-sm text-white font-medium capitalize mb-1">
              {{ work.type.replace(/_/g, ' ') }}
            </p>
            <div class="flex items-center justify-between text-xs text-gray-500">
              <span>{{ work.created }}</span>
              <span>{{ work.credits }} credits</span>
            </div>
          </div>
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

          <!-- Image -->
          <div class="aspect-square max-h-[60vh] overflow-hidden">
            <img
              :src="selectedWork.thumbnail"
              :alt="selectedWork.type"
              class="w-full h-full object-contain bg-dark-900"
            />
          </div>

          <!-- Info -->
          <div class="p-6">
            <h3 class="text-xl font-semibold text-white capitalize mb-2">
              {{ selectedWork.type.replace(/_/g, ' ') }}
            </h3>
            <div class="flex items-center gap-4 text-sm text-gray-400 mb-6">
              <span>Created: {{ selectedWork.created }}</span>
              <span>Credits used: {{ selectedWork.credits }}</span>
            </div>

            <div class="flex gap-3">
              <button @click="downloadWork" class="btn-primary flex-1">
                {{ t('common.download') }}
              </button>
              <button class="btn-secondary">
                Regenerate
              </button>
              <button class="btn-ghost text-red-400 hover:text-red-300 hover:bg-red-500/10">
                {{ t('common.delete') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
