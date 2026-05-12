# Fashion And Avatar Inputs

Use these for `/tools/try-on`, `/tools/avatar`, and `/tools/video-dubbing`.

## Try-On

Critical rule: the before/input image is clothing only. Do not put a person, mannequin body, or model photo in the garment input.

### Try-On Model References

The try-on tool combines a garment with a model image. Garments stay person-free; the
person comes from one of these full-body model templates (white tee + grey pants on
white background, neutral pose, ready to be redressed by the AI):

- `assets/try-on/model-female-1.png` — female-1 (front, neutral, hair tied back)
- `assets/try-on/model-female-2.png` — female-2 (front, weight on one leg, shoulder-length hair)
- `assets/try-on/model-male-1.png`   — male-1 (front, neutral)

1. Camel wool coat to female model
   - Model: `female-2`
   - Asset: `assets/try-on/garment-coat-only.png`
   - EN: Camel wool coat only, front-facing ecommerce garment photo, no person, clean white background, clear sleeves and collar.
   - ZH: 駝色羊毛大衣單品，正面電商服裝照，不含人物，乾淨白底，袖子與領口清楚。

2. Blue denim dress to female model
   - Model: `female-1`
   - Asset: `assets/try-on/garment-dress-only.png`
   - EN: Blue denim dress only, flat ecommerce product image, no mannequin, no person, straight front view, simple studio background.
   - ZH: 藍色丹寧洋裝單品，平面電商商品圖，無模特、無人體，正面視角，簡單棚拍背景。

3. White oversized T-shirt to male model
   - Model: `male-1`
   - EN: White oversized T-shirt only, front and sleeves visible, no person, no hanger, plain white ecommerce background.
   - ZH: 白色寬版 T 恤單品，正面與袖口清楚，無人物、無衣架，純白電商背景。

## AI Avatar / Product Spokesperson

1. Serum launch in Traditional Chinese
   - Avatar: `female-1`
   - Language: `zh-TW`
   - ZH script: 這瓶保濕精華專為台灣悶熱天氣設計，質地清爽、不黏膩。早晚各一次，讓肌膚維持穩定透亮。今天下單享免運，30 天不滿意可退。
   - EN script: This hydrating serum is designed for humid weather. It feels light, never sticky, and keeps skin calm and bright with morning and night use. Order today for free shipping and a 30-day satisfaction guarantee.

2. Bubble tea social pitch in English
   - Avatar: `male-1`
   - Language: `en`
   - EN script: Stop scrolling. Our brown sugar bubble tea is made fresh every morning, with chewy pearls and roasted caramel flavor. Buy two cups today and get the second one half off.
   - ZH script: 先別滑走。我們的黑糖珍珠奶茶每天早上現煮，珍珠 Q 彈、焦糖香濃。今天買兩杯，第二杯半價。

## Video Dubbing

1. Product launch EN to ZH
   - Video URL: `https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4`
   - Source language: `English`
   - Target language: `Traditional Chinese`
   - Source script: Meet our new seasonal bouquet. Fresh color, soft texture, and a natural look for every special moment.
   - Translated script: 認識我們全新的季節花束。清新的色彩、柔和的質感，為每個特別時刻帶來自然優雅的氛圍。

2. Brand update EN to ES
   - Video URL: `https://storage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyrides.mp4`
   - Source language: `English`
   - Target language: `Spanish`
   - Source script: A new update is here. Faster setup, cleaner visuals, and a more polished customer experience from start to finish.
   - Translated script: La nueva version ya esta aqui. Configuracion mas rapida, imagenes mas limpias y una experiencia de cliente mas cuidada de principio a fin.
