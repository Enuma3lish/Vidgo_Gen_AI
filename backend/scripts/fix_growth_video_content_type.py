#!/usr/bin/env python3
"""
One-off backfill: repair growth videos mis-stored in GCS as images.

Background
----------
Before the 2026-06-02 fix, ``provider_router._task_to_media_type`` did not
classify ``TaskType.KLING_VIDEO`` as video, so the floor-plan→3D growth MP4 was
persisted to GCS under ``media_type="image"``. When the Kling CDN served the
file as ``application/octet-stream``, ``persist_url`` fell back to ``image/png``
content-type. The object IS a valid MP4, but GCS serves it with an image
Content-Type, so the frontend ``<video>`` element silently refuses to play it —
the result appears blank with no error.

What this does
--------------
Scans the bucket prefix(es) where those objects live (default
``generated/image/``), reads each object's first bytes, and for any object whose
bytes are actually a video (MP4/MOV/WebM) but whose stored Content-Type is NOT a
video type, rewrites the Content-Type **in place**. The object name/URL is left
unchanged, so existing references in the DB keep working — only the served
Content-Type is corrected, which is all the browser needs for playback.

Genuine images are detected by magic bytes and never touched. Re-running is
safe and idempotent (objects already served as ``video/*`` are skipped).

Usage
-----
    # dry run (default — reports what WOULD change, mutates nothing)
    python scripts/fix_growth_video_content_type.py

    # actually apply the fix
    python scripts/fix_growth_video_content_type.py --apply

    # options
    --bucket NAME     GCS bucket (default: $GCS_BUCKET)
    --prefix P        Object prefix to scan; repeatable (default: generated/image/)
    --apply           Perform the rewrite (omit for dry-run)

Auth: uses Application Default Credentials (``storage.Client()``), same as the
app. In deploy.sh this runs inside the backend image with the operator's gcloud
ADC mounted.
"""
from __future__ import annotations

import argparse
import os
import sys

try:
    from google.cloud import storage
except ImportError:  # pragma: no cover
    sys.stderr.write("google-cloud-storage is required (it ships in the backend image).\n")
    sys.exit(2)


# Magic-byte sniffers. We only ever PROMOTE an image/octet-stream object to a
# video type, never the reverse, so a false negative is harmless (object left
# as-is) and a false positive is prevented by requiring a real video signature.
def _sniff_video_content_type(head: bytes) -> str | None:
    """Return the correct video Content-Type for ``head`` bytes, or None."""
    if len(head) < 12:
        return None
    # ISO Base Media (MP4/MOV/M4V): a 4-byte box size then the 'ftyp' box tag.
    if head[4:8] == b"ftyp":
        return "video/mp4"
    # WebM / Matroska: EBML header.
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return "video/webm"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair growth videos mis-stored as images in GCS.")
    parser.add_argument("--bucket", default=os.environ.get("GCS_BUCKET"),
                        help="GCS bucket name (default: $GCS_BUCKET)")
    parser.add_argument("--prefix", action="append", default=None,
                        help="Object prefix to scan (repeatable; default: generated/image/)")
    parser.add_argument("--apply", action="store_true",
                        help="Apply the Content-Type rewrite (default: dry-run)")
    args = parser.parse_args()

    if not args.bucket:
        sys.stderr.write("No bucket: pass --bucket or set $GCS_BUCKET. Nothing to do.\n")
        # Exit 0 so a deploy that simply has GCS disabled is not treated as a failure.
        return 0

    prefixes = args.prefix or ["generated/image/"]
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[fix-growth-video] mode={mode} bucket={args.bucket} prefixes={prefixes}")

    client = storage.Client()
    bucket = client.bucket(args.bucket)

    scanned = fixed = skipped_video = skipped_image = errors = 0

    for prefix in prefixes:
        for blob in client.list_blobs(bucket, prefix=prefix):
            scanned += 1
            ct = (blob.content_type or "").lower()
            if ct.startswith("video/"):
                skipped_video += 1
                continue
            try:
                # Range-read only the header; enough to identify the container.
                head = blob.download_as_bytes(start=0, end=31)
            except Exception as exc:  # noqa: BLE001
                errors += 1
                print(f"  ! read failed: {blob.name}: {exc}")
                continue

            correct = _sniff_video_content_type(head)
            if not correct:
                skipped_image += 1  # genuine image (or unknown) — leave untouched
                continue

            print(f"  ~ {blob.name}: {ct or '(none)'} -> {correct}")
            if args.apply:
                try:
                    blob.content_type = correct
                    blob.patch()
                    fixed += 1
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    print(f"  ! patch failed: {blob.name}: {exc}")
            else:
                fixed += 1  # would-fix count in dry-run

    verb = "fixed" if args.apply else "would fix"
    print(
        f"[fix-growth-video] done: scanned={scanned} {verb}={fixed} "
        f"already-video={skipped_video} left-as-image={skipped_image} errors={errors}"
    )
    if not args.apply and fixed:
        print("[fix-growth-video] re-run with --apply to perform the rewrite.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
