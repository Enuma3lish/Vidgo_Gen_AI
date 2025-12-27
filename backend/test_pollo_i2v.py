"""
Test Pollo AI Image-to-Video API
"""
import asyncio
import httpx
import os

API_KEY = os.getenv("POLLO_API_KEY", "") or "pollo_7f6ZiszaD2B3eXSpbLjuPj7rc7Ivc3GuzYiuODroyTYX"
BASE_URL = "https://pollo.ai/api/platform"

async def test_pollo_i2v():
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY
    }

    print("Testing Pollo AI Image-to-Video API...")
    print(f"API Key: {API_KEY[:20]}..." if API_KEY else "API Key: NOT SET")
    print(f"Base URL: {BASE_URL}")
    print("=" * 50)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: Check account/credits
        print("\n1. Checking account info...")
        try:
            response = await client.get(
                f"{BASE_URL}/user",
                headers=headers
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print(f"   Response: {response.json()}")
            else:
                print(f"   Response: {response.text[:200]}")
        except Exception as e:
            print(f"   Error: {e}")

        # Test 2: Try a simple generation request (dry run - no image)
        print("\n2. Testing generation endpoint structure...")
        test_endpoints = [
            "/generation/kling-ai/kling-v2",
            "/generation/kling-ai/kling-v1-5",
            "/generation/pixverse/pixverse-v5",
        ]

        for endpoint in test_endpoints:
            try:
                # Just check if endpoint exists (will fail due to missing image but shows if endpoint is valid)
                response = await client.post(
                    f"{BASE_URL}{endpoint}",
                    headers=headers,
                    json={
                        "input": {
                            "prompt": "test"
                        }
                    }
                )
                print(f"   {endpoint}: {response.status_code}")
                if response.status_code != 404:
                    data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text[:100]
                    print(f"      Response: {data}")
            except Exception as e:
                print(f"   {endpoint}: Error - {type(e).__name__}")

        # Test 3: Get task status endpoint
        print("\n3. Testing task status endpoint...")
        try:
            response = await client.get(
                f"{BASE_URL}/tasks/test-task-id",
                headers=headers
            )
            print(f"   Status: {response.status_code}")
            if response.status_code != 404:
                print(f"   Response: {response.text[:200]}")
        except Exception as e:
            print(f"   Error: {e}")

    print("\n" + "=" * 50)
    print("Test completed!")

if __name__ == "__main__":
    asyncio.run(test_pollo_i2v())
