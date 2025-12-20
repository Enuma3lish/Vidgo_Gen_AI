"""
Unit Tests for Demo Matching Service
"""
import pytest
from app.services.demo import DemoMatchingService, get_demo_service


class TestKeywordExtraction:
    """Tests for keyword extraction from prompts"""

    def setup_method(self):
        self.service = DemoMatchingService()

    def test_extract_basic_keywords(self):
        """Test basic keyword extraction"""
        keywords, style, category = self.service.extract_keywords(
            "A cute cat playing with a ball"
        )
        assert "cat" in keywords
        assert "cute" in keywords
        assert "ball" in keywords
        assert "playing" in keywords

    def test_detect_anime_style(self):
        """Test anime style detection"""
        keywords, style, category = self.service.extract_keywords(
            "Anime character in Japanese style"
        )
        assert style == "anime"

    def test_detect_realistic_style(self):
        """Test realistic style detection"""
        keywords, style, category = self.service.extract_keywords(
            "Photorealistic portrait of a person"
        )
        assert style == "realistic"

    def test_detect_3d_style(self):
        """Test 3D style detection"""
        keywords, style, category = self.service.extract_keywords(
            "Pixar style 3D animated character"
        )
        assert style == "3d"

    def test_detect_cyberpunk_style(self):
        """Test cyberpunk style detection"""
        keywords, style, category = self.service.extract_keywords(
            "Cyberpunk neon city at night"
        )
        assert style == "cyberpunk"

    def test_detect_animals_category(self):
        """Test animals category detection"""
        keywords, style, category = self.service.extract_keywords(
            "A dog running in the field"
        )
        assert category == "animals"

    def test_detect_nature_category(self):
        """Test nature category detection"""
        keywords, style, category = self.service.extract_keywords(
            "Beautiful sunset over the ocean with clouds"
        )
        assert category == "nature"

    def test_detect_technology_category(self):
        """Test technology category detection"""
        keywords, style, category = self.service.extract_keywords(
            "A robot in a digital computer room"
        )
        assert category == "technology"

    def test_filter_stop_words(self):
        """Test that stop words are filtered out"""
        keywords, style, category = self.service.extract_keywords(
            "The cat is on the mat"
        )
        assert "the" not in keywords
        assert "is" not in keywords
        assert "on" not in keywords
        assert "cat" in keywords
        assert "mat" in keywords

    def test_empty_prompt(self):
        """Test handling of empty prompt"""
        keywords, style, category = self.service.extract_keywords("")
        assert keywords == []
        assert style is None
        assert category is None

    def test_no_style_detected(self):
        """Test when no specific style is detected"""
        keywords, style, category = self.service.extract_keywords(
            "Something very generic"
        )
        # May or may not have a style, but shouldn't crash
        assert isinstance(keywords, list)


class TestMatchScoring:
    """Tests for demo matching score calculation"""

    def setup_method(self):
        self.service = DemoMatchingService()

    def test_keyword_match_increases_score(self):
        """Test that keyword matches increase score"""
        # Create a mock demo object
        class MockDemo:
            prompt = "A cute cat playing with a red ball"
            keywords = ["cat", "ball", "cute"]
            style = "realistic"
            popularity_score = 100
            quality_score = 0.8
            is_featured = False

        demo = MockDemo()

        # Query that matches keywords
        score1, reasons1 = self.service.calculate_match_score(
            demo,
            query_keywords=["cat", "ball"],
            query_style=None,
            query_category=None
        )

        # Query that doesn't match
        score2, reasons2 = self.service.calculate_match_score(
            demo,
            query_keywords=["dog", "running"],
            query_style=None,
            query_category=None
        )

        assert score1 > score2

    def test_style_match_increases_score(self):
        """Test that style match increases score"""

        class MockDemo:
            prompt = "A cat"
            keywords = ["cat"]
            style = "anime"
            popularity_score = 0
            quality_score = 0
            is_featured = False

        demo = MockDemo()

        score1, _ = self.service.calculate_match_score(
            demo,
            query_keywords=["cat"],
            query_style="anime",
            query_category=None
        )

        score2, _ = self.service.calculate_match_score(
            demo,
            query_keywords=["cat"],
            query_style="realistic",
            query_category=None
        )

        assert score1 > score2

    def test_popularity_bonus(self):
        """Test that popularity adds bonus score"""

        class PopularDemo:
            prompt = "A cat"
            keywords = ["cat"]
            style = None
            popularity_score = 600
            quality_score = 0
            is_featured = False

        class UnpopularDemo:
            prompt = "A cat"
            keywords = ["cat"]
            style = None
            popularity_score = 10
            quality_score = 0
            is_featured = False

        score1, _ = self.service.calculate_match_score(
            PopularDemo(),
            query_keywords=["cat"],
            query_style=None,
            query_category=None
        )

        score2, _ = self.service.calculate_match_score(
            UnpopularDemo(),
            query_keywords=["cat"],
            query_style=None,
            query_category=None
        )

        assert score1 > score2

    def test_featured_bonus(self):
        """Test that featured demos get bonus score"""

        class FeaturedDemo:
            prompt = "A cat"
            keywords = ["cat"]
            style = None
            popularity_score = 0
            quality_score = 0
            is_featured = True

        class NormalDemo:
            prompt = "A cat"
            keywords = ["cat"]
            style = None
            popularity_score = 0
            quality_score = 0
            is_featured = False

        score1, reasons1 = self.service.calculate_match_score(
            FeaturedDemo(),
            query_keywords=["cat"],
            query_style=None,
            query_category=None
        )

        score2, reasons2 = self.service.calculate_match_score(
            NormalDemo(),
            query_keywords=["cat"],
            query_style=None,
            query_category=None
        )

        assert score1 > score2
        assert "Featured" in reasons1

    def test_score_capped_at_one(self):
        """Test that score is capped at 1.0"""

        class PerfectDemo:
            prompt = "anime cat in cyberpunk nature"
            keywords = ["anime", "cat", "cyberpunk", "nature", "featured"]
            style = "anime"
            popularity_score = 1000
            quality_score = 1.0
            is_featured = True

        score, _ = self.service.calculate_match_score(
            PerfectDemo(),
            query_keywords=["anime", "cat", "cyberpunk", "nature"],
            query_style="anime",
            query_category="animals"
        )

        assert score <= 1.0


class TestDemoServiceSingleton:
    """Tests for demo service singleton"""

    def test_singleton_returns_same_instance(self):
        """Test that get_demo_service returns same instance"""
        service1 = get_demo_service()
        service2 = get_demo_service()
        assert service1 is service2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
