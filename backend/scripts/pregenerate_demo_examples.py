#!/usr/bin/env python3
"""
pregenerate_demo_examples.py
============================

Generate ONE real example per dropdown-preset prompt (UNMODIFIED), in BOTH
English and Traditional Chinese (zh-TW), using the TOP model for each tool,
by calling the REAL provider API (spending real credits ONCE), and store each
result in the demo cache (`materials` table + GCS) so that unpaid users /
visitors can "try" the tool for FREE forever after — without costing us money
per visit.

Tools covered
-------------
  t2i     Text-to-Image   — TOP model: Nano Banana Pro (Gemini 3 Pro Image)
                            presets: prompt_library  tools.premium_image  (pi_###)
                            stored as ToolType.MIDJOURNEY_IMAGINE, input_params.model="nano-banana-pro"
  t2v     Text-to-Video   — TOP visitor-reachable model: Kling V3.0 (omni)
                            presets: prompt_library  tools.short_video    (sv_###)
                            stored as ToolType.SHORT_VIDEO, input_params.model_id="kling_v3"
                            (Short Video page is the only T2V surface visitors can reach today.)
  avatar  AI Avatar       — TOP model: PiAPI Kling Avatar  (A2E is NOT used)
                            presets: prompt_library  tools.ai_avatar      (av_###)
                            ONE head per script-case (cycled, no duplicate (head,case)),
                            SAME head used for the EN and zh-TW render of a case.

Every preset is generated in EN and zh-TW (two real generations per preset),
verbatim from the dropdown — no prompt rewriting.

Safety
------
  * --dry-run          : enumerate + print a credit/USD cost estimate, generate NOTHING.
  * cost confirmation  : prints the estimate and requires --yes (or interactive "yes").
  * idempotent         : skips any (tool, preset, language[, model]) already cached
                         with a result URL, so re-runs never double-spend.
  * persist_to_gcs     : route() re-uploads provider CDN URLs to durable GCS URLs,
                         so we pay once and cache a permanent link.

Run modes
---------
  --mode local  (default): import provider_router + DB directly and generate in-process.
                           Run from the backend/ dir with prod DB + GCS + PIAPI_KEY env set.
  --mode api             : POST each job to the deployed admin pregen endpoint
                           (POST {BACKEND_URL}/api/v1/admin/pregenerate) with X-Admin-Token.
                           Use this to spend from the deployed service's creds/quota.

Examples
--------
  # see what it WOULD do + cost, spend nothing:
  python -m scripts.pregenerate_demo_examples --tool t2i,t2v,avatar --mode local --dry-run

  # actually generate the first 3 presets of each tool, locally, no prompt:
  python -m scripts.pregenerate_demo_examples --tool avatar --mode local --limit 3 --yes

  # full run against the deployed service:
  python -m scripts.pregenerate_demo_examples --tool t2i,t2v,avatar --mode api --yes
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pregenerate_demo_examples")

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

# The DROPDOWN source the visitor picks from. Locally we read the FRONTEND JSON
# (the real dropdown); inside the backend Docker image (Cloud Run Job) the
# frontend file isn't present, so we fall back to the SYNCED backend mirror at
# app/data/prompt_library.json (kept in lock-step — see the prompt-library sync).
# Override the path explicitly with PROMPT_LIBRARY_JSON.
def _resolve_prompt_lib() -> Path:
    env = os.getenv("PROMPT_LIBRARY_JSON")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "frontend-vue" / "src" / "data" / "prompt_library.json",  # local dev
        here.parents[1] / "app" / "data" / "prompt_library.json",                   # backend image
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


PROMPT_LIBRARY_JSON = _resolve_prompt_lib()

# The 6 curated head-and-shoulders portraits that pass Kling Avatar's face
# detector (same set the live UI + on-demand generator use). One head is bound
# to each script-case; both language renders of a case reuse that head.
_GCS_AVATARS = "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/avatars"
AVATAR_HEADS: List[Tuple[str, str]] = [
    ("female-1", f"{_GCS_AVATARS}/female-1.png"),
    ("male-1", f"{_GCS_AVATARS}/male-1.png"),
    ("female-2", f"{_GCS_AVATARS}/female-2.png"),
    ("male-2", f"{_GCS_AVATARS}/male-2.png"),
    ("female-3", f"{_GCS_AVATARS}/female-3.png"),
    ("male-3", f"{_GCS_AVATARS}/male-3.png"),
]

LANGUAGES: List[str] = ["en", "zh-TW"]

# Per-tool plan. `lib_topic` is the prompt_library tools.<key>; `credits` is the
# approximate per-call credit cost for the printed estimate.
TOOL_PLANS: Dict[str, Dict[str, Any]] = {
    "t2i": {
        "lib_topic": "premium_image",     # pi_### — 40 image prompts
        "tool_type": "midjourney_imagine",
        "media": "image",
        "model": os.getenv("PREGEN_T2I_MODEL", "nano-banana-pro"),
        "credits": 8,
    },
    "t2v": {
        "lib_topic": "short_video",       # sv_### — Short Video page (only visitor-reachable T2V)
        "tool_type": "short_video",
        "media": "video",
        "model": os.getenv("PREGEN_T2V_MODEL", "kling_v3"),
        "credits": 130,
    },
    "avatar": {
        "lib_topic": "ai_avatar",         # av_### — 40 script cases
        "tool_type": "ai_avatar",
        "media": "video",
        "model": "kling",                 # PiAPI Kling Avatar
        "credits": 80,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Preset loading (verbatim dropdown prompts)
# ─────────────────────────────────────────────────────────────────────────────

def load_presets(lib_topic: str) -> List[Dict[str, str]]:
    """Return [{id, en, zh}] for a prompt_library topic, verbatim (no rewriting)."""
    if not PROMPT_LIBRARY_JSON.exists():
        raise FileNotFoundError(
            f"prompt library not found at {PROMPT_LIBRARY_JSON} — set PROMPT_LIBRARY_JSON"
        )
    data = json.loads(PROMPT_LIBRARY_JSON.read_text(encoding="utf-8"))
    tools = data.get("tools", {})
    topic = tools.get(lib_topic)
    if not topic:
        raise KeyError(
            f"prompt_library has no tools.{lib_topic} (available: {list(tools.keys())})"
        )
    presets: List[Dict[str, str]] = []
    for p in topic.get("prompts", []):
        pid, en, zh = p.get("id"), p.get("en"), p.get("zh")
        if pid and en and zh:
            presets.append({"id": pid, "en": en, "zh": zh})
    return presets


def prompt_for(preset: Dict[str, str], language: str) -> str:
    """The EXACT string the frontend submits for this language (zh-* → zh, else en)."""
    return preset["zh"] if str(language).lower().startswith("zh") else preset["en"]


# ─────────────────────────────────────────────────────────────────────────────
# Job planning
# ─────────────────────────────────────────────────────────────────────────────

class Job:
    """One generation: a (tool, preset, language[, head]) unit of work."""

    def __init__(self, tool: str, plan: Dict[str, Any], preset: Dict[str, str],
                 language: str, head: Optional[Tuple[str, str]] = None):
        self.tool = tool
        self.plan = plan
        self.preset = preset
        self.language = language
        self.head = head  # (avatar_id, url) for avatar only
        self.prompt = prompt_for(preset, language)

    @property
    def topic(self) -> str:
        return self.preset["id"]

    @property
    def input_params(self) -> Dict[str, Any]:
        if self.tool == "t2v":
            return {"model_id": self.plan["model"]}
        if self.tool == "t2i":
            return {"model": self.plan["model"]}
        if self.tool == "avatar":
            return {"avatar_id": self.head[0], "language": self.language, "script": self.prompt}
        return {}

    def label(self) -> str:
        extra = f" head={self.head[0]}" if self.head else ""
        return f"{self.tool}/{self.topic}/{self.language}{extra}"


def plan_jobs(tools: List[str], limit: Optional[int]) -> List[Job]:
    jobs: List[Job] = []
    for tool in tools:
        plan = TOOL_PLANS[tool]
        presets = load_presets(plan["lib_topic"])
        if limit:
            presets = presets[:limit]
        for idx, preset in enumerate(presets):
            head = AVATAR_HEADS[idx % len(AVATAR_HEADS)] if tool == "avatar" else None
            for language in LANGUAGES:
                jobs.append(Job(tool, plan, preset, language, head))
    return jobs


def print_estimate(jobs: List[Job]) -> None:
    by_tool: Dict[str, Tuple[int, int]] = {}
    for j in jobs:
        n, c = by_tool.get(j.tool, (0, 0))
        by_tool[j.tool] = (n + 1, c + int(j.plan["credits"]))
    logger.info("─" * 64)
    logger.info("COST ESTIMATE (real credits will be spent on a non-dry run):")
    total_n, total_c = 0, 0
    for tool, (n, c) in by_tool.items():
        logger.info(f"  {tool:7s}: {n:4d} generations  ~{c:6d} credits")
        total_n += n
        total_c += c
    logger.info(f"  {'TOTAL':7s}: {total_n:4d} generations  ~{total_c:6d} credits")
    logger.info("  (idempotent: already-cached presets are skipped, so real spend ≤ this)")
    logger.info("─" * 64)


# ─────────────────────────────────────────────────────────────────────────────
# LOCAL mode — import provider_router + DB and generate in-process
# ─────────────────────────────────────────────────────────────────────────────

async def _already_cached(session, tool_type, topic: str, language: str,
                          input_params: Dict[str, Any], media: str) -> bool:
    """Idempotency: a row for this (tool_type, topic, language[, model]) with a result already exists."""
    from sqlalchemy import select, and_
    from app.models.material import Material, MaterialStatus

    result_col = Material.result_video_url if media == "video" else Material.result_image_url
    conds = [
        Material.tool_type == tool_type,
        Material.topic == topic,
        Material.language == language,
        Material.is_active.is_(True),
        Material.status.in_([MaterialStatus.APPROVED, MaterialStatus.FEATURED]),
        result_col.isnot(None),
    ]
    # short_video / midjourney also key on the model in input_params
    model_key = "model_id" if tool_type.value == "short_video" else ("model" if tool_type.value == "midjourney_imagine" else None)
    if model_key and input_params.get(model_key):
        conds.append(Material.input_params[model_key].astext == str(input_params[model_key]))
    row = (await session.execute(select(Material.id).where(and_(*conds)).limit(1))).first()
    return row is not None


def _route_params(job: Job) -> Tuple[str, Dict[str, Any]]:
    """Map a job to (TaskType name, params) for provider_router.route()."""
    if job.tool == "t2i":
        # Nano Banana Pro via the T2I branch (reads aspect_ratio directly).
        return "T2I", {
            "prompt": job.prompt,
            "model": job.plan["model"],          # "nano-banana-pro"
            "aspect_ratio": "1:1",
            "resolution": "2K",
        }
    if job.tool == "t2v":
        # Kling V3.0 (omni) text-to-video — the top model the Short Video demo serves.
        return "KLING_VIDEO", {
            "prompt": job.prompt,
            "tier": "omni",
            "aspect_ratio": "16:9",
            "duration": 5,
            "image_url": None,                   # None ⇒ pure text-to-video
            "negative_prompt": "",
            "enable_audio": True,
        }
    # avatar — PiAPI Kling Avatar
    return "AVATAR", {
        "image_url": job.head[1],
        "script": job.prompt,
        "language": job.language,
        "duration": 10,
        "resolution": "720p",
        "aspect_ratio": "9:16",
        "mode": "pro",                           # top quality
    }


async def run_local(jobs: List[Job], dry_run: bool) -> None:
    from app.providers.provider_router import get_provider_router, TaskType
    from app.core.database import AsyncSessionLocal
    from app.models.material import (
        Material, ToolType, MaterialSource, MaterialStatus,
    )

    router = get_provider_router()
    ok = skipped = failed = 0

    async with AsyncSessionLocal() as session:
        for i, job in enumerate(jobs, 1):
            tool_type = ToolType(job.plan["tool_type"])
            media = job.plan["media"]

            if await _already_cached(session, tool_type, job.topic, job.language, job.input_params, media):
                logger.info(f"[{i}/{len(jobs)}] SKIP (cached): {job.label()}")
                skipped += 1
                continue

            if dry_run:
                logger.info(f"[{i}/{len(jobs)}] WOULD generate: {job.label()} :: {job.prompt[:70]}…")
                continue

            task_name, params = _route_params(job)
            logger.info(f"[{i}/{len(jobs)}] generating {job.label()} via {task_name} ({job.plan['model']})…")
            try:
                result = await router.route(
                    TaskType[task_name], params, user_tier="pro", persist_to_gcs=True,
                )
                if not result or result.get("success") is False:
                    raise RuntimeError(result.get("error") if result else "no result")
                out = result.get("output", {})
                url = out.get("video_url") if media == "video" else out.get("image_url")
                if not url:
                    raise RuntimeError(f"no {media} url in result")
            except Exception as e:
                logger.error(f"   FAILED {job.label()}: {e}")
                failed += 1
                continue

            mat = Material(
                tool_type=tool_type,
                topic=job.topic,
                language=job.language,
                source=MaterialSource.SEED,
                status=MaterialStatus.APPROVED,
                prompt=job.prompt,
                prompt_en=job.preset["en"],
                prompt_zh=job.preset["zh"],
                effect_prompt=(job.prompt if job.tool == "t2v" else None),
                input_params=job.input_params,
                result_image_url=(url if media == "image" else None),
                result_video_url=(url if media == "video" else None),
                # Free users receive the watermarked field; we have no separate
                # watermark render here, so the result doubles as the teaser
                # (matches the existing avatar/short_video pregen behavior).
                result_watermarked_url=url,
                quality_score=0.9,
                is_featured=True,
                is_active=True,
            )
            session.add(mat)
            await session.commit()
            logger.info(f"   ✓ cached {job.label()} → {url[:80]}")
            ok += 1

    logger.info("─" * 64)
    logger.info(f"DONE (local). generated={ok}  skipped={skipped}  failed={failed}")


# ─────────────────────────────────────────────────────────────────────────────
# API mode — POST each job to the deployed admin pregen endpoint
# ─────────────────────────────────────────────────────────────────────────────

async def run_api(jobs: List[Job], dry_run: bool) -> None:
    import httpx

    base = os.getenv("BACKEND_URL", "").rstrip("/")
    token = os.getenv("ADMIN_PREGEN_TOKEN", "")
    if not base or not token:
        logger.error("API mode requires BACKEND_URL and ADMIN_PREGEN_TOKEN env vars.")
        logger.error("NOTE: the admin pregen endpoint must exist — see the 'remaining work' "
                     "section in the PR description (POST /api/v1/admin/pregenerate).")
        sys.exit(2)

    url = f"{base}/api/v1/admin/pregenerate"
    ok = failed = 0
    async with httpx.AsyncClient(timeout=2400.0) as client:
        for i, job in enumerate(jobs, 1):
            task_name, params = _route_params(job)
            payload = {
                "tool_type": job.plan["tool_type"],
                "topic": job.topic,
                "language": job.language,
                "task": task_name,
                "params": params,
                "input_params": job.input_params,
            }
            if dry_run:
                logger.info(f"[{i}/{len(jobs)}] WOULD POST: {job.label()}")
                continue
            logger.info(f"[{i}/{len(jobs)}] POST {job.label()}…")
            try:
                r = await client.post(url, json=payload, headers={"X-Admin-Token": token})
                r.raise_for_status()
                ok += 1
                logger.info(f"   ✓ {r.json().get('result_url', 'ok')}")
            except Exception as e:
                logger.error(f"   FAILED {job.label()}: {e}")
                failed += 1
    logger.info(f"DONE (api). ok={ok} failed={failed}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Pregenerate demo examples (T2I / T2V / AI Avatar).")
    ap.add_argument("--tool", default="t2i,t2v,avatar",
                    help="comma list of: t2i,t2v,avatar (default: all)")
    ap.add_argument("--mode", choices=["local", "api"], default="local")
    ap.add_argument("--limit", type=int, default=None,
                    help="only the first N presets per tool (for testing)")
    ap.add_argument("--dry-run", action="store_true", help="enumerate + estimate only, spend nothing")
    ap.add_argument("--yes", action="store_true", help="skip the interactive cost confirmation")
    return ap.parse_args()


async def amain() -> None:
    args = parse_args()
    tools = [t.strip() for t in args.tool.split(",") if t.strip()]
    bad = [t for t in tools if t not in TOOL_PLANS]
    if bad:
        logger.error(f"unknown tool(s): {bad}. valid: {list(TOOL_PLANS)}")
        sys.exit(2)

    jobs = plan_jobs(tools, args.limit)
    if not jobs:
        logger.error("no jobs planned (empty preset set?)")
        sys.exit(1)

    logger.info(f"Planned {len(jobs)} generations across tools={tools} "
                f"({len(LANGUAGES)} languages each) from {PROMPT_LIBRARY_JSON.name}")
    print_estimate(jobs)

    if not args.dry_run and not args.yes:
        try:
            ans = input("This will spend REAL credits. Type 'yes' to proceed: ").strip().lower()
        except EOFError:
            ans = ""
        if ans != "yes":
            logger.info("aborted (no confirmation).")
            return

    if args.mode == "local":
        await run_local(jobs, args.dry_run)
    else:
        await run_api(jobs, args.dry_run)


if __name__ == "__main__":
    asyncio.run(amain())
