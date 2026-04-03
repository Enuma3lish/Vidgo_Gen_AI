# Example Creation and Serving Workflow Analysis

**Date**: 2026-03-29
**Scope**: Current codebase behavior after the demo-serving refactor
**Status**: Backend demo/example serving now follows the pre-generated-only model

## Executive Summary

The requested target flow was:

1. Remove automatic example generation at user request time
2. Let developers/admins generate examples manually from default prompts, inputs, and effects
3. Store those examples durably and cache them without expiry
4. When a user clicks an example, only return pre-generated content

That target is now mostly implemented in the backend:

- Demo-serving paths no longer generate content on cache miss
- Legacy public runtime demo-generation endpoints are disabled with `410`
- Demo cache writes are non-expiring in Redis
- Material DB remains the durable source of truth for approved demo examples

The intended operating rule should be stated explicitly:

- Developers must try each default example with the real API first
- Only after the result is correct should that example be stored in Redis and exposed to users
- Users should experience those default examples as cache queries only

The frontend demo action path now matches that contract as well:

- Vue demo pages still preload preset lists with `GET /api/v1/demo/presets/{tool_type}`
- When the user runs or applies a default example, the page now resolves that selection through `POST /api/v1/demo/use-preset`
- This means the system now guarantees both **no request-time demo generation** and **backend cache-backed preset lookup on demo actions**

## Verification Against the Target Flow

| Requirement | Status | Current Behavior |
|-------------|--------|------------------|
| No automatic demo generation at request time | Implemented | Demo retrieval returns cached/DB content only; no lazy generation fallback |
| Developer/admin manually generates examples | Implemented | `scripts.main_pregenerate` and `POST /api/v1/admin/generate-demo` are the intended creation paths |
| Store examples durably | Implemented | Approved examples are stored in `Material` rows |
| Keep demo cache non-expiring | Implemented | Redis demo cache is now warmed without TTL |
| User click only retrieves existing example | Implemented on backend | `/demo/use-preset` and demo helpers return stored content only |
| Every click queries backend cache | Implemented | Demo actions now resolve selected preset IDs through `/demo/use-preset` |

## End-to-End Architecture Diagram

```mermaid
flowchart LR
    subgraph Legacy[Legacy flow now disabled]
        L1[Demo user action] --> L2[Legacy demo generate endpoint or cache miss fallback]
        L2 --> L3[External AI provider call]
        L3 --> L4[Temporary Redis cache with TTL]
        L4 --> L5[Return generated demo]
    end

    subgraph Target[Current backend contract]
        A1[Developer or admin] --> A2[scripts.main_pregenerate or POST /api/v1/admin/generate-demo]
        A2 --> A3[PiAPI / Pollo / A2E by tool]
        A3 --> A4[Material DB approved demo rows]
        A4 --> A5[Redis demo read cache no TTL]

        U1[Demo user opens tool page] --> A6[GET /api/v1/demo/presets/{tool_type}]
        A6 --> A4

        U2[Demo user clicks example] --> A7[POST /api/v1/demo/use-preset]
        A7 --> A5
        A5 --> A4
        A5 --> A8[Return existing watermarked result]
    end

    subgraph Subscriber[Subscriber runtime generation remains]
        S1[Subscriber submits tool request] --> S2[POST /api/v1/tools/* or related endpoint]
        S2 --> S3[External AI provider runtime generation]
        S3 --> S4[Persist user generation and deduct credits]
        S4 --> S5[Return full-quality result]
    end
```

## Current Example Creation Paths

### Required Rule For Default Examples

- A default example is not considered ready until a developer/admin has run the real provider call and confirmed the output is correct.
- After validation, that finished output must be stored in Material DB and Redis before users see it.
- The user-facing demo path is retrieval only: query cache, return existing example, never generate.

### 1. Mapping-Based Pregeneration Script

Primary operator path:

```bash
cd backend
python -m scripts.main_pregenerate --tool <tool_name> --limit <n>
python -m scripts.main_pregenerate --all --limit <n>
```

Characteristics:

- Uses explicit mappings for prompts, scenes, styles, avatars, scripts, or source assets depending on tool
- Initializes PiAPI, Pollo, and A2E clients as needed
- Generates assets first, then stores results in `Material`
- Designed for curated example coverage rather than user-triggered generation

Supported tool types in the current material system:

- `background_removal`
- `product_scene`
- `try_on`
- `room_redesign`
- `short_video`
- `ai_avatar`
- `pattern_generate`
- `effect`

### 2. Admin Single-Example Generation

Admin-only path:

```text
POST /api/v1/admin/generate-demo
```

Characteristics:

- Generates or accepts an input image
- Runs a tool-specific transformation
- Stores both input and result in Material DB
- Warms Redis through `DemoCacheService.store_demo`

This is the right path for curated one-off example creation from the dashboard or internal tooling.

## Tool-by-Tool Workflow

| Tool | Developer/Admin Example Creation | Demo Serving Path | Subscriber Runtime Path | Notes |
|------|----------------------------------|-------------------|-------------------------|-------|
| `background_removal` | Generate or supply input image, then remove background | Preset list from Material DB, result served from DB/Redis | `POST /api/v1/tools/remove-bg` | Demo result is pre-generated only |
| `product_scene` | Pregeneration script uses mapped product/scene pairs; admin path currently uses a simplified transform flow | Pre-generated scene examples only | `POST /api/v1/tools/product-scene` | Admin route is less sophisticated than the full mapping script |
| `try_on` | Pregeneration uses mapped model and garment combinations | Pre-generated try-on examples only | `POST /api/v1/tools/try-on` | No demo-time generation |
| `room_redesign` | Generate or supply room input, then apply mapped style prompt | Pre-generated redesign examples only | `POST /api/v1/tools/room-redesign` | Demo and subscriber flows are intentionally separated |
| `short_video` | Generate or supply image, then transform to video | Pre-generated demo video only | `POST /api/v1/tools/short-video` | Demo videos are stored and replayed, not generated on click |
| `ai_avatar` | Pregeneration script combines avatar, script, and language; admin route supports single example generation | Pre-generated avatar clips only | `POST /api/v1/tools/avatar` | A2E is part of the curated generation path |
| `pattern_generate` | Single-step mapped prompt generation | Pre-generated patterns only | Tool-specific runtime path depends on subscriber flow | No separate input asset required |
| `effect` | Apply mapped style/effect to curated source material | Pre-generated style examples only | `POST /api/v1/effects/apply-style` and related endpoints | Demo style gallery is read-only |

## What Changed in the Backend Refactor

### Demo Retrieval

- `DemoCacheService.get_or_generate(...)` now performs retrieval only
- On cache miss it checks Material DB and returns `None` instead of generating new content
- Demo cache warm-up writes are now persistent in Redis rather than TTL-based

### Disabled Legacy Runtime Endpoints

The following legacy public endpoints now return `410` instead of generating examples:

- `POST /api/v1/demo/generate`
- `POST /api/v1/demo/generate/paid`
- `POST /api/v1/demo/search`
- `POST /api/v1/demo/generate-image`
- `POST /api/v1/demo/generate-realtime`

### Startup Behavior

- The app no longer runs the old expiring-demo persistence loop in the FastAPI lifespan manager
- Normal runtime does not pregenerate examples automatically
- Pregeneration is now an explicit developer/operator action

## Serving Semantics After the Refactor

### Demo Users

- Receive pre-generated demo content only
- See watermarked results unless they are entitled to the full asset
- Never trigger external provider calls through the current backend demo-serving path

### Subscribers

- Still use real runtime generation through `/api/v1/tools/*`, `/api/v1/effects/*`, and related endpoints
- Continue to consume credits and receive full-quality assets

## Recommended Operating Model

1. Curate prompt, style, topic, and input mappings in the pregeneration pipeline.
2. Generate examples manually through `scripts.main_pregenerate` or `POST /api/v1/admin/generate-demo`.
3. Approve and feature those materials in the database.
4. Serve demo users from Material DB and Redis only.
5. Keep subscriber generation separate and real-time.

This is the clean separation the platform now follows on the backend.
