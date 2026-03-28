<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const orderNumber = route.query.order as string
</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-4 py-24" style="background: #09090b;">
    <div class="max-w-md w-full text-center card p-8">
      <div class="w-16 h-16 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
        <svg class="w-8 h-8 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
        </svg>
      </div>
      <h1 class="text-2xl font-bold text-dark-900 mb-2">
        {{ t('subscription.paymentSuccess', 'Payment successful') }}
      </h1>
      <p class="text-dark-500 mb-6">
        {{ t('subscription.paymentSuccessDesc', 'Your subscription is now active. You can start using all features.') }}
      </p>
      <p v-if="orderNumber" class="text-sm text-dark-400 mb-6">
        Order: {{ orderNumber }}
      </p>
      <div class="flex flex-col sm:flex-row gap-3 justify-center">
        <button
          type="button"
          class="btn-primary px-6 py-2"
          @click="router.push('/dashboard')"
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
