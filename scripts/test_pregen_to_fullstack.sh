#!/bin/bash
# Full test: Pre-generation → Material DB → Start Full Stack Services
# Backend entrypoint checks Material DB, runs pregen if empty, then starts.
# Usage:
#   ./scripts/test_pregen_to_fullstack.sh           # Test with existing data (fast)
#   ./scripts/test_pregen_to_fullstack.sh --fresh   # Reset materials, test first-time flow (30-90 min)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

FRESH=false
[ "$1" = "--fresh" ] && FRESH=true

echo "=========================================="
echo "VidGo Full Test: Pregen → Material DB → Full Stack"
echo "=========================================="
echo ""

# Step 1: Tear down
echo "Step 1: Tear down existing containers..."
docker compose down --remove-orphans 2>/dev/null || true
echo ""

# Step 2: Optionally reset materials volume for fresh test
if [ "$FRESH" = true ]; then
  echo "Step 2: Resetting materials (--fresh)..."
  docker volume rm vidgo_gen_ai_vidgo_generated vidgo_gen_ai_vidgo_materials 2>/dev/null || true
  echo "   Materials volume reset. First-time pregen will run (~30-90 min)."
else
  echo "Step 2: Keeping existing materials (quick test)"
fi
echo ""

# Step 3: Start postgres, redis
echo "Step 3: Starting postgres, redis..."
docker compose up -d postgres redis
echo "   Waiting for postgres, redis healthy..."
sleep 5
for i in $(seq 1 30); do
  if docker compose ps postgres redis 2>/dev/null | grep -q "healthy"; then
    sleep 2
    break
  fi
  sleep 2
done
echo ""

# Step 4: Start full stack (backend runs material check + pregen in entrypoint)
echo "Step 4: Starting backend, frontend, worker..."
docker compose up -d backend frontend worker
echo "   Backend entrypoint will check Material DB, run pregen if empty."
echo "   Checking backend logs..."
sleep 5
docker compose logs backend --tail 30
echo ""

# Step 5: Wait for backend health
echo "Step 5: Waiting for backend health..."
BASE_URL="${API_BASE:-http://localhost:8001}"
MAX_WAIT=${TEST_MAX_WAIT:-7200}
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
  if curl -s --connect-timeout 5 "$BASE_URL/health" 2>/dev/null | grep -q '"status":"ok"'; then
    echo "   ✓ Backend healthy"
    break
  fi
  if [ $WAITED -gt 0 ] && [ $((WAITED % 60)) -eq 0 ]; then
    echo "   Still waiting... (${WAITED}s / ${MAX_WAIT}s)"
    docker compose logs backend --tail 5 2>/dev/null || true
  fi
  sleep 10
  WAITED=$((WAITED + 10))
done
if [ $WAITED -ge $MAX_WAIT ]; then
  echo "   ✗ Backend not ready after ${MAX_WAIT}s"
  docker compose logs backend --tail 50
  exit 1
fi
echo ""

# Step 6: Run full stack test
echo "Step 6: Running full stack API tests..."
if [ -f "$SCRIPT_DIR/test_full_stack.sh" ]; then
  bash "$SCRIPT_DIR/test_full_stack.sh"
fi
if [ -f "$SCRIPT_DIR/test_all_apis.sh" ]; then
  echo ""
  bash "$SCRIPT_DIR/test_all_apis.sh" || true
fi
if [ ! -f "$SCRIPT_DIR/test_full_stack.sh" ] && [ ! -f "$SCRIPT_DIR/test_all_apis.sh" ]; then
  echo "   Running basic checks..."
  curl -s "$BASE_URL/health" | head -1
  curl -s "$BASE_URL/api/v1/demo/presets/background_removal?limit=1" | grep -o '"success":[^,]*' || true
fi
echo ""

echo "=========================================="
echo "Full test complete"
echo "=========================================="
