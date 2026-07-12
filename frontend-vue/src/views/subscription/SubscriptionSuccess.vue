<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { creditsApi } from '@/api'
import { useCreditsStore } from '@/stores'
import { useDemoMode } from '@/composables/useDemoMode'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const orderNumber = route.query.order as string

// One-time PayPal orders (credit packs) come back with ?token=<order id> and
// need a server-side CAPTURE before any money moves. Subscriptions redirect
// with ?subscription_id (their token is a BA-* agreement id) and are
// activated by webhooks — no capture leg.
const payPalToken = route.query.token as string | undefined
const isOrderCapture = Boolean(payPalToken && !route.query.subscription_id)

// 'confirming' → capture in flight; 'confirmed' → captured (or nothing to
// capture); 'pending' → capture didn't confirm — the webhook will finish it.
const captureState = ref<'confirming' | 'confirmed' | 'pending'>(
  isOrderCapture ? 'confirming' : 'confirmed',
)

const creditsStore = useCreditsStore()
const { refreshSubscription } = useDemoMode()

onMounted(async () => {
  if (isOrderCapture && payPalToken) {
    try {
      const res = await creditsApi.capturePayPalOrder(payPalToken, orderNumber)
      captureState.value = res.success ? 'confirmed' : 'pending'
    } catch {
      // 404/409/network — the CHECKOUT.ORDER.APPROVED webhook still captures
      // server-side, so show "processing" instead of an error.
      captureState.value = 'pending'
    }
  }
  // Reflect the new plan/credits immediately (audit #10): force-refresh the
  // shared subscription cache and the balance so the header + tool gating
  // update without a hard reload. Best-effort — never block the page.
  refreshSubscription().catch(() => { /* non-fatal */ })
  creditsStore.reconcileBalance(500)
  // Subscribe flow completed — clear the pending-subscribe breadcrumb so it
  // can't resurface on a later /pricing visit (audit #11 storage hygiene).
  try { sessionStorage.removeItem('vidgo.pendingPaypalSubscribe') } catch { /* private mode */ }
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-4 py-24" style="background: #09090b;">
    <div class="max-w-md w-full text-center card p-8">
      <div
        v-if="captureState === 'confirming'"
        class="w-16 h-16 bg-blue-500/20 rounded-full flex items-center justify-center mx-auto mb-6"
      >
        <svg class="w-8 h-8 text-blue-400 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
        </svg>
      </div>
      <div
        v-else
        class="w-16 h-16 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-6"
      >
        <svg class="w-8 h-8 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
        </svg>
      </div>

      <template v-if="captureState === 'confirming'">
        <h1 class="text-2xl font-bold text-dark-900 mb-2">
          {{ t('subscription.paymentConfirming', 'Confirming payment…') }}
        </h1>
        <p class="text-dark-500 mb-6">
          {{ t('subscription.paymentConfirmingDesc', 'We are confirming your PayPal payment. This only takes a moment.') }}
        </p>
      </template>
      <template v-else-if="captureState === 'pending'">
        <h1 class="text-2xl font-bold text-dark-900 mb-2">
          {{ t('subscription.paymentProcessing', 'Payment processing') }}
        </h1>
        <p class="text-dark-500 mb-6">
          {{ t('subscription.paymentProcessingDesc', 'PayPal is finalizing your payment. Your credits will be added automatically within a few minutes.') }}
        </p>
      </template>
      <template v-else>
        <h1 class="text-2xl font-bold text-dark-900 mb-2">
          {{ t('subscription.paymentSuccess', 'Payment successful') }}
        </h1>
        <p class="text-dark-500 mb-6">
          {{ isOrderCapture
            ? t('subscription.creditsPurchaseSuccessDesc', 'Your credits have been added to your account.')
            : t('subscription.paymentSuccessDesc', 'Your subscription is now active. You can start using all features.') }}
        </p>
      </template>

      <p v-if="orderNumber" class="text-sm text-dark-400 mb-6">
        Order: {{ orderNumber }}
      </p>
      <div class="flex flex-col sm:flex-row gap-3 justify-center">
        <button
          type="button"
          class="btn-primary px-6 py-2"
          @click="router.push('/dashboard/my-works')"
        >
          {{ t('subscription.goToDashboard', 'Go to Dashboard') }}
        </button>
        <button
          type="button"
          class="px-6 py-2 rounded-xl"
          style="background: #141420; color: #9494b0; border: 1px solid rgba(255,255,255,0.06);"
          @click="router.push('/pricing')"
        >
          {{ t('subscription.viewPlans', 'View plans') }}
        </button>
      </div>
    </div>
  </div>
</template>
