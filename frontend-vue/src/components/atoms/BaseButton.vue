<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  disabled?: boolean
  loading?: boolean
  fullWidth?: boolean
  type?: 'button' | 'submit' | 'reset'
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'primary',
  size: 'md',
  disabled: false,
  loading: false,
  fullWidth: false,
  type: 'button'
})

const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

const classes = computed(() => [
  'base-button',
  `variant-${props.variant}`,
  `size-${props.size}`,
  {
    'is-loading': props.loading,
    'is-disabled': props.disabled,
    'full-width': props.fullWidth
  }
])

function handleClick(event: MouseEvent) {
  if (!props.disabled && !props.loading) {
    emit('click', event)
  }
}
</script>

<template>
  <button
    :class="classes"
    :type="type"
    :disabled="disabled || loading"
    @click="handleClick"
  >
    <span v-if="loading" class="spinner"></span>
    <span class="content" :class="{ 'is-hidden': loading }">
      <slot />
    </span>
  </button>
</template>

<style scoped>
.base-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
}

.base-button:focus {
  outline: none;
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.25);
}

/* Sizes */
.size-sm {
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
}

.size-md {
  padding: 0.75rem 1.5rem;
  font-size: 1rem;
}

.size-lg {
  padding: 1rem 2rem;
  font-size: 1.125rem;
}

/* Variants */
.variant-primary {
  background: #f59e0b;
  color: #0a0a0a;
  font-weight: 600;
}

.variant-primary:hover:not(:disabled) {
  background: #fbbf24;
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(245, 158, 11, 0.35);
}

.variant-secondary {
  background: transparent;
  color: var(--text-primary, #fafaf9);
  border: 1px solid rgba(255, 251, 245, 0.16);
}

.variant-secondary:hover:not(:disabled) {
  border-color: #f59e0b;
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.06);
}

.variant-outline {
  background: transparent;
  border: 1.5px solid #f59e0b;
  color: #f59e0b;
}

.variant-outline:hover:not(:disabled) {
  background: #f59e0b;
  color: #0a0a0a;
}

.variant-ghost {
  background: transparent;
  color: var(--text-secondary, #a8a29e);
}

.variant-ghost:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-primary, #fafaf9);
}

.variant-danger {
  background: #dc2626;
  color: white;
}

.variant-danger:hover:not(:disabled) {
  background: #b91c1c;
  box-shadow: 0 4px 12px rgba(220, 38, 38, 0.35);
}

/* States */
.is-disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.is-loading {
  cursor: wait;
}

.full-width {
  width: 100%;
}

/* Loading spinner */
.spinner {
  position: absolute;
  width: 16px;
  height: 16px;
  border: 2px solid transparent;
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.content.is-hidden {
  visibility: hidden;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
