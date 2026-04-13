#!/bin/bash
# VidGo Backend Entrypoint — sequential startup gate.
#
# Contract:
#   1. Run migrations (blocking).
#   2. Seed pricing tiers (blocking, idempotent).
#   3. Ensure example INPUT images are in GCS (blocking, idempotent — skips
#      items already uploaded).
#   4. Backfill any Material DB rows with broken URLs to GCS (blocking,
#      idempotent — no-op when DB is clean).
#   5. VERIFY: refuse to start uvicorn if the Material DB still contains
#      /static/... or provider temp URLs. Fail loudly rather than serve
#      broken presets.
#   6. Only after all checks pass, exec uvicorn.
#
# Escape hatches (set in backend/.env or Cloud Run env):
#   STRICT_MATERIAL_CHECK=false  → log warnings but start anyway (dev only)
#   SKIP_STARTUP_GATE=true       → skip phases 3-5 entirely (emergency restart)
#
# Heavy first-boot seeding (main_pregenerate.py — 30-90 min of real provider
# API calls) must NOT run here. Run it as a separate Cloud Run Job once, then
# let this entrypoint handle idempotent upkeep on every subsequent boot. See
# backend/scripts/backfill_material_urls.py for the Job command reference.

set -euo pipefail

log()  { echo "[entrypoint] $(date -u +%H:%M:%SZ) $*"; }
fail() { echo "[entrypoint] FATAL: $*" >&2; exit 1; }

log "VidGo Backend starting"

# ── Phase 1: Migrations ──────────────────────────────────────────────────────
log "Running alembic migrations..."
if ! timeout 120 alembic upgrade head; then
    fail "Alembic migrations failed"
fi

# ── Phase 2: Pricing tiers (idempotent) ──────────────────────────────────────
log "Seeding pricing tiers..."
timeout 30 python -m scripts.seed_new_pricing_tiers || log "WARN: pricing tier seed had errors (non-fatal)"

# ── Optional bypass for dev / emergency restart ──────────────────────────────
if [ "${SKIP_STARTUP_GATE:-false}" = "true" ]; then
    log "SKIP_STARTUP_GATE=true — skipping GCS checks and verify gate"
    log "Starting uvicorn without material verification"
    exec "$@"
fi

# ── Phase 3: Example input images (blocking, idempotent) ─────────────────────
if [ -z "${GCS_BUCKET:-}" ]; then
    log "WARN: GCS_BUCKET not set — skipping input image generation and verify gate"
    log "Starting uvicorn in DEGRADED mode (Material rows may be broken)"
    exec "$@"
fi

if [ -n "${VERTEX_AI_PROJECT:-}" ] || [ -n "${GEMINI_API_KEY:-}" ]; then
    log "Ensuring example input images are in GCS (idempotent)..."
    if ! timeout 900 python -m scripts.generate_example_inputs; then
        fail "Example input image generation failed — refusing to start on broken data"
    fi
    log "Example input images OK"
else
    log "WARN: VERTEX_AI_PROJECT and GEMINI_API_KEY both unset — cannot generate example inputs"
fi

# ── Phase 4: Backfill broken Material DB URLs (idempotent) ───────────────────
# No-op when the DB is already clean. Does NOT call provider APIs —
# only moves existing content from temp CDNs / local paths to GCS, and
# flips unrescuable rows to PENDING.
log "Backfilling Material DB URLs to GCS..."
if ! timeout 600 python -m scripts.backfill_material_urls; then
    log "WARN: backfill exited non-zero — continuing to verify gate to see severity"
fi

# ── Phase 5: VERIFY gate ─────────────────────────────────────────────────────
# Hard stop: if Material DB still has any broken URL in an APPROVED row,
# the service must not start. The verify mode is read-only.
log "Verifying Material DB is fully persisted to GCS..."
if ! python -m scripts.backfill_material_urls --verify; then
    if [ "${STRICT_MATERIAL_CHECK:-true}" = "true" ]; then
        fail "Material DB has unpersisted URLs — refusing to start uvicorn. Set STRICT_MATERIAL_CHECK=false to override (dev only)."
    else
        log "WARN: verify failed but STRICT_MATERIAL_CHECK=false — starting anyway"
    fi
fi

log "All startup gates passed. Starting uvicorn..."
exec "$@"
