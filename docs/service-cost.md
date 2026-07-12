# VidGo 服務成本與毛利分析

> **2026-07-12 增補（本輪落地）**：Sora 2 拆分為 **std / pro 兩檔 SKU**、`_check_and_deduct_credits` 新增 **per-model 扣點下限**。細節見 §5 新加的「已完成」區。
>
> **2026-06-12 增補**：本文撰寫後，影片計價已改以 `tier_config.py` 的
> `VIDEO_CREDIT_COSTS` 為唯一對照表（hailuo 18 / wan・hunyuan 20 /
> kling_std 28 / seedance_720p・kling_v3_std 65 / veo・**sora2_pro 80**（06-09 新增，
> **sora2_std 30**新增於 07-12）/ kling_v3_pro 130 / seedance_1080p 160），且 `ai_try_on`
> 實際扣點為 **30 點**（前端顯示已同步修正）。其餘分析仍以 2026-06-03 資料為準。

> 產出日期：2026-06-03
> 範圍：目前線上 v2.1 訂閱方案、Credit Pack、所有經過 `_check_and_deduct_credits` 的工具呼叫
> 資料來源：
> - `backend/alembic/versions/g1a2b3c4d5e6_v2_1_pricing_rollout.py`（最新 plan / pack / service_pricing 設定）
> - `backend/app/services/tier_config.py`（fallback 點數表）
> - `backend/app/api/v1/tools.py`（各端點實際呼叫的 `service_type` 與 `CREDIT_COST`）
> - `backend/scripts/seed_service_pricing.py`（每個服務的 `api_cost_usd` 假設值）

---

## 1. 使用者一點 (credit) 實際付多少錢？

| SKU | TWD / 月 | USD / 月 | 點數 | NT$ / 點 | USD / 點 |
|---|---|---|---|---|---|
| Basic (標準版) | 399 | 19.99 | 450 | 0.887 | **0.0444** |
| Pro (專業版) | 999 | 49.99 | 1,200 | 0.833 | **0.0416** |
| Premium (進階版) | 1,699 | 89.99 | 2,200 | 0.772 | **0.0409** |
| heavy_pack | 999 | 32.99 | 1,000 | 0.999 | **0.0330** ← 最便宜 |
| standard_pack | 499 | 16.99 | 450 | 1.109 | 0.0377 |
| light_pack | 299 | 9.99 | 250 | 1.196 | 0.0400 |

**最低營收 / 點 = USD $0.033**（精明的使用者會買 heavy_pack）。
所有毛利計算都應以 **$0.033/點** 當作最壞情境基準。

---

## 2. 雙重計價來源（資料流要點）

`_check_and_deduct_credits()` 的扣點邏輯：

1. **先查 DB**：`service_pricing.credit_cost` WHERE `service_type = ?`
   - 若有列 → 用 DB 值（ops 可在不重新部署的前提下調整，稱為「扣點防火牆」）
2. **找不到 → 退回 hard-coded fallback**
   - `app/api/v1/tools.py` 每個端點頂端的 `CREDIT_COST = N`
   - 或 `tier_config.CREDIT_COSTS[tool_type][model_tier]`

### 重大問題：service_type 對不上 DB 欄位

`tools.py` 傳入的 `service_type` 與 `seed_service_pricing.py` 種子的 key 不一致，導致以下工具**永遠走 fallback**，DB 調整完全無效：

| `tools.py` 用的 service_type | DB 種子裡的 key | 結果 |
|---|---|---|
| `background_removal` | `bg_removal` | ❌ 對不上 |
| `product_scene` | `product_scene_gen` | ❌ 對不上 |
| `upscale` | `image_upscale` | ❌ 對不上 |

這代表：v2.1 migration 雖然把 `image_upscale` 設成 15 點，但實際線上 `upscale` 端點仍走 fallback 10 點。**這是個沉默 bug** — 無 log、無 error。

---

## 3. 每個工具的營收 vs. 上游成本

> **2026-07-12 新增 — 室內設計全系列 + 全屋批次收費**（[interior.py](../backend/app/api/v1/interior.py)，seed 於 `seed_new_pricing_tiers.py`）。**上游成本用 PiAPI 官網實際牌價**（2026-07 查證,來源見下方 §3.0）,不再是估計區間：
>
> | service_type | 扣點 | 營收 (heavy_pack) | 上游實際成本 (PiAPI 牌價) | 毛利 |
> |---|---|---|---|---|
> | `interior_redesign` / `_generate` / `_fusion` / `_edit`(每輪) / `_style_transfer` | 20 | $0.66 | I2I：Flux dev **$0.015** / Nano Banana **$0.03**(依畫質 model) | ✅ **22–44×** |
> | `interior_3d_model` | 150 | $4.95 | Trellis image→3D **$0.04**（固定） | ✅ **124×** |
> | `interior_3d_from_floorplan` | 170 | $5.61 | 渲染 $0.03 + Trellis $0.04 = **$0.07** | ✅ **80×** |
> | `interior_batch_render`(全屋批次) | 20 × 圖數 × 變體數 | 每張 $0.66 | 每張 I2I **$0.015–0.03** | ✅ 每張同 redesign |
> | `interior_house_tour`(全屋影片) | 20 | $0.66 | 本地 ffmpeg（CPU）≈ **$0** | ✅ 近乎純毛利 |
>
> ⚠️ **`interior_batch_render` 絕不可 seed 進 ServicePricing** — 它的扣點傳入的是「算好的總額」(每張價 × 圖數 × 變體數)，seeded 的單價列會用扣點防火牆機制把總額**覆蓋成單張價**。單張價要調就調 `interior_render` 列。

## 3.0 PiAPI 實際牌價參考（2026-07 官網查證,取代先前的估計區間）

> 這些是從 PiAPI 官網/文件抓到的**實際牌價**（非估計）。VidGo 走 PiAPI 為主要 provider,所以這是計算毛利的權威上游成本。來源連結見本節末。

| PiAPI 模型 / 任務 | 實際牌價 | VidGo 用途 |
|---|---|---|
| Flux.1 **schnell** | **$0.002 / 圖** | 預設 T2I/I2I（最便宜） |
| Flux.1 **dev** | **$0.015 / 圖** | 高品質 I2I |
| Flux.1 dev-advanced (**Kontext**) | ≈ dev 級（$0.015+） | room-redesign / interior 編輯 |
| **Qwen Image** | **$0.015 / 圖** | 中文 prompt T2I（程式碼註解已記） |
| **Z-Image** | **$0.004 / 圖** | 最便宜 T2I（程式碼註解已記） |
| **Nano Banana**（Gemini 2.5 Flash Image） | **$0.03 / 圖**（一次最多 4 張） | 高品質室內渲染 / 試衣 prompt 模式 |
| **Trellis** image→3D | **$0.04 / 次** | 3D 模型 |
| **Kling 2.6** 5s 標準 | **$0.20 / 次** | 影片 / 試衣底層 |
| **Kling 2.6** 5s Pro | **$0.33 / 次** | 高階影片 |
| **Seedance 2** 720p | **$0.20/秒**（5s=$1.00） | 主力影片 720p |
| **Seedance 2** 1080p | **$0.50/秒**（5s=$2.50） | 影片 1080p |
| **Seedance 2 fast** 720p | **$0.16/秒** | 快速影片 |
| **Hailuo v2.3** 6s/768p | **$0.23**；10s/768p $0.45；6s/1080p $0.40 | 最便宜影片 |
| **Sora 2** 標準 | **$0.08/秒**（1080p,5s=$0.40） | — |
| **Sora 2 Pro** | **$0.24/秒**（1080p,5s=**$1.20**） | sora2-pro（video_sora2 扣 80 點 ≈ $2.64 營收,✅ 2.2×） |
| 背景去除 / image-toolkit | **$0.001 / 次** | 去背 |
| Host-Your-Account（自帶帳號吃到飽） | $5–10 / seat / 月 | 高量時的替代計價 |

**來源**：[PiAPI Flux API](https://piapi.ai/flux-api)、[Trellis 3D API](https://piapi.ai/trellis-3d-api)、[Kling 2.6](https://piapi.ai/kling-2-6)、[Seedance 2.0](https://piapi.ai/seedance-2-0)、[Hailuo](https://piapi.ai/hailuo)、[Sora 2](https://piapi.ai/sora-2)、[Nano Banana pricing blog](https://piapi.ai/blogs/free-nano-banana-api-pricing-and-key-access-2025-google-gemini-2-5-flash-via-piapi)、[Remove Background API](https://piapi.ai/docs/image-editing-api/remove-background-api)、[PiAPI Pricing](https://piapi.ai/pricing)。牌價會變動,調價前請重新查證。

### a) DB 沒有對應列、走 fallback 的工具（在 `tools.py` 內 hard-coded）

| 來源行 | service_type | fallback 扣點 | 營收 (heavy_pack) | 實際上游成本 | 評估 |
|---|---|---|---|---|---|
| tools.py:1724 | `background_removal` | 3 | $0.10 | $0.02–0.05 | ✅ OK |
| tools.py:2117 | `product_scene` | 10 | $0.33 | $0.04–0.10 | ✅ OK |
| tools.py:2484 | `virtual_try_on` | 15 | $0.50 | Kling try-on $0.50–1.00 | ⚠️ **打平或虧損** |
| tools.py:2851 | `room_redesign` | 20 | $0.66 | Flux/Kontext $0.025–0.04 | ✅ OK |
| tools.py:3613 | `claymation` | 8 / 50 | $0.26 / $1.65 | Kling 5s $0.28–0.70 | ⚠️ 8 點時虧損 |
| tools.py:3838 | `video_background_remove` | 50 | $1.65 | $0.10–0.30 | ✅ OK |
| tools.py:3944 | `upscale` | 10 | $0.33 | $0.05–0.20 | ✅ OK (但 DB 失效) |
| tools.py:4108 | `ai_avatar` | 300 | $9.90 | Kling/A2E $1–3 | ✅ 強健 |
| tools.py:4574 | `video_dubbing` | 30 | $0.99 | A2E $1–3 | ❌ **虧損** |

### b) 走 `tier_config.CREDIT_COSTS` fallback 的工具（默認 v2.0 舊值）

`tier_config.py` 仍保留 v2.0 校正前的舊點數，且檔頭註解寫「1 credit ≈ $0.5 cost」是錯的（實際上游成本只有 $0.003–$0.10）。

| tool_type | default 點 | wan_pro 點 | 營收 (default) | 上游成本 | 評估 |
|---|---|---|---|---|---|
| text_to_image | 1 | 3 | $0.033 | Flux schnell $0.003、Nano Banana Pro $0.10 | ❌ **高階模型虧損** |
| i2i / style_transfer | 1 | 3 | $0.033 | Flux Kontext $0.04 | ❌ **虧損** |
| image_translator | 1 | 3 | $0.033 | Flux + OCR $0.04 | ❌ **虧損** |
| image_to_video | 10 | 30 | $0.33 / $0.99 | Hailuo $0.10、Kling 2.6 $0.28、Kling 2.1-master $0.70 | ❌ **旗艦虧損** |
| text_to_video | 10 | 30 | $0.33 / $0.99 | 同上 | ❌ **旗艦虧損** |
| ai_try_on | 10 | 30 | $0.33 / $0.99 | Kling try-on $0.50–1.00 | ❌ **default 虧損** |
| ai_avatar | 30 | — | $0.99 | A2E/Kling avatar $1–3 | ❌ **虧損** |
| lip_sync | 30 | — | $0.99 | $0.50–2.00 | ⚠️ 打平/虧損 |
| video_dubbing | 30 | — | $0.99 | $0.50–2.00 | ⚠️ 打平/虧損 |
| video_extend | 15 | — | $0.50 | $0.30–1.00 | ⚠️ 打平/虧損 |

### c) DB 有列、v2.1 已校正過的工具（健康）

| service_type | 點數 | 營收 | 種子假設成本 | 評估 |
|---|---|---|---|---|
| text_to_image_default | 1 | $0.033 | $0.015 | ⚠️ 毛利非常薄 |
| image_generation_premium | 5 | $0.165 | $0.05–0.10 | ✅ OK |
| short_video / video_generation_standard | 20 | $0.66 | $0.10–0.30 | ✅ OK |
| video_generation_professional | 60 | $1.98 | $0.40–0.70 | ✅ OK |
| veo3_video | 200 | $6.60 | $0.50 | ✅ 強健 |
| seedance_wan_video | 40 | $1.32 | $0.10 | ✅ 強健 |
| image_upscale | 15 | $0.50 | $0.05–0.20 | ✅ OK（但目前無法觸發，見 §2） |

---

## 4. 漏錢漏在哪（依嚴重度排序）

1. **`ai_avatar` / `ai_try_on` / `lip_sync` / `video_dubbing` default 階層**
   上游 $0.50–$3.00，扣點僅 30 點 ($0.99) 甚至 10 點 ($0.33)。**每筆呼叫皆虧損**。
2. **高品質單張圖片只收 1 點**
   Nano Banana Pro / MJ / Flux Kontext 上游 $0.04–$0.10，營收 $0.033 — **每張負毛利**。
3. **`virtual_try_on` fallback 15 點**
   Kling try-on 是 PiAPI 較貴的端點，營收 $0.50 = 上游下限。
4. **`claymation` 視訊模式 8 點**
   短影片上游 ≥ $0.10，營收 $0.26 — 在 Kling 上虧損。
5. **service_type ↔ DB key 對不上**（見 §2）
   v2.1 的 DB 扣點防火牆對這 3 個工具完全失效，未來想調整也調不到。
6. **heavy_pack 套利空間**
   $0.033/點 比最便宜訂閱還低 17%。重度使用者只會買 pack，使整體營收上限被壓死。
7. **年付方案內建「買十送二」**
   `price_yearly = 10 × price_monthly`，但 `monthly_credits × 12` 全額配給，使年付的 $/點 比月付再低 ~17%，旗艦模型逼近成本價。

---

## 5. 建議修正 — 已完成 vs. 剩餘

### 5.a 已完成（2026-06 到 2026-07 之間陸續落地）

| 項目 | 落地版本 / commit | 驗證方式 |
|---|---|---|
| ✅ **P0-a** `service_type` 命名對不上 DB — bg_removal / product_scene_gen / image_upscale 全數修正 | 2026-06 v2.1 遷移窗口 | [tools.py:2179](../backend/app/api/v1/tools.py#L2179)、[tools.py:2635](../backend/app/api/v1/tools.py#L2635)、[tools.py:5086](../backend/app/api/v1/tools.py#L5086) 已改用正確 key |
| ✅ **P0-b** `tier_config.CREDIT_COSTS` fallback 大幅拉高 | 2026-06 v2.1 → 2026-07 v3.0 | [tier_config.py:97+](../backend/app/services/tier_config.py#L97)：text_to_image `{default:2, premium:3, nano_banana:8, nano_banana_4k:12}`；image_to_video `{default:18, wan_pro:65, veo:80}`；ai_try_on 30/60；ai_avatar 80；lip_sync 50；video_dubbing 60；video_extend 30 |
| ✅ **P1（部分）** heavy_pack 1000→833 點，$32.99 不變 | [f1a2b3c4d5e6](../backend/alembic/versions/f1a2b3c4d5e6_lock_legacy_packs_and_sync_plan_models.py) 遷移 | $0.0396/credit，貼近 Basic 訂閱 $0.0444/credit |
| ✅ **P3（部分）** VidGo 3.0 每模型扣點表 + 官方 `api_cost_usd` 種子 | [j4d5e6f7g8h9](../backend/alembic/versions/j4d5e6f7g8h9_v3_0_credit_table_and_plan_credits.py) | 影像 / 影片 15 列 service_pricing 全部落表，`/admin/costs` 有真實 margin |
| ✅ **室內設計全系列扣點** | [interior batch memory](../.claude/projects/-Users-mlw-Desktop-Vidgo-Gen-AI/memory/interior-batch-whole-house.md) 2026-07-10 | interior_redesign 等固定 20 點、interior_3d_model 150、interior_batch_render 動態 |
| ✅ **Sora 2 SKU 拆分**（本輪落地） | 2026-07-12 (`k7m8n9o0p1q2` migration) | `sora2_std` 30 點 / no-audio / $0.40 上游；`sora2_pro` 80 點 / 含音 / $1.20 上游 — 使用者選 std 不再幫 pro 補貼 |
| ✅ **Per-model 扣點下限**（本輪落地） | 2026-07-12 [tools.py:1090+](../backend/app/api/v1/tools.py#L1090) | `_check_and_deduct_credits` 新增 `model_hint` 參數；任何端點忘記走 `resolve_*_credits` 或未來新增模型分支，都會被 floor guard 抬回真實扣點 + 一則 warning log |

### 5.b 剩餘工作（依 ROI 排序）

**R1 — seed_service_pricing.py 的 `api_cost_usd` 用 §3.0 PiAPI 官方牌價全面重寫（原 P3 收尾）**
本輪已把 15 列影像 / 影片主表校正；`seed_service_pricing.py` 還有一批舊 v2.0 的 `api_cost_usd` 估值沒對齊 PiAPI 現價（Kling 2.6、Sora 2 Pro、Seedance 2 fast、Nano-Banana Pro 3K/4K、Trellis）。同一支腳本一次改完，`/admin/costs` 的 margin 才會全綠。**Idea 5** — 純資料更新，無程式風險。

**R2 — Nano-Banana-Pro try-on 圖片數量硬上限**
`try-on` 已升到 30 點 / $0.99 營收；`nano-banana-pro` 每張 $0.03，multi-image identity guard 若無限增長，5 張圖 → $0.15 → 6.6× → 仍安全。但若 identity guard 迴圈上限沒鎖，$1+ 就打平。**行動**：在 `tools.py` try-on 呼叫端硬編一個 `max_reference_images` 常數（建議 2）。

**R3 — 年付方案「買 10 送 12」隱性折扣（原 P1 尾巴）**
若 `price_yearly = 10 × price_monthly` 且 `monthly_credits × 12` 全額配給，等於 $/credit 再打 ~17% 折。兩擇一：
  - 年配給改為 `monthly_credits × 11`（買 10 送 11）
  - 年價改為 `monthly_price × 11`（10% off，不是 ~17%）
需要動 `plans` 表 + `credit_service.grant_monthly_credits`。

**R4 — Claymation 影片模式 20 點對上 Kling 5s Pro（$0.33）只剩 2× 毛利**
[tools.py:3623](../backend/app/api/v1/tools.py#L3623) 建議調到 25 點，或強制走 Kling std 而非 Pro。單點改動。

**R5 — 損益偵測 cron（新提案）**
Worker 每晚跑一支 job：讀 `service_pricing.credit_cost × 0.033 - api_cost_usd`，任何列 < 0 或 < 2× 就寄一封 admin summary。避免未來出現當年 §2 那種「命名不對就沉默虧錢」的黑洞。與 R1 一起做 ROI 最高。

**R6 — `tier_config.py` 檔頭註解「1 credit ≈ $0.5 cost」清掉**（原 P4）
最小改動、防後人踩雷。

---

## 6. 預估影響（更新）

假設付費使用者使用比例為：圖片 50%、標準影片 35%、avatar/try-on/lip-sync 15%

| 使用者類型 | 2026-06 前 | 2026-07 現況（P0/P1/j4d5 遷移已上） | R1-R6 全部落地後 |
|---|---|---|---|
| 純圖片使用者 | ~$0.15/$1 營收 | ~$0.10 | ~$0.08 |
| 混合使用者 | ~$0.85/$1 營收 | ~$0.55 | ~$0.40 |
| Avatar / 試衣 / lip-sync 重度使用者 | **>$1.20（虧損）** | ~$0.75 | ~$0.60 |
| Sora 2 使用者（本輪新拆） | — | **std 15% / pro 45%**（拆分後兩檔均勻分佈時） | 同左 |

> Avatar 重度使用者的血洞在 2026-06 P0-b 已止住；本輪 Sora 2 SKU 拆分是最後一個「知道的用戶會刻意選貴款」孔洞。

---

## 7. 執行清單

- [x] **P0-a** 修正 3 個 service_type 命名（tools.py 3 行改動）
- [x] **P0-b** 改 `tier_config.CREDIT_COSTS` + `tools.py` 內 `CREDIT_COST` + alembic migration 寫進 `service_pricing`
- [x] **P1（部分）** heavy_pack 縮到 833 點；**年付折扣仍未處理**（見 R3）
- [~] **P2** `TIER_ALLOWED_MODELS` — 2026-07 credits-only 政策上線後這條被替換為「per-model 扣點下限」；已於本輪 [tools.py:1090+](../backend/app/api/v1/tools.py#L1090) 落地
- [x] **本輪** Sora 2 SKU 拆分（migration `k7m8n9o0p1q2`）
- [x] **本輪** `_check_and_deduct_credits` 新增 `model_hint` per-model 扣點下限
- [ ] **R1** 補齊 `seed_service_pricing.py` 的新模型列 + 校正 `api_cost_usd`
- [ ] **R2** try-on multi-image 硬上限（`max_reference_images = 2`）
- [ ] **R3** 年付方案改為買 10 送 11
- [ ] **R4** Claymation 影片扣點 20 → 25，或強制 Kling std
- [ ] **R5** 損益偵測 cron（每晚 admin summary）
- [ ] **R6** 清掉 `tier_config.py` 檔頭「1 credit ≈ $0.5 cost」錯誤註解
- [ ] 驗證：R1 落地後在 `/admin/costs` 上跑一週，確認 `margin_usd` 全綠

---

## 8. 本輪（2026-07-12）落地細節

### 8.1 Sora 2 std / pro SKU 拆分

**動機**：Sora 2 std 上游 $0.40（$0.08 s ×5），Sora 2 Pro 上游 $1.20（$0.24 s ×5）— PiAPI 兩個 task_type 都用 model="sora2"。過去統一 80 點會讓所有 std 使用者付 6.6× 毛利、pro 使用者只付 2.2× 毛利 — 只要「懂的人」都會選 pro，最終 pro 佔比拉高後整體毛利被壓死。

**改動**：
- [`tier_config.VIDEO_CREDIT_COSTS`](../backend/app/services/tier_config.py#L300) — 新增 `sora2_std` (30 credits, $0.40) 與 `sora2_pro` (80 credits, $1.20) 兩列；`sora2` 保留當 pro 別名以維持向下相容（早期分析欄位、front-end 遺留 model_id）。
- [`resolve_video_credits`](../backend/app/services/tier_config.py#L317) — 任何含 `"std"` / `"standard"` 的 sora 型號自動落到 std row。
- [`model_registry.PIAPI_MODELS.sora2_std_task`](../backend/app/core/model_registry.py) — 新增 env `PIAPI_SORA2_STD_TASK` 預設 `sora2-video`（std）；既有 `sora2_task` 仍是 `sora2-pro-video`。
- [`piapi_provider.sora2_video_generation`](../backend/app/providers/piapi_provider.py#L1760) — 接受 `params["mode"] ∈ {"std", "pro"}`；std 強制 `enable_audio=False`。
- [`/api/v1/tools/sora2-pro`](../backend/app/api/v1/tools.py#L6853) — request 新增 `mode: str = "pro"` 欄位（back-compat 預設 pro）；`_sora2_pro_inner` 用 `_mode` 選 billing row、`_model_id`、往下傳 `mode=`。
- [`plan_gates._PLAN_FLOOR_FOR_MODEL`](../backend/app/services/plan_gates.py#L108) — 新增 `sora2_std` 等 4 個 key，設在 `pro` floor（credits-only 政策下實際仍為訂閱通行；只擋 free/demo）。
- [Alembic `k7m8n9o0p1q2_split_sora2_std_pro_pricing.py`](../backend/alembic/versions/k7m8n9o0p1q2_split_sora2_std_pro_pricing.py) — UPSERT `video_sora2_std` 列到 service_pricing。
- 前端 [`Sora2Pro.vue`](../frontend-vue/src/views/tools/Sora2Pro.vue) 新增 std/pro toggle，`displayCost` 隨模式切換 30↔80，std 隱藏 audio toggle 且強制關閉。前端 [`toolsApi.sora2Pro`](../frontend-vue/src/api/tools.ts#L435) 新增 `mode` 參數。

**風險 / 觀察**：既有分析 / history 用 `service_type = "video_sora2"` 追 pro；新的 `video_sora2_std` 是獨立列，pro 歷史行不受影響。若 4/5 位存量用戶已透過 API 自行呼叫此端點且沒帶 `mode`，預設 `pro` 保證不動舊行為。

### 8.2 Per-model 扣點下限（credit floor guard）

**動機**：現行 `_check_and_deduct_credits` 只信任呼叫端傳入的 `amount` + ServicePricing 覆蓋。當呼叫端忘記走 `resolve_*_credits(model_id)`（例如未來新加一個影像端點、或 model 分派邏輯藏在 provider 內部），使用者可能付 default 2 點卻拿到 Nano Banana Pro $0.10 上游。

**改動**：
- [`tools.py:_check_and_deduct_credits`](../backend/app/api/v1/tools.py#L1090) 新增 kwarg `model_hint: Optional[str]`。
- 內部邏輯：`effective_amount = max(effective_amount, resolve_*_credits(model_hint).credits)`。當抬升發生時打一則 `WARNING` 級 log（便於 audit）。
- 已在 [midjourney-imagine](../backend/app/api/v1/tools.py#L6293)、[short-video](../backend/app/api/v1/tools.py#L4195)、[text-to-video](../backend/app/api/v1/tools.py#L6711)、[sora2-pro](../backend/app/api/v1/tools.py#L6899) 四支主熱路徑接上 `model_hint=request.model_id / _model_id / request.model` — 這些端點今天原本就會走 `resolve_*_credits`，`model_hint` 在此扮演 defensive-in-depth。未來新端點只要照這個模式呼叫，就自動有下限保護。

**風險**：`resolve_*_credits` 內部有 fallback 到 hailuo (最便宜)，所以未知 `model_hint` 不會誤抬扣點；只有明確可辨識為高價模型的 hint 才會觸發 floor。已用一組 assertion（本輪 CI-adjacent smoke test）覆蓋 6 個 model id 驗過。
