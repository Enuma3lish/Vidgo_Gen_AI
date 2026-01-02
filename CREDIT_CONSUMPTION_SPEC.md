# VidGo AI - 點數消耗規格文件

> 版本：2.0.0  
> 最後更新：2024年12月28日

---

## 目錄

1. [概述](#概述)
2. [訂閱方案](#訂閱方案)
3. [點數消耗表](#點數消耗表)
4. [API 成本對照](#api-成本對照)
5. [點數加值包](#點數加值包)
6. [快取節省機制](#快取節省機制)
7. [計費規則](#計費規則)
8. [技術實作規格](#技術實作規格)

---

## 概述

VidGo AI 採用**週期點數制計費系統**，所有 AI 服務均以點數計價。**訂閱點數每週一 00:00 UTC 重置**。

### 版本 2.0 重大變更

| 項目 | v1.0 (舊) | v2.0 (新) |
|------|-----------|-----------|
| 點數週期 | 每月重置 | **每週重置** |
| Starter 點數 | 100/月 | **25/週** |
| Pro 點數 | 250/月 | **60/週** |
| Pro+ 點數 | 500/月 | **125/週** |
| GoEnhance 品牌 | GoEnhance | **VidGo Effects** |
| GoEnhance 權限 | 所有用戶 | **僅訂閱用戶** |
| 影片/圖像生成 | 多服務 | **僅 Leonardo AI** |
| Pollo AI | 啟用 | **未來功能** |
| 帳號驗證 | 連結驗證 | **6 位數驗證碼** |

### 設計原則

| 原則 | 說明 |
|------|------|
| **透明定價** | 每個操作明確標示點數消耗 |
| **週期控制** | 每週重置確保穩定使用 |
| **白標服務** | 所有外部 API 以 VidGo 品牌呈現 |
| **訂閱分級** | VidGo Effects 僅限付費訂閱用戶 |
| **3倍利潤率** | 主要服務維持 3x API 成本的售價 |
| **快取優先** | 相似提示詞可免費使用快取結果 |
| **備援機制** | Leonardo 不可用時切換至 Runway |

---

## 訂閱方案

### 方案比較表（週點數制）

| 方案 | 月費 | 每週點數 | 加購折扣 | 最高解析度 | VidGo Effects |
|------|------|----------|----------|------------|---------------|
| **Demo** | $0 | 2 次（一次性） | — | 720p + 浮水印 | ❌ 無法使用 |
| **Starter** | NT$299 | 25 pts | 標準價格 | 1080p | ✅ 可使用 |
| **Pro** | NT$599 | 60 pts | 9折 | 4K | ✅ 可使用 |
| **Pro+** | NT$999 | 125 pts | 8折 | 4K 60fps | ✅ 可使用 |

### 點數單價計算（以週為單位）

| 方案 | 每週點數 | 月費 | 點數單價 |
|------|----------|------|----------|
| Starter | 25 pts × 4週 = 100 pts | NT$299 | NT$2.99/pt |
| Pro | 60 pts × 4週 = 240 pts | NT$599 | NT$2.50/pt |
| Pro+ | 125 pts × 4週 = 500 pts | NT$999 | NT$2.00/pt |

### 週點數重置時間

```
每週一 00:00 UTC（台灣時間 08:00）
┌─────────────────────────────────────────┐
│  週一    週二    週三    週四    週五    週六    週日  │
│   ↑                                               │
│ 重置                                              │
│                                                   │
│  Starter: 25 pts                                 │
│  Pro:     60 pts                                 │
│  Pro+:   125 pts                                 │
└─────────────────────────────────────────┘
```

---

## 點數消耗表

### 白標服務對照表

| 使用者看到的名稱 | 內部服務 | API 提供者 |
|------------------|----------|------------|
| VidGo Video 720p | leonardo_video_720p | Leonardo AI |
| VidGo Video 1080p | leonardo_video_1080p | Leonardo AI |
| VidGo Video 4K | leonardo_video_4k | Leonardo AI |
| VidGo Image | leonardo_image | Leonardo AI |
| VidGo Style Effects | goenhance_style | GoEnhance |
| VidGo HD Enhance | goenhance_4k | GoEnhance |
| VidGo Video Pro | goenhance_video | GoEnhance |
| VidGo Advanced Models | pollo_* | Pollo AI（未來） |

### 影片生成服務（Leonardo AI）

| 服務名稱 | 解析度 | 長度 | 點數消耗 | 平台成本 | 利潤率 | 權限 |
|----------|--------|------|----------|----------|--------|------|
| **VidGo Video 720p** | 720p | 8秒 | 5 pts | ~$0.05 | 3.0x | 全部 |
| **VidGo Video 1080p** | 1080p | 8秒 | 8 pts | ~$0.08 | 3.0x | Starter+ |
| **VidGo Video 4K** | 4K | 8秒 | 12 pts | ~$0.12 | 3.0x | Pro+ |
| **Runway 備援** | 720p | 8秒 | 15 pts | ~$0.50 | 0.9x | 內部 |

### 圖像生成服務（Leonardo AI）

| 服務名稱 | 解析度 | 點數消耗 | 平台成本 | 利潤率 | 權限 |
|----------|--------|----------|----------|--------|------|
| **VidGo Image** | 512x512 | 2 pts | ~$0.015 | 4.0x | 全部 |
| **VidGo Image HD** | 1024x1024 | 3 pts | ~$0.025 | 3.6x | 全部 |
| **VidGo Image Pro** | 1536x1536 | 5 pts | ~$0.04 | 3.8x | Pro+ |

### VidGo Effects（僅訂閱用戶）

| 服務名稱 | 說明 | 點數消耗 | 平台成本 | 利潤率 | 權限 |
|----------|------|----------|----------|--------|------|
| **VidGo Style Effects** | 藝術風格轉換 | 8 pts | ~$0.15 | 1.6x | 訂閱用戶 |
| **VidGo HD Enhance** | 圖像放大至 4K | 10 pts | ~$0.20 | 1.5x | 訂閱用戶 |
| **VidGo Video Pro** | 影片品質增強 | 12 pts | ~$0.25 | 1.4x | 訂閱用戶 |

> ⚠️ **重要**：VidGo Effects 不開放給 Demo 用戶使用

### 已移除的功能

以下 GoEnhance 功能**不包含**在 VidGo 中：
- ❌ AI ASMR
- ❌ AI Dance
- ❌ Character Animation
- ❌ GoEnhance Animate

### 輔助服務（免費）

| 服務 | 說明 | 點數消耗 |
|------|------|----------|
| **Gemini 提示詞優化** | AI 優化使用者提示詞 | 0 pts |
| **Gemini 內容審核** | 檢查不當內容 | 0 pts |
| **快取命中** | 相似度 >85% 使用快取 | 0 pts |

---

## API 成本對照

### Leonardo AI API

| 操作 | API Credits | USD 成本 | 說明 |
|------|-------------|----------|------|
| Phoenix Image (512px) | 7 credits | $0.011 | 基礎圖像生成 |
| Phoenix Image (1024px) | 15 credits | $0.024 | 高解析度圖像 |
| Motion SVD (8秒 720p) | 30 credits | $0.048 | 圖像轉影片 |
| Motion SVD (8秒 1080p) | 50 credits | $0.080 | 高畫質影片 |
| Motion SVD (8秒 4K) | 75 credits | $0.120 | 超高畫質影片 |

> **計算基準**：Pro API Plan，$0.0016/credit

### GoEnhance API（VidGo Effects）

| 操作 | 預估成本 | 說明 |
|------|----------|------|
| Style Transfer | $0.10-0.20 | 風格轉換 |
| 4K Upscale | $0.15-0.25 | 圖像放大 |
| Video Enhancement | $0.20-0.40 | 影片增強 |

### Runway API（備援）

| 操作 | Credits | USD 成本 | 說明 |
|------|---------|----------|------|
| Gen-4 Video (每秒) | 12 credits | $0.12 | 高品質影片 |
| Gen-4 Turbo (每秒) | 5 credits | $0.05 | 快速生成 |

> **計算基準**：$0.01/credit

### Pollo AI API（未來功能）

| 操作 | 預估成本 | 說明 |
|------|----------|------|
| Wan 2.2 Video | $0.60-0.80 | 新模型 |
| Veo 3.1 Video | $0.80-1.20 | Google 模型 |
| Kling Video | $1.00-1.50 | 高品質模型 |

> **狀態**：🔮 未來功能，將以「VidGo Advanced Models」品牌推出

---

## 點數加值包

### 標準加值包

| 包裝 | 點數 | 價格 | 單價 | 適用方案 |
|------|------|------|------|----------|
| 小包 | 50 pts | NT$150 | NT$3.00/pt | 全部 |
| 中包 | 100 pts | NT$250 | NT$2.50/pt | Starter+ |
| 大包 | 200 pts | NT$400 | NT$2.00/pt | Pro+ |
| 企業包 | 500 pts | NT$800 | NT$1.60/pt | Pro+ |

### 方案專屬折扣

| 方案 | 加購折扣 | 100 pts 實際價格 |
|------|----------|------------------|
| Demo | 無法加購 | — |
| Starter | 標準價格 | NT$250 |
| Pro | 10% 折扣 | NT$225 |
| Pro+ | 20% 折扣 | NT$200 |

---

## 快取節省機制

### 相似度快取運作原理

```
使用者提示詞 → Gemini Embedding (768維向量) → 餘弦相似度比對
                                                    ↓
                                          相似度 ≥ 85%？
                                                    ↓
                                    是 → 返回快取結果 (0 pts)
                                    否 → 生成新內容 (扣除點數)
```

### 快取節省統計

| 場景 | 點數消耗 | 說明 |
|------|----------|------|
| 首次生成 | 5-12 pts | 完整生成流程 |
| 完全相同提示詞 | 0 pts | Hash 精確匹配 |
| 相似提示詞 (>85%) | 0 pts | 向量相似度匹配 |
| 不同提示詞 (<85%) | 5-12 pts | 需要重新生成 |

### 預估快取命中率

| 使用情境 | 預估命中率 | 每週節省 |
|----------|------------|----------|
| 產品廣告（重複產品） | 40-60% | 10-15 pts |
| 創意探索（多樣提示） | 10-20% | 3-5 pts |
| 團隊協作（共享快取） | 50-70% | 15-25 pts |

---

## 計費規則

### 點數扣除時機

1. **生成開始時**：確認帳戶有足夠點數
2. **生成成功後**：實際扣除點數
3. **生成失敗時**：不扣除點數（API 錯誤）
4. **快取命中時**：不扣除點數

### 點數類型與有效期

| 點數類型 | 有效期 | 重置時間 | 說明 |
|----------|--------|----------|------|
| 訂閱點數 | **每週重置** | 週一 00:00 UTC | 不累積至下週 |
| 加購點數 | 永久有效 | — | 帳號存續期間 |
| 贈送點數 | 90 天 | — | 促銷活動贈送 |

### 點數扣除優先順序

1. **贈送點數**（即將過期的優先）
2. **訂閱點數**（當週會過期）
3. **加購點數**（永久有效，最後使用）

### VidGo Effects 權限檢查

```
用戶請求 VidGo Effects
        ↓
檢查是否為訂閱用戶？
        ↓
    ┌───────┴───────┐
    ↓               ↓
   是              否
    ↓               ↓
檢查點數          返回錯誤：
是否足夠          「此功能需要付費訂閱」
    ↓
執行效果
```

### 退款政策

| 情況 | 退款方式 |
|------|----------|
| 生成失敗（平台問題） | 點數返還 |
| 生成品質不滿意 | 不退款（可重新生成） |
| 訂閱取消 | 剩餘週點數不退款 |
| 加購點數 | 7 天內未使用可退款 |

---

## 技術實作規格

### 資料庫欄位

```sql
-- 使用者點數餘額（週制）
users.subscription_credits    -- 訂閱點數（每週重置）
users.purchased_credits       -- 加購點數（永久）
users.bonus_credits           -- 贈送點數（有期限）
users.bonus_credits_expiry    -- 贈送點數到期日
users.credits_reset_at        -- 上次週重置時間

-- 方案定義（週點數）
plans.weekly_credits          -- 每週點數
plans.can_use_effects         -- 是否可使用 VidGo Effects

-- 點數交易記錄
credit_transactions.id
credit_transactions.user_id
credit_transactions.amount           -- 正數=增加，負數=扣除
credit_transactions.balance_after    -- 交易後餘額
credit_transactions.transaction_type -- generation, purchase, weekly_reset, refund, bonus
credit_transactions.service_type     -- leonardo_video, vidgo_style, etc.
credit_transactions.reference_id     -- 關聯的生成記錄 ID
credit_transactions.created_at

-- 服務定價（含權限）
service_pricing.service_type         -- leonardo_720p, vidgo_style, etc.
service_pricing.display_name         -- 使用者看到的名稱
service_pricing.credit_cost          -- 點數消耗
service_pricing.subscribers_only     -- 是否僅限訂閱用戶
```

### API 回應格式

```json
{
  "success": true,
  "generation_id": "uuid-here",
  "credits_used": 5,
  "credits_remaining": {
    "subscription": 20,
    "purchased": 100,
    "bonus": 10,
    "total": 130,
    "next_reset": "2024-12-30T00:00:00Z"
  },
  "cache_hit": false,
  "service_used": "leonardo_video_720p",
  "service_display_name": "VidGo Video 720p",
  "result": {
    "image_url": "https://...",
    "video_url": "https://..."
  }
}
```

### VidGo Effects 權限錯誤回應

```json
{
  "success": false,
  "error": {
    "code": "SUBSCRIPTION_REQUIRED",
    "message": "VidGo Effects 需要付費訂閱才能使用",
    "message_en": "VidGo Effects requires a paid subscription",
    "upgrade_url": "/plans"
  }
}
```

### 週重置 API 回應

```json
{
  "reset_schedule": {
    "frequency": "weekly",
    "day": "Monday",
    "time": "00:00 UTC",
    "next_reset": "2024-12-30T00:00:00Z",
    "your_plan": {
      "name": "Pro",
      "weekly_credits": 60
    }
  }
}
```

### 併發控制

```python
# 使用 Redis 分散式鎖確保點數扣除原子性
async def deduct_credits(user_id: str, amount: int, service_type: str):
    lock_key = f"credit_lock:{user_id}"
    async with redis.lock(lock_key, timeout=10):
        # 1. 檢查服務權限
        can_access, error = await check_service_access(user_id, service_type)
        if not can_access:
            raise AccessDeniedError(error)
        
        # 2. 檢查餘額
        balance = await get_balance(user_id)
        if balance < amount:
            raise InsufficientCreditsError()
        
        # 3. 扣除點數（按優先順序）
        await update_balance(user_id, -amount)
        
        # 4. 記錄交易
        await create_transaction(user_id, -amount, service_type, ...)
```

### 週重置任務（Celery）

```python
from celery import Celery
from celery.schedules import crontab

celery_app = Celery('vidgo')

@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # 每週一 00:00 UTC 重置點數
    sender.add_periodic_task(
        crontab(hour=0, minute=0, day_of_week=1),
        weekly_credit_reset.s(),
        name='weekly-credit-reset'
    )

@celery_app.task
async def weekly_credit_reset():
    """重置所有訂閱用戶的週點數"""
    async with get_db_session() as db:
        # 取得所有活躍訂閱用戶及其方案
        query = """
            UPDATE users u
            SET 
                subscription_credits = p.weekly_credits,
                credits_reset_at = NOW()
            FROM plans p
            WHERE u.current_plan_id = p.id
            AND u.is_active = true
            AND u.is_verified = true
            AND p.name != 'demo'
            RETURNING u.id, u.email, p.weekly_credits
        """
        
        result = await db.execute(text(query))
        reset_users = result.fetchall()
        
        # 記錄交易
        for user_id, email, weekly_credits in reset_users:
            transaction = CreditTransaction(
                user_id=user_id,
                amount=weekly_credits,
                balance_after=weekly_credits,
                transaction_type="weekly_reset",
                description=f"週點數重置：{weekly_credits} pts"
            )
            db.add(transaction)
        
        await db.commit()
        
        return f"已重置 {len(reset_users)} 位用戶的點數"
```

---

## 附錄：常見問題

### Q1: 為什麼改成每週重置？

每週重置讓用戶更頻繁獲得點數，提升使用體驗。對於輕度用戶，不會因為月底用不完而浪費；對於重度用戶，每週固定配額也更容易規劃使用。

### Q2: Demo 用戶為什麼不能使用 VidGo Effects？

VidGo Effects（風格轉換、4K 放大、影片增強）是付費訂閱的核心價值之一。限制 Demo 用戶使用可以：
1. 區分免費與付費功能
2. 控制免費用戶的 API 成本
3. 提供升級誘因

### Q3: 為什麼只用 Leonardo AI 生成影片和圖像？

Leonardo AI 是我們的主要生成服務，提供穩定且高品質的結果。Pollo AI 未來將作為「VidGo Advanced Models」推出，提供 Wan 2.2、Veo 3.1 等新興模型供進階用戶探索。

### Q4: 週點數沒用完會累積嗎？

不會。訂閱點數每週一 00:00 UTC 會重置為方案的週點數上限。但加購點數永久有效，不受週重置影響。

### Q5: 如何最大化點數使用效率？

1. **善用快取**：相似的提示詞可免費使用快取結果
2. **從低解析度開始**：先用 720p 確認效果，再升級至 1080p/4K
3. **批量加購**：大包裝的點數單價更優惠
4. **升級方案**：Pro+ 方案的加購享 20% 折扣
5. **週末前使用**：訂閱點數在週一重置，週日前用完最划算

### Q6: VidGo Effects 包含哪些功能？

| 功能 | 說明 | 點數 |
|------|------|------|
| VidGo Style Effects | 將圖像/影片轉換為藝術風格 | 8 pts |
| VidGo HD Enhance | 將圖像放大至 4K 解析度 | 10 pts |
| VidGo Video Pro | 增強影片品質、穩定度、清晰度 | 12 pts |

以下功能**不包含**：
- ❌ AI ASMR
- ❌ AI Dance
- ❌ Character Animation
- ❌ GoEnhance Animate

---

## 附錄：服務權限對照表

| 服務 | Demo | Starter | Pro | Pro+ |
|------|------|---------|-----|------|
| VidGo Video 720p | ✅ (僅快取) | ✅ | ✅ | ✅ |
| VidGo Video 1080p | ❌ | ✅ | ✅ | ✅ |
| VidGo Video 4K | ❌ | ❌ | ✅ | ✅ |
| VidGo Image | ✅ (僅快取) | ✅ | ✅ | ✅ |
| VidGo Image HD | ❌ | ✅ | ✅ | ✅ |
| VidGo Style Effects | ❌ | ✅ | ✅ | ✅ |
| VidGo HD Enhance | ❌ | ✅ | ✅ | ✅ |
| VidGo Video Pro | ❌ | ❌ | ✅ | ✅ |
| 優先佇列 | ❌ | ❌ | ✅ | ✅ |
| 無浮水印 | ❌ | ✅ | ✅ | ✅ |
| 加購點數 | ❌ | ✅ | ✅ (9折) | ✅ (8折) |

---

## 附錄：週點數 vs 月點數對比

| 項目 | 週點數制 | 月點數制 |
|------|----------|----------|
| **重置頻率** | 每週一次 | 每月一次 |
| **Starter 總量** | 25 × 4 = 100/月 | 100/月 |
| **Pro 總量** | 60 × 4 = 240/月 | 250/月 |
| **Pro+ 總量** | 125 × 4 = 500/月 | 500/月 |
| **浪費風險** | 低（每週用完即可） | 高（月底可能剩餘） |
| **預算規劃** | 每週固定 | 需要月度規劃 |
| **適合用戶** | 穩定使用型 | 集中使用型 |

---

*文件版本：2.0.0 | 最後更新：2024年12月28日*
