"""
Full Demo Flow Test:
1. GoEnhance Nano Banana → Generate Image
2. Pollo AI → Generate Video from Image
3. GoEnhance V2V → Enhance Video
"""
import asyncio
import httpx

# API Keys
GOENHANCE_API_KEY = "sk-_xYZTgkPqK2hJu_dxq2b4cdOCzk0tErvNdaMjSkMdkNTxRLa"
POLLO_API_KEY = "pollo_7f6ZiszaD2B3eXSpbLjuPj7rc7Ivc3GuzYiuODroyTYX"

GOENHANCE_URL = "https://api.goenhance.ai/api/v1"
POLLO_URL = "https://pollo.ai/api/platform"


async def step1_generate_image(client: httpx.AsyncClient, prompt: str) -> str:
    """Step 1: Generate image with GoEnhance Nano Banana"""
    print("\n" + "=" * 60)
    print("STEP 1: Generate Image (GoEnhance Nano Banana)")
    print("=" * 60)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GOENHANCE_API_KEY}"
    }

    # Create image task
    response = await client.post(
        f"{GOENHANCE_URL}/nano-banana",
        headers=headers,
        json={"args": {"prompt": prompt}}
    )

    data = response.json()
    print(f"Response: {data}")

    if data.get("code") != 0:
        raise Exception(f"Image generation failed: {data}")

    img_uuid = data["data"]["img_uuid"]
    print(f"Task created: {img_uuid}")

    # Poll for completion
    for i in range(30):
        await asyncio.sleep(3)

        status_response = await client.get(
            f"{GOENHANCE_URL}/jobs/detail",
            params={"img_uuid": img_uuid},
            headers=headers
        )

        job_data = status_response.json().get("data", {})
        status = job_data.get("status", "unknown")
        print(f"[{i+1}] Status: {status}")

        if status == "success":
            # Get image URL from json array
            json_data = job_data.get("json", [])
            if json_data and len(json_data) > 0:
                image_url = json_data[0].get("value")
                print(f"\nImage generated: {image_url}")
                return image_url
            raise Exception("No image URL in response")

        elif status == "failed":
            raise Exception(f"Image generation failed: {job_data}")

    raise Exception("Image generation timed out")


async def step2_generate_video(client: httpx.AsyncClient, image_url: str, prompt: str) -> str:
    """Step 2: Generate video with Pollo AI (cheapest model)"""
    print("\n" + "=" * 60)
    print("STEP 2: Generate Video (Pollo AI)")
    print("=" * 60)

    headers = {
        "Content-Type": "application/json",
        "x-api-key": POLLO_API_KEY
    }

    # Use Pixverse (cheaper) or Kling
    # Pixverse is generally cheaper
    endpoint = "/generation/pixverse/pixverse-v4-5"

    payload = {
        "input": {
            "image": image_url,
            "prompt": f"{prompt}, smooth motion, cinematic",
            "negativePrompt": "blurry, distorted, low quality, jerky motion",
            "length": 5  # 5 or 8 seconds only
        }
    }

    response = await client.post(
        f"{POLLO_URL}{endpoint}",
        headers=headers,
        json=payload
    )

    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {data}")

    if data.get("code") != "SUCCESS":
        raise Exception(f"Video generation failed: {data}")

    task_id = data["data"]["taskId"]
    print(f"Task created: {task_id}")

    # Poll for completion (Pollo uses webhooks but we'll poll)
    # Note: Pollo task status endpoint might be different
    print("Waiting for video generation (this may take 1-3 minutes)...")

    # Poll for completion using /generation/{taskId}/status
    for i in range(60):  # Max 5 minutes
        await asyncio.sleep(5)

        try:
            status_response = await client.get(
                f"{POLLO_URL}/generation/{task_id}/status",
                headers=headers
            )
            print(f"[{i+1}] Status check: {status_response.status_code}")

            if status_response.status_code == 200:
                status_data = status_response.json()
                print(f"   Response: {status_data}")

                # Status is in generations[0]
                generations = status_data.get("data", {}).get("generations", [])
                if generations:
                    gen = generations[0]
                    task_status = gen.get("status", "")
                    video_url = gen.get("url", "")

                    if task_status == "succeed" and video_url:
                        print(f"\nVideo generated: {video_url}")
                        return video_url

                    elif task_status == "failed":
                        raise Exception(f"Video generation failed: {gen.get('failMsg')}")

        except httpx.HTTPError as e:
            print(f"[{i+1}] HTTP error: {e}")

    raise Exception("Video generation timed out")


async def step3_enhance_video(client: httpx.AsyncClient, video_url: str, style_id: int = 2000) -> str:
    """Step 3: Enhance video with GoEnhance V2V"""
    print("\n" + "=" * 60)
    print("STEP 3: Enhance Video (GoEnhance V2V)")
    print("=" * 60)

    if video_url.startswith("pollo_task:"):
        print("Skipping V2V enhancement - waiting for Pollo video")
        return video_url

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GOENHANCE_API_KEY}"
    }

    payload = {
        "args": {
            "model": style_id,  # Anime Style
            "duration": 3,
            "reference_video_url": video_url,
            "seed": -1,
            "resolution": "720p"
        },
        "type": "mx-v2v"
    }

    response = await client.post(
        f"{GOENHANCE_URL}/video2video/generate",
        headers=headers,
        json=payload
    )

    data = response.json()
    print(f"Response: {data}")

    if data.get("code") != 0:
        raise Exception(f"V2V failed: {data}")

    task_id = data["data"]["img_uuid"]
    print(f"Task created: {task_id}")

    # Poll for completion
    for i in range(60):
        await asyncio.sleep(5)

        status_response = await client.get(
            f"{GOENHANCE_URL}/jobs/detail",
            params={"img_uuid": task_id},
            headers=headers
        )

        job_data = status_response.json().get("data", {})
        status = job_data.get("status", "unknown")
        print(f"[{i+1}] Status: {status}")

        if status == "completed":
            output = job_data.get("output", {})
            video_url = output.get("video_url")
            print(f"\nEnhanced video: {video_url}")
            return video_url

        elif status == "failed":
            raise Exception(f"V2V failed: {job_data}")

    raise Exception("V2V timed out")


async def run_full_demo():
    """Run the full demo flow"""
    print("\n" + "=" * 60)
    print("FULL DEMO FLOW TEST")
    print("=" * 60)

    prompt = "A beautiful sunset over mountains with clouds"

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            # Step 1: Generate Image
            image_url = await step1_generate_image(client, prompt)

            # Step 2: Generate Video
            video_url = await step2_generate_video(client, image_url, prompt)

            # Step 3: Enhance Video (optional, only if we have video URL)
            if not video_url.startswith("pollo_task:"):
                enhanced_url = await step3_enhance_video(client, video_url)
            else:
                enhanced_url = video_url

            print("\n" + "=" * 60)
            print("DEMO FLOW COMPLETE!")
            print("=" * 60)
            print(f"Original Image: {image_url}")
            print(f"Video: {video_url}")
            print(f"Enhanced Video: {enhanced_url}")

        except Exception as e:
            print(f"\nError: {e}")


async def generate_category_videos():
    """Generate videos for all categories via API"""
    print("\n" + "=" * 60)
    print("CATEGORY VIDEO GENERATION")
    print("=" * 60)

    API_BASE = "http://localhost:8000/api/v1/demo"
    CATEGORIES = ["animals", "nature", "urban", "people", "fantasy", "sci-fi", "food"]

    async with httpx.AsyncClient(timeout=600.0) as client:
        for category in CATEGORIES:
            # Check current count
            resp = await client.get(f"{API_BASE}/videos/{category}/count")
            if resp.status_code == 200:
                count_data = resp.json()
                current = count_data.get("count", 0)
                print(f"\n[{category}] Current: {current}/30")

                if current >= 30:
                    print(f"[{category}] Already complete. Skipping.")
                    continue

            # Generate videos
            print(f"[{category}] Generating videos...")
            resp = await client.post(
                f"{API_BASE}/videos/{category}/generate",
                params={"count": 5}
            )

            if resp.status_code == 200:
                data = resp.json()
                print(f"[{category}] Generated: {data.get('generated', 0)}, Total: {data.get('total', 0)}")
            else:
                print(f"[{category}] Error: {resp.status_code}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "batch":
        # Run batch category video generation
        asyncio.run(generate_category_videos())
    else:
        # Run full demo flow test
        asyncio.run(run_full_demo())
