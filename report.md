# 模型版本同步策略報告（PiAPI / Pollo）

> 狀態：v1 已實作（Option A 中央化模型登錄表）
> 撰寫日期：2026-05-15
> 範圍：`backend/app/core/model_registry.py` 與所有 PiAPI / Pollo provider
> 舊版報告已封存為 [report.previous.md](report.previous.md)

---

## 1. 摘要

> **「PiAPI 今天上 Kling 4，我們網站還在 Kling 3，能不能自動同步？」**

**結論：能做到「30 秒內手動切換」，但目前不建議「完全自動拉取最新版」。**
本次已完成中央化模型登錄表（model registry）+ 環境變數覆寫機制；
未來若要往「全自動同步」推進，需要面對下方第 4 節列出的三個風險。

---

## 2. 為什麼我們無法 100% 自動同步？

### 2.1 PiAPI / Pollo 沒有提供「列出當前可用模型」的 API
經過實際盤點：

| 廠商 | 模型清單 API | 自動發現的可行性 |
|------|--------------|------------------|
| PiAPI | ❌ 不存在 | 只能讀官網 HTML 文件 |
| Pollo (REST) | ❌ 不存在 | 端點是 `/{vendor}/{model-slug}` 硬路徑 |
| Pollo (MCP) | 只列 tool 名（`text2video_kling-v2`） | 版本後綴需從 tool 名 parse |

也就是說，沒有一個官方端點告訴我們「你呼叫 `kling` 這個 alias，
今天會被路由到 v3 還是 v4」。

### 2.2 廠商的 alias 行為不一致
- PiAPI 的 `"model": "kling"` 是 **server-side alias**：他們可能在
  某次部署後把它指到 v4，也可能繼續指 v3，毫無公告。
- Pollo 則是 **顯式版本字串**：`pixverse_v4.5` 與 `pixverse_v5`
  是兩個不同 endpoint，呼叫端必須明示。

### 2.3 大版本升級幾乎都帶 breaking changes
歷史上 Kling v1 → v2 改了：
- `aspectRatio` 接受值（從 `16:9, 9:16` 加入 `1:1, 4:3`）
- `duration` 從固定 5/10 秒改成 enum
- 部分回傳欄位重新命名

如果做「夜間自動 promote」，PiAPI 上線 Kling v4 的當下，
我們的 prod 會在沒有人值守的情況下開始打到新模型，輸入欄位可能
被 reject、回傳格式可能 parse 失敗，**直接造成全站該工具掛掉**。
比「使用者多等一天才用上新版」嚴重很多。

---

## 3. 本次實作（Option A — 中央化登錄表 + env 覆寫）

### 3.1 新檔案
- [backend/app/core/model_registry.py](backend/app/core/model_registry.py)
  集中所有 PiAPI / Pollo 的模型 ID，每個欄位都用
  `os.environ.get(<KEY>, <default>)` 包起來。

### 3.2 改動的呼叫端
| 檔案 | 改動 |
|------|------|
| [backend/app/providers/piapi_provider.py](backend/app/providers/piapi_provider.py) | Kling 影片特效、Try-On、Avatar、Lip-Sync、Trellis v1/v2 全部改讀 `PIAPI_MODELS` |
| [backend/app/providers/pollo_provider.py](backend/app/providers/pollo_provider.py) | `_normalize_model` 預設值改用 `POLLO_MODELS["pixverse_default"]` |
| [backend/app/providers/pollo_mcp_provider.py](backend/app/providers/pollo_mcp_provider.py) | `DEFAULT_VIDEO_MODEL` 改用 `POLLO_MODELS["mcp_default_video"]` |
| [backend/app/services/pollo_ai.py](backend/app/services/pollo_ai.py) | 函式預設參數改用 `DEFAULT_MODEL` 常數 |
| [backend/app/services/generation/pollo_service.py](backend/app/services/generation/pollo_service.py) | 同上 |
| [backend/app/api/v1/uploads.py](backend/app/api/v1/uploads.py) | V2V 短影片預設模型改用 registry |
| [backend/.env.example](backend/.env.example) | 新增 11 個註解掉的 `PIAPI_*` / `POLLO_*` 環境變數範例 |

### 3.3 操作流程（升級 Kling 3 → 4 的 SOP）
1. PiAPI 公告新模型可用、確認 API 文件中要求的欄位。
2. 在本機 `.env` 設 `PIAPI_KLING_AVATAR_MODEL=kling-v4`，跑一次煙霧測試。
3. 通過後在 GCP Cloud Run 設定相同環境變數（或寫入 Secret Manager）。
4. `gcloud run services update vidgo-backend --region asia-east1 --update-env-vars PIAPI_KLING_AVATAR_MODEL=kling-v4` 觸發 rolling restart（**不需要重新打 image**）。
5. 觀察 Cloud Logging 的 5xx 率與成功率 30 分鐘。
6. 若失常，將 env 改回原值再 `update` 一次，**30 秒內可回滾**。

> 與舊作法相比：以前要 grep 程式碼 → 改 4 個檔案 → 重 build image → 部署，
> 約需 15–30 分鐘且不可即時回滾。

---

## 4. 為什麼「不再加自動拉取」是有意識的決定？

### 風險 A：靜默上線新版會踩到 schema breaking change
見 §2.3。除非我們同時建立「相容性測試矩陣 + 自動 schema 偵測」，
否則自動 promote 等同把生產環境當測試環境。

### 風險 B：偵測手段只剩爬官網文件
- PiAPI 文件是動態目錄樹，每次改版 selector 就壞掉。
- 違反 robots.txt 風險。
- 每天打一次 LLM 來 diff 文件 ≈ 月成本 USD$5–10，但訊號品質不穩定。

### 風險 C：自動 dry-run 探測會花錢、也會誤觸限流
若改成「每日對 `kling-v3 / kling-v4 / kling-v5` 發試打 request 看 200 vs 400」：
- 即使最小請求，每模型每天成本約 USD$0.01–0.03。
- 容易被 PiAPI 視為異常流量觸發 429，影響真實使用者。

---

## 5. 未來路線圖（如果真的要做「半自動同步」）

| 階段 | 動作 | 風險 | 預估投入 |
|------|------|------|----------|
| **v1（已完成）** | 中央 registry + env 覆寫 | 低 | 已完成 |
| v1.1 | 把 `model_registry` 改讀 PostgreSQL `model_registry` 表 + Redis 快取 1h，運維可在 admin panel 改 | 低 | 0.5 天 |
| v2 | 加 Cloud Scheduler 每日通知（不變更）：對候選新版本送 1 token dry-run，若回 200 就開 Slack 告警給工程師審核 | 中 | 1 天 |
| v3 | 自動 PR：偵測到新版即在 GitHub 自動開 PR 改 `.env` 預設並附上 schema diff，仍需人工 merge | 中高 | 2–3 天 |
| v4 | 真自動 promote（不建議） | 高 | — |

> 個人建議停在 **v2**：得到「新版上線通知」的好處，但永遠保留人類最後一道閘門。

---

## 6. 已知的可立即收益

完成 v1 後：
1. **緊急回滾時間** 從 ~20 分鐘降到 ~30 秒。
2. **A/B 測試**：可同時在不同 Cloud Run revision 跑不同模型，比較成功率與成本。
3. **多區域差異化**：例如台灣站 pin `kling_v2`，海外站試 `kling_v3`。
4. **降低 build pipeline 噪音**：模型升級不再產生 commit history。

---

## 7. 驗收清單

- [x] `backend/app/core/model_registry.py` 提供 `PIAPI_MODELS` / `POLLO_MODELS`。
- [x] 所有先前 hard-coded `"kling"` / `"pixverse_v4.5"` / `"pollo-v1-6"` 改為從 registry 讀取。
- [x] `.env.example` 提供完整覆寫範例。
- [x] Lint / Type 檢查通過（`get_errors` 0 errors）。
- [ ] 部署後抽測 RoomRedesign / ShortVideo / VirtualTryOn 三條鏈，確保預設模型仍正確（**待下次部署回歸**）。

---

## 附錄：可覆寫的環境變數一覽

```bash
# PiAPI
PIAPI_KLING_EFFECTS_MODEL=kling
PIAPI_KLING_TRYON_MODEL=kling
PIAPI_KLING_AVATAR_MODEL=kling
PIAPI_KLING_LIPSYNC_MODEL=kling
PIAPI_TRELLIS_V1_MODEL=Qubico/trellis
PIAPI_TRELLIS_V2_MODEL=Qubico/trellis2

# Pollo
POLLO_PIXVERSE_DEFAULT_MODEL=pixverse_v4.5
POLLO_PIXVERSE_CREATIVE_MODEL=pixverse_v5
POLLO_KLING_VIDEO_MODEL=kling_v2
POLLO_MCP_DEFAULT_MODEL=pollo-v1-6
```
