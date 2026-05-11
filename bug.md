# VidGo.co UAT Bug List

Date: 2026-05-11
Source files:

- `bug_list/VidGo.co_網站測試驗收清單_(UAT_Checklist)0511.pdf`
- `bug_list/VidGo.co_網站測試驗收清單_(UAT_Checklist)0511.docx`

Extraction note: direct PDF text conversion through the available local tool failed because the PDF text is Flate-encoded/embedded. The same checklist exists as a paired DOCX with the same filename/date, and its table text was extracted successfully with `textutil`; the bugs below are based on that extracted UAT checklist content.

## Summary

| Severity | Count | Items |
| --- | ---: | --- |
| Critical / Blocker | 6 | BUG-001, BUG-006, BUG-011, BUG-012, BUG-013, BUG-018 |
| High | 7 | BUG-002, BUG-003, BUG-004, BUG-005, BUG-007, BUG-008, BUG-009 |
| Medium | 4 | BUG-010, BUG-014, BUG-015, BUG-017 |
| Low / UI polish | 1 | BUG-016 |

Overall UAT status from source: unresolved. The checklist notes that most generation flows display failures and/or wait too long.

## Bugs

### BUG-001 — Dashboard generated-work thumbnails do not display

- Severity: Critical / Blocker
- Source row: Dashboard, result `fail`
- Affected area: Dashboard / generated works list
- Source wording: `生成作品縮圖無法顯示`
- Observed issue: Generated work thumbnails are missing or fail to render in the dashboard.
- Expected behavior: Every completed generation should show a visible thumbnail/preview in the dashboard so users can identify and reopen their work.
- Reproduction steps:
  1. Log in to VidGo.co.
  2. Generate any supported asset.
  3. Navigate to Dashboard / generated works.
  4. Check whether the generated item has a thumbnail.
- Impact: Users cannot visually identify previous results; this also makes download/history workflows unreliable.
- Suggested fix direction: Verify stored thumbnail/result URLs, signed URL expiry, image proxy/CORS behavior, and dashboard fallback rendering for missing thumbnails.

### BUG-002 — Product Dynamic Video exposes unwanted data/name text in top-left

- Severity: High
- Source row: AI-02 Product Dynamic Video, result `pass` with note
- Affected area: Product Dynamic Video result UI/output preview
- Source wording: `左上角資料名稱需隱藏`
- Observed issue: The top-left data/name label is visible and should be hidden.
- Expected behavior: Generated video preview/output should not expose internal filenames, data labels, or debugging metadata.
- Reproduction steps:
  1. Open Product Dynamic Video.
  2. Upload a product image.
  3. Select a motion effect/template.
  4. Generate a short video.
  5. Inspect the top-left area of the preview/result.
- Impact: Internal metadata may be visible to users and can make the output look unprofessional.
- Suggested fix direction: Hide debug/name overlays in the frontend result card and confirm the provider output itself does not burn metadata into the video.

### BUG-003 — AI Digital Human cannot accept custom script

- Severity: High
- Source row: AI 數位人, result `fail`
- Affected area: AI Digital Human / Avatar script input
- Source wording: `無法自行輸入腳本`
- Observed issue: Users cannot freely input their own script for digital-human generation.
- Expected behavior: The tool should allow custom script entry before generation, with validation for length/language.
- Reproduction steps:
  1. Open the AI Digital Human / Avatar tool.
  2. Try to enter a custom speaking script.
  3. Attempt generation using that script.
- Impact: Core user workflow is blocked because users cannot create their own spokesperson content.
- Suggested fix direction: Check whether the script textarea is disabled, overwritten by presets, not bound to request payload, or hidden by account state.

### BUG-004 — AI Digital Human result video is not shown on the same page

- Severity: High
- Source row: AI 數位人, result `fail`
- Affected area: AI Digital Human / Avatar result rendering
- Source wording: `生成後的影片未顯示在同個頁面 要到控制板才看到`
- Observed issue: After generation, the result video does not appear on the generation page; users must go to the dashboard/control panel to find it.
- Expected behavior: The generated video should appear immediately on the same tool page with playback and download controls.
- Reproduction steps:
  1. Open AI Digital Human / Avatar.
  2. Select/avatar upload input and provide script.
  3. Generate video.
  4. Observe whether the video appears in the tool result panel.
- Impact: Users may think generation failed and repeat the action, wasting credits and time.
- Suggested fix direction: Ensure the frontend maps backend `result_video_url` / `video_url` to the visible result state and does not only persist it in dashboard history.

### BUG-005 — AI Digital Human generated video contains unexpected text

- Severity: High
- Source row: AI 數位人, result `fail`
- Affected area: AI Digital Human / Avatar output quality
- Source wording: `生成影片有莫名的文字`
- Observed issue: Generated digital-human video includes unexpected/random text.
- Expected behavior: Output video should only include intended avatar/video content and should not add stray text overlays unless explicitly requested.
- Reproduction steps:
  1. Generate an AI Digital Human video.
  2. Play the generated result.
  3. Inspect for unexpected text overlays or artifacts.
- Impact: Output may be unusable for commercial publishing.
- Suggested fix direction: Review provider prompt/request parameters, overlay/subtitle settings, template defaults, and post-processing layers.

### BUG-006 — AI Product Scene Studio output does not follow standard-plan/request changes

- Severity: Critical / Blocker
- Source row: AI-03 AI Product Scene Studio, result `Fail`
- Affected area: AI Product Scene Studio / paid generation
- Source wording: `標準版生成圖片無照需求變動`
- Observed issue: Standard-plan generated images do not reflect the requested requirement changes.
- Expected behavior: When a user changes the scene description/requirements, the generated product-scene image should reflect those changes according to the selected plan permissions.
- Reproduction steps:
  1. Open AI Product Scene Studio.
  2. Upload a product image.
  3. Choose or enter a scene description.
  4. Change the requested requirements.
  5. Generate using a standard-plan account.
  6. Compare the output with the requested changes.
- Impact: Paid users may receive outputs that ignore prompts or plan-specific capabilities.
- Suggested fix direction: Verify prompt payload construction, plan/model routing, cache-key reuse, and whether old preset/demo results are being returned instead of fresh standard-plan generation.

### BUG-007 — Smart Background Removal fails on complex backgrounds

- Severity: High
- Source row: AI-04 Smart Background Removal, result `Fail`
- Affected area: Background Removal / segmentation quality
- Source wording: `複雜背景會失效`
- Observed issue: Background removal fails when the uploaded product image has a complex background.
- Expected behavior: The tool should detect the product subject and remove complex backgrounds with acceptable edge quality.
- Reproduction steps:
  1. Open Smart Background Removal.
  2. Upload a product image with a complex background.
  3. Click background removal.
  4. Inspect the resulting cutout.
- Impact: Core background-removal promise is unreliable for real-world product photos.
- Suggested fix direction: Improve segmentation model/settings, add fallback provider or matting refinement, and add test fixtures with complex backgrounds.

### BUG-008 — Smart Background Removal black-background mode does not work

- Severity: High
- Source row: AI-04 Smart Background Removal, result `Fail`
- Affected area: Background Removal / replacement background options
- Source wording: `黑底無效`
- Observed issue: Selecting black background does not produce a valid black-background output.
- Expected behavior: Black background mode should composite the cutout onto a black background and display/download the result.
- Reproduction steps:
  1. Open Smart Background Removal.
  2. Upload a valid product image.
  3. Select black background output.
  4. Generate and inspect result.
- Impact: Replacement-background feature is unreliable and may confuse users.
- Suggested fix direction: Verify selected background mode state, request payload mapping, compositing code path, and result format/preview update.

### BUG-009 — Smart Background Removal mobile cannot upload custom image

- Severity: High
- Source row: AI-04 Smart Background Removal, result `Fail`
- Affected area: Background Removal / mobile upload
- Source wording: `手機版無法上傳自訂圖片`
- Observed issue: On mobile, users cannot upload their own custom image.
- Expected behavior: Mobile users should be able to select/capture/upload an image through the upload control.
- Reproduction steps:
  1. Open `/tools/background-removal` on a mobile viewport/device.
  2. Tap upload/custom image control.
  3. Select an image from the device.
  4. Verify preview appears and generation can proceed.
- Impact: Mobile workflow is blocked for a core free/basic tool.
- Suggested fix direction: Inspect mobile layout overlays, hidden file input click forwarding, accepted MIME types, and `capture`/file input behavior.

### BUG-010 — Background replacement should use file upload instead of URL paste

- Severity: Medium
- Source row: AI-04 Smart Background Removal, result `Fail`
- Affected area: Background Removal / replacement background UX
- Source wording: `更換背景不該為貼上網址 改為上傳 檔案`
- Observed issue: Replacement background requires pasting a URL instead of uploading a file.
- Expected behavior: Users should upload a replacement background image directly from local device.
- Reproduction steps:
  1. Open Smart Background Removal.
  2. Choose replacement background mode.
  3. Observe the input method.
- Impact: URL-only input is too technical and blocks normal users from completing the workflow.
- Suggested fix direction: Replace/augment URL input with an `input[type=file]` upload flow and reuse the existing image uploader component.

### BUG-011 — Sketch Instant Render is completely unavailable / API 404

- Severity: Critical / Blocker
- Source row: AI-05 Sketch Instant Render, result `Fail`
- Affected area: Sketch Instant Render / Room Redesign render flow
- Source wording: `全功能無法使用`, `API error:404`, `生成有誤`
- Observed issue: The feature cannot be used; generation returns API 404 and output is incorrect.
- Expected behavior: Sketch upload plus selected style should generate a realistic interior render matching the selected style.
- Reproduction steps:
  1. Open Sketch Instant Render.
  2. Upload an interior sketch.
  3. Select a style such as Scandinavian/Nordic.
  4. Click generate.
  5. Observe API response and output.
- Impact: Entire feature appears broken and blocks the sketch-to-render workflow.
- Suggested fix direction: Confirm route registration/deployment for sketch render endpoint, frontend endpoint path, Cloud Run deploy context, and backend handler mapping.

### BUG-012 — Image Translation has no effect

- Severity: Critical / Blocker
- Source row: 圖片翻譯, result `fail`
- Affected area: Image Translator
- Source wording: `無作用`
- Observed issue: Image Translation does not perform the expected action.
- Expected behavior: Uploaded image text should be detected, translated into the target language, and rendered back into the image layout.
- Reproduction steps:
  1. Open Image Translator.
  2. Upload an image containing readable text.
  3. Select source/target language.
  4. Click translate/generate.
  5. Inspect whether translated result appears.
- Impact: Core feature is non-functional.
- Suggested fix direction: Verify frontend submit handler, credit/permission gating, `/api/v1/tools/image-translate` route, provider result mapping, and result panel state update.

### BUG-013 — Annual subscription checkout routes to monthly-price payment page

- Severity: Critical / Blocker
- Source row: PAY-02 Purchase subscription plan, result `Fail`
- Affected area: Pricing / checkout / subscription payment
- Source wording: `年付頁面點支付會到月付價格支付頁面`
- Observed issue: Clicking payment from the annual plan page opens a monthly-price payment page.
- Expected behavior: Annual plan checkout should preserve annual billing interval and annual price through the payment flow.
- Reproduction steps:
  1. Open Pricing.
  2. Select annual billing.
  3. Choose a paid annual plan.
  4. Click payment/checkout.
  5. Verify amount and billing interval on payment page.
- Impact: Users may be charged/displayed the wrong price; this is a serious billing trust issue.
- Suggested fix direction: Validate billing interval state in frontend, checkout payload, backend order creation, and ECPay/payment page parameters.

### BUG-014 — User plan changes immediately after entering payment page and pressing back

- Severity: Medium
- Source row: PAY-03 Credit update confirmation, result `Fail`
- Affected area: Subscription lifecycle / payment callback handling
- Source wording: `點擊付款後到付款頁面回上一頁用戶方案會直接更改`
- Observed issue: After clicking payment and navigating to the payment page, pressing browser Back causes the user plan to change immediately, before confirmed payment completion.
- Expected behavior: Plan and credits should change only after verified successful payment callback/webhook.
- Reproduction steps:
  1. Select a paid plan.
  2. Click payment and reach the payment provider page.
  3. Use browser Back before completing payment.
  4. Check the user's plan in dashboard/account state.
- Impact: Users can receive plan changes without payment confirmation; revenue and entitlement logic are at risk.
- Suggested fix direction: Ensure order creation uses pending status only; apply plan changes only after trusted payment confirmation and idempotent webhook validation.

### BUG-015 — Cancel subscription immediately zeros account credits

- Severity: Medium
- Source row: PAY-04 Subscription management / cancel, result `Fail`
- Affected area: Subscription cancellation / credits
- Source wording: `取消後帳戶點數直接歸零`
- Observed issue: User credits become zero immediately after cancellation.
- Expected behavior: Cancellation should change subscription status to canceled/non-renewing, but current-period credits should remain usable until the end of the paid period unless policy says otherwise.
- Reproduction steps:
  1. Log in as a paid subscriber with remaining credits.
  2. Open subscription management.
  3. Cancel subscription.
  4. Check remaining credits immediately after cancellation.
- Impact: Paid users lose purchased/current-period value unexpectedly, causing support and refund risk.
- Suggested fix direction: Separate subscription renewal state from credit balance; do not clear credits on cancel unless explicitly expiring at period end.

### BUG-016 — Mobile Product Dynamic Video thumbnail does not display

- Severity: Low / UI polish
- Source row: UX-01 Responsive mobile design, result `Fail`
- Affected area: Mobile UI / Product Dynamic Video thumbnail
- Source wording: `動態短影音縮圖無顯示`
- Observed issue: Product Dynamic Video thumbnail is missing on mobile.
- Expected behavior: Thumbnail should render correctly in mobile layout with no overflow or hidden content.
- Reproduction steps:
  1. Open VidGo.co on a mobile browser/viewport.
  2. Navigate to Product Dynamic Video or homepage tool card section.
  3. Check whether the short-video thumbnail appears.
- Impact: Mobile users see incomplete UI and may not understand the tool preview.
- Suggested fix direction: Check responsive image sizing, lazy-loading, source URL, container height, and mobile breakpoints.

### BUG-017 — Non-Chinese language settings still show English operation UI

- Severity: Medium
- Source row: UX-02 Multi-language switching, result `Fail`
- Affected area: i18n / operation panels
- Source wording: `中文以外語言操作區仍為英文介面`
- Observed issue: When switching to non-Chinese languages, operation areas still display English UI.
- Expected behavior: Main content, menus, buttons, and operation panels should switch to the selected language.
- Reproduction steps:
  1. Click the language selector.
  2. Choose a non-Chinese language.
  3. Navigate through homepage and tool operation panels.
  4. Check labels, buttons, and form controls.
- Impact: International users get inconsistent localization and may not understand tool operation steps.
- Suggested fix direction: Audit locale message coverage for tool forms/components, especially operation panels, dropdowns, buttons, validation, and loading/result states.

## Cross-Cutting Blocker From UAT Summary

### BUG-018 — Most generation flows show failure and wait too long

- Severity: Critical / Blocker
- Source section: Overall Test Summary / Blockers-Critical Issues
- Source wording: `大部分生成顯示失敗，等待時間過長`
- Affected area: AI generation platform-wide
- Observed issue: Most generation flows show failure states and excessive waiting time.
- Expected behavior: Generation flows should show clear progress, complete within documented time budgets, and either return a usable result or a friendly actionable error with credit refund behavior.
- Reproduction steps:
  1. Run each core AI generation flow with standard test fixtures.
  2. Record request time, loading state, final status, and result visibility.
  3. Compare against expected time budgets per tool.
- Impact: This is a release blocker because it affects multiple core paid/free product workflows.
- Suggested fix direction: Add per-tool timeout/error telemetry, provider-status polling diagnostics, frontend stuck-state guards, credit-refund checks, and nightly E2E generation tests.

## Enhancement Requests From UAT

These were listed in the UAT summary as non-urgent but recommended improvements:

1. Improve generation effect/model quality.
   - Source wording: `生成效果模型優化`
2. Replace/update demo example images.
   - Source wording: `範例示範圖更改`
3. Replace/update demo example videos.
   - Source wording: `範例影片更改`

## Passed Areas Mentioned In Checklist

The source checklist marked these rows as passed and they are not included as bugs unless notes above indicate a related issue:

- UA-01 New user registration
- UA-02 User login
- UA-03 Password reset
- UA-04 Logout
- AI-01 AI Model Try-On
- AI-06 Commercial HD Upscale
- AI-07 Result download and save
- PAY-01 Pricing page browsing
- UX-03 Error prompt for unsupported file format
- UX-04 Page loading speed
