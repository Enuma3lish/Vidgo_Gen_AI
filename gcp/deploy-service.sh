#!/bin/bash
###############################################################################
# VidGo — SERVICE-ONLY re-deploy (code change, NO infra change)
#
# Use this when you ONLY changed application code and want to ship it without
# touching VPC / Cloud SQL / secrets / env / scaling / domain mappings.
#
# How it stays infra-safe:
#   1. Builds the image on Cloud Build (linux/amd64, native on GCP — no local
#      Docker needed) and pushes it to Artifact Registry.
#   2. Swaps it onto the EXISTING Cloud Run service with
#         gcloud run services update <svc> --image <repo>@<digest>
#      `services update --image` changes ONLY the container image; every other
#      setting (VPC connector / Direct VPC egress, --add-cloudsql-instances,
#      env vars, secrets, min/max instances, CPU/memory, timeout, domain
#      mappings) is preserved exactly as-is.
#   3. Deploys by DIGEST (not a mutable tag) so the exact image you built is the
#      one that runs.
#   4. If the new revision fails to start, Cloud Run keeps serving the previous
#      healthy revision — no outage — and this script exits non-zero.
#
# For INFRA changes (new VPC/SQL/secret/scaling/flags) use gcp/deploy.sh instead.
#
# Usage:
#   bash gcp/deploy-service.sh                # backend + frontend
#   bash gcp/deploy-service.sh --backend      # backend only
#   bash gcp/deploy-service.sh --frontend     # frontend only
#   bash gcp/deploy-service.sh --frontend --firebase   # frontend via Firebase Hosting instead of Cloud Run
#   PROJECT_ID=vidgo-ai REGION=asia-east1 bash gcp/deploy-service.sh
#
# Rollback (no rebuild needed — pick a prior revision):
#   gcloud run services update-traffic <svc> --to-revisions <REVISION>=100 \
#     --project=<PROJECT_ID> --region=<REGION>
###############################################################################
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# ── Config (override via env) ────────────────────────────────────────────────
PROJECT_ID="${PROJECT_ID:-vidgo-ai}"
REGION="${REGION:-asia-east1}"
ARTIFACT_REPO="${ARTIFACT_REPO:-vidgo-images}"
BACKEND_SERVICE="${BACKEND_SERVICE:-vidgo-backend}"
FRONTEND_SERVICE="${FRONTEND_SERVICE:-vidgo-frontend}"
FIREBASE_PROJECT="${FIREBASE_PROJECT:-vidgo-gen-ai-prod}"
AR="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}"
TAG="svc-$(date +%Y%m%d-%H%M%S)"

# ── Args ─────────────────────────────────────────────────────────────────────
DO_BACKEND=false
DO_FRONTEND=false
USE_FIREBASE=false
if [[ $# -eq 0 ]]; then DO_BACKEND=true; DO_FRONTEND=true; fi
while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend)  DO_BACKEND=true ;;
    --frontend) DO_FRONTEND=true ;;
    --all)      DO_BACKEND=true; DO_FRONTEND=true ;;
    --firebase) USE_FIREBASE=true ;;
    -h|--help)  sed -n '2,40p' "$0"; exit 0 ;;
    *) echo "Unknown arg: $1 (use --backend|--frontend|--all|--firebase)"; exit 2 ;;
  esac
  shift
done

C='\033[0;36m'; G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; NC='\033[0m'
log()  { printf "\n${C}▶ %s${NC}\n" "$1"; }
ok()   { printf "${G}✓ %s${NC}\n" "$1"; }
warn() { printf "${Y}! %s${NC}\n" "$1"; }
die()  { printf "${R}✗ %s${NC}\n" "$1"; exit 1; }

command -v gcloud >/dev/null || die "gcloud not found"
gcloud config set project "${PROJECT_ID}" >/dev/null 2>&1 || true

# ── Build + push one image on Cloud Build, return nothing (uses global TAG) ──
#    $1 service name   $2 source dir to upload   $3 Dockerfile (relative to src)
build_push() {
  local svc=$1 src=$2 dockerfile=$3
  local img="${AR}/${svc}"
  log "[${svc}] Building on Cloud Build → ${img}:${TAG}"
  local cfg; cfg="$(mktemp)"
  cat > "${cfg}" <<EOF
steps:
  - name: gcr.io/cloud-builders/docker
    args: ['build','-t','${img}:${TAG}','-t','${img}:latest','--cache-from','${img}:latest','-f','${dockerfile}','.']
  - name: gcr.io/cloud-builders/docker
    args: ['push','--all-tags','${img}']
images: ['${img}:${TAG}']
options:
  logging: CLOUD_LOGGING_ONLY
  machineType: E2_HIGHCPU_8
timeout: 1800s
EOF
  gcloud builds submit "${src}" --project="${PROJECT_ID}" --config="${cfg}"
  rm -f "${cfg}"
  ok "[${svc}] image pushed"
}

# ── Image-swap deploy by digest (NO infra change) + health check ─────────────
swap_and_check() {
  local svc=$1 health_path=$2
  local img="${AR}/${svc}"
  local digest
  digest="$(gcloud artifacts docker images describe "${img}:${TAG}" \
            --project="${PROJECT_ID}" --format='value(image_summary.digest)')"
  [[ -n "${digest}" ]] || die "[${svc}] could not resolve digest for ${img}:${TAG}"
  log "[${svc}] Deploying image-swap (keeps all existing config) → ${digest}"
  gcloud run services update "${svc}" \
    --project="${PROJECT_ID}" --region="${REGION}" \
    --image="${img}@${digest}" \
    || die "[${svc}] deploy failed — Cloud Run kept the previous revision serving (no outage). Check: gcloud run services logs read ${svc} --project=${PROJECT_ID} --region=${REGION}"

  local url rev
  url="$(gcloud run services describe "${svc}" --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"
  rev="$(gcloud run services describe "${svc}" --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.latestReadyRevisionName)')"
  ok "[${svc}] now serving revision ${rev}"

  log "[${svc}] Health check ${url}${health_path}"
  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "${url}${health_path}" || echo 000)"
  if [[ "${code}" == "200" ]]; then
    ok "[${svc}] HTTP ${code} — healthy"
  else
    warn "[${svc}] HTTP ${code} on ${health_path} — verify manually (revision is Ready but the endpoint did not return 200)"
  fi
}

# ── Backend ──────────────────────────────────────────────────────────────────
if [[ "${DO_BACKEND}" == "true" ]]; then
  build_push "${BACKEND_SERVICE}" "." "backend/Dockerfile"
  swap_and_check "${BACKEND_SERVICE}" "/health"
fi

# ── Frontend ─────────────────────────────────────────────────────────────────
if [[ "${DO_FRONTEND}" == "true" ]]; then
  if [[ "${USE_FIREBASE}" == "true" ]]; then
    # Firebase Hosting path (static SPA, global CDN) — also infra-free.
    log "[frontend] Building + deploying to Firebase Hosting (${FIREBASE_PROJECT})"
    command -v firebase >/dev/null || die "firebase CLI not found (npm i -g firebase-tools && firebase login)"
    ( cd frontend-vue && npm ci && npm run build && firebase deploy --only hosting --project "${FIREBASE_PROJECT}" )
    ok "[frontend] deployed to Firebase Hosting"
  else
    # Cloud Run path (current prod: the vidgo-frontend service). Dockerfile.prod
    # context is the frontend-vue/ dir.
    build_push "${FRONTEND_SERVICE}" "frontend-vue" "Dockerfile.prod"
    swap_and_check "${FRONTEND_SERVICE}" "/"
  fi
fi

printf "\n${G}━━━ service re-deploy complete (no infra changed) ━━━${NC}\n"
echo "Rollback if needed:"
echo "  gcloud run services update-traffic <svc> --to-revisions <PRIOR_REV>=100 --project=${PROJECT_ID} --region=${REGION}"
