<script setup lang="ts">
interface Props {
  size?: 'sm' | 'md' | 'lg' | 'xl'
  color?: string
}

withDefaults(defineProps<Props>(), {
  size: 'md',
  color: '#667eea'
})
</script>

<template>
  <div class="spinner" :class="`size-${size}`" :style="{ borderTopColor: color }">
    <span class="sr-only">Loading...</span>
  </div>
</template>

<style scoped>
.spinner {
  border: 3px solid #f0f0f0;
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.size-sm {
  width: 16px;
  height: 16px;
  border-width: 2px;
}

.size-md {
  width: 24px;
  height: 24px;
  border-width: 3px;
}

.size-lg {
  width: 40px;
  height: 40px;
  border-width: 4px;
}

.size-xl {
  width: 56px;
  height: 56px;
  border-width: 5px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
