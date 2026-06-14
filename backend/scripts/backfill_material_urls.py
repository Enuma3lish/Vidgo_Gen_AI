#!/usr/bin/env python3
"""
Backfill Material URLs — one-shot repair pass for F-012.

Why this exists
===============
The Material DB on production has rows where:
  - `input_image_url`   points to PiAPI temp CDN (`https://img.theapi.app/temp/...`)
    which expires after ~14 days and is currently 404-ing.
  - `result_image_url`, `result_watermarked_url`, `thumbnail_url` point to
    `/static/generated/rembg_*.png` — local Cloud Run filesystem paths that
    do not exist on the deployed container (404 from both frontend and
    backend hosts).

This script walks every Material row with a broken URL and tries to persist
the content to the project's GCS bucket, then rewrites the row to use the
permanent GCS URL. Rows that cannot be rescued (temp URL already expired,
local file missing) are marked `status=PENDING` so an admin can regenerate
them instead of serving dead links.

The going-forward fix lives in `main_pregenerate.py` — this script is purely
for the existing broken rows. Once this runs green, `main_pregenerate.py`'s
new `_to_gcs_url` + GCS-backed watermark path will prevent recurrence.

Usage
=====
  # Dry run — inspect what would change, no DB writes
  python -m scripts.backfill_material_urls --dry-run

  # Limit to a single tool type
  python -m scripts.backfill_material_urls --tool background_removal

  # Real run, committing changes in batches of 50
  python -m scripts.backfill_material_urls --batch-size 50

Running on production (Cloud Run)
=================================
This script must NOT be run from a laptop against the production DB without
VPC access. The recommended path is a Cloud Run Job with the same image as
the backend service:

  1. Build the backend image (the project's normal Cloud Build flow works):
       gcloud builds submit --config=cloudbuild.yaml --project=vidgo-ai

  2. Deploy a one-shot Job that runs this script:
       gcloud run jobs deploy vidgo-material-backfill \\
         --image=asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images/backend:latest \\
         --project=vidgo-ai --region=asia-east1 \\
         --vpc-connector=vidgo-connector \\
         --service-account=vidgo-backend@vidgo-ai.iam.gserviceaccount.com \\
         --set-env-vars=GCS_BUCKET=vidgo-media-vidgo-ai \\
         --set-secrets=DATABASE_URL=DATABASE_URL:latest \\
         --command=python \\
         --args=-m,scripts.backfill_material_urls,--dry-run \\
         --task-timeout=30m

  3. Execute the dry-run first to review the plan:
       gcloud run jobs execute vidgo-material-backfill \\
         --project=vidgo-ai --region=asia-east1 --wait
       gcloud run jobs executions list \\
         --job=vidgo-material-backfill --project=vidgo-ai --region=asia-east1

  4. Review the logs. When satisfied, update the job to drop --dry-run and
     run again:
       gcloud run jobs update vidgo-material-backfill \\
         --args=-m,scripts.backfill_material_urls \\
         --project=vidgo-ai --region=asia-east1
       gcloud run jobs execute vidgo-material-backfill \\
         --project=vidgo-ai --region=asia-east1 --wait

Requirements
============
  - GCS_BUCKET env var
  - DATABASE_URL env var
  - Service account with `roles/storage.objectAdmin` on the bucket
    (vidgo-backend@vidgo-ai.iam.gserviceaccount.com already has this)
  - Network route to Cloud SQL (via VPC connector on Cloud Run)
"""
import argparse
import asyncio
import logging
import os
import sys
from typing import List, Optional, Tuple

# Add app to path (same as main_pregenerate.py)
sys.path.insert(0, "/app")

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.material import Material, MaterialStatus
from app.services.gcs_storage_service import GCSStorageService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger("backfill_material_urls")


# URL patterns we consider "broken" and in need of repair.
# Anything matching any of these must be migrated to GCS or nulled out.
BROKEN_PREFIXES = (
    "/static/",
    "https://img.theapi.app/temp/",
    "http://img.theapi.app/temp/",
    "https://images.pollo.ai/",  # Pollo temp CDN (if in use)
)

GCS_PREFIX = "https://storage.googleapis.com/"


def is_broken(url: Optional[str]) -> bool:
    if not url:
        return False
    if url.startswith(GCS_PREFIX):
        return False
    return url.startswith(BROKEN_PREFIXES)


async def resolve_url_to_gcs(
    gcs: GCSStorageService,
    url: Optional[str],
    media_type: str,
) -> Tuple[Optional[str], str]:
    """
    Try to convert a broken URL into a permanent GCS URL.

    Returns (new_url, status) where status is one of:
      - "already_gcs"   — URL was already on GCS, no action
      - "no_url"        — field was None/empty
      - "persisted"     — successfully rescued and re-uploaded
      - "local_missing" — local /static/ file is gone, cannot rescue
      - "temp_404"      — external URL returned 404 / unreachable
      - "error"         — any other failure
    """
    if not url:
        return None, "no_url"
    if url.startswith(GCS_PREFIX):
        return url, "already_gcs"

    # Local /static/ path — read from disk if the file still exists on THIS
    # container. In production Cloud Run this will almost always fail
    # (the files were written by a different container revision that's gone),
    # which is exactly why those rows are broken in the first place.
    if url.startswith("/static/"):
        from pathlib import Path as _P
        local_path = _P(f"/app{url}")
        if not local_path.exists():
            return None, "local_missing"
        try:
            data = local_path.read_bytes()
            ext = local_path.suffix or ".png"
            content_type = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".mp4": "video/mp4",
                ".webm": "video/webm",
            }.get(ext.lower(), "application/octet-stream")
            blob_name = f"backfill/{media_type}/{local_path.stem}{ext}"
            new_url = gcs.upload_public(data, blob_name, content_type=content_type)
            return new_url, "persisted"
        except Exception as e:
            logger.error(f"  local upload failed for {url}: {e}")
            return None, "error"

    # External temp URL — try to download + re-upload.
    try:
        new_url = await gcs.persist_url(source_url=url, media_type=media_type)
        # persist_url returns the source URL unchanged on fetch failure.
        if new_url == url:
            return None, "temp_404"
        return new_url, "persisted"
    except Exception as e:
        logger.error(f"  persist_url failed for {url}: {e}")
        return None, "error"


async def process_material(
    gcs: GCSStorageService,
    material: Material,
    dry_run: bool,
) -> dict:
    """
    Evaluate one Material row and (optionally) rewrite its URL fields.

    Returns a result dict for the summary.
    """
    changes: dict = {"id": str(material.id), "tool": material.tool_type.value, "fields": {}}
    fields_to_check = [
        ("input_image_url", "image"),
        ("result_image_url", "image"),
        ("result_video_url", "video"),
        ("result_watermarked_url", "image"),
    ]
    # result_thumbnail_url exists on the model but is rarely populated
    if hasattr(material, "result_thumbnail_url"):
        fields_to_check.append(("result_thumbnail_url", "image"))

    any_rescue_failed = False

    for field, media_type in fields_to_check:
        old = getattr(material, field, None)
        if not is_broken(old):
            continue

        new_url, status = await resolve_url_to_gcs(gcs, old, media_type)
        changes["fields"][field] = {"old": old, "new": new_url, "status": status}

        if status in ("local_missing", "temp_404", "error"):
            any_rescue_failed = True

        if not dry_run and new_url and new_url != old:
            setattr(material, field, new_url)
        elif not dry_run and status in ("local_missing", "temp_404"):
            # Unrescuable — null out so the row doesn't keep serving a dead link.
            setattr(material, field, None)

    # If ALL critical output URLs are dead, flip the row back to PENDING so
    # admin can regenerate. Don't touch rows that still have at least one
    # working result URL.
    result_fields = [
        getattr(material, "result_image_url", None),
        getattr(material, "result_video_url", None),
        getattr(material, "result_watermarked_url", None),
    ]
    still_has_result = any(
        (u and (u.startswith(GCS_PREFIX) or not is_broken(u))) for u in result_fields
    )
    if any_rescue_failed and not still_has_result:
        changes["marked_pending"] = True
        if not dry_run and material.status == MaterialStatus.APPROVED:
            material.status = MaterialStatus.PENDING

    return changes


async def run_verify(tool: Optional[str]) -> int:
    """
    Read-only gate: return 0 if no APPROVED Material row has a broken URL,
    return 1 otherwise. No GCS calls, no DB writes. Intended for the Docker
    entrypoint to refuse startup on dirty data.
    """
    async with AsyncSessionLocal() as session:  # type: AsyncSession
        like_any_broken = or_(
            *[
                getattr(Material, f).like(p + "%")
                for f in (
                    "input_image_url",
                    "result_image_url",
                    "result_video_url",
                    "result_watermarked_url",
                )
                for p in BROKEN_PREFIXES
            ]
        )
        q = select(Material).where(
            like_any_broken,
            Material.status == MaterialStatus.APPROVED,
        )
        if tool:
            from app.models.material import ToolType
            try:
                q = q.where(Material.tool_type == ToolType(tool))
            except ValueError:
                logger.error(f"Unknown tool_type: {tool}")
                return 2
        rows: List[Material] = (await session.execute(q)).scalars().all()
        total = len(rows)

    if total == 0:
        logger.info("VERIFY OK — no APPROVED Material rows have broken URLs")
        return 0

    # Report a breakdown by field + sample URLs so operators can see exactly
    # why the gate failed.
    by_field: dict = {}
    samples: dict = {}
    for mat in rows:
        for f in ("input_image_url", "result_image_url", "result_video_url", "result_watermarked_url"):
            url = getattr(mat, f, None)
            if is_broken(url):
                by_field[f] = by_field.get(f, 0) + 1
                if f not in samples:
                    samples[f] = url

    logger.error(f"VERIFY FAILED — {total} APPROVED Material row(s) with broken URLs")
    for f, count in sorted(by_field.items()):
        logger.error(f"  {f}: {count}  (e.g. {samples[f][:100]})")
    logger.error(
        "Run `python -m scripts.backfill_material_urls` (no --dry-run) to migrate "
        "rescuable rows and flip unrescuable rows to PENDING."
    )
    return 1


async def run_backfill(
    dry_run: bool,
    tool: Optional[str],
    batch_size: int,
    limit: Optional[int],
) -> None:
    gcs = GCSStorageService()
    if not gcs.enabled:
        logger.error("GCS_BUCKET not set — cannot run backfill")
        sys.exit(1)
    logger.info(f"GCS bucket: {gcs.bucket_name}")
    logger.info(f"Mode: {'DRY RUN (no DB writes)' if dry_run else 'COMMIT'}")
    if tool:
        logger.info(f"Tool filter: {tool}")
    if limit:
        logger.info(f"Row limit:   {limit}")

    summary = {
        "inspected": 0,
        "rewritten": 0,
        "marked_pending": 0,
        "already_clean": 0,
        "status_counts": {},
    }

    async with AsyncSessionLocal() as session:  # type: AsyncSession
        # Build the query: any row with any broken URL
        like_any_broken = or_(
            *[
                getattr(Material, f).like(p + "%")
                for f in (
                    "input_image_url",
                    "result_image_url",
                    "result_video_url",
                    "result_watermarked_url",
                )
                for p in BROKEN_PREFIXES
            ]
        )
        q = select(Material).where(like_any_broken)
        if tool:
            from app.models.material import ToolType
            try:
                q = q.where(Material.tool_type == ToolType(tool))
            except ValueError:
                logger.error(f"Unknown tool_type: {tool}")
                sys.exit(1)
        if limit:
            q = q.limit(limit)

        rows: List[Material] = (await session.execute(q)).scalars().all()
        logger.info(f"Found {len(rows)} rows with at least one broken URL")

        pending = 0
        for i, mat in enumerate(rows, start=1):
            summary["inspected"] += 1
            result = await process_material(gcs, mat, dry_run=dry_run)
            if result["fields"]:
                summary["rewritten"] += 1
                logger.info(
                    f"[{i}/{len(rows)}] {result['tool']} {result['id'][:8]} — "
                    f"{len(result['fields'])} field(s): "
                    f"{ {f: v['status'] for f, v in result['fields'].items()} }"
                )
                for v in result["fields"].values():
                    summary["status_counts"][v["status"]] = (
                        summary["status_counts"].get(v["status"], 0) + 1
                    )
            else:
                summary["already_clean"] += 1
            if result.get("marked_pending"):
                summary["marked_pending"] += 1

            pending += 1
            if not dry_run and pending >= batch_size:
                await session.commit()
                pending = 0

        if not dry_run and pending > 0:
            await session.commit()

    logger.info("=" * 60)
    logger.info("BACKFILL SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Inspected:       {summary['inspected']}")
    logger.info(f"Rewritten:       {summary['rewritten']}")
    logger.info(f"Marked PENDING:  {summary['marked_pending']}")
    logger.info(f"Already clean:   {summary['already_clean']}")
    logger.info("Per-field status breakdown:")
    for status, count in sorted(summary["status_counts"].items()):
        logger.info(f"  {status}: {count}")
    if dry_run:
        logger.info("")
        logger.info("DRY RUN — no database writes were made.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--dry-run", action="store_true", help="Do not commit changes")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Read-only gate: exit 0 if all APPROVED rows have clean URLs, exit 1 otherwise. "
        "Used by docker_entrypoint.sh to refuse startup on broken data.",
    )
    parser.add_argument("--tool", type=str, default=None, help="Limit to one tool_type (e.g. background_removal)")
    parser.add_argument("--batch-size", type=int, default=50, help="Commit every N rows")
    parser.add_argument("--limit", type=int, default=None, help="Max rows to process")
    args = parser.parse_args()

    if args.verify:
        rc = asyncio.run(run_verify(tool=args.tool))
        sys.exit(rc)

    asyncio.run(
        run_backfill(
            dry_run=args.dry_run,
            tool=args.tool,
            batch_size=args.batch_size,
            limit=args.limit,
        )
    )


if __name__ == "__main__":
    main()
