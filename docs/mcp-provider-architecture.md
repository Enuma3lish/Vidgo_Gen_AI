# VidGo AI — MCP Provider Architecture

## Overview

VidGo uses **Model Context Protocol (MCP)** to communicate with AI generation providers. Both Pollo.ai and PiAPI run as MCP servers (Node.js subprocesses), managed by the backend's MCP Client Manager.

```
FastAPI Backend (Python)
│
├── MCPClientManager (singleton)
│   ├── pollo-mcp (npm)  ← stdio transport → Pollo.ai API
│   └── piapi-mcp-server ← stdio transport → PiAPI API
│
├── ProviderRouter
│   ├── PolloMCPProvider  (primary: video)
│   ├── PiAPIMCPProvider  (supplement + backup)
│   ├── GeminiProvider    (image backup + moderation)
│   ├── A2EProvider       (avatar backup)
│   ├── PiAPIProvider     (REST fallback)
│   └── PolloProvider     (REST fallback)
│
└── GCSStorageService
    └── Downloads CDN URLs → uploads to GCS bucket
```

## Provider Routing

### Task → Provider Mapping

| Task | Primary | Backup | REST Fallback |
|------|---------|--------|---------------|
| **Text-to-Video** | Pollo MCP | PiAPI MCP | Pollo REST |
| **Image-to-Video** | Pollo MCP | PiAPI MCP | Pollo REST |
| **Video Style Transfer** | Pollo MCP | PiAPI MCP | Pollo REST |
| **Text-to-Image** | PiAPI MCP | Gemini | PiAPI REST |
| **Image-to-Image** | PiAPI MCP | Gemini | PiAPI REST |
| **Image Effects** | PiAPI MCP | Gemini | PiAPI REST |
| **Upscale** | PiAPI MCP | Gemini | PiAPI REST |
| **Background Removal** | PiAPI MCP (local rembg) | Gemini | PiAPI REST |
| **Interior Design** | PiAPI MCP | Gemini | PiAPI REST |
| **3D Model** | PiAPI MCP | — | PiAPI REST |
| **Avatar** | PiAPI MCP | A2E | PiAPI REST |
| **Moderation** | Gemini | — | — |
| **Material Generation** | Gemini | — | — |

### Routing Flow

```
Request → ProviderRouter.route(task_type, params)
  │
  ├─ 1. Try PRIMARY (MCP provider)
  │     └─ Success → persist to GCS → return result
  │
  ├─ 2. Try BACKUP (MCP or REST provider)
  │     └─ Success → persist to GCS → return result
  │
  └─ 3. Try FALLBACK (legacy REST provider)
        └─ Success → persist to GCS → return result
        └─ All failed → user-friendly error
```

## MCP Client Manager

**File**: `backend/app/services/mcp_client.py`

Manages MCP server subprocess lifecycle:

- **Startup**: Starts both MCP servers as Node.js subprocesses via stdio transport
- **Connection**: Initializes MCP sessions, caches available tools
- **Auto-reconnect**: Retries on connection failure (3 attempts with backoff)
- **Shutdown**: Gracefully terminates subprocesses on app shutdown

### Configuration

| Env Variable | Description |
|---|---|
| `POLLO_API_KEY` | Pollo.ai API key (enables pollo-mcp server) |
| `PIAPI_KEY` | PiAPI API key (enables piapi-mcp-server) |
| `PIAPI_MCP_PATH` | Path to built piapi-mcp-server `dist/index.js` |

### Lifecycle

```python
# Startup (in main.py lifespan)
mcp_manager = get_mcp_manager()
await mcp_manager.startup()

# Usage (in providers)
result = await mcp_manager.call("pollo", "text2video", {"prompt": "..."})

# Shutdown
await mcp_manager.shutdown()
```

## Pollo.ai MCP Provider

**File**: `backend/app/providers/pollo_mcp_provider.py`

**Role**: Primary video generation (50+ models)

### MCP Tools Used

| Tool | VidGo Task | Description |
|------|-----------|-------------|
| `text2video` | T2V | Text prompt → video |
| `img2video` | I2V | Image URL → video |
| `getTaskStatus` | (internal) | Poll task status |

### Supported Models (via Pollo)

Kling (3.0, Omni, O1), Wan (2.1-2.6), Runway, Hailuo, Hunyuan, Luma, Pika, PixVerse, Seedance, Sora, Veo, Pollo native models.

## PiAPI MCP Provider

**File**: `backend/app/providers/piapi_mcp_provider.py`

**Role**: Supplement (tasks Pollo doesn't support) + video backup

### MCP Tools Used

| Tool | VidGo Task | Description |
|------|-----------|-------------|
| `flux_text_to_image` | T2I | Flux text-to-image |
| `flux_image_to_image` | I2I, Effects, Upscale | Flux img2img |
| `wan_image_to_video` | I2V (backup) | Wan I2V |
| `wan_text_to_video` | T2V (backup) | Wan T2V |
| `kling_virtual_try_on` | Try-On | Kling virtual try-on |
| `kling_video_generation` | Avatar | Kling avatar + lip sync |
| `kling_video_effects` | V2V (backup) | Video effects |
| `trellis_image_to_3d` | 3D Model | Image → GLB |
| `tts_zero_shot` | TTS | F5-TTS voice synthesis |

### Background Removal

BG removal uses **local rembg** (Python library), not MCP. It runs directly in the backend process.

## GCS Storage Service

**File**: `backend/app/services/gcs_storage_service.py`

**Purpose**: Both Pollo.ai and PiAPI return temporary CDN URLs with **14-day expiry**. GCS Storage downloads these URLs and persists them in the project's GCS bucket.

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

## Comparison: MCP vs Direct REST

| Aspect | MCP | Direct REST |
|--------|-----|-------------|
| **Protocol** | Stdio (subprocess) | HTTP |
| **Polling** | Handled by MCP server | Implemented in provider |
| **Tool discovery** | Dynamic (`list_tools`) | Hardcoded endpoints |
| **Error handling** | MCP protocol errors | HTTP status codes |
| **Latency** | ~same (subprocess overhead negligible) | Direct |
| **Reliability** | Auto-reconnect; REST fallback | Single point |

The MCP approach provides a unified interface across providers, automatic tool discovery, and the ability to swap providers without changing application code.

## File Structure

```
backend/app/
├── providers/
│   ├── base.py                 # Abstract base classes
│   ├── pollo_mcp_provider.py   # Pollo.ai via MCP (primary video)
│   ├── piapi_mcp_provider.py   # PiAPI via MCP (supplement + backup)
│   ├── piapi_provider.py       # PiAPI REST (legacy fallback)
│   ├── pollo_provider.py       # Pollo REST (legacy fallback)
│   ├── gemini_provider.py      # Gemini (image backup + moderation)
│   ├── a2e_provider.py         # A2E (avatar backup)
│   └── provider_router.py      # Routes tasks → providers
├── services/
│   ├── mcp_client.py           # MCP client manager (subprocess lifecycle)
│   └── gcs_storage_service.py  # CDN → GCS persistence
└── core/
    └── config.py               # POLLO_API_KEY, PIAPI_KEY, GCS_BUCKET, etc.
```
