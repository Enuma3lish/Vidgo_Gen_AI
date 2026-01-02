<script setup lang="ts">
import { useRouter } from 'vue-router'
import BaseButton from '@/components/atoms/BaseButton.vue'
import GlassCard from '@/components/atoms/GlassCard.vue'

interface Props {
  title?: string
  message?: string
  credits?: number
  requiredCredits?: number
}

withDefaults(defineProps<Props>(), {
  title: 'Upgrade Your Plan',
  message: 'Get more credits to continue using this feature.',
  credits: 0,
  requiredCredits: 0
})

const emit = defineEmits<{
  close: []
}>()

const router = useRouter()

function goToPricing() {
  emit('close')
  router.push('/pricing')
}

function handleClose() {
  emit('close')
}
</script>

<template>
  <GlassCard class="upgrade-prompt" padding="lg">
    <button class="close-btn" @click="handleClose">&times;</button>

    <div class="prompt-icon">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
      </svg>
    </div>

    <h3 class="prompt-title">{{ title }}</h3>
    <p class="prompt-message">{{ message }}</p>

    <div v-if="requiredCredits > 0" class="credit-info">
      <div class="credit-row">
        <span>Your credits</span>
        <span class="credit-value" :class="{ 'is-low': credits < requiredCredits }">
          {{ credits }}
        </span>
      </div>
      <div class="credit-row">
        <span>Required</span>
        <span class="credit-value">{{ requiredCredits }}</span>
      </div>
    </div>

    <div class="prompt-actions">
      <BaseButton variant="primary" full-width @click="goToPricing">
        View Plans
      </BaseButton>
      <BaseButton variant="ghost" size="sm" @click="handleClose">
        Maybe Later
      </BaseButton>
    </div>
  </GlassCard>
</template>

<style scoped>
.upgrade-prompt {
  position: relative;
  max-width: 360px;
  text-align: center;
}

.close-btn {
  position: absolute;
  top: 1rem;
  right: 1rem;
  background: none;
  border: none;
  font-size: 1.5rem;
  color: #999;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.close-btn:hover {
  color: #666;
}

.prompt-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 1rem;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.prompt-icon svg {
  width: 32px;
  height: 32px;
  color: #667eea;
}

.prompt-title {
  margin: 0 0 0.5rem;
  font-size: 1.25rem;
  font-weight: 700;
  color: #1a1a2e;
}

.prompt-message {
  margin: 0 0 1.5rem;
  color: #666;
  line-height: 1.5;
}

.credit-info {
  background: #f9f9f9;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1.5rem;
}

.credit-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.875rem;
}

.credit-row:not(:last-child) {
  margin-bottom: 0.5rem;
}

.credit-value {
  font-weight: 600;
  color: #1a1a2e;
}

.credit-value.is-low {
  color: #dc3545;
}

.prompt-actions {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
</style>
