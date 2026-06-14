"""Configuration module for VidGo Gen AI."""
from .demo_topics import (
    TopicDefinition,
    TopicCategory,
    OutputType,
    get_all_topics,
    get_topics_by_category,
    get_topic_by_id,
    get_topics_by_output_type,
    CATEGORY_OUTPUT_MAP,
    PRODUCT_VIDEO_TOPICS,
    INTERIOR_DESIGN_TOPICS,
    STYLE_TRANSFER_TOPICS,
    AVATAR_TOPICS,
    T2I_SHOWCASE_TOPICS,
)

__all__ = [
    "TopicDefinition",
    "TopicCategory",
    "OutputType",
    "get_all_topics",
    "get_topics_by_category",
    "get_topic_by_id",
    "get_topics_by_output_type",
    "CATEGORY_OUTPUT_MAP",
    "PRODUCT_VIDEO_TOPICS",
    "INTERIOR_DESIGN_TOPICS",
    "STYLE_TRANSFER_TOPICS",
    "AVATAR_TOPICS",
    "T2I_SHOWCASE_TOPICS",
]
