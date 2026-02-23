#!/bin/bash
# Full flow: migrate -> seed pricing + test user -> seed materials (until enough) -> start services -> run API content tests.
# Run from repo root. Uses docker compose. Set API_BASE for tests (default http://localhost:8001).
set -e
cd "$(dirname "$0")/.."
API_BASE="${API_BASE:-http://localhost:8001}"

echo "=========================================="
echo "VidGo full flow: DB + materials + services + content tests"
echo "=========================================="

# 1. Start infra
echo ""
echo "1. Starting postgres, redis, mailpit..."
docker compose up -d postgres redis mailpit
echo "   Waiting for postgres..."
sleep 5
until docker compose exec -T postgres pg_isready -U postgres 2>/dev/null; do sleep 2; done
echo "   Postgres ready."

# 2. Run migrations and seeds in backend container (build/start backend once for one-off commands)
echo ""
echo "2. Running migrations..."
docker compose run --rm backend alembic upgrade head
echo ""
echo "3. Seeding service pricing..."
docker compose run --rm backend python -m scripts.seed_service_pricing
echo ""
echo "4. Seeding test user (test@example.com)..."
docker compose run --rm backend python -m scripts.seed_test_user

# 5. Seed materials until we have enough (required: product_scene, effect, background_removal, short_video, ai_avatar min 3 each)
echo ""
echo "5. Seeding materials (until enough for product-scene, short-video, avatar tools)..."
docker compose run --rm backend python -m scripts.seed_materials_if_empty --force 2>/dev/null || true
echo "   Checking material status (required for /tools/product-scene, /tools/short-video, /tools/avatar)..."
MATERIAL_WAIT_TIMEOUT="${MATERIAL_WAIT_TIMEOUT:-600}"
MATERIAL_WAIT_START=$(date +%s)
while true; do
  if docker compose run --rm backend python -m scripts.check_material_status 2>/dev/null; then
    echo "   Material DB ready - required tools have enough examples."
    break
  fi
  ELAPSED=$(($(date +%s) - MATERIAL_WAIT_START))
  if [ "$ELAPSED" -ge "$MATERIAL_WAIT_TIMEOUT" ]; then
    echo ""
    echo "ERROR: Materials not ready after ${MATERIAL_WAIT_TIMEOUT}s. Full stack will NOT start."
    echo "  /tools/product-scene, /tools/short-video, /tools/avatar need pre-generated examples."
    echo "  Options: set PIAPI_KEY, POLLO_API_KEY, A2E_* and run step 5 again; or: docker compose --profile init up init-materials"
    exit 1
  fi
  echo "   Waiting for materials (${ELAPSED}s / ${MATERIAL_WAIT_TIMEOUT}s)..."
  sleep 15
done

# 6. Start fullstack (only after materials are ready)
echo ""
echo "6. Starting backend, worker, frontend..."
docker compose up -d backend worker frontend
echo "   Waiting for backend health..."
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -s -o /dev/null -w "%{http_code}" "$API_BASE/health" 2>/dev/null | grep -q 200; then
    echo "   Backend is up."
    break
  fi
  if [ "$i" -eq 10 ]; then
    echo "   WARN: Backend health check timed out. Continuing anyway."
  fi
  sleep 5
done

# 7. Run API content tests (validate response body, not just status)
echo ""
echo "7. Running API content tests..."
sleep 3
chmod +x scripts/test_api_content.sh
API_BASE="${API_BASE:-http://localhost:8001}" ./scripts/test_api_content.sh

echo ""
echo "=========================================="
echo "Full flow completed. All content checks passed."
echo "=========================================="
