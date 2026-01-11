<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCreditsStore } from '@/stores'

const props = defineProps<{
  service?: string
  cost?: number
  count?: number
}>()

const { t } = useI18n()
const creditsStore = useCreditsStore()

const cost = computed(() => {
  if (props.cost !== undefined) {
    return props.cost * (props.count || 1)
  }
  if (!props.service) return 0
  
  const baseCost = creditsStore.getServiceCost(props.service)
  return baseCost * (props.count || 1)
})

const canAfford = computed(() => creditsStore.remainingCredits >= cost.value)
</script>

<template>
  <div class="flex items-center gap-2 text-sm">
    <span class="text-gray-400">{{ t('common.estimatedCost') }}:</span>
    <span
      class="font-semibold"
      :class="canAfford ? 'text-primary-400' : 'text-red-400'"
    >
      {{ cost }} {{ t('common.credits') }}
    </span>
    <span v-if="!canAfford" class="text-red-400 text-xs">(Insufficient)</span>
  </div>
</template>
