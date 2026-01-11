"""
Demo Topics Configuration with Output Type Routing

This module defines all demo topics with their categories and output types.
Based on the Prompt Chaining Design workflow:

┌─────────────────────────────────────────────────────────────────┐
│  Category         │ output_type │ Flow           │ Output      │
├───────────────────┼─────────────┼────────────────┼─────────────┤
│  product_video    │ video       │ T2I → I2V      │ Video       │
│  interior_design  │ image       │ Gemini T2I     │ Image       │
│  style_transfer   │ video       │ I2V → V2V      │ Video       │
│  avatar           │ video       │ Pollo Avatar   │ Video       │
│  t2i_showcase     │ image       │ Leonardo T2I   │ Image       │
└─────────────────────────────────────────────────────────────────┘
"""
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field


class OutputType(str, Enum):
    """Output type determines the final deliverable format."""
    VIDEO = "video"
    IMAGE = "image"


class TopicCategory(str, Enum):
    """Topic categories that map to different generation flows."""
    PRODUCT_VIDEO = "product_video"      # T2I → I2V
    INTERIOR_DESIGN = "interior_design"  # Gemini 2.5 Flash Image (T2I)
    STYLE_TRANSFER = "style_transfer"    # I2V → V2V
    AVATAR = "avatar"                    # Pollo Avatar API
    T2I_SHOWCASE = "t2i_showcase"        # Pure image generation


@dataclass
class TopicDefinition:
    """
    Definition of a demo topic with all generation parameters.

    Attributes:
        id: Unique identifier for this topic
        category: The category determines which generation flow to use
        output_type: Final output format (video or image)
        subject: Main subject of the generation
        mood: Mood/atmosphere for prompt enhancement
        image_prompt_template: Template for image generation
        effect_prompt_template: Template for video effects (if video output)
        style_id: Optional style ID for style transfer
        language: Language for avatar scripts
        tags: Search/filter tags
    """
    id: str
    category: TopicCategory
    output_type: OutputType
    subject: str
    mood: str
    image_prompt_template: str
    effect_prompt_template: Optional[str] = None
    style_id: Optional[int] = None
    language: str = "en"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def build_image_prompt(self) -> str:
        """Build the image generation prompt from template."""
        return self.image_prompt_template.format(
            subject=self.subject,
            mood=self.mood
        )

    def build_effect_prompt(self) -> str:
        """Build the effect/motion prompt for video generation."""
        if self.effect_prompt_template:
            return self.effect_prompt_template.format(
                subject=self.subject,
                mood=self.mood
            )
        # Default effect prompt based on mood
        return f"Smooth cinematic motion, {self.mood}, professional quality"


# =============================================================================
# PRODUCT VIDEO TOPICS - T2I → I2V Flow
# =============================================================================

PRODUCT_VIDEO_TOPICS: List[TopicDefinition] = [
    TopicDefinition(
        id="luxury_watch",
        category=TopicCategory.PRODUCT_VIDEO,
        output_type=OutputType.VIDEO,
        subject="luxury wristwatch",
        mood="elegant, sophisticated, premium",
        image_prompt_template="""
A {subject} on polished marble surface,
{mood} lighting, studio photography,
golden hour reflection, 8K quality,
professional product photography
""".strip(),
        effect_prompt_template="""
Slow cinematic rotation, {mood},
gentle light play on metal surfaces,
premium brand commercial feel
""".strip(),
        tags=["watch", "luxury", "ecommerce", "product"]
    ),
    TopicDefinition(
        id="perfume_bottle",
        category=TopicCategory.PRODUCT_VIDEO,
        output_type=OutputType.VIDEO,
        subject="elegant perfume bottle",
        mood="luxurious, glamorous, sensual",
        image_prompt_template="""
A {subject} with crystal clear liquid,
{mood} atmosphere, soft studio lighting,
water droplets, reflective surface,
high-end cosmetic photography
""".strip(),
        effect_prompt_template="""
Ethereal mist rising, {mood},
light rays through crystal,
slow motion liquid shimmer
""".strip(),
        tags=["perfume", "cosmetics", "luxury", "beauty"]
    ),
    TopicDefinition(
        id="sneaker_product",
        category=TopicCategory.PRODUCT_VIDEO,
        output_type=OutputType.VIDEO,
        subject="premium sports sneaker",
        mood="dynamic, energetic, modern",
        image_prompt_template="""
A {subject} floating on clean background,
{mood} lighting, sharp details,
product showcase, athletic brand,
studio photography, 4K quality
""".strip(),
        effect_prompt_template="""
Dynamic rotation, {mood},
subtle bounce effect,
streetwear commercial style
""".strip(),
        tags=["sneaker", "shoes", "fashion", "sports"]
    ),
    TopicDefinition(
        id="skincare_cream",
        category=TopicCategory.PRODUCT_VIDEO,
        output_type=OutputType.VIDEO,
        subject="skincare cream jar",
        mood="pure, fresh, natural",
        image_prompt_template="""
A {subject} with cream texture visible,
{mood} atmosphere, soft natural lighting,
green leaves and water drops nearby,
clean beauty product photography
""".strip(),
        effect_prompt_template="""
Gentle cream swirl, {mood},
dewdrops glistening,
organic beauty commercial
""".strip(),
        tags=["skincare", "beauty", "cosmetics", "organic"]
    ),
    TopicDefinition(
        id="tech_earbuds",
        category=TopicCategory.PRODUCT_VIDEO,
        output_type=OutputType.VIDEO,
        subject="wireless earbuds in charging case",
        mood="sleek, minimal, futuristic",
        image_prompt_template="""
A {subject} on dark surface,
{mood} lighting with LED glow,
tech product photography,
Apple-style minimalist aesthetic
""".strip(),
        effect_prompt_template="""
Smooth case opening, {mood},
LED pulse effect,
tech commercial reveal
""".strip(),
        tags=["earbuds", "tech", "audio", "gadgets"]
    ),
    TopicDefinition(
        id="coffee_product",
        category=TopicCategory.PRODUCT_VIDEO,
        output_type=OutputType.VIDEO,
        subject="artisanal coffee bag and beans",
        mood="warm, artisan, rustic",
        image_prompt_template="""
A {subject} with scattered coffee beans,
{mood} atmosphere, warm morning light,
wooden surface, steam rising from cup,
specialty coffee brand photography
""".strip(),
        effect_prompt_template="""
Steam rising slowly, {mood},
beans rolling gently,
coffee commercial warmth
""".strip(),
        tags=["coffee", "food", "artisan", "beverage"]
    ),
]


# =============================================================================
# INTERIOR DESIGN TOPICS - Gemini 2.5 Flash Image (T2I Only)
# =============================================================================

INTERIOR_DESIGN_TOPICS: List[TopicDefinition] = [
    TopicDefinition(
        id="modern_living",
        category=TopicCategory.INTERIOR_DESIGN,
        output_type=OutputType.IMAGE,
        subject="modern minimalist living room",
        mood="clean, bright, spacious",
        image_prompt_template="""
A {subject} with floor-to-ceiling windows,
{mood} atmosphere, natural light flooding in,
neutral color palette, designer furniture,
Scandinavian meets Japanese aesthetic,
interior design magazine photography
""".strip(),
        tags=["living_room", "modern", "minimalist", "interior"]
    ),
    TopicDefinition(
        id="cozy_bedroom",
        category=TopicCategory.INTERIOR_DESIGN,
        output_type=OutputType.IMAGE,
        subject="cozy master bedroom",
        mood="warm, relaxing, inviting",
        image_prompt_template="""
A {subject} with soft textiles and warm lighting,
{mood} atmosphere, layered bedding,
earth tones, wooden accents,
hygge inspired design,
professional interior photography
""".strip(),
        tags=["bedroom", "cozy", "hygge", "interior"]
    ),
    TopicDefinition(
        id="zen_bathroom",
        category=TopicCategory.INTERIOR_DESIGN,
        output_type=OutputType.IMAGE,
        subject="Japanese zen bathroom",
        mood="serene, peaceful, spa-like",
        image_prompt_template="""
A {subject} with natural stone and wood,
{mood} atmosphere, soaking tub,
bamboo elements, indoor plants,
Japanese ryokan inspired,
luxury bathroom design
""".strip(),
        tags=["bathroom", "zen", "japanese", "spa"]
    ),
    TopicDefinition(
        id="industrial_kitchen",
        category=TopicCategory.INTERIOR_DESIGN,
        output_type=OutputType.IMAGE,
        subject="industrial style kitchen",
        mood="bold, urban, functional",
        image_prompt_template="""
A {subject} with exposed brick and metal,
{mood} atmosphere, concrete countertops,
professional appliances, pendant lighting,
loft apartment kitchen design,
architectural photography
""".strip(),
        tags=["kitchen", "industrial", "urban", "loft"]
    ),
    TopicDefinition(
        id="coastal_dining",
        category=TopicCategory.INTERIOR_DESIGN,
        output_type=OutputType.IMAGE,
        subject="coastal dining room",
        mood="breezy, relaxed, beachy",
        image_prompt_template="""
A {subject} with ocean view,
{mood} atmosphere, white and blue palette,
natural textures, driftwood accents,
beach house luxury dining,
lifestyle interior photography
""".strip(),
        tags=["dining", "coastal", "beach", "nautical"]
    ),
]


# =============================================================================
# STYLE TRANSFER TOPICS - I2V → V2V Flow
# =============================================================================

STYLE_TRANSFER_TOPICS: List[TopicDefinition] = [
    TopicDefinition(
        id="anime_landscape",
        category=TopicCategory.STYLE_TRANSFER,
        output_type=OutputType.VIDEO,
        subject="cherry blossom tree by lake",
        mood="dreamy, magical, peaceful",
        image_prompt_template="""
A {subject} at sunset,
{mood} atmosphere, pink petals falling,
reflection on calm water,
Japanese landscape photography
""".strip(),
        effect_prompt_template="""
Gentle breeze, petals drifting, {mood},
water ripples, light rays through branches
""".strip(),
        style_id=2000,  # Anime Style v5
        tags=["anime", "landscape", "nature", "japanese"]
    ),
    TopicDefinition(
        id="ghibli_cottage",
        category=TopicCategory.STYLE_TRANSFER,
        output_type=OutputType.VIDEO,
        subject="cozy cottage in meadow",
        mood="whimsical, nostalgic, heartwarming",
        image_prompt_template="""
A {subject} with smoke from chimney,
{mood} atmosphere, wildflowers everywhere,
golden hour lighting, puffy clouds,
Studio Ghibli inspired scene
""".strip(),
        effect_prompt_template="""
Smoke rising, flowers swaying, {mood},
clouds drifting, birds flying
""".strip(),
        style_id=1033,  # GPT Anime Style (Ghibli)
        tags=["ghibli", "cottage", "meadow", "fantasy"]
    ),
    TopicDefinition(
        id="cyberpunk_city",
        category=TopicCategory.STYLE_TRANSFER,
        output_type=OutputType.VIDEO,
        subject="neon-lit city street at night",
        mood="futuristic, electric, mysterious",
        image_prompt_template="""
A {subject} with rain reflections,
{mood} atmosphere, holographic signs,
flying vehicles, towering buildings,
Blade Runner inspired cyberpunk scene
""".strip(),
        effect_prompt_template="""
Neon flickering, rain falling, {mood},
vehicles zooming, hologram glitches
""".strip(),
        style_id=2008,  # Cyberpunk v5
        tags=["cyberpunk", "city", "neon", "scifi"]
    ),
    TopicDefinition(
        id="oil_painting_nature",
        category=TopicCategory.STYLE_TRANSFER,
        output_type=OutputType.VIDEO,
        subject="golden wheat field at sunset",
        mood="pastoral, romantic, timeless",
        image_prompt_template="""
A {subject} with dramatic clouds,
{mood} atmosphere, Van Gogh style,
rich golden colors, sweeping brushstrokes,
impressionist landscape painting
""".strip(),
        effect_prompt_template="""
Wheat swaying, clouds moving, {mood},
birds flying across sky
""".strip(),
        style_id=2006,  # Oil Painting v5
        tags=["oil_painting", "nature", "impressionist", "art"]
    ),
    TopicDefinition(
        id="cinematic_ocean",
        category=TopicCategory.STYLE_TRANSFER,
        output_type=OutputType.VIDEO,
        subject="dramatic ocean waves on rocky shore",
        mood="powerful, majestic, epic",
        image_prompt_template="""
A {subject} at golden hour,
{mood} atmosphere, spray and mist,
stormy clouds, lighthouse in distance,
cinematic landscape photography
""".strip(),
        effect_prompt_template="""
Waves crashing, mist rising, {mood},
clouds churning, lighthouse light spinning
""".strip(),
        style_id=2010,  # Cinematic v5
        tags=["cinematic", "ocean", "dramatic", "nature"]
    ),
]


# =============================================================================
# AVATAR TOPICS - Pollo Avatar API
# =============================================================================

# Asian/Taiwanese professional avatar images
ASIAN_AVATAR_IMAGES = {
    "female_professional": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=512",
    "male_professional": "https://images.unsplash.com/photo-1492562080023-ab3db95bfbce?w=512",
    "female_business": "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=512",
    "male_business": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=512",
    "female_young": "https://images.unsplash.com/photo-1580489944761-15a19d654956?w=512",
    "male_young": "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=512",
}

AVATAR_TOPICS: List[TopicDefinition] = [
    TopicDefinition(
        id="ecommerce_pitch_en",
        category=TopicCategory.AVATAR,
        output_type=OutputType.VIDEO,
        subject="Asian professional woman presenter",
        mood="confident, trustworthy, engaging",
        image_prompt_template=ASIAN_AVATAR_IMAGES["female_professional"],
        language="en",
        metadata={
            "script": "Welcome to our exclusive collection! Today I'm excited to introduce our premium product line that combines quality with innovation. Don't miss our special launch offer!",
            "avatar_url": ASIAN_AVATAR_IMAGES["female_professional"]
        },
        tags=["avatar", "ecommerce", "english", "professional", "asian"]
    ),
    TopicDefinition(
        id="tech_presenter_en",
        category=TopicCategory.AVATAR,
        output_type=OutputType.VIDEO,
        subject="Asian tech entrepreneur presenter",
        mood="innovative, dynamic, inspiring",
        image_prompt_template=ASIAN_AVATAR_IMAGES["male_professional"],
        language="en",
        metadata={
            "script": "The future is here! Our groundbreaking AI technology is revolutionizing the industry. Join thousands of early adopters who are already experiencing the difference.",
            "avatar_url": ASIAN_AVATAR_IMAGES["male_professional"]
        },
        tags=["avatar", "tech", "english", "startup", "asian"]
    ),
    TopicDefinition(
        id="beauty_influencer_en",
        category=TopicCategory.AVATAR,
        output_type=OutputType.VIDEO,
        subject="Asian beauty brand ambassador",
        mood="glamorous, friendly, authentic",
        image_prompt_template=ASIAN_AVATAR_IMAGES["female_young"],
        language="en",
        metadata={
            "script": "Unlock your natural glow with our organic skincare collection. Made with love and the finest ingredients nature has to offer.",
            "avatar_url": ASIAN_AVATAR_IMAGES["female_young"]
        },
        tags=["avatar", "beauty", "english", "influencer", "asian"]
    ),
    TopicDefinition(
        id="ecommerce_pitch_zh",
        category=TopicCategory.AVATAR,
        output_type=OutputType.VIDEO,
        subject="台灣專業女性主持人",
        mood="專業, 親切, 可信賴",
        image_prompt_template=ASIAN_AVATAR_IMAGES["female_business"],
        language="zh-TW",
        metadata={
            "script": "歡迎來到我們的品牌！今天為您帶來我們最新的產品系列，結合頂級品質與創新設計。現在購買還有限時優惠！",
            "avatar_url": ASIAN_AVATAR_IMAGES["female_business"]
        },
        tags=["avatar", "ecommerce", "chinese", "professional", "taiwanese"]
    ),
    TopicDefinition(
        id="food_presenter_zh",
        category=TopicCategory.AVATAR,
        output_type=OutputType.VIDEO,
        subject="台灣美食推薦主持人",
        mood="熱情, 美味, 誘人",
        image_prompt_template=ASIAN_AVATAR_IMAGES["male_business"],
        language="zh-TW",
        metadata={
            "script": "各位美食愛好者大家好！今天為您推薦我們餐廳的招牌料理，使用最新鮮的食材，由米其林主廚精心烹調。",
            "avatar_url": ASIAN_AVATAR_IMAGES["male_business"]
        },
        tags=["avatar", "food", "chinese", "restaurant", "taiwanese"]
    ),
    TopicDefinition(
        id="education_presenter_zh",
        category=TopicCategory.AVATAR,
        output_type=OutputType.VIDEO,
        subject="台灣線上教育講師",
        mood="專業, 耐心, 熱誠",
        image_prompt_template=ASIAN_AVATAR_IMAGES["female_professional"],
        language="zh-TW",
        metadata={
            "script": "歡迎加入我們的線上學習平台！我們提供上百門專業課程，讓您隨時隨地學習新技能，開啟職涯新篇章。",
            "avatar_url": ASIAN_AVATAR_IMAGES["female_professional"]
        },
        tags=["avatar", "education", "chinese", "learning", "taiwanese"]
    ),
    TopicDefinition(
        id="tech_presenter_zh",
        category=TopicCategory.AVATAR,
        output_type=OutputType.VIDEO,
        subject="台灣科技創業家",
        mood="創新, 專業, 領先",
        image_prompt_template=ASIAN_AVATAR_IMAGES["male_young"],
        language="zh-TW",
        metadata={
            "script": "大家好！今天要跟大家分享我們最新的AI科技產品。台灣製造，品質保證，讓您的工作更有效率！",
            "avatar_url": ASIAN_AVATAR_IMAGES["male_young"]
        },
        tags=["avatar", "tech", "chinese", "startup", "taiwanese"]
    ),
    TopicDefinition(
        id="lifestyle_presenter_zh",
        category=TopicCategory.AVATAR,
        output_type=OutputType.VIDEO,
        subject="台灣生活風格達人",
        mood="時尚, 親切, 有品味",
        image_prompt_template=ASIAN_AVATAR_IMAGES["female_young"],
        language="zh-TW",
        metadata={
            "script": "嗨大家好！今天要分享幾個讓生活更精彩的小秘訣。跟著我一起打造質感生活吧！",
            "avatar_url": ASIAN_AVATAR_IMAGES["female_young"]
        },
        tags=["avatar", "lifestyle", "chinese", "influencer", "taiwanese"]
    ),
]


# =============================================================================
# T2I SHOWCASE TOPICS - Pure Image Generation
# =============================================================================

T2I_SHOWCASE_TOPICS: List[TopicDefinition] = [
    TopicDefinition(
        id="seamless_marble",
        category=TopicCategory.T2I_SHOWCASE,
        output_type=OutputType.IMAGE,
        subject="rose gold marble pattern",
        mood="elegant, luxurious, seamless",
        image_prompt_template="""
A {subject} seamless tileable texture,
{mood} aesthetic, veining details,
high resolution, textile design quality,
perfect for product backgrounds
""".strip(),
        tags=["pattern", "marble", "seamless", "luxury"],
        metadata={"pattern_style": "seamless"}
    ),
    TopicDefinition(
        id="floral_vintage",
        category=TopicCategory.T2I_SHOWCASE,
        output_type=OutputType.IMAGE,
        subject="vintage botanical roses",
        mood="romantic, classic, timeless",
        image_prompt_template="""
A {subject} floral pattern design,
{mood} style, watercolor illustration,
delicate petals and leaves,
fabric print quality, botanical art
""".strip(),
        tags=["pattern", "floral", "vintage", "botanical"],
        metadata={"pattern_style": "floral"}
    ),
    TopicDefinition(
        id="geometric_artdeco",
        category=TopicCategory.T2I_SHOWCASE,
        output_type=OutputType.IMAGE,
        subject="art deco geometric pattern",
        mood="bold, glamorous, sophisticated",
        image_prompt_template="""
A {subject} with gold and black,
{mood} design, 1920s inspired,
symmetrical shapes, fan motifs,
luxury wallpaper quality
""".strip(),
        tags=["pattern", "geometric", "artdeco", "gold"],
        metadata={"pattern_style": "geometric"}
    ),
    TopicDefinition(
        id="abstract_watercolor",
        category=TopicCategory.T2I_SHOWCASE,
        output_type=OutputType.IMAGE,
        subject="abstract watercolor flow",
        mood="artistic, fluid, dreamy",
        image_prompt_template="""
A {subject} pattern design,
{mood} colors blending softly,
organic shapes, gradient washes,
contemporary art print quality
""".strip(),
        tags=["pattern", "abstract", "watercolor", "art"],
        metadata={"pattern_style": "abstract"}
    ),
    TopicDefinition(
        id="japanese_wave",
        category=TopicCategory.T2I_SHOWCASE,
        output_type=OutputType.IMAGE,
        subject="Japanese seigaiha wave pattern",
        mood="traditional, serene, harmonious",
        image_prompt_template="""
A {subject} in indigo blue,
{mood} aesthetic, repeating arcs,
traditional Japanese textile design,
ukiyo-e inspired, fabric quality
""".strip(),
        tags=["pattern", "japanese", "traditional", "wave"],
        metadata={"pattern_style": "traditional"}
    ),
]


# =============================================================================
# TOPIC REGISTRY - All Topics in One Place
# =============================================================================

def get_all_topics() -> List[TopicDefinition]:
    """Get all topic definitions across all categories."""
    return (
        PRODUCT_VIDEO_TOPICS +
        INTERIOR_DESIGN_TOPICS +
        STYLE_TRANSFER_TOPICS +
        AVATAR_TOPICS +
        T2I_SHOWCASE_TOPICS
    )


def get_topics_by_category(category: TopicCategory) -> List[TopicDefinition]:
    """Get all topics for a specific category."""
    category_map = {
        TopicCategory.PRODUCT_VIDEO: PRODUCT_VIDEO_TOPICS,
        TopicCategory.INTERIOR_DESIGN: INTERIOR_DESIGN_TOPICS,
        TopicCategory.STYLE_TRANSFER: STYLE_TRANSFER_TOPICS,
        TopicCategory.AVATAR: AVATAR_TOPICS,
        TopicCategory.T2I_SHOWCASE: T2I_SHOWCASE_TOPICS,
    }
    return category_map.get(category, [])


def get_topic_by_id(topic_id: str) -> Optional[TopicDefinition]:
    """Get a specific topic by its ID."""
    for topic in get_all_topics():
        if topic.id == topic_id:
            return topic
    return None


def get_topics_by_output_type(output_type: OutputType) -> List[TopicDefinition]:
    """Get all topics that produce a specific output type."""
    return [t for t in get_all_topics() if t.output_type == output_type]


# Category to Output Type mapping for quick reference
CATEGORY_OUTPUT_MAP: Dict[TopicCategory, OutputType] = {
    TopicCategory.PRODUCT_VIDEO: OutputType.VIDEO,
    TopicCategory.INTERIOR_DESIGN: OutputType.IMAGE,
    TopicCategory.STYLE_TRANSFER: OutputType.VIDEO,
    TopicCategory.AVATAR: OutputType.VIDEO,
    TopicCategory.T2I_SHOWCASE: OutputType.IMAGE,
}
