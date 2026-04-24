# Full Test Report

Date: 2026-04-20
Environment: Production
Frontend: <https://vidgo.co>
Backend: <https://api.vidgo.co>

## Summary

Production redeploy completed successfully.

Verified fixes:

- Background removal now returns a public GCS URL and the generated image is reachable.
- Admin analytics endpoints return 200 instead of 500.
- Frontend upscale upload-button regression was fixed in the Vue app and the production frontend redeployed successfully.
- Backend now normalizes backend-local `/static/...` media paths to absolute public URLs before returning provider results.

Latest production deploy:

- Backend: `vidgo-backend-00063-496`
- Worker: `vidgo-worker-00028-4n9`
- Frontend: `vidgo-frontend-00039-5vx`

Open issues:

- Live upscale is still failing in production because both upstream providers failed during generation after the latest deploy validation run.
- PiAPI returned HTTP 500 for the upscale task.
- Vertex AI fallback returned `No image in Imagen edit response`.
- Product Scene paid generation was timing out in the browser because the frontend request timeout was too short for the synchronous backend path. The frontend timeout fix has now been deployed in `vidgo-frontend-00039-5vx`.
- Short Video is still failing server-side after the frontend deploy. Production logs show the full fallback chain failing: PiAPI I2V returned `failed to freeze account point quota` or `invalid request` / `failed to get valid image`, Pollo MCP fell back from missing `img2video_pixverse_v4.5` to `img2video_pollo-v1-6` and then failed or timed out after 600s, and Vertex AI failed with `Publisher Model projects/vidgo-ai/locations/asia-east1/publishers/google/models/veo-3.0-generate-preview was not found or your project does not have access to it`.
- Because generation failed before a result image was produced, the new absolute-URL normalization path could not be verified end-to-end from the live API after redeploy.
- Browser/manual testing against production still shows multiple visitor and paid-user generation flows that either stall, surface placeholder-only results, or do not produce semantically trustworthy outputs.
- A stale browser access token can make paid tools look broken: optional-auth tool endpoints silently downgrade invalid tokens to demo mode instead of returning 401, while the frontend can still show cached paid UI.

## Latest Follow-Up

### Frontend Redeploy

- Deployed frontend revision: `vidgo-frontend-00039-5vx`
- Traffic: `100%` on latest revision
- Service URL: `https://vidgo-frontend-r2laip67ma-de.a.run.app`

### Product Scene

- Direct production API validation returned success after about `123s`.
- Root cause was frontend timeout, not missing result rendering logic.
- The longer per-request timeout has now been deployed with the frontend revision above.

### Short Video

- Direct production API validation still failed after about `621s`.
- Backend/provider diagnosis from Cloud Run logs:
  - PiAPI `wan26-img2video` failed with either quota freeze failure or invalid input image retrieval.
  - Pollo MCP does not have the requested `img2video_pixverse_v4.5` tool in production and falls back to `img2video_pollo-v1-6`, which then fails or times out.
  - Vertex AI Veo fallback is configured to a publisher model that the current project/region cannot access.
- Conclusion: the remaining Short Video failure is backend/provider-side and is not solved by the frontend redeploy.

## Production Checks

### 1. Service Reachability

Backend health:

```json
{"status":"ok","mode":"preset-only","materials_ready":false}
```

Frontend reachability:

- `https://vidgo.co` returned HTTP 200.

### 2. Authentication

Working admin account used for tests:

- `qaz0978005418@gmail.com`

Result:

- Login succeeded.
- API response returned `tokens.access` and `tokens.refresh`.
- After refreshing the browser session token, `GET /api/v1/auth/me` confirmed this account resolves to `plan_type: pro` and `is_superuser: true`.

Notes:

- `vidgo168@gmail.com / Vidgo96003146` failed in production.
- `qa_test_01@vidgo.local` is rejected by email validation because `.local` is a reserved domain.
- Earlier paid-tool checks were partially contaminated by a stale browser access token. Protected endpoints such as `/api/v1/auth/me` rejected that stale token, but optional-auth tool endpoints silently fell back to demo mode.

### 3. Admin Analytics

Verified endpoints:

- `GET /api/v1/admin/stats/dashboard`
- `GET /api/v1/admin/stats/api-costs`

Result:

- Both returned HTTP 200.
- Dashboard returned user and paid-plan counts.
- API costs returned default empty totals instead of 500.

### 4. Background Removal

Endpoint:

- `POST /api/v1/tools/remove-bg`

Input:

- Remote image URL from Unsplash

Result:

```json
{
  "success": true,
  "result_url": "https://storage.googleapis.com/vidgo-media-vidgo-ai/generated/image/a97a9098fce1.png"
}
```

Verification:

- `curl -I` to the returned `result_url` returned HTTP 200.
- Content type was `image/png`.

Status:

- Passed

### 5. Upscale Before URL Fix Deploy

Endpoint:

- `POST /api/v1/tools/upscale`

Input:

- Same remote image URL from Unsplash

Result before latest backend patch:

```json
{
  "success": true,
  "result_url": "/static/generated/vertex_8ccda615.png"
}
```

Verification:

- `https://api.vidgo.co/static/generated/vertex_8ccda615.png` returned HTTP 200.
- `https://vidgo.co/static/generated/vertex_8ccda615.png` returned HTTP 404.

Conclusion:

- Relative backend-local result URLs are broken for the frontend domain.

### 6. Upscale After URL Fix Deploy

Backend patch deployed in revision:

- `vidgo-backend-00060-pj2`

Code change:

- Backend provider router now converts backend-local `/static/...` result paths into absolute URLs using `PUBLIC_APP_URL` before the API returns them.

Live validation result after deploy:

```json
{
  "success": false,
  "message": "Upscale failed: Image generation services are experiencing issues. Please try again in a few minutes."
}
```

Related production logs:

- `Provider piapi failed for TaskType.UPSCALE: PiAPI request failed`
- `Server error '500 Internal Server Error' for url 'https://api.piapi.ai/api/v1/task'`
- `Provider vertex_ai failed for TaskType.UPSCALE: vertex_ai soft-failed: No image in Imagen edit response`

Status:

- Failed due to upstream generation providers, not due to the previously observed relative-URL bug.

### 7. Visitor Browser Validation On Latest Production Deploy

Frontend tested:

- `https://vidgo.co`

- Visitor / unauthenticated session

#### 7.1 Background Removal - Visitor Example Mode

Flow:

- Open `/tools/background-removal`
- Select built-in example
- Click `Remove Background`

Observed behavior:

- Demo flow completed successfully.
- Distinct original and result assets rendered in the DOM.
- Result image was served from public GCS watermarked output.

Status:

- Passed

#### 7.2 Product Scene - Visitor Example Mode

Flow:

- Open `/tools/product-scene`
- Select preset product and preset scene
- Click `Generate`

Observed behavior:

- Demo flow completed and showed `Generated successfully (Demo)`.
- Result image rendered from public GCS watermarked output.
- Visitor flow is functional as a preset-only demo.

Status:

- Passed

#### 7.3 Try-On - Visitor Example Mode

Flow:

- Open `/tools/try-on`
- Select preset clothing and preset model
- Click `Generate`

Observed behavior:

- Demo flow completed and showed `Generated successfully (Demo)`.
- Result image rendered from public GCS watermarked output.

Status:

- Passed

#### 7.4 Short Video - Visitor Example Mode

Flow:

- Open `/tools/short-video`
- Select built-in example clip
- Click `View Result`

Observed behavior:

- Visitor example selection worked.
- Demo result path showed `Generated successfully (Demo)`.
- Generated/demo video assets were present in the DOM.

Status:

- Passed

#### 7.5 Room Redesign - Visitor Example Mode

Flow:

- Open `/tools/room-redesign`
- Select a public style example
- Click `View Example`

Observed behavior:

- Visitor UI exposed curated examples as intended.
- After selecting a style and opening the example, the page stayed in loading/placeholder state.
- Result panel did not advance to a visible rendered design during the manual check.

Status:

- Failed

#### 7.6 Upscale - Visitor Demo Mode

Flow:

- Open `/tools/upscale`
- Select a built-in demo image
- Click `Upscale 2x`

Observed behavior:

- Result area appeared and the flow advanced.
- DOM image inspection showed the same Unsplash source image reused instead of a clearly distinct upscaled result asset.

Status:

- Failed semantically

#### 7.7 Pattern Generate - Visitor Mode

Flow:

- Open `/tools/pattern-generate`
- Select preset prompt
- Click `Generate`

Observed behavior:

- Visitor page is reachable.
- Example interaction still funnels toward `Subscribe Now` rather than surfacing a generated visitor result.

Status:

- Effectively paywalled / no usable visitor result

#### 7.8 Avatar - Visitor Mode

Flow:

- Open `/tools/avatar`
- Select preset script and preset avatar
- Click `Generate`

Observed behavior:

- Flow entered `Generating in real-time (3-5 min)...`.
- Manual browser window did not reach a completed result during the check window.

Status:

- Inconclusive

### 8. Paid User Browser Validation On Latest Production Deploy

Authenticated account:

- `qaz0978005418@gmail.com`

Local upload fixtures used:

- `qa/fixtures/product_test.svg.png` - single-product camera photo used for product-scene and short-video uploads
- `qa/fixtures/person_test.svg.png` - realistic portrait/model photo used for avatar and try-on style uploads
- `qa/fixtures/room_test.jpg` - indoor living-room photo used for room-redesign validation
- `qa/fixtures/test.jpg` - neutral backup product photo for generic upload checks

Authentication note:

- Reliable paid login required using the real `/auth/login` form with typed inputs.
- After correct login, dashboard showed `pro` and a 10k+ credit balance.
- Some tool pages still showed inconsistent credit/session rendering during client-side transitions.

#### 8.1 Background Removal - Uploaded Product Image

Flow:

- Login to production frontend
- Open `/tools/background-removal`
- Upload `qa/fixtures/product_test.svg.png`
- Click `Remove Background`

Observed behavior:

- Initial stale-token session misleadingly behaved like a demo/downgraded flow.
- After refreshing the browser session token, upload control accepted the file and generation completed successfully.
- Result panel rendered a downloadable output (`Download Result`).
- Credit balance decreased from `10,083` to `10,080` during the successful recheck.

Status:

- Passed after fresh auth

Assessment:

- The earlier failure was caused by stale auth, not by background-removal generation itself.

#### 8.2 Product Scene - Uploaded Product Image

Flow:

- Open `/tools/product-scene`
- Upload `qa/fixtures/product_test.svg.png`
- Select `Nature`
- Click `Generate`

Observed behavior:

- Initial stale-token session returned demo content instead of subscriber generation.
- After refreshing auth, the page loaded in a valid paid state and the Generate button became enabled.
- Browser automation still could not observe a completed result panel after clicking Generate.
- Direct live API check with the same fresh token succeeded and returned `https://storage.googleapis.com/vidgo-media-vidgo-ai/generated/image/product_scene_4fa78ee8.png`.

Status:

- Browser inconclusive; backend passed

Assessment:

- Product-scene backend generation is working for the paid account. The remaining issue is browser/UI interaction or page-state observation, not the API path itself.

#### 8.3 Short Video - Uploaded Product Image

Flow:

- Open `/tools/short-video`
- Upload `qa/fixtures/product_test.svg.png`
- Select built-in motion example
- Click `View Result`

Observed behavior:

- With a fresh paid session, upload control accepted the file, motion/model controls appeared, and the primary action was enabled.
- Browser automation timed out after clicking `View Result`, but the page state did not advance to a visible generated result.
- Generated panel still showed placeholder text during the longer wait-window recheck.

Status:

- Inconclusive / unstable

Assessment:

- This is better than the previous disabled-button behavior, but it still did not produce a completed visible result during the live manual pass.

#### 8.4 Try-On - Custom Model Upload + Preset Garment

Flow:

- Open `/tools/try-on`
- Select preset garment `Floral Midi Dress`
- Open `Upload Custom Model`
- Upload `qa/fixtures/person_test.svg.png`
- Click `Generate`

Observed behavior:

- Preset garment selection worked
- Custom model upload control accepted the portrait fixture
- Flow entered `Processing...`
- Result panel did not reach a completed rendered try-on output during the manual check window

Status:

- Inconclusive / unstable

#### 8.5 Upscale - Uploaded Product Image

Flow:

- Open `/tools/upscale`
- Upload `qa/fixtures/product_test.svg.png`
- Click `Upscale 2x`

Observed behavior:

- Upload control accepted the file
- Action button became enabled
- UI showed explicit error: `Upscale failed: Image generation services are experiencing issues. Please try again in a few minutes.`

Status:

- Failed

#### 8.6 Room Redesign - Paid Controls

Flow:

- Open `/tools/room-redesign`

Observed behavior:

- Paid-only design tabs and room-photo upload control were visible in authenticated mode.
- A real local room-photo fixture (`qa/fixtures/room_test.jpg`) was uploaded successfully.
- The page still behaved inconsistently between `Browse Examples` and `Generate Design` states, and generation could not be confirmed from the browser UI.

Status:

- Inconclusive / suspicious UI state

#### 8.7 Avatar - Paid Controls

Flow:

- Open `/tools/avatar`

Observed behavior:

- Authenticated route exposed portrait upload and custom-script controls as expected.
- Full avatar generation was not executed in the paid pass because it is a multi-minute asynchronous workflow and earlier visitor check already showed long-running generation behavior.

Status:

- UI coverage only

#### 8.8 Pattern Generate - Authenticated Example Flow

Flow:

- Open `/tools/pattern-generate`
- Select example prompt
- Click `Generate`

Observed behavior:

- Authenticated page exposed custom prompt input and enabled generation.
- Button transitioned to `Processing...`
- No generated result asset appeared during the manual check window.
- Page still surfaced a `Subscribe Now` CTA near the lower section even in authenticated mode.

Status:

- Inconclusive / suspicious UX state

## Deployment Result

Successful rollout revisions:

- Backend: `vidgo-backend-00063-496`
- Worker: `vidgo-worker-00028-4n9`
- Frontend: `vidgo-frontend-00038-v27`

## 9. Post-Redeploy Rerun On Fresh Production Revisions

Redeploy result:

- Backend: `vidgo-backend-00063-496`
- Worker: `vidgo-worker-00028-4n9`
- Frontend: `vidgo-frontend-00038-v27`

Health check:

```json
{"status":"ok","mode":"preset-only","materials_ready":false}
```

### 9.1 Paid Dashboard Refresh

Flow:

- Re-open `https://vidgo.co/dashboard` after deploy completion

Observed behavior:

- Dashboard loaded successfully on the fresh frontend session.
- Authenticated admin session remained valid.
- Dashboard showed `pro` plan and refreshed recent works cards.

Status:

- Passed

### 9.2 Background Removal - Fresh Post-Deploy Rerun

Flow:

- Open `/tools/background-removal`
- Upload `qa/fixtures/product_test.svg.png`
- Click `Remove Background`

Observed behavior:

- Generation completed successfully on the fresh deployment.
- Result panel rendered a downloadable output (`Download Result`).
- A success toast appeared.

Status:

- Passed

### 9.3 Product Scene - Fresh Post-Deploy Rerun

Flow:

- Open `/tools/product-scene`
- Upload `qa/fixtures/product_test.svg.png`
- Select `Nature`
- Click `Generate`

Observed behavior:

- Browser accepted the upload and scene selection.
- Generate click registered, but the fresh rerun did not surface a visible downloaded/generated result in the browser state after waiting.
- This remains inconsistent with earlier successful browser/direct API evidence.

Status:

- Browser inconclusive / unstable

### 9.4 Short Video - Fresh Post-Deploy Rerun

Flow:

- Open `/tools/short-video`
- Upload `qa/fixtures/product_test.svg.png`
- Select the first example motion preset
- Click `View Result`

Observed behavior:

- On the fresh frontend, the page now visibly entered `Generating video... This may take a few minutes` after the click.
- This is an improvement over the earlier silent placeholder-only behavior.
- After waiting, the page returned to the placeholder `Generated video will appear here` state without surfacing `Download Video` or a visible completed result.

Status:

- Improved but still failed to complete visibly

## Current Assessment

Resolved:

- Broken background-removal delivery path
- Backend memory increase deployment
- PiAPI MCP disabled in production routing
- Admin analytics 500
- Frontend upscale upload button disabled state
- Backend absolute URL normalization for local static media paths

Still unresolved:

- Live upscale provider reliability in production
- Product-scene browser flow is still inconsistent after redeploy; a fresh paid rerun again failed to surface a visible completed result even though earlier direct paid API generation succeeded
- Short-video paid flow now surfaces a real `Generating video...` state after redeploy, but still did not complete to a visible downloadable result during the manual browser pass
- Room-redesign visitor example mode did not render a finished example result
- Room-redesign paid generation UI is still inconsistent after a real room-photo upload
- Visitor upscale result is not semantically distinguishable from the source image
- Pattern generation processing/result handling remains unclear in both visitor and paid flows
- Stale browser access tokens can silently downgrade paid tool requests to demo mode because optional-auth endpoints do not force a refresh or 401 path

## Recommended Next Step

Investigate live upscale provider behavior separately from URL handling:

- Decide whether to keep PiAPI as primary for upscale.
- Inspect why Vertex AI intermittently returns no edited image.
- Add a stable upscale fallback or force persistence to GCS for successful local-static outputs when providers recover.

Then investigate uploaded-input browser flows end-to-end in production:

- Inspect frontend state transitions after upload for product-scene, short-video, and room-redesign after a valid auth refresh.
- Ensure paid/demo gating revalidates auth before trusting cached `plan_type`, so expired access tokens cannot masquerade as paid sessions.
- Add explicit UI error surfacing when generation completes without a valid new result asset.
- Add timeout/final-state handling for long-running paid flows so the UI does not remain in silent placeholder states.
