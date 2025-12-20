"""
Content Moderation Service
Uses Gemini API as primary, with keyword fallback filter
"""
import re
import logging
from typing import Optional, List, Tuple
import httpx
from app.core.config import get_settings
from app.schemas.moderation import ModerationResult, ModerationCategory

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
    """Content moderation service with Gemini API and keyword fallback"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'GEMINI_API_KEY', '')
        self.gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        self._gemini_available = True

    async def moderate(self, prompt: str, strict_mode: bool = False) -> ModerationResult:
        """
        Moderate content using Gemini API with keyword fallback

        Args:
            prompt: The text to moderate
            strict_mode: If True, use more aggressive filtering

        Returns:
            ModerationResult with safety assessment
        """
        prompt_lower = prompt.lower()

        # Step 1: Quick keyword filter check
        keyword_result = self._keyword_filter(prompt_lower)
        if not keyword_result.is_safe:
            logger.warning(f"Content blocked by keyword filter: {keyword_result.flagged_keywords}")
            return keyword_result

        # Step 2: Check suspicious patterns
        pattern_result = self._pattern_check(prompt_lower)
        if pattern_result.needs_manual_review:
            logger.info(f"Content flagged for manual review: {prompt[:50]}...")
            if strict_mode:
                pattern_result.is_safe = False
            return pattern_result

        # Step 3: Try Gemini API for deeper analysis
        if self.api_key and self._gemini_available:
            try:
                gemini_result = await self._gemini_moderate(prompt)
                if gemini_result:
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
