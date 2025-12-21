# VidGo AI 影片生成平台 - 開發報告

## 專案概述

VidGo 是一個 AI 驅動的影片生成 SaaS 平台，提供 AI 換裝特效和進階藝術風格轉換功能。本報告總結了 Phase 1 和 Phase 2 的開發成果。

---

## 目錄

1. [技術架構](#技術架構)
2. [Phase 1 - 基礎建設](#phase-1---基礎建設)
3. [Phase 2 - Demo 引擎與內容審核](#phase-2---demo-引擎與內容審核)
4. [功能清單](#功能清單)
5. [API 端點](#api-端點)
6. [資料庫模型](#資料庫模型)
7. [待開發功能](#待開發功能)
8. [部署指南](#部署指南)

---

## 技術架構

### 後端 (Backend)
- **框架**: FastAPI
- **資料庫**: PostgreSQL (async with SQLAlchemy)
- **快取**: Redis
- **任務佇列**: Celery
- **ORM**: SQLAlchemy 2.0 (async)
- **遷移工具**: Alembic

### 前端 (Frontend)
- **框架**: Streamlit
- **UI 元件**: streamlit-option-menu
- **HTTP 客戶端**: requests

### 第三方服務
- **支付**: ECPay (綠界科技)
- **內容審核**: Google Gemini AI
- **影像生成**: GoEnhance API (準備整合)
- **郵件服務**: SMTP (Gmail)

---

## Phase 1 - 基礎建設

### 1.1 使用者認證系統

#### 功能
- [x] 使用者註冊 (含密碼確認)
- [x] 電子郵件驗證
- [x] 使用者登入 (JWT Token)
- [x] Token 刷新機制
- [x] 忘記密碼 / 重設密碼
- [x] 使用者登出
- [x] 客戶端密碼雜湊 (SHA256 + 伺服端 bcrypt)

#### 安全機制
```python
# 客戶端密碼雜湊
def hash_password_client(password: str, salt: str = "vidgo_salt_2024") -> str:
    salted = f"{salt}{password}{salt}"
    return hashlib.sha256(salted.encode()).hexdigest()
```

### 1.2 訂閱方案管理

#### 方案類型
| 方案名稱 | 月費 | 年費 | 點數/月 | 最大影片長度 | 解析度 |
|---------|------|------|---------|-------------|--------|
| Starter | $9.99 | $99.99 | 100 | 30秒 | 720p |
| Pro | $29.99 | $299.99 | 500 | 60秒 | 1080p |
| Business | $99.99 | $999.99 | 2000 | 120秒 | 4K |

#### 功能特色
- [x] 方案瀏覽
- [x] 訂閱管理
- [x] 訂閱取消
- [x] 訂單管理
- [x] 發票記錄

### 1.3 支付整合 (ECPay)

#### 支援付款方式
- [x] 信用卡
- [x] ATM 轉帳
- [x] 超商代碼
- [x] 條碼繳費

#### 流程
```
使用者選擇方案 → 建立訂單 → 產生 ECPay 表單 → 導向支付閘道 → 回調處理 → 啟用訂閱
```

### 1.4 郵件服務

#### 郵件類型
- [x] 電子郵件驗證信
- [x] 密碼重設信
- [x] 歡迎信 (驗證成功後)

#### 設定需求
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your-app-password  # 需使用 App Password
```

---

## Phase 2 - Demo 引擎與內容審核

### 2.1 Smart Demo 引擎

#### 核心功能
- [x] AI 換裝特效展示
- [x] 進階藝術風格展示
- [x] 多語言提示詞支援 (EN, ZH-TW, JA, KO, ES)
- [x] 風格選擇器 (每個風格含範例)
- [x] 類別探索 (可點擊查看影片)
- [x] 生成預覽動畫

#### 換裝風格
| 風格名稱 | 範例提示詞 |
|---------|-----------|
| Casual Wear | 輕鬆牛仔褲配白T恤 |
| Formal Suit | 深藍色商務西裝 |
| Evening Dress | 優雅黑色晚禮服 |
| Streetwear | 時尚連帽衫配球鞋 |
| Vintage Style | 1950年代復古洋裝 |
| Sporty Look | 運動服配運動鞋 |

#### 藝術風格
| 風格名稱 | 範例提示詞 |
|---------|-----------|
| Japanese Anime | 穿著校服的大眼睛女孩 |
| Pixar Style | 探索城市的可愛機器人 |
| Makoto Shinkai | 東京天際線上的夕陽雲彩 |
| Cyberpunk | 霓虹燈街道與飛行汽車 |
| Watercolor | 春天花園裡盛開的花朵 |
| Oil Painting | 貴族夫人的肖像畫 |

### 2.2 內容審核系統

#### 多層審核機制
```
使用者輸入 → Block Cache 檢查 → Gemini AI 審核 → 通過/拒絕
     ↓              ↓                ↓
   快速過濾      關鍵字比對        深度分析
```

#### Block Cache (Redis)
- [x] 種子違規詞庫 (200+ 詞彙)
- [x] 多語言支援
- [x] 動態學習 (Gemini 檢測到的新詞)
- [x] 手動新增/移除
- [x] 統計資訊

#### Gemini AI 審核
- [x] 多類別分析 (暴力、色情、仇恨言論等)
- [x] 信心分數
- [x] 自動學習到 Block Cache
- [x] 詳細原因說明

### 2.3 多語言介面

#### 支援語言
- 🇺🇸 English (en)
- 🇹🇼 繁體中文 (zh-TW)
- 🇯🇵 日本語 (ja)
- 🇰🇷 한국어 (ko)
- 🇪🇸 Español (es)

#### 翻譯涵蓋範圍
- [x] 導覽列
- [x] 功能卡片
- [x] 風格選擇器
- [x] 輸入區域
- [x] 生成預覽
- [x] 類別探索
- [x] 錯誤訊息

### 2.4 類別影片瀏覽

#### 類別
| 類別 | 圖示 | 描述 |
|-----|------|------|
| Animals | 🐱 | 動物主題影片 |
| Nature | 🌿 | 自然風景影片 |
| Urban | 🏙️ | 都市場景影片 |
| People | 👤 | 人物主題影片 |
| Fantasy | 🐉 | 奇幻主題影片 |
| Sci-Fi | 🚀 | 科幻主題影片 |

#### 功能
- [x] 點擊類別顯示相關影片
- [x] 每個類別最多 10 部影片
- [x] 影片卡片顯示標題、描述、時長
- [x] 支援影片播放或縮圖顯示

---

## 功能清單

### 後端服務

| 服務 | 檔案 | 功能說明 |
|-----|------|---------|
| 認證服務 | `auth.py` | JWT 認證、使用者管理 |
| 方案服務 | `plans.py` | 訂閱方案 CRUD |
| 支付服務 | `payments.py` | ECPay 整合 |
| Demo 服務 | `demo.py`, `demo_service.py` | Demo 引擎核心 |
| 審核服務 | `moderation.py` | Gemini AI 內容審核 |
| 快取服務 | `block_cache.py` | Redis 違規詞快取 |
| 提示詞配對 | `prompt_matching.py` | 多語言提示詞處理 |
| 郵件服務 | `email_service.py` | SMTP 郵件發送 |
| GoEnhance | `goenhance.py` | 影像生成 API 客戶端 |
| 浮水印 | `watermark.py` | 影片浮水印處理 |

### 前端頁面

| 頁面 | 功能說明 |
|-----|---------|
| Landing Page | 未登入使用者首頁 |
| Demo Page | AI 特效展示 |
| Login/Register | 使用者認證 |
| Dashboard | 使用者儀表板 |
| Plans | 方案選擇 |
| Subscriptions | 訂閱管理 |
| Orders | 訂單記錄 |
| Invoices | 發票記錄 |
| Settings | 帳戶設定 |

---

## API 端點

### 認證 API (`/api/v1/auth`)

| 方法 | 端點 | 說明 |
|-----|------|------|
| POST | `/login` | 使用者登入 |
| POST | `/logout` | 使用者登出 |
| POST | `/refresh` | 刷新 Token |
| POST | `/register` | 使用者註冊 |
| POST | `/verify-email` | 驗證電子郵件 |
| POST | `/resend-verification` | 重發驗證信 |
| POST | `/forgot-password` | 忘記密碼 |
| POST | `/reset-password` | 重設密碼 |
| GET | `/me` | 取得使用者資訊 |
| PUT | `/me` | 更新使用者資訊 |
| POST | `/me/change-password` | 變更密碼 |

### 方案 API (`/api/v1/plans`)

| 方法 | 端點 | 說明 |
|-----|------|------|
| GET | `/` | 取得所有方案 |
| GET | `/current` | 取得目前訂閱 |
| GET | `/with-subscription` | 方案含訂閱狀態 |
| GET | `/{plan_id}` | 取得特定方案 |

### Demo API (`/api/v1/demo`)

| 方法 | 端點 | 說明 |
|-----|------|------|
| POST | `/search` | 搜尋或生成 Demo |
| GET | `/random` | 隨機 Demo |
| POST | `/analyze` | 分析提示詞 |
| GET | `/styles` | 取得可用風格 |
| GET | `/categories` | 取得類別列表 |
| GET | `/topics/{category}` | 取得類別主題 |
| GET | `/videos/{category}` | 取得類別影片 |
| POST | `/moderate` | 內容審核 |
| GET | `/{demo_id}` | 取得特定 Demo |
| GET | `/block-cache/stats` | 快取統計 |
| POST | `/block-cache/check` | 檢查提示詞 |

### 支付 API (`/api/v1/payments`)

| 方法 | 端點 | 說明 |
|-----|------|------|
| POST | `/create` | 建立支付 |
| POST | `/callback` | ECPay 回調 |

---

## 資料庫模型

### 使用者模型 (User)
```python
class User(Base):
    id: UUID
    username: str
    email: str
    password_hash: str
    first_name: str
    last_name: str
    is_active: bool
    is_verified: bool
    verification_token: str
    reset_token: str
    created_at: datetime
    updated_at: datetime
```

### 訂閱模型 (Subscription)
```python
class Subscription(Base):
    id: UUID
    user_id: UUID
    plan_id: UUID
    status: str  # active, cancelled, expired
    start_date: datetime
    end_date: datetime
    created_at: datetime
```

### Demo 影片模型 (DemoVideo)
```python
class DemoVideo(Base):
    id: UUID
    title: str
    description: str
    prompt: str
    keywords: List[str]
    category_id: UUID
    video_url: str
    thumbnail_url: str
    duration_seconds: float
    style: str
    popularity_score: int
    is_active: bool
```

### Demo 類別模型 (DemoCategory)
```python
class DemoCategory(Base):
    id: UUID
    name: str
    slug: str
    description: str
    icon: str
    sort_order: int
    is_active: bool
```

---

## 待開發功能

### Phase 3 - GoEnhance API 整合

- [ ] GoEnhance API 連接
- [ ] 即時影像生成
- [ ] 影片生成 (5秒)
- [ ] 生成佇列管理
- [ ] 點數扣除系統

### Phase 4 - 進階功能

- [ ] 批次處理
- [ ] API 存取 (Business 方案)
- [ ] 自訂風格訓練
- [ ] 影片編輯工具
- [ ] 社群分享功能

### Phase 5 - 商業化

- [ ] 更多支付方式
- [ ] 企業方案
- [ ] 白標服務
- [ ] 數據分析儀表板
- [ ] A/B 測試框架

---

## 部署指南

### 環境變數設定

```env
# 資料庫
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/vidgo

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# SMTP (Gmail App Password)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your-16-char-app-password

# Gemini AI
GEMINI_API_KEY=your-gemini-api-key

# GoEnhance (待整合)
GOENHANCE_API_KEY=your-goenhance-api-key

# ECPay
ECPAY_MERCHANT_ID=your-merchant-id
ECPAY_HASH_KEY=your-hash-key
ECPAY_HASH_IV=your-hash-iv
```

### 啟動服務

```bash
# 啟動 Docker 服務 (PostgreSQL, Redis)
docker-compose up -d

# 執行資料庫遷移
cd backend
PYTHONPATH=. uv run alembic upgrade head

# 啟動後端
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# 啟動前端
cd frontend
uv run streamlit run app.py --server.port 8501
```

### 存取位址

- **前端**: http://localhost:8501
- **後端 API**: http://localhost:8000
- **API 文件**: http://localhost:8000/docs

---

## 專案結構

```
VidGo_Gen_AI/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── auth.py        # 認證 API
│   │   │       ├── demo.py        # Demo API
│   │   │       ├── payments.py    # 支付 API
│   │   │       └── plans.py       # 方案 API
│   │   ├── core/
│   │   │   ├── config.py          # 設定
│   │   │   ├── database.py        # 資料庫連接
│   │   │   └── security.py        # 安全工具
│   │   ├── models/
│   │   │   ├── user.py            # 使用者模型
│   │   │   ├── billing.py         # 帳務模型
│   │   │   └── demo.py            # Demo 模型
│   │   ├── services/
│   │   │   ├── block_cache.py     # 違規詞快取
│   │   │   ├── demo_service.py    # Demo 服務
│   │   │   ├── email_service.py   # 郵件服務
│   │   │   ├── goenhance.py       # GoEnhance 客戶端
│   │   │   ├── moderation.py      # 內容審核
│   │   │   └── prompt_matching.py # 提示詞配對
│   │   └── main.py                # 應用程式入口
│   ├── alembic/                   # 資料庫遷移
│   └── tests/                     # 測試
├── frontend/
│   ├── components/
│   │   └── demo.py                # Demo 頁面元件
│   ├── utils/
│   │   ├── api_client.py          # API 客戶端
│   │   └── auth.py                # 認證工具
│   ├── app.py                     # Streamlit 主應用
│   └── config.py                  # 前端設定
├── docker-compose.yml             # Docker 編排
├── pyproject.toml                 # Python 專案設定
└── REPORT.md                      # 本報告
```

---

## 開發團隊

- **專案**: VidGo AI Video Generation Platform
- **版本**: 1.0.0 (Phase 1 + Phase 2)
- **日期**: 2024 年 12 月

---

## 授權

版權所有 © 2024 VidGo。保留所有權利。
