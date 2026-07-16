#!/usr/bin/env python3
"""
generate_style_previews.py — generate the per-style preview thumbnails for the
Templates galleries (/tools/interior-templates, /tools/exterior-templates,
/tools/commercial-templates) and optionally re-generate the room-redesign
ExampleGallery thumbnails (rr-01..rr-10).

The backend derives each gallery card's preview as
    https://storage.googleapis.com/<bucket>/static/interior-styles/<id>.jpg
(see tools.py `_with_preview_urls`), so uploading a file at that path makes it
appear on the live site with no deploy.

STDLIB-ONLY on purpose: backend/.venv's interpreter is gone (uv-managed python
was removed), so this script avoids all `app.*` imports. It re-reads the style
catalogs from tools.py via ast.literal_eval and talks to PiAPI's REST API with
urllib. Uploads shell out to gsutil (gcloud auth is the only working GCS
credential on this machine — no ADC json).

Usage:
    python3 scripts/generate_style_previews.py --smoke
    python3 scripts/generate_style_previews.py --catalog all
    python3 scripts/generate_style_previews.py --catalog interior --catalog exterior
    python3 scripts/generate_style_previews.py --examples          # rr-01..10 only
    python3 scripts/generate_style_previews.py --catalog all --examples

Cost (PiAPI list prices, docs/service-cost.md §3.0, 2026-07):
    previews  — Flux dev txt2img  $0.015/img (61 styles ≈ $0.92)
    examples  — Flux Kontext i2i  ~$0.015-0.04/img (10 ≈ $0.15-0.40)
"""
from __future__ import annotations

import argparse
import ast
import concurrent.futures
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
TOOLS_PY = BACKEND_DIR / "app" / "api" / "v1" / "tools.py"

PIAPI_BASE = "https://api.piapi.ai/api/v1"
GCS_BUCKET = "vidgo-media-vidgo-ai"
PREVIEW_PREFIX = "static/interior-styles"
EXAMPLES_PREFIX = "static/examples/room-redesign"
# Match gcs_storage_service.IMMUTABLE_CACHE_CONTROL
CACHE_CONTROL = "public, max-age=31536000, immutable"

# Card tiles are aspect-[4/5]; flux1-dev caps at 1024*1024 px total,
# 896*1120 = 1,003,520 px fits and is a clean 32-multiple.
PREVIEW_W, PREVIEW_H = 896, 1120

FLUX_DEV = "Qubico/flux1-dev"
FLUX_KONTEXT = "Qubico/flux1-dev-advanced"

# The interior and exterior catalogs BOTH contain id="tropical_resort", and
# both would derive .../tropical_resort.jpg. The interior render keeps the
# shared path (interior is the flagship gallery); the exterior one goes to a
# namespaced file that EXTERIOR_STYLES now pins via an explicit preview_url.
BLOB_OVERRIDES = {("exterior", "tropical_resort"): "tropical_resort_exterior.jpg"}

ROOM_INPUT = "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/examples/_inputs/room-empty.jpg"
# Keep in sync with generate_example_assets.py PROMPTS["room-redesign"].
RR_EXAMPLES = [
    ("rr-01", "Redesign this room in Scandinavian style: light wood floor, off-white sofa, dusty-blue cushions, natural light."),
    ("rr-02", "Redesign in Japandi style: tatami, low wood table, paper lantern, beige palette."),
    ("rr-03", "Redesign in industrial loft style: exposed brick, black steel framing, leather sofa, Edison bulbs."),
    ("rr-04", "Redesign in mid-century modern style: walnut wood, mustard velvet sofa, geometric rug."),
    ("rr-05", "Redesign in bohemian style: woven tapestry, Turkish rugs, layered textiles, warm candlelight."),
    ("rr-06", "Redesign in minimal modern style: white walls, grey sofa, clean lines, negative space and light."),
    ("rr-07", "Redesign in American farmhouse style: weathered beams, white kitchen, woven baskets, warm rustic feel."),
    ("rr-08", "Redesign in Art Deco style: dark green velvet headboard, brass sconces, geometric mirror."),
    ("rr-09", "Redesign in tropical resort style: rattan furniture, palm-leaf plants, ocean-blue palette."),
    ("rr-10", "Redesign as a café storefront: neon signage, wood counter, industrial pendants, hipster vibe."),
]

CATALOG_VARS = {
    "interior": "INTERIOR_STYLES",
    "exterior": "EXTERIOR_STYLES",
    "commercial": "COMMERCIAL_STYLES",
    "landscape": "LANDSCAPE_STYLES",
}


def load_env_key(name: str) -> str:
    for line in (BACKEND_DIR / ".env").read_text().splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"{name} not found in backend/.env")


def load_catalog(kind: str) -> list[dict]:
    src = TOOLS_PY.read_text()
    var = CATALOG_VARS[kind]
    m = re.search(rf"^{var} = (\[.*?\n\])", src, re.S | re.M)
    if not m:
        raise SystemExit(f"could not locate {var} in tools.py")
    return ast.literal_eval(m.group(1))


# ─── PiAPI REST (stdlib) ────────────────────────────────────────────────────

def _http_json(url: str, api_key: str, payload: dict | None = None) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        # Cloudflare in front of api.piapi.ai bans urllib's default UA
        # (403 "error code: 1010") — impersonate httpx like the backend.
        headers={"X-API-Key": api_key, "Content-Type": "application/json",
                 "User-Agent": "python-httpx/0.27.0", "Accept": "*/*"},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def submit_and_poll(payload: dict, api_key: str, max_wait: int = 600) -> dict:
    data = _http_json(f"{PIAPI_BASE}/task", api_key, payload)
    body = data.get("data") if isinstance(data.get("data"), dict) else data
    task_id = body.get("task_id")
    if not task_id:
        raise RuntimeError(f"no task_id in PiAPI response: {data}")
    deadline = time.time() + max_wait
    while time.time() < deadline:
        time.sleep(5)
        try:
            st = _http_json(f"{PIAPI_BASE}/task/{task_id}", api_key)
        except (urllib.error.URLError, json.JSONDecodeError):
            continue  # transient poll blip — task is still running upstream
        task = st.get("data") if isinstance(st.get("data"), dict) else st
        status = str(task.get("status", "")).lower()
        if status in ("completed", "success", "done"):
            return task.get("output") or task.get("result") or {}
        if status in ("failed", "error"):
            raise RuntimeError(f"task {task_id} failed: {json.dumps(task.get('error') or task)[:300]}")
    raise RuntimeError(f"task {task_id} timed out after {max_wait}s")


def extract_image_url(output: dict) -> str:
    url = output.get("image_url") or (output.get("images") or [None])[0]
    if isinstance(url, dict):
        url = url.get("url")
    if not url:
        raise RuntimeError(f"no image url in output: {json.dumps(output)[:300]}")
    return url


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "python-httpx/0.27.0", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def upload_public(data: bytes, blob_name: str, workdir: Path) -> str:
    local = workdir / blob_name.replace("/", "__")
    local.write_bytes(data)
    subprocess.run(
        ["gsutil", "-q", "-h", f"Cache-Control:{CACHE_CONTROL}",
         "-h", "Content-Type:image/jpeg",
         "cp", "-a", "public-read", str(local), f"gs://{GCS_BUCKET}/{blob_name}"],
        check=True,
    )
    return f"https://storage.googleapis.com/{GCS_BUCKET}/{blob_name}"


# ─── Jobs ───────────────────────────────────────────────────────────────────

def preview_job(kind: str, style: dict, api_key: str, workdir: Path) -> tuple[str, str]:
    payload = {
        "model": FLUX_DEV,
        "task_type": "txt2img",
        "input": {
            "prompt": style["prompt"],
            "negative_prompt": "",
            "width": PREVIEW_W,
            "height": PREVIEW_H,
        },
    }
    blob = BLOB_OVERRIDES.get((kind, style["id"]), f"{style['id']}.jpg")
    output = submit_and_poll(payload, api_key)
    url = upload_public(download(extract_image_url(output)), f"{PREVIEW_PREFIX}/{blob}", workdir)
    return f"{kind}:{style['id']}", url


def example_job(ex_id: str, prompt: str, api_key: str, workdir: Path) -> tuple[str, str]:
    payload = {
        "model": FLUX_KONTEXT,
        "task_type": "kontext",
        "input": {
            "image": ROOM_INPUT,
            "prompt": prompt,
            "width": 1024,
            "height": 1024,
            "steps": 28,
            "seed": -1,
        },
    }
    output = submit_and_poll(payload, api_key)
    url = upload_public(download(extract_image_url(output)), f"{EXAMPLES_PREFIX}/{ex_id}.jpg", workdir)
    return f"examples:{ex_id}", url


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", action="append", choices=[*CATALOG_VARS, "all"], default=None,
                    help="Which style catalogs to render (repeatable).")
    ap.add_argument("--examples", action="store_true", help="Also re-generate rr-01..rr-10 via Kontext.")
    ap.add_argument("--smoke", action="store_true", help="One preview image only, then exit.")
    ap.add_argument("--only", action="append", default=None, help="Restrict to these style ids (repeatable).")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--workdir", default="/tmp/style-previews")
    ap.add_argument("--manifest", default=str(SCRIPT_DIR / "style_previews_manifest.json"))
    args = ap.parse_args()

    api_key = load_env_key("PIAPI_KEY")
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    kinds = args.catalog or []
    if "all" in kinds:
        kinds = list(CATALOG_VARS)

    jobs = []
    for kind in kinds:
        for style in load_catalog(kind):
            if args.only and style["id"] not in args.only:
                continue
            jobs.append(("preview", kind, style))
    if args.smoke:
        jobs = jobs[:1]
    elif args.examples:
        jobs += [("example", ex_id, prompt) for ex_id, prompt in RR_EXAMPLES]

    if not jobs:
        ap.error("nothing to do — pass --catalog and/or --examples")

    print(f"{len(jobs)} generations (flux dev previews @$0.015, kontext examples ~$0.02-0.04)")
    results: dict[str, str] = {}
    failures: list[str] = []

    def run(job) -> tuple[str, str]:
        if job[0] == "preview":
            return preview_job(job[1], job[2], api_key, workdir)
        return example_job(job[1], job[2], api_key, workdir)

    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(args.workers) as pool:
        futs = {pool.submit(run, j): j for j in jobs}
        for fut in concurrent.futures.as_completed(futs):
            job = futs[fut]
            label = f"{job[1]}:{job[2]['id']}" if job[0] == "preview" else f"examples:{job[1]}"
            try:
                key, url = fut.result()
                results[key] = url
                print(f"  ✓ {key}  -> {url}")
            except Exception as e:
                failures.append(label)
                print(f"  ✗ {label}: {e}")

    Path(args.manifest).write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print(f"\n{len(results)} ok, {len(failures)} failed in {time.time() - t0:.0f}s — manifest: {args.manifest}")
    if failures:
        print("failed:", ", ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
