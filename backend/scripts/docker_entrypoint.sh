#!/bin/bash
set -e

echo "========================================"
echo "VidGo Backend Docker Entrypoint"
echo "========================================"
echo "Time: $(date)"
echo ""

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
# STEP 4: Seed Demo Data
# ============================================
echo "Step 5: Seeding static demo data into database..."
python -m scripts.seed_demo_data 2>&1 || echo "  (Demo data seed failed or skipped)"
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
# STEP 5: Load seed fixtures (instant) + start background generation
# ============================================
echo "Step 5: Loading seed fixtures (instant SMB examples)..."
set +e
python -m scripts.seed_fixtures 2>&1 || echo "  (Seed fixtures skipped or failed - will generate from scratch)"
set -e
echo ""

echo "Step 5b: Checking Material DB status..."
if python -m scripts.check_material_status 2>/dev/null; then
    echo "  Material DB ready - all tools have enough examples!"
else
    echo "  Material DB incomplete - starting background generation..."
    echo "  Server will start immediately. Examples will appear progressively."
    nohup python -m scripts.seed_materials_if_empty --force --background > /tmp/pregen.log 2>&1 &
    PREGEN_PID=$!
    echo "  Background pre-generation started (PID: $PREGEN_PID)"
fi
echo ""

# ============================================
# STEP 6: Status Report (non-blocking)
# ============================================
echo "========================================"
echo "Material DB Status (server starting regardless):"
echo "========================================"
python -m scripts.check_material_status 2>/dev/null || echo "  (Partial - background generation in progress)"
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
