# PayPal + 綠界（ECPay）金流設定指南（管理員操作手冊）

> **對象**：VidGo 的系統管理員 / 財務窗口
> **目的**：在 PayPal 官方後台、綠界（ECPay）廠商後台完成金流串接所需的設定
> **前提**：本文只涵蓋「在 PayPal 官網、綠界官網」要做的事。程式碼與 Secret Manager 部份請交給工程師搭配 `docs/PAYPAL_SETUP.md`、`docs/dns-and-ecpay-setup.md` 操作。

---

## 0. 開始前，先備妥這些資料

| 項目 | 內容 | 備註 |
|---|---|---|
| 主網域 | `vidgo.co` | 前端 |
| 後端 API 網域 | `api.vidgo.co` | Webhook / Callback 全部指到這裡 |
| 公司資料 | 瞬影科技股份有限公司 · 統一編號 `96003146` | ECPay 商店登記用 |
| 綠界商店代號 (MerchantID) | `3422044` | 生產環境 |
| Cloud Run NAT 出站 IP | 請工程師執行 `gcloud compute addresses describe vidgo-nat-ip --region=asia-east1 --project=vidgo-ai --format="value(address)"` 給你 | ECPay IP 白名單要用 |
| VidGo 訂閱方案定價（USD，PayPal 用） | Basic $19.99/月、Pro $49.99/月、Premium $89.99/月；**年繳一律 = 月費 × 12** | 對應 `frontend-vue/src/views/Pricing.vue:OVERSEAS_USD_MONTHLY` |
| 折算年繳金額 | Basic $239.88/年、Pro $599.88/年、Premium $1079.88/年 | PayPal 建方案要輸入這個 |

**請把上面「NAT 出站 IP」跟你的工程師要一次，並準備一張表記下 PayPal 建方案時系統回傳的 6 個 Plan ID（格式 `P-XXXXX…`）**。

---

## 1. PayPal 官網設定（Developer Dashboard）

PayPal 有兩個環境：**Sandbox（沙盒 / 測試）** 與 **Production / Live（正式 / 真金流）**。務必先在 Sandbox 走完流程，確認整條鏈路通了，再重複同樣步驟切到 Live。

以下先以 **Sandbox** 為例；Live 版就是把每個「Sandbox」文字改成「Live」，然後全部重做一次（包含 Client ID / Secret / Plan ID / Webhook ID）。

### 1.1 建立 PayPal 商用帳號（如果還沒有）

1. 到 <https://www.paypal.com/tw/business>。
2. 用要收款的公司信箱註冊 **Business Account（商業帳號）**。
3. 完成身分驗證（KYC）、綁定收款銀行。
   > 未通過 KYC 之前，就算 Sandbox 都能跑，Live 時 PayPal 會扣款成功但撥款會被凍結。

### 1.2 建立 Developer App（拿到 Client ID / Secret）

1. 到 <https://developer.paypal.com/dashboard/applications/sandbox> 登入（用 1.1 的商業帳號）。
2. 右上角 **Create App**。
3. 選 **Merchant** 類型，App 名稱建議：`VidGo Backend (Sandbox)`。
4. 建立完成後，畫面上就會顯示：
   - **Client ID** ← 抄下來
   - **Secret** ← 抄下來（按「Show」才會顯示；只顯示一次，務必存好）
5. Live 版：改到 <https://developer.paypal.com/dashboard/applications/live> 重複同一件事，App 名稱建議 `VidGo Backend (Live)`。

### 1.3 建立訂閱方案（Subscription Plans）

VidGo 有 3 個方案 × 2 個週期（月 / 年）= **6 個 PayPal Plan**，每個都要在 PayPal 建一次。

1. Sandbox：<https://www.sandbox.paypal.com/billing/plans>
   Live：<https://www.paypal.com/billing/plans>
2. **Create Plan**（或「建立方案」）→ 依下表逐一輸入：

| VidGo 內部 key | 產品（Product）名稱 | Billing cycle | Price (USD) | Trial |
|---|---|---|---|---|
| `basic_monthly` | VidGo Basic | Every 1 month | **19.99** | 無 |
| `basic_yearly` | VidGo Basic | Every 1 year | **239.88** | 無 |
| `pro_monthly` | VidGo Pro | Every 1 month | **49.99** | 無 |
| `pro_yearly` | VidGo Pro | Every 1 year | **599.88** | 無 |
| `premium_monthly` | VidGo Premium | Every 1 month | **89.99** | 無 |
| `premium_yearly` | VidGo Premium | Every 1 year | **1079.88** | 無 |

- 幣別選 **USD**。
- **Auto-Bill Outstanding Amount**：勾選 **Yes**（自動重試失敗扣款）。
- **Setup Fee**：不用填。
- 一個「Product」下面可以掛 monthly + yearly 兩個 Billing Cycle，也可以分兩個 Plan，兩種都 OK。

3. 每建完一個方案，系統會顯示 **Plan ID**（格式 `P-XXXXXXXXXXXXXXXXXXXX`）。把它填進下面這張表：

```
basic_monthly    → P-________________________
basic_yearly     → P-________________________
pro_monthly      → P-________________________
pro_yearly       → P-________________________
premium_monthly  → P-________________________
premium_yearly   → P-________________________
```

### 1.4 建立 Webhook（訂閱狀態變化通知）

1. 回 <https://developer.paypal.com/dashboard/applications/sandbox>，點你剛才建的 App。
2. 往下捲到 **Webhooks** 區塊 → **Add Webhook**。
3. **Webhook URL**（正式與 Sandbox 都填同一個，因為後端會用 `PAYPAL_ENV` 自動切換沙盒 / 正式端點）：

   ```
   https://api.vidgo.co/api/v1/payments/paypal/webhook
   ```

4. **Event types** 只勾這 6 個（其他不要打勾，避免噪音）：
   - `BILLING.SUBSCRIPTION.ACTIVATED`
   - `BILLING.SUBSCRIPTION.CANCELLED`
   - `BILLING.SUBSCRIPTION.SUSPENDED`
   - `BILLING.SUBSCRIPTION.PAYMENT.FAILED`
   - `PAYMENT.SALE.COMPLETED`
   - `PAYMENT.SALE.REFUNDED`
5. 儲存後，系統會給你一組 **Webhook ID**（格式 `WH-XXXXXXXXXX` 或 `數字-數字`）— **抄下來**。
6. Live 版一模一樣操作一次；會拿到另一組不同的 Webhook ID。

### 1.5 把值填進 VidGo Admin 後台（不用改程式碼、不用重新部署）

1. 用 **superuser** 帳號登入 <https://vidgo.co/admin/settings/payment>。
2. 對照下表填入（一次填一個環境；先 Sandbox 測完再切 Production）：

| 欄位 | Sandbox 填什麼 | Production 填什麼 |
|---|---|---|
| **PAYPAL_ENV** | `sandbox` | `production` |
| **PAYPAL_CLIENT_ID** | 1.2 拿到的 Sandbox Client ID | 1.2 拿到的 Live Client ID |
| **PAYPAL_CLIENT_SECRET** | 1.2 拿到的 Sandbox Secret | 1.2 拿到的 Live Secret |
| **PAYPAL_WEBHOOK_ID** | 1.4 拿到的 Sandbox Webhook ID | 1.4 拿到的 Live Webhook ID |
| **PAYPAL_PLAN_IDS** | 1.3 六個 Plan ID 組成的 JSON（見下） | 同格式，換成 Live 的 6 個 |

**`PAYPAL_PLAN_IDS` JSON 範例**（直接複製到 Admin 後台的 textarea，把 `P-...` 換成你的實際值）：

```json
{
  "basic_monthly":   "P-XXXXXXXXXXXXXXXXXXXX",
  "basic_yearly":    "P-XXXXXXXXXXXXXXXXXXXX",
  "pro_monthly":     "P-XXXXXXXXXXXXXXXXXXXX",
  "pro_yearly":      "P-XXXXXXXXXXXXXXXXXXXX",
  "premium_monthly": "P-XXXXXXXXXXXXXXXXXXXX",
  "premium_yearly":  "P-XXXXXXXXXXXXXXXXXXXX"
}
```

3. **Save Changes**。
4. 按 **Test Connection** 按鈕：
   - Sandbox 成功會顯示 ✓ `OAuth ok. env=sandbox`
   - Production 成功會顯示 ✓ `OAuth ok. env=production`
   - **如果失敗**：多半是 Client ID / Secret 有多打了空白或換行，回上面剪貼一次即可。

> 60 秒內設定即會生效，不需要工程師重新部署。

### 1.6 Sandbox → Production 切換前的檢查清單

Sandbox 測完之後才做 Live 切換。**Live 的 6 個 Plan ID、Client ID、Secret、Webhook ID 全部都是不同一組，一定要重建。**

- [ ] Live 版商業帳號 KYC 已通過、銀行帳號已綁定
- [ ] Live 版 Developer App 已建（1.2 重跑一次）
- [ ] Live 版 6 個 Plan 已建（1.3 重跑一次）
- [ ] Live 版 Webhook 已建（1.4 重跑一次）
- [ ] Admin 後台 `PAYPAL_ENV=production`
- [ ] Admin 後台 `PAYPAL_CLIENT_ID / SECRET / WEBHOOK_ID / PLAN_IDS` 全部換成 Live
- [ ] Test Connection 顯示 ✓ `env=production`
- [ ] 用自己的信用卡買最便宜的方案（$19.99）跑一次真金流，並在 30 分鐘內從 PayPal Activity 退款

---

## 2. 綠界（ECPay）廠商後台設定

綠界的金鑰（MerchantID / HashKey / HashIV）**不能透過 Admin 後台改**，必須交給工程師寫進 Secret Manager 後重新部署一次。這一節只涵蓋「你要在綠界廠商後台做什麼」，程式面的部份請看 `docs/dns-and-ecpay-setup.md`。

### 2.1 登入綠界廠商後台

1. 到 <https://vendor.ecpay.com.tw>。
2. 用商店代號 `3422044` 登入。

### 2.2 設定四個回傳網址

**位置**：左側選單 **系統開發管理** → **系統介接設定**。

依照下表更新，然後按最下方 **儲存**：

| 綠界欄位名稱 | 要填的值 |
|---|---|
| **付款完成通知回傳網址（ReturnURL）** | `https://api.vidgo.co/api/v1/payments/ecpay/callback` |
| **訂單查詢網址（OrderResultURL）** | `https://api.vidgo.co/api/v1/payments/ecpay/result-redirect` |
| **Client 端返回商店網址（ClientBackURL）** | `https://vidgo.co/subscription/ecpay-result` |
| **Client 端付款失敗返回商店網址** | `https://vidgo.co/subscription/ecpay-result` |

> ⚠️ 三個 URL 一定要 `https://` 開頭；HTTP 的綠界會直接拒收。
> ⚠️ 這些網址若打錯，會導致「使用者付款成功、後台卻沒收到通知」，然後訂閱不會啟用。務必再三確認。

### 2.3 加入伺服器 IP 白名單

**位置**：同一頁 **系統介接設定** → **允許的 Server 端 IP** 欄位。

1. 把第 0 節「Cloud Run NAT 出站 IP」加進去（單一 IP，格式如 `35.234.xxx.xxx`）。
2. 按 **儲存**。

> 沒加白名單，綠界會直接拒接後端主動查單、退款、對帳等 Server-to-Server 呼叫。

### 2.4 拿 HashKey / HashIV 給工程師

**位置**：**系統開發管理** → **系統介接設定** → 頁面最上方會列出：

- **MerchantID**：`3422044`（已經知道）
- **HashKey**：一串英數字
- **HashIV**：一串英數字

**這兩個值等同於支付密碼**，請用內部安全的方式（1Password / Vaultwarden / 加密郵件）交給工程師，工程師會執行以下步驟後重新部署：

```bash
gcloud --project vidgo-ai secrets versions add ECPAY_HASH_KEY --data-file=- <<< "貼上 HashKey"
gcloud --project vidgo-ai secrets versions add ECPAY_HASH_IV  --data-file=- <<< "貼上 HashIV"
bash gcp/deploy-service.sh --backend
```

**絕對不要用 Slack / LINE / 一般 email 傳這兩個值。**

### 2.5 電子發票（Giveme）— 順帶提醒

VidGo 的電子發票是走 **Giveme**（`GIVEME_ENABLED=true`），綠界電子發票只是 fallback。你還要做：

1. 到 <https://www.giveme.com.tw> 廠商後台 → **系統設定** → **白名單設定**。
2. 把同一組 NAT IP 加進去。
3. 存檔。

否則使用者付款成功後開發票會失敗（該筆訂單不會自動開票）。

---

## 3. 端到端驗證（切生產前一定要做）

以下每一項都通過，才代表金流真的能用。

### 3.1 PayPal Sandbox 全流程

1. **買方登入**：<https://developer.paypal.com/dashboard/accounts> → 用一個 Sandbox Personal 帳號登入 vidgo.co。
2. **結帳**：`/pricing` → 選 Basic Monthly → 按 PayPal 按鈕 → 用 Sandbox 買方帳號完成付款。
3. **回導成功頁**：瀏覽器會回到 `https://vidgo.co/subscription/success?order=SUB…`。
4. **後台檢查**（請工程師查一次或你自己有 admin 權限就自己查）：
   - `users.status = active`
   - `users.plan_id = basic`
   - `subscription_credits > 0`
5. **Webhook 收到**：Cloud Run log 內應出現 `[PayPal] webhook received event=BILLING.SUBSCRIPTION.ACTIVATED`。
6. **測試取消 / 退款**：`/dashboard/subscription` 按取消 → 7 天內應觸發部分退款 → 到 PayPal Sandbox → **Activity** 查 REFUNDED 狀態。

### 3.2 綠界（Production 因為綠界沒有沙盒可測金流全流程；先做小額）

1. 用自己的信用卡去 `/pricing` 買 **Basic Monthly**（TWD $399）。
2. 綠界頁面完成付款。
3. 應回導到 `https://vidgo.co/subscription/ecpay-result` 顯示成功。
4. 檢查後台 `users` / `orders`：應有一筆 `orders.status = paid`、`users.plan_id = basic`。
5. Giveme 應在幾分鐘內自動開發票（會 email 給付款者）。
6. **測退款**：Admin 後台 → Users → 找到自己 → 觸發退款 → 到綠界廠商後台 → 對帳查詢確認狀態 = 已退款。

### 3.3 常見錯誤

| 症狀 | 原因 | 修法 |
|---|---|---|
| PayPal 按鈕沒出現 | Admin 後台的 `PAYPAL_CLIENT_ID` 或 `SECRET` 是空的 | 回 1.5 重填、Test Connection 按到綠燈 |
| PayPal 結帳按了沒反應、`checkout_url=null` | 後端仍在 mock 模式 | Admin → payment settings → Test Connection 應顯示錯誤細節 |
| PayPal 付完成但訂閱沒啟用 | Webhook URL 打錯、或 Webhook Event Type 少勾 | 回 1.4 確認 URL 與 6 個 event 有勾 |
| PayPal `HTTP 401` | Client ID / Secret 對不上 env（Sandbox 值用在 Production 或反之） | 回 1.5 確認 `PAYPAL_ENV` 與那組憑證是同一環境 |
| 綠界付款成功但沒進系統 | ReturnURL 打錯 / NAT IP 沒白名單 | 回 2.2、2.3 檢查 |
| 綠界 `10200052` 或簽章錯誤 | HashKey / HashIV 交給工程師時貼錯 / 有空白 | 回 2.4 重丟一次給工程師 |
| Giveme 沒開發票 | Giveme 白名單沒加 NAT IP | 回 2.5 |

---

## 4. 附錄 A：Admin 後台可改 vs. 只能工程師改

| 項目 | 改的地方 | 是否需要重新部署 |
|---|---|---|
| PayPal 環境 / Client ID / Secret / Webhook ID / Plan IDs | Admin 後台 `/admin/settings/payment` | ❌ 60 秒內生效 |
| PayPal Webhook URL 內容 | PayPal Developer Dashboard | ❌ |
| PayPal 訂閱方案價格、名稱 | PayPal Developer Dashboard | ❌ 但方案改價格通常要建新 Plan，然後把 Admin 後台 PLAN_IDS 換成新的 ID |
| 綠界 MerchantID / HashKey / HashIV | Secret Manager（工程師） | ✅ 需 `bash gcp/deploy-service.sh --backend` |
| 綠界 Callback URL | 綠界廠商後台 → 系統介接設定 | ❌ |
| 綠界 IP 白名單 | 綠界廠商後台 → 系統介接設定 | ❌ |
| Giveme IP 白名單 | Giveme 廠商後台 | ❌ |

## 5. 附錄 B：緊急停用金流（Live 出事時）

**PayPal 停用**（不動綠界）：

1. Admin 後台 → payment settings。
2. 把 `PAYPAL_CLIENT_ID` **清空** → Save。
3. 60 秒內前端 PayPal 按鈕會消失（`/api/v1/payments/methods` 回 `paypal.enabled=false`）。
4. 事後恢復：把 Client ID 貼回去 → Save。

**綠界停用**（不動 PayPal）：綠界的金鑰在 Secret Manager，臨時停用最快的方法是請工程師執行：

```bash
gcloud --project vidgo-ai run services update vidgo-backend \
  --region asia-east1 \
  --update-env-vars="ECPAY_ENV=disabled"
```

（後端讀到 `ECPAY_ENV` 非 `production` / `sandbox` 就會關掉綠界結帳按鈕。）恢復時把 env var 改回 `production` 即可。

---

## 6. 相關文件與檔案

- 完整程式行為（快取、runtime override 機制）：[`docs/PAYPAL_SETUP.md`](PAYPAL_SETUP.md)
- DNS + Cloud Run domain mapping：[`docs/dns-and-ecpay-setup.md`](dns-and-ecpay-setup.md)
- 部署腳本：[`gcp/deploy-service.sh`](../gcp/deploy-service.sh)（純程式碼變動時用）、[`gcp/deploy.sh`](../gcp/deploy.sh)（環境變數 / 新 Secret 變動時用）
- 目前生效的 PayPal Webhook ID：`75T233837H582090M`（見團隊 memory；如要輪替請按 1.4 建新的然後回 1.5 換值）
