"""
One-shot: generate try-on candidate assets via PiAPI T2I for human review.

Generates:
  6 full-body model photos (3 female + 3 male) in portrait (768x1152)
  6 garment photos (t-shirt, dress, jacket, blouse, sweater, coat)

Saves PNGs locally to /tmp/vidgo-tryon-candidates/ for human review. After
approval, upload the good ones to gs://vidgo-media-vidgo-ai/static/tryon/.

Usage:
    export PIAPI_KEY=$(gcloud secrets versions access latest --secret=PIAPI_KEY --project=vidgo-ai)
    python backend/scripts/generate_tryon_candidates.py [id ...]

With no args, generates all 12. With args, regenerates only the listed IDs
(e.g. `female-1 male-2 garment-dress`).
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

OUT_DIR = Path("/tmp/vidgo-tryon-candidates")

# Full-body model prompts — very explicit framing to guarantee head-to-toe.
MODELS = {
    "female-1": "Full body portrait photograph of a young east asian woman in her twenties, standing straight facing camera, head to toe visible in frame, arms relaxed at sides, wearing a plain white fitted t-shirt and light blue jeans, hair down, natural makeup, gentle smile, centered composition, plain solid light gray studio backdrop, soft professional fashion lighting, vertical full-body fashion photography, 8K, tall portrait format, no cropping of head or feet",
    "female-2": "Full body portrait photograph of a young taiwanese woman in her late twenties, standing straight facing camera, head to toe visible in frame, arms relaxed at sides, wearing a plain beige fitted sweater and slim black trousers, hair in a ponytail, natural makeup, calm expression, centered composition, plain solid light gray studio backdrop, soft professional fashion lighting, vertical full-body fashion photography, 8K, tall portrait format, no cropping",
    "female-3": "Full body portrait photograph of a young asian woman in her mid twenties, standing straight facing camera, head to toe visible in frame, arms relaxed at sides, wearing a plain gray crew neck t-shirt and dark blue jeans, short bob haircut, natural makeup, friendly expression, centered composition, plain solid light gray studio backdrop, soft professional fashion lighting, vertical full-body fashion photography, 8K, tall portrait format, no cropping",
    "male-1": "Full body portrait photograph of a young east asian man in his twenties, standing straight facing camera, head to toe visible in frame, arms relaxed at sides, wearing a plain white crew neck t-shirt and dark blue jeans, short black hair, neutral expression, athletic build, centered composition, plain solid light gray studio backdrop, soft professional fashion lighting, vertical full-body fashion photography, 8K, tall portrait format, no cropping of head or feet",
    "male-2": "Full body portrait photograph of a young taiwanese man in his late twenties, standing straight facing camera, head to toe visible in frame, arms relaxed at sides, wearing a plain navy blue polo shirt and beige khaki trousers, short styled hair, calm expression, slim build, centered composition, plain solid light gray studio backdrop, soft professional fashion lighting, vertical full-body fashion photography, 8K, tall portrait format, no cropping",
    "male-3": "Full body portrait photograph of a young asian man in his mid twenties, standing straight facing camera, head to toe visible in frame, arms relaxed at sides, wearing a plain light gray t-shirt and black slim fit trousers, short hair, friendly expression, average build, centered composition, plain solid light gray studio backdrop, soft professional fashion lighting, vertical full-body fashion photography, 8K, tall portrait format, no cropping",
}

# Garment prompts — on a plain mannequin or flat-lay so Kling can segment them cleanly.
GARMENTS = {
    "garment-tshirt": "Product photograph of a plain white cotton crew neck t-shirt displayed on an invisible ghost mannequin, front view, centered, clean white background, soft shadows, commercial apparel photography, 8K",
    "garment-dress": "Product photograph of an elegant floral summer midi dress with short sleeves displayed on an invisible ghost mannequin, front view, centered, clean white background, soft shadows, commercial apparel photography, 8K",
    "garment-jacket": "Product photograph of a blue denim casual jacket displayed on an invisible ghost mannequin, front view fully unzipped, centered, clean white background, soft shadows, commercial apparel photography, 8K",
    "garment-blouse": "Product photograph of a soft pink silk button-up blouse with long sleeves displayed on an invisible ghost mannequin, front view, centered, clean white background, soft shadows, commercial apparel photography, 8K",
    "garment-sweater": "Product photograph of a beige knit crew neck sweater displayed on an invisible ghost mannequin, front view, centered, clean white background, soft shadows, commercial apparel photography, 8K",
    "garment-coat": "Product photograph of a classic camel color wool trench coat displayed on an invisible ghost mannequin, front view fully buttoned, centered, clean white background, soft shadows, commercial apparel photography, 8K",
}

ALL = {**MODELS, **GARMENTS}


async def generate_one(client: PiAPIClient, asset_id: str, prompt: str) -> bool:
    logger.info(f"[{asset_id}] generating...")
    # Models: 768x1152 portrait for full-body framing.
    # Garments: 1024x1024 square (standard product shot).
    if asset_id.startswith(("female", "male")):
        width, height = 768, 1152
    else:
        width, height = 1024, 1024
    result = await client.generate_image(prompt=prompt, width=width, height=height, save_locally=False)
    if not result.get("success"):
        logger.error(f"[{asset_id}] FAILED: {result.get('error')}")
        return False
    url = result.get("image_url")
    if not url:
        logger.error(f"[{asset_id}] no image_url in response")
        return False
    dest = OUT_DIR / f"{asset_id}.png"
    async with httpx.AsyncClient(timeout=60.0) as http:
        r = await http.get(url)
        r.raise_for_status()
        dest.write_bytes(r.content)
    logger.info(f"[{asset_id}] saved -> {dest}")
    return True


async def main():
    api_key = os.environ.get("PIAPI_KEY")
    if not api_key:
        print("ERROR: PIAPI_KEY not set in environment", file=sys.stderr)
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    targets = sys.argv[1:] or list(ALL.keys())
    unknown = [t for t in targets if t not in ALL]
    if unknown:
        print(f"ERROR: unknown asset IDs: {unknown}", file=sys.stderr)
        print(f"Valid: {list(ALL.keys())}", file=sys.stderr)
        sys.exit(1)

    client = PiAPIClient(api_key=api_key)
    results = await asyncio.gather(
        *[generate_one(client, a, ALL[a]) for a in targets],
        return_exceptions=True,
    )

    ok = sum(1 for r in results if r is True)
    print(f"\nDone: {ok}/{len(targets)} succeeded. Review in {OUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
