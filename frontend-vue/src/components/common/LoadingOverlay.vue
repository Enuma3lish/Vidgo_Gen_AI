<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'

const props = withDefaults(defineProps<{
  show: boolean
  message?: string
  title?: string
  detail?: string
  duration?: string
  icon?: string
  /**
   * Predicted generation time in seconds. When given, the overlay shows a
   * live progress bar + "estimated vs elapsed" timer so the user knows
   * roughly how long the generation will take. Omit it and the overlay
   * falls back to the static `duration` string.
   */
  etaSeconds?: number
}>(), {
  title: undefined,
  detail: undefined,
  duration: undefined,
  icon: undefined,
  etaSeconds: undefined,
})

const { t } = useI18n()

// ── Live elapsed timer ────────────────────────────────────────────────
// Counts up from 0 each time the overlay is shown so every tool's loading
// screen behaves identically. Cleared on hide + unmount so we never leak
// an interval.
const elapsed = ref(0)
let timer: ReturnType<typeof setInterval> | null = null

function stopTimer() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}
function startTimer() {
  stopTimer()
  elapsed.value = 0
  timer = setInterval(() => { elapsed.value += 1 }, 1000)
}

watch(
  () => props.show,
  (visible) => {
    if (visible) startTimer()
    else stopTimer()
  },
  { immediate: true },
)
onUnmounted(stopTimer)

function fmt(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds))
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}:${sec.toString().padStart(2, '0')}`
}

const hasEta = computed(() => typeof props.etaSeconds === 'number' && props.etaSeconds > 0)
const elapsedLabel = computed(() => fmt(elapsed.value))
const etaLabel = computed(() => (hasEta.value ? `~${fmt(props.etaSeconds as number)}` : props.duration || ''))
// Cap the bar at 95% while still waiting so it never reads "100% / done"
// before the result actually lands; floor at 4% so there's always motion.
const progress = computed<number | null>(() => {
  if (!hasEta.value) return null
  const pct = (elapsed.value / (props.etaSeconds as number)) * 100
  return Math.min(95, Math.max(4, Math.round(pct)))
})
const overEstimate = computed(() => hasEta.value && elapsed.value > (props.etaSeconds as number))

const titleText = computed(() => props.title || props.message || t('common.loadingOverlay.title'))
const detailText = computed(() => {
  if (overEstimate.value) return t('common.loadingOverlay.almostDone')
  return props.detail || props.message || t('common.loadingOverlay.keepOpen')
})
</script>

<template>
  <Transition name="fade">
    <div
      v-if="show"
      class="fixed inset-0 z-[60] flex items-center justify-center px-4 loading-backdrop"
      role="status"
      aria-live="polite"
    >
      <div class="loading-shell">
        <!-- Big spinner -->
        <div class="spinner-wrap">
          <div class="spinner-track" />
          <div class="spinner-ring" />
          <span v-if="icon" class="spinner-icon">{{ icon }}</span>
        </div>

        <p class="loading-title">{{ titleText }}</p>
        <p class="loading-detail">{{ detailText }}</p>

        <!-- Time card: estimated vs elapsed + progress -->
        <div class="loading-time-card">
          <div class="loading-time-row">
            <span v-if="etaLabel">
              <span class="loading-time-label">{{ t('common.loadingOverlay.estimated') }}</span>
              <span class="loading-time-value">{{ etaLabel }}</span>
            </span>
            <span>
              <span class="loading-time-label">{{ t('common.loadingOverlay.elapsed') }}</span>
              <span class="loading-time-value">{{ elapsedLabel }}</span>
            </span>
          </div>

          <div class="loading-bar">
            <div
              class="loading-bar-fill"
              :class="{ 'is-indeterminate': progress === null || overEstimate }"
              :style="progress !== null && !overEstimate ? { width: progress + '%' } : undefined"
            />
          </div>
        </div>

        <p class="loading-foot">{{ t('common.loadingOverlay.keepOpen') }}</p>
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
    radial-gradient(circle at 50% 30%, rgba(124, 58, 237, 0.18), transparent 38%),
    rgba(9, 9, 11, 0.94);
  backdrop-filter: blur(12px);
}

.loading-shell {
  width: min(100%, 520px);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.1rem;
  text-align: center;
}

/* Big spinner — ~5x the old result-pane size so the loading state reads as
   a deliberate full-screen step rather than a tiny inline indicator. */
.spinner-wrap {
  position: relative;
  width: 84px;
  height: 84px;
  flex: 0 0 84px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 0.25rem;
}
.spinner-icon {
  position: absolute;
  font-size: 2rem;
  line-height: 1;
  pointer-events: none;
}
.spinner-track,
.spinner-ring {
  position: absolute;
  inset: 0;
  border-radius: 999px;
  border: 6px solid rgba(255, 255, 255, 0.12);
}
.spinner-ring {
  border-color: #a78bfa;
  border-top-color: transparent;
  animation: spin 1s linear infinite;
}

.loading-title {
  max-width: 480px;
  color: #f5f5fa;
  font-size: clamp(1.5rem, 4vw, 2.25rem);
  line-height: 1.3;
  font-weight: 800;
}
.loading-detail {
  max-width: 440px;
  color: #b8b8cc;
  font-size: 0.95rem;
  line-height: 1.5;
  margin: -0.25rem 0 0.25rem;
}

.loading-time-card {
  width: min(100%, 440px);
  padding: 1rem 1.25rem 1.1rem;
  border-radius: 16px;
  background: rgba(20, 20, 32, 0.96);
  border: 1px solid rgba(255, 255, 255, 0.09);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.42);
}
.loading-time-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.7rem;
}
.loading-time-label {
  color: #9494b0;
  font-size: 0.78rem;
  margin-right: 0.4rem;
}
.loading-time-value {
  color: #f5f5fa;
  font-size: 1.05rem;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.loading-bar {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  overflow: hidden;
}
.loading-bar-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #7c3aed 0%, #a78bfa 100%);
  transition: width 0.9s ease;
}
/* Used both when no ETA is known and after we pass the estimate — keep a
   reassuring sweep going instead of a frozen bar. */
.loading-bar-fill.is-indeterminate {
  width: 40%;
  animation: indeterminate 1.4s ease-in-out infinite;
}

.loading-foot {
  color: #6b6b8a;
  font-size: 0.8rem;
  margin: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
@keyframes indeterminate {
  0% { transform: translateX(-120%); }
  100% { transform: translateX(320%); }
}
</style>
