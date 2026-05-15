#!/usr/bin/env python3
"""
Mirror every third-party image URL embedded in frontend-vue/src into the
vidgo-media-vidgo-ai GCS bucket so the site no longer depends on
images.unsplash.com / cdn.pixabay.com for hero / topic / demo rendering.

Why: external CDNs occasionally serve images that Chrome's ORB
opaque-response blocker rejects (mismatched MIME, missing CORP), causing
visible-broken images on /topics/* and /gallery. Hosting them ourselves
removes the dependency entirely.

Behavior:
  - Walks `frontend-vue/src` looking for absolute Unsplash + Pixabay URLs.
  - Groups by photo identifier so we upload each photo only once even
    when the codebase requests it at multiple sizes.
  - Downloads each photo (largest variant seen in code) to /tmp.
  - Uploads to gs://vidgo-media-vidgo-ai/mirror/unsplash/<id>.jpg with
    Content-Type=image/jpeg and `cache-control: public, max-age=31536000`.
  - Emits `scripts/gcs/mirror-map.json` mapping every encountered third-
    party URL to its mirrored public GCS URL.
  - Idempotent: re-running skips photos already in the bucket.

The companion script ``apply-mirror.py`` consumes mirror-map.json and
performs the actual in-place replacement in the .vue files.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = ROOT / "frontend-vue" / "src"
MAP_FILE = ROOT / "scripts" / "gcs" / "mirror-map.json"
BUCKET = "vidgo-media-vidgo-ai"
MIRROR_PREFIX = "mirror/unsplash"

URL_RE = re.compile(
    r"https://images\.unsplash\.com/photo-[a-f0-9-]+(?:\?[^\"'\s)>]*)?"
    r"|https://cdn\.pixabay\.com/photo/[^\"'\s)>]+"
)
UNSPLASH_ID_RE = re.compile(r"/photo-([a-f0-9-]+)")


def gather_urls() -> dict[str, str]:
    """Return {photo_id: best_seen_url}. "Best" = the variant requesting
    the largest width so the mirror is at least as crisp as the original."""
    urls_by_id: dict[str, str] = {}
    for path in FRONTEND_SRC.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".vue", ".ts", ".js", ".tsx", ".json"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for match in URL_RE.findall(text):
            id_match = UNSPLASH_ID_RE.search(match)
            if not id_match:
                continue
            photo_id = id_match.group(1)
            prev = urls_by_id.get(photo_id)
            if prev is None or _approx_width(match) > _approx_width(prev):
                urls_by_id[photo_id] = match
    return urls_by_id


def _approx_width(url: str) -> int:
    """Pull `w=` (or `width=`) out of the Unsplash query string; default 800."""
    parsed = urlparse(url)
    for piece in parsed.query.split("&"):
        if piece.startswith("w=") or piece.startswith("width="):
            try:
                return int(piece.split("=", 1)[1])
            except ValueError:
                return 800
    return 800


def download(url: str, dest: Path) -> bool:
    """Fetch with a desktop UA so Unsplash returns the actual image
    instead of an HTML splash page."""
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 vidgo-mirror-bot"})
    try:
        with urlopen(req, timeout=30) as resp:
            data = resp.read()
            dest.write_bytes(data)
            return True
    except Exception as exc:  # noqa: BLE001
        print(f"  download FAILED ({exc})", file=sys.stderr)
        return False


def gcs_upload(local: Path, blob: str, content_type: str = "image/jpeg") -> str:
    """Upload via the gcloud CLI; returns the public URL."""
    target = f"gs://{BUCKET}/{blob}"
    subprocess.run(
        [
            "gcloud", "storage", "cp",
            "--cache-control=public, max-age=31536000",
            f"--content-type={content_type}",
            str(local),
            target,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return f"https://storage.googleapis.com/{BUCKET}/{blob}"


def gcs_exists(blob: str) -> bool:
    """gcloud storage ls returns 0 when the object exists."""
    result = subprocess.run(
        ["gcloud", "storage", "ls", f"gs://{BUCKET}/{blob}"],
        capture_output=True,
    )
    return result.returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only enumerate URLs; don't download or upload",
    )
    args = parser.parse_args()

    urls = gather_urls()
    print(f"Found {len(urls)} unique Unsplash photo IDs across frontend-vue/src")

    mapping: dict[str, str] = {}
    if MAP_FILE.exists():
        try:
            mapping = json.loads(MAP_FILE.read_text())
        except json.JSONDecodeError:
            mapping = {}

    new_count = 0
    skip_count = 0
    fail_count = 0
    with tempfile.TemporaryDirectory(prefix="vidgo-mirror-") as tmp:
        for photo_id, url in sorted(urls.items()):
            blob = f"{MIRROR_PREFIX}/{photo_id}.jpg"
            mirrored_url = f"https://storage.googleapis.com/{BUCKET}/{blob}"

            if args.dry_run:
                print(f"  {photo_id} ← {url}")
                continue

            # Already mirrored? Skip the download.
            if gcs_exists(blob):
                mapping[photo_id] = mirrored_url
                skip_count += 1
                continue

            local = Path(tmp) / f"{photo_id}.jpg"
            print(f"  → mirroring {photo_id}")
            if not download(url, local):
                fail_count += 1
                continue
            try:
                gcs_upload(local, blob)
                mapping[photo_id] = mirrored_url
                new_count += 1
            except subprocess.CalledProcessError as exc:
                print(f"  upload FAILED ({exc})", file=sys.stderr)
                fail_count += 1

    if not args.dry_run:
        MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
        MAP_FILE.write_text(json.dumps(mapping, indent=2, sort_keys=True))
        print(
            f"\nDone. new={new_count} existing={skip_count} failed={fail_count}\n"
            f"Map written to: {MAP_FILE}"
        )


if __name__ == "__main__":
    main()
