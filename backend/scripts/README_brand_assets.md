# `generate_brand_assets.py` — quick start

Generates the two asset sets you said you needed:

1. **Hub thumbnails** (17 images) — for the tool hub tiles
   (Recolor, Virtual Model, Ghost Mannequin, Product Staging, etc.)
2. **Try-on model references** (11 images) — full-body fashion models
   (Avery, Sam, Taylor, Kendall, …) for the Virtual Try-On grid.

All prompts are themed for the VidGo site:
e-commerce / fashion / product photography / branding.

---

## What the script does, step by step

For each asset in the catalog:

1. Call **PiAPI Flux T2I** (`text_to_image`) with a curated prompt +
   a negative-prompt that strips text/watermarks/clutter.
2. Download the result bytes over HTTP.
3. Save the PNG locally under
   `frontend-vue/public/static_assets/...` so Vite serves it at
   `/static_assets/...` immediately in dev.
4. (Optional) Upload to **GCS** at `static/...` — same path layout the
   rest of the site uses — when you pass `--gcs`.
5. (Optional) Upsert a row into the `materials` table:
   - `tool_type = effect`,  `topic = "hub_thumbnail"` for hub tiles
   - `tool_type = try_on`, `topic = "model_library"` for models
   - The row carries the public URL + the prompt + `input_params` for
     auditing. The script uses a deterministic `lookup_hash` so
     re-running upserts the same row instead of creating duplicates.
6. At the end, print a **ready-to-paste snippet** showing the new URLs
   in the exact shape needed for `toolHub.ts` and `TryOn.vue`'s
   `modelOptions`.

---

## Prerequisites

Credentials live in **`backend/.env`** — the script auto-loads it on
startup, so you do **not** need to `export` anything. Expected keys:

```ini
# backend/.env
PIAPI_KEY=...                                       # Flux T2I
DATABASE_URL=postgresql+asyncpg://user:pw@host/db   # for DB upserts
GCS_BUCKET=vidgo-media-vidgo-ai                     # only used with --gcs
# Plus GOOGLE_APPLICATION_CREDENTIALS (or ADC) for GCS auth
```

The script is **self-contained** — it does not import from `app.*`.
That means you do *not* need a working project `uv sync`. (Useful if
your current sync is broken, e.g. the `llvmlite==0.46.0` no-x86_64-mac-
wheel issue blocking `rembg → numba`.)

We tell uv to skip the project entirely with `--no-project` and add
just the four packages the script actually needs.

---

## Usage

Run from the **repo root**.

```bash
# 1. Preview what will be generated. No API calls, no writes.
#    Only needs python-dotenv to read backend/.env.
uv run --no-project --with python-dotenv \
    python backend/scripts/generate_brand_assets.py --set all --dry-run

# 2. Generate one asset (great while you're iterating on a prompt)
uv run --no-project --with httpx --with python-dotenv --with asyncpg \
    python backend/scripts/generate_brand_assets.py \
    --set hub --only virtual-model

# 3. Generate everything, save locally, write DB rows (no GCS)
uv run --no-project --with httpx --with python-dotenv --with asyncpg \
    python backend/scripts/generate_brand_assets.py --set all

# 4. Full production run — local + GCS + DB
uv run --no-project \
    --with httpx --with python-dotenv --with asyncpg \
    --with google-cloud-storage \
    python backend/scripts/generate_brand_assets.py --set all --gcs

# 5. Re-generate something even though the local file already exists
uv run --no-project --with httpx --with python-dotenv --with asyncpg \
    python backend/scripts/generate_brand_assets.py \
    --set hub --only logo --force

# 6. Files-only mode (no DB writes — drops the asyncpg dependency)
uv run --no-project --with httpx --with python-dotenv \
    python backend/scripts/generate_brand_assets.py --set all --no-db
```

> **Tip**: define a shell alias so you don't have to remember the
> `--with` list each time:
>
> ```bash
> alias vidgo-assets='uv run --no-project --with httpx --with python-dotenv --with asyncpg --with google-cloud-storage python backend/scripts/generate_brand_assets.py'
> # then: vidgo-assets --set all --gcs
> ```

### Why not `uv run python -m scripts.generate_brand_assets`?

That syntax requires `uv sync` to succeed on the parent project — and
right now `rembg → numba → llvmlite==0.46.0` doesn't have a macOS
x86_64 wheel, so `uv sync` builds llvmlite from source and falls over
on a setuptools incompatibility. `--no-project` skips the sync.

If you ever want to fix the underlying sync issue: pin
`llvmlite<0.46` (or drop `rembg` from the top-level deps — it's only
imported in two `app/` modules and could be lazy-installed).

After a real run you'll see something like:

```text
============================================================
Frontend snippet for set=hub
============================================================
Replace each tile's `thumb:` field in
  frontend-vue/src/data/toolHub.ts
with the values below:

  // Recolor
  id 'recolor'  →  thumb: '/static_assets/hub/recolor.png',
  // Product Beautifier
  id 'product-beautifier'  →  thumb: '/static_assets/hub/product-beautifier.png',
  ...
```

Paste those URLs into `toolHub.ts` and the new images go live.

---

## What goes where

| Asset set | Local path | GCS blob path | DB |
| --- | --- | --- | --- |
| hub | `frontend-vue/public/static_assets/hub/{id}.png` | `static/hub/{id}.png` | `materials.topic='hub_thumbnail'` |
| models | `frontend-vue/public/static_assets/tryon/models/{id}.png` | `static/tryon/models/{id}.png` | `materials.topic='model_library'` |

Note: the model GCS path `static/tryon/models/{id}.png` deliberately
matches the URLs `TryOn.vue` already points at, so once you `--gcs`-
upload the new images, the existing `modelOptions` URLs **start
showing the new full-body renders without any code change**. The
asset IDs (`avery`, `sam`, etc.) are different from the legacy IDs
(`female-1`, `male-1`); see "Switching the try-on grid" below.

---

## Switching the try-on grid to the new model images

After you've run the script with `--gcs`, the new models live at:

```text
https://storage.googleapis.com/${GCS_BUCKET}/static/tryon/models/avery.png
…  kendall.png
…  maya.png
…  taylor.png
…  jordan.png
…  casey.png
…  alex.png  reece.png  sam.png  lena.png  julia.png
```

Update `frontend-vue/src/views/tools/TryOn.vue` (`modelOptions`) so
each entry's `id` matches the new asset id (`avery` instead of
`female-1`, etc.) and `preview` points at the new URL. The script's
end-of-run snippet shows exactly what to paste.

You'll also want the backend's `generate_model_library()` to know
about the new IDs so generation still resolves. Search for
`female-1`, `male-1` in `backend/app/services/` and add the new ids.

---

## Costs (rough)

Flux schnell on PiAPI runs around **$0.003 per 1024×1024 image** at
time of writing. Worst case the full run is:

- 17 hub tiles  + 11 models = 28 images
- ≈ $0.084 total
- ≈ 4–6 minutes wall clock at the default 3 s rate limit

Re-running for prompt iteration is cheap. If a single asset isn't
quite right, just `--only <id> --force` to regenerate that one image.

---

## Tuning tips

- **Wrong style on one tile?** Edit the `subject` string in
  `hub_catalog()` (or `model_catalog()`). Subjects are deliberately
  short and concrete so the per-set style suffix can stay consistent.
- **Wrong style on a whole set?** Edit `HUB_STYLE_SUFFIX` /
  `MODEL_STYLE_SUFFIX` at the top of the script. A few specific
  tiles have per-tile overrides (`logo`, `text`,
  `three-d-illustration`, `instagram-story`, `create-any-image`) so
  the "photoreal e-commerce" suffix doesn't fight their intended look.
- **Bad models?** Iterate with `--only avery --force` until one looks
  right, then move on. Each model is independent.
- **Want square hub thumbs instead of 4:3?** Change `width=1024`,
  `height=768` → `1024, 1024` in `hub_catalog()`.

---

## Why this script — and not a one-off prompt batch?

1. **Reproducibility** — the same prompts produce comparable assets
   at any time, and the `lookup_hash` makes re-runs idempotent.
2. **Auditability** — every asset's prompt and parameters are
   recorded in the `materials` table, so you can answer "where did
   that thumb come from?" months later.
3. **Topic match** — the prompts encode VidGo's voice (fashion /
   e-commerce / product / branding) so you don't end up with a
   stock-photo look that doesn't fit the site.
4. **One source of truth** — the same script feeds both the local
   dev environment, the GCS production URL, and the DB row that the
   admin tooling can list.
