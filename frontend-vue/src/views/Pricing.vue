<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { subscriptionApi } from '@/api'
import ConfirmModal from '@/components/molecules/ConfirmModal.vue'
import type { PlanInfo, SubscriptionStatus } from '@/api'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

const billingPeriod = ref<'monthly' | 'yearly'>('monthly')
const plans = ref<PlanInfo[]>([])
const subscriptionStatus = ref<SubscriptionStatus | null>(null)
const loading = ref(false)
const subscribing = ref<string | null>(null)
const cancelling = ref(false)
const error = ref<string | null>(null)
const successMessage = ref<string | null>(null)
const showCancelModal = ref(false)
const cancelWithRefund = ref(false)

// Computed
const isLoggedIn = computed(() => authStore.isAuthenticated)
const currentPlanId = computed(() => subscriptionStatus.value?.plan?.id)
const isRefundEligible = computed(() => subscriptionStatus.value?.refund_eligible ?? false)
const refundDaysRemaining = computed(() => subscriptionStatus.value?.refund_days_remaining ?? 0)

// Plan name mapping for display
const planDisplayNames: Record<string, string> = {
  free: 'demo',
  starter: 'starter',
  pro: 'pro',
  enterprise: 'proPlus',
  '免費體驗': 'demo',
  'Starter': 'starter',
  'Pro': 'pro',
  'Enterprise': 'proPlus'
}

// Fetch plans from API
async function fetchPlans() {
  try {
    loading.value = true
    plans.value = await subscriptionApi.getPlans()
  } catch (err) {
    console.error('Failed to fetch plans:', err)
    // Fallback to default plans if API fails
    plans.value = [
      {
        id: 'free',
        name: 'free',
        display_name: '免費體驗',
        description: '新用戶專屬，立即體驗 AI 生成',
        price_monthly: 0,
        price_yearly: 0,
        monthly_credits: 40,
        features: { max_video_length: 5, max_resolution: '720p', has_watermark: true, priority_queue: false, api_access: false, can_use_effects: false, batch_processing: false, custom_styles: false }
      },
      {
        id: 'starter',
        name: 'starter',
        display_name: 'Starter',
        description: '適合個人創作者與小型電商',
        price_monthly: 99,
        price_yearly: 79,
        monthly_credits: 100,
        features: { max_video_length: 30, max_resolution: '1080p', has_watermark: false, priority_queue: false, api_access: false, can_use_effects: true, batch_processing: false, custom_styles: false }
      },
      {
        id: 'pro',
        name: 'pro',
        display_name: 'Pro',
        description: '專業團隊首選，最高畫質輸出',
        price_monthly: 649,
        price_yearly: 519,
        monthly_credits: -1,
        features: { max_video_length: null, max_resolution: '4K', has_watermark: false, priority_queue: true, api_access: true, can_use_effects: true, batch_processing: true, custom_styles: true }
      },
      {
        id: 'enterprise',
        name: 'enterprise',
        display_name: 'Enterprise',
        description: '大型企業專屬，客製化服務',
        price_monthly: 0,
        price_yearly: 0,
        monthly_credits: -1,
        features: { max_video_length: null, max_resolution: '4K', has_watermark: false, priority_queue: true, api_access: true, can_use_effects: true, batch_processing: true, custom_styles: true }
      }
    ]
  } finally {
    loading.value = false
  }
}

// Fetch subscription status
async function fetchSubscriptionStatus() {
  if (!isLoggedIn.value) return

  try {
    subscriptionStatus.value = await subscriptionApi.getStatus()
  } catch (err) {
    console.error('Failed to fetch subscription status:', err)
  }
}

// Submit ECPay form (auto-submit hidden form to ECPay payment page)
function submitECPayForm(ecpayForm: { action_url: string; params: Record<string, string> }) {
  const form = document.createElement('form')
  form.method = 'POST'
  form.action = ecpayForm.action_url
  form.target = '_self'
  Object.entries(ecpayForm.params).forEach(([key, value]) => {
    const input = document.createElement('input')
    input.type = 'hidden'
    input.name = key
    input.value = String(value)
    form.appendChild(input)
  })
  document.body.appendChild(form)
  form.submit()
}

// Subscribe to a plan
async function handleSubscribe(plan: PlanInfo, paymentMethod: 'paddle' | 'ecpay' = 'ecpay') {
  if (!isLoggedIn.value) {
    router.push('/auth/login')
    return
  }

  if (plan.name === 'free' || plan.name === 'demo') {
    // Free plan - just redirect to dashboard
    router.push('/dashboard')
    return
  }

  try {
    subscribing.value = plan.id
    error.value = null
    successMessage.value = null

    const result = await subscriptionApi.subscribe({
      plan_id: plan.id,
      billing_cycle: billingPeriod.value,
      payment_method: paymentMethod
    })

    if (result.success) {
      if (result.payment_method === 'ecpay' && result.ecpay_form) {
        // ECPay: auto-submit form to ECPay payment page
        successMessage.value = '正在導向 ECPay 付款頁面...'
        setTimeout(() => submitECPayForm(result.ecpay_form!), 500)
      } else if (result.checkout_url && !result.is_mock) {
        // Paddle: redirect to checkout URL
        successMessage.value = t('pricing.redirectingToPayment')
        window.location.href = result.checkout_url
      } else {
        // Mock mode - refresh status
        successMessage.value = result.message || t('pricing.subscribeSuccess')
        await fetchSubscriptionStatus()
      }
    } else {
      error.value = result.error || t('pricing.subscribeFailed')
    }
  } catch (err: unknown) {
    const e = err as { response?: { data?: { detail?: string } } }
    error.value = e.response?.data?.detail || t('pricing.subscribeFailed')
  } finally {
    subscribing.value = null
  }
}

// Open cancel confirmation (refund or cancel at period end)
function askCancel(requestRefund: boolean) {
  cancelWithRefund.value = requestRefund
  showCancelModal.value = true
}

// Cancel subscription (after user confirms)
async function handleCancel(requestRefund: boolean = false) {
  showCancelModal.value = false
  try {
    cancelling.value = true
    error.value = null
    successMessage.value = null

    const result = await subscriptionApi.cancel({ request_refund: requestRefund })

    if (result.success) {
      successMessage.value = requestRefund
        ? t('pricing.refundProcessed')
        : t('pricing.subscriptionCancelled')
      await fetchSubscriptionStatus()
    } else {
      error.value = result.error || t('pricing.cancelFailed')
    }
  } catch (err: unknown) {
    const e = err as { response?: { data?: { detail?: string } } }
    error.value = e.response?.data?.detail || t('pricing.cancelFailed')
  } finally {
    cancelling.value = false
  }
}

function onConfirmCancel() {
  handleCancel(cancelWithRefund.value)
}

// Get display name for plan
function getPlanDisplayKey(name: string): string {
  return planDisplayNames[name] || name
}

// Check if plan is popular
function isPlanPopular(name: string): boolean {
  return name === 'pro' || name === 'Pro'
}

// Get price based on billing period
function getPrice(plan: PlanInfo): number {
  return billingPeriod.value === 'monthly' ? plan.price_monthly : plan.price_yearly
}

// Check if this is the current plan
function isCurrentPlan(planId: string): boolean {
  return currentPlanId.value === planId && subscriptionStatus.value?.status === 'active'
}

onMounted(async () => {
  await Promise.all([
    fetchPlans(),
    fetchSubscriptionStatus()
  ])
})
</script>

<template>
  <div class="min-h-screen pt-24 pb-20 bg-white">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Header -->
      <div class="text-center mb-12">
        <h1 class="text-4xl font-bold text-dark-900 mb-4">{{ t('pricing.title') }}</h1>
        <p class="text-xl text-dark-500">{{ t('pricing.subtitle') }}</p>

        <!-- Billing Toggle -->
        <div class="mt-8 inline-flex items-center bg-gray-100 rounded-xl p-1">
          <button
            @click="billingPeriod = 'monthly'"
            class="px-6 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="billingPeriod === 'monthly' ? 'bg-primary-500 text-dark-900' : 'text-dark-500 hover:text-dark-900'"
          >
            {{ t('pricing.monthly') }}
          </button>
          <button
            @click="billingPeriod = 'yearly'"
            class="px-6 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="billingPeriod === 'yearly' ? 'bg-primary-500 text-dark-900' : 'text-dark-500 hover:text-dark-900'"
          >
            {{ t('pricing.yearly') }}
            <span class="ml-1 text-green-400">-20%</span>
          </button>
        </div>
      </div>

      <!-- Current Subscription Status -->
      <div v-if="isLoggedIn && subscriptionStatus?.has_subscription" class="mb-8">
        <div class="card p-4 border border-primary-500/30">
          <div class="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h3 class="text-lg font-semibold text-dark-900">
                {{ t('pricing.currentPlan') }}: {{ subscriptionStatus.plan?.display_name || subscriptionStatus.plan?.name }}
              </h3>
              <p class="text-sm text-dark-500">
                {{ t('pricing.status') }}:
                <span :class="subscriptionStatus.status === 'active' ? 'text-green-400' : 'text-yellow-400'">
                  {{ subscriptionStatus.status }}
                </span>
                <span v-if="subscriptionStatus.end_date" class="ml-2">
                  | {{ t('pricing.validUntil') }}: {{ new Date(subscriptionStatus.end_date).toLocaleDateString() }}
                </span>
              </p>
            </div>

            <div class="flex gap-2">
              <button
                v-if="isRefundEligible"
                @click="askCancel(true)"
                :disabled="cancelling"
                class="px-4 py-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-colors disabled:opacity-50"
              >
                {{ cancelling ? t('pricing.processing') : t('pricing.cancelWithRefund') }}
                <span class="text-xs ml-1">({{ refundDaysRemaining }} {{ t('pricing.daysLeft') }})</span>
              </button>
              <button
                v-if="subscriptionStatus.status === 'active'"
                @click="askCancel(false)"
                :disabled="cancelling"
                class="px-4 py-2 bg-gray-100 text-dark-600 rounded-lg hover:bg-dark-600 transition-colors disabled:opacity-50"
              >
                {{ cancelling ? t('pricing.processing') : t('pricing.cancelSubscription') }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Cancel confirmation modal -->
      <ConfirmModal
        :show="showCancelModal"
        :title="cancelWithRefund ? t('pricing.confirmRefundTitle') : t('pricing.confirmCancelTitle')"
        :message="cancelWithRefund ? t('pricing.confirmRefundMessage') : t('pricing.confirmCancelMessage')"
        :confirm-text="cancelWithRefund ? t('pricing.confirmRefund') : t('pricing.confirmCancel')"
        :cancel-text="t('common.cancel', 'Cancel')"
        variant="danger"
        :loading="cancelling"
        @confirm="onConfirmCancel"
        @close="showCancelModal = false"
      />

      <!-- Success/Error Messages -->
      <div v-if="successMessage" class="mb-6 p-4 bg-green-500/20 border border-green-500/30 rounded-lg text-green-400 text-center">
        {{ successMessage }}
      </div>
      <div v-if="error" class="mb-6 p-4 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 text-center">
        {{ error }}
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="flex justify-center py-12">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500"></div>
      </div>

      <!-- Plans Grid -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div
          v-for="plan in plans"
          :key="plan.id"
          class="relative rounded-2xl p-6 transition-transform hover:scale-[1.02]"
          :class="[
            isPlanPopular(plan.name) ? 'bg-dark-900 border-2 border-dark-900 text-white' : 'bg-white border border-gray-200 shadow-sm',
            isCurrentPlan(plan.id) ? 'ring-2 ring-green-500' : ''
          ]"
        >
          <!-- Popular Badge -->
          <span
            v-if="isPlanPopular(plan.name)"
            class="absolute -top-3 left-1/2 -translate-x-1/2 bg-primary-300 text-dark-900 text-xs font-semibold px-4 py-1 rounded-full"
          >
            {{ t('badges.hot') }}
          </span>

          <!-- Current Plan Badge -->
          <span
            v-if="isCurrentPlan(plan.id)"
            class="absolute -top-3 right-4 bg-green-500 text-dark-900 text-xs font-semibold px-4 py-1 rounded-full"
          >
            {{ t('pricing.currentPlan') }}
          </span>

          <!-- Plan Name -->
          <h3 class="text-xl font-semibold mb-4" :class="isPlanPopular(plan.name) ? 'text-white' : 'text-dark-900'">
            {{ plan.display_name || t(`pricing.${getPlanDisplayKey(plan.name)}`) }}
          </h3>

          <!-- Price -->
          <div class="mb-6">
            <span class="text-4xl font-bold" :class="isPlanPopular(plan.name) ? 'text-white' : 'text-dark-900'">
              NT${{ getPrice(plan) }}
            </span>
            <span :class="isPlanPopular(plan.name) ? 'text-gray-400' : 'text-dark-500'">
              /{{ billingPeriod === 'monthly' ? 'mo' : 'yr' }}
            </span>
          </div>

          <!-- Credits -->
          <p class="mb-6" :class="isPlanPopular(plan.name) ? 'text-gray-400' : 'text-dark-500'">
            {{ plan.monthly_credits === -1 ? "無限制" : plan.monthly_credits }} 點數/月
          </p>

          <!-- CTA Button -->
          <div v-if="!isCurrentPlan(plan.id)">
            <!-- ECPay Credit Card Payment Button (for paid plans) -->
            <button
              v-if="plan.price_monthly > 0 && isLoggedIn"
              @click="handleSubscribe(plan, 'ecpay')"
              :disabled="subscribing === plan.id"
              class="block w-full text-center py-3 rounded-xl font-medium transition-colors mb-2 disabled:opacity-50"
              :class="isPlanPopular(plan.name) ? 'bg-primary-500 hover:bg-primary-600 text-dark-900' : 'bg-dark-900 hover:bg-dark-800 text-white'"
            >
              <span v-if="subscribing === plan.id" class="flex items-center justify-center gap-2">
                <svg class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                正在處理...
              </span>
              <span v-else class="flex items-center justify-center gap-2">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                </svg>
                信用卡付款 (ECPay)
              </span>
            </button>
            <!-- Free plan / Not logged in button -->
            <button
              v-else
              @click="handleSubscribe(plan, 'ecpay')"
              :disabled="subscribing === plan.id"
              class="block w-full text-center py-3 rounded-xl font-medium transition-colors mb-2 disabled:opacity-50"
              :class="isPlanPopular(plan.name) ? 'bg-primary-500 hover:bg-primary-600 text-dark-900' : 'bg-gray-100 hover:bg-gray-200 text-dark-900'"
            >
              {{ plan.price_monthly === 0 ? t('hero.cta') : t('pricing.getStarted') }}
            </button>
          </div>
          <div v-else class="w-full text-center py-3 rounded-xl font-medium bg-green-500/20 text-green-400 mb-6">
            {{ t('pricing.currentPlan') }}
          </div>

          <!-- Features -->
          <ul class="space-y-3">
            <li class="flex items-start gap-2 text-sm text-dark-600">
              <svg class="w-5 h-5 text-green-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
              {{ plan.monthly_credits }} credits/month
            </li>
            <li v-if="plan.features.max_resolution" class="flex items-start gap-2 text-sm text-dark-600">
              <svg class="w-5 h-5 text-green-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
              {{ plan.features.max_resolution }} quality
            </li>
            <li v-if="plan.features.priority_queue" class="flex items-start gap-2 text-sm text-dark-600">
              <svg class="w-5 h-5 text-green-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
              Priority queue
            </li>
            <li v-if="plan.features.api_access" class="flex items-start gap-2 text-sm text-dark-600">
              <svg class="w-5 h-5 text-green-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
              API access
            </li>
            <li v-if="plan.features.batch_processing" class="flex items-start gap-2 text-sm text-dark-600">
              <svg class="w-5 h-5 text-green-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
              Batch processing
            </li>
            <li v-if="!plan.features.has_watermark" class="flex items-start gap-2 text-sm text-dark-600">
              <svg class="w-5 h-5 text-green-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
              No watermark
            </li>
            <li v-if="plan.features.has_watermark" class="flex items-start gap-2 text-sm text-dark-600">
              <svg class="w-5 h-5 text-yellow-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              With watermark
            </li>
          </ul>
        </div>
      </div>

      <!-- FAQ Section -->
      <div class="mt-20 max-w-3xl mx-auto">
        <h2 class="text-2xl font-bold text-dark-900 text-center mb-8">{{ t('pricing.faq.title') }}</h2>
        <div class="space-y-4">
          <div class="card">
            <h3 class="text-lg font-semibold text-dark-900 mb-2">{{ t('pricing.faq.credits.q') }}</h3>
            <p class="text-dark-500">{{ t('pricing.faq.credits.a') }}</p>
          </div>
          <div class="card">
            <h3 class="text-lg font-semibold text-dark-900 mb-2">{{ t('pricing.faq.rollover.q') }}</h3>
            <p class="text-dark-500">{{ t('pricing.faq.rollover.a') }}</p>
          </div>
          <div class="card">
            <h3 class="text-lg font-semibold text-dark-900 mb-2">{{ t('pricing.faq.change.q') }}</h3>
            <p class="text-dark-500">{{ t('pricing.faq.change.a') }}</p>
          </div>
          <div class="card">
            <h3 class="text-lg font-semibold text-dark-900 mb-2">{{ t('pricing.faq.refund.q') }}</h3>
            <p class="text-dark-500">{{ t('pricing.faq.refund.a') }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
