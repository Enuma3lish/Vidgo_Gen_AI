"""Quick diagnostic: call PiAPI Kling Avatar with one of the curated
headshots and print the raw response so we can see exactly why Kling is
rejecting the input.
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.providers.piapi_provider import PiAPIProvider  # noqa: E402


async def main():
    if not os.environ.get("PIAPI_KEY"):
        print("ERROR: PIAPI_KEY not set", file=sys.stderr)
        sys.exit(1)

    _GCS = "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/avatars"
    test_urls = [
        f"{_GCS}/female-1.png",
        f"{_GCS}/female-2.png",
        f"{_GCS}/male-1.png",
    ]
    provider = PiAPIProvider()

    for url in test_urls:
        print(f"\n=== Testing {url} ===")
        try:
            result = await provider.generate_avatar({
                "image_url": url,
                "script": "Hello, this is a test.",
                "language": "en",
                "mode": "std",
            })
            print(f"  success={result.get('success')}")
            print(f"  error={result.get('error')}")
            print(f"  raw={str(result)[:400]}")
        except Exception as e:
            print(f"  EXCEPTION: {e}")


if __name__ == "__main__":
    asyncio.run(main())
