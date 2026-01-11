#!/bin/bash
set -e

echo "========================================"
echo "VidGo Backend Docker Entrypoint"
echo "PRESET-ONLY Mode Initialization"
echo "========================================"
echo "Time: $(date)"
echo ""

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
# STEP 3: Seed Service Pricing (Required)
# ============================================
echo "Step 4: Seeding service pricing..."
python -m scripts.seed_service_pricing 2>/dev/null || echo "  (Pricing already seeded or skipped)"
echo ""

# ============================================
# STEP 4: Pre-generation Pipeline
# ============================================
echo "Step 5: Running pre-generation pipeline..."
echo "        (This generates demo materials using AI APIs)"
echo "        Services: PiAPI (T2I), Pollo (Video), A2E (Avatar), rembg (BG removal - FREE)"
echo ""

# Check if pre-generation should run
SKIP_PREGENERATION=${SKIP_PREGENERATION:-false}
PREGENERATION_LIMIT=${PREGENERATION_LIMIT:-10}

if [ "$SKIP_PREGENERATION" = "true" ]; then
    echo "  Skipping pre-generation (SKIP_PREGENERATION=true)"
else
    # Run the new unified pre-generation script
    # --limit controls how many materials to generate per tool
    python -m scripts.pregenerate \
        --limit ${PREGENERATION_LIMIT} \
        2>&1 || {
            echo ""
            echo "  Pre-generation encountered errors"
            echo "  This is not fatal - checking minimum requirements..."
        }
fi
echo ""

# ============================================
# STEP 6: Startup Validation
# ============================================
echo "Step 7: Running startup validation..."
echo "        (Service will NOT start if demo materials are not ready)"
echo ""

# Run startup check with wait and generate options
# --wait: Wait for materials to be ready (up to timeout)
# --generate: Generate missing materials if found
# --timeout: Maximum wait time (5 minutes)
# --min-templates: Minimum cached templates per group
STARTUP_TIMEOUT=${STARTUP_TIMEOUT:-300}
MIN_TEMPLATES=${MIN_TEMPLATES:-1}

if python -m scripts.startup_check \
    --wait \
    --generate \
    --timeout ${STARTUP_TIMEOUT} \
    --min-templates ${MIN_TEMPLATES}; then
    echo ""
    echo "  Startup validation passed!"
    echo ""
else
    echo ""
    echo "  STARTUP VALIDATION FAILED!"
    echo "  Demo materials are not ready."
    echo ""
    echo "  Possible fixes:"
    echo "  1. Check API keys in .env file:"
    echo "     - PIAPI_KEY (for T2I)"
    echo "     - POLLO_API_KEY (for video)"
    echo "     - A2E_API_KEY (for avatar)"
    echo "  2. Run pre-generation manually:"
    echo "     python -m scripts.pregenerate --all"
    echo "  3. Set SKIP_PREGENERATION=true to skip (dev mode only)"
    echo ""

    # In development, we might want to continue anyway
    if [ "${ALLOW_EMPTY_MATERIALS:-false}" = "true" ]; then
        echo "  ALLOW_EMPTY_MATERIALS=true - continuing anyway..."
    else
        exit 1
    fi
fi

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
echo "    - All users see pre-generated materials"
echo "    - No runtime API calls for demo users"
echo "    - All downloads are watermarked"
echo ""
echo "========================================"

# Execute the main command (uvicorn)
exec "$@"
