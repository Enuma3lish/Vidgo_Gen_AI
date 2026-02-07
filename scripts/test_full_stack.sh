#!/bin/bash
# VidGo Full Stack Test Script
# Run after: docker compose up -d
# Use SKIP_PREGENERATION=true when materials already exist for faster startup.

set -e
BASE_URL="${API_BASE:-http://localhost:8001}"
FRONTEND_URL="${FRONTEND_BASE:-http://localhost:8501}"
MAX_RETRIES="${HEALTH_RETRIES:-24}"  # ~2 min at 5s interval

echo "=========================================="
echo "VidGo Full Stack Test"
echo "=========================================="
echo ""

# 1. Backend health (with retry for pre-generation)
echo "1. Backend Health..."
for i in $(seq 1 $MAX_RETRIES); do
  HEALTH=$(curl -s --connect-timeout 5 "$BASE_URL/health" 2>/dev/null || echo '{"status":"fail"}')
  if echo "$HEALTH" | grep -q '"status":"ok"'; then
    echo "   $HEALTH"
    echo "   ✓ Backend OK"
    break
  fi
  if [ $i -eq $MAX_RETRIES ]; then
    echo "   ✗ Backend not ready after ${MAX_RETRIES} attempts"
    echo "   Run: docker compose logs -f backend"
    exit 1
  fi
  echo "   Attempt $i/$MAX_RETRIES: waiting for backend..."
  sleep 5
done
echo ""

# 2. Materials in DB
echo "2. Materials in Material DB..."
MAT_STATUS=$(curl -s --connect-timeout 5 "$BASE_URL/materials/status" 2>/dev/null || echo '{}')
if echo "$MAT_STATUS" | grep -q '"status":"ok"'; then
  echo "   ✓ Materials API OK"
  echo "$MAT_STATUS" | python3 -c "
import sys, json
try:
  d = json.load(sys.stdin)
  m = d.get('materials', {})
  counts = {}
  for cat, info in (m or {}).items():
    if isinstance(info, dict) and 'counts' in info:
      c = info['counts']
      if isinstance(c, dict):
        counts[cat] = sum(v for v in c.values() if isinstance(v, (int, float)))
      else:
        counts[cat] = c
    elif isinstance(info, dict) and 'ready' in info:
      counts[cat] = 'ready' if info.get('ready') else 'incomplete'
  total = sum(v for v in counts.values() if isinstance(v, (int, float)))
  if total > 0 or counts:
    print(f'   ✓ Materials in DB: {counts}' if counts else '   ✓ Materials endpoint OK')
  else:
    print('   ⚠ No materials yet (pre-generation may still be running)')
except Exception as e: print('   (parse:', str(e)[:40], ')')
" 2>/dev/null || echo "   (raw response received)"
else
  echo "   ⚠ Materials status unavailable (backend may still be starting)"
fi
echo ""

# 3. Demo topics
echo "3. Demo Topics API..."
TOPICS=$(curl -s "$BASE_URL/api/v1/demo/topics")
if echo "$TOPICS" | grep -q '"success":true'; then
  echo "   ✓ Topics API OK"
else
  echo "   ✗ Topics API failed"
fi
echo ""

# 4. Presets
echo "4. Presets API (background_removal)..."
PRESETS=$(curl -s "$BASE_URL/api/v1/demo/presets/background_removal?limit=3")
if echo "$PRESETS" | grep -q '"success":true'; then
  COUNT=$(echo "$PRESETS" | grep -o '"count":[0-9]*' | cut -d: -f2)
  echo "   ✓ Presets OK (count: $COUNT)"
else
  echo "   ✗ Presets API failed"
fi
echo ""

# 5. Frontend (retry - Vite/type-check may take 20-60s)
echo "5. Frontend..."
for i in $(seq 1 $MAX_RETRIES); do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$FRONTEND_URL" 2>/dev/null || echo "000")
  if [ "$CODE" = "200" ]; then
    echo "   ✓ Frontend OK ($FRONTEND_URL)"
    break
  fi
  if [ $i -eq $MAX_RETRIES ]; then
    echo "   ✗ Frontend not ready after ${MAX_RETRIES} attempts (HTTP $CODE)"
    exit 1
  fi
  echo "   Attempt $i/$MAX_RETRIES: waiting for frontend..."
  sleep 5
done
echo ""

echo "=========================================="
echo "Test complete"
echo "=========================================="
