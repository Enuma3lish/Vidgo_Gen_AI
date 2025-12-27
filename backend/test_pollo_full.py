"""
Full Test of Pollo AI Image-to-Video API
"""
import asyncio
import httpx
import os
import time

API_KEY = "pollo_7f6ZiszaD2B3eXSpbLjuPj7rc7Ivc3GuzYiuODroyTYX"
BASE_URL = "https://pollo.ai/api/platform"

# Sample image URL for testing (public image)
SAMPLE_IMAGE = "https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?w=512"

async def test_full_i2v():
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY
    }

    print("Testing Pollo AI Full Image-to-Video Flow...")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Step 1: Create I2V task
        print("\n1. Creating Image-to-Video task...")
        print(f"   Image: {SAMPLE_IMAGE[:50]}...")

        payload = {
            "input": {
                "image": SAMPLE_IMAGE,
                "prompt": "A cute cat looking at camera, gentle movement, cinematic",
                "negativePrompt": "blurry, distorted, low quality",
                "strength": 50,
                "length": 5
            }
        }

        try:
            response = await client.post(
                f"{BASE_URL}/generation/kling-ai/kling-v2",
                headers=headers,
                json=payload
            )
            print(f"   Status: {response.status_code}")
            data = response.json()
            print(f"   Response: {data}")

            if response.status_code == 200 and data.get("code") == "SUCCESS":
                task_id = data["data"]["taskId"]
                print(f"\n   Task ID: {task_id}")

                # Step 2: Poll for task completion
                print("\n2. Polling for task completion...")
                for i in range(30):  # Max 30 attempts (2.5 minutes)
                    await asyncio.sleep(5)

                    status_response = await client.get(
                        f"{BASE_URL}/tasks/{task_id}",
                        headers=headers
                    )

                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        print(f"   [{i+1}] Status: {status_data}")

                        task_status = status_data.get("data", {}).get("status")
                        if task_status == "succeed":
                            print("\n   SUCCESS!")
                            output = status_data.get("data", {}).get("output", {})
                            print(f"   Video URL: {output.get('video')}")
                            break
                        elif task_status == "failed":
                            print("\n   FAILED!")
                            print(f"   Error: {status_data}")
                            break
                    else:
                        print(f"   [{i+1}] Status check returned: {status_response.status_code}")

        except Exception as e:
            print(f"   Error: {e}")

    print("\n" + "=" * 60)
    print("Test completed!")

if __name__ == "__main__":
    asyncio.run(test_full_i2v())
