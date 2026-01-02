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
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.3);
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
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.variant-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.variant-secondary {
  background: #f5f5f5;
  color: #1a1a2e;
}

.variant-secondary:hover:not(:disabled) {
  background: #e0e0e0;
}

.variant-outline {
  background: transparent;
  border: 2px solid #667eea;
  color: #667eea;
}

.variant-outline:hover:not(:disabled) {
  background: #667eea;
  color: white;
}

.variant-ghost {
  background: transparent;
  color: #667eea;
}

.variant-ghost:hover:not(:disabled) {
  background: rgba(102, 126, 234, 0.1);
}

.variant-danger {
  background: #dc3545;
  color: white;
}

.variant-danger:hover:not(:disabled) {
  background: #c82333;
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
