<script setup lang="ts">
// Tool hub page — formerly the Product Scene generator. The legacy
// scene-picker UI lives on as the Product Scene Classic route so existing
// links and the Material DB demo flow keep working; this view now acts as
// the top-level "what do you need?" launcher matching the visual mockup.
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { toolHubTiles, getRecentTiles, pushRecentTool, type ToolHubTile } from '@/data/toolHub'

const { t } = useI18n()
const router = useRouter()

const recentTiles = ref<ToolHubTile[]>([])
const createTiles = computed<ToolHubTile[]>(() => {
  const recentIds = new Set(recentTiles.value.map((tile) => tile.id))
  return toolHubTiles.filter((tile) => !recentIds.has(tile.id))
})

onMounted(() => {
  recentTiles.value = getRecentTiles()
})

function openTile(tile: ToolHubTile): void {
  pushRecentTool(tile.id)
  router.push(tile.to)
}
</script>

<template>
  <div class="min-h-screen pt-24 pb-20" style="background: #09090b; color: #f5f5fa;">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Back -->
      <button
        @click="router.back()"
        class="mb-6 flex items-center gap-2 text-dark-300 hover:text-dark-50 transition-colors"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
        {{ t('common.back') }}
      </button>

      <!-- Page title -->
      <div class="mb-8">
        <h1 class="text-3xl md:text-4xl font-bold text-dark-50">
          {{ t('tools.hub.pageTitle') }}
        </h1>
      </div>

      <!-- Recently Used -->
      <section v-if="recentTiles.length > 0" class="mb-10">
        <h2 class="text-sm font-semibold mb-4" style="color: #6b6b8a;">
          {{ t('tools.hub.recentlyUsed') }}
        </h2>
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
          <button
            v-for="tile in recentTiles"
            :key="tile.id"
            @click="openTile(tile)"
            class="hub-tile"
          >
            <span class="hub-tile-label">{{ t(tile.labelKey) }}</span>
            <img :src="tile.thumb" :alt="t(tile.labelKey)" class="hub-tile-thumb" />
          </button>
        </div>
      </section>

      <!-- Create with AI -->
      <section>
        <h2 class="text-sm font-semibold mb-4" style="color: #6b6b8a;">
          {{ t('tools.hub.createWithAi') }}
        </h2>
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
          <button
            v-for="tile in createTiles"
            :key="tile.id"
            @click="openTile(tile)"
            class="hub-tile"
          >
            <span class="hub-tile-label">{{ t(tile.labelKey) }}</span>
            <img :src="tile.thumb" :alt="t(tile.labelKey)" class="hub-tile-thumb" />
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.hub-tile {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 14px;
  background: #141420;
  border: 1px solid rgba(255, 255, 255, 0.06);
  text-align: left;
  overflow: hidden;
  transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
  min-height: 88px;
}

.hub-tile:hover {
  transform: translateY(-1px);
  border-color: rgba(245, 158, 11, 0.45);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
}

.hub-tile-label {
  font-size: 14px;
  font-weight: 600;
  color: #f5f5fa;
  line-height: 1.25;
  max-width: 55%;
  word-break: break-word;
}

.hub-tile-thumb {
  width: 72px;
  height: 56px;
  object-fit: cover;
  border-radius: 10px;
  background: #0f0f17;
  flex-shrink: 0;
}
</style>
