<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useAdminStore } from '@/stores/admin'
import { adminApi } from '@/api/admin'
import type { UserDetail } from '@/api/admin'

const adminStore = useAdminStore()

const searchQuery = ref('')
const selectedPlan = ref('')
const sortBy = ref('created_at')
const sortOrder = ref<'asc' | 'desc'>('desc')
const selectedUser = ref<UserDetail | null>(null)
const showUserModal = ref(false)
const showCreditsModal = ref(false)
const creditsAmount = ref(0)
const creditsReason = ref('')

const plans = ['demo', 'basic', 'pro', 'enterprise']

onMounted(() => {
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
  selectedUser.value.recent_transactions = result.recent_transactions
  showUserModal.value = true
}

async function toggleBan(userId: string, isActive: boolean) {
  if (isActive) {
    const reason = prompt('Enter ban reason:')
    if (reason) {
      await adminStore.banUser(userId, reason)
    }
  } else {
    await adminStore.unbanUser(userId)
  }
}

function openCreditsModal(userId: string) {
  selectedUser.value = adminStore.users.find(u => u.id === userId) as any
  creditsAmount.value = 0
  creditsReason.value = ''
  showCreditsModal.value = true
}

async function submitCreditsAdjustment() {
  if (!selectedUser.value || !creditsReason.value) return

  await adminStore.adjustCredits(
    selectedUser.value.id,
    creditsAmount.value,
    creditsReason.value
  )
  showCreditsModal.value = false
  loadUsers(adminStore.usersPage)
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString()
}

function getTotalCredits(user: any): number {
  return (user.subscription_credits || 0) + (user.purchased_credits || 0) + (user.bonus_credits || 0)
}
</script>

<template>
  <div class="admin-users">
    <header class="page-header">
      <h1>User Management</h1>
      <p class="subtitle">Manage platform users</p>
    </header>

    <!-- Filters -->
    <div class="filters">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="Search by email or name..."
        class="search-input"
      />
      <select v-model="selectedPlan" class="filter-select">
        <option value="">All Plans</option>
        <option v-for="plan in plans" :key="plan" :value="plan">
          {{ plan }}
        </option>
      </select>
      <select v-model="sortBy" class="filter-select">
        <option value="created_at">Join Date</option>
        <option value="email">Email</option>
        <option value="plan">Plan</option>
      </select>
      <select v-model="sortOrder" class="filter-select">
        <option value="desc">Descending</option>
        <option value="asc">Ascending</option>
      </select>
    </div>

    <!-- Users Table -->
    <div class="table-container">
      <table class="users-table">
        <thead>
          <tr>
            <th>Email</th>
            <th>Name</th>
            <th>Plan</th>
            <th>Credits</th>
            <th>Status</th>
            <th>Joined</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in adminStore.users" :key="user.id">
            <td>
              <span class="email">{{ user.email }}</span>
            </td>
            <td>{{ user.name || '-' }}</td>
            <td>
              <span class="plan-badge" :class="user.plan">
                {{ user.plan }}
              </span>
            </td>
            <td>{{ getTotalCredits(user) }}</td>
            <td>
              <span class="status-badge" :class="{ active: user.is_active, inactive: !user.is_active }">
                {{ user.is_active ? 'Active' : 'Banned' }}
              </span>
            </td>
            <td>{{ formatDate(user.created_at) }}</td>
            <td>
              <div class="actions">
                <button @click="viewUser(user.id)" class="btn-icon" title="View Details">
                  View
                </button>
                <button @click="openCreditsModal(user.id)" class="btn-icon" title="Adjust Credits">
                  Credits
                </button>
                <button
                  @click="toggleBan(user.id, user.is_active)"
                  class="btn-icon"
                  :class="{ danger: user.is_active }"
                  :title="user.is_active ? 'Ban User' : 'Unban User'"
                >
                  {{ user.is_active ? 'Ban' : 'Unban' }}
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
        Previous
      </button>
      <span class="page-info">
        Page {{ adminStore.usersPage }} of {{ Math.ceil(adminStore.usersTotal / 20) }}
      </span>
      <button
        @click="loadUsers(adminStore.usersPage + 1)"
        :disabled="adminStore.usersPage >= Math.ceil(adminStore.usersTotal / 20)"
        class="page-btn"
      >
        Next
      </button>
    </div>

    <!-- User Detail Modal -->
    <div v-if="showUserModal" class="modal-overlay" @click.self="showUserModal = false">
      <div class="modal">
        <div class="modal-header">
          <h2>User Details</h2>
          <button @click="showUserModal = false" class="close-btn">&times;</button>
        </div>
        <div class="modal-body" v-if="selectedUser">
          <div class="detail-grid">
            <div class="detail-item">
              <label>Email</label>
              <span>{{ selectedUser.email }}</span>
            </div>
            <div class="detail-item">
              <label>Name</label>
              <span>{{ selectedUser.name || '-' }}</span>
            </div>
            <div class="detail-item">
              <label>Plan</label>
              <span class="plan-badge" :class="selectedUser.plan">{{ selectedUser.plan }}</span>
            </div>
            <div class="detail-item">
              <label>Status</label>
              <span>
                <span class="status-dot" :class="{ online: selectedUser.is_online }"></span>
                {{ selectedUser.is_online ? 'Online' : 'Offline' }}
              </span>
            </div>
            <div class="detail-item">
              <label>Total Credits</label>
              <span>{{ getTotalCredits(selectedUser) }}</span>
            </div>
            <div class="detail-item">
              <label>Generations</label>
              <span>{{ selectedUser.generation_count }}</span>
            </div>
          </div>

          <h3>Credit Breakdown</h3>
          <div class="credits-breakdown">
            <div class="credit-type">
              <span>Subscription</span>
              <strong>{{ selectedUser.subscription_credits }}</strong>
            </div>
            <div class="credit-type">
              <span>Purchased</span>
              <strong>{{ selectedUser.purchased_credits }}</strong>
            </div>
            <div class="credit-type">
              <span>Bonus</span>
              <strong>{{ selectedUser.bonus_credits }}</strong>
            </div>
          </div>

          <h3>Recent Transactions</h3>
          <div class="transactions-list">
            <div
              v-for="tx in selectedUser.recent_transactions"
              :key="tx.id"
              class="transaction-item"
            >
              <span class="tx-amount" :class="{ positive: tx.amount > 0, negative: tx.amount < 0 }">
                {{ tx.amount > 0 ? '+' : '' }}{{ tx.amount }}
              </span>
              <span class="tx-desc">{{ tx.description }}</span>
              <span class="tx-date">{{ formatDate(tx.created_at) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Credits Adjustment Modal -->
    <div v-if="showCreditsModal" class="modal-overlay" @click.self="showCreditsModal = false">
      <div class="modal small">
        <div class="modal-header">
          <h2>Adjust Credits</h2>
          <button @click="showCreditsModal = false" class="close-btn">&times;</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>Amount (positive to add, negative to deduct)</label>
            <input v-model.number="creditsAmount" type="number" class="form-input" />
          </div>
          <div class="form-group">
            <label>Reason</label>
            <input v-model="creditsReason" type="text" class="form-input" placeholder="Enter reason..." />
          </div>
          <button @click="submitCreditsAdjustment" class="btn-primary" :disabled="!creditsReason">
            Submit
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
  flex-wrap: wrap;
}

.search-input {
  flex: 1;
  min-width: 200px;
  padding: 0.75rem 1rem;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 1rem;
}

.filter-select {
  padding: 0.75rem 1rem;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 1rem;
  background: white;
}

.table-container {
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
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
  border-bottom: 1px solid #f0f0f0;
}

.users-table th {
  background: #f9fafb;
  font-weight: 600;
  color: #666;
}

.email {
  font-family: monospace;
}

.plan-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.plan-badge.demo { background: #f0f0f0; color: #666; }
.plan-badge.basic { background: #e3f2fd; color: #1976d2; }
.plan-badge.pro { background: #f3e5f5; color: #7b1fa2; }
.plan-badge.enterprise { background: #fff3e0; color: #f57c00; }

.status-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
}

.status-badge.active { background: #e8f5e9; color: #388e3c; }
.status-badge.inactive { background: #ffebee; color: #d32f2f; }

.actions {
  display: flex;
  gap: 0.5rem;
}

.btn-icon {
  padding: 0.5rem 0.75rem;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  font-size: 0.75rem;
  transition: all 0.2s;
}

.btn-icon:hover {
  background: #f5f5f5;
}

.btn-icon.danger {
  border-color: #d32f2f;
  color: #d32f2f;
}

.btn-icon.danger:hover {
  background: #ffebee;
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

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: white;
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
  border-bottom: 1px solid #f0f0f0;
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
  color: #666;
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
  color: #666;
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

.modal-body h3 {
  font-size: 1rem;
  margin: 1.5rem 0 1rem;
  color: #666;
}

.credits-breakdown {
  display: flex;
  gap: 1rem;
}

.credit-type {
  flex: 1;
  background: #f5f5f5;
  padding: 1rem;
  border-radius: 8px;
  text-align: center;
}

.credit-type span {
  display: block;
  font-size: 0.75rem;
  color: #666;
}

.credit-type strong {
  font-size: 1.25rem;
}

.transactions-list {
  max-height: 200px;
  overflow-y: auto;
}

.transaction-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 0;
  border-bottom: 1px solid #f0f0f0;
}

.tx-amount {
  font-weight: 600;
  min-width: 60px;
}

.tx-amount.positive { color: #388e3c; }
.tx-amount.negative { color: #d32f2f; }

.tx-desc {
  flex: 1;
  font-size: 0.875rem;
  color: #666;
}

.tx-date {
  font-size: 0.75rem;
  color: #999;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  font-size: 0.875rem;
  margin-bottom: 0.5rem;
  color: #666;
}

.form-input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 1rem;
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
