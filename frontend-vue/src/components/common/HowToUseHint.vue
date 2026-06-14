<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { imageHintForTool, videoHintForTool } from '@/utils/mediaValidation'

// Steps can be provided in two shapes:
//   1. As an `i18nKeys` prop — array of i18n keys; the component resolves
//      each via `t(...)`. Preferred for new tool pages.
//   2. As a `steps` prop — array of objects keyed by locale code:
//      { en, zh, ja?, ko?, es? }. ja/ko/es fall back to `en` so older call
//      sites keep working without breaking when locale switches.
interface LocalizedStep {
  en: string
  zh: string
  ja?: string
  ko?: string
  es?: string
}

const props = withDefaults(defineProps<{
  toolType?: string
  mediaKind?: 'image' | 'video' | 'none'
  steps?: LocalizedStep[]
  i18nKeys?: string[]
  // Optional override hint when the tool requires something custom.
  formatHintEn?: string
  formatHintZh?: string
}>(), {
  toolType: '',
  mediaKind: 'image',
  steps: () => [],
  i18nKeys: () => [],
  formatHintEn: '',
  formatHintZh: '',
})

const { t, locale } = useI18n()

const headingTitle = computed(() => t('howTo.heading'))
const formatTitle = computed(() => t('howTo.formatTitle'))
const reuploadNote = computed(() => t('howTo.reuploadNote'))

function pickLocaleString(step: LocalizedStep): string {
  const code = locale.value
  if (code.startsWith('zh')) return step.zh
  if (code.startsWith('ja') && step.ja) return step.ja
  if (code.startsWith('ko') && step.ko) return step.ko
  if (code.startsWith('es') && step.es) return step.es
  return step.en
}

const formatHint = computed(() => {
  if (props.formatHintEn || props.formatHintZh) {
    return locale.value.startsWith('zh') ? props.formatHintZh : props.formatHintEn
  }
  if (props.mediaKind === 'video') return videoHintForTool(props.toolType, locale.value)
  if (props.mediaKind === 'none') return ''
  return imageHintForTool(props.toolType, locale.value)
})

const renderedSteps = computed(() => {
  if (props.i18nKeys.length) {
    return props.i18nKeys.map(key => t(key))
  }
  return props.steps.map(pickLocaleString)
})
</script>

<template>
  <section
    class="mb-8 rounded-2xl border border-primary-500/30 bg-gradient-to-br from-primary-500/10 via-purple-500/5 to-transparent p-5 sm:p-6"
    role="region"
    :aria-label="headingTitle"
  >
    <div class="flex flex-col md:flex-row md:items-stretch gap-5">
      <!-- How to use steps -->
      <div v-if="renderedSteps.length" class="flex-1 min-w-0">
        <div class="flex items-center gap-2 mb-3">
          <span aria-hidden="true">💡</span>
          <h3 class="text-base font-semibold text-dark-50">{{ headingTitle }}</h3>
        </div>
        <ol class="space-y-2 text-sm text-dark-200 list-none">
          <li
            v-for="(step, idx) in renderedSteps"
            :key="idx"
            class="flex gap-3 items-start"
          >
            <span
              class="flex-shrink-0 w-5 h-5 rounded-full bg-primary-500/30 text-primary-300 text-[11px] font-semibold flex items-center justify-center"
            >{{ idx + 1 }}</span>
            <span>{{ step }}</span>
          </li>
        </ol>
      </div>

      <!-- Format requirements -->
      <div
        v-if="formatHint"
        class="flex-1 min-w-0 md:max-w-sm md:border-l md:border-primary-500/20 md:pl-5"
      >
        <div class="flex items-center gap-2 mb-3">
          <span aria-hidden="true">📥</span>
          <h3 class="text-base font-semibold text-dark-50">{{ formatTitle }}</h3>
        </div>
        <p class="text-sm text-dark-200 leading-relaxed">{{ formatHint }}</p>
        <p class="text-xs text-dark-400 mt-2 leading-relaxed">{{ reuploadNote }}</p>
      </div>
    </div>
  </section>
</template>
