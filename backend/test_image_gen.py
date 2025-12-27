"""
Test Gemini Image Generation (Nano Banana)
"""
import asyncio
import httpx
import os
import base64

GEMINI_API_KEY = "AIzaSyDSnsuDS4IZnnv92_UcXtAmUCCy0V9KDaY"

async def test_gemini_image():
    print("Testing Gemini Image Generation (Nano Banana)...")
    print("=" * 60)

    # Test with gemini-2.0-flash-exp (supports image generation)
    models_to_try = [
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash",
    ]

    base_url = "https://generativelanguage.googleapis.com/v1beta"
    prompt = "Generate an image of a cute orange cat sitting on a windowsill, looking at a sunset. Photorealistic style."

    async with httpx.AsyncClient(timeout=60.0) as client:
        for model in models_to_try:
            print(f"\n1. Testing model: {model}")

            try:
                response = await client.post(
                    f"{base_url}/models/{model}:generateContent?key={GEMINI_API_KEY}",
                    json={
                        "contents": [{
                            "parts": [{
                                "text": prompt
                            }]
                        }],
                        "generationConfig": {
                            "responseModalities": ["image", "text"],
                        }
                    }
                )

                print(f"   Status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])

                    if candidates:
                        content = candidates[0].get("content", {})
                        parts = content.get("parts", [])

                        for i, part in enumerate(parts):
                            if "text" in part:
                                print(f"   Part {i} (text): {part['text'][:100]}...")
                            if "inlineData" in part:
                                inline = part["inlineData"]
                                mime = inline.get("mimeType", "unknown")
                                data_len = len(inline.get("data", ""))
                                print(f"   Part {i} (image): {mime}, {data_len} chars base64")

                                # Save image for verification
                                if data_len > 0:
                                    print(f"   SUCCESS! Image generated.")
                                    # Optionally save to file
                                    # with open(f"test_output_{model}.png", "wb") as f:
                                    #     f.write(base64.b64decode(inline["data"]))
                                    break
                    else:
                        print(f"   No candidates in response")
                        print(f"   Response: {data}")
                else:
                    print(f"   Error: {response.text[:300]}")

            except Exception as e:
                print(f"   Exception: {e}")

    print("\n" + "=" * 60)
    print("Test completed!")

if __name__ == "__main__":
    asyncio.run(test_gemini_image())
