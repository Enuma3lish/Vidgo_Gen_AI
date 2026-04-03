# VidGo — Next Steps

Last updated: 2026-04-03

---

## 1. CRITICAL: MCP Integration Testing

The MCP providers were just fixed (tool names, parameter schemas, model structure were all wrong). These must be tested before anything else.

### 1a. Smoke-test MCP server connections

```bash
# Start the stack
docker compose up -d postgres redis backend

# Check MCP health in logs
docker logs vidgo_backend 2>&1 | grep -i mcp

# Hit the health endpoint — verify MCP servers connected
curl http://localhost:8001/api/v1/admin/provider-status
```

Expected: both `pollo_mcp` and `piapi_mcp` show `connected: true` with tool lists.

### 1b. Test PiAPI MCP tools individually

Each tool name and parameter was wrong before. Verify each works:

| Tool | Test endpoint | What to check |
|------|--------------|---------------|
| `generate_image` (T2I) | POST `/api/v1/generation/image` with prompt | Returns image URL |
| `derive_image` (I2I) | POST `/api/v1/effects/apply` with image + style | Returns styled image |
| `image_upscale` | POST `/api/v1/generation/upscale` | Returns upscaled image |
| `image_rmbg` | POST `/api/v1/tools/background-removal` | Returns transparent PNG |
| `generate_video_wan` (T2V) | POST `/api/v1/generation/video` | Returns video URL |
| `generate_video_wan` (I2V) | POST `/api/v1/generation/video` with image | Returns video URL |
| `generate_video_kling` (avatar) | POST `/api/v1/tools/avatar` | Returns video URL |
| `generate_3d_model` | POST `/api/v1/tools/3d-model` | Returns GLB model URL |
| `tts_zero_shot` | POST `/api/v1/tools/tts` | Returns audio URL |

### 1c. Test Pollo MCP model parameter

The `model` param was changed from flat string to nested `{modelBrand, modelAlias}`.

```bash
# Test text-to-video with default model (pollo-v1-6)
curl -X POST http://localhost:8001/api/v1/generation/video \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A cup of bubble tea, close-up, cinematic"}'

# Test with explicit model (kling)
curl -X POST http://localhost:8001/api/v1/generation/video \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A cat walking", "model": "kling-v2"}'
```

### 1d. Test provider failover

1. Set `POLLO_API_KEY=""` temporarily — video requests should fall through to PiAPI MCP (`generate_video_wan`), then to Pollo REST.
2. Set `PIAPI_KEY=""` temporarily — image requests should fall through to Gemini.

---

## 2. CRITICAL: Security Cleanup

### 2a. Remove secrets from git history

`backend/.env` has been committed with all API keys. Even though `.gitignore` lists `.env`, the file was tracked before the ignore rule was added.

```bash
# Remove .env from tracking (keeps local file)
git rm --cached backend/.env

# Remove .DS_Store from tracking
git rm --cached .DS_Store backend/.DS_Store

# Commit the removal
git commit -m "chore: remove tracked .env and .DS_Store files"
```

For full history scrubbing (rotate all keys after this):
```bash
pip install git-filter-repo
git filter-repo --path backend/.env --invert-paths
```

### 2b. Rotate all API keys

After removing `.env` from history, rotate:
- PIAPI_KEY
- POLLO_API_KEY
- GEMINI_API_KEY
- A2E_API_KEY
- Paddle API keys
- ECPay credentials
- SMTP password

### 2c. Move secrets out of `gcp/deploy.sh`

Lines 78-90 in `deploy.sh` contain hardcoded secrets. Move to GCP Secret Manager:
```bash
echo -n "your-api-key" | gcloud secrets create PIAPI_KEY --data-file=-
```

Then reference in Cloud Run via `--set-secrets`.

---

## 3. Run Pre-generation Pipeline

The pre-generation scripts use direct REST clients (not MCP), so they should work independently. But verify after all the recent changes:

```bash
# Dry run first
docker compose --profile tools run --rm pregenerate \
  python -m scripts.main_pregenerate --dry-run

# Generate a single tool to test
docker compose --profile tools run --rm pregenerate \
  python -m scripts.main_pregenerate --tool background_removal --limit 3

# Full generation (expensive — review TOOL_LIMITS first)
docker compose --profile init up init-materials
```

---

## 4. Frontend Validation

After MCP fixes, test the frontend tool views end-to-end:

| View | Route | Test |
|------|-------|------|
| Short Video | `/tools/short-video` | Generate video from prompt |
| Image Effects | `/tools/effects` | Upload image, apply style |
| Background Removal | `/tools/bg-removal` | Upload image, remove BG |
| Room Redesign | `/tools/room-redesign` | Select room + style |
| Product Scene | `/tools/product-scene` | Product on scene background |
| Try-On | `/tools/try-on` | Model + garment |
| AI Avatar | `/tools/avatar` | Avatar video generation |
| Pattern Design | `/tools/pattern` | Generate pattern |

---

## 5. Testing Infrastructure

### 5a. Run existing tests

```bash
cd backend
python -m pytest tests/ -v
```

### 5b. Run E2E tests

```bash
cd TEST
python e2e_tools_test.py --base-url http://localhost:8001
```

### 5c. Add MCP-specific tests

Currently missing — add tests that verify:
- MCP server connection lifecycle (start, reconnect, shutdown)
- Tool name resolution (TOOL_MAP maps to actual server tools)
- Parameter transformation (internal format → MCP format)
- Response normalization (raw text → structured dict)
- Failover (MCP down → REST fallback)

---

## 6. CI/CD Pipeline

`.github/` exists but has no workflow files. Add GitHub Actions:

### 6a. PR checks
- Python linting (ruff)
- Backend unit tests
- Frontend build check (`npm run build`)
- Docker build check

### 6b. Deployment
- `cloudbuild.yaml` exists for GCP Cloud Build
- Consider triggering from GitHub Actions or Cloud Build triggers

---

## 7. Monitoring & Observability

### 7a. Provider health dashboard
- Log MCP connection state changes
- Track per-provider success/failure rates
- Alert when primary provider goes down

### 7b. Cost tracking
- Track API credit usage per provider
- Track per-user generation costs
- Alert on unusual spending

---

## 8. Feature Gaps to Consider

| Feature | Status | Notes |
|---------|--------|-------|
| Virtual Try-On via MCP | Not available | PiAPI MCP has no try-on tool; falls to REST |
| Video watermarking | Incomplete | Image watermarks work; video watermarks are pass-through |
| Token blacklisting | TODO in code | `auth.py:155` — implement with Redis |
| Cloud storage upload | TODO in code | `image_generator.py:156` — use GCS service |
| Social media posting | Partial | Facebook/Instagram auth done; TikTok pending |

---

## Priority Order

1. **MCP smoke testing** (verify the fixes actually work)
2. **Security cleanup** (secrets in git history)
3. **E2E tool testing** (each frontend tool works end-to-end)
4. **Pre-generation validation** (materials DB populated correctly)
5. **CI/CD setup** (prevent regressions)
6. **Monitoring** (know when things break in production)
