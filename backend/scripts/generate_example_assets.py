"""
generate_example_assets.py — generate real result images for the per-tool
gallery in frontend-vue/src/data/toolExamples.ts.

Runs the existing PiAPI provider directly (no HTTP, no auth) so we don't
have to spin up the API server. Downloads each result, re-uploads it to
gs://<GCS_BUCKET>/static/examples/<tool>/<example_id>.jpg with a stable
public URL, and writes a manifest JSON the frontend update can consume.

Usage:
    cd backend
    python scripts/generate_example_assets.py --tool midjourney-imagine --smoke
    python scripts/generate_example_assets.py --tool all

Cost guard: --smoke runs ONE prompt per --tool flag and exits. Use it
first to verify GCS upload works before running the full batch.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Make `app.*` imports resolve when running this script from anywhere.
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / "backend" / ".env")

import httpx  # noqa: E402

from app.providers.piapi_provider import PiAPIProvider  # noqa: E402
from app.services.gcs_storage_service import get_gcs_storage  # noqa: E402

# ─── Curated prompts (must stay in sync with frontend-vue/src/data/toolExamples.ts)
# We duplicate them here so the script is hermetic — no TS parser needed.

PRODUCT_INPUTS = [
    "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-1.png",
    "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-2.png",
    "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-3.png",
    "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-4.png",
    "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-5.png",
    "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-6.png",
    "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-7.png",
    "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/products/product-8.png",
]
ROOM_INPUT = "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/examples/_inputs/room-empty.jpg"

# tool_key -> list of (example_id, prompt_en[, input_url])
PROMPTS: Dict[str, List[Tuple[str, str, Optional[str]]]] = {
    "midjourney-imagine": [
        ("mj-01", "Side-profile close-up of an Asian woman, soft window light, film grain, 35mm lens, shallow depth of field", None),
        ("mj-02", "Steaming bowl of ramen, rising steam, wooden table, magazine-style shot, 45° overhead angle", None),
        ("mj-03", "Neon cyberpunk street, rain-reflective ground, mist, holographic billboards, cinematic lighting", None),
        ("mj-04", "Minimalist exposed-concrete villa, morning light, reflecting pool, Tadao Ando style", None),
        ("mj-05", "Floating crystal castle in a misty forest, magical particles, moonlight, epic fantasy illustration", None),
        ("mj-06", "Luxury perfume bottle, pure white backdrop, soft studio light, refractive glass, ad photography", None),
        ("mj-07", "Arctic fox lying in snow, fur detail, silver-white palette, National Geographic style", None),
        ("mj-08", "Ghibli-style village at dusk, falling cherry blossoms, soft watercolor feel", None),
        ("mj-09", "Paris street fashion shoot, model in beige trench, autumn leaves, natural light, Vogue style", None),
        ("mj-10", "Liquid metal flowing art, deep blue and gold, 4K detail, modern abstract", None),
    ],
    "pattern-generate": [
        ("pt-01", "Japanese porcelain-style seamless floral, blue & white, wrapping paper, tileable repeat", None),
        ("pt-02", "Art Deco geometric seamless tile, black & gold, ceramic tile, tileable repeat", None),
        ("pt-03", "Abstract ink brushstrokes, generous negative space, beige base, zen silk scarf, seamless tile", None),
        ("pt-04", "Taiwanese majolica tile pattern, red & green, traditional retro, seamless repeat", None),
        ("pt-05", "Deep blue 3D embossed diamond grid, gold trim, luxury leather pattern, tileable", None),
        ("pt-06", "Nordic seamless leaf wallpaper, cream background, forest-green foliage, tileable repeat", None),
        ("pt-07", "Coffee bag packaging pattern, hand-drawn beans, brown palette, handcrafted feel, tileable", None),
        ("pt-08", "Cute cartoon animals seamless pattern, pastel palette, kids bedding repeat", None),
        ("pt-09", "Tropical foliage with flamingos, jewel-green palette, summer scarf, seamless tileable", None),
        ("pt-10", "Van Gogh-style brushstrokes, starry blue & lemon yellow, art fabric, seamless tile", None),
    ],
    "claymation": [
        ("cl-01", "Claymation-style chubby kitten, big round eyes, studio lit, soft shadows", None),
        ("cl-02", "Claymation boy with red rain boots and umbrella, street scene", None),
        ("cl-03", "Claymation cheeseburger with all ingredients popping out, ad-style", None),
        ("cl-04", "Claymation city skyline overhead, afternoon sun, tiny vehicles", None),
        ("cl-05", "Claymation Santa handing a gift, red Christmas background", None),
        ("cl-06", "Claymation robot, bright blue paint, battle pose", None),
        ("cl-07", "Claymation coffee mug with heart-shaped steam", None),
        ("cl-08", "Claymation village train station, miniature passengers boarding", None),
        ("cl-09", "Claymation fairy holding wand, stardust particles swirling", None),
        ("cl-10", "Claymation corgi wagging tail, tongue out, sunny grass background", None),
    ],
    "product-scene-classic": [
        ("ps-01", "Place the product on pure white studio backdrop, soft light, centered, gentle shadow.", PRODUCT_INPUTS[0]),
        ("ps-02", "Place the product on moss-covered stones and ferns, natural light, outdoor feel.", PRODUCT_INPUTS[1]),
        ("ps-03", "Place the product on a black marble surface with a gold candleholder beside it, luxe dinner ambience.", PRODUCT_INPUTS[2]),
        ("ps-04", "Place the product on beige seamless paper with a single green sprig beside it, minimal Nordic look.", PRODUCT_INPUTS[3]),
        ("ps-05", "Place the product on a wooden bar counter with a coffee mug and notebook props, warm café atmosphere.", PRODUCT_INPUTS[4]),
        ("ps-06", "Place the product on white sand with shells, turquoise sea background, summer holiday feel.", PRODUCT_INPUTS[5]),
        ("ps-07", "Place the product on rough concrete backdrop with metallic reflections, industrial vibe.", PRODUCT_INPUTS[6]),
        ("ps-08", "Place the product on a deep blue backdrop with pink and purple neon side lighting, futuristic feel.", PRODUCT_INPUTS[7]),
        ("ps-09", "Place the product on aged wood table with linen mat and dried flowers, rustic handcrafted look.", PRODUCT_INPUTS[0]),
        ("ps-10", "Place the product in an English garden with roses and butterflies, soft light, romantic spring feel.", PRODUCT_INPUTS[1]),
    ],
    "room-redesign": [
        ("rr-01", "Redesign this room in Scandinavian style: light wood floor, off-white sofa, dusty-blue cushions, natural light.", ROOM_INPUT),
        ("rr-02", "Redesign in Japandi style: tatami, low wood table, paper lantern, beige palette.", ROOM_INPUT),
        ("rr-03", "Redesign in industrial loft style: exposed brick, black steel framing, leather sofa, Edison bulbs.", ROOM_INPUT),
        ("rr-04", "Redesign in mid-century modern style: walnut wood, mustard velvet sofa, geometric rug.", ROOM_INPUT),
        ("rr-05", "Redesign in bohemian style: woven tapestry, Turkish rugs, layered textiles, warm candlelight.", ROOM_INPUT),
        ("rr-06", "Redesign in minimal modern style: white walls, grey sofa, clean lines, negative space and light.", ROOM_INPUT),
        ("rr-07", "Redesign in American farmhouse style: weathered beams, white kitchen, woven baskets, warm rustic feel.", ROOM_INPUT),
        ("rr-08", "Redesign in Art Deco style: dark green velvet headboard, brass sconces, geometric mirror.", ROOM_INPUT),
        ("rr-09", "Redesign in tropical resort style: rattan furniture, palm-leaf plants, ocean-blue palette.", ROOM_INPUT),
        ("rr-10", "Redesign as a café storefront: neon signage, wood counter, industrial pendants, hipster vibe.", ROOM_INPUT),
    ],
}

# ─── Dispatchers ────────────────────────────────────────────────────────────

async def _t2i_flux(prov: PiAPIProvider, prompt: str, _input: Optional[str]) -> Dict[str, Any]:
    return await prov.text_to_image({"prompt": prompt, "size": "1024*1024", "model": "flux"})


async def _t2i_seedream(prov: PiAPIProvider, prompt: str, _input: Optional[str]) -> Dict[str, Any]:
    # Claymation uses Seedream in production.
    return await prov.text_to_image({
        "prompt": f"claymation stop-motion clay style: {prompt}",
        "model": "seedream",
        "aspect_ratio": "1:1",
        "size": "1K",
    })


async def _kontext_i2i(prov: PiAPIProvider, prompt: str, input_url: Optional[str]) -> Dict[str, Any]:
    if not input_url:
        raise ValueError("kontext_i2i requires input_url")
    return await prov.kontext_image({
        "image_url": input_url,
        "prompt": prompt,
        "width": 1024,
        "height": 1024,
    })


DISPATCH: Dict[str, Callable] = {
    "midjourney-imagine":    _t2i_flux,
    "pattern-generate":      _t2i_flux,
    "claymation":            _t2i_seedream,
    "product-scene-classic": _kontext_i2i,
    "room-redesign":         _kontext_i2i,
}

# ─── Driver ─────────────────────────────────────────────────────────────────

async def _download(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


async def generate_one(prov: PiAPIProvider, tool: str, ex_id: str, prompt: str, input_url: Optional[str]) -> Optional[str]:
    """Run one generation, return the stable public GCS URL or None on failure."""
    print(f"  ▶ {tool}:{ex_id}  prompt={prompt[:60]!r}")
    t0 = time.time()
    try:
        result = await DISPATCH[tool](prov, prompt, input_url)
    except Exception as e:
        print(f"  ✗ {ex_id}: provider error: {e}")
        return None
    if not result or not result.get("success"):
        print(f"  ✗ {ex_id}: provider returned not success: {result}")
        return None
    out = result.get("output") or {}
    url = out.get("image_url") or (out.get("images") or [None])[0]
    if not url:
        print(f"  ✗ {ex_id}: no image_url in output: {out}")
        return None

    try:
        data = await _download(url)
    except Exception as e:
        print(f"  ✗ {ex_id}: download failed: {e}")
        return None

    gcs = get_gcs_storage()
    if not gcs.enabled:
        print(f"  ✗ {ex_id}: GCS not configured")
        return None

    blob_name = f"static/examples/{tool}/{ex_id}.jpg"
    try:
        public_url = gcs.upload_public(data, blob_name, content_type="image/jpeg")
    except Exception as e:
        print(f"  ✗ {ex_id}: GCS upload failed: {e}")
        return None

    print(f"  ✓ {ex_id}  ({(time.time() - t0):.1f}s)  -> {public_url}")
    return public_url


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool", action="append", required=True,
                        help="Repeatable. Use a tool key from PROMPTS or 'all'.")
    parser.add_argument("--smoke", action="store_true",
                        help="Generate only the first prompt per tool and exit.")
    parser.add_argument("--out", default=str(REPO_ROOT / "backend" / "scripts" / "examples_manifest.json"),
                        help="Where to write the {tool: {example_id: url}} manifest.")
    args = parser.parse_args()

    tools = list(PROMPTS.keys()) if "all" in args.tool else args.tool
    bad = [t for t in tools if t not in PROMPTS]
    if bad:
        print(f"Unknown tool(s): {bad}")
        sys.exit(2)

    prov = PiAPIProvider()
    manifest: Dict[str, Dict[str, str]] = {}

    out_path = Path(args.out)
    if out_path.exists():
        try:
            manifest = json.loads(out_path.read_text())
            print(f"Loaded existing manifest with {sum(len(v) for v in manifest.values())} entries.")
        except Exception:
            manifest = {}

    for tool in tools:
        manifest.setdefault(tool, {})
        prompts = PROMPTS[tool][:1] if args.smoke else PROMPTS[tool]
        print(f"\n=== {tool} ({len(prompts)} prompts) ===")
        for ex_id, prompt, input_url in prompts:
            if ex_id in manifest[tool] and not args.smoke:
                print(f"  ~ {ex_id}: already in manifest, skipping")
                continue
            url = await generate_one(prov, tool, ex_id, prompt, input_url)
            if url:
                manifest[tool][ex_id] = url
                out_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    print(f"\nManifest written to {out_path}")
    total = sum(len(v) for v in manifest.values())
    print(f"Total assets in manifest: {total}")


if __name__ == "__main__":
    asyncio.run(main())
