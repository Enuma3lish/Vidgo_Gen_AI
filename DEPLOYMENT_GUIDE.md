# VidGo 新定價系統部署指南

## 部署步驟

### 1. 資料庫遷移
```bash
cd /Users/mailungwu/Desktop/Vidgo_Gen_AI/backend

# 執行 migration
alembic upgrade head

# 如果 alembic 不可用，使用以下命令：
python -m alembic upgrade head
# 或
uv run alembic upgrade head
```

### 2. 初始化新定價資料
```bash
cd /Users/mailungwu/Desktop/Vidgo_Gen_AI/backend

# 執行新的 seed 腳本
python -m scripts.seed_new_pricing_tiers

# 或使用 uv
uv run python -m scripts.seed_new_pricing_tiers
```

### 3. 驗證部署
```bash
# 測試 API 端點
curl -X GET "http://localhost:8000/api/v1/plans/"
curl -X GET "http://localhost:8000/api/v1/plans/comparison"
curl -X GET "http://localhost:8000/api/v1/credits/pricing"
```

## 新功能說明

### 1. 訂閱方案 (4個層級)
- **基礎進階版 (Basic)**: $699 TWD/月, 7,000 點, 僅限 default 模型
- **專業版 (Pro)**: $999 TWD/月, 10,000 點, 開放高級模型
- **尊榮版 (Premium)**: $1699 TWD/月, 18,000 點, 優先佇列
- **企業旗艦版 (Enterprise)**: $15,000 TWD/月, 160,000 點, 全功能解鎖

### 2. 點數包 (3種)
- **輕量包**: $299 TWD 購買 3,000 點
- **標準包**: $499 TWD 購買 5,500 點 (多送 10%)
- **重度包**: $999 TWD 購買 12,000 點 (多送 20%)

### 3. AI 工具扣點對照表
- **標準靜態生成**: 20 點/次 (文生圖、去背)
- **進階動態生成**: 250-300 點/次 (圖生影片、AI試穿、虛擬人物)
- **頂規耗能任務**: 2,500 點/次 (超高畫質影片)

## API 端點

### Plans API (`/api/v1/plans/`)
- `GET /` - 取得所有可用方案
- `GET /comparison` - 取得方案比較表
- `GET /current` - 取得當前用戶方案詳情
- `POST /upgrade` - 升級用戶方案
- `POST /downgrade` - 降級用戶方案
- `GET /check-permission` - 檢查模型權限
- `GET /check-concurrent` - 檢查併發限制

### Credits API (`/api/v1/credits/`)
- `GET /balance` - 取得點數餘額
- `GET /transactions` - 取得交易記錄
- `GET /packages` - 取得可用點數包
- `POST /purchase` - 購買點數包
- `GET /pricing` - 取得服務定價表

## 防護機制

### 1. 點數過期機制
- 月訂閱點數不累計至下月
- 每月1號自動重置所有用戶點數
- 使用 `reset_monthly_credits_for_all_users()` 方法

### 2. 併發限制
- 基礎版: 1個同時生成任務
- 專業版: 3個同時生成任務
- 尊榮版: 5個同時生成任務
- 企業版: 10個同時生成任務

### 3. 模型權限控制
- 基礎版: 僅限 default 模型
- 專業版以上: 開放 wan_pro, gemini_pro 模型
- 企業版: 額外開放 sora 模型

## 管理員功能

### 1. 重置月點數 (Cron Job)
```bash
# 每月1號 00:00 執行
curl -X POST "http://localhost:8000/api/v1/plans/admin/reset-monthly-credits" \
  -H "Authorization: Bearer <admin_token>"
```

### 2. 動態調整定價
- 透過管理後台調整 `service_pricing` 表
- 即時生效，不需重啟服務

### 3. 用戶點數管理
- 查看用戶點數使用情況
- 手動調整用戶點數餘額
- 強制過期用戶點數

## 前端整合建議

### 1. 方案選擇頁面
- 顯示4個方案的比較表
- 突出顯示每個方案的特點
- 提供升級/降級按鈕

### 2. 點數購買頁面
- 顯示3種點數包
- 顯示優惠資訊 (多送10%/20%)
- 整合金流支付

### 3. 使用限制提示
- 當用戶嘗試使用未授權的模型時顯示錯誤
- 當達到併發限制時顯示等待訊息
- 當點數不足時顯示購買提示

## 監控與報表

### 1. API 成本細分報表
- 追蹤每個服務的 API 成本
- 計算毛利率
- 識別高成本服務

### 2. 用戶使用統計
- 各方案用戶數
- 點數消耗趨勢
- 熱門服務排行

### 3. 系統健康檢查
- 併發使用情況
- 點數餘額分布
- 模型使用頻率

## 故障排除

### 1. Migration 失敗
```sql
-- 手動檢查資料庫欄位
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'plans';

-- 手動新增缺少的欄位
ALTER TABLE plans ADD COLUMN allowed_models JSON DEFAULT '["default"]';
ALTER TABLE plans ADD COLUMN max_concurrent_generations INTEGER DEFAULT 1;
```

### 2. Seed 資料錯誤
```bash
# 清除舊的 seed 資料
DELETE FROM plans WHERE name IN ('basic', 'pro', 'premium', 'enterprise');
DELETE FROM credit_packages WHERE name IN ('light_pack', 'standard_pack', 'heavy_pack');

# 重新執行 seed
python -m scripts.seed_new_pricing_tiers
```

### 3. API 端點無法存取
```bash
# 檢查 API 路由
curl -X GET "http://localhost:8000/docs"  # 查看 Swagger UI

# 檢查日誌
tail -f /var/log/vidgo/backend.log
```

## 效能優化建議

### 1. 快取方案資料
```python
# 使用 Redis 快取方案比較表
redis_key = "plans:comparison"
cached = await redis.get(redis_key)
if not cached:
    comparison = await credit_service.get_plan_comparison()
    await redis.setex(redis_key, 3600, json.dumps(comparison))
```

### 2. 批次處理點數過期
```python
# 使用批次更新減少資料庫負載
UPDATE users 
SET subscription_credits = 0 
WHERE current_plan_id IS NOT NULL 
  AND plan_expires_at < NOW();
```

### 3. 監控併發限制
```python
# 使用 Redis 計數器實時監控
redis_key = f"concurrent:{user_id}:count"
current = await redis.incr(redis_key)
await redis.expire(redis_key, 300)  # 5分鐘過期
```

## 安全注意事項

### 1. 權限驗證
- 所有 API 端點都需要身份驗證
- 管理員功能需要 superuser 權限
- 模型權限檢查在服務層執行

### 2. 點數扣除原子性
- 使用 Redis 分散式鎖
- 確保點數扣除的原子性
- 防止重複扣除

### 3. 金流整合安全
- 使用 HTTPS 加密傳輸
- 驗證支付回調簽名
- 記錄所有支付交易

## 聯絡支援

如有問題，請聯絡：
- 技術支援: tech@vidgo.com
- 系統管理員: admin@vidgo.com
- 緊急聯絡: +886-2-1234-5678