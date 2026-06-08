# T-01 — GCS image assets (ops hand-off)

Status as of 2026-06-08. The **code** side of T-01 is done; what remains needs
the real image files **and** write access to the GCS bucket, so it must be run
by someone with `gcloud` credentials for the project.

There are currently **no broken images** on `/`, `/tools/room-redesign`, or
`/tools/interior-templates` — the frontend swaps any missing asset for a styled
placeholder (`@error` handlers + `previewUrl()→null`). The work below replaces
those placeholders with the real thumbnails so the pages look finished.

The `no-broken-images` Vitest spec guards the fallback behaviour from regressing.

## What's verified

| Asset | URL | HTTP |
|---|---|---|
| Landing interior "before" | `…/static/landing/room-before.jpg` | **403** (missing / not public) |
| Landing interior "after"  | `…/static/landing/room-after.jpg`  | **403** |
| OG social-share cover     | `…/static/landing/og-cover.jpg`    | **403** |
| Example fallbacks (`examples/room`, `examples/hero`, `examples/bg`, `examples/tryon`, `examples/avatar`) | various | 200 ✅ |
| Per-style thumbnails (63 interior/exterior/commercial styles) | `…/static/interior-styles/<id>.jpg` | missing — newly emitted by backend |

Base bucket: `gs://vidgo-media-vidgo-ai` (public-read prefix `examples/` already works).

## Code already done

- **Backend** (`backend/app/api/v1/tools.py`): `/templates/interior-styles`,
  `/templates/exterior-styles`, `/templates/commercial-styles` now emit a
  `preview_url` for every style, derived by convention:
  `https://storage.googleapis.com/vidgo-media-vidgo-ai/static/interior-styles/<id>.jpg`.
  Upload a `<id>.jpg` per style id and it appears automatically — no code change.

## Remaining ops steps

```bash
# 0. Authenticate (no credentialed account is currently configured)
gcloud auth login
gcloud config set project <PROJECT_ID>

# 1. Landing hero + OG cover (the three 403s above)
gsutil cp room-before.jpg room-after.jpg og-cover.jpg \
  gs://vidgo-media-vidgo-ai/static/landing/

# 2. Per-style thumbnails — one <style_id>.jpg per catalog entry.
#    Get the id list from the endpoint:
#      curl -s '<API>/api/v1/tools/templates/interior-styles?space_kind=interior' | jq -r '.[].id'
#      (repeat for space_kind=exterior and space_kind=commercial)
gsutil -m cp interior-thumbs/*.jpg gs://vidgo-media-vidgo-ai/static/interior-styles/

# 3. Ensure the static/ objects are publicly readable (examples/ already is)
gsutil iam ch allUsers:objectViewer gs://vidgo-media-vidgo-ai
#    …or per-object if bucket-wide public read is not desired:
# gsutil acl ch -u AllUsers:R gs://vidgo-media-vidgo-ai/static/landing/*.jpg \
#   gs://vidgo-media-vidgo-ai/static/interior-styles/*.jpg
```

## Verification (delivery standard)

```bash
for u in static/landing/room-before.jpg static/landing/room-after.jpg \
         static/landing/og-cover.jpg static/interior-styles/modern_minimalist.jpg; do
  printf '%s  ' "$(curl -sI -o /dev/null -w '%{http_code}' \
    "https://storage.googleapis.com/vidgo-media-vidgo-ai/$u")"; echo "$u"
done   # expect 200 for each
```

Then load `/`, `/tools/room-redesign`, `/tools/interior-templates` — real
thumbnails should render in place of the placeholders.
