#!/bin/bash
###############################################################################
# fix-f012-material-urls.sh
#
# Staged remediation for F-012 (Material DB rows pointing at expired PiAPI temp
# URLs and non-existent /static/generated/*.png paths).
#
# This script runs EVERYTHING EXCEPT the final backend service deploy:
#
#   Pre-flight:   project + secrets + VPC connector sanity
#   Step 1:       gcloud builds submit → build image with the F-012 fix
#   Step 2:       gcloud run jobs deploy (vidgo-material-backfill, --dry-run)
#   Step 3:       execute dry run + print summary, PAUSE for operator review
#   Step 4:       gcloud run jobs update + execute (real backfill, writes DB)
#   Step 5:       gcloud run jobs update + execute (--verify, read-only gate)
#
# The actual `gcloud run deploy vidgo-backend` is NOT run here on purpose.
# Once step 5 prints VERIFY OK, run the deploy yourself (command printed at
# the end of this script) so you stay in control of the live service flip.
#
# This script is safe to re-run: every gcloud action is idempotent. If it
# halts mid-way, fix the reported error and re-run from the top.
#
# Usage:
#   bash gcp/fix-f012-material-urls.sh
#   bash gcp/fix-f012-material-urls.sh --yes     # skip interactive pause
#
# Exit codes:
#   0  — everything through step 5 succeeded, safe to run the deploy
#   1  — a gcloud command failed (see the last line before the exit)
#   2  — pre-flight found a missing dependency (fix before re-running)
#   3  — verify step found broken rows even after the real backfill ran
#   10 — operator aborted during the dry-run review pause
###############################################################################

set -euo pipefail

# Resolve repo root from the script's location and cd there so every
# relative path below (backend/, /tmp/..., etc.) works no matter where
# the script was invoked from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# ── Config ───────────────────────────────────────────────────────────────────
PROJECT_ID="vidgo-ai"
REGION="asia-east1"
JOB_NAME="vidgo-material-backfill"
BACKEND_SERVICE="vidgo-backend"
ARTIFACT_REPO="vidgo-images"
IMAGE_NAME="vidgo-backend"
GCS_BUCKET="vidgo-media-vidgo-ai"
VPC_CONNECTOR="vidgo-connector"
SERVICE_ACCOUNT="vidgo-backend@${PROJECT_ID}.iam.gserviceaccount.com"
DB_SECRET_NAME="DATABASE_URL"      # Secret Manager secret name; override via env if different
JOB_TIMEOUT="30m"
BACKEND_DIR="backend/"
IMAGE_TAG_FILE="/tmp/vidgo-f012-image.txt"
BUILD_CONFIG_FILE="/tmp/vidgo-f012-cloudbuild.yaml"
BUILD_IGNORE_FILE="/tmp/vidgo-f012-gcloudignore"

# Override DB_SECRET_NAME if caller exported it
DB_SECRET_NAME="${DB_SECRET_NAME_OVERRIDE:-${DB_SECRET_NAME}}"

# ── Flags ────────────────────────────────────────────────────────────────────
ASSUME_YES="false"
for arg in "$@"; do
    case "$arg" in
        --yes|-y)  ASSUME_YES="true" ;;
        -h|--help)
            sed -n '2,40p' "$0"
            exit 0
            ;;
        *)
            echo "Unknown flag: $arg" >&2
            exit 2
            ;;
    esac
done

# ── Output helpers ───────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
    BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GREEN=$'\033[32m'
    YELLOW=$'\033[33m'; CYAN=$'\033[36m'; RESET=$'\033[0m'
else
    BOLD=""; DIM=""; RED=""; GREEN=""; YELLOW=""; CYAN=""; RESET=""
fi

header()  { printf "\n${BOLD}${CYAN}=== %s ===${RESET}\n" "$*"; }
step()    { printf "${BOLD}[%s]${RESET} %s\n" "$(date -u +%H:%M:%SZ)" "$*"; }
good()    { printf "${GREEN}✓${RESET} %s\n" "$*"; }
warn()    { printf "${YELLOW}!${RESET} %s\n" "$*"; }
fail()    { printf "${RED}✗ FATAL: %s${RESET}\n" "$*" >&2; exit 1; }

pause_for_review() {
    local prompt="$1"
    if [[ "$ASSUME_YES" == "true" ]]; then
        step "ASSUME_YES — auto-continuing: $prompt"
        return 0
    fi
    printf "\n${BOLD}${YELLOW}%s${RESET}\n" "$prompt"
    printf "Type ${BOLD}yes${RESET} to continue, anything else to abort: "
    read -r reply
    if [[ "$reply" != "yes" ]]; then
        printf "${YELLOW}Operator aborted. Re-run this script when ready.${RESET}\n"
        exit 10
    fi
}

# ── Pre-flight ───────────────────────────────────────────────────────────────
header "Pre-flight"

step "Checking gcloud is installed..."
command -v gcloud >/dev/null || fail "gcloud CLI not found in PATH"
good "gcloud present: $(gcloud --version | head -1)"

step "Checking active project..."
CURRENT_PROJECT="$(gcloud config get-value project 2>/dev/null || true)"
if [[ "$CURRENT_PROJECT" != "$PROJECT_ID" ]]; then
    warn "Active project is '$CURRENT_PROJECT', setting to '$PROJECT_ID' for this run"
    gcloud config set project "$PROJECT_ID" >/dev/null
fi
good "Project: $PROJECT_ID"

step "Checking secret '$DB_SECRET_NAME' exists in Secret Manager..."
if ! gcloud secrets describe "$DB_SECRET_NAME" --project="$PROJECT_ID" >/dev/null 2>&1; then
    printf "${RED}✗${RESET} Secret '%s' not found.\n" "$DB_SECRET_NAME"
    printf "   Available DB-ish secrets:\n"
    gcloud secrets list --project="$PROJECT_ID" \
        --filter="name~.*(DATABASE|DB|POSTGRES|SQL).*" \
        --format="value(name)" | sed 's/^/     - /'
    printf "   If the name is different, re-run with:\n"
    printf "     DB_SECRET_NAME_OVERRIDE=<real-name> bash %s\n" "$0"
    exit 2
fi
good "Secret '$DB_SECRET_NAME' found"

step "Checking VPC connector '$VPC_CONNECTOR' is READY..."
CONNECTOR_STATE="$(gcloud compute networks vpc-access connectors describe "$VPC_CONNECTOR" \
    --region="$REGION" --project="$PROJECT_ID" --format="value(state)" 2>/dev/null || true)"
if [[ "$CONNECTOR_STATE" != "READY" ]]; then
    fail "VPC connector '$VPC_CONNECTOR' state is '${CONNECTOR_STATE:-missing}'. Job cannot reach Cloud SQL without it."
fi
good "VPC connector READY"

step "Checking service account '$SERVICE_ACCOUNT' exists..."
if ! gcloud iam service-accounts describe "$SERVICE_ACCOUNT" --project="$PROJECT_ID" >/dev/null 2>&1; then
    fail "Service account '$SERVICE_ACCOUNT' not found"
fi
good "Service account present"

step "Checking backend source exists at '$REPO_ROOT/$BACKEND_DIR'..."
if [[ ! -f "${BACKEND_DIR}Dockerfile" ]]; then
    fail "Could not find '${REPO_ROOT}/${BACKEND_DIR}Dockerfile' — repo layout unexpected"
fi
if [[ ! -f "${BACKEND_DIR}scripts/backfill_material_urls.py" ]]; then
    fail "Missing ${BACKEND_DIR}scripts/backfill_material_urls.py — did you run the F-012 code fix first?"
fi
# The Dockerfile has `COPY mcp-servers/piapi-mcp-server ...` with the repo
# root as context — required for the build to succeed.
if [[ ! -d "mcp-servers/piapi-mcp-server" ]]; then
    fail "Missing mcp-servers/piapi-mcp-server/ at repo root — needed by backend/Dockerfile"
fi
good "Backend source looks sane (repo root: $REPO_ROOT)"

# ── Step 1: Build image ──────────────────────────────────────────────────────
header "Step 1: Build backend image"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/${IMAGE_NAME}:f012-$(date +%Y%m%d-%H%M%S)"
printf "${DIM}Image tag: %s${RESET}\n" "$IMAGE"
printf "%s\n" "$IMAGE" > "$IMAGE_TAG_FILE"
step "Saved image tag to $IMAGE_TAG_FILE"

# backend/Dockerfile requires the repo root as its build context
# (COPY mcp-servers/... , COPY backend/... , etc). We can't use
# `gcloud builds submit --tag` because that assumes a Dockerfile at the
# source root. Instead we generate a minimal inline cloudbuild.yaml that
# does the one build step and points at backend/Dockerfile.
cat > "$BUILD_CONFIG_FILE" <<EOF
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - '${IMAGE}'
      - '-f'
      - 'backend/Dockerfile'
      - '.'
images:
  - '${IMAGE}'
timeout: '1200s'
options:
  machineType: E2_HIGHCPU_8
EOF

# And a temp .gcloudignore so we don't upload node_modules, .git, qa/ etc.
# Keeps the build context small and fast. Does NOT touch the real
# .gcloudignore if one exists — we pass this via --ignore-file.
cat > "$BUILD_IGNORE_FILE" <<'EOF'
.git/
.gitignore
.github/
node_modules/
**/node_modules/
frontend-vue/dist/
frontend-vue/.vite/
backend/__pycache__/
**/__pycache__/
*.pyc
.venv/
venv/
qa/
.playwright-mcp/
.claude/
.vscode/
.idea/
.DS_Store
*.log
EOF
step "Generated temp build config + ignore file"

step "Running 'gcloud builds submit' (5–10 min)..."
if ! gcloud builds submit . \
        --config="$BUILD_CONFIG_FILE" \
        --ignore-file="$BUILD_IGNORE_FILE" \
        --project="$PROJECT_ID"; then
    fail "Cloud Build failed — see the last step output above"
fi
good "Image built and pushed: $IMAGE"
rm -f "$BUILD_CONFIG_FILE" "$BUILD_IGNORE_FILE"

# ── Step 2: Deploy Cloud Run Job (dry-run args) ──────────────────────────────
header "Step 2: Deploy Cloud Run Job (dry-run mode)"

step "Creating/updating Cloud Run Job '$JOB_NAME'..."
gcloud run jobs deploy "$JOB_NAME" \
    --image="$IMAGE" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --vpc-connector="$VPC_CONNECTOR" \
    --service-account="$SERVICE_ACCOUNT" \
    --set-env-vars="GCS_BUCKET=${GCS_BUCKET}" \
    --set-secrets="DATABASE_URL=${DB_SECRET_NAME}:latest" \
    --command=python \
    --args="-m,scripts.backfill_material_urls,--dry-run" \
    --task-timeout="$JOB_TIMEOUT" \
    --max-retries=0 \
    --quiet
good "Job '$JOB_NAME' deployed (dry-run args)"

# ── Step 3: Execute dry-run + review ─────────────────────────────────────────
header "Step 3: Execute DRY RUN and review output"

DRY_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
step "Executing job (no DB writes)... this may take 1–5 minutes"
if ! gcloud run jobs execute "$JOB_NAME" \
        --project="$PROJECT_ID" \
        --region="$REGION" \
        --wait; then
    fail "Dry-run execution failed — pull logs with: gcloud logging read 'resource.type=cloud_run_job AND resource.labels.job_name=${JOB_NAME}' --project=${PROJECT_ID} --limit=200"
fi

step "Pulling dry-run logs..."
printf "${DIM}--- dry-run log output ---${RESET}\n"
gcloud logging read \
    "resource.type=cloud_run_job AND resource.labels.job_name=${JOB_NAME} AND timestamp>=\"${DRY_START}\"" \
    --project="$PROJECT_ID" \
    --limit=500 \
    --order=asc \
    --format='value(textPayload)' \
    | tail -150
printf "${DIM}--- end dry-run log ---${RESET}\n"

pause_for_review "Review the BACKFILL SUMMARY above. Does it look correct? (checking: inspected > 0, temp_404/local_missing/persisted counts match expectations)"

# ── Step 4: Real backfill ────────────────────────────────────────────────────
header "Step 4: Real backfill (DB writes enabled)"

step "Updating job to drop --dry-run..."
gcloud run jobs update "$JOB_NAME" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --args="-m,scripts.backfill_material_urls" \
    --quiet
good "Job updated"

REAL_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
step "Executing real backfill..."
if ! gcloud run jobs execute "$JOB_NAME" \
        --project="$PROJECT_ID" \
        --region="$REGION" \
        --wait; then
    fail "Real backfill execution failed — pull logs with the command printed above"
fi

step "Pulling real-backfill logs..."
printf "${DIM}--- real backfill log output ---${RESET}\n"
gcloud logging read \
    "resource.type=cloud_run_job AND resource.labels.job_name=${JOB_NAME} AND timestamp>=\"${REAL_START}\"" \
    --project="$PROJECT_ID" \
    --limit=500 \
    --order=asc \
    --format='value(textPayload)' \
    | tail -150
printf "${DIM}--- end real backfill log ---${RESET}\n"

# ── Step 5: Verify ───────────────────────────────────────────────────────────
header "Step 5: Verify gate"

step "Updating job to --verify mode..."
gcloud run jobs update "$JOB_NAME" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --args="-m,scripts.backfill_material_urls,--verify" \
    --quiet

VERIFY_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
step "Executing verify..."
VERIFY_RC=0
gcloud run jobs execute "$JOB_NAME" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --wait || VERIFY_RC=$?

step "Pulling verify logs..."
printf "${DIM}--- verify log output ---${RESET}\n"
gcloud logging read \
    "resource.type=cloud_run_job AND resource.labels.job_name=${JOB_NAME} AND timestamp>=\"${VERIFY_START}\"" \
    --project="$PROJECT_ID" \
    --limit=200 \
    --order=asc \
    --format='value(textPayload)' \
    | tail -100
printf "${DIM}--- end verify log ---${RESET}\n"

if [[ "$VERIFY_RC" -ne 0 ]]; then
    printf "\n${RED}${BOLD}VERIFY FAILED${RESET} — Material DB still has broken URLs after the real backfill.\n"
    printf "Do NOT run the backend deploy yet. Investigate the field breakdown above.\n"
    exit 3
fi

# ── Done ─────────────────────────────────────────────────────────────────────
header "ALL STEPS PASSED"
good "Material DB is clean — safe to deploy the new backend revision."
printf "\n"
printf "${BOLD}Next: run the deploy yourself${RESET} (this script deliberately does NOT):\n"
printf "\n"
printf "  ${CYAN}IMAGE=\$(cat %s)${RESET}\n" "$IMAGE_TAG_FILE"
printf "  ${CYAN}gcloud run deploy %s \\\\\n    --image=\"\$IMAGE\" \\\\\n    --project=%s \\\\\n    --region=%s${RESET}\n" \
    "$BACKEND_SERVICE" "$PROJECT_ID" "$REGION"
printf "\n"
printf "If the new revision fails to become healthy, roll back traffic with:\n"
printf "  ${CYAN}gcloud run revisions list --service=%s --project=%s --region=%s${RESET}\n" \
    "$BACKEND_SERVICE" "$PROJECT_ID" "$REGION"
printf "  ${CYAN}gcloud run services update-traffic %s --to-revisions=<old-revision>=100 --project=%s --region=%s${RESET}\n" \
    "$BACKEND_SERVICE" "$PROJECT_ID" "$REGION"
printf "\n"

exit 0
