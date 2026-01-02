<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  type?: 'success' | 'error' | 'warning' | 'info'
  message: string
  show: boolean
  duration?: number
}

const props = withDefaults(defineProps<Props>(), {
  type: 'info',
  duration: 3000
})

const emit = defineEmits<{
  close: []
}>()

const icon = computed(() => {
  const icons = {
    success: '✓',
    error: '✕',
    warning: '!',
    info: 'i'
  }
  return icons[props.type]
})

function handleClose() {
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="toast">
      <div v-if="show" class="toast-container">
        <div class="toast" :class="`type-${type}`">
          <span class="toast-icon">{{ icon }}</span>
          <span class="toast-message">{{ message }}</span>
          <button class="toast-close" @click="handleClose">&times;</button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.toast-container {
  position: fixed;
  top: 1.5rem;
  right: 1.5rem;
  z-index: 9999;
}

.toast {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 1.25rem;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  min-width: 280px;
  max-width: 400px;
}

.toast-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.75rem;
  flex-shrink: 0;
}

.toast-message {
  flex: 1;
  font-size: 0.875rem;
  line-height: 1.4;
}

.toast-close {
  background: none;
  border: none;
  font-size: 1.25rem;
  color: inherit;
  opacity: 0.6;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.toast-close:hover {
  opacity: 1;
}

/* Types */
.type-success {
  background: #d4edda;
  color: #155724;
}

.type-success .toast-icon {
  background: #28a745;
  color: white;
}

.type-error {
  background: #f8d7da;
  color: #721c24;
}

.type-error .toast-icon {
  background: #dc3545;
  color: white;
}

.type-warning {
  background: #fff3cd;
  color: #856404;
}

.type-warning .toast-icon {
  background: #ffc107;
  color: #000;
}

.type-info {
  background: #d1ecf1;
  color: #0c5460;
}

.type-info .toast-icon {
  background: #17a2b8;
  color: white;
}

/* Transitions */
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}

.toast-leave-to {
  opacity: 0;
  transform: translateY(-100%);
}
</style>
