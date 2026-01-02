<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useAdminStore } from '@/stores/admin'

const adminStore = useAdminStore()

const selectedToolType = ref('')
const selectedStatus = ref('')

const toolTypes = [
  { value: 'background_removal', label: 'Background Removal' },
  { value: 'product_scene', label: 'Product Scene' },
  { value: 'try_on', label: 'AI Try-On' },
  { value: 'room_redesign', label: 'Room Redesign' },
  { value: 'short_video', label: 'Short Video' }
]

const statuses = [
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'featured', label: 'Featured' }
]

onMounted(() => {
  loadMaterials()
})

watch([selectedToolType, selectedStatus], () => {
  loadMaterials()
})

async function loadMaterials(page = 1) {
  await adminStore.fetchMaterials({
    page,
    per_page: 20,
    tool_type: selectedToolType.value || undefined,
    status: selectedStatus.value || undefined
  })
}

async function reviewMaterial(materialId: string, action: 'approve' | 'reject' | 'feature') {
  let reason: string | undefined
  if (action === 'reject') {
    reason = prompt('Enter rejection reason:') || undefined
    if (!reason) return
  }

  await adminStore.reviewMaterial(materialId, action, reason)
  loadMaterials(adminStore.materialsPage)
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString()
}

function getStatusClass(status: string | null): string {
  if (!status) return ''
  return status.toLowerCase()
}

function getToolLabel(toolType: string | null): string {
  const tool = toolTypes.find(t => t.value === toolType)
  return tool?.label || toolType || '-'
}
</script>

<template>
  <div class="admin-materials">
    <header class="page-header">
      <h1>Material Management</h1>
      <p class="subtitle">Manage generated examples and showcases</p>
    </header>

    <!-- Filters -->
    <div class="filters">
      <select v-model="selectedToolType" class="filter-select">
        <option value="">All Tools</option>
        <option v-for="tool in toolTypes" :key="tool.value" :value="tool.value">
          {{ tool.label }}
        </option>
      </select>
      <select v-model="selectedStatus" class="filter-select">
        <option value="">All Statuses</option>
        <option v-for="status in statuses" :key="status.value" :value="status.value">
          {{ status.label }}
        </option>
      </select>
    </div>

    <!-- Materials Grid -->
    <div class="materials-grid">
      <div
        v-for="material in adminStore.materials"
        :key="material.id"
        class="material-card"
      >
        <div class="material-preview">
          <img
            v-if="material.result_image_url"
            :src="material.result_image_url"
            :alt="material.title_en || 'Material'"
          />
          <video
            v-else-if="material.result_video_url"
            :src="material.result_video_url"
            muted
            loop
            @mouseenter="($event.target as HTMLVideoElement).play()"
            @mouseleave="($event.target as HTMLVideoElement).pause()"
          />
          <div v-else class="no-preview">No Preview</div>
        </div>

        <div class="material-info">
          <div class="material-header">
            <span class="tool-type">{{ getToolLabel(material.tool_type) }}</span>
            <span class="status-badge" :class="getStatusClass(material.status)">
              {{ material.status }}
            </span>
          </div>

          <h3 class="material-title">{{ material.title_en || material.topic }}</h3>

          <div class="material-meta">
            <span>{{ material.view_count }} views</span>
            <span>{{ formatDate(material.created_at) }}</span>
          </div>

          <div class="material-actions" v-if="material.status === 'pending'">
            <button @click="reviewMaterial(material.id, 'approve')" class="btn approve">
              Approve
            </button>
            <button @click="reviewMaterial(material.id, 'feature')" class="btn feature">
              Feature
            </button>
            <button @click="reviewMaterial(material.id, 'reject')" class="btn reject">
              Reject
            </button>
          </div>
          <div class="material-actions" v-else-if="material.status !== 'featured'">
            <button @click="reviewMaterial(material.id, 'feature')" class="btn feature">
              Make Featured
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="adminStore.materials.length === 0 && !adminStore.isLoading" class="empty-state">
      <p>No materials found</p>
    </div>

    <!-- Pagination -->
    <div class="pagination" v-if="adminStore.materialsTotal > 20">
      <button
        @click="loadMaterials(adminStore.materialsPage - 1)"
        :disabled="adminStore.materialsPage <= 1"
        class="page-btn"
      >
        Previous
      </button>
      <span class="page-info">
        Page {{ adminStore.materialsPage }} of {{ Math.ceil(adminStore.materialsTotal / 20) }}
      </span>
      <button
        @click="loadMaterials(adminStore.materialsPage + 1)"
        :disabled="adminStore.materialsPage >= Math.ceil(adminStore.materialsTotal / 20)"
        class="page-btn"
      >
        Next
      </button>
    </div>

    <!-- Loading -->
    <div v-if="adminStore.isLoading" class="loading">
      <div class="spinner"></div>
    </div>
  </div>
</template>

<style scoped>
.admin-materials {
  padding: 2rem;
  max-width: 1400px;
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

.filters {
  display: flex;
  gap: 1rem;
  margin: 2rem 0;
}

.filter-select {
  padding: 0.75rem 1rem;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 1rem;
  background: white;
  min-width: 150px;
}

.materials-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.5rem;
}

.material-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.material-preview {
  aspect-ratio: 4/3;
  background: #f5f5f5;
  overflow: hidden;
}

.material-preview img,
.material-preview video {
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

.material-info {
  padding: 1rem;
}

.material-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.tool-type {
  font-size: 0.75rem;
  color: #666;
}

.status-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: capitalize;
}

.status-badge.pending { background: #fff3e0; color: #f57c00; }
.status-badge.approved { background: #e8f5e9; color: #388e3c; }
.status-badge.rejected { background: #ffebee; color: #d32f2f; }
.status-badge.featured { background: #e3f2fd; color: #1976d2; }

.material-title {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 0.5rem;
  color: #1a1a2e;
}

.material-meta {
  display: flex;
  gap: 1rem;
  font-size: 0.75rem;
  color: #999;
  margin-bottom: 1rem;
}

.material-actions {
  display: flex;
  gap: 0.5rem;
}

.btn {
  flex: 1;
  padding: 0.5rem;
  border: none;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}

.btn:hover {
  opacity: 0.8;
}

.btn.approve {
  background: #e8f5e9;
  color: #388e3c;
}

.btn.feature {
  background: #e3f2fd;
  color: #1976d2;
}

.btn.reject {
  background: #ffebee;
  color: #d32f2f;
}

.empty-state {
  text-align: center;
  padding: 4rem;
  color: #666;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 1rem;
  margin-top: 2rem;
}

.page-btn {
  padding: 0.5rem 1rem;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background: white;
  cursor: pointer;
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-info {
  color: #666;
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
</style>
