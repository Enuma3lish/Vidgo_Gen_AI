<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

defineProps<{
  beforeImage: string
  afterImage: string
  beforeLabel?: string
  afterLabel?: string
}>()

const sliderPosition = ref(50)
const containerRef = ref<HTMLDivElement | null>(null)
const isDragging = ref(false)

function updatePosition(clientX: number) {
  if (!containerRef.value) return

  const rect = containerRef.value.getBoundingClientRect()
  const x = clientX - rect.left
  const percentage = (x / rect.width) * 100
  sliderPosition.value = Math.max(0, Math.min(100, percentage))
}

function handleMouseDown(e: MouseEvent) {
  isDragging.value = true
  updatePosition(e.clientX)
}

function handleMouseMove(e: MouseEvent) {
  if (isDragging.value) {
    updatePosition(e.clientX)
  }
}

function handleMouseUp() {
  isDragging.value = false
}

function handleTouchStart(e: TouchEvent) {
  isDragging.value = true
  updatePosition(e.touches[0].clientX)
}

function handleTouchMove(e: TouchEvent) {
  if (isDragging.value) {
    updatePosition(e.touches[0].clientX)
  }
}

onMounted(() => {
  document.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('mouseup', handleMouseUp)
  document.addEventListener('touchmove', handleTouchMove as EventListener)
  document.addEventListener('touchend', handleMouseUp)
})

onUnmounted(() => {
  document.removeEventListener('mousemove', handleMouseMove)
  document.removeEventListener('mouseup', handleMouseUp)
  document.removeEventListener('touchmove', handleTouchMove as EventListener)
  document.removeEventListener('touchend', handleMouseUp)
})
</script>

<template>
  <div
    ref="containerRef"
    class="relative overflow-hidden rounded-2xl select-none"
    @mousedown="handleMouseDown"
    @touchstart="handleTouchStart"
  >
    <!-- After Image (Background) -->
    <img
      :src="afterImage"
      alt="After"
      class="w-full h-auto block"
    />

    <!-- Before Image (Clipped) -->
    <div
      class="absolute inset-0 overflow-hidden"
      :style="{ width: `${sliderPosition}%` }"
    >
      <img
        :src="beforeImage"
        alt="Before"
        class="w-full h-full object-cover"
        :style="{ width: containerRef ? `${containerRef.offsetWidth}px` : '100%' }"
      />
    </div>

    <!-- Slider Line -->
    <div
      class="absolute top-0 bottom-0 w-1 bg-white shadow-lg cursor-ew-resize"
      :style="{ left: `${sliderPosition}%`, transform: 'translateX(-50%)' }"
    >
      <!-- Handle -->
      <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-10 h-10 bg-white rounded-full shadow-lg flex items-center justify-center">
        <svg class="w-5 h-5 text-dark-900" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9l4-4 4 4m0 6l-4 4-4-4" />
        </svg>
      </div>
    </div>

    <!-- Labels -->
    <div
      v-if="beforeLabel"
      class="absolute top-4 left-4 bg-dark-900/80 px-3 py-1 rounded-lg text-sm font-medium"
    >
      {{ beforeLabel }}
    </div>
    <div
      v-if="afterLabel"
      class="absolute top-4 right-4 bg-dark-900/80 px-3 py-1 rounded-lg text-sm font-medium"
    >
      {{ afterLabel }}
    </div>
  </div>
</template>
