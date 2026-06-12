# AI 短影音自動獲客與成交系統
## 瞬影科技（VidGo）完整操作 SOP

> 版本：1.0 | 適合對象：不會寫程式的業務、行銷主管
> 目標：輸入一個產業名稱，系統自動完成腳本→影片→上傳→CRM

---

## 你需要準備的東西（清單）

在開始之前，請先準備好這 5 樣東西：

| 需要什麼 | 在哪裡拿 | 花多少時間 |
|---|---|---|
| Anthropic API Key | [console.anthropic.com](https://console.anthropic.com) 免費申請 | 5 分鐘 |
| Notion API Key | [notion.so/my-integrations](https://notion.so/my-integrations) 建立 Integration | 5 分鐘 |
| n8n 帳號 | [n8n.io](https://n8n.io) 免費 Cloud 版 或 自架 | 10 分鐘 |
| VidGo 帳號 | 你自己的 VidGo 平台帳號 | 已有 |
| YouTube 帳號 | 你的品牌 YouTube 頻道 | 已有 |

---

## 第一步：設定 VidGo 環境變數

> 這一步讓 VidGo 知道要用哪個 AI 來生成腳本。

### 1-1. 開啟 VidGo 的環境設定檔

找到你的 VidGo 安裝目錄，開啟 `.env` 或 `docker-compose.yml` 檔案。

在 **後端（backend）** 的環境變數裡，加入這一行：

```
ANTHROPIC_API_KEY=你的Anthropic_API_Key貼在這裡
```

**範例：**
```
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 1-2. 重新啟動後端

```bash
docker-compose restart backend
```

### 1-3. 確認設定成功

在瀏覽器開啟：
```
http://你的VidGo網址:8001/api/v1/lead-gen/health
```

你應該看到：
```json
{
  "status": "ok",
  "anthropic_configured": true,
  "message": "AI 獲客腳本服務正常運作"
}
```

---

## 第二步：建立 Notion CRM 資料庫

> 這是你的客戶管理中心，系統會自動把每支影片的資料寫進來。

### 2-1. 在 Notion 建立新資料庫

1. 開啟 Notion，新增一個頁面
2. 輸入標題：**瞬影科技 客戶 CRM**
3. 輸入 `/database`，選擇「Table - Full page」

### 2-2. 建立以下欄位

依序新增這些欄位（點擊 `+` 新增）：

| 欄位名稱 | 類型 | 選項設定 |
|---|---|---|
| 客戶名稱 | Title | （預設，不用改） |
| 行業 | Select | 醫美、建築、宗教、餐飲、科技、其他 |
| 狀態 | Select | 🧊冷客戶、🌡️溫客戶、🔥熱客戶 |
| 來源影片 | URL | - |
| 來源平台 | Select | YouTube、TikTok、Instagram |
| 影片觀看數 | Number | Format: Number |
| 互動數 | Number | Format: Number |
| 加入日期 | Date | - |
| 腳本Hook | Text | - |
| 跟進備註 | Text | - |
| LINE 連結 | URL | - |

### 2-3. 連接 Notion Integration

1. 到 [notion.so/my-integrations](https://notion.so/my-integrations)
2. 點「+ New integration」
3. 名稱填：VidGo Lead Gen
4. 權限勾選：Read content + Update content + Insert content
5. 複製 **Internal Integration Token**（這就是你的 NOTION_API_KEY）

6. 回到剛才建立的 CRM 資料庫頁面
7. 右上角點「...」→「Connect to」→ 選擇「VidGo Lead Gen」

### 2-4. 取得資料庫 ID

看你的 Notion 頁面 URL：
```
https://notion.so/你的名字/瞬影科技-客戶-CRM-【這一段就是ID】?v=xxxxx
```

把 ID 複製起來（32位字元，例如：`a1b2c3d4e5f6...`），這是你的 `NOTION_DATABASE_ID`。

---

## 第三步：連接 YouTube 帳號到 VidGo

> 讓 VidGo 有權限自動上傳影片到你的 YouTube 頻道。

1. 登入你的 VidGo 平台（例如：[vidgo.co](https://vidgo.co)）
2. 點右上角頭像 → **帳號設定**
3. 找到「**社群媒體帳號**」區塊
4. 點「連接 YouTube」
5. 用你的 Google 帳號登入，授權 VidGo 上傳影片
6. 連接成功後，這裡會顯示你的 YouTube 頻道名稱

---

## 第四步：設定 n8n Workflow

> 這是讓一切自動化的核心。

### 4-1. 匯入 Workflow

1. 開啟你的 n8n
2. 左上角點「+」新增 Workflow
3. 右上角點「...」→「Import from file」
4. 選擇這個檔案：`n8n_workflows/vidgo_lead_gen_workflow.json`
5. 匯入後你會看到 11 個節點（Node）

### 4-2. 設定 Variables（重要！）

在 n8n 左側選單點「**Variables**」，新增以下 5 個變數：

```
VIDGO_BASE_URL     = http://你的VidGo網址:8001
VIDGO_EMAIL        = 你的VidGo登入Email
VIDGO_PASSWORD     = 你的VidGo密碼
NOTION_API_KEY     = secret_xxxxxxxxxx（從步驟2-3複製）
NOTION_CRM_DATABASE_ID = xxxxxxxxxx（從步驟2-4複製）
```

> ⚠️ 注意：這些是機密資訊，不要截圖或傳給別人。

### 4-3. 測試 Workflow

1. 在 n8n 打開 Workflow
2. 點第一個節點「1. 觸發器 Webhook」
3. 複製顯示的 Webhook URL（例如：`https://n8n.你的網址.com/webhook/vidgo-lead-gen`）
4. 點右上角「Test Workflow」

5. 用下面的指令測試（在電腦的終端機貼上執行）：

```bash
curl -X POST https://你的n8n網址/webhook/vidgo-lead-gen \
  -H "Content-Type: application/json" \
  -d '{
    "industry": "醫美",
    "cta_type": "line",
    "line_id": "@你的LINE_ID"
  }'
```

6. 如果成功，你會看到：
```json
{
  "success": true,
  "message": "✅ 短影音已生成並上傳！",
  "industry": "醫美",
  "script_hook": "你花了50萬廣告費，但客戶還是不記得你？",
  "youtube_url": "https://youtube.com/shorts/xxx",
  "notion_created": true
}
```

### 4-4. 設定定時自動執行（可選）

如果你想每天自動生成：

1. 刪掉「1. 觸發器 Webhook」節點
2. 換成「Schedule Trigger」節點
3. 設定：每天早上 9:00 執行
4. 在排程節點的輸出 JSON 裡固定寫入：
```json
{
  "industry": "醫美",
  "cta_type": "line",
  "line_id": "@vidgoai"
}
```

---

## 第五步：了解系統流程

每次觸發後，系統會自動做這 7 件事：

```
1. 接收「產業」輸入（例如：醫美）
   ↓ 約 0 秒
2. 呼叫 Claude AI 生成爆款腳本
   → 產出：Hook + 痛點 + 解決方案 + CTA
   ↓ 約 5-10 秒
3. 呼叫 VidGo 生成 9:16 短影音
   → 模型：Kling v1（高品質）
   ↓ 約 60-90 秒
4. 等待影片完成
   ↓
5. 自動上傳 YouTube Shorts
   → 標題 = Hook 文字
   → 說明 = 完整腳本 + hashtag
   ↓ 約 30 秒
6. 在 Notion CRM 新增一筆記錄
   → 初始狀態：冷客戶
   → 來源影片：YouTube 連結
   ↓
7. 完成！回傳結果
   
總時間：約 2-3 分鐘
```

---

## 第六步：客戶分類 SOP（每週手動更新）

> 現在的版本是手動更新分類，未來可以自動化。

每週一，在 Notion CRM 做以下分類：

### 冷客戶 → 溫客戶（任一條件符合）
- 影片觀看數 ≥ 100
- 有留言互動
- 有點擊說明欄的 LINE 連結

### 溫客戶 → 熱客戶（任一條件符合）
- 影片觀看數 ≥ 1,000
- 主動傳訊息詢問
- 看了多支影片（同一產業）

### 熱客戶 → 開始成交
- 進入正式業務流程
- 安排 Demo 或報價

---

## AI 腳本 Prompt（可直接複製使用）

如果你想在 ChatGPT 或 Claude 手動生成腳本，複製以下 Prompt：

```
你是台灣頂級 B2B 行銷文案師，專門寫讓企業主看完立刻行動的短影音腳本。

產業：[填入你的產業，例如：醫美診所]
品牌：瞬影科技
影片長度：60秒（約150字）
目標觀眾：台灣中小企業主、老闆、行銷主管
CTA：加 LINE @vidgoai 免費諮詢，前10名送 AI 影片製作

請依以下結構輸出完整腳本（直接輸出，不要解釋）：

【Hook - 前3秒】
一句讓人停下來的話，用數字或問句，例如：
「你的[產業]每年花多少錢在沒效果的廣告？」

【痛點 - 10秒】
說出他們每天遇到的具體困境，讓他們點頭說「對就是這樣！」

【解決方案 - 35秒】
用3個具體結果說明瞬影科技帶來什麼改變：
✅ 結果1
✅ 結果2  
✅ 結果3

【CTA - 10秒】
限時限量的行動呼籲，要有緊迫感

語氣：口語、像朋友在說話、不要廣告味
```

---

## MoneyPrinterTurbo 替代方案（免費版）

> 如果你沒有 VidGo 訂閱點數，可以用這個免費工具生成影片。

### 啟動方式（用 Docker）

電腦需要先安裝 Docker Desktop，然後執行：

```bash
docker pull harry0703/moneyprinterturbo:latest
docker run -d -p 8501:8501 -p 8080:8080 \
  --name mpt \
  harry0703/moneyprinterturbo:latest
```

啟動後：
- 管理介面：`http://localhost:8501`
- API 地址：`http://localhost:8080`

### 用 n8n 呼叫 MoneyPrinterTurbo

在 n8n 的「4. 生成短影音」節點，把 URL 改成：

```
http://localhost:8080/api/v1/video/start
```

Body 改成：

```json
{
  "video_subject": "{{ $('3. AI 生成短影音腳本').item.json.hook }}",
  "video_script": "{{ $('3. AI 生成短影音腳本').item.json.full_script }}",
  "video_terms": ["{{ $('1. 觸發器 Webhook').item.json.body.industry }}", "AI行銷", "台灣"],
  "video_aspect": "9:16",
  "video_language": "zh-TW",
  "voice_name": "zh-TW-HsiaoChenNeural",
  "bgm_type": "random",
  "subtitle_enabled": true
}
```

查詢影片進度（加一個 Wait 60秒後輪詢）：
```
GET http://localhost:8080/api/v1/video/{task_id}
```

完成時 `status` 變成 `"completed"`，`video_url` 就是下載連結。

---

## 常見問題

**Q: 腳本生成失敗，顯示「AI 腳本生成服務暫時無法使用」？**
→ 確認 `ANTHROPIC_API_KEY` 有正確設定，且帳戶有餘額。

**Q: 影片一直顯示「生成中」沒有完成？**
→ VidGo 的 Kling v1 通常需要 60-120 秒。可以把 n8n 的等待時間改成 120 秒。

**Q: YouTube 上傳失敗？**
→ 確認 VidGo 社群媒體設定裡已連接 YouTube，且 OAuth Token 沒有過期。重新連接一次即可。

**Q: Notion 沒有寫入資料？**
→ 確認 Notion Integration 有被邀請進資料庫（步驟 2-3 的最後一步）。

**Q: 可以同時做多個產業嗎？**
→ 可以！複製 n8n Workflow，改不同的 `industry` 值，設定不同的執行時間即可。

---

## 7天執行計畫

| 天 | 任務 | 預計時間 |
|---|---|---|
| Day 1 | 設定 Anthropic API Key + 重啟 VidGo | 30 分鐘 |
| Day 2 | 建立 Notion CRM 資料庫（步驟2）| 1 小時 |
| Day 3 | 連接 YouTube 帳號（步驟3）+ 測試上傳 | 1 小時 |
| Day 4 | 設定 n8n + 匯入 Workflow（步驟4）| 2 小時 |
| Day 5 | 端對端測試：輸入「醫美」跑完整流程 | 2 小時 |
| Day 6 | 修正問題 + 做第一批影片（3個產業）| 3 小時 |
| Day 7 | 上線 + 觀察數據 + 調整腳本 Prompt | 持續 |

---

## 需要協助？

- 系統問題：聯繫 VidGo 技術團隊
- n8n 使用：[n8n 官方文件](https://docs.n8n.io)
- Notion API：[Notion API 文件](https://developers.notion.com)
- Anthropic API：[Anthropic 文件](https://docs.anthropic.com)
