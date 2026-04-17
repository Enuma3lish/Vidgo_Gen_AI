"""
Template Prompt Service for VidGo Platform

Resolves style templates into detailed English prompts for PiAPI.
Users never see these prompts — they only pick a thumbnail.
The backend composes the full prompt with cinematic parameters
(lighting, focal length, material, mood, color grading).
"""
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.style_template import StyleTemplate

logger = logging.getLogger(__name__)


# ============================================================================
# Seed templates — inserted on first startup or via admin command
# ============================================================================

SEED_TEMPLATES: List[Dict[str, Any]] = [
    # ── Product Scene Templates ──
    {
        "tool_type": "product_scene",
        "category": "mediterranean",
        "name_en": "Mediterranean Sunset",
        "name_zh": "地中海夕陽",
        "name_ja": "地中海の夕日",
        "name_ko": "지중해 석양",
        "name_es": "Atardecer Mediterráneo",
        "prompt_en": (
            "Professional product photography on a Mediterranean coastal terrace at golden hour sunset, "
            "warm terracotta tiles, cascading bougainvillea flowers, soft diffused golden light from the left, "
            "f/2.8 aperture, 85mm portrait lens, shallow depth of field with bokeh background, "
            "natural stone texture, warm amber color grading, editorial style, "
            "no people no person no human"
        ),
        "prompt_metadata": {
            "lighting": "golden hour, diffused warm light from left",
            "focal_length": "85mm",
            "aperture": "f/2.8",
            "mood": "warm, luxurious, Mediterranean",
            "color_grading": "warm amber tones",
        },
        "sort_order": 1,
        "is_featured": True,
    },
    {
        "tool_type": "product_scene",
        "category": "minimalist",
        "name_en": "Wabi-Sabi Minimalist",
        "name_zh": "極簡侘寂風",
        "name_ja": "侘び寂び ミニマリスト",
        "name_ko": "와비사비 미니멀리스트",
        "name_es": "Wabi-Sabi Minimalista",
        "prompt_en": (
            "Minimalist wabi-sabi product photography, raw concrete background wall with subtle cracks, "
            "natural linen fabric draped softly, dried pampas grass arrangement, "
            "soft north-facing window light creating gentle shadows, f/4.0 aperture, 35mm wide angle lens, "
            "neutral earth tones, textured matte surfaces, zen aesthetic, commercial quality, "
            "no people no person no human"
        ),
        "prompt_metadata": {
            "lighting": "soft north-facing window, gentle shadows",
            "focal_length": "35mm",
            "aperture": "f/4.0",
            "mood": "zen, calm, organic",
            "color_grading": "neutral earth tones, matte",
        },
        "sort_order": 2,
        "is_featured": True,
    },
    {
        "tool_type": "product_scene",
        "category": "street",
        "name_en": "Paris Street Café",
        "name_zh": "巴黎街頭",
        "name_ja": "パリのストリートカフェ",
        "name_ko": "파리 거리 카페",
        "name_es": "Café Parisino",
        "prompt_en": (
            "Elegant Parisian street café scene with wrought iron bistro chairs, "
            "cobblestone sidewalk, vintage awning overhead, overcast soft diffused light, "
            "f/5.6 aperture, 50mm standard lens, muted blue-grey color palette with cream accents, "
            "vintage film grain texture, European editorial product photography style, "
            "no people no person no human"
        ),
        "prompt_metadata": {
            "lighting": "overcast diffused, soft shadows",
            "focal_length": "50mm",
            "aperture": "f/5.6",
            "mood": "elegant, vintage, European",
            "color_grading": "muted blue-grey, cream accents",
        },
        "sort_order": 3,
        "is_featured": True,
    },
    {
        "tool_type": "product_scene",
        "category": "neon",
        "name_en": "Tokyo Neon Night",
        "name_zh": "東京霓虹夜景",
        "name_ja": "東京ネオンナイト",
        "name_ko": "도쿄 네온 나이트",
        "name_es": "Noche de Neón en Tokio",
        "prompt_en": (
            "Product photography in a neon-lit Tokyo alleyway at night, rain-wet reflections on pavement, "
            "vibrant pink and cyan neon signs glowing in background, f/1.8 aperture, 35mm lens, "
            "cinematic bokeh with neon light circles, cyberpunk mood, high contrast, "
            "dramatic side lighting from neon, urban product editorial quality, "
            "no people no person no human"
        ),
        "prompt_metadata": {
            "lighting": "neon side lighting, pink and cyan",
            "focal_length": "35mm",
            "aperture": "f/1.8",
            "mood": "cyberpunk, dramatic, urban",
            "color_grading": "high contrast, neon pink/cyan",
        },
        "sort_order": 4,
        "is_featured": False,
    },
    {
        "tool_type": "product_scene",
        "category": "scandinavian",
        "name_en": "Nordic White Studio",
        "name_zh": "北歐極簡白",
        "name_ja": "北欧ホワイトスタジオ",
        "name_ko": "노르딕 화이트 스튜디오",
        "name_es": "Estudio Nórdico Blanco",
        "prompt_en": (
            "Clean Scandinavian white photography studio, pure white seamless background, "
            "bright even daylight from large windows, minimal soft shadows, f/8.0 aperture, "
            "50mm lens, crisp sharp focus throughout, minimal composition, "
            "light wood accent surface, professional e-commerce product photography, "
            "no people no person no human"
        ),
        "prompt_metadata": {
            "lighting": "bright even daylight, large windows",
            "focal_length": "50mm",
            "aperture": "f/8.0",
            "mood": "clean, minimal, professional",
            "color_grading": "bright whites, light wood accents",
        },
        "sort_order": 5,
        "is_featured": True,
    },
    {
        "tool_type": "product_scene",
        "category": "tropical",
        "name_en": "Tropical Paradise",
        "name_zh": "熱帶天堂",
        "name_ja": "トロピカルパラダイス",
        "name_ko": "열대 파라다이스",
        "name_es": "Paraíso Tropical",
        "prompt_en": (
            "Tropical beach product photography, white sand with turquoise ocean in background, "
            "palm frond shadows casting patterns, bright midday sun with fill reflector, "
            "f/4.0 aperture, 85mm lens, vibrant saturated colors, "
            "fresh tropical mood, resort lifestyle product editorial quality, "
            "no people no person no human"
        ),
        "prompt_metadata": {
            "lighting": "bright midday sun, fill reflector",
            "focal_length": "85mm",
            "aperture": "f/4.0",
            "mood": "fresh, vibrant, tropical",
            "color_grading": "saturated tropical colors",
        },
        "sort_order": 6,
        "is_featured": False,
    },
    {
        "tool_type": "product_scene",
        "category": "dark_elegance",
        "name_en": "Dark Stone Elegance",
        "name_zh": "深色石材質感",
        "name_ja": "ダークストーン エレガンス",
        "name_ko": "다크 스톤 엘레강스",
        "name_es": "Elegancia en Piedra Oscura",
        "prompt_en": (
            "Product photography on polished dark stone surface with natural veining, brushed brass accents, "
            "dramatic rim lighting from behind, single overhead softbox key light, "
            "f/2.8 aperture, 100mm macro lens, deep rich blacks with warm metallic reflections, "
            "professional cosmetics and skincare advertising quality, moody refined feel, "
            "no people no person no human"
        ),
        "prompt_metadata": {
            "lighting": "dramatic rim light, overhead softbox",
            "focal_length": "100mm macro",
            "aperture": "f/2.8",
            "mood": "refined, premium, moody",
            "color_grading": "deep blacks, warm metallic accents",
        },
        "sort_order": 7,
        "is_featured": True,
    },
    {
        "tool_type": "product_scene",
        "category": "garden",
        "name_en": "English Garden Morning",
        "name_zh": "英式花園晨光",
        "name_ja": "イングリッシュガーデンの朝",
        "name_ko": "잉글리시 가든 모닝",
        "name_es": "Jardín Inglés al Amanecer",
        "prompt_en": (
            "Product photography in a lush English garden at early morning, dew drops on petals, "
            "soft golden morning light filtering through foliage, white roses and lavender surrounding, "
            "f/3.5 aperture, 85mm lens, dreamy soft bokeh, pastel color palette, "
            "romantic garden mood, lifestyle product editorial quality, "
            "no people no person no human"
        ),
        "prompt_metadata": {
            "lighting": "soft golden morning, filtered through foliage",
            "focal_length": "85mm",
            "aperture": "f/3.5",
            "mood": "romantic, dreamy, garden",
            "color_grading": "pastel, soft greens and pinks",
        },
        "sort_order": 8,
        "is_featured": False,
    },

    # ── Try-On Templates ──
    {
        "tool_type": "try_on",
        "category": "beach",
        "name_en": "Seaside Resort",
        "name_zh": "海濱度假風",
        "name_ja": "シーサイドリゾート",
        "name_ko": "해변 리조트",
        "name_es": "Resort de Playa",
        "prompt_en": (
            "Fashion model on a Mediterranean beach boardwalk, turquoise sea in background, "
            "white limestone architecture, golden hour sunset light casting long warm shadows, "
            "f/2.8 aperture, 85mm portrait lens, wind in hair, lifestyle resort fashion editorial, "
            "high-end magazine quality, natural confident pose"
        ),
        "prompt_metadata": {
            "lighting": "golden hour sunset, warm long shadows",
            "focal_length": "85mm",
            "aperture": "f/2.8",
            "mood": "resort, breezy, confident",
            "color_grading": "warm golden, turquoise accents",
        },
        "sort_order": 1,
        "is_featured": True,
    },
    {
        "tool_type": "try_on",
        "category": "urban",
        "name_en": "Urban Street Style",
        "name_zh": "都市街拍風",
        "name_ja": "アーバンストリートスタイル",
        "name_ko": "어반 스트리트 스타일",
        "name_es": "Estilo Urbano Callejero",
        "prompt_en": (
            "Fashion model in a modern urban cityscape, clean concrete architecture, "
            "street style photography, overcast even lighting, f/4.0 aperture, 50mm lens, "
            "neutral grey and white background, sharp focus, contemporary minimalist mood, "
            "fashion week street style editorial quality"
        ),
        "prompt_metadata": {
            "lighting": "overcast even, no harsh shadows",
            "focal_length": "50mm",
            "aperture": "f/4.0",
            "mood": "modern, cool, minimal",
            "color_grading": "desaturated, neutral greys",
        },
        "sort_order": 2,
        "is_featured": True,
    },
    {
        "tool_type": "try_on",
        "category": "studio",
        "name_en": "Clean Studio White",
        "name_zh": "純白攝影棚",
        "name_ja": "クリーンスタジオホワイト",
        "name_ko": "클린 스튜디오 화이트",
        "name_es": "Estudio Blanco Limpio",
        "prompt_en": (
            "Fashion model in a professional white cyclorama photography studio, "
            "three-point lighting setup with key light at 45 degrees, fill and rim light, "
            "f/5.6 aperture, 85mm lens, clean white background, sharp focus on fabric details, "
            "e-commerce catalog photography, professional model posing"
        ),
        "prompt_metadata": {
            "lighting": "three-point studio setup",
            "focal_length": "85mm",
            "aperture": "f/5.6",
            "mood": "professional, clean, commercial",
            "color_grading": "neutral, true-to-color",
        },
        "sort_order": 3,
        "is_featured": True,
    },
    {
        "tool_type": "try_on",
        "category": "nature",
        "name_en": "Autumn Forest",
        "name_zh": "秋日森林",
        "name_ja": "秋の森",
        "name_ko": "가을 숲",
        "name_es": "Bosque Otoñal",
        "prompt_en": (
            "Fashion model in an autumn forest setting, golden and amber fallen leaves, "
            "soft dappled sunlight filtering through tree canopy, f/2.8 aperture, 85mm lens, "
            "warm autumn color palette, natural relaxed pose, outdoor lifestyle editorial, "
            "fashion magazine cover quality"
        ),
        "prompt_metadata": {
            "lighting": "dappled sunlight through canopy",
            "focal_length": "85mm",
            "aperture": "f/2.8",
            "mood": "warm, natural, relaxed",
            "color_grading": "golden amber autumn tones",
        },
        "sort_order": 4,
        "is_featured": False,
    },
    {
        "tool_type": "try_on",
        "category": "indoor",
        "name_en": "Hotel Lobby",
        "name_zh": "飯店大廳",
        "name_ja": "ホテルロビー",
        "name_ko": "호텔 로비",
        "name_es": "Lobby de Hotel",
        "prompt_en": (
            "Fashion model in a spacious hotel lobby, polished stone floors with geometric patterns, "
            "large chandelier overhead, warm ambient lighting mixed with natural window light, "
            "f/3.5 aperture, 50mm lens, rich warm tones, sophisticated elegant mood, "
            "fashion editorial quality, professional campaign style"
        ),
        "prompt_metadata": {
            "lighting": "warm ambient + natural window mix",
            "focal_length": "50mm",
            "aperture": "f/3.5",
            "mood": "sophisticated, elegant, warm",
            "color_grading": "rich warm, soft undertones",
        },
        "sort_order": 5,
        "is_featured": True,
    },
]


async def seed_templates(db: AsyncSession) -> int:
    """Insert seed templates if none exist. Returns count of inserted rows."""
    result = await db.execute(select(StyleTemplate).limit(1))
    if result.scalars().first():
        return 0  # Already seeded

    count = 0
    for data in SEED_TEMPLATES:
        template = StyleTemplate(
            id=uuid4(),
            **data,
        )
        db.add(template)
        count += 1

    await db.commit()
    logger.info(f"Seeded {count} style templates")
    return count


async def get_templates(
    db: AsyncSession,
    tool_type: str,
    category: Optional[str] = None,
    featured_only: bool = False,
) -> List[Dict[str, Any]]:
    """Return active templates for a given tool type."""
    q = select(StyleTemplate).where(
        StyleTemplate.tool_type == tool_type,
        StyleTemplate.is_active.is_(True),
    )
    if category:
        q = q.where(StyleTemplate.category == category)
    if featured_only:
        q = q.where(StyleTemplate.is_featured.is_(True))
    q = q.order_by(StyleTemplate.sort_order)

    result = await db.execute(q)
    templates = result.scalars().all()

    return [
        {
            "id": str(t.id),
            "category": t.category,
            "name_en": t.name_en,
            "name_zh": t.name_zh,
            "name_ja": t.name_ja,
            "name_ko": t.name_ko,
            "name_es": t.name_es,
            "preview_image_url": t.preview_image_url,
            "is_featured": t.is_featured,
        }
        for t in templates
    ]


async def resolve_template_prompt(
    db: AsyncSession,
    template_id: str,
) -> Optional[str]:
    """Look up a template by ID and return its full English prompt."""
    template = await db.get(StyleTemplate, template_id)
    if not template or not template.is_active:
        return None
    return template.prompt_en
