#!/bin/bash
###############################################################################
# VidGo — Material pre-generation Cloud Run Job runner
#
# Runs backend/scripts/main_pregenerate.py as a Cloud Run Job, one tool at a
# time. Uses the live vidgo-backend image + the same Secret Manager entries
# the backend service uses, so no secret plumbing is needed here.
#
# EXPENSIVE. This burns real provider credits. Rough per-tool cost:
#   ai_avatar        $8-15   (slowest, ~32 avatars x 4 scripts x 2 languages)
#   short_video      $10-20  (video is costly)
#   try_on           $5-8
#   product_scene    $5-10
#   room_redesign    $3-6
#   effect           $4-8
#   pattern_generate $2-4
#   background_removal $2-4
# Full 8-tool run: ~$40-75 USD.
#
# Usage:
#   bash gcp/pregen-materials.sh                   # prompts, then all 8 tools
#   bash gcp/pregen-materials.sh --tool bg_removal # one tool
#   bash gcp/pregen-materials.sh --list            # show tool name aliases
#   bash gcp/pregen-materials.sh --yes             # auto-confirm (dangerous)
#   bash gcp/pregen-materials.sh --limit 4         # cap rows per tool (cheap smoke)
###############################################################################

set -euo pipefail

# ── Self-locate: cd to repo root so this script works from anywhere ──────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

PROJECT_ID="${PROJECT_ID:-vidgo-ai}"
REGION="${REGION:-asia-east1}"
BACKEND_SERVICE="${BACKEND_SERVICE:-vidgo-backend}"
BUCKET_NAME="${BUCKET_NAME:-vidgo-media-${PROJECT_ID}}"
CUSTOM_DOMAIN_BACKEND="${CUSTOM_DOMAIN_BACKEND:-api.vidgo.co}"
BACKEND_SA="${BACKEND_SERVICE}@${PROJECT_ID}.iam.gserviceaccount.com"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/vidgo-images/vidgo-backend:latest"
JOB_NAME="vidgo-pregen"

# Canonical tool names accepted by main_pregenerate.py --tool <name>
ALL_TOOLS=(
  background_removal
  product_scene
  try_on
  room_redesign
  short_video
  ai_avatar
  pattern_generate
  effect
)

# Resolve a short alias to a canonical tool name, or pass through.
# Returns "ALL" for the special "all" alias. Portable to bash 3.2 (macOS).
resolve_tool_alias() {
  case "$1" in
    bg|bg_removal|background_removal) echo "background_removal" ;;
    product|product_scene)            echo "product_scene" ;;
    tryon|try_on)                     echo "try_on" ;;
    room|room_redesign)               echo "room_redesign" ;;
    video|short_video)                echo "short_video" ;;
    avatar|ai_avatar)                 echo "ai_avatar" ;;
    pattern|pattern_generate)         echo "pattern_generate" ;;
    effect)                           echo "effect" ;;
    all|ALL)                          echo "ALL" ;;
    *)                                echo "$1" ;;
  esac
}

# ── Flags ────────────────────────────────────────────────────────────────────
TOOLS_TO_RUN=()
AUTO_YES=false
LIMIT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tool)
      resolved="$(resolve_tool_alias "$2")"
      if [[ "${resolved}" == "ALL" ]]; then
        TOOLS_TO_RUN=("${ALL_TOOLS[@]}")
      else
        TOOLS_TO_RUN=("${resolved}")
      fi
      shift 2
      ;;
    --yes|-y)  AUTO_YES=true; shift ;;
    --limit)   LIMIT="$2"; shift 2 ;;
    --list)
      echo "Canonical tool names:"
      printf '  %s\n' "${ALL_TOOLS[@]}"
      echo ""
      echo "Short aliases:"
      echo "  bg, bg_removal     -> background_removal"
      echo "  product            -> product_scene"
      echo "  tryon              -> try_on"
      echo "  room               -> room_redesign"
      echo "  video              -> short_video"
      echo "  avatar             -> ai_avatar"
      echo "  pattern            -> pattern_generate"
      echo "  all                -> all 8 tools"
      exit 0
      ;;
    -h|--help)
      sed -n '3,30p' "$0"
      exit 0
      ;;
    *) echo "Unknown flag: $1" >&2; exit 2 ;;
  esac
done

# Default: all tools
if [[ ${#TOOLS_TO_RUN[@]} -eq 0 ]]; then
  TOOLS_TO_RUN=("${ALL_TOOLS[@]}")
fi

# ── Helpers ──────────────────────────────────────────────────────────────────
log()  { echo -e "[pregen $(date -u +%H:%M:%SZ)] $*"; }
die()  { echo -e "\033[0;31m[pregen FATAL]\033[0m $*" >&2; exit 1; }
ok()   { echo -e "\033[0;32m✓\033[0m $*"; }
warn() { echo -e "\033[0;33m⚠\033[0m $*"; }

confirm() {
  local prompt="$1"
  if [[ "${AUTO_YES}" == "true" ]]; then return 0; fi
  read -r -p "${prompt} [y/N] " reply
  [[ "${reply}" =~ ^[Yy]$ ]]
}

# ── Preflight ────────────────────────────────────────────────────────────────
command -v gcloud >/dev/null 2>&1 || die "gcloud not found"

active_project="$(gcloud config get-value project 2>/dev/null || echo '')"
if [[ "${active_project}" != "${PROJECT_ID}" ]]; then
  die "Active gcloud project is '${active_project}', expected '${PROJECT_ID}'. Run: gcloud config set project ${PROJECT_ID}"
fi

# Verify the backend service exists (we reuse its image)
if ! gcloud run services describe "${BACKEND_SERVICE}" --region="${REGION}" >/dev/null 2>&1; then
  die "Backend service ${BACKEND_SERVICE} not found in ${REGION}. Run gcp/deploy.sh first."
fi

# ── Summary + confirm ────────────────────────────────────────────────────────
warn "About to run material pre-generation for the following tools:"
printf '  - %s\n' "${TOOLS_TO_RUN[@]}"
[[ -n "${LIMIT}" ]] && warn "  limit = ${LIMIT} rows per tool (smoke mode)"
warn ""
warn "This spends real PiAPI + Pollo + Vertex credits."
warn "Rough cost: ~\$5-20 per tool, ~\$40-75 for a full 8-tool run."
confirm "Proceed?" || die "Cancelled."

# ── Deploy the Job once (idempotent: gcloud updates if it exists) ────────────
log "Deploying Job '${JOB_NAME}' (image: ${IMAGE})"

# The long --set-secrets list mirrors what vidgo-backend already uses, so the
# Job has exactly the same provider access as the live service.
SECRETS="DATABASE_URL=DATABASE_URL:latest"
SECRETS="${SECRETS},SECRET_KEY=SECRET_KEY:latest"
SECRETS="${SECRETS},PIAPI_KEY=PIAPI_KEY:latest"
SECRETS="${SECRETS},POLLO_API_KEY=POLLO_API_KEY:latest"
SECRETS="${SECRETS},A2E_API_KEY=A2E_API_KEY:latest"
SECRETS="${SECRETS},A2E_API_ID=A2E_API_ID:latest"
SECRETS="${SECRETS},GEMINI_API_KEY=GEMINI_API_KEY:latest"
SECRETS="${SECRETS},REDIS_URL=REDIS_URL:latest"

ENV_VARS="GCS_BUCKET=${BUCKET_NAME}"
ENV_VARS="${ENV_VARS},VERTEX_AI_PROJECT=${PROJECT_ID}"
ENV_VARS="${ENV_VARS},VERTEX_AI_LOCATION=${REGION}"
ENV_VARS="${ENV_VARS},VERTEX_AI_IMAGE_LOCATION=us-central1"
ENV_VARS="${ENV_VARS},IMAGEN_MODEL=imagen-3.0-generate-002"
ENV_VARS="${ENV_VARS},GEMINI_MODEL=gemini-2.0-flash"
ENV_VARS="${ENV_VARS},PIAPI_MCP_PATH=/app/mcp-servers/piapi-mcp-server/dist/index.js"
ENV_VARS="${ENV_VARS},PUBLIC_APP_URL=https://${CUSTOM_DOMAIN_BACKEND}"

# Redeploy (or create) the Job. We don't set --command here so each execution
# can override it with --args for a specific tool (see loop below).
gcloud run jobs deploy "${JOB_NAME}" \
  --image="${IMAGE}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --service-account="${BACKEND_SA}" \
  --set-secrets="${SECRETS}" \
  --set-env-vars="${ENV_VARS}" \
  --task-timeout=3600 \
  --memory=2Gi \
  --cpu=2 \
  --max-retries=0 \
  --command="/bin/bash"

ok "Job '${JOB_NAME}' deployed"

# ── Run once per tool, sequentially ─────────────────────────────────────────
FAILED_TOOLS=()
START_EPOCH=$(date +%s)

for tool in "${TOOLS_TO_RUN[@]}"; do
  log ""
  log "━━━ Pregenerating: ${tool} ━━━"

  cmd_args="python -m scripts.main_pregenerate --tool ${tool}"
  [[ -n "${LIMIT}" ]] && cmd_args="${cmd_args} --limit ${LIMIT}"

  if gcloud run jobs execute "${JOB_NAME}" \
        --region="${REGION}" \
        --project="${PROJECT_ID}" \
        --args="-c,${cmd_args}" \
        --wait; then
    ok "${tool} finished"
  else
    warn "${tool} FAILED — check job logs"
    FAILED_TOOLS+=("${tool}")
  fi

  # Quick preset count check
  count="$(curl -fsS "https://${CUSTOM_DOMAIN_BACKEND}/api/v1/demo/presets/${tool}" 2>/dev/null \
            | python3 -c "import sys,json;print(json.load(sys.stdin).get('count',0))" 2>/dev/null || echo '?')"
  log "  post-run preset count for ${tool}: ${count}"
done

END_EPOCH=$(date +%s)
DURATION=$((END_EPOCH - START_EPOCH))
log ""
log "Pregen finished in $((DURATION / 60))m $((DURATION % 60))s"

if [[ ${#FAILED_TOOLS[@]} -gt 0 ]]; then
  warn "Failed tools (re-run with --tool <name> to retry):"
  printf '  - %s\n' "${FAILED_TOOLS[@]}"
  exit 1
fi

ok "All requested tools completed"
