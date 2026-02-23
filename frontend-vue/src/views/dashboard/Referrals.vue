<template>
  <div class="min-h-screen bg-slate-900 text-slate-50 p-4 md:p-8">
    <div class="max-w-4xl mx-auto space-y-8">

      <!-- Header -->
      <div>
        <h1 class="text-3xl font-bold text-white">{{ $t('referrals.title') }}</h1>
        <p class="mt-1 text-slate-400">{{ $t('referrals.subtitle') }}</p>
      </div>

      <!-- Stats cards -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div class="bg-slate-800 rounded-xl p-5 border border-slate-700">
          <p class="text-sm text-slate-400">{{ $t('referrals.stats.invited') }}</p>
          <p class="text-3xl font-bold text-indigo-400 mt-1">{{ stats?.referral_count ?? 0 }}</p>
        </div>
        <div class="bg-slate-800 rounded-xl p-5 border border-slate-700">
          <p class="text-sm text-slate-400">{{ $t('referrals.stats.creditsEarned') }}</p>
          <p class="text-3xl font-bold text-emerald-400 mt-1">{{ stats?.credits_earned ?? 0 }}</p>
        </div>
        <div class="bg-slate-800 rounded-xl p-5 border border-slate-700">
          <p class="text-sm text-slate-400">{{ $t('referrals.stats.referredBy') }}</p>
          <p class="text-lg font-medium text-slate-300 mt-1 truncate">
            {{ stats?.referred_by ?? $t('referrals.stats.none') }}
          </p>
        </div>
      </div>

      <!-- Referral link card -->
      <div class="bg-gradient-to-br from-indigo-900/60 to-purple-900/60 rounded-2xl p-6 border border-indigo-700/40">
        <h2 class="text-xl font-semibold text-white mb-1">{{ $t('referrals.yourLink') }}</h2>
        <p class="text-slate-400 text-sm mb-4">{{ $t('referrals.linkDescription') }}</p>

        <!-- Referral URL display -->
        <div class="flex gap-2">
          <input
            :value="stats?.referral_url ?? ''"
            readonly
            class="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none"
          />
          <button
            @click="copyLink"
            class="shrink-0 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {{ copied ? $t('referrals.copied') : $t('referrals.copy') }}
          </button>
        </div>

        <!-- Share buttons -->
        <div class="flex flex-wrap gap-2 mt-4">
          <button
            v-for="channel in shareChannels"
            :key="channel.id"
            @click="share(channel)"
            class="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm border transition-colors"
            :class="channel.cls"
          >
            <span>{{ channel.icon }}</span>
            <span>{{ channel.label }}</span>
          </button>
        </div>
      </div>

      <!-- How it works -->
      <div class="bg-slate-800 rounded-2xl p-6 border border-slate-700">
        <h2 class="text-xl font-semibold text-white mb-4">{{ $t('referrals.howItWorks.title') }}</h2>
        <ol class="space-y-3">
          <li v-for="(step, i) in howItWorksSteps" :key="i" class="flex gap-3">
            <span class="w-7 h-7 shrink-0 rounded-full bg-indigo-600 text-white text-sm flex items-center justify-center font-bold">
              {{ i + 1 }}
            </span>
            <p class="text-slate-300 text-sm leading-relaxed pt-0.5">{{ step }}</p>
          </li>
        </ol>
      </div>

      <!-- Apply referral code (only if user hasn't been referred yet) -->
      <div v-if="!stats?.referred_by" class="bg-slate-800 rounded-2xl p-6 border border-slate-700">
        <h2 class="text-xl font-semibold text-white mb-1">{{ $t('referrals.applyCode.title') }}</h2>
        <p class="text-slate-400 text-sm mb-4">{{ $t('referrals.applyCode.description') }}</p>
        <div class="flex gap-2">
          <input
            v-model="applyCodeInput"
            :placeholder="$t('referrals.applyCode.placeholder')"
            class="flex-1 bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
          <button
            @click="applyCode"
            :disabled="!applyCodeInput || applyLoading"
            class="shrink-0 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
          >
            {{ applyLoading ? '...' : $t('referrals.applyCode.submit') }}
          </button>
        </div>
        <p v-if="applyMessage" class="mt-2 text-sm" :class="applySuccess ? 'text-emerald-400' : 'text-red-400'">
          {{ applyMessage }}
        </p>
      </div>

      <!-- Leaderboard -->
      <div class="bg-slate-800 rounded-2xl p-6 border border-slate-700">
        <h2 class="text-xl font-semibold text-white mb-4">{{ $t('referrals.leaderboard.title') }}</h2>
        <div v-if="leaderboard.length" class="space-y-2">
          <div
            v-for="entry in leaderboard"
            :key="entry.rank"
            class="flex items-center justify-between py-2 px-3 rounded-lg"
            :class="entry.rank <= 3 ? 'bg-indigo-900/30' : 'bg-slate-700/40'"
          >
            <div class="flex items-center gap-3">
              <span class="text-lg w-8 text-center">
                {{ entry.rank === 1 ? '🥇' : entry.rank === 2 ? '🥈' : entry.rank === 3 ? '🥉' : `#${entry.rank}` }}
              </span>
              <span class="text-slate-200 text-sm font-medium">{{ entry.username }}</span>
            </div>
            <span class="text-indigo-400 text-sm font-semibold">
              {{ entry.referral_count }} {{ $t('referrals.leaderboard.referrals') }}
            </span>
          </div>
        </div>
        <p v-else class="text-slate-500 text-sm">{{ $t('referrals.leaderboard.empty') }}</p>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { referralsApi } from '@/api/referrals'
import type { ReferralStatsResponse, LeaderboardEntry } from '@/api/referrals'

const { t } = useI18n()

const stats = ref<ReferralStatsResponse | null>(null)
const leaderboard = ref<LeaderboardEntry[]>([])
const copied = ref(false)
const applyCodeInput = ref('')
const applyLoading = ref(false)
const applyMessage = ref('')
const applySuccess = ref(false)

const howItWorksSteps = computed(() => [
  t('referrals.howItWorks.step1'),
  t('referrals.howItWorks.step2'),
  t('referrals.howItWorks.step3'),
])

const shareChannels = computed(() => {
  const url = stats.value?.referral_url ?? ''
  const text = t('referrals.shareText')
  return [
    {
      id: 'copy',
      icon: '🔗',
      label: t('referrals.share.copyLink'),
      cls: 'border-slate-600 text-slate-300 hover:border-indigo-500 hover:text-white',
      action: () => navigator.clipboard.writeText(url),
    },
    {
      id: 'line',
      icon: '💬',
      label: 'LINE',
      cls: 'border-green-700 text-green-400 hover:bg-green-900/30',
      action: () => window.open(`https://line.me/R/msg/text/?${encodeURIComponent(text + '\n' + url)}`),
    },
    {
      id: 'twitter',
      icon: '𝕏',
      label: 'X / Twitter',
      cls: 'border-slate-600 text-slate-300 hover:border-white hover:text-white',
      action: () => window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`),
    },
    {
      id: 'fb',
      icon: '📘',
      label: 'Facebook',
      cls: 'border-blue-700 text-blue-400 hover:bg-blue-900/30',
      action: () => window.open(`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`),
    },
  ]
})

async function copyLink() {
  if (!stats.value?.referral_url) return
  await navigator.clipboard.writeText(stats.value.referral_url)
  copied.value = true
  setTimeout(() => (copied.value = false), 2000)
}

function share(channel: { action: () => void }) {
  channel.action()
}

async function applyCode() {
  if (!applyCodeInput.value) return
  applyLoading.value = true
  applyMessage.value = ''
  try {
    const result = await referralsApi.applyCode(applyCodeInput.value.trim())
    applySuccess.value = result.success
    applyMessage.value = result.message
    if (result.success) {
      applyCodeInput.value = ''
      await loadStats()
    }
  } catch (err: any) {
    applySuccess.value = false
    applyMessage.value = err?.response?.data?.detail ?? t('referrals.applyCode.error')
  } finally {
    applyLoading.value = false
  }
}

async function loadStats() {
  try {
    stats.value = await referralsApi.getStats()
  } catch {
    // not authenticated or other error
  }
}

async function loadLeaderboard() {
  try {
    leaderboard.value = await referralsApi.getLeaderboard()
  } catch {
    // silently fail
  }
}

onMounted(async () => {
  await Promise.all([loadStats(), loadLeaderboard()])
})
</script>
