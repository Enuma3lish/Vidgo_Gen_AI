<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const router = useRouter()
</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-4 py-24 bg-dark-900">
    <div class="max-w-md w-full text-center card p-8">
      <div class="w-16 h-16 bg-yellow-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
        <svg class="w-8 h-8 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </div>
      <h1 class="text-2xl font-bold text-white mb-2">
        {{ t('subscription.paymentCancelled', 'Payment cancelled') }}
      </h1>
      <p class="text-gray-400 mb-6">
        {{ t('subscription.paymentCancelledDesc', 'You cancelled the payment. No charges were made.') }}
      </p>
      <button
        type="button"
        class="btn-primary px-6 py-2"
        @click="router.push('/pricing')"
      >
        {{ t('subscription.backToPricing', 'Back to Pricing') }}
      </button>
    </div>
  </div>
</template>
