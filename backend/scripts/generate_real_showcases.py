"""
Generate Real Showcase Examples using Leonardo AI API.

This script generates actual AI-generated images and videos for tool showcases:
1. For image tools: Generate images using prompts
2. For video tools: Generate image then convert to video

The complete generation flow is stored in generation_params:
- original_prompt: User's input prompt
- enhanced_prompt: Prompt enhanced for AI generation
- image_prompt: Prompt used for image generation step
- video_prompt: Motion prompt for video generation step
- model: Leonardo model used
- motion_strength: Motion intensity for video
- generated_at: Timestamp of generation

This allows the showcase to be reproduced or used as a template.

Run with: python -m scripts.generate_real_showcases
Options:
  --category: Only generate for specific category (edit_tools, ecommerce, architecture, portrait)
  --limit: Limit number of showcases to generate
  --dry-run: Show what would be generated without actually calling API
"""
import asyncio
import sys
import argparse
import logging
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, "/app")

from sqlalchemy import select, update
from app.core.database import AsyncSessionLocal
from app.models.demo import ToolShowcase
from app.services.leonardo import LeonardoClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Tools that generate videos (need image-to-video conversion)
# Note: product_design in ecommerce category can generate videos for product ads
VIDEO_TOOLS = ["product_design"]

# Tools that generate images only
# These must match frontend tool IDs in front_app.py
IMAGE_TOOLS = [
    # Edit tools
    "universal_edit", "hd_upscale", "ai_cutout", "change_bg", "photo_cartoon", "ai_expand",
    # E-commerce tools
    "white_bg", "scene_gen", "model_tryon",
    # Architecture tools
    "ai_concept", "3d_render", "style_convert", "floor_plan",
    # Portrait tools
    "face_swap", "photo_restore", "ai_portrait"
]


async def generate_image_for_showcase(
    client: LeonardoClient,
    showcase: ToolShowcase,
    dry_run: bool = False
) -> dict:
    """Generate an image for a showcase using Leonardo API."""
    original_prompt = showcase.prompt
    tool_id = showcase.tool_id

    # Enhance prompt based on tool type
    enhanced_prompt = original_prompt
    if tool_id == "style_transfer":
        enhanced_prompt = f"{original_prompt}, artistic transformation, high quality"
    elif tool_id == "ai_enhance":
        enhanced_prompt = f"{original_prompt}, 4K ultra HD, sharp details, vibrant colors"
    elif tool_id == "background_remove":
        enhanced_prompt = f"Person or product with clean transparent background, {original_prompt}"
    elif tool_id == "color_correction":
        enhanced_prompt = f"{original_prompt}, professional color grading"
    elif tool_id == "product_background":
        enhanced_prompt = f"Product photography, {original_prompt}, professional studio lighting"
    elif tool_id in ["interior_design", "exterior_rendering"]:
        enhanced_prompt = f"Architectural visualization, {original_prompt}, photorealistic rendering"
    elif tool_id in ["style_portrait", "portrait_enhancement"]:
        enhanced_prompt = f"Portrait photography, {original_prompt}, high quality"

    logger.info(f"  Generating image for: {showcase.title}")
    logger.info(f"    Original prompt: {original_prompt[:60]}...")
    logger.info(f"    Enhanced prompt: {enhanced_prompt[:60]}...")

    if dry_run:
        return {"success": True, "dry_run": True, "prompt": enhanced_prompt}

    # Generate image using Leonardo
    model = "phoenix"
    result = await client.generate_image_and_wait(
        prompt=enhanced_prompt,
        model=model,
        width=1024,
        height=768,
        timeout=120
    )

    if result.get("success"):
        logger.info(f"    Generated image: {result.get('image_url', '')[:60]}...")
        return {
            "success": True,
            "image_url": result.get("image_url"),
            "image_id": result.get("image_id"),
            "generation_id": result.get("generation_id"),
            # Store generation flow for reproducibility
            "generation_params": {
                "original_prompt": original_prompt,
                "enhanced_prompt": enhanced_prompt,
                "model": model,
                "width": 1024,
                "height": 768,
                "generated_at": datetime.utcnow().isoformat()
            }
        }
    else:
        logger.error(f"    Failed: {result.get('error')}")
        return {"success": False, "error": result.get("error")}


async def generate_video_for_showcase(
    client: LeonardoClient,
    showcase: ToolShowcase,
    dry_run: bool = False
) -> dict:
    """
    Generate a video for a showcase using Leonardo API.

    Complete flow:
    1. Use original prompt to generate enhanced image prompt
    2. Generate base image using Leonardo
    3. Convert image to video with motion
    4. Store complete flow for reproducibility
    """
    original_prompt = showcase.prompt
    model = "phoenix"
    motion_strength = 5

    # Step 1: Create enhanced prompt for image generation
    image_prompt = f"Product advertisement, {original_prompt}, cinematic, professional lighting, 4K quality"

    logger.info(f"  Generating video for: {showcase.title}")
    logger.info(f"    Original prompt: {original_prompt[:60]}...")
    logger.info(f"    Step 1: Generate base image")
    logger.info(f"    Image prompt: {image_prompt[:60]}...")

    if dry_run:
        return {"success": True, "dry_run": True, "prompt": image_prompt}

    # Step 2: Generate base image
    image_result = await client.generate_image_and_wait(
        prompt=image_prompt,
        model=model,
        width=1024,
        height=576,  # 16:9 aspect ratio for video
        timeout=120
    )

    if not image_result.get("success"):
        logger.error(f"    Failed to generate base image: {image_result.get('error')}")
        return {"success": False, "error": image_result.get("error")}

    image_id = image_result.get("image_id")
    image_url = image_result.get("image_url")
    image_generation_id = image_result.get("generation_id")
    logger.info(f"    Base image generated: {image_url[:60]}...")

    # Step 3: Generate video from the image
    logger.info(f"    Step 2: Convert to video (motion strength: {motion_strength})")

    success, video_gen_id, _ = await client.generate_video(
        image_id=image_id,
        motion_strength=motion_strength
    )

    if not success:
        logger.error(f"    Failed to start video generation: {video_gen_id}")
        # Return image as fallback with generation params
        return {
            "success": True,
            "image_url": image_url,
            "video_url": None,
            "note": "Video generation failed, using image",
            "generation_params": {
                "original_prompt": original_prompt,
                "image_prompt": image_prompt,
                "model": model,
                "image_generation_id": image_generation_id,
                "motion_strength": motion_strength,
                "video_failed": True,
                "generated_at": datetime.utcnow().isoformat()
            }
        }

    # Poll for video completion
    logger.info(f"    Waiting for video generation...")
    timeout = 300  # 5 minutes
    poll_interval = 10
    elapsed = 0

    while elapsed < timeout:
        result = await client.get_motion_result(video_gen_id)
        status = result.get("status", "").upper()

        if status == "COMPLETE":
            video_url = result.get("video_url")
            logger.info(f"    Video generated: {video_url[:60] if video_url else 'None'}...")
            return {
                "success": True,
                "image_url": image_url,
                "video_url": video_url,
                "generation_id": video_gen_id,
                # Store complete generation flow for reproducibility
                "generation_params": {
                    "original_prompt": original_prompt,
                    "image_prompt": image_prompt,
                    "model": model,
                    "width": 1024,
                    "height": 576,
                    "motion_strength": motion_strength,
                    "image_generation_id": image_generation_id,
                    "video_generation_id": video_gen_id,
                    "generated_at": datetime.utcnow().isoformat(),
                    "flow": "prompt -> image -> video"
                }
            }
        elif status == "FAILED":
            logger.error(f"    Video generation failed")
            return {
                "success": True,
                "image_url": image_url,
                "video_url": None,
                "note": "Video generation failed, using image",
                "generation_params": {
                    "original_prompt": original_prompt,
                    "image_prompt": image_prompt,
                    "model": model,
                    "motion_strength": motion_strength,
                    "video_failed": True,
                    "generated_at": datetime.utcnow().isoformat()
                }
            }

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        logger.info(f"    Still processing... ({elapsed}s)")

    logger.warning(f"    Video generation timed out")
    return {
        "success": True,
        "image_url": image_url,
        "video_url": None,
        "note": "Video generation timed out",
        "generation_params": {
            "original_prompt": original_prompt,
            "image_prompt": image_prompt,
            "model": model,
            "motion_strength": motion_strength,
            "video_timeout": True,
            "generated_at": datetime.utcnow().isoformat()
        }
    }


async def update_showcase_with_result(
    session,
    showcase_id: str,
    result: dict
) -> bool:
    """
    Update a showcase in the database with generated result.

    Stores:
    - result_image_url: Generated image URL
    - result_video_url: Generated video URL (for video tools)
    - generation_params: Complete generation flow for reproducibility
    """
    try:
        update_data = {}

        if result.get("image_url"):
            update_data["result_image_url"] = result["image_url"]
        if result.get("video_url"):
            update_data["result_video_url"] = result["video_url"]
        if result.get("generation_params"):
            update_data["generation_params"] = result["generation_params"]

        if update_data:
            await session.execute(
                update(ToolShowcase)
                .where(ToolShowcase.id == showcase_id)
                .values(**update_data)
            )
            await session.commit()
            logger.info(f"    Updated showcase with generation_params: {list(result.get('generation_params', {}).keys())}")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to update showcase: {e}")
        await session.rollback()
        return False


async def main(category: str = None, limit: int = None, dry_run: bool = False):
    """Main function to generate real showcases."""
    print("=" * 60)
    print("VidGo Real Showcase Generator")
    print("Using Leonardo AI API")
    print("=" * 60)

    if dry_run:
        print("\n*** DRY RUN MODE - No API calls will be made ***\n")

    # Initialize Leonardo client
    client = LeonardoClient()

    if not client.api_key:
        print("ERROR: Leonardo API key not configured!")
        print("Please set LEONARDO_API_KEY in your environment.")
        return

    async with AsyncSessionLocal() as session:
        # Build query
        query = select(ToolShowcase).where(ToolShowcase.is_active == True)

        if category:
            query = query.where(ToolShowcase.tool_category == category)

        query = query.order_by(ToolShowcase.tool_category, ToolShowcase.tool_id)

        if limit:
            query = query.limit(limit)

        result = await session.execute(query)
        showcases = result.scalars().all()

        print(f"\nFound {len(showcases)} showcases to process")

        # Track stats
        stats = {
            "total": len(showcases),
            "images_generated": 0,
            "videos_generated": 0,
            "failed": 0,
            "skipped": 0
        }

        current_category = None

        for showcase in showcases:
            # Print category header
            if showcase.tool_category != current_category:
                current_category = showcase.tool_category
                print(f"\n{'='*40}")
                print(f"Category: {current_category}")
                print(f"{'='*40}")

            tool_id = showcase.tool_id

            # Check if this is a video or image tool
            if tool_id in VIDEO_TOOLS:
                # Generate video
                gen_result = await generate_video_for_showcase(client, showcase, dry_run)

                if gen_result.get("success") and not dry_run:
                    await update_showcase_with_result(session, str(showcase.id), gen_result)
                    if gen_result.get("video_url"):
                        stats["videos_generated"] += 1
                    else:
                        stats["images_generated"] += 1
                elif not gen_result.get("success"):
                    stats["failed"] += 1

            elif tool_id in IMAGE_TOOLS:
                # Generate image
                gen_result = await generate_image_for_showcase(client, showcase, dry_run)

                if gen_result.get("success") and not dry_run:
                    # Pass full result including generation_params
                    await update_showcase_with_result(session, str(showcase.id), gen_result)
                    stats["images_generated"] += 1
                elif not gen_result.get("success"):
                    stats["failed"] += 1
            else:
                logger.info(f"  Skipping unknown tool: {tool_id}")
                stats["skipped"] += 1

            # Small delay between API calls
            if not dry_run:
                await asyncio.sleep(2)

        # Print summary
        print("\n" + "=" * 60)
        print("GENERATION COMPLETE")
        print("=" * 60)
        print(f"Total showcases: {stats['total']}")
        print(f"Images generated: {stats['images_generated']}")
        print(f"Videos generated: {stats['videos_generated']}")
        print(f"Failed: {stats['failed']}")
        print(f"Skipped: {stats['skipped']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate real showcase examples using Leonardo AI")
    parser.add_argument("--category", type=str, help="Only generate for specific category")
    parser.add_argument("--limit", type=int, help="Limit number of showcases to generate")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated without API calls")

    args = parser.parse_args()

    asyncio.run(main(
        category=args.category,
        limit=args.limit,
        dry_run=args.dry_run
    ))
