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
    """7 Core Tools - must match material.py ToolType"""
    BACKGROUND_REMOVAL = "background_removal"
    PRODUCT_SCENE = "product_scene"
    TRY_ON = "try_on"
    ROOM_REDESIGN = "room_redesign"
    SHORT_VIDEO = "short_video"
    AI_AVATAR = "ai_avatar"
    PATTERN_GENERATE = "pattern_generate"


# =============================================================================
# OFFICIAL TOOL TOPICS REGISTRY
# =============================================================================

TOOL_TOPICS: Dict[str, List[TopicInfo]] = {
    # -------------------------------------------------------------------------
    # Background Removal - Product categories
    # -------------------------------------------------------------------------
    "background_removal": [
        {"id": "electronics", "name_en": "Electronics", "name_zh": "電子產品"},
        {"id": "fashion", "name_en": "Fashion", "name_zh": "時尚服飾"},
        {"id": "jewelry", "name_en": "Jewelry", "name_zh": "珠寶首飾"},
        {"id": "food", "name_en": "Food & Beverage", "name_zh": "食品飲料"},
        {"id": "cosmetics", "name_en": "Cosmetics", "name_zh": "化妝品"},
        {"id": "furniture", "name_en": "Furniture", "name_zh": "家具"},
        {"id": "toys", "name_en": "Toys", "name_zh": "玩具"},
        {"id": "sports", "name_en": "Sports", "name_zh": "運動用品"},
    ],
    
    # -------------------------------------------------------------------------
    # Product Scene - Photography styles/settings
    # -------------------------------------------------------------------------
    "product_scene": [
        {"id": "studio", "name_en": "Studio Lighting", "name_zh": "攝影棚"},
        {"id": "nature", "name_en": "Nature Setting", "name_zh": "自然場景"},
        {"id": "luxury", "name_en": "Luxury Setting", "name_zh": "奢華場景"},
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
        {"id": "modern", "name_en": "Modern", "name_zh": "現代風格"},
        {"id": "nordic", "name_en": "Nordic", "name_zh": "北歐風格"},
        {"id": "japanese", "name_en": "Japanese", "name_zh": "日式風格"},
        {"id": "industrial", "name_en": "Industrial", "name_zh": "工業風格"},
        {"id": "minimalist", "name_en": "Minimalist", "name_zh": "極簡風格"},
        {"id": "luxury", "name_en": "Luxury", "name_zh": "奢華風格"},
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
