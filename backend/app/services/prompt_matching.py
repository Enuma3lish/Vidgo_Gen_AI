"""
Multi-Language Prompt Matching Service
Handles prompt normalization, translation, and similarity matching for demo images.

Supports: English (en), Traditional Chinese (zh-TW), Japanese (ja), Korean (ko), Spanish (es)
"""
import re
import hashlib
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# =============================================================================
# LANGUAGE DETECTION & KEYWORDS
# =============================================================================

# Common keywords in different languages (for detection and matching)
KEYWORD_TRANSLATIONS = {
    # Animals
    "cat": {"zh-TW": ["貓", "貓咪", "喵"], "ja": ["猫", "ネコ", "にゃん"], "ko": ["고양이"], "es": ["gato"]},
    "dog": {"zh-TW": ["狗", "狗狗", "汪"], "ja": ["犬", "イヌ"], "ko": ["개", "강아지"], "es": ["perro"]},
    "bird": {"zh-TW": ["鳥", "小鳥"], "ja": ["鳥", "とり"], "ko": ["새"], "es": ["pájaro", "ave"]},
    "fish": {"zh-TW": ["魚"], "ja": ["魚", "さかな"], "ko": ["물고기"], "es": ["pez", "pescado"]},
    "lion": {"zh-TW": ["獅子"], "ja": ["ライオン"], "ko": ["사자"], "es": ["león"]},
    "tiger": {"zh-TW": ["老虎", "虎"], "ja": ["虎", "タイガー"], "ko": ["호랑이"], "es": ["tigre"]},
    "elephant": {"zh-TW": ["大象"], "ja": ["象", "ゾウ"], "ko": ["코끼리"], "es": ["elefante"]},
    "horse": {"zh-TW": ["馬"], "ja": ["馬", "うま"], "ko": ["말"], "es": ["caballo"]},
    "rabbit": {"zh-TW": ["兔子", "兔"], "ja": ["うさぎ", "ウサギ"], "ko": ["토끼"], "es": ["conejo"]},
    "dragon": {"zh-TW": ["龍"], "ja": ["竜", "ドラゴン"], "ko": ["용"], "es": ["dragón"]},

    # Nature
    "sunset": {"zh-TW": ["夕陽", "日落"], "ja": ["夕日", "サンセット"], "ko": ["일몰", "석양"], "es": ["atardecer", "puesta de sol"]},
    "sunrise": {"zh-TW": ["日出", "朝陽"], "ja": ["日の出", "朝日"], "ko": ["일출"], "es": ["amanecer"]},
    "ocean": {"zh-TW": ["海洋", "大海", "海"], "ja": ["海", "オーシャン"], "ko": ["바다", "해양"], "es": ["océano", "mar"]},
    "mountain": {"zh-TW": ["山", "高山"], "ja": ["山", "やま"], "ko": ["산"], "es": ["montaña"]},
    "forest": {"zh-TW": ["森林", "樹林"], "ja": ["森", "森林"], "ko": ["숲", "산림"], "es": ["bosque"]},
    "flower": {"zh-TW": ["花", "花朵"], "ja": ["花", "はな"], "ko": ["꽃"], "es": ["flor"]},
    "sky": {"zh-TW": ["天空"], "ja": ["空", "そら"], "ko": ["하늘"], "es": ["cielo"]},
    "rain": {"zh-TW": ["雨", "下雨"], "ja": ["雨", "あめ"], "ko": ["비"], "es": ["lluvia"]},
    "snow": {"zh-TW": ["雪"], "ja": ["雪", "ゆき"], "ko": ["눈"], "es": ["nieve"]},
    "waterfall": {"zh-TW": ["瀑布"], "ja": ["滝", "たき"], "ko": ["폭포"], "es": ["cascada"]},
    "cherry blossom": {"zh-TW": ["櫻花"], "ja": ["桜", "さくら"], "ko": ["벚꽃"], "es": ["flor de cerezo"]},

    # Urban
    "city": {"zh-TW": ["城市", "都市"], "ja": ["都市", "まち"], "ko": ["도시"], "es": ["ciudad"]},
    "street": {"zh-TW": ["街道", "街"], "ja": ["通り", "ストリート"], "ko": ["거리"], "es": ["calle"]},
    "night": {"zh-TW": ["夜晚", "夜", "晚上"], "ja": ["夜", "よる"], "ko": ["밤"], "es": ["noche"]},
    "neon": {"zh-TW": ["霓虹", "霓虹燈"], "ja": ["ネオン"], "ko": ["네온"], "es": ["neón"]},
    "tokyo": {"zh-TW": ["東京"], "ja": ["東京", "とうきょう"], "ko": ["도쿄"], "es": ["Tokio"]},
    "building": {"zh-TW": ["建築", "大樓"], "ja": ["建物", "ビル"], "ko": ["건물"], "es": ["edificio"]},

    # People
    "dancer": {"zh-TW": ["舞者", "跳舞"], "ja": ["ダンサー", "踊り子"], "ko": ["댄서", "무용수"], "es": ["bailarín", "bailarina"]},
    "samurai": {"zh-TW": ["武士"], "ja": ["侍", "サムライ"], "ko": ["사무라이"], "es": ["samurái"]},
    "chef": {"zh-TW": ["廚師"], "ja": ["シェフ", "料理人"], "ko": ["요리사", "셰프"], "es": ["chef", "cocinero"]},
    "astronaut": {"zh-TW": ["太空人", "宇航員"], "ja": ["宇宙飛行士"], "ko": ["우주비행사"], "es": ["astronauta"]},
    "warrior": {"zh-TW": ["戰士"], "ja": ["戦士", "ウォリアー"], "ko": ["전사"], "es": ["guerrero"]},

    # Fantasy
    "wizard": {"zh-TW": ["巫師", "魔法師"], "ja": ["魔法使い", "ウィザード"], "ko": ["마법사"], "es": ["mago", "hechicero"]},
    "unicorn": {"zh-TW": ["獨角獸"], "ja": ["ユニコーン"], "ko": ["유니콘"], "es": ["unicornio"]},
    "fairy": {"zh-TW": ["仙女", "精靈"], "ja": ["妖精", "フェアリー"], "ko": ["요정"], "es": ["hada"]},
    "castle": {"zh-TW": ["城堡"], "ja": ["城", "キャッスル"], "ko": ["성"], "es": ["castillo"]},
    "magic": {"zh-TW": ["魔法", "魔術"], "ja": ["魔法", "マジック"], "ko": ["마법"], "es": ["magia"]},

    # Sci-Fi
    "robot": {"zh-TW": ["機器人"], "ja": ["ロボット"], "ko": ["로봇"], "es": ["robot"]},
    "spaceship": {"zh-TW": ["太空船", "宇宙飛船"], "ja": ["宇宙船", "スペースシップ"], "ko": ["우주선"], "es": ["nave espacial"]},
    "future": {"zh-TW": ["未來"], "ja": ["未来", "フューチャー"], "ko": ["미래"], "es": ["futuro"]},
    "cyberpunk": {"zh-TW": ["賽博朋克", "電馭叛客"], "ja": ["サイバーパンク"], "ko": ["사이버펑크"], "es": ["cyberpunk"]},

    # Food
    "sushi": {"zh-TW": ["壽司"], "ja": ["寿司", "すし"], "ko": ["초밥", "스시"], "es": ["sushi"]},
    "ramen": {"zh-TW": ["拉麵"], "ja": ["ラーメン", "らーめん"], "ko": ["라멘"], "es": ["ramen"]},
    "pizza": {"zh-TW": ["披薩"], "ja": ["ピザ"], "ko": ["피자"], "es": ["pizza"]},
    "cake": {"zh-TW": ["蛋糕"], "ja": ["ケーキ"], "ko": ["케이크"], "es": ["pastel", "tarta"]},
    "coffee": {"zh-TW": ["咖啡"], "ja": ["コーヒー"], "ko": ["커피"], "es": ["café"]},

    # Styles
    "anime": {"zh-TW": ["動漫", "動畫"], "ja": ["アニメ"], "ko": ["애니메"], "es": ["anime"]},
    "realistic": {"zh-TW": ["寫實", "真實"], "ja": ["リアル", "写実的"], "ko": ["사실적"], "es": ["realista"]},
    "watercolor": {"zh-TW": ["水彩"], "ja": ["水彩", "すいさい"], "ko": ["수채화"], "es": ["acuarela"]},
    "oil painting": {"zh-TW": ["油畫"], "ja": ["油絵", "油彩"], "ko": ["유화"], "es": ["pintura al óleo"]},
    "cinematic": {"zh-TW": ["電影感", "電影風格"], "ja": ["シネマティック"], "ko": ["시네마틱"], "es": ["cinematográfico"]},

    # Actions
    "flying": {"zh-TW": ["飛行", "飛"], "ja": ["飛ぶ", "フライング"], "ko": ["비행", "날다"], "es": ["volando", "volar"]},
    "running": {"zh-TW": ["跑步", "奔跑"], "ja": ["走る", "ランニング"], "ko": ["달리기"], "es": ["corriendo", "correr"]},
    "dancing": {"zh-TW": ["跳舞"], "ja": ["踊る", "ダンス"], "ko": ["춤추다"], "es": ["bailando", "bailar"]},
    "swimming": {"zh-TW": ["游泳"], "ja": ["泳ぐ", "スイミング"], "ko": ["수영"], "es": ["nadando", "nadar"]},
}

# Category mapping keywords
CATEGORY_KEYWORDS = {
    "animals": ["cat", "dog", "bird", "fish", "lion", "tiger", "elephant", "horse", "rabbit", "dragon", "pet", "wildlife", "animal"],
    "nature": ["sunset", "sunrise", "ocean", "mountain", "forest", "flower", "sky", "rain", "snow", "waterfall", "cherry blossom", "landscape", "nature"],
    "urban": ["city", "street", "night", "neon", "tokyo", "building", "skyline", "urban", "downtown"],
    "people": ["dancer", "samurai", "chef", "astronaut", "warrior", "person", "portrait", "human"],
    "fantasy": ["wizard", "unicorn", "fairy", "castle", "magic", "dragon", "mythical", "enchanted"],
    "sci-fi": ["robot", "spaceship", "future", "cyberpunk", "space", "alien", "futuristic", "tech"],
    "food": ["sushi", "ramen", "pizza", "cake", "coffee", "food", "meal", "cuisine", "delicious"],
    "abstract": ["abstract", "geometric", "pattern", "colorful", "artistic", "surreal"],
    "sports": ["soccer", "basketball", "swimming", "running", "sport", "athlete", "fitness"],
    "music": ["guitar", "piano", "music", "concert", "musician", "band", "performance"],
    "seasonal": ["christmas", "halloween", "spring", "summer", "autumn", "winter", "holiday"],
    "architecture": ["temple", "cathedral", "modern", "ancient", "building", "architecture"],
    "vehicles": ["car", "motorcycle", "airplane", "boat", "train", "vehicle"],
}

# Style keywords
STYLE_KEYWORDS = {
    "anime": ["anime", "animation", "japanese", "cartoon", "manga"],
    "realistic": ["realistic", "real", "photo", "photorealistic", "lifelike"],
    "watercolor": ["watercolor", "water color", "aquarelle", "painted"],
    "oil_painting": ["oil painting", "oil", "classical", "traditional art"],
    "cinematic": ["cinematic", "movie", "film", "hollywood", "dramatic"],
    "pixar": ["pixar", "3d", "cartoon", "disney", "animated"],
    "cyberpunk": ["cyberpunk", "neon", "futuristic", "cyber", "punk"],
    "gpt_anime": ["gpt anime", "ai anime", "enhanced anime"],
}


@dataclass
class PromptAnalysis:
    """Result of prompt analysis"""
    original: str
    normalized: str
    language: str
    keywords: List[str]
    category: Optional[str]
    style: Optional[str]
    confidence: float


class PromptMatchingService:
    """
    Multi-language prompt matching service.
    Normalizes prompts and finds similar demos in database.
    """

    def __init__(self):
        self.keyword_translations = KEYWORD_TRANSLATIONS
        self.category_keywords = CATEGORY_KEYWORDS
        self.style_keywords = STYLE_KEYWORDS

    def detect_language(self, text: str) -> str:
        """
        Detect language of input text.
        Returns: 'en', 'zh-TW', 'ja', 'ko', 'es', or 'unknown'
        """
        # Check for character ranges
        has_cjk = bool(re.search(r'[\u4e00-\u9fff]', text))  # Chinese/Japanese Kanji
        has_hiragana = bool(re.search(r'[\u3040-\u309f]', text))  # Hiragana
        has_katakana = bool(re.search(r'[\u30a0-\u30ff]', text))  # Katakana
        has_korean = bool(re.search(r'[\uac00-\ud7af]', text))  # Korean
        has_spanish_chars = bool(re.search(r'[áéíóúüñ¿¡]', text.lower()))

        if has_korean:
            return "ko"
        if has_hiragana or has_katakana:
            return "ja"
        if has_cjk:
            return "zh-TW"  # Default to Traditional Chinese for CJK
        if has_spanish_chars:
            return "es"
        return "en"

    def normalize_prompt(self, prompt: str) -> PromptAnalysis:
        """
        Normalize prompt to English and extract keywords.
        """
        original = prompt.strip()
        language = self.detect_language(original)
        normalized_words = []
        matched_keywords = []

        # Tokenize (simple word splitting)
        words = re.findall(r'\w+', original.lower())

        for word in words:
            matched = False

            # Check if word matches any translation
            for eng_word, translations in self.keyword_translations.items():
                # Check English
                if word == eng_word.lower() or word in eng_word.lower().split():
                    normalized_words.append(eng_word)
                    matched_keywords.append(eng_word)
                    matched = True
                    break

                # Check translations for detected language
                if language in translations:
                    for trans in translations[language]:
                        if word == trans.lower() or trans.lower() in original.lower():
                            normalized_words.append(eng_word)
                            matched_keywords.append(eng_word)
                            matched = True
                            break
                if matched:
                    break

            if not matched and language == "en":
                normalized_words.append(word)

        # Build normalized prompt
        if language == "en":
            normalized = original.lower()
        else:
            # For non-English, use matched keywords
            normalized = " ".join(normalized_words) if normalized_words else original

        # Detect category
        category = self._detect_category(matched_keywords + words)

        # Detect style
        style = self._detect_style(matched_keywords + words)

        # Calculate confidence
        confidence = len(matched_keywords) / max(len(words), 1)
        confidence = min(confidence, 1.0)

        return PromptAnalysis(
            original=original,
            normalized=normalized,
            language=language,
            keywords=list(set(matched_keywords)),
            category=category,
            style=style,
            confidence=confidence
        )

    def _detect_category(self, keywords: List[str]) -> Optional[str]:
        """Detect category from keywords"""
        scores = {}
        for category, cat_keywords in self.category_keywords.items():
            score = sum(1 for kw in keywords if kw.lower() in cat_keywords)
            if score > 0:
                scores[category] = score

        if scores:
            return max(scores, key=scores.get)
        return None

    def _detect_style(self, keywords: List[str]) -> Optional[str]:
        """Detect style from keywords"""
        for style, style_kws in self.style_keywords.items():
            for kw in keywords:
                if kw.lower() in style_kws:
                    return style
        return None

    def calculate_similarity(
        self,
        query_keywords: List[str],
        demo_keywords: List[str],
        query_category: Optional[str],
        demo_category: Optional[str],
        query_style: Optional[str],
        demo_style: Optional[str]
    ) -> float:
        """
        Calculate similarity score between query and demo.
        Returns score 0.0 - 1.0
        """
        if not query_keywords and not demo_keywords:
            return 0.0

        # Keyword overlap (Jaccard similarity)
        query_set = set(kw.lower() for kw in query_keywords)
        demo_set = set(kw.lower() for kw in demo_keywords)

        intersection = len(query_set & demo_set)
        union = len(query_set | demo_set)

        keyword_score = intersection / max(union, 1)

        # Category match bonus
        category_bonus = 0.2 if query_category and query_category == demo_category else 0.0

        # Style match bonus
        style_bonus = 0.2 if query_style and query_style == demo_style else 0.0

        # Final score
        total_score = keyword_score * 0.6 + category_bonus + style_bonus

        return min(total_score, 1.0)

    def hash_prompt(self, prompt: str) -> str:
        """Generate hash for prompt caching"""
        return hashlib.sha256(prompt.strip().lower().encode()).hexdigest()

    async def find_similar_demos(
        self,
        db: AsyncSession,
        prompt: str,
        limit: int = 10,
        min_score: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Find similar demos in database for a given prompt.
        Returns list of demos with similarity scores.
        """
        from app.models.demo import ImageDemo

        # Analyze prompt
        analysis = self.normalize_prompt(prompt)

        # Query active demos
        query = select(ImageDemo).where(
            and_(
                ImageDemo.is_active == True,
                ImageDemo.status == "completed"
            )
        )
        result = await db.execute(query)
        demos = result.scalars().all()

        # Calculate scores
        scored_demos = []
        for demo in demos:
            score = self.calculate_similarity(
                query_keywords=analysis.keywords,
                demo_keywords=demo.keywords or [],
                query_category=analysis.category,
                demo_category=demo.category_slug,
                query_style=analysis.style,
                demo_style=demo.style_slug
            )

            if score >= min_score:
                scored_demos.append({
                    "demo": demo,
                    "score": score,
                    "matched_keywords": list(set(analysis.keywords) & set(demo.keywords or []))
                })

        # Sort by score (descending) and popularity
        scored_demos.sort(key=lambda x: (x["score"], x["demo"].popularity_score), reverse=True)

        return scored_demos[:limit]

    async def get_random_demo(
        self,
        db: AsyncSession,
        category: Optional[str] = None,
        style: Optional[str] = None
    ) -> Optional[Any]:
        """
        Get a random demo for display on demo page.
        Optionally filter by category or style.
        """
        from app.models.demo import ImageDemo

        query = select(ImageDemo).where(
            and_(
                ImageDemo.is_active == True,
                ImageDemo.status == "completed"
            )
        )

        if category:
            query = query.where(ImageDemo.category_slug == category)
        if style:
            query = query.where(ImageDemo.style_slug == style)

        # Random ordering
        query = query.order_by(func.random()).limit(1)

        result = await db.execute(query)
        return result.scalar_one_or_none()


# Singleton instance
_prompt_matching_service: Optional[PromptMatchingService] = None


def get_prompt_matching_service() -> PromptMatchingService:
    """Get or create prompt matching service singleton"""
    global _prompt_matching_service
    if _prompt_matching_service is None:
        _prompt_matching_service = PromptMatchingService()
    return _prompt_matching_service
