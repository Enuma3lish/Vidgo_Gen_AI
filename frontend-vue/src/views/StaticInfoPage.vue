<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

const route = useRoute()
const { locale } = useI18n()
const isZh = computed(() => locale.value.startsWith('zh'))

const pages = computed<Record<string, { title: string; body: string[] }>>(() => ({
  about: {
    title: isZh.value ? '關於 VidGo' : 'About VidGo',
    body: isZh.value
      ? ['VidGo 協助電商與內容團隊快速製作商品圖、短影音、去背、試穿與數位人素材。', '平台採用點數與訂閱制，並保存作品紀錄與下載期限，方便團隊追蹤生成結果。']
      : ['VidGo helps ecommerce and content teams create product images, short videos, background removal, try-on, and avatar assets faster.', 'The platform uses credits and subscriptions, with generation history and download retention built in for production workflows.'],
  },
  contact: {
    title: isZh.value ? '聯絡我們' : 'Contact',
    body: isZh.value
      ? ['客服與商務合作請聯絡 support@vidgo.ai。', '付款、發票或企業方案需求，請附上帳戶信箱與訂單編號，方便我們協助查詢。']
      : ['For support and business inquiries, contact support@vidgo.ai.', 'For payments, invoices, or enterprise plans, include your account email and order number so we can help faster.'],
  },
  blog: {
    title: isZh.value ? '資源與更新' : 'Resources',
    body: isZh.value
      ? ['VidGo 正在整理教學、案例與產品更新。', '您也可以先從作品集與工具頁查看最新可用能力。']
      : ['VidGo is preparing tutorials, case studies, and product updates.', 'For now, browse the gallery and tool pages to see the latest available capabilities.'],
  },
  affiliate: {
    title: isZh.value ? '推薦合作' : 'Affiliate',
    body: isZh.value
      ? ['推薦與合作方案可透過客服信箱申請。', '已登入用戶可在儀表板查看自己的推薦連結與分享紀錄。']
      : ['Referral and partnership programs are available through support.', 'Signed-in users can view their referral links and sharing activity from the dashboard.'],
  },
  terms: {
    title: isZh.value ? '服務條款' : 'Terms of Service',
    body: isZh.value
      ? ['使用 VidGo 代表您同意遵守平台使用規範、付款規則與內容政策。', '不得上傳侵權、違法或違反平台政策的素材。']
      : ['By using VidGo, you agree to follow platform usage rules, payment terms, and content policies.', 'Do not upload infringing, illegal, or policy-violating media.'],
  },
  privacy: {
    title: isZh.value ? '隱私權政策' : 'Privacy Policy',
    body: isZh.value
      ? ['VidGo 僅為提供服務、付款、發票、登入安全與客服用途處理必要資料。', '上傳與生成素材會依保留政策保存，逾期後媒體檔案不可下載但紀錄仍可供查詢。']
      : ['VidGo processes necessary data for service delivery, payments, invoices, login security, and support.', 'Uploaded and generated media follows the retention policy; expired media cannot be downloaded, while records remain available for history.'],
  },
  cookies: {
    title: isZh.value ? 'Cookie 政策' : 'Cookie Policy',
    body: isZh.value
      ? ['VidGo 使用必要 Cookie 與本機儲存來維持登入、語言、主題與安全狀態。', '未來若加入分析或行銷 Cookie，將依適用規範提供說明與選項。']
      : ['VidGo uses necessary cookies and local storage for login, language, theme, and security state.', 'If analytics or marketing cookies are added, VidGo will provide notice and controls as required.'],
  },
  refunds: {
    title: isZh.value ? '退款政策' : 'Refund Policy',
    body: isZh.value
      ? ['訂閱退款依平台顯示的退款期限與付款服務商規則處理。', '取消訂閱不會立即歸零已購買或註冊贈送點數；退款時僅撤回與該訂閱對應的訂閱點數。']
      : ['Subscription refunds follow the refund window shown in the platform and the payment provider rules.', 'Cancelling a subscription does not immediately zero purchased or registration bonus credits; refunds revoke only subscription credits tied to that subscription.'],
  },
}))

const page = computed(() => pages.value[String(route.params.slug || 'about')] || pages.value.about)
</script>

<template>
  <main class="min-h-screen px-4 py-24" style="background: var(--bg-primary); color: var(--text-primary);">
    <section class="max-w-3xl mx-auto">
      <h1 class="text-3xl font-bold mb-6">{{ page.title }}</h1>
      <div class="space-y-4 text-base leading-7" style="color: var(--text-secondary);">
        <p v-for="paragraph in page.body" :key="paragraph">{{ paragraph }}</p>
      </div>
    </section>
  </main>
</template>
