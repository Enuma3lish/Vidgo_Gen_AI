<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore, useCreditsStore } from '@/stores'

const { t } = useI18n()
const authStore = useAuthStore()
const creditsStore = useCreditsStore()

const recentWorks = ref([
  { id: 1, type: 'background_removal', thumbnail: 'https://picsum.photos/seed/work1/200/200', created: '2 hours ago' },
  { id: 2, type: 'product_scene', thumbnail: 'https://picsum.photos/seed/work2/200/200', created: '5 hours ago' },
  { id: 3, type: 'room_redesign', thumbnail: 'https://picsum.photos/seed/work3/200/200', created: 'Yesterday' }
])

const quickActions = [
  { key: 'backgroundRemoval', icon: '✂️', route: '/tools/background-removal', color: 'from-red-500 to-orange-500' },
  { key: 'productScene', icon: '🛍️', route: '/tools/product-scene', color: 'from-pink-500 to-rose-500' },
  { key: 'tryOn', icon: '👔', route: '/tools/try-on', color: 'from-purple-500 to-indigo-500' },
  { key: 'roomRedesign', icon: '🏠', route: '/tools/room-redesign', color: 'from-cyan-500 to-blue-500' },
  { key: 'shortVideo', icon: '🎬', route: '/tools/short-video', color: 'from-green-500 to-emerald-500' }
]

onMounted(async () => {
  try {
    await creditsStore.fetchBalance()
    await creditsStore.fetchPricing()
  } catch {
    // Handle error silently
  }
})
</script>

<template>
  <div class="min-h-screen pt-24 pb-20">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-3xl font-bold text-white mb-2">
          {{ t('dashboard.welcome') }}, {{ authStore.user?.email?.split('@')[0] }}!
        </h1>
        <p class="text-gray-400">Here's an overview of your account</p>
      </div>

      <!-- Stats Grid -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
        <!-- Total Credits -->
        <div class="card">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-gray-400 font-medium">{{ t('dashboard.totalCredits') }}</h3>
            <span class="text-2xl">💰</span>
          </div>
          <p class="text-4xl font-bold text-white">
            {{ creditsStore.balance?.remaining_credits ?? 0 }}
          </p>
          <p class="text-sm text-gray-500 mt-1">
            of {{ creditsStore.balance?.total_credits ?? 0 }} total
          </p>
        </div>

        <!-- Used This Week -->
        <div class="card">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-gray-400 font-medium">{{ t('dashboard.usedThisWeek') }}</h3>
            <span class="text-2xl">📊</span>
          </div>
          <p class="text-4xl font-bold text-white">
            {{ creditsStore.balance?.weekly_used ?? 0 }}
          </p>
          <p class="text-sm text-gray-500 mt-1">
            limit: {{ creditsStore.balance?.weekly_limit ?? 0 }} / week
          </p>
        </div>

        <!-- Plan -->
        <div class="card">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-gray-400 font-medium">Current Plan</h3>
            <span class="text-2xl">⭐</span>
          </div>
          <p class="text-4xl font-bold text-white capitalize">
            {{ authStore.user?.plan_type ?? 'Demo' }}
          </p>
          <RouterLink to="/pricing" class="text-sm text-primary-400 hover:text-primary-300 mt-1 inline-block">
            Upgrade plan →
          </RouterLink>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="mb-12">
        <h2 class="text-xl font-bold text-white mb-6">{{ t('dashboard.quickActions') }}</h2>
        <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
          <RouterLink
            v-for="action in quickActions"
            :key="action.key"
            :to="action.route"
            class="card hover:border-primary-500/50 transition-all group"
          >
            <div
              class="w-12 h-12 rounded-xl flex items-center justify-center mb-3 bg-gradient-to-br"
              :class="action.color"
            >
              <span class="text-2xl">{{ action.icon }}</span>
            </div>
            <h3 class="font-medium text-white group-hover:text-primary-400 transition-colors">
              {{ t(`tools.${action.key}.name`) }}
            </h3>
          </RouterLink>
        </div>
      </div>

      <!-- Recent Works -->
      <div>
        <div class="flex items-center justify-between mb-6">
          <h2 class="text-xl font-bold text-white">{{ t('dashboard.recentWorks') }}</h2>
          <RouterLink to="/dashboard/my-works" class="text-primary-400 hover:text-primary-300 text-sm font-medium">
            {{ t('dashboard.viewAll') }} →
          </RouterLink>
        </div>

        <div v-if="recentWorks.length > 0" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          <div
            v-for="work in recentWorks"
            :key="work.id"
            class="card p-0 overflow-hidden group cursor-pointer"
          >
            <div class="aspect-square relative">
              <img
                :src="work.thumbnail"
                :alt="work.type"
                class="w-full h-full object-cover"
              />
              <div class="absolute inset-0 bg-dark-900/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                <button class="btn-primary text-sm">View</button>
              </div>
            </div>
            <div class="p-3">
              <p class="text-sm text-white font-medium capitalize">{{ work.type.replace('_', ' ') }}</p>
              <p class="text-xs text-gray-500">{{ work.created }}</p>
            </div>
          </div>
        </div>

        <div v-else class="card text-center py-12">
          <span class="text-5xl block mb-4">🎨</span>
          <h3 class="text-lg font-medium text-white mb-2">No works yet</h3>
          <p class="text-gray-400 mb-4">Start creating to see your works here</p>
          <RouterLink to="/tools/background-removal" class="btn-primary">
            Start Creating
          </RouterLink>
        </div>
      </div>
    </div>
  </div>
</template>
