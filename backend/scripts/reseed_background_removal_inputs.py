#!/usr/bin/env python3
"""
Re-seed background_removal Materials with logically-paired before/after URLs.

Why this exists
===============
`generate_background_removal()` in `main_pregenerate.py` runs the flow
T2I-on-pure-white-background → PiAPI remove_bg. The T2I step prompts include
"pure #FFFFFF seamless background" so the input is **already** clean. After
removeBG the visible difference at thumbnail size is near-zero, so the
homepage / showcase preview shows two near-identical images and visitors
think the BG-removal tool does nothing.

The repo already ships hand-curated, real-photo, with-background product
shots at `gs://vidgo-media-vidgo-ai/examples/bg/{subject}.png`, paired with
their cutout result at `gs://vidgo-media-vidgo-ai/examples/fx/{subject}.png`.
This script rewrites every existing background_removal Material row so
input_image_url points at the paired `bg/` image and result_image_url points
at the paired `fx/` cutout. The visible before/after on the homepage / demo
endpoints then becomes a real "messy background → clean cutout" pair.

Pairing strategy
================
Materials are matched to a curated subject by their existing prompt text
(falls back to round-robin distribution across subjects when no keyword
matches). Subjects available: bento, bubbletea, cake, fried-chicken, soap.

Usage
=====
  # Dry run (no DB writes):
  python -m scripts.reseed_background_removal_inputs --dry-run

  # Real run:
  python -m scripts.reseed_background_removal_inputs

Running on production (Cloud Run Job)
=====================================
  gcloud run jobs deploy vidgo-bg-reseed \\
    --image=asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images/vidgo-backend:latest \\
    --project=vidgo-ai --region=asia-east1 \\
    --vpc-connector=vidgo-connector --vpc-egress=all-traffic \\
    --service-account=vidgo-backend@vidgo-ai.iam.gserviceaccount.com \\
    --set-env-vars=GCS_BUCKET=vidgo-media-vidgo-ai \\
    --set-secrets=DATABASE_URL=DATABASE_URL:latest \\
    --command=python \\
    --args=-m,scripts.reseed_background_removal_inputs

  gcloud run jobs execute vidgo-bg-reseed \\
    --project=vidgo-ai --region=asia-east1 --wait

Requirements
============
  - DATABASE_URL env var
  - Network route to Cloud SQL (VPC connector when on Cloud Run)
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Optional

sys.path.insert(0, "/app")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.material import Material, MaterialStatus, ToolType

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("reseed_bg")

GCS_BASE = "https://storage.googleapis.com/vidgo-media-vidgo-ai/examples"

# Curated subjects available in examples/bg/ AND examples/fx/.
# Order matters: when a Material row's prompt doesn't match any keyword AND
# its topic doesn't either, we round-robin across this list so we don't pile
# every row onto bubbletea.
SUBJECTS = ["bubbletea", "fried-chicken", "bento", "cake", "soap"]

# prompt-keyword → subject. Substring match against the Material's prompt
# (case-insensitive). The fallback is round-robin via SUBJECTS.
KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("bubble", "boba", "tapioca", "milk tea", "fruit tea", "coffee", "latte", "drink", "iced", "cup"), "bubbletea"),
    (("chicken", "fried", "scallion", "pancake", "squid", "skewer", "egg tart", "snack"), "fried-chicken"),
    (("bento", "rice", "noodle", "meal", "lunch box", "lunch", "soup"), "bento"),
    (("cake", "tart", "dessert", "pineapple cake", "shaved ice", "pastry"), "cake"),
    (("soap", "candle", "tote", "cleaning", "packaging", "container", "bag", "kraft"), "soap"),
]

# topic → subject. Checked BEFORE the prompt-keyword pass so a row tagged
# topic='desserts' gets `cake` (not `bubbletea` from a "milk tea" mention in
# its prompt). This was the root cause of the 2026-05-17 audit where the
# same `bubbletea.png` was attached to topics `desserts`, `snacks`,
# `general`, etc., producing visible image↔topic mismatches in
# /admin/materials.
TOPIC_TO_SUBJECT: dict[str, str] = {
    "drinks":      "bubbletea",
    "beverages":   "bubbletea",
    "drink":       "bubbletea",
    "tea":         "bubbletea",
    "coffee":      "bubbletea",
    "snacks":      "fried-chicken",
    "snack":       "fried-chicken",
    "fried":       "fried-chicken",
    "meals":       "bento",
    "meal":        "bento",
    "lunch":       "bento",
    "rice":        "bento",
    "desserts":    "cake",
    "dessert":     "cake",
    "bakery":      "cake",
    "pastry":      "cake",
    "packaging":   "soap",
    "container":   "soap",
    "equipment":   "soap",
    "ingredients": "soap",
    "signage":     "soap",
}


def pick_subject(topic: str | None, prompt: str, fallback_index: int) -> str:
    # Topic match first — the explicit category dominates over heuristic
    # keyword sniffing of the prompt text.
    t = (topic or "").lower().strip()
    if t in TOPIC_TO_SUBJECT:
        return TOPIC_TO_SUBJECT[t]
    text = (prompt or "").lower()
    for kws, subj in KEYWORDS:
        if any(kw in text for kw in kws):
            return subj
    return SUBJECTS[fallback_index % len(SUBJECTS)]


def is_seeded_clean_background(input_url: str | None) -> bool:
    """Heuristic: a piapi_*.png input means the seed flow generated a clean
    studio shot before BG removal — exactly the rows we want to repair."""
    if not input_url:
        return True
    return "/piapi_" in input_url or "img.theapi.app" in input_url or input_url.startswith("/static/")


async def reseed(session: AsyncSession, dry_run: bool) -> None:
    stmt = (
        select(Material)
        .where(Material.tool_type == ToolType.BACKGROUND_REMOVAL)
        .where(Material.status.in_([MaterialStatus.APPROVED, MaterialStatus.FEATURED, MaterialStatus.PENDING]))
    )
    rows = (await session.execute(stmt)).scalars().all()
    logger.info("Found %d background_removal materials to inspect", len(rows))

    updated = 0
    skipped = 0
    for i, mat in enumerate(rows):
        prompt_text = (mat.prompt_en or mat.prompt_zh or "")
        subject = pick_subject(mat.topic, prompt_text, i)
        new_input = f"{GCS_BASE}/bg/{subject}.png"
        new_output = f"{GCS_BASE}/fx/{subject}.png"

        # Skip rows that already point at the curated pair.
        if mat.input_image_url == new_input and mat.result_image_url == new_output:
            skipped += 1
            continue

        # Only repair seeded rows (T2I → removeBG flow). User-uploaded rows
        # have meaningful inputs that we should not overwrite.
        if mat.source and getattr(mat.source, "value", str(mat.source)).lower() == "user":
            skipped += 1
            continue
        if not is_seeded_clean_background(mat.input_image_url):
            skipped += 1
            continue

        old_input = mat.input_image_url or "(none)"
        old_output = mat.result_image_url or "(none)"
        action = "WOULD UPDATE" if dry_run else "UPDATING"
        logger.info(
            "%s [%s] subject=%s\n   input  %s -> %s\n   output %s -> %s",
            action,
            str(mat.id)[:8],
            subject,
            old_input[-60:],
            new_input,
            old_output[-60:],
            new_output,
        )

        if not dry_run:
            mat.input_image_url = new_input
            mat.result_image_url = new_output
            # Match the watermark/thumbnail URL too so the demo response is
            # consistent. The cutout is a transparent PNG with no need for a
            # watermark — point at the same fx/ asset.
            mat.result_watermarked_url = new_output
            mat.thumbnail_url = new_output
            updated += 1

    if not dry_run:
        await session.commit()

    logger.info("Done. Updated=%d  Skipped=%d  Total=%d  (dry_run=%s)", updated, skipped, len(rows), dry_run)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Show planned changes without writing.")
    args = parser.parse_args()

    if not os.getenv("DATABASE_URL"):
        logger.error("DATABASE_URL not set")
        return 2

    async with AsyncSessionLocal() as session:
        await reseed(session, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
