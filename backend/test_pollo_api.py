"""
Test Pollo AI API for Image-to-Video
"""
import asyncio
import httpx
import os

API_KEY = os.getenv("POLLO_API_KEY", "")
BASE_URL = "https://api.pollo.ai/api/v1"

async def test_pollo_api():
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    print("Testing Pollo AI API...")
    print(f"API Key: {API_KEY[:20]}..." if API_KEY else "API Key: NOT SET")
    print("=" * 50)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: Get user info/credits
        print("\n1. GET /user or /credits")
        for endpoint in ["/user", "/credits", "/balance", "/account"]:
            try:
                response = await client.get(
                    f"{BASE_URL}{endpoint}",
                    headers=headers
                )
                print(f"   {endpoint}: {response.status_code}")
                if response.status_code == 200:
                    print(f"   Response: {response.json()}")
                    break
            except Exception as e:
                print(f"   {endpoint}: Error - {e}")

        # Test 2: Try different API base URLs
        print("\n2. Testing different API base URLs...")
        base_urls = [
            "https://api.pollo.ai/api/v1",
            "https://api.pollo.ai/v1",
            "https://pollo.ai/api/v1",
            "https://pollo.ai/api/platform",
        ]

        for base in base_urls:
            try:
                response = await client.get(
                    f"{base}/models",
                    headers=headers
                )
                print(f"   {base}/models: {response.status_code}")
                if response.status_code == 200:
                    print(f"   Response: {response.json()}")
            except Exception as e:
                print(f"   {base}: Error")

        # Test 3: Try generation endpoint info
        print("\n3. Testing generation endpoints...")
        endpoints = [
            "/generation/models",
            "/generation/kling-ai/models",
            "/generation/info",
            "/models/list",
        ]

        for endpoint in endpoints:
            try:
                response = await client.get(
                    f"{BASE_URL}{endpoint}",
                    headers=headers
                )
                print(f"   {endpoint}: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"   Response keys: {data.keys() if isinstance(data, dict) else type(data)}")
            except Exception as e:
                print(f"   {endpoint}: Error")

    print("\n" + "=" * 50)
    print("Test completed!")

if __name__ == "__main__":
    asyncio.run(test_pollo_api())
