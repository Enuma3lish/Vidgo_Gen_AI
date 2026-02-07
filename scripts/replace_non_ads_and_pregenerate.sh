#!/bin/bash
# Replace non-ads materials and run pregenerate for Effect, Short Video, AI Avatar.
# Ads scope: common purpose (food, general product) — NOT luxury.
#
# Prerequisites:
#   - backend/.env exists with DATABASE_URL and API keys
#   - Docker Compose services (postgres, redis) running
#
# Usage:
#   ./scripts/replace_non_ads_and_pregenerate.sh           # Dry-run
#   ./scripts/replace_non_ads_and_pregenerate.sh --delete  # Delete + pregenerate

set -e
cd "$(dirname "$0")/.."

echo "=============================================="
echo "1. Audit current materials"
echo "=============================================="
docker compose --profile tools run --rm pregenerate python -m scripts.audit_material_prompts || true

echo ""
echo "=============================================="
echo "2. Replace non-ads materials (selective delete)"
echo "=============================================="
docker compose --profile tools run --rm pregenerate python -m scripts.replace_non_ads_materials "$@"

echo ""
echo "=============================================="
echo "3. Pregenerate Effect, Short Video, AI Avatar"
echo "=============================================="
docker compose --profile tools run --rm pregenerate python -m scripts.main_pregenerate --tool effect --limit 40
docker compose --profile tools run --rm pregenerate python -m scripts.main_pregenerate --tool short_video --limit 40
docker compose --profile tools run --rm pregenerate python -m scripts.main_pregenerate --tool ai_avatar --limit 40

echo ""
echo "4. Verify"
echo "=============================================="
docker compose --profile tools run --rm pregenerate python -m scripts.audit_material_prompts || true

echo ""
echo "Done."
