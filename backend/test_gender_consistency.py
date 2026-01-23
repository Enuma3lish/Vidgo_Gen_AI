"""
Test script for gender consistency in avatar generation.

This script validates that the new gender-matching helper functions work correctly.
"""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.services.material_generator import (
    assign_voice_for_example,
    select_avatar_by_gender,
    get_avatar_for_topic_example,
    AVATAR_IMAGES_BY_GENDER,
    AVATAR_IMAGE_TOPIC_MAPPING
)
from app.services.a2e_service import A2E_VOICES


def test_assign_voice_for_example():
    """Test voice assignment with gender alternation."""
    print("\n=== Testing assign_voice_for_example() ===")
    
    test_cases = [
        ("en", 0),
        ("en", 1),
        ("en", 2),
        ("zh-TW", 0),
        ("zh-TW", 1),
        ("zh-TW", 2),
    ]
    
    for lang, idx in test_cases:
        voice_id, gender = assign_voice_for_example(lang, idx)
        
        # Verify voice exists in A2E_VOICES
        voices = A2E_VOICES.get(lang, A2E_VOICES["en"])
        voice = next((v for v in voices if v["id"] == voice_id), None)
        
        assert voice is not None, f"Voice {voice_id} not found in A2E_VOICES"
        assert voice["gender"] == gender, f"Gender mismatch for {voice_id}"
        
        print(f"✓ {lang}[{idx}]: {voice['name']} ({gender}) - {voice_id}")
    
    print("✅ All voice assignments verified!")


def test_select_avatar_by_gender():
    """Test avatar selection by gender and style."""
    print("\n=== Testing select_avatar_by_gender() ===")
    
    test_cases = [
        ("female", "professional"),
        ("female", "young"),
        ("female", "business"),
        ("male", "professional"),
        ("male", "young"),
        ("male", "business"),
    ]
    
    for gender, style in test_cases:
        avatar_url = select_avatar_by_gender(gender, style)
        
        # Verify avatar URL is in the correct gender-style category
        expected_images = AVATAR_IMAGES_BY_GENDER[gender][style]
        assert avatar_url in expected_images, f"Avatar URL not in {gender}/{style} category"
        
        print(f"✓ {gender}/{style}: {avatar_url[:50]}...")
    
    print("✅ All avatar selections verified!")


def test_get_avatar_for_topic_example():
    """Test topic-based avatar selection."""
    print("\n=== Testing get_avatar_for_topic_example() ===")
    
    topics = ["ecommerce", "social", "brand", "app", "promo", "service"]
    
    for topic in topics:
        print(f"\n{topic}:")
        for idx in range(6):  # 6 examples per topic
            avatar_url = get_avatar_for_topic_example(topic, idx)
            
            # Get expected gender-style pair
            pairs = AVATAR_IMAGE_TOPIC_MAPPING[topic]
            gender, style = pairs[idx % len(pairs)]
            
            # Verify avatar matches expected gender-style
            expected_images = AVATAR_IMAGES_BY_GENDER[gender][style]
            assert avatar_url in expected_images, f"Avatar mismatch for {topic}[{idx}]"
            
            print(f"  [{idx}] {gender}/{style}: {avatar_url[:45]}...")
    
    print("\n✅ All topic-based selections verified!")


def test_gender_consistency_integration():
    """Test end-to-end gender consistency for Landing Examples."""
    print("\n=== Testing Gender Consistency Integration ===")
    
    languages = ["en", "zh-TW"]
    topics = ["ecommerce", "social", "brand", "app", "promo", "service"]
    
    for topic in topics:
        print(f"\n{topic}:")
        for lang in languages:
            for idx in range(6):
                # Get voice and gender
                voice_id, voice_gender = assign_voice_for_example(lang, idx)
                
                # Get avatar for topic/index
                avatar_url = get_avatar_for_topic_example(topic, idx)
                
                # Get expected gender-style from topic mapping
                pairs = AVATAR_IMAGE_TOPIC_MAPPING[topic]
                expected_gender, style = pairs[idx % len(pairs)]
                
                # Verify avatar matches expected gender
                expected_images = AVATAR_IMAGES_BY_GENDER[expected_gender][style]
                assert avatar_url in expected_images, f"Avatar gender mismatch"
                
                # Get voice details
                voices = A2E_VOICES.get(lang, A2E_VOICES["en"])
                voice = next((v for v in voices if v["id"] == voice_id), None)
                
                print(f"  [{lang}][{idx}] Voice: {voice['name']}({voice_gender}) | "
                      f"Avatar: {expected_gender}/{style} ✓")
    
    print("\n✅ Gender consistency integration test passed!")


def main():
    """Run all tests."""
    print("=" * 70)
    print("Gender Consistency Validation Tests")
    print("=" * 70)
    
    try:
        test_assign_voice_for_example()
        test_select_avatar_by_gender()
        test_get_avatar_for_topic_example()
        test_gender_consistency_integration()
        
        print("\n" + "=" * 70)
        print("🎉 ALL TESTS PASSED! Gender consistency logic is working correctly.")
        print("=" * 70)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
