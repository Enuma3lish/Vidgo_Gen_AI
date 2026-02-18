"""
Model Registry Service
Manages catalog of available AI models per provider and tracks new model announcements.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ModelInfo(BaseModel):
    id: str
    name: str
    name_zh: str
    provider: str
    type: str  # t2i, i2v, t2v, v2v, avatar, interior, 3d, moderation
    tier: str  # free, paid, both
    description: str
    description_zh: str
    announced_at: Optional[str] = None
    is_new: bool = False


# Known models catalog - this is the source of truth
KNOWN_MODELS: List[ModelInfo] = [
    ModelInfo(id="flux1-schnell", name="Flux 1 Schnell", name_zh="Flux 1 快速", provider="piapi", type="t2i", tier="both", description="Fast text-to-image generation", description_zh="快速文字轉圖片"),
    ModelInfo(id="wan26-img2video", name="Wan 2.6 Image-to-Video", name_zh="Wan 2.6 圖轉影片", provider="piapi", type="i2v", tier="both", description="Convert images to video clips", description_zh="將圖片轉換為影片"),
    ModelInfo(id="wan26-txt2video", name="Wan 2.6 Text-to-Video", name_zh="Wan 2.6 文轉影片", provider="piapi", type="t2v", tier="both", description="Generate videos from text prompts", description_zh="從文字生成影片"),
    ModelInfo(id="wan21-vace", name="Wan 2.1 VACE", name_zh="Wan 2.1 風格轉換", provider="piapi", type="v2v", tier="paid", description="Video style transfer", description_zh="影片風格轉換"),
    ModelInfo(id="wan21-doodle", name="Wan 2.1 Doodle", name_zh="Wan 2.1 室內設計", provider="piapi", type="interior", tier="both", description="Interior design generation", description_zh="室內設計生成"),
    ModelInfo(id="kling-tryon", name="Kling AI Try-On", name_zh="Kling AI 試穿", provider="piapi", type="tryon", tier="both", description="Virtual clothing try-on", description_zh="虛擬試穿"),
    ModelInfo(id="goenhance-bgremoval", name="GoEnhance Background Removal", name_zh="GoEnhance 去背", provider="piapi", type="bgremoval", tier="both", description="AI background removal", description_zh="AI 智能去背"),
    ModelInfo(id="trellis-3d", name="Trellis 3D", name_zh="Trellis 3D 模型", provider="piapi", type="3d", tier="paid", description="Image to 3D model generation", description_zh="圖片轉 3D 模型"),
    ModelInfo(id="a2e-avatar", name="A2E Digital Avatar", name_zh="A2E 數位人", provider="a2e", type="avatar", tier="both", description="AI avatar with lip sync", description_zh="AI 數位人口播"),
    ModelInfo(id="gemini-moderation", name="Gemini 1.5 Flash", name_zh="Gemini 內容審核", provider="gemini", type="moderation", tier="both", description="Content safety moderation", description_zh="內容安全審核"),
    ModelInfo(id="pollo-keyframes", name="Pollo Keyframes", name_zh="Pollo 關鍵幀", provider="pollo", type="i2v", tier="paid", description="Keyframe-based video generation", description_zh="關鍵幀影片生成"),
    ModelInfo(id="pollo-effects", name="Pollo Effects", name_zh="Pollo 特效", provider="pollo", type="effects", tier="paid", description="Video effects and transitions", description_zh="影片特效與轉場"),
]


class ModelRegistry:
    """Manages available AI models and new model announcements."""

    def __init__(self):
        self._announcements: List[Dict] = []

    def get_all_models(self) -> List[ModelInfo]:
        """Get all known models."""
        return KNOWN_MODELS

    def get_models_for_tier(self, tier: str) -> List[ModelInfo]:
        """Get models available for a user tier."""
        return [m for m in KNOWN_MODELS if m.tier == tier or m.tier == "both"]

    def get_models_by_provider(self, provider: str) -> List[ModelInfo]:
        """Get all models from a specific provider."""
        return [m for m in KNOWN_MODELS if m.provider == provider]

    def get_models_by_type(self, model_type: str) -> List[ModelInfo]:
        """Get all models of a specific type."""
        return [m for m in KNOWN_MODELS if m.type == model_type]

    def announce_model(self, model_id: str, message: str = "", message_zh: str = "") -> bool:
        """Mark a model as newly announced."""
        model = next((m for m in KNOWN_MODELS if m.id == model_id), None)
        if not model:
            return False

        self._announcements.append({
            "model_id": model_id,
            "model_name": model.name,
            "model_name_zh": model.name_zh,
            "message": message or f"New AI model available: {model.name}",
            "message_zh": message_zh or f"全新 AI 模型上線：{model.name_zh}",
            "tier": model.tier,
            "announced_at": datetime.utcnow().isoformat(),
        })
        return True

    def get_new_models(self, since_days: int = 7) -> List[Dict]:
        """Get models announced in the last N days."""
        cutoff = datetime.utcnow() - timedelta(days=since_days)
        return [
            a for a in self._announcements
            if datetime.fromisoformat(a["announced_at"]) > cutoff
        ]

    def get_announcements(self) -> List[Dict]:
        """Get all announcements."""
        return self._announcements


# Singleton
_registry: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry
