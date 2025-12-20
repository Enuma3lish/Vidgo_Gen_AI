"""
Unit Tests for Content Moderation Service
"""
import pytest
from app.services.moderation import ModerationService, get_moderation_service
from app.schemas.moderation import ModerationCategory


class TestKeywordFilter:
    """Tests for keyword-based content filtering"""

    def setup_method(self):
        """Set up test fixtures"""
        self.service = ModerationService(api_key=None)  # No API key - uses keyword filter only

    @pytest.mark.asyncio
    async def test_safe_content_passes(self):
        """Test that safe content passes moderation"""
        safe_prompts = [
            "A cat playing with a ball",
            "Beautiful sunset over the ocean",
            "A person walking in the park",
            "Flowers blooming in spring",
            "A cozy coffee shop scene",
        ]

        for prompt in safe_prompts:
            result = await self.service.moderate(prompt)
            assert result.is_safe, f"Safe prompt was flagged: {prompt}"
            assert ModerationCategory.SAFE in result.categories

    @pytest.mark.asyncio
    async def test_adult_content_blocked(self):
        """Test that adult content is blocked"""
        adult_prompts = [
            "nude woman on beach",
            "explicit sexual content",
            "nsfw adult video",
        ]

        for prompt in adult_prompts:
            result = await self.service.moderate(prompt)
            assert not result.is_safe, f"Adult content was not blocked: {prompt}"
            assert ModerationCategory.ADULT in result.categories
            assert len(result.flagged_keywords) > 0

    @pytest.mark.asyncio
    async def test_violence_content_blocked(self):
        """Test that violent content is blocked"""
        violent_prompts = [
            "graphic murder scene",
            "brutal torture video",
            "gore and blood everywhere",
        ]

        for prompt in violent_prompts:
            result = await self.service.moderate(prompt)
            assert not result.is_safe, f"Violent content was not blocked: {prompt}"
            assert ModerationCategory.VIOLENCE in result.categories

    @pytest.mark.asyncio
    async def test_illegal_content_blocked(self):
        """Test that illegal content is blocked"""
        illegal_prompts = [
            "child abuse video",
            "underage content",
        ]

        for prompt in illegal_prompts:
            result = await self.service.moderate(prompt)
            assert not result.is_safe, f"Illegal content was not blocked: {prompt}"
            assert ModerationCategory.ILLEGAL in result.categories

    @pytest.mark.asyncio
    async def test_pattern_detection_flags_review(self):
        """Test that suspicious patterns are flagged for review"""
        suspicious_prompts = [
            "young girl in school uniform",
            "little boy playing",
        ]

        for prompt in suspicious_prompts:
            result = await self.service.moderate(prompt)
            # These might pass but should flag for manual review
            assert result.needs_manual_review or not result.is_safe

    @pytest.mark.asyncio
    async def test_case_insensitive_matching(self):
        """Test that keyword matching is case insensitive"""
        prompts = [
            "NUDE CONTENT",
            "Nude Content",
            "nude content",
            "NuDe CoNtEnT",
        ]

        for prompt in prompts:
            result = await self.service.moderate(prompt)
            assert not result.is_safe, f"Case-insensitive match failed: {prompt}"

    @pytest.mark.asyncio
    async def test_confidence_scores(self):
        """Test that confidence scores are within valid range"""
        prompts = [
            "A beautiful landscape",
            "nude content explicit",
        ]

        for prompt in prompts:
            result = await self.service.moderate(prompt)
            assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_source_attribution(self):
        """Test that moderation source is correctly attributed"""
        result = await self.service.moderate("test content")
        assert result.source in ["keyword_filter", "pattern_filter", "gemini"]


class TestModerationServiceSingleton:
    """Tests for moderation service singleton"""

    def test_singleton_returns_same_instance(self):
        """Test that get_moderation_service returns same instance"""
        service1 = get_moderation_service()
        service2 = get_moderation_service()
        assert service1 is service2


class TestModerationEdgeCases:
    """Tests for edge cases in moderation"""

    def setup_method(self):
        self.service = ModerationService(api_key=None)

    @pytest.mark.asyncio
    async def test_empty_prompt(self):
        """Test handling of empty prompt - should pass"""
        result = await self.service.moderate("")
        # Empty prompts should pass keyword filter
        assert result.is_safe

    @pytest.mark.asyncio
    async def test_very_long_prompt(self):
        """Test handling of very long prompt"""
        long_prompt = "safe content " * 1000
        result = await self.service.moderate(long_prompt)
        assert result.is_safe

    @pytest.mark.asyncio
    async def test_special_characters(self):
        """Test handling of special characters"""
        prompt = "A beautiful scene with !@#$%^&*() symbols"
        result = await self.service.moderate(prompt)
        assert result.is_safe

    @pytest.mark.asyncio
    async def test_unicode_content(self):
        """Test handling of unicode/emoji content"""
        prompt = "A happy cat 🐱 playing with a ball 🎾"
        result = await self.service.moderate(prompt)
        assert result.is_safe


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
