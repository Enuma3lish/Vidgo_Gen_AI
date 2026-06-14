<script setup lang="ts">
interface Props {
  padding?: 'none' | 'sm' | 'md' | 'lg'
  blur?: 'sm' | 'md' | 'lg'
  hoverable?: boolean
}

withDefaults(defineProps<Props>(), {
  padding: 'md',
  blur: 'md',
  hoverable: false
})
</script>

<template>
  <div
    class="glass-card"
    :class="[`padding-${padding}`, `blur-${blur}`, { 'is-hoverable': hoverable }]"
  >
    <slot />
  </div>
</template>

<style scoped>
.glass-card {
  background: rgba(255, 255, 255, 0.7);
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
  transition: all 0.3s ease;
}

.blur-sm {
  backdrop-filter: blur(8px);
}

.blur-md {
  backdrop-filter: blur(16px);
}

.blur-lg {
  backdrop-filter: blur(24px);
}

.padding-none {
  padding: 0;
}

.padding-sm {
  padding: 1rem;
}

.padding-md {
  padding: 1.5rem;
}

.padding-lg {
  padding: 2rem;
}

.is-hoverable:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
}
</style>
