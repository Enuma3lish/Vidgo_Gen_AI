<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue'
import { useAdminStore } from '@/stores/admin'
import { adminApi } from '@/api/admin'
import type { AdminUser, UserDetail } from '@/api/admin'

const adminStore = useAdminStore()

const searchQuery = ref('')
const selectedPlan = ref('')
const sortBy = ref('created_at')
const sortOrder = ref<'asc' | 'desc'>('desc')
const selectedUser = ref<UserDetail | null>(null)
const showUserModal = ref(false)
const showPromotionModal = ref(false)
const promotionTarget = ref<AdminUser | null>(null)
const promotionCodeInput = ref('')
const promotingUserId = ref<string | null>(null)
const testingUserId = ref<string | null>(null)

const plans = ['demo', 'basic', 'pro', 'premium', 'enterprise', 'test_pro_usd_1']

const registeredUsersTotal = computed(() => adminStore.dashboardStats?.users?.total ?? adminStore.usersTotal)
const filteredUsersTotal = computed(() => adminStore.usersTotal)
const paidUsersTotal = computed(() => adminStore.dashboardStats?.paid_stats?.paid ?? 0)
const freeUsersTotal = computed(() => adminStore.dashboardStats?.paid_stats?.free ?? 0)

onMounted(() => {
  adminStore.fetchDashboardStats()
  loadUsers()
})

watch([searchQuery, selectedPlan, sortBy, sortOrder], () => {
  loadUsers()
})

async function loadUsers(page = 1) {
  await adminStore.fetchUsers({
    page,
    per_page: 20,
    search: searchQuery.value || undefined,
    plan: selectedPlan.value || undefined,
    sort_by: sortBy.value,
    sort_order: sortOrder.value
  })
}

async function viewUser(userId: string) {
  const result = await adminApi.getUserDetail(userId)
  selectedUser.value = result.user as UserDetail
  selectedUser.value.generation_count = result.generation_count
  selectedUser.value.is_online = result.is_online
  showUserModal.value = true
}

async function toggleBan(userId: string, isActive: boolean) {
  if (isActive) {
    const reason = prompt('請輸入停權原因：')
    if (reason) {
      await adminStore.banUser(userId, reason)
    }
  } else {
    await adminStore.unbanUser(userId)
  }
}

function openPromotionModal(user: AdminUser) {
  promotionTarget.value = user
  promotionCodeInput.value = user.referral_code || ''
  showPromotionModal.value = true
}

async function makePromotionAccount(user: AdminUser) {
  if (user.referral_code || promotingUserId.value) return
  promotingUserId.value = user.id
  try {
    const result = await adminStore.setPromotionCode(user.id)
    if (result) {
      await loadUsers(adminStore.usersPage)
    }
  } finally {
    promotingUserId.value = null
  }
}

async function submitPromotionCode() {
  if (!promotionTarget.value) return

  const result = await adminStore.setPromotionCode(
    promotionTarget.value.id,
    promotionCodeInput.value.trim() || undefined
  )
  if (result) {
    showPromotionModal.value = false
    promotionTarget.value = null
    await loadUsers(adminStore.usersPage)
  }
}

async function grantTestAccount(user: AdminUser) {
  if (testingUserId.value) return
  const actionLabel = user.is_test_account
    ? '重設 $1 測試方案'
    : '指派 $1 測試方案'
  if (!confirm(`${actionLabel}？\n${user.email}\n\n此使用者將以 $1 USD / 月使用 Pro 全功能。`)) return

  testingUserId.value = user.id
  try {
    const result = await adminStore.grantTestAccount(user.id)
    if (result) {
      await loadUsers(adminStore.usersPage)
    }
  } finally {
    testingUserId.value = null
  }
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString()
}

function formatPlan(plan?: string | null): string {
  return (plan || 'demo').replace(/_/g, ' ')
}

function planClass(plan?: string | null): string {
  return (plan || 'demo').toLowerCase().replace(/[^a-z0-9_-]/g, '-')
}
</script>

<template>
  <div class="admin-users">
    <header class="page-header">
      <h1>使用者管理</h1>
      <p class="subtitle">管理會員方案、帳號狀態與推廣帳號</p>
    </header>

    <div v-if="adminStore.error" class="error-banner">
      <span>{{ adminStore.error }}</span>
      <button @click="adminStore.error = null" class="dismiss-btn">&times;</button>
    </div>

    <div class="summary-grid">
      <div class="summary-card">
        <span class="summary-label">註冊使用者</span>
        <strong>{{ registeredUsersTotal }}</strong>
        <span class="summary-note">目前篩選符合 {{ filteredUsersTotal }} 位</span>
      </div>
      <div class="summary-card">
        <span class="summary-label">付費 / 免費</span>
        <strong>{{ paidUsersTotal }} / {{ freeUsersTotal }}</strong>
        <span class="summary-note">依目前方案統計</span>
      </div>
      <div class="summary-card">
        <span class="summary-label">推廣帳號</span>
        <strong>{{ adminStore.promotionAccounts }}</strong>
        <span class="summary-note">帶來 {{ adminStore.promotionRegistrations }} 位註冊</span>
      </div>
    </div>

    <!-- Filters -->
    <div class="filters">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="搜尋電子郵件或姓名..."
        class="search-input"
      />
      <select v-model="selectedPlan" class="filter-select">
        <option value="">全部方案</option>
        <option v-for="plan in plans" :key="plan" :value="plan">
          {{ plan }}
        </option>
      </select>
      <select v-model="sortBy" class="filter-select">
        <option value="created_at">註冊日期</option>
        <option value="email">Email</option>
        <option value="plan">方案</option>
      </select>
      <select v-model="sortOrder" class="filter-select">
        <option value="desc">由新到舊</option>
        <option value="asc">由舊到新</option>
      </select>
    </div>

    <!-- Users Table -->
    <div class="table-container">
      <table class="users-table">
        <thead>
          <tr>
            <th>電子郵件</th>
            <th>姓名</th>
            <th>方案</th>
            <th>推廣碼</th>
            <th>使用次數</th>
            <th>狀態</th>
            <th>加入日期</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in adminStore.users" :key="user.id">
            <td>
              <span class="email">{{ user.email }}</span>
            </td>
            <td>{{ user.name || '-' }}</td>
            <td>
              <div class="plan-cell">
                <span class="plan-badge" :class="planClass(user.plan)">
                  {{ formatPlan(user.plan) }}
                </span>
                <span v-if="user.is_test_account" class="role-badge test-account">測試帳號</span>
              </div>
            </td>
            <td>
              <div class="promotion-cell">
                <span v-if="user.referral_code" class="promo-code">{{ user.referral_code }}</span>
                <span v-else class="muted">尚非推廣帳號</span>
                <span v-if="user.is_promotion_account" class="role-badge">推廣帳號</span>
              </div>
            </td>
            <td>{{ user.referral_count || 0 }}</td>
            <td>
              <span class="status-badge" :class="{ active: user.is_active, inactive: !user.is_active }">
                {{ user.is_active ? '啟用' : '停權' }}
              </span>
            </td>
            <td>{{ formatDate(user.created_at) }}</td>
            <td>
              <div class="actions">
                <button @click="viewUser(user.id)" class="btn-icon" title="查看詳細資料">
                  查看
                </button>
                <button
                  v-if="!user.referral_code"
                  @click="makePromotionAccount(user)"
                  class="btn-icon promoter primary-promoter"
                  :disabled="promotingUserId === user.id"
                  title="設為推廣帳號"
                >
                  {{ promotingUserId === user.id ? '設定中...' : '設為推廣帳號' }}
                </button>
                <button v-else @click="openPromotionModal(user)" class="btn-icon promoter" title="編輯推廣碼">
                  編輯推廣碼
                </button>
                <button
                  @click="grantTestAccount(user)"
                  class="btn-icon tester"
                  :disabled="testingUserId === user.id"
                  :title="user.is_test_account ? '重設 $1 測試方案' : '指派 $1 測試方案'"
                >
                  {{ testingUserId === user.id ? '設定中...' : user.is_test_account ? '重設 $1 測試方案' : '指派 $1 測試方案' }}
                </button>
                <button
                  @click="toggleBan(user.id, user.is_active)"
                  class="btn-icon"
                  :class="{ danger: user.is_active }"
                  :title="user.is_active ? '停權使用者' : '解除停權'"
                >
                  {{ user.is_active ? '停權' : '解除' }}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div class="pagination">
      <button
        @click="loadUsers(adminStore.usersPage - 1)"
        :disabled="adminStore.usersPage <= 1"
        class="page-btn"
      >
        上一頁
      </button>
      <span class="page-info">
        第 {{ adminStore.usersPage }} / {{ Math.ceil(adminStore.usersTotal / 20) }} 頁
      </span>
      <button
        @click="loadUsers(adminStore.usersPage + 1)"
        :disabled="adminStore.usersPage >= Math.ceil(adminStore.usersTotal / 20)"
        class="page-btn"
      >
        下一頁
      </button>
    </div>

    <!-- User Detail Modal -->
    <div v-if="showUserModal" class="modal-overlay" @click.self="showUserModal = false">
      <div class="modal">
        <div class="modal-header">
          <h2>使用者詳細資料</h2>
          <button @click="showUserModal = false" class="close-btn">&times;</button>
        </div>
        <div class="modal-body" v-if="selectedUser">
          <div class="detail-grid">
            <div class="detail-item">
              <label>電子郵件</label>
              <span>{{ selectedUser.email }}</span>
            </div>
            <div class="detail-item">
              <label>姓名</label>
              <span>{{ selectedUser.name || '-' }}</span>
            </div>
            <div class="detail-item">
              <label>方案</label>
              <span class="plan-badge" :class="planClass(selectedUser.plan)">{{ formatPlan(selectedUser.plan) }}</span>
            </div>
            <div class="detail-item">
              <label>測試帳號</label>
              <span>{{ selectedUser.is_test_account ? '已啟用 $1 測試方案' : '否' }}</span>
            </div>
            <div class="detail-item">
              <label>狀態</label>
              <span>
                <span class="status-dot" :class="{ online: selectedUser.is_online }"></span>
                {{ selectedUser.is_online ? '在線' : '離線' }}
              </span>
            </div>
            <div class="detail-item">
              <label>生成次數</label>
              <span>{{ selectedUser.generation_count }}</span>
            </div>
            <div class="detail-item">
              <label>推廣碼</label>
              <span>{{ selectedUser.referral_code || '-' }}</span>
            </div>
            <div class="detail-item">
              <label>推廣使用次數</label>
              <span>{{ selectedUser.referral_count || 0 }}</span>
            </div>
            <div class="detail-item">
              <label>推廣狀態</label>
              <span>{{ selectedUser.is_promotion_account ? '推廣帳號' : '一般使用者' }}</span>
            </div>
          </div>

        </div>
      </div>
    </div>

    <!-- Promoter Assignment Modal -->
    <div v-if="showPromotionModal" class="modal-overlay" @click.self="showPromotionModal = false">
      <div class="modal small">
        <div class="modal-header">
          <h2>設定推廣帳號</h2>
          <button @click="showPromotionModal = false" class="close-btn">&times;</button>
        </div>
        <div class="modal-body" v-if="promotionTarget">
          <p class="modal-copy">
            可自訂推廣碼；若留空，系統會自動產生唯一推廣碼。
          </p>
          <div class="target-user">
            <span>{{ promotionTarget.email }}</span>
            <span class="plan-badge" :class="planClass(promotionTarget.plan)">{{ formatPlan(promotionTarget.plan) }}</span>
          </div>
          <div class="form-group">
            <label>推廣碼</label>
            <input
              v-model="promotionCodeInput"
              type="text"
              class="form-input uppercase"
              placeholder="留空自動產生"
              maxlength="16"
            />
            <p class="form-hint">限 3-16 碼英文字母或數字。</p>
          </div>
          <button @click="submitPromotionCode" class="btn-primary">
            儲存推廣帳號
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-users {
  padding: 2rem;
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

.error-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 1.5rem;
  padding: 0.75rem 1rem;
  border: 1px solid rgba(244,67,54,0.22);
  border-radius: 8px;
  background: rgba(244,67,54,0.1);
  color: #ff8a80;
}

.dismiss-btn {
  background: transparent;
  border: none;
  color: #ff8a80;
  cursor: pointer;
  font-size: 1.25rem;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
  margin: 2rem 0 0;
}

.summary-card {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 1rem;
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 10px;
  background: #141420;
  box-shadow: 0 2px 8px rgba(0,0,0,0.22);
}

.summary-label {
  color: #9494b0;
  font-size: 0.8rem;
  font-weight: 600;
}

.summary-card strong {
  color: #f5f5fa;
  font-size: 1.5rem;
}

.summary-note {
  color: #6b6b8a;
  font-size: 0.78rem;
}

.filters {
  display: flex;
  gap: 1rem;
  margin: 2rem 0;
  flex-wrap: wrap;
}

.search-input {
  flex: 1;
  min-width: 200px;
  padding: 0.75rem 1rem;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 8px;
  font-size: 1rem;
}

.filter-select {
  padding: 0.75rem 1rem;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 8px;
  font-size: 1rem;
  background: #141420;
}

.table-container {
  background: #141420;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  overflow-x: auto;
}

.users-table {
  width: 100%;
  border-collapse: collapse;
}

.users-table th,
.users-table td {
  padding: 1rem;
  text-align: left;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}

.users-table th {
  background: #0f0f17;
  font-weight: 600;
  color: #9494b0;
}

.email {
  font-family: monospace;
}

.promo-code {
  display: inline-flex;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  background: rgba(22,119,255,0.12);
  color: #69b1ff;
  font-family: monospace;
  font-size: 0.8rem;
  font-weight: 700;
}

.promotion-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.plan-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.role-badge {
  padding: 0.2rem 0.45rem;
  border-radius: 999px;
  background: rgba(16,185,129,0.12);
  color: #34d399;
  font-size: 0.7rem;
  font-weight: 700;
}

.role-badge.test-account {
  background: rgba(245,158,11,0.14);
  color: #fbbf24;
}

.muted {
  color: #6b6b8a;
}

.plan-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.plan-badge.demo { background: rgba(255,255,255,0.05); color: #9494b0; }
.plan-badge.free { background: rgba(255,255,255,0.05); color: #9494b0; }
.plan-badge.basic { background: rgba(25,118,210,0.15); color: #1976d2; }
.plan-badge.pro { background: rgba(123,31,162,0.15); color: #7b1fa2; }
.plan-badge.premium { background: rgba(236,72,153,0.15); color: #f472b6; }
.plan-badge.enterprise { background: rgba(245,158,11,0.15); color: #f57c00; }
.plan-badge.test-pro-usd-1 { background: rgba(245,158,11,0.16); color: #fbbf24; }

.status-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
}

.status-badge.active { background: rgba(16,185,129,0.15); color: #388e3c; }
.status-badge.inactive { background: rgba(244,67,54,0.15); color: #d32f2f; }

.actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.btn-icon {
  padding: 0.5rem 0.75rem;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 4px;
  background: #141420;
  cursor: pointer;
  font-size: 0.75rem;
  transition: all 0.2s;
}

.btn-icon:hover {
  background: #0f0f17;
}

.btn-icon:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.btn-icon.danger {
  border-color: #d32f2f;
  color: #d32f2f;
}

.btn-icon.danger:hover {
  background: rgba(244,67,54,0.15);
}

.btn-icon.promoter {
  border-color: rgba(16,185,129,0.35);
  color: #34d399;
}

.btn-icon.promoter:hover {
  background: rgba(16,185,129,0.12);
}

.btn-icon.primary-promoter {
  background: rgba(16,185,129,0.15);
}

.btn-icon.tester {
  border-color: rgba(245,158,11,0.4);
  color: #fbbf24;
}

.btn-icon.tester:hover {
  background: rgba(245,158,11,0.12);
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

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: #141420;
  border-radius: 12px;
  max-width: 600px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
}

.modal.small {
  max-width: 400px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}

.modal-header h2 {
  margin: 0;
  font-size: 1.25rem;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: #9494b0;
}

.modal-body {
  padding: 1.5rem;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
}

.detail-item label {
  display: block;
  font-size: 0.75rem;
  color: #9494b0;
  margin-bottom: 0.25rem;
}

.detail-item span {
  font-weight: 500;
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ccc;
  margin-right: 0.5rem;
}

.status-dot.online {
  background: #4caf50;
}

.modal-copy {
  margin: 0 0 1rem;
  color: #9494b0;
  font-size: 0.9rem;
  line-height: 1.5;
}

.target-user {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 1rem;
  padding: 0.75rem;
  border-radius: 8px;
  background: #0f0f17;
  color: #f5f5fa;
  font-size: 0.85rem;
}

.form-hint {
  margin: 0.4rem 0 0;
  color: #6b6b8a;
  font-size: 0.75rem;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  font-size: 0.875rem;
  margin-bottom: 0.5rem;
  color: #9494b0;
}

.form-input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 8px;
  font-size: 1rem;
  background: #0f0f17;
  color: #f5f5fa;
}

.uppercase {
  text-transform: uppercase;
}

.btn-primary {
  width: 100%;
  padding: 0.75rem;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  cursor: pointer;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
