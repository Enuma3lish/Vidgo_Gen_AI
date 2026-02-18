<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { apiClient } from '@/api'
import { useToast } from '@/composables'
import { useCreditsStore } from '@/stores'
import BaseButton from '@/components/atoms/BaseButton.vue'

const { t } = useI18n()
const toast = useToast()
const creditsStore = useCreditsStore()

interface RedeemedCode {
  code: string
  credits_added: number
  redeemed_at: string
  promotion_name?: string
}

const giftCode = ref('')
const loading = ref(false)
const successMessage = ref('')
const errorMessage = ref('')
const redeemedCodes = ref<RedeemedCode[]>([])
const loadingHistory = ref(false)

async function redeemCode() {
  if (!giftCode.value.trim()) {
    errorMessage.value = '請輸入兌換碼'
    return
  }

  loading.value = true
  successMessage.value = ''
  errorMessage.value = ''

  try {
    const response = await apiClient.post('/api/v1/promotions/redeem', {
      code: giftCode.value.trim()
    })

    const data = response.data
    successMessage.value = `兌換成功！已獲得 ${data.credits_added ?? ''} 點數。`
    giftCode.value = ''

    // Refresh credits balance and history
    await creditsStore.fetchBalance()
    await fetchHistory()
  } catch (err: unknown) {
    const e = err as { response?: { status?: number; data?: { detail?: string } } }
    if (e.response?.status === 404) {
      errorMessage.value = '兌換碼無效或已過期。'
    } else if (e.response?.status === 409) {
      errorMessage.value = '此兌換碼已被使用。'
    } else {
      errorMessage.value = e.response?.data?.detail || '兌換失敗，請稍後再試。'
    }
  } finally {
    loading.value = false
  }
}

async function fetchHistory() {
  loadingHistory.value = true
  try {
    const response = await apiClient.get('/api/v1/promotions/redeemed')
    redeemedCodes.value = response.data.items ?? response.data ?? []
  } catch {
    // Silently fail - history is optional
  } finally {
    loadingHistory.value = false
  }
}

function formatDate(iso: string): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString('zh-TW', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return iso
  }
}

onMounted(() => {
  fetchHistory()
})
</script>

<template>
  <div class="min-h-screen pt-24 pb-20">
    <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-3xl font-bold text-white mb-2">兌換碼</h1>
        <p class="text-gray-400">輸入您的兌換碼以獲取點數</p>
      </div>

      <!-- Back link -->
      <div class="mb-6">
        <RouterLink
          to="/dashboard"
          class="text-primary-400 hover:text-primary-300 text-sm font-medium"
        >
          ← {{ t('dashboard.backToDashboard', 'Back to Dashboard') }}
        </RouterLink>
      </div>

      <!-- Redeem Card -->
      <div class="card p-6 mb-8">
        <h2 class="text-lg font-semibold text-white mb-4">輸入兌換碼</h2>

        <div class="flex gap-3">
          <input
            v-model="giftCode"
            type="text"
            placeholder="請輸入兌換碼..."
            class="flex-1 px-4 py-3 bg-dark-700 border border-dark-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors font-mono text-lg tracking-wider uppercase"
            :disabled="loading"
            @keyup.enter="redeemCode"
          />
          <BaseButton variant="primary" :loading="loading" @click="redeemCode">
            兌換
          </BaseButton>
        </div>

        <!-- Success Message -->
        <div v-if="successMessage" class="mt-4 p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
          <div class="flex items-center gap-2">
            <svg class="w-5 h-5 text-green-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
            <p class="text-sm text-green-400">{{ successMessage }}</p>
          </div>
        </div>

        <!-- Error Message -->
        <div v-if="errorMessage" class="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
          <div class="flex items-center gap-2">
            <svg class="w-5 h-5 text-red-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="15" y1="9" x2="9" y2="15" />
              <line x1="9" y1="9" x2="15" y2="15" />
            </svg>
            <p class="text-sm text-red-400">{{ errorMessage }}</p>
          </div>
        </div>
      </div>

      <!-- Redeemed History -->
      <div class="card overflow-hidden p-0">
        <div class="px-6 py-4 border-b border-dark-600">
          <h2 class="text-lg font-semibold text-white">兌換紀錄</h2>
        </div>

        <!-- Loading -->
        <div v-if="loadingHistory" class="text-center py-8">
          <div class="animate-spin w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full mx-auto mb-2" />
          <p class="text-gray-400 text-sm">載入中...</p>
        </div>

        <!-- Table -->
        <div v-else-if="redeemedCodes.length > 0" class="overflow-x-auto">
          <table class="w-full">
            <thead class="bg-dark-800/80 border-b border-dark-600">
              <tr>
                <th class="text-left py-4 px-4 text-sm font-medium text-gray-400">兌換碼</th>
                <th class="text-left py-4 px-4 text-sm font-medium text-gray-400">活動名稱</th>
                <th class="text-right py-4 px-4 text-sm font-medium text-gray-400">獲得點數</th>
                <th class="text-right py-4 px-4 text-sm font-medium text-gray-400">兌換時間</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-dark-600">
              <tr
                v-for="record in redeemedCodes"
                :key="record.code"
                class="hover:bg-dark-700/50 transition-colors"
              >
                <td class="py-4 px-4">
                  <span class="text-white font-mono text-sm">{{ record.code }}</span>
                </td>
                <td class="py-4 px-4 text-gray-400 text-sm">
                  {{ record.promotion_name || '—' }}
                </td>
                <td class="py-4 px-4 text-right">
                  <span class="text-green-400 font-semibold">+{{ record.credits_added }}</span>
                </td>
                <td class="py-4 px-4 text-right text-gray-400 text-sm">
                  {{ formatDate(record.redeemed_at) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Empty state -->
        <div v-else class="text-center py-12 px-6">
          <span class="text-4xl block mb-3">🎁</span>
          <h3 class="text-base font-medium text-white mb-1">尚無兌換紀錄</h3>
          <p class="text-gray-400 text-sm">兌換後的紀錄將顯示在這裡</p>
        </div>
      </div>
    </div>
  </div>
</template>
