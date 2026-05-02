<script setup lang="ts">
import { useI18n } from 'vue-i18n'

withDefaults(defineProps<{
  show: boolean
  message?: string
  title?: string
  detail?: string
  duration?: string
}>(), {
  title: undefined,
  detail: undefined,
  duration: undefined,
})

const { t } = useI18n()
</script>

<template>
  <Transition name="fade">
    <div
      v-if="show"
      class="fixed inset-0 z-50 flex items-center justify-center px-4 loading-backdrop"
    >
      <div class="loading-shell">
        <p class="loading-title">
          {{ title || message || t('common.loading') }}
        </p>

        <div class="loading-card">
          <div class="spinner-wrap">
            <div class="spinner-track" />
            <div class="spinner-ring" />
          </div>

          <div>
            <p class="loading-card-title">
              {{ detail || message || t('common.loading') }}
            </p>
            <p class="loading-card-subtitle">
              {{ duration || t('common.loading') }}
            </p>
          </div>
        </div>
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

.loading-backdrop {
  background:
    radial-gradient(circle at 50% 30%, rgba(22, 119, 255, 0.16), transparent 32%),
    rgba(9, 9, 11, 0.92);
  backdrop-filter: blur(10px);
}

.loading-shell {
  width: min(100%, 720px);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.75rem;
  text-align: center;
}

.loading-title {
  max-width: 680px;
  color: #f5f5fa;
  font-size: clamp(1.35rem, 4vw, 2.5rem);
  line-height: 1.35;
  font-weight: 800;
  letter-spacing: 0;
}

.loading-card {
  width: min(100%, 420px);
  min-height: 92px;
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.25rem;
  border-radius: 16px;
  background: rgba(20, 20, 32, 0.96);
  border: 1px solid rgba(255, 255, 255, 0.09);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.42);
  text-align: left;
}

.spinner-wrap {
  position: relative;
  width: 46px;
  height: 46px;
  flex: 0 0 46px;
}

.spinner-track,
.spinner-ring {
  position: absolute;
  inset: 0;
  border-radius: 999px;
  border: 4px solid rgba(255, 255, 255, 0.12);
}

.spinner-ring {
  border-color: #1677ff;
  border-top-color: transparent;
  animation: spin 1s linear infinite;
}

.loading-card-title {
  color: #f5f5fa;
  font-size: 1rem;
  line-height: 1.35;
  font-weight: 800;
  margin: 0 0 0.25rem;
}

.loading-card-subtitle {
  color: #9494b0;
  font-size: 0.9rem;
  line-height: 1.45;
  margin: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
