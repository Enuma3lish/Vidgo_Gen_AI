<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { imageHintForTool, videoHintForTool } from '@/utils/mediaValidation'

interface Step {
  en: string
  zh: string
}

const props = withDefaults(defineProps<{
  toolType?: string
  mediaKind?: 'image' | 'video' | 'none'
  steps?: Step[]
  // Optional override hint when the tool requires something custom.
  formatHintEn?: string
  formatHintZh?: string
}>(), {
  toolType: '',
  mediaKind: 'image',
  steps: () => [],
  formatHintEn: '',
  formatHintZh: '',
})

const { locale } = useI18n()
const isZh = computed(() => locale.value.startsWith('zh'))

const headingTitle = computed(() => isZh.value ? '使用方法' : 'How to use')
const formatTitle = computed(() => isZh.value ? '上傳檔案要求' : 'Upload requirements')
const reuploadNote = computed(() => isZh.value
  ? '若上傳格式或尺寸不符，系統會提示您依正確格式重新上傳。'
  : 'If the file does not match these requirements, you will be asked to re-upload in the correct format.')

const formatHint = computed(() => {
  if (props.formatHintEn || props.formatHintZh) {
    return isZh.value ? props.formatHintZh : props.formatHintEn
  }
  if (props.mediaKind === 'video') return videoHintForTool(props.toolType, isZh.value)
  if (props.mediaKind === 'none') return ''
  return imageHintForTool(props.toolType, isZh.value)
})

const renderedSteps = computed(() => props.steps.map(s => isZh.value ? s.zh : s.en))
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
