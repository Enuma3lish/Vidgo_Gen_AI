#!/bin/bash
###############################################################################
# VidGo — End-to-end GCP deploy orchestrator
#
# Runs the full sequence:
#   1. Preflight  — gcloud auth, project, git clean, working dir
#   2. Infra      — bash gcp/deploy.sh  (infra + Cloud Run services)
#   3. Admin      — seed test_user / admin account (one-shot Job)
#   4. Pregen     — populate Material DB for all 8 tools (EXPENSIVE, prompts)
#   5. Verify     — health + preset counts + basic smoke test
#
# Usage:
#   bash gcp/full-deploy.sh                     # full run, prompts before pregen
#   bash gcp/full-deploy.sh --skip-infra        # skip step 2 (infra already up)
#   bash gcp/full-deploy.sh --skip-pregen       # skip step 4 (don't burn credits)
#   bash gcp/full-deploy.sh --only-verify       # only run step 5
#   bash gcp/full-deploy.sh --pregen-tool bg    # pregen a single tool
#   bash gcp/full-deploy.sh --yes               # non-interactive (auto-confirm)
#
# Env overrides (same vars as deploy.sh):
#   PROJECT_ID, REGION, BACKEND_SERVICE, BUCKET_NAME, CUSTOM_DOMAIN_BACKEND
###############################################################################

set -euo pipefail

# ── Self-locate: cd to repo root so this script works from anywhere ──────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# ── Config (matches gcp/deploy.sh) ───────────────────────────────────────────
PROJECT_ID="${PROJECT_ID:-vidgo-ai}"
REGION="${REGION:-asia-east1}"
BACKEND_SERVICE="${BACKEND_SERVICE:-vidgo-backend}"
BUCKET_NAME="${BUCKET_NAME:-vidgo-media-${PROJECT_ID}}"
CUSTOM_DOMAIN_BACKEND="${CUSTOM_DOMAIN_BACKEND:-api.vidgo.co}"
CUSTOM_DOMAIN_FRONTEND="${CUSTOM_DOMAIN_FRONTEND:-vidgo.co}"
BACKEND_SA="${BACKEND_SERVICE}@${PROJECT_ID}.iam.gserviceaccount.com"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/vidgo-images/vidgo-backend:latest"
BACKEND_URL="https://${CUSTOM_DOMAIN_BACKEND}"

LOG_DIR="/tmp"
LOG_FILE="${LOG_DIR}/vidgo-deploy-$(date +%Y%m%d-%H%M%S).log"

# ── Flags ────────────────────────────────────────────────────────────────────
SKIP_INFRA=false
SKIP_ADMIN=false
SKIP_PREGEN=false
ONLY_VERIFY=false
AUTO_YES=false
PREGEN_TOOL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-infra)      SKIP_INFRA=true;  shift ;;
    --skip-admin)      SKIP_ADMIN=true;  shift ;;
    --skip-pregen)     SKIP_PREGEN=true; shift ;;
    --only-verify)     ONLY_VERIFY=true; shift ;;
    --yes|-y)          AUTO_YES=true;    shift ;;
    --pregen-tool)     PREGEN_TOOL="$2"; shift 2 ;;
    -h|--help)
      sed -n '3,25p' "$0"
      exit 0
      ;;
    *) echo "Unknown flag: $1" >&2; exit 2 ;;
  esac
done

# ── Helpers ──────────────────────────────────────────────────────────────────
log()    { echo -e "[full-deploy $(date -u +%H:%M:%SZ)] $*" | tee -a "${LOG_FILE}"; }
die()    { echo -e "\033[0;31m[full-deploy FATAL]\033[0m $*" >&2; exit 1; }
step()   { echo -e "\n\033[1;36m━━━ $* ━━━\033[0m" | tee -a "${LOG_FILE}"; }
ok()     { echo -e "\033[0;32m✓\033[0m $*" | tee -a "${LOG_FILE}"; }
warn()   { echo -e "\033[0;33m⚠\033[0m $*" | tee -a "${LOG_FILE}"; }

confirm() {
  local prompt="$1"
  if [[ "${AUTO_YES}" == "true" ]]; then
    log "auto-confirm: ${prompt}"
    return 0
  fi
  read -r -p "${prompt} [y/N] " reply
  [[ "${reply}" =~ ^[Yy]$ ]]
}

ensure_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

# ── Phase 1: Preflight ───────────────────────────────────────────────────────
preflight() {
  step "Phase 1 / 5 — Preflight"

  ensure_cmd gcloud
  ensure_cmd git
  ensure_cmd curl
  ensure_cmd python3

  # Sanity: the cd at the top of this script should have landed us at repo root.
  if [[ ! -f gcp/deploy.sh ]]; then
    die "gcp/deploy.sh not found in ${REPO_ROOT} — is this the VidGo repo?"
  fi
  log "repo root: ${REPO_ROOT}"

  # Check gcloud auth
  local active_account
  active_account="$(gcloud config get-value account 2>/dev/null || echo '')"
  [[ -z "${active_account}" ]] && die "No active gcloud account. Run: gcloud auth login"
  ok "gcloud account: ${active_account}"

  # Check active project
  local active_project
  active_project="$(gcloud config get-value project 2>/dev/null || echo '')"
  if [[ "${active_project}" != "${PROJECT_ID}" ]]; then
    warn "Active project is '${active_project}', expected '${PROJECT_ID}'"
    confirm "Set gcloud project to '${PROJECT_ID}'?" || die "Aborted."
    gcloud config set project "${PROJECT_ID}"
  fi
  ok "project: ${PROJECT_ID}"

  # Check ADC (needed for some scripts that use google-cloud-storage locally)
  if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    warn "ADC not configured. Vertex AI / GCS SDKs will fail locally until you run:"
    warn "  gcloud auth application-default login"
    confirm "Continue anyway?" || die "Aborted."
  else
    ok "ADC available"
  fi

  # Check git status
  if [[ -n "$(git status --porcelain)" ]]; then
    warn "Uncommitted changes detected:"
    git status --short | head -20
    confirm "Continue with uncommitted changes?" || die "Aborted. Commit or stash first."
  else
    ok "git working tree clean"
  fi

  # Warn if we're not on main
  local branch
  branch="$(git rev-parse --abbrev-ref HEAD)"
  if [[ "${branch}" != "main" ]]; then
    warn "Current branch is '${branch}', not 'main'"
    confirm "Deploy anyway?" || die "Aborted."
  fi
  ok "branch: ${branch}"

  log "Preflight passed. Log: ${LOG_FILE}"
}

# ── Phase 2: Infra + Cloud Run services ─────────────────────────────────────
run_infra() {
  step "Phase 2 / 5 — Infra + Cloud Run (gcp/deploy.sh)"

  if [[ "${SKIP_INFRA}" == "true" ]]; then
    log "--skip-infra set, skipping"
    return 0
  fi

  warn "This runs the full gcp/deploy.sh — first-run takes 25-40 min."
  warn "Re-runs are idempotent and much faster (most steps skip-if-exists)."
  confirm "Run gcp/deploy.sh now?" || { warn "Skipped infra step"; return 0; }

  bash gcp/deploy.sh 2>&1 | tee -a "${LOG_FILE}"

  # Verify service is live
  local url
  url="$(gcloud run services describe "${BACKEND_SERVICE}" \
          --region="${REGION}" --format='value(status.url)' 2>/dev/null || echo '')"
  [[ -z "${url}" ]] && die "Backend service not found after deploy"
  ok "backend service URL: ${url}"
}

# ── Phase 3: Seed admin + test user ─────────────────────────────────────────
#
# Reads ADMIN_ACCOUNT + ADMIN_PASSWORD from backend/.env (your local,
# gitignored file) if present, otherwise prompts interactively. Pushes them
# into Secret Manager (ADMIN_ACCOUNT / ADMIN_PASSWORD secrets), then runs
# scripts/seed_test_user.py as a one-shot Cloud Run Job with those secrets
# injected. Real credentials never appear in source control or in CLI history.
seed_admin() {
  step "Phase 3 / 5 — Seed admin + test user"

  if [[ "${SKIP_ADMIN}" == "true" ]]; then
    log "--skip-admin set, skipping"
    return 0
  fi

  local job_name="vidgo-seed-user"
  local admin_account=""
  local admin_password=""

  # 1. Try backend/.env first (your local file, gitignored)
  if [[ -f backend/.env ]]; then
    admin_account="$(grep -E '^ADMIN_ACCOUNT=' backend/.env | head -1 | cut -d= -f2- | tr -d '"'"'"' ')"
    admin_password="$(grep -E '^ADMIN_PASSWORD=' backend/.env | head -1 | cut -d= -f2- | tr -d '"'"'"' ')"
    admin_extra="$(grep -E '^ADMIN_EXTRA_ACCOUNTS=' backend/.env | head -1 | cut -d= -f2- | tr -d '"'"'"' ')"
    if [[ -n "${admin_account}" && -n "${admin_password}" ]]; then
      ok "found ADMIN_ACCOUNT + ADMIN_PASSWORD in backend/.env"
    fi
  fi

  # 2. Fall back to interactive prompt
  if [[ -z "${admin_account}" ]]; then
    read -r -p "Admin email: " admin_account
  fi
  if [[ -z "${admin_password}" ]]; then
    read -r -s -p "Admin password (input hidden): " admin_password
    echo
  fi

  [[ -z "${admin_account}" ]] && die "Admin email is required"
  [[ -z "${admin_password}" ]] && die "Admin password is required"

  # Basic sanity check on password length
  if [[ "${#admin_password}" -lt 8 ]]; then
    warn "Admin password is shorter than 8 characters — continuing anyway"
  fi

  # 3. Push / update Secret Manager entries (idempotent)
  push_secret() {
    local name="$1" value="$2"
    if gcloud secrets describe "${name}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
      printf '%s' "${value}" | gcloud secrets versions add "${name}" \
        --project="${PROJECT_ID}" --data-file=- >/dev/null
      log "  ↑ added new version of secret: ${name}"
    else
      printf '%s' "${value}" | gcloud secrets create "${name}" \
        --project="${PROJECT_ID}" --replication-policy="automatic" \
        --data-file=- >/dev/null
      log "  + created secret: ${name}"
    fi
    # Ensure the backend SA can read it
    gcloud secrets add-iam-policy-binding "${name}" \
      --project="${PROJECT_ID}" \
      --member="serviceAccount:${BACKEND_SA}" \
      --role="roles/secretmanager.secretAccessor" \
      >/dev/null 2>&1 || true
  }

  log "Pushing ADMIN_ACCOUNT + ADMIN_PASSWORD to Secret Manager..."
  push_secret "ADMIN_ACCOUNT"  "${admin_account}"
  push_secret "ADMIN_PASSWORD" "${admin_password}"
  if [[ -n "${admin_extra:-}" ]]; then
    push_secret "ADMIN_EXTRA_ACCOUNTS" "${admin_extra}"
    log "  + pushed ADMIN_EXTRA_ACCOUNTS secret"
  fi

  # 4. Deploy / update the one-shot Job
  log "Deploying one-shot Job: ${job_name}"
  gcloud run jobs deploy "${job_name}" \
    --image="${IMAGE}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --service-account="${BACKEND_SA}" \
    --set-secrets="DATABASE_URL=DATABASE_URL:latest,SECRET_KEY=SECRET_KEY:latest,ADMIN_ACCOUNT=ADMIN_ACCOUNT:latest,ADMIN_PASSWORD=ADMIN_PASSWORD:latest,ADMIN_EXTRA_ACCOUNTS=ADMIN_EXTRA_ACCOUNTS:latest" \
    --task-timeout=300 \
    --max-retries=0 \
    --command="/bin/bash" \
    --args="-c,python -m scripts.seed_test_user" \
    2>&1 | tee -a "${LOG_FILE}"

  log "Executing ${job_name}..."
  gcloud run jobs execute "${job_name}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --wait \
    2>&1 | tee -a "${LOG_FILE}"

  # Clear the local copy of the password from this shell ASAP
  admin_password=""

  ok "admin + test user seeded"
  log "Admin login: ${admin_account} at https://${CUSTOM_DOMAIN_FRONTEND}/auth/login"
}

# ── Phase 4: Pre-generate materials (EXPENSIVE) ─────────────────────────────
pregen_materials() {
  step "Phase 4 / 5 — Pre-generate Material DB (EXPENSIVE)"

  if [[ "${SKIP_PREGEN}" == "true" ]]; then
    log "--skip-pregen set, skipping"
    return 0
  fi

  warn "This runs main_pregenerate.py and WILL burn real PiAPI + Pollo + Vertex credits."
  warn "Estimated cost for a full 8-tool run: \$40-75 USD."

  bash gcp/pregen-materials.sh ${PREGEN_TOOL:+--tool "${PREGEN_TOOL}"} ${AUTO_YES:+--yes}
}

# ── Phase 5: Verify ─────────────────────────────────────────────────────────
verify() {
  step "Phase 5 / 5 — Verify"

  # /health
  log "Checking ${BACKEND_URL}/health ..."
  local health
  health="$(curl -fsS "${BACKEND_URL}/health" 2>&1 || echo 'FAILED')"
  echo "  ${health}" | tee -a "${LOG_FILE}"
  [[ "${health}" != *'"status":"ok"'* ]] && die "Backend /health failed"
  ok "backend healthy"

  # Preset counts for all 8 tools
  log "Checking preset counts..."
  local all_ok=true
  for tool in background_removal try_on ai_avatar effect product_scene room_redesign short_video pattern_generate; do
    local resp count db_empty
    resp="$(curl -fsS "${BACKEND_URL}/api/v1/demo/presets/${tool}" 2>&1 || echo '')"
    if [[ -z "${resp}" ]]; then
      printf "  %-20s ERROR\n" "${tool}" | tee -a "${LOG_FILE}"
      all_ok=false
      continue
    fi
    count="$(echo "${resp}"    | python3 -c "import sys,json;print(json.load(sys.stdin).get('count',0))"    2>/dev/null || echo '?')"
    db_empty="$(echo "${resp}" | python3 -c "import sys,json;print(json.load(sys.stdin).get('db_empty',False))" 2>/dev/null || echo '?')"
    printf "  %-20s count=%-4s db_empty=%s\n" "${tool}" "${count}" "${db_empty}" | tee -a "${LOG_FILE}"
    [[ "${count}" == "0" ]] && all_ok=false
  done

  if [[ "${all_ok}" == "true" ]]; then
    ok "All 8 tools have preset rows"
  else
    warn "Some tools have 0 presets — re-run pregen for those tools"
  fi

  # Print login info
  echo ""
  log "Deploy complete. Log saved to: ${LOG_FILE}"
  log "Frontend: https://${CUSTOM_DOMAIN_FRONTEND}"
  log "Backend:  ${BACKEND_URL}"
  log "Admin login: admin@vidgo.ai / Admin1234!"
  log ""
  log "Next: run the visitor/free/paid/admin browser verification in"
  log "  qa/runs/2026-04-13/visitor-run-report.md (visitor flow reference)"
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
  log "VidGo full deploy starting — log: ${LOG_FILE}"
  log "project=${PROJECT_ID} region=${REGION} backend=${BACKEND_SERVICE}"

  if [[ "${ONLY_VERIFY}" == "true" ]]; then
    verify
    exit 0
  fi

  preflight
  run_infra
  seed_admin
  pregen_materials
  verify
}

main "$@"
