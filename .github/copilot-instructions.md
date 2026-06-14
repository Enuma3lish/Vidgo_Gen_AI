# VidGo Gen AI Platform - Copilot Instructions

## Architecture Overview

VidGo is an AI-powered visual content generation platform with a **dual-mode tier model**:

- **PRESET-ONLY** (free / trial users): every showcase result is pre-generated into the `materials` table before the service starts. No runtime AI API calls. Results are watermarked.
- **REAL-API** (paid subscribers): real-time calls to AI providers with custom uploads, model selection, and watermark-free downloads.

**Stack**: FastAPI + ARQ worker (backend) · Vue 3 / Vite / TypeScript (frontend) · PostgreSQL · Redis · Google Cloud Storage (media).

**External AI providers** (REST; the in-repo MCP wrappers for PiAPI and Pollo were deleted 2026-05-26):
- **PiAPI** — primary T2I (Flux), I2V, virtual try-on (Kling), avatar, interior, upscale, 3D (Trellis).
- **Pollo AI** — video backup (Pixverse, Kling), I2V / T2V fallback.
- **A2E.ai** — talking avatar lip-sync.
- **Vertex AI / Gemini** — Gemini for moderation + image-translation OCR + material generation; Veo for video backup.

### Key Components

| Layer | Location | Purpose |
|-------|----------|---------|
| API endpoints | `backend/app/api/v1/` | Versioned REST endpoints (`auth`, `demo`, `tools`, `credits`, `interior`, `subscriptions`, …) |
| Dependencies | `backend/app/api/deps.py` | `get_db`, `get_current_user`, `get_redis` |
| Services | `backend/app/services/` | Business logic, AI orchestration, demo cache, billing |
| Providers | `backend/app/providers/` | AI provider adapters routed by `provider_router.py` |
| Models | `backend/app/models/` | SQLAlchemy 2.0 async models (`material.py` is central) |
| ARQ worker | `backend/app/worker.py` | Background tasks (`arq app.worker.WorkerSettings`) |
| Alembic | `backend/alembic/versions/` | Schema migrations |
| Frontend API | `frontend-vue/src/api/` | Axios client with token refresh |
| Stores | `frontend-vue/src/stores/` | Pinia state (`auth`, `credits`, `generation`, `branding`, `ui`, `admin`) |
| Composables | `frontend-vue/src/composables/` | Reusable logic (`useCredits`, `useDemoMode`, `useExamplePrefill`, `useSeo`, `useUpload`, …) |

## Critical Patterns

### Material System (Preset-Only Mode)

The `Material` model (`backend/app/models/material.py`) backs the showcase gallery:
- `lookup_hash` — SHA256(`tool_type` + `prompt` + `effect_prompt` + `input_image_id`) for O(1) preset lookup
- `ToolType` enum currently covers **13 tools**:
  `background_removal`, `product_scene`, `try_on`, `room_redesign`, `short_video`,
  `ai_avatar`, `pattern_generate`, `effect`,
  `claymation`, `kling_video`, `upscale`, `image_translator`, `midjourney_imagine`
- Adding a new tool requires extending `ToolType`, adding the matching value to the Postgres enum via an Alembic migration, and registering a generator branch in `backend/scripts/main_pregenerate.py`.

```python
# backend/app/models/material.py
class ToolType(str, enum.Enum):
    BACKGROUND_REMOVAL = "background_removal"
    # …
    MIDJOURNEY_IMAGINE = "midjourney_imagine"
```

### Provider Pattern

All adapters extend the abstract base classes in `backend/app/providers/base.py`:
- `ImageGenerationProvider.text_to_image()`
- `VideoGenerationProvider.image_to_video()` / `text_to_video()`
- `StyleTransferProvider.style_transfer()`
- `AvatarProvider.generate_avatar()`

Concrete adapters in `backend/app/providers/`: `piapi_provider.py`, `pollo_provider.py`, `a2e_provider.py`, `vertex_ai_provider.py`. Routing, failover, and per-task provider selection live in `provider_router.py` (which `app/providers/__init__.py` re-exports as `ProviderRouter` + `TaskType`).

### Database & Migrations

- Async SQLAlchemy 2.0 with `asyncpg` (`AsyncSessionLocal` in `app/core/database.py`).
- Generate: `cd backend && alembic revision --autogenerate -m "description"`
- Apply: `cd backend && alembic upgrade head`
- When you add a new value to a Postgres `Enum` type (e.g. `ToolType`), do it in a migration with `ALTER TYPE … ADD VALUE` — autogenerate will not detect enum value changes.

### Startup Lifecycle

`backend/app/main.py` runs material validation **in the background** after the server is listening (Cloud Run health-check friendly). It also kicks off:
- `_media_cleanup_loop` — hourly cleanup of expired generations (`run_media_cleanup`).
- Model-registry Redis pub/sub subscriber — picks up admin model-ID overrides across Cloud Run instances within seconds (see `app/services/model_registry_pubsub.py`).

## Development Workflow

### Start Services

```bash
# Full stack (recommended)
docker compose up

# Backend only (assumes postgres + redis are up)
cd backend && uvicorn app.main:app --reload --port 8000

# ARQ worker (background tasks)
cd backend && arq app.worker.WorkerSettings

# Frontend only
cd frontend-vue && npm run dev
```

Backend listens on `8000` inside Docker, exposed as `8001` on the host. Frontend dev server is on `5173` by default (Vite) or `8501` when run via docker-compose.

### Environment Variables

Backend `.env` (see `backend/.env.example` for the full template). Required for real generation:
- `PIAPI_KEY` — primary image/video provider
- `POLLO_API_KEY` — video backup
- `A2E_API_KEY`, `A2E_API_ID`, `A2E_DEFAULT_CREATOR_ID` — avatar lip-sync
- `VERTEX_AI_PROJECT`, `VERTEX_AI_LOCATION`, `VEO_MODEL`, `GEMINI_MODEL` — Vertex AI (uses Application Default Credentials)
- `DATABASE_URL`, `REDIS_URL` — supplied by docker-compose

Provider model IDs (e.g. `PIAPI_KLING_TRYON_MODEL`, `POLLO_PIXVERSE_DEFAULT_MODEL`) are env-overridable via `app/core/model_registry.py` — no rebuild needed when an upstream provider bumps an alias.

### Pre-generation Pipeline

```bash
# From repo root or backend/
python -m scripts.main_pregenerate --tool ai_avatar --limit 10
python -m scripts.main_pregenerate --all --limit 20
python -m scripts.main_pregenerate --dry-run
```

`scripts/main_pregenerate.py` lives under `backend/scripts/`. The Docker entrypoint (`backend/scripts/docker_entrypoint.sh`) auto-runs pregen when the `materials` table is empty; set `SKIP_PREGENERATION=true` in Cloud Run / docker-compose to skip it on every restart.

### Testing

Backend (`backend/pytest.ini` enables `asyncio_mode = auto`):

```bash
cd backend
pytest                                    # full suite
pytest tests/test_api_full.py             # API smoke tests
pytest tests/test_provider_router.py      # provider failover routing
pytest -k "test_health"                   # filter by name
```

Tests mock the DB session via `app.dependency_overrides[get_db]` and patch `validate_materials_on_startup` — no live Postgres or Redis required.

Frontend (`frontend-vue/vitest.config.ts`, specs under `frontend-vue/tests/`):

```bash
cd frontend-vue
npm run type-check    # vue-tsc --noEmit (strict app type-check)
npm run test          # vitest run (a11y, locale coverage, SEO smoke, …)
npm run build         # vue-tsc && vite build
```

Vitest specs deliberately live outside `src/` so they never bend the production type-check. GitHub Actions (`.github/workflows/ci.yml`) runs both jobs on every push and PR.

## Conventions

### API Endpoints
- All versioned under `/api/v1/` (`settings.API_V1_STR`).
- Routers are mounted in `backend/app/api/api.py`.
- Use dependency injection from `app/api/deps.py` (`get_db`, `get_current_user`, `get_redis`).
- Successful responses follow `{"success": True, …}`; errors raise `HTTPException`.

### Frontend
- Atomic components: `src/components/{atoms,molecules,layout,common,admin,tools,social,invoice}/`.
- Reusable logic in `src/composables/` (e.g. `useCredits`, `useDemoMode`, `useExamplePrefill`, `useSeo`).
- i18n via `vue-i18n` with 5 locales in `src/locales/`: `en`, `zh-TW`, `ja`, `ko`, `es`.
- Active locale is reflected on `<html lang>` for SEO; see `src/main.ts` and `useSeo`.
- Tailwind CSS with a dark Slate palette (`frontend-vue/tailwind.config.js`).
- Pinia is installed **before** the router in `src/main.ts` so navigation guards can resolve auth state on first load.

### Models
- UUID primary keys (`uuid.uuid4` default).
- Bilingual fields pattern: `prompt` + `prompt_zh` (and `prompt_en` where present); same pattern for `topic` / `main_topic` / `title`.
- JSONB columns for flexible metadata (`input_params`, `generation_steps`).

## Common Tasks

**Add a new AI tool**
1. Add the value to `ToolType` in `backend/app/models/material.py`.
2. Write an Alembic migration that `ALTER TYPE tooltype ADD VALUE 'new_tool'` (autogenerate misses enum additions — model `p5q6r7s8t9u0_extend_tooltype_for_new_demos.py` is the canonical example).
3. Register topics in `backend/app/config/topic_registry.py`.
4. Add a generator branch in `backend/scripts/main_pregenerate.py`.
5. Add the endpoint to `backend/app/api/v1/tools.py` (or a dedicated router) and include it in `backend/app/api/api.py`.
6. Build the frontend view in `frontend-vue/src/views/tools/` and route it in `frontend-vue/src/router/index.ts`.

**Add a new API endpoint**
1. Create the router file in `backend/app/api/v1/`.
2. Register it in `backend/app/api/api.py`.
3. Add the matching client in `frontend-vue/src/api/`.

**Database schema change**
1. Modify the SQLAlchemy model in `backend/app/models/`.
2. `cd backend && alembic revision --autogenerate -m "description"`.
3. Review the generated migration (enum changes, indexes, JSONB defaults often need hand-editing).
4. `alembic upgrade head` locally, then commit the migration.

**Add a new AI provider**
1. Subclass the relevant interface in `backend/app/providers/base.py`.
2. Implement `health_check()` + `close()` + the task methods.
3. Register the adapter and its `TaskType`s in `backend/app/providers/provider_router.py`.
4. Re-export from `backend/app/providers/__init__.py` if it should be importable as `app.providers.NewProvider`.
