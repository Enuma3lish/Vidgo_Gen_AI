# Landing-page examples — "not enough + incorrect" fix

Goal: every example region on `/` (vidgo.co) shows **enough** and **correct**
before/after results.

## Root causes found (2026-06-25)

1. **Frontend capped each region to one example.** `demo()` always returned
   `list[0]`, so the hero card, the 3 deep-dive rows, and the category tiles
   each showed a single pair even when the API returned many.
2. **Thin / contaminated data for some tools.** Live `/api/v1/demo/presets`
   counts: `product_scene` ok, `short_video` 11, `background_removal` 14 (but
   near-identical before≈after), `try_on` **3** (all leaked *user* uploads —
   `clothing_id=garment-user`, random Unsplash garments, results on the
   expiring `theapi.app` host), `room_redesign` **3** (curated, but few).
3. **Incorrect pairs were patched with fragile per-filename overrides** in
   `demo()`.

## What is already done in code (in this repo)

### Track 1 — frontend (DONE, type-checked, no-broken-images test logic passes)
`frontend-vue/src/views/LandingPage.vue`
- `loadDemos()` fetch limit `2 → 8`.
- New `demoList(cat, n=4)` returns up to **4** validated pairs: drops empty /
  identical pairs and auto-generated near-identical inputs, dedupes by result,
  and **leads with the curated `FALLBACK[cat]`** so every region always opens
  with a known-correct example. Replaces the old per-filename overrides.
- Hero card and the 3 deep-dive rows now render up to 4 examples with a
  thumbnail selector (`.hero-demo-thumbs`, `.dd-thumbs`).
- Every `<img>` keeps an `@error` placeholder (regression test still green).

### Track 2a — backend filter (DONE, needs redeploy to take effect)
`backend/app/services/material_lookup.py` → `get_presets_for_tool()`
- Excludes `input_params.clothing_id == "garment-user"` so visitors' own demo
  uploads stop surfacing as public try_on presets. No-op for other tools.
- ⚠️ After deploy, `try_on` presets are **empty until you run the refill
  below** — the homepage still shows the curated coat (FALLBACK), but the
  try_on tool page will be sparse until pregen runs. So deploy + pregen
  together.

## Track 2b — data refill (RUN THIS — needs PiAPI key + GCP creds + review)

Repopulates curated, correctly-paired rows and persists results to your own
GCS (`gs://vidgo-media-vidgo-ai/generated/...`), not `theapi.app`.

```bash
# from repo root, authenticated to the vidgo-ai GCP project
# try_on: --clean wipes ALL try_on rows first (incl. the garment-user leftovers)
bash gcp/pregen.sh materials --tool try_on        --limit 12 --clean --yes

# room_redesign: 7 rooms × 6 styles
bash gcp/pregen.sh materials --tool room_redesign  --limit 42 --clean --yes

# OPTIONAL — give background_removal real with-background inputs so before≠after
bash gcp/pregen.sh materials --tool background_removal --limit 15 --clean --yes
```

Tool limits live in `backend/scripts/main_pregenerate.py` → `TOOL_LIMITS`.
Each run burns real PiAPI/Kling credits; **human-review the candidates** (the
review gate in `docs/example-mode-cache-system.md`) before they go live.

## Verify

```bash
# counts should rise and no more garment-user rows
for c in product_scene try_on background_removal room_redesign short_video; do
  echo "== $c =="; curl -s "https://vidgo.co/api/v1/demo/presets/$c?limit=20" \
    | python3 -c "import sys,json;d=json.load(sys.stdin);print('count',d['count'])"
done
```

Then load `/` in all 5 locales and confirm each hero tab, deep-dive row, and
the seasonal grid shows 4 sensible paired examples with no broken images.
