"""
Test GoEnhance Image-to-Video API
"""
import asyncio
import httpx
import os

API_KEY = os.getenv("GOENHANCE_API_KEY", "")
BASE_URL = "https://api.goenhance.ai/api/v1"

async def test_i2v_api():
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    print("Testing GoEnhance Image-to-Video API...")
    print("=" * 50)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: Check available endpoints
        print("\n1. Checking API endpoints...")

        # Try image2video modellist
        print("\n   a) GET /image2video/modellist")
        try:
            response = await client.get(
                f"{BASE_URL}/image2video/modellist",
                headers=headers
            )
            print(f"      Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"      Response: {data}")
        except Exception as e:
            print(f"      Error: {e}")

        # Try img2video
        print("\n   b) GET /img2video/modellist")
        try:
            response = await client.get(
                f"{BASE_URL}/img2video/modellist",
                headers=headers
            )
            print(f"      Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"      Response: {data}")
        except Exception as e:
            print(f"      Error: {e}")

        # Check all available endpoints by looking at common patterns
        print("\n2. Checking other potential endpoints...")

        endpoints_to_check = [
            "/txt2video/modellist",
            "/text2video/modellist",
            "/generate/modellist",
            "/models",
            "/v2v/modellist",
        ]

        for endpoint in endpoints_to_check:
            try:
                response = await client.get(
                    f"{BASE_URL}{endpoint}",
                    headers=headers
                )
                print(f"   {endpoint}: {response.status_code}")
                if response.status_code == 200:
                    print(f"      Data: {response.json()}")
            except Exception as e:
                print(f"   {endpoint}: Error - {e}")

    print("\n" + "=" * 50)
    print("Test completed!")

if __name__ == "__main__":
    asyncio.run(test_i2v_api())
