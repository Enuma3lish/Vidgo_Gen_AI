"""
One-shot: generate 8 product photo candidates via PiAPI T2I for human review.

Saves PNGs locally to /tmp/vidgo-product-candidates/product-{1..8}.png using
the same prompts as PRODUCT_SCENE_MAPPING so the frozen assets line up with
the existing product IDs.

Usage:
    export PIAPI_KEY=$(gcloud secrets versions access latest --secret=PIAPI_KEY --project=vidgo-ai)
    python backend/scripts/generate_product_candidates.py [product-1 product-3 ...]

With no args, generates all 8. With args, regenerates only the listed IDs.
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

OUT_DIR = Path("/tmp/vidgo-product-candidates")

PRODUCTS = {
    "product-1": "Studio product photo of a clear cup of bubble milk tea with tapioca pearls, centered, clean white background, soft shadows, commercial photography, 8K",
    "product-2": "Studio product photo of a natural canvas tote bag with minimalist design, standing upright, clean white background, soft shadows, commercial photography, 8K",
    "product-3": "Studio product photo of handmade silver earrings and bracelet set on velvet display, centered, clean white background, jewelry photography, 8K",
    "product-4": "Studio product photo of a glass skincare serum bottle with dropper, clean cosmetics product style, white background, soft glow, 8K",
    "product-5": "Studio product photo of a kraft paper bag of roasted coffee beans with some beans scattered around, centered, clean white background, food product photography, 8K",
    "product-6": "Studio product photo of a compact stainless steel espresso machine, front angle, clean white background, professional appliance advertising, 8K",
    "product-7": "Studio product photo of a handmade soy wax candle in glass jar, centered, clean white background, cozy product advertising, 8K",
    "product-8": "Studio product photo of a premium retail gift set: a decorative pastel pink rigid box open at an angle showing an assortment of curated products inside (small skincare bottle, scented candle, chocolate truffles, dried flowers), satin ribbon accent, luxury boutique packaging design, centered composition, clean white background, soft shadows, commercial product photography, 8K",
}


async def generate_one(client: PiAPIClient, pid: str, prompt: str) -> bool:
    logger.info(f"[{pid}] generating...")
    result = await client.generate_image(prompt=prompt, width=1024, height=1024, save_locally=False)
    if not result.get("success"):
        logger.error(f"[{pid}] FAILED: {result.get('error')}")
        return False
    url = result.get("image_url")
    if not url:
        logger.error(f"[{pid}] no image_url in response")
        return False
    dest = OUT_DIR / f"{pid}.png"
    async with httpx.AsyncClient(timeout=60.0) as http:
        r = await http.get(url)
        r.raise_for_status()
        dest.write_bytes(r.content)
    logger.info(f"[{pid}] saved -> {dest}")
    return True


async def main():
    api_key = os.environ.get("PIAPI_KEY")
    if not api_key:
        print("ERROR: PIAPI_KEY not set in environment", file=sys.stderr)
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    targets = sys.argv[1:] or list(PRODUCTS.keys())
    unknown = [t for t in targets if t not in PRODUCTS]
    if unknown:
        print(f"ERROR: unknown product IDs: {unknown}", file=sys.stderr)
        print(f"Valid: {list(PRODUCTS.keys())}", file=sys.stderr)
        sys.exit(1)

    client = PiAPIClient(api_key=api_key)
    results = await asyncio.gather(
        *[generate_one(client, pid, PRODUCTS[pid]) for pid in targets],
        return_exceptions=True,
    )

    ok = sum(1 for r in results if r is True)
    print(f"\nDone: {ok}/{len(targets)} succeeded. Review in {OUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
