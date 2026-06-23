#!/bin/bash
###############################################################################
#                     VidGo GCP 完整部署腳本 (Full Deploy Script)
#                     Version: 2.0  |  Updated: 2026-06
###############################################################################
#
#  Consolidated deploy script. Supersedes the old gcp/deploy-production.sh.
#  Architecture (2026-06 cost pass):
#    - NO Memorystore Redis      (in-process cache + Cloud Scheduler instead)
#    - NO worker Cloud Run svc    (background tasks via Cloud Scheduler → /api/v1/tasks/*)
#    - NO Serverless VPC Connector (Direct VPC egress on the Cloud Run service)
#    - Frontend on Firebase Hosting (global CDN), NOT Cloud Run
#    - Static NAT IP kept — required for Giveme / ECPay outbound IP whitelist
#    - Real GCP cost on the admin dashboard via BigQuery billing export
#
#  Usage:
#    bash gcp/deploy.sh                                 # 執行全部步驟
#    bash gcp/deploy.sh --step 3                        # 只執行第 3 步
#    bash gcp/deploy.sh --from 5                        # 從第 5 步開始
#    bash gcp/deploy.sh --step secrets                  # 只執行 secrets 步驟
#    bash gcp/deploy.sh --step frontend                 # 只 build+deploy 前端到 Firebase
#    bash gcp/deploy.sh --step fixmedia                 # 只修復 GCS 影片 Content-Type
#    bash gcp/deploy.sh --step secret_cleanup           # 清理舊版 Secret (省成本)
#    SECRET_VERSIONS_TO_KEEP=1 bash gcp/deploy.sh --step secret_cleanup
#
#  修改指南:
#    1. 修改下方 ══ CONFIG ══ 區塊的變數
#    2. 修改 ══ SECRETS ══ 區塊的 API Keys
#    3. 執行腳本
#
###############################################################################

set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════════
# 確保從專案根目錄執行 (Anchor to repo root so build paths resolve regardless of CWD)
# This script lives in gcp/, so the repo root is its parent directory.
# ═══════════════════════════════════════════════════════════════════════════════
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG — 請修改這裡 (Modify these values)
# ═══════════════════════════════════════════════════════════════════════════════

PROJECT_ID="${PROJECT_ID:-vidgo-ai}"           # <-- 你的 GCP 專案 ID
REGION="${REGION:-asia-east1}"                 # <-- 台灣區域
ZONE="${ZONE:-asia-east1-b}"                   # <-- 可用區域

# 命名
APP_NAME="vidgo"                               # <-- 所有資源的前綴
VPC_NAME="${APP_NAME}-vpc"
SUBNET_NAME="${APP_NAME}-subnet"
SQL_INSTANCE="prod-db"
BUCKET_NAME="${APP_NAME}-media-${PROJECT_ID}"
ARTIFACT_REPO="${APP_NAME}-images"

# Cloud Run 服務名稱 (backend only — frontend is on Firebase Hosting)
BACKEND_SERVICE="${APP_NAME}-backend"

# Cloud SQL 設定
DB_NAME="vidgo"
DB_USER="postgres"
DB_PASSWORD="${DB_PASSWORD:-Vidgo96003146}"    # <-- !! 務必修改 / 用環境變數覆蓋 !!
DB_TIER="db-g1-small"                          # Phase 1; Phase 2 改 db-n1-standard-2
DB_STORAGE="10GB"

# Cloud Run 資源設定 (Phase 1: 0-500 users)
# 2026-06 cost pass: memory 2Gi → 1Gi. Backend uses request-based CPU
# (no --no-cpu-throttling) so idle instances are cheap; min=1 keeps one warm.
BACKEND_MIN_INSTANCES=1
BACKEND_MAX_INSTANCES=10
BACKEND_MEMORY="1Gi"
BACKEND_CPU=1

# 預算告警 (USD)
BUDGET_AMOUNT=300

# Firebase Hosting (frontend). NOTE: the frontend lives in a SEPARATE Firebase
# project from the GCP backend project — frontend-vue/.firebaserc default is
# `vidgo-gen-ai-prod`, while the backend GCP project is `vidgo-ai`. Override
# via FIREBASE_PROJECT if your .firebaserc differs.
FIREBASE_PROJECT="${FIREBASE_PROJECT:-vidgo-gen-ai-prod}"

# Custom Domain (vidgo.co)
CUSTOM_DOMAIN_BACKEND="api.vidgo.co"
CUSTOM_DOMAIN_FRONTEND="vidgo.co"
CUSTOM_DOMAIN_FRONTEND_WWW="www.vidgo.co"

# ── GCP Billing export (admin Cost dashboard: real weekly GCP spend) ──────────
# Enable Billing → "Standard usage cost" export to BigQuery, then set the
# fully-qualified table id here. Empty = the dashboard falls back to the
# GCP_*_BUDGET_USD env estimates. The backend SA gets bigquery.dataViewer +
# jobUser in STEP iam.
GCP_BILLING_BQ_TABLE="${GCP_BILLING_BQ_TABLE:-}"   # e.g. vidgo-ai.billing_export.gcp_billing_export_v1_0123AB_CDEF
GCP_BILLING_PROJECT="${GCP_BILLING_PROJECT:-${PROJECT_ID}}"

# ═══════════════════════════════════════════════════════════════════════════════
# SECRETS — loaded from shell environment or CI/CD secret variables.
# Empty values are skipped so existing Secret Manager versions remain intact.
# ═══════════════════════════════════════════════════════════════════════════════

SECRET_KEY="${SECRET_KEY:-}"
PIAPI_KEY="${PIAPI_KEY:-}"
GEMINI_API_KEY="${GEMINI_API_KEY:-}"
POLLO_API_KEY="${POLLO_API_KEY:-}"
A2E_API_KEY="${A2E_API_KEY:-}"
A2E_API_ID="${A2E_API_ID:-}"
A2E_DEFAULT_CREATOR_ID="${A2E_DEFAULT_CREATOR_ID:-}"
# SMTP for Cloud Run should come from deploy-time environment variables or
# pre-existing Secret Manager entries, not hardcoded local credentials.
SMTP_HOST="${SMTP_HOST:-}"
SMTP_PORT="${SMTP_PORT:-587}"
SMTP_USER="${SMTP_USER:-}"
SMTP_PASSWORD="${SMTP_PASSWORD:-}"
SMTP_FROM_EMAIL="${SMTP_FROM_EMAIL:-noreply@vidgo.co}"
SMTP_FROM_NAME="${SMTP_FROM_NAME:-VidGo}"
SMTP_SSL="${SMTP_SSL:-false}"
SMTP_TIMEOUT_SECONDS="${SMTP_TIMEOUT_SECONDS:-15}"

# Paddle removed 2026-05-31 — payments use ECPay (zh-TW) and PayPal (else).

# PayPal (International Payment)
PAYPAL_ENV="${PAYPAL_ENV:-production}"
PAYPAL_CLIENT_ID="${PAYPAL_CLIENT_ID:-}"
PAYPAL_CLIENT_SECRET="${PAYPAL_CLIENT_SECRET:-}"
PAYPAL_WEBHOOK_ID="${PAYPAL_WEBHOOK_ID:-}"
PAYPAL_WEBHOOK_SECRET="${PAYPAL_WEBHOOK_SECRET:-}"
PAYPAL_PLAN_IDS="${PAYPAL_PLAN_IDS:-}"

# ECPay Payment (Taiwan) — outbound calls must exit via the static NAT IP (whitelisted)
ECPAY_ENV=production
ECPAY_MERCHANT_ID="${ECPAY_MERCHANT_ID:-}"
ECPAY_HASH_KEY="${ECPAY_HASH_KEY:-}"
ECPAY_HASH_IV="${ECPAY_HASH_IV:-}"            # <-- 你的 ECPay HashIV

# Giveme E-Invoice — outbound calls must exit via the static NAT IP (whitelisted)
GIVEME_IDNO="${GIVEME_IDNO:-}"
GIVEME_PASSWORD="${GIVEME_PASSWORD:-}"          # <-- 你的 Giveme API 密碼

# Social Media OAuth (Facebook / Instagram / TikTok / YouTube)
FACEBOOK_APP_ID="${FACEBOOK_APP_ID:-}"       # <-- https://developers.facebook.com/
FACEBOOK_APP_SECRET="${FACEBOOK_APP_SECRET:-}"
TIKTOK_CLIENT_KEY="${TIKTOK_CLIENT_KEY:-}"   # <-- https://developers.tiktok.com/
TIKTOK_CLIENT_SECRET="${TIKTOK_CLIENT_SECRET:-}"
YOUTUBE_CLIENT_ID="${YOUTUBE_CLIENT_ID:-}"   # <-- https://console.cloud.google.com/
YOUTUBE_CLIENT_SECRET="${YOUTUBE_CLIENT_SECRET:-}"

# ═══════════════════════════════════════════════════════════════════════════════
# 以下不需修改 (Do not modify below unless you know what you're doing)
# ═══════════════════════════════════════════════════════════════════════════════

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }
step() { echo -e "\n${CYAN}${BOLD}═══════════════════════════════════════════════════════${NC}"; echo -e "${CYAN}${BOLD}  STEP $1: $2${NC}"; echo -e "${CYAN}${BOLD}═══════════════════════════════════════════════════════${NC}"; }

# Parse args
RUN_STEP=""
RUN_FROM=1
while [[ $# -gt 0 ]]; do
  case $1 in
    --step) RUN_STEP="$2"; shift 2 ;;
    --from) RUN_FROM="$2"; shift 2 ;;
    *) shift ;;
  esac
done

should_run() {
  local step_num=$1
  local step_name=$2
  if [[ -n "$RUN_STEP" ]]; then
    [[ "$RUN_STEP" == "$step_num" || "$RUN_STEP" == "$step_name" ]]
  else
    [[ "$step_num" -ge "$RUN_FROM" ]]
  fi
}

echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║         VidGo GCP Production Deployment  (v2.0)         ║"
echo "║         Project:  ${PROJECT_ID}                              ║"
echo "║         Region:   ${REGION}                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

###############################################################################
# STEP 1: Enable APIs
###############################################################################
if should_run 1 "apis"; then
  step 1 "啟用 GCP APIs"

  gcloud config set project "${PROJECT_ID}" 2>/dev/null

  APIS=(
    run.googleapis.com
    sqladmin.googleapis.com
    compute.googleapis.com
    artifactregistry.googleapis.com
    cloudbuild.googleapis.com
    secretmanager.googleapis.com
    cloudresourcemanager.googleapis.com
    monitoring.googleapis.com
    logging.googleapis.com
    servicenetworking.googleapis.com
    aiplatform.googleapis.com
    bigquery.googleapis.com
    cloudscheduler.googleapis.com
  )

  for api in "${APIS[@]}"; do
    gcloud services enable "$api" --project="${PROJECT_ID}" 2>/dev/null && \
      log "Enabled $api" || warn "$api already enabled"
  done
fi

###############################################################################
# STEP 2: VPC + Subnet + Private Service Connection + Static NAT
#
# No Serverless VPC Connector — Cloud Run uses Direct VPC egress (--network /
# --subnet on the service in STEP deploy), which is cheaper (~$10-15/mo saved)
# and has no min-2-instance connector floor. The static NAT IP is KEPT because
# outbound calls to Giveme + ECPay must exit from a whitelisted IP.
###############################################################################
if should_run 2 "vpc"; then
  step 2 "建立 VPC 網路 / Subnet / Private Service / Static NAT"

  # VPC
  gcloud compute networks create "${VPC_NAME}" \
    --project="${PROJECT_ID}" \
    --subnet-mode=custom \
    2>/dev/null && log "VPC created" || warn "VPC already exists"

  # Subnet
  gcloud compute networks subnets create "${SUBNET_NAME}" \
    --project="${PROJECT_ID}" \
    --network="${VPC_NAME}" \
    --region="${REGION}" \
    --range="10.0.1.0/24" \
    2>/dev/null && log "Subnet created" || warn "Subnet already exists"

  # Private Service Connection (for private-IP Cloud SQL)
  gcloud compute addresses create google-managed-services-${VPC_NAME} \
    --global \
    --purpose=VPC_PEERING \
    --prefix-length=16 \
    --network="${VPC_NAME}" \
    --project="${PROJECT_ID}" \
    2>/dev/null && log "Private IP range allocated" || warn "Private IP range already exists"

  gcloud services vpc-peerings connect \
    --service=servicenetworking.googleapis.com \
    --ranges=google-managed-services-${VPC_NAME} \
    --network="${VPC_NAME}" \
    --project="${PROJECT_ID}" \
    2>/dev/null && log "VPC peering created" || warn "VPC peering already exists"

  # Cloud Router + NAT with a STATIC IP.
  # The static IP is REQUIRED: Giveme (e-invoice) and ECPay enforce an outbound
  # IP whitelist, and the Cloud Run backend deploys with --vpc-egress=all-traffic
  # so those calls leave via this IP. Do NOT switch the backend to
  # private-ranges-only or those payment/invoice calls will be rejected.
  gcloud compute routers create "${APP_NAME}-router" \
    --project="${PROJECT_ID}" \
    --network="${VPC_NAME}" \
    --region="${REGION}" \
    2>/dev/null && log "Router created" || warn "Router already exists"

  gcloud compute addresses create "${APP_NAME}-nat-ip" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --description="VidGo NAT static IP for Giveme/ECPay whitelist" \
    2>/dev/null && log "Static NAT IP created" || warn "Static NAT IP already exists"

  NAT_IP=$(gcloud compute addresses describe "${APP_NAME}-nat-ip" \
    --project="${PROJECT_ID}" --region="${REGION}" \
    --format='value(address)' 2>/dev/null || echo "PENDING")
  log "NAT Static IP: ${NAT_IP}  ← 請將此 IP 加入 Giveme 白名單 & ECPay 允許 IP"

  NAT_IP_SELF_LINK=$(gcloud compute addresses describe "${APP_NAME}-nat-ip" \
    --project="${PROJECT_ID}" --region="${REGION}" \
    --format='value(selfLink)' 2>/dev/null)

  gcloud compute routers nats create "${APP_NAME}-nat" \
    --project="${PROJECT_ID}" \
    --router="${APP_NAME}-router" \
    --region="${REGION}" \
    --nat-external-ip-pool="${NAT_IP_SELF_LINK}" \
    --nat-all-subnet-ip-ranges \
    2>/dev/null && log "NAT created with static IP" || warn "NAT already exists"
fi

###############################################################################
# STEP 3: Artifact Registry
###############################################################################
if should_run 3 "registry"; then
  step 3 "建立 Artifact Registry (Docker Image 存放)"

  gcloud artifacts repositories create "${ARTIFACT_REPO}" \
    --project="${PROJECT_ID}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="VidGo Docker images" \
    2>/dev/null && log "Artifact Registry created" || warn "Already exists"
fi

###############################################################################
# STEP 4: Cloud SQL (PostgreSQL 15)
###############################################################################
if should_run 4 "sql"; then
  step 4 "建立 Cloud SQL (PostgreSQL 15)"

  if [[ "$DB_PASSWORD" == "CHANGE_ME_TO_A_STRONG_PASSWORD" ]]; then
    err "請先修改 DB_PASSWORD！(CONFIG 區塊) 或用環境變數覆蓋"
    exit 1
  fi

  gcloud sql instances create "${SQL_INSTANCE}" \
    --project="${PROJECT_ID}" \
    --database-version=POSTGRES_15 \
    --tier="${DB_TIER}" \
    --region="${REGION}" \
    --network="${VPC_NAME}" \
    --no-assign-ip \
    --storage-type=SSD \
    --storage-size="${DB_STORAGE}" \
    --storage-auto-increase \
    --backup-start-time="03:00" \
    --maintenance-window-day=SUN \
    --maintenance-window-hour=4 \
    --database-flags="max_connections=100" \
    2>/dev/null && log "Cloud SQL instance created (takes ~5 min)" || warn "Instance already exists"

  # Create database
  gcloud sql databases create "${DB_NAME}" \
    --project="${PROJECT_ID}" \
    --instance="${SQL_INSTANCE}" \
    2>/dev/null && log "Database '${DB_NAME}' created" || warn "Database already exists"

  # Set password
  gcloud sql users set-password "${DB_USER}" \
    --instance="${SQL_INSTANCE}" \
    --project="${PROJECT_ID}" \
    --password="${DB_PASSWORD}" \
    && log "Password set for user '${DB_USER}'" || err "Failed to set password"

  # Get private IP
  SQL_IP=$(gcloud sql instances describe "${SQL_INSTANCE}" \
    --project="${PROJECT_ID}" \
    --format='value(ipAddresses[0].ipAddress)' 2>/dev/null || echo "PENDING")
  log "Cloud SQL Private IP: ${SQL_IP}"
fi

###############################################################################
# STEP 5: Cloud Storage + Lifecycle Policy
###############################################################################
if should_run 5 "storage"; then
  step 5 "建立 Cloud Storage + Lifecycle 政策"

  gsutil mb -p "${PROJECT_ID}" -l "${REGION}" -c STANDARD \
    "gs://${BUCKET_NAME}" \
    2>/dev/null && log "Bucket created" || warn "Bucket already exists"

  # Apply lifecycle: generated/ 14天刪, uploads/ 30天刪, materials/ 7天→Nearline
  gsutil lifecycle set gcp/storage-lifecycle.json "gs://${BUCKET_NAME}" \
    && log "Lifecycle policy applied" || err "Failed to apply lifecycle"

  # CORS for frontend
  cat > /tmp/vidgo-cors.json << 'CORS_EOF'
[
  {
    "origin": ["*"],
    "method": ["GET", "PUT", "POST"],
    "responseHeader": ["Content-Type", "Authorization"],
    "maxAgeSeconds": 3600
  }
]
CORS_EOF
  gsutil cors set /tmp/vidgo-cors.json "gs://${BUCKET_NAME}" \
    && log "CORS policy applied" || warn "CORS failed"
fi

###############################################################################
# STEP 6: Service Account + IAM
#
# One backend service account. (Worker + frontend SAs removed — worker is gone
# and the frontend is a static SPA on Firebase Hosting with no SA.) bigquery.*
# roles let the admin Cost dashboard read the billing export.
###############################################################################
if should_run 6 "iam"; then
  step 6 "建立 Service Account + IAM 權限"

  gcloud iam service-accounts create "${BACKEND_SERVICE}" \
    --project="${PROJECT_ID}" \
    --display-name="VidGo ${BACKEND_SERVICE}" \
    2>/dev/null && log "SA '${BACKEND_SERVICE}' created" || warn "SA already exists"

  SA_EMAIL="${BACKEND_SERVICE}@${PROJECT_ID}.iam.gserviceaccount.com"
  for ROLE in \
    roles/cloudsql.client \
    roles/storage.objectAdmin \
    roles/secretmanager.secretAccessor \
    roles/run.invoker \
    roles/aiplatform.user \
    roles/bigquery.dataViewer \
    roles/bigquery.jobUser; do
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
      --member="serviceAccount:${SA_EMAIL}" \
      --role="${ROLE}" \
      --quiet 2>/dev/null
  done
  log "IAM roles granted to ${BACKEND_SERVICE} (incl. BigQuery billing read)"
fi

###############################################################################
# STEP 7: Secret Manager (存放所有 API Keys)
###############################################################################
if should_run 7 "secrets"; then
  step 7 "存放 Secrets 到 Secret Manager"

  # Get Cloud SQL private IP for the connection string
  SQL_IP=$(gcloud sql instances describe "${SQL_INSTANCE}" \
    --project="${PROJECT_ID}" \
    --format='value(ipAddresses[0].ipAddress)' 2>/dev/null)
  if [ -z "$SQL_IP" ] || [ "$SQL_IP" = "PENDING" ]; then
    err "Cloud SQL IP not ready! Wait a few minutes and retry."
    exit 1
  fi

  DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${SQL_IP}:5432/${DB_NAME}"

  # Number of historical secret versions to keep per secret. Each stored version
  # incurs ongoing "Secret version replica storage" billing, so we prune.
  : "${SECRET_VERSIONS_TO_KEEP:=2}"

  # Helper function: create or update secret + prune stale versions
  put_secret() {
    local name=$1
    local value=$2
    if [ -z "$value" ]; then
      warn "Skipping empty secret: $name"
      return 0
    fi
    if gcloud secrets describe "$name" --project="${PROJECT_ID}" &>/dev/null; then
      echo -n "$value" | gcloud secrets versions add "$name" --data-file=- --project="${PROJECT_ID}" &>/dev/null
      log "Updated secret: $name"
    else
      echo -n "$value" | gcloud secrets create "$name" --data-file=- --project="${PROJECT_ID}" \
        --replication-policy="user-managed" --locations="${REGION}" &>/dev/null
      log "Created secret: $name"
    fi
    local stale_versions
    stale_versions=$(gcloud secrets versions list "$name" \
      --project="${PROJECT_ID}" \
      --filter="state=ENABLED OR state=DISABLED" \
      --sort-by=~createTime \
      --format='value(name)' 2>/dev/null \
      | tail -n +"$((SECRET_VERSIONS_TO_KEEP + 1))" || true)
    if [ -n "$stale_versions" ]; then
      while IFS= read -r v; do
        [ -z "$v" ] && continue
        gcloud secrets versions destroy "$v" \
          --secret="$name" --project="${PROJECT_ID}" --quiet &>/dev/null || true
      done <<< "$stale_versions"
      log "Pruned old versions of secret: $name (kept latest ${SECRET_VERSIONS_TO_KEEP})"
    fi
  }

  put_secret "DATABASE_URL"          "$DATABASE_URL"
  put_secret "SECRET_KEY"            "$SECRET_KEY"
  put_secret "PIAPI_KEY"             "$PIAPI_KEY"
  put_secret "GEMINI_API_KEY"        "$GEMINI_API_KEY"
  put_secret "POLLO_API_KEY"         "$POLLO_API_KEY"
  put_secret "A2E_API_KEY"           "$A2E_API_KEY"
  put_secret "A2E_API_ID"            "$A2E_API_ID"
  put_secret "A2E_DEFAULT_CREATOR_ID" "$A2E_DEFAULT_CREATOR_ID"
  put_secret "PAYPAL_CLIENT_ID"      "$PAYPAL_CLIENT_ID"
  put_secret "PAYPAL_CLIENT_SECRET"  "$PAYPAL_CLIENT_SECRET"
  put_secret "PAYPAL_WEBHOOK_ID"     "$PAYPAL_WEBHOOK_ID"
  put_secret "PAYPAL_WEBHOOK_SECRET" "$PAYPAL_WEBHOOK_SECRET"
  put_secret "PAYPAL_PLAN_IDS"       "$PAYPAL_PLAN_IDS"
  put_secret "SMTP_HOST"             "$SMTP_HOST"
  put_secret "SMTP_PORT"             "$SMTP_PORT"
  put_secret "SMTP_USER"             "$SMTP_USER"
  put_secret "SMTP_PASSWORD"         "$SMTP_PASSWORD"
  put_secret "ECPAY_MERCHANT_ID"     "$ECPAY_MERCHANT_ID"
  put_secret "ECPAY_HASH_KEY"        "$ECPAY_HASH_KEY"
  put_secret "ECPAY_HASH_IV"         "$ECPAY_HASH_IV"
  put_secret "GIVEME_IDNO"           "$GIVEME_IDNO"
  put_secret "GIVEME_PASSWORD"       "$GIVEME_PASSWORD"
  put_secret "FACEBOOK_APP_ID"      "$FACEBOOK_APP_ID"
  put_secret "FACEBOOK_APP_SECRET"  "$FACEBOOK_APP_SECRET"
  put_secret "TIKTOK_CLIENT_KEY"    "$TIKTOK_CLIENT_KEY"
  put_secret "TIKTOK_CLIENT_SECRET" "$TIKTOK_CLIENT_SECRET"
  put_secret "YOUTUBE_CLIENT_ID"    "$YOUTUBE_CLIENT_ID"
  put_secret "YOUTUBE_CLIENT_SECRET" "$YOUTUBE_CLIENT_SECRET"

  log "All secrets stored."
  warn "DATABASE_URL = ${DATABASE_URL}"
fi

###############################################################################
# STEP 75: Secret Manager — prune stale versions (cost optimization)
#
#   bash gcp/deploy.sh --step secret_cleanup
#   SECRET_VERSIONS_TO_KEEP=1 bash gcp/deploy.sh --step secret_cleanup
###############################################################################
if should_run 75 "secret_cleanup"; then
  step 75 "Prune stale Secret Manager versions (keep latest ${SECRET_VERSIONS_TO_KEEP:-2})"

  : "${SECRET_VERSIONS_TO_KEEP:=2}"
  pruned_total=0

  while IFS= read -r secret_name; do
    [ -z "$secret_name" ] && continue
    stale=$(gcloud secrets versions list "$secret_name" \
      --project="${PROJECT_ID}" \
      --filter="state=ENABLED OR state=DISABLED" \
      --sort-by=~createTime \
      --format='value(name)' 2>/dev/null \
      | tail -n +"$((SECRET_VERSIONS_TO_KEEP + 1))" || true)
    if [ -z "$stale" ]; then
      continue
    fi
    count=0
    while IFS= read -r v; do
      [ -z "$v" ] && continue
      gcloud secrets versions destroy "$v" \
        --secret="$secret_name" --project="${PROJECT_ID}" --quiet &>/dev/null \
        && count=$((count + 1)) || true
    done <<< "$stale"
    if [ "$count" -gt 0 ]; then
      log "Pruned ${count} stale version(s) of ${secret_name}"
      pruned_total=$((pruned_total + count))
    fi
  done < <(gcloud secrets list --project="${PROJECT_ID}" --format='value(name)' 2>/dev/null)

  log "Secret cleanup complete: ${pruned_total} versions destroyed."
fi

###############################################################################
# STEP 8: Build & Push Backend Image
#
# Backend only — the frontend is built + deployed to Firebase Hosting in the
# `frontend` step, not as a Docker image. (CI/CD via cloudbuild.yaml builds the
# same backend image on push to main; this step is for manual/first deploys.)
###############################################################################
if should_run 8 "build"; then
  step 8 "Build & Push Backend Image"

  IMAGE_TAG=$(date +%Y%m%d-%H%M%S)
  BACKEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/${BACKEND_SERVICE}"

  gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

  log "Building backend image..."
  docker build \
    -t "${BACKEND_IMAGE}:${IMAGE_TAG}" \
    -t "${BACKEND_IMAGE}:latest" \
    -f backend/Dockerfile \
    .

  log "Pushing image..."
  docker push "${BACKEND_IMAGE}:${IMAGE_TAG}"
  docker push "${BACKEND_IMAGE}:latest"

  log "Image pushed: tag=${IMAGE_TAG}"
  echo "${IMAGE_TAG}" > /tmp/vidgo-image-tag
fi

###############################################################################
# STEP 9: Deploy Backend to Cloud Run (Direct VPC egress)
###############################################################################
if should_run 9 "deploy"; then
  step 9 "部署 Backend 到 Cloud Run"

  IMAGE_TAG=$(cat /tmp/vidgo-image-tag 2>/dev/null || echo "latest")
  BACKEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/${BACKEND_SERVICE}:${IMAGE_TAG}"
  SQL_CONNECTION="${PROJECT_ID}:${REGION}:${SQL_INSTANCE}"

  _BACKEND_URL="https://${CUSTOM_DOMAIN_BACKEND}"
  _FRONTEND_URL="https://${CUSTOM_DOMAIN_FRONTEND}"
  log "BACKEND_URL  = ${_BACKEND_URL}"
  log "FRONTEND_URL = ${_FRONTEND_URL}"

  # Non-secret env vars
  COMMON_ENV="SKIP_PREGENERATION=true,SKIP_DEPENDENCY_CHECK=true,DEBUG=false,ALGORITHM=HS256,ACCESS_TOKEN_EXPIRE_MINUTES=30,REFRESH_TOKEN_EXPIRE_DAYS=7,ECPAY_ENV=production,ECPAY_PAYMENT_URL=https://payment.ecpay.com.tw/Cashier/AioCheckOut/V2,GIVEME_ENABLED=true,GIVEME_BASE_URL=https://www.giveme.com.tw/invoice.do,GIVEME_UNCODE=96003146,FRONTEND_URL=${_FRONTEND_URL},BACKEND_URL=${_BACKEND_URL},PUBLIC_APP_URL=${_BACKEND_URL},CORS_ALLOW_ALL=true,PAYPAL_ENV=${PAYPAL_ENV},SMTP_FROM_EMAIL=${SMTP_FROM_EMAIL},SMTP_FROM_NAME=${SMTP_FROM_NAME},SMTP_TLS=${SMTP_TLS:-true},SMTP_SSL=${SMTP_SSL:-false},SMTP_TIMEOUT_SECONDS=${SMTP_TIMEOUT_SECONDS:-15},GCS_BUCKET=${BUCKET_NAME},VERTEX_AI_PROJECT=${PROJECT_ID},VERTEX_AI_LOCATION=${REGION},VEO_MODEL=veo-3.0-fast-generate-001,GEMINI_MODEL=gemini-2.5-flash,GEMINI_IMAGE_MODEL=gemini-2.5-flash-image,PIAPI_MCP_ENABLED=true"

  # BigQuery billing export → admin Cost dashboard (only when configured)
  if [ -n "${GCP_BILLING_BQ_TABLE}" ]; then
    COMMON_ENV+=",GCP_BILLING_BQ_TABLE=${GCP_BILLING_BQ_TABLE},GCP_BILLING_PROJECT=${GCP_BILLING_PROJECT}"
  fi

  # Secret env vars (reference from Secret Manager). No REDIS_URL (Redis removed).
  SECRET_ENV="DATABASE_URL=DATABASE_URL:latest,SECRET_KEY=SECRET_KEY:latest,PIAPI_KEY=PIAPI_KEY:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest,POLLO_API_KEY=POLLO_API_KEY:latest,A2E_API_KEY=A2E_API_KEY:latest,A2E_API_ID=A2E_API_ID:latest,A2E_DEFAULT_CREATOR_ID=A2E_DEFAULT_CREATOR_ID:latest,SMTP_HOST=SMTP_HOST:latest,SMTP_PORT=SMTP_PORT:latest,SMTP_USER=SMTP_USER:latest,SMTP_PASSWORD=SMTP_PASSWORD:latest,ECPAY_MERCHANT_ID=ECPAY_MERCHANT_ID:latest,ECPAY_HASH_KEY=ECPAY_HASH_KEY:latest,ECPAY_HASH_IV=ECPAY_HASH_IV:latest,GIVEME_IDNO=GIVEME_IDNO:latest,GIVEME_PASSWORD=GIVEME_PASSWORD:latest"

  append_optional_secret_ref() {
    local name=$1
    local value=$2
    if [ -n "$value" ]; then
      SECRET_ENV+=",${name}=${name}:latest"
    fi
  }

  append_optional_secret_ref "PAYPAL_CLIENT_ID" "$PAYPAL_CLIENT_ID"
  append_optional_secret_ref "PAYPAL_CLIENT_SECRET" "$PAYPAL_CLIENT_SECRET"
  append_optional_secret_ref "PAYPAL_WEBHOOK_ID" "$PAYPAL_WEBHOOK_ID"
  append_optional_secret_ref "PAYPAL_WEBHOOK_SECRET" "$PAYPAL_WEBHOOK_SECRET"
  append_optional_secret_ref "PAYPAL_PLAN_IDS" "$PAYPAL_PLAN_IDS"
  append_optional_secret_ref "FACEBOOK_APP_ID" "$FACEBOOK_APP_ID"
  append_optional_secret_ref "FACEBOOK_APP_SECRET" "$FACEBOOK_APP_SECRET"
  append_optional_secret_ref "TIKTOK_CLIENT_KEY" "$TIKTOK_CLIENT_KEY"
  append_optional_secret_ref "TIKTOK_CLIENT_SECRET" "$TIKTOK_CLIENT_SECRET"
  append_optional_secret_ref "YOUTUBE_CLIENT_ID" "$YOUTUBE_CLIENT_ID"
  append_optional_secret_ref "YOUTUBE_CLIENT_SECRET" "$YOUTUBE_CLIENT_SECRET"

  log "Deploying backend..."
  gcloud run deploy "${BACKEND_SERVICE}" \
    --image="${BACKEND_IMAGE}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --platform=managed \
    --min-instances="${BACKEND_MIN_INSTANCES}" \
    --max-instances="${BACKEND_MAX_INSTANCES}" \
    --memory="${BACKEND_MEMORY}" \
    --cpu="${BACKEND_CPU}" \
    --port=8000 \
    --timeout=3600 \
    `# 3600s is Cloud Run's ceiling — avatar / Kling Omni / Veo endpoints poll` \
    `# the upstream provider up to ~50 min. Keep strictly > every poll ceiling.` \
    --network="${VPC_NAME}" \
    --subnet="${SUBNET_NAME}" \
    --vpc-egress=all-traffic \
    `# all-traffic + static NAT IP: Giveme/ECPay outbound must come from the` \
    `# whitelisted IP. Direct VPC egress (no connector) keeps the cost down.` \
    --add-cloudsql-instances="${SQL_CONNECTION}" \
    --service-account="${BACKEND_SERVICE}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --set-env-vars="${COMMON_ENV}" \
    --set-secrets="${SECRET_ENV}" \
    --cpu-boost \
    --allow-unauthenticated
  log "Backend deployed"

  BACKEND_URL=$(gcloud run services describe "${BACKEND_SERVICE}" \
    --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')
  log "Backend URL:  ${BACKEND_URL}"
fi

###############################################################################
# STEP 10: Deploy Frontend to Firebase Hosting (global CDN)
#
# The Vue SPA is served by Firebase Hosting, not Cloud Run — global edge CDN,
# better TTFB worldwide, cheaper. Requires the firebase CLI and frontend-vue/
# firebase.json + .firebaserc (already in the repo).
###############################################################################
if should_run 10 "frontend"; then
  step 10 "Build & Deploy 前端到 Firebase Hosting"

  if ! command -v firebase >/dev/null 2>&1; then
    warn "firebase CLI not found. Install with: npm i -g firebase-tools && firebase login"
    warn "Then re-run: bash gcp/deploy.sh --step frontend"
  else
    (
      cd frontend-vue
      log "Installing frontend deps..."
      npm ci 2>/dev/null || npm install
      log "Building frontend (vite)..."
      npm run build
      log "Deploying to Firebase Hosting (project ${FIREBASE_PROJECT})..."
      firebase deploy --only hosting --project "${FIREBASE_PROJECT}"
    ) && log "Frontend deployed to Firebase Hosting" \
      || warn "Firebase deploy failed — check 'firebase login' and frontend-vue/.firebaserc"
  fi
fi

###############################################################################
# STEP 11: Custom Domain Mapping
#
# Backend api.vidgo.co → Cloud Run domain mapping (below).
# Frontend vidgo.co / www → set as a custom domain in the Firebase Hosting
# console (Hosting → Add custom domain), NOT via Cloud Run.
###############################################################################
if should_run 11 "domain"; then
  step 11 "設定 Custom Domain"

  warn "Backend: 確認 GoDaddy DNS 有 CNAME ${CUSTOM_DOMAIN_BACKEND} → ghs.googlehosted.com"
  warn "Frontend: 在 Firebase Hosting 控制台 → Add custom domain 設定 ${CUSTOM_DOMAIN_FRONTEND} / ${CUSTOM_DOMAIN_FRONTEND_WWW}"

  # Map api.vidgo.co → backend (Cloud Run)
  gcloud beta run domain-mappings create \
    --service="${BACKEND_SERVICE}" \
    --domain="${CUSTOM_DOMAIN_BACKEND}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    2>/dev/null && log "Domain mapped: ${CUSTOM_DOMAIN_BACKEND} → ${BACKEND_SERVICE}" \
    || warn "Domain mapping for ${CUSTOM_DOMAIN_BACKEND} already exists"

  echo ""
  warn "Backend DNS (GoDaddy):"
  echo "  ┌──────────┬──────────────────────┬─────────────────────────┐"
  echo "  │ Type     │ Name                 │ Value                   │"
  echo "  ├──────────┼──────────────────────┼─────────────────────────┤"
  echo "  │ CNAME    │ api                  │ ghs.googlehosted.com    │"
  echo "  └──────────┴──────────────────────┴─────────────────────────┘"
  warn "Frontend DNS records are shown by Firebase when you add the custom domain."
fi

###############################################################################
# STEP 12: Cloud Armor (WAF + Rate Limiting)
###############################################################################
if should_run 12 "armor"; then
  step 12 "建立 Cloud Armor 安全政策"

  POLICY_NAME="${APP_NAME}-security-policy"

  gcloud compute security-policies create "${POLICY_NAME}" \
    --project="${PROJECT_ID}" \
    --description="VidGo WAF and rate limiting" \
    2>/dev/null && log "Policy created" || warn "Policy already exists"

  # /auth/* rate limit: 100 req/min
  gcloud compute security-policies rules create 1000 \
    --project="${PROJECT_ID}" \
    --security-policy="${POLICY_NAME}" \
    --expression="request.path.matches('/auth/.*') || request.path.matches('/api/v1/auth/.*')" \
    --action=rate-based-ban \
    --rate-limit-threshold-count=100 \
    --rate-limit-threshold-interval-sec=60 \
    --ban-duration-sec=300 \
    --conform-action=allow \
    --exceed-action=deny-429 \
    --enforce-on-key=IP \
    --description="Auth rate limit: 100/min" \
    2>/dev/null && log "Rule 1000: auth rate limit" || warn "Rule 1000 exists"

  # /generate/* rate limit: 50 req/min
  gcloud compute security-policies rules create 2000 \
    --project="${PROJECT_ID}" \
    --security-policy="${POLICY_NAME}" \
    --expression="request.path.matches('/api/v1/generate/.*')" \
    --action=rate-based-ban \
    --rate-limit-threshold-count=50 \
    --rate-limit-threshold-interval-sec=60 \
    --ban-duration-sec=600 \
    --conform-action=allow \
    --exceed-action=deny-429 \
    --enforce-on-key=IP \
    --description="Generate rate limit: 50/min" \
    2>/dev/null && log "Rule 2000: generate rate limit" || warn "Rule 2000 exists"

  # /tools/* rate limit: 30 req/min
  gcloud compute security-policies rules create 3000 \
    --project="${PROJECT_ID}" \
    --security-policy="${POLICY_NAME}" \
    --expression="request.path.matches('/api/v1/tools/.*')" \
    --action=rate-based-ban \
    --rate-limit-threshold-count=30 \
    --rate-limit-threshold-interval-sec=60 \
    --ban-duration-sec=600 \
    --conform-action=allow \
    --exceed-action=deny-429 \
    --enforce-on-key=IP \
    --description="Tools rate limit: 30/min" \
    2>/dev/null && log "Rule 3000: tools rate limit" || warn "Rule 3000 exists"

  # SQLi + XSS protection
  gcloud compute security-policies rules create 4000 \
    --project="${PROJECT_ID}" \
    --security-policy="${POLICY_NAME}" \
    --expression="evaluatePreconfiguredExpr('sqli-v33-stable')" \
    --action=deny-403 \
    --description="Block SQLi" \
    2>/dev/null && log "Rule 4000: SQLi block" || warn "Rule 4000 exists"

  gcloud compute security-policies rules create 4100 \
    --project="${PROJECT_ID}" \
    --security-policy="${POLICY_NAME}" \
    --expression="evaluatePreconfiguredExpr('xss-v33-stable')" \
    --action=deny-403 \
    --description="Block XSS" \
    2>/dev/null && log "Rule 4100: XSS block" || warn "Rule 4100 exists"

  warn "Cloud Armor 需要 Load Balancer 才能啟用。設定 LB 後執行:"
  warn "  gcloud compute backend-services update <BACKEND_SERVICE> --security-policy=${POLICY_NAME} --global"
fi

###############################################################################
# STEP 13: Repair growth videos mis-stored as images in GCS (backfill)
#
# Rewrites Content-Type IN PLACE (URLs unchanged) for GCS objects whose bytes
# are really video but were stored with an image Content-Type. Best-effort.
###############################################################################
if should_run 13 "fixmedia"; then
  step 13 "修復 GCS 影片 Content-Type (growth video backfill)"

  IMAGE_TAG=$(cat /tmp/vidgo-image-tag 2>/dev/null || echo "latest")
  BACKEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/${BACKEND_SERVICE}:${IMAGE_TAG}"

  GCLOUD_CONFIG_DIR="${HOME}/.config/gcloud"
  if [[ ! -f "${GCLOUD_CONFIG_DIR}/application_default_credentials.json" ]]; then
    warn "No ADC found at ${GCLOUD_CONFIG_DIR}/application_default_credentials.json."
    warn "Run 'gcloud auth application-default login', then re-run: bash gcp/deploy.sh --step fixmedia"
  else
    log "Repairing growth-video Content-Type in gs://${BUCKET_NAME} ..."
    docker run --rm \
      -e GCS_BUCKET="${BUCKET_NAME}" \
      -e GOOGLE_CLOUD_PROJECT="${PROJECT_ID}" \
      -e CLOUDSDK_CORE_PROJECT="${PROJECT_ID}" \
      -v "${GCLOUD_CONFIG_DIR}:/root/.config/gcloud:ro" \
      --entrypoint python \
      "${BACKEND_IMAGE}" \
      scripts/fix_growth_video_content_type.py --apply \
      || warn "growth-video Content-Type backfill failed (non-fatal) — see output above."
  fi
fi

###############################################################################
# STEP 14: Final Summary
###############################################################################
if should_run 14 "summary"; then
  step 14 "部署完成總結"

  echo ""
  echo -e "${BOLD}━━━ 基礎設施 ━━━${NC}"
  echo "  Project:    ${PROJECT_ID}"
  echo "  Region:     ${REGION}"
  echo "  Domain:     ${CUSTOM_DOMAIN_FRONTEND} (Firebase) / ${CUSTOM_DOMAIN_BACKEND} (Cloud Run)"

  SQL_IP=$(gcloud sql instances describe "${SQL_INSTANCE}" \
    --project="${PROJECT_ID}" --format='value(ipAddresses[0].ipAddress)' 2>/dev/null || echo "N/A")
  echo "  Cloud SQL:  ${SQL_INSTANCE} (${SQL_IP})"

  NAT_IP=$(gcloud compute addresses describe "${APP_NAME}-nat-ip" \
    --project="${PROJECT_ID}" --region="${REGION}" \
    --format='value(address)' 2>/dev/null || echo "N/A")
  echo "  NAT IP:     ${NAT_IP}  (Giveme/ECPay 白名單用)"
  echo "  Bucket:     gs://${BUCKET_NAME}"

  echo ""
  echo -e "${BOLD}━━━ Cloud Run 服務 ━━━${NC}"
  BACKEND_URL=$(gcloud run services describe "${BACKEND_SERVICE}" \
    --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)' 2>/dev/null || echo "Not deployed")
  echo "  ${BACKEND_SERVICE}: ${BACKEND_URL}"
  echo "  frontend: Firebase Hosting (https://${CUSTOM_DOMAIN_FRONTEND})"

  echo ""
  echo -e "${BOLD}━━━ Payment & Invoice ━━━${NC}"
  echo "  ECPay:    production (MerchantID: ${ECPAY_MERCHANT_ID})"
  echo "  Giveme:   enabled (統一編號: 96003146)"
  echo "  PayPal:   ${PAYPAL_ENV}"

  echo ""
  echo -e "${BOLD}━━━ 待辦事項 ━━━${NC}"
  echo "  [ ] 將 NAT IP (${NAT_IP}) 加入 Giveme 白名單 & ECPay 允許 IP"
  echo "  [ ] Backend DNS: CNAME ${CUSTOM_DOMAIN_BACKEND} → ghs.googlehosted.com"
  echo "  [ ] Frontend: Firebase Hosting → Add custom domain ${CUSTOM_DOMAIN_FRONTEND}"
  echo "  [ ] ECPay 回調 URL: https://${CUSTOM_DOMAIN_BACKEND}/api/v1/payments/ecpay/callback"
  echo "  [ ] 測試: curl https://${CUSTOM_DOMAIN_BACKEND}/health"
  echo "  [ ] 設定 Budget Alert (\$${BUDGET_AMOUNT}): https://console.cloud.google.com/billing/budgets"
  echo "  [ ] 設定 Cloud Build Trigger (GitHub → main branch, cloudbuild.yaml)"
  echo "  [ ] 設定 Cloud Scheduler jobs → /api/v1/tasks/* (背景任務, with X-Tasks-Secret)"
  echo "  [ ] 啟用 Billing→BigQuery export, 設 GCP_BILLING_BQ_TABLE → admin Cost 儀表板顯示實際週費用"
  echo "  [ ] (穩定 ~3 月後) 購買 Cloud SQL Committed Use Discount (~37% off)"
  echo ""
  echo -e "${GREEN}${BOLD}Deployment complete!${NC}"
fi

# ═══════════════════════════════════════════════════════════════════════════
# POST-DEPLOY: visitor demo-example cache (T2I / T2V / AI Avatar)
#
# Runs AFTER the new revision is live (so the pregen Job pins the new image that
# carries the synced prompt_library.json + demo code). CHECKS the cache FIRST:
# if the demos are already populated it skips pregeneration entirely (no credits
# spent) — only when missing does it run `gcp/pregen.sh demos`, which is
# itself idempotent + cost-confirmed. So routine deploys never re-spend.
#
#   PREGEN_DEMOS=skip   → never run this hook
#   PREGEN_READY_MIN=N  → per-tool demo count considered "ready" (default 30)
#   PREGEN_FLAGS="..."  → flags passed to the runner (default: --full --yes)
# ═══════════════════════════════════════════════════════════════════════════
if [[ "${PREGEN_DEMOS:-auto}" != "skip" ]]; then
  step "POST" "Visitor demo cache (T2I / T2V / AI Avatar)"
  READY_MIN="${PREGEN_READY_MIN:-30}"
  _demo_count() {
    curl -fsS "https://${CUSTOM_DOMAIN_BACKEND}/api/v1/demo/presets/$1" 2>/dev/null \
      | python3 -c 'import sys,json;print(int(json.load(sys.stdin).get("count",0)))' 2>/dev/null || echo 0
  }
  T2I_N=$(_demo_count midjourney_imagine)
  T2V_N=$(_demo_count short_video)
  AV_N=$(_demo_count ai_avatar)
  log "Demo cache counts — t2i=${T2I_N}  t2v=${T2V_N}  avatar=${AV_N}  (ready when each ≥ ${READY_MIN})"
  if [[ "${T2I_N}" -ge "${READY_MIN}" && "${T2V_N}" -ge "${READY_MIN}" && "${AV_N}" -ge "${READY_MIN}" ]]; then
    log "Demo cache already populated — skipping pregeneration (no credits spent)."
  else
    warn "Demo cache not fully populated → running pregeneration (spends real credits, multi-hour)."
    PREGEN_FLAGS_DEFAULT="--full --yes"
    if bash "${SCRIPT_DIR}/pregen.sh" demos ${PREGEN_FLAGS:-${PREGEN_FLAGS_DEFAULT}}; then
      log "Demo-example pregeneration finished — visitor demos are live."
    else
      warn "Pregeneration job failed — re-run later: bash gcp/pregen.sh demos --full"
    fi
  fi
fi
