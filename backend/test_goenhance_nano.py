"""
Test GoEnhance Nano Banana API for Image Generation
"""
import asyncio
import httpx

API_KEY = "sk-_xYZTgkPqK2hJu_dxq2b4cdOCzk0tErvNdaMjSkMdkNTxRLa"
BASE_URL = "https://api.goenhance.ai/api/v1"

async def test_nano_banana():
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    print("Testing GoEnhance Nano Banana API...")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Step 1: Generate image
        print("\n1. Generating image with Nano Banana...")

        payload = {
            "args": {
                "prompt": "A cute orange cat sitting on a windowsill, looking at sunset, photorealistic, high quality"
            }
        }

        try:
            response = await client.post(
                f"{BASE_URL}/nano-banana",
                headers=headers,
                json=payload
            )

            print(f"   Status: {response.status_code}")
            data = response.json()
            print(f"   Response: {data}")

            if response.status_code == 200 and data.get("code") == 0:
                img_uuid = data["data"]["img_uuid"]
                print(f"\n   Image UUID: {img_uuid}")

                # Step 2: Poll for completion
                print("\n2. Polling for image completion...")

                for i in range(30):
                    await asyncio.sleep(3)

                    status_response = await client.get(
                        f"{BASE_URL}/jobs/detail",
                        params={"img_uuid": img_uuid},
                        headers=headers
                    )

                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        job_data = status_data.get("data", {})
                        status = job_data.get("status", "unknown")

                        print(f"   [{i+1}] Status: {status}")

                        if status in ["completed", "success"]:
                            output = job_data.get("output", {})
                            image_url = output.get("image_url") or output.get("url") or output.get("result")
                            print(f"\n   SUCCESS!")
                            print(f"   Image URL: {image_url}")
                            print(f"   Full output: {output}")
                            print(f"   Full job data: {job_data}")
                            break
                        elif status == "failed":
                            print(f"\n   FAILED!")
                            print(f"   Error: {job_data}")
                            break
                    else:
                        print(f"   [{i+1}] Status check error: {status_response.status_code}")

        except Exception as e:
            print(f"   Error: {e}")

    print("\n" + "=" * 60)
    print("Test completed!")

if __name__ == "__main__":
    asyncio.run(test_nano_banana())
