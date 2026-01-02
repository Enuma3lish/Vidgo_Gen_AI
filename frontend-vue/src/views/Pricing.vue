<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const billingPeriod = ref<'monthly' | 'yearly'>('monthly')

const plans = [
  {
    name: 'demo',
    price: 0,
    yearlyPrice: 0,
    credits: 10,
    period: 'week',
    features: [
      'Basic AI tools access',
      '10 credits per week',
      'Standard quality output',
      'Community support'
    ]
  },
  {
    name: 'starter',
    price: 329,
    yearlyPrice: 2999,
    credits: 500,
    period: 'month',
    features: [
      'All AI tools access',
      '500 credits per month',
      'HD quality output',
      'Email support',
      'Priority queue'
    ]
  },
  {
    name: 'pro',
    price: 649,
    yearlyPrice: 5999,
    credits: 1200,
    period: 'month',
    popular: true,
    features: [
      'All AI tools access',
      '1200 credits per month',
      '4K quality output',
      'Priority support',
      'Fast queue',
      'API access',
      'Team features'
    ]
  },
  {
    name: 'proPlus',
    price: 1099,
    yearlyPrice: 9999,
    credits: 3000,
    period: 'month',
    features: [
      'All AI tools access',
      '3000 credits per month',
      '4K+ quality output',
      'Dedicated support',
      'Fastest queue',
      'Full API access',
      'White-label options',
      'Custom integrations'
    ]
  }
]
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

      <!-- Plans Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div
          v-for="plan in plans"
          :key="plan.name"
          class="relative rounded-2xl p-6 transition-transform hover:scale-[1.02]"
          :class="plan.popular ? 'bg-gradient-to-b from-primary-500/20 to-dark-800 border-2 border-primary-500' : 'card'"
        >
          <!-- Popular Badge -->
          <span
            v-if="plan.popular"
            class="absolute -top-3 left-1/2 -translate-x-1/2 bg-primary-500 text-white text-xs font-semibold px-4 py-1 rounded-full"
          >
            {{ t('badges.hot') }}
          </span>

          <!-- Plan Name -->
          <h3 class="text-xl font-semibold text-white mb-4">
            {{ t(`pricing.${plan.name}`) }}
          </h3>

          <!-- Price -->
          <div class="mb-6">
            <span class="text-4xl font-bold text-white">
              NT${{ billingPeriod === 'monthly' ? plan.price : plan.yearlyPrice }}
            </span>
            <span class="text-gray-400">
              /{{ billingPeriod === 'monthly' ? 'mo' : 'yr' }}
            </span>
          </div>

          <!-- Credits -->
          <p class="text-gray-400 mb-6">
            {{ plan.credits }} credits/{{ plan.period }}
          </p>

          <!-- CTA Button -->
          <RouterLink
            to="/auth/register"
            class="block w-full text-center py-3 rounded-xl font-medium transition-colors mb-6"
            :class="plan.popular ? 'bg-primary-500 hover:bg-primary-600 text-white' : 'bg-dark-700 hover:bg-dark-600 text-white'"
          >
            {{ plan.price === 0 ? t('hero.cta') : t('pricing.upgrade') }}
          </RouterLink>

          <!-- Features -->
          <ul class="space-y-3">
            <li
              v-for="(feature, index) in plan.features"
              :key="index"
              class="flex items-start gap-2 text-sm text-gray-300"
            >
              <svg class="w-5 h-5 text-green-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
              {{ feature }}
            </li>
          </ul>
        </div>
      </div>

      <!-- FAQ Section -->
      <div class="mt-20 max-w-3xl mx-auto">
        <h2 class="text-2xl font-bold text-white text-center mb-8">Frequently Asked Questions</h2>
        <div class="space-y-4">
          <div class="card">
            <h3 class="text-lg font-semibold text-white mb-2">What are credits?</h3>
            <p class="text-gray-400">Credits are used to generate content. Different tools consume different amounts of credits based on complexity.</p>
          </div>
          <div class="card">
            <h3 class="text-lg font-semibold text-white mb-2">Do unused credits roll over?</h3>
            <p class="text-gray-400">Monthly credits reset at the end of each billing period. Purchased credit packs never expire.</p>
          </div>
          <div class="card">
            <h3 class="text-lg font-semibold text-white mb-2">Can I upgrade or downgrade?</h3>
            <p class="text-gray-400">Yes, you can change your plan at any time. Changes take effect at the next billing cycle.</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
