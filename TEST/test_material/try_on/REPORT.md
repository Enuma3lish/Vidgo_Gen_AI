# Try-On Deep Test Report

Live target: https://vidgo.co/tools/try-on
Date: 2026-05-06
Auth: admin (vidgo168@gmail.com), bearer token via `localStorage.access_token`

## 1. Inputs archived

All inputs that the page actually serves (signed GCS URLs from
`vidgo-media-vidgo-ai/static/tryon/...`) are saved under
`TEST/test_material/try_on/`:

- `garments/garment-{tshirt,coat,jacket,blouse,sweater,dress}.png` — 6 preset clothing items shown in the "預設服裝（示範）" picker
- `models/{female,male}-{1,2,3}.png` — 6 preset model figures
- `results/result-{tshirt,coat,jacket,blouse,sweater,dress}.png` — outputs for the deep test below

## 2. Deep test — every garment example, real PiAPI call

For each garment we issued `POST /api/v1/tools/try-on` with the live GCS URL
of the garment + the female-1 model (the same call the UI fires). All calls
succeeded end-to-end through the real PiAPI virtual try-on path:

| # | Garment        | HTTP | success | image returned | latency |
|---|----------------|------|---------|----------------|---------|
| 1 | garment-tshirt | 200  | true    | piapi_cd4df0e2 | 99.0 s  |
| 2 | garment-coat   | 200  | true    | piapi_5132cb02 | 131.0 s |
| 3 | garment-jacket | 200  | true    | piapi_c9f1ad36 | 112.8 s |
| 4 | garment-blouse | 200  | true    | piapi_83105672 | 113.7 s |
| 5 | garment-sweater| 200  | true    | piapi_b6cd8964 | 90.1 s  |
| 6 | garment-dress  | 200  | true    | piapi_0a9fd938 | 88.0 s  |

All 6 generated images downloaded into `results/` (≈750–950 KB each, PNG).

Conclusion: the production try-on pipeline (PiAPI provider → GCS upload →
result URL) is healthy end-to-end for every shipped example.

## 3. Why "🔒 此範例尚未預生成結果" appears

Source: [frontend-vue/src/views/tools/TryOn.vue](frontend-vue/src/views/tools/TryOn.vue#L661-L664)
sets `demoEmptyState = true` when both lookup paths fail in
[frontend-vue/src/views/tools/TryOn.vue](frontend-vue/src/views/tools/TryOn.vue#L279-L313):

1. The DB preset lookup —
   `demoTemplates.find(t => input_params.clothing_id === selectedClothingId
   && input_params.model_id === selectedModel)` — yields nothing because the
   `try_on` slice of the materials table is empty/invalid in production:
   - `GET /api/v1/demo/presets/try_on` → `db_empty: true`, `presets: []`
   - `GET /api/v1/demo/inputs/try_on`  → `count: 0`
   - `GET /api/v1/admin/materials?tool_type=try_on` shows only:
     - a few `topic=user` PiAPI rows (irrelevant `clothing_id` keys), and
     - rows with `status=rejected` or `result_image_url=null`
   - [backend/app/services/material_lookup.py](backend/app/services/material_lookup.py#L100-L220)
     filters out rejected / null-URL / readiness-seed rows, so
     `get_presets_for_tool('try_on')` returns nothing.

2. The on-demand fallback —
   `generateOnDemand('try_on', topic, { product_id: model_id, input_image_url })`
   — also fails for the same reason: the backend's cache-through path looks
   up the (garment, model) pair via `lookup_hash`, doesn't find it, and
   there is no try_on material to seed the cache, so the helper returns
   `null`.

3. With both paths empty, the view enters the demo empty-state and renders
   `🔒 此範例尚未預生成結果` plus the "subscribe" CTA.

Important: this only affects the **demo** UI branch
(`isDemoUser === true`, i.e. unauthenticated or free-plan users). Logged-in
subscribers — including the admin account used in §2 — bypass that branch
entirely and hit `POST /api/v1/tools/try-on` directly, which works for all
6 garments as shown above.

## 4. Recommended fix (not yet applied)

Backfill `materials` for `tool_type=try_on` so the demo lookup succeeds:

- For each (clothing_id ∈ {tshirt, coat, jacket, blouse, sweater, dress},
  model_id ∈ {female_1..3, male_1..3}) valid pair, insert a row with:
  - `input_image_url` = the garment GCS URL
  - `result_image_url` = a pre-generated PiAPI try-on output (the 6 we
    just generated can serve as the female-1 column)
  - `input_params` = `{ "clothing_id": "<id>", "model_id": "<id>",
    "clothing_type": "...", "gender_restriction": ... }`
  - `status` = `APPROVED` (or `FEATURED`), `is_active=true`
  - `lookup_hash` = SHA256 of the canonical (clothing_id, model_id) key so
    the cache-through path can also hit it
- Skip male × {dress, skirt} combinations (the UI already disables them).

Once seeded, the same six examples in the picker will resolve via the demo
preset path and stop showing the empty-state message.
