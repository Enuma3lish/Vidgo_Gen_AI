#!/bin/bash
###############################################################################
# VidGo — Seed QA test personas on GCP prod (Path B from the test plan)
#
# Builds a fresh backend image (Job-only tag), deploys the vidgo-seed-user
# Cloud Run Job, and executes it twice — once for qa-pro@vidgo.local and
# once for qa-premium@vidgo.local — using the --plan mode of
# scripts/seed_test_user.py. The live vidgo-backend Cloud Run service is
# NOT touched; only the Job gets the new image.
#
# Prerequisites:
#   - You've generated a .qa-secrets file in the repo root (step 1 of the
#     instructions I gave earlier). It must look like:
#         QA_PRO_PASSWORD=<urlsafe-token>
#         QA_PREMIUM_PASSWORD=<urlsafe-token>
#   - You're authenticated: `gcloud auth login` + `gcloud config set project vidgo-ai`
#   - The repo is committed through commit e92253e (seed_test_user --plan mode)
#
# Usage:
#   bash gcp/seed-qa-personas.sh                      # full run
#   bash gcp/seed-qa-personas.sh --skip-build         # reuse an already-built image
#   bash gcp/seed-qa-personas.sh --image-tag <tag>    # use a specific tag
#   bash gcp/seed-qa-personas.sh --only pro           # only seed the Pro persona
#   bash gcp/seed-qa-personas.sh --only premium       # only seed the Premium persona
###############################################################################

set -euo pipefail

# ── Self-locate: cd to repo root ─────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# ── Config ───────────────────────────────────────────────────────────────────
PROJECT_ID="${PROJECT_ID:-vidgo-ai}"
REGION="${REGION:-asia-east1}"
BACKEND_SA="vidgo-backend@${PROJECT_ID}.iam.gserviceaccount.com"
IMAGE_REPO="${REGION}-docker.pkg.dev/${PROJECT_ID}/vidgo-images/vidgo-backend"
JOB_NAME="vidgo-seed-user"
SECRETS_FILE="${REPO_ROOT}/.qa-secrets"

# Infra wiring — must match gcp/deploy.sh so the Job container has the same
# network + Cloud SQL access as the live backend service. Without these flags
# the Job can't reach Cloud SQL and fails at startup.
APP_NAME="${APP_NAME:-vidgo}"
SQL_INSTANCE="${SQL_INSTANCE:-prod-db}"
CONNECTOR_NAME="${CONNECTOR_NAME:-${APP_NAME}-connector}"
SQL_CONNECTION="${PROJECT_ID}:${REGION}:${SQL_INSTANCE}"
CONNECTOR_PATH="projects/${PROJECT_ID}/locations/${REGION}/connectors/${CONNECTOR_NAME}"

# Note: .local is rejected by pydantic's email-validator as a reserved TLD.
# Use a fictional but syntactically valid public-TLD domain so the /auth/login
# Pydantic EmailStr validator accepts the address at login time.
PRO_EMAIL="qa-pro@vidgoqa.com"
PREMIUM_EMAIL="qa-premium@vidgoqa.com"

# ── Flags ────────────────────────────────────────────────────────────────────
SKIP_BUILD=false
IMAGE_TAG=""
ONLY=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-build)  SKIP_BUILD=true; shift ;;
    --image-tag)   IMAGE_TAG="$2"; shift 2 ;;
    --only)        ONLY="$2"; shift 2 ;;
    -h|--help)
      sed -n '3,30p' "$0"
      exit 0
      ;;
    *) echo "Unknown flag: $1" >&2; exit 2 ;;
  esac
done

# ── Helpers ──────────────────────────────────────────────────────────────────
log()  { echo -e "\033[1;36m[qa-seed $(date -u +%H:%M:%SZ)]\033[0m $*"; }
die()  { echo -e "\033[0;31m[qa-seed FATAL]\033[0m $*" >&2; exit 1; }
ok()   { echo -e "\033[0;32m  ✓\033[0m $*"; }
step() { echo -e "\n\033[1;36m━━━ $* ━━━\033[0m"; }

# Create or update a Secret Manager secret. Idempotent.
push_secret() {
  local name="$1" value="$2"
  if gcloud secrets describe "${name}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    printf '%s' "${value}" | gcloud secrets versions add "${name}" \
      --project="${PROJECT_ID}" --data-file=- >/dev/null
    ok "added new version of secret: ${name}"
  else
    printf '%s' "${value}" | gcloud secrets create "${name}" \
      --project="${PROJECT_ID}" --replication-policy="automatic" \
      --data-file=- >/dev/null
    ok "created secret: ${name}"
  fi
  # Grant the backend SA access (idempotent; fails silently if already bound)
  gcloud secrets add-iam-policy-binding "${name}" \
    --project="${PROJECT_ID}" \
    --member="serviceAccount:${BACKEND_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet >/dev/null 2>&1 || true
}

# Deploy + execute the seed Job for one persona.
seed_persona() {
  local plan="$1" email="$2" qa_secret_name="$3"

  log "Deploying Job ${JOB_NAME} for ${plan} (email=${email})"
  gcloud run jobs deploy "${JOB_NAME}" \
    --image="${IMAGE_URI}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --service-account="${BACKEND_SA}" \
    --vpc-connector="${CONNECTOR_PATH}" \
    --set-cloudsql-instances="${SQL_CONNECTION}" \
    --set-secrets="DATABASE_URL=DATABASE_URL:latest,SECRET_KEY=SECRET_KEY:latest,QA_PASSWORD=${qa_secret_name}:latest" \
    --task-timeout=300 \
    --max-retries=0 \
    --command="/bin/bash" \
    --args="-c,python -m scripts.seed_test_user --plan ${plan} --email ${email}" \
    2>&1 | grep -vE "^Deploying|This command is equivalent|Done|\\.\\.\\." || true

  log "Executing ${JOB_NAME} for ${plan}..."
  if gcloud run jobs execute "${JOB_NAME}" \
        --region="${REGION}" \
        --project="${PROJECT_ID}" \
        --wait 2>&1 | tail -5; then
    ok "${plan} persona seeded (${email})"
  else
    die "${plan} persona seed FAILED — check job logs: gcloud run jobs executions list --job=${JOB_NAME} --region=${REGION} --project=${PROJECT_ID}"
  fi
}

# ── Preflight ────────────────────────────────────────────────────────────────
step "Preflight"

command -v gcloud >/dev/null 2>&1 || die "gcloud not found"

active_project="$(gcloud config get-value project 2>/dev/null || echo '')"
if [[ "${active_project}" != "${PROJECT_ID}" ]]; then
  die "Active gcloud project is '${active_project}', expected '${PROJECT_ID}'. Run: gcloud config set project ${PROJECT_ID}"
fi
ok "project: ${PROJECT_ID}"

if [[ ! -f "${SECRETS_FILE}" ]]; then
  die ".qa-secrets not found at ${SECRETS_FILE}. Run step 1 first: generate QA_PRO_PASSWORD and QA_PREMIUM_PASSWORD into .qa-secrets"
fi

# Load .qa-secrets
# shellcheck disable=SC1090
set -a
source "${SECRETS_FILE}"
set +a

if [[ -z "${QA_PRO_PASSWORD:-}" ]]; then die "QA_PRO_PASSWORD missing from ${SECRETS_FILE}"; fi
if [[ -z "${QA_PREMIUM_PASSWORD:-}" ]]; then die "QA_PREMIUM_PASSWORD missing from ${SECRETS_FILE}"; fi
ok ".qa-secrets loaded"

# Verify the backend Cloud Run service exists (we just need it for reference)
if ! gcloud run services describe vidgo-backend --region="${REGION}" >/dev/null 2>&1; then
  die "vidgo-backend Cloud Run service not found in ${REGION}. Run gcp/deploy.sh first."
fi
ok "vidgo-backend service reachable"

# ── Step 2-3: push secrets + grant SA access ────────────────────────────────
step "Step 2-3 / 6 — Push QA passwords to Secret Manager"

push_secret "QA_PRO_PASSWORD"     "${QA_PRO_PASSWORD}"
push_secret "QA_PREMIUM_PASSWORD" "${QA_PREMIUM_PASSWORD}"

# Clear from this shell to limit exposure
QA_PRO_PASSWORD=""
QA_PREMIUM_PASSWORD=""

# ── Step 4: build fresh backend image (Job-only) ────────────────────────────
step "Step 4 / 6 — Build backend image for the Job"

if [[ "${SKIP_BUILD}" == "true" ]]; then
  if [[ -z "${IMAGE_TAG}" ]]; then
    die "--skip-build requires --image-tag <existing_tag>"
  fi
  IMAGE_URI="${IMAGE_REPO}:${IMAGE_TAG}"
  ok "skipping build, reusing ${IMAGE_URI}"
else
  if [[ -z "${IMAGE_TAG}" ]]; then
    IMAGE_TAG="seed-$(date +%Y%m%d-%H%M)"
  fi
  IMAGE_URI="${IMAGE_REPO}:${IMAGE_TAG}"

  log "Building ${IMAGE_URI} (may take 5-10 min)..."

  # Write a temp cloudbuild.yaml so we control the Dockerfile path + repo-root
  # context (gcloud builds submit --config=- + positional source dir doesn't
  # work reliably across gcloud versions; use a real file instead).
  CLOUDBUILD_YAML="$(mktemp -t vidgo-cloudbuild-XXXXXX.yaml)"
  trap 'rm -f "${CLOUDBUILD_YAML}"' EXIT
  cat > "${CLOUDBUILD_YAML}" <<EOF
steps:
- name: gcr.io/cloud-builders/docker
  args: ['build', '-f', 'backend/Dockerfile', '-t', '${IMAGE_URI}', '.']
images: ['${IMAGE_URI}']
timeout: 1500s
EOF

  gcloud builds submit . \
    --project="${PROJECT_ID}" \
    --config="${CLOUDBUILD_YAML}"

  rm -f "${CLOUDBUILD_YAML}"
  trap - EXIT

  ok "built ${IMAGE_URI}"
fi

# ── Step 5-6: deploy + execute the seed Job for each persona ────────────────
step "Step 5 / 6 — Seed Pro persona"
if [[ -z "${ONLY}" || "${ONLY}" == "pro" ]]; then
  seed_persona "pro" "${PRO_EMAIL}" "QA_PRO_PASSWORD"
else
  log "skipped (--only=${ONLY})"
fi

step "Step 6 / 6 — Seed Premium persona"
if [[ -z "${ONLY}" || "${ONLY}" == "premium" ]]; then
  seed_persona "premium" "${PREMIUM_EMAIL}" "QA_PREMIUM_PASSWORD"
else
  log "skipped (--only=${ONLY})"
fi

# ── Done ─────────────────────────────────────────────────────────────────────
step "Done"
log "Image used:  ${IMAGE_URI}"
log "Personas:    ${PRO_EMAIL} (pro) + ${PREMIUM_EMAIL} (premium)"
log ""
log "Next: sanity-check via Cloud SQL:"
log "  gcloud sql connect prod-db --user=postgres --project=${PROJECT_ID}"
log ""
log "Then in psql:"
cat <<'PSQL'
  \c vidgo
  SELECT u.email, u.plan_started_at::date, u.plan_expires_at::date,
         p.name, p.max_resolution, u.subscription_credits
  FROM users u LEFT JOIN plans p ON u.current_plan_id = p.id
  WHERE u.email LIKE 'qa-%@vidgo.local'
  ORDER BY u.email;
PSQL
log ""
log "Expected: 2 rows (qa-premium plan=premium/4k/18000, qa-pro plan=pro/1080p/10000)"
log ""
log "Paste the credentials (from .qa-secrets) + sanity-check output back in chat"
log "and I'll start Phase 2 (Playwright visitor test)."
