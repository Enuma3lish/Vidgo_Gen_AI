<template>
  <div class="flex items-center gap-2">
    <div class="flex rounded-lg bg-gray-800 p-1">
      <button
        v-for="preset in presets"
        :key="preset.value"
        @click="selectPreset(preset.value)"
        :class="[
          'px-3 py-1.5 text-xs font-medium rounded-md transition-colors',
          selectedPreset === preset.value
            ? 'bg-indigo-600 text-white'
            : 'text-gray-400 hover:text-white hover:bg-gray-700'
        ]"
      >
        {{ preset.label }}
      </button>
    </div>
    <div v-if="selectedPreset === 'custom'" class="flex items-center gap-2">
      <input
        type="date"
        v-model="customStart"
        @change="emitCustomRange"
        class="bg-gray-800 border border-gray-600 rounded-md px-2 py-1.5 text-xs text-gray-300 focus:ring-indigo-500 focus:border-indigo-500"
      />
      <span class="text-gray-500 text-xs">to</span>
      <input
        type="date"
        v-model="customEnd"
        @change="emitCustomRange"
        class="bg-gray-800 border border-gray-600 rounded-md px-2 py-1.5 text-xs text-gray-300 focus:ring-indigo-500 focus:border-indigo-500"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

export interface DateRange {
  preset: string
  startDate: string | null
  endDate: string | null
  days: number
  months: number
}

const emit = defineEmits<{
  (e: 'change', range: DateRange): void
}>()

const presets = [
  { label: '7D', value: '7d' },
  { label: '30D', value: '30d' },
  { label: '90D', value: '90d' },
  { label: '1Y', value: '1y' },
  { label: 'Custom', value: 'custom' },
]

const selectedPreset = ref('30d')
const customStart = ref('')
const customEnd = ref('')

function selectPreset(value: string) {
  selectedPreset.value = value
  if (value !== 'custom') {
    const daysMap: Record<string, number> = { '7d': 7, '30d': 30, '90d': 90, '1y': 365 }
    const monthsMap: Record<string, number> = { '7d': 1, '30d': 1, '90d': 3, '1y': 12 }
    emit('change', {
      preset: value,
      startDate: null,
      endDate: null,
      days: daysMap[value] || 30,
      months: monthsMap[value] || 1,
    })
  }
}

function emitCustomRange() {
  if (customStart.value && customEnd.value) {
    const start = new Date(customStart.value)
    const end = new Date(customEnd.value)
    const diffDays = Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24))
    const diffMonths = Math.ceil(diffDays / 30)
    emit('change', {
      preset: 'custom',
      startDate: customStart.value,
      endDate: customEnd.value,
      days: Math.max(diffDays, 1),
      months: Math.max(diffMonths, 1),
    })
  }
}
</script>
