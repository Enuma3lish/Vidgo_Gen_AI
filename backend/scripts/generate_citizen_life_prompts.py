#!/usr/bin/env python3
"""
Generate Citizen Life Product Prompts for AI Avatar

Generates promotional scripts for everyday Taiwanese/Chinese products
(NOT luxury items, NOT services). Output is compatible with:
- app/config/try_prompts.py (AI_AVATAR_TRY_PROMPTS format)
- scripts/main_pregenerate.py (SCRIPT_MAPPING format)

Usage:
    python -m scripts.generate_citizen_life_prompts                       # Print both formats
    python -m scripts.generate_citizen_life_prompts --format try_prompts  # try_prompts.py format
    python -m scripts.generate_citizen_life_prompts --format script_mapping  # SCRIPT_MAPPING format
    python -m scripts.generate_citizen_life_prompts --validate-only       # Validate only
    python -m scripts.generate_citizen_life_prompts --output prompts.json # Write to JSON file
"""
import argparse
import json
import sys
from typing import Any, Dict, List

# =============================================================================
# CITIZEN LIFE PRODUCT TAXONOMY
# =============================================================================
# All products: everyday affordable items for Taiwanese/Chinese consumers
# Exclusions: watches, jewelry, designer goods, luxury cosmetics, high-end tech

CITIZEN_LIFE_PRODUCTS = {
    "kitchen_household": [
        {"key": "thermos", "name_en": "Vacuum Thermos Bottle", "name_zh": "保溫瓶", "price_range": "399-890"},
        {"key": "rice_cooker", "name_en": "Smart Rice Cooker", "name_zh": "智慧電子鍋", "price_range": "1290-2490"},
        {"key": "lunch_box", "name_en": "Stainless Steel Lunch Box", "name_zh": "不鏽鋼便當盒", "price_range": "299-599"},
    ],
    "personal_care": [
        {"key": "shampoo", "name_en": "Herbal Shampoo", "name_zh": "草本洗髮精", "price_range": "299-599"},
        {"key": "face_mask", "name_en": "Hydrating Face Mask", "name_zh": "保濕面膜", "price_range": "199-499"},
        {"key": "sunscreen", "name_en": "Daily Sunscreen SPF50", "name_zh": "防曬乳", "price_range": "350-690"},
    ],
    "food_beverages": [
        {"key": "tea_leaves", "name_en": "Alishan Oolong Tea", "name_zh": "阿里山烏龍茶", "price_range": "390-890"},
        {"key": "dried_fruit", "name_en": "Dried Mango Snack", "name_zh": "芒果乾", "price_range": "150-299"},
        {"key": "soy_sauce", "name_en": "Naturally Brewed Soy Sauce", "name_zh": "天然釀造醬油", "price_range": "159-349"},
    ],
    "electronics": [
        {"key": "toothbrush", "name_en": "Sonic Electric Toothbrush", "name_zh": "音波電動牙刷", "price_range": "599-1290"},
        {"key": "desk_lamp", "name_en": "LED Desk Lamp", "name_zh": "LED護眼檯燈", "price_range": "490-990"},
        {"key": "earbuds", "name_en": "Wireless Earbuds", "name_zh": "無線藍牙耳機", "price_range": "590-1290"},
        {"key": "charger", "name_en": "Fast Charging Cable Set", "name_zh": "快充充電組", "price_range": "299-699"},
    ],
    "cleaning": [
        {"key": "laundry_detergent", "name_en": "Plant-Based Laundry Detergent", "name_zh": "植物系洗衣精", "price_range": "199-399"},
    ],
    "baby_kids": [
        {"key": "baby_bottle", "name_en": "Anti-Colic Baby Bottle", "name_zh": "防脹氣奶瓶", "price_range": "350-690"},
    ],
}

# =============================================================================
# VALIDATION KEYWORDS
# =============================================================================

EXCLUDED_LUXURY_KEYWORDS = [
    "watch", "jewelry", "diamond", "gold", "luxury", "designer",
    "handbag", "perfume", "premium beauty", "high-end",
    "手錶", "珠寶", "鑽石", "黃金", "奢華", "精品", "名牌", "高端",
    "頂級", "奢華美妝",
]

EXCLUDED_SERVICE_KEYWORDS = [
    "salon", "grooming", "repair shop", "class", "studio",
    "美甲", "寵物美容", "維修店", "課程", "工作室",
]

CATEGORY_ZH_MAP = {
    "spokesperson": "品牌故事",
    "product_intro": "產品開箱",
    "customer_service": "客戶服務",
    "social_media": "社群行銷",
}

# =============================================================================
# 12 CITIZEN LIFE PRODUCT SCRIPTS
# =============================================================================
# 4 categories x 3 scripts each
# All product-focused, no services
# Bilingual: EN + ZH-TW (Traditional Chinese)
# Avatars: Chinese/Taiwanese men and women

CITIZEN_LIFE_SCRIPTS = {
    # spokesperson: Origin story / brand storytelling (builds trust)
    "spokesperson": [
        {
            "id": "spokesperson-1",
            "text_en": (
                "My father was an ironworker. He carried a cheap thermos every day "
                "and it always leaked. That is why I spent two years developing this "
                "vacuum bottle—double-wall stainless steel, keeps drinks hot for 12 hours. "
                "We have sold over 8000 since last year. Only 599. Try it risk-free with "
                "our 30-day money-back guarantee!"
            ),
            "text_zh": (
                "我爸是做鐵工的，每天帶一個便宜保溫瓶，總是會漏水。"
                "所以我花了兩年研發這款真空保溫瓶——雙層不鏽鋼，保溫12小時。"
                "去年到現在賣超過8000個，只要599元。"
                "30天不滿意全額退費，放心試！"
            ),
        },
        {
            "id": "spokesperson-2",
            "preferred_gender": "female",
            "text_en": (
                "My grandmother used to wash her hair with natural herbs from the mountains. "
                "At 80, she still had thick, beautiful hair. I turned her recipe into this "
                "shampoo—no silicone, no sulfate, just 12 kinds of herbal extracts. Over "
                "3000 customers have switched to us this year. 399 per bottle. Your hair "
                "will thank you!"
            ),
            "text_zh": (
                "阿嬤以前都用山上採的天然草本洗頭，80歲頭髮還是又黑又亮。"
                "我把她的配方做成了這瓶洗髮精——無矽靈、無硫酸鹽，12種草本精華。"
                "今年已經有超過3000位客人轉用。每瓶399元，你的頭髮會感謝你！"
            ),
        },
        {
            "id": "spokesperson-3",
            "preferred_gender": "male",
            "text_en": (
                "My family has been growing tea in Alishan for three generations. Every "
                "spring I hand-pick the leaves at dawn when the dew is still fresh. This "
                "oolong goes through five stages of roasting over 72 hours. One sip and you "
                "will taste the mountain. 150 grams for 590. We ship same-day, vacuum-sealed "
                "for freshness!"
            ),
            "text_zh": (
                "我家在阿里山種茶已經三代了。每年春天我天亮就上山手採，趁露水還在的時候。"
                "這款烏龍經過72小時五道烘焙。喝一口，你就能嚐到山的味道。"
                "150克只要590元，當天出貨、真空包裝鎖住鮮味！"
            ),
        },
    ],
    # product_intro: Social proof / before-after / demo (shows results)
    "product_intro": [
        {
            "id": "product-intro-1",
            "preferred_gender": "female",
            "text_en": (
                "Check this out—I just put in rice, water, and pressed one button. 25 minutes "
                "later? Perfect fluffy rice, every single time. This smart cooker has 8 "
                "cooking modes, a non-stick inner pot, and a 24-hour timer. Over 1500 "
                "five-star reviews online. Only 1290 for restaurant-quality rice at home. "
                "Free shipping this week!"
            ),
            "text_zh": (
                "你看——我只要放米、加水、按一個按鈕，25分鐘後就是粒粒分明的完美白飯，"
                "每次都一樣。這台智慧電子鍋有8種模式、不沾內鍋、24小時預約。"
                "網路上超過1500則五星評價。只要1290元，在家就能煮出餐廳等級的飯。本週免運費！"
            ),
        },
        {
            "id": "product-intro-2",
            "preferred_gender": "male",
            "text_en": (
                "I used to brush for 30 seconds and call it done. Then my dentist said I "
                "had three cavities. I switched to this sonic toothbrush—40000 vibrations "
                "per minute, 2-minute smart timer, 30-day battery life. Six months later, "
                "zero cavities. 799 with two extra brush heads. Your teeth will thank you!"
            ),
            "text_zh": (
                "以前我刷牙30秒就覺得好了，結果牙醫說我有三顆蛀牙。"
                "換了這支音波牙刷——每分鐘40000次震動、2分鐘智慧計時、充一次電用30天。"
                "半年後零蛀牙。799元附兩個替換刷頭，你的牙齒會感謝你！"
            ),
        },
        {
            "id": "product-intro-3",
            "text_en": (
                "I compared 20 desk lamps before choosing this one. Zero flicker, adjustable "
                "color temperature from warm to cool, and a built-in USB charging port. My "
                "eyes stopped hurting after late-night work. 690 and it comes with a 2-year "
                "warranty. Over 800 students and remote workers recommend it. Light up your "
                "workspace!"
            ),
            "text_zh": (
                "我比較了20款檯燈才選了這一台。零頻閃、色溫可調從暖光到白光、還有USB充電孔。"
                "加班到深夜眼睛不再痠痛。690元含兩年保固。"
                "超過800位學生和遠距工作者推薦。照亮你的工作空間！"
            ),
        },
    ],
    # customer_service: Trust-building / guarantee (reduces purchase anxiety)
    "customer_service": [
        {
            "id": "customer-service-1",
            "preferred_gender": "male",
            "text_en": (
                "Worried about buying a charging cable online? I understand. That is why "
                "every cable we sell goes through a 5000-bend test. If it breaks within one "
                "year, we replace it for free—no questions asked. Just message us on LINE "
                "with your order number. Over 10000 cables sold, replacement rate under "
                "0.5 percent. 349 for a set of two!"
            ),
            "text_zh": (
                "擔心網路買充電線踩雷？我懂。所以我們每條線都通過5000次彎折測試。"
                "一年內斷裂免費換新——不問原因。LINE傳訂單號碼就好。"
                "賣出超過10000條，換貨率不到0.5%。兩條一組只要349元！"
            ),
        },
        {
            "id": "customer-service-2",
            "preferred_gender": "female",
            "text_en": (
                "A lot of moms ask me: is this laundry detergent really safe for baby "
                "clothes? Let me answer. It is 99 percent plant-derived, dermatologist-tested, "
                "and free of fluorescent agents. We even have the SGS test report on our "
                "website. 2000ml for only 299. Perfect for the whole family. Questions? "
                "Message us anytime on LINE—we reply within 2 hours!"
            ),
            "text_zh": (
                "很多媽媽問我：這瓶洗衣精洗寶寶衣服真的安全嗎？讓我來回答。"
                "99%植物萃取、皮膚科醫師測試、無螢光劑。SGS檢驗報告就在我們網站上。"
                "2000ml只要299元，全家都能用。有問題隨時LINE我們，2小時內回覆！"
            ),
        },
        {
            "id": "customer-service-3",
            "preferred_gender": "female",
            "text_en": (
                "New parents, I know you have questions about our baby bottle. Here are "
                "the top three: Is it BPA-free? Yes, 100 percent. Does the anti-colic valve "
                "really work? 92 percent of parents say their baby had less gas. Can I "
                "sterilize it? Yes, it is heat-resistant up to 180 degrees. 490 per bottle. "
                "Free return within 7 days if baby does not like it!"
            ),
            "text_zh": (
                "新手爸媽，我知道你們對奶瓶有很多問題。最常問的三個：不含BPA嗎？是的，100%。"
                "防脹氣閥真的有用嗎？92%的家長說寶寶脹氣減少了。可以消毒嗎？耐熱180度沒問題。"
                "每支490元。7天內寶寶不適應可免費退貨！"
            ),
        },
    ],
    # social_media: Interactive / viral hooks / emotional (drives shares)
    "social_media": [
        {
            "id": "social-media-1",
            "preferred_gender": "female",
            "text_en": (
                "Save this video right now! This is our best-selling hydrating face mask—"
                "normally 499 for a box of 10. But today only, buy one box get one free. "
                "That is 20 masks for 499! Last time we did this, we sold out in 3 hours. "
                "Follow us and turn on notifications so you never miss a deal. Link in bio!"
            ),
            "text_zh": (
                "馬上存下這支影片！這是我們最暢銷的保濕面膜——原價一盒10片499元。"
                "但只限今天，買一送一。20片只要499！上次辦這個活動3小時就賣完了。"
                "追蹤我們開啟通知才不會錯過。連結在自介！"
            ),
        },
        {
            "id": "social-media-2",
            "preferred_gender": "male",
            "text_en": (
                "Stop scrolling—you need to hear this. These wireless earbuds have 30-hour "
                "battery life, noise cancellation, and they are waterproof. The best part? "
                "Only 890. I have been using them for 6 months at the gym, on the bus, even "
                "in the rain. Flash sale ends tonight at midnight. Tap the link now before "
                "they sell out!"
            ),
            "text_zh": (
                "先別滑了——你一定要聽聽這個。這副無線耳機續航30小時、有降噪、還防水。"
                "最棒的是只要890元。我已經用了6個月，健身房、公車上、甚至淋雨都沒問題。"
                "限時特賣今晚12點結束，趕快點連結，賣完就沒了！"
            ),
        },
        {
            "id": "social-media-3",
            "text_en": (
                "I gave this dried mango to 10 coworkers without telling them the price. "
                "Every single one guessed it costs over 300. The real price? 169 for a big "
                "bag. Made in Pingtung from Irwin mangoes, no added sugar. Tag someone who "
                "loves mango! Buy 3 bags and get free shipping. Best office snack ever!"
            ),
            "text_zh": (
                "我把這包芒果乾給10個同事吃，沒說價錢。每個人都猜超過300元。"
                "真正的價格？大包裝只要169元。屏東愛文芒果製作、無添加糖。"
                "標記一個愛吃芒果的朋友！買三包免運。辦公室最佳零嘴！"
            ),
        },
    ],
}


# =============================================================================
# VALIDATION
# =============================================================================

def validate_no_luxury(scripts: Dict[str, List[Dict]]) -> List[str]:
    """Check that no script contains luxury keywords."""
    errors = []
    for category, items in scripts.items():
        for item in items:
            text = (item.get("text_en", "") + " " + item.get("text_zh", "")).lower()
            for kw in EXCLUDED_LUXURY_KEYWORDS:
                if kw.lower() in text:
                    errors.append(f"[{item['id']}] contains luxury keyword: '{kw}'")
    return errors


def validate_no_services(scripts: Dict[str, List[Dict]]) -> List[str]:
    """Check that no script promotes a service instead of a product."""
    errors = []
    for category, items in scripts.items():
        for item in items:
            text = (item.get("text_en", "") + " " + item.get("text_zh", "")).lower()
            for kw in EXCLUDED_SERVICE_KEYWORDS:
                if kw.lower() in text:
                    errors.append(f"[{item['id']}] contains service keyword: '{kw}'")
    return errors


def validate_bilingual(scripts: Dict[str, List[Dict]]) -> List[str]:
    """Check that every script has both EN and ZH text."""
    errors = []
    for category, items in scripts.items():
        for item in items:
            if not item.get("text_en", "").strip():
                errors.append(f"[{item['id']}] missing text_en")
            if not item.get("text_zh", "").strip():
                errors.append(f"[{item['id']}] missing text_zh")
    return errors


def validate_structure(scripts: Dict[str, List[Dict]]) -> List[str]:
    """Check category count and ID uniqueness."""
    errors = []
    expected_categories = {"spokesperson", "product_intro", "customer_service", "social_media"}
    if set(scripts.keys()) != expected_categories:
        errors.append(f"Expected categories {expected_categories}, got {set(scripts.keys())}")

    for category, items in scripts.items():
        if len(items) != 3:
            errors.append(f"[{category}] expected 3 scripts, got {len(items)}")

    all_ids = [item["id"] for items in scripts.values() for item in items]
    if len(all_ids) != len(set(all_ids)):
        dupes = [x for x in all_ids if all_ids.count(x) > 1]
        errors.append(f"Duplicate IDs: {set(dupes)}")

    return errors


def run_all_validations(scripts: Dict[str, List[Dict]]) -> List[str]:
    """Run all validation checks and return list of errors."""
    errors = []
    errors.extend(validate_structure(scripts))
    errors.extend(validate_bilingual(scripts))
    errors.extend(validate_no_luxury(scripts))
    errors.extend(validate_no_services(scripts))
    return errors


# =============================================================================
# OUTPUT FORMATTERS
# =============================================================================

def format_as_try_prompts(scripts: Dict[str, List[Dict]]) -> List[Dict[str, Any]]:
    """
    Convert CITIZEN_LIFE_SCRIPTS to AI_AVATAR_TRY_PROMPTS format
    (used in app/config/try_prompts.py).
    """
    result = []
    for category, items in scripts.items():
        for item in items:
            entry = {
                "id": item["id"],
                "topic": category,
                "prompt_en": item["text_en"],
                "prompt_zh": item["text_zh"],
                "category": category,
                "category_zh": CATEGORY_ZH_MAP[category],
            }
            result.append(entry)
    return result


def format_as_script_mapping(scripts: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
    """
    Return scripts in SCRIPT_MAPPING format
    (used in scripts/main_pregenerate.py).
    Already in the correct format, just return as-is.
    """
    return scripts


def print_try_prompts_python(prompts: List[Dict[str, Any]]) -> str:
    """Format try_prompts output as Python source code."""
    lines = ["AI_AVATAR_TRY_PROMPTS: List[Dict[str, Any]] = ["]
    for p in prompts:
        lines.append("    {")
        lines.append(f'        "id": "{p["id"]}", "topic": "{p["topic"]}",')
        lines.append(f'        "prompt_en": "{p["prompt_en"]}",')
        lines.append(f'        "prompt_zh": "{p["prompt_zh"]}",')
        lines.append(f'        "category": "{p["category"]}", "category_zh": "{p["category_zh"]}",')
        lines.append("    },")
    lines.append("]")
    return "\n".join(lines)


def print_script_mapping_python(scripts: Dict[str, List[Dict]]) -> str:
    """Format SCRIPT_MAPPING output as Python source code."""
    lines = ["SCRIPT_MAPPING = {"]
    for category, items in scripts.items():
        lines.append(f'    "{category}": [')
        for item in items:
            lines.append("        {")
            lines.append(f'            "id": "{item["id"]}",')
            if "preferred_gender" in item:
                lines.append(f'            "preferred_gender": "{item["preferred_gender"]}",')
            # Use repr() to safely handle quotes in text
            lines.append(f'            "text_en": {repr(item["text_en"])},')
            lines.append(f'            "text_zh": {repr(item["text_zh"])}')
            lines.append("        },")
        lines.append("    ],")
    lines.append("}")
    return "\n".join(lines)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate citizen life product prompts for AI Avatar"
    )
    parser.add_argument(
        "--format",
        choices=["try_prompts", "script_mapping", "both"],
        default="both",
        help="Output format (default: both)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write output to file (JSON or Python based on extension)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only run validation checks, do not output prompts",
    )
    args = parser.parse_args()

    # Always validate first
    print("=" * 70)
    print("Citizen Life Product Prompt Generator")
    print("=" * 70)

    errors = run_all_validations(CITIZEN_LIFE_SCRIPTS)
    if errors:
        print("\nVALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1

    total = sum(len(items) for items in CITIZEN_LIFE_SCRIPTS.values())
    print(f"\nValidation passed! {total} scripts, 0 errors.")

    # Show product summary
    print(f"\nProduct categories: {len(CITIZEN_LIFE_PRODUCTS)}")
    for cat, products in CITIZEN_LIFE_PRODUCTS.items():
        names = ", ".join(p["name_en"] for p in products)
        print(f"  {cat}: {names}")

    # Show script summary
    print(f"\nScript categories: {len(CITIZEN_LIFE_SCRIPTS)}")
    for cat, items in CITIZEN_LIFE_SCRIPTS.items():
        print(f"  {cat} ({CATEGORY_ZH_MAP[cat]}): {len(items)} scripts")
        for item in items:
            gender = item.get("preferred_gender", "any")
            print(f"    - {item['id']} (gender: {gender})")

    if args.validate_only:
        print("\n[validate-only] No output generated.")
        return 0

    # Generate output
    print("\n" + "=" * 70)

    if args.format in ("try_prompts", "both"):
        prompts = format_as_try_prompts(CITIZEN_LIFE_SCRIPTS)
        print("\n## Format: AI_AVATAR_TRY_PROMPTS (for try_prompts.py)\n")
        print(print_try_prompts_python(prompts))

    if args.format in ("script_mapping", "both"):
        print("\n## Format: SCRIPT_MAPPING (for main_pregenerate.py)\n")
        print(print_script_mapping_python(CITIZEN_LIFE_SCRIPTS))

    # Write to file if requested
    if args.output:
        data = {}
        if args.format in ("try_prompts", "both"):
            data["try_prompts"] = format_as_try_prompts(CITIZEN_LIFE_SCRIPTS)
        if args.format in ("script_mapping", "both"):
            data["script_mapping"] = format_as_script_mapping(CITIZEN_LIFE_SCRIPTS)

        if args.output.endswith(".json"):
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"\nWritten to {args.output}")
        else:
            # Write as Python
            with open(args.output, "w", encoding="utf-8") as f:
                if "try_prompts" in data:
                    f.write(print_try_prompts_python(data["try_prompts"]))
                    f.write("\n\n")
                if "script_mapping" in data:
                    f.write(print_script_mapping_python(data["script_mapping"]))
                    f.write("\n")
            print(f"\nWritten to {args.output}")

    print("\n" + "=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
