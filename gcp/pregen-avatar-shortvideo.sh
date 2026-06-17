#!/bin/bash
###############################################################################
# VidGo — Demo-cache pre-generation for AI Avatar + Short-Video (T2V)
#
# Populates the demo cache (Material DB) that the runtime serves to visitors:
#   • ai_avatar   — talking-head examples
#   • short_video — ONE clip per (preset, model): preset = prompt_id
#                   (sv_001…sv_022), model = the dropdown video model.
#
# ─ NO REDEPLOY NEEDED ────────────────────────────────────────────────────────
# This runs main_pregenerate.py as a Cloud Run JOB using the SAME image digest
# the live `vidgo-backend` service is already running (resolved at runtime), and
# writes rows straight into the production Material DB. The live service is never
# touched. DemoCacheService reads those rows on the next request, so new demos
# appear immediately — no `gcp/deploy*.sh`, no new revision.
#
# ─ COST ──────────────────────────────────────────────────────────────────────
# EXPENSIVE — burns real PiAPI / Pollo / Vertex / A2E credits. Short-video is the
# big one: 22 presets × N models. The script prints the exact render count and a
# rough $ range and asks you to confirm before spending.
#
# Usage:
#   bash gcp/pregen-avatar-shortvideo.sh                 # SMOKE (cheap, ~$3-6): proves the pipeline
#   bash gcp/pregen-avatar-shortvideo.sh --full          # FULL: avatar + all selected models × 22 presets
#   bash gcp/pregen-avatar-shortvideo.sh --full --models hailuo,wan,kling_std,veo
#   bash gcp/pregen-avatar-shortvideo.sh --full --only short_video
#   bash gcp/pregen-avatar-shortvideo.sh --full --only ai_avatar
#   bash gcp/pregen-avatar-shortvideo.sh --full --clean  # wipe stale rows for the tool first
#   bash gcp/pregen-avatar-shortvideo.sh --full --yes    # non-interactive
#
# Env overrides: PROJECT_ID, REGION, BACKEND_SERVICE
###############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# ── Config ───────────────────────────────────────────────────────────────────
PROJECT_ID="${PROJECT_ID:-vidgo-ai}"
REGION="${REGION:-asia-east1}"
BACKEND_SERVICE="${BACKEND_SERVICE:-vidgo-backend}"
BUCKET_NAME="${BUCKET_NAME:-vidgo-media-${PROJECT_ID}}"
CUSTOM_DOMAIN_BACKEND="${CUSTOM_DOMAIN_BACKEND:-api.vidgo.co}"
BACKEND_SA="${BACKEND_SERVICE}@${PROJECT_ID}.iam.gserviceaccount.com"
JOB_NAME="${JOB_NAME:-vidgo-pregen-avsv}"
APP_NAME="${APP_NAME:-vidgo}"
SQL_INSTANCE="${SQL_INSTANCE:-prod-db}"
VPC_NAME="${VPC_NAME:-${APP_NAME}-vpc}"
SUBNET_NAME="${SUBNET_NAME:-${APP_NAME}-subnet}"
SQL_CONNECTION="${PROJECT_ID}:${REGION}:${SQL_INSTANCE}"

# All 10 dropdown video models (tier_config.VIDEO_CREDIT_COSTS). Default FULL set;
# override with --models to trim cost.
DEFAULT_MODELS="hailuo,wan,hunyuan,kling_std,seedance_720p,seedance_1080p,kling_v3_std,kling_v3_pro,veo,sora2"
PRESET_COUNT=22  # sv_001…sv_022 in prompt_library.json

# ── Flags ────────────────────────────────────────────────────────────────────
MODE="smoke"          # smoke | full
ONLY=""               # ""(both) | ai_avatar | short_video
MODELS="${DEFAULT_MODELS}"
AVATAR_LIMIT_FULL=40  # avatar pregen iterates its own script mapping; this caps total
AUTO_YES=false
CLEAN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --full)   MODE="full"; shift ;;
    --smoke)  MODE="smoke"; shift ;;
    --only)   ONLY="$2"; shift 2 ;;
    --models) MODELS="$2"; shift 2 ;;
    --avatar-limit) AVATAR_LIMIT_FULL="$2"; shift 2 ;;
    --clean)  CLEAN=true; shift ;;
    --yes|-y) AUTO_YES=true; shift ;;
    -h|--help) sed -n '3,38p' "$0"; exit 0 ;;
    *) echo "Unknown flag: $1" >&2; exit 2 ;;
  esac
done

# ── Helpers ──────────────────────────────────────────────────────────────────
log()  { echo -e "[pregen $(date -u +%H:%M:%SZ)] $*"; }
die()  { echo -e "\033[0;31m[pregen FATAL]\033[0m $*" >&2; exit 1; }
ok()   { echo -e "\033[0;32m✓\033[0m $*"; }
warn() { echo -e "\033[0;33m⚠\033[0m $*"; }
confirm() { [[ "${AUTO_YES}" == "true" ]] && return 0; read -r -p "$1 [y/N] " r; [[ "${r}" =~ ^[Yy]$ ]]; }

# ── Preflight ────────────────────────────────────────────────────────────────
command -v gcloud >/dev/null 2>&1 || die "gcloud not found"
active_project="$(gcloud config get-value project 2>/dev/null || echo '')"
[[ "${active_project}" == "${PROJECT_ID}" ]] || die "Active gcloud project '${active_project}' != '${PROJECT_ID}'. Run: gcloud config set project ${PROJECT_ID}"

[[ -z "${ONLY}" || "${ONLY}" == "ai_avatar" || "${ONLY}" == "short_video" ]] || die "--only must be ai_avatar or short_video"

# Resolve the EXACT image the live service runs (by digest). Guarantees the Job
# runs the deployed code without rebuilding or redeploying anything.
log "Resolving live ${BACKEND_SERVICE} image digest…"
LIVE_IMAGE="$(gcloud run services describe "${BACKEND_SERVICE}" --project="${PROJECT_ID}" --region="${REGION}" \
  --format='value(spec.template.spec.containers[0].image)' 2>/dev/null || true)"
[[ -n "${LIVE_IMAGE}" ]] || die "Could not resolve live image for ${BACKEND_SERVICE}. Is it deployed?"
case "${LIVE_IMAGE}" in
  *@sha256:*) ok "Live image (by digest): ${LIVE_IMAGE##*/}" ;;
  *) warn "Live image is tag-based, not a digest: ${LIVE_IMAGE} (still uses what the service runs)" ;;
esac

# ── Build per-tool commands + cost math ──────────────────────────────────────
MODEL_COUNT="$(awk -F',' '{print NF}' <<<"${MODELS}")"

if [[ "${MODE}" == "smoke" ]]; then
  AVATAR_CMD="python -m scripts.main_pregenerate --tool ai_avatar --limit 2"
  # 1 cheap model, 3 presets → 3 short clips
  SV_CMD="SHORT_VIDEO_PREGEN_MODELS=hailuo python -m scripts.main_pregenerate --tool short_video --limit 3"
  SV_RENDERS=3; AVATAR_RENDERS=2
else
  AVATAR_CMD="python -m scripts.main_pregenerate --tool ai_avatar --limit ${AVATAR_LIMIT_FULL}"
  # per-topic-limit = #models so every preset renders every selected model
  SV_CMD="SHORT_VIDEO_PREGEN_MODELS=${MODELS} python -m scripts.main_pregenerate --tool short_video --per-topic-limit ${MODEL_COUNT}"
  SV_RENDERS=$((PRESET_COUNT * MODEL_COUNT)); AVATAR_RENDERS="${AVATAR_LIMIT_FULL}"
fi
if [[ "${CLEAN}" == "true" ]]; then
  AVATAR_CMD="${AVATAR_CMD} --clean"
  SV_CMD="${SV_CMD} --clean"
fi

# ── Summary + confirm ────────────────────────────────────────────────────────
echo
warn "Mode: ${MODE}   |   Job: ${JOB_NAME}   |   no service redeploy (writes Material DB directly)"
[[ -z "${ONLY}" || "${ONLY}" == "ai_avatar"   ]] && warn "  ai_avatar   → ~${AVATAR_RENDERS} renders   (~\$8-15 full)"
if [[ -z "${ONLY}" || "${ONLY}" == "short_video" ]]; then
  warn "  short_video → ${SV_RENDERS} renders  (${PRESET_COUNT} presets × ${MODEL_COUNT} models: ${MODELS})"
  [[ "${MODE}" == "full" ]] && warn "                 rough cost \$$(( SV_RENDERS / 10 ))-\$$(( SV_RENDERS / 2 )) (model-dependent; veo/seedance/sora2 pricier)"
fi
echo
confirm "Spend real credits and proceed?" || die "Cancelled."

# ── Deploy the Job (idempotent), pinned to the live image ────────────────────
SECRETS="DATABASE_URL=DATABASE_URL:latest,SECRET_KEY=SECRET_KEY:latest"
SECRETS="${SECRETS},PIAPI_KEY=PIAPI_KEY:latest,POLLO_API_KEY=POLLO_API_KEY:latest"
SECRETS="${SECRETS},A2E_API_KEY=A2E_API_KEY:latest,A2E_API_ID=A2E_API_ID:latest"
SECRETS="${SECRETS},GEMINI_API_KEY=GEMINI_API_KEY:latest"

ENV_VARS="GCS_BUCKET=${BUCKET_NAME}"
ENV_VARS="${ENV_VARS},VERTEX_AI_PROJECT=${PROJECT_ID},VERTEX_AI_LOCATION=${REGION},VERTEX_AI_IMAGE_LOCATION=us-central1"
ENV_VARS="${ENV_VARS},IMAGEN_MODEL=imagen-3.0-generate-002,GEMINI_MODEL=gemini-2.5-flash,GEMINI_IMAGE_MODEL=gemini-2.5-flash-image"
ENV_VARS="${ENV_VARS},PUBLIC_APP_URL=https://${CUSTOM_DOMAIN_BACKEND}"
# Avatar must actually run inside the job — bypass the prod kill-switch here so a
# `false` flag on the service doesn't make the avatar generator no-op.
ENV_VARS="${ENV_VARS},AI_AVATAR_ENABLED=true"

log "Deploying Job '${JOB_NAME}' pinned to the live image…"
gcloud run jobs deploy "${JOB_NAME}" \
  --image="${LIVE_IMAGE}" \
  --region="${REGION}" --project="${PROJECT_ID}" \
  --service-account="${BACKEND_SA}" \
  --network="${VPC_NAME}" --subnet="${SUBNET_NAME}" --vpc-egress=all-traffic \
  --set-cloudsql-instances="${SQL_CONNECTION}" \
  --set-secrets="${SECRETS}" \
  --set-env-vars="${ENV_VARS}" \
  --task-timeout=3600 --memory=2Gi --cpu=2 --max-retries=0 \
  --command="/bin/bash"
ok "Job deployed"

# ── Execute per tool ─────────────────────────────────────────────────────────
run_tool() {
  local tool="$1" cmd="$2"
  log ""
  log "━━━ Pregenerating: ${tool} ━━━"
  log "  cmd: ${cmd}"
  # ^|^ sets | as the arg delimiter so bash gets: -c "<cmd>"
  if gcloud run jobs execute "${JOB_NAME}" --region="${REGION}" --project="${PROJECT_ID}" \
       --args="^|^-c|${cmd}" --wait; then
    ok "${tool} finished"
  else
    warn "${tool} FAILED — inspect: gcloud run jobs executions list --job ${JOB_NAME} --region ${REGION}"
    return 1
  fi
  local count
  count="$(curl -fsS "https://${CUSTOM_DOMAIN_BACKEND}/api/v1/demo/presets/${tool}" 2>/dev/null \
            | python3 -c 'import sys,json;print(json.load(sys.stdin).get("count",0))' 2>/dev/null || echo '?')"
  log "  post-run demo count for ${tool}: ${count}"
}

FAILED=()
if [[ -z "${ONLY}" || "${ONLY}" == "ai_avatar"   ]]; then run_tool ai_avatar   "${AVATAR_CMD}" || FAILED+=(ai_avatar); fi
if [[ -z "${ONLY}" || "${ONLY}" == "short_video" ]]; then run_tool short_video "${SV_CMD}"     || FAILED+=(short_video); fi

echo
if [[ ${#FAILED[@]} -gt 0 ]]; then
  warn "Failed: ${FAILED[*]} — re-run with --only <tool>"
  exit 1
fi
ok "Done. New demos are live immediately (runtime reads Material DB; no redeploy)."
ok "Verify a combo:  curl -s https://${CUSTOM_DOMAIN_BACKEND}/api/v1/demo/presets/short_video | python3 -m json.tool | head"
