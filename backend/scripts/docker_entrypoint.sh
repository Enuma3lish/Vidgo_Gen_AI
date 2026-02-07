#!/bin/bash
set -e

echo "========================================"
echo "VidGo Backend Docker Entrypoint"
echo "========================================"
echo "Time: $(date)"
echo ""

SKIP_MATERIAL_CHECK=${SKIP_MATERIAL_CHECK:-false}
MATERIAL_CHECK_TIMEOUT=${MATERIAL_CHECK_TIMEOUT:-10800}
MATERIAL_CHECK_INTERVAL=${MATERIAL_CHECK_INTERVAL:-30}
# Set CLEAN_MATERIALS to a tool name (e.g., "ai_avatar") to delete and re-seed that tool
# Set CLEAN_MATERIALS=all to clean ALL tools before re-seeding
CLEAN_MATERIALS=${CLEAN_MATERIALS:-}

# ============================================
# STEP 1: Wait for Dependencies
# ============================================
echo "Step 1: Waiting for PostgreSQL..."
while ! pg_isready -h ${DB_HOST:-postgres} -p ${DB_PORT:-5432} -U ${DB_USER:-postgres} 2>/dev/null; do
    echo "  PostgreSQL is unavailable - sleeping"
    sleep 2
done
echo "  PostgreSQL is ready!"
echo ""

echo "Step 2: Waiting for Redis..."
while ! redis-cli -h ${REDIS_HOST:-redis} ping 2>/dev/null; do
    echo "  Redis is unavailable - sleeping"
    sleep 2
done
echo "  Redis is ready!"
echo ""

# ============================================
# STEP 2: Database Migrations
# ============================================
echo "Step 3: Running database migrations..."
alembic upgrade head
echo "  Database migrations complete!"
echo ""

# ============================================
# STEP 3: Seed Service Pricing
# ============================================
echo "Step 4: Seeding service pricing..."
python -m scripts.seed_service_pricing 2>/dev/null || echo "  (Pricing already seeded or skipped)"
echo ""

# ============================================
# STEP 4: Clean Materials (if CLEAN_MATERIALS is set)
# ============================================
if [ -n "$CLEAN_MATERIALS" ]; then
    echo "Step 4b: Cleaning materials (CLEAN_MATERIALS=$CLEAN_MATERIALS)..."
    if [ "$CLEAN_MATERIALS" = "all" ]; then
        echo "  Cleaning ALL materials and re-seeding..."
        python -m scripts.seed_materials_if_empty --clean 2>&1 || echo "  (Clean+seed failed, will retry)"
    else
        # Support comma-separated tool names: CLEAN_MATERIALS=ai_avatar,effect,short_video
        IFS=',' read -ra TOOLS <<< "$CLEAN_MATERIALS"
        for tool in "${TOOLS[@]}"; do
            tool=$(echo "$tool" | xargs)  # trim whitespace
            echo "  Cleaning tool '$tool' and re-seeding..."
            python -m scripts.seed_materials_if_empty --clean --tool "$tool" 2>&1 || echo "  (Clean+seed for $tool failed, will retry)"
        done
    fi
    echo ""
fi

# ============================================
# STEP 5: Material DB Check (wait until ready, run pregen if empty)
# ============================================
echo "Step 5: Checking Material DB status..."
if [ "$SKIP_MATERIAL_CHECK" = "true" ]; then
    echo "  SKIP_MATERIAL_CHECK=true - skipping material check"
else
    START=$(date +%s)
    GENERATED=false
    PREGEN_TIMEOUT=7200

    while true; do
        # Check all 8 tools
        echo "  --- Material DB Status ---"
        if python -m scripts.check_material_status 2>/dev/null; then
            echo "  Material DB ready - all tools have enough examples!"
            break
        fi

        ELAPSED=$(($(date +%s) - START))
        if [ $ELAPSED -ge $MATERIAL_CHECK_TIMEOUT ]; then
            echo "  Timeout: Material DB not ready after ${MATERIAL_CHECK_TIMEOUT}s"
            if [ "${ALLOW_EMPTY_MATERIALS:-false}" = "true" ]; then
                echo "  ALLOW_EMPTY_MATERIALS=true - continuing anyway (demo may be incomplete)"
                break
            fi
            echo "  Set ALLOW_EMPTY_MATERIALS=true to start anyway (dev only)"
            exit 1
        fi

        # First attempt: seed missing tools only (not --all to save API credits)
        if [ "$GENERATED" = "false" ]; then
            echo ""
            echo "  Material DB not ready - seeding missing tools..."
            echo "  This may take 30-90 minutes on first run."
            echo ""
            set +e
            python -m scripts.seed_materials_if_empty --force 2>&1 || true
            set -e
            GENERATED=true
            echo ""
            echo "  Seeding done. Checking status again..."
            continue
        fi

        echo "  Waiting ${MATERIAL_CHECK_INTERVAL}s (timeout in $((MATERIAL_CHECK_TIMEOUT - ELAPSED))s)..."
        sleep $MATERIAL_CHECK_INTERVAL
    done
fi
echo ""

# ============================================
# STEP 6: Final Status Report
# ============================================
echo "========================================"
echo "Material DB Final Status:"
echo "========================================"
python -m scripts.check_material_status 2>/dev/null || true
echo ""

# ============================================
# STEP 7: Start the Service
# ============================================
echo "========================================"
echo "Starting VidGo Backend Server"
echo "========================================"
echo ""
echo "  API Endpoints:"
echo "    - Health: http://localhost:8000/health"
echo "    - Docs:   http://localhost:8000/docs"
echo "    - API:    http://localhost:8000/api/v1/"
echo ""
echo "  Mode: PRESET-ONLY"
echo "========================================"

exec "$@"
