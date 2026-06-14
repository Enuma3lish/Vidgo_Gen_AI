# VidGo 服務成本與毛利分析

> **2026-06-12 增補**：本文撰寫後，影片計價已改以 `tier_config.py` 的
> `VIDEO_CREDIT_COSTS` 為唯一對照表（hailuo 18 / wan・hunyuan 20 /
> kling_std 28 / seedance_720p・kling_v3_std 65 / veo・**sora2 80**（06-09 新增，
> Sora 2 Pro）/ kling_v3_pro 130 / seedance_1080p 160），且 `ai_try_on`
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

## 5. 建議修正（P0 → P4）

### P0：止血（必做、可一週內完成）

**P0-a. 修正 `service_type` 命名對不上 DB 的 bug**
`backend/app/api/v1/tools.py`：

```python
# tools.py:1724
"background_removal" → "bg_removal"

# tools.py:2117
"product_scene" → "product_scene_gen"

# tools.py:3944
"upscale" → "image_upscale"
```

否則 v2.1 的 DB 扣點防火牆永遠摸不到這 3 個工具。

**P0-b. 拉高 `tier_config.CREDIT_COSTS` 的 fallback 並同步寫進 DB**

| tool_type | default 舊 → 新 | premium 舊 → 新 | 備註 |
|---|---|---|---|
| text_to_image | 1 → 1 | 3 → 5 | premium = MJ / Nano Banana Pro / Kontext |
| i2i / style_transfer | 1 → 2 | 3 → 5 | |
| image_translator | 1 → 2 | 3 → 5 | |
| image_to_video | 10 → 20 | 30 → 60 | premium = Kling 旗艦 |
| text_to_video | 10 → 20 | 30 → 60 | |
| ai_try_on | 10 → 30 | 30 → 60 | |
| ai_avatar | 30 → 80 | — | A2E/Kling avatar 上游 $1–3 |
| lip_sync | 30 → 50 | — | |
| video_dubbing | 30 → 60 | — | |
| video_extend | 15 → 30 | — | |

調整後 `tools.py` 內各 `CREDIT_COST = N` hard-code 也要同步，並寫一支 alembic migration 把這些值寫入 `service_pricing` 表（同時補上對應 `api_cost_usd` 以利 admin dashboard 毛利計算）。

### P1：縮窄 pack 套利空間

- `heavy_pack` 1,000 點 / NT$999 → **850 點 / NT$999**（NT$1.175/點，USD $0.0388/點）
  讓 pack 不再比訂閱便宜；高用量者改回買訂閱、訂閱用戶可靠 breakage（未用完）保毛利。
- 或 → **保持 1,000 點，但漲價到 NT$1,199**
- 年付方案：要嘛改成 11 月（不是 10 月）的折扣、要嘛年配給縮為 `monthly_credits × 11`。

### P2：把 default tier 強制路由到便宜的上游模型

`provider_router` 已支援 tier-based parameter override，只差「明確的 model whitelist」。

- Free / Basic 的 `image_to_video` default → 強制走 Hailuo fast 或 Seedance fast（上游 ~$0.10），**絕不**碰 Kling 2.1-master。
- 旗艦（Kling 2.1-master、Veo 3.1、Nano Banana Pro）只能透過明確選 `wan_pro` / `veo` / `premium` 階層才能呼叫；對應扣點走 §P0-b 的高階表。
- 在 `TIER_ALLOWED_MODELS` 中強化：`free / basic` → 只能 `["default"]`，且 `default` 在 provider_router 內被映射為「最便宜的可用上游」。

### P3：修正 admin dashboard 的 api_cost_usd 假設

`backend/scripts/seed_service_pricing.py` 的 `api_cost_usd` 是 v1.0 時代的舊估，且**完全沒涵蓋** Nano Banana、Seedance、Hailuo、Veo、Hunyuan、Z-Image、Qwen Image、Kling 2.6 / 3.0 (Omni) 等新模型。

- 為新模型補列 `service_pricing` 種子（含 `api_cost_usd`）。
- 每季根據 PiAPI / Pollo / Vertex 帳單對齊一次。
- 否則 `/admin/costs` 的 `margin_usd` 完全失真，看不出在虧錢。

### P4：清理過時註解 / 文件

- `tier_config.py` 檔頭註解寫「1 credit ≈ $0.5 cost」，是 v2.0 制定前的想像值，**請改寫成實際 PiAPI 報價**，否則下一位接手者會以為定價已經有 10× 毛利、再加碼下調。
- `docs/vidgo-project-supplement.md` 內的 credit_cost 範例應一併校正。

---

## 6. 預估影響

假設付費使用者使用比例為：圖片 50%、標準影片 35%、avatar/try-on/lip-sync 15%

| 使用者類型 | 目前每 $1 營收的成本 | P0 + P1 + P2 後 |
|---|---|---|
| 純圖片使用者 | ~$0.15 | ~$0.10 |
| 混合使用者 | ~$0.85 | ~$0.45 |
| Avatar 重度使用者 | **>$1.20（虧損）** | ~$0.70 |

> **Avatar 重度使用者**是目前最大血洞，P0 一做完就能止血。

---

## 7. 執行清單

- [ ] **P0-a** 修正 3 個 service_type 命名 (`tools.py` 3 行改動)
- [ ] **P0-b** 改 `tier_config.CREDIT_COSTS` + `tools.py` 內 `CREDIT_COST` + alembic migration 寫進 `service_pricing`
- [ ] **P1** 改 `credit_packages` 表（migration）+ 年付 credits 計算
- [ ] **P2** 在 `provider_router` 增加 tier-based model whitelist；free/basic 不可觸發旗艦
- [ ] **P3** 補齊 `seed_service_pricing.py` 的新模型列 + 校正 `api_cost_usd`
- [ ] **P4** 改寫 `tier_config.py` 檔頭註解
- [ ] 驗證：在 `/admin/costs` 上跑一週，確認 `margin_usd` 為正
