#!/bin/bash
###############################################################################
# VidGo — INPUT-ONLY pre-generation Cloud Run Job runner
#
# Runs backend/scripts/pregenerate_inputs.py as a Cloud Run Job. Populates the
# pregenerated INPUT library (Vertex Imagen T2I + Vertex Veo T2V) used by the
# visitor (input × effect) picker. Results are NOT generated here — the
# runtime cache-through path calls the real provider API on first click for
# each (input, effect) pair and caches the result under a deterministic
# lookup_hash.
#
# Cost profile is much lower than main_pregenerate.py:
#   Imagen (T2I): ~$0.02 / image × ~2 per topic × ~8 tools × ~few topics each
#                 ≈ $2-6 for the full run
#   Veo    (T2V): ~$0.30-0.60 / short clip × 2-4 clips
#                 ≈ $1-3
# Rough full-run cost: $3-10 USD. Safe to run repeatedly — the script is
# idempotent (skips rows whose (tool, topic, prompt) hash already exists).
#
# Usage:
#   bash gcp/pregen-inputs.sh                   # all tools, 2 inputs per topic
#   bash gcp/pregen-inputs.sh --tool bg         # one tool
#   bash gcp/pregen-inputs.sh --count 4         # more inputs per topic
#   bash gcp/pregen-inputs.sh --dry-run         # list planned work, skip gen
#   bash gcp/pregen-inputs.sh --yes             # non-interactive
###############################################################################

set -euo pipefail

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
JOB_NAME="vidgo-pregen-inputs"
APP_NAME="${APP_NAME:-vidgo}"
SQL_INSTANCE="${SQL_INSTANCE:-prod-db}"
CONNECTOR_NAME="${CONNECTOR_NAME:-${APP_NAME}-connector}"
SQL_CONNECTION="${PROJECT_ID}:${REGION}:${SQL_INSTANCE}"
CONNECTOR_PATH="projects/${PROJECT_ID}/locations/${REGION}/connectors/${CONNECTOR_NAME}"

# Tool names that pregenerate_inputs.py accepts (image + video tools).
ALL_TOOLS=(
  background_removal
  product_scene
  room_redesign
  try_on
  ai_avatar
  effect
  short_video
)

resolve_tool_alias() {
  case "$1" in
    bg|bg_removal|background_removal) echo "background_removal" ;;
    product|product_scene)            echo "product_scene" ;;
    tryon|try_on)                     echo "try_on" ;;
    room|room_redesign)               echo "room_redesign" ;;
    video|short_video)                echo "short_video" ;;
    avatar|ai_avatar)                 echo "ai_avatar" ;;
    effect)                           echo "effect" ;;
    all|ALL)                          echo "ALL" ;;
    *)                                echo "$1" ;;
  esac
}

# ── Flags ────────────────────────────────────────────────────────────────────
TOOL_ARG=""
COUNT=""
DRY_RUN=false
AUTO_YES=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tool)      TOOL_ARG="$(resolve_tool_alias "$2")"; shift 2 ;;
    --count)     COUNT="$2"; shift 2 ;;
    --dry-run)   DRY_RUN=true; shift ;;
    --yes|-y)    AUTO_YES=true; shift ;;
    -h|--help)   sed -n '3,30p' "$0"; exit 0 ;;
    *) echo "Unknown flag: $1" >&2; exit 2 ;;
  esac
done

log()  { echo -e "[pregen-inputs $(date -u +%H:%M:%SZ)] $*"; }
die()  { echo -e "\033[0;31m[pregen-inputs FATAL]\033[0m $*" >&2; exit 1; }
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

if ! gcloud run services describe "${BACKEND_SERVICE}" --region="${REGION}" >/dev/null 2>&1; then
  die "Backend service ${BACKEND_SERVICE} not found in ${REGION}. Run gcp/deploy.sh first."
fi

# ── Summary + confirm ───────────────────────────────────────────────────────
warn "Input-only pregen via Vertex AI (Imagen T2I + Veo T2V)."
if [[ -n "${TOOL_ARG}" && "${TOOL_ARG}" != "ALL" ]]; then
  warn "  tool   = ${TOOL_ARG}"
else
  warn "  tools  = all (${#ALL_TOOLS[@]})"
fi
warn "  count per topic = ${COUNT:-2}"
[[ "${DRY_RUN}" == "true" ]] && warn "  DRY RUN (no API calls, no DB writes)"
warn ""
warn "Cost: image inputs ~\$0.02 each, video inputs ~\$0.30-0.60 each."
warn "Full run typically \$3-10 USD; rerunning is cheap (idempotent skip)."
confirm "Proceed?" || die "Cancelled."

# ── Deploy the Job (idempotent) ─────────────────────────────────────────────
log "Deploying Job '${JOB_NAME}' (image: ${IMAGE})"

# Mirror vidgo-pregen's secret set so the script can reach Postgres + any
# provider it happens to touch through the imports.
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
# Veo is only hosted in us-central1 today; pin it independently.
ENV_VARS="${ENV_VARS},VEO_LOCATION=us-central1"
# Veo 3 preview is behind an allowlist most projects don't have (the
# pregen job hit "Publisher Model ... not found or your project does not
# have access to it" on first run). Fall back to Veo 2 GA by default; to
# use Veo 3 pass VEO_MODEL=veo-3.0-generate-preview when the allowlist
# approval lands.
ENV_VARS="${ENV_VARS},VEO_MODEL=${VEO_MODEL:-veo-2.0-generate-001}"
ENV_VARS="${ENV_VARS},IMAGEN_MODEL=imagen-3.0-generate-002"
ENV_VARS="${ENV_VARS},GEMINI_MODEL=gemini-2.0-flash"
# Pace Vertex calls (seconds) to stay under the per-minute Imagen quota.
ENV_VARS="${ENV_VARS},VERTEX_PACING_SECONDS=${VERTEX_PACING_SECONDS:-2.5}"
ENV_VARS="${ENV_VARS},VERTEX_MAX_RETRIES=${VERTEX_MAX_RETRIES:-3}"
ENV_VARS="${ENV_VARS},VERTEX_RETRY_BACKOFF_SECONDS=${VERTEX_RETRY_BACKOFF_SECONDS:-30}"
ENV_VARS="${ENV_VARS},PUBLIC_APP_URL=https://${CUSTOM_DOMAIN_BACKEND}"

gcloud run jobs deploy "${JOB_NAME}" \
  --image="${IMAGE}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --service-account="${BACKEND_SA}" \
  --vpc-connector="${CONNECTOR_PATH}" \
  --set-cloudsql-instances="${SQL_CONNECTION}" \
  --set-secrets="${SECRETS}" \
  --set-env-vars="${ENV_VARS}" \
  --task-timeout=3600 \
  --memory=2Gi \
  --cpu=2 \
  --max-retries=0 \
  --command="/bin/bash"

ok "Job '${JOB_NAME}' deployed"

# ── Build args and execute ──────────────────────────────────────────────────
cmd_args="python -m scripts.pregenerate_inputs"
if [[ -z "${TOOL_ARG}" || "${TOOL_ARG}" == "ALL" ]]; then
  cmd_args="${cmd_args} --all"
else
  cmd_args="${cmd_args} --tool ${TOOL_ARG}"
fi
[[ -n "${COUNT}" ]] && cmd_args="${cmd_args} --count ${COUNT}"
[[ "${DRY_RUN}" == "true" ]] && cmd_args="${cmd_args} --dry-run"

log "Executing: ${cmd_args}"
if gcloud run jobs execute "${JOB_NAME}" \
      --region="${REGION}" \
      --project="${PROJECT_ID}" \
      --args="-c,${cmd_args}" \
      --wait; then
  ok "Input pregen finished"
else
  die "Input pregen failed — check job logs"
fi

# ── Quick verification ──────────────────────────────────────────────────────
log ""
log "Checking input-library counts via /api/v1/demo/inputs/{tool}:"
for tool in "${ALL_TOOLS[@]}"; do
  count="$(curl -fsS "https://${CUSTOM_DOMAIN_BACKEND}/api/v1/demo/inputs/${tool}" 2>/dev/null \
            | python3 -c "import sys,json;print(json.load(sys.stdin).get('count',0))" 2>/dev/null || echo '?')"
  printf "  %-20s inputs=%s\n" "${tool}" "${count}"
done

ok "Done."
