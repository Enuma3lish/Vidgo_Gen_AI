<script setup lang="ts">
/**
 * Activity feed — surfaces recent platform events on the admin dashboard.
 *
 * Pulls from /api/v1/admin/activity-feed, which derives entries from
 * existing tables (User, Order, Material, PaymentSettings,
 * ModelRegistryAudit). No new audit table — the data is already there;
 * this just timeline-merges it for admin visibility.
 *
 * Each entry deep-links into the matching detail view, so the feed
 * doubles as a fast nav surface ("oh that one customer signed up,
 * let me check them").
 */
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useLocalized } from '@/composables'
import apiClient from '@/api/client'

// 5-language picker — fixes ja/ko/es fall-through (BUG-017).
const { L } = useLocalized()

interface FeedEvent {
  type: 'user_signup' | 'order' | 'material_review' | 'payment_settings' | 'model_registry'
  summary: string
  actor: string | null
  timestamp: string
  target_url: string
}

const events = ref<FeedEvent[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    const res = await apiClient.get('/api/v1/admin/activity-feed', { params: { limit: 25 } })
    events.value = res.data.events || []
  } catch (e: any) {
    error.value = e.message || 'Failed to load activity feed'
  } finally {
    loading.value = false
  }
}

function typeBadge(type: FeedEvent['type']): { label: string; color: string } {
  switch (type) {
    case 'user_signup':       return { label: 'USER',  color: '#10b981' }
    case 'order':             return { label: 'ORDER', color: '#3b82f6' }
    case 'material_review':   return { label: 'MAT',   color: '#f59e0b' }
    case 'payment_settings':  return { label: 'PAY',   color: '#a855f7' }
    case 'model_registry':    return { label: 'MODEL', color: '#ec4899' }
    default:                  return { label: '·',     color: '#6b7280' }
  }
}

function relTime(iso: string): string {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  const now = Date.now()
  const sec = Math.max(0, Math.floor((now - then) / 1000))
  if (sec < 60) return L(`${sec} 秒前`, `${sec}s ago`, `${sec}秒前`, `${sec}초 전`, `hace ${sec} s`)
  const min = Math.floor(sec / 60)
  if (min < 60) return L(`${min} 分鐘前`, `${min}m ago`, `${min}分前`, `${min}분 전`, `hace ${min} min`)
  const hr = Math.floor(min / 60)
  if (hr < 24) return L(`${hr} 小時前`, `${hr}h ago`, `${hr}時間前`, `${hr}시간 전`, `hace ${hr} h`)
  const day = Math.floor(hr / 24)
  if (day < 30) return L(`${day} 天前`, `${day}d ago`, `${day}日前`, `${day}일 전`, `hace ${day} d`)
  return new Date(iso).toLocaleDateString()
}

onMounted(load)
</script>

<template>
  <div class="activity-feed">
    <div class="activity-feed-head">
      <h3 class="activity-feed-title">{{ L('最近活動', 'Recent Activity', '最近のアクティビティ', '최근 활동', 'Actividad reciente') }}</h3>
      <button
        @click="load"
        :disabled="loading"
        class="activity-feed-refresh"
        :title="L('重新整理', 'Refresh', '更新', '새로고침', 'Actualizar')"
      >
        {{ loading ? '⟳' : '↻' }}
      </button>
    </div>

    <div v-if="error" class="activity-feed-error">
      {{ error }}
    </div>

    <div v-else-if="loading && events.length === 0" class="activity-feed-empty">
      {{ L('載入中…', 'Loading…', '読み込み中…', '불러오는 중…', 'Cargando…') }}
    </div>

    <div v-else-if="events.length === 0" class="activity-feed-empty">
      {{ L('尚無事件', 'No recent events', '最近のイベントはありません', '최근 이벤트가 없습니다', 'Sin eventos recientes') }}
    </div>

    <div v-else class="activity-feed-list">
      <RouterLink
        v-for="(ev, i) in events"
        :key="i"
        :to="ev.target_url"
        class="activity-feed-row"
      >
        <span
          class="activity-feed-badge"
          :style="`background: ${typeBadge(ev.type).color}1a; color: ${typeBadge(ev.type).color}; border: 1px solid ${typeBadge(ev.type).color}40;`"
        >
          {{ typeBadge(ev.type).label }}
        </span>
        <div class="activity-feed-body">
          <div class="activity-feed-summary">{{ ev.summary }}</div>
          <div class="activity-feed-meta">
            <span v-if="ev.actor">{{ ev.actor }} · </span>
            <span class="activity-feed-time">{{ relTime(ev.timestamp) }}</span>
          </div>
        </div>
      </RouterLink>
    </div>
  </div>
</template>

<style scoped>
.activity-feed {
  background: #141420;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  padding: 18px;
}

.activity-feed-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.activity-feed-title {
  font-size: 14px;
  font-weight: 700;
  color: #f5f5fa;
  margin: 0;
  letter-spacing: -0.01em;
}

.activity-feed-refresh {
  width: 26px;
  height: 26px;
  border-radius: 5px;
  background: #0d0d15;
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #9494b0;
  cursor: pointer;
  font-size: 14px;
}

.activity-feed-refresh:hover { color: #f5f5fa; background: rgba(245, 158, 11, 0.08); }

.activity-feed-empty,
.activity-feed-error {
  padding: 24px 12px;
  text-align: center;
  font-size: 12px;
  color: #6b6b8a;
}

.activity-feed-error { color: #ef4444; }

.activity-feed-list {
  display: flex;
  flex-direction: column;
  max-height: 540px;
  overflow-y: auto;
  gap: 2px;
  margin: 0 -6px;
}

.activity-feed-row {
  display: grid;
  grid-template-columns: 50px 1fr;
  gap: 10px;
  align-items: start;
  padding: 10px 8px;
  border-radius: 6px;
  text-decoration: none;
  color: inherit;
  transition: background 0.12s ease;
}

.activity-feed-row:hover { background: rgba(245, 158, 11, 0.05); }

.activity-feed-badge {
  font-family: ui-monospace, "JetBrains Mono", "SF Mono", monospace;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.08em;
  padding: 3px 4px;
  border-radius: 3px;
  text-align: center;
  white-space: nowrap;
}

.activity-feed-body { min-width: 0; }

.activity-feed-summary {
  font-size: 12px;
  color: #e8e8f0;
  line-height: 1.35;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.activity-feed-meta {
  font-size: 10px;
  color: #6b6b8a;
  margin-top: 2px;
}

.activity-feed-time {
  font-family: ui-monospace, "JetBrains Mono", "SF Mono", monospace;
}
</style>
