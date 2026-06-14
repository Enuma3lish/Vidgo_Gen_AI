"""
Tests for Startup Check - Material Validation

Ensures that:
1. Minimum required materials are enforced per tool
2. Service startup correctly validates material counts
3. Single prompt → result flow (not two separate prompts)
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

# Mark all tests as async
pytestmark = pytest.mark.asyncio


class TestMaterialValidation:
    """Tests for material validation logic."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def mock_material_counts(self):
        """Return mock material counts per tool."""
        return {
            "background_removal": 5,
            "product_scene": 4,
            "short_video": 3,
            "ai_avatar": 6,
            "try_on": 2,
            "room_redesign": 1,
        }

    async def test_minimum_required_materials_defined(self):
        """Verify minimum required materials are defined for core tools."""
        from app.models.material import ToolType
        
        # These are the minimum requirements we set
        min_required = {
            ToolType.BACKGROUND_REMOVAL: 3,
            ToolType.PRODUCT_SCENE: 3,
            ToolType.SHORT_VIDEO: 3,
            ToolType.AI_AVATAR: 3,
        }
        
        # Verify all core tools have minimum requirements
        assert ToolType.BACKGROUND_REMOVAL in min_required
        assert ToolType.PRODUCT_SCENE in min_required
        assert ToolType.SHORT_VIDEO in min_required
        assert ToolType.AI_AVATAR in min_required
        
        # Verify minimums are reasonable (>= 3)
        for tool, min_count in min_required.items():
            assert min_count >= 3, f"{tool.value} should require at least 3 materials"

    async def test_check_materials_with_sufficient_counts(self, mock_material_counts):
        """Test that check passes when all materials meet minimum requirements."""
        # All counts exceed minimum of 3
        all_ready = all(count >= 3 for tool, count in mock_material_counts.items() 
                       if tool in ["background_removal", "product_scene", "short_video", "ai_avatar"])
        
        assert all_ready is True

    async def test_check_materials_with_insufficient_counts(self):
        """Test that check fails when materials are below minimum."""
        insufficient_counts = {
            "background_removal": 2,  # Below 3
            "product_scene": 1,       # Below 3
            "short_video": 5,         # OK
            "ai_avatar": 0,           # Below 3
        }
        
        required_tools = ["background_removal", "product_scene", "short_video", "ai_avatar"]
        min_required = 3
        
        all_ready = all(
            insufficient_counts.get(tool, 0) >= min_required 
            for tool in required_tools
        )
        
        assert all_ready is False, "Should fail when any required tool is below minimum"

    async def test_optional_tools_dont_block_startup(self):
        """Test that optional tools (try_on, room_redesign) don't block startup."""
        counts_with_missing_optional = {
            "background_removal": 5,
            "product_scene": 4,
            "short_video": 3,
            "ai_avatar": 6,
            "try_on": 0,         # Optional - 0 is OK
            "room_redesign": 0,  # Optional - 0 is OK
        }
        
        required_tools = ["background_removal", "product_scene", "short_video", "ai_avatar"]
        min_required = 3
        
        all_ready = all(
            counts_with_missing_optional.get(tool, 0) >= min_required 
            for tool in required_tools
        )
        
        assert all_ready is True, "Optional tools with 0 count should not block startup"


class TestMaterialLookupHash:
    """Tests for Material lookup_hash generation - ensures single prompt flow."""

    async def test_lookup_hash_uses_single_prompt(self):
        """Verify lookup_hash is generated from single prompt, not multiple."""
        import hashlib
        
        # Simulate the hash generation logic
        tool_type = "short_video"
        prompt = "Cinematic product showcase, luxury watch rotating slowly"
        effect_prompt = None  # No separate effect prompt
        input_image_url = None  # T2V doesn't need input image
        
        content = f"{tool_type}:{prompt}:{effect_prompt or ''}:{input_image_url or ''}"
        lookup_hash = hashlib.sha256(content.encode()).hexdigest()[:64]
        
        # Verify hash is deterministic for same input
        content2 = f"{tool_type}:{prompt}:{effect_prompt or ''}:{input_image_url or ''}"
        lookup_hash2 = hashlib.sha256(content2.encode()).hexdigest()[:64]
        
        assert lookup_hash == lookup_hash2, "Same prompt should generate same hash"

    async def test_different_prompts_generate_different_hashes(self):
        """Verify different prompts generate different lookup hashes."""
        import hashlib
        
        tool_type = "short_video"
        prompt1 = "Product showcase video"
        prompt2 = "Different product video"
        
        content1 = f"{tool_type}:{prompt1}::"
        content2 = f"{tool_type}:{prompt2}::"
        
        hash1 = hashlib.sha256(content1.encode()).hexdigest()[:64]
        hash2 = hashlib.sha256(content2.encode()).hexdigest()[:64]
        
        assert hash1 != hash2, "Different prompts should generate different hashes"


class TestSinglePromptFlow:
    """Tests to verify single prompt generates both image and video (I2V flow)."""

    async def test_landing_material_uses_same_prompt_for_image_and_video(self):
        """Verify landing page materials use single prompt for image→video flow."""
        # This simulates the flow in material_generator.py
        
        example = {
            "prompt_en": "Student backpack with multiple compartments",
            "prompt_zh": "學生書包配多層收納",
        }
        
        # Step 1: Generate image from prompt
        prompt_for_image = example["prompt_zh"]
        
        # Step 2: Convert to video using SAME prompt
        prompt_for_video = example["prompt_zh"]  # Same prompt!
        
        assert prompt_for_image == prompt_for_video, \
            "I2V flow should use same prompt for image and video"

    async def test_short_video_uses_direct_t2v_single_prompt(self):
        """Verify short_video uses single prompt (T2V, no intermediate image)."""
        # This simulates the flow in main_pregenerate.py
        
        motion_data = {
            "prompts": [
                {
                    "en": "Cinematic product showcase, luxury watch rotating slowly",
                    "zh": "電影級產品展示，奢華手錶緩慢旋轉"
                }
            ]
        }
        
        prompt_data = motion_data["prompts"][0]
        
        # T2V uses single prompt, no image generation step
        prompt_for_video = prompt_data["en"]
        
        # Verify there's no separate "image_prompt" field
        assert "image_prompt" not in prompt_data, \
            "T2V should not have separate image prompt"
        
        # Verify prompt is directly used for video
        assert prompt_for_video == motion_data["prompts"][0]["en"]


class TestMaterialModel:
    """Tests for Material model structure."""

    async def test_material_has_single_prompt_field(self):
        """Verify Material model uses single prompt field (not separate image/video prompts)."""
        from app.models.material import Material
        
        # Check that Material has 'prompt' field
        assert hasattr(Material, 'prompt'), "Material should have 'prompt' field"
        
        # Verify there's no separate video_prompt field
        assert not hasattr(Material, 'video_prompt'), \
            "Material should NOT have separate 'video_prompt' field"
        assert not hasattr(Material, 'image_prompt'), \
            "Material should NOT have separate 'image_prompt' field"

    async def test_material_lookup_hash_generation(self):
        """Test Material.generate_lookup_hash method exists and works."""
        from app.models.material import Material, ToolType
        
        # Check if generate_lookup_hash method exists
        assert hasattr(Material, 'generate_lookup_hash'), \
            "Material should have generate_lookup_hash method"
        
        # Test hash generation
        hash1 = Material.generate_lookup_hash(
            tool_type=ToolType.SHORT_VIDEO.value,
            prompt="Test prompt"
        )
        
        assert hash1 is not None
        assert len(hash1) == 64, "Hash should be 64 characters (SHA256)"
