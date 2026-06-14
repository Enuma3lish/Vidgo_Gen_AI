"""
Prompt Similarity Service
Finds similar cached prompts to reuse generation results and save credits.
Uses cosine similarity on text embeddings.
"""
import logging
import hashlib
import math
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.demo import PromptCache
from app.services.gemini_service import get_gemini_service

logger = logging.getLogger(__name__)

# Similarity threshold: 0.85 = 85% similar means we use cached result
SIMILARITY_THRESHOLD = 0.85


def calculate_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors.

    Returns:
        Similarity score between -1 and 1 (higher = more similar)
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)


def normalize_prompt(prompt: str) -> str:
    """
    Normalize prompt for consistent matching.
    Removes extra whitespace, lowercases, strips punctuation.
    """
    # Lowercase and strip
    normalized = prompt.lower().strip()

    # Remove extra whitespace
    normalized = " ".join(normalized.split())

    return normalized


def generate_prompt_hash(prompt: str) -> str:
    """
    Generate a unique hash for a prompt.
    Used for exact matching lookup.
    """
    normalized = normalize_prompt(prompt)
    return hashlib.sha256(normalized.encode()).hexdigest()


class SimilarityService:
    """
    Service for finding similar prompts in cache.

    Uses Gemini embeddings for semantic similarity matching.
    Falls back to hash-based matching when embeddings unavailable.
    """

    def __init__(self, threshold: float = SIMILARITY_THRESHOLD):
        self.threshold = threshold
        self.gemini = get_gemini_service()

    async def find_similar_prompt(
        self,
        prompt: str,
        db: AsyncSession,
        embedding: Optional[List[float]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find a similar cached prompt.

        Args:
            prompt: User's prompt to match
            db: Database session
            embedding: Pre-computed embedding (optional)

        Returns:
            Dict with cached result if similar found, None otherwise
        """
        normalized = normalize_prompt(prompt)
        prompt_hash = generate_prompt_hash(prompt)

        # Step 1: Try exact hash match first (fastest)
        exact_match = await self._find_exact_match(prompt_hash, db)
        if exact_match:
            logger.info(f"Found exact match for prompt: {prompt[:50]}...")
            return exact_match

        # Step 2: Try semantic similarity with embeddings
        if embedding is None:
            # Generate embedding for the prompt
            embed_result = await self.gemini.get_embedding(normalized)
            embedding = embed_result.get("embedding", [])

        if embedding:
            similar = await self._find_similar_by_embedding(embedding, db)
            if similar:
                logger.info(f"Found similar cached prompt (similarity: {similar['similarity']:.2f})")
                return similar

        return None

    async def _find_exact_match(
        self,
        prompt_hash: str,
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """Find exact match by hash."""
        result = await db.execute(
            select(PromptCache).where(
                and_(
                    PromptCache.prompt_hash == prompt_hash,
                    PromptCache.is_active == True,
                    PromptCache.status == "completed"
                )
            )
        )
        cached = result.scalar_one_or_none()

        if cached and cached.image_url:
            # Update usage count
            cached.usage_count += 1
            await db.commit()

            return {
                "found": True,
                "exact_match": True,
                "similarity": 1.0,
                "cached_id": str(cached.id),
                "prompt_original": cached.prompt_original,
                "prompt_enhanced": cached.prompt_enhanced,
                "image_url": cached.image_url,
                "video_url": cached.video_url,
                "video_url_watermarked": cached.video_url_watermarked
            }

        return None

    async def _find_similar_by_embedding(
        self,
        query_embedding: List[float],
        db: AsyncSession,
        limit: int = 10
    ) -> Optional[Dict[str, Any]]:
        """
        Find similar prompts by embedding similarity.

        We load recent cached prompts and compute similarity in Python.
        For larger datasets, consider using pgvector extension.
        """
        # Get recent cached prompts with embeddings
        result = await db.execute(
            select(PromptCache).where(
                and_(
                    PromptCache.prompt_embedding.isnot(None),
                    PromptCache.is_active == True,
                    PromptCache.status == "completed",
                    PromptCache.image_url.isnot(None)
                )
            ).order_by(PromptCache.usage_count.desc()).limit(100)
        )
        cached_prompts = result.scalars().all()

        best_match = None
        best_similarity = 0.0

        for cached in cached_prompts:
            if cached.prompt_embedding:
                # Calculate similarity
                similarity = calculate_cosine_similarity(
                    query_embedding,
                    cached.prompt_embedding
                )

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = cached

        # Check if best match exceeds threshold
        if best_match and best_similarity >= self.threshold:
            # Update usage count
            best_match.usage_count += 1
            await db.commit()

            return {
                "found": True,
                "exact_match": False,
                "similarity": best_similarity,
                "cached_id": str(best_match.id),
                "prompt_original": best_match.prompt_original,
                "prompt_enhanced": best_match.prompt_enhanced,
                "image_url": best_match.image_url,
                "video_url": best_match.video_url,
                "video_url_watermarked": best_match.video_url_watermarked
            }

        return None

    async def cache_generation_result(
        self,
        prompt: str,
        enhanced_prompt: str,
        embedding: List[float],
        image_url: str,
        video_url: Optional[str] = None,
        video_url_watermarked: Optional[str] = None,
        db: AsyncSession = None
    ) -> Dict[str, Any]:
        """
        Cache a generation result for future similarity matching.

        Args:
            prompt: Original user prompt
            enhanced_prompt: Enhanced version of prompt
            embedding: Prompt embedding vector
            image_url: Generated image URL
            video_url: Generated video URL (optional)
            video_url_watermarked: Watermarked video URL (optional)
            db: Database session

        Returns:
            Dict with cache entry info
        """
        if not db:
            return {"success": False, "error": "No database session"}

        normalized = normalize_prompt(prompt)
        prompt_hash = generate_prompt_hash(prompt)

        # Check if already cached
        existing = await db.execute(
            select(PromptCache).where(PromptCache.prompt_hash == prompt_hash)
        )
        cached = existing.scalar_one_or_none()

        if cached:
            # Update existing entry
            cached.image_url = image_url
            cached.video_url = video_url
            cached.video_url_watermarked = video_url_watermarked
            cached.prompt_enhanced = enhanced_prompt
            cached.prompt_embedding = embedding
            cached.status = "completed"
            await db.commit()

            return {
                "success": True,
                "cached_id": str(cached.id),
                "is_update": True
            }

        # Create new cache entry
        new_cache = PromptCache(
            prompt_hash=prompt_hash,
            prompt_original=prompt,
            prompt_normalized=normalized,
            prompt_enhanced=enhanced_prompt,
            prompt_embedding=embedding,
            image_url=image_url,
            video_url=video_url,
            video_url_watermarked=video_url_watermarked,
            source_service="leonardo",
            status="completed",
            is_active=True
        )

        db.add(new_cache)
        await db.commit()
        await db.refresh(new_cache)

        return {
            "success": True,
            "cached_id": str(new_cache.id),
            "is_update": False
        }


# Singleton instance
_similarity_service: Optional[SimilarityService] = None


def get_similarity_service() -> SimilarityService:
    """Get or create similarity service singleton"""
    global _similarity_service
    if _similarity_service is None:
        _similarity_service = SimilarityService()
    return _similarity_service
