#!/usr/bin/env python3
"""
Regenerate the per-tool example thumbnails surfaced by ExampleGallery.vue,
using PiAPI's Nano Banana Pro (Google Gemini 2.5 Flash Image Pro) so the
images match the production-quality aesthetic the tools themselves emit
instead of the older, AI-tell-heavy renders currently in the bucket.

In scope (40 thumbnails):
    - product-scene-classic  ps-01 … ps-10
    - claymation             cl-01 … cl-10
    - pattern-generate       pt-01 … pt-10
    - room-redesign          rr-01 … rr-10

Output:
    gs://vidgo-media-vidgo-ai/static/examples/<tool>/<id>.jpg
    (overwrites the existing files — toolExamples.ts URLs stay valid)

Requirements:
    - PIAPI_KEY in backend/.env (or env var)
    - gcloud CLI authenticated against the project that owns the bucket
    - Python 3.10+ (stdlib only — no pip install needed)

Usage:
    python3 scripts/regenerate-example-thumbnails.py --dry-run
    python3 scripts/regenerate-example-thumbnails.py --only product-scene-classic
    python3 scripts/regenerate-example-thumbnails.py --limit 2
    python3 scripts/regenerate-example-thumbnails.py            # full batch
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUCKET = "vidgo-media-vidgo-ai"
GCS_PREFIX = "static/examples"
PIAPI_BASE = "https://api.piapi.ai/api/v1"
POLL_INTERVAL_SEC = 6
POLL_TIMEOUT_SEC = 240


@dataclass
class Job:
    tool: str
    example_id: str
    prompt: str
    aspect_ratio: str = "1:1"


# ─── product-scene-classic ──────────────────────────────────────────────────
# Scene prompts taken from frontend-vue/src/data/toolExamples.ts (ps-01..10).
# Each gets a paired product hint so the thumbnail actually demonstrates the
# "product placed in scene" feature instead of rendering an empty backdrop.
_PS_SCENE_PROMPTS = [
    ("ps-01", "minimalist white ceramic skincare bottle, brushed silver cap, no visible text",
     "subtle off-white marble plinth, soft directional side light from upper-left casting a long elegant shadow, pale grey gradient backdrop, premium studio packshot mood"),
    ("ps-02", "amber glass essential-oil bottle with wooden dropper cap",
     "scene set on moss-covered river stones with fresh ferns, soft natural daylight, outdoor feel"),
    ("ps-03", "tall dark frosted perfume bottle with brushed gold cap, no logo",
     "black polished marble surface, gold candleholder beside the product, warm luxe dinner ambience, rim lighting"),
    ("ps-04", "matte beige cylindrical cosmetic tube",
     "beige seamless paper backdrop, single fresh green sprig beside the product, minimal Nordic styling, soft diffuse light"),
    ("ps-05", "speckled ceramic latte mug with handle",
     "warm walnut bar counter, leather notebook and brass pen prop beside the mug, cozy cafe afternoon light"),
    ("ps-06", "frosted sunscreen tube with subtle pastel blue cap",
     "scene placed on white sand with scattered seashells, turquoise ocean blurred in background, bright summer daylight"),
    ("ps-07", "raw paper-wrapped bar of soap with twine, no visible text",
     "rough exposed-concrete backdrop, single brushed-steel basin in background, industrial loft mood, moody cool side light"),
    ("ps-08", "tall sleek matte-black energy-drink can",
     "deep cobalt blue backdrop, pink and purple neon strip lighting from the side, futuristic cyberpunk vibe, glossy reflections"),
    ("ps-09", "linen-wrapped artisan honey jar with kraft tag",
     "aged wooden tabletop, linen runner and dried wheat sprigs beside the jar, rustic handcrafted afternoon light"),
    ("ps-10", "frosted glass floral perfume bottle with pink cap",
     "English country garden setting, climbing roses and a single butterfly mid-frame, soft warm spring sunlight, romantic"),
]


def _build_ps_jobs() -> list[Job]:
    base_clause = (
        "Photorealistic commercial product photography, high resolution, "
        "tack-sharp focus on the product, natural light that matches the "
        "scene, realistic ground contact shadow, no humans, no extra "
        "products, no logos, no overlaid text or watermark."
    )
    jobs = []
    for ex_id, product, scene in _PS_SCENE_PROMPTS:
        prompt = (
            f"Hero shot of a {product}, placed in this scene: {scene}. "
            f"{base_clause}"
        )
        jobs.append(Job("product-scene-classic", ex_id, prompt, "4:3"))
    return jobs


# ─── claymation ─────────────────────────────────────────────────────────────
# Each prompt rewritten to lean hard on the stop-motion clay aesthetic so we
# don't get the cheesy AI-typography overlay seen on the current cl-03 burger.
_CL_PROMPTS = [
    ("cl-01", "Chubby claymation kitten, big round shiny eyes, soft pastel palette, plasticine fingerprint texture visible, studio lit, soft contact shadow on white seamless paper"),
    ("cl-02", "Claymation boy with red rain boots, yellow raincoat and umbrella, walking on a wet cobblestone street, stop-motion plasticine textures, overcast moody light"),
    ("cl-03", "Claymation cheeseburger with bun, lettuce, tomato, cheese, patty exploded apart in mid-air, light pastel-blue backdrop, advertising hero shot, no text or labels, no captions"),
    ("cl-04", "Claymation overhead aerial of a tiny stop-motion city skyline at golden hour, miniature plasticine cars and trees, soft warm afternoon sun, depth-of-field blur on the edges"),
    ("cl-05", "Claymation Santa Claus handing a wrapped gift toward camera, deep red Christmas backdrop with soft bokeh fairy lights, classic stop-motion plasticine texture"),
    ("cl-06", "Claymation bright cobalt-blue robot, riveted metal-look plates rendered in clay, dynamic battle stance, clean studio backdrop, dramatic side light"),
    ("cl-07", "Claymation coffee mug on a wooden table, heart-shaped steam rising in plasticine puffs, cosy morning light, no text"),
    ("cl-08", "Claymation parade of tiny animals (rabbit, fox, bear, cat) walking single file across a soft pastel-green meadow, lateral camera pan composition, upbeat playful stop-motion mood"),
    ("cl-09", "Claymation fairy holding a glowing wand, swirling stardust particles around her, deep twilight-blue backdrop, soft magical rim light, plasticine sculpt detail"),
    ("cl-10", "Claymation corgi mid-tail-wag, tongue out, on a sunny green grass meadow, plasticine fur texture, bright cheerful daylight, soft shadow under paws"),
]


def _build_cl_jobs() -> list[Job]:
    return [Job("claymation", ex_id, p, "1:1") for ex_id, p in _CL_PROMPTS]


# ─── pattern-generate ───────────────────────────────────────────────────────
# Tile-able / seamless was the failure mode on the old pt-05 (visible seam),
# so every prompt explicitly demands a real seamless tile.
_PT_PROMPTS = [
    ("pt-01", "Seamless tileable Japanese porcelain floral pattern, indigo blue on crisp white background, designed as wrapping paper, perfectly repeating, no seams"),
    ("pt-02", "Seamless tileable Art Deco geometric tile pattern, black background with gold linework, fan and sunburst motifs, ceramic-tile look, perfectly repeating"),
    ("pt-03", "Seamless tileable abstract sumi-e ink brushstroke pattern, generous negative space, beige rice-paper base, zen aesthetic for a silk scarf, perfectly repeating"),
    ("pt-04", "Seamless tileable Taiwanese majolica floor-tile pattern, terracotta red and forest green on cream, ornate traditional motifs, perfectly repeating"),
    ("pt-05", "Seamless tileable deep-blue 3D quilted diamond grid pattern with crisp gold stitching along every edge, luxury leather goods feel, perfectly repeating tile with no visible seams"),
    ("pt-06", "Seamless tileable Nordic leaf wallpaper pattern, cream background with forest-green hand-drawn foliage, perfectly repeating"),
    ("pt-07", "Seamless tileable coffee bag pattern, hand-drawn coffee beans and leaves, warm brown palette on kraft-paper texture, handcrafted feel, perfectly repeating, no readable text"),
    ("pt-08", "Seamless tileable kawaii cartoon-animal pattern, pastel pink mint and butter-yellow palette, suitable for kids bedding, perfectly repeating"),
    ("pt-09", "Seamless tileable tropical foliage and flamingo pattern, deep jewel-emerald palette with hot pink accents, summer scarf feel, perfectly repeating"),
    ("pt-10", "Seamless tileable Van Gogh-style brushstroke pattern, starry-night blue with lemon-yellow swirls, art fabric, perfectly repeating"),
]


def _build_pt_jobs() -> list[Job]:
    return [Job("pattern-generate", ex_id, p, "1:1") for ex_id, p in _PT_PROMPTS]


# ─── room-redesign ──────────────────────────────────────────────────────────
# The old rr-* renders had melted sofas / odd proportions — we lean on
# "real interior photograph" cues so Gemini renders furniture-shaped objects
# instead of dreamlike approximations.
_RR_PROMPTS = [
    ("rr-01", "Real interior photograph of a Scandinavian living room, light oak wood floor, off-white linen sofa with dusty-blue cushions, large window with sheer curtains, natural daylight, magazine quality"),
    ("rr-02", "Real interior photograph of a Japandi living room, tatami flooring, low solid-wood table, paper lantern pendant, beige and muted-green palette, soft diffuse light, magazine quality"),
    ("rr-03", "Real interior photograph of an industrial loft living room, exposed red brick wall, black steel-framed windows, tan leather chesterfield sofa, Edison-bulb pendant lights, warm evening light"),
    ("rr-04", "Real interior photograph of a mid-century modern living room, walnut wood credenza, mustard-yellow velvet sofa, geometric rug, large arched window, afternoon sun"),
    ("rr-05", "Real interior photograph of a bohemian living room, woven jute wall tapestry, layered Turkish rugs, low rattan sofa with multicoloured cushions, warm candlelight and string lights"),
    ("rr-06", "Real interior photograph of a minimal modern living room, white walls, polished concrete floor, single grey sofa, one piece of abstract art, clean lines, soft daylight"),
    ("rr-07", "Real interior photograph of an American farmhouse kitchen, weathered ceiling beams, white shaker cabinetry, woven baskets, butcher-block island, warm rustic morning light"),
    ("rr-08", "Real interior photograph of an Art Deco bedroom, dark emerald velvet headboard, brass wall sconces, geometric mirror above the bed, rich jewel-tone palette, moody evening light"),
    ("rr-09", "Real interior photograph of a tropical resort living room, woven rattan sofa, palm-leaf print cushions, large potted monstera, ocean-blue accent wall, breezy daylight"),
    ("rr-10", "Real interior photograph of a hipster café storefront seen from inside, neon signage on brick wall, reclaimed-wood bar counter, industrial pendant lights, low warm evening light"),
]


def _build_rr_jobs() -> list[Job]:
    # Suppress people/pets globally — "room redesign" thumbnails should let
    # the viewer project themselves into the space. rr-03 originally rendered
    # two people on the sofa before this guard was added.
    suffix = " Empty room, no people, no humans, no pets, no figures, focus on the space and furniture only."
    return [Job("room-redesign", ex_id, p + suffix, "1:1") for ex_id, p in _RR_PROMPTS]


def all_jobs() -> list[Job]:
    return _build_ps_jobs() + _build_cl_jobs() + _build_pt_jobs() + _build_rr_jobs()


# ─── PiAPI ──────────────────────────────────────────────────────────────────
def _load_piapi_key() -> str:
    key = os.environ.get("PIAPI_KEY")
    if key:
        return key
    env_file = ROOT / "backend" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("PIAPI_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("PIAPI_KEY not set and backend/.env has no PIAPI_KEY entry")


def _http_json(method: str, url: str, key: str, body: dict | None = None) -> dict:
    # PiAPI sits behind Cloudflare; the default Python-urllib User-Agent
    # trips bot detection (error 1010) so we must masquerade as a browser.
    data = None
    headers = {
        "x-api-key": key,
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


def submit_task(key: str, job: Job) -> str:
    payload = {
        "model": "gemini",
        "task_type": "nano-banana-pro",
        "input": {
            "prompt": job.prompt,
            "aspect_ratio": job.aspect_ratio,
            "resolution": "2K",
        },
    }
    body = _http_json("POST", f"{PIAPI_BASE}/task", key, payload)
    data = body.get("data") or body
    task_id = data.get("task_id") or data.get("id")
    if not task_id:
        raise RuntimeError(f"PiAPI submit returned no task_id: {body}")
    return task_id


def poll_task(key: str, task_id: str) -> str:
    deadline = time.time() + POLL_TIMEOUT_SEC
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL_SEC)
        body = _http_json("GET", f"{PIAPI_BASE}/task/{task_id}", key)
        data = body.get("data") or body
        status = (data.get("status") or "").lower()
        if status in {"completed", "success", "successful"}:
            output = data.get("output") or {}
            url = output.get("image_url")
            if not url:
                imgs = output.get("image_urls") or output.get("images") or []
                if imgs:
                    first = imgs[0]
                    url = first if isinstance(first, str) else (first.get("url") or first.get("image_url"))
            if not url:
                raise RuntimeError(f"PiAPI completed but no image_url: {data}")
            return url
        if status in {"failed", "error"}:
            err = (data.get("error") or {}).get("message") or data.get("message") or "unknown"
            raise RuntimeError(f"PiAPI task {task_id} failed: {err}")
    raise TimeoutError(f"PiAPI task {task_id} did not complete in {POLL_TIMEOUT_SEC}s")


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "vidgo-thumbs/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, dest.open("wb") as f:
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                break
            f.write(chunk)


def gcs_upload(local: Path, blob: str) -> str:
    target = f"gs://{BUCKET}/{blob}"
    # vidgo-media-vidgo-ai uses fine-grained ACLs (not uniform bucket-level
    # access) and its default object ACL is empty, so newly-uploaded objects
    # are private unless we explicitly opt them into publicRead — otherwise
    # the frontend ExampleGallery would 403 on the new thumbnails.
    subprocess.run(
        [
            "gcloud", "storage", "cp",
            "--cache-control=public, max-age=3600",
            "--content-type=image/jpeg",
            "--predefined-acl=publicRead",
            str(local),
            target,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return f"https://storage.googleapis.com/{BUCKET}/{blob}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="List jobs and exit; no API calls or uploads.")
    p.add_argument("--only", default="",
                   help="Comma-separated tool slugs to include (e.g. product-scene-classic,claymation).")
    p.add_argument("--limit", type=int, default=0,
                   help="Run at most this many jobs (after --only filter).")
    p.add_argument("--id", default="",
                   help="Comma-separated example IDs to include (e.g. ps-01,cl-03).")
    args = p.parse_args()

    jobs = all_jobs()
    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        jobs = [j for j in jobs if j.tool in wanted]
    if args.id:
        wanted_ids = {s.strip() for s in args.id.split(",") if s.strip()}
        jobs = [j for j in jobs if j.example_id in wanted_ids]
    if args.limit > 0:
        jobs = jobs[: args.limit]

    if not jobs:
        print("No jobs matched the filters; nothing to do.")
        return 0

    print(f"Planned {len(jobs)} job(s):")
    for j in jobs:
        print(f"  {j.tool}/{j.example_id}  ({j.aspect_ratio})  {j.prompt[:80]}…")

    if args.dry_run:
        return 0

    key = _load_piapi_key()

    ok = 0
    fail = 0
    with tempfile.TemporaryDirectory(prefix="vidgo-thumbs-") as tmp:
        for i, job in enumerate(jobs, 1):
            blob = f"{GCS_PREFIX}/{job.tool}/{job.example_id}.jpg"
            print(f"[{i}/{len(jobs)}] {job.tool}/{job.example_id} → submitting…", flush=True)
            try:
                task_id = submit_task(key, job)
                print(f"    task_id={task_id}, polling…", flush=True)
                provider_url = poll_task(key, task_id)
                local = Path(tmp) / f"{job.tool}__{job.example_id}.jpg"
                download(provider_url, local)
                public_url = gcs_upload(local, blob)
                print(f"    ✓ uploaded → {public_url}", flush=True)
                ok += 1
            except Exception as exc:  # noqa: BLE001
                print(f"    ✗ FAILED: {exc}", flush=True)
                fail += 1

    print(f"\nDone — {ok} succeeded, {fail} failed.")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
