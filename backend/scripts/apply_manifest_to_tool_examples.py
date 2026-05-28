"""
apply_manifest_to_tool_examples.py — merge examples_manifest.json into
frontend-vue/src/data/toolExamples.ts as the `thumbnail:` field.

The TS file is hand-edited. To stay safe, this script only injects/updates
`thumbnail: 'url'` lines that follow each entry's `prompt_en: '...'` line
when the (tool_key, example_id) appears in the manifest.

Idempotent — running twice is a no-op.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TS_PATH = REPO_ROOT / "frontend-vue" / "src" / "data" / "toolExamples.ts"
MANIFEST_PATH = Path(__file__).resolve().parent / "examples_manifest.json"


def main():
    if not MANIFEST_PATH.exists():
        print(f"No manifest at {MANIFEST_PATH}", file=sys.stderr)
        sys.exit(1)
    manifest = json.loads(MANIFEST_PATH.read_text())
    # flat lookup: example_id -> url (ids are unique across tools by prefix)
    flat: dict[str, str] = {}
    for tool, entries in manifest.items():
        for ex_id, url in entries.items():
            flat[ex_id] = url
    print(f"Manifest has {len(flat)} thumbnails")

    src = TS_PATH.read_text()
    # Find each entry block:  { id: 'mj-01', ... prompt_en: '...' },
    # and insert thumbnail: '...' before the closing } when missing.
    pattern = re.compile(
        r"\{\s*id:\s*'([^']+)',(?P<body>.*?)\}",
        flags=re.DOTALL,
    )
    inserted = 0
    updated = 0
    skipped = 0

    def replace(match: re.Match) -> str:
        nonlocal inserted, updated, skipped
        ex_id = match.group(1)
        body = match.group("body")
        url = flat.get(ex_id)
        if not url:
            skipped += 1
            return match.group(0)
        thumb_re = re.compile(r"thumbnail:\s*'([^']*)'")
        if thumb_re.search(body):
            existing = thumb_re.search(body).group(1)
            if existing == url:
                skipped += 1
                return match.group(0)
            new_body = thumb_re.sub(f"thumbnail: '{url}'", body)
            updated += 1
            return "{ id: '" + ex_id + "'," + new_body + "}"
        # Insert before the closing brace, after the last meaningful field.
        # Strip trailing whitespace from body before injecting.
        trimmed = body.rstrip()
        # Ensure trailing comma before our new field
        if not trimmed.endswith(","):
            trimmed += ","
        new_body = trimmed + f" thumbnail: '{url}' "
        inserted += 1
        return "{ id: '" + ex_id + "'," + new_body + "}"

    new_src = pattern.sub(replace, src)
    if new_src != src:
        TS_PATH.write_text(new_src)
    print(f"Inserted: {inserted}, updated: {updated}, skipped: {skipped}")


if __name__ == "__main__":
    main()
