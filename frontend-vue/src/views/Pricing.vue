<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { subscriptionApi } from '@/api'
import apiClient from '@/api/client'
import ConfirmModal from '@/components/molecules/ConfirmModal.vue'
import type { PlanInfo, SubscriptionStatus } from '@/api'

const { t, te, locale } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

interface CreditTopUpPackage {
  id: string
  name: string
  displayName: string
  credits: number
  price: number
  currency: string
  bonusCredits: number
  bonusPct: number
  isPopular: boolean
  isBestValue: boolean
}

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
const TEST_PRO_PLAN_NAME = 'test_pro_usd_1'
const officialCreditPackageNames = ['light_pack', 'standard_pack', 'heavy_pack']
const creditPackages = ref<CreditTopUpPackage[]>([])
const creditPackagesLoading = ref(false)

// Computed
const isLoggedIn = computed(() => authStore.isAuthenticated)
const isZh = computed(() => locale.value.startsWith('zh'))
const visiblePlans = computed(() => plans.value.filter(plan => !isHiddenDisplayPlan(plan)))
const currentPlanId = computed(() => subscriptionStatus.value?.plan?.id)
const isRefundEligible = computed(() => subscriptionStatus.value?.refund_eligible ?? false)
const refundDaysRemaining = computed(() => subscriptionStatus.value?.refund_days_remaining ?? 0)

// Plan name mapping for display
const planDisplayNames: Record<string, string> = {
  demo: 'demo',
  free: 'demo',
  basic: 'basic',
  starter: 'starter',
  standard: 'standard',
  pro: 'pro',
  premium: 'premium',
  enterprise: 'enterprise',
  pro_plus: 'proPlus',
  test_pro_usd_1: 'testPro',
  '免費體驗': 'demo',
  '基礎進階版': 'basic',
  'Starter': 'starter',
  'Standard': 'standard',
  'Pro': 'pro',
  'Premium': 'premium',
  'Enterprise': 'enterprise'
}

function fallbackCreditPackages(): CreditTopUpPackage[] {
  return [
    {
      id: 'light_pack',
      name: 'light_pack',
      displayName: isZh.value ? '輕量包' : 'Light Pack',
      credits: 3000,
      price: 299,
      currency: 'TWD',
      bonusCredits: 0,
      bonusPct: 0,
      isPopular: false,
      isBestValue: false,
    },
    {
      id: 'standard_pack',
      name: 'standard_pack',
      displayName: isZh.value ? '標準包' : 'Standard Pack',
      credits: 5500,
      price: 499,
      currency: 'TWD',
      bonusCredits: 500,
      bonusPct: 10,
      isPopular: true,
      isBestValue: false,
    },
    {
      id: 'heavy_pack',
      name: 'heavy_pack',
      displayName: isZh.value ? '重度包' : 'Heavy Pack',
      credits: 12000,
      price: 999,
      currency: 'TWD',
      bonusCredits: 2000,
      bonusPct: 20,
      isPopular: false,
      isBestValue: true,
    },
  ]
}

function normalizeCreditPackage(raw: any): CreditTopUpPackage {
  const fallback = fallbackCreditPackages().find(pkg => pkg.name === raw.name)
  const price = Number(raw.price_twd ?? raw.price ?? raw.price_usd ?? fallback?.price ?? 0)
  const credits = Number(raw.credits ?? fallback?.credits ?? 0)
  return {
    id: String(raw.id ?? raw.name),
    name: String(raw.name),
    displayName: isZh.value
      ? (raw.name_zh ?? fallback?.displayName ?? raw.display_name ?? raw.name)
      : (raw.name_en ?? fallback?.displayName ?? raw.display_name ?? raw.name),
    credits,
    price,
    currency: 'TWD',
    bonusCredits: Number(raw.bonus_credits ?? fallback?.bonusCredits ?? 0),
    bonusPct: raw.name === 'heavy_pack' ? 20 : raw.name === 'standard_pack' ? 10 : 0,
    isPopular: Boolean(raw.is_popular ?? fallback?.isPopular),
    isBestValue: Boolean(raw.is_best_value ?? fallback?.isBestValue),
  }
}

async function fetchCreditPackages() {
  try {
    creditPackagesLoading.value = true
    const response = await apiClient.get('/api/v1/promotions/packages')
    const items: any[] = response.data.packages ?? response.data ?? []
    const normalized = items
      .filter(pkg => officialCreditPackageNames.includes(pkg.name))
      .map(normalizeCreditPackage)
      .sort((a, b) => officialCreditPackageNames.indexOf(a.name) - officialCreditPackageNames.indexOf(b.name))
    creditPackages.value = normalized.length === officialCreditPackageNames.length
      ? normalized
      : fallbackCreditPackages()
  } catch (err) {
    console.error('Failed to fetch credit packages:', err)
    creditPackages.value = fallbackCreditPackages()
  } finally {
    creditPackagesLoading.value = false
  }
}

// Fetch plans from API
async function fetchPlans() {
  try {
    loading.value = true
    plans.value = await subscriptionApi.getPlans()
  } catch (err) {
    console.error('Failed to fetch plans:', err)
    // Fallback when /api/v1/subscriptions/plans is unreachable.
    // Values MUST match backend DEFAULT_VIDGO_PLANS (TWD per month / per year
    // TOTAL) so the UI never disagrees with what the backend would charge.
    plans.value = [
      {
        id: 'standard',
        name: 'standard',
        display_name: 'Standard',
        description: '適合成長中的中小型企業',
        price_monthly: 399,
        price_yearly: 3990,
        monthly_credits: 150,
        features: { max_video_length: 60, max_resolution: '1080p', has_watermark: false, priority_queue: false, api_access: false, can_use_effects: true, batch_processing: true, custom_styles: false }
      },
      {
        id: 'pro',
        name: 'pro',
        display_name: 'Pro',
        description: '專業團隊首選，最高畫質輸出',
        price_monthly: 599,
        price_yearly: 5990,
        monthly_credits: 250,
        features: { max_video_length: null, max_resolution: '4k', has_watermark: false, priority_queue: true, api_access: true, can_use_effects: true, batch_processing: true, custom_styles: true }
      },
      {
        id: 'pro_plus',
        name: 'pro_plus',
        display_name: 'Pro+',
        description: '大型企業專屬，客製化服務',
        price_monthly: 999,
        price_yearly: 9990,
        monthly_credits: 500,
        features: { max_video_length: null, max_resolution: '4k', has_watermark: false, priority_queue: true, api_access: true, can_use_effects: true, batch_processing: true, custom_styles: true }
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

async function handleCreditPurchase(pkg: CreditTopUpPackage) {
  if (!isLoggedIn.value) {
    router.push('/auth/login')
    return
  }

  try {
    subscribing.value = `credit:${pkg.id}`
    error.value = null
    successMessage.value = null
    let packageId = pkg.id
    if (officialCreditPackageNames.includes(packageId)) {
      const packageResponse = await apiClient.get('/api/v1/credits/packages')
      const packages: any[] = packageResponse.data.packages ?? packageResponse.data ?? []
      const matched = packages.find(item => item.name === pkg.name)
      if (!matched?.id) {
        throw new Error('Credit package is not available for this account')
      }
      packageId = matched.id
    }
    const response = await apiClient.post('/api/v1/credits/purchase', {
      package_id: packageId,
      payment_method: 'ecpay',
    })
    const result = response.data
    if (result.ecpay_form) {
      successMessage.value = t('pricing.redirectingToPayment')
      setTimeout(() => submitECPayForm(result.ecpay_form), 500)
    } else if (result.payment_url) {
      window.location.href = result.payment_url
    } else {
      successMessage.value = isZh.value ? '訂單已建立' : 'Order created'
    }
  } catch (err: unknown) {
    const e = err as { response?: { data?: { detail?: string } } }
    error.value = e.response?.data?.detail || (isZh.value ? '點數包購買失敗，請稍後再試。' : 'Credit package purchase failed. Please try again.')
  } finally {
    subscribing.value = null
  }
}

// Subscribe to a plan
async function handleSubscribe(plan: PlanInfo, paymentMethod: 'paddle' | 'ecpay' = 'ecpay') {
  if (!isLoggedIn.value) {
    router.push('/auth/login')
    return
  }

  if (plan.name === 'free' || plan.name === 'demo') {
    // Free plan - just redirect to dashboard
    router.push('/dashboard/my-works')
    return
  }

  try {
    subscribing.value = plan.id
    error.value = null
    successMessage.value = null

    const result = await subscriptionApi.subscribe({
      plan_id: plan.id,
      billing_cycle: isTestPlan(plan) ? 'monthly' : billingPeriod.value,
      payment_method: paymentMethod
    })

    if (result.success) {
      if (result.payment_method === 'ecpay' && result.ecpay_form) {
        // ECPay: auto-submit form to ECPay payment page
        successMessage.value = t('pricing.redirectingToPayment')
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

function getLocalizedPlanName(name?: string | null, fallback?: string | null): string {
  const displayKey = getPlanDisplayKey(name || fallback || '')
  const translationKey = `pricing.${displayKey}`
  if (te(translationKey)) {
    return t(translationKey)
  }
  return fallback || name || ''
}

function getPlanDisplayName(plan: PlanInfo): string {
  return getLocalizedPlanName(plan.name, plan.display_name)
}

function getCurrentPlanDisplayName(): string {
  const plan = subscriptionStatus.value?.plan
  return plan ? getLocalizedPlanName(plan.name, plan.display_name || plan.name) : ''
}

function getCreditsPerMonthLabel(plan: PlanInfo): string {
  return plan.monthly_credits === -1
    ? t('pricing.unlimitedCredits')
    : t('pricing.creditsPerMonth', { credits: plan.monthly_credits })
}

// Check if plan is popular
function isPlanPopular(name: string): boolean {
  return name === 'pro' || name === 'Pro'
}

function isTestPlan(plan: PlanInfo): boolean {
  return Boolean(plan.is_test_only) || plan.name === TEST_PRO_PLAN_NAME
}

function isHiddenDisplayPlan(plan: PlanInfo): boolean {
  const name = (plan.name || plan.display_name || '').toLowerCase()
  return name === 'demo' || name === 'free' || name === 'starter' || plan.price_monthly <= 0 || plan.price_monthly === 299
}

function getCurrencySymbol(plan: PlanInfo): string {
  return plan.currency?.toUpperCase() === 'USD' || isTestPlan(plan) ? 'US$' : 'NT$'
}

function formatPackagePrice(pkg: CreditTopUpPackage): string {
  return `${pkg.currency === 'TWD' ? 'NT$' : 'US$'}${pkg.price}`
}

function formatCredits(value: number): string {
  return value.toLocaleString(isZh.value ? 'zh-TW' : 'en-US')
}

function formatPlanPrice(plan: PlanInfo): string {
  return `${getCurrencySymbol(plan)}${getPrice(plan)}`
}

function getPrimaryPaymentLabel(plan: PlanInfo): string {
  return isTestPlan(plan) ? t('pricing.testPaymentLabel') : t('pricing.ecpayPaymentLabel')
}

// Price shown in the big headline. Backend returns price_yearly as the TOTAL
// annual amount (e.g. 2990 for Starter). Displaying "NT$2990/yr" next to
// "NT$299/mo" trips users up — they cannot compare the monthly commitment.
// Show the per-month-billed-annually rate instead, with the real annual total
// surfaced underneath via `getAnnualTotal()`.
function getPrice(plan: PlanInfo): number {
  if (isTestPlan(plan)) {
    return plan.price_monthly
  }
  if (billingPeriod.value === 'monthly') {
    return plan.price_monthly
  }
  if (!plan.price_yearly) return 0
  // Divide annual total by 12 and round to whole NT$ to match how SaaS
  // comparison tables are written.
  return Math.round(plan.price_yearly / 12)
}

// Real annual total the customer is charged up-front when choosing yearly.
function getAnnualTotal(plan: PlanInfo): number {
  return Math.round(plan.price_yearly || 0)
}

// Yearly discount percentage vs 12 × monthly. Non-fatal: 0 when data missing.
function getYearlySavingsPct(plan: PlanInfo): number {
  if (isTestPlan(plan)) return 0
  const monthlyTotal = (plan.price_monthly || 0) * 12
  const yearlyTotal = plan.price_yearly || 0
  if (monthlyTotal <= 0 || yearlyTotal <= 0 || yearlyTotal >= monthlyTotal) return 0
  return Math.round((1 - yearlyTotal / monthlyTotal) * 100)
}

// Check if this is the current plan
function isCurrentPlan(planId: string): boolean {
  return currentPlanId.value === planId && subscriptionStatus.value?.status === 'active'
}

onMounted(async () => {
  await Promise.all([
    fetchPlans(),
    fetchSubscriptionStatus(),
    fetchCreditPackages()
  ])
})
</script>

<template>
  <div class="min-h-screen pt-24 pb-20" style="background: #09090b;">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Header -->
      <div class="text-center mb-12">
        <h1 class="text-4xl font-bold mb-4" style="color: #f5f5fa;">{{ t('pricing.title') }}</h1>
        <p class="text-xl" style="color: #9494b0;">{{ t('pricing.subtitle') }}</p>

        <!-- Billing Toggle -->
        <div class="mt-8 inline-flex items-center rounded-lg p-1" style="background: #141420; border: 1px solid rgba(255,255,255,0.08);">
          <button
            @click="billingPeriod = 'monthly'"
            class="px-6 py-2 rounded-md text-sm font-medium transition-all"
            :style="billingPeriod === 'monthly' ? 'background: #1677ff; color: white;' : 'color: #9494b0;'"
          >
            {{ t('pricing.monthly') }}
          </button>
          <button
            @click="billingPeriod = 'yearly'"
            class="px-6 py-2 rounded-md text-sm font-medium transition-all"
            :style="billingPeriod === 'yearly' ? 'background: #1677ff; color: white;' : 'color: #9494b0;'"
          >
            {{ t('pricing.yearly') }}
            <!-- Label reflects the actual average yearly discount across paid
                 plans (backend uses ~17% = 2 months free for yearly). -->
            <span class="ml-1" style="color: #10b981;">{{ t('pricing.yearlyDiscountLabel', '-17%') }}</span>
          </button>
        </div>
      </div>

      <!-- Current Subscription Status -->
      <div v-if="isLoggedIn && subscriptionStatus?.has_subscription" class="mb-8">
        <div class="p-4 rounded-xl" style="background: #141420; border: 1px solid rgba(22,119,255,0.2);">
          <div class="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h3 class="text-lg font-semibold" style="color: #f5f5fa;">
                {{ t('pricing.currentPlan') }}: {{ getCurrentPlanDisplayName() }}
              </h3>
              <p class="text-sm" style="color: #6b6b8a;">
                {{ t('pricing.status') }}:
                <span :style="subscriptionStatus.status === 'active' ? 'color: #10b981;' : 'color: #f59e0b;'">
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
                class="px-4 py-2 rounded-lg transition-colors disabled:opacity-50 text-sm font-medium"
                style="background: rgba(255,77,79,0.08); color: #ff4d4f; border: 1px solid rgba(255,77,79,0.2);"
              >
                {{ cancelling ? t('pricing.processing') : t('pricing.cancelWithRefund') }}
                <span class="text-xs ml-1">({{ refundDaysRemaining }} {{ t('pricing.daysLeft') }})</span>
              </button>
              <button
                v-if="subscriptionStatus.status === 'active'"
                @click="askCancel(false)"
                :disabled="cancelling"
                class="px-4 py-2 rounded-lg transition-colors disabled:opacity-50 text-sm font-medium"
                style="background: rgba(255,255,255,0.04); color: #9494b0; border: 1px solid rgba(255,255,255,0.1);"
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
      <div v-if="successMessage" class="mb-6 p-4 rounded-lg text-center text-sm font-medium" style="background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.2); color: #10b981;">
        {{ successMessage }}
      </div>
      <div v-if="error" class="mb-6 p-4 rounded-lg text-center text-sm font-medium" style="background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.2); color: #ef4444;">
        {{ error }}
      </div>

      <!-- Credit Top-Up Packages -->
      <section id="credit-packs" class="mb-12">
        <div class="rounded-xl p-5 md:p-6" style="background: #11111b; border: 1px solid rgba(22,119,255,0.18); box-shadow: 0 16px 48px rgba(0,0,0,0.22);">
          <div class="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4 mb-6">
            <div>
              <span
                class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold mb-3"
                style="background: rgba(22,119,255,0.12); color: #69b1ff; border: 1px solid rgba(22,119,255,0.25);"
              >
                {{ isZh ? '單買點數收費' : 'One-time Credit Pricing' }}
              </span>
              <h2 class="text-2xl md:text-3xl font-bold mb-2" style="color: #f5f5fa;">
                {{ isZh ? '不訂閱也可以直接購買點數' : 'Buy credits directly without a subscription' }}
              </h2>
              <p class="max-w-2xl text-sm md:text-base" style="color: #9494b0;">
                {{ isZh ? '三個正式 TWD 點數包已固定，適合臨時提案、室內設計渲染、批次商品圖與影片補量。購買點數不會在每月週期重置。' : 'Three official TWD packs are available for ad hoc proposals, interior renders, batch product images, and extra video runs. Purchased credits do not reset with monthly billing.' }}
              </p>
            </div>
            <div class="text-sm" style="color: #b7b7cc;">
              {{ isZh ? '台灣 ECPay 金流付款' : 'Taiwan ECPay checkout' }}
            </div>
          </div>

          <div v-if="creditPackagesLoading && !creditPackages.length" class="flex justify-center py-10">
            <div class="animate-spin rounded-full h-10 w-10 border-b-2" style="border-color: #1677ff;"></div>
          </div>
          <div v-else class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <article
              v-for="pkg in creditPackages"
              :key="pkg.name"
              class="relative rounded-xl p-6 transition-all duration-300 hover:-translate-y-1"
              :style="pkg.isPopular
                ? 'background: #141420; border: 2px solid #1677ff; box-shadow: 0 0 36px rgba(22,119,255,0.14);'
                : pkg.isBestValue
                  ? 'background: #141420; border: 2px solid #10b981; box-shadow: 0 0 36px rgba(16,185,129,0.14);'
                  : 'background: #141420; border: 1px solid rgba(255,255,255,0.06);'"
            >
              <span
                v-if="pkg.isPopular || pkg.isBestValue"
                class="absolute -top-3 left-6 text-xs font-semibold px-3 py-1 rounded-full text-white"
                :style="pkg.isBestValue ? 'background: #10b981;' : 'background: #1677ff;'"
              >
                {{ pkg.isBestValue ? (isZh ? '最划算' : 'Best Value') : (isZh ? '熱門' : 'Popular') }}
              </span>

              <div class="flex items-start justify-between gap-4 mb-5">
                <div>
                  <h3 class="text-xl font-semibold mb-1" style="color: #f5f5fa;">{{ pkg.displayName }}</h3>
                  <p class="text-sm" style="color: #9494b0;">
                    {{ pkg.bonusPct > 0 ? (isZh ? `多送 ${pkg.bonusPct}%` : `${pkg.bonusPct}% bonus included`) : (isZh ? '彈性補量' : 'Flexible top-up') }}
                  </p>
                </div>
                <div class="text-right">
                  <div class="text-3xl font-bold" style="color: #f5f5fa;">{{ formatPackagePrice(pkg) }}</div>
                  <div class="text-xs" style="color: #6b6b8a;">{{ isZh ? '一次購買' : 'one-time' }}</div>
                </div>
              </div>

              <div class="rounded-lg px-4 py-3 mb-5" style="background: rgba(255,255,255,0.035); border: 1px solid rgba(255,255,255,0.06);">
                <div class="text-2xl font-bold" style="color: #f5f5fa;">
                  {{ formatCredits(pkg.credits) }} {{ isZh ? '點' : 'credits' }}
                </div>
                <div class="text-xs mt-1" style="color: #9494b0;">
                  {{ pkg.bonusCredits > 0 ? (isZh ? `內含 ${formatCredits(pkg.bonusCredits)} 點加贈額度` : `Includes ${formatCredits(pkg.bonusCredits)} bonus credits`) : (isZh ? '無加贈，適合小量測試' : 'No bonus, best for light testing') }}
                </div>
              </div>

              <ul class="space-y-2 mb-6 text-sm" style="color: #9494b0;">
                <li class="flex items-start gap-2">
                  <svg class="w-4 h-4 flex-shrink-0 mt-0.5" style="color: #52c41a;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                  {{ isZh ? '可用於圖片、影片、室內設計與商品場景生成' : 'Works across images, video, interiors, and product scenes' }}
                </li>
                <li class="flex items-start gap-2">
                  <svg class="w-4 h-4 flex-shrink-0 mt-0.5" style="color: #52c41a;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                  {{ isZh ? '購買點數不會每月歸零，適合專案補量' : 'Purchased credits do not reset monthly, ideal for project bursts' }}
                </li>
              </ul>

              <button
                @click="handleCreditPurchase(pkg)"
                :disabled="subscribing === `credit:${pkg.id}`"
                class="w-full py-3 rounded font-medium transition-all duration-200 disabled:opacity-50 text-white"
                style="background: #1677ff;"
              >
                <span v-if="subscribing === `credit:${pkg.id}`" class="flex items-center justify-center gap-2">
                  <svg class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  {{ t('pricing.processing') }}
                </span>
                <span v-else>{{ isLoggedIn ? (isZh ? '購買點數' : 'Buy Credits') : (isZh ? '登入後購買' : 'Sign In to Buy') }}</span>
              </button>
            </article>
          </div>
        </div>
      </section>

      <!-- Loading State -->
      <div v-if="loading" class="flex justify-center py-12">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2" style="border-color: #1677ff;"></div>
      </div>

      <!-- Plans Grid -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <div
          v-for="plan in visiblePlans"
          :key="plan.id"
          class="relative rounded-xl p-6 transition-all duration-300 hover:-translate-y-1"
          :style="isPlanPopular(plan.name)
            ? 'background: #141420; border: 2px solid #1677ff; box-shadow: 0 0 40px rgba(22,119,255,0.15);'
            : isCurrentPlan(plan.id)
              ? 'background: #141420; border: 2px solid #10b981; box-shadow: 0 0 24px rgba(16,185,129,0.12);'
              : 'background: #141420; border: 1px solid rgba(255,255,255,0.06);'"
        >
          <!-- Popular Badge -->
          <span
            v-if="isPlanPopular(plan.name)"
            class="absolute -top-3 left-1/2 -translate-x-1/2 text-xs font-semibold px-4 py-1 rounded-full text-white"
            style="background: #1677ff;"
          >
            {{ t('badges.hot') }}
          </span>

          <span
            v-if="isTestPlan(plan)"
            class="absolute -top-3 left-1/2 -translate-x-1/2 text-xs font-semibold px-4 py-1 rounded-full text-white"
            style="background: #7c3aed;"
          >
            {{ t('pricing.testOnly') }}
          </span>

          <!-- Current Plan Badge -->
          <span
            v-if="isCurrentPlan(plan.id)"
            class="absolute -top-3 right-4 text-xs font-semibold px-4 py-1 rounded-full text-white"
            style="background: #52c41a;"
          >
            {{ t('pricing.currentPlan') }}
          </span>

          <!-- Plan Name -->
          <h3 class="text-xl font-semibold mb-4" style="color: #f5f5fa;">
            {{ getPlanDisplayName(plan) }}
          </h3>

          <!-- Price -->
          <div class="mb-6">
            <span class="text-4xl font-bold" style="color: #f5f5fa;">
              {{ formatPlanPrice(plan) }}
            </span>
            <span style="color: #6b6b8a;">
              /{{ t('pricing.perMonthShort', 'mo') }}
            </span>
            <!-- When the user is viewing yearly pricing, also surface the real
                 annual total + savings so they understand the full commitment. -->
            <div
              v-if="billingPeriod === 'yearly' && plan.price_monthly > 0 && !isTestPlan(plan)"
              class="mt-2 text-xs"
              style="color: #6b6b8a;"
            >
              <span>{{ t('pricing.billedAnnually') }}: NT${{ getAnnualTotal(plan) }}</span>
              <span
                v-if="getYearlySavingsPct(plan) > 0"
                class="ml-2"
                style="color: #10b981;"
              >
                {{ t('pricing.saveVsMonthly', { pct: getYearlySavingsPct(plan) }) }}
              </span>
            </div>
          </div>

          <!-- Credits -->
          <p class="mb-6 text-sm" style="color: #9494b0;">
            {{ getCreditsPerMonthLabel(plan) }}
          </p>

          <!-- CTA Button -->
          <div v-if="!isCurrentPlan(plan.id)">
            <button
              v-if="plan.price_monthly > 0 && isLoggedIn"
              @click="handleSubscribe(plan, 'ecpay')"
              :disabled="subscribing === plan.id"
              class="block w-full text-center py-3 rounded font-medium transition-all duration-200 mb-2 disabled:opacity-50 text-white hover:opacity-90"
              style="background: #1677ff;"
            >
              <span v-if="subscribing === plan.id" class="flex items-center justify-center gap-2">
                <svg class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                {{ t('pricing.processing') }}
              </span>
              <span v-else class="flex items-center justify-center gap-2">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                </svg>
                {{ getPrimaryPaymentLabel(plan) }}
              </span>
            </button>
            <button
              v-if="plan.price_monthly > 0 && isLoggedIn && !isTestPlan(plan)"
              @click="handleSubscribe(plan, 'paddle')"
              :disabled="subscribing === plan.id"
              class="block w-full text-center py-3 rounded font-medium transition-all duration-200 mb-2 disabled:opacity-50"
              style="background: rgba(22,119,255,0.08); color: #1677ff; border: 1px solid rgba(22,119,255,0.2);"
            >
              <span class="flex items-center justify-center gap-2">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                </svg>
                {{ t('pricing.paddlePaymentLabel') }}
              </span>
            </button>
            <button
              v-if="!(plan.price_monthly > 0 && isLoggedIn)"
              @click="handleSubscribe(plan, 'ecpay')"
              :disabled="subscribing === plan.id"
              class="block w-full text-center py-3 rounded font-medium transition-all duration-200 mb-2 disabled:opacity-50"
              style="background: rgba(22,119,255,0.08); color: #1677ff; border: 1px solid rgba(22,119,255,0.2);"
            >
              {{ plan.price_monthly === 0 ? t('hero.cta') : t('pricing.getStarted') }}
            </button>
          </div>
          <div v-else class="w-full text-center py-3 rounded font-medium mb-6 text-sm" style="background: rgba(82,196,26,0.08); color: #52c41a; border: 1px solid rgba(82,196,26,0.2);">
            {{ t('pricing.currentPlan') }}
          </div>

          <!-- Features -->
          <ul class="space-y-3">
            <li class="flex items-start gap-2 text-sm" style="color: #9494b0;">
              <svg class="w-4 h-4 flex-shrink-0 mt-0.5" style="color: #52c41a;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
              {{ getCreditsPerMonthLabel(plan) }}
            </li>
            <li v-if="plan.features.max_resolution" class="flex items-start gap-2 text-sm" style="color: #9494b0;">
              <svg class="w-4 h-4 flex-shrink-0 mt-0.5" style="color: #52c41a;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
              {{ t('pricing.qualityFeature', { resolution: plan.features.max_resolution }) }}
            </li>
            <li v-if="plan.features.priority_queue" class="flex items-start gap-2 text-sm" style="color: #9494b0;">
              <svg class="w-4 h-4 flex-shrink-0 mt-0.5" style="color: #52c41a;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
              {{ t('pricing.priorityQueueFeature') }}
            </li>
            <li v-if="plan.features.api_access" class="flex items-start gap-2 text-sm" style="color: #9494b0;">
              <svg class="w-4 h-4 flex-shrink-0 mt-0.5" style="color: #52c41a;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
              {{ t('pricing.apiAccessFeature') }}
            </li>
            <li v-if="plan.features.batch_processing" class="flex items-start gap-2 text-sm" style="color: #9494b0;">
              <svg class="w-4 h-4 flex-shrink-0 mt-0.5" style="color: #52c41a;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
              {{ t('pricing.batchProcessingFeature') }}
            </li>
            <li v-if="!plan.features.has_watermark" class="flex items-start gap-2 text-sm" style="color: #9494b0;">
              <svg class="w-4 h-4 flex-shrink-0 mt-0.5" style="color: #52c41a;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
              {{ t('pricing.noWatermarkFeature') }}
            </li>
            <li v-if="plan.features.has_watermark" class="flex items-start gap-2 text-sm" style="color: #6b6b8a;">
              <svg class="w-4 h-4 flex-shrink-0 mt-0.5" style="color: #faad14;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
              {{ t('pricing.withWatermarkFeature') }}
            </li>
          </ul>
        </div>
      </div>

      <!-- FAQ Section -->
      <div class="mt-20 max-w-3xl mx-auto">
        <h2 class="text-2xl font-bold text-center mb-8" style="color: #f5f5fa;">{{ t('pricing.faq.title') }}</h2>
        <div class="space-y-3">
          <div class="rounded-xl p-6" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <h3 class="text-base font-semibold mb-2" style="color: #e8e8f0;">{{ t('pricing.faq.credits.q') }}</h3>
            <p class="text-sm" style="color: #9494b0;">{{ t('pricing.faq.credits.a') }}</p>
          </div>
          <div class="rounded-xl p-6" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <h3 class="text-base font-semibold mb-2" style="color: #e8e8f0;">{{ t('pricing.faq.rollover.q') }}</h3>
            <p class="text-sm" style="color: #9494b0;">{{ t('pricing.faq.rollover.a') }}</p>
          </div>
          <div class="rounded-xl p-6" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <h3 class="text-base font-semibold mb-2" style="color: #e8e8f0;">{{ t('pricing.faq.change.q') }}</h3>
            <p class="text-sm" style="color: #9494b0;">{{ t('pricing.faq.change.a') }}</p>
          </div>
          <div class="rounded-xl p-6" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <h3 class="text-base font-semibold mb-2" style="color: #e8e8f0;">{{ t('pricing.faq.refund.q') }}</h3>
            <p class="text-sm" style="color: #9494b0;">{{ t('pricing.faq.refund.a') }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
