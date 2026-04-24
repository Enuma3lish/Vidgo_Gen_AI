#!/usr/bin/env python3
"""
Input-Only Pregeneration
========================

Pregenerates ONLY the input assets the visitor picks from — not finished
examples. The runtime flow (DemoCacheService.get_or_generate) handles the
effect-application step on cache miss by calling the real provider API for
the chosen (input, effect) pair and persisting the result.

Assets:
  - Image inputs via Vertex AI Imagen (T2I)
  - Video inputs via Vertex AI Veo (T2V)

Storage:
  - Uploaded to GCS under `inputs/{tool_type}/{topic}/{uuid}.(png|mp4)`
  - Indexed as Material rows with:
      source           = SEED
      status           = APPROVED
      input_image_url  OR input_video_url  (the asset)
      result_*_url     = NULL  (deliberately — this is not a finished example)
      input_params     = {"is_input_library": true, "topic": ...}

Runtime contract:
  - The frontend lists these rows as pickable inputs (via
    /api/v1/demo/inputs/{tool_type}).
  - When the user picks one + an effect_prompt, the existing cache-through
    flow in DemoCacheService builds lookup_hash(tool, effect, input_url)
    and either serves a cached result or generates a fresh one via the
    real provider API and persists it under the same hash.

Usage:
    python -m scripts.pregenerate_inputs --tool background_removal --count 2
    python -m scripts.pregenerate_inputs --all
    python -m scripts.pregenerate_inputs --all --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import os
import sys
import uuid
from typing import Dict, List, Optional, Tuple

# Make `app` importable when running from the backend/ directory or /app.
for candidate in ("/app", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))):
    if candidate and candidate not in sys.path:
        sys.path.insert(0, candidate)

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.material import Material, ToolType, MaterialSource, MaterialStatus
from app.providers.vertex_ai_provider import VertexAIProvider
from app.services.gcs_storage_service import get_gcs_storage

# Pacing between consecutive Vertex calls (Imagen/Veo) to avoid the
# per-minute online_prediction_requests_per_base_model burst quota. A small
# async sleep is cheaper than adding full retry/backoff at every call site,
# and the pregen script is throughput-insensitive.
PACING_SECONDS = float(os.getenv("VERTEX_PACING_SECONDS", "2.5"))

# Retry budget for transient 429s from Imagen/Veo. Most projects clear the
# per-minute quota within ~60s.
MAX_RETRIES = int(os.getenv("VERTEX_MAX_RETRIES", "3"))
RETRY_BACKOFF_SECONDS = float(os.getenv("VERTEX_RETRY_BACKOFF_SECONDS", "30"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pregenerate_inputs")

# -----------------------------------------------------------------------------
# INPUT PROMPT CATALOG
# -----------------------------------------------------------------------------
# Each entry describes what the pregenerated input should LOOK like so the
# visitor has a meaningful library to pick from. Prompts are intentionally
# generic (no branded terms) and mention the subject clearly so the T2I model
# produces recognizable inputs.

IMAGE_INPUT_PROMPTS: Dict[str, Dict[str, List[str]]] = {
    "background_removal": {
        "drinks": [
            "A cup of bubble milk tea with tapioca pearls, glossy studio lighting, on a plain surface, product photography",
            "A tall iced coffee in a clear plastic cup with ice cubes and straw, clean plain background",
        ],
        "snacks": [
            "Crispy fried chicken cutlet on a paper wrapper, isolated on a plain backdrop",
            "A basket of golden french fries, isolated on a plain background",
        ],
        "desserts": [
            "Mango shaved ice with colorful toppings, isolated on a plain backdrop",
            "A slice of strawberry shortcake on a white plate, isolated on a plain backdrop",
        ],
        "packaging": [
            "An eco-friendly drink cup with paper straw and a plain sleeve, isolated product shot",
            "A kraft paper takeaway bag with handles, isolated product shot",
        ],
    },
    "product_scene": {
        "bubble_tea": [
            "A cup of bubble milk tea with tapioca pearls, clean studio backdrop, product-only photo",
            "A tall iced bubble tea cup with straw, plain backdrop, product-only photo",
        ],
        "canvas_tote": [
            "A plain canvas tote bag, folded handles, isolated product shot",
            "A natural-color cotton canvas tote bag with minimal stitching, isolated product shot",
        ],
        "skincare": [
            "A minimalist amber glass serum bottle with a dropper cap, isolated product shot",
            "A ceramic skincare jar with wooden lid, isolated product shot",
        ],
        "coffee_beans": [
            "A resealable kraft paper bag of whole roasted coffee beans with a small front label, isolated product shot",
            "A tin of ground coffee with a minimal label, isolated product shot",
        ],
    },
    "room_redesign": {
        "living_room": [
            "Empty modern living room with neutral walls, soft natural daylight through a large window, wide-angle real estate photo, no people",
            "Empty apartment living room with bare walls and wooden floor, window light, wide-angle interior photo, no people",
        ],
        "bedroom": [
            "Empty small bedroom with off-white walls and wooden flooring, soft daylight, wide-angle interior photo, no people",
            "Empty bedroom with bay window and neutral paint, wide-angle real estate photo, no people",
        ],
        "kitchen": [
            "Empty small apartment kitchen with bare countertops and neutral cabinets, window light, wide-angle real estate photo, no people",
            "Empty galley kitchen with tile flooring and blank walls, wide-angle interior photo, no people",
        ],
        "bathroom": [
            "Empty compact bathroom with basic white tile and a single window, wide-angle real estate photo, no people",
            "Empty bathroom with a pedestal sink and plain walls, wide-angle interior photo, no people",
        ],
    },
    "try_on": {
        "tshirt": [
            "A plain white crew-neck t-shirt, flat lay on a clean backdrop, e-commerce catalog photo",
            "A solid black crew-neck t-shirt, flat lay on a clean backdrop, e-commerce catalog photo",
        ],
        "dress": [
            "A simple floral midi dress on a hanger, clean backdrop, e-commerce catalog photo",
            "A solid pastel midi dress on a hanger, clean backdrop, e-commerce catalog photo",
        ],
        "jacket": [
            "A classic denim jacket, flat lay on a clean backdrop, e-commerce catalog photo",
            "A black bomber jacket, flat lay on a clean backdrop, e-commerce catalog photo",
        ],
    },
    "ai_avatar": {
        # Head-and-shoulders portraits that pass face-detector requirements.
        # Must be photo-real, front-facing, neutral expression, shoulders visible.
        "portrait_female": [
            "Photorealistic head-and-shoulders portrait of an Asian woman, front-facing, neutral expression, natural lighting, plain neutral backdrop, modern professional attire, shoulders visible, no props",
            "Photorealistic head-and-shoulders portrait of an East Asian woman in her 30s, smiling softly, plain backdrop, studio lighting",
        ],
        "portrait_male": [
            "Photorealistic head-and-shoulders portrait of an Asian man, front-facing, neutral expression, plain backdrop, professional attire, shoulders visible, no props",
            "Photorealistic head-and-shoulders portrait of an East Asian man in his 30s, light smile, plain backdrop, studio lighting",
        ],
    },
    "effect": {
        # Sources intentionally plain so a downstream style transfer has room
        # to change the aesthetic without fighting competing styles.
        "product_photos": [
            "A ceramic mug on a plain backdrop, product-only photography, soft neutral light",
            "A pair of white sneakers on a plain backdrop, product-only photography, soft neutral light",
            "A small potted succulent on a plain backdrop, soft neutral light",
        ],
    },
    "pattern_generate": {
        # Pattern tool is T2I-only at runtime, so we do NOT need inputs.
        # Intentionally empty — list() will skip it.
    },
}


# Video input catalog — consumed by Veo T2V.
VIDEO_INPUT_PROMPTS: Dict[str, Dict[str, List[str]]] = {
    "short_video": {
        "product_showcase": [
            "Cinematic slow orbit around a steaming cup of coffee on a wooden table, soft warm window light, gentle dust particles in air, 4K commercial",
            "Cinematic close-up of a bottle of juice with condensation droplets, slow camera push-in, studio backdrop, 4K commercial",
        ],
        "brand_intro": [
            "Cozy drink-shop interior at golden hour, camera slowly glides past the counter, warm pendant lighting, welcoming atmosphere, 4K cinematic",
        ],
    },
}


# -----------------------------------------------------------------------------
# STORAGE HELPERS
# -----------------------------------------------------------------------------

def _lookup_hash_for_input(tool_type: str, topic: str, prompt: str) -> str:
    """
    Content-addressed hash so re-running the script is idempotent: if the
    same (tool, topic, prompt) was already generated, we skip it.

    This is distinct from the runtime cache hash (which is keyed on effect
    and input_url). Kept under `input_params.input_hash` so lookup never
    collides with the runtime request-identity hash.
    """
    content = f"input|{tool_type}|{topic}|{prompt}"
    return hashlib.sha256(content.encode()).hexdigest()[:64]


async def _existing_input(db, tool_type: str, input_hash: str) -> Optional[Material]:
    """Return an existing input-library row for this (tool, input_hash), if any."""
    result = await db.execute(
        select(Material).where(
            Material.tool_type == tool_type,
            Material.input_params["input_hash"].astext == input_hash,
            Material.is_active == True,
        )
    )
    return result.scalars().first()


async def _store_input_material(
    db,
    *,
    tool_type: str,
    topic: str,
    prompt: str,
    input_hash: str,
    input_image_url: Optional[str] = None,
    input_video_url: Optional[str] = None,
    extra_params: Optional[Dict] = None,
) -> Material:
    """
    Persist a Material row for a pregenerated INPUT (no result).

    Convention: input-only rows have null result_*_url and carry
    `input_params.is_input_library = true` so the frontend input-list
    endpoint can filter them.
    """
    params = {
        "is_input_library": True,
        "input_hash": input_hash,
        "source_model": "vertex_ai",
        "input_prompt": prompt,
        **(extra_params or {}),
    }

    material = Material(
        tool_type=tool_type,
        topic=topic,
        prompt=prompt,
        input_image_url=input_image_url,
        input_video_url=input_video_url,
        result_image_url=None,
        result_video_url=None,
        result_watermarked_url=None,
        input_params=params,
        source=MaterialSource.SEED,
        status=MaterialStatus.APPROVED,
        is_active=True,
        quality_score=0.85,
        is_featured=False,
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)
    return material


# -----------------------------------------------------------------------------
# GENERATION
# -----------------------------------------------------------------------------

async def _fetch_image_bytes(url: str) -> bytes:
    """Pull a remote image so we can re-upload it to our own GCS bucket."""
    import httpx
    if url.startswith("/"):
        # Local path (when VertexAIProvider.text_to_image writes to /app/static/generated)
        from pathlib import Path
        return Path("/app" + url).read_bytes()
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as http:
        resp = await http.get(url)
        resp.raise_for_status()
        return resp.content


async def _fetch_video_bytes(url: str) -> bytes:
    return await _fetch_image_bytes(url)


def _is_quota_error(result: Dict) -> bool:
    err = str(result.get("error") or "")
    return "429" in err or "RESOURCE_EXHAUSTED" in err or "Quota exceeded" in err


async def _call_with_retry(label: str, fn, *args, **kwargs):
    """Run a Vertex call with a cheap retry on 429 quota errors."""
    for attempt in range(1, MAX_RETRIES + 1):
        result = await fn(*args, **kwargs)
        if result.get("success") or not _is_quota_error(result):
            return result
        if attempt >= MAX_RETRIES:
            logger.warning(f"[input] {label}: quota still exhausted after {attempt} attempts")
            return result
        wait = RETRY_BACKOFF_SECONDS * attempt
        logger.info(f"[input] {label}: quota hit, sleeping {wait:.0f}s before retry {attempt + 1}")
        await asyncio.sleep(wait)
    return result


async def _generate_image_input(
    vertex: VertexAIProvider,
    *,
    tool_type: str,
    topic: str,
    prompt: str,
    aspect_ratio: str = "1:1",
    dry_run: bool = False,
) -> Optional[Tuple[str, str]]:
    """
    T2I via Vertex AI (Imagen) → upload to GCS → return (public_url, blob_name).

    For ai_avatar portraits we use 3:4 aspect ratio so Kling's face detector
    has a meaningful head crop.
    """
    logger.info(f"[input] T2I tool={tool_type} topic={topic} ar={aspect_ratio}")
    if dry_run:
        return ("https://example.invalid/dry-run.png", "dry-run")

    result = await _call_with_retry(
        f"T2I {tool_type}/{topic}",
        vertex.text_to_image,
        {"prompt": prompt, "aspect_ratio": aspect_ratio},
    )
    if not result.get("success"):
        logger.warning(f"[input] T2I failed: {result.get('error')}")
        return None

    source_url = result.get("output", {}).get("image_url")
    if not source_url:
        return None

    # Re-host on our own bucket so the Material row never points to a
    # temporary provider CDN URL or ephemeral Cloud Run filesystem.
    try:
        img_bytes = await _fetch_image_bytes(source_url)
    except Exception as e:
        logger.warning(f"[input] fetch failed: {e}")
        return None

    gcs = get_gcs_storage()
    if not gcs.enabled:
        logger.warning("[input] GCS not configured — cannot persist input library")
        return None

    blob_name = f"inputs/{tool_type}/{topic}/{uuid.uuid4().hex[:12]}.png"
    public_url = gcs.upload_public(img_bytes, blob_name, content_type="image/png")
    return (public_url, blob_name)


async def _generate_video_input(
    vertex: VertexAIProvider,
    *,
    tool_type: str,
    topic: str,
    prompt: str,
    duration: int = 6,
    aspect_ratio: str = "16:9",
    dry_run: bool = False,
) -> Optional[Tuple[str, str]]:
    """T2V via Vertex AI (Veo) → upload to GCS → return (public_url, blob_name)."""
    logger.info(f"[input] T2V tool={tool_type} topic={topic} dur={duration}s")
    if dry_run:
        return ("https://example.invalid/dry-run.mp4", "dry-run")

    result = await _call_with_retry(
        f"T2V {tool_type}/{topic}",
        vertex.text_to_video,
        {"prompt": prompt, "duration": duration, "aspect_ratio": aspect_ratio},
    )
    if not result.get("success"):
        logger.warning(f"[input] T2V failed: {result.get('error')}")
        return None

    source_url = result.get("output", {}).get("video_url")
    if not source_url:
        return None

    try:
        vid_bytes = await _fetch_video_bytes(source_url)
    except Exception as e:
        logger.warning(f"[input] fetch video failed: {e}")
        return None

    gcs = get_gcs_storage()
    if not gcs.enabled:
        logger.warning("[input] GCS not configured — cannot persist input library")
        return None

    blob_name = f"inputs/{tool_type}/{topic}/{uuid.uuid4().hex[:12]}.mp4"
    public_url = gcs.upload_public(vid_bytes, blob_name, content_type="video/mp4")
    return (public_url, blob_name)


# -----------------------------------------------------------------------------
# PER-TOOL DRIVERS
# -----------------------------------------------------------------------------

async def _run_image_tool(
    vertex: VertexAIProvider,
    tool_type: str,
    per_topic_count: int,
    dry_run: bool,
) -> Tuple[int, int]:
    """
    Generate up to `per_topic_count` image inputs for each topic of an image tool.

    Returns (created, skipped).
    """
    topics = IMAGE_INPUT_PROMPTS.get(tool_type, {})
    if not topics:
        logger.info(f"[{tool_type}] no image input prompts configured — skipping")
        return (0, 0)

    aspect_ratio = "3:4" if tool_type == "ai_avatar" else "1:1"
    created = skipped = 0

    async with AsyncSessionLocal() as db:
        for topic, prompts in topics.items():
            for prompt in prompts[:per_topic_count]:
                input_hash = _lookup_hash_for_input(tool_type, topic, prompt)
                existing = await _existing_input(db, tool_type, input_hash)
                if existing:
                    logger.info(f"[{tool_type}/{topic}] skip (exists): {prompt[:60]}…")
                    skipped += 1
                    continue

                gen = await _generate_image_input(
                    vertex,
                    tool_type=tool_type,
                    topic=topic,
                    prompt=prompt,
                    aspect_ratio=aspect_ratio,
                    dry_run=dry_run,
                )
                if not gen:
                    # Pace between attempts even on failure so we don't thrash
                    # the per-minute quota trying the next prompt immediately.
                    if not dry_run:
                        await asyncio.sleep(PACING_SECONDS)
                    continue
                public_url, _ = gen

                if dry_run:
                    logger.info(f"[{tool_type}/{topic}] (dry) would store: {public_url}")
                    created += 1
                    continue

                await _store_input_material(
                    db,
                    tool_type=tool_type,
                    topic=topic,
                    prompt=prompt,
                    input_hash=input_hash,
                    input_image_url=public_url,
                    extra_params={"aspect_ratio": aspect_ratio},
                )
                created += 1
                # Space successful calls too so the next topic/prompt does not
                # immediately trip the per-minute Imagen quota.
                await asyncio.sleep(PACING_SECONDS)
    return (created, skipped)


async def _run_video_tool(
    vertex: VertexAIProvider,
    tool_type: str,
    per_topic_count: int,
    dry_run: bool,
) -> Tuple[int, int]:
    topics = VIDEO_INPUT_PROMPTS.get(tool_type, {})
    if not topics:
        logger.info(f"[{tool_type}] no video input prompts configured — skipping")
        return (0, 0)

    created = skipped = 0

    async with AsyncSessionLocal() as db:
        for topic, prompts in topics.items():
            for prompt in prompts[:per_topic_count]:
                input_hash = _lookup_hash_for_input(tool_type, topic, prompt)
                existing = await _existing_input(db, tool_type, input_hash)
                if existing:
                    logger.info(f"[{tool_type}/{topic}] skip (exists): {prompt[:60]}…")
                    skipped += 1
                    continue

                gen = await _generate_video_input(
                    vertex,
                    tool_type=tool_type,
                    topic=topic,
                    prompt=prompt,
                    dry_run=dry_run,
                )
                if not gen:
                    if not dry_run:
                        await asyncio.sleep(PACING_SECONDS)
                    continue
                public_url, _ = gen

                if dry_run:
                    logger.info(f"[{tool_type}/{topic}] (dry) would store: {public_url}")
                    created += 1
                    continue

                await _store_input_material(
                    db,
                    tool_type=tool_type,
                    topic=topic,
                    prompt=prompt,
                    input_hash=input_hash,
                    input_video_url=public_url,
                    extra_params={"duration": 6, "aspect_ratio": "16:9"},
                )
                created += 1
                await asyncio.sleep(PACING_SECONDS)
    return (created, skipped)


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

_ALL_TOOLS = [
    "background_removal",
    "product_scene",
    "room_redesign",
    "try_on",
    "ai_avatar",
    "effect",
    "short_video",
]


async def _run(tools: List[str], per_topic_count: int, dry_run: bool) -> None:
    vertex = VertexAIProvider()
    if not vertex.project:
        raise SystemExit("VERTEX_AI_PROJECT is not set — cannot run input pregen.")

    total_created = total_skipped = 0
    for tool_type in tools:
        logger.info(f"=== {tool_type} ===")
        if tool_type in VIDEO_INPUT_PROMPTS:
            created, skipped = await _run_video_tool(vertex, tool_type, per_topic_count, dry_run)
        else:
            created, skipped = await _run_image_tool(vertex, tool_type, per_topic_count, dry_run)
        total_created += created
        total_skipped += skipped
        logger.info(f"[{tool_type}] created={created} skipped={skipped}")

    await vertex.close()
    logger.info(f"DONE — created={total_created} skipped={total_skipped}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pregenerate INPUT library via Vertex AI")
    parser.add_argument("--tool", choices=_ALL_TOOLS, help="Specific tool to pregenerate inputs for")
    parser.add_argument("--all", action="store_true", help="Pregenerate inputs for all supported tools")
    parser.add_argument(
        "--count",
        type=int,
        default=2,
        help="Max inputs per topic per tool (default: 2)",
    )
    parser.add_argument("--dry-run", action="store_true", help="List planned work, skip generation")
    args = parser.parse_args()

    if not args.tool and not args.all:
        parser.error("pass --tool <name> or --all")

    tools = _ALL_TOOLS if args.all else [args.tool]
    asyncio.run(_run(tools, args.count, args.dry_run))


if __name__ == "__main__":
    main()
