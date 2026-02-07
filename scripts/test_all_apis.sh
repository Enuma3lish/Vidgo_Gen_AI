#!/bin/bash
# Test all VidGo APIs in Docker
# Run after: docker compose up -d
set +e  # Don't exit on first failure - run all tests
BASE="${API_BASE:-http://localhost:8001}"
FAILED=0
PASSED=0

test_api() {
  local method="$1"
  local path="$2"
  local desc="$3"
  local extra="$4"
  local code
  if [ "$method" = "GET" ]; then
    code=$(curl -s -o /tmp/api_resp.json -w "%{http_code}" --connect-timeout 5 $extra "$BASE$path" 2>/dev/null || echo "000")
  else
    code=$(curl -s -o /tmp/api_resp.json -w "%{http_code}" --connect-timeout 5 -X "$method" $extra "$BASE$path" 2>/dev/null || echo "000")
  fi
  if [ "$code" = "200" ] || [ "$code" = "201" ]; then
    echo "  ✓ $desc ($code)"
    PASSED=$((PASSED + 1))
    return 0
  else
    echo "  ✗ $desc (HTTP $code)"
    FAILED=$((FAILED + 1))
    return 1
  fi
}

echo "=========================================="
echo "VidGo API Tests (Docker)"
echo "=========================================="
echo ""

# Core
echo "1. Core"
test_api GET "/health" "Health check"
test_api GET "/materials/status" "Materials status"
echo ""

# Demo
echo "2. Demo"
test_api GET "/api/v1/demo/topics" "Demo topics"
test_api GET "/api/v1/demo/presets/background_removal?limit=3" "Presets (background_removal)"
test_api GET "/api/v1/demo/presets/product_scene?limit=3" "Presets (product_scene)"
test_api GET "/api/v1/demo/presets/effect?limit=3" "Presets (effect)"
test_api GET "/api/v1/demo/try-prompts/background_removal" "Try prompts"
test_api GET "/api/v1/demo/landing/works" "Landing works"
test_api GET "/api/v1/demo/landing/examples" "Landing examples"
test_api GET "/api/v1/demo/materials/status" "Demo materials status"
test_api GET "/api/v1/demo/styles" "Demo styles"
test_api GET "/api/v1/demo/categories" "Demo categories"
echo ""

# Landing
echo "3. Landing"
test_api GET "/api/v1/landing/stats" "Landing stats"
test_api GET "/api/v1/landing/features" "Landing features"
test_api GET "/api/v1/landing/examples" "Landing examples"
test_api GET "/api/v1/landing/pricing" "Landing pricing"
test_api GET "/api/v1/landing/faq" "Landing FAQ"
echo ""

# Plans & Credits
echo "4. Plans & Credits"
test_api GET "/api/v1/plans" "Plans list"
test_api GET "/api/v1/credits/packages" "Credit packages"
test_api GET "/api/v1/credits/pricing" "Credits pricing"
test_api GET "/api/v1/promotions/active" "Active promotions"
test_api GET "/api/v1/promotions/packages" "Promotions packages"
echo ""

# Tools (GET only - POST needs auth/files)
echo "5. Tools"
test_api GET "/api/v1/tools/templates/scenes" "Templates scenes"
test_api GET "/api/v1/tools/templates/interior-styles" "Templates interior-styles"
test_api GET "/api/v1/tools/models/list" "Models list"
test_api GET "/api/v1/tools/voices/list" "Voices list"
test_api GET "/api/v1/tools/styles" "Tools styles"
test_api GET "/api/v1/tools/avatar/voices" "Avatar voices"
test_api GET "/api/v1/tools/avatar/characters" "Avatar characters"
echo ""

# Effects & Generation
echo "6. Effects & Generation"
test_api GET "/api/v1/effects/styles" "Effects styles"
test_api GET "/api/v1/generate/service-status" "Service status"
test_api GET "/api/v1/generate/interior-styles" "Interior styles"
test_api GET "/api/v1/generate/room-types" "Room types"
test_api GET "/api/v1/generate/video/styles" "Video styles"
test_api GET "/api/v1/generate/api-status" "API status"
echo ""

# Interior
echo "7. Interior"
test_api GET "/api/v1/interior/styles" "Interior styles"
test_api GET "/api/v1/interior/room-types" "Interior room-types"
echo ""

# Workflow
echo "8. Workflow"
test_api GET "/api/v1/workflow/topics" "Workflow topics"
test_api GET "/api/v1/workflow/categories" "Workflow categories"
echo ""

# Prompts
echo "9. Prompts"
test_api GET "/api/v1/prompts/groups" "Prompt groups"
test_api GET "/api/v1/prompts/cached" "Prompts cached"
echo ""

# Auth (public)
echo "10. Auth (public)"
test_api GET "/api/v1/auth/geo-language" "Geo language"
echo ""

# Session
echo "11. Session"
test_api GET "/api/v1/session/online-count" "Online count"
echo ""

# Quota
echo "12. Quota"
test_api GET "/api/v1/quota/daily" "Daily quota"
echo ""

echo "=========================================="
echo "Results: $PASSED passed, $FAILED failed"
echo "=========================================="
[ $FAILED -eq 0 ]
