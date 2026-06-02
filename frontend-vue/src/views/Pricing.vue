<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useBrandingStore } from '@/stores/branding'
import { subscriptionApi } from '@/api'
import apiClient from '@/api/client'
import ConfirmModal from '@/components/molecules/ConfirmModal.vue'
import type { PlanInfo, SubscriptionStatus } from '@/api'

const { t, te, locale } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const brandingStore = useBrandingStore()

// Admin-editable pricing copy (added 2026-05-23). When the admin types a
// title/body/footnote in /admin/branding, these computed props render it on
// the public Pricing page so the edits actually appear. Empty/null falls
// back to the built-in i18n strings so unconfigured installs still look OK.
//
// Locale handling (revised 2026-06-02): admin only stores _zh and _en, so
// for ja/ko/es visitors the _en string is NOT a translation in their
// language — showing it would replace the localized i18n default with
// English text. We therefore only honor the admin override on zh-* and
// en-* locales; ja/ko/es fall straight through to t('pricing.title') etc.
const isEn = computed(() => locale.value.startsWith('en'))
const pricingIntroTitle = computed(() => {
  const s = brandingStore.settings
  if (isZh.value) return s.pricing_intro_title_zh || ''
  if (isEn.value) return s.pricing_intro_title_en || ''
  return ''
})
const pricingIntroBody = computed(() => {
  const s = brandingStore.settings
  if (isZh.value) return s.pricing_intro_body_zh || ''
  if (isEn.value) return s.pricing_intro_body_en || ''
  return ''
})
const pricingFootnote = computed(() => {
  const s = brandingStore.settings
  if (isZh.value) return s.pricing_footnote_zh || ''
  if (isEn.value) return s.pricing_footnote_en || ''
  return ''
})

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
// v2.1: Refund eligibility now incorporates the 5% usage gate on top of the
// 7-day window. The /refund-eligibility endpoint computes both server-side
// so the UI can't be tricked by stale subscriptionStatus data.
const refundEligibility = ref<{
  eligible: boolean
  days_remaining: number
  used?: number
  allowance?: number
  used_pct?: number
  has_hq_export?: boolean
  reason?: string | null
  code?: string
} | null>(null)
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
// Prefer the dedicated /refund-eligibility endpoint when its value has
// loaded; fall back to subscriptionStatus.refund_eligible (which is only the
// 7-day check) so the button still renders during the fetch race.
const isRefundEligible = computed(() => refundEligibility.value?.eligible ?? subscriptionStatus.value?.refund_eligible ?? false)
const refundDaysRemaining = computed(() => refundEligibility.value?.days_remaining ?? subscriptionStatus.value?.refund_days_remaining ?? 0)
const refundUsedPct = computed(() => refundEligibility.value?.used_pct ?? 0)

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
  // SECURITY/CORRECTNESS: these values MUST mirror what
  // backend/scripts/seed_new_pricing_tiers.py inserts into credit_packages.
  // Owner directive 2026-05-25 enforces a strict NT$1.20/credit floor:
  //   light:     299 / 250 = NT$1.196/cr
  //   standard:  499 / 416 = NT$1.200/cr
  //   heavy:     999 / 833 = NT$1.200/cr
  // The previous fallback (3000/5500/12000) reflected the pre-2026-05-20
  // pack sizes that sold below cost; even the intermediate (450/1000)
  // values violated the floor. Keep this table in lock-step with the
  // backend seed — a mismatch is a bait-and-switch hazard.
  return [
    {
      id: 'light_pack',
      name: 'light_pack',
      displayName: t('pricing.creditPacks.fallbackNames.light'),
      credits: 250,
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
      displayName: t('pricing.creditPacks.fallbackNames.standard'),
      credits: 416,
      price: 499,
      currency: 'TWD',
      bonusCredits: 0,
      bonusPct: 0,
      isPopular: true,
      isBestValue: false,
    },
    {
      id: 'heavy_pack',
      name: 'heavy_pack',
      displayName: t('pricing.creditPacks.fallbackNames.heavy'),
      credits: 833,
      price: 999,
      currency: 'TWD',
      bonusCredits: 0,
      bonusPct: 0,
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
    // 2026-06-02 — DB only stores name_zh / name_en. For ja/ko/es prefer the
    // i18n fallbackNames (already localized) over name_en, otherwise the
    // English string would leak into the Japanese / Korean / Spanish UI.
    displayName: (() => {
      if (isZh.value) {
        return raw.name_zh ?? fallback?.displayName ?? raw.display_name ?? raw.name
      }
      if (isEn.value) {
        return raw.name_en ?? fallback?.displayName ?? raw.display_name ?? raw.name
      }
      return fallback?.displayName ?? raw.name_en ?? raw.display_name ?? raw.name
    })(),
    credits,
    price,
    currency: 'TWD',
    bonusCredits: Number(raw.bonus_credits ?? fallback?.bonusCredits ?? 0),
    // bonusPct is derived from the actual returned bonus_credits — the old
    // hard-coded 10/20% values were tied to the pre-2026-05-20 pack sizes
    // (3000/5500/12000) where standard_pack shipped with +500 bonus and
    // heavy_pack with +2000. v2.1 packs have no bonus, so this collapses
    // to 0 unless the API explicitly returns a bonus_credits value.
    bonusPct: (() => {
      const base = Number(raw.credits ?? fallback?.credits ?? 0)
      const bonus = Number(raw.bonus_credits ?? fallback?.bonusCredits ?? 0)
      return base > 0 && bonus > 0 ? Math.round((bonus / base) * 100) : 0
    })(),
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
    // Fallback when /api/v1/subscriptions/plans is unreachable. Values match
    // backend NEW_PLAN_DATA / v2.1 migration so the offline UI never lies
    // about what the user would actually pay.
    plans.value = [
      {
        id: 'basic',
        name: 'basic',
        display_name: '標準版 Standard',
        description: '入門首選 — 1080p HD、無浮水印',
        price_monthly: 399,
        price_yearly: 3990,
        monthly_credits: 450,
        features: { max_video_length: 60, max_resolution: '1080p', has_watermark: false, priority_queue: false, api_access: false, can_use_effects: true, batch_processing: false, custom_styles: false }
      },
      {
        id: 'pro',
        name: 'pro',
        display_name: '專業版 Pro',
        description: '主力銷售方案 — 4K、進階模型',
        price_monthly: 999,
        price_yearly: 9990,
        monthly_credits: 1200,
        features: { max_video_length: null, max_resolution: '4k', has_watermark: false, priority_queue: false, api_access: true, can_use_effects: true, batch_processing: true, custom_styles: true }
      },
      {
        id: 'premium',
        name: 'premium',
        display_name: '進階版 Advanced',
        description: '重度創作者方案 — 4K、優先佇列、Kling Omni / Veo 3.1',
        price_monthly: 1699,
        price_yearly: 16990,
        monthly_credits: 2200,
        features: { max_video_length: null, max_resolution: '4k', has_watermark: false, priority_queue: true, api_access: true, can_use_effects: true, batch_processing: true, custom_styles: true }
      },
      {
        id: 'enterprise',
        name: 'enterprise',
        display_name: '企業版 Enterprise',
        description: '企業客製方案 — 詢價、全功能解鎖、客製點數',
        price_monthly: 0,  // 0 triggers "Contact Us" UI per isContactUsPlan()
        price_yearly: 0,
        monthly_credits: -1,  // -1 → "客製化點數" in formatCredits()
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
    // After the status is known, also pull the dedicated refund-eligibility
    // payload. The backend joins the 7-day check with the 5% usage gate so
    // the UI cannot show "refund available" when usage has already crossed
    // the threshold (v2.1 spec).
    if (subscriptionStatus.value?.has_subscription) {
      try {
        refundEligibility.value = await subscriptionApi.checkRefundEligibility() as any
      } catch (e) {
        console.error('Failed to fetch refund eligibility:', e)
        refundEligibility.value = null
      }
    } else {
      refundEligibility.value = null
    }
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

async function handleCreditPurchase(
  pkg: CreditTopUpPackage,
  paymentMethod: 'ecpay' | 'paypal' = 'ecpay',
) {
  if (!isLoggedIn.value) {
    router.push('/auth/login')
    return
  }

  try {
    subscribing.value = `credit:${pkg.id}:${paymentMethod}`
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
      payment_method: paymentMethod,
    })
    const result = response.data
    if (result.ecpay_form) {
      successMessage.value = t('pricing.redirectingToPayment')
      setTimeout(() => submitECPayForm(result.ecpay_form), 500)
    } else if (result.payment_url) {
      // PayPal returns an external approve link (https://...) which we
      // open in the same tab; ECPay rarely lands here but we keep the
      // fallback for older clients.
      successMessage.value = t('pricing.redirectingToPayment')
      window.location.href = result.payment_url
    } else {
      successMessage.value = t('pricing.creditPacks.orderCreated')
    }
  } catch (err: unknown) {
    const e = err as { response?: { data?: { detail?: string } } }
    error.value = e.response?.data?.detail || t('pricing.creditPacks.purchaseFailed')
  } finally {
    subscribing.value = null
  }
}

// Subscribe to a plan
async function handleSubscribe(plan: PlanInfo, paymentMethod: 'paypal' | 'ecpay' = 'ecpay') {
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
        // PayPal: redirect to checkout URL. Stash the chosen plan +
        // billing cycle in sessionStorage so SubscriptionCancelled can
        // offer a one-click retry on the SAME plan instead of dumping
        // the user back to /pricing to re-pick.
        try {
          sessionStorage.setItem(
            'vidgo.pendingPaypalSubscribe',
            JSON.stringify({
              plan_id: plan.id,
              plan_name: plan.name,
              billing_cycle: isTestPlan(plan) ? 'monthly' : billingPeriod.value,
              ts: Date.now(),
            }),
          )
        } catch { /* sessionStorage disabled in private mode — non-fatal */ }
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
  // Priority (revised 2026-06-02): per-locale admin field (handled upstream
  // in getPlanDisplayName via display_name_zh/_en) > i18n translation for a
  // known plan slug > single-column display_name > raw slug.
  //
  // The 2026-05-23 rule put the single `display_name` column above i18n so
  // admin edits in /admin/plans took effect. But the v2.1 seed writes the
  // bilingual string "標準版 Standard" into that column, which then leaks
  // onto the ja/ko/es pricing pages because they fall through here. Result:
  // Japanese visitors saw "標準版 Standard" instead of "スタンダード".
  //
  // New rule: for plans the i18n catalogue knows about (basic/pro/premium/
  // enterprise/etc.) prefer the locale translation; the bilingual seed only
  // shows on locales that genuinely contain it (and that's still wrong for
  // most). Admin edits should go through display_name_zh / display_name_en
  // — those still win because they're checked before this function runs.
  const displayKey = getPlanDisplayKey(name || fallback || '')
  const translationKey = `pricing.${displayKey}`
  if (te(translationKey)) {
    return t(translationKey)
  }
  const trimmed = (fallback || '').trim()
  if (trimmed) return trimmed
  return name || ''
}

function getLocaleSpecificBilingual(plan: any): string {
  // 2026-06-02 — the bilingual admin fields are only display_name_zh and
  // display_name_en. For ja/ko/es we must NOT fall back to the EN field
  // (it would replace localized i18n with English text). Return '' so the
  // caller drops through to the i18n lookup.
  if (isZh.value) return String(plan?.display_name_zh || '').trim()
  if (isEn.value) return String(plan?.display_name_en || '').trim()
  return ''
}

function getPlanDisplayName(plan: PlanInfo): string {
  // 2026-05-24 — prefer locale-matched bilingual admin edit, then fall back
  // to the single-locale `display_name`, then i18n. Mirrors the same split
  // already used for plan features_text_zh/en.
  const bilingual = getLocaleSpecificBilingual(plan)
  if (bilingual) return bilingual
  return getLocalizedPlanName(plan.name, plan.display_name)
}

function getCurrentPlanDisplayName(): string {
  const plan = subscriptionStatus.value?.plan
  if (!plan) return ''
  const bilingual = getLocaleSpecificBilingual(plan)
  if (bilingual) return bilingual
  return getLocalizedPlanName(plan.name, plan.display_name || plan.name)
}

// NOTE — locale-matched plan description helper omitted on purpose: the
// Pricing card body renders features_text_zh/en (not the short description),
// so no getter is needed today. Wire one up here when description_zh/en
// gets a render site (e.g., a card subtitle row above features_text).

function getCreditsPerMonthLabel(plan: PlanInfo): string {
  // Enterprise (Contact Us tier) → "客製化點數". -1 still maps to unlimited
  // for any internal/test plans that use that sentinel.
  if (isContactUsPlan(plan)) return t('pricing.customCredits', '客製化點數')
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

// Recommended overseas USD pricing for international PayPal checkout.
// Keep aligned with the locale `paypalPricingStrategy` copy and PayPal Plan IDs.
// Values mirror backend DEFAULT_VIDGO_PLANS.price_usd so the full plan grid
// (basic / pro / premium / enterprise) shows USD on non-zh locales — without
// enterprise, the card silently fell back to NT$15000 on EN/JA/KO/ES.
// Hardcoded USD per plan (修正單 v2.1, 2026-05-22). Must NOT be FX-converted
// at runtime — PayPal reads these literal values to keep the margin honest
// when TWD/USD drifts. Match backend NEW_PLAN_DATA.price_usd exactly.
const OVERSEAS_USD_MONTHLY: Record<string, number> = {
  basic: 19.99,
  pro: 49.99,
  premium: 89.99,
  enterprise: 0,  // Contact Us — render contact CTA, no buy button
}

// USD pricing for the three official credit packs (v2.1 spec).
// Hardcoded — never auto-converted. Mirrors backend NEW_CREDIT_PACKAGE_DATA.
const CREDIT_PACK_USD_PRICE: Record<string, number> = {
  light_pack: 9.99,
  standard_pack: 16.99,
  heavy_pack: 32.99,
}

function getOverseasUsdMonthly(plan: PlanInfo): number | null {
  const key = (plan.name || plan.display_name || '').toLowerCase()
  return OVERSEAS_USD_MONTHLY[key] ?? null
}

function formatOverseasUsd(plan: PlanInfo, period: 'monthly' | 'yearly'): string {
  const monthly = getOverseasUsdMonthly(plan)
  if (monthly == null) return ''
  if (period === 'yearly') {
    const yearly = Math.round(monthly * 12 * 100) / 100
    return `US$${yearly.toFixed(2)}/yr`
  }
  return `US$${monthly.toFixed(2)}/mo`
}

function isHiddenDisplayPlan(plan: PlanInfo): boolean {
  const name = (plan.name || plan.display_name || '').toLowerCase()
  // v2.1: Enterprise has price_monthly=0 but should remain VISIBLE as a
  // "Contact Us" tier. Only hide truly-internal plans (demo / free / starter
  // / NT$299 starter promo). The price_monthly<=0 rule used to hide
  // enterprise too — fixed 2026-05-22.
  if (name === 'enterprise') return false
  return name === 'demo' || name === 'free' || name === 'starter' || plan.price_monthly <= 0 || plan.price_monthly === 299
}

function isContactUsPlan(plan: PlanInfo): boolean {
  const name = (plan.name || plan.display_name || '').toLowerCase()
  return name === 'enterprise'
}

function getCurrencySymbol(plan: PlanInfo): string {
  return plan.currency?.toUpperCase() === 'USD' || isTestPlan(plan) ? 'US$' : 'NT$'
}

function formatPackagePrice(pkg: CreditTopUpPackage): string {
  // Mirror the plan-card pricing rule: zh-TW visitors see NT$ (paid via
  // ECPay), everyone else sees US$ (paid via PayPal). Without this branch
  // the credit-pack currency was hardcoded to TWD on every locale, which
  // surfaced "NT$299" on the English/JA/KO/ES Pricing page even though
  // the checkout would go through PayPal in USD.
  if (isZh.value) return `NT$${pkg.price}`
  const usd = CREDIT_PACK_USD_PRICE[pkg.name]
  if (usd != null) return `US$${usd.toFixed(2)}`
  return `US$${pkg.price}`
}

function formatCredits(value: number): string {
  // Map the active i18n locale to an Intl-friendly tag so number grouping
  // uses the right separators for ja/ko/es too (BUG-017 follow-through).
  const l = locale.value || ''
  const tag = l.startsWith('zh') ? 'zh-TW'
    : l.startsWith('ja') ? 'ja-JP'
    : l.startsWith('ko') ? 'ko-KR'
    : l.startsWith('es') ? 'es-ES'
    : 'en-US'
  return value.toLocaleString(tag)
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

// Whether each payment gateway is wired up server-side. PayPal credentials
// are unset in production right now (PAYPAL_CLIENT_ID empty in Secret
// Manager), so the service is in MOCK mode and a real checkout cannot be
// created — we therefore hide the PayPal button until the credentials are
// configured.
const paypalEnabled = ref(false)

async function fetchPaymentMethods() {
  try {
    const { data } = await apiClient.get('/api/v1/payments/methods')
    paypalEnabled.value = !!data?.paypal?.enabled
  } catch {
    // Network failure — default to hidden so users don't hit a broken button.
    paypalEnabled.value = false
  }
}

onMounted(async () => {
  await Promise.all([
    fetchPlans(),
    fetchSubscriptionStatus(),
    fetchCreditPackages(),
    fetchPaymentMethods()
  ])
})
</script>

<template>
  <div class="min-h-screen pt-24 pb-20" style="background: #09090b;">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Header. Admin-editable title/body override the i18n defaults when
           set in /admin/branding (pricing_intro_title_* / pricing_intro_body_*).
           Falls back to t('pricing.title' / 'pricing.subtitle') so legacy
           installs render the built-in copy. -->
      <div class="text-center mb-12">
        <h1 class="text-4xl font-bold mb-4" style="color: #f5f5fa;">{{ pricingIntroTitle || t('pricing.title') }}</h1>
        <p class="text-xl whitespace-pre-line" style="color: #9494b0;">{{ pricingIntroBody || t('pricing.subtitle') }}</p>

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
            <div class="flex flex-col items-end gap-1">
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
              <!-- v2.1 refund-blocker hint. Two distinct block reasons:
                   (a) 5% usage exceeded → show used %.
                   (b) HQ watermark-free export produced → spec condition #2.
                   Both render in yellow so support can identify the case
                   immediately without inspecting backend logs. -->
              <p
                v-if="refundEligibility && !refundEligibility.eligible && refundEligibility.code === 'REFUND_USAGE_EXCEEDED'"
                class="text-xs text-right max-w-xs leading-relaxed"
                style="color: #facc15;"
              >
                {{ t('pricing.refundUsageBlocked', { pct: refundUsedPct.toFixed(1) }) }}
              </p>
              <p
                v-else-if="refundEligibility && !refundEligibility.eligible && refundEligibility.code === 'REFUND_HQ_EXPORT_PRODUCED'"
                class="text-xs text-right max-w-xs leading-relaxed"
                style="color: #facc15;"
              >
                {{ t('pricing.refundHqExportBlocked') }}
              </p>
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
                {{ t('pricing.creditPacks.sectionBadge') }}
              </span>
              <h2 class="text-2xl md:text-3xl font-bold mb-2" style="color: #f5f5fa;">
                {{ t('pricing.creditPacks.title') }}
              </h2>
              <p class="max-w-2xl text-sm md:text-base" style="color: #9494b0;">
                {{ t('pricing.creditPacks.subtitle') }}
              </p>
            </div>
            <div class="text-sm" style="color: #b7b7cc;">
              {{ t('pricing.creditPacks.checkoutNote') }}
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
                {{ pkg.isBestValue ? t('pricing.creditPacks.badges.bestValue') : t('pricing.creditPacks.badges.popular') }}
              </span>

              <div class="flex items-start justify-between gap-4 mb-5">
                <div>
                  <h3 class="text-xl font-semibold mb-1" style="color: #f5f5fa;">{{ pkg.displayName }}</h3>
                  <p class="text-sm" style="color: #9494b0;">
                    {{ pkg.bonusPct > 0 ? t('pricing.creditPacks.bonusPct', { pct: pkg.bonusPct }) : t('pricing.creditPacks.flexibleTopup') }}
                  </p>
                </div>
                <div class="text-right">
                  <div class="text-3xl font-bold" style="color: #f5f5fa;">{{ formatPackagePrice(pkg) }}</div>
                  <div class="text-xs" style="color: #6b6b8a;">{{ t('pricing.creditPacks.oneTime') }}</div>
                </div>
              </div>

              <div class="rounded-lg px-4 py-3 mb-5" style="background: rgba(255,255,255,0.035); border: 1px solid rgba(255,255,255,0.06);">
                <div class="text-2xl font-bold" style="color: #f5f5fa;">
                  {{ formatCredits(pkg.credits) }} {{ t('pricing.creditPacks.creditsUnit') }}
                </div>
                <div class="text-xs mt-1" style="color: #9494b0;">
                  {{ pkg.bonusCredits > 0 ? t('pricing.creditPacks.bonusInclusion', { bonus: formatCredits(pkg.bonusCredits) }) : t('pricing.creditPacks.noBonus') }}
                </div>
              </div>

              <ul class="space-y-2 mb-6 text-sm" style="color: #9494b0;">
                <li class="flex items-start gap-2">
                  <svg class="w-4 h-4 flex-shrink-0 mt-0.5" style="color: #52c41a;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                  {{ t('pricing.creditPacks.featureCrossTool') }}
                </li>
                <li class="flex items-start gap-2">
                  <svg class="w-4 h-4 flex-shrink-0 mt-0.5" style="color: #52c41a;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                  {{ t('pricing.creditPacks.featureNoReset') }}
                </li>
              </ul>

              <!-- v2.1 spec: prominent non-refundable notice on every pack
                   card so the buyer can't claim it was hidden after they
                   try to dispute via PayPal/ECPay. -->
              <p
                class="text-xs leading-relaxed mb-4 rounded px-3 py-2"
                style="background: rgba(250,204,21,0.10); color: #facc15; border: 1px solid rgba(250,204,21,0.30);"
              >
                {{ t('pricing.creditPacks.nonRefundable', '⚠ 點數包屬虛擬商品，購買後不予退款') }}
              </p>

              <div class="space-y-2">
                <button
                  v-if="isZh"
                  @click="handleCreditPurchase(pkg, 'ecpay')"
                  :disabled="!!subscribing && subscribing.startsWith(`credit:${pkg.id}`)"
                  class="w-full py-3 rounded font-medium transition-all duration-200 disabled:opacity-50 text-white"
                  style="background: #1677ff;"
                >
                  <span v-if="subscribing === `credit:${pkg.id}:ecpay`" class="flex items-center justify-center gap-2">
                    <svg class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    {{ t('pricing.processing') }}
                  </span>
                  <span v-else>{{ isLoggedIn ? t('pricing.creditPacks.cta.buyCard') : t('pricing.creditPacks.cta.signInToBuy') }}</span>
                </button>
                <button
                  v-if="!isZh"
                  @click="handleCreditPurchase(pkg, 'paypal')"
                  :disabled="!!subscribing && subscribing.startsWith(`credit:${pkg.id}`)"
                  class="w-full py-3 rounded font-medium transition-all duration-200 disabled:opacity-50"
                  style="background: #ffc439; color: #003087;"
                >
                  <span v-if="subscribing === `credit:${pkg.id}:paypal`" class="flex items-center justify-center gap-2">
                    <svg class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    {{ t('pricing.processing') }}
                  </span>
                  <span v-else class="flex items-center justify-center gap-2 font-bold">
                    {{ t('pricing.creditPacks.cta.buyPayPal') }}
                  </span>
                </button>
              </div>
            </article>
          </div>

          <div class="mt-8 rounded-xl p-5 md:p-6" style="background: #0f0f16; border: 1px solid rgba(255,255,255,0.12);">
            <h3 class="text-lg md:text-xl font-semibold mb-4" style="color: #f5f5fa;">
              {{ t('pricing.creditReference.title') }}
            </h3>

            <div class="overflow-x-auto mb-5">
              <table class="w-full text-sm" style="border-collapse: collapse; color: #e8e8f0; min-width: 620px;">
                <thead>
                  <tr>
                    <th class="px-3 py-2 text-left font-semibold" style="border: 1px solid rgba(255,255,255,0.35);">{{ t('pricing.creditReference.headers.featureType') }}</th>
                    <th class="px-3 py-2 text-left font-semibold" style="border: 1px solid rgba(255,255,255,0.35);">{{ t('pricing.creditReference.headers.creditsPerRun') }}</th>
                    <th class="px-3 py-2 text-left font-semibold" style="border: 1px solid rgba(255,255,255,0.35);">{{ t('pricing.creditReference.headers.outputFor100') }}</th>
                    <th class="px-3 py-2 text-left font-semibold" style="border: 1px solid rgba(255,255,255,0.35);">{{ t('pricing.creditReference.headers.useCase') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="key in ['standardImage','premiumImage','standardVideo','proLong','restore','veo3','seedanceWan']" :key="key">
                    <td class="px-3 py-2 align-top" style="border: 1px solid rgba(255,255,255,0.35);">{{ t(`pricing.creditReference.rows.${key}.feature`) }}</td>
                    <td class="px-3 py-2 align-top" style="border: 1px solid rgba(255,255,255,0.35);">{{ t(`pricing.creditReference.rows.${key}.cost`) }}</td>
                    <td class="px-3 py-2 align-top" style="border: 1px solid rgba(255,255,255,0.35);">{{ t(`pricing.creditReference.rows.${key}.output`) }}</td>
                    <td class="px-3 py-2 align-top" style="border: 1px solid rgba(255,255,255,0.35);">{{ t(`pricing.creditReference.rows.${key}.useCase`) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <h4 class="text-base md:text-lg font-semibold mb-3" style="color: #fef08a;">
              {{ t('pricing.creditReference.scenarios.title') }}
            </h4>
            <p class="text-sm mb-3" style="color: #b7b7cc;">
              {{ t('pricing.creditReference.scenarios.intro') }}
            </p>
            <ul class="space-y-2 text-sm" style="color: #e8e8f0;">
              <li>• {{ t('pricing.creditReference.scenarios.creatorStarter') }}</li>
              <li>• {{ t('pricing.creditReference.scenarios.proDesigner') }}</li>
              <li>• {{ t('pricing.creditReference.scenarios.imageSprint') }}</li>
            </ul>
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
            <!-- Enterprise (Contact Us) — show "詢價" instead of $0 -->
            <template v-if="isContactUsPlan(plan)">
              <span class="text-4xl font-bold" style="color: #facc15;">
                {{ t('pricing.contactPrice', '詢價') }}
              </span>
            </template>
            <!-- zh-TW: 顯示新台幣 (ECPay) 價格 -->
            <template v-else-if="isZh">
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
            </template>
            <!-- Non-zh locales: show USD (PayPal) price as the primary headline, in yellow. -->
            <template v-else>
              <template v-if="getOverseasUsdMonthly(plan) !== null && !isTestPlan(plan)">
                <span class="text-4xl font-bold" style="color: #facc15;">
                  {{ formatOverseasUsd(plan, billingPeriod === 'yearly' ? 'yearly' : 'monthly') }}
                </span>
              </template>
              <template v-else>
                <span class="text-4xl font-bold" style="color: #f5f5fa;">
                  {{ formatPlanPrice(plan) }}
                </span>
                <span style="color: #6b6b8a;">
                  /{{ t('pricing.perMonthShort', 'mo') }}
                </span>
              </template>
            </template>
          </div>

          <!-- Credits -->
          <p class="mb-6 text-sm" style="color: #9494b0;">
            {{ getCreditsPerMonthLabel(plan) }}
          </p>

          <!-- CTA Button -->
          <div v-if="!isCurrentPlan(plan.id)">
            <!-- Enterprise → Contact Us mailto (v2.1 spec). Pricing is
                 negotiated and provisioned via the admin panel; no buy
                 button to keep accidental purchases from happening. -->
            <a
              v-if="isContactUsPlan(plan)"
              href="mailto:hi@vidgo.co?subject=Enterprise%20Plan%20Inquiry"
              class="block w-full text-center py-3 rounded font-medium transition-all duration-200 mb-2 text-white hover:opacity-90"
              style="background: #1677ff;"
            >
              {{ t('pricing.contactUs', 'Contact Us') }}
            </a>
            <!-- ECPay (TWD) — only shown to zh-TW visitors -->
            <button
              v-if="!isContactUsPlan(plan) && isZh && plan.price_monthly > 0 && isLoggedIn"
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
            <!-- PayPal (USD) — only shown to non-zh-TW visitors -->
            <button
              v-if="!isContactUsPlan(plan) && !isZh && paypalEnabled && plan.price_monthly > 0 && isLoggedIn && !isTestPlan(plan)"
              @click="handleSubscribe(plan, 'paypal')"
              :disabled="subscribing === plan.id"
              class="block w-full text-center py-3 rounded font-medium transition-all duration-200 mb-2 disabled:opacity-50"
              style="background: #ffc439; color: #003087;"
            >
              <span class="flex items-center justify-center gap-2 font-bold">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                </svg>
                {{ t('pricing.paypalPaymentLabel') }}
              </span>
            </button>
            <p
              v-if="!isZh && paypalEnabled && plan.price_monthly > 0 && !isTestPlan(plan)"
              class="mb-2 rounded px-3 py-2 text-xs leading-relaxed"
              style="background: #fef08a; color: #111827;"
            >
              {{ t('pricing.paypalPricingStrategy') }}
            </p>
            <button
              v-if="!isContactUsPlan(plan) && !(plan.price_monthly > 0 && isLoggedIn)"
              @click="handleSubscribe(plan, isZh ? 'ecpay' : 'paypal')"
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

      <!-- Admin-editable footnote (set in /admin/branding →
           pricing_footnote_zh / _en). Renders below the FAQ so the operator
           can drop legal / regulatory / disclaimer copy without code changes.
           Hidden entirely when both locale variants are empty. -->
      <div
        v-if="pricingFootnote"
        class="mt-12 max-w-3xl mx-auto text-center text-xs leading-relaxed whitespace-pre-line"
        style="color: #6b6b8a;"
      >
        {{ pricingFootnote }}
      </div>
    </div>
  </div>
</template>
