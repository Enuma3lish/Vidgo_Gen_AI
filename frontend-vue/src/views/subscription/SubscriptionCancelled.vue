<script setup lang="ts">
/**
 * SubscriptionCancelled — landing page when PayPal redirects the user
 * back to vidgo.co after they declined to pay or cancelled on the
 * PayPal login screen.
 *
 * Designed to render IMMEDIATELY (this route is now eagerly imported
 * in router/index.ts so there's no chunk-load delay between the
 * PayPal redirect and the user seeing this page).
 *
 * If the user clicked Subscribe from /pricing before being sent to
 * PayPal, Pricing.vue stashed the plan + billing-cycle to
 * sessionStorage. We read it here so the "Retry" button can resume
 * the SAME plan instead of forcing the user to re-pick.
 */
import { onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { subscriptionApi } from '@/api'
import { useUIStore } from '@/stores'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const uiStore = useUIStore()

const pendingPlanId = ref<string | null>(null)
const pendingPlanName = ref<string>('')
const pendingBillingCycle = ref<string>('monthly')
const isRetrying = ref(false)

// PayPal redirects with subscription_id / ba_token / token query params
// when the user cancelled. We don't strictly need them, but surfacing
// helps the user understand what they're seeing.
const paypalToken = ref<string | null>(null)

onMounted(() => {
  paypalToken.value =
    (route.query.token as string) ||
    (route.query.ba_token as string) ||
    (route.query.subscription_id as string) ||
    null

  try {
    const raw = sessionStorage.getItem('vidgo.pendingPaypalSubscribe')
    if (raw) {
      const saved = JSON.parse(raw)
      // Stale entries (> 30 min) are ignored — user probably abandoned
      // the flow long ago.
      if (saved && saved.ts && Date.now() - saved.ts < 30 * 60 * 1000) {
        pendingPlanId.value = saved.plan_id || null
        pendingPlanName.value = saved.plan_name || ''
        pendingBillingCycle.value = saved.billing_cycle || 'monthly'
      }
    }
  } catch { /* sessionStorage disabled — non-fatal */ }
})

async function retrySamePlan() {
  if (!pendingPlanId.value) {
    router.push('/pricing')
    return
  }
  isRetrying.value = true
  try {
    const result = await subscriptionApi.subscribe({
      plan_id: pendingPlanId.value,
      billing_cycle: pendingBillingCycle.value as 'monthly' | 'yearly',
      payment_method: 'paypal',
    })
    if (result.success && result.checkout_url && !result.is_mock) {
      // Re-stamp the sessionStorage key so a second cancel still offers retry.
      sessionStorage.setItem(
        'vidgo.pendingPaypalSubscribe',
        JSON.stringify({
          plan_id: pendingPlanId.value,
          plan_name: pendingPlanName.value,
          billing_cycle: pendingBillingCycle.value,
          ts: Date.now(),
        }),
      )
      window.location.href = result.checkout_url
    } else {
      uiStore.showError(
        result.error ||
        t('subscription.retryFailed', '無法重新建立付款連結，請回到方案頁重試。'),
      )
      isRetrying.value = false
    }
  } catch (err: any) {
    const detail = err?.response?.data?.detail || err?.message
    uiStore.showError(
      detail || t('subscription.retryFailed', '無法重新建立付款連結，請回到方案頁重試。'),
    )
    isRetrying.value = false
  }
}

function goPricing() {
  router.push('/pricing')
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-4 py-24" style="background: #09090b;">
    <div class="max-w-md w-full">
      <div
        class="card p-8 text-center"
        style="background: #141420; border: 1px solid rgba(255,255,255,0.06);"
      >
        <div
          class="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-6"
          style="background: rgba(245,158,11,0.15);"
        >
          <svg class="w-8 h-8" style="color: #fbbf24;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M5.07 19h13.86a2 2 0 001.74-3l-6.93-12a2 2 0 00-3.48 0l-6.93 12a2 2 0 001.74 3z" />
          </svg>
        </div>

        <h1 class="text-2xl font-bold mb-2" style="color: #f5f5fa;">
          {{ t('subscription.paymentUnsuccessful', '訂閱未完成') }}
        </h1>
        <p class="mb-2" style="color: #c4c4d8;">
          {{ t('subscription.paymentUnsuccessfulDesc', '您在 PayPal 上取消了付款，沒有任何費用扣款。') }}
        </p>
        <p class="mb-6 text-sm" style="color: #9494b0;">
          {{ t('subscription.pleaseRetry', '請點擊下方按鈕重新訂閱，或回到方案頁挑選其他方案。') }}
        </p>

        <div v-if="pendingPlanId" class="space-y-3">
          <button
            type="button"
            class="btn-primary w-full py-3 font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="isRetrying"
            @click="retrySamePlan"
          >
            <span v-if="isRetrying">{{ t('common.loading', '載入中...') }}</span>
            <span v-else>
              {{ t('subscription.retrySamePlan', '重新訂閱') }}
              <span v-if="pendingPlanName" style="opacity: 0.7;">
                — {{ pendingPlanName }}
              </span>
            </span>
          </button>
          <button
            type="button"
            class="w-full py-2 rounded-xl text-sm"
            style="background: transparent; color: #9494b0; border: 1px solid rgba(255,255,255,0.08);"
            @click="goPricing"
          >
            {{ t('subscription.backToPricing', '回到方案頁') }}
          </button>
        </div>

        <button
          v-else
          type="button"
          class="btn-primary w-full py-3 font-semibold"
          @click="goPricing"
        >
          {{ t('subscription.backToPricing', '回到方案頁') }}
        </button>

        <p
          v-if="paypalToken"
          class="mt-6 text-xs"
          style="color: #5d5d7a; font-family: ui-monospace, SFMono-Regular, monospace;"
        >
          ref: {{ paypalToken }}
        </p>
      </div>
    </div>
  </div>
</template>
