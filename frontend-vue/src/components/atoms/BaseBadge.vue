<script setup lang="ts">
interface Props {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info' | 'premium'
  size?: 'sm' | 'md'
  pill?: boolean
}

withDefaults(defineProps<Props>(), {
  variant: 'default',
  size: 'md',
  pill: false
})
</script>

<template>
  <span
    class="badge"
    :class="[`variant-${variant}`, `size-${size}`, { 'is-pill': pill }]"
  >
    <slot />
  </span>
</template>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-weight: 600;
  border-radius: 4px;
}

.size-sm {
  padding: 0.125rem 0.375rem;
  font-size: 0.625rem;
}

.size-md {
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
}

.is-pill {
  border-radius: 9999px;
}

.variant-default {
  background: #f0f0f0;
  color: #666;
}

.variant-success {
  background: #d4edda;
  color: #155724;
}

.variant-warning {
  background: #fff3cd;
  color: #856404;
}

.variant-error {
  background: #f8d7da;
  color: #721c24;
}

.variant-info {
  background: #d1ecf1;
  color: #0c5460;
}

.variant-premium {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}
</style>
