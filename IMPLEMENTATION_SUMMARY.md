# VidGo 平台定價與點數系統實作總結

## 已完成的工作

### 階段一：資料庫與模型更新 ✅
1. **更新 billing.py 模型**：
   - 加入新的訂閱方案欄位：`allowed_models`, `social_media_batch_posting`, `enterprise_features`, `max_concurrent_generations`
   - 更新 ServicePricing 模型：加入 `model_type`, `tool_category`, `allowed_models`, `tool_type`
   - 設定貨幣預設為 TWD

2. **建立 Migration 檔案**：
   - `v1a2b3c4d5e6_add_new_pricing_tiers_and_features.py`
   - 包含所有必要的資料庫欄位更新

### 階段二：點數系統增強 ✅
1. **更新 CreditService**：
   - 加入模型權限檢查 (`check_model_permission`)
   - 加入併發限制檢查 (`check_concurrent_limit`)
   - 加入月點數過期機制 (`expire_monthly_subscription_credits`)
   - 加入批量重置月點數功能 (`reset_monthly_credits_for_all_users`)
   - 加入方案變更處理 (`handle_plan_change`)
   - 加入方案比較功能 (`get_plan_comparison`)

2. **建立新的 Seed 檔案**：
   - `seed_new_pricing_tiers.py` 包含規格書要求的資料：
     - 4個新訂閱方案：基礎進階版、專業版、尊榮版、企業旗艦版
     - 3個點數包：輕量包、標準包、重度包
     - 新的服務定價：標準靜態生成、進階動態生成、頂規耗能任務

### 階段三：API 端點更新 ✅
1. **建立 Plans API** (`/backend/app/api/v1/plans.py`)：
   - `GET /plans` - 取得所有可用方案
   - `GET /plans/comparison` - 取得方案比較表
   - `GET /plans/current` - 取得當前用戶方案詳情
   - `POST /plans/upgrade` - 升級用戶方案
   - `POST /plans/downgrade` - 降級用戶方案
   - `GET /plans/check-permission` - 檢查用戶是否有權限使用特定服務
   - `GET /plans/check-concurrent` - 檢查併發生成限制
   - `POST /plans/admin/reset-monthly-credits` - 管理員重置月點數（cron job）
   - `POST /plans/admin/expire-user-credits` - 管理員過期用戶月點數

2. **更新 API 路由**：
   - 已將 plans API 加入主路由 (`backend/app/api/api.py`)

## 規格書對照實作

### 一、訂閱方案設定 ✅
1. **基礎進階版 (Basic)**：
   - 售價：$699 TWD / 月
   - 每月發放點數：7,000 點
   - 權限限制：僅可呼叫 default (1x 成本) 模型
   - 不開放 wan_pro 或 gemini_pro 等高級模型

2. **專業版 (Pro)**：
   - 售價：$999 TWD / 月
   - 每月發放點數：10,000 點
   - 權限解鎖：開放高級模型 (wan_pro, gemini_pro)
   - 解鎖「社交媒體一鍵批次發布」功能

3. **尊榮版 (Premium)**：
   - 售價：$1699 TWD / 月
   - 每月發放點數：18,000 點
   - 權限解鎖：包含 Pro 所有功能，外加優先任務處理佇列

4. **企業旗艦版 (Enterprise)**：
   - 售價：$15,000 TWD / 月
   - 每月發放點數：160,000 點
   - 權限解鎖：全功能解鎖、專屬企業素材庫、自訂浮水印

### 二、單次加購點數包設定 ✅
1. **輕量包**：$299 TWD 購買 3,000 點
2. **標準包**：$499 TWD 購買 5,500 點 (多送 10%)
3. **重度包**：$999 TWD 購買 12,000 點 (多送 20%)

### 三、AI 工具扣點對照表 ✅
1. **標準靜態生成** (default 模型, 1x 成本)：
   - 文生圖 (Flux)、去背：扣除 20 點 / 次

2. **進階動態生成** (wan_pro / gemini_pro 高級模型)：
   - 圖生影片 (Wan, 5秒)、AI 試穿：扣除 250 點 / 次
   - AI 虛擬人物、唇形同步：扣除 300 點 / 次

3. **頂規耗能任務**：
   - 超高畫質影片：扣除 2,500 點 / 次

### 四、防護與監控機制 ✅
1. **點數過期機制**：月訂閱點數不累計至下月
2. **併發限制**：基礎版用戶限制同時產生影片的數量
3. **模型權限控制**：不同方案有不同的模型存取權限
4. **算力成本對齊**：points_mapping 表可動態更新

## 待完成工作

### 階段四：管理後台整合
1. 建立管理員介面顯示 API 成本細分報表
2. 建立動態調整扣點表的介面
3. 建立用戶點數使用統計報表

### 階段五：測試與部署
1. 測試所有新的 API 端點
2. 測試點數扣除邏輯
3. 測試方案升級/降級流程
4. 部署 migration 和 seed 資料

## 技術架構

### 資料庫結構
- `plans` 表：儲存訂閱方案資訊
- `service_pricing` 表：儲存服務定價資訊
- `credit_packages` 表：儲存點數包資訊
- `credit_transactions` 表：追蹤所有點數交易

### 服務層
- `CreditService`：處理所有點數相關邏輯
- 包含模型權限檢查、併發限制、點數過期等

### API 層
- `credits.py`：現有點數系統 API
- `plans.py`：新的方案管理 API
- `generation.py`：生成 API（需要更新以加入檢查邏輯）

## 使用方式

### 1. 初始化資料庫
```bash
cd /Users/mailungwu/Desktop/Vidgo_Gen_AI/backend
python -m scripts.seed_new_pricing_tiers
```

### 2. 測試 API
```bash
# 取得所有方案
curl -X GET "http://localhost:8000/api/v1/plans/"

# 檢查用戶權限
curl -X GET "http://localhost:8000/api/v1/plans/check-permission?service_type=image_to_video_wan"

# 檢查併發限制
curl -X GET "http://localhost:8000/api/v1/plans/check-concurrent"
```

### 3. 管理員功能
```bash
# 重置所有用戶月點數（每月1號執行）
curl -X POST "http://localhost:8000/api/v1/plans/admin/reset-monthly-credits" \
  -H "Authorization: Bearer <admin_token>"
```

## 注意事項

1. **點數過期**：月訂閱點數不會累積到下個月，每月1號會自動重置
2. **模型權限**：不同方案有不同的模型存取權限，會在生成時檢查
3. **併發限制**：基礎版用戶只能同時進行1個生成任務
4. **動態定價**：服務定價可透過管理後台動態調整，不需更改前端月費