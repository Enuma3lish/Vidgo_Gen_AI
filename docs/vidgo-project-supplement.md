# VidGo Gen AI — 計畫補充說明

---

## 一、商業價值與 API 完善開發策略

### 1.1 商業價值

**核心商業模式：AI 算力路由 × 信用點數經濟**

VidGo 的商業價值不僅在於提供 AI 影片生成服務，更在於其**動態算力路由（Dynamic Compute Routing）**機制——根據使用者願意支付的信用點數，自動分配對應品質的 AI 模型進行生成。此機制具體帶來以下商業效益：

| 商業面向 | 說明 |
|----------|------|
| **差異化定價** | 同一功能提供 Standard / Kling v2 / Luma Ray2 等多層模型，信用消耗倍率從 1× 到 3×，讓用戶依預算自選，擴大付費覆蓋率 |
| **邊際成本遞減** | 免費用戶瀏覽預生成內容（PRESET 模式），不消耗 API 成本；付費用戶才觸發真實 API，確保每筆收入皆高於邊際成本 |
| **訂閱 + 點數雙軌收入** | 訂閱制提供穩定現金流，點數包（Starter / Standard / Premium）提供彈性高消費通路，降低客戶流失敏感度 |
| **推薦裂變成長** | 推薦人獲得 50 點、新用戶獲得 20 點，形成低成本病毒式獲客機制 |
| **跨境電商切入** | 10 大 AI 工具全面覆蓋電商視覺生產需求（商品去背、場景合成、試穿、室內設計、短影片、Avatar），對中小型電商賣家有強烈降本吸引力 |

**市場規模估算**

- 全球電商賣家數量逾 2,600 萬（Shopify 2024），視覺製作是最大痛點之一
- AI 內容生成 SaaS 市場預計 2027 年達 1,847 億美元（Grand View Research）
- 台灣電商及直播電商市場年成長率逾 15%，是初期落地的理想驗證市場

---

### 1.2 如何開發出完善功能的 API

VidGo 後端採用 **FastAPI + ARQ 非同步任務佇列 + Redis** 架構，已具備完整 API 骨架（20 個路由模組）。以下為使 API 達到生產完善等級的關鍵開發路徑：

#### (1) API 閘道與路由層強化

```
用戶請求 → API Gateway（速率限制 / 認證）
         → 路由決策引擎（信用點數 × 工具類型 → 選定 AI Provider）
         → 任務佇列（ARQ / Redis）
         → AI Provider（PiAPI / Pollo / A2E / Gemini）
         → 非同步回調 → 結果儲存 → Webhook 通知用戶
```

#### (2) 模型路由決策引擎設計

```python
# 路由決策邏輯示意
def route_model(tool: str, user_credits: int, user_preference: str) -> AIProvider:
    model_tiers = MODEL_REGISTRY[tool]  # 從 /api/v1/models 動態載入
    affordable = [m for m in model_tiers if m.credit_cost <= user_credits]
    if user_preference in affordable:
        return user_preference
    return affordable[-1]  # 回退至最高可負擔模型
```

- 模型清單維護於 `/api/v1/models` 端點，支援熱更新
- 每個 AI Provider 均實作統一介面（Provider Abstraction Layer），新增模型只需新增 Provider 類別

#### (3) API 完善化的具體里程碑

| 階段 | 目標 | 關鍵功能 |
|------|------|----------|
| **MVP（已完成）** | 10 工具上線、付費牆、信用系統 | PRESET + REAL-API 雙模式、Paddle 金流 |
| **穩定化** | SLA 99.5%、全面錯誤處理 | Circuit Breaker、Provider 自動 Failover、全域 retry 策略 |
| **平台化** | 開放 B2B API | API Key 管理、用量計費、Webhook、OpenAPI SDK 自動生成 |
| **生態化** | 第三方整合 | Zapier / Make 連接器、Shopify App、LINE 官方帳號 Bot |

---

## 二、技術創新性說明

### 2.1 服務創新之外的技術創新

本計畫在技術層面具備以下實質創新，並非單純服務整合：

#### (1) 多 Provider 動態 Failover 引擎

系統對每個 AI 工具維護主備 Provider 清單，當主 Provider 回應異常（HTTP 5xx、逾時、配額耗盡）時，由路由引擎自動切換至備用 Provider，全程對用戶透明。此機制需解決：

- **結果格式統一化**：不同 Provider 回傳的 JSON 結構、媒體 URL 格式各異，需實作格式轉換層
- **異步任務狀態同步**：主備切換後需確保任務 ID 一致性，避免用戶端輪詢錯誤
- **成本感知路由**：Failover 時同時考量備用 Provider 的 API 單價，避免成本爆增

範例：Room Redesign 工具以 Gemini 2.5 Flash 為主、PiAPI Wan 為備；Video 工具以 PiAPI Wan 為主、Pollo AI 為備。

#### (2) 三步驟商品場景合成 Pipeline

Product Scene 功能非直接呼叫 T2I API，而是自研三步驟 Pipeline：

```
步驟 1：背景移除（PiAPI Flux / rembg）→ 透明底商品圖
步驟 2：場景生成（PiAPI Wan T2I）→ 純場景背景圖
步驟 3：PIL 合成（本地計算）→ 精確對齊商品與場景，保留邊緣細節
```

此 Pipeline 解決了直接用 I2I 生成商品場景時「商品外觀失真」的常見問題，是電商場景下的技術突破。

#### (3) 雙模式架構（PRESET / REAL-API）的工程創新

PRESET 模式不只是快取，而是在服務啟動時執行批次預生成腳本，將真實 AI 輸出作為示範素材，並疊加浮水印。此設計解決了：

- **冷啟動展示問題**：新用戶立即看到高品質示範，無需等待
- **API 成本隔離**：免費流量零 AI API 成本，大幅降低 CAC 對應的邊際費用
- **品質一致性**：示範素材為真實模型輸出，非靜態設計稿，真實反映付費效果

#### (4) 信用點數精算引擎

信用扣除在任務派發前（HTTP 402 預檢）即發生，並設計**任務失敗退款機制**，確保用戶不因 Provider 端失敗而損失點數。此為分散式系統下的事務一致性問題，需搭配 Redis 分散式鎖與 PostgreSQL 事務確保冪等性。

---

## 三、與國內外競品之比較分析

### 3.1 主要競品比較

| 比較維度 | **VidGo Gen AI** | **Runway ML** | **Pika Labs** | **Adobe Firefly** | **Canva AI** | **國內：Pixso AI / 鴻海 FIDO** |
|----------|-----------------|---------------|---------------|-------------------|--------------|-------------------------------|
| **目標用戶** | 電商賣家、中小企業 | 影視創作者 | 短影音創作者 | Adobe 生態用戶 | 設計師、行銷人員 | 設計師、企業內部 |
| **核心場景** | 電商視覺全流程 | 專業影片生成 | 短影片特效 | 圖像生成、廣告素材 | 設計範本 + AI | 設計協作 + AI 輔助 |
| **多模型路由** | **是（核心特色）** | 否（自有模型） | 否（自有模型） | 否（Adobe 模型） | 否 | 否 |
| **電商專用工具** | **10 項（去背、試穿、3D 等）** | 無 | 無 | 部分（去背） | 部分（去背） | 無 |
| **定價彈性** | **點數制 + 多模型分層** | 訂閱制（高單價） | 訂閱制 | CC 訂閱捆綁 | Freemium | 企業授權 |
| **亞洲本地化** | **繁中 / 日 / 韓 / 英 / 西** | 英文為主 | 英文為主 | 多語（非重點） | 多語 | 繁中 |
| **Avatar / 口播** | **A2E.ai 亞洲臉孔優化** | 無 | 無 | 無 | 無 | 無 |
| **API 開放性** | 規劃中（B2B） | 開放 API | 無開放 API | Creative Cloud API | 無 | 無 |
| **部署方式** | Docker 自部署 + 雲端 | 純雲端 SaaS | 純雲端 SaaS | 純雲端 SaaS | 純雲端 SaaS | 雲端 SaaS |

### 3.2 核心差異化優勢

1. **電商垂直深度**：競品多為通用 AI 工具，VidGo 是少數從電商痛點出發、整合去背→試穿→3D→短影片→Avatar 完整鏈路的平台
2. **亞洲市場優先**：繁中、日、韓語系、亞洲臉孔 Avatar 優化，Runway / Pika 的英語用戶體驗難以直接滿足台日韓電商需求
3. **彈性算力分層**：其他競品單一模型定價，VidGo 的多模型路由讓中小賣家能以低成本試用，高需求用戶再升級，付費轉換率更高
4. **自部署可能性**：Docker 架構允許企業客戶私有化部署，滿足資料主權需求（特別是日、韓企業市場）

### 3.3 競品弱點與 VidGo 切入機會

| 競品弱點 | VidGo 切入策略 |
|----------|---------------|
| Runway / Pika 高月費（$35–$95/月）讓小賣家望而卻步 | 點數制低門檻，試用零成本（40 點新用戶贈點） |
| Adobe 需整個 CC 訂閱生態才能用 AI 功能 | 單一平台涵蓋電商所需全部 AI 工具，無需切換 |
| 競品均無虛擬試穿 × 亞洲模特整合 | Kling AI 試穿 + 亞洲模特圖庫，直接服務時尚電商 |
| 競品無推薦裂變機制 | 推薦獎勵形成社群口碑，降低 CAC |

---

## 四、應對 AI 模型快速迭代的策略

### 4.1 架構層面：Provider Abstraction Layer

VidGo 後端已採用 Provider 抽象層設計（`backend/app/providers/`），每個 AI 服務商實作統一介面：

```python
class BaseProvider:
    async def generate(self, task: GenerationTask) -> GenerationResult: ...
    async def poll_status(self, task_id: str) -> TaskStatus: ...
    async def get_result(self, task_id: str) -> MediaResult: ...
```

新增模型只需：
1. 新增一個 Provider 類別繼承 `BaseProvider`
2. 在 `/api/v1/models` 模型登錄表中加入新模型的 credit 倍率與參數
3. 在對應工具的路由配置中加入新模型選項

**無需修改前端、業務邏輯或資料庫 Schema**，最快可在數小時內完成新模型上線。

### 4.2 模型評估與淘汰機制

| 機制 | 說明 |
|------|------|
| **A/B 測試框架** | 新模型上線後以 5–10% 流量進行影子測試，收集品質評分與用戶留存數據 |
| **品質基準測試集** | 維護標準測試提示詞集（每工具 20 組），新模型上線前自動跑基準測試並與現有模型比較 |
| **成本監控儀表板** | Admin 後台實時顯示各 Provider 的 API 成本 / 任務數 / 成功率，及時發現性能退化 |
| **模型版本管理** | 每個模型保留版本號，舊模型不立即下架而是降低流量比例，確保進行中任務不受影響 |

### 4.3 供應商多元化策略（避免單一 Provider 依賴）

```
影片生成：PiAPI Wan（主）→ Pollo AI（備）→ Luma Ray2（高品質選項）
圖像生成：PiAPI Flux（主）→ Google Gemini（備）
室內設計：Gemini 2.5 Flash（主）→ PiAPI Wan T2I（備）
試穿效果：Kling AI / PiAPI（主）→ 備援待接入
```

當任一 Provider 推出更優模型，VidGo 可同時維持舊 Provider 穩定性並將新模型作為「進階選項」推出，用戶自行選擇。

### 4.4 開源模型的本地化部署路徑

隨著開源模型（如 Wan 2.1、CogVideoX、LTX-Video）品質逐漸逼近閉源 API，VidGo 規劃以下本地化路徑：

| 時間軸 | 策略 |
|--------|------|
| 近期 | 持續使用 API 服務，專注業務驗證 |
| 中期 | 針對使用量最大的工具（去背、T2I），評估自建推理節點的 ROI |
| 長期 | 高頻低成本工具自建 GPU 節點，降低邊際成本；高複雜度工具繼續使用 API |

### 4.5 社群與情報監控

- 持續追蹤 Hugging Face、Papers With Code、AI 廠商 Release Note
- 與 PiAPI、Pollo、A2E 等 Provider 保持商務合作關係，取得 Beta 模型優先測試資格
- 用戶回饋系統（作品庫評分、客服工單）作為模型品質的市場訊號

---

## 總結

VidGo Gen AI 的核心競爭力在於三個層面的協同：

1. **服務創新**：為電商垂直市場設計的 10 工具一站式 AI 視覺生產平台
2. **技術創新**：多 Provider 動態路由、Failover 引擎、三步驟商品合成 Pipeline、雙模式架構的工程實現
3. **商業創新**：算力路由 × 點數分層定價，讓同一平台服務從小賣家到企業客戶的全客群

面對 AI 模型快速迭代的挑戰，VidGo 以 Provider Abstraction Layer 作為技術護城河，將「模型更換成本」從系統重構降低至單一 Provider 類別的新增，確保平台能在模型競賽中持續提供最具性價比的生成品質。


