<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  credits: number
  showIcon?: boolean
  size?: 'sm' | 'md' | 'lg'
  variant?: 'default' | 'warning' | 'danger'
}

const props = withDefaults(defineProps<Props>(), {
  showIcon: true,
  size: 'md',
  variant: 'default'
})

const displayCredits = computed(() => {
  if (props.credits >= 1000) {
    return (props.credits / 1000).toFixed(1) + 'K'
  }
  return props.credits.toString()
})

const computedVariant = computed(() => {
  if (props.variant !== 'default') return props.variant
  if (props.credits <= 0) return 'danger'
  if (props.credits < 10) return 'warning'
  return 'default'
})
</script>

<template>
  <div
    class="credit-badge"
    :class="[`size-${size}`, `variant-${computedVariant}`]"
  >
    <svg v-if="showIcon" class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="12" cy="12" r="10"/>
      <path d="M12 6v6l4 2"/>
    </svg>
    <span class="credits">{{ displayCredits }}</span>
    <span class="label">credits</span>
  </div>
</template>

<style scoped>
.credit-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.5rem 0.75rem;
  border-radius: 9999px;
  font-weight: 600;
}

.icon {
  flex-shrink: 0;
}

.size-sm {
  font-size: 0.75rem;
}

.size-sm .icon {
  width: 12px;
  height: 12px;
}

.size-md {
  font-size: 0.875rem;
}

.size-md .icon {
  width: 16px;
  height: 16px;
}

.size-lg {
  font-size: 1rem;
  padding: 0.625rem 1rem;
}

.size-lg .icon {
  width: 20px;
  height: 20px;
}

.variant-default {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
  color: #667eea;
}

.variant-warning {
  background: #fff3cd;
  color: #856404;
}

.variant-danger {
  background: #f8d7da;
  color: #721c24;
}

.label {
  opacity: 0.7;
}
</style>
