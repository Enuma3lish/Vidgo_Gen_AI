"""
One-shot: generate 6 AI Avatar headshot candidates via PiAPI T2I.

Kling Avatar needs a clear, centered face — full-body photos are rejected
with "failed to freeze point". These prompts force head-and-shoulders
framing with a big face area so Kling can detect landmarks.

Saves PNGs locally to /tmp/vidgo-avatar-candidates/ for review. After
approval, upload to gs://vidgo-media-vidgo-ai/static/avatars/.

Usage:
    export PIAPI_KEY=$(gcloud secrets versions access latest --secret=PIAPI_KEY --project=vidgo-ai)
    python backend/scripts/generate_avatar_candidates.py [id ...]
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.services.piapi_client import PiAPIClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

OUT_DIR = Path("/tmp/vidgo-avatar-candidates")

# Head-and-shoulders portraits. Every prompt explicitly asks for:
#   * head and shoulders framing (not full body)
#   * centered face
#   * looking straight at camera
#   * plain studio background
#   * professional portrait lighting
# so Kling Avatar's face detector can lock on.
AVATARS = {
    "female-1": "Professional headshot portrait photograph of a young east asian woman in her mid twenties, head and shoulders framing, face centered and clearly visible, looking straight at camera with warm natural smile, plain light gray studio backdrop, soft even portrait lighting, shoulder-length hair, wearing a simple white blouse, sharp focus on eyes, photo realistic, 85mm portrait lens, 8K",
    "female-2": "Professional headshot portrait photograph of a young taiwanese woman in her late twenties, head and shoulders framing, face centered and clearly visible, looking straight at camera with calm confident expression, plain light gray studio backdrop, soft even portrait lighting, hair in a neat ponytail, wearing a beige knit sweater, sharp focus on eyes, photo realistic, 85mm portrait lens, 8K",
    "female-3": "Professional headshot portrait photograph of a young asian woman in her twenties, head and shoulders framing, face centered and clearly visible, looking straight at camera with friendly expression, plain light gray studio backdrop, soft even portrait lighting, short bob haircut, wearing a gray crew neck top, sharp focus on eyes, photo realistic, 85mm portrait lens, 8K",
    "male-1": "Professional headshot portrait photograph of a young east asian man in his mid twenties, head and shoulders framing, face centered and clearly visible, looking straight at camera with neutral friendly expression, plain light gray studio backdrop, soft even portrait lighting, short black hair, wearing a simple white crew neck t-shirt, sharp focus on eyes, photo realistic, 85mm portrait lens, 8K",
    "male-2": "Professional headshot portrait photograph of a young taiwanese man in his late twenties, head and shoulders framing, face centered and clearly visible, looking straight at camera with calm confident expression, plain light gray studio backdrop, soft even portrait lighting, short styled hair, wearing a navy blue polo shirt, sharp focus on eyes, photo realistic, 85mm portrait lens, 8K",
    "male-3": "Professional headshot portrait photograph of a young asian man in his twenties, head and shoulders framing, face centered and clearly visible, looking straight at camera with approachable friendly expression, plain light gray studio backdrop, soft even portrait lighting, short hair, wearing a light gray t-shirt, sharp focus on eyes, photo realistic, 85mm portrait lens, 8K",
}


async def generate_one(client: PiAPIClient, aid: str, prompt: str) -> bool:
    logger.info(f"[{aid}] generating...")
    # Square-ish portrait (1024x1024) — Kling Avatar prefers big face area.
    result = await client.generate_image(prompt=prompt, width=1024, height=1024, save_locally=False)
    if not result.get("success"):
        logger.error(f"[{aid}] FAILED: {result.get('error')}")
        return False
    url = result.get("image_url")
    if not url:
        logger.error(f"[{aid}] no image_url in response")
        return False
    dest = OUT_DIR / f"{aid}.png"
    async with httpx.AsyncClient(timeout=60.0) as http:
        r = await http.get(url)
        r.raise_for_status()
        dest.write_bytes(r.content)
    logger.info(f"[{aid}] saved -> {dest}")
    return True


async def main():
    api_key = os.environ.get("PIAPI_KEY")
    if not api_key:
        print("ERROR: PIAPI_KEY not set in environment", file=sys.stderr)
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    targets = sys.argv[1:] or list(AVATARS.keys())
    unknown = [t for t in targets if t not in AVATARS]
    if unknown:
        print(f"ERROR: unknown avatar IDs: {unknown}", file=sys.stderr)
        print(f"Valid: {list(AVATARS.keys())}", file=sys.stderr)
        sys.exit(1)

    client = PiAPIClient(api_key=api_key)
    results = await asyncio.gather(
        *[generate_one(client, a, AVATARS[a]) for a in targets],
        return_exceptions=True,
    )

    ok = sum(1 for r in results if r is True)
    print(f"\nDone: {ok}/{len(targets)} succeeded. Review in {OUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
