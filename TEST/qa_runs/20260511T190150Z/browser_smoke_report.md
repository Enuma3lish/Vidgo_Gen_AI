# Browser Smoke Report

Run ID: `20260511T190150Z`
Frontend: `https://vidgo.co`
Date: 2026-05-12 local / 2026-05-11 UTC

## Environment Smoke

- `https://api.vidgo.co/health`: HTTP 200, body `{"status":"ok","mode":"preset-only","materials_ready":false}`.
- `https://api.vidgo.co/api/v1/admin/branding/public`: HTTP 200, `settings` schema present.
- `https://vidgo.co/`: HTTP 200, `content-type: text/html`.

## Public Pages

- `/`: HTTP 200, H1 `VIDGO AI / 把商品照片變成高轉換視覺`, main content rendered.
- `/topics/pattern`: HTTP 200, H1 `圖案設計`, main content rendered.
- `/topics/product`: HTTP 200, H1 `電商產品圖`; one Unsplash image request failed with `net::ERR_BLOCKED_BY_ORB`.
- `/topics/video`: HTTP 200, H1 `AI影片`; four Pixabay image requests failed with `net::ERR_BLOCKED_BY_ORB`.
- `/gallery`: HTTP 200, H1 `產品攝影靈感庫`; multiple GCS image/video media requests failed with `net::ERR_BLOCKED_BY_ORB` or `net::ERR_ABORTED`.
- `/pricing`: HTTP 200, H1 `選擇您的方案`; observed 6 subscription cards plus credit packs, not the 4 plan cards expected by `final_test.md`.

## Static Info Routes

Expected by `final_test.md` but rendered SPA 404:

- `/info/about`
- `/info/contact`
- `/info/terms`
- `/info/privacy`
- `/info/cookies`
- `/info/refund`
- `/info/affiliate`

Root slug equivalents render:

- `/about`
- `/contact`
- `/terms`
- `/privacy`
- `/cookies`
- `/refunds`
- `/affiliate`

## Tool Route Aliases

- `/tools/upscale`: renders `HD 圖片放大`.
- `/tools/image-upscale`: renders SPA 404.
- `/tools/video-transform`: renders `影片風格轉換`.
- `/tools/short-video?mode=transform`: renders `商品動態短影音（圖生影片）`, not the transform workflow.
- `/tools/pattern-generate` and `/topics/pattern`: both render `圖案設計`.

## Admin Pages

Logged in as admin and verified these routes render without auth bounce or console errors:

- `/admin/dashboard`
- `/admin/users`
- `/admin/materials`
- `/admin/revenue`
- `/admin/costs`
- `/admin/plans`
- `/admin/branding`
- `/admin/system`

Non-blocking warning: `/admin/materials` produced aborted GCS video media requests during page load.
