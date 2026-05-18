"""
Generate VidGo brand assets via PiAPI (Flux T2I).

Two asset sets are supported, both tuned to match the VidGo site topic
(fashion / product e-commerce / interior / branding):

  1. hub       — 17 tool-hub tile thumbnails (Recolor, Virtual Model,
                 Ghost Mannequin, Product Staging, …). Square / 4:3
                 friendly, small composition, clean studio look.

  2. models    — Full-body fashion-e-commerce model references for the
                 Virtual Try-On grid (Avery, Sam, Taylor, Kendall, …).
                 Portrait 2:3, neutral background, consistent lighting
                 so they read as a single curated set.

Each generated asset is:
  - downloaded to the local frontend-vue public folder so vite serves it
    at /static_assets/...
  - optionally uploaded to GCS at static/... (same path layout the rest
    of the site uses)
  - upserted into the `materials` table via raw SQL so the asset is
    discoverable from the admin / inputLibrary endpoints

This script is *self-contained*: it does NOT import from `app.*`. That
makes it survivable when the wider project venv is broken (e.g. a
transitive build failure on llvmlite blocks `uv sync`). Recommended
invocation uses `uv run --no-project --with …` to skip project sync.

Usage:
    # Preview (no API calls, no DB writes)
    uv run --no-project --with httpx --with python-dotenv \\
        python backend/scripts/generate_brand_assets.py \\
        --set all --dry-run

    # Real run — local + DB (no GCS)
    uv run --no-project --with httpx --with python-dotenv --with asyncpg \\
        python backend/scripts/generate_brand_assets.py --set all

    # Full run — local + GCS + DB
    uv run --no-project --with httpx --with python-dotenv --with asyncpg \\
        --with google-cloud-storage \\
        python backend/scripts/generate_brand_assets.py --set all --gcs

Required env vars (read from backend/.env automatically):
    PIAPI_KEY            PiAPI API key (Flux T2I)
    DATABASE_URL         Postgres URL (unless --no-db)
    GCS_BUCKET           Only required when --gcs is set
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_ENV = REPO_ROOT / "backend" / ".env"

# Load env from backend/.env *before* anything else reads os.getenv.
try:
    from dotenv import load_dotenv  # type: ignore

    if _BACKEND_ENV.exists():
        load_dotenv(_BACKEND_ENV, override=False)
except ImportError:
    # dotenv only matters for non-dry-run paths; let argparse handle the
    # rest, the user will get a clear error if PIAPI_KEY is missing.
    pass

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("brand_assets")

FRONTEND_PUBLIC = REPO_ROOT / "frontend-vue" / "public" / "static_assets"
HUB_LOCAL_DIR = FRONTEND_PUBLIC / "hub"
MODELS_LOCAL_DIR = FRONTEND_PUBLIC / "tryon" / "models"
DEMOS_LOCAL_DIR = FRONTEND_PUBLIC / "premium" / "demos"

HUB_GCS_PREFIX = "static/hub"
MODELS_GCS_PREFIX = "static/tryon/models"
DEMOS_GCS_PREFIX = "static/premium/demos"

# Style guidelines applied to every prompt. The site theme calls for
# clean, professional e-commerce visuals — neutral backgrounds, soft
# studio light, no logos / no text / no faces in product shots so the
# tiles read as branded thumbnails rather than stock photos.
HUB_STYLE_SUFFIX = (
    "professional e-commerce hero shot, soft daylight studio lighting, "
    "matte light-grey backdrop, centered composition, shallow depth of "
    "field, ultra clean, no text, no watermark, no logo, photoreal, 8k"
)
HUB_NEGATIVE = "text, watermark, logo, signature, busy background, clutter, low quality, blur"

MODEL_STYLE_SUFFIX = (
    "full-body fashion lookbook portrait, standing relaxed pose facing "
    "camera, plain off-white seamless backdrop, soft top-lighting, "
    "natural skin, sharp focus, neutral expression, fashion catalog "
    "photography, no text, no watermark, no logo, photoreal, 8k"
)
MODEL_NEGATIVE = (
    "text, watermark, logo, multiple people, cropped body, tight crop, "
    "low quality, blur, deformed hands, deformed face, oversaturated"
)

PIAPI_BASE_URL = "https://api.piapi.ai/api/v1"
PIAPI_FLUX_MODEL = os.getenv("PIAPI_FLUX_T2I_MODEL", "Qubico/flux1-schnell")
PIAPI_KLING_MODEL = os.getenv("PIAPI_KLING_VIDEO_MODEL", "kling")
PIAPI_LUMA_MODEL = os.getenv("PIAPI_LUMA_VIDEO_MODEL", "luma")
PIAPI_LUMA_RAY = os.getenv("PIAPI_LUMA_RAY_VERSION", "ray-v2")


# ─────────────────────────────────────────────────────────────────────
# Catalogs
# ─────────────────────────────────────────────────────────────────────


@dataclass
class AssetSpec:
    """One image to generate. Same shape for hub tiles, try-on models, and
    premium-tool demo media. The `kind` field decides which PiAPI task
    type is used (image / kling_video / luma_video)."""

    asset_id: str                # stable id, used as filename
    label: str                   # human-readable
    prompt: str                  # main subject — site-themed
    width: int
    height: int
    topic: str                   # DB `materials.topic`
    extra_params: Dict[str, Any] = field(default_factory=dict)
    kind: str = "image"          # "image" | "kling_video" | "luma_video"
    extension: str = "png"       # "png" | "mp4"


# Per-tile style overrides — used when the default photoreal e-commerce
# suffix would fight the intended look (logo art, neon text, 3D illos).
HUB_STYLE_OVERRIDES: Dict[str, str] = {
    "logo": (
        "graphic design hero shot of a typographic mark, soft studio "
        "lighting, clean isolated composition, no surrounding text or "
        "watermark, 8k"
    ),
    "text": (
        "3D typography hero shot, dramatic studio rim lighting, glossy "
        "render, clean isolated composition, no surrounding watermark, 8k"
    ),
    "three-d-illustration": (
        "stylised pixar-style 3D render, soft cinematic lighting, "
        "pastel background, clean composition, no text, no watermark, 8k"
    ),
    "instagram-story": (
        "social media flat-lay aesthetic, warm natural lighting, beige "
        "and cream tones, clean composition, no extra text or watermark, 8k"
    ),
    "create-any-image": (
        "moodboard-style flat composition with multiple small product "
        "vignettes, soft natural lighting, cream background, clean "
        "layout, no extra text or watermark, 8k"
    ),
}


def hub_catalog() -> List[AssetSpec]:
    """17 thumbnails matching the toolHub.ts tile order."""

    def s(asset_id: str, label: str, subject: str) -> AssetSpec:
        suffix = HUB_STYLE_OVERRIDES.get(asset_id, HUB_STYLE_SUFFIX)
        return AssetSpec(
            asset_id=asset_id,
            label=label,
            prompt=f"{subject}. {suffix}",
            width=1024,
            height=768,
            topic="hub_thumbnail",
            extra_params={"set": "hub", "label": label},
        )

    return [
        s("recolor",
          "Recolor",
          "A single oversized hoodie split visually into two colorways "
          "(left half teal, right half mustard yellow), folded neatly, "
          "showing colour-swap concept for an apparel recolor feature"),
        s("product-beautifier",
          "Product Beautifier",
          "A premium tan leather messenger bag on a soft pastel yellow "
          "background, perfectly lit hero product shot for an e-commerce "
          "listing beautification tool"),
        s("virtual-model",
          "Virtual Model",
          "Friendly fashion model wearing a navy turtleneck, head and "
          "shoulders portrait against neutral grey backdrop, suggesting "
          "an AI virtual model service for apparel brands"),
        s("product-staging",
          "Product Staging",
          "A reusable water bottle held by a hand against a forest-green "
          "blurred outdoor background, lifestyle product staging hero "
          "shot for e-commerce"),
        s("edit-with-ai",
          "Edit with AI",
          "A metallic silver clutch handbag on a soft pink background "
          "with subtle reflection, suggesting AI-powered photo editing "
          "and retouching"),
        s("ghost-mannequin",
          "Ghost Mannequin",
          "An invisible-mannequin style charcoal tracksuit jacket "
          "floating in mid-air on a plain studio backdrop, classic "
          "ghost mannequin apparel photography"),
        s("ironing",
          "Ironing",
          "A perfectly crisp pastel-green t-shirt hanging on a wooden "
          "hanger against a neutral wall, smooth fabric, suggesting an "
          "AI de-wrinkling / ironing tool"),
        s("flat-lay",
          "Flat lay",
          "A flat-lay overhead photo of a folded silver clutch, beige "
          "scarf, and gold earrings on a dusty-pink paper background, "
          "marketing flat-lay composition"),
        s("logo",
          "Logo",
          "Bold typographic 3D 'Logos' wordmark in deep brown serif "
          "letters with subtle gradient, isolated on a pale background, "
          "concept for an AI logo generator"),
        s("text",
          "Text",
          "Glowing neon-red 3D capital letters spelling 'TEXT' on a "
          "deep burgundy backdrop, dramatic studio rim light, concept "
          "for an AI text/typography tool"),
        s("create-any-image",
          "Create any image",
          "Stylised collage of three diverse e-commerce visuals "
          "(jewelry close-up, gift packaging, sneakers flatlay) "
          "arranged like a moodboard on a cream background"),
        s("instagram-story",
          "Instagram story",
          "An overhead latte art shot with a flowing 'Discover our New "
          "Latte' handwritten script overlay style, beige aesthetic, "
          "Instagram story 9:16 feel cropped horizontally"),
        s("product-photography",
          "Product photography",
          "A delicate gold ring with a small green gemstone on a piece "
          "of polished marble, hero close-up product photography for "
          "a jewelry brand"),
        s("product-packaging",
          "Product packaging",
          "A dark glass cosmetic jar with minimalist beige label on a "
          "warm taupe backdrop, premium skincare product packaging hero"),
        s("background",
          "Background",
          "An empty white wooden display pedestal on a sun-lit tropical "
          "beach background, ready for product placement, scene/"
          "background replacement concept"),
        s("three-d-illustration",
          "3D illustration",
          "Stylised 3D cartoon character — a cheerful young woman with "
          "shoulder-length dark hair holding a tiny puppy, pixar-style "
          "render on a clean pastel background"),
        s("video-generator",
          "Video Generator",
          "A glowing play button overlaid on a mountain landscape photo "
          "with subtle motion-blur snow texture, concept for an AI "
          "video generator"),
    ]


def demo_catalog() -> List[AssetSpec]:
    """One demo asset per premium tool — used as the static fallback
    served by `_demo_response` so non-paying users can preview the
    feature without burning credits.

    Cost: ~$0.003 (Flux T2I) + ~$0.20 (Kling 5s) + ~$0.40 (Luma 5s).
    """
    return [
        AssetSpec(
            asset_id="premium-image",
            label="Premium AI Image Demo",
            prompt=(
                "Cinematic golden-hour city skyline with dramatic clouds, "
                "ultra-wide vista, photorealistic landmark architecture, "
                "lens flare, magazine cover composition. " + HUB_STYLE_SUFFIX
            ),
            width=1280, height=720,
            topic="premium_demo_image",
            extra_params={"set": "premium-demos", "label": "Premium AI Image Demo"},
            kind="image", extension="png",
        ),
        AssetSpec(
            asset_id="kling-video",
            label="Kling Cinematic Demo",
            prompt=(
                "slow cinematic camera glide forward over ocean waves at "
                "sunset, dramatic golden light reflecting on the water, "
                "photorealistic, soft volumetric clouds"
            ),
            width=1280, height=720,
            topic="premium_demo_kling",
            extra_params={"set": "premium-demos", "label": "Kling Cinematic Demo", "duration": 5, "aspect_ratio": "16:9"},
            kind="kling_video", extension="mp4",
        ),
        AssetSpec(
            asset_id="luma-video",
            label="Luma Dream Demo",
            prompt=(
                "elegant overhead shot of an espresso being poured into a "
                "ceramic cup on dark wood, slow motion, warm cinematic "
                "lighting, photorealistic food cinematography"
            ),
            width=1280, height=720,
            topic="premium_demo_luma",
            extra_params={"set": "premium-demos", "label": "Luma Dream Demo", "duration": 5, "aspect_ratio": "16:9"},
            kind="luma_video", extension="mp4",
        ),
    ]


def model_catalog() -> List[AssetSpec]:
    """11 full-body model references for the Virtual Try-On grid."""

    def m(asset_id: str, label: str, look: str) -> AssetSpec:
        return AssetSpec(
            asset_id=asset_id,
            label=label,
            prompt=f"{look}, {MODEL_STYLE_SUFFIX}",
            width=768,
            height=1152,
            topic="model_library",
            extra_params={"set": "tryon-models", "label": label},
        )

    # All 11 models are East Asian (Taiwanese / Chinese / Japanese) to match
    # the platform's primary audience. Asset IDs are kept identical to the
    # legacy Western-name catalog so backend TRYON_MODELS aliases and any
    # existing UserGeneration rows referencing these IDs continue to work.
    # Variety is preserved across age, gender, hairstyle, build, and outfit.
    return [
        m("avery",
          "Yi-Jun (怡君)",
          "young taiwanese woman with shoulder-length straight black hair, "
          "soft natural makeup, in plain black crew-neck t-shirt and dark "
          "indigo jeans, white sneakers, gentle smile, hands clasped in front"),
        m("sam",
          "Zhi-Wei (志偉)",
          "young taiwanese man with short clean-cut black hair, in "
          "oversized black t-shirt and charcoal joggers, white sneakers, "
          "neutral expression, hands at sides"),
        m("taylor",
          "Jun-Hao (俊豪)",
          "young east asian man with short side-parted black hair in "
          "plain black t-shirt and dark indigo straight-leg jeans, white "
          "sneakers, standing relaxed, arms loose"),
        m("kendall",
          "Xiao-Yu (曉雨)",
          "young taiwanese woman with long straight black hair and side "
          "bangs in plain white scoop-neck t-shirt and mid-blue jeans, "
          "white sneakers, calm confident expression"),
        m("jordan",
          "Guan-Yu (冠宇)",
          "young east asian man with neatly trimmed short beard and short "
          "black hair in oatmeal cream t-shirt and faded blue jeans, white "
          "sneakers, hands relaxed at sides"),
        m("casey",
          "Zong-Han (宗翰)",
          "young east asian man with short cropped black hair in light "
          "grey t-shirt and off-white relaxed trousers, white sneakers, "
          "neutral pose, arms at sides"),
        m("alex",
          "Jia-Ying (佳穎)",
          "young east asian woman with very short cropped black hair in "
          "beige loungewear set (matching short-sleeve top and joggers), "
          "beige sneakers, hands behind back, calm pose"),
        m("maya",
          "Ya-Ting (雅婷)",
          "young east asian woman with long straight black hair in plain "
          "black short-sleeve t-shirt and matte black joggers, black "
          "sneakers, hands relaxed at sides, soft natural makeup"),
        m("reece",
          "Hao-Ran (昊然)",
          "middle-aged east asian man with greying short black hair and "
          "trimmed beard in plain white crew-neck t-shirt and mid-blue "
          "straight-leg jeans, white sneakers, friendly relaxed expression"),
        m("lena",
          "Mei-Ling (美玲)",
          "young east asian woman with curly shoulder-length black hair "
          "in plain white scoop-neck t-shirt and dark indigo jeans, white "
          "sneakers, arms loose at sides, gentle smile"),
        m("julia",
          "Pei-Shan (佩珊)",
          "young east asian woman with wavy shoulder-length dark brown "
          "hair, soft natural makeup, in plain white t-shirt and mid-blue "
          "straight-leg jeans, white sneakers, calm friendly expression"),
    ]


# ─────────────────────────────────────────────────────────────────────
# PiAPI client (self-contained — no `app.*` import)
# ─────────────────────────────────────────────────────────────────────


class PiAPIError(RuntimeError):
    """Raised when PiAPI rejects a request or returns an unexpected payload."""


async def _piapi_submit_and_poll(
    client,
    api_key: str,
    payload: Dict[str, Any],
    *,
    media_keys: tuple = ("image_url", "image_urls", "url"),
    max_attempts: int = 240,
    sleep_sec: float = 5.0,
) -> str:
    """Submit a PiAPI task and poll until done; return the first URL it
    yields from `media_keys`. Used by all three task types below."""
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    resp = await client.post(f"{PIAPI_BASE_URL}/task", json=payload, headers=headers)
    if resp.status_code >= 400:
        raise PiAPIError(f"submit failed ({resp.status_code}): {resp.text[:400]}")
    data = resp.json()
    if "data" in data and "task_id" in data["data"]:
        task_id = data["data"]["task_id"]
    elif "task_id" in data:
        task_id = data["task_id"]
    else:
        raise PiAPIError(f"no task_id in submit response: {data}")

    for _ in range(max_attempts):
        await asyncio.sleep(sleep_sec)
        try:
            poll = await client.get(f"{PIAPI_BASE_URL}/task/{task_id}", headers=headers)
            poll.raise_for_status()
            blob = poll.json()
            task = blob.get("data", blob)
            status = (task.get("status") or "").lower()
            if status in {"completed", "success", "done"}:
                output = task.get("output") or task.get("result") or {}
                for key in media_keys:
                    val = output.get(key)
                    if isinstance(val, list):
                        val = val[0] if val else None
                    if val:
                        return val
                raise PiAPIError(f"task done but no media url in: {output}")
            if status in {"failed", "error"}:
                raise PiAPIError(f"task failed: {task.get('error', task)}")
        except PiAPIError:
            raise
        except Exception as e:  # transient network blip  # noqa: BLE001
            logger.debug("  poll glitch (will retry): %s", e)
    raise PiAPIError(f"task {task_id} timed out")


async def piapi_text_to_image(client, api_key: str, spec: AssetSpec) -> str:
    """Submit a Flux txt2img task and return the resulting image URL."""
    negative = HUB_NEGATIVE if spec.topic == "hub_thumbnail" else MODEL_NEGATIVE
    payload = {
        "model": PIAPI_FLUX_MODEL,
        "task_type": "txt2img",
        "input": {
            "prompt": spec.prompt,
            "negative_prompt": negative,
            "width": spec.width,
            "height": spec.height,
        },
    }
    return await _piapi_submit_and_poll(client, api_key, payload, media_keys=("image_url", "image_urls", "url"))


async def piapi_kling_video(client, api_key: str, spec: AssetSpec) -> str:
    """Submit a Kling T2V task and return the resulting video URL."""
    duration = int(spec.extra_params.get("duration", 5))
    aspect = spec.extra_params.get("aspect_ratio", "16:9")
    payload = {
        "model": PIAPI_KLING_MODEL,
        "task_type": "video_generation",
        "input": {
            "prompt": spec.prompt,
            "duration": duration,
            "aspect_ratio": aspect,
            "version": os.getenv("PIAPI_KLING_VIDEO_VERSION", "2.6"),
        },
    }
    return await _piapi_submit_and_poll(
        client, api_key, payload,
        media_keys=("video_url", "url"),
        max_attempts=240, sleep_sec=5.0,
    )


async def piapi_luma_video(client, api_key: str, spec: AssetSpec) -> str:
    """Submit a Luma T2V task and return the resulting video URL."""
    duration = int(spec.extra_params.get("duration", 5))
    aspect = spec.extra_params.get("aspect_ratio", "16:9")
    payload = {
        "model": PIAPI_LUMA_MODEL,
        "task_type": "video_generation",
        "input": {
            "prompt": spec.prompt,
            "duration": duration,
            "aspect_ratio": aspect,
            "model_name": PIAPI_LUMA_RAY,
        },
    }
    return await _piapi_submit_and_poll(
        client, api_key, payload,
        media_keys=("video_url", "url"),
        max_attempts=240, sleep_sec=5.0,
    )


async def download(client, url: str) -> bytes:
    resp = await client.get(url, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


# ─────────────────────────────────────────────────────────────────────
# Storage helpers
# ─────────────────────────────────────────────────────────────────────


def save_local(data: bytes, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    logger.info("  saved local: %s (%d bytes)", target.relative_to(REPO_ROOT), len(data))
    return target


def _content_type_for(blob_name: str) -> str:
    """Best-effort content-type from the blob suffix."""
    if blob_name.lower().endswith(".mp4"):
        return "video/mp4"
    if blob_name.lower().endswith(".webm"):
        return "video/webm"
    return "image/png"


def upload_gcs(data: bytes, blob_name: str, bucket_name: str) -> str:
    """Upload bytes to GCS and return the public URL.

    Uses google.cloud.storage directly. Auth uses ADC — the same
    credentials chain the rest of the project relies on
    (GOOGLE_APPLICATION_CREDENTIALS env var or `gcloud auth
    application-default login`)."""
    from google.cloud import storage  # type: ignore

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(data, content_type=_content_type_for(blob_name))
    blob.make_public()
    logger.info("  uploaded GCS: %s → %s", blob_name, blob.public_url)
    return blob.public_url


def lookup_hash_for(spec: AssetSpec) -> str:
    """Deterministic hash so re-running the script upserts the same row."""
    h = hashlib.sha256()
    h.update(spec.topic.encode())
    h.update(b"|")
    h.update(spec.asset_id.encode())
    h.update(b"|")
    h.update(spec.prompt.encode())
    return h.hexdigest()


def normalize_db_url(url: str) -> str:
    """Translate a SQLAlchemy URL into a plain asyncpg URL.

    The project stores the DSN as `postgresql+asyncpg://…` for
    SQLAlchemy. asyncpg.connect() wants `postgresql://…`.
    """
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url[len("postgresql+asyncpg://"):]
    if url.startswith("postgres+asyncpg://"):
        return "postgresql://" + url[len("postgres+asyncpg://"):]
    return url


def build_material_sql(spec: AssetSpec, public_url: str, gcs_url: Optional[str]) -> str:
    """Render the same UPSERT we'd issue to Postgres as a single SQL
    string. Used by --emit-sql to produce a file the user can apply
    from inside the VPC (Cloud Shell + cloud-sql-proxy --private-ip)."""
    # Map asset purpose → Material.tool_type enum value. Premium-demo
    # rows are tagged as `effect` for now (they don't have a dedicated
    # enum value); the `_demo_response` patch keys off the topic, not
    # the tool_type, so this is just a placeholder that satisfies the
    # NOT NULL enum constraint on the column.
    if spec.topic == "model_library":
        tool_type = "try_on"
    elif spec.topic.startswith("premium_demo_"):
        tool_type = "effect"
    else:
        tool_type = "effect"
    lookup = lookup_hash_for(spec)
    image_url = gcs_url or public_url
    is_video = spec.extension in {"mp4", "webm"}
    params = {
        **spec.extra_params,
        "asset_id": spec.asset_id,
        "width": spec.width,
        "height": spec.height,
    }
    tags = ["brand", spec.topic, spec.asset_id]

    def q(s: str) -> str:
        return "'" + str(s).replace("'", "''") + "'"

    tags_array = "ARRAY[" + ",".join(q(t) for t in tags) + "]::text[]"

    if is_video:
        return (
            f"INSERT INTO materials ("
            f"id, lookup_hash, tool_type, main_topic, topic, language, "
            f"tags, source, status, prompt, input_video_url, input_params, "
            f"result_video_url, title_en, quality_score, is_active, "
            f"created_at, updated_at) VALUES ("
            f"gen_random_uuid(), {q(lookup)}, {q(tool_type)}, "
            f"{q('Brand Assets')}, {q(spec.topic)}, 'en', {tags_array}, "
            f"'seed', 'approved', {q(spec.prompt)}, {q(image_url)}, "
            f"{q(json.dumps(params))}::jsonb, {q(image_url)}, "
            f"{q(spec.label)}, 0.9, true, now(), now()) "
            f"ON CONFLICT (lookup_hash) DO UPDATE SET "
            f"input_video_url=EXCLUDED.input_video_url, "
            f"result_video_url=EXCLUDED.result_video_url, "
            f"prompt=EXCLUDED.prompt, "
            f"input_params=materials.input_params || EXCLUDED.input_params, "
            f"title_en=EXCLUDED.title_en, status='approved', "
            f"is_active=true, updated_at=now();\n"
        )
    return (
        f"INSERT INTO materials ("
        f"id, lookup_hash, tool_type, main_topic, topic, language, "
        f"tags, source, status, prompt, input_image_url, input_params, "
        f"result_image_url, title_en, quality_score, is_active, "
        f"created_at, updated_at) VALUES ("
        f"gen_random_uuid(), {q(lookup)}, {q(tool_type)}, "
        f"{q('Brand Assets')}, {q(spec.topic)}, 'en', {tags_array}, "
        f"'seed', 'approved', {q(spec.prompt)}, {q(image_url)}, "
        f"{q(json.dumps(params))}::jsonb, {q(image_url)}, "
        f"{q(spec.label)}, 0.9, true, now(), now()) "
        f"ON CONFLICT (lookup_hash) DO UPDATE SET "
        f"input_image_url=EXCLUDED.input_image_url, "
        f"result_image_url=EXCLUDED.result_image_url, "
        f"prompt=EXCLUDED.prompt, "
        f"input_params=materials.input_params || EXCLUDED.input_params, "
        f"title_en=EXCLUDED.title_en, status='approved', "
        f"is_active=true, updated_at=now();\n"
    )


async def upsert_material_row(spec: AssetSpec, public_url: str, gcs_url: Optional[str]) -> None:
    """Upsert a row in the `materials` table for the generated asset.

    Hub tiles → tool_type='effect', topic='hub_thumbnail'.
    Try-on models → tool_type='try_on', topic='model_library'
    (matches what the inputLibrary endpoint expects).

    We INSERT … ON CONFLICT(lookup_hash) DO UPDATE so re-runs update
    the same row instead of creating duplicates.
    """
    import asyncpg  # type: ignore

    dsn = normalize_db_url(os.getenv("DATABASE_URL", ""))
    if not dsn:
        raise RuntimeError("DATABASE_URL not set — required for DB upserts (use --no-db to skip)")

    tool_type = "try_on" if spec.topic == "model_library" else "effect"
    lookup = lookup_hash_for(spec)
    image_url = gcs_url or public_url
    params = {
        **spec.extra_params,
        "asset_id": spec.asset_id,
        "width": spec.width,
        "height": spec.height,
    }
    tags = ["brand", spec.topic, spec.asset_id]

    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            """
            INSERT INTO materials (
                id, lookup_hash, tool_type, main_topic, topic, language,
                tags, source, status, prompt, input_image_url, input_params,
                result_image_url, title_en, quality_score, is_active,
                created_at, updated_at
            )
            VALUES (
                gen_random_uuid(), $1, $2, $3, $4, 'en',
                $5::text[], 'seed', 'approved', $6, $7, $8::jsonb,
                $7, $9, 0.9, true,
                now(), now()
            )
            ON CONFLICT (lookup_hash) DO UPDATE SET
                input_image_url = EXCLUDED.input_image_url,
                result_image_url = EXCLUDED.result_image_url,
                prompt = EXCLUDED.prompt,
                input_params = materials.input_params || EXCLUDED.input_params,
                title_en = EXCLUDED.title_en,
                status = 'approved',
                is_active = true,
                updated_at = now()
            """,
            lookup,
            tool_type,
            "Brand Assets",
            spec.topic,
            tags,
            spec.prompt,
            image_url,
            json.dumps(params),
            spec.label,
        )
        logger.info("  db: upserted material (lookup=%s…)", lookup[:8])
    finally:
        await conn.close()


# ─────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────


@dataclass
class RunResult:
    asset_id: str
    label: str
    local_path: str
    public_url: str
    gcs_url: Optional[str]


async def run_one(
    client,
    api_key: str,
    spec: AssetSpec,
    local_root: Path,
    gcs_prefix: str,
    *,
    do_gcs: bool,
    do_db: bool,
    force: bool,
    dry_run: bool,
    sql_sink: Optional[list] = None,
) -> Optional[RunResult]:
    local_path = local_root / f"{spec.asset_id}.{spec.extension}"
    blob_name = f"{gcs_prefix}/{spec.asset_id}.{spec.extension}"

    if dry_run:
        logger.info("[DRY] %s", spec.asset_id)
        logger.info("  prompt : %s", spec.prompt)
        logger.info("  local  : %s", local_path)
        logger.info("  gcs    : %s", blob_name if do_gcs else "(skipped)")
        logger.info("  db     : %s", "yes" if do_db else "(skipped)")
        return None

    # If the local file already exists we still need to try GCS + DB
    # — they may have failed on a previous run. We re-use the local
    # bytes instead of re-spending on PiAPI; the GCS and DB paths are
    # idempotent (blob overwrite, lookup_hash upsert).
    if local_path.exists() and not force:
        logger.info("  reuse %s — local file already exists, skipping PiAPI call",
                    spec.asset_id)
        data = local_path.read_bytes()
    else:
        logger.info("[GEN] %s — %s (kind=%s)", spec.asset_id, spec.label, spec.kind)
        try:
            if spec.kind == "image":
                media_url = await piapi_text_to_image(client, api_key, spec)
            elif spec.kind == "kling_video":
                media_url = await piapi_kling_video(client, api_key, spec)
            elif spec.kind == "luma_video":
                media_url = await piapi_luma_video(client, api_key, spec)
            else:
                raise RuntimeError(f"unknown spec.kind={spec.kind}")
            data = await download(client, media_url)
        except Exception as e:  # noqa: BLE001
            logger.error("  FAIL generation: %s", e)
            return None

        save_local(data, local_path)

    gcs_url: Optional[str] = None
    if do_gcs:
        bucket = os.getenv("GCS_BUCKET")
        if not bucket:
            logger.warning("  GCS disabled (GCS_BUCKET not set) — skipping upload")
        else:
            try:
                gcs_url = upload_gcs(data, blob_name, bucket)
            except Exception as e:  # noqa: BLE001
                logger.error("  GCS upload failed: %s", e)

    public_url = (
        gcs_url
        if gcs_url
        else f"/static_assets/{local_path.relative_to(FRONTEND_PUBLIC).as_posix()}"
    )

    if sql_sink is not None:
        sql_sink.append(build_material_sql(spec, public_url, gcs_url))

    if do_db:
        try:
            await upsert_material_row(spec, public_url, gcs_url)
        except Exception as e:  # noqa: BLE001
            logger.error("  DB upsert failed: %s", e)

    return RunResult(spec.asset_id, spec.label, str(local_path), public_url, gcs_url)


def print_frontend_snippet(set_name: str, results: List[RunResult]) -> None:
    if not results:
        return

    print("\n" + "=" * 72)
    print(f"Frontend snippet for set={set_name}")
    print("=" * 72)
    if set_name == "hub":
        print("Replace each tile's `thumb:` field in")
        print("  frontend-vue/src/data/toolHub.ts")
        print("with the values below:\n")
        for r in results:
            print(f"  // {r.label}")
            print(f"  id '{r.asset_id}'  →  thumb: '{r.public_url}',")
    elif set_name == "models":
        print("Replace `preview:` URLs in modelOptions in")
        print("  frontend-vue/src/views/tools/TryOn.vue")
        print("with the values below:\n")
        for r in results:
            print(f"  // {r.label} ({r.asset_id})")
            print(f"  preview: '{r.public_url}',")
    print("=" * 72 + "\n")


async def run_set(
    set_name: str,
    catalog: List[AssetSpec],
    local_root: Path,
    gcs_prefix: str,
    *,
    only: Optional[str],
    limit: Optional[int],
    do_gcs: bool,
    do_db: bool,
    force: bool,
    dry_run: bool,
    rate_limit_sec: float,
    sql_sink: Optional[list] = None,
) -> List[RunResult]:
    if only:
        catalog = [s for s in catalog if s.asset_id == only]
        if not catalog:
            logger.error("--only %s did not match any asset in set %s", only, set_name)
            return []
    if limit is not None:
        catalog = catalog[:limit]

    results: List[RunResult] = []
    if dry_run:
        for spec in catalog:
            await run_one(None, "", spec, local_root, gcs_prefix,
                          do_gcs=do_gcs, do_db=do_db, force=force, dry_run=True,
                          sql_sink=sql_sink)
        return results

    import httpx  # lazy — only needed for real runs

    api_key = os.getenv("PIAPI_KEY", "").strip()
    if not api_key:
        raise RuntimeError("PIAPI_KEY env var not set (check backend/.env)")

    async with httpx.AsyncClient(timeout=120.0) as client:
        for i, spec in enumerate(catalog):
            res = await run_one(
                client,
                api_key,
                spec,
                local_root,
                gcs_prefix,
                do_gcs=do_gcs,
                do_db=do_db,
                force=force,
                dry_run=False,
                sql_sink=sql_sink,
            )
            if res:
                results.append(res)
            if i < len(catalog) - 1 and rate_limit_sec > 0:
                logger.debug("  sleeping %.1fs (rate limit)", rate_limit_sec)
                time.sleep(rate_limit_sec)
    return results


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--set", choices=["hub", "models", "demos", "all"], default="all",
                   help="Which asset set to generate")
    p.add_argument("--only", type=str, help="Generate only the asset with this id "
                                            "(e.g. virtual-model, avery)")
    p.add_argument("--limit", type=int, help="Generate at most N assets from the set")
    p.add_argument("--gcs", action="store_true", help="Upload each result to GCS")
    p.add_argument("--no-db", action="store_true", help="Skip DB upsert (just produce files)")
    p.add_argument("--force", action="store_true", help="Re-generate even if local file exists")
    p.add_argument("--dry-run", action="store_true", help="Print prompts only — no API calls, no writes")
    p.add_argument("--rate-limit", type=float, default=3.0,
                   help="Seconds to sleep between PiAPI calls (default 3.0)")
    p.add_argument("--print-json", action="store_true",
                   help="Print machine-readable JSON of all results at the end")
    p.add_argument("--emit-sql", type=str, metavar="PATH",
                   help="Also write all upsert statements to this .sql file. "
                        "Useful when you can't reach the prod DB directly — apply "
                        "the file later from Cloud Shell + cloud-sql-proxy.")
    return p.parse_args()


async def main_async() -> int:
    args = parse_args()

    sets: List[tuple] = []
    if args.set in ("hub", "all"):
        sets.append(("hub", hub_catalog(), HUB_LOCAL_DIR, HUB_GCS_PREFIX))
    if args.set in ("models", "all"):
        sets.append(("models", model_catalog(), MODELS_LOCAL_DIR, MODELS_GCS_PREFIX))
    if args.set in ("demos", "all"):
        sets.append(("demos", demo_catalog(), DEMOS_LOCAL_DIR, DEMOS_GCS_PREFIX))

    sql_sink: Optional[list] = [] if args.emit_sql else None

    all_results: Dict[str, List[RunResult]] = {}
    for set_name, catalog, local_root, gcs_prefix in sets:
        logger.info("")
        logger.info("=== set=%s — %d assets ===", set_name, len(catalog))
        res = await run_set(
            set_name,
            catalog,
            local_root,
            gcs_prefix,
            only=args.only,
            limit=args.limit,
            do_gcs=args.gcs,
            do_db=not args.no_db,
            force=args.force,
            dry_run=args.dry_run,
            rate_limit_sec=args.rate_limit,
            sql_sink=sql_sink,
        )
        all_results[set_name] = res
        if not args.dry_run:
            print_frontend_snippet(set_name, res)

    if args.emit_sql and sql_sink:
        sql_path = Path(args.emit_sql)
        sql_path.parent.mkdir(parents=True, exist_ok=True)
        header = (
            "-- Auto-generated by backend/scripts/generate_brand_assets.py\n"
            "-- Apply from a context that can reach the prod-db private IP\n"
            "-- (e.g. Cloud Shell with cloud-sql-proxy --private-ip).\n"
            "BEGIN;\n"
        )
        sql_path.write_text(header + "".join(sql_sink) + "COMMIT;\n")
        logger.info("Wrote %d UPSERT statements to %s", len(sql_sink), sql_path)

    if args.print_json:
        out = {
            set_name: [
                {
                    "asset_id": r.asset_id,
                    "label": r.label,
                    "local_path": r.local_path,
                    "public_url": r.public_url,
                    "gcs_url": r.gcs_url,
                }
                for r in res
            ]
            for set_name, res in all_results.items()
        }
        print(json.dumps(out, indent=2))

    total = sum(len(v) for v in all_results.values())
    logger.info("Done. Wrote %d asset(s).", total)
    return 0


def main() -> int:
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
