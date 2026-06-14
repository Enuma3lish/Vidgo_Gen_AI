<script setup lang="ts">
import { ref } from 'vue'
import BaseBadge from '@/components/atoms/BaseBadge.vue'

interface Props {
  title: string
  imageUrl?: string
  videoUrl?: string
  toolType: string
  topic?: string
  viewCount?: number
  isFeatured?: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  click: []
  use: []
}>()

const isHovering = ref(false)
const videoRef = ref<HTMLVideoElement | null>(null)

function handleMouseEnter() {
  isHovering.value = true
  if (videoRef.value) {
    videoRef.value.play()
  }
}

function handleMouseLeave() {
  isHovering.value = false
  if (videoRef.value) {
    videoRef.value.pause()
    videoRef.value.currentTime = 0
  }
}

function formatViews(count: number): string {
  if (count >= 1000) {
    return (count / 1000).toFixed(1) + 'K'
  }
  return count.toString()
}
</script>

<template>
  <div
    class="material-card"
    :class="{ 'is-hovering': isHovering }"
    @mouseenter="handleMouseEnter"
    @mouseleave="handleMouseLeave"
    @click="emit('click')"
  >
    <div class="card-media">
      <img v-if="imageUrl && !videoUrl" :src="imageUrl" :alt="title" class="media-image" />
      <video
        v-else-if="videoUrl"
        ref="videoRef"
        :src="videoUrl"
        :poster="imageUrl"
        muted
        loop
        playsinline
        class="media-video"
      />
      <div v-else class="media-placeholder">
        <span>No preview</span>
      </div>

      <div class="card-overlay">
        <button class="use-btn" @click.stop="emit('use')">
          Use This
        </button>
      </div>

      <BaseBadge v-if="isFeatured" variant="premium" class="featured-badge">
        Featured
      </BaseBadge>
    </div>

    <div class="card-content">
      <h3 class="card-title">{{ title }}</h3>
      <div class="card-meta">
        <span class="tool-type">{{ toolType }}</span>
        <span v-if="viewCount !== undefined" class="view-count">
          {{ formatViews(viewCount) }} views
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.material-card {
  background: white;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  cursor: pointer;
  transition: all 0.3s ease;
}

.material-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}

.card-media {
  position: relative;
  aspect-ratio: 4/3;
  background: #f5f5f5;
  overflow: hidden;
}

.media-image,
.media-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}

.material-card:hover .media-image,
.material-card:hover .media-video {
  transform: scale(1.05);
}

.media-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
}

.card-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.material-card:hover .card-overlay {
  opacity: 1;
}

.use-btn {
  padding: 0.75rem 1.5rem;
  background: white;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  color: #667eea;
  cursor: pointer;
  transition: all 0.2s ease;
}

.use-btn:hover {
  transform: scale(1.05);
  background: #667eea;
  color: white;
}

.featured-badge {
  position: absolute;
  top: 0.75rem;
  right: 0.75rem;
}

.card-content {
  padding: 1rem;
}

.card-title {
  margin: 0 0 0.5rem;
  font-size: 0.9375rem;
  font-weight: 600;
  color: #1a1a2e;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.75rem;
  color: #999;
}

.tool-type {
  text-transform: capitalize;
}
</style>
