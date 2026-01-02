<script setup lang="ts">
import { onMounted } from 'vue'
import { useAdminStore } from '@/stores/admin'

const adminStore = useAdminStore()

const toolTypes: Record<string, string> = {
  background_removal: 'Background Removal',
  product_scene: 'Product Scene',
  try_on: 'AI Try-On',
  room_redesign: 'Room Redesign',
  short_video: 'Short Video'
}

onMounted(() => {
  adminStore.fetchModerationQueue()
})

async function reviewItem(materialId: string, action: 'approve' | 'reject' | 'feature') {
  let reason: string | undefined
  if (action === 'reject') {
    reason = prompt('Enter rejection reason:') || undefined
    if (!reason) return
  }

  await adminStore.reviewMaterial(materialId, action, reason)
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString()
}

function getToolLabel(toolType: string | null): string {
  return toolType ? toolTypes[toolType] || toolType : '-'
}
</script>

<template>
  <div class="admin-moderation">
    <header class="page-header">
      <h1>Content Moderation</h1>
      <p class="subtitle">Review pending user-generated content</p>
    </header>

    <!-- Queue Stats -->
    <div class="queue-stats">
      <div class="stat">
        <span class="stat-value">{{ adminStore.moderationQueue.length }}</span>
        <span class="stat-label">Items in Queue</span>
      </div>
    </div>

    <!-- Moderation Queue -->
    <div class="moderation-queue">
      <div
        v-for="item in adminStore.moderationQueue"
        :key="item.id"
        class="moderation-item"
      >
        <div class="item-preview">
          <img
            v-if="item.result_image_url"
            :src="item.result_image_url"
            :alt="item.topic"
          />
          <video
            v-else-if="item.result_video_url"
            :src="item.result_video_url"
            muted
            controls
          />
          <div v-else class="no-preview">No Preview</div>
        </div>

        <div class="item-details">
          <div class="item-header">
            <span class="tool-badge">{{ getToolLabel(item.tool_type) }}</span>
            <span class="source-badge" :class="item.source">{{ item.source }}</span>
          </div>

          <h3 class="item-topic">{{ item.topic }}</h3>

          <div class="item-prompt" v-if="item.prompt">
            <strong>Prompt:</strong>
            <p>{{ item.prompt }}</p>
          </div>

          <div class="item-meta">
            <span>Submitted: {{ formatDate(item.created_at) }}</span>
          </div>
        </div>

        <div class="item-actions">
          <button @click="reviewItem(item.id, 'approve')" class="action-btn approve">
            <span class="icon">✓</span>
            Approve
          </button>
          <button @click="reviewItem(item.id, 'feature')" class="action-btn feature">
            <span class="icon">★</span>
            Feature
          </button>
          <button @click="reviewItem(item.id, 'reject')" class="action-btn reject">
            <span class="icon">✕</span>
            Reject
          </button>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="adminStore.moderationQueue.length === 0 && !adminStore.isLoading" class="empty-state">
      <div class="empty-icon">✓</div>
      <h2>All Clear!</h2>
      <p>No items pending review</p>
    </div>

    <!-- Loading -->
    <div v-if="adminStore.isLoading" class="loading">
      <div class="spinner"></div>
    </div>
  </div>
</template>

<style scoped>
.admin-moderation {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header h1 {
  font-size: 2rem;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0;
}

.subtitle {
  color: #666;
  margin-top: 0.5rem;
}

.queue-stats {
  display: flex;
  gap: 1rem;
  margin: 2rem 0;
}

.stat {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.stat-value {
  display: block;
  font-size: 2rem;
  font-weight: 700;
  color: #1a1a2e;
}

.stat-label {
  font-size: 0.875rem;
  color: #666;
}

.moderation-queue {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.moderation-item {
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  display: grid;
  grid-template-columns: 300px 1fr auto;
  overflow: hidden;
}

.item-preview {
  aspect-ratio: 4/3;
  background: #f5f5f5;
  overflow: hidden;
}

.item-preview img,
.item-preview video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.no-preview {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
}

.item-details {
  padding: 1.5rem;
}

.item-header {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.tool-badge {
  background: #f0f0f0;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  color: #666;
}

.source-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  text-transform: capitalize;
}

.source-badge.user { background: #e3f2fd; color: #1976d2; }
.source-badge.admin { background: #f3e5f5; color: #7b1fa2; }
.source-badge.seed { background: #e8f5e9; color: #388e3c; }

.item-topic {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0 0 1rem;
  color: #1a1a2e;
}

.item-prompt {
  background: #f9f9f9;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
}

.item-prompt strong {
  display: block;
  font-size: 0.75rem;
  color: #666;
  margin-bottom: 0.5rem;
}

.item-prompt p {
  margin: 0;
  font-size: 0.875rem;
  color: #333;
  line-height: 1.5;
}

.item-meta {
  font-size: 0.75rem;
  color: #999;
}

.item-actions {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 1.5rem;
  background: #f9f9f9;
  border-left: 1px solid #f0f0f0;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border: none;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn .icon {
  font-size: 1rem;
}

.action-btn.approve {
  background: #e8f5e9;
  color: #388e3c;
}

.action-btn.approve:hover {
  background: #c8e6c9;
}

.action-btn.feature {
  background: #fff3e0;
  color: #f57c00;
}

.action-btn.feature:hover {
  background: #ffe0b2;
}

.action-btn.reject {
  background: #ffebee;
  color: #d32f2f;
}

.action-btn.reject:hover {
  background: #ffcdd2;
}

.empty-state {
  text-align: center;
  padding: 4rem;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.empty-icon {
  width: 80px;
  height: 80px;
  background: #e8f5e9;
  color: #388e3c;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2rem;
  margin: 0 auto 1rem;
}

.empty-state h2 {
  margin: 0 0 0.5rem;
  color: #1a1a2e;
}

.empty-state p {
  color: #666;
  margin: 0;
}

.loading {
  display: flex;
  justify-content: center;
  padding: 2rem;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #f0f0f0;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 900px) {
  .moderation-item {
    grid-template-columns: 1fr;
  }

  .item-actions {
    flex-direction: row;
    border-left: none;
    border-top: 1px solid #f0f0f0;
  }
}
</style>
