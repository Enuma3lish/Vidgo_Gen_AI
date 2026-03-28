#!/bin/bash
# VidGo Backend Entrypoint
# Start uvicorn IMMEDIATELY. Migrations run in background.
# Demo examples are generated via admin API, not at startup.

echo "VidGo Backend starting at $(date)"

# Background: run migrations after server is listening
(
    sleep 3
    echo "[init] Running alembic migrations..."
    timeout 60 alembic upgrade head 2>&1 || echo "[init] WARNING: migrations failed or timed out"
    timeout 30 python -m scripts.seed_new_pricing_tiers 2>/dev/null || true
    echo "[init] Background init complete."
) &

# Start server immediately
exec "$@"
