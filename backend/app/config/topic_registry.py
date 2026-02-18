"""
VidGo Topic Registry - Single Source of Truth for Tool Topics

This module defines the OFFICIAL topics for each tool type.
All other systems (pre-generation, API endpoints, frontend) should use this registry.

IMPORTANT: This replaces the legacy demo_topics.py system.
Do NOT use TopicDefinition classes from demo_topics.py - they are deprecated.
"""
from typing import Dict, List, TypedDict
from enum import Enum


class TopicInfo(TypedDict):
    """Type definition for topic information."""
    id: str
    name_en: str
    name_zh: str


class ToolType(str, Enum):
    """8 Core Tools - must match material.py ToolType"""
    BACKGROUND_REMOVAL = "background_removal"
    PRODUCT_SCENE = "product_scene"
    TRY_ON = "try_on"
    ROOM_REDESIGN = "room_redesign"
    SHORT_VIDEO = "short_video"
    AI_AVATAR = "ai_avatar"
    PATTERN_GENERATE = "pattern_generate"
    EFFECT = "effect"


# =============================================================================
# OFFICIAL TOOL TOPICS REGISTRY
# =============================================================================

TOOL_TOPICS: Dict[str, List[TopicInfo]] = {
    # -------------------------------------------------------------------------
    # Background Removal - Product categories
    # -------------------------------------------------------------------------
    "background_removal": [
        {"id": "drinks", "name_en": "Drinks", "name_zh": "飲料"},
        {"id": "snacks", "name_en": "Snacks", "name_zh": "小吃"},
        {"id": "desserts", "name_en": "Desserts", "name_zh": "甜點"},
        {"id": "meals", "name_en": "Meals", "name_zh": "正餐便當"},
        {"id": "packaging", "name_en": "Packaging", "name_zh": "包裝外帶"},
        {"id": "equipment", "name_en": "Equipment", "name_zh": "設備器材"},
        {"id": "signage", "name_en": "Signage", "name_zh": "招牌菜單"},
        {"id": "ingredients", "name_en": "Ingredients", "name_zh": "食材原料"},
    ],
    
    # -------------------------------------------------------------------------
    # Product Scene - Photography styles/settings
    # -------------------------------------------------------------------------
    "product_scene": [
        {"id": "studio", "name_en": "Studio Lighting", "name_zh": "攝影棚"},
        {"id": "nature", "name_en": "Nature Setting", "name_zh": "自然場景"},
        {"id": "elegant", "name_en": "Elegant Setting", "name_zh": "質感場景"},
        {"id": "minimal", "name_en": "Minimal", "name_zh": "極簡風格"},
        {"id": "lifestyle", "name_en": "Lifestyle", "name_zh": "生活風格"},
        {"id": "urban", "name_en": "Urban", "name_zh": "都市風格"},
        {"id": "seasonal", "name_en": "Seasonal", "name_zh": "季節性"},
        {"id": "holiday", "name_en": "Holiday", "name_zh": "節日"},
    ],
    
    # -------------------------------------------------------------------------
    # Try-On - Clothing categories
    # -------------------------------------------------------------------------
    "try_on": [
        {"id": "casual", "name_en": "Casual Wear", "name_zh": "休閒服飾"},
        {"id": "formal", "name_en": "Formal Wear", "name_zh": "正式服飾"},
        {"id": "sportswear", "name_en": "Sportswear", "name_zh": "運動服"},
        {"id": "outerwear", "name_en": "Outerwear", "name_zh": "外套"},
        {"id": "accessories", "name_en": "Accessories", "name_zh": "配件"},
        {"id": "dresses", "name_en": "Dresses", "name_zh": "洋裝"},
    ],
    
    # -------------------------------------------------------------------------
    # Room Redesign - Interior design styles
    # -------------------------------------------------------------------------
    "room_redesign": [
        {"id": "living_room", "name_en": "Living Room", "name_zh": "客廳"},
        {"id": "bedroom", "name_en": "Bedroom", "name_zh": "臥室"},
        {"id": "kitchen", "name_en": "Kitchen", "name_zh": "廚房"},
        {"id": "bathroom", "name_en": "Bathroom", "name_zh": "浴室"},
    ],
    
    # -------------------------------------------------------------------------
    # Short Video - Video content types
    # -------------------------------------------------------------------------
    "short_video": [
        {"id": "product_showcase", "name_en": "Product Showcase", "name_zh": "產品展示"},
        {"id": "brand_intro", "name_en": "Brand Introduction", "name_zh": "品牌介紹"},
        {"id": "tutorial", "name_en": "Tutorial", "name_zh": "教學"},
        {"id": "promo", "name_en": "Promotion", "name_zh": "促銷"},
    ],
    
    # -------------------------------------------------------------------------
    # AI Avatar - Use cases / scenarios
    # -------------------------------------------------------------------------
    "ai_avatar": [
        {"id": "spokesperson", "name_en": "Spokesperson", "name_zh": "品牌代言人"},
        {"id": "product_intro", "name_en": "Product Introduction", "name_zh": "產品介紹"},
        {"id": "customer_service", "name_en": "Customer Service", "name_zh": "客服助理"},
        {"id": "social_media", "name_en": "Social Media", "name_zh": "社群媒體"},
    ],
    
    # -------------------------------------------------------------------------
    # Pattern Generate - Pattern styles
    # -------------------------------------------------------------------------
    "pattern_generate": [
        {"id": "seamless", "name_en": "Seamless Pattern", "name_zh": "無縫圖案"},
        {"id": "floral", "name_en": "Floral Pattern", "name_zh": "花卉圖案"},
        {"id": "geometric", "name_en": "Geometric Pattern", "name_zh": "幾何圖案"},
        {"id": "abstract", "name_en": "Abstract Pattern", "name_zh": "抽象圖案"},
        {"id": "traditional", "name_en": "Traditional Pattern", "name_zh": "傳統紋樣"},
    ],

    # -------------------------------------------------------------------------
    # Effect (Style Transfer) - Art styles
    # -------------------------------------------------------------------------
    "effect": [
        {"id": "anime", "name_en": "Anime", "name_zh": "動漫風格"},
        {"id": "ghibli", "name_en": "Ghibli", "name_zh": "吉卜力風格"},
        {"id": "cartoon", "name_en": "Cartoon", "name_zh": "卡通風格"},
        {"id": "oil_painting", "name_en": "Oil Painting", "name_zh": "油畫風格"},
        {"id": "watercolor", "name_en": "Watercolor", "name_zh": "水彩風格"},
    ],
}


# =============================================================================
# LANDING PAGE TOPICS (Separate from tool topics)
# =============================================================================

LANDING_TOPICS: List[TopicInfo] = [
    {"id": "ecommerce", "name_en": "E-commerce", "name_zh": "電商廣告"},
    {"id": "social", "name_en": "Social Media", "name_zh": "社群媒體"},
    {"id": "brand", "name_en": "Brand Promotion", "name_zh": "品牌推廣"},
    {"id": "app", "name_en": "App Promotion", "name_zh": "應用推廣"},
    {"id": "promo", "name_en": "Promotional", "name_zh": "活動促銷"},
    {"id": "service", "name_en": "Service Introduction", "name_zh": "服務介紹"},
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_topics_for_tool(tool_type: str) -> List[TopicInfo]:
    """
    Get valid topics for a specific tool type.
    
    Args:
        tool_type: Tool type string (e.g., 'ai_avatar', 'background_removal')
        
    Returns:
        List of TopicInfo dictionaries, or empty list if tool_type not found.
    """
    return TOOL_TOPICS.get(tool_type, [])


def get_topic_ids_for_tool(tool_type: str) -> List[str]:
    """
    Get list of valid topic IDs for a specific tool type.
    
    Args:
        tool_type: Tool type string
        
    Returns:
        List of topic ID strings.
    """
    return [t["id"] for t in get_topics_for_tool(tool_type)]


def is_valid_topic(tool_type: str, topic_id: str) -> bool:
    """
    Check if a topic ID is valid for a given tool type.
    
    Args:
        tool_type: Tool type string
        topic_id: Topic ID to validate
        
    Returns:
        True if valid, False otherwise.
    """
    valid_ids = get_topic_ids_for_tool(tool_type)
    return topic_id in valid_ids


def get_topic_info(tool_type: str, topic_id: str) -> TopicInfo | None:
    """
    Get full topic info for a specific topic ID.
    
    Args:
        tool_type: Tool type string
        topic_id: Topic ID to look up
        
    Returns:
        TopicInfo dict or None if not found.
    """
    for topic in get_topics_for_tool(tool_type):
        if topic["id"] == topic_id:
            return topic
    return None


def get_all_tool_types() -> List[str]:
    """Get list of all supported tool types."""
    return list(TOOL_TOPICS.keys())


def get_landing_topics() -> List[TopicInfo]:
    """Get topics used for landing page materials."""
    return LANDING_TOPICS


def get_landing_topic_ids() -> List[str]:
    """Get list of landing page topic IDs."""
    return [t["id"] for t in LANDING_TOPICS]


def is_landing_topic(topic_id: str) -> bool:
    """Check if a topic ID is a landing page topic."""
    return topic_id in get_landing_topic_ids()


# =============================================================================
# PROMPT-TOPIC VALIDATION
# =============================================================================

# Keywords associated with each topic for content matching
TOPIC_KEYWORDS: Dict[str, List[str]] = {
    # Background Removal topics
    "drinks": ["tea", "coffee", "juice", "beverage", "drink", "cup", "straw", "latte", "smoothie", "水", "茶", "咖啡", "飲", "杯"],
    "snacks": ["snack", "fried", "crispy", "chip", "popcorn", "chicken", "fry", "炸", "雞", "薯", "小吃", "零食"],
    "desserts": ["cake", "dessert", "sweet", "pastry", "chocolate", "ice cream", "cookie", "蛋糕", "甜", "巧克力", "冰淇淋"],
    "meals": ["meal", "lunch", "dinner", "rice", "noodle", "soup", "bento", "飯", "麵", "湯", "便當", "正餐"],
    "packaging": ["package", "bag", "box", "container", "takeout", "包裝", "袋", "盒", "外帶"],
    "equipment": ["equipment", "machine", "oven", "blender", "mixer", "tool", "設備", "機器", "烤箱"],
    "signage": ["sign", "menu", "board", "banner", "poster", "招牌", "菜單", "看板"],
    "ingredients": ["ingredient", "raw", "fresh", "vegetable", "fruit", "meat", "食材", "蔬菜", "水果", "肉"],

    # Product Scene topics
    "studio": ["studio", "lighting", "professional", "flash", "backdrop", "攝影棚", "燈光"],
    "nature": ["nature", "outdoor", "garden", "forest", "grass", "natural", "自然", "戶外", "花園"],
    "elegant": ["elegant", "luxury", "premium", "gold", "marble", "silk", "質感", "優雅", "高級"],
    "minimal": ["minimal", "simple", "clean", "white", "plain", "極簡", "簡約", "乾淨"],
    "lifestyle": ["lifestyle", "home", "cozy", "living", "casual", "daily", "生活", "居家"],
    "urban": ["urban", "city", "street", "modern", "concrete", "都市", "城市", "街頭"],
    "seasonal": ["seasonal", "spring", "summer", "autumn", "winter", "season", "季節", "春", "夏", "秋", "冬"],
    "holiday": ["holiday", "christmas", "new year", "valentine", "festival", "節日", "聖誕", "新年"],

    # Try-On topics
    "casual": ["casual", "t-shirt", "jeans", "hoodie", "everyday", "休閒", "T恤", "牛仔"],
    "formal": ["formal", "suit", "dress shirt", "tie", "blazer", "business", "正式", "西裝"],
    "sportswear": ["sport", "athletic", "gym", "running", "yoga", "fitness", "運動", "健身"],
    "outerwear": ["jacket", "coat", "parka", "windbreaker", "outer", "外套", "夾克", "大衣"],
    "accessories": ["accessory", "hat", "scarf", "watch", "bag", "belt", "glasses", "配件", "帽", "圍巾"],
    "dresses": ["dress", "gown", "skirt", "frock", "洋裝", "裙"],

    # Room Redesign topics
    "living_room": ["living room", "sofa", "couch", "tv", "lounge", "客廳", "沙發", "電視"],
    "bedroom": ["bedroom", "bed", "sleep", "pillow", "mattress", "nightstand", "臥室", "床", "枕"],
    "kitchen": ["kitchen", "cook", "stove", "oven", "counter", "cabinet", "廚房", "烹飪", "爐"],
    "bathroom": ["bathroom", "bath", "shower", "sink", "tile", "toilet", "mirror", "浴室", "淋浴", "洗手台"],

    # Short Video topics
    "product_showcase": ["showcase", "product", "display", "present", "close-up", "展示", "產品", "特寫"],
    "brand_intro": ["brand", "introduction", "story", "company", "about", "品牌", "介紹", "故事"],
    "tutorial": ["tutorial", "how to", "step", "guide", "learn", "教學", "步驟", "指南"],
    "promo": ["promo", "sale", "discount", "offer", "deal", "limited", "促銷", "優惠", "折扣", "限時"],

    # AI Avatar topics
    "spokesperson": ["spokesperson", "brand", "ambassador", "represent", "代言", "品牌", "形象"],
    "product_intro": ["product", "introduce", "feature", "benefit", "launch", "產品", "介紹", "功能"],
    "customer_service": ["customer", "service", "help", "support", "assist", "FAQ", "客服", "服務", "幫助"],
    "social_media": ["social", "media", "instagram", "tiktok", "post", "share", "社群", "媒體", "分享"],

    # Pattern Generate topics
    "seamless": ["seamless", "repeat", "tile", "continuous", "無縫", "重複", "連續"],
    "floral": ["floral", "flower", "petal", "botanical", "rose", "leaf", "花", "花卉", "玫瑰", "葉"],
    "geometric": ["geometric", "triangle", "circle", "square", "hexagon", "line", "幾何", "三角", "圓"],
    "abstract": ["abstract", "modern", "artistic", "creative", "shape", "抽象", "藝術", "現代"],
    "traditional": ["traditional", "cultural", "chinese", "japanese", "classic", "heritage", "傳統", "文化", "古典"],

    # Effect/Style Transfer topics
    "anime": ["anime", "manga", "animation", "japanese", "動漫", "漫畫", "動畫"],
    "ghibli": ["ghibli", "miyazaki", "totoro", "spirited", "吉卜力", "宮崎駿"],
    "cartoon": ["cartoon", "pixar", "3d", "toon", "disney", "卡通", "動畫"],
    "oil_painting": ["oil", "painting", "canvas", "brush", "van gogh", "impressionist", "油畫", "畫布"],
    "watercolor": ["watercolor", "wash", "soft", "pastel", "aquarelle", "水彩", "柔和"],
}


def validate_prompt_topic(
    tool_type: str,
    topic_id: str,
    prompt: str,
    min_matches: int = 1,
) -> Dict:
    """
    Validate if a prompt's content matches its assigned topic using keyword matching.

    Args:
        tool_type: Tool type string (e.g., 'background_removal')
        topic_id: Topic ID to validate against (e.g., 'drinks')
        prompt: The prompt text to check
        min_matches: Minimum keyword matches required (default: 1)

    Returns:
        Dict with: is_valid, matched_keywords, total_keywords, confidence, message
    """
    if not is_valid_topic(tool_type, topic_id):
        return {
            "is_valid": False,
            "matched_keywords": [],
            "total_keywords": 0,
            "confidence": 0.0,
            "message": f"Invalid topic '{topic_id}' for tool '{tool_type}'",
        }

    keywords = TOPIC_KEYWORDS.get(topic_id, [])
    if not keywords:
        # No keywords defined for this topic — skip validation
        return {
            "is_valid": True,
            "matched_keywords": [],
            "total_keywords": 0,
            "confidence": 1.0,
            "message": f"No keywords defined for topic '{topic_id}', skipping validation",
        }

    prompt_lower = prompt.lower()
    matched = [kw for kw in keywords if kw.lower() in prompt_lower]

    is_valid = len(matched) >= min_matches
    confidence = len(matched) / len(keywords) if keywords else 0.0

    return {
        "is_valid": is_valid,
        "matched_keywords": matched,
        "total_keywords": len(keywords),
        "confidence": round(confidence, 3),
        "message": (
            f"OK: {len(matched)}/{len(keywords)} keywords matched"
            if is_valid
            else f"MISMATCH: prompt has {len(matched)}/{len(keywords)} matches for topic '{topic_id}' (need {min_matches})"
        ),
    }


def validate_all_prompts(
    tool_type: str,
    topic_prompts: Dict[str, List[str]],
) -> Dict:
    """
    Validate all prompts for a tool type against their assigned topics.

    Args:
        tool_type: Tool type string
        topic_prompts: Dict mapping topic_id -> list of prompt strings

    Returns:
        Dict with: total, valid, invalid, mismatches (list of problem prompts)
    """
    total = 0
    valid = 0
    mismatches = []

    for topic_id, prompts in topic_prompts.items():
        for prompt in prompts:
            total += 1
            result = validate_prompt_topic(tool_type, topic_id, prompt)
            if result["is_valid"]:
                valid += 1
            else:
                mismatches.append({
                    "topic": topic_id,
                    "prompt": prompt[:80] + "..." if len(prompt) > 80 else prompt,
                    "matched_keywords": result["matched_keywords"],
                    "confidence": result["confidence"],
                })

    return {
        "tool_type": tool_type,
        "total": total,
        "valid": valid,
        "invalid": len(mismatches),
        "pass_rate": round(valid / total, 3) if total > 0 else 1.0,
        "mismatches": mismatches,
    }
