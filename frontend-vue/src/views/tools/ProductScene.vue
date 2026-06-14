<script setup lang="ts">
// Tool hub page — top-level "what do you need?" launcher. Renamed in
// spirit on 2026-05-25 (legacy file name kept so router and "Recently
// Used" localStorage entries don't desync). The previous version was a
// single ungrouped grid; the brand-refresh adds category filter tabs
// inspired by piapi.ai's tool catalog so users can narrow by intent
// (Image / Video / Interior / Effects) instead of scanning all 22 tiles.
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import {
  toolHubTiles,
  getRecentTiles,
  pushRecentTool,
  TOOL_HUB_CATEGORIES,
  type ToolHubTile,
  type ToolHubCategory,
} from '@/data/toolHub'

const { t } = useI18n()
const router = useRouter()

const recentTiles = ref<ToolHubTile[]>([])
type CategoryFilter = 'all' | ToolHubCategory
const activeCategory = ref<CategoryFilter>('all')

const createTiles = computed<ToolHubTile[]>(() => {
  // Recents already render in their own section above — keep them out
  // of the main grid to avoid duplicate cards.
  const recentIds = new Set(recentTiles.value.map((tile) => tile.id))
  const pool = toolHubTiles.filter((tile) => !recentIds.has(tile.id))
  if (activeCategory.value === 'all') return pool
  return pool.filter((tile) => tile.category === activeCategory.value)
})

const categoryCounts = computed<Record<CategoryFilter, number>>(() => {
  const counts: Record<CategoryFilter, number> = {
    all: toolHubTiles.length,
    advertising: 0,
    interior: 0,
    exterior: 0,
    branding: 0,
    other: 0,
  }
  for (const tile of toolHubTiles) counts[tile.category]++
  return counts
})

onMounted(() => {
  recentTiles.value = getRecentTiles()
})

function openTile(tile: ToolHubTile): void {
  pushRecentTool(tile.id)
  router.push(tile.to)
}

function categoryLabel(cat: CategoryFilter): string {
  const key = `tools.hub.categories.${cat}`
  // Fall back to a Title-cased version of the id if the locale string
  // hasn't been translated yet.
  const translated = t(key)
  return translated === key ? cat.charAt(0).toUpperCase() + cat.slice(1) : translated
}
</script>

<template>
  <div class="min-h-screen pt-24 pb-20 bg-surface-page text-text-primary">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Back -->
      <button
        @click="router.back()"
        class="mb-6 flex items-center gap-2 text-text-muted hover:text-text-primary transition-colors"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
        {{ t('common.back') }}
      </button>

      <!-- Page title -->
      <div class="mb-8">
        <h1 class="text-3xl md:text-4xl font-bold text-text-primary">
          {{ t('tools.hub.pageTitle') }}
        </h1>
      </div>

      <!-- Recently Used -->
      <section v-if="recentTiles.length > 0" class="mb-10">
        <h2 class="text-sm font-semibold mb-4 text-text-subtle uppercase tracking-wider">
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

      <!-- Create with AI + category filter -->
      <section>
        <div class="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-4">
          <h2 class="text-sm font-semibold text-text-subtle uppercase tracking-wider">
            {{ t('tools.hub.createWithAi') }}
          </h2>

          <!-- Filter tabs — piapi.ai-style segmented control. Counts give
               users a quick sense of how rich each bucket is before they
               click; helps avoid the "tab looks empty" letdown. -->
          <div class="hub-cat-bar" role="tablist" :aria-label="t('tools.hub.categoryAria')">
            <button
              v-for="cat in (['all', ...TOOL_HUB_CATEGORIES] as CategoryFilter[])"
              :key="cat"
              role="tab"
              :aria-selected="activeCategory === cat"
              :class="['hub-cat-chip', activeCategory === cat ? 'is-active' : '']"
              @click="activeCategory = cat"
            >
              <span>{{ categoryLabel(cat) }}</span>
              <span class="hub-cat-count">{{ categoryCounts[cat] }}</span>
            </button>
          </div>
        </div>

        <div v-if="createTiles.length > 0" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
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
        <div v-else class="hub-empty">
          {{ t('tools.hub.emptyCategory') }}
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

/* Hover lifts on the cool brand-blue accent so the hub now feels visually
   continuous with Pricing.vue and RoomRedesign.vue. */
.hub-tile:hover {
  transform: translateY(-1px);
  border-color: rgba(22, 119, 255, 0.45);
  box-shadow: 0 8px 24px rgba(22, 119, 255, 0.18);
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

.hub-cat-bar {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  flex-wrap: wrap;
}

.hub-cat-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #9494b0;
  transition: background 0.15s ease, color 0.15s ease;
  text-transform: capitalize;
}

.hub-cat-chip:hover {
  color: #f5f5fa;
}

.hub-cat-chip.is-active {
  background: linear-gradient(135deg, #1677ff 0%, #7c3aed 100%);
  color: #ffffff;
  box-shadow: 0 2px 8px rgba(22, 119, 255, 0.30);
}

.hub-cat-count {
  font-size: 11px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: inherit;
  opacity: 0.85;
}

.hub-cat-chip.is-active .hub-cat-count {
  background: rgba(255, 255, 255, 0.20);
}

.hub-empty {
  padding: 48px 16px;
  text-align: center;
  color: #6b6b8a;
  font-size: 14px;
  border: 1px dashed rgba(255, 255, 255, 0.08);
  border-radius: 12px;
}
</style>
