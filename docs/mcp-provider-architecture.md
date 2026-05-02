# VidGo AI — Provider Architecture

## Overview

VidGo routes generation through two lanes. The normal path starts with MCP providers, while explicit model choices and REST-only tools go directly to REST APIs. Trellis image-to-3D is REST-only through PiAPI, and Pollo model selections such as Pixverse, Kling, or Luma go through Pollo REST so the chosen model ID is honored. Google Vertex AI is used directly via SDK for Gemini image/moderation and Veo video backup.

```text
FastAPI Backend (Python)
│
├── MCPClientManager (singleton)
│   ├── piapi-mcp-server ← stdio transport → PiAPI API
│   └── pollo-mcp (npm)  ← stdio transport → Pollo.ai API
│
├── ProviderRouter
│   ├── PiAPIMCPProvider  (normal primary: video + image/specialized)
│   ├── PiAPIProvider     (REST lane: explicit PiAPI model choices + 3D)
│   ├── PolloMCPProvider  (normal video backup)
│   ├── PolloProvider     (REST lane: explicit Pollo model choices)
│   ├── VertexAIProvider  (Gemini: image backup + moderation; Veo: 3rd video backup)
│   ├── A2EProvider       (avatar backup)
│
└── GCSStorageService
    └── Downloads CDN URLs → uploads to GCS bucket
```

## Provider Routing

### Task → Provider Mapping

| Task | Normal Path | REST-First Exception | Backup Path |
| ---- | ----------- | -------------------- | ----------- |
| **Text-to-Video** | PiAPI MCP | Explicit PiAPI model → PiAPI REST; explicit Pollo model → Pollo REST | Pollo MCP → Vertex AI Veo → PiAPI REST |
| **Image-to-Video** | PiAPI MCP | Explicit PiAPI model → PiAPI REST; explicit Pollo model → Pollo REST | Pollo MCP → Vertex AI Veo → PiAPI REST |
| **Video Style Transfer** | PiAPI MCP | Explicit PiAPI model → PiAPI REST; explicit Pollo model → Pollo REST | Pollo MCP → Vertex AI Veo → PiAPI REST |
| **Text-to-Image** | PiAPI MCP | Explicit PiAPI model → PiAPI REST | PiAPI REST → Vertex AI Gemini → Pollo REST |
| **Image-to-Image** | PiAPI MCP | Explicit PiAPI model → PiAPI REST | PiAPI REST → Vertex AI Gemini |
| **Image Effects** | PiAPI MCP | Explicit PiAPI model → PiAPI REST | PiAPI REST → Vertex AI Gemini |
| **Upscale** | PiAPI MCP | Explicit PiAPI model → PiAPI REST | PiAPI REST → Vertex AI Gemini |
| **Background Removal** | PiAPI MCP | Explicit PiAPI model → PiAPI REST | PiAPI REST → Vertex AI Gemini |
| **Interior Design** | PiAPI MCP | Explicit PiAPI model → PiAPI REST | PiAPI REST → Vertex AI Gemini |
| **3D Model** | — | PiAPI REST Trellis via `/api/v1/interior/3d-model` | — |
| **Avatar** | PiAPI MCP | Explicit PiAPI model → PiAPI REST | PiAPI REST → A2E |
| **Moderation** | Vertex AI Gemini | — | — |
| **Material Generation** | Vertex AI Gemini | — | — |

### Routing Flow

```
Request → ProviderRouter.route(task_type, params)
  │
  ├─ 1. Choose lane
  │     ├─ No explicit model and not 3D → MCP-first normal path
  │     └─ Explicit model or 3D → matching REST API first
  │
  ├─ 2. Try PRIMARY provider for that lane
  │     └─ Success → persist to GCS → return result
  │
  ├─ 3. Try BACKUP (MCP, REST, or Vertex AI)
  │     └─ Success → persist to GCS → return result
  │
  ├─ 4. Try TERTIARY (Vertex AI Veo — video only)
  │     └─ Success → persist to GCS → return result
  │
  └─ 5. All failed → user-friendly error
```

### Provider Health & Circuit Breaker

- Provider health checks are cached for `PROVIDER_HEALTH_CACHE_SECONDS` to avoid slow checks on every request.
- Runtime provider failures increment an in-memory failure counter.
- After `PROVIDER_CIRCUIT_BREAKER_FAILURES` failures, the provider is marked down and its circuit opens for `PROVIDER_CIRCUIT_BREAKER_COOLDOWN_SECONDS`.
- While the circuit is open, routing skips that provider when another fallback is available.
- If every provider in a route has an open circuit, the router probes the primary provider so recovery is still possible.
- Status checks call provider `health_check()` and close the circuit after a successful probe.
- Provider failure emails are still rate-limited by `PROVIDER_ALERT_COOLDOWN_MINUTES`.

## MCP Client Manager

**File**: `backend/app/services/mcp_client.py`

Manages MCP server subprocess lifecycle:

- **Startup**: Starts MCP servers as Node.js subprocesses via stdio transport
- **Connection**: Initializes MCP sessions, caches available tools
- **Auto-reconnect**: Retries on connection failure (3 attempts with backoff)
- **Shutdown**: Gracefully terminates subprocesses on app shutdown

### Configuration

| Env Variable | Description |
|---|---|
| `PIAPI_KEY` | PiAPI API key (enables piapi-mcp-server) |
| `PIAPI_MCP_PATH` | Path to built piapi-mcp-server `dist/index.js` |
| `POLLO_API_KEY` | Pollo.ai API key (enables pollo-mcp server) |

### Lifecycle

```python
# Startup (in main.py lifespan)
mcp_manager = get_mcp_manager()
await mcp_manager.startup()

# Usage (in providers)
result = await mcp_manager.call("piapi", "generate_video_wan", {"prompt": "..."})
result = await mcp_manager.call("pollo", "text2video_pollo-v1-6", {"prompt": "..."})

# Shutdown
await mcp_manager.shutdown()
```

## PiAPI MCP Provider

**File**: `backend/app/providers/piapi_mcp_provider.py`

**Role**: Normal primary path for standard PiAPI-backed generation tasks.

### MCP Tools Used

| Tool | VidGo Task | Description |
|------|-----------|-------------|
| `generate_image` | T2I | Flux text-to-image |
| `derive_image` | I2I, Effects | Flux img2img / variation |
| `generate_video_wan` | T2V, I2V | Wan text/image-to-video |
| `generate_video_kling` | Avatar | Kling video + lip sync |
| `generate_video_effect_kling` | V2V | Kling video effects |
| `generate_video_luma` | T2V (alt) | Luma video generation |
| `generate_video_hunyuan` | T2V (alt) | Hunyuan video generation |
| `generate_3d_model` | 3D Model | Trellis image-to-3D (GLB) |
| `image_upscale` | Upscale | Image upscale |
| `image_rmbg` | BG Removal | Background removal |
| `tts_zero_shot` | TTS | F5-TTS voice synthesis |
| `midjourney_imagine` | T2I (alt) | Midjourney generation |

### Background Removal

BG removal uses **local rembg** (Python library), not MCP. It runs directly in the backend process.

## Pollo.ai MCP Provider

**File**: `backend/app/providers/pollo_mcp_provider.py`

**Role**: Backup video generation (50+ models)

### MCP Tools Used

| Tool | VidGo Task | Description |
|------|-----------|-------------|
| `text2video_{model}` | T2V | Text prompt → video |
| `img2video_{model}` | I2V | Image URL → video |
| `getTaskStatus` | (internal) | Poll task status |

Tool names are **dynamic** — constructed per-model at startup (e.g., `text2video_pollo-v1-6`, `text2video_kling-v2`).

### Supported Models (via Pollo)

Kling (3.0, Omni, O1), Wan (2.1-2.6), Runway, Hailuo, Hunyuan, Luma, Pika, PixVerse, Seedance, Sora, Veo, Pollo native models.

## Vertex AI Provider

**File**: `backend/app/providers/vertex_ai_provider.py`

**Role**: Backup for image tasks (Gemini), 3rd backup for video (Veo), primary for moderation/embeddings/material generation.

Replaces the old `GeminiProvider` that used API key auth against `generativelanguage.googleapis.com`. Now uses GCP Vertex AI with Application Default Credentials (ADC).

### Gemini Capabilities (image backup + moderation)

| Capability | Description |
|---|---|
| Content Moderation | NSFW/violence/hate detection (text + image) |
| Image Editing | Transform images via Gemini image generation |
| Text-to-Image | Generate images from text prompts |
| Interior Design | Room redesign with image + text description |
| Background Removal | Remove background via image editing |
| Upscale | Enhance resolution via image editing |
| Material Generation | Generate showcase materials for demos |

### Veo Capabilities (3rd video backup)

| Capability | Description |
|---|---|
| Text-to-Video | Veo text prompt → video (4/6/8s, 720p/1080p/4K) |
| Image-to-Video | Veo image → video with optional prompt |

Veo uses the Vertex AI predict API with long-running operation (LRO) polling.

### Configuration

| Env Variable | Description | Default |
|---|---|---|
| `VERTEX_AI_PROJECT` | GCP project ID (required) | — |
| `VERTEX_AI_LOCATION` | GCP region | `us-central1` |
| `VEO_MODEL` | Veo model name | `veo-3.0-generate-preview` |
| `GEMINI_MODEL` | Gemini model for text tasks | `gemini-2.5-flash` |
| `GEMINI_IMAGE_MODEL` | Gemini model for image output | `gemini-2.5-flash-image` |
| `GEMINI_API_KEY` | Legacy fallback (if Vertex AI not configured) | — |

### Authentication

- **On GCP (Cloud Run / GKE)**: Automatic via service account ADC
- **Local dev**: `gcloud auth application-default login` or set `GOOGLE_APPLICATION_CREDENTIALS`

## GCS Storage Service

**File**: `backend/app/services/gcs_storage_service.py`

**Purpose**: Both PiAPI and Pollo.ai return temporary CDN URLs with **14-day expiry**. GCS Storage downloads these URLs and persists them in the project's GCS bucket.

### Flow

```
Provider returns CDN URL (14-day expiry)
  → GCSStorageService.persist_url(cdn_url)
    → httpx GET download
    → Upload to gs://vidgo-media-vidgo-ai/generated/{type}/{id}.{ext}
    → Return permanent GCS URL
```

### Configuration

| Env Variable | Description |
|---|---|
| `GCS_BUCKET` | GCS bucket name (e.g., `vidgo-media-vidgo-ai`) |

On Cloud Run, authentication uses the service account's Application Default Credentials (already has `roles/storage.objectAdmin`).

### Fallback

If GCS is not configured or upload fails, the original CDN URL is returned. It remains valid for ~14 days.

## MCP Server Installation

### Pollo MCP (npm package)

```bash
npm install -g pollo-mcp
```

### PiAPI MCP (build from source)

```bash
git clone https://github.com/apinetwork/piapi-mcp-server.git mcp-servers/piapi-mcp-server
cd mcp-servers/piapi-mcp-server
npm install
npm run build
# Built output: dist/index.js
```

### Docker Integration

In the backend Dockerfile, add Node.js and MCP servers:

```dockerfile
# Install Node.js for MCP servers
RUN apt-get update && apt-get install -y nodejs npm

# Install Pollo MCP
RUN npm install -g pollo-mcp

# Build PiAPI MCP server
COPY mcp-servers/piapi-mcp-server /app/mcp-servers/piapi-mcp-server
RUN cd /app/mcp-servers/piapi-mcp-server && npm install && npm run build
```

## Comparison: MCP vs Direct REST vs Vertex AI

| Aspect | MCP | Direct REST | Vertex AI SDK |
|--------|-----|-------------|---------------|
| **Protocol** | Stdio (subprocess) | HTTP | gRPC / HTTP |
| **Polling** | Handled by MCP server | Implemented in provider | LRO polling (Veo) |
| **Tool discovery** | Dynamic (`list_tools`) | Hardcoded endpoints | SDK methods |
| **Auth** | API key in env | API key in header | ADC (service account) |
| **Error handling** | MCP protocol errors | HTTP status codes | SDK exceptions |
| **Billing** | Per-provider API key | Per-provider API key | GCP project billing |

The MCP approach provides a unified interface across providers, automatic tool discovery, and the ability to swap providers without changing application code. Direct REST remains necessary for REST-only capabilities and exact model selection. Vertex AI consolidates GCP services under a single auth and billing model.

## File Structure

```
backend/app/
├── providers/
│   ├── base.py                 # Abstract base classes
│   ├── piapi_mcp_provider.py   # PiAPI via MCP (normal primary path)
│   ├── piapi_provider.py       # PiAPI REST (explicit model choices + 3D)
│   ├── pollo_mcp_provider.py   # Pollo.ai via MCP (normal video backup)
│   ├── pollo_provider.py       # Pollo REST (explicit Pollo model choices)
│   ├── vertex_ai_provider.py   # Vertex AI Gemini + Veo (image backup, 3rd video, moderation)
│   ├── a2e_provider.py         # A2E (avatar backup)
│   └── provider_router.py      # Routes tasks → providers
├── services/
│   ├── mcp_client.py           # MCP client manager (subprocess lifecycle)
│   ├── gemini_service.py       # Gemini AI service (prompt enhancement, moderation, embeddings)
│   └── gcs_storage_service.py  # CDN → GCS persistence
└── core/
    └── config.py               # PIAPI_KEY, POLLO_API_KEY, VERTEX_AI_PROJECT, GCS_BUCKET, etc.
```
