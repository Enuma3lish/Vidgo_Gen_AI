#!/bin/bash
###############################################################################
# VidGo — unified pre-generation Cloud Run Job runner
#
# Single entry point for every pregeneration flow (merged 2026-06-23 from the
# former pregen-demo-examples.sh / pregen-avatar-shortvideo.sh / pregen-
# materials.sh / pregen-inputs.sh — they all shared the same Cloud Run Job
# boilerplate). Each subcommand deploys a Job pinned to the LIVE vidgo-backend
# image (so it runs the deployed code, no rebuild/redeploy) and writes straight
# into the production DB; new demos appear immediately.
#
# Subcommands:
#   demos              T2I + T2V + AI Avatar from the dropdown presets (top models).
#                      → scripts.pregenerate_demo_examples   (visitor "try free" cache)
#   avatar-shortvideo  AI Avatar + Short-Video matrix (avatar + short_video × models).
#                      → scripts.main_pregenerate
#   materials          General per-tool material pregen (8 tools).
#                      → scripts.main_pregenerate --tool <name>
#   inputs             Input-only library (Vertex Imagen T2I + Veo T2V) for the
#                      visitor (input × effect) picker. → scripts.pregenerate_inputs
#
# ALL spend real provider credits. Each subcommand prints a cost estimate and
# asks to confirm (skip with --yes). Idempotent: already-cached rows are skipped.
#
# Usage:
#   bash gcp/pregen.sh demos                       # SMOKE: 2 presets/tool, all tools
#   bash gcp/pregen.sh demos --full --yes          # FULL: 40 presets × 2 langs
#   bash gcp/pregen.sh demos --full --tool t2i,t2v
#   bash gcp/pregen.sh avatar-shortvideo --full --models hailuo,wan,kling_std,veo
#   bash gcp/pregen.sh materials --tool bg_removal --limit 4
#   bash gcp/pregen.sh materials --list
#   bash gcp/pregen.sh inputs --count 4
#   bash gcp/pregen.sh inputs --tool bg --dry-run
#
# Env overrides: PROJECT_ID, REGION, BACKEND_SERVICE, BUCKET_NAME
###############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# ── Shared config ────────────────────────────────────────────────────────────
PROJECT_ID="${PROJECT_ID:-vidgo-ai}"
REGION="${REGION:-asia-east1}"
BACKEND_SERVICE="${BACKEND_SERVICE:-vidgo-backend}"
BUCKET_NAME="${BUCKET_NAME:-vidgo-media-${PROJECT_ID}}"
CUSTOM_DOMAIN_BACKEND="${CUSTOM_DOMAIN_BACKEND:-api.vidgo.co}"
BACKEND_SA="${BACKEND_SERVICE}@${PROJECT_ID}.iam.gserviceaccount.com"
APP_NAME="${APP_NAME:-vidgo}"
SQL_INSTANCE="${SQL_INSTANCE:-prod-db}"
VPC_NAME="${VPC_NAME:-${APP_NAME}-vpc}"
SUBNET_NAME="${SUBNET_NAME:-${APP_NAME}-subnet}"
SQL_CONNECTION="${PROJECT_ID}:${REGION}:${SQL_INSTANCE}"

# Same secret set the live backend uses — every flow gets identical provider access.
SECRETS="DATABASE_URL=DATABASE_URL:latest,SECRET_KEY=SECRET_KEY:latest"
SECRETS="${SECRETS},PIAPI_KEY=PIAPI_KEY:latest,POLLO_API_KEY=POLLO_API_KEY:latest"
SECRETS="${SECRETS},A2E_API_KEY=A2E_API_KEY:latest,A2E_API_ID=A2E_API_ID:latest"
SECRETS="${SECRETS},GEMINI_API_KEY=GEMINI_API_KEY:latest"

# Common env shared by every subcommand; each appends its own extras.
BASE_ENV="GCS_BUCKET=${BUCKET_NAME}"
BASE_ENV="${BASE_ENV},VERTEX_AI_PROJECT=${PROJECT_ID},VERTEX_AI_LOCATION=${REGION},VERTEX_AI_IMAGE_LOCATION=us-central1"
BASE_ENV="${BASE_ENV},IMAGEN_MODEL=imagen-3.0-generate-002,GEMINI_MODEL=gemini-2.5-flash,GEMINI_IMAGE_MODEL=gemini-2.5-flash-image"
BASE_ENV="${BASE_ENV},PUBLIC_APP_URL=https://${CUSTOM_DOMAIN_BACKEND}"

# ── Helpers ──────────────────────────────────────────────────────────────────
log()  { echo -e "[pregen $(date -u +%H:%M:%SZ)] $*"; }
die()  { echo -e "\033[0;31m[pregen FATAL]\033[0m $*" >&2; exit 1; }
ok()   { echo -e "\033[0;32m✓\033[0m $*"; }
warn() { echo -e "\033[0;33m⚠\033[0m $*"; }

IMAGE=""        # resolved lazily by preflight()
AUTO_YES=false  # set per-subcommand from --yes

confirm() { [[ "${AUTO_YES}" == "true" ]] && return 0; read -r -p "$1 [y/N] " r; [[ "${r}" =~ ^[Yy]$ ]]; }

preflight() {
  command -v gcloud >/dev/null 2>&1 || die "gcloud not found"
  local active; active="$(gcloud config get-value project 2>/dev/null || echo '')"
  [[ "${active}" == "${PROJECT_ID}" ]] || die "Active gcloud project '${active}' != '${PROJECT_ID}'. Run: gcloud config set project ${PROJECT_ID}"
  # Pin the EXACT image the live service runs, so the Job uses deployed code.
  IMAGE="$(gcloud run services describe "${BACKEND_SERVICE}" --project="${PROJECT_ID}" --region="${REGION}" \
            --format='value(spec.template.spec.containers[0].image)' 2>/dev/null || true)"
  [[ -n "${IMAGE}" ]] || die "Could not resolve live image for ${BACKEND_SERVICE}. Run gcp/deploy.sh first."
  ok "Live image: ${IMAGE##*/}"
}

# deploy_job <job_name> <task_timeout> <env_vars>
deploy_job() {
  local job="$1" timeout="$2" env="$3"
  log "Deploying Job '${job}' (timeout ${timeout}s)…"
  gcloud run jobs deploy "${job}" \
    --image="${IMAGE}" --region="${REGION}" --project="${PROJECT_ID}" \
    --service-account="${BACKEND_SA}" \
    --network="${VPC_NAME}" --subnet="${SUBNET_NAME}" --vpc-egress=all-traffic \
    --set-cloudsql-instances="${SQL_CONNECTION}" \
    --set-secrets="${SECRETS}" --set-env-vars="${env}" \
    --task-timeout="${timeout}" --memory=2Gi --cpu=2 --max-retries=0 \
    --command="/bin/bash"
  ok "Job '${job}' deployed"
}

# exec_job <job_name> <shell_command>   (^|^ delimiter handles spaces/commas)
exec_job() {
  local job="$1" cmd="$2"
  log "Executing: ${cmd}"
  gcloud run jobs execute "${job}" --region="${REGION}" --project="${PROJECT_ID}" \
    --args="^|^-c|${cmd}" --wait
}

demo_count() {  # demo material count for a tool_type (readiness probe)
  curl -fsS "https://${CUSTOM_DOMAIN_BACKEND}/api/v1/demo/presets/$1" 2>/dev/null \
    | python3 -c 'import sys,json;print(json.load(sys.stdin).get("count",0))' 2>/dev/null || echo '?'
}

# ─────────────────────────────────────────────────────────────────────────────
# SUBCOMMAND: demos  (T2I + T2V + AI Avatar, dropdown presets, top models)
# ─────────────────────────────────────────────────────────────────────────────
cmd_demos() {
  local MODE="smoke" TOOLS="t2i,t2v,avatar" SMOKE_LIMIT=2
  # Per-generation credit estimate. Function instead of `declare -A`: macOS
  # ships bash 3.2 (no associative arrays) and the shebang is /bin/bash —
  # the array made every local run die with "t2i: unbound variable".
  _demo_cred() { case "$1" in t2i) echo 8 ;; t2v) echo 130 ;; avatar) echo 80 ;; *) echo "" ;; esac; }
  while [[ $# -gt 0 ]]; do case "$1" in
    --full)  MODE="full"; shift ;;
    --smoke) MODE="smoke"; shift ;;
    --tool)  TOOLS="$2"; shift 2 ;;
    --yes|-y) AUTO_YES=true; shift ;;
    *) die "demos: unknown flag '$1'" ;;
  esac; done
  for t in ${TOOLS//,/ }; do [[ -n "$(_demo_cred "$t")" ]] || die "demos: unknown tool '$t' (t2i|t2v|avatar)"; done

  preflight
  local PRESET_COUNT=40 LANGS=2 per_tool total=0
  [[ "${MODE}" == "smoke" ]] && per_tool=$(( SMOKE_LIMIT * LANGS )) || per_tool=$(( PRESET_COUNT * LANGS ))
  echo; warn "demos  |  mode=${MODE}  |  writes Material DB directly (no service redeploy)"
  for t in ${TOOLS//,/ }; do local c=$(( per_tool * $(_demo_cred "$t") )); total=$(( total + c )); warn "  ${t}: ${per_tool} generations  ~${c} credits"; done
  warn "  TOTAL: ~${total} credits (idempotent — cached presets are skipped)"; echo
  confirm "Spend real credits and proceed?" || die "Cancelled."

  local env="${BASE_ENV},PROMPT_LIBRARY_JSON=app/data/prompt_library.json"
  deploy_job "vidgo-pregen-demos" 86400 "${env}"
  local limit=""; [[ "${MODE}" == "smoke" ]] && limit="--limit ${SMOKE_LIMIT}"
  if exec_job "vidgo-pregen-demos" "python -m scripts.pregenerate_demo_examples --tool ${TOOLS} --mode local --yes ${limit}"; then
    ok "Done. New demos live immediately (runtime reads Material DB)."
  else
    die "demos Job FAILED — gcloud run jobs executions list --job vidgo-pregen-demos --region ${REGION}"
  fi
}

# ─────────────────────────────────────────────────────────────────────────────
# SUBCOMMAND: avatar-shortvideo  (avatar + short_video × models, main_pregenerate)
# ─────────────────────────────────────────────────────────────────────────────
cmd_avsv() {
  local MODE="smoke" ONLY="" CLEAN=false AVATAR_LIMIT_FULL=40
  local DEFAULT_MODELS="hailuo,wan,hunyuan,kling_std,seedance_720p,seedance_1080p,kling_v3_std,kling_v3_pro,veo,sora2"
  local MODELS="${DEFAULT_MODELS}" PRESET_COUNT=22
  while [[ $# -gt 0 ]]; do case "$1" in
    --full)  MODE="full"; shift ;;
    --smoke) MODE="smoke"; shift ;;
    --only)  ONLY="$2"; shift 2 ;;
    --models) MODELS="$2"; shift 2 ;;
    --avatar-limit) AVATAR_LIMIT_FULL="$2"; shift 2 ;;
    --clean) CLEAN=true; shift ;;
    --yes|-y) AUTO_YES=true; shift ;;
    *) die "avatar-shortvideo: unknown flag '$1'" ;;
  esac; done
  [[ -z "${ONLY}" || "${ONLY}" == "ai_avatar" || "${ONLY}" == "short_video" ]] || die "--only must be ai_avatar or short_video"

  preflight
  local MODEL_COUNT; MODEL_COUNT="$(awk -F',' '{print NF}' <<<"${MODELS}")"
  local AVATAR_CMD SV_CMD SV_RENDERS AVATAR_RENDERS
  if [[ "${MODE}" == "smoke" ]]; then
    AVATAR_CMD="python -m scripts.main_pregenerate --tool ai_avatar --limit 2"
    SV_CMD="SHORT_VIDEO_PREGEN_MODELS=hailuo python -m scripts.main_pregenerate --tool short_video --limit 3"
    SV_RENDERS=3; AVATAR_RENDERS=2
  else
    AVATAR_CMD="python -m scripts.main_pregenerate --tool ai_avatar --limit ${AVATAR_LIMIT_FULL}"
    SV_CMD="SHORT_VIDEO_PREGEN_MODELS=${MODELS} python -m scripts.main_pregenerate --tool short_video --per-topic-limit ${MODEL_COUNT}"
    SV_RENDERS=$(( PRESET_COUNT * MODEL_COUNT )); AVATAR_RENDERS="${AVATAR_LIMIT_FULL}"
  fi
  [[ "${CLEAN}" == "true" ]] && { AVATAR_CMD="${AVATAR_CMD} --clean"; SV_CMD="${SV_CMD} --clean"; }

  echo; warn "avatar-shortvideo  |  mode=${MODE}  |  writes Material DB directly"
  [[ -z "${ONLY}" || "${ONLY}" == "ai_avatar"   ]] && warn "  ai_avatar   → ~${AVATAR_RENDERS} renders   (~\$8-15 full)"
  if [[ -z "${ONLY}" || "${ONLY}" == "short_video" ]]; then
    warn "  short_video → ${SV_RENDERS} renders (${PRESET_COUNT} presets × ${MODEL_COUNT} models: ${MODELS})"
    [[ "${MODE}" == "full" ]] && warn "                 rough cost \$$(( SV_RENDERS / 10 ))-\$$(( SV_RENDERS / 2 ))"
  fi
  echo; confirm "Spend real credits and proceed?" || die "Cancelled."

  local env="${BASE_ENV},AI_AVATAR_ENABLED=true"
  deploy_job "vidgo-pregen-avsv" 3600 "${env}"
  local FAILED=()
  if [[ -z "${ONLY}" || "${ONLY}" == "ai_avatar" ]]; then
    exec_job "vidgo-pregen-avsv" "${AVATAR_CMD}" && ok "ai_avatar finished" || FAILED+=(ai_avatar)
    log "  post-run count ai_avatar: $(demo_count ai_avatar)"
  fi
  if [[ -z "${ONLY}" || "${ONLY}" == "short_video" ]]; then
    exec_job "vidgo-pregen-avsv" "${SV_CMD}" && ok "short_video finished" || FAILED+=(short_video)
    log "  post-run count short_video: $(demo_count short_video)"
  fi
  [[ ${#FAILED[@]} -eq 0 ]] || die "Failed: ${FAILED[*]} — re-run with --only <tool>"
  ok "Done. New demos live immediately."
}

# ─────────────────────────────────────────────────────────────────────────────
# SUBCOMMAND: materials  (general per-tool main_pregenerate)
# ─────────────────────────────────────────────────────────────────────────────
cmd_materials() {
  local ALL_TOOLS=( background_removal product_scene try_on room_redesign short_video ai_avatar pattern_generate effect )
  local -a TOOLS_TO_RUN=()
  local LIMIT="" PER_TOPIC_LIMIT="" CLEAN=false TOPICS=""
  _alias() { case "$1" in
    bg|bg_removal|background_removal) echo background_removal ;;
    product|product_scene) echo product_scene ;; tryon|try_on) echo try_on ;;
    room|room_redesign) echo room_redesign ;; video|short_video) echo short_video ;;
    avatar|ai_avatar) echo ai_avatar ;; pattern|pattern_generate) echo pattern_generate ;;
    effect) echo effect ;; all|ALL) echo ALL ;; *) echo "$1" ;; esac; }
  while [[ $# -gt 0 ]]; do case "$1" in
    --tool) local r; r="$(_alias "$2")"; [[ "$r" == "ALL" ]] && TOOLS_TO_RUN=("${ALL_TOOLS[@]}") || TOOLS_TO_RUN=("$r"); shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    --per-topic-limit) PER_TOPIC_LIMIT="$2"; shift 2 ;;
    --clean) CLEAN=true; shift ;;
    --topics) TOPICS="$2"; shift 2 ;;
    --yes|-y) AUTO_YES=true; shift ;;
    --list) printf 'tools: %s\n' "${ALL_TOOLS[*]}"; echo "aliases: bg→background_removal product→product_scene tryon→try_on room→room_redesign video→short_video avatar→ai_avatar pattern→pattern_generate all→all"; return 0 ;;
    *) die "materials: unknown flag '$1'" ;;
  esac; done
  [[ ${#TOOLS_TO_RUN[@]} -gt 0 ]] || TOOLS_TO_RUN=("${ALL_TOOLS[@]}")

  preflight
  echo; warn "materials: ${TOOLS_TO_RUN[*]}"
  [[ -n "${LIMIT}" ]] && warn "  limit=${LIMIT} rows/tool (smoke)"
  warn "  spends real PiAPI/Pollo/Vertex credits (~\$5-20/tool, ~\$40-75 full 8-tool)"; echo
  confirm "Proceed?" || die "Cancelled."

  local env="${BASE_ENV},PIAPI_MCP_PATH=/app/mcp-servers/piapi-mcp-server/dist/index.js"
  deploy_job "vidgo-pregen" 3600 "${env}"
  local FAILED=()
  for tool in "${TOOLS_TO_RUN[@]}"; do
    local cmd="python -m scripts.main_pregenerate --tool ${tool}"
    [[ -n "${LIMIT}" ]] && cmd="${cmd} --limit ${LIMIT}"
    [[ -n "${PER_TOPIC_LIMIT}" ]] && cmd="${cmd} --per-topic-limit ${PER_TOPIC_LIMIT}"
    [[ "${CLEAN}" == "true" ]] && cmd="${cmd} --clean"
    [[ -n "${TOPICS}" ]] && cmd="${cmd} --topics ${TOPICS}"
    log "━━━ ${tool} ━━━"
    exec_job "vidgo-pregen" "${cmd}" && ok "${tool} finished" || FAILED+=("${tool}")
    log "  post-run count ${tool}: $(demo_count ${tool})"
  done
  [[ ${#FAILED[@]} -eq 0 ]] || die "Failed tools: ${FAILED[*]}"
  ok "All requested tools completed"
}

# ─────────────────────────────────────────────────────────────────────────────
# SUBCOMMAND: inputs  (Vertex Imagen/Veo input library, pregenerate_inputs)
# ─────────────────────────────────────────────────────────────────────────────
cmd_inputs() {
  local ALL_TOOLS=( background_removal product_scene room_redesign try_on ai_avatar effect short_video )
  local TOOL_ARG="" COUNT="" DRY_RUN=false
  _alias() { case "$1" in
    bg|bg_removal|background_removal) echo background_removal ;;
    product|product_scene) echo product_scene ;; tryon|try_on) echo try_on ;;
    room|room_redesign) echo room_redesign ;; video|short_video) echo short_video ;;
    avatar|ai_avatar) echo ai_avatar ;; effect) echo effect ;; all|ALL) echo ALL ;; *) echo "$1" ;; esac; }
  while [[ $# -gt 0 ]]; do case "$1" in
    --tool) TOOL_ARG="$(_alias "$2")"; shift 2 ;;
    --count) COUNT="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --yes|-y) AUTO_YES=true; shift ;;
    *) die "inputs: unknown flag '$1'" ;;
  esac; done

  preflight
  echo; warn "inputs: Vertex Imagen T2I + Veo T2V input library"
  [[ -n "${TOOL_ARG}" && "${TOOL_ARG}" != "ALL" ]] && warn "  tool=${TOOL_ARG}" || warn "  tools=all (${#ALL_TOOLS[@]})"
  warn "  count/topic=${COUNT:-2}; ~\$3-10 full (idempotent skip)"
  [[ "${DRY_RUN}" == "true" ]] && warn "  DRY RUN (no API/DB writes)"; echo
  confirm "Proceed?" || die "Cancelled."

  local env="${BASE_ENV},VEO_LOCATION=us-central1,VEO_MODEL=${VEO_MODEL:-veo-2.0-generate-001}"
  env="${env},VERTEX_PACING_SECONDS=${VERTEX_PACING_SECONDS:-2.5},VERTEX_MAX_RETRIES=${VERTEX_MAX_RETRIES:-3},VERTEX_RETRY_BACKOFF_SECONDS=${VERTEX_RETRY_BACKOFF_SECONDS:-30}"
  deploy_job "vidgo-pregen-inputs" 3600 "${env}"
  local cmd="python -m scripts.pregenerate_inputs"
  [[ -z "${TOOL_ARG}" || "${TOOL_ARG}" == "ALL" ]] && cmd="${cmd} --all" || cmd="${cmd} --tool ${TOOL_ARG}"
  [[ -n "${COUNT}" ]] && cmd="${cmd} --count ${COUNT}"
  [[ "${DRY_RUN}" == "true" ]] && cmd="${cmd} --dry-run"
  exec_job "vidgo-pregen-inputs" "${cmd}" && ok "Input pregen finished" || die "Input pregen failed — check job logs"
}

# ── Dispatch ─────────────────────────────────────────────────────────────────
usage() { sed -n '3,46p' "$0" | sed 's/^#//'; }

SUB="${1:-}"; [[ $# -gt 0 ]] && shift || true
case "${SUB}" in
  demos)                    cmd_demos "$@" ;;
  avatar-shortvideo|avsv)   cmd_avsv "$@" ;;
  materials)                cmd_materials "$@" ;;
  inputs)                   cmd_inputs "$@" ;;
  -h|--help|"")             usage ;;
  *) die "unknown subcommand '${SUB}' (demos | avatar-shortvideo | materials | inputs)" ;;
esac
