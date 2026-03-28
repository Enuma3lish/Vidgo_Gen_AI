<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import apiClient from '@/api/client'

const router = useRouter()
const route = useRoute()

const loading = ref(true)
const status = ref<'success' | 'pending' | 'failed' | 'unknown'>('pending')
const orderNumber = ref('')
const errorMsg = ref('')
const pollCount = ref(0)
const MAX_POLLS = 12  // Poll up to 12 times (60 seconds)

async function checkOrderStatus(order: string) {
  try {
    const response = await apiClient.get(`/api/v1/payments/ecpay/result?order=${order}`)
    const data = response.data
    if (data.success) {
      if (data.status === 'paid') {
        status.value = 'success'
        loading.value = false
        // Redirect to dashboard after 3 seconds
        setTimeout(() => router.replace('/dashboard'), 3000)
      } else if (data.status === 'pending' && pollCount.value < MAX_POLLS) {
        // Still pending - poll again after 5 seconds
        pollCount.value++
        setTimeout(() => checkOrderStatus(order), 5000)
      } else if (data.status === 'pending') {
        // Timeout - show pending message
        status.value = 'pending'
        loading.value = false
      } else {
        status.value = 'failed'
        loading.value = false
      }
    } else {
      status.value = 'unknown'
      errorMsg.value = data.error || '無法查詢訂單狀態'
      loading.value = false
    }
  } catch (err) {
    console.error('Failed to check order status:', err)
    status.value = 'unknown'
    errorMsg.value = '查詢訂單狀態時發生錯誤'
    loading.value = false
  }
}

onMounted(() => {
  const order = route.query.order as string
  if (order) {
    orderNumber.value = order
    // Start polling after 3 seconds (give ECPay callback time to process)
    setTimeout(() => checkOrderStatus(order), 3000)
  } else {
    status.value = 'unknown'
    errorMsg.value = '缺少訂單編號'
    loading.value = false
  }
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-4 py-24" style="background: #09090b;">
    <div class="max-w-md w-full text-center card p-8">

      <!-- Loading / Pending -->
      <div v-if="loading || status === 'pending'">
        <div class="w-16 h-16 bg-primary-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
          <svg class="w-8 h-8 text-primary-400 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
        <h1 class="text-2xl font-bold text-dark-900 mb-2">
          {{ loading ? '正在確認付款狀態...' : '付款處理中' }}
        </h1>
        <p class="text-dark-500 mb-4">
          {{ loading ? '請稍候，正在向 ECPay 確認您的付款結果' : '您的付款正在處理中，請稍後查看訂閱狀態' }}
        </p>
        <p v-if="orderNumber" class="text-sm text-dark-400">訂單編號：{{ orderNumber }}</p>
      </div>

      <!-- Success -->
      <div v-else-if="status === 'success'">
        <div class="w-16 h-16 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
          <svg class="w-8 h-8 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h1 class="text-2xl font-bold text-dark-900 mb-2">付款成功！</h1>
        <p class="text-dark-500 mb-4">您的訂閱已成功啟用，正在導向儀表板...</p>
        <p v-if="orderNumber" class="text-sm text-dark-400 mb-6">訂單編號：{{ orderNumber }}</p>
        <button
          type="button"
          class="btn-primary w-full"
          @click="router.replace('/dashboard')"
        >
          立即前往儀表板
        </button>
      </div>

      <!-- Failed -->
      <div v-else-if="status === 'failed'">
        <div class="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
          <svg class="w-8 h-8 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
        <h1 class="text-2xl font-bold text-dark-900 mb-2">付款失敗</h1>
        <p class="text-dark-500 mb-4">很抱歉，您的付款未能完成。請重新嘗試或聯繫客服。</p>
        <p v-if="orderNumber" class="text-sm text-dark-400 mb-6">訂單編號：{{ orderNumber }}</p>
        <button
          type="button"
          class="btn-primary w-full"
          @click="router.replace('/pricing')"
        >
          返回方案頁面
        </button>
      </div>

      <!-- Unknown -->
      <div v-else>
        <div class="w-16 h-16 bg-yellow-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
          <svg class="w-8 h-8 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h1 class="text-2xl font-bold text-dark-900 mb-2">無法確認付款狀態</h1>
        <p class="text-dark-500 mb-2">{{ errorMsg }}</p>
        <p class="text-sm text-dark-400 mb-6">如已完成付款，請前往儀表板確認訂閱狀態，或聯繫客服。</p>
        <div class="flex gap-3">
          <button
            type="button"
            class="flex-1 py-2 px-4 rounded-lg transition-colors"
            style="background: #141420; color: #9494b0; border: 1px solid rgba(255,255,255,0.06);"
            @click="router.replace('/pricing')"
          >
            返回方案頁面
          </button>
          <button
            type="button"
            class="flex-1 btn-primary"
            @click="router.replace('/dashboard')"
          >
            前往儀表板
          </button>
        </div>
      </div>

    </div>
  </div>
</template>
