"""
Redis-based Prompt Block Cache Service
Caches illegal/blocked words for fast detection.
Uses Gemini API to analyze unknown prompts and update cache.

Flow:
1. User submits prompt
2. Check Redis block cache for known illegal words
3. If found in cache -> Block immediately
4. If not in cache -> Use Gemini to analyze
5. If Gemini says unsafe -> Add to block cache + Block
6. If Gemini says safe -> Allow (optionally cache as safe)
"""
import hashlib
import json
import logging
import re
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

import httpx

try:
    import redis.asyncio as redis
except ImportError:
    import aioredis as redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class BlockReason(str, Enum):
    """Reasons for blocking content"""
    ADULT = "adult_content"
    VIOLENCE = "violence"
    HATE = "hate_speech"
    ILLEGAL = "illegal_content"
    SELF_HARM = "self_harm"
    DANGEROUS = "dangerous_activity"
    CUSTOM = "custom_rule"


@dataclass
class BlockCacheResult:
    """Result from block cache check"""
    is_blocked: bool
    reason: Optional[str] = None
    blocked_words: List[str] = None
    source: str = "cache"  # "cache", "gemini", "keyword"
    confidence: float = 1.0
    cached_at: Optional[datetime] = None

    def __post_init__(self):
        if self.blocked_words is None:
            self.blocked_words = []


class PromptBlockCache:
    """
    Redis-based cache for blocking illegal prompts.

    Redis Keys:
    - block:word:{word_hash} -> blocked word info (JSON)
    - block:prompt:{prompt_hash} -> prompt analysis result (JSON)
    - block:stats -> statistics counter
    - safe:prompt:{prompt_hash} -> known safe prompts (for optimization)
    """

    # Cache TTL settings
    BLOCKED_WORD_TTL = 60 * 60 * 24 * 30  # 30 days for blocked words
    SAFE_PROMPT_TTL = 60 * 60 * 24 * 7    # 7 days for safe prompts
    ANALYSIS_TTL = 60 * 60 * 24           # 24 hours for analysis results

    # Pre-seeded blocked words in multiple languages
    # Supported: English (en), Traditional Chinese (zh-TW), Japanese (ja), Korean (ko), Spanish (es)
    SEED_BLOCKED_WORDS = {
        BlockReason.ADULT: [
            # English
            "nude", "naked", "porn", "xxx", "nsfw", "hentai", "erotic",
            "explicit", "sex", "sexual", "fetish", "bdsm", "lewd", "pornography",
            "masturbation", "orgasm", "intercourse", "genitals",
            # Traditional Chinese (繁體中文)
            "裸體", "色情", "成人片", "A片", "做愛", "性愛", "淫蕩", "淫穢",
            "自慰", "性交", "裸露", "情色", "成人內容", "十八禁", "限制級",
            "露點", "脫光", "性感裸", "口交", "肛交",
            # Japanese (日本語)
            "ヌード", "裸", "ポルノ", "エロ", "アダルト", "セックス", "性的",
            "卑猥", "わいせつ", "淫乱", "オナニー", "フェラ", "中出し",
            "無修正", "18禁", "成人向け", "エッチ",
            # Korean (한국어)
            "누드", "벗은", "포르노", "야동", "성인물", "섹스", "음란",
            "자위", "성행위", "야한", "19금", "성인용", "음란물",
            # Spanish (Español)
            "desnudo", "pornografía", "porno", "sexual", "erótico", "sexo",
            "masturbación", "obsceno", "lujuria", "adulto", "explícito",
        ],
        BlockReason.VIOLENCE: [
            # English
            "gore", "blood", "murder", "kill", "death", "torture",
            "massacre", "execution", "beheading", "mutilate", "dismember",
            "slaughter", "brutal killing", "graphic violence",
            # Traditional Chinese (繁體中文)
            "血腥", "殺人", "謀殺", "屠殺", "虐殺", "斬首", "砍頭",
            "殘殺", "凌遲", "酷刑", "分屍", "血肉模糊", "暴力殺害",
            "處決", "槍決", "肢解",
            # Japanese (日本語)
            "殺人", "殺害", "虐殺", "斬首", "処刑", "拷問", "血まみれ",
            "残虐", "惨殺", "グロ", "グロテスク", "暴力",
            # Korean (한국어)
            "살인", "살해", "학살", "참수", "처형", "고문", "피투성이",
            "잔혹", "폭력", "유혈",
            # Spanish (Español)
            "asesinato", "matar", "masacre", "tortura", "decapitación",
            "ejecución", "violencia", "sangre", "gore", "brutal",
        ],
        BlockReason.HATE: [
            # English
            "nazi", "kkk", "white supremacy", "genocide", "ethnic cleansing",
            "racial slur", "hate crime", "terrorism", "terrorist",
            # Traditional Chinese (繁體中文)
            "納粹", "種族滅絕", "種族清洗", "仇恨犯罪", "恐怖主義",
            "恐怖分子", "白人至上", "種族歧視",
            # Japanese (日本語)
            "ナチス", "人種差別", "民族浄化", "虐殺", "テロリスト",
            "ヘイトクライム", "差別主義",
            # Korean (한국어)
            "나치", "인종차별", "민족학살", "테러리스트", "혐오범죄",
            "백인우월주의",
            # Spanish (Español)
            "nazi", "supremacía blanca", "genocidio", "limpieza étnica",
            "crimen de odio", "terrorismo", "terrorista", "racismo",
        ],
        BlockReason.ILLEGAL: [
            # English
            "child abuse", "pedophil", "underage", "loli", "shota",
            "bomb making", "weapon tutorial", "drug dealing", "child porn",
            "trafficking", "smuggling drugs",
            # Traditional Chinese (繁體中文)
            "兒童色情", "戀童", "未成年", "蘿莉", "正太", "幼女", "幼童",
            "製造炸彈", "武器教學", "販毒", "毒品交易", "人口販賣",
            "非法武器", "兒童性虐待",
            # Japanese (日本語)
            "児童ポルノ", "小児性愛", "ペドフィリア", "ロリ", "ショタ",
            "未成年", "爆弾製造", "武器製造", "麻薬取引", "人身売買",
            "違法薬物",
            # Korean (한국어)
            "아동포르노", "소아성애", "미성년자", "로리", "쇼타",
            "폭탄제조", "마약거래", "인신매매", "불법무기",
            # Spanish (Español)
            "pornografía infantil", "pedofilia", "menor de edad", "abuso infantil",
            "fabricación de bombas", "tráfico de drogas", "trata de personas",
        ],
        BlockReason.SELF_HARM: [
            # English
            "suicide", "self harm", "cut myself", "kill myself", "end my life",
            "overdose", "hang myself", "slit wrists",
            # Traditional Chinese (繁體中文)
            "自殺", "自殘", "割腕", "上吊", "跳樓", "輕生", "尋短",
            "結束生命", "想死", "過量服藥",
            # Japanese (日本語)
            "自殺", "自傷", "リストカット", "首吊り", "飛び降り",
            "死にたい", "命を絶つ", "過剰摂取",
            # Korean (한국어)
            "자살", "자해", "손목긋기", "목매달기", "투신", "죽고싶다",
            "과다복용",
            # Spanish (Español)
            "suicidio", "autolesión", "cortarme", "matarme", "sobredosis",
            "ahorcarme", "quitarme la vida",
        ],
        BlockReason.DANGEROUS: [
            # English
            "how to make bomb", "poison someone", "hack into", "make explosives",
            "synthesize drugs", "create weapon", "attack tutorial",
            # Traditional Chinese (繁體中文)
            "如何製造炸彈", "毒死", "如何入侵", "製作炸藥", "合成毒品",
            "製造武器", "攻擊教學", "駭入", "破解密碼",
            # Japanese (日本語)
            "爆弾の作り方", "毒を盛る", "ハッキング方法", "爆発物製造",
            "薬物合成", "武器作成", "攻撃方法",
            # Korean (한국어)
            "폭탄만들기", "독살", "해킹방법", "폭발물제조", "마약제조",
            "무기제작",
            # Spanish (Español)
            "cómo hacer bomba", "envenenar", "hackear", "fabricar explosivos",
            "sintetizar drogas", "crear arma", "tutorial de ataque",
        ],
    }

    def __init__(self, redis_url: Optional[str] = None, gemini_api_key: Optional[str] = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self.gemini_api_key = gemini_api_key or getattr(settings, 'GEMINI_API_KEY', '')
        self.gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        self._redis: Optional[redis.Redis] = None
        self._initialized = False

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection"""
        if self._redis is None:
            self._redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        return self._redis

    async def initialize(self) -> None:
        """Initialize cache with seed blocked words"""
        if self._initialized:
            return

        try:
            r = await self._get_redis()

            # Seed blocked words into cache
            for reason, words in self.SEED_BLOCKED_WORDS.items():
                for word in words:
                    await self._cache_blocked_word(word, reason.value, "seed")

            self._initialized = True
            logger.info(f"Block cache initialized with {sum(len(w) for w in self.SEED_BLOCKED_WORDS.values())} seed words")

        except Exception as e:
            logger.error(f"Failed to initialize block cache: {e}")
            # Don't raise - continue without cache

    def _hash_text(self, text: str) -> str:
        """Create hash for text (for cache keys)"""
        normalized = text.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _normalize_prompt(self, prompt: str) -> str:
        """Normalize prompt for comparison"""
        # Lowercase, remove extra whitespace
        normalized = prompt.lower().strip()
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized

    def _extract_words(self, prompt: str) -> Set[str]:
        """Extract individual words and phrases from prompt"""
        normalized = self._normalize_prompt(prompt)

        # Extract single words
        words = set(re.findall(r'\b\w+\b', normalized))

        # Extract 2-word phrases (for phrases like "child abuse")
        word_list = normalized.split()
        for i in range(len(word_list) - 1):
            phrase = f"{word_list[i]} {word_list[i+1]}"
            words.add(phrase)

        # Extract 3-word phrases (for phrases like "how to make bomb")
        for i in range(len(word_list) - 2):
            phrase = f"{word_list[i]} {word_list[i+1]} {word_list[i+2]}"
            words.add(phrase)

        return words

    async def _cache_blocked_word(
        self,
        word: str,
        reason: str,
        source: str = "gemini"
    ) -> None:
        """Add a word to the block cache"""
        try:
            r = await self._get_redis()
            word_hash = self._hash_text(word)
            key = f"block:word:{word_hash}"

            data = {
                "word": word.lower(),
                "reason": reason,
                "source": source,
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "hit_count": 0
            }

            await r.set(key, json.dumps(data), ex=self.BLOCKED_WORD_TTL)

            # Update stats
            await r.hincrby("block:stats", "total_blocked_words", 1)
            await r.hincrby("block:stats", f"blocked_by_{source}", 1)

        except Exception as e:
            logger.error(f"Failed to cache blocked word: {e}")

    async def _cache_prompt_result(
        self,
        prompt: str,
        is_blocked: bool,
        reason: Optional[str] = None,
        blocked_words: Optional[List[str]] = None
    ) -> None:
        """Cache the analysis result for a prompt"""
        try:
            r = await self._get_redis()
            prompt_hash = self._hash_text(prompt)

            if is_blocked:
                key = f"block:prompt:{prompt_hash}"
                ttl = self.ANALYSIS_TTL
            else:
                key = f"safe:prompt:{prompt_hash}"
                ttl = self.SAFE_PROMPT_TTL

            data = {
                "prompt_hash": prompt_hash,
                "is_blocked": is_blocked,
                "reason": reason,
                "blocked_words": blocked_words or [],
                "cached_at": datetime.now(timezone.utc).isoformat()
            }

            await r.set(key, json.dumps(data), ex=ttl)

        except Exception as e:
            logger.error(f"Failed to cache prompt result: {e}")

    async def _check_word_in_cache(self, word: str) -> Optional[Dict[str, Any]]:
        """Check if a word is in the block cache"""
        try:
            r = await self._get_redis()
            word_hash = self._hash_text(word)
            key = f"block:word:{word_hash}"

            data = await r.get(key)
            if data:
                result = json.loads(data)
                # Update hit count
                await r.hincrby("block:stats", "cache_hits", 1)
                result["hit_count"] = result.get("hit_count", 0) + 1
                await r.set(key, json.dumps(result), ex=self.BLOCKED_WORD_TTL)
                return result

            return None

        except Exception as e:
            logger.error(f"Failed to check word in cache: {e}")
            return None

    async def _check_prompt_in_cache(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Check if a prompt result is cached"""
        try:
            r = await self._get_redis()
            prompt_hash = self._hash_text(prompt)

            # Check blocked prompts first
            blocked_key = f"block:prompt:{prompt_hash}"
            data = await r.get(blocked_key)
            if data:
                await r.hincrby("block:stats", "prompt_cache_hits", 1)
                return json.loads(data)

            # Check safe prompts
            safe_key = f"safe:prompt:{prompt_hash}"
            data = await r.get(safe_key)
            if data:
                await r.hincrby("block:stats", "prompt_cache_hits", 1)
                return json.loads(data)

            return None

        except Exception as e:
            logger.error(f"Failed to check prompt in cache: {e}")
            return None

    async def check_prompt(self, prompt: str) -> BlockCacheResult:
        """
        Main entry point: Check if a prompt should be blocked.

        Flow:
        1. Check if exact prompt is cached
        2. Check individual words against block cache
        3. If unknown, use Gemini to analyze
        4. Cache the result

        Args:
            prompt: The user prompt to check

        Returns:
            BlockCacheResult with blocking decision
        """
        await self.initialize()

        normalized = self._normalize_prompt(prompt)

        # Step 1: Check prompt cache
        cached_result = await self._check_prompt_in_cache(normalized)
        if cached_result:
            return BlockCacheResult(
                is_blocked=cached_result["is_blocked"],
                reason=cached_result.get("reason"),
                blocked_words=cached_result.get("blocked_words", []),
                source="cache",
                confidence=1.0,
                cached_at=datetime.fromisoformat(cached_result["cached_at"]) if cached_result.get("cached_at") else None
            )

        # Step 2: Check individual words
        words = self._extract_words(prompt)
        blocked_words = []
        block_reasons = []

        for word in words:
            cached_word = await self._check_word_in_cache(word)
            if cached_word:
                blocked_words.append(cached_word["word"])
                block_reasons.append(cached_word["reason"])

        if blocked_words:
            # Found blocked words in cache
            result = BlockCacheResult(
                is_blocked=True,
                reason=f"Contains blocked content: {', '.join(block_reasons[:3])}",
                blocked_words=blocked_words,
                source="cache",
                confidence=0.95
            )
            await self._cache_prompt_result(normalized, True, result.reason, blocked_words)
            return result

        # Step 3: Use Gemini to analyze unknown prompt
        gemini_result = await self._analyze_with_gemini(prompt)

        if gemini_result:
            # Cache the result
            await self._cache_prompt_result(
                normalized,
                gemini_result.is_blocked,
                gemini_result.reason,
                gemini_result.blocked_words
            )

            # If blocked, add individual words to cache for future
            if gemini_result.is_blocked and gemini_result.blocked_words:
                for word in gemini_result.blocked_words:
                    await self._cache_blocked_word(
                        word,
                        gemini_result.reason or BlockReason.CUSTOM.value,
                        "gemini"
                    )

            return gemini_result

        # Default: Allow if Gemini fails
        result = BlockCacheResult(
            is_blocked=False,
            source="fallback",
            confidence=0.5
        )
        await self._cache_prompt_result(normalized, False)
        return result

    async def _analyze_with_gemini(self, prompt: str) -> Optional[BlockCacheResult]:
        """Use Gemini API to analyze prompt for safety"""
        if not self.gemini_api_key:
            logger.warning("Gemini API key not configured")
            return None

        analysis_prompt = f"""Analyze the following text for content safety.
Determine if it contains any of these categories:
- adult/sexual content
- violence/gore
- hate speech
- illegal content (child exploitation, drugs, weapons)
- self-harm
- dangerous activities

Text to analyze: "{prompt}"

Respond in this exact JSON format:
{{
    "is_safe": true/false,
    "reason": "brief explanation if not safe",
    "categories": ["list", "of", "detected", "categories"],
    "blocked_words": ["specific", "problematic", "words"],
    "confidence": 0.0 to 1.0
}}

Only output the JSON, no other text."""

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.gemini_url}?key={self.gemini_api_key}",
                    json={
                        "contents": [{"parts": [{"text": analysis_prompt}]}],
                        "safetySettings": [
                            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                        ],
                        "generationConfig": {
                            "temperature": 0.1,
                            "maxOutputTokens": 300,
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

    def _parse_gemini_response(self, response_text: str) -> Optional[BlockCacheResult]:
        """Parse Gemini JSON response"""
        try:
            # Clean up response text (remove markdown if present)
            text = response_text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            data = json.loads(text)

            is_safe = data.get("is_safe", True)

            if is_safe:
                return BlockCacheResult(
                    is_blocked=False,
                    source="gemini",
                    confidence=data.get("confidence", 0.9)
                )
            else:
                return BlockCacheResult(
                    is_blocked=True,
                    reason=data.get("reason", "Content flagged by AI moderation"),
                    blocked_words=data.get("blocked_words", []),
                    source="gemini",
                    confidence=data.get("confidence", 0.9)
                )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            # Try fallback parsing
            return self._parse_gemini_fallback(response_text)
        except Exception as e:
            logger.error(f"Error parsing Gemini response: {e}")
            return None

    def _parse_gemini_fallback(self, response_text: str) -> Optional[BlockCacheResult]:
        """Fallback parsing for non-JSON Gemini responses"""
        text_lower = response_text.lower()

        # Simple heuristic
        is_unsafe = any(word in text_lower for word in [
            "not safe", "unsafe", "blocked", "harmful", "inappropriate",
            "violence", "adult", "illegal", "dangerous"
        ])

        return BlockCacheResult(
            is_blocked=is_unsafe,
            reason="Content flagged by AI moderation" if is_unsafe else None,
            source="gemini_fallback",
            confidence=0.6
        )

    async def add_blocked_word(
        self,
        word: str,
        reason: str = BlockReason.CUSTOM.value,
        source: str = "manual"
    ) -> bool:
        """
        Manually add a word to the block cache.
        Useful for admin-added blocked words.
        """
        try:
            await self._cache_blocked_word(word, reason, source)
            logger.info(f"Added blocked word: {word} (reason: {reason})")
            return True
        except Exception as e:
            logger.error(f"Failed to add blocked word: {e}")
            return False

    async def remove_blocked_word(self, word: str) -> bool:
        """Remove a word from the block cache"""
        try:
            r = await self._get_redis()
            word_hash = self._hash_text(word)
            key = f"block:word:{word_hash}"

            deleted = await r.delete(key)
            if deleted:
                logger.info(f"Removed blocked word: {word}")
                return True
            return False

        except Exception as e:
            logger.error(f"Failed to remove blocked word: {e}")
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            r = await self._get_redis()
            stats = await r.hgetall("block:stats")

            # Count total blocked words
            blocked_keys = []
            async for key in r.scan_iter("block:word:*"):
                blocked_keys.append(key)

            return {
                "total_blocked_words": len(blocked_keys),
                "cache_hits": int(stats.get("cache_hits", 0)),
                "prompt_cache_hits": int(stats.get("prompt_cache_hits", 0)),
                "blocked_by_seed": int(stats.get("blocked_by_seed", 0)),
                "blocked_by_gemini": int(stats.get("blocked_by_gemini", 0)),
                "blocked_by_manual": int(stats.get("blocked_by_manual", 0)),
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}

    async def clear_cache(self) -> int:
        """Clear all block cache data (use with caution!)"""
        try:
            r = await self._get_redis()
            count = 0

            # Delete block words
            async for key in r.scan_iter("block:*"):
                await r.delete(key)
                count += 1

            # Delete safe prompts
            async for key in r.scan_iter("safe:*"):
                await r.delete(key)
                count += 1

            self._initialized = False
            logger.warning(f"Cleared {count} cache entries")
            return count

        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return 0

    async def close(self) -> None:
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
            self._redis = None


# Singleton instance
_block_cache: Optional[PromptBlockCache] = None


def get_block_cache() -> PromptBlockCache:
    """Get or create block cache singleton"""
    global _block_cache
    if _block_cache is None:
        _block_cache = PromptBlockCache()
    return _block_cache


async def check_prompt_safety(prompt: str) -> BlockCacheResult:
    """Convenience function to check prompt safety"""
    cache = get_block_cache()
    return await cache.check_prompt(prompt)
