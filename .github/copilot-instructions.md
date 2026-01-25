# VidGo Gen AI Platform - Copilot Instructions

## Architecture Overview

VidGo is an AI-powered visual content generation platform operating in **PRESET-ONLY mode**—all demo content is pre-generated before service starts. No runtime AI API calls for demo users; paid users get real-time generation.

**Stack**: FastAPI (backend) + Vue 3/Vite/TypeScript (frontend) + PostgreSQL + Redis  
**External AI Providers**: PiAPI (T2I/I2V), Pollo AI (Video), A2E.ai (Avatar), Gemini (moderation)

### Key Components

| Layer | Location | Purpose |
|-------|----------|---------|
| API Endpoints | `backend/app/api/v1/` | REST endpoints (auth, demo, tools, credits) |
| Services | `backend/app/services/` | Business logic, AI integration |
| Providers | `backend/app/providers/` | AI provider abstractions (base.py interface) |
| Models | `backend/app/models/` | SQLAlchemy models (material.py is central) |
| Frontend API | `frontend-vue/src/api/` | Axios client with token refresh |
| Stores | `frontend-vue/src/stores/` | Pinia state management |

## Critical Patterns

### Material System (Preset-Only Mode)

The `Material` model ([backend/app/models/material.py](backend/app/models/material.py)) is central:
- `lookup_hash`: SHA256 hash enabling O(1) preset lookup
- `ToolType` enum: `background_removal`, `product_scene`, `try_on`, `room_redesign`, `short_video`, `ai_avatar`, `pattern_generate`
- Pre-generated materials are created via `scripts/main_pregenerate.py` before service starts

```python
# Example: Adding new tool type requires updating ToolType enum
class ToolType(str, enum.Enum):
    BACKGROUND_REMOVAL = "background_removal"
    # ... add new tools here
```

### Provider Pattern

All AI providers extend base classes in `backend/app/providers/base.py`:
- `ImageGenerationProvider.text_to_image()`
- `VideoGenerationProvider.image_to_video()` / `text_to_video()`
- `AvatarProvider.generate_avatar()`

New providers must implement these interfaces and be registered in `provider_router.py`.

### Database & Migrations

- Async SQLAlchemy with asyncpg
- Alembic migrations in `backend/alembic/versions/`
- Generate migration: `alembic revision --autogenerate -m "description"`
- Apply: `alembic upgrade head`

## Development Workflow

### Start Services

```bash
# Full stack (recommended)
docker-compose up

# Backend only (after docker-compose up postgres redis)
cd backend && uvicorn app.main:app --reload --port 8001

# Frontend only
cd frontend-vue && npm run dev
```

### Environment Variables

Backend requires `.env` in `backend/` with:
- `PIAPI_KEY` - Primary image/video generation
- `POLLO_API_KEY` - Video effects
- `A2E_API_KEY`, `A2E_API_ID` - Avatar generation
- `DATABASE_URL`, `REDIS_URL` - Set automatically by docker-compose

### Pre-generation Pipeline

```bash
# Generate materials for specific tool
python -m scripts.main_pregenerate --tool ai_avatar --limit 10

# Generate all tools
python -m scripts.main_pregenerate --all --limit 20

# Dry run (no API calls)
python -m scripts.main_pregenerate --dry-run
```

Set `SKIP_PREGENERATION=true` in docker-compose to skip on restart.

### Testing

```bash
cd backend
pytest                           # Run all tests
pytest tests/test_api_full.py    # API tests
pytest -k "test_health"          # Specific test
```

Tests use `pytest-asyncio` with mocked DB sessions. Pattern: override `get_db` dependency and mock `validate_materials_on_startup`.

## Conventions

### API Endpoints
- Versioned under `/api/v1/`
- Use `deps.py` for dependency injection (`get_db`, `get_current_user`, `get_redis`)
- Return `{"success": bool, ...}` response pattern

### Frontend
- Components: Atomic design (`atoms/`, `molecules/`, `layout/`, `tools/`)
- Composables in `src/composables/` for reusable logic (e.g., `useCredits`, `useDemoMode`)
- i18n via vue-i18n with locales in `src/locales/`
- Tailwind CSS with dark theme (Slate color palette)

### Models
- UUID primary keys with `uuid.uuid4` default
- Bilingual fields pattern: `prompt` + `prompt_zh` + `prompt_en`
- JSONB for flexible metadata (`input_params`, `generation_steps`)

## Common Tasks

**Add new AI tool:**
1. Add to `ToolType` enum in `material.py`
2. Create endpoint in `backend/app/api/v1/tools.py`
3. Add generator function in `scripts/main_pregenerate.py`
4. Create frontend view in `frontend-vue/src/views/`

**Add new API endpoint:**
1. Create file in `backend/app/api/v1/`
2. Register router in `backend/app/api/api.py`
3. Add corresponding client in `frontend-vue/src/api/`

**Database schema change:**
1. Modify model in `backend/app/models/`
2. Run `alembic revision --autogenerate -m "description"`
3. Review and apply: `alembic upgrade head`
