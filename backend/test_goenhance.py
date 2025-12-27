"""
Test GoEnhance API connectivity
"""
import asyncio
import httpx
import os

API_KEY = os.getenv("GOENHANCE_API_KEY", "")
BASE_URL = "https://api.goenhance.ai/api/v1"

async def test_api():
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    print(f"Testing GoEnhance API...")
    print(f"API Key: {API_KEY[:20]}..." if API_KEY else "API Key: NOT SET")
    print("-" * 50)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: Get credits/tokens
        print("\n1. Testing /user/tokens endpoint...")
        try:
            response = await client.get(
                f"{BASE_URL}/user/tokens",
                headers=headers
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Response: {data}")
                credits = data.get("data", {}).get("count", 0)
                print(f"   Credits available: {credits}")
            else:
                print(f"   Error: {response.text[:200]}")
        except Exception as e:
            print(f"   Exception: {e}")

        # Test 2: Get model list
        print("\n2. Testing /video2video/modellist endpoint...")
        try:
            response = await client.get(
                f"{BASE_URL}/video2video/modellist",
                headers=headers
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                total_models = 0
                for category in data.get("data", []):
                    models = category.get("list", [])
                    total_models += len(models)
                    print(f"   Category: {category.get('label')} - {len(models)} models")
                print(f"   Total models available: {total_models}")
            else:
                print(f"   Error: {response.text[:200]}")
        except Exception as e:
            print(f"   Exception: {e}")

    print("\n" + "=" * 50)
    print("Test completed!")

if __name__ == "__main__":
    asyncio.run(test_api())
