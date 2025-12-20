"""
Smart Demo Engine Service
Matches user prompts to pre-generated demo videos
"""
import re
import logging
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload

from app.models.demo import DemoVideo, DemoCategory, DemoView
from app.schemas.demo import DemoSearchResult, DemoVideoResponse

logger = logging.getLogger(__name__)


# Common keywords for different video styles/categories
STYLE_KEYWORDS = {
    "anime": ["anime", "japanese animation", "manga", "shinkai", "ghibli", "cartoon"],
    "realistic": ["realistic", "real", "photorealistic", "lifelike", "natural"],
    "3d": ["3d", "pixar", "disney", "animated", "cgi", "render"],
    "artistic": ["oil painting", "watercolor", "sketch", "artistic", "impressionist"],
    "retro": ["retro", "80s", "vhs", "vintage", "nostalgic", "synthwave"],
    "cyberpunk": ["cyberpunk", "neon", "futuristic", "sci-fi", "cyber"],
    "nature": ["nature", "landscape", "forest", "ocean", "mountain", "wildlife"],
    "urban": ["city", "urban", "street", "building", "architecture"],
    "abstract": ["abstract", "geometric", "pattern", "motion graphics"],
}

CATEGORY_KEYWORDS = {
    "animals": ["cat", "dog", "bird", "animal", "pet", "wildlife", "lion", "tiger", "elephant"],
    "people": ["person", "man", "woman", "human", "dancer", "walking", "running"],
    "nature": ["tree", "flower", "water", "sky", "cloud", "sunset", "sunrise", "rain", "snow"],
    "technology": ["robot", "ai", "computer", "digital", "tech", "machine"],
    "food": ["food", "cooking", "kitchen", "restaurant", "meal", "fruit", "vegetable"],
    "travel": ["travel", "city", "landmark", "vacation", "tourism", "adventure"],
    "music": ["music", "dance", "concert", "instrument", "dj", "beat"],
    "sports": ["sports", "athlete", "game", "competition", "football", "basketball"],
}


class DemoMatchingService:
    """Smart Demo matching service using keyword and semantic matching"""

    def __init__(self):
        self.style_keywords = STYLE_KEYWORDS
        self.category_keywords = CATEGORY_KEYWORDS

    def extract_keywords(self, prompt: str) -> Tuple[List[str], Optional[str], Optional[str]]:
        """
        Extract keywords, style, and category from a prompt

        Returns:
            Tuple of (keywords, detected_style, detected_category)
        """
        prompt_lower = prompt.lower()
        words = set(re.findall(r'\b\w+\b', prompt_lower))

        # Detect style
        detected_style = None
        max_style_matches = 0
        for style, keywords in self.style_keywords.items():
            matches = sum(1 for kw in keywords if kw in prompt_lower)
            if matches > max_style_matches:
                max_style_matches = matches
                detected_style = style

        # Detect category
        detected_category = None
        max_cat_matches = 0
        for category, keywords in self.category_keywords.items():
            matches = sum(1 for kw in keywords if kw in prompt_lower)
            if matches > max_cat_matches:
                max_cat_matches = matches
                detected_category = category

        # Extract significant words (nouns, adjectives - simplified)
        # Filter out common words
        stop_words = {
            "a", "an", "the", "in", "on", "at", "to", "for", "of", "with",
            "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did",
            "and", "or", "but", "not", "no", "yes",
            "this", "that", "these", "those",
            "i", "you", "he", "she", "it", "we", "they",
            "my", "your", "his", "her", "its", "our", "their",
            "what", "which", "who", "whom", "whose",
            "make", "create", "generate", "show", "video", "image",
        }
        keywords = [w for w in words if w not in stop_words and len(w) > 2]

        return keywords, detected_style, detected_category

    def calculate_match_score(
        self,
        demo: DemoVideo,
        query_keywords: List[str],
        query_style: Optional[str],
        query_category: Optional[str]
    ) -> Tuple[float, List[str]]:
        """
        Calculate how well a demo matches the query

        Returns:
            Tuple of (score 0-1, list of match reasons)
        """
        score = 0.0
        reasons = []

        # Prepare demo data
        demo_keywords = set(k.lower() for k in (demo.keywords or []))
        demo_prompt_words = set(re.findall(r'\b\w+\b', demo.prompt.lower()))
        all_demo_words = demo_keywords | demo_prompt_words

        # 1. Keyword matching (max 0.4)
        keyword_matches = sum(1 for kw in query_keywords if kw in all_demo_words)
        if keyword_matches > 0:
            keyword_score = min(keyword_matches / max(len(query_keywords), 1), 1.0) * 0.4
            score += keyword_score
            reasons.append(f"Matched {keyword_matches} keywords")

        # 2. Style matching (max 0.25)
        if query_style and demo.style:
            if query_style.lower() == demo.style.lower():
                score += 0.25
                reasons.append(f"Style match: {query_style}")
            elif query_style.lower() in demo.style.lower() or demo.style.lower() in query_style.lower():
                score += 0.15
                reasons.append(f"Partial style match: {demo.style}")

        # 3. Category matching via keywords (max 0.2)
        if query_category:
            cat_keywords = self.category_keywords.get(query_category, [])
            cat_matches = sum(1 for kw in cat_keywords if kw in all_demo_words)
            if cat_matches > 0:
                cat_score = min(cat_matches / 3, 1.0) * 0.2
                score += cat_score
                reasons.append(f"Category relevance: {query_category}")

        # 4. Popularity bonus (max 0.1)
        if demo.popularity_score > 100:
            score += 0.05
            reasons.append("Popular demo")
        if demo.popularity_score > 500:
            score += 0.05

        # 5. Quality bonus (max 0.05)
        if demo.quality_score and demo.quality_score > 0.8:
            score += 0.05
            reasons.append("High quality")

        # 6. Featured bonus
        if demo.is_featured:
            score += 0.05
            reasons.append("Featured")

        return min(score, 1.0), reasons

    async def search_demos(
        self,
        db: AsyncSession,
        prompt: str,
        category_slug: Optional[str] = None,
        style: Optional[str] = None,
        limit: int = 5
    ) -> List[DemoSearchResult]:
        """
        Search for demos matching the given prompt

        Args:
            db: Database session
            prompt: User's search prompt
            category_slug: Optional category filter
            style: Optional style filter
            limit: Maximum results to return

        Returns:
            List of DemoSearchResult sorted by match score
        """
        # Extract keywords from prompt
        query_keywords, detected_style, detected_category = self.extract_keywords(prompt)

        # Use provided style/category or detected ones
        search_style = style or detected_style
        search_category = category_slug

        # Build query
        query = select(DemoVideo).where(DemoVideo.is_active == True)

        # Add category filter if specified
        if search_category:
            query = query.join(DemoCategory).where(DemoCategory.slug == search_category)

        # Add style filter if specified
        if search_style:
            query = query.where(DemoVideo.style == search_style)

        # Load with category relationship
        query = query.options(selectinload(DemoVideo.category))

        # Execute query
        result = await db.execute(query)
        demos = result.scalars().all()

        # Calculate scores and rank
        scored_demos = []
        for demo in demos:
            score, reasons = self.calculate_match_score(
                demo, query_keywords, search_style, detected_category
            )
            if score > 0.1:  # Minimum threshold
                scored_demos.append((demo, score, reasons))

        # Sort by score descending
        scored_demos.sort(key=lambda x: x[1], reverse=True)

        # Convert to response objects
        results = []
        for demo, score, reasons in scored_demos[:limit]:
            demo_response = DemoVideoResponse(
                id=demo.id,
                title=demo.title,
                description=demo.description,
                prompt=demo.prompt,
                keywords=demo.keywords or [],
                resolution=demo.resolution,
                style=demo.style,
                video_url_watermarked=demo.video_url_watermarked,
                thumbnail_url=demo.thumbnail_url,
                duration_seconds=demo.duration_seconds,
                category=None,  # Will set if available
                is_featured=demo.is_featured,
                popularity_score=demo.popularity_score,
                created_at=demo.created_at
            )

            results.append(DemoSearchResult(
                demo=demo_response,
                match_score=score,
                match_reasons=reasons
            ))

        return results

    async def get_featured_demos(
        self,
        db: AsyncSession,
        limit: int = 6
    ) -> List[DemoVideoResponse]:
        """Get featured demo videos for homepage"""
        query = (
            select(DemoVideo)
            .where(DemoVideo.is_active == True)
            .where(DemoVideo.is_featured == True)
            .order_by(DemoVideo.popularity_score.desc())
            .limit(limit)
        )

        result = await db.execute(query)
        demos = result.scalars().all()

        return [
            DemoVideoResponse(
                id=demo.id,
                title=demo.title,
                description=demo.description,
                prompt=demo.prompt,
                keywords=demo.keywords or [],
                resolution=demo.resolution,
                style=demo.style,
                video_url_watermarked=demo.video_url_watermarked,
                thumbnail_url=demo.thumbnail_url,
                duration_seconds=demo.duration_seconds,
                category=None,
                is_featured=demo.is_featured,
                popularity_score=demo.popularity_score,
                created_at=demo.created_at
            )
            for demo in demos
        ]

    async def record_view(
        self,
        db: AsyncSession,
        demo_id: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """Record a demo view for popularity tracking"""
        from uuid import UUID

        view = DemoView(
            demo_id=UUID(demo_id),
            user_id=UUID(user_id) if user_id else None,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.add(view)

        # Update popularity score
        await db.execute(
            DemoVideo.__table__.update()
            .where(DemoVideo.id == UUID(demo_id))
            .values(popularity_score=DemoVideo.popularity_score + 1)
        )

        await db.commit()


# Singleton instance
_demo_service: Optional[DemoMatchingService] = None


def get_demo_service() -> DemoMatchingService:
    """Get or create demo matching service singleton"""
    global _demo_service
    if _demo_service is None:
        _demo_service = DemoMatchingService()
    return _demo_service
