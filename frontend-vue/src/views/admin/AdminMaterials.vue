<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAdminStore } from '@/stores/admin'
import { useLocalized } from '@/composables'

const adminStore = useAdminStore()
const { locale } = useI18n()
// 5-language inline picker — fixes ja/ko/es fall-through (BUG-017).
const { L } = useLocalized()

const selectedToolType = ref('')
const selectedStatus = ref('')
// Retained for backend-data ternaries below (material.title_zh / title_en).
const isZh = computed(() => locale.value === 'zh-TW')

// Delegates to the 5-language L() helper so ja/ko/es viewers don't see
// English (BUG-017). Optional ja/ko/es default to English when omitted.
function localized(zh: string, en: string, ja?: string, ko?: string, es?: string): string {
  return L(zh, en, ja, ko, es)
}

const toolTypes = computed(() => [
  { value: 'background_removal', label: localized('智能去背', 'Background Removal', '背景除去', '배경 제거', 'Quitar fondo') },
  { value: 'product_scene', label: localized('商品情境', 'Product Scene', '商品シーン', '제품 장면', 'Escena de producto') },
  { value: 'try_on', label: localized('模特換裝', 'Try-On', '試着', '가상 피팅', 'Probador virtual') },
  { value: 'room_redesign', label: localized('空間改造', 'Room Redesign', '空間リデザイン', '공간 리디자인', 'Rediseño de espacio') },
  { value: 'short_video', label: localized('短影音', 'Short Video', 'ショート動画', '쇼트 비디오', 'Video corto') },
  { value: 'ai_avatar', label: localized('數位人', 'AI Avatar', 'AIアバター', 'AI 아바타', 'Avatar IA') },
  { value: 'pattern_generate', label: localized('圖案生成', 'Pattern Generator', 'パターン生成', '패턴 생성', 'Generador de patrones') },
  { value: 'effect', label: localized('圖片特效', 'Image Effect', '画像エフェクト', '이미지 이펙트', 'Efecto de imagen') }
])

const statuses = computed(() => [
  { value: 'pending', label: localized('待審核', 'Pending', '審査待ち', '검수 대기', 'Pendiente') },
  { value: 'approved', label: localized('已通過', 'Approved', '承認済み', '승인됨', 'Aprobado') },
  { value: 'rejected', label: localized('已拒絕', 'Rejected', '却下', '거부됨', 'Rechazado') },
  { value: 'featured', label: localized('精選', 'Featured', 'おすすめ', '추천', 'Destacado') }
])

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
    reason = prompt(localized('請輸入拒絕原因：', 'Please enter a rejection reason:', '却下理由を入力してください：', '거부 사유를 입력해 주세요:', 'Introduce el motivo del rechazo:')) || undefined
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
  const tool = toolTypes.value.find(t => t.value === toolType)
  return tool?.label || toolType || '-'
}

function getStatusLabel(status: string | null): string {
  const item = statuses.value.find(s => s.value === status)
  return item?.label || status || '-'
}

function getMaterialTitle(material: { title_zh?: string | null; title_en?: string | null; topic?: string | null }): string {
  // Backend stores only title_zh / title_en — ja/ko/es fall through to English (BUG-017, backend out of scope).
  return isZh.value
    ? material.title_zh || material.title_en || material.topic || '-'
    : material.title_en || material.title_zh || material.topic || '-'
}
</script>

<template>
  <div class="admin-materials">
    <header class="page-header">
      <h1>{{ localized('素材管理', 'Material Management', '素材管理', '소재 관리', 'Gestión de materiales') }}</h1>
      <p class="subtitle">{{ localized('管理預生成範例、展示素材與審核狀態', 'Manage pregenerated examples, showcase materials, and review status', '事前生成のサンプル、紹介素材、審査ステータスを管理します', '미리 생성된 예시, 쇼케이스 소재, 검수 상태를 관리합니다', 'Gestiona ejemplos pregenerados, materiales de muestra y el estado de revisión') }}</p>
    </header>

    <!-- Filters -->
    <div class="filters">
      <select v-model="selectedToolType" class="filter-select">
        <option value="">{{ localized('全部工具', 'All Tools', 'すべてのツール', '모든 도구', 'Todas las herramientas') }}</option>
        <option v-for="tool in toolTypes" :key="tool.value" :value="tool.value">
          {{ tool.label }}
        </option>
      </select>
      <select v-model="selectedStatus" class="filter-select">
        <option value="">{{ localized('全部狀態', 'All Statuses', 'すべてのステータス', '모든 상태', 'Todos los estados') }}</option>
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
            :alt="getMaterialTitle(material) || localized('素材', 'Material', '素材', '소재', 'Material')"
          />
          <video
            v-else-if="material.result_video_url"
            :src="material.result_video_url"
            muted
            loop
            @mouseenter="($event.target as HTMLVideoElement).play()"
            @mouseleave="($event.target as HTMLVideoElement).pause()"
          />
          <div v-else class="no-preview">{{ localized('無預覽', 'No Preview', 'プレビューなし', '미리보기 없음', 'Sin vista previa') }}</div>
        </div>

        <div class="material-info">
          <div class="material-header">
            <span class="tool-type">{{ getToolLabel(material.tool_type) }}</span>
            <span class="status-badge" :class="getStatusClass(material.status)">
              {{ getStatusLabel(material.status) }}
            </span>
          </div>

          <h3 class="material-title">{{ getMaterialTitle(material) }}</h3>

          <div class="material-meta">
            <span>{{ localized(`${material.view_count} 次瀏覽`, `${material.view_count} views`, `${material.view_count} 回視聴`, `조회 ${material.view_count}회`, `${material.view_count} vistas`) }}</span>
            <span>{{ formatDate(material.created_at) }}</span>
          </div>

          <div class="material-actions" v-if="material.status === 'pending'">
            <button @click="reviewMaterial(material.id, 'approve')" class="btn approve">
              {{ localized('通過', 'Approve', '承認', '승인', 'Aprobar') }}
            </button>
            <button @click="reviewMaterial(material.id, 'feature')" class="btn feature">
              {{ localized('設為精選', 'Feature', 'おすすめに設定', '추천 설정', 'Destacar') }}
            </button>
            <button @click="reviewMaterial(material.id, 'reject')" class="btn reject">
              {{ localized('拒絕', 'Reject', '却下', '거부', 'Rechazar') }}
            </button>
          </div>
          <div class="material-actions" v-else-if="material.status !== 'featured'">
            <button @click="reviewMaterial(material.id, 'feature')" class="btn feature">
              {{ localized('設為精選', 'Feature', 'おすすめに設定', '추천 설정', 'Destacar') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="adminStore.materials.length === 0 && !adminStore.isLoading" class="empty-state">
      <p>{{ localized('找不到素材', 'No materials found', '素材が見つかりません', '소재를 찾을 수 없습니다', 'No se encontraron materiales') }}</p>
    </div>

    <!-- Pagination -->
    <div class="pagination" v-if="adminStore.materialsTotal > 20">
      <button
        @click="loadMaterials(adminStore.materialsPage - 1)"
        :disabled="adminStore.materialsPage <= 1"
        class="page-btn"
      >
        {{ localized('上一頁', 'Previous', '前へ', '이전', 'Anterior') }}
      </button>
      <span class="page-info">
        {{ localized(`第 ${adminStore.materialsPage} / ${Math.ceil(adminStore.materialsTotal / 20)} 頁`, `Page ${adminStore.materialsPage} / ${Math.ceil(adminStore.materialsTotal / 20)}`, `${adminStore.materialsPage} / ${Math.ceil(adminStore.materialsTotal / 20)} ページ`, `${adminStore.materialsPage} / ${Math.ceil(adminStore.materialsTotal / 20)} 페이지`, `Página ${adminStore.materialsPage} / ${Math.ceil(adminStore.materialsTotal / 20)}`) }}
      </span>
      <button
        @click="loadMaterials(adminStore.materialsPage + 1)"
        :disabled="adminStore.materialsPage >= Math.ceil(adminStore.materialsTotal / 20)"
        class="page-btn"
      >
        {{ localized('下一頁', 'Next', '次へ', '다음', 'Siguiente') }}
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
  padding: 1.5rem 2rem 2rem;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header h1 {
  font-size: 2rem;
  font-weight: 700;
  color: #f5f5fa;
  margin: 0;
}

.subtitle {
  color: #9494b0;
  margin-top: 0.5rem;
}

.filters {
  display: flex;
  gap: 1rem;
  margin: 2rem 0;
}

.filter-select {
  padding: 0.75rem 1rem;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 8px;
  font-size: 1rem;
  background: #141420;
  min-width: 150px;
}

.materials-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.5rem;
}

.material-card {
  background: #141420;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  overflow: hidden;
}

.material-preview {
  aspect-ratio: 4/3;
  background: #0f0f17;
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
  color: #6b6b8a;
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
  color: #9494b0;
}

.status-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: capitalize;
}

.status-badge.pending { background: rgba(245,158,11,0.15); color: #f57c00; }
.status-badge.approved { background: rgba(16,185,129,0.15); color: #388e3c; }
.status-badge.rejected { background: rgba(244,67,54,0.15); color: #d32f2f; }
.status-badge.featured { background: rgba(25,118,210,0.15); color: #1976d2; }

.material-title {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 0.5rem;
  color: #f5f5fa;
}

.material-meta {
  display: flex;
  gap: 1rem;
  font-size: 0.75rem;
  color: #6b6b8a;
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
  background: rgba(16,185,129,0.15);
  color: #388e3c;
}

.btn.feature {
  background: rgba(25,118,210,0.15);
  color: #1976d2;
}

.btn.reject {
  background: rgba(244,67,54,0.15);
  color: #d32f2f;
}

.empty-state {
  text-align: center;
  padding: 4rem;
  color: #9494b0;
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
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 8px;
  background: #141420;
  cursor: pointer;
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-info {
  color: #9494b0;
}

.loading {
  display: flex;
  justify-content: center;
  padding: 2rem;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(255,255,255,0.1);
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
