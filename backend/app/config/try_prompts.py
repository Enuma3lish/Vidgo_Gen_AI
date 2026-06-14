"""
Fixed Try Prompts - For Demo/Try-Play Mode

When Material DB is empty, these prompts define what users can "try".
Used by:
- GET /api/v1/demo/try-prompts/{tool_type} - return selectable prompts
- scripts/seed_materials_if_empty.py - same structure guides pre-generation (via main_pregenerate mappings)

Structure per tool:
- product_scene: product x scene combinations
- effect: source image prompt x style
- background_removal: topic x prompt
- try_on: clothing items with image_url for thumbnail display
- ai_avatar: script prompts with category
- room_redesign: room type x design style
- short_video: video content type x product
- pattern_generate: pattern style x product application
"""

from typing import List, Dict, Any

# Product Scene: product + scene = one try option
# Taiwan SMB focus: food, drinks, daily necessities — NOT luxury/tech
PRODUCT_SCENE_TRY_PROMPTS: List[Dict[str, Any]] = [
    {"id": "bubble-tea-studio", "topic": "studio", "prompt_en": "E-commerce product photo of bubble tea on a clean warm-white studio surface, soft diffused light, realistic condensation, centered 3/4 angle, crisp cup label, no extra text", "prompt_zh": "珍珠奶茶電商商品照，乾淨暖白攝影棚桌面，柔和棚燈，杯身凝結水珠自然，45度置中構圖，杯標清晰，不要額外文字", "product": "bubble_tea", "scene": "studio"},
    {"id": "fried-chicken-lifestyle", "topic": "lifestyle", "prompt_en": "Fried chicken box in a bright casual takeout table scene, warm daylight, appetizing steam, clean sauce props to the side, product unobstructed, social-ad ready", "prompt_zh": "炸雞盒放在明亮外帶餐桌生活場景，暖日光、誘人熱氣，醬料小道具在側邊，主商品不被遮住，適合社群廣告", "product": "fried_chicken", "scene": "lifestyle"},
    {"id": "bento-minimal", "topic": "minimal", "prompt_en": "Lunch bento box on a minimalist cream background, top-front commercial angle, neat shadow, balanced negative space for marketplace listing, natural food color", "prompt_zh": "便當盒置於極簡奶油色背景，商用正前上方角度，乾淨陰影，保留電商上架留白，食物色澤自然", "product": "bento", "scene": "minimal"},
    {"id": "backpack-nature", "topic": "nature", "prompt_en": "Student backpack staged outdoors near soft greenery, morning light, realistic fabric texture, product upright and fully visible, gentle depth of field, no people", "prompt_zh": "學生書包在柔和綠意戶外場景展示，晨光、布料紋理真實，商品直立完整可見，淺景深，不出現人物", "product": "backpack", "scene": "nature"},
    {"id": "soap-studio", "topic": "studio", "prompt_en": "Handmade soap studio hero shot with kraft paper, natural linen, soft side light, gentle shadow, premium small-brand packaging mood, readable label", "prompt_zh": "手工皂攝影棚主視覺，牛皮紙與天然亞麻布，柔和側光、細緻陰影，高質感小品牌包裝氛圍，標籤可讀", "product": "soap", "scene": "studio"},
    {"id": "cake-seasonal", "topic": "seasonal", "prompt_en": "Birthday cake seasonal campaign photo, pastel celebratory background, soft bokeh string lights, centered cake, clean plate shadow, no distorted candles or text", "prompt_zh": "生日蛋糕季節活動商品照，粉彩慶祝背景、柔和燈串散景，蛋糕置中，盤子陰影乾淨，不要扭曲蠟燭或文字", "product": "cake", "scene": "seasonal"},
]

# Effect: source x style (common people business: menu, shop, social ads)
EFFECT_TRY_PROMPTS: List[Dict[str, Any]] = [
    {"id": "bubble-tea-anime", "topic": "anime", "prompt_en": "Bubble tea in anime style for menu and social ads", "prompt_zh": "珍珠奶茶動漫風格，適合菜單與社群廣告", "source_topic": "drinks", "style": "anime"},
    {"id": "chicken-ghibli", "topic": "ghibli", "prompt_en": "Fried chicken in Ghibli style for cafe branding", "prompt_zh": "炸雞吉卜力風格，餐飲品牌用", "source_topic": "snacks", "style": "ghibli"},
    {"id": "bento-cartoon", "topic": "cartoon", "prompt_en": "Lunch bento in cartoon style for shop menu", "prompt_zh": "便當卡通風格，店面菜單用", "source_topic": "meals", "style": "cartoon"},
    {"id": "cake-oil", "topic": "oil_painting", "prompt_en": "Birthday cake in oil painting style for bakery poster", "prompt_zh": "生日蛋糕油畫風格，烘焙坊海報用", "source_topic": "desserts", "style": "oil_painting"},
    {"id": "soap-watercolor", "topic": "watercolor", "prompt_en": "Handmade soap in watercolor style for market stall", "prompt_zh": "手工皂水彩風格，市集攤位用", "source_topic": "daily", "style": "watercolor"},
]

# Background Removal: topic x prompt
BACKGROUND_REMOVAL_TRY_PROMPTS: List[Dict[str, Any]] = [
    {"id": "drinks-1", "topic": "drinks", "prompt_en": "Remove background from beverage image", "prompt_zh": "飲料圖去背"},
    {"id": "snacks-1", "topic": "snacks", "prompt_en": "Remove background from snack product", "prompt_zh": "小吃產品去背"},
    {"id": "desserts-1", "topic": "desserts", "prompt_en": "Create transparent PNG for dessert", "prompt_zh": "甜點透明去背"},
    {"id": "equipment-1", "topic": "equipment", "prompt_en": "Remove background from product", "prompt_zh": "產品圖去背"},
    {"id": "packaging-1", "topic": "packaging", "prompt_en": "Clean product cutout for e-commerce", "prompt_zh": "電商產品去背"},
]

# Try-On: clothing items with image_url for thumbnail display when DB is empty
TRY_ON_TRY_PROMPTS: List[Dict[str, Any]] = [
    {
        "id": "casual-tshirt-1", "topic": "casual",
        "prompt_en": "White casual T-shirt, clean fit", "prompt_zh": "白色休閒T恤，簡約剪裁",
        "clothing_type": "t_shirt", "category": "casual", "category_zh": "休閒服飾",
        "image_url": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400",
    },
    {
        "id": "casual-polo-1", "topic": "casual",
        "prompt_en": "Navy polo shirt for daily wear", "prompt_zh": "深藍色Polo衫，日常穿搭",
        "clothing_type": "polo", "category": "casual", "category_zh": "休閒服飾",
        "image_url": "https://images.unsplash.com/photo-1586363104862-3a5e2ab60d99?w=400",
    },
    {
        "id": "formal-blazer-1", "topic": "formal",
        "prompt_en": "Black business blazer, slim fit", "prompt_zh": "黑色商務西裝外套，修身版型",
        "clothing_type": "blazer", "category": "formal", "category_zh": "正式服飾",
        "image_url": "https://images.unsplash.com/photo-1507679799987-c73b4e84e290?w=400",
    },
    {
        "id": "dress-floral-1", "topic": "dresses",
        "prompt_en": "Floral summer dress", "prompt_zh": "碎花夏日洋裝",
        "clothing_type": "dress", "category": "dresses", "category_zh": "洋裝",
        "image_url": "https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?w=400",
    },
    {
        "id": "sportswear-jacket-1", "topic": "sportswear",
        "prompt_en": "Lightweight running jacket", "prompt_zh": "輕量慢跑外套",
        "clothing_type": "jacket", "category": "sportswear", "category_zh": "運動服",
        "image_url": "https://images.unsplash.com/photo-1556906781-9a412961c28c?w=400",
    },
    {
        "id": "outerwear-coat-1", "topic": "outerwear",
        "prompt_en": "Wool overcoat, camel color", "prompt_zh": "駝色羊毛大衣",
        "clothing_type": "coat", "category": "outerwear", "category_zh": "外套",
        "image_url": "https://images.unsplash.com/photo-1544923246-77307dd270ce?w=400",
    },
]

# AI Avatar: script prompts matching backend SCRIPT_MAPPING categories
# 4 categories × 3 scripts = 12 total
# Focus: Citizen life PRODUCTS (everyday Taiwanese/Chinese consumer goods)
# NOT luxury items (watches, jewelry), NOT services (salons, repair shops)
# Generated by: scripts/generate_citizen_life_prompts.py
AI_AVATAR_TRY_PROMPTS: List[Dict[str, Any]] = [
    {
        "id": "spokesperson-1", "topic": "spokesperson",
        "prompt_en": "My father was an ironworker. He carried a cheap thermos every day and it always leaked. That is why I spent two years developing this vacuum bottle—double-wall stainless steel, keeps drinks hot for 12 hours. We have sold over 8000 since last year. Only 599. Try it risk-free with our 30-day money-back guarantee!",
        "prompt_zh": "我爸是做鐵工的，每天帶一個便宜保溫瓶，總是會漏水。所以我花了兩年研發這款真空保溫瓶——雙層不鏽鋼，保溫12小時。去年到現在賣超過8000個，只要599元。30天不滿意全額退費，放心試！",
        "category": "spokesperson", "category_zh": "品牌故事",
    },
    {
        "id": "spokesperson-2", "topic": "spokesperson",
        "prompt_en": "My grandmother used to wash her hair with natural herbs from the mountains. At 80, she still had thick, beautiful hair. I turned her recipe into this shampoo—no silicone, no sulfate, just 12 kinds of herbal extracts. Over 3000 customers have switched to us this year. 399 per bottle. Your hair will thank you!",
        "prompt_zh": "阿嬤以前都用山上採的天然草本洗頭，80歲頭髮還是又黑又亮。我把她的配方做成了這瓶洗髮精——無矽靈、無硫酸鹽，12種草本精華。今年已經有超過3000位客人轉用。每瓶399元，你的頭髮會感謝你！",
        "category": "spokesperson", "category_zh": "品牌故事",
    },
    {
        "id": "spokesperson-3", "topic": "spokesperson",
        "prompt_en": "My family has been growing tea in Alishan for three generations. Every spring I hand-pick the leaves at dawn when the dew is still fresh. This oolong goes through five stages of roasting over 72 hours. One sip and you will taste the mountain. 150 grams for 590. We ship same-day, vacuum-sealed for freshness!",
        "prompt_zh": "我家在阿里山種茶已經三代了。每年春天我天亮就上山手採，趁露水還在的時候。這款烏龍經過72小時五道烘焙。喝一口，你就能嚐到山的味道。150克只要590元，當天出貨、真空包裝鎖住鮮味！",
        "category": "spokesperson", "category_zh": "品牌故事",
    },
    {
        "id": "product-intro-1", "topic": "product_intro",
        "prompt_en": "Check this out—I just put in rice, water, and pressed one button. 25 minutes later? Perfect fluffy rice, every single time. This smart cooker has 8 cooking modes, a non-stick inner pot, and a 24-hour timer. Over 1500 five-star reviews online. Only 1290 for restaurant-quality rice at home. Free shipping this week!",
        "prompt_zh": "你看——我只要放米、加水、按一個按鈕，25分鐘後就是粒粒分明的完美白飯，每次都一樣。這台智慧電子鍋有8種模式、不沾內鍋、24小時預約。網路上超過1500則五星評價。只要1290元，在家就能煮出餐廳等級的飯。本週免運費！",
        "category": "product_intro", "category_zh": "產品開箱",
    },
    {
        "id": "product-intro-2", "topic": "product_intro",
        "prompt_en": "I used to brush for 30 seconds and call it done. Then my dentist said I had three cavities. I switched to this sonic toothbrush—40000 vibrations per minute, 2-minute smart timer, 30-day battery life. Six months later, zero cavities. 799 with two extra brush heads. Your teeth will thank you!",
        "prompt_zh": "以前我刷牙30秒就覺得好了，結果牙醫說我有三顆蛀牙。換了這支音波牙刷——每分鐘40000次震動、2分鐘智慧計時、充一次電用30天。半年後零蛀牙。799元附兩個替換刷頭，你的牙齒會感謝你！",
        "category": "product_intro", "category_zh": "產品開箱",
    },
    {
        "id": "product-intro-3", "topic": "product_intro",
        "prompt_en": "I compared 20 desk lamps before choosing this one. Zero flicker, adjustable color temperature from warm to cool, and a built-in USB charging port. My eyes stopped hurting after late-night work. 690 and it comes with a 2-year warranty. Over 800 students and remote workers recommend it. Light up your workspace!",
        "prompt_zh": "我比較了20款檯燈才選了這一台。零頻閃、色溫可調從暖光到白光、還有USB充電孔。加班到深夜眼睛不再痠痛。690元含兩年保固。超過800位學生和遠距工作者推薦。照亮你的工作空間！",
        "category": "product_intro", "category_zh": "產品開箱",
    },
    {
        "id": "customer-service-1", "topic": "customer_service",
        "prompt_en": "Worried about buying a charging cable online? I understand. That is why every cable we sell goes through a 5000-bend test. If it breaks within one year, we replace it for free—no questions asked. Just message us on LINE with your order number. Over 10000 cables sold, replacement rate under 0.5 percent. 349 for a set of two!",
        "prompt_zh": "擔心網路買充電線踩雷？我懂。所以我們每條線都通過5000次彎折測試。一年內斷裂免費換新——不問原因。LINE傳訂單號碼就好。賣出超過10000條，換貨率不到0.5%。兩條一組只要349元！",
        "category": "customer_service", "category_zh": "客戶服務",
    },
    {
        "id": "customer-service-2", "topic": "customer_service",
        "prompt_en": "A lot of moms ask me: is this laundry detergent really safe for baby clothes? Let me answer. It is 99 percent plant-derived, dermatologist-tested, and free of fluorescent agents. We even have the SGS test report on our website. 2000ml for only 299. Perfect for the whole family. Questions? Message us anytime on LINE—we reply within 2 hours!",
        "prompt_zh": "很多媽媽問我：這瓶洗衣精洗寶寶衣服真的安全嗎？讓我來回答。99%植物萃取、皮膚科醫師測試、無螢光劑。SGS檢驗報告就在我們網站上。2000ml只要299元，全家都能用。有問題隨時LINE我們，2小時內回覆！",
        "category": "customer_service", "category_zh": "客戶服務",
    },
    {
        "id": "customer-service-3", "topic": "customer_service",
        "prompt_en": "New parents, I know you have questions about our baby bottle. Here are the top three: Is it BPA-free? Yes, 100 percent. Does the anti-colic valve really work? 92 percent of parents say their baby had less gas. Can I sterilize it? Yes, it is heat-resistant up to 180 degrees. 490 per bottle. Free return within 7 days if baby does not like it!",
        "prompt_zh": "新手爸媽，我知道你們對奶瓶有很多問題。最常問的三個：不含BPA嗎？是的，100%。防脹氣閥真的有用嗎？92%的家長說寶寶脹氣減少了。可以消毒嗎？耐熱180度沒問題。每支490元。7天內寶寶不適應可免費退貨！",
        "category": "customer_service", "category_zh": "客戶服務",
    },
    {
        "id": "social-media-1", "topic": "social_media",
        "prompt_en": "Save this video right now! This is our best-selling hydrating face mask—normally 499 for a box of 10. But today only, buy one box get one free. That is 20 masks for 499! Last time we did this, we sold out in 3 hours. Follow us and turn on notifications so you never miss a deal. Link in bio!",
        "prompt_zh": "馬上存下這支影片！這是我們最暢銷的保濕面膜——原價一盒10片499元。但只限今天，買一送一。20片只要499！上次辦這個活動3小時就賣完了。追蹤我們開啟通知才不會錯過。連結在自介！",
        "category": "social_media", "category_zh": "社群行銷",
    },
    {
        "id": "social-media-2", "topic": "social_media",
        "prompt_en": "Stop scrolling—you need to hear this. These wireless earbuds have 30-hour battery life, noise cancellation, and they are waterproof. The best part? Only 890. I have been using them for 6 months at the gym, on the bus, even in the rain. Flash sale ends tonight at midnight. Tap the link now before they sell out!",
        "prompt_zh": "先別滑了——你一定要聽聽這個。這副無線耳機續航30小時、有降噪、還防水。最棒的是只要890元。我已經用了6個月，健身房、公車上、甚至淋雨都沒問題。限時特賣今晚12點結束，趕快點連結，賣完就沒了！",
        "category": "social_media", "category_zh": "社群行銷",
    },
    {
        "id": "social-media-3", "topic": "social_media",
        "prompt_en": "I gave this dried mango to 10 coworkers without telling them the price. Every single one guessed it costs over 300. The real price? 169 for a big bag. Made in Pingtung from Irwin mangoes, no added sugar. Tag someone who loves mango! Buy 3 bags and get free shipping. Best office snack ever!",
        "prompt_zh": "我把這包芒果乾給10個同事吃，沒說價錢。每個人都猜超過300元。真正的價格？大包裝只要169元。屏東愛文芒果製作、無添加糖。標記一個愛吃芒果的朋友！買三包免運。辦公室最佳零嘴！",
        "category": "social_media", "category_zh": "社群行銷",
    },
]

# Room Redesign: 7 room topics × 6 proposal styles, matching the public tool.
_ROOM_REDESIGN_ROOMS = [
    ("living_room", "Living Room", "客廳"),
    ("bedroom", "Bedroom", "臥室"),
    ("kitchen", "Kitchen", "廚房"),
    ("bathroom", "Bathroom", "浴室"),
    ("dining_room", "Dining Room", "餐廳"),
    ("home_office", "Home Office", "書房"),
    ("balcony", "Balcony", "陽台"),
]

_ROOM_REDESIGN_STYLES = [
    ("modern_minimalist", "Modern Minimalist", "現代極簡"),
    ("scandinavian", "Scandinavian", "北歐風格"),
    ("japanese", "Japanese Zen", "日式禪風"),
    ("industrial", "Industrial", "工業風"),
    ("mediterranean", "Mediterranean", "地中海風格"),
    ("mid_century_modern", "Mid-Century Modern", "中世紀現代"),
]

ROOM_REDESIGN_TRY_PROMPTS: List[Dict[str, Any]] = [
    {
        "id": f"{room_id}-{style_id}-1",
        "topic": room_id,
        "prompt_en": f"{style_en} {room_en.lower()} proposal render, preserve layout, daylight, and spatial proportion",
        "prompt_zh": f"{style_zh}{room_zh}提案渲染，保留格局、採光與空間比例",
        "room_type": room_id,
        "style": style_id,
    }
    for room_id, room_en, room_zh in _ROOM_REDESIGN_ROOMS
    for style_id, style_en, style_zh in _ROOM_REDESIGN_STYLES
]

# Short Video: video content type x product
SHORT_VIDEO_TRY_PROMPTS: List[Dict[str, Any]] = [
    {
        "id": "showcase-bubbletea-1", "topic": "product_showcase",
        "prompt_en": "8-second vertical product showcase for a bubble tea shop. Shot 1: slow push-in on the cup with condensation. Shot 2: pearls swirl naturally. Shot 3: handoff-ready hero frame, warm daylight, no extra text.",
        "prompt_zh": "8秒直式珍珠奶茶商品展示。鏡頭1：緩慢推近杯身與凝結水珠。鏡頭2：珍珠自然旋動。鏡頭3：可交付主視覺定格，暖日光，不要額外文字。",
        "content_type": "product_showcase", "product": "bubble_tea",
    },
    {
        "id": "brand-chicken-1", "topic": "brand_intro",
        "prompt_en": "10-second restaurant brand intro for fried chicken. Shot 1: crispy box opens with steam. Shot 2: sauce dip close-up. Shot 3: clean storefront table hero shot, handheld but stable, appetizing warm color.",
        "prompt_zh": "10秒炸雞店品牌介紹。鏡頭1：酥脆餐盒打開冒熱氣。鏡頭2：沾醬特寫。鏡頭3：店面桌上乾淨主視覺，手持但穩定，暖色誘人。",
        "content_type": "brand_intro", "product": "fried_chicken",
    },
    {
        "id": "tutorial-skincare-1", "topic": "tutorial",
        "prompt_en": "12-second skincare tutorial clip. Shot 1: serum bottle on clean vanity. Shot 2: one drop on fingertip macro. Shot 3: product beside fresh towel, soft studio light, realistic glass reflections, calm pacing.",
        "prompt_zh": "12秒保養品使用教學。鏡頭1：精華瓶在乾淨梳妝台。鏡頭2：指尖一滴精華微距。鏡頭3：商品與乾淨毛巾同框，柔和棚燈、玻璃反射真實、節奏平穩。",
        "content_type": "tutorial", "product": "skincare",
    },
    {
        "id": "promo-backpack-1", "topic": "promo",
        "prompt_en": "8-second student backpack promo. Shot 1: backpack upright on desk. Shot 2: zipper opens smoothly to show capacity. Shot 3: outdoor school walkway hero frame, natural fabric motion, no people blocking product.",
        "prompt_zh": "8秒學生書包促銷。鏡頭1：書包直立在書桌。鏡頭2：拉鍊順暢打開展示容量。鏡頭3：校園走道戶外主視覺，布料動態自然，沒有人遮擋商品。",
        "content_type": "promo", "product": "backpack",
    },
    {
        "id": "showcase-sneaker-1", "topic": "product_showcase",
        "prompt_en": "10-second running sneaker showcase. Shot 1: clean turntable rotation. Shot 2: sole texture macro with light sweep. Shot 3: shoe lands on track surface, realistic shadow and dust, sharp brand-safe frame.",
        "prompt_zh": "10秒運動鞋動態展示。鏡頭1：乾淨轉台旋轉。鏡頭2：鞋底紋理與掃光微距。鏡頭3：鞋落在跑道表面，陰影與微塵真實，畫面銳利且品牌安全。",
        "content_type": "product_showcase", "product": "sneaker",
    },
]

# Pattern Generate: pattern style x product application
PATTERN_GENERATE_TRY_PROMPTS: List[Dict[str, Any]] = [
    {
        "id": "seamless-bubbletea-1", "topic": "seamless",
        "prompt_en": "Seamless bubble tea packaging pattern, tapioca pearls, cup silhouettes and tiny straw icons, milk tea beige and cocoa palette, clean repeat, no text",
        "prompt_zh": "珍珠奶茶包裝用無縫圖案，珍珠、杯子剪影與小吸管圖示，奶茶米色與可可色配色，乾淨重複，不要文字",
        "pattern_style": "seamless", "application": "packaging",
    },
    {
        "id": "floral-skincare-1", "topic": "floral",
        "prompt_en": "Boutique skincare floral pattern, white camellia petals and soft water droplets, pearl white and sage green palette, airy spacing, seamless luxury repeat",
        "prompt_zh": "保養品牌花卉圖案，白山茶花瓣與柔和水滴，珍珠白與鼠尾草綠配色，留白充足，高級無縫重複",
        "pattern_style": "floral", "application": "branding",
    },
    {
        "id": "geometric-tech-1", "topic": "geometric",
        "prompt_en": "Modern tech accessory pattern, rounded geometric modules with subtle depth, cobalt blue and graphite accents, precise tileable repeat, no logo",
        "prompt_zh": "現代科技配件圖案，圓角幾何模組帶微立體感，鈷藍與石墨灰點綴，精準可平鋪，不要 Logo",
        "pattern_style": "geometric", "application": "background",
    },
    {
        "id": "abstract-cafe-1", "topic": "abstract",
        "prompt_en": "Cafe menu abstract pattern, hand-drawn coffee bean curves, steam doodles, warm mocha and ivory, playful clean repeat with balanced negative space",
        "prompt_zh": "咖啡廳菜單抽象圖案，手繪咖啡豆曲線與蒸氣線稿，摩卡與象牙白，俏皮乾淨重複並保留留白",
        "pattern_style": "abstract", "application": "menu",
    },
    {
        "id": "traditional-gift-1", "topic": "traditional",
        "prompt_en": "Modern traditional gift-wrap pattern, cloud motifs, plum blossoms and fine line borders, red clay and muted gold palette, refined seamless print",
        "prompt_zh": "現代傳統禮品包裝圖案，雲紋、梅花與細線邊框，陶土紅與霧金配色，精緻無縫印刷",
        "pattern_style": "traditional", "application": "gift",
    },
]

TRY_PROMPTS_BY_TOOL: Dict[str, List[Dict[str, Any]]] = {
    "product_scene": PRODUCT_SCENE_TRY_PROMPTS,
    "effect": EFFECT_TRY_PROMPTS,
    "background_removal": BACKGROUND_REMOVAL_TRY_PROMPTS,
    "try_on": TRY_ON_TRY_PROMPTS,
    "ai_avatar": AI_AVATAR_TRY_PROMPTS,
    "room_redesign": ROOM_REDESIGN_TRY_PROMPTS,
    "short_video": SHORT_VIDEO_TRY_PROMPTS,
    "pattern_generate": PATTERN_GENERATE_TRY_PROMPTS,
}

# Extra fields to pass through per tool (beyond id, topic, prompt)
_EXTRA_FIELDS_BY_TOOL: Dict[str, List[str]] = {
    "try_on": ["image_url", "clothing_type", "category", "category_zh"],
    "ai_avatar": ["category", "category_zh"],
    "room_redesign": ["room_type", "style"],
    "short_video": ["content_type", "product"],
    "pattern_generate": ["pattern_style", "application"],
}


def get_try_prompts(tool_type: str, language: str = "en") -> List[Dict[str, Any]]:
    """
    Get fixed try prompts for a tool type.

    Returns list of prompt definitions that users can select.
    Includes extra fields (image_url, clothing_type, category, etc.) when available.
    """
    prompts = TRY_PROMPTS_BY_TOOL.get(tool_type, [])
    is_zh = language.startswith("zh")
    extra_fields = _EXTRA_FIELDS_BY_TOOL.get(tool_type, [])

    result = []
    for p in prompts:
        item: Dict[str, Any] = {
            "id": p["id"],
            "topic": p["topic"],
            "prompt": p["prompt_zh"] if is_zh else p["prompt_en"],
        }
        for field in extra_fields:
            if field in p:
                item[field] = p[field]
        result.append(item)
    return result
