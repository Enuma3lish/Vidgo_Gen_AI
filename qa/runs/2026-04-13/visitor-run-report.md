# Visitor / Unpaid-User Run Report — Docker Env
**Date:** 2026-04-13
**Env:** local docker (`http://localhost:8501`)
**Persona:** P1 anonymous visitor (no signup, no `access_token`)
**Driver:** Playwright MCP

## Setup
- `docker compose up -d` — 5 containers healthy: postgres, redis, mailpit, backend, frontend
- `docker compose exec -T backend python -m scripts.seed_demo_fixtures` → 26 Material rows across 7 tool types (public Unsplash / sample-video URLs, `source=SEED`)
- Seeding was needed because this env has no GCS ADC / Vertex / working PiAPI MCP, so on-demand cache-through couldn't generate results. Fixtures bypass providers entirely and prove the UI flow.

## Rules enforced
1. Any user can click example presets without limit
2. Only paid users can upload
3. Only paid users can select different AI models
4. Only paid users can download

## Results per tool

| Tool | Route | Presets shown | Upload hidden | Model selector hidden | Download hidden | Generate click → result | Overall |
|---|---|---|---|---|---|---|---|
| Background Removal | /tools/background-removal | 4 tiles | ✅ | n/a | ✅ → "Subscribe for Full Access" | ✅ image rendered | **PASS** |
| Virtual Try-On | /tools/try-on | 4 clothing tiles + 6 personas | ✅ | persona open (intentional, it's preset-browsing not AI model choice) | ✅ → "Subscribe for Full Access" | ✅ image rendered | **PASS** |
| AI Avatar | /tools/avatar | 8 tiles (avatars + scripts) | ✅ | n/a | ✅ | ✅ UI reachable | **PASS** |
| Image Effects / Style Clone | /tools/effects | 15 tiles (4 demo images + 11 styles) | ✅ | n/a | ✅ | ✅ UI reachable, "AI Transform requires subscription" badge | **PASS** |
| Product Scene | /tools/product-scene | 8 tiles | ✅ | n/a | ✅ | ✅ | **PASS** |
| Room Redesign | /tools/room-redesign | gallery tabs + style cards | ✅ | n/a | ✅ (Generate tab marked Pro) | ✅ gallery browse | **PASS** |
| Short Video | /tools/short-video | 4 example reels | ✅ | ✅ **"Subscribers Only" + "🔒 Upgrade to choose different AI models"**, Pixverse/Kling names hidden | ✅ | ✅ | **PASS** |
| HD Upscale | /tools/upscale | 4 demo tiles | ✅ (shows tiles, not uploader) | n/a (2x/4x is quality not AI model) | ✅ → "Subscribe to download HD" | ✅ 2x preview rendered | **PASS** |

8 / 8 tools reachable and functional for visitors. All four gating rules pass.

## Fixes applied during this run
- [useDemoMode.ts](../../../frontend-vue/src/composables/useDemoMode.ts) — exposed `isPaid` alias
- [ShortVideo.vue:521](../../../frontend-vue/src/views/tools/ShortVideo.vue#L521) — replaced CSS `opacity-50 pointer-events-none` with hard `v-if="isSubscribed"` on the AI model grid
- [ImageUpscale.vue](../../../frontend-vue/src/views/tools/ImageUpscale.vue) — reverted my earlier too-aggressive "full splash" gate (which hid the tool entirely). Now visitors see: 4 demo tiles, no uploader, 2x/4x selector, Upscale button, and a "Subscribe to download HD" CTA on the result. Demo click shows a preview using the example URL itself. Real upscale stays paid-only.
- [backend/scripts/seed_demo_fixtures.py](../../../backend/scripts/seed_demo_fixtures.py) — new script seeding 26 Material rows (background_removal, product_scene, try_on, room_redesign, short_video, ai_avatar, effect) from public Unsplash + Google sample video URLs. Re-runnable (deletes existing `source=SEED` rows first).

## Provider status in docker env (for context)
- **PiAPI MCP** — node module `mcp-proxy/dist/index.js` missing. MCP connect fails after 3 retries.
- **Vertex AI** — "Your default credentials were not found" (no ADC file at `~/.config/gcloud/application_default_credentials.json`)
- **REST PiAPI fallback** — configured but [provider_router.py:148](../../../backend/app/providers/provider_router.py#L148) treats `{"success": false}` as a valid response and returns it without moving to the next provider. The REST fallback never actually runs when Vertex returns success=false. This is a latent bug in the fallback chain, but it's out of scope for today's visitor test.

**Implication:** The cache-through path documented in [demo_cache_service.py](../../../backend/app/services/demo_cache_service.py) (`_generate_on_demand`) doesn't work in local docker without credentials. For now, visitors rely on pre-seeded Material rows. Real cache-through can be validated on GCP staging where ADC and provider keys exist.

## Notes
- `/tools/image-upscale` (the old route I was testing against) is 404; correct route is `/tools/upscale`. Noted in passing.
- The TryOn persona model grid (female-1..male-3) is intentionally open to visitors because it's part of preset browsing (each persona has different pre-generated clothing results). This is **not** the same as an "AI model" selector and does not violate Rule 3.
- ImageEffects "AI Transform" tab shows a "requires subscription" lock badge on the custom-prompt path, while the "Style Presets" tab is open to visitors.
