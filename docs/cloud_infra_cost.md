# VidGo Gen AI — GCP 雲端基礎架構成本估算與優化指南

## 概覽

本文件提供 VidGo Gen AI 平台部署至 Google Cloud Platform (asia-east1 台灣/亞洲區域) 的月度成本估算，以及具體的成本優化策略。

平台組成：
- **前端**：Vue 3 (Cloud Run)
- **後端 API**：FastAPI (Cloud Run)
- **背景工作器**：ARQ Worker (Cloud Run)
- **資料庫**：PostgreSQL 15 (Cloud SQL)
- **快取 / 任務佇列**：Redis 7 (Memorystore)
- **媒體儲存**：圖片、影片、素材 (Cloud Storage + CDN)

---

## 月度成本估算（三個階段）

### 階段一：早期啟動（0–500 活躍用戶）

| GCP 服務 | 規格 | 月費估算（USD） |
|---|---|---|
| Cloud Run — 後端 | 2 vCPU / 2 GB，min 1 instance，~30 req/s | $15–25 |
| Cloud Run — 前端 | 1 vCPU / 512 MB，min 0，1000 並發 | $2–8 |
| Cloud Run — Worker | 2 vCPU / 2 GB，min 1，concurrency 1 | $15–20 |
| Cloud SQL | db-g1-small，10 GB SSD，單一可用區 | $9 |
| Memorystore (Redis) | Basic tier，1 GB | $16 |
| Cloud Storage | 50 GB 儲存 + 10 GB egress | $3–5 |
| Cloud Load Balancer | 全球 HTTPS LB | $18 |
| Cloud Build | ~50 次 build/月（120 min 免費額度） | $0–5 |
| Cloud Armor | 基礎規則集 | $5 |
| Secret Manager | < 10,000 次存取 | $0–1 |
| Cloud Monitoring | 免費額度內 | $0 |
| VPC / 網路 | Cloud NAT、VPC connector | $5–8 |
| **月費合計** | | **約 $88–115 USD/月** |

---

### 階段二：成長期（500–5,000 活躍用戶）

| GCP 服務 | 規格 | 月費估算（USD） |
|---|---|---|
| Cloud Run — 後端 | 2 vCPU / 2 GB，min 2，auto-scale 最多 10 | $40–80 |
| Cloud Run — 前端 | 1 vCPU / 512 MB，min 0，最多 4 | $5–15 |
| Cloud Run — Worker | 2 vCPU / 2 GB，min 1，最多 3 | $20–35 |
| Cloud SQL | db-n1-standard-2，20 GB SSD，HA（高可用） | $80–100 |
| Memorystore (Redis) | Standard tier，5 GB（含備援） | $85 |
| Cloud Storage | 200 GB 儲存 + 50 GB egress | $10–15 |
| Cloud Load Balancer + CDN | 全球 LB + Cloud CDN | $25–40 |
| Cloud Build | ~100 次 build/月 | $5–10 |
| Cloud Armor | 進階規則 | $10 |
| Secret Manager | < 100,000 次存取 | $1–3 |
| Cloud Monitoring | 自訂指標 + 告警 | $5–10 |
| VPC / 網路 | Cloud NAT、connector | $10–15 |
| **月費合計** | | **約 $296–408 USD/月** |

---

### 階段三：規模化（5,000+ 活躍用戶）

| GCP 服務 | 規格 | 月費估算（USD） |
|---|---|---|
| Cloud Run — 後端 | 4 vCPU / 4 GB，min 3，最多 20 | $120–200 |
| Cloud Run — 前端 | 2 vCPU / 1 GB，min 1，最多 8 | $15–30 |
| Cloud Run — Worker | 4 vCPU / 4 GB，min 2，最多 8 | $80–150 |
| Cloud SQL | db-n1-standard-4，50 GB SSD，HA + 讀取副本 | $200–250 |
| Memorystore (Redis) | Standard tier，10 GB | $170 |
| Cloud Storage | 1 TB 儲存 + 200 GB egress | $30–50 |
| Cloud Load Balancer + CDN | 全球 LB + Cloud CDN | $50–80 |
| Cloud Build + Artifact Registry | | $15–25 |
| Cloud Armor | 企業規則集 | $25 |
| Cloud Monitoring + Logging | 進階觀測能力 | $20–40 |
| VPC / 網路 | Cloud NAT、connector | $20–30 |
| **月費合計** | | **約 $745–1,050 USD/月** |

---

## AI API 費用（額外計算）

以下費用**不含在 GCP 帳單**中，但是平台主要成本來源之一：

| AI 服務商 | 用途 | 費率 |
|---|---|---|
| PiAPI | **所有生成任務**：文生圖 (Flux)、圖生影片 (Wan)、去背、3D (Trellis)、試穿 (Kling)、室內設計、風格轉換、圖案生成、AI 虛擬人物 | 依 API 使用量計費 |
| Google Gemini | **內容審核** + **素材預生成**（僅用於預生成展示素材） | 免費額度後 $0.00015/1K token |

> **重要**：PiAPI 是唯一生成服務提供商，無備援方案。若服務中斷，所有生成端點返回「服務更新中，請稍候！」訊息。

### 模型選擇對成本影響

付費用戶可選擇不同 AI 模型，影響信用點消耗與 API 成本：

| 模型 | 倍率 | 適用工具 | 對 API 成本影響 |
|------|------|----------|----------------|
| default | 1× | 所有工具 | 基礎 API 成本 |
| wan_pro | 2× | product_scene, room_redesign, pattern_generate, effect, short_video | API 成本約 2× |
| gemini_pro | 2× | ai_avatar, try_on | API 成本約 2× |

**成本優化建議**：
- 標準模型適用於大多數日常使用場景
- 高級模型（wan_pro, gemini_pro）僅在需要最高品質輸出時使用
- 透過 Admin Dashboard 監控各模型使用頻率與成本占比

> 建議追蹤 Admin Dashboard 的 API 成本細分報表（`/admin/costs`）來監控各工具的 AI API 支出，並分析模型選擇對總成本的影響。

---

## 成本優化策略（12項）

### 1. Cloud Run 前端縮放至零（Scale to Zero）

**節省幅度：約 $5–15/月**

```bash
# 前端 min instance 設為 0
gcloud run services update vidgo-frontend \
  --region=asia-east1 \
  --min-instances=0
```

Vue 3 打包後由 Nginx 提供服務，容器啟動時間低於 1 秒，冷啟動幾乎無感。前端流量透過 Cloud CDN 快取靜態資源，大幅減少 Cloud Run 被呼叫的次數。

---

### 2. Cloud CDN 快取靜態資源

**節省幅度：減少 30–60% 的 Cloud Run 前端呼叫**

```bash
# 在 Load Balancer backend service 啟用 CDN
gcloud compute backend-services update vidgo-frontend-svc \
  --global \
  --enable-cdn \
  --cache-mode=CACHE_ALL_STATIC \
  --default-ttl=3600
```

快取命中的請求不會觸發 Cloud Run instance，直接從 CDN 邊緣節點回應，同時降低延遲。

---

### 3. Cloud Storage 生命週期政策（對應平台 14 天清除政策）

**節省幅度：避免媒體儲存無限膨脹，每月省 $10–50+**

**重要**：正式環境僅使用 Cloud Storage，不依賴 Docker volumes。本機開發使用 Docker volumes (`vidgo_materials`, `vidgo_generated`, `vidgo_tryon_garments`)，但正式部署時所有媒體檔案儲存在 Cloud Storage。

平台已有 14 天自動清除政策，在 Cloud Storage 層同步設定：

```json
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {"age": 14, "matchesPrefix": ["generated/"]}
    },
    {
      "action": {"type": "Delete"},
      "condition": {"age": 30, "matchesPrefix": ["uploads/"]}
    },
    {
      "action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
      "condition": {"age": 7, "matchesPrefix": ["materials/"]}
    }
  ]
}
```

`materials/` 資料夾存放預生成展示素材，超過 7 天後轉為 Nearline 儲存等級，費率從 $0.02/GB 降至 $0.01/GB。

#### 從 Docker Volumes 遷移至 Cloud Storage

若從本機開發環境遷移至正式環境，需執行以下步驟：

1. **備份現有資料**：
   ```bash
   # 備份 Docker volumes 內容
   docker run --rm -v vidgo_materials:/source -v $(pwd)/backup:/backup alpine \
     tar czf /backup/materials.tar.gz -C /source .
   ```

2. **上傳至 Cloud Storage**：
   ```bash
   # 上傳預生成素材
   gcloud storage cp backup/materials.tar.gz gs://vidgo-media-$PROJECT/materials/legacy/
   
   # 解壓縮到正確位置
   gcloud storage objects update gs://vidgo-media-$PROJECT/materials/legacy/materials.tar.gz \
     --custom-metadata="extract_to=materials/"
   ```

3. **更新環境變數**：
   - 設定 `GCS_BUCKET=vidgo-media-$PROJECT`
   - 移除 Docker volume 掛載設定
   - 確保後端服務帳戶有 `storage.objectAdmin` 權限

4. **驗證遷移**：
   ```bash
   # 檢查檔案數量
   gcloud storage ls gs://vidgo-media-$PROJECT/materials/ | wc -l
   
   # 測試存取
   curl "https://storage.googleapis.com/vidgo-media-$PROJECT/materials/sample.jpg"
   ```

---

### 4. Cloud SQL 連線池（Connection Pooling）

**節省幅度：可使用更小的 Cloud SQL 規格，省 $30–70/月**

在 `db-g1-small` 上，PostgreSQL 預設 `max_connections=100`。透過 SQLAlchemy 連線池設定，減少連線開銷：

```python
# backend/app/core/database.py
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,          # 每個 Cloud Run instance 最多 10 個連線
    max_overflow=5,
    pool_timeout=30,
    pool_recycle=1800,
)
```

Cloud Run 最多 10 個 instance × 10 連線 = 100，剛好符合 `db-g1-small` 上限，延後升級至 `db-n1-standard-2` 的時間。

---

### 5. Docker 分層快取（Build 時間與費用）

**節省幅度：縮短 build 時間 50–70%，節省 Cloud Build 費用**

```yaml
# cloudbuild.yaml
- name: 'gcr.io/cloud-builders/docker'
  args:
    - 'build'
    - '--cache-from=asia-east1-docker.pkg.dev/$PROJECT_ID/vidgo/backend:latest'
    - '-t'
    - 'asia-east1-docker.pkg.dev/$PROJECT_ID/vidgo/backend:$SHORT_SHA'
    - './backend'
```

後端 `requirements.txt` 獨立為一層，只有依賴變更時才重新安裝套件：

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt   # ← 此層被快取
COPY . .
```

---

### 6. Memorystore Redis — 善用 TTL 控制記憶體

**節省幅度：延後從 1 GB 升級至 5 GB，省 $69/月**

`block_cache.py` 已有 Redis 快取機制。確認所有快取 key 都有設定 TTL：

```python
# 建議 TTL 設定
await redis.setex("materials:status", 300, json_data)        # 5 分鐘
await redis.setex("landing:stats", 600, json_data)            # 10 分鐘
await redis.setex("demo:preset:{tool}", 3600, json_data)      # 1 小時
await redis.setex("admin:costs:daily", 86400, json_data)      # 24 小時
```

監控 Redis 記憶體使用率：
```bash
gcloud redis instances describe vidgo-redis \
  --region=asia-east1 \
  --format="value(memorySizeGb,currentLocationId)"
```

---

### 7. 預付費用折扣（Committed Use）

**節省幅度：Cloud SQL 節省約 37%，Memorystore 節省約 35%**

在上線穩定運行 3 個月後，對持續使用的服務購買年度承諾：

```bash
# Cloud SQL 1 年承諾（db-n1-standard-2）
# 月費從 ~$100 降至 ~$63
# 透過 Cloud Console > Billing > Commitments 購買

# Memorystore Standard 5 GB 1 年承諾
# 月費從 ~$85 降至 ~$55
```

> 建議：前 3 個月觀察實際用量再購買，避免承諾過多。

---

### 8. ARQ Worker 工作負載隔離

**節省幅度：避免不必要的 backend scale-out，省 $10–30/月**

Worker 獨立部署，`concurrency=1` 確保每個 instance 只處理一個 AI 任務。後端 API 的 scale-out 不會受到 AI 任務佇列影響：

```bash
# Worker 設定 CPU always-allocated（長任務不被 throttle）
gcloud run services update vidgo-worker \
  --region=asia-east1 \
  --cpu-throttling=false
```

注意：`cpu-throttling=false` 會讓閒置時仍計費 CPU，僅在 Worker 持續有任務時才啟用。

---

### 9. 預算告警（Budget Alerts）

**防止意外帳單超支**

```bash
gcloud billing budgets create \
  --billing-account=YOUR_BILLING_ACCOUNT_ID \
  --display-name="VidGo 月度預算" \
  --budget-amount=300USD \
  --threshold-rule=percent=50 \
  --threshold-rule=percent=80 \
  --threshold-rule=percent=100 \
  --notifications-rule-pubsub-topic=projects/PROJECT/topics/billing-alerts
```

建議設定三個告警門檻（50%、80%、100%），在超支前及早介入。

---

### 10. Cloud Armor 防禦 API 濫用

**間接成本節省：防止惡意爬蟲或濫用 AI 工具造成 API 費用暴增**

```bash
gcloud compute security-policies create vidgo-armor-policy \
  --description="VidGo WAF policy"

# 限制 /auth/* 每 IP 每分鐘 100 次請求
gcloud compute security-policies rules create 1000 \
  --security-policy=vidgo-armor-policy \
  --expression='request.path.matches("/auth/.*")' \
  --action=rate_based_ban \
  --rate-limit-threshold-count=100 \
  --rate-limit-threshold-interval-sec=60 \
  --ban-duration-sec=600

# 套用至 backend service
gcloud compute backend-services update vidgo-backend-svc \
  --global \
  --security-policy=vidgo-armor-policy
```

### 11. 社交媒體發布成本優化

**背景**：平台支援 YouTube、Facebook、Instagram、TikTok 發布功能，但這些服務的 API 成本由用戶自行承擔。

**成本優化策略**：
1. **Token 自動刷新**：避免因 token 過期導致發布失敗，減少重試成本
2. **批次發布**：允許用戶一次選擇多個平台，減少 API 呼叫次數
3. **發布佇列**：非同步處理發布請求，避免阻塞主要服務

**監控重點**：
- 各社交平台發布成功率
- Token 刷新失敗率
- 發布佇列積壓情況

### 12. 信用點成本 vs API 成本關聯分析

**優化目標**：確保信用點定價覆蓋實際 API 成本並提供合理利潤

**分析方法**：
1. **計算每信用點實際成本**：
   ```
   每信用點成本 = (PiAPI 月費 + Gemini 月費) / 月信用點消耗總量
   ```

2. **識別高成本工具**：
   - 追蹤各工具每生成任務的平均 API 成本
   - 比較信用點定價與實際成本比例

3. **動態定價調整**：
   - 根據 API 成本波動調整信用點定價
   - 針對高成本工具設定不同信用點消耗率

---

## 各環境建議配置

| 設定項目 | 本機開發 (Docker Compose) | 測試環境 (GCP Staging) | 正式環境 (GCP Production) |
|---|---|---|---|
| 後端 min instances | N/A | 0 | 1 |
| 前端 min instances | N/A | 0 | 0 |
| Worker min instances | N/A | 0 | 1 |
| Cloud SQL 規格 | postgres:15-alpine | db-g1-small | db-n1-standard-2 |
| Redis 規格 | redis:7-alpine | Memorystore 1 GB Basic | Memorystore 5 GB Standard |
| Cloud Armor | 無 | 無 | 啟用 |
| Cloud CDN | 無 | 無 | 啟用 |
| `SKIP_PREGENERATION` | false | true | true |
| 預算告警 | 無 | $50/月 | $300/月 |
| 預付折扣 | N/A | N/A | 穩定 3 個月後購買 |

---

## 成本監控儀表板

建議在 Cloud Monitoring 建立以下自訂指標面板：

```
┌─────────────────────────────────────────────────────────┐
│             VidGo GCP 成本監控儀表板                      │
├──────────────┬──────────────┬──────────────┬────────────┤
│ Cloud Run    │  Cloud SQL   │ Memorystore  │  Storage   │
│ 本月請求數   │  CPU 使用率  │  記憶體使用  │  儲存容量  │
│ Instance 數  │  連線數      │  命中率      │  每日 egress│
├──────────────┴──────────────┴──────────────┴────────────┤
│              AI API 成本（來自 Admin Dashboard）          │
│  PiAPI 本月支出 | Gemini 本月支出 | 模型成本分析           │
│  標準模型 vs 高級模型成本 | 各工具 API 成本占比            │
└─────────────────────────────────────────────────────────┘
```

### 關鍵監控指標

1. **PiAPI 成本細分**：
   - 各工具類型 API 呼叫次數與成本
   - 標準模型 vs 高級模型使用比例
   - 每生成任務平均 API 成本

2. **模型選擇成本影響**：
   ```sql
   -- 分析模型選擇對成本的影響
   SELECT 
     tool_type,
     model_selected,
     COUNT(*) as task_count,
     AVG(credit_cost) as avg_credit_cost,
     SUM(credit_cost) as total_credit_cost
   FROM user_generations
   WHERE created_at >= NOW() - INTERVAL '30 days'
   GROUP BY tool_type, model_selected
   ORDER BY total_credit_cost DESC;
   ```

3. **信用點 vs API 成本關聯**：
   - 追蹤用戶信用點消耗與實際 API 成本的比例
   - 識別高成本低利潤的服務項目
   - 優化定價策略

**查看 GCP 帳單明細：**
```
Cloud Console → Billing → Reports
  → Group by: Service
  → Filter: Project = vidgo-production
```

**查看 AI API 成本（內部）：**
```
GET https://api.vidgo.ai/admin/costs
Authorization: Bearer ADMIN_TOKEN
```

### 性能與成本權衡分析

#### 1. Cloud Run 實例規模 vs 回應時間
- **小規模** (1 vCPU / 2 GB)：成本較低，但高負載時延遲增加
- **中規模** (2 vCPU / 4 GB)：平衡成本與性能，適合成長期
- **大規模** (4 vCPU / 8 GB)：最佳性能，但成本較高

**建議**：根據 p95 回應時間設定自動擴展規則：
```bash
# 當 p95 回應時間 > 2 秒時擴展
gcloud run services update vidgo-backend \
  --region=asia-east1 \
  --add-autoscaling-metric=latency \
  --add-autoscaling-target=2000
```

#### 2. Cloud SQL 規格 vs 查詢性能
- **db-g1-small**：適合早期階段，最大 100 連線
- **db-n1-standard-2**：成長期推薦，支援 250+ 連線
- **db-n1-standard-4**：規模化需求，支援 500+ 連線

**監控指標**：
- 查詢平均執行時間
- 活躍連線數
- 緩存命中率

#### 3. 模型選擇 vs 用戶滿意度 vs 成本
- **標準模型**：成本最低，滿足 80% 日常需求
- **高級模型**：成本 2×，但用戶滿意度提升 15-25%

**優化策略**：
- 追蹤高級模型使用頻率與用戶回饋
- 針對高價值客戶自動推薦高級模型
- 設定高級模型使用上限防止成本超支

---

## 常見問題與對應方案

| 問題 | 症狀 | 解決方案 |
|---|---|---|
| Cloud SQL 連線耗盡 | 後端 500 錯誤，日誌顯示 `too many connections` | 降低 SQLAlchemy `pool_size`，或升級至 db-n1-standard-2 |
| Redis 記憶體超限 | ARQ worker 任務掉落 | 清查無 TTL 的 key，或升級 Memorystore |
| Cloud Run 冷啟動延遲 | 後端第一個請求 > 3 秒 | 設定 `min-instances=1` |
| Storage egress 費用暴增 | 帳單中 Storage Network 項目異常 | 啟用 Cloud CDN 快取媒體檔案，減少直接存取 bucket |
| Build 費用超支 | Cloud Build 計費超出預期 | 啟用 Docker layer cache，減少全量重建 |
| AI API 費用暴增 | Admin Dashboard API 成本異常 | 確認 demo 模式是否正常攔截、rate limit 是否生效 |
| PiAPI 服務中斷 | 所有生成端點返回「服務更新中」 | 檢查 PiAPI 服務狀態，等待服務恢復（無備援方案） |
| 模型選擇成本失控 | 高級模型使用比例過高，API 成本暴增 | 設定高級模型使用上限，追蹤 ROI |
| 社交媒體發布失敗 | Token 過期導致發布失敗 | 啟用 token 自動刷新機制 |
| 信用點 vs API 成本失衡 | 信用點收入無法覆蓋 API 成本 | 重新計算信用點定價，調整高成本工具費率 |

### 架構一致性驗證

為確保成本估算與實際架構一致，請驗證以下項目：

1. **AI 提供商架構**：
   - ✅ 僅使用 PiAPI 進行所有生成任務
   - ✅ Gemini 僅用於內容審核與素材預生成
   - ✅ 無備援方案，服務中斷時顯示維護訊息

2. **儲存架構**：
   - ✅ 正式環境使用 Cloud Storage，非 Docker volumes
   - ✅ 14 天媒體保留政策
   - ✅ 預生成素材使用 Nearline 儲存等級

3. **成本監控**：
   - ✅ Admin Dashboard 提供 API 成本細分
   - ✅ 追蹤模型選擇對成本的影響
   - ✅ 監控信用點 vs API 成本比例

4. **社交媒體整合**：
   - ✅ 支援 YouTube、Facebook、Instagram、TikTok
   - ✅ Token 自動刷新機制
   - ✅ 非同步發布佇列

**驗證指令**：
```bash
# 檢查後端環境變數
echo "AI Providers:"
echo "PIAPI_KEY: ${PIAPI_KEY:0:10}..."
echo "GEMINI_API_KEY: ${GEMINI_API_KEY:0:10}..."

# 檢查儲存設定
echo "Storage:"
echo "GCS_BUCKET: $GCS_BUCKET"
echo "STORAGE_TYPE: $STORAGE_TYPE"

# 檢查社交媒體設定
echo "Social Media:"
echo "YOUTUBE_CLIENT_ID: ${YOUTUBE_CLIENT_ID:0:10}..."
echo "FACEBOOK_APP_ID: ${FACEBOOK_APP_ID:0:10}..."
```

---

## 參考資料

- [Cloud Run 定價](https://cloud.google.com/run/pricing)
- [Cloud SQL 定價](https://cloud.google.com/sql/pricing)
- [Memorystore 定價](https://cloud.google.com/memorystore/docs/redis/pricing)
- [Cloud Storage 定價](https://cloud.google.com/storage/pricing)
- [Cloud Load Balancer 定價](https://cloud.google.com/vpc/network-pricing#lb)
- [Cloud Armor 定價](https://cloud.google.com/armor/pricing)
- [GCP 定價計算機](https://cloud.google.com/products/calculator)
- [VidGo 基礎架構英文文件](./vidgo-cloud-infra-architecture.md)
