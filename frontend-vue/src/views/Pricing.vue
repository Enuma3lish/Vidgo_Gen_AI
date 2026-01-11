<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { subscriptionApi } from '@/api'
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
  enterprise: 'proPlus'
}

// Fetch plans from API
async function fetchPlans() {
  try {
    loading.value = true
    plans.value = await subscriptionApi.getPlans()
  } catch (err) {
    console.error('Failed to fetch plans:', err)
    // Fallback to default plans if API fails
    plans.value = []
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

// Subscribe to a plan
async function handleSubscribe(plan: PlanInfo) {
  if (!isLoggedIn.value) {
    router.push('/auth/login')
    return
  }

  if (plan.name === 'free') {
    // Free plan - just redirect to dashboard
    router.push('/dashboard')
    return
  }

  try {
    subscribing.value = plan.id
    error.value = null
    successMessage.value = null

    const result = await subscriptionApi.subscribeDirect({
      plan_id: plan.id,
      billing_cycle: billingPeriod.value,
      payment_method: 'paddle'
    })

    if (result.success) {
      successMessage.value = result.is_mock
        ? t('pricing.subscribeSuccess')
        : t('pricing.redirectingToPayment')

      if (result.checkout_url && !result.is_mock) {
        // Redirect to payment page
        window.location.href = result.checkout_url
      } else {
        // Mock mode - refresh status
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

// Cancel subscription
async function handleCancel(requestRefund: boolean = false) {
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

// Get display name for plan
function getPlanDisplayKey(name: string): string {
  return planDisplayNames[name] || name
}

// Check if plan is popular
function isPlanPopular(name: string): boolean {
  return name === 'pro'
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
  <div class="min-h-screen pt-24 pb-20">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Header -->
      <div class="text-center mb-12">
        <h1 class="text-4xl font-bold text-white mb-4">{{ t('pricing.title') }}</h1>
        <p class="text-xl text-gray-400">{{ t('pricing.subtitle') }}</p>

        <!-- Billing Toggle -->
        <div class="mt-8 inline-flex items-center bg-dark-800 rounded-xl p-1">
          <button
            @click="billingPeriod = 'monthly'"
            class="px-6 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="billingPeriod === 'monthly' ? 'bg-primary-500 text-white' : 'text-gray-400 hover:text-white'"
          >
            {{ t('pricing.monthly') }}
          </button>
          <button
            @click="billingPeriod = 'yearly'"
            class="px-6 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="billingPeriod === 'yearly' ? 'bg-primary-500 text-white' : 'text-gray-400 hover:text-white'"
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
              <h3 class="text-lg font-semibold text-white">
                {{ t('pricing.currentPlan') }}: {{ subscriptionStatus.plan?.display_name || subscriptionStatus.plan?.name }}
              </h3>
              <p class="text-sm text-gray-400">
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
                @click="handleCancel(true)"
                :disabled="cancelling"
                class="px-4 py-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-colors disabled:opacity-50"
              >
                {{ cancelling ? t('pricing.processing') : t('pricing.cancelWithRefund') }}
                <span class="text-xs ml-1">({{ refundDaysRemaining }} {{ t('pricing.daysLeft') }})</span>
              </button>
              <button
                v-if="subscriptionStatus.status === 'active'"
                @click="handleCancel(false)"
                :disabled="cancelling"
                class="px-4 py-2 bg-dark-700 text-gray-300 rounded-lg hover:bg-dark-600 transition-colors disabled:opacity-50"
              >
                {{ cancelling ? t('pricing.processing') : t('pricing.cancelSubscription') }}
              </button>
            </div>
          </div>
        </div>
      </div>

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
            isPlanPopular(plan.name)
              ? 'bg-gradient-to-b from-primary-500/20 to-dark-800 border-2 border-primary-500'
              : 'card',
            isCurrentPlan(plan.id) ? 'ring-2 ring-green-500' : ''
          ]"
        >
          <!-- Popular Badge -->
          <span
            v-if="isPlanPopular(plan.name)"
            class="absolute -top-3 left-1/2 -translate-x-1/2 bg-primary-500 text-white text-xs font-semibold px-4 py-1 rounded-full"
          >
            {{ t('badges.hot') }}
          </span>

          <!-- Current Plan Badge -->
          <span
            v-if="isCurrentPlan(plan.id)"
            class="absolute -top-3 right-4 bg-green-500 text-white text-xs font-semibold px-4 py-1 rounded-full"
          >
            {{ t('pricing.currentPlan') }}
          </span>

          <!-- Plan Name -->
          <h3 class="text-xl font-semibold text-white mb-4">
            {{ plan.display_name || t(`pricing.${getPlanDisplayKey(plan.name)}`) }}
          </h3>

          <!-- Price -->
          <div class="mb-6">
            <span class="text-4xl font-bold text-white">
              NT${{ getPrice(plan) }}
            </span>
            <span class="text-gray-400">
              /{{ billingPeriod === 'monthly' ? 'mo' : 'yr' }}
            </span>
          </div>

          <!-- Credits -->
          <p class="text-gray-400 mb-6">
            {{ plan.monthly_credits }} credits/month
          </p>

          <!-- CTA Button -->
          <button
            v-if="!isCurrentPlan(plan.id)"
            @click="handleSubscribe(plan)"
            :disabled="subscribing === plan.id"
            class="block w-full text-center py-3 rounded-xl font-medium transition-colors mb-6 disabled:opacity-50"
            :class="isPlanPopular(plan.name) ? 'bg-primary-500 hover:bg-primary-600 text-white' : 'bg-dark-700 hover:bg-dark-600 text-white'"
          >
            <span v-if="subscribing === plan.id" class="flex items-center justify-center gap-2">
              <svg class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              {{ t('pricing.subscribing') }}
            </span>
            <span v-else>
              {{ plan.price_monthly === 0 ? t('hero.cta') : (isLoggedIn ? t('pricing.upgrade') : t('pricing.getStarted')) }}
            </span>
          </button>
          <div v-else class="w-full text-center py-3 rounded-xl font-medium bg-green-500/20 text-green-400 mb-6">
            {{ t('pricing.currentPlan') }}
          </div>

          <!-- Features -->
          <ul class="space-y-3">
            <li class="flex items-start gap-2 text-sm text-gray-300">
              <svg class="w-5 h-5 text-green-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
              {{ plan.monthly_credits }} credits/month
            </li>
            <li v-if="plan.features.max_resolution" class="flex items-start gap-2 text-sm text-gray-300">
              <svg class="w-5 h-5 text-green-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
              {{ plan.features.max_resolution }} quality
            </li>
            <li v-if="plan.features.priority_queue" class="flex items-start gap-2 text-sm text-gray-300">
              <svg class="w-5 h-5 text-green-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
              Priority queue
            </li>
            <li v-if="plan.features.api_access" class="flex items-start gap-2 text-sm text-gray-300">
              <svg class="w-5 h-5 text-green-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
              API access
            </li>
            <li v-if="plan.features.batch_processing" class="flex items-start gap-2 text-sm text-gray-300">
              <svg class="w-5 h-5 text-green-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
              Batch processing
            </li>
            <li v-if="!plan.features.has_watermark" class="flex items-start gap-2 text-sm text-gray-300">
              <svg class="w-5 h-5 text-green-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
              No watermark
            </li>
            <li v-if="plan.features.has_watermark" class="flex items-start gap-2 text-sm text-gray-300">
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
        <h2 class="text-2xl font-bold text-white text-center mb-8">{{ t('pricing.faq.title') }}</h2>
        <div class="space-y-4">
          <div class="card">
            <h3 class="text-lg font-semibold text-white mb-2">{{ t('pricing.faq.credits.q') }}</h3>
            <p class="text-gray-400">{{ t('pricing.faq.credits.a') }}</p>
          </div>
          <div class="card">
            <h3 class="text-lg font-semibold text-white mb-2">{{ t('pricing.faq.rollover.q') }}</h3>
            <p class="text-gray-400">{{ t('pricing.faq.rollover.a') }}</p>
          </div>
          <div class="card">
            <h3 class="text-lg font-semibold text-white mb-2">{{ t('pricing.faq.change.q') }}</h3>
            <p class="text-gray-400">{{ t('pricing.faq.change.a') }}</p>
          </div>
          <div class="card">
            <h3 class="text-lg font-semibold text-white mb-2">{{ t('pricing.faq.refund.q') }}</h3>
            <p class="text-gray-400">{{ t('pricing.faq.refund.a') }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
