<script setup lang="ts">
/**
 * PiapiPlayground — reusable two-column tool layout matching piapi.ai's
 * /flux-kontext playground UX (owner directive 2026-05-24: every tool
 * page should look like this, except Interior which uses the Pippit
 * templates-gallery style).
 *
 * Layout (two-column, stacks on mobile):
 *
 *   ┌────────────────────────┬─────────────────────────────┐
 *   │ Left: Configuration    │ Right: Result + Logs        │
 *   ├────────────────────────┼─────────────────────────────┤
 *   │ [Model dropdown]       │ [Status: idle | running…]   │
 *   │ [Task Type dropdown]   │ ┌─────────────────────────┐ │
 *   │ [Prompt textarea]      │ │                         │ │
 *   │ [Negative prompt]      │ │   Result preview        │ │
 *   │ [Image upload]         │ │                         │ │
 *   │ [Param chips/sliders]  │ └─────────────────────────┘ │
 *   │ [Generate]             │ [Download] [Regenerate]     │
 *   └────────────────────────┴─────────────────────────────┘
 *
 *   Below: Examples gallery (6 cards) | Pricing block | FAQ
 *
 * Color palette intentionally matches the rest of the tools UI
 * (#0a0a0f bg, #141420 panels, #7c3aed→#a78bfa violet gradient accents,
 * #94949f/#f5f5fa text). Owner directive: "ui color like before but
 * change ux like piapi."
 *
 * Slots:
 *   - inputs       — model dropdown, task type, prompt, params (left col body)
 *   - result       — output preview (right col body); falls back to placeholder
 *   - result-actions — download / regenerate buttons under the result
 *   - examples     — example cards under the playground
 *   - faq          — optional FAQ block at the bottom
 *
 * Props: title, subtitle, status ('idle' | 'running' | 'done' | 'error'),
 * statusText, creditCost, onGenerate (callback), disabled
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'

const { locale } = useI18n()
// Used to localize the "Cost per run / 單次消耗" label on the credit-cost
// badge. The rest of the playground copy comes from each tool view's
// own translations passed via props/slots.
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

interface Props {
  title: string
  subtitle?: string
  /** 'idle' | 'running' | 'done' | 'error' — drives the status pill color. */
  status?: 'idle' | 'running' | 'done' | 'error'
  /** Free-text label shown next to the status pill in the result panel. */
  statusText?: string
  /** Credit cost displayed in the Generate button. Omit for tools that vary. */
  creditCost?: number
  generateLabel?: string
  generateLabelRunning?: string
  /** Disable Generate (eg. when required inputs are missing). */
  disabled?: boolean
  /**
   * Predicted generation time in seconds — drives the full-screen loading
   * overlay's ETA / progress bar while status === 'running'. Each tool view
   * passes a realistic estimate (image ~30s, video ~150s, avatar ~300s).
   */
  etaSeconds?: number
}

const props = withDefaults(defineProps<Props>(), {
  status: 'idle',
  generateLabel: 'Generate',
  generateLabelRunning: 'Generating…',
  disabled: false,
  etaSeconds: 60,
})

const emit = defineEmits<{ (e: 'generate'): void }>()

const isRunning = computed(() => props.status === 'running')
const statusColor = computed(() => {
  switch (props.status) {
    case 'running': return 'background: rgba(168,85,247,0.15); color: #c4b5fd; border-color: rgba(168,85,247,0.3);'
    case 'done':    return 'background: rgba(16,185,129,0.15); color: #6ee7b7; border-color: rgba(16,185,129,0.3);'
    case 'error':   return 'background: rgba(239,68,68,0.15);  color: #fca5a5; border-color: rgba(239,68,68,0.3);'
    default:        return 'background: rgba(255,255,255,0.06); color: #94949f; border-color: rgba(255,255,255,0.08);'
  }
})

function onGenerateClick() {
  if (props.disabled || isRunning.value) return
  emit('generate')
}
</script>

<template>
  <div class="min-h-screen" style="background: #0a0a0f;">
    <!-- Unified full-screen loading overlay (same across every tool). Shows
         a big spinner + predicted time vs elapsed while generating, instead
         of the old tiny status pill that only covered the result pane. -->
    <LoadingOverlay :show="isRunning" :eta-seconds="etaSeconds" :title="statusText || undefined" />
    <!-- Hero — pt-24 (96px) clears the fixed 64px AppHeader plus a 32px
         breathing strip. The earlier pt-10 (40px) was clipped behind the
         header on every tool using this layout (Claymation / ShortVideo /
         AIAvatar / TryOn / BackgroundRemoval / Claymation / Avatar / etc.).
         Fixed 2026-05-25 after user screenshot confirmed the title was
         being covered. -->
    <section class="px-4 sm:px-6 lg:px-8 pt-24 pb-6 max-w-7xl mx-auto">
      <h1 class="text-3xl sm:text-4xl font-bold" style="color: #f5f5fa;">
        {{ title }}
      </h1>
      <p v-if="subtitle" class="text-base mt-2 max-w-3xl" style="color: #94949f;">
        {{ subtitle }}
      </p>
    </section>

    <!-- Two-column playground -->
    <section class="px-4 sm:px-6 lg:px-8 pb-12 max-w-7xl mx-auto">
      <div class="grid grid-cols-1 lg:grid-cols-[420px_1fr] gap-6">
        <!-- LEFT: Configuration -->
        <aside class="rounded-2xl p-5 space-y-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <slot name="inputs" />

          <!-- Credit cost — shown as a separate row above the Generate
               button (owner directive 2026-05-25). Previously the cost was
               appended inside the button text ("Generate (50 cr)") which
               read as part of the call-to-action rather than as standalone
               pricing info. Pulling it out makes the button copy a clean
               action verb and lets the cost behave like a label. -->
          <div
            v-if="creditCost !== undefined"
            class="flex items-center justify-between rounded-xl px-3 py-2"
            style="background: rgba(124,58,237,0.10); border: 1px solid rgba(124,58,237,0.25);"
          >
            <span class="text-xs font-medium" style="color: #c4b5fd;">
              {{ isZh ? '單次消耗' : 'Cost per run' }}
            </span>
            <span class="text-sm font-bold tabular-nums" style="color: #fff;">
              {{ creditCost }}
              <span class="text-xs opacity-70 font-normal ml-0.5">{{ isZh ? '點' : 'credits' }}</span>
            </span>
          </div>

          <!-- Generate Button -->
          <button
            @click="onGenerateClick"
            :disabled="disabled || isRunning"
            class="w-full py-3 rounded-xl font-semibold text-sm transition-all"
            :style="(disabled || isRunning)
              ? 'background: rgba(124,58,237,0.4); color: rgba(255,255,255,0.6); cursor: not-allowed;'
              : 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color: #fff;'"
          >
            <span v-if="isRunning" class="inline-flex items-center gap-2 justify-center">
              <svg class="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              {{ generateLabelRunning }}
            </span>
            <span v-else>{{ generateLabel }}</span>
          </button>
        </aside>

        <!-- RIGHT: Result + status -->
        <main class="rounded-2xl p-5 flex flex-col" style="background: #0f0f17; border: 1px solid rgba(255,255,255,0.06); min-height: 480px;">
          <!-- Status pill -->
          <div class="flex items-center justify-between mb-4">
            <span
              class="px-3 py-1 rounded-full text-xs font-medium border"
              :style="statusColor"
            >
              {{ statusText || (status === 'idle' ? 'Idle' : status === 'running' ? 'Generating…' : status === 'done' ? 'Done' : 'Error') }}
            </span>
            <slot name="result-actions" />
          </div>

          <!-- Result body -->
          <div class="flex-1 rounded-xl overflow-hidden flex items-center justify-center" style="background: #0a0a0f; border: 1px dashed rgba(255,255,255,0.08); min-height: 360px;">
            <slot name="result">
              <div class="text-center px-6 py-10">
                <p class="text-5xl mb-3 opacity-40">🎨</p>
                <p class="text-sm" style="color: #94949f;">
                  Generate to see the result here.
                </p>
              </div>
            </slot>
          </div>
        </main>
      </div>
    </section>

    <!-- Examples gallery (optional) -->
    <section v-if="$slots.examples" class="px-4 sm:px-6 lg:px-8 pb-12 max-w-7xl mx-auto">
      <h2 class="text-xl font-semibold mb-4" style="color: #f5f5fa;">
        <slot name="examples-title">Examples</slot>
      </h2>
      <slot name="examples" />
    </section>

    <!-- FAQ (optional) -->
    <section v-if="$slots.faq" class="px-4 sm:px-6 lg:px-8 pb-16 max-w-7xl mx-auto">
      <slot name="faq" />
    </section>
  </div>
</template>

<style scoped>
/* Re-usable mini-styles for slot content. Components passing inputs can
   apply .pp-field-label / .pp-field-help / .pp-input for consistent look. */
:slotted(.pp-field-label) {
  display: block;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #94949f;
  margin-bottom: 0.4rem;
}
:slotted(.pp-field-help) {
  font-size: 0.7rem;
  color: #6b6b7a;
  margin-top: 0.25rem;
}
:slotted(.pp-input),
:slotted(.pp-select),
:slotted(.pp-textarea) {
  width: 100%;
  padding: 0.625rem 0.75rem;
  font-size: 0.875rem;
  color: #f5f5fa;
  background: #0a0a0f;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 0.5rem;
  outline: none;
  transition: border-color 0.15s;
}
:slotted(.pp-input:focus),
:slotted(.pp-select:focus),
:slotted(.pp-textarea:focus) {
  border-color: #7c3aed;
}
:slotted(.pp-textarea) {
  min-height: 90px;
  resize: vertical;
  font-family: inherit;
}
</style>
