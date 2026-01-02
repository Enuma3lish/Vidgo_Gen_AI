"""
Generate product-related video examples using Pollo AI text-to-video
"""
import asyncio
import httpx
import uuid
import os
from pathlib import Path

# Pollo AI configuration - use environment variable
POLLO_API_KEY = os.getenv("POLLO_API_KEY")
if not POLLO_API_KEY:
    raise ValueError("POLLO_API_KEY environment variable not set")
STATIC_DIR = Path("/app/static/generated")

# Product-related video prompts
PRODUCT_VIDEO_PROMPTS = [
    {
        "title": "Sneaker Showcase",
        "title_zh": "運動鞋展示",
        "prompt": "Professional product video of a white sneaker rotating 360 degrees on a clean white platform, studio lighting, e-commerce style, smooth rotation",
        "prompt_zh": "專業產品影片，白色運動鞋在乾淨白色平台上360度旋轉，攝影棚燈光，電商風格",
        "style": "product",
        "tool": "product_video"
    },
    {
        "title": "Perfume Bottle",
        "title_zh": "香水瓶展示",
        "prompt": "Elegant perfume bottle with golden liquid, soft mist spray effect, luxury beauty product advertisement, slow motion, bokeh lights",
        "prompt_zh": "優雅香水瓶，金色液體，柔和噴霧效果，奢華美妝廣告，慢動作",
        "style": "luxury",
        "tool": "product_video"
    },
    {
        "title": "Watch Commercial",
        "title_zh": "手錶廣告",
        "prompt": "Luxury wristwatch slowly rotating, metallic reflections, dark elegant background, premium product showcase, cinematic lighting",
        "prompt_zh": "豪華腕錶緩慢旋轉，金屬反光，深色優雅背景，高級產品展示",
        "style": "luxury",
        "tool": "product_video"
    },
    {
        "title": "Coffee Product",
        "title_zh": "咖啡產品",
        "prompt": "Steaming hot coffee being poured into a ceramic cup, coffee beans scattered around, warm morning atmosphere, food advertisement style",
        "prompt_zh": "熱騰騰咖啡倒入陶瓷杯中，咖啡豆散落四周，溫暖早晨氛圍，食品廣告風格",
        "style": "lifestyle",
        "tool": "product_video"
    },
    {
        "title": "Cosmetics Display",
        "title_zh": "化妝品展示",
        "prompt": "Lipstick and makeup products arranged elegantly, soft pink lighting, beauty product commercial, gentle camera movement, feminine aesthetic",
        "prompt_zh": "口紅和化妝品優雅排列，柔和粉色燈光，美妝產品廣告，輕柔鏡頭運動",
        "style": "beauty",
        "tool": "product_video"
    },
    {
        "title": "Tech Gadget",
        "title_zh": "科技產品",
        "prompt": "Sleek smartphone floating and rotating in space, holographic light effects, futuristic tech product advertisement, blue neon glow",
        "prompt_zh": "時尚智能手機在空中漂浮旋轉，全息光效，未來科技產品廣告，藍色霓虹光",
        "style": "tech",
        "tool": "product_video"
    }
]


async def generate_video_with_pollo(prompt: str) -> str | None:
    """Generate video using Pollo AI text-to-video API"""
    print(f"  Generating video with prompt: {prompt[:50]}...")

    async with httpx.AsyncClient(timeout=300) as client:
        # Step 1: Create generation task
        try:
            response = await client.post(
                "https://pollo.ai/api/platform/generation/pollo/pollo-v2-0",
                headers={
                    "x-api-key": POLLO_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "input": {
                        "prompt": prompt,
                        "length": 5,  # 5 seconds
                        "resolution": "720p"
                    }
                }
            )

            if response.status_code != 200:
                print(f"  Error creating task: {response.status_code} - {response.text}")
                return None

            data = response.json()
            # Handle nested response format: {"code": "SUCCESS", "data": {"taskId": "xxx"}}
            task_id = data.get("id") or data.get("data", {}).get("taskId")
            if not task_id:
                print(f"  No task ID returned: {data}")
                return None

            print(f"  Task created: {task_id}")

        except Exception as e:
            print(f"  Error creating task: {e}")
            return None

        # Step 2: Poll for completion
        max_attempts = 60  # 5 minutes max
        for attempt in range(max_attempts):
            await asyncio.sleep(5)

            try:
                status_response = await client.get(
                    f"https://pollo.ai/api/platform/generation/{task_id}/status",
                    headers={"x-api-key": POLLO_API_KEY}
                )

                if status_response.status_code != 200:
                    continue

                status_data = status_response.json()
                # Pollo API format: {"data": {"generations": [{"status": "succeed", "url": "..."}]}}
                generations = status_data.get("data", {}).get("generations", [])

                if generations:
                    gen = generations[0]
                    status = gen.get("status")

                    if status == "succeed":
                        video_url = gen.get("url")
                        if video_url:
                            print(f"  Video ready: {video_url[:60]}...")
                            return video_url
                        else:
                            print(f"  Completed but no video URL: {status_data}")
                            return None

                    elif status == "failed":
                        print(f"  Generation failed: {gen.get('failMsg', 'Unknown error')}")
                        return None

                    else:
                        if attempt % 6 == 0:  # Log every 30 seconds
                            print(f"  Status: {status} (attempt {attempt + 1}/{max_attempts})")

            except Exception as e:
                print(f"  Error checking status: {e}")

        print("  Timeout waiting for video generation")
        return None


async def download_video(video_url: str, task_id: str) -> str | None:
    """Download video and save locally"""
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.get(video_url)
            if response.status_code == 200:
                filename = f"video_product_{task_id}_{uuid.uuid4().hex[:8]}.mp4"
                filepath = STATIC_DIR / filename
                filepath.write_bytes(response.content)
                print(f"  Downloaded: {filename} ({len(response.content) / 1024 / 1024:.1f}MB)")
                return f"/static/generated/{filename}"
    except Exception as e:
        print(f"  Download error: {e}")
    return None


async def save_to_database(video_data: dict, local_url: str):
    """Save video example to database"""
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.demo import ToolShowcase

    async with AsyncSessionLocal() as session:
        showcase = ToolShowcase(
            tool_category="video",
            tool_id="product_video",
            tool_name="Product Video",
            tool_name_zh="產品影片",
            source_image_url=None,  # Text-to-video, no source image
            prompt=video_data["prompt"],
            prompt_zh=video_data["prompt_zh"],
            result_video_url=local_url,
            result_image_url=local_url,  # For compatibility
            title=video_data["title"],
            title_zh=video_data["title_zh"],
            style_tags=[video_data["style"], "product", "video"],
            is_featured=True,
            is_active=True,
            source_service="pollo_ai"
        )
        session.add(showcase)
        await session.commit()
        print(f"  Saved to database: {video_data['title']}")


async def main():
    """Generate product video examples"""
    print("=" * 60)
    print("Generating Product-Related Video Examples")
    print("=" * 60)

    # Ensure static directory exists
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    success_count = 0

    for i, video_data in enumerate(PRODUCT_VIDEO_PROMPTS):
        print(f"\n[{i+1}/{len(PRODUCT_VIDEO_PROMPTS)}] {video_data['title']}")

        # Generate video
        video_url = await generate_video_with_pollo(video_data["prompt"])

        if video_url:
            # Download locally
            task_id = f"prod{i+1}"
            local_url = await download_video(video_url, task_id)

            if local_url:
                # Save to database
                await save_to_database(video_data, local_url)
                success_count += 1

        # Small delay between requests
        await asyncio.sleep(2)

    print("\n" + "=" * 60)
    print(f"Complete! Generated {success_count}/{len(PRODUCT_VIDEO_PROMPTS)} product videos")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
