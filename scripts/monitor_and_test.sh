#!/bin/bash
# Monitor pre-generation, wait for Material DB ready, then run full stack test.
# Usage: ./scripts/monitor_and_test.sh
# Material DB must have presets before tests run; otherwise the script waits.

set -e
BASE_URL="${API_BASE:-http://localhost:8001}"
MAX_WAIT="${MONITOR_MAX_WAIT:-3600}"  # 60 min default
INTERVAL=10

echo "=========================================="
echo "VidGo Monitor & Full Stack Test"
echo "=========================================="
echo ""

# Step 1: Wait for backend healthy
echo "1. Waiting for backend to become healthy (pre-generation may take 30-60 min)..."
echo "   Polling every ${INTERVAL}s, max ${MAX_WAIT}s"
echo ""

ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
  HEALTH=$(curl -s --connect-timeout 5 "$BASE_URL/health" 2>/dev/null || echo '{}')
  if echo "$HEALTH" | grep -q '"status":"ok"'; then
    echo "   ✓ Backend healthy after ${ELAPSED}s"
    break
  fi
  echo "   [${ELAPSED}s] Backend not ready... (run: docker compose logs -f backend)"
  sleep $INTERVAL
  ELAPSED=$((ELAPSED + INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
  echo ""
  echo "✗ Timeout after ${MAX_WAIT}s. Backend may still be pre-generating."
  echo "  Check: docker compose logs -f backend"
  exit 1
fi
echo ""

# Step 2: Wait for Material DB ready (presets available)
echo "2. Waiting for Material DB to be ready (presets available)..."
echo "   Polling every ${INTERVAL}s"
echo ""

MAT_READY=0
MAT_ELAPSED=0
while [ $MAT_ELAPSED -lt $MAX_WAIT ]; do
  PRESETS=$(curl -s --connect-timeout 5 "$BASE_URL/api/v1/demo/presets/background_removal?limit=1" 2>/dev/null || echo '{}')
  COUNT=$(echo "$PRESETS" | grep -o '"count":[0-9]*' | cut -d: -f2)
  if [ -n "$COUNT" ] && [ "$COUNT" -gt 0 ] 2>/dev/null; then
    echo "   ✓ Material DB ready after ${MAT_ELAPSED}s (presets: $COUNT)"
    MAT_READY=1
    break
  fi
  echo "   [${MAT_ELAPSED}s] Material DB not ready (no presets yet)..."
  sleep $INTERVAL
  MAT_ELAPSED=$((MAT_ELAPSED + INTERVAL))
done

if [ "$MAT_READY" -ne 1 ]; then
  echo ""
  echo "✗ Timeout. Material DB has no presets - pre-generation may still be running."
  echo "  Check: docker compose logs -f backend"
  exit 1
fi
echo ""

# Step 3: Run full stack test
echo "3. Running full stack test..."
echo ""
bash "$(dirname "$0")/test_full_stack.sh"
