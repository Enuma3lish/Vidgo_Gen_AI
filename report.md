# VidGo Homepage + Tool QA Report

Date: 2026-05-11
Target: https://vidgo.co
Tester account: admin account `vidgo168@gmail.com` (password omitted from report)
Browser: built-in Playwright browser automation, authenticated admin session

## Executive Summary

| Area | Status | Notes |
| --- | --- | --- |
| Admin login/session | PASS | `/admin/dashboard` was reachable without redirecting to login. |
| Homepage zh-TW | PASS | Homepage rendered target tool cards and no raw i18n keys or broken images were detected. |
| Homepage English | PASS | Homepage rendered target tool cards and no raw i18n keys or broken images were detected. English copy uses `Video Translation & Dubbing`. |
| Tool page language coverage | PASS | Room Redesign, Image Translator, Video Dubbing, and Background Removal rendered in zh-TW and English with expected localized UI text. |
| Background Removal operation | PASS | Uploaded product fixture, generated result, and verified download URL returned a valid PNG. |
| Room Redesign operation | BLOCKED | Admin session sees custom generation as subscription-only: `Generate Design (Requires Subscription)` and `Style Transfer (Requires Subscription)`. |
| Image Translator operation | BLOCKED | Admin session shows `20 Credits (Insufficient)`; upload/settings worked, but generation did not proceed. |
| Video Dubbing operation | BLOCKED | Admin session shows `35 Credits (Insufficient)`; sample/settings worked, but generation did not proceed. |

## Environment Checks

- `https://vidgo.co` loaded successfully.
- Admin-authenticated navigation was confirmed by reaching `https://vidgo.co/admin/dashboard`.
- Language selector was visible on the homepage.
- The four target homepage links were present:
  - `/tools/room-redesign`: found 6 links
  - `/tools/image-translator`: found 2 links
  - `/tools/video-dubbing`: found 2 links
  - `/tools/background-removal`: found 5 links

## Homepage Checks

### zh-TW

Status: PASS

Validated visible localized content:
- `VidGo AI`
- `智能去背`
- `室內設計渲染`
- `圖片翻譯`
- `影片翻譯配音`

Additional checks:
- No raw i18n keys detected.
- No opposite-language leakage detected in the sampled terms.
- No broken images detected in the visible sampled image set.
- Target tool cards link to the expected `/tools/...` routes.

### English

Status: PASS

Validated visible localized content:
- `VidGo AI`
- `Background Removal`
- `Interior Rendering`
- `Image Translation`
- `Video Translation & Dubbing`

Additional checks:
- No raw i18n keys detected.
- No opposite-language leakage detected in the sampled terms.
- No broken images detected in the visible sampled image set.
- Target tool cards link to the expected `/tools/...` routes.

Note: the English homepage/page wording is `Video Translation & Dubbing`, not the shorter `Video Dubbing`. This looks like intentional product copy, not a localization failure.

## Tool Page Language Checks

| Page | zh-TW Result | English Result | Notes |
| --- | --- | --- | --- |
| `/tools/room-redesign` | PASS | PASS | zh-TW h1: `室內設計渲染與提案工具`; English h1: `Interior Rendering and Proposal Tool`. |
| `/tools/image-translator` | PASS | PASS | zh-TW h1: `圖片翻譯`; English h1: `Image Translation`. |
| `/tools/video-dubbing` | PASS | PASS | zh-TW h1: `影片翻譯配音`; English h1: `Video Translation & Dubbing`. |
| `/tools/background-removal` | PASS | PASS | zh-TW h1: `智能去背（基礎）`; English h1: `Smart Background Removal (Base)`. |

Language validation details:
- Checked zh-TW and English via locale setting reloads.
- No raw i18n keys such as `lp.*`, `nav.*`, `tools.*`, or `common.*` were detected.
- No sampled opposite-language leakage was detected.
- No broken images were detected in sampled visible images.

## Operational Checks

### Background Removal

Status: PASS

Flow tested:
1. Opened `/tools/background-removal` in English.
2. Uploaded fixture: `TEST/Test_material/assets/product-scene/product-skincare-serum-packshot.png`.
3. Selected `Transparent PNG` output mode.
4. Clicked `Remove Background`.
5. Result panel appeared with generated image.
6. Download link appeared as `Download Result`.
7. Download URL was fetched and validated.

Download validation:
- HTTP status: 200
- Content type: `image/png`
- Size: 250,540 bytes
- PNG signature: valid
- Result URL observed: `https://storage.googleapis.com/vidgo-media-vidgo-ai/generated/image/eda6540ff0d9.png`

Result: admin account can run and download Background Removal successfully.

### Room Redesign

Status: BLOCKED by account entitlement/subscription gate

Flow attempted:
1. Opened `/tools/room-redesign` in English.
2. Uploaded fixture: `TEST/Test_material/assets/room-redesign/room-living-2d-sketch.png`.
3. Selected room/style controls:
   - `Living`
   - `Scandinavian`
4. Looked for an unlocked generation CTA.

Observed blocker:
- No unlocked custom generation button was available.
- Page displayed subscription-gated CTAs:
  - `Generate Design (Requires Subscription)`
  - `Style Transfer (Requires Subscription)`
- Page also displayed: `Select a design style to view AI-generated examples, or subscribe to upload your room photo`.

API observations:
- `/api/v1/interior/room-types` returned 200 with room types.
- `/api/v1/interior/styles` returned 200 with design styles.
- No custom generation API request was triggered.

Result: page, upload, and selectors work, but custom generation/download could not be verified using the admin account because this admin session is not treated as a subscriber for Room Redesign generation.

### Image Translator

Status: BLOCKED by insufficient credits

Flow attempted:
1. Opened `/tools/image-translator` in English.
2. Uploaded fixture: `TEST/Test_material/assets/image-translator/text-sale-card-en.png`.
3. Selected target language: `Traditional Chinese`.
4. Selected tone: `Food & beverage menu`.
5. Clicked `Translate Image`.

Observed blocker:
- Page displayed: `Estimated cost: 20 Credits (Insufficient)`.
- No generation result appeared.
- No generation API response was captured after clicking.
- No download control appeared.

Result: upload and settings UI work, but generation/download could not be verified using the admin account because the account has insufficient credits for Image Translator.

### Video Dubbing

Status: BLOCKED by insufficient credits

Flow attempted:
1. Opened `/tools/video-dubbing` in English.
2. Selected sample: `Retail Product Launch`.
3. Filled script text.
4. Selected target language: `Traditional Chinese`.
5. Clicked the dubbing CTA after scrolling/force-click retry.

Observed blocker:
- Page displayed: `Estimated cost: 35 Credits (Insufficient)`.
- No generation API response was captured after clicking.
- No generated downloadable video appeared.
- The page did show the demo/sample output panel, but this is not proof of a new generated result from uploaded input.

Result: page and settings UI work, but generation/download could not be verified using the admin account because the account has insufficient credits for Video Dubbing.

Note: the test plan estimated Video Dubbing at 30 credits, but the live UI shows 35 credits. Update the plan or pricing expectations if 35 is the intended production price.

## Issues / Follow-Up Items

1. Admin account is not enough for paid-tool E2E generation.
   - Room Redesign custom generation is subscription-gated.
   - Image Translator shows insufficient credits.
   - Video Dubbing shows insufficient credits.
   - Recommendation: seed this admin account with test credits/subscriber entitlement, or use a dedicated QA Pro subscriber account for paid generation flows.

2. Video Dubbing pricing expectation mismatch.
   - Plan expected 30 credits.
   - Live UI shows 35 credits.
   - Recommendation: confirm intended production price and align `tier_config.py`, UI copy, and test plan.

3. Full upload → effect → generate → download validation is currently complete only for Background Removal.
   - Background Removal passed with a valid generated PNG download.
   - Room Redesign, Image Translator, and Video Dubbing require account entitlement/credits before their generation/download flows can be fully validated.

## Final Status

| Requirement | Status |
| --- | --- |
| Homepage target items correct | PASS |
| Each requested page checked in zh-TW | PASS |
| Each requested page checked in English | PASS |
| Background Removal upload/effect/generate/download | PASS |
| Room Redesign upload/effect/generate/download | BLOCKED |
| Image Translator upload/effect/generate/download | BLOCKED |
| Video Dubbing upload/effect/generate/download | BLOCKED |

Overall: homepage and localization checks passed. Background Removal passed the full operational flow. The other three paid tools are blocked by the current admin account's entitlement/credit state, not by page-rendering or language failures.
