<template>
  <div class="chart-container" :style="{ height: height + 'px' }">
    <Bar :data="chartData" :options="mergedOptions" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend)

interface Props {
  chartData: {
    labels: string[]
    datasets: Array<{
      label: string
      data: number[]
      backgroundColor?: string | string[]
      borderColor?: string | string[]
      borderWidth?: number
      borderRadius?: number
      barPercentage?: number
    }>
  }
  height?: number
  horizontal?: boolean
  options?: Record<string, any>
}

const props = withDefaults(defineProps<Props>(), {
  height: 300,
  horizontal: false,
  options: () => ({}),
})

const defaultOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  indexAxis: props.horizontal ? ('y' as const) : ('x' as const),
  plugins: {
    legend: {
      display: true,
      position: 'top' as const,
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
  scales: {
    x: {
      grid: { color: 'rgba(75, 85, 99, 0.2)' },
      ticks: { color: '#9ca3af', font: { size: 11 } },
      beginAtZero: true,
    },
    y: {
      grid: { color: 'rgba(75, 85, 99, 0.2)' },
      ticks: { color: '#9ca3af', font: { size: 11 } },
      beginAtZero: true,
    },
  },
}))

const mergedOptions = computed(() => {
  return deepMerge(defaultOptions.value, props.options)
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
