<template>
  <div class="chart-container" :style="{ height: height + 'px' }">
    <Doughnut :data="chartData" :options="mergedOptions" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Doughnut } from 'vue-chartjs'
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
} from 'chart.js'

ChartJS.register(ArcElement, Tooltip, Legend)

interface Props {
  chartData: {
    labels: string[]
    datasets: Array<{
      data: number[]
      backgroundColor?: string[]
      borderColor?: string[]
      borderWidth?: number
      hoverOffset?: number
    }>
  }
  height?: number
  options?: Record<string, any>
}

const props = withDefaults(defineProps<Props>(), {
  height: 280,
  options: () => ({}),
})

const defaultOptions = {
  responsive: true,
  maintainAspectRatio: false,
  cutout: '60%',
  plugins: {
    legend: {
      display: true,
      position: 'bottom' as const,
      labels: {
        color: '#9ca3af',
        font: { size: 12, family: 'Inter, system-ui, sans-serif' },
        usePointStyle: true,
        padding: 16,
      },
    },
    tooltip: {
      backgroundColor: '#1f2937',
      titleColor: '#f9fafb',
      bodyColor: '#d1d5db',
      borderColor: '#374151',
      borderWidth: 1,
      padding: 10,
      cornerRadius: 8,
    },
  },
}

const mergedOptions = computed(() => {
  return deepMerge(defaultOptions, props.options)
})

function deepMerge(target: any, source: any): any {
  const result = { ...target }
  for (const key of Object.keys(source)) {
    if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
      result[key] = deepMerge(result[key] || {}, source[key])
    } else {
      result[key] = source[key]
    }
  }
  return result
}
</script>

<style scoped>
.chart-container {
  position: relative;
  width: 100%;
}
</style>
