<script setup lang="ts">
import { useUIStore } from '@/stores'

const uiStore = useUIStore()

function getIcon(type: string) {
  switch (type) {
    case 'success':
      return '✓'
    case 'error':
      return '✕'
    case 'warning':
      return '⚠'
    default:
      return 'ℹ'
  }
}

function getClasses(type: string) {
  switch (type) {
    case 'success':
      return 'bg-green-500/10 border-green-500/30 text-green-400'
    case 'error':
      return 'bg-red-500/10 border-red-500/30 text-red-400'
    case 'warning':
      return 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
    default:
      return 'bg-primary-500/10 border-primary-500/30 text-primary-400'
  }
}
</script>

<template>
  <div class="fixed bottom-4 right-4 z-50 space-y-2">
    <TransitionGroup name="toast">
      <div
        v-for="toast in uiStore.toasts"
        :key="toast.id"
        class="flex items-center gap-3 px-4 py-3 rounded-xl border backdrop-blur-lg shadow-lg animate-slide-up"
        :class="getClasses(toast.type)"
      >
        <span class="text-lg">{{ getIcon(toast.type) }}</span>
        <span class="text-sm font-medium">{{ toast.message }}</span>
        <button
          @click="uiStore.removeToast(toast.id)"
          class="ml-2 opacity-60 hover:opacity-100 transition-opacity"
        >
          ✕
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(100px);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(100px);
}
</style>
