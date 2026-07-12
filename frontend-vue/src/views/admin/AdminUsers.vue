<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAdminStore } from '@/stores/admin'
import { adminApi } from '@/api/admin'
import type { AdminUser, UserDetail } from '@/api/admin'

const adminStore = useAdminStore()
const { locale } = useI18n()

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
const extendingUserId = ref<string | null>(null)
const revokingUserId = ref<string | null>(null)

// Admin Grant Credits modal (2026-05-23). Wired to the long-standing
// POST /api/v1/admin/users/{user_id}/credits backend endpoint, which lands
// the amount in bonus_credits (never expires) and logs a CreditTransaction
// with transaction_type='admin_adjustment'. Negative amounts deduct.
const showGrantCreditsModal = ref(false)
const grantCreditsTarget = ref<AdminUser | null>(null)
const grantCreditsAmount = ref<number>(100)
const grantCreditsReason = ref<string>('')
const grantingCreditsUserId = ref<string | null>(null)
const reprovisioningUserId = ref<string | null>(null)

const plans = ['demo', 'basic', 'pro', 'premium', 'enterprise', 'test_pro_usd_1']

const registeredUsersTotal = computed(() => adminStore.dashboardStats?.users?.total ?? adminStore.usersTotal)
const filteredUsersTotal = computed(() => adminStore.usersTotal)
const paidUsersTotal = computed(() => adminStore.dashboardStats?.paid_stats?.paid ?? 0)
const freeUsersTotal = computed(() => adminStore.dashboardStats?.paid_stats?.free ?? 0)
const isZh = computed(() => locale.value === 'zh-TW')

function localized(zh: string, en: string): string {
  return isZh.value ? zh : en
}

onMounted(() => {
  adminStore.fetchDashboardStats()
  loadUsers()
})

// Debounce the free-text search so we don't fire a request per keystroke
// (2026-07-12 perf audit); dropdowns switch immediately. Mirrors the
// AdminPromotions pattern.
let searchTimer: ReturnType<typeof setTimeout> | null = null
watch(searchQuery, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => loadUsers(), 250)
})
watch([selectedPlan, sortBy, sortOrder], () => {
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
    const reason = prompt(localized('請輸入停權原因：', 'Please enter a suspension reason:'))
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

function openGrantCreditsModal(user: AdminUser) {
  grantCreditsTarget.value = user
  grantCreditsAmount.value = 100
  grantCreditsReason.value = ''
  showGrantCreditsModal.value = true
}

async function submitGrantCredits() {
  const target = grantCreditsTarget.value
  if (!target) return
  const amount = Number(grantCreditsAmount.value)
  if (!Number.isFinite(amount) || amount === 0) {
    alert(localized('請輸入非零點數', 'Please enter a non-zero amount'))
    return
  }
  if (!grantCreditsReason.value.trim()) {
    alert(localized('請輸入調整原因（會記錄於審計表）', 'Please enter a reason (recorded in the audit log)'))
    return
  }
  grantingCreditsUserId.value = target.id
  try {
    await adminStore.adjustCredits(target.id, Math.round(amount), grantCreditsReason.value.trim())
    showGrantCreditsModal.value = false
    grantCreditsTarget.value = null
    await loadUsers(adminStore.usersPage)
  } catch (err: any) {
    alert(err?.response?.data?.detail || err?.message || localized('調整失敗', 'Adjustment failed'))
  } finally {
    grantingCreditsUserId.value = null
  }
}

async function grantTestAccount(user: AdminUser) {
  if (testingUserId.value) return
  const actionLabel = user.is_test_account
    ? localized('重設 $1 測試方案', 'Reset $1 test plan')
    : localized('指派 $1 測試方案', 'Assign $1 test plan')
  if (!confirm(localized(
    `${actionLabel}？\n${user.email}\n\n此使用者將以 $1 USD / 月使用 Pro 全功能。`,
    `${actionLabel}?\n${user.email}\n\nThis user will receive full Pro access for $1 USD per month.`
  ))) return

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

async function revokeTestSubscription(user: AdminUser) {
  if (revokingUserId.value) return
  if (!confirm(localized(
    `結束 ${user.email} 的 $1 試用方案?\n\n` +
    '會做的事:\n' +
    '• 取消當前訂閱(end_date=now)\n' +
    '• 移除使用者方案(回到一般帳號)\n' +
    '• 清空試用點數(購買/獎勵點數不受影響)\n' +
    '• 該使用者不會再看到 $1 方案',
    `Revoke ${user.email}'s $1 test subscription?\n\n` +
    'This will:\n' +
    '• Cancel the active subscription (end_date=now)\n' +
    '• Clear the plan (revert to normal account)\n' +
    '• Zero the test credits (purchased/bonus credits untouched)\n' +
    '• Hide the $1 plan from this user\'s pricing view',
  ))) return

  const reason = prompt(
    localized('原因(選填,會寫入審計):', 'Reason (optional, written to audit):'),
    '',
  ) || undefined

  revokingUserId.value = user.id
  try {
    const result = await adminStore.revokeTestSubscription(user.id, true, reason)
    if (result) {
      alert(localized(
        `已結束。取消 ${result.subscriptions_cancelled} 個訂閱、清掉 ${result.previous_credits} 點。`,
        `Revoked. ${result.subscriptions_cancelled} subscription(s) cancelled, ${result.previous_credits} credits cleared.`,
      ))
      await loadUsers(adminStore.usersPage)
    }
  } finally {
    revokingUserId.value = null
  }
}

async function extendTestSubscription(user: AdminUser) {
  if (extendingUserId.value) return
  const raw = prompt(
    localized(
      `延長 $1 試用方案 — ${user.email}\n\n要延長幾天？(1-365,預設 30)`,
      `Extend $1 test plan — ${user.email}\n\nHow many days to add? (1-365, default 30)`
    ),
    '30',
  )
  if (raw === null) return
  const days = parseInt(raw.trim() || '30', 10)
  if (!Number.isFinite(days) || days < 1 || days > 365) {
    alert(localized('天數必須是 1-365 之間的整數', 'Days must be an integer between 1 and 365'))
    return
  }
  if (!confirm(localized(
    `延長 ${days} 天且不收費？\n會把當前的訂閱期推後並重置 100 點測試額度。`,
    `Extend ${days} days at no charge?\nThis pushes back the current end date and refills 100 test credits.`,
  ))) return
  extendingUserId.value = user.id
  try {
    const result = await adminStore.extendTestSubscription(user.id, days, true)
    if (result) {
      alert(localized(
        `已延長至 ${new Date(result.new_end_date).toLocaleDateString(locale.value)}`,
        `Extended through ${new Date(result.new_end_date).toLocaleDateString(locale.value)}`,
      ))
      await loadUsers(adminStore.usersPage)
    }
  } finally {
    extendingUserId.value = null
  }
}

async function reprovisionSubscription(user: AdminUser) {
  if (reprovisioningUserId.value) return
  if (!confirm(localized(
    `重新開通 ${user.email} 的訂閱？\n\n用於「已付款但方案／點數未開通」（例如 PayPal webhook 失敗）。會以最近一筆未完成的訂閱訂單重跑開通流程，可安全重複執行。`,
    `Re-provision ${user.email}'s subscription?\n\nFor "paid but plan/credits never granted" (e.g. a failed PayPal webhook). Re-runs provisioning on their most recent unpaid subscription order. Safe to run more than once.`,
  ))) return
  reprovisioningUserId.value = user.id
  try {
    const result = await adminApi.reprovisionSubscription(user.id)
    if (result.provisioned) {
      alert(localized(
        `已開通：方案 ${result.plan}，訂閱點數 ${result.subscription_credits}。`,
        `Provisioned: plan ${result.plan}, ${result.subscription_credits} subscription credits.`,
      ))
    } else {
      alert(localized(
        `已處理訂單 ${result.order_number}，但未設定方案（可能缺少 subscription 紀錄）。`,
        `Processed order ${result.order_number}, but no plan was set (subscription row may be missing).`,
      ))
    }
    await loadUsers(adminStore.usersPage)
  } catch (err: any) {
    alert(err?.response?.data?.detail || err?.message || localized('重新開通失敗', 'Re-provision failed'))
  } finally {
    reprovisioningUserId.value = null
  }
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString(locale.value)
}

// Total remaining credits = subscription (resets each cycle) + purchased
// (top-ups) + bonus (never-expiring admin/referral grants). Mirrors how the
// backend spends them, so this is the real balance the user can still use.
function totalCredits(u: { subscription_credits?: number; purchased_credits?: number; bonus_credits?: number }): number {
  return (u.subscription_credits || 0) + (u.purchased_credits || 0) + (u.bonus_credits || 0)
}

function formatCredits(n: number): string {
  return new Intl.NumberFormat(locale.value).format(n)
}

function creditsTooltip(u: AdminUser): string {
  return localized(
    `訂閱點數 ${formatCredits(u.subscription_credits || 0)} ／ 購買點數 ${formatCredits(u.purchased_credits || 0)} ／ 獎勵點數 ${formatCredits(u.bonus_credits || 0)}`,
    `Subscription ${formatCredits(u.subscription_credits || 0)} / Purchased ${formatCredits(u.purchased_credits || 0)} / Bonus ${formatCredits(u.bonus_credits || 0)}`,
  )
}

function formatPlan(plan?: string | null): string {
  return (plan || 'demo').replace(/_/g, ' ')
}

function planClass(plan?: string | null): string {
  return (plan || 'demo').toLowerCase().replace(/[^a-z0-9_-]/g, '-')
}

function testAccountActionLabel(user: AdminUser): string {
  return user.is_test_account
    ? localized('重設 $1 測試方案', 'Reset $1 test plan')
    : localized('指派 $1 測試方案', 'Assign $1 test plan')
}

function activeLabel(isActive: boolean): string {
  return isActive ? localized('啟用', 'Active') : localized('停權', 'Suspended')
}
</script>

<template>
  <div class="admin-users">
    <header class="page-header">
      <h1>{{ localized('使用者管理', 'User Management') }}</h1>
      <p class="subtitle">{{ localized('管理會員方案、帳號狀態與推廣帳號', 'Manage plans, account status, and promotion accounts') }}</p>
    </header>

    <div v-if="adminStore.error" class="error-banner">
      <span>{{ adminStore.error }}</span>
      <button @click="adminStore.error = null" class="dismiss-btn">&times;</button>
    </div>

    <div class="summary-grid">
      <div class="summary-card">
        <span class="summary-label">{{ localized('註冊使用者', 'Registered Users') }}</span>
        <strong>{{ registeredUsersTotal }}</strong>
        <span class="summary-note">{{ localized(`目前篩選符合 ${filteredUsersTotal} 位`, `${filteredUsersTotal} users match the current filters`) }}</span>
      </div>
      <div class="summary-card">
        <span class="summary-label">{{ localized('付費 / 免費', 'Paid / Free') }}</span>
        <strong>{{ paidUsersTotal }} / {{ freeUsersTotal }}</strong>
        <span class="summary-note">{{ localized('依目前方案統計', 'Calculated from current plans') }}</span>
      </div>
      <div class="summary-card">
        <span class="summary-label">{{ localized('推廣帳號', 'Promotion Accounts') }}</span>
        <strong>{{ adminStore.promotionAccounts }}</strong>
        <span class="summary-note">{{ localized(`帶來 ${adminStore.promotionRegistrations} 位註冊`, `${adminStore.promotionRegistrations} referred registrations`) }}</span>
      </div>
    </div>

    <!-- Filters -->
    <div class="filters">
      <input
        v-model="searchQuery"
        type="text"
        :placeholder="localized('搜尋電子郵件或姓名...', 'Search email or name...')"
        class="search-input"
      />
      <select v-model="selectedPlan" class="filter-select">
        <option value="">{{ localized('全部方案', 'All Plans') }}</option>
        <option v-for="plan in plans" :key="plan" :value="plan">
          {{ plan }}
        </option>
      </select>
      <select v-model="sortBy" class="filter-select">
        <option value="created_at">{{ localized('註冊日期', 'Join Date') }}</option>
        <option value="email">Email</option>
        <option value="plan">{{ localized('方案', 'Plan') }}</option>
        <option value="subscription_credits">{{ localized('訂閱點數', 'Subscription Credits') }}</option>
      </select>
      <select v-model="sortOrder" class="filter-select">
        <option value="desc">{{ localized('由新到舊', 'Newest First') }}</option>
        <option value="asc">{{ localized('由舊到新', 'Oldest First') }}</option>
      </select>
    </div>

    <!-- Users Table -->
    <div class="table-container">
      <table class="users-table">
        <thead>
          <tr>
            <th>{{ localized('電子郵件', 'Email') }}</th>
            <th>{{ localized('姓名', 'Name') }}</th>
            <th>{{ localized('方案', 'Plan') }}</th>
            <th>{{ localized('推廣碼', 'Promotion Code') }}</th>
            <th>{{ localized('使用次數', 'Uses') }}</th>
            <th>{{ localized('剩餘點數', 'Remaining Credits') }}</th>
            <th>{{ localized('狀態', 'Status') }}</th>
            <th>{{ localized('加入日期', 'Joined') }}</th>
            <th>{{ localized('操作', 'Actions') }}</th>
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
                <span v-if="user.is_test_account" class="role-badge test-account">{{ localized('測試帳號', 'Test Account') }}</span>
              </div>
            </td>
            <td>
              <div class="promotion-cell">
                <span v-if="user.referral_code" class="promo-code">{{ user.referral_code }}</span>
                <span v-else class="muted">{{ localized('尚非推廣帳號', 'Not a promoter yet') }}</span>
                <span v-if="user.is_promotion_account" class="role-badge">{{ localized('推廣帳號', 'Promoter') }}</span>
              </div>
            </td>
            <td>{{ user.referral_count || 0 }}</td>
            <td>
              <div class="credits-cell" :title="creditsTooltip(user)">
                <span class="credits-total">{{ formatCredits(totalCredits(user)) }}</span>
                <span class="credits-breakdown">
                  {{ localized('訂閱', 'Sub') }} {{ formatCredits(user.subscription_credits || 0) }}
                  · {{ localized('購買', 'Buy') }} {{ formatCredits(user.purchased_credits || 0) }}
                  · {{ localized('獎勵', 'Bonus') }} {{ formatCredits(user.bonus_credits || 0) }}
                </span>
              </div>
            </td>
            <td>
              <span class="status-badge" :class="{ active: user.is_active, inactive: !user.is_active }">
                {{ activeLabel(user.is_active) }}
              </span>
            </td>
            <td>{{ formatDate(user.created_at) }}</td>
            <td>
              <div class="actions">
                <button @click="viewUser(user.id)" class="btn-icon" :title="localized('查看詳細資料', 'View details')">
                  {{ localized('查看', 'View') }}
                </button>
                <button
                  v-if="!user.referral_code"
                  @click="makePromotionAccount(user)"
                  class="btn-icon promoter primary-promoter"
                  :disabled="promotingUserId === user.id"
                  :title="localized('設為推廣帳號', 'Set as promoter')"
                >
                  {{ promotingUserId === user.id ? localized('設定中...', 'Setting...') : localized('設為推廣帳號', 'Set Promoter') }}
                </button>
                <button v-else @click="openPromotionModal(user)" class="btn-icon promoter" :title="localized('編輯推廣碼', 'Edit promotion code')">
                  {{ localized('編輯推廣碼', 'Edit Code') }}
                </button>
                <button
                  @click="grantTestAccount(user)"
                  class="btn-icon tester"
                  :disabled="testingUserId === user.id"
                  :title="testAccountActionLabel(user)"
                >
                  {{ testingUserId === user.id ? localized('設定中...', 'Setting...') : testAccountActionLabel(user) }}
                </button>
                <button
                  v-if="user.is_test_account"
                  @click="extendTestSubscription(user)"
                  class="btn-icon tester-extend"
                  :disabled="extendingUserId === user.id"
                  :title="localized('延長 $1 試用週期（無需付款）', 'Extend $1 test plan (no payment)')"
                >
                  {{ extendingUserId === user.id ? localized('延長中…', 'Extending…') : localized('延長 $1 試用', 'Extend $1 Test') }}
                </button>
                <button
                  v-if="user.is_test_account"
                  @click="revokeTestSubscription(user)"
                  class="btn-icon tester-revoke"
                  :disabled="revokingUserId === user.id"
                  :title="localized('結束 $1 試用 — 回到一般帳號', 'End $1 test plan — revert to normal user')"
                >
                  {{ revokingUserId === user.id ? localized('結束中…', 'Revoking…') : localized('結束 $1 試用', 'End $1 Test') }}
                </button>
                <button
                  @click="openGrantCreditsModal(user)"
                  class="btn-icon grant-credits"
                  :disabled="grantingCreditsUserId === user.id"
                  :title="localized('贈送 / 調整點數', 'Grant / adjust credits')"
                >
                  {{ grantingCreditsUserId === user.id ? localized('調整中…', 'Adjusting…') : localized('贈點', 'Grant Credits') }}
                </button>
                <button
                  @click="reprovisionSubscription(user)"
                  class="btn-icon reprovision"
                  :disabled="reprovisioningUserId === user.id"
                  :title="localized('已付款但未開通方案時，重新開通訂閱', 'Re-provision subscription (paid but plan not granted)')"
                >
                  {{ reprovisioningUserId === user.id ? localized('開通中…', 'Provisioning…') : localized('重新開通', 'Re-provision') }}
                </button>
                <button
                  @click="toggleBan(user.id, user.is_active)"
                  class="btn-icon"
                  :class="{ danger: user.is_active }"
                  :title="user.is_active ? localized('停權使用者', 'Suspend user') : localized('解除停權', 'Unsuspend user')"
                >
                  {{ user.is_active ? localized('停權', 'Suspend') : localized('解除', 'Restore') }}
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
        {{ localized('上一頁', 'Previous') }}
      </button>
      <span class="page-info">
        {{ localized(`第 ${adminStore.usersPage} / ${Math.ceil(adminStore.usersTotal / 20)} 頁`, `Page ${adminStore.usersPage} / ${Math.ceil(adminStore.usersTotal / 20)}`) }}
      </span>
      <button
        @click="loadUsers(adminStore.usersPage + 1)"
        :disabled="adminStore.usersPage >= Math.ceil(adminStore.usersTotal / 20)"
        class="page-btn"
      >
        {{ localized('下一頁', 'Next') }}
      </button>
    </div>

    <!-- User Detail Modal -->
    <div v-if="showUserModal" class="modal-overlay" @click.self="showUserModal = false">
      <div class="modal">
        <div class="modal-header">
          <h2>{{ localized('使用者詳細資料', 'User Details') }}</h2>
          <button @click="showUserModal = false" class="close-btn">&times;</button>
        </div>
        <div class="modal-body" v-if="selectedUser">
          <div class="detail-grid">
            <div class="detail-item">
              <label>{{ localized('電子郵件', 'Email') }}</label>
              <span>{{ selectedUser.email }}</span>
            </div>
            <div class="detail-item">
              <label>{{ localized('姓名', 'Name') }}</label>
              <span>{{ selectedUser.name || '-' }}</span>
            </div>
            <div class="detail-item">
              <label>{{ localized('方案', 'Plan') }}</label>
              <span class="plan-badge" :class="planClass(selectedUser.plan)">{{ formatPlan(selectedUser.plan) }}</span>
            </div>
            <div class="detail-item">
              <label>{{ localized('測試帳號', 'Test Account') }}</label>
              <span>{{ selectedUser.is_test_account ? localized('已啟用 $1 測試方案', '$1 test plan enabled') : localized('否', 'No') }}</span>
            </div>
            <div class="detail-item">
              <label>{{ localized('狀態', 'Status') }}</label>
              <span>
                <span class="status-dot" :class="{ online: selectedUser.is_online }"></span>
                {{ selectedUser.is_online ? localized('在線', 'Online') : localized('離線', 'Offline') }}
              </span>
            </div>
            <div class="detail-item">
              <label>{{ localized('生成次數', 'Generations') }}</label>
              <span>{{ selectedUser.generation_count }}</span>
            </div>
            <div class="detail-item credits-detail">
              <label>{{ localized('剩餘點數', 'Remaining Credits') }}</label>
              <span>
                <strong>{{ formatCredits(totalCredits(selectedUser)) }}</strong>
                <span class="credits-breakdown">
                  {{ localized('訂閱', 'Sub') }} {{ formatCredits(selectedUser.subscription_credits || 0) }}
                  · {{ localized('購買', 'Buy') }} {{ formatCredits(selectedUser.purchased_credits || 0) }}
                  · {{ localized('獎勵', 'Bonus') }} {{ formatCredits(selectedUser.bonus_credits || 0) }}
                </span>
              </span>
            </div>
            <div class="detail-item">
              <label>{{ localized('推廣碼', 'Promotion Code') }}</label>
              <span>{{ selectedUser.referral_code || '-' }}</span>
            </div>
            <div class="detail-item">
              <label>{{ localized('推廣使用次數', 'Promotion Uses') }}</label>
              <span>{{ selectedUser.referral_count || 0 }}</span>
            </div>
            <div class="detail-item">
              <label>{{ localized('推廣狀態', 'Promotion Status') }}</label>
              <span>{{ selectedUser.is_promotion_account ? localized('推廣帳號', 'Promoter') : localized('一般使用者', 'Regular User') }}</span>
            </div>
          </div>

        </div>
      </div>
    </div>

    <!-- Promoter Assignment Modal -->
    <div v-if="showPromotionModal" class="modal-overlay" @click.self="showPromotionModal = false">
      <div class="modal small">
        <div class="modal-header">
          <h2>{{ localized('設定推廣帳號', 'Set Promotion Account') }}</h2>
          <button @click="showPromotionModal = false" class="close-btn">&times;</button>
        </div>
        <div class="modal-body" v-if="promotionTarget">
          <p class="modal-copy">
            {{ localized('可自訂推廣碼；若留空，系統會自動產生唯一推廣碼。', 'Customize a promotion code, or leave it blank to generate a unique one automatically.') }}
          </p>
          <div class="target-user">
            <span>{{ promotionTarget.email }}</span>
            <span class="plan-badge" :class="planClass(promotionTarget.plan)">{{ formatPlan(promotionTarget.plan) }}</span>
          </div>
          <div class="form-group">
            <label>{{ localized('推廣碼', 'Promotion Code') }}</label>
            <input
              v-model="promotionCodeInput"
              type="text"
              class="form-input uppercase"
              :placeholder="localized('留空自動產生', 'Leave blank to auto-generate')"
              maxlength="16"
            />
            <p class="form-hint">{{ localized('限 3-16 碼英文字母或數字。', 'Use 3-16 letters or numbers.') }}</p>
          </div>
          <button @click="submitPromotionCode" class="btn-primary">
            {{ localized('儲存推廣帳號', 'Save Promotion Account') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Grant / Adjust Credits modal (added 2026-05-23) -->
    <div v-if="showGrantCreditsModal" class="modal-overlay" @click.self="showGrantCreditsModal = false">
      <div class="modal small">
        <div class="modal-header">
          <h2>{{ localized('贈送 / 調整點數', 'Grant / Adjust Credits') }}</h2>
          <button @click="showGrantCreditsModal = false" class="close-btn">&times;</button>
        </div>
        <div class="modal-body" v-if="grantCreditsTarget">
          <p class="modal-copy">
            {{ localized(
              '正數為贈送、負數為扣除。贈送點數會落在「永不過期」的 bonus 餘額；扣除時優先扣 bonus、再扣訂閱點數。每筆都會記錄在 CreditTransaction 審計表。',
              'Positive = grant, negative = deduct. Grants land in the never-expiring bonus balance; deductions hit bonus first then subscription. Every adjustment is logged in the CreditTransaction audit table.'
            ) }}
          </p>
          <div class="target-user">
            <span>{{ grantCreditsTarget.email }}</span>
            <span class="plan-badge" :class="planClass(grantCreditsTarget.plan)">{{ formatPlan(grantCreditsTarget.plan) }}</span>
          </div>
          <div class="form-group">
            <label>{{ localized('點數', 'Amount') }}</label>
            <input
              v-model.number="grantCreditsAmount"
              type="number"
              step="1"
              class="form-input"
              :placeholder="localized('正數贈送，負數扣除', 'positive grants, negative deducts')"
            />
            <p class="form-hint">
              {{ localized(
                '例：100 = 贈 100 點；-50 = 扣 50 點',
                'e.g. 100 grants 100 credits; -50 deducts 50 credits'
              ) }}
            </p>
          </div>
          <div class="form-group">
            <label>{{ localized('原因（必填）', 'Reason (required)') }}</label>
            <input
              v-model="grantCreditsReason"
              type="text"
              class="form-input"
              :placeholder="localized('例：客戶補償 / 活動贈點 / 客服處理', 'e.g. customer comp / campaign grant / support ticket #')"
              maxlength="200"
            />
            <p class="form-hint">
              {{ localized('會寫入 CreditTransaction.description，方便日後對帳。', 'Written to CreditTransaction.description for audit.') }}
            </p>
          </div>
          <button
            @click="submitGrantCredits"
            class="btn-primary"
            :disabled="grantingCreditsUserId === grantCreditsTarget.id"
          >
            {{ grantingCreditsUserId === grantCreditsTarget.id
                ? localized('調整中…', 'Adjusting…')
                : localized('確認調整', 'Confirm Adjustment') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-users {
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

.credits-cell {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  white-space: nowrap;
}

.credits-total {
  font-weight: 700;
  color: #f5f5fa;
  font-variant-numeric: tabular-nums;
}

.credits-breakdown {
  font-size: 0.7rem;
  color: #6b6b8a;
}

.credits-detail strong {
  display: inline-block;
  margin-right: 0.5rem;
  font-size: 1.1rem;
  color: #34d399;
}

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

.btn-icon.tester-extend {
  border-color: rgba(245,158,11,0.4);
  color: #fcd34d;
  background: rgba(245,158,11,0.06);
}

.btn-icon.tester-extend:hover {
  background: rgba(245,158,11,0.18);
}

.btn-icon.tester-revoke {
  border-color: rgba(239,68,68,0.45);
  color: #f87171;
}

.btn-icon.tester-revoke:hover {
  background: rgba(239,68,68,0.12);
}

.btn-icon.grant-credits {
  border-color: rgba(16,185,129,0.45);
  color: #34d399;
}

.btn-icon.grant-credits:hover {
  background: rgba(16,185,129,0.12);
}

.btn-icon.reprovision {
  border-color: rgba(99,102,241,0.5);
  color: #a5b4fc;
}

.btn-icon.reprovision:hover {
  background: rgba(99,102,241,0.14);
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
