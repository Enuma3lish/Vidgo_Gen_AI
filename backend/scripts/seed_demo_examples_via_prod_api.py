"""Seed Material demo examples for the 5 newly-enum'd tool types
(claymation, kling_video, upscale, image_translator, midjourney_imagine)
plus top up the 4 existing tools (background_removal, short_video,
ai_avatar, pattern_generate) that had < 3 examples each.

Why this approach
-----------------
Adding 5 new generator functions to `main_pregenerate.py` would take
~hours and duplicate logic that already exists in our production
`/api/v1/tools/*` endpoints. This script just **calls the live prod
endpoints as the admin account** (admin bypasses credit checks at the
backend, so cost is only the PiAPI/provider spend), takes whatever URL
comes back, and posts it to the **prod** admin seed-demo endpoint so the
Material row lives in the prod DB (NOT this script's local DB).

This means the script can run from anywhere with HTTPS access to prod —
no Cloud SQL tunnel, no VPC, no docker exec required.

Re-runs are idempotent thanks to Material.lookup_hash uniqueness — the
admin endpoint checks the hash and skips inserts if a row already exists.

Cost
----
Worst case: 9 tools × 3 prompts = 27 generations. Per-call provider cost
ranges from $0.005 (background-removal) to $0.50 (ai_avatar / kling
omni). Expected total: ~$5-8 of PiAPI spend.

Usage
-----
    PROD_BACKEND_URL=https://vidgo-backend-r2laip67ma-de.a.run.app \\
        ADMIN_EMAIL=vidgo168@gmail.com ADMIN_PASSWORD=... \\
        python -m scripts.seed_demo_examples_via_prod_api
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("seed_demo_examples")


# ─── Configuration ──────────────────────────────────────────────────────────
PROD = os.getenv("PROD_BACKEND_URL", "http://backend:8000")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "vidgo168@gmail.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
# Optional comma-separated allow-list to limit which tools to seed on a re-run
# (e.g. TOOLS_FILTER=ai_avatar,pattern_generate). Avoids re-generating expensive
# items whose rows already exist — the per-entry lookup_hash check is done
# AFTER calling the tool endpoint, so unfiltered re-runs waste provider $.
TOOLS_FILTER = {
    s.strip() for s in os.getenv("TOOLS_FILTER", "").split(",") if s.strip()
}

# Reusable image URLs already in our GCS bucket — these are inputs used by
# tools that take an image (upscale, image_translator, etc.). Picked from
# the static/hub assets that we know are publicly readable + non-broken.
HUB = "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/hub"
AVATAR = "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/avatars"
GARMENT = "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/garments"
TRYON_MODEL = "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/models"


# ─── Seed plan per tool ─────────────────────────────────────────────────────
# Each plan entry produces ONE Material row. Designed so the prompts are
# realistic / customer-relevant (not "test test test").
SEED_PLAN: List[Dict[str, Any]] = [
    # ===== claymation (3) =====
    {"tool_type": "claymation", "topic": "product",   "endpoint": "/api/v1/tools/claymation",
     "payload": {"prompt": "a steaming bowl of ramen, claymation style", "mode": "text_to_image"},
     "title_en": "Ramen bowl (clay)", "title_zh": "黏土風拉麵"},
    {"tool_type": "claymation", "topic": "character", "endpoint": "/api/v1/tools/claymation",
     "payload": {"prompt": "an astronaut waving, claymation style", "mode": "text_to_image"},
     "title_en": "Astronaut (clay)",   "title_zh": "黏土風太空人"},
    {"tool_type": "claymation", "topic": "scene",     "endpoint": "/api/v1/tools/claymation",
     "payload": {"prompt": "a tiny wooden cabin in foggy forest at sunset, claymation style", "mode": "text_to_image"},
     "title_en": "Cabin in forest",    "title_zh": "森林小木屋"},

    # ===== kling_video (3) — default tier (60 cr each) =====
    {"tool_type": "kling_video", "topic": "cinematic", "endpoint": "/api/v1/tools/kling-video",
     "payload": {"prompt": "slow cinematic dolly across a candlelit dinner table", "tier": "default", "duration": 5, "aspect_ratio": "16:9"},
     "title_en": "Candlelit dinner",   "title_zh": "燭光晚餐"},
    {"tool_type": "kling_video", "topic": "product_motion", "endpoint": "/api/v1/tools/kling-video",
     "payload": {"prompt": "luxury perfume bottle rotating on a velvet pedestal, soft studio light", "tier": "default", "duration": 5, "aspect_ratio": "1:1"},
     "title_en": "Perfume rotation",   "title_zh": "香水旋轉"},
    {"tool_type": "kling_video", "topic": "atmosphere", "endpoint": "/api/v1/tools/kling-video",
     "payload": {"prompt": "morning mist drifting through a Japanese zen garden", "tier": "default", "duration": 5, "aspect_ratio": "16:9"},
     "title_en": "Zen garden mist",    "title_zh": "禪意晨霧"},

    # ===== upscale (3) — uses our own hub PNGs as inputs =====
    {"tool_type": "upscale", "topic": "product",  "endpoint": "/api/v1/tools/upscale",
     "payload": {"image_url": f"{HUB}/product-photography.png", "scale": 2},
     "title_en": "Product 2x",  "title_zh": "商品圖 2x"},
    {"tool_type": "upscale", "topic": "portrait", "endpoint": "/api/v1/tools/upscale",
     "payload": {"image_url": f"{AVATAR}/female-1.png", "scale": 2},
     "title_en": "Portrait 2x", "title_zh": "人像 2x"},
    {"tool_type": "upscale", "topic": "scenery",  "endpoint": "/api/v1/tools/upscale",
     "payload": {"image_url": f"{HUB}/three-d-illustration.png", "scale": 4},
     "title_en": "Scenery 4x",  "title_zh": "風景 4x"},

    # ===== image_translator (3) =====
    {"tool_type": "image_translator", "topic": "menu", "endpoint": "/api/v1/tools/image-translate",
     "payload": {"image_url": f"{HUB}/text.png", "target_language": "Traditional Chinese"},
     "title_en": "Menu → ZH",   "title_zh": "菜單 → 中"},
    {"tool_type": "image_translator", "topic": "signage", "endpoint": "/api/v1/tools/image-translate",
     "payload": {"image_url": f"{HUB}/text.png", "target_language": "English"},
     "title_en": "Signage → EN", "title_zh": "招牌 → 英"},
    {"tool_type": "image_translator", "topic": "poster", "endpoint": "/api/v1/tools/image-translate",
     "payload": {"image_url": f"{HUB}/text.png", "target_language": "Japanese"},
     "title_en": "Poster → JA",  "title_zh": "海報 → 日"},

    # ===== midjourney_imagine (3) — different models for variety =====
    {"tool_type": "midjourney_imagine", "topic": "logo", "endpoint": "/api/v1/tools/midjourney-imagine",
     "payload": {"prompt": "minimal monogram coffee shop logo, single-color mark", "model": "flux", "aspect_ratio": "1:1"},
     "title_en": "Coffee monogram", "title_zh": "咖啡店單字 logo"},
    {"tool_type": "midjourney_imagine", "topic": "marketing", "endpoint": "/api/v1/tools/midjourney-imagine",
     "payload": {"prompt": "vibrant summer beverage hero shot, ice cubes, splash", "model": "flux", "aspect_ratio": "16:9"},
     "title_en": "Summer beverage", "title_zh": "夏日飲品主視覺"},
    {"tool_type": "midjourney_imagine", "topic": "illustration", "endpoint": "/api/v1/tools/midjourney-imagine",
     "payload": {"prompt": "whimsical animated forest creatures, children's book style", "model": "flux", "aspect_ratio": "4:3"},
     "title_en": "Forest creatures","title_zh": "童趣森林動物"},

    # ===== background_removal (3) — top-up =====
    {"tool_type": "background_removal", "topic": "drinks",   "endpoint": "/api/v1/tools/remove-bg",
     "payload": {"image_url": f"{HUB}/product-photography.png", "output_format": "png"},
     "title_en": "Drink cutout",  "title_zh": "飲料去背"},
    {"tool_type": "background_removal", "topic": "snacks",   "endpoint": "/api/v1/tools/remove-bg",
     "payload": {"image_url": f"{HUB}/recolor.png", "output_format": "png"},
     "title_en": "Snack cutout",  "title_zh": "零食去背"},
    {"tool_type": "background_removal", "topic": "packaging","endpoint": "/api/v1/tools/remove-bg",
     "payload": {"image_url": f"{HUB}/product-packaging.png", "output_format": "white"},
     "title_en": "Packaging on white", "title_zh": "包裝白底"},

    # ===== short_video (3) =====
    {"tool_type": "short_video", "topic": "product_showcase", "endpoint": "/api/v1/tools/short-video",
     "payload": {"image_url": f"{HUB}/product-photography.png", "prompt": "slow product rotation, golden-hour light", "model_id": "seedance", "duration": 5},
     "title_en": "Product rotation", "title_zh": "商品旋轉"},
    {"tool_type": "short_video", "topic": "brand_intro", "endpoint": "/api/v1/tools/short-video",
     "payload": {"image_url": f"{HUB}/instagram-story.png", "prompt": "cinematic zoom-in with subtle parallax", "model_id": "seedance", "duration": 5},
     "title_en": "Brand zoom-in", "title_zh": "品牌推近"},
    {"tool_type": "short_video", "topic": "tutorial", "endpoint": "/api/v1/tools/short-video",
     "payload": {"image_url": f"{HUB}/edit-with-ai.png", "prompt": "left-to-right pan revealing details", "model_id": "seedance", "duration": 5},
     "title_en": "Detail pan", "title_zh": "細節橫搖"},

    # ===== ai_avatar (3) — short scripts to keep TTS fast =====
    {"tool_type": "ai_avatar", "topic": "spokesperson", "endpoint": "/api/v1/tools/avatar",
     "payload": {"image_url": f"{AVATAR}/female-1.png", "script": "Welcome to our store! Today's special is twenty percent off.", "language": "en"},
     "title_en": "Welcome spokesperson", "title_zh": "歡迎代言"},
    {"tool_type": "ai_avatar", "topic": "product_intro", "endpoint": "/api/v1/tools/avatar",
     "payload": {"image_url": f"{AVATAR}/male-1.png", "script": "Let me introduce our brand new product, made for everyday comfort.", "language": "en"},
     "title_en": "Product intro", "title_zh": "產品介紹"},
    {"tool_type": "ai_avatar", "topic": "customer_service", "endpoint": "/api/v1/tools/avatar",
     "payload": {"image_url": f"{AVATAR}/female-2.png", "script": "How may I help you today? Please describe your concern.", "language": "en"},
     "title_en": "Customer service", "title_zh": "客服助理"},

    # ===== pattern_generate (3) — different router /generate/pattern/generate =====
    {"tool_type": "pattern_generate", "topic": "seamless", "endpoint": "/api/v1/generate/pattern/generate",
     "payload": {"prompt": "elegant gold-line botanical leaves on cream background", "style": "seamless", "width": 1024, "height": 1024},
     "title_en": "Botanical seamless",  "title_zh": "植物無縫圖"},
    {"tool_type": "pattern_generate", "topic": "geometric", "endpoint": "/api/v1/generate/pattern/generate",
     "payload": {"prompt": "art deco gold and navy geometric tiles", "style": "geometric", "width": 1024, "height": 1024},
     "title_en": "Art deco tiles",      "title_zh": "裝飾藝術幾何"},
    {"tool_type": "pattern_generate", "topic": "floral", "endpoint": "/api/v1/generate/pattern/generate",
     "payload": {"prompt": "watercolor cherry blossoms on light pink background", "style": "floral", "width": 1024, "height": 1024},
     "title_en": "Cherry blossoms",     "title_zh": "水彩櫻花"},
]


# ─── Helpers ────────────────────────────────────────────────────────────────

def _hash(tool_type: str, prompt: str, input_image_url: Optional[str] = None) -> str:
    """Same shape Material uses elsewhere — keep collisions across re-runs."""
    parts = [tool_type, prompt or "", "", input_image_url or ""]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


async def _login(client: httpx.AsyncClient) -> str:
    r = await client.post(
        f"{PROD}/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["tokens"]["access"]


async def _call_tool(client: httpx.AsyncClient, token: str, endpoint: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Call a production /tools/* endpoint. Returns the JSON response or None on error."""
    try:
        r = await client.post(
            f"{PROD}{endpoint}",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=600,  # avatar / kling can take 5+ min
        )
        if r.status_code != 200:
            logger.warning(f"  HTTP {r.status_code} for {endpoint}: {r.text[:200]}")
            return None
        body = r.text.strip()
        if not body:
            logger.warning(f"  Empty body from {endpoint}")
            return None
        return json.loads(body)
    except Exception as e:
        logger.warning(f"  Call failed for {endpoint}: {e}")
        return None


async def _insert_via_admin(
    client: httpx.AsyncClient,
    token: str,
    plan: Dict[str, Any],
    result_url: str,
    output_kind: str,
) -> Optional[bool]:
    """Post the generated example to the prod admin endpoint for insertion.
    Returns True if newly inserted, False if already existed (idempotent skip),
    or None on error."""
    prompt_text = plan["payload"].get("prompt") or plan.get("title_en", "")
    image_in = plan["payload"].get("image_url")
    h = _hash(plan["tool_type"], prompt_text, image_in)

    body = {
        "tool_type": plan["tool_type"],
        "topic": plan["topic"],
        "topic_zh": None,
        "prompt": prompt_text,
        "prompt_zh": plan.get("title_zh") or prompt_text,
        "input_image_url": image_in,
        "input_params": plan["payload"],
        "result_image_url": result_url if output_kind == "image" else None,
        "result_video_url": result_url if output_kind == "video" else None,
        "title_en": plan.get("title_en"),
        "title_zh": plan.get("title_zh"),
        "lookup_hash": h,
    }
    try:
        r = await client.post(
            f"{PROD}/api/v1/admin/materials/seed-demo",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
            timeout=30,
        )
        if r.status_code != 200:
            logger.warning(f"  admin/seed-demo HTTP {r.status_code}: {r.text[:200]}")
            return None
        return bool(r.json().get("inserted"))
    except Exception as e:
        logger.warning(f"  admin/seed-demo call failed: {e}")
        return None


async def main() -> None:
    if not ADMIN_PASSWORD:
        logger.error("ADMIN_PASSWORD env not set; aborting.")
        sys.exit(1)

    plan_to_run = SEED_PLAN
    if TOOLS_FILTER:
        plan_to_run = [p for p in SEED_PLAN if p["tool_type"] in TOOLS_FILTER]
        logger.info(f"TOOLS_FILTER applied — running only: {sorted(TOOLS_FILTER)}")

    logger.info(f"Seeding {len(plan_to_run)} demo examples against {PROD} as {ADMIN_EMAIL}")
    inserted = 0
    failed = 0
    skipped = 0

    async with httpx.AsyncClient() as client:
        token = await _login(client)
        logger.info(f"Logged in OK; running seed plan…")

        for plan in plan_to_run:
            label = f"{plan['tool_type']}/{plan['topic']}"
            logger.info(f"→ {label}")
            result = await _call_tool(client, token, plan["endpoint"], plan["payload"])
            if not result or not result.get("success"):
                msg = (result or {}).get("message", "(no body)")
                logger.warning(f"  ✗ generation failed: {msg[:120]}")
                failed += 1
                continue

            url = (
                result.get("video_url")
                or result.get("image_url")
                or result.get("result_url")
            )
            if not url:
                logger.warning(f"  ✗ provider returned success but no URL — keys={list(result.keys())}")
                failed += 1
                continue

            output_kind = "video" if (result.get("video_url") or ".mp4" in url) else "image"
            ins = await _insert_via_admin(client, token, plan, url, output_kind)
            if ins is True:
                inserted += 1
                logger.info(f"  ✓ inserted ({output_kind}) — {url[:80]}")
            elif ins is False:
                skipped += 1
                logger.info(f"  · skip (lookup_hash exists)")
            else:
                failed += 1

    logger.info("=" * 60)
    logger.info(f"Done. inserted={inserted}  skipped={skipped}  failed={failed}")


if __name__ == "__main__":
    asyncio.run(main())
