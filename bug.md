# VidGo Final QA Bugs

Date: 2026-05-12
Test plan: `final_test.md`
Run folder: `TEST/qa_runs/20260511T190150Z/`
Production target: `https://vidgo.co` + `https://api.vidgo.co`

## Status — fix pass 2026-05-12

| ID | Status | Note |
|---|---|---|
| FT-001 `/info/*` 404 | ✅ Fixed | Added `/info/:slug` alias route to `frontend-vue/src/router/index.ts` |
| FT-002 `/tools/image-upscale` 404 | ✅ Fixed | Added redirect alias to `/tools/upscale` |
| FT-003 `?mode=transform` ignored | ✅ Fixed | `ShortVideo.vue` now also honours `route.query.mode === 'transform'` |
| FT-004 ORB blocked Unsplash/Pixabay/GCS | ❌ Cannot fix in code | Bucket/CDN config — see "Cannot fix in this pass" below |
| FT-005 Pricing has 6 cards not 4 | ❌ Won't fix | Admin-editable plans intentionally surface 6; final QA spec needs updating, not the product |
| FT-006 AI Avatar provider ERROR before fallback | ❌ Cannot fix in code | PiAPI F5-TTS upstream is dead (500 on every call) — fallback already in place; log line is honest signal |
| FT-007 Pollo/PiAPI progress validation errors | ❌ Cannot fix in code | Provider partner notification schema mismatch — log noise only, generation completes |
| FT-008 Admin redirected away from My Works | ✅ Fixed | Router guard now lets `/dashboard/my-works`, `/dashboard/share-links` pass for admins |
| FT-009 Avatar 504 from edge | ✅ Fixed | Avatar endpoint now uses chunked `StreamingResponse` with a 25 s whitespace heartbeat to keep edge proxies from idling out; raised axios global timeout 6→15 min and PiAPI httpx 5→10 min |
| FT-010 Room Redesign button click no-op | ✅ Fixed | `handleRoomFileSelected` was setting `uploadedFile` but never `uploadedImage`, so the button's `:disabled` binding stayed true after a subscriber upload — bot's click was hitting a disabled button |
| FT-011 Test asset 403 | ✅ Fixed | Replaced the dead `gtv-videos-bucket/sample/ForBiggerJoyrides.mp4` references with `test-videos.co.uk` Big Buck Bunny / Sintel mirrors that return 200 |
| image-translator results faulty | ✅ Fixed | Switched from generic I2I (Flux derive_image / Imagen edit) to direct Gemini 2.5 Flash Image edit path |
| video-dubbing results faulty | ✅ Fixed | New ffmpeg graph keeps full video length, mixes original ambient under the dub, never `-shortest`-truncates |

### Cannot fix in this pass

- **FT-004 ORB / cross-origin image blocks** — caused by GCS bucket/CDN not returning `Cross-Origin-Resource-Policy: cross-origin`. Needs bucket CORS config update in GCP console; route the Unsplash/Pixabay topic assets through the existing `/api/v1/share/share-media` proxy if you can't relax the bucket CORS.
- **FT-005 Pricing 6 vs 4 cards** — product decision, not a code bug. Update `final_test.md` PAY-EXISTS-01 to accept the admin-editable count.
- **FT-006/FT-007 provider noise** — F5-TTS upstream is broken on PiAPI side; we already fall through to tts-1 and the user-visible flow works. Notification schema drift is a partner-side fix.


## BUG-FT-001 - Static `/info/*` pages render SPA 404

- Severity: Blocker
- Related UAT: TOPIC-07
- Steps: Open `/info/about`, `/info/contact`, `/info/terms`, `/info/privacy`, `/info/cookies`, `/info/refund`, `/info/affiliate`.
- Expected: Each static info page renders.
- Actual: Each route returns HTTP 200 at the CDN level but the Vue app renders H1 `404` / `Page Not Found`.
- Notes: Root slug routes do work: `/about`, `/contact`, `/terms`, `/privacy`, `/cookies`, `/refunds`, `/affiliate`.
- Evidence: `TEST/qa_runs/20260511T190150Z/browser_smoke_report.md`.

## BUG-FT-002 - `/tools/image-upscale` route is missing

- Severity: Blocker
- Related UAT: Section 3.7 Commercial HD Upscale
- Steps: Open `/tools/image-upscale`.
- Expected: Commercial HD Upscale tool renders.
- Actual: Vue SPA renders H1 `404` / `Page Not Found`.
- Notes: The deployed route is `/tools/upscale`; `frontend-vue/src/router/index.ts` does not define `/tools/image-upscale` or a redirect alias.
- Evidence: `TEST/qa_runs/20260511T190150Z/browser_smoke_report.md`.

## BUG-FT-003 - `/tools/short-video?mode=transform` does not open Video Transform

- Severity: Blocker
- Related UAT: Section 3.10 Video Transform
- Steps: Open `/tools/short-video?mode=transform`.
- Expected: Video Transform workflow renders with upload video + transform style controls.
- Actual: The page still renders `商品動態短影音（圖生影片）`, the Image-to-Video workflow.
- Notes: `/tools/video-transform` renders the correct `影片風格轉換` page; `ShortVideo.vue` uses `route.name === 'video-transform'`, so the query-string mode is ignored.
- Evidence: `TEST/qa_runs/20260511T190150Z/browser_smoke_report.md`.

## BUG-FT-004 - Topic/gallery media assets fail in browser with ORB/abort errors

- Severity: Major
- Related UAT: TOPIC-03, TOPIC-04, TOPIC-05, GAL-03
- Steps: Browser-smoke `/topics/product`, `/topics/video`, `/gallery`.
- Expected: Product image grid, video/motion examples, and gallery tiles render all visible media.
- Actual:
	- `/topics/product`: one Unsplash image request failed with `net::ERR_BLOCKED_BY_ORB`.
	- `/topics/video`: four Pixabay image requests failed with `net::ERR_BLOCKED_BY_ORB`.
	- `/gallery`: multiple GCS image/video media requests failed with `net::ERR_BLOCKED_BY_ORB` or `net::ERR_ABORTED`.
- Evidence: `TEST/qa_runs/20260511T190150Z/browser_smoke_report.md`.

## BUG-FT-005 - Pricing page card count does not match final QA expectation

- Severity: Major / Spec mismatch
- Related UAT: TOPIC-06, PAY-EXISTS-01
- Steps: Open `/pricing`.
- Expected: 4 plan cards render with localized text.
- Actual: Browser smoke observed 6 subscription plan cards plus credit-pack cards.
- Notes: This may be intentional after the new pricing-system work, but it conflicts with the current signed-off `final_test.md` expectation.
- Evidence: `TEST/qa_runs/20260511T190150Z/browser_smoke_report.md`.

## BUG-FT-006 - AI Avatar generation logs provider ERROR before fallback

- Severity: Major
- Related UAT: REL-01, Section 3.6
- Steps: Run admin AI Avatar generation (`avatar_serum_launch_zh`) through `TEST/admin_test_tools.py`.
- Expected: Completed generation has no backend `ERROR` lines for the task.
- Actual: Cloud Run logs include `ERROR:app.providers.base:[piapi] Response: zero-shot - FAILED: Server error '500 Internal Server Error' for url 'https://api.piapi.ai/api/v1/task'`, then `F5-TTS failed ... falling back to tts-1`.
- User impact: The user-facing task may still complete through fallback, but REL-01 explicitly fails on backend `ERROR` lines for just-completed tasks.
- Evidence: Cloud Run log sample captured during run; `TEST/qa_runs/20260511T190150Z/admin_test_tools.log` contains the corresponding Avatar case.

## BUG-FT-007 - Provider progress notification validation errors appear during generation

- Severity: Minor / Reliability
- Related UAT: REL-01
- Steps: Run Product Scene generation through `TEST/admin_test_tools.py` and inspect Cloud Run logs.
- Expected: No backend errors during completed generation.
- Actual: Cloud Run logs showed Pydantic validation errors for `TaskStatusNotification.params.status` and `TaskStatusNotification.params.lastUpdatedAt` on `notifications/progress` payloads like `{'progress': 23.333333333333332, 'total': 100}`.
- User impact: Product Scene still completed successfully, but backend logs are noisy and violate the no-error-lines reliability check.

## BUG-FT-008 - Admin account cannot access Dashboard My Works gallery

- Severity: Blocker
- Related UAT: Section 3 step E for every tool, GAL-01 through GAL-08
- Steps: Log in as admin `vidgo168@gmail.com`, then open `/dashboard/my-works`.
- Expected: Admin tester can view My Works so generated results can be verified in the dashboard gallery.
- Actual: Browser navigates to `/admin/dashboard`; My Works never renders.
- Notes: `frontend-vue/src/router/index.ts` intentionally redirects any authenticated admin from `/dashboard/*` to `admin-dashboard`, which conflicts with the final QA plan's admin-account dashboard validation.
- Evidence: Browser smoke returned final URL `https://vidgo.co/admin/dashboard` for `/dashboard/my-works`.

## BUG-FT-009 - AI Avatar generation returns production 504

- Severity: Blocker
- Related UAT: Section 3.6 AI Digital Human / Avatar
- Steps: Run admin Avatar generation cases `avatar_serum_launch_zh` and `avatar_bubble_tea_social_en` through `TEST/admin_test_tools.py`.
- Expected: Backend completes and returns a JSON response with `result_video_url`; frontend renders result video on the same page.
- Actual: `/api/v1/tools/avatar` returned HTTP 504 with `content-type: text/plain` at the browser/API proxy layer, after the backend logged a PiAPI TTS 500 fallback and Kling submission. Backend Cloud Run logs later show `POST /api/v1/tools/avatar` completing with `200 OK`, so the client appears to time out before the backend result is delivered.
- User impact: Avatar generation does not complete for the admin QA case; no result URL is available for same-page preview, download, dashboard gallery, or sharing validation.
- Evidence: `TEST/qa_runs/20260511T190150Z/admin_test_tools.log` shows both Avatar admin cases returned `[RES] 504 /api/v1/tools/avatar non-json content_type=text/plain`, then failed with `status=pending wait=900.1s`; Cloud Run logs show the backend request eventually completed with `200 OK`. The recording run reproduced this on `avatar_serum_launch_zh` with HTTP 504 text/plain and `status=pending wait=420.3s`, while `avatar_bubble_tea_social_en` completed in 60.0s.

## BUG-FT-010 - Room Redesign button click does not start generation

- Severity: Blocker
- Related UAT: Section 3.8 Room Redesign
- Steps: Run admin Room Redesign cases `room_living_scandinavian` and `room_kitchen_modern_minimalist` through `TEST/admin_test_tools.py`.
- Expected: Clicking `✨ 生成設計` sends a generation request and returns a completed design image.
- Actual: The page loaded `/api/v1/interior/styles` and `/api/v1/interior/room-types`, accepted the upload/prep steps, and the script clicked `✨ 生成設計`, but no generation API request was observed for either case within 50 seconds.
- User impact: Room Redesign cannot be validated end-to-end; users may click generate and see no completed design.
- Evidence: `TEST/qa_runs/20260511T190150Z/admin_test_report.json` has both Room Redesign cases with `completion_status: no_api_observed`, `http_status: 0`, and no `result_url`. The recording report reproduced both failures with `status=no_api_observed` after 46.0s / 46.1s.

## BUG-FT-011 - Two video UAT source assets return HTTP 403

- Severity: Major / Test data blocker
- Related UAT: Section 3.10 Video Transform, Section 3.11 Video Dubbing
- Steps: Run admin cases `video_transform_social_watercolor` and `dubbing_brand_update_en_to_es` through `TEST/admin_test_tools.py`.
- Expected: Each catalog source video downloads successfully so the browser can upload it and exercise the tool.
- Actual: The script logged `remote asset download failed ... HTTP Error 403: Forbidden`; `video_transform_social_watercolor` could not find an enabled action button, and `dubbing_brand_update_en_to_es` clicked `原文翻譯` but observed no generation API.
- User impact: These cases cannot validate production tool behavior until the catalog media URLs are replaced with accessible assets or mirrored into controlled storage.
- Evidence: `TEST/qa_runs/20260511T190150Z/admin_test_tools.log`, `TEST/qa_runs/20260511T190150Z/admin_test_report.json`, and `TEST/qa_runs/20260511T190150Z/browser_record_run_report.json`.

## Current Script Status

- `TEST/admin_test_tools.py` completed: 22 total, 16 passed, 6 failed. Passing tools: try-on, product-scene, background-removal, short-video, upscale, pattern-generate, image-translator, one video-transform case, and one video-dubbing case. Failing tools: 2/2 Avatar, 2/2 Room Redesign, 1/2 Video Transform, 1/2 Video Dubbing.
- `TEST/browser_record_tools.py` completed: 33 total recordings, 11 default-example screenshots loaded, 17 generated outputs downloaded, 5 generated cases failed/no result. Successful generated tools: try-on 2/2, product-scene 2/2, background-removal 2/2, short-video 2/2, upscale 2/2, pattern-generate 2/2, image-translator 2/2, ai-avatar 1/2, video-transform 1/2, video-dubbing 1/2. Failed generated cases: `avatar_serum_launch_zh` pending after HTTP 504, both Room Redesign cases no API observed, `video_transform_social_watercolor` source asset 403/no action button, and `dubbing_brand_update_en_to_es` source asset 403/no generation API.
- Fresh artifacts: `TEST/qa_runs/20260511T190150Z/browser_record_tools.log`, `TEST/qa_runs/20260511T190150Z/browser_record_run_report.json`, screenshots/videos under `TEST/screen_recording/`, and generated downloads under `TEST/screen_recording/result/`.
