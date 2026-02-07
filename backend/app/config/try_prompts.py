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
    {"id": "bubble-tea-studio", "topic": "studio", "prompt_en": "Bubble tea in studio lighting", "prompt_zh": "珍珠奶茶攝影棚場景", "product": "bubble_tea", "scene": "studio"},
    {"id": "fried-chicken-lifestyle", "topic": "lifestyle", "prompt_en": "Fried chicken box in lifestyle setting", "prompt_zh": "炸雞排生活風格場景", "product": "fried_chicken", "scene": "lifestyle"},
    {"id": "bento-minimal", "topic": "minimal", "prompt_en": "Lunch bento box minimalist style", "prompt_zh": "便當極簡風格", "product": "bento", "scene": "minimal"},
    {"id": "backpack-nature", "topic": "nature", "prompt_en": "Student backpack in nature setting", "prompt_zh": "學生書包自然場景", "product": "backpack", "scene": "nature"},
    {"id": "soap-studio", "topic": "studio", "prompt_en": "Handmade soap studio shot", "prompt_zh": "手工皂棚拍", "product": "soap", "scene": "studio"},
    {"id": "cake-seasonal", "topic": "seasonal", "prompt_en": "Birthday cake in seasonal setting", "prompt_zh": "生日蛋糕季節性場景", "product": "cake", "scene": "seasonal"},
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
# Focus: Small personal business promotion techniques
# Each script demonstrates a DIFFERENT promotional strategy that SMB owners would want to copy
AI_AVATAR_TRY_PROMPTS: List[Dict[str, Any]] = [
    {
        "id": "spokesperson-1", "topic": "spokesperson",
        "prompt_en": "I started this bubble tea shop 3 years ago with one recipe from my grandmother. Today we sell over 500 cups a day. Our secret? Real milk, hand-cooked pearls, no shortcuts. Come taste the difference—first cup free for new customers!",
        "prompt_zh": "三年前我用阿嬤的一個配方開了這家珍珠奶茶店。現在每天賣超過500杯。我們的秘訣？鮮奶、手煮珍珠、不偷工減料。來嚐嚐看有什麼不同——新客人第一杯免費！",
        "category": "spokesperson", "category_zh": "品牌故事",
    },
    {
        "id": "spokesperson-2", "topic": "spokesperson",
        "prompt_en": "Every morning at 5 AM, I bake these matcha cream rolls fresh. Only 50 per day because I refuse to use preservatives. When they are gone, they are gone. That is why our customers line up before we open. Come try one before today's batch sells out!",
        "prompt_zh": "每天早上五點，我親手烤製這些抹茶生乳捲。因為堅持不加防腐劑，每日限量50條。賣完就沒有了，這就是為什麼客人都在開店前排隊。快來嚐一條，今天的很快就賣完了！",
        "category": "spokesperson", "category_zh": "品牌故事",
    },
    {
        "id": "spokesperson-3", "topic": "spokesperson",
        "prompt_en": "My customers always ask: how do you make nails look this good? Let me show you. This is our signature aurora cat-eye gel. Three layers, hand-painted gradient. It takes me 90 minutes per set. Book this week and get a free nail art upgrade worth 300!",
        "prompt_zh": "客人常問我：怎麼做出這麼美的指甲？讓我示範一下。這是我們的招牌極光貓眼凝膠，三層手繪漸層，每一組要90分鐘。本週預約送價值300元的美甲升級！",
        "category": "spokesperson", "category_zh": "品牌故事",
    },
    {
        "id": "product-intro-1", "topic": "product_intro",
        "prompt_en": "See this phone case? Customers said it survived a drop from a second-floor balcony. We tested it ourselves—dropped it 50 times. Still perfect. Military-grade protection, only 399. No wonder it is our best-seller with over 2000 five-star reviews!",
        "prompt_zh": "看這個手機殼？客人說它從二樓陽台掉下來都沒事。我們自己測試過——摔了50次，完好如初。軍規防護，只要399元。難怪它是我們的暢銷品，超過2000則五星評價！",
        "category": "product_intro", "category_zh": "產品開箱",
    },
    {
        "id": "product-intro-2", "topic": "product_intro",
        "prompt_en": "Left side: my skin one month ago. Right side: today. The only thing I changed was this serum. 100% plant-based, no alcohol, safe for sensitive skin. 599 for 30ml—that is less than 20 per day. Your skin deserves this. Free shipping over 1000!",
        "prompt_zh": "左邊是一個月前的我的皮膚，右邊是今天。唯一的改變就是這瓶精華液。100%植萃、無酒精、敏感肌也能用。30ml只要599元，每天不到20元。你的肌膚值得擁有。滿千免運！",
        "category": "product_intro", "category_zh": "產品開箱",
    },
    {
        "id": "product-intro-3", "topic": "product_intro",
        "prompt_en": "I make each candle by hand using soy wax and essential oils. This lavender one takes 48 hours to cure. Smell it once and you will understand why 80% of my customers reorder. Only 280 each. Light one up tonight and feel the difference!",
        "prompt_zh": "每一顆蠟燭都是我用大豆蠟和精油手工製作的。這款薰衣草需要48小時熟成。聞一次你就知道為什麼八成的客人都會回購。每顆只要280元。今晚點一顆，感受不一樣的品質！",
        "category": "product_intro", "category_zh": "產品開箱",
    },
    {
        "id": "customer-service-1", "topic": "customer_service",
        "prompt_en": "Got your order and something is not right? Do not worry at all. Send us a photo on LINE and we will fix it within 24 hours—exchange, refund, or reship. That is our promise. We have handled over 5000 orders and our satisfaction rate is 99.2%!",
        "prompt_zh": "收到商品有問題嗎？完全不用擔心！LINE我們傳張照片，24小時內處理完畢——換貨、退款、重寄都可以。這是我們的承諾。超過5000筆訂單，滿意度99.2%！",
        "category": "customer_service", "category_zh": "客戶服務",
    },
    {
        "id": "customer-service-2", "topic": "customer_service",
        "prompt_en": "Welcome to our pet grooming studio! Before your first visit, let me explain how we work. We spend 15 minutes just letting your pet get comfortable. No rushing, no stress. That is why nervous dogs love coming back. Book a trial grooming for only 399!",
        "prompt_zh": "歡迎來到我們的寵物美容工作室！第一次來之前讓我說明一下。我們會花15分鐘讓毛孩先適應環境，不趕時間、零壓力。所以怕生的狗狗都喜歡回來。體驗價只要399元！",
        "category": "customer_service", "category_zh": "客戶服務",
    },
    {
        "id": "customer-service-3", "topic": "customer_service",
        "prompt_en": "Three things that make our repair shop different: one, we diagnose for free. Two, we only charge if we fix it. Three, every repair comes with a 90-day warranty. Fair and simple. Bring your phone in today—most repairs done in under one hour!",
        "prompt_zh": "我們維修店有三個不同：第一，免費檢測。第二，修不好不收費。第三，每次維修都有90天保固。公平、簡單。今天就帶手機來——大部分維修一小時內完成！",
        "category": "customer_service", "category_zh": "客戶服務",
    },
    {
        "id": "social-media-1", "topic": "social_media",
        "prompt_en": "Save this video! Show it at checkout and get buy-one-get-one-free on all drinks today only. We do this every Tuesday—follow us so you never miss it. Last week 200 people used this deal. Do not miss out this time!",
        "prompt_zh": "存下這支影片！結帳時出示就能全品項飲料買一送一，限今天。每週二都有這個活動——追蹤我們才不會錯過。上週有200人使用了這個優惠，這次別再錯過了！",
        "category": "social_media", "category_zh": "社群行銷",
    },
    {
        "id": "social-media-2", "topic": "social_media",
        "prompt_en": "A customer sent me this photo—she gave our flower box to her mom and her mom cried happy tears. That is why I do this. Mother's Day carnation boxes, handwrapped with love, only 680. Order by Friday for free delivery. Let us make someone smile together!",
        "prompt_zh": "一位客人傳了這張照片給我——她把我們的花禮盒送給媽媽，媽媽感動到流淚。這就是我做這行的原因。母親節康乃馨禮盒，用心手作包裝，只要680元。週五前預訂免運。一起讓人微笑吧！",
        "category": "social_media", "category_zh": "社群行銷",
    },
    {
        "id": "social-media-3", "topic": "social_media",
        "prompt_en": "Parents keep asking what their kids did in class today, so I started filming. Look at this—your child painted this in just one hour! Summer art classes, only 350 per session. Groups of 3 save 20%. Tag a parent who needs to see this!",
        "prompt_zh": "家長一直問小朋友今天上課做了什麼，所以我開始拍攝了。看這個——你的孩子一小時就畫出了這幅作品！暑假美術課，每堂只要350元。三人同行八折。標記一位需要看到這個的家長！",
        "category": "social_media", "category_zh": "社群行銷",
    },
]

# Room Redesign: room type x design style
ROOM_REDESIGN_TRY_PROMPTS: List[Dict[str, Any]] = [
    {
        "id": "living-modern-1", "topic": "living_room",
        "prompt_en": "Modern minimalist living room with warm lighting",
        "prompt_zh": "現代極簡客廳，暖色燈光",
        "room_type": "living_room", "style": "modern",
    },
    {
        "id": "bedroom-nordic-1", "topic": "bedroom",
        "prompt_en": "Nordic style bedroom with natural wood",
        "prompt_zh": "北歐風臥室，自然木質",
        "room_type": "bedroom", "style": "nordic",
    },
    {
        "id": "kitchen-industrial-1", "topic": "kitchen",
        "prompt_en": "Industrial style kitchen for cafe",
        "prompt_zh": "工業風廚房，咖啡廳風格",
        "room_type": "kitchen", "style": "industrial",
    },
    {
        "id": "bathroom-zen-1", "topic": "bathroom",
        "prompt_en": "Zen style bathroom with stone accents",
        "prompt_zh": "禪風浴室，石材點綴",
        "room_type": "bathroom", "style": "zen",
    },
    {
        "id": "living-japanese-1", "topic": "living_room",
        "prompt_en": "Japanese style living room with tatami",
        "prompt_zh": "日式客廳，榻榻米風格",
        "room_type": "living_room", "style": "japanese",
    },
]

# Short Video: video content type x product
SHORT_VIDEO_TRY_PROMPTS: List[Dict[str, Any]] = [
    {
        "id": "showcase-bubbletea-1", "topic": "product_showcase",
        "prompt_en": "Product showcase video for bubble tea shop",
        "prompt_zh": "珍珠奶茶店產品展示影片",
        "content_type": "product_showcase", "product": "bubble_tea",
    },
    {
        "id": "brand-chicken-1", "topic": "brand_intro",
        "prompt_en": "Brand introduction video for fried chicken restaurant",
        "prompt_zh": "炸雞店品牌介紹影片",
        "content_type": "brand_intro", "product": "fried_chicken",
    },
    {
        "id": "tutorial-skincare-1", "topic": "tutorial",
        "prompt_en": "Tutorial video for skincare routine",
        "prompt_zh": "保養品使用教學影片",
        "content_type": "tutorial", "product": "skincare",
    },
    {
        "id": "promo-backpack-1", "topic": "promo",
        "prompt_en": "Promotional video for student backpacks",
        "prompt_zh": "學生書包促銷影片",
        "content_type": "promo", "product": "backpack",
    },
    {
        "id": "showcase-sneaker-1", "topic": "product_showcase",
        "prompt_en": "Dynamic showcase for running sneakers",
        "prompt_zh": "運動鞋動態展示影片",
        "content_type": "product_showcase", "product": "sneaker",
    },
]

# Pattern Generate: pattern style x product application
PATTERN_GENERATE_TRY_PROMPTS: List[Dict[str, Any]] = [
    {
        "id": "seamless-bubbletea-1", "topic": "seamless",
        "prompt_en": "Seamless bubble tea pattern for packaging",
        "prompt_zh": "珍珠奶茶無縫圖案，包裝用",
        "pattern_style": "seamless", "application": "packaging",
    },
    {
        "id": "floral-skincare-1", "topic": "floral",
        "prompt_en": "Floral pattern for skincare brand packaging",
        "prompt_zh": "花卉圖案，保養品品牌包裝用",
        "pattern_style": "floral", "application": "branding",
    },
    {
        "id": "geometric-tech-1", "topic": "geometric",
        "prompt_en": "Geometric pattern for tech brand background",
        "prompt_zh": "幾何圖案，科技品牌背景用",
        "pattern_style": "geometric", "application": "background",
    },
    {
        "id": "abstract-cafe-1", "topic": "abstract",
        "prompt_en": "Abstract pattern for cafe menu design",
        "prompt_zh": "抽象圖案，咖啡廳菜單設計用",
        "pattern_style": "abstract", "application": "menu",
    },
    {
        "id": "traditional-gift-1", "topic": "traditional",
        "prompt_en": "Traditional Chinese pattern for gift wrapping",
        "prompt_zh": "傳統中式紋樣，禮品包裝用",
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
