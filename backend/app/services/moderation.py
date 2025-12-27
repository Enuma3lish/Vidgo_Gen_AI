"""
Content Moderation Service
Uses Redis Block Cache + Gemini API for intelligent content moderation.

Moderation Flow:
1. Check Redis block cache for known illegal words/prompts (fastest)
2. If not in cache, use keyword filter (fast)
3. Check suspicious patterns (fast)
4. Use Gemini API for deep analysis (slower but accurate)
5. Update block cache with Gemini results (learning)
"""
import re
import logging
from typing import Optional, List, Tuple
import httpx
from app.core.config import get_settings
from app.schemas.moderation import ModerationResult, ModerationCategory
from app.services.block_cache import get_block_cache, BlockCacheResult

logger = logging.getLogger(__name__)
settings = get_settings()


# Keyword-based filter as fallback
BLOCKED_KEYWORDS = {
    ModerationCategory.ADULT: [
        "nude", "naked", "sex", "porn", "xxx", "erotic", "hentai",
        "nsfw", "adult only", "explicit", "18+", "r18", "r-18",
        "sexual", "fetish", "bdsm", "lewd", "vulgar",
    ],
    ModerationCategory.VIOLENCE: [
        "gore", "blood", "murder", "kill", "death", "torture",
        "massacre", "execution", "beheading", "dismember", "mutilate",
        "brutal", "violent death", "graphic violence",
    ],
    ModerationCategory.HATE: [
        "nazi", "kkk", "white supremacy", "racial slur", "hate crime",
        "ethnic cleansing", "genocide", "terrorist",
    ],
    ModerationCategory.ILLEGAL: [
        "child abuse", "pedophil", "underage", "minor", "loli", "shota",
        "drug dealing", "bomb making", "weapon tutorial",
    ],
    ModerationCategory.SELF_HARM: [
        "suicide", "self harm", "cut myself", "kill myself",
        "end my life", "overdose",
    ],
    ModerationCategory.DANGEROUS: [
        "how to make bomb", "how to make weapon", "poison someone",
        "hack into", "steal identity",
    ],
}

# Suspicious patterns that need review
SUSPICIOUS_PATTERNS = [
    r"young\s*(girl|boy|child)",
    r"(little|small)\s*(girl|boy|child)",
    r"school\s*(girl|boy)\s*(uniform|outfit)",
    r"(teen|teenager)\s*(nude|naked|undress)",
]


class ModerationService:
    """Content moderation service with Redis Block Cache + Gemini API"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'GEMINI_API_KEY', '')
        self.gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        self._gemini_available = True
        self._block_cache = get_block_cache()

    async def moderate(self, prompt: str, strict_mode: bool = False) -> ModerationResult:
        """
        Moderate content using Redis Block Cache + Gemini API with keyword fallback

        Flow:
        1. Check Redis block cache (fastest - cached known illegal words)
        2. Quick keyword filter check (fast - local)
        3. Check suspicious patterns (fast - regex)
        4. Gemini API for deep analysis (slower - API call)
        5. Update cache with results (learning)

        Args:
            prompt: The text to moderate
            strict_mode: If True, use more aggressive filtering

        Returns:
            ModerationResult with safety assessment
        """
        prompt_lower = prompt.lower()

        # Step 1: Check Redis block cache FIRST (fastest)
        try:
            cache_result = await self._block_cache.check_prompt(prompt)
            if cache_result.is_blocked:
                logger.warning(f"Content blocked by block cache: {cache_result.blocked_words}")
                return ModerationResult(
                    is_safe=False,
                    categories=[self._map_reason_to_category(cache_result.reason)],
                    confidence=cache_result.confidence,
                    reason=cache_result.reason or "Content blocked by cache",
                    flagged_keywords=cache_result.blocked_words,
                    source=f"block_cache:{cache_result.source}"
                )
            # If cache says safe with high confidence and source is "cache" or "gemini", trust it
            if cache_result.source in ("cache", "gemini") and cache_result.confidence >= 0.8:
                logger.debug(f"Content approved by block cache (confidence: {cache_result.confidence})")
                return ModerationResult(
                    is_safe=True,
                    categories=[ModerationCategory.SAFE],
                    confidence=cache_result.confidence,
                    source=f"block_cache:{cache_result.source}"
                )
        except Exception as e:
            logger.error(f"Block cache error (continuing with fallback): {e}")

        # Step 2: Quick keyword filter check
        keyword_result = self._keyword_filter(prompt_lower)
        if not keyword_result.is_safe:
            logger.warning(f"Content blocked by keyword filter: {keyword_result.flagged_keywords}")
            # Add blocked words to cache for future
            await self._update_cache_from_keyword_filter(keyword_result)
            return keyword_result

        # Step 3: Check suspicious patterns
        pattern_result = self._pattern_check(prompt_lower)
        if pattern_result.needs_manual_review:
            logger.info(f"Content flagged for manual review: {prompt[:50]}...")
            if strict_mode:
                pattern_result.is_safe = False
            return pattern_result

        # Step 4: Try Gemini API for deeper analysis
        if self.api_key and self._gemini_available:
            try:
                gemini_result = await self._gemini_moderate(prompt)
                if gemini_result:
                    # Update cache with Gemini result
                    await self._update_cache_from_gemini(prompt, gemini_result)
                    return gemini_result
            except Exception as e:
                logger.error(f"Gemini API error: {e}")
                self._gemini_available = False

        # Default: Pass if no issues found
        return ModerationResult(
            is_safe=True,
            categories=[ModerationCategory.SAFE],
            confidence=0.8,
            source="keyword_filter"
        )

    def _map_reason_to_category(self, reason: Optional[str]) -> ModerationCategory:
        """Map block cache reason to ModerationCategory"""
        if not reason:
            return ModerationCategory.SAFE

        reason_lower = reason.lower()
        if "adult" in reason_lower or "sexual" in reason_lower:
            return ModerationCategory.ADULT
        elif "violence" in reason_lower or "gore" in reason_lower:
            return ModerationCategory.VIOLENCE
        elif "hate" in reason_lower:
            return ModerationCategory.HATE
        elif "illegal" in reason_lower or "child" in reason_lower:
            return ModerationCategory.ILLEGAL
        elif "self" in reason_lower or "harm" in reason_lower:
            return ModerationCategory.SELF_HARM
        elif "dangerous" in reason_lower:
            return ModerationCategory.DANGEROUS
        return ModerationCategory.SAFE

    async def _update_cache_from_keyword_filter(self, result: ModerationResult) -> None:
        """Update block cache with keyword filter results"""
        try:
            if result.flagged_keywords:
                for word in result.flagged_keywords:
                    category = result.categories[0].value if result.categories else "custom"
                    await self._block_cache.add_blocked_word(word, category, "keyword_filter")
        except Exception as e:
            logger.error(f"Failed to update cache from keyword filter: {e}")

    async def _update_cache_from_gemini(self, prompt: str, result: ModerationResult) -> None:
        """Update block cache with Gemini results"""
        try:
            if not result.is_safe and result.flagged_keywords:
                for word in result.flagged_keywords:
                    category = result.categories[0].value if result.categories else "gemini_detected"
                    await self._block_cache.add_blocked_word(word, category, "gemini")
        except Exception as e:
            logger.error(f"Failed to update cache from Gemini: {e}")

    def _keyword_filter(self, prompt_lower: str) -> ModerationResult:
        """Check prompt against blocked keywords"""
        flagged_categories = []
        flagged_keywords = []

        for category, keywords in BLOCKED_KEYWORDS.items():
            for keyword in keywords:
                if keyword in prompt_lower:
                    flagged_categories.append(category)
                    flagged_keywords.append(keyword)

        if flagged_categories:
            # Determine primary category (most severe)
            severity_order = [
                ModerationCategory.ILLEGAL,
                ModerationCategory.ADULT,
                ModerationCategory.VIOLENCE,
                ModerationCategory.HATE,
                ModerationCategory.SELF_HARM,
                ModerationCategory.DANGEROUS,
            ]
            primary_category = ModerationCategory.SAFE
            for cat in severity_order:
                if cat in flagged_categories:
                    primary_category = cat
                    break

            return ModerationResult(
                is_safe=False,
                categories=list(set(flagged_categories)),
                confidence=0.95,
                reason=f"Content contains prohibited keywords: {', '.join(flagged_keywords[:3])}",
                flagged_keywords=flagged_keywords,
                source="keyword_filter"
            )

        return ModerationResult(
            is_safe=True,
            categories=[ModerationCategory.SAFE],
            confidence=0.7,
            source="keyword_filter"
        )

    def _pattern_check(self, prompt_lower: str) -> ModerationResult:
        """Check for suspicious patterns that need manual review"""
        matched_patterns = []

        for pattern in SUSPICIOUS_PATTERNS:
            if re.search(pattern, prompt_lower):
                matched_patterns.append(pattern)

        if matched_patterns:
            return ModerationResult(
                is_safe=True,  # Not blocking, but flagging
                categories=[],
                confidence=0.5,
                reason="Content matches suspicious patterns - manual review recommended",
                needs_manual_review=True,
                source="pattern_filter"
            )

        return ModerationResult(
            is_safe=True,
            categories=[ModerationCategory.SAFE],
            confidence=0.7,
            source="pattern_filter"
        )

    async def _gemini_moderate(self, prompt: str) -> Optional[ModerationResult]:
        """Use Gemini API for content moderation"""
        if not self.api_key:
            return None

        moderation_prompt = f"""Analyze the following text for content safety.
Determine if it contains any of these categories:
- adult/sexual content
- violence/gore
- hate speech
- illegal content
- self-harm
- dangerous activities

Text to analyze: "{prompt}"

Respond in this exact format:
SAFE: yes/no
CATEGORIES: comma-separated list or "none"
CONFIDENCE: 0.0 to 1.0
REASON: brief explanation

Example response:
SAFE: yes
CATEGORIES: none
CONFIDENCE: 0.95
REASON: The prompt describes a nature scene with no concerning content."""

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.gemini_url}?key={self.api_key}",
                    json={
                        "contents": [{"parts": [{"text": moderation_prompt}]}],
                        "safetySettings": [
                            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                        ],
                        "generationConfig": {
                            "temperature": 0.1,
                            "maxOutputTokens": 200,
                        }
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    return self._parse_gemini_response(text)
                else:
                    logger.error(f"Gemini API returned status {response.status_code}")
                    return None

        except httpx.TimeoutException:
            logger.warning("Gemini API timeout")
            return None
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None

    def _parse_gemini_response(self, response_text: str) -> Optional[ModerationResult]:
        """Parse Gemini API response into ModerationResult"""
        try:
            lines = response_text.strip().split('\n')
            result = {}

            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    result[key.strip().upper()] = value.strip()

            is_safe = result.get('SAFE', 'yes').lower() == 'yes'
            categories_str = result.get('CATEGORIES', 'none')
            confidence = float(result.get('CONFIDENCE', '0.8'))
            reason = result.get('REASON', '')

            # Parse categories
            categories = []
            if categories_str.lower() != 'none':
                cat_mapping = {
                    'adult': ModerationCategory.ADULT,
                    'sexual': ModerationCategory.ADULT,
                    'violence': ModerationCategory.VIOLENCE,
                    'gore': ModerationCategory.VIOLENCE,
                    'hate': ModerationCategory.HATE,
                    'illegal': ModerationCategory.ILLEGAL,
                    'self-harm': ModerationCategory.SELF_HARM,
                    'dangerous': ModerationCategory.DANGEROUS,
                }
                for cat_str in categories_str.split(','):
                    cat_str = cat_str.strip().lower()
                    if cat_str in cat_mapping:
                        categories.append(cat_mapping[cat_str])

            if is_safe:
                categories = [ModerationCategory.SAFE]

            return ModerationResult(
                is_safe=is_safe,
                categories=categories,
                confidence=min(max(confidence, 0.0), 1.0),
                reason=reason,
                source="gemini"
            )

        except Exception as e:
            logger.error(f"Error parsing Gemini response: {e}")
            return None

    async def check_health(self) -> Tuple[bool, str]:
        """Check if Gemini API is available"""
        if not self.api_key:
            return False, "API key not configured"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{self.gemini_url}?key={self.api_key}",
                    json={
                        "contents": [{"parts": [{"text": "Hello"}]}],
                        "generationConfig": {"maxOutputTokens": 10}
                    }
                )
                if response.status_code == 200:
                    self._gemini_available = True
                    return True, "Gemini API is available"
                else:
                    self._gemini_available = False
                    return False, f"API returned status {response.status_code}"
        except Exception as e:
            self._gemini_available = False
            return False, str(e)


# Singleton instance
_moderation_service: Optional[ModerationService] = None


def get_moderation_service() -> ModerationService:
    """Get or create moderation service singleton"""
    global _moderation_service
    if _moderation_service is None:
        _moderation_service = ModerationService()
    return _moderation_service
