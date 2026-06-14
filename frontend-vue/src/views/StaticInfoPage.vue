<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useLocalized } from '@/composables'

const route = useRoute()
const { locale } = useI18n()
const isZh = computed(() => locale.value.startsWith('zh'))
// 5-language inline picker — fixes ja/ko/es fall-through (BUG-017).
const { L } = useLocalized()

// PayPal (and other PSP) compliance: Terms / Privacy / Refund pages must contain
// substantive, business-identifying content. Each page below covers the topics
// PSP reviewers verify (legal entity, services, billing, cancellation, refund
// window, data handling, contact, governing law).

const COMPANY_NAME = 'VidGo (Enuma3lish)'
const CONTACT_EMAIL = 'support@vidgo.ai'
const SITE_URL = 'https://vidgo.co'
const LAST_UPDATED = '2026-05-07'

const pages = computed<Record<string, { title: string; body: string[] }>>(() => ({
  about: {
    title: L('關於 VidGo', 'About VidGo', 'VidGoについて', 'VidGo 소개', 'Acerca de VidGo'),
    body: isZh.value
      ? [
          'VidGo 協助電商與內容團隊快速製作商品圖、短影音、去背、試穿、室內設計與數位人素材。',
          '平台採點數與訂閱制，並保存作品紀錄與下載期限，方便團隊追蹤生成結果。',
          `聯絡信箱：${CONTACT_EMAIL}　|　網站：${SITE_URL}`,
        ]
      : [
          'VidGo helps ecommerce and content teams create product images, short videos, background removal, try-on, room redesign, and avatar assets faster.',
          'The platform uses credits and subscriptions, with generation history and download retention built in for production workflows.',
          `Contact: ${CONTACT_EMAIL}　|　Website: ${SITE_URL}`,
        ],
  },
  contact: {
    title: L('聯絡我們', 'Contact', 'お問い合わせ', '문의', 'Contacto'),
    body: isZh.value
      ? [
          `客服與商務合作請聯絡 ${CONTACT_EMAIL}。`,
          '付款、發票或企業方案需求，請附上帳戶信箱與訂單編號，方便我們協助查詢。',
          '我們通常於 1–2 個工作天內回覆。',
        ]
      : [
          `For support and business inquiries, contact ${CONTACT_EMAIL}.`,
          'For payments, invoices, or enterprise plans, include your account email and order number so we can help faster.',
          'We typically respond within 1–2 business days.',
        ],
  },
  blog: {
    title: L('資源與更新', 'Resources', 'リソースと更新', '리소스 및 업데이트', 'Recursos y novedades'),
    body: isZh.value
      ? ['VidGo 正在整理教學、案例與產品更新。', '您也可以先從作品集與工具頁查看最新可用能力。']
      : ['VidGo is preparing tutorials, case studies, and product updates.', 'For now, browse the gallery and tool pages to see the latest available capabilities.'],
  },
  affiliate: {
    title: L('推薦合作', 'Affiliate', 'アフィリエイト', '제휴 마케팅', 'Afiliados'),
    body: isZh.value
      ? ['推薦與合作方案可透過客服信箱申請。', '已登入用戶可在儀表板查看自己的推薦連結與分享紀錄。']
      : ['Referral and partnership programs are available through support.', 'Signed-in users can view their referral links and sharing activity from the dashboard.'],
  },
  terms: {
    title: L('服務條款', 'Terms of Service', '利用規約', '서비스 약관', 'Términos del servicio'),
    body: isZh.value
      ? [
          `最後更新：${LAST_UPDATED}`,
          `1. 服務提供者。本服務由 ${COMPANY_NAME}（以下稱「VidGo」）營運，網址為 ${SITE_URL}。聯絡信箱：${CONTACT_EMAIL}。`,
          '2. 服務內容。VidGo 提供 AI 影像與影片生成工具，包含智能去背、AI 商品情境攝影棚、AI 模特換裝、室內設計渲染、商品動態短影音、AI 數位人、圖案生成等。所有生成結果均依當下可用之第三方模型能力供應，不保證特定藝術或商業效果。',
          '3. 註冊與帳號。使用者須提供有效電子郵件並妥善保管帳號密碼，所有透過該帳號之操作均視為使用者本人行為。禁止共享帳號或將帳號用於違反本條款之用途。',
          '4. 訂閱與付款。付費方案以儀表板顯示為準，由第三方付款服務商（包含但不限於 PayPal、ECPay）處理金流並開立收據與發票。訂閱於每個計費週期自動續訂，使用者可隨時於帳號設定中取消，避免下次扣款。',
          '5. 點數與生成額度。每個方案附帶之點數依當期方案規則發放。註冊贈送點數、購買點數、訂閱點數計算方式詳見儀表板說明；訂閱取消或退款時，僅撤回與該訂閱對應的訂閱點數，已購買或贈送點數不受影響。',
          '6. 內容規範。使用者不得上傳或要求生成下列內容：（a）侵犯第三方智慧財產權之素材；（b）含未成年人之色情內容；（c）煽動暴力、仇恨或非法行為之內容；（d）冒充他人或未經授權使用真實人物肖像之內容；（e）違反當地法律之任何內容。VidGo 保留移除違規內容並終止帳號之權利。',
          '7. 智慧財產權。VidGo 平台、UI、文件與品牌標識為 VidGo 所有。使用者對其上傳之原始素材保有權利；對於透過 VidGo 生成的結果，付費訂閱者可商業使用，免費示範用戶之輸出僅供個人預覽且帶有浮水印。',
          '8. 服務可用性。VidGo 致力維持服務穩定，但不保證 100% 可用率。維護、第三方供應商中斷或不可抗力事件導致暫時無法使用時，VidGo 不負賠償責任，但會合理補償已扣除但未交付之點數。',
          '9. 免責聲明。AI 生成內容可能不準確、含有偏誤或無法商業使用，使用者須自行判斷是否合規。VidGo 對因使用生成內容造成之直接、間接、附帶或衍生損害不負責任，且總賠償責任以使用者最近 12 個月實際支付金額為上限。',
          '10. 終止。使用者可隨時刪除帳號；VidGo 可於違反本條款時暫停或終止帳號。終止後，依保留政策保存之必要紀錄仍可能保留至法定期間。',
          '11. 修訂。本條款可能隨服務調整而更新，重大變更會以電子郵件或站內公告通知。繼續使用視為接受新版條款。',
          '12. 準據法。本條款依中華民國（台灣）法律解釋，並以台灣台北地方法院為第一審管轄法院；對於台灣以外之使用者，可依當地強制性消費者保護法規請求救濟。',
          `如對本條款有任何疑問，請聯絡 ${CONTACT_EMAIL}。`,
        ]
      : [
          `Last updated: ${LAST_UPDATED}`,
          `1. Service Provider. The service is operated by ${COMPANY_NAME} ("VidGo") at ${SITE_URL}. Contact: ${CONTACT_EMAIL}.`,
          '2. Services. VidGo provides AI image and video generation tools including background removal, product scene composition, virtual try-on, room redesign, short video, AI avatar, and pattern generation. All outputs are produced through third-party generation models available at the time of request; no specific artistic or commercial outcome is guaranteed.',
          '3. Account. Users must provide a valid email and keep credentials confidential. Activity performed under an account is deemed performed by the account holder. Account sharing or using the account in breach of these terms is prohibited.',
          '4. Subscriptions and Billing. Paid plans are described in the dashboard. International payments are processed by PayPal, which issues receipts and invoices. Subscriptions auto-renew each billing period and may be cancelled anytime in account settings to prevent the next charge.',
          '5. Credits and Generation Quotas. Each plan grants credits per its rules. Sign-up bonus, purchased, and subscription credits are accounted separately as shown in the dashboard. On subscription cancellation or refund, only subscription-tied credits are revoked; purchased and bonus credits are unaffected.',
          '6. Content Rules. Users may not upload or request generation of: (a) material infringing third-party IP; (b) sexual content involving minors; (c) content inciting violence, hate or unlawful acts; (d) impersonation or unauthorized use of real persons\' likeness; (e) any content unlawful in the user\'s jurisdiction. VidGo may remove violating content and terminate accounts.',
          '7. Intellectual Property. The VidGo platform, UI, documentation, and brand assets are owned by VidGo. Users retain rights to their original uploads. Outputs generated through VidGo may be used commercially by paid subscribers; outputs from free demo users are watermarked and intended for personal preview only.',
          '8. Availability. VidGo aims for high availability but does not guarantee 100% uptime. Scheduled maintenance, upstream provider outages, or force majeure may temporarily affect service. VidGo will reasonably refund credits charged but not delivered.',
          '9. Disclaimer of Warranties and Liability. AI-generated content may be inaccurate, biased, or unsuitable for commercial use; users must independently judge fitness for their purpose. VidGo is not liable for direct, indirect, incidental, or consequential damages arising from use of generated content; total aggregate liability is capped at the amount paid by the user in the preceding 12 months.',
          '10. Termination. Users may delete their account at any time. VidGo may suspend or terminate accounts that violate these terms. Records required for legal or accounting compliance may be retained per the retention policy.',
          '11. Changes. These terms may be updated as the service evolves. Material changes will be notified by email or in-app notice. Continued use constitutes acceptance of the new terms.',
          '12. Governing Law. These terms are governed by the laws of Taiwan (R.O.C.) with the Taipei District Court as the court of first instance. Users outside Taiwan retain mandatory consumer-protection rights under their local law.',
          `Questions about these terms: ${CONTACT_EMAIL}.`,
        ],
  },
  privacy: {
    title: L('隱私權政策', 'Privacy Policy', 'プライバシーポリシー', '개인정보 처리방침', 'Política de privacidad'),
    body: isZh.value
      ? [
          `最後更新：${LAST_UPDATED}`,
          `1. 控制者身份。${COMPANY_NAME}（以下稱「VidGo」），網址 ${SITE_URL}，聯絡信箱 ${CONTACT_EMAIL}，為您個人資料之控制者。`,
          '2. 我們收集的資料。（a）帳號資料：電子郵件、加密後密碼、語言/主題偏好、登入紀錄與裝置資訊；（b）付款資料：付款交易識別碼、訂閱方案、發票抬頭與統一編號（由 PayPal / ECPay 處理卡片資料，VidGo 不接觸完整卡號）；（c）使用資料：上傳之素材、生成提示詞、生成結果、點數消費紀錄；（d）支援資料：與客服往來信件之內容。',
          '3. 使用目的。（a）提供與維護服務；（b）處理付款、開立發票、退款；（c）執行內容安全與防止濫用；（d）回覆客服請求；（e）改善產品與分析使用情形；（f）遵循法律義務。',
          '4. 法律依據。依約必要、使用者同意、合法利益（防止詐騙、改善服務）、以及法律遵循。',
          '5. 第三方處理者。我們使用以下類別之處理者：付款（PayPal、ECPay）、雲端基礎設施（Google Cloud Run、Cloud Storage、Cloud SQL）、AI 模型供應商（PiAPI、Pollo、A2E.ai、Google Vertex AI、Gemini）、發票（Giveme）、電子郵件（SMTP/Mailpit）。每家供應商僅取得執行其功能所需之最小資料。',
          '6. 國際傳輸。為提供服務，部分資料可能在台灣、美國、歐盟與其他國家處理。我們選擇承諾遵循 GDPR / CCPA / 台灣個資法等同等保護標準之供應商。',
          '7. 保存期間。帳號資料保留至帳號刪除後 30 天；交易與發票紀錄依會計法保存 7 年；上傳與生成媒體依儀表板顯示之保留政策（依方案不同為 7–90 天）保存，逾期後媒體不可下載但生成紀錄仍可查詢；客服信件保留 2 年。',
          '8. 您的權利。您可以隨時：（a）查詢、更正或更新您的個人資料；（b）要求刪除帳號與相關資料（法律要求保留之紀錄除外）；（c）匯出您的資料；（d）撤回行銷類同意；（e）向當地個資主管機關申訴。請來信 ' + CONTACT_EMAIL + ' 行使權利，我們將於 30 天內回覆。',
          '9. Cookie 與本機儲存。我們使用必要 Cookie 與 localStorage 維持登入、語言、主題與安全狀態。如未來加入分析或行銷 Cookie，將提供同意管理介面。',
          '10. 兒童隱私。VidGo 不刻意收集 13 歲以下兒童資料。若得知有未成年人帳號，將立即停用並刪除相關資料。',
          '11. 資料安全。我們採用 TLS 傳輸加密、密碼雜湊（bcrypt）、最小權限原則、定期備份與漏洞掃描。然而沒有任何系統可保證絕對安全，發生重大資料事件時將依法通知。',
          '12. 政策更新。本政策更新會於本頁面標示「最後更新」日期；重大變更將以電子郵件通知。',
        ]
      : [
          `Last updated: ${LAST_UPDATED}`,
          `1. Data Controller. ${COMPANY_NAME} ("VidGo"), ${SITE_URL}, contact ${CONTACT_EMAIL}, is the controller of your personal data.`,
          '2. Data We Collect. (a) Account data: email, hashed password, language/theme preferences, sign-in history, device fingerprint; (b) Payment data: transaction IDs, subscription plan, invoice details (card data is handled exclusively by PayPal; VidGo does not see full card numbers); (c) Usage data: uploaded media, generation prompts, generated outputs, credit transactions; (d) Support data: content of correspondence with our team.',
          '3. Purposes. (a) Provide and operate the service; (b) Process payments, invoices, and refunds; (c) Apply content safety and prevent abuse; (d) Respond to support requests; (e) Improve and analyse the product; (f) Comply with legal obligations.',
          '4. Legal Bases. Contractual necessity, your consent, legitimate interests (fraud prevention, service improvement), and legal compliance.',
          '5. Sub-processors. We rely on: payment (PayPal), cloud infrastructure (Google Cloud Run, Cloud Storage, Cloud SQL), AI providers (PiAPI, Pollo, A2E.ai, Google Vertex AI, Gemini), email (SMTP). Each receives only the minimum data needed to perform its function.',
          '6. International Transfers. To deliver the service, some data is processed in Taiwan, the United States, the European Union, and other regions. We select sub-processors that contractually adhere to GDPR, CCPA, and Taiwan PDPA-equivalent protections.',
          '7. Retention. Account data: retained for 30 days after account deletion. Transaction and invoice records: 7 years per accounting law. Uploaded and generated media: per the retention policy shown in the dashboard (7–90 days depending on plan); expired media cannot be downloaded but generation records remain. Support correspondence: 2 years.',
          `8. Your Rights. You may at any time: (a) access, correct, or update your data; (b) request deletion of your account and data (except records we are legally required to retain); (c) export your data; (d) withdraw marketing consent; (e) lodge a complaint with your local data-protection authority. Email ${CONTACT_EMAIL} to exercise these rights; we respond within 30 days.`,
          '9. Cookies and Local Storage. We use necessary cookies and localStorage to maintain login, language, theme, and security state. If analytics or marketing cookies are introduced, we will provide a consent interface.',
          '10. Children. VidGo does not knowingly collect data from children under 13. We will disable any account discovered to belong to a minor and delete associated data.',
          '11. Security. We use TLS in transit, bcrypt password hashing, least-privilege access, periodic backups, and vulnerability scanning. No system is perfectly secure; in the event of a material data incident we will notify users as required by law.',
          '12. Updates. Updates to this policy will be reflected by the "Last updated" date above; material changes will be notified by email.',
        ],
  },
  cookies: {
    title: L('Cookie 政策', 'Cookie Policy', 'Cookieポリシー', 'Cookie 정책', 'Política de cookies'),
    body: isZh.value
      ? [
          `最後更新：${LAST_UPDATED}`,
          'VidGo 使用必要 Cookie 與本機儲存（localStorage）來維持登入狀態、語言/主題偏好、與防止 CSRF 等安全功能。這些 Cookie 為提供服務所必須，無法停用。',
          '我們目前不使用第三方分析或行銷 Cookie。若日後加入，將事先提供同意管理介面。',
          '您可以透過瀏覽器設定清除 Cookie，但這可能導致需重新登入或偏好設定遺失。',
        ]
      : [
          `Last updated: ${LAST_UPDATED}`,
          'VidGo uses strictly necessary cookies and localStorage to maintain login state, language/theme preferences, and security features such as CSRF protection. These are required for the service and cannot be disabled.',
          'We currently do not use third-party analytics or marketing cookies. If introduced in the future, a consent interface will be provided in advance.',
          'You may clear cookies in your browser settings; doing so may require you to sign in again or restore preferences.',
        ],
  },
  refunds: {
    title: L('退款政策', 'Refund Policy', '返金ポリシー', '환불 정책', 'Política de reembolso'),
    body: isZh.value
      ? [
          `最後更新：${LAST_UPDATED}`,
          '您可以在訂閱後的 7 天內 申請退款，但需同時符合以下兩項條件：',
          '1. 該月點數消耗量 低於該月配發量的 5%（例：標準版 450 點，消耗低於 22 點）。',
          '2. 尚未導出過 無浮水印的高畫質成品。',
          '若消耗超過門檻，或已超過 7 天期限，視同已產生 API 成本，不予退款。',
          '單次購買的點數包屬虛擬商品，購買後不予退款。',
          '— — —',
          '其他補充條款：',
          '・自動續訂。訂閱於每個計費週期自動續訂。使用者可隨時於「帳號 → 訂閱」取消，取消後該週期內仍可使用至到期日，下次將不再扣款。',
          '・服務中斷補償。若 VidGo 因平台故障導致已扣除但未交付之點數，將自動補回相同點數，不另行退費。',
          '・退款方式。經核准之退款將原路退回至原付款方式（信用卡 / PayPal / 銀行轉帳），通常於 5–10 個工作天內到帳。',
          '・退款時的點數處理。獲得退款後，與該次付款對應之訂閱點數將自帳戶餘額中扣回；註冊贈送點數與其他購買點數不受影響。',
          '・法定權利。本政策不影響您依當地法律享有之強制性消費者權利（例如歐盟 14 天冷靜期）。',
          `・申請方式。請寄電子郵件至 ${CONTACT_EMAIL}，主旨註明「退款申請」，並附上：帳號電子郵件、訂單編號、退款原因。我們將於 5 個工作天內回覆審核結果。`,
        ]
      : [
          `Last updated: ${LAST_UPDATED}`,
          'You may request a refund within 7 days of subscribing if you meet BOTH of the following conditions:',
          '1. Credits used this month are below 5% of your monthly allowance (e.g. Standard plan: less than 22 credits out of 450).',
          '2. You have not yet exported any watermark-free high-quality output.',
          'If you have exceeded either threshold, or are past the 7-day window, the API cost is considered consumed and no refund is issued.',
          'One-time credit packs are digital goods and are non-refundable once purchased.',
          '— — —',
          'Additional terms:',
          '・Auto-renewal. Subscriptions auto-renew each billing cycle. Cancel anytime under "Account → Subscription"; access continues until period end and you will not be charged again.',
          '・Service outage compensation. If a platform fault deducted credits without delivering output, VidGo restores the same credit amount automatically; no monetary refund is issued for this case.',
          '・Refund method. Approved refunds are returned to the original payment method (credit card / PayPal / bank transfer), typically within 5–10 business days.',
          '・Credit reconciliation. When a refund is granted, subscription credits tied to that payment are reversed from your balance; sign-up bonus credits and other purchased credits are not affected.',
          '・Statutory rights. This policy does not affect mandatory consumer rights you have under your local law (e.g. the 14-day cooling-off right in the EU).',
          `・How to request. Email ${CONTACT_EMAIL} with the subject "Refund Request" and include: account email, order ID, and refund reason. We respond within 5 business days.`,
        ],
  },
}))

const SLUG_ALIASES: Record<string, string> = {
  'terms-of-service': 'terms',
  'terms-and-conditions': 'terms',
  'privacy-policy': 'privacy',
  refund: 'refunds',
  'refund-policy': 'refunds',
}

const page = computed(() => {
  const raw = String(route.params.slug || 'about')
  const slug = SLUG_ALIASES[raw] || raw
  return pages.value[slug] || pages.value.about
})
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
