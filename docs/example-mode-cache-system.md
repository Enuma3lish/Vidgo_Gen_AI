# Example Mode — Cache-Through System

## Overview

Example mode provides a preset-only experience. Users cannot type prompts — they pick from our provided inputs and effects, then click generate. Results are cached in Redis forever, so only the first request per preset hits the AI provider.

## Architecture

```
User clicks preset
  │
  ▼
POST /api/v1/examples/{tool_type}/generate
  { "preset_id": "fx-bubbletea-anime" }
  │
  ▼
ExampleCacheService.generate_or_cache()
  │
  ├─ Redis GET "example:effect:fx-bubbletea-anime"
  │   ├─ HIT  → return cached result (instant)
  │   └─ MISS → continue ▼
  │
  ├─ Build params from preset config
  │   (prompt, image_url, duration, etc.)
  │
  ├─ ProviderRouter.route(TaskType.I2I, params)
  │   PiAPI MCP → Pollo MCP → Vertex AI → PiAPI REST
  │
  ├─ Persist result to GCS (permanent URL)
  │
  ├─ Redis SET "example:effect:fx-bubbletea-anime" (no TTL)
  │
  └─ Return result
```

## Components

### 1. Preset Config (`backend/app/config/example_presets.py`)

Complete, self-contained preset records for each tool. Each preset contains:

| Field | Purpose |
|-------|---------|
| `id` | Unique identifier, used as part of Redis cache key |
| `name` | Display name (en + zh) |
| `image_url` | GCS public URL for the input image |
| `params` | All parameters needed to call the AI provider |
| `gemini_prompt` | Prompt used to generate the input image (used by seed script) |

**7 tools with 4-6 presets each = ~37 total presets.**

All presets target small business / personal users:
- Products: bubble tea, fried chicken, bento, soap, cake, coffee, skincare, backpack
- No luxury brands, no high-end items
- Bilingual: English + Traditional Chinese

### 2. Cache Service (`backend/app/services/example_cache_service.py`)

Single service with the cache-through pattern:

```python
service = ExampleCacheService(redis_client)

# List presets for frontend display
presets = service.list_presets("effect")

# Generate or return cached
result = await service.generate_or_cache("effect", "fx-bubbletea-anime")
# → { "success": True, "from_cache": True/False, "image_url": "..." }

# Check cache warm-up status
status = await service.get_cache_status()
# → { "effect": { "total": 5, "cached": 3 }, ... }

# Invalidate (for re-generation)
await service.invalidate("effect", "fx-bubbletea-anime")
```

**Redis key format:** `example:{tool_type}:{preset_id}`

**Redis value:** JSON with result URLs, no TTL (stored forever)

### 3. API Endpoints (`backend/app/api/v1/example.py`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/examples/{tool_type}` | List available presets (id, name, thumbnail) |
| POST | `/api/v1/examples/{tool_type}/generate` | Generate or return cached result |
| GET | `/api/v1/examples/status/cache` | Cache warm-up status per tool |

### 4. Input Image Generation (`backend/scripts/generate_example_inputs.py`)

One-time script that generates input images using Gemini and uploads to GCS:

```bash
# Dry run — see what would be generated
cd backend
python -m scripts.generate_example_inputs --dry-run

# Generate all
python -m scripts.generate_example_inputs

# Generate only one tool
python -m scripts.generate_example_inputs --tool effect
```

Requires: `VERTEX_AI_PROJECT` (or `GEMINI_API_KEY`), `GCS_BUCKET`

### 5. GCS Public Upload (`backend/app/services/gcs_storage_service.py`)

New method `upload_public(data, blob_name)`:
- Uploads bytes to GCS bucket
- Calls `blob.make_public()` — URL never expires
- Returns permanent public URL: `https://storage.googleapis.com/{bucket}/{path}`

## Setup Steps

### 1. Generate input images

```bash
cd backend

# Set env vars
export VERTEX_AI_PROJECT=vidgo-ai
export GCS_BUCKET=vidgo-media-vidgo-ai

# Generate all input images
python -m scripts.generate_example_inputs
```

This creates images at:
```
gs://vidgo-media-vidgo-ai/examples/
  bg/bubbletea.png, fried-chicken.png, ...
  ps/bubbletea.png, fried-chicken.png, ...
  fx/bubbletea.png, fried-chicken.png, ...
  room/living-room.png, bedroom.png, ...
  vid/bubbletea.png, fried-chicken.png, ...
  avatar/yijun.png, zhiwei.png, ...
```

### 2. Deploy and warm cache (lazy)

Cache warms lazily — first user click per preset triggers generation. After that, it's instant.

To check warm-up progress:
```bash
curl https://api.vidgo.co/api/v1/examples/status/cache
```

### 3. (Optional) Pre-warm cache

If you want all presets cached before any user visits, hit each preset once:

```bash
for tool in background_removal product_scene effect room_redesign short_video ai_avatar pattern_generate; do
  curl -s "https://api.vidgo.co/api/v1/examples/$tool" | \
    python3 -c "import sys,json; [print(p['id']) for p in json.load(sys.stdin)['presets']]" | \
    while read id; do
      curl -s -X POST "https://api.vidgo.co/api/v1/examples/$tool/generate" \
        -H "Content-Type: application/json" \
        -d "{\"preset_id\": \"$id\"}"
      echo " → $tool/$id"
    done
done
```

## Adding New Presets

1. Add a new entry to the appropriate list in `example_presets.py`
2. Include a `gemini_prompt` for input image generation
3. Run `python -m scripts.generate_example_inputs --tool <tool_type>`
4. The new preset is immediately available via the API
5. First user click will generate and cache the result

## Cache Management

**View cached data:**
```bash
redis-cli KEYS "example:*"
redis-cli GET "example:effect:fx-bubbletea-anime"
```

**Invalidate one preset:**
```bash
redis-cli DEL "example:effect:fx-bubbletea-anime"
```

**Invalidate all presets for a tool:**
```bash
redis-cli KEYS "example:effect:*" | xargs redis-cli DEL
```

## Tool → TaskType Mapping

| Tool Type | TaskType (ProviderRouter) | Primary Provider |
|-----------|--------------------------|-----------------|
| background_removal | BACKGROUND_REMOVAL | PiAPI MCP |
| product_scene | T2I | PiAPI MCP |
| effect | I2I | PiAPI MCP |
| room_redesign | INTERIOR | PiAPI MCP |
| short_video | I2V | PiAPI MCP |
| ai_avatar | AVATAR | PiAPI MCP |
| pattern_generate | T2I | PiAPI MCP |

## File Reference

| File | Purpose |
|------|---------|
| `backend/app/config/example_presets.py` | Preset definitions (inputs + params) |
| `backend/app/services/example_cache_service.py` | Cache-through logic |
| `backend/app/api/v1/example.py` | REST endpoints |
| `backend/scripts/generate_example_inputs.py` | Gemini → GCS image generator |
| `backend/app/services/gcs_storage_service.py` | `upload_public()` for permanent URLs |
| `backend/app/api/api.py` | Router registration |
