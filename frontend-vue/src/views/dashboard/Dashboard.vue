<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore, useCreditsStore } from '@/stores'
import { userApi } from '@/api/user'
import type { UserGeneration, UserStatsResponse } from '@/api/user'

const { t, locale } = useI18n()
const authStore = useAuthStore()
const creditsStore = useCreditsStore()

const recentWorks = ref<UserGeneration[]>([])
const userStats = ref<UserStatsResponse | null>(null)
const loadingWorks = ref(false)

const isZh = computed(() => locale.value.startsWith('zh'))

const creditsProgressWidth = computed(() => {
  const total = creditsStore.balance?.total_credits ?? 0
  const remaining = creditsStore.balance?.remaining_credits ?? 0
  if (total <= 0) return '0%'
  return `${Math.round((remaining / total) * 100)}%`
})

const quickActions = computed(() => [
  { key: 'shortVideo', icon: '🎬', route: '/tools/short-video', label: t('dashboard.tools.shortVideo'), color: '#1677ff', bg: 'rgba(22,119,255,0.08)' },
  { key: 'avatar', icon: '🎭', route: '/tools/avatar', label: t('dashboard.tools.avatar'), color: '#722ed1', bg: 'rgba(114,46,209,0.08)' },
  { key: 'tryOn', icon: '👗', route: '/tools/try-on', label: t('dashboard.tools.tryOn'), color: '#eb2f96', bg: 'rgba(235,47,150,0.08)' },
  { key: 'productScene', icon: '📸', route: '/tools/product-scene', label: t('dashboard.tools.productScene'), color: '#fa8c16', bg: 'rgba(250,140,22,0.08)' },
  { key: 'backgroundRemoval', icon: '✂️', route: '/tools/background-removal', label: t('dashboard.tools.bgRemoval'), color: '#13c2c2', bg: 'rgba(19,194,194,0.08)' },
  { key: 'roomRedesign', icon: '🏠', route: '/tools/room-redesign', label: t('dashboard.tools.roomRedesign'), color: '#10b981', bg: 'rgba(16,185,129,0.08)' },
])

function getThumbnail(work: UserGeneration): string {
  return work.result_image_url || work.result_video_url || work.input_image_url || ''
}

function formatRelativeDate(dateStr: string): string {
  const now = new Date()
  const date = new Date(dateStr)
  const diffMs = now.getTime() - date.getTime()
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  if (diffHours < 1) return t('dashboard.time.justNow')
  if (diffHours < 24) return t('dashboard.time.hoursAgo', { n: diffHours })
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays === 1) return t('dashboard.time.yesterday')
  if (diffDays < 7) return t('dashboard.time.daysAgo', { n: diffDays })
  return date.toLocaleDateString()
}

onMounted(async () => {
  try {
    await creditsStore.fetchBalance()
    await creditsStore.fetchPricing()
  } catch {
    // Handle error silently
  }

  loadingWorks.value = true
  try {
    const [worksRes, statsRes] = await Promise.all([
      userApi.getGenerations({ page: 1, per_page: 3 }),
      userApi.getStats(),
    ])
    recentWorks.value = worksRes.data.items
    userStats.value = statsRes.data
  } catch {
    // Handle error silently
  } finally {
    loadingWorks.value = false
  }
})
</script>

<template>
  <div class="min-h-screen pt-20 pb-16" style="background: #09090b;">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

      <!-- Page Header -->
      <div class="py-8">
        <h1 class="text-2xl font-bold mb-1" style="color: #f5f5fa;">
          {{ t('dashboard.welcome') }}{{ isZh ? '，' : ', ' }}{{ authStore.user?.email?.split('@')[0] }}{{ isZh ? '！' : '!' }}
        </h1>
        <p class="text-sm" style="color: #6b6b8a;">{{ t('dashboard.subtitle') }}</p>
      </div>

      <!-- Stats Grid -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-5 mb-8">
        <!-- Credits -->
        <div class="rounded-xl p-6" style="background: #141420; border: 1px solid rgba(255,255,255,0.06); box-shadow: 0 2px 8px rgba(0,0,0,0.2);">
          <div class="flex items-center justify-between mb-4">
            <span class="text-sm font-medium" style="color: #6b6b8a;">{{ t('dashboard.remainingCredits') }}</span>
            <div class="w-9 h-9 rounded-lg flex items-center justify-center" style="background: rgba(22,119,255,0.08);">
              <svg class="w-5 h-5" style="color: #1677ff;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            </div>
          </div>
          <p class="text-3xl font-black mb-1" style="color: #f5f5fa;">{{ creditsStore.balance?.remaining_credits ?? 0 }}</p>
          <p class="text-xs" style="color: #6b6b8a;">{{ t('dashboard.totalOf', { n: creditsStore.balance?.total_credits ?? 0 }) }}</p>
          <div class="mt-3 h-1.5 rounded-full overflow-hidden" style="background: rgba(22,119,255,0.1);">
            <div class="h-full rounded-full transition-all" :style="{ background: '#1677ff', width: creditsProgressWidth }"></div>
          </div>
        </div>

        <!-- Used This Week -->
        <div class="rounded-xl p-6" style="background: #141420; border: 1px solid rgba(255,255,255,0.06); box-shadow: 0 2px 8px rgba(0,0,0,0.2);">
          <div class="flex items-center justify-between mb-4">
            <span class="text-sm font-medium" style="color: #6b6b8a;">{{ t('dashboard.usedThisWeek') }}</span>
            <div class="w-9 h-9 rounded-lg flex items-center justify-center" style="background: rgba(114,46,209,0.08);">
              <svg class="w-5 h-5" style="color: #722ed1;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
            </div>
          </div>
          <p class="text-3xl font-black mb-1" style="color: #f5f5fa;">{{ creditsStore.balance?.weekly_used ?? 0 }}</p>
          <p class="text-xs" style="color: #6b6b8a;">{{ t('dashboard.weeklyLimit', { n: creditsStore.balance?.weekly_limit ?? 0 }) }}</p>
        </div>

        <!-- Plan -->
        <div class="rounded-xl p-6" style="background: #141420; border: 1px solid rgba(255,255,255,0.06); box-shadow: 0 2px 8px rgba(0,0,0,0.2);">
          <div class="flex items-center justify-between mb-4">
            <span class="text-sm font-medium" style="color: #6b6b8a;">{{ t('dashboard.currentPlan') }}</span>
            <div class="w-9 h-9 rounded-lg flex items-center justify-center" style="background: rgba(250,140,22,0.08);">
              <svg class="w-5 h-5" style="color: #fa8c16;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"/></svg>
            </div>
          </div>
          <p class="text-3xl font-black mb-1 capitalize" style="color: #f5f5fa;">{{ authStore.user?.plan_type ?? 'Free' }}</p>
          <RouterLink to="/pricing" class="text-xs font-medium transition-colors hover:opacity-80" style="color: #1677ff;">
            {{ t('dashboard.upgradePlan') }} →
          </RouterLink>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="mb-8">
        <h2 class="text-base font-bold mb-4" style="color: #f5f5fa;">{{ t('dashboard.quickActions') }}</h2>
        <div class="grid grid-cols-3 md:grid-cols-6 gap-3">
          <RouterLink
            v-for="action in quickActions"
            :key="action.key"
            :to="action.route"
            class="rounded-xl p-4 text-center transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
            style="background: #141420; border: 1px solid rgba(255,255,255,0.06); box-shadow: 0 2px 6px rgba(0,0,0,0.2);"
          >
            <div class="w-10 h-10 rounded-xl flex items-center justify-center text-xl mx-auto mb-2.5"
              :style="'background: ' + action.bg">
              {{ action.icon }}
            </div>
            <span class="text-xs font-semibold" :style="'color: ' + action.color">{{ action.label }}</span>
          </RouterLink>
        </div>
      </div>

      <!-- Recent Works + Nav Links -->
      <div>
        <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
          <h2 class="text-base font-bold" style="color: #f5f5fa;">{{ t('dashboard.recentWorks') }}</h2>
          <div class="flex items-center gap-4">
            <RouterLink to="/dashboard/my-works" class="text-sm font-medium transition-colors hover:opacity-80" style="color: #1677ff;">
              {{ t('dashboard.viewAll') }} →
            </RouterLink>
            <RouterLink to="/dashboard/invoices" class="text-sm font-medium transition-colors hover:opacity-80" style="color: #6b6b8a;">
              {{ t('dashboard.invoices') }}
            </RouterLink>
            <RouterLink to="/dashboard/referrals" class="text-sm font-medium transition-colors hover:opacity-80" style="color: #6b6b8a;">
              🎁 {{ t('dashboard.referrals') }}
            </RouterLink>
            <RouterLink to="/dashboard/social-accounts" class="text-sm font-medium transition-colors hover:opacity-80" style="color: #6b6b8a;">
              📡 {{ t('dashboard.socialMedia') }}
            </RouterLink>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="loadingWorks" class="rounded-xl text-center py-10" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <div class="animate-spin w-6 h-6 border-2 border-t-transparent rounded-full mx-auto mb-2" style="border-color: #1677ff; border-top-color: transparent;"></div>
          <p class="text-sm" style="color: #6b6b8a;">{{ t('common.loading') }}...</p>
        </div>

        <div v-else-if="recentWorks.length > 0" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          <div
            v-for="work in recentWorks"
            :key="work.id"
            class="rounded-xl overflow-hidden group cursor-pointer transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
            style="background: #141420; border: 1px solid rgba(255,255,255,0.06);"
          >
            <div class="aspect-square relative">
              <img
                v-if="getThumbnail(work)"
                :src="getThumbnail(work)"
                :alt="work.tool_type"
                class="w-full h-full object-cover"
              />
              <div v-else class="w-full h-full flex items-center justify-center" style="background: #0f0f17;">
                <span class="text-3xl">🎨</span>
              </div>
              <div class="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center" style="background: rgba(0,0,0,0.5);">
                <RouterLink to="/dashboard/my-works" class="px-4 py-2 rounded text-xs font-bold text-white" style="background: #1677ff;">{{ t('dashboard.view') }}</RouterLink>
              </div>
            </div>
            <div class="px-3 py-2.5">
              <p class="text-xs font-semibold capitalize" style="color: #f5f5fa;">{{ work.tool_type.replace(/_/g, ' ') }}</p>
              <p class="text-xs mt-0.5" style="color: #6b6b8a;">{{ formatRelativeDate(work.created_at) }}</p>
            </div>
          </div>
        </div>

        <div v-else class="rounded-xl text-center py-16" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <span class="text-5xl block mb-4">🎨</span>
          <h3 class="text-base font-semibold mb-2" style="color: #f5f5fa;">{{ t('dashboard.noWorks') }}</h3>
          <p class="text-sm mb-6" style="color: #6b6b8a;">{{ t('dashboard.noWorksDesc') }}</p>
          <RouterLink to="/tools/short-video"
            class="inline-flex items-center gap-2 px-6 py-2.5 text-sm font-semibold text-white rounded transition-all hover:opacity-90"
            style="background: #1677ff;">
            {{ t('dashboard.startCreating') }}
          </RouterLink>
        </div>
      </div>

    </div>
  </div>
</template>
