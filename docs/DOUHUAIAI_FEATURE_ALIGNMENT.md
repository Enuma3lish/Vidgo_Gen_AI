# 豆绘AI (douhuiai.com) 功能對齊計畫

**目標：** 功能與豆绘AI 越接近越好，**UI 維持現狀**（沿用現有 VidGo 介面與路由結構）。

**參考網站：** https://www.douhuiai.com/

---

## 一、豆绘AI 功能結構 vs VidGo 對照

### 1. 產品電商（豆绘）→ VidGo 電商視覺

| 豆绘AI 功能 | 豆绘路徑 | VidGo 對應 | 狀態 |
|-------------|----------|------------|------|
| 一鍵白底圖 | /product/ecommerce | 背景移除 Background Removal | ✅ 已有 |
| 一鍵場景圖 | /product/genscene | 商品場景 Product Scene | ✅ 已有 |
| AI試穿試戴 | /product/virtualtryon | 虛擬試穿 Try-On | ✅ 已有 |
| 商品場景圖 | /product/editscene | Product Scene（同一工具） | ✅ 已有 |
| 批量抠图 | /product/rmbg | 背景移除（單張）；**批量** | ⚠️ 缺批量 |
| 商品图编辑 | /product/editimage | 部分由 Effect / 產品增強 | ⚠️ 部分 |
| 模特试衣 / AI换模特 / 模特换背景 | 多個子頁 | Try-On + Product Scene 涵蓋部分 | ⚠️ 可強化文案/預設 |

**小結：** 核心「白底、場景、試穿」已對齊；可補 **批量抠图 API + 前端批次上傳**。

---

### 2. 建築室內（豆绘）→ VidGo 空間設計

| 豆绘AI 功能 | 豆绘路徑 | VidGo 對應 | 狀態 |
|-------------|----------|------------|------|
| 毛坯房精装 | /creative/roughcast | 空間重設計 Room Redesign | ✅ 已有 |
| 风格转换 | /creative/idtransform | 室內風格 (interior) | ✅ 已有 |
| 效果图后期/增强、3D渲染、线稿、彩平图、场景加模特、软硬装替换 | 多個子頁 | 部分在 generation/interior | ⚠️ 進階功能可後續擴充 |

**小結：** 主功能「毛坯精裝」已對齊；其餘屬進階，可列為 Phase 2。

---

### 3. 視頻創作（豆绘）→ VidGo AI 影片

| 豆绘AI 功能 | 豆绘路徑 | VidGo 對應 | 狀態 |
|-------------|----------|------------|------|
| 图生视频 | /video/image2video | 短影片 Short Video (I2V) | ✅ 已有 |
| 文生视频 | /video/text2video | 短影片 (T2V) | ✅ 已有 |
| 数字人口播 | /video/aipresenter | AI 數位人 AI Avatar | ✅ 已有 |
| 视频特效 | /video/videoeffects | 目前無獨立「影片特效」 | ⚠️ 可選 |
| 首尾帧、Veo、Sora、文生音频 | 多個子頁 | 目前未對應 | ⚠️ Phase 2 |

**小結：** 圖生視頻、文生視頻、數字人已對齊；其餘可後續對齊。

---

### 4. AI 創作 / 編輯應用（豆绘）→ VidGo 圖像與效果

| 豆绘AI 功能 | 豆绘路徑 | VidGo 對應 | 狀態 |
|-------------|----------|------------|------|
| 文生图 | /creative/txt2img | Generation T2I | ✅ 後端有 |
| 图生图/图片重绘 | /creative/repainting | Effect (I2I 風格) | ✅ 已有 |
| 换风格 / 风格转换 | editimage/changestyle | 圖片風格 Image Effects | ✅ 已有 |
| 高清放大 | editimage/upscale | Effects HD Enhance | ✅ 後端有 |
| 无损抠图 | editimage/ps 或 /product/rmbg | 背景移除 | ✅ 已有 |
| AI换背景 | editimage/changebg | 可視為「場景圖」或擴充 | ⚠️ 部分 |
| 万能改图、描述词反推、多图融合、线稿渲染、相似图生成、局部修改、去水印、扩图、消除、修复、裁剪、去色、一键美化 | 多個 | 部分無直接對應 | ❌ 多數為缺口 |

**小結：** 文生图、图生图/风格、抠图、高清放大 已對齊或後端具備；**描述词反推 (Prompt 反推)**、**批量处理** 為高價值且可與現有 UI 整合。

---

### 5. 人像寫真（豆绘）

| 豆绘AI 功能 | 豆绘路徑 | VidGo 對應 | 狀態 |
|-------------|----------|------------|------|
| 人像换脸、老照片修复、人像变清晰、照片上色、AI证件照、AI写真、换发型、真人转漫画 | 多個 | 目前無專門「人像」工具 | ❌ 缺口 |

**小結：** 屬獨立產品線，可列 Phase 2；若只做「與豆绘功能接近」且 UI 不變，可先以**導航/文案**將「人像變清晰」對到現有 **Effect / 高清**，其餘後續再加。

---

### 6. 其他豆绘功能

| 豆绘AI 功能 | VidGo 對應 | 狀態 |
|-------------|------------|------|
| 我的作品 | 我的作品 My Works | ✅ 已有 |
| 图片库 / 参考图 | 目前無統一「圖片庫」 | ⚠️ 可選 |
| 批量生成 | 目前單次生成 | ⚠️ 缺批量 |
| 模型训练 | 無 | ❌ Phase 2+ |
| 邀请好友送豆点、每日领豆点、充值 | 訂閱/點數/推廣 | ⚠️ 部分有（訂閱與點數） |

---

## 二、優先對齊清單（功能接近、UI 維持現狀）

以下依「與豆绘對齊」且「改動集中在後端或既有頁面」排序。

### Phase 1（建議先做）

1. **批量抠图 (批量去背)**  
   - 後端：`POST /api/v1/tools/remove-bg/batch` 已存在，確認支援多張上傳與回傳多結果。  
   - 前端：在現有 **Background Removal** 頁面加上「多圖上傳」與結果列表（UI 維持現有風格）。

2. **描述词反推 (Prompt 反推)**  
   - 豆绘：輸入圖片 → 輸出描述詞。  
   - 後端：`GeminiService.describe_image` 已存在，可新增 `POST /api/v1/prompts/reverse` 或 `POST /api/v1/demo/describe-image`（接收 image_url，回傳 description / prompt 文字）。  
   - 前端：在 **Effect** 或 **Product Scene** 頁面加「從圖片反推描述」按鈕與欄位（不新增整頁，維持現狀）。

3. **文生图 (T2I) 入口**  
   - 豆绘有明顯「文生图」入口。  
   - VidGo 已有 `POST /api/v1/generate/t2i`。  
   - 前端：在 Landing 或既有「AI 圖像」區塊增加「文生图」入口，接到現有 generation 或新建一個最小 **Text2Image.vue**（沿用現有工具頁版型）。

4. **「免費創作」對齊**  
   - 豆绘有免費創作。  
   - 維持現有 **Preset-Only / Demo** 流程，在文案與 Landing 上標示「免費試用 / 免費創作」即可。

### Phase 2（其後對齊）

5. **批量生成（多張圖一次生成）**  
   - 後端：支援多 prompt 或多檔的 batch 介面。  
   - 前端：在現有工具頁加「批次」模式（同一 UI 風格）。

6. **圖片編輯類**  
   - 去水印、扩图、局部修改、消除、修复、裁剪、去色、一键美化：依 API 能力逐步對接，在 **Effect** 或新「圖片編輯」頁用現有版型呈現。

7. **人像寫真**  
   - 若後端有人像類 API，可集中一個「人像」入口，底下多個子功能用現有工具頁版型。

8. **视频特效、首尾帧、文生音频**  
   - 依後端能力與優先級逐步對齊，仍用現有 Short Video / Avatar 頁面擴充。

---

## 三、Landing / 導航文案對齊（UI 不變、只改文案與分組）

- **產品電商：** 一鍵白底圖、一鍵場景圖、AI 試穿 → 維持現有三個工具，文案與豆绘對齊。  
- **建築室內：** 毛坯房精裝、風格轉換 → 維持 Room Redesign + Interior，文案對齊。  
- **視頻創作：** 图生视频、文生视频、数字人口播 → 維持 Short Video + Avatar，文案對齊。  
- **AI 創作 / 編輯：** 文生图、图生图、换风格、高清放大、抠图 → 在現有 Effect、Generation、Background Removal 的入口與說明上對齊用詞。

---

## 四、實作檢查表（Phase 1）

- [ ] 批量抠图：後端 batch 行為確認；前端多圖上傳 + 結果列表（同一頁）。  
- [ ] 描述词反推：後端 API；前端在 Effect 或 Product Scene 加「反推」按鈕。  
- [ ] 文生图：前端入口 + 最小 T2I 頁（或接現有 generation）。  
- [ ] Landing / 導航：文案與豆绘對齊（一鍵白底圖、一鍵場景圖、毛坯房精装、图生视频、数字人口播 等）。

## 五、試玩功能（已實作）

- [x] **固定提示詞試玩**：使用者選擇固定 prompts → 查詢 Material DB → 顯示結果
- [x] **訂閱者專屬**：只有訂閱者可上傳自訂資料、呼叫 real API、下載無水印結果
- [x] **Material 空庫處理**：當 product_scene / effect / background_removal 無資料時：
  - 前端顯示 try_prompts（固定提示詞選項）
  - 執行 `python -m scripts.seed_materials_if_empty` 呼叫 real API 預生成
  - Effect 如需動態效果描述，可使用 `GeminiService.generate_effect_prompt_for_image()`

完成以上後，功能與豆绘的對齊度會明顯提高，且 **UI 維持現狀**。
