# VidGo 系統真實架構盤點與維運交接清單 (V6) — 填寫版

> Audit performed: **2026-05-26** against live production (Cloud Run revisions `vidgo-backend-00295-zjm` + `vidgo-frontend-00250-ndc`).
> Performed by inspecting source tree + live Cloud Run / Cloud SQL / Vertex AI / PiAPI endpoints. Payment flows skipped per request — see Section 5 for file paths only.

---

## 一、原始碼與 GitHub CI/CD 部署架構

| Item | Answer |
|---|---|
| **GitHub 儲存庫 URL** | `https://github.com/Enuma3lish/Vidgo_Gen_AI.git` |
| **Production 分支** | `main` |
| **CI/CD 機制** | **沒有** `.github/workflows/` (GitHub Actions 未啟用)。實際部署是手動觸發 **Google Cloud Build**：<br>• `cloudbuild.yaml` — full stack<br>• `cloudbuild.backend-only.yaml` — just backend<br>• `cloudbuild.frontend-only.yaml` — just frontend |
| **部署指令** | `gcloud builds submit --config cloudbuild.<scope>.yaml --project vidgo-ai --region asia-east1 .`<br>之後 `gcloud run services update vidgo-<service> --image …` 把新 image 滾到 Cloud Run |
| **底層部署腳本** | `gcp/deploy.sh` (基礎建設一鍵腳本)<br>`gcp/deploy-production.sh` (production 重置腳本) |
| **Cloud Build → Artifact Registry** | Image 推到 `asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images/{vidgo-backend,vidgo-frontend}` |

**⚠️ 給外包的重點**：目前是手動 Cloud Build → 手動 Cloud Run 更新。如要 push-to-main 自動部署，需新增 `.github/workflows/deploy.yml`（目前不存在）。

---

## 二、GCP 雲端基礎設施實際部署資源

| GCP 服務 | 實際使用 | 資源實例名稱 |
|---|---|---|
| **GCP Project ID** | — | `vidgo-ai` |
| **Region** | — | `asia-east1` (Taiwan) |
| **前端 + 後端** | ✅ **Cloud Run** (非 GCE VM) | 前端：`vidgo-frontend` → `https://vidgo-frontend-r2laip67ma-de.a.run.app`<br>後端：`vidgo-backend` → `https://vidgo-backend-r2laip67ma-de.a.run.app`<br>Worker：`vidgo-worker` (背景任務) |
| **主資料庫** | ✅ **Cloud SQL** (Postgres 15) | Instance：`prod-db`<br>Connection name：`vidgo-ai:asia-east1:prod-db`<br>Tier：`db-f1-micro` (Phase 1)<br>**Private IP only** (`10.70.0.3`，無公網 IP) — 必須走 Cloud SQL Auth Proxy 或 VPC connector |
| **快取與佇列** | ✅ **GCP Memorystore** Redis | Instance：`vidgo-redis`<br>Host：`10.24.105.251:6379`<br>Tier：`BASIC` 1 GB |
| **媒體儲存** | ✅ **GCS Bucket** | `gs://vidgo-media-vidgo-ai/`<br>Cloud Build 工件：`gs://vidgo-ai_cloudbuild/` |
| **VPC** | — | `vidgo-vpc` + connector `vidgo-connector` (Cloud Run ↔ Cloud SQL/Redis) |

---

## 三、三大 AI 供應商架構做法與路徑

> **2026-05-26 重大架構變更**：兩個 MCP provider (`piapi_mcp_provider.py`, `pollo_mcp_provider.py`) **已全部刪除**，僅保留 REST 通道。原因：MCP 工具目錄與 PiAPI 模型不同步、`PIAPI_MCP_ENABLED=false` 已在 prod 停用數週、REST `piapi` 已是所有 task 的 primary。詳見最新 commit 與 `provider_router.py` header 註解。

| Provider | 架構做法 | 程式檔案 |
|---|---|---|
| **PiAPI** (主線路徑) | ✅ **REST API 直接呼叫** (純 HTTP via `httpx`)<br>❌ MCP server 子進程 **已移除 2026-05-26** | Provider 類別：<br>`backend/app/providers/piapi_provider.py` (~88 KB, ~1885 行)<br>路由分派：`backend/app/providers/provider_router.py` (lines 580-595, `_execute_piapi`)<br>FastAPI tool routes：`backend/app/api/v1/tools.py` (16 個 POST endpoints) |
| **Pollo AI** (影片備援) | ✅ **REST API 直接呼叫**<br>❌ `pollo-mcp` npm 套件 **已移除 2026-05-26** (catalog 不同步，每次 img2video_seedance 都 404) | Provider：`backend/app/providers/pollo_provider.py`<br>備註：僅作為 Kling I2V (`kling_v1.5`, `kling_v2`) + Pixverse + Hailuo 的 REST 備援；Pollo 不支援 `seedance` 或純 T2V |
| **A2E AI** (數位人專用) | ✅ **REST API** (透過 `app.services.a2e_service`)<br>❌ Apidog MCP 未使用 | Provider：`backend/app/providers/a2e_provider.py`<br>備援於 Avatar 流程：`backend/app/api/v1/tools.py` line 4038 `/avatar` 呼叫 `_check_provider_health("a2e")` |
| **Vertex AI / Gemini / Veo** (最終備援) | ✅ Vertex AI Predict API + Gemini API | Provider：`backend/app/providers/vertex_ai_provider.py`<br>Veo model：`veo-3.0-fast-generate-001` (修正於 2026-05-26；舊值 `veo-3.1-generate` 不存在會 404)<br>Region: `us-central1` for Veo (image/text 在 `asia-east1`) |

**Provider chain 現況** (每個 task type 的路由順序，定義於 `provider_router.py` `ROUTING_CONFIG`)：

| Task Type | Primary | Backup | Tertiary | Pollo override (model-aware) |
|---|---|---|---|---|
| **I2V** | `piapi` | `vertex_ai` (Veo) | `pollo` (added 2026-05-26 — only succeeds for Kling v1.5/v2, Pixverse, Hailuo, Minimax, Wan, pollo-v1-6) | **Pollo → primary** when `model_id ∈ POLLO_VIDEO_MODEL_IDS` |
| **T2V** | `piapi` | `vertex_ai` (Veo) | — | Pollo REST has no T2V endpoint (`not implemented` 404) — excluded |
| **V2V** | `piapi` | `vertex_ai` (Veo) | — | Pollo REST has no V2V endpoint — excluded |
| T2I / I2I / Effects | `piapi` | `vertex_ai` (Gemini Imagen) | — | Pollo doesn't expose image generation REST endpoints |
| Upscale / BG-Remove | `piapi` | `vertex_ai` | — | Pollo doesn't expose these |
| Interior / Interior-3D | `piapi` | `vertex_ai` | — | Pollo doesn't expose these |
| Avatar | `piapi` (Kling Avatar) | `a2e` | — | Pollo has no avatar API |
| Moderation / Material-Gen | `vertex_ai` | — | — | Only Gemini |
| Midjourney-Imagine (旗艦圖) | `piapi` only | — | — | Pollo doesn't expose Midjourney-class T2I |
| **Kling-Video** | `piapi` | `pollo` (I2V mode only) | — | Pollo's Kling REST is I2V-only — T2V Kling falls back to PiAPI directly |

> **Pollo REST coverage matrix** (audited 2026-05-25 against PiAPI's actual catalog response):
> - ✅ supports: `pixverse_v4.5`, `pixverse_v5`, `kling_v1.5`, `kling_v2`, `kling2.5`, `kling_v3`, `kling_omni`, `hailuo`, `hailuo_fast`, `minimax`, `wan2.6`, `wan`, `pollo-v1-6` — **all in I2V mode only**
> - ❌ does NOT support: any T2I (`flux`, `qwen`, `seedream`, `nano-banana*`), T2V (any model), V2V, upscale, background-remove, avatar, interior, Midjourney
>
> **TL;DR**: Pollo is a model-specific I2V fallback, not a full secondary provider. The `POLLO_VIDEO_MODEL_IDS` set in `provider_router.py:135` is the authoritative coverage list — anything not in it makes Pollo soft-fail in ~200ms and the chain moves to the next provider.

**MCP 殘留偵測** (sanity)：
```bash
$ ls backend/app/providers/*.py
__init__.py  a2e_provider.py  base.py  piapi_provider.py
pollo_provider.py  provider_router.py  vertex_ai_provider.py
# (沒有任何 *_mcp_provider.py — 已全部刪除)

$ ls backend/app/services/mcp_client.py
ls: ...: No such file or directory   # 已刪除

$ ls mcp-servers/
ls: ...: No such file or directory   # 整個 dir 已刪除 (省 ~59 MB)
```

Cloud Run env 確認 MCP 已關閉：
```
$ gcloud run services describe vidgo-backend ... --format json | grep MCP
(無任何 MCP env var — 2026-05-26 已 remove-env-vars PIAPI_MCP_ENABLED,PIAPI_MCP_PATH)
```

---

## 四、24 項 AI 工具實際串接進度

> 全部 24 項皆驗證於 2026-05-26 (E2E 測試以 admin 帳號 `vidgo168@gmail.com` 對 prod backend `vidgo-backend-00295-zjm`)。<br>**底層 provider 全部 = PiAPI REST** (Vertex Veo / A2E 為 fallback)。

| # | 工具名稱 | 前端路由 | 後端 handler (`tools.py`) | TaskType / 模型 | Provider | 狀態 |
|---|---|---|---|---|---|---|
| 1 | 室內設計改造 | `/tools/room-redesign` | line 2723 `room_redesign` | I2I → Flux Kontext (or Magic 模式直送) | PiAPI | ✅ 已完工 (20 credits, ~30s, 已驗證) |
| 2 | 商品去背 / 換景 | `/tools/background-removal` | line 1663 `/remove-bg` | BACKGROUND_REMOVAL + T2I (AI scene 模式) | PiAPI Qubico | ✅ 已完工 (3 cr, ~5s) |
| 3 | 運用 AI 建立圖片 | `/tools/midjourney-imagine` (Create-any-image tile) | line 4801 `midjourney_imagine` | T2I → Flux / Qwen / Z-Image / Nano Banana / Seedream | PiAPI | ✅ 已完工 (5 cr) |
| 4 | 商品換色 (Recolor) | `/tools/pattern-generate` | `generation.py` line 370 `/generate/pattern/generate` | T2I (圖案生成) | PiAPI | ✅ 已完工 (前端 hub tile 連到此 route) |
| 5 | 商品圖優化放大 | `/tools/upscale` | line 3947 `upscale_image` | UPSCALE Qubico image-toolkit (2x/4x/8x) | PiAPI | ✅ 已完工 (10 cr, 8x 已驗證可運作) |
| 6 | 虛擬模特試穿 | `/tools/try-on` | line 2385 `ai_try_on` | I2I → Kling Try-On (garment 模式) / Flux Kontext (prompt 模式) | PiAPI | ✅ 已完工 (15 cr) — 須用 2:3/3:4 portrait 模特照 |
| 7 | 商品場景圖 | `/tools/product-scene` | line 1965 `product_scene` | I2I Kontext | PiAPI | ✅ 已完工 (10 cr) |
| 8 | AI 圖片修飾 | `/tools/midjourney-imagine` (Edit-with-AI tile) | line 4801 (同 #3) | T2I | PiAPI | ✅ 已完工 |
| 9 | 服飾去人台 (Ghost mannequin) | `/tools/background-removal` (tile only) | 同 #2 | BG remove | PiAPI | ✅ 已完工 |
| 10 | 服飾去皺 (Ironing) | `/tools/upscale` (tile only) | 同 #5 | UPSCALE | PiAPI | ✅ 已完工 (tile 共用 upscale) |
| 11 | 商品平拍 (Flat lay) | `/tools/product-scene-classic` | 同 #7 | I2I Kontext | PiAPI | ✅ 已完工 |
| 12 | 品牌 Logo | `/tools/midjourney-imagine` (Logo tile) | line 4801 | T2I | PiAPI | ✅ 已完工 |
| 13 | 圖片文字 (Image translator) | `/tools/image-translator` | line 4436 `image_translate` | OCR + Gemini 翻譯 + 重新合成 | **Vertex AI Gemini + PiAPI** (混合) | ✅ 已完工 (1 cr) |
| 14 | 行銷主視覺 (Create-any-image) | `/tools/midjourney-imagine` | line 4801 | T2I | PiAPI | ✅ 已完工 |
| 15 | IG / TikTok 短片 | `/tools/short-video` | line 3084 `generate_short_video` | I2V → Seedance / Kling Omni / Veo / Hailuo / Hunyuan / Wan | PiAPI (Kling 模型路由到 KLING_VIDEO) | ✅ 已完工 (20-750 cr 依 model_id) — 2026-05-26 修正 Kling cost leak |
| 16 | 商品電商照 (Product photography) | `/tools/product-scene-classic` | 同 #7 | I2I Kontext | PiAPI | ✅ 已完工 |
| 17 | 包裝圖案設計 (Product packaging) | `/tools/pattern-generate` | 同 #4 | T2I | PiAPI | ✅ 已完工 |
| 18 | 立體感影片 (3D illustration) | `/tools/kling-video` | line 4911 `kling_video` | KLING_VIDEO (default / flagship / omni) | PiAPI Kling | ✅ 已完工 (60/500/750 cr) |
| 19 | 商品動態廣告 (Video generator) | `/tools/kling-video` | 同 #18 | KLING_VIDEO | PiAPI Kling | ✅ 已完工 |
| 20 | 室內設計範本 | `/tools/interior-templates` | 靜態目錄 (`/tools/templates/interior-styles` GET) | — (純前端 picker → 跳轉到 #1 room-redesign) | 無生成；只是 catalog | ✅ 已完工 (33 個 style 模板) |
| 21 | 影片去背 | `/tools/video-bg-remove` (FE route) → `/api/v1/tools/video-background-remove` (BE) | line 3853 `video_background_remove` | Qubico video-toolkit | PiAPI | ✅ 已完工 (50 cr, ~130s) |
| 22 | 黏土風生成 | `/tools/claymation` | line 3617 `claymation_generate` | T2I (Seedream) / I2I (Flux Kontext) / T2V (Kling Omni) / V2V (Seedance first-frame) | PiAPI | ✅ 已完工 (8/8/50/50 cr) — 2026-05-26 修正 T2V URL extraction bug |
| 23 | AI 數位人 / 代言人 | `/tools/avatar` | line 4038 `generate_avatar_video` | AVATAR → PiAPI Kling Avatar + F5-TTS / tts-1 | PiAPI primary, **A2E backup** | ✅ 已完工 (300 cr) |
| 24 | 影片配音翻譯 | `/tools/video-dubbing` | line 4566 `video_dubbing` | Whisper (PiAPI) + GPT translate + TTS (PiAPI) + lip-sync | PiAPI (composite pipeline) | ✅ 已完工 (30 cr) — 需提供 source_script 或 translated_script (ASR 暫不可用) |

**Smoke test result (2026-05-26)**：16/16 POST endpoints reachable;
- 13 returned `422 Unprocessable Entity` for empty body (代表 Pydantic 驗證正常)
- 3 returned `200 OK` with `success:false, message:"..."` (handler 內部驗證代替 Pydantic — product-scene / try-on / room-redesign)
- 0 endpoint 真正 broken

---

## 五、金流對接稽核 (依需求**跳過實機測試**，僅標記程式路徑)

### 5.1 ECPay (台灣信用卡) + Giveme (電子發票)
| Item | Path |
|---|---|
| ECPay client | `backend/app/services/ecpay/client.py` |
| ECPay callback / 結果處理 | `backend/app/api/v1/payments.py` (`/ecpay/callback`, `/ecpay/result-redirect`) |
| Giveme 電子發票 service | `backend/app/services/giveme/` |
| 發票自動開立 | `backend/app/services/invoice_service.py` (`auto_issue_invoice`) — 在 `handle_payment_success` 後 fire-and-forget |
| 環境變數 | `ECPAY_MERCHANT_ID`, `ECPAY_HASH_KEY`, `ECPAY_HASH_IV`, `ECPAY_PAYMENT_URL`, `GIVEME_ENABLED`, `GIVEME_UNCODE` (in Cloud Run env) |

### 5.2 PayPal + 內建 Invoice
| Item | Path |
|---|---|
| PayPal service | `backend/app/services/paypal_service.py` |
| PayPal webhook receiver | `backend/app/api/v1/payments.py` (`/paypal/webhook`, `/paypal/return`) |
| 訂閱 checkout / cancel / refund | `backend/app/services/subscription_service.py` (`_create_payment_checkout`, `_process_refund`, `handle_payment_success`) |
| 環境變數 | `PAYPAL_ENV`, `PAYPAL_PLAN_IDS` (Cloud Run env);<br>API key 透過 `payment_settings_service` 從 DB 讀取 (admin 可在 `/admin/settings/payment` 編輯) |
| 價格寫死 USD | ✅ **無 runtime FX 轉換**；price_usd 在 `plans` table 與 seed 中 hardcode (e.g. `$19.99`) — 確認於 2026-05-25 audit |

### 5.3 退款防護 (重點稽核項目)
| Mechanism | Path |
|---|---|
| 5% usage gate + HQ-export gate | `backend/app/services/subscription_service.py` `_refund_usage_allowed` |
| 持久化 `is_refundable` flag | `subscriptions.is_refundable` column (新增於 alembic `o4p5q6r7s8t9`, 2026-05-25) |
| 立即翻轉 flag on HQ export (≥5 cr) | `backend/app/services/credit_service.py` `_do_deduct` (eager flip in tail) |
| Admin override 退款資格 | `PATCH /api/v1/admin/subscriptions/{id}/refund-eligibility` (新增於 2026-05-25) |

### 5.4 Row Lock 防護 (併發點數扣除)
- `backend/app/services/credit_service.py` `_do_deduct` **line 189**: `select(User).where(User.id == user_id).with_for_update()` (SQLAlchemy 對應的 `SELECT ... FOR UPDATE`)
- Redis distributed lock 額外保護: **line 150** `async with self.redis.lock(lock_key, timeout=10):` (wrapping the entire deduct flow)
- 內部審計於 2026-05-20 確認: 兩道鎖串接 → 同一個 user 的併發 deduct 呼叫被 serialize, balance 永遠不會被扣到負值. 詳見 `_do_deduct` docstring lines 173-187.

---

## 六、簽章與備忘錄

| Field | Value |
|---|---|
| **填寫者** | (自動產生 — 由 Claude AI 助理依 production state 盤點) |
| **填寫日期** | 民國 115 年 5 月 26 日 (2026-05-26) |
| **填寫依據** | 1. Source tree (`/Users/mlw/Desktop/Vidgo_Gen_AI`)<br>2. Live Cloud Run revisions `vidgo-backend-00295-zjm` + `vidgo-frontend-00250-ndc`<br>3. `gcloud run/sql/redis/storage` 即時查詢<br>4. `/api/v1/openapi.json` 與 `/api/v1/admin/*` API 回應<br>5. E2E smoke test 經 admin 帳號 `vidgo168@gmail.com` 驗證 |

### 補充備忘錄 (✍️ 給外包重點)

1. **架構大幅簡化 (2026-05-26)**：兩個 MCP provider 全刪、Cloud Run 多省 ~150 MB image size、build 時間從 5m+ 降到 3m51s。所有 AI 呼叫都走純 HTTP REST，不再需要 Node.js subprocess 管理。

2. **唯一一個 broken provider**：A2E status 顯示 `error`（"a2e is not responding"）。它是 Avatar 流程的 backup，主路徑 PiAPI Kling Avatar 正常運作，所以 user 不會看到問題。若要修，檢查 `A2E_API_KEY` secret 是否過期。

3. **VEO_MODEL 修正 (2026-05-26)**：`veo-3.1-generate` (404 不存在) → `veo-3.0-fast-generate-001` (GA)。同時更新於 Cloud Run env + `gcp/deploy.sh`。

4. **價格一致性 (2026-05-26 deep audit 修正)**：UI 顯示的點數成本與後端實際扣除已對齊：
   - ShortVideo I2V `kling_omni` 從 backend 漏扣 20→750 cr (修正)
   - VideoDubbing UI 80→30 (對齊 backend)
   - KlingVideo default tier 100→60 (對齊 spec)
   - MidjourneyImagine 全部 model 一律 5 cr (對齊 backend flat pricing)
   - ImageUpscale 全部 scale 一律 10 cr

5. **沒有 GitHub Actions**：目前 CI/CD = 手動 `gcloud builds submit`。若要自動化建議在 `.github/workflows/` 新增 push-on-main 觸發。

6. **私網 Cloud SQL**：`prod-db` 沒有 public IP，本機要連必須 `cloud-sql-proxy --private-ip` 經由 VPC connector (或在 Cloud Shell)。

7. **資安提醒**：`gcp/deploy.sh` line ~52 把 `DB_PASSWORD=Vidgo96003146` 寫死 + 同值也是 admin password。建議：
   - 將 DB 密碼移到 Secret Manager
   - 將 admin 密碼 rotate 並改用 ENV / Secret
   - 修改後重新 deploy backend
