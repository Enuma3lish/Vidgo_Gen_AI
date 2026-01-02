<script setup lang="ts">
import { useI18n } from 'vue-i18n'

defineProps<{
  show: boolean
  message?: string
}>()

const { t } = useI18n()
</script>

<template>
  <Transition name="fade">
    <div
      v-if="show"
      class="fixed inset-0 z-50 flex items-center justify-center bg-dark-900/80 backdrop-blur-sm"
    >
      <div class="flex flex-col items-center gap-4">
        <!-- Spinner -->
        <div class="relative w-16 h-16">
          <div class="absolute inset-0 border-4 border-dark-600 rounded-full" />
          <div class="absolute inset-0 border-4 border-primary-500 rounded-full border-t-transparent animate-spin" />
        </div>

        <!-- Message -->
        <p class="text-gray-300 text-sm">
          {{ message || t('common.loading') }}
        </p>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
