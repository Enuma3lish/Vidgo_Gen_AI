#!/bin/bash
###############################################################################
#                     VidGo GCP 完整部署腳本 (Full Deploy Script)
#                     Version: 1.0  |  Date: 2026-03
###############################################################################
#
#  Usage:
#    bash gcp/deploy.sh                       # 執行全部步驟
#    bash gcp/deploy.sh --step 3              # 只執行第 3 步
#    bash gcp/deploy.sh --from 5              # 從第 5 步開始
#    bash gcp/deploy.sh --step secrets        # 只執行 secrets 步驟
#
#  修改指南:
#    1. 修改下方 ══ CONFIG ══ 區塊的變數
#    2. 修改 ══ SECRETS ══ 區塊的 API Keys
#    3. 執行腳本
#
###############################################################################

set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG — 請修改這裡 (Modify these values)
# ═══════════════════════════════════════════════════════════════════════════════

PROJECT_ID="vidgo-ai"                       # <-- 你的 GCP 專案 ID
REGION="asia-east1"                         # <-- 台灣區域
ZONE="asia-east1-b"                         # <-- 可用區域

# 命名
APP_NAME="vidgo"                            # <-- 所有資源的前綴
VPC_NAME="${APP_NAME}-vpc"
SUBNET_NAME="${APP_NAME}-subnet"
CONNECTOR_NAME="${APP_NAME}-connector"
SQL_INSTANCE="prod-db"
REDIS_INSTANCE="${APP_NAME}-redis"
BUCKET_NAME="${APP_NAME}-media-${PROJECT_ID}"
ARTIFACT_REPO="${APP_NAME}-images"

# Cloud Run 服務名稱
BACKEND_SERVICE="${APP_NAME}-backend"
FRONTEND_SERVICE="${APP_NAME}-frontend"
WORKER_SERVICE="${APP_NAME}-worker"

# Cloud SQL 設定
DB_NAME="vidgo"
DB_USER="postgres"
DB_PASSWORD="Vidgo96003146"  # <-- !! 務必修改 !!
DB_TIER="db-g1-small"                         # Phase 1; Phase 2 改 db-n1-standard-2
DB_STORAGE="10GB"

# Redis 設定
REDIS_TIER="basic"                            # Phase 1; Phase 2 改 standard
REDIS_SIZE_GB=1                               # Phase 1; Phase 2 改 5

# Cloud Run 資源設定 (Phase 1: 0-500 users, ~$88-115/month)
BACKEND_MIN_INSTANCES=1
BACKEND_MAX_INSTANCES=10
BACKEND_MEMORY="1Gi"
BACKEND_CPU=1

FRONTEND_MIN_INSTANCES=0                      # Scale to Zero 省錢
FRONTEND_MAX_INSTANCES=4
FRONTEND_MEMORY="256Mi"
FRONTEND_CPU=1

WORKER_MIN_INSTANCES=1
WORKER_MAX_INSTANCES=3
WORKER_MEMORY="512Mi"
WORKER_CPU=1

# 預算告警 (USD)
BUDGET_AMOUNT=300

# Custom Domain (vidgo.co)
CUSTOM_DOMAIN_BACKEND="api.vidgo.co"
CUSTOM_DOMAIN_FRONTEND="vidgo.co"
CUSTOM_DOMAIN_FRONTEND_WWW="www.vidgo.co"

# ═══════════════════════════════════════════════════════════════════════════════
# SECRETS — API Keys (請替換成你的值)
# !! WARNING: 這些金鑰以明文儲存在此腳本中。請勿將此檔案推送到公開 repo !!
# !! 正式上線後建議改用 .env 檔案或 CI/CD secret variables !!
# ═══════════════════════════════════════════════════════════════════════════════

SECRET_KEY="9375626ad2099c8668dd80660f76cf1d5e20910664c21fdfac7c5c0dbd1cbf1d"
PIAPI_KEY="1deed395a2cddd29c0489d8c7b4ee511e777a6a95e7a463e3535326d44df3b30"
GEMINI_API_KEY="AIzaSyDiNxTyCHFGanH17J3W6g_p6jOkhixe4Ic"
POLLO_API_KEY="pollo_7f6ZiszaD2B3eXSpbLjuPj7rc7Ivc3GuzYiuODroyTYX"
A2E_API_KEY="sk_eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJfaWQiOiI2OTViMzMwNDExNTc2MzAwNWJjZmUyOTIiLCJuYW1lIjoidmlkZ28xNjhAZ21haWwuY29tIiwicm9sZSI6ImNvaW4iLCJpYXQiOjE3NjgxMjc4MTZ9.Hg7wZwlTg-RqTCdvnWr78d0sW_EvGLbFbXUh5ICpttw"
A2E_API_ID="695b3304115763005bcfe292"
A2E_DEFAULT_CREATOR_ID="693bf9bd3caab0848a4cd107"
SMTP_HOST="smtp.gmail.com"
SMTP_PORT="587"
SMTP_USER="vidago168@gmail.com"
SMTP_PASSWORD="mxff kwsh xgyn otew"

# Paddle (International Payment)
PADDLE_API_KEY="pdl_sdbx_apikey_01kedx5qy6zp7tjpkajd3yb9t5_Fczyp1QH0hnC2FW6vfkr4G_ABz"
PADDLE_PUBLIC_KEY=""                         # <-- 你的 Paddle Public Key (webhook verification)
PADDLE_WEBHOOK_SECRET=""                     # <-- 你的 Paddle Webhook Secret
PADDLE_ENV="sandbox"                         # <-- 上線改 "production"
PADDLE_PRICE_IDS=""                          # <-- JSON: '{"starter_monthly":"pri_xxx","pro_monthly":"pri_yyy"}'

# ECPay Payment (Taiwan)
ECPAY_ENV=production
ECPAY_MERCHANT_ID=3422044
ECPAY_HASH_KEY=fwNTpcFCaGaiOOt7
ECPAY_HASH_IV=Xv8pXkFk8zEGqv3T            # <-- 你的 ECPay HashIV

# Giveme E-Invoice
GIVEME_IDNO=qaz0978005418
GIVEME_PASSWORD=qaz129946858          # <-- 你的 Giveme API 密碼

# Social Media OAuth (Facebook / Instagram / TikTok / YouTube)
FACEBOOK_APP_ID=""                           # <-- https://developers.facebook.com/
FACEBOOK_APP_SECRET=""
TIKTOK_CLIENT_KEY=""                         # <-- https://developers.tiktok.com/
TIKTOK_CLIENT_SECRET=""
YOUTUBE_CLIENT_ID=""                         # <-- https://console.cloud.google.com/
YOUTUBE_CLIENT_SECRET=""

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
echo "║         VidGo GCP Production Deployment                 ║"
echo "║         Project:  ${PROJECT_ID}                              ║"
echo "║         Region:   ${REGION}                          ║"
echo "║         Cost Est: \$88–115 USD/month (Phase 1)           ║"
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
    redis.googleapis.com
    compute.googleapis.com
    artifactregistry.googleapis.com
    cloudbuild.googleapis.com
    secretmanager.googleapis.com
    vpcaccess.googleapis.com
    cloudresourcemanager.googleapis.com
    monitoring.googleapis.com
    logging.googleapis.com
    servicenetworking.googleapis.com
    aiplatform.googleapis.com
  )

  for api in "${APIS[@]}"; do
    gcloud services enable "$api" --project="${PROJECT_ID}" 2>/dev/null && \
      log "Enabled $api" || warn "$api already enabled"
  done
fi

###############################################################################
# STEP 2: VPC + Subnet + NAT + VPC Connector
###############################################################################
if should_run 2 "vpc"; then
  step 2 "建立 VPC 網路 / Subnet / NAT / Connector"

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

  # Private Service Connection (for Cloud SQL)
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

  # VPC Connector (Cloud Run → VPC)
  gcloud compute networks vpc-access connectors create "${CONNECTOR_NAME}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --network="${VPC_NAME}" \
    --range="10.8.0.0/28" \
    --min-instances=2 \
    --max-instances=3 \
    2>/dev/null && log "VPC Connector created" || warn "VPC Connector already exists"

  # Cloud Router + NAT (outbound to PiAPI / Gemini / etc.)
  gcloud compute routers create "${APP_NAME}-router" \
    --project="${PROJECT_ID}" \
    --network="${VPC_NAME}" \
    --region="${REGION}" \
    2>/dev/null && log "Router created" || warn "Router already exists"

  # Static IP for NAT (required for Giveme & ECPay IP whitelist)
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
  step 4 "刪除舊 & 建立新 Cloud SQL (PostgreSQL 15)"

  # Delete existing instances (vidgo-db, vidgo-db2) if they exist
  for OLD_INSTANCE in "vidgo-db" "vidgo-db2"; do
    if gcloud sql instances describe "$OLD_INSTANCE" --project="${PROJECT_ID}" &>/dev/null; then
      warn "Deleting old instance: $OLD_INSTANCE ..."
      gcloud sql instances delete "$OLD_INSTANCE" --project="${PROJECT_ID}" --quiet \
        && log "Deleted $OLD_INSTANCE" || warn "Failed to delete $OLD_INSTANCE (may be pending deletion)"
    fi
  done

  if [[ "$DB_PASSWORD" == "CHANGE_ME_TO_A_STRONG_PASSWORD" ]]; then
    err "請先修改 DB_PASSWORD！(line ~65 of this script)"
    err "目前密碼是預設值，不安全！"
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
# STEP 5: Memorystore Redis
###############################################################################
if should_run 5 "redis"; then
  step 5 "建立 Memorystore Redis"

  gcloud redis instances create "${REDIS_INSTANCE}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --tier="${REDIS_TIER}" \
    --size="${REDIS_SIZE_GB}" \
    --redis-version=redis_7_0 \
    --network="${VPC_NAME}" \
    2>/dev/null && log "Redis created (takes ~3 min)" || warn "Already exists"

  REDIS_IP=$(gcloud redis instances describe "${REDIS_INSTANCE}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --format='value(host)' 2>/dev/null || echo "PENDING")
  log "Redis IP: ${REDIS_IP}"
fi

###############################################################################
# STEP 6: Cloud Storage + Lifecycle Policy
###############################################################################
if should_run 6 "storage"; then
  step 6 "建立 Cloud Storage + Lifecycle 政策"

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
# STEP 7: Service Accounts + IAM
###############################################################################
if should_run 7 "iam"; then
  step 7 "建立 Service Accounts + IAM 權限"

  for SA in "${BACKEND_SERVICE}" "${WORKER_SERVICE}" "${FRONTEND_SERVICE}"; do
    gcloud iam service-accounts create "${SA}" \
      --project="${PROJECT_ID}" \
      --display-name="VidGo ${SA}" \
      2>/dev/null && log "SA '${SA}' created" || warn "SA '${SA}' already exists"
  done

  # Backend + Worker: SQL, Storage, Secrets
  for SA in "${BACKEND_SERVICE}" "${WORKER_SERVICE}"; do
    SA_EMAIL="${SA}@${PROJECT_ID}.iam.gserviceaccount.com"
    for ROLE in roles/cloudsql.client roles/storage.objectAdmin roles/secretmanager.secretAccessor roles/run.invoker roles/aiplatform.user; do
      gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="${ROLE}" \
        --quiet 2>/dev/null
    done
    log "IAM roles granted to ${SA}"
  done

  # Frontend: read-only storage
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${FRONTEND_SERVICE}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer" \
    --quiet 2>/dev/null
  log "IAM roles granted to ${FRONTEND_SERVICE}"
fi

###############################################################################
# STEP 8: Secret Manager (存放所有 API Keys)
###############################################################################
if should_run 8 "secrets"; then
  step 8 "存放 Secrets 到 Secret Manager"

  # Get IPs for connection strings
  SQL_IP=$(gcloud sql instances describe "${SQL_INSTANCE}" \
    --project="${PROJECT_ID}" \
    --format='value(ipAddresses[0].ipAddress)' 2>/dev/null)
  if [ -z "$SQL_IP" ] || [ "$SQL_IP" = "PENDING" ]; then
    err "Cloud SQL IP not ready! Wait a few minutes and retry."
    exit 1
  fi

  REDIS_IP=$(gcloud redis instances describe "${REDIS_INSTANCE}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --format='value(host)' 2>/dev/null || echo "127.0.0.1")

  DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${SQL_IP}:5432/${DB_NAME}"
  REDIS_URL="redis://${REDIS_IP}:6379/0"

  # Helper function: create or update secret
  put_secret() {
    local name=$1
    local value=$2
    if gcloud secrets describe "$name" --project="${PROJECT_ID}" &>/dev/null; then
      echo -n "$value" | gcloud secrets versions add "$name" --data-file=- --project="${PROJECT_ID}" &>/dev/null
      log "Updated secret: $name"
    else
      echo -n "$value" | gcloud secrets create "$name" --data-file=- --project="${PROJECT_ID}" \
        --replication-policy="user-managed" --locations="${REGION}" &>/dev/null
      log "Created secret: $name"
    fi
  }

  put_secret "DATABASE_URL"          "$DATABASE_URL"
  put_secret "REDIS_URL"             "$REDIS_URL"
  put_secret "SECRET_KEY"            "$SECRET_KEY"
  put_secret "PIAPI_KEY"             "$PIAPI_KEY"
  put_secret "GEMINI_API_KEY"        "$GEMINI_API_KEY"
  put_secret "POLLO_API_KEY"         "$POLLO_API_KEY"
  put_secret "A2E_API_KEY"           "$A2E_API_KEY"
  put_secret "A2E_API_ID"            "$A2E_API_ID"
  put_secret "A2E_DEFAULT_CREATOR_ID" "$A2E_DEFAULT_CREATOR_ID"
  put_secret "PADDLE_API_KEY"        "$PADDLE_API_KEY"
  put_secret "PADDLE_PUBLIC_KEY"    "$PADDLE_PUBLIC_KEY"
  put_secret "PADDLE_WEBHOOK_SECRET" "$PADDLE_WEBHOOK_SECRET"
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
  warn "REDIS_URL    = ${REDIS_URL}"
fi

###############################################################################
# STEP 9: Build & Push Docker Images
###############################################################################
if should_run 9 "build"; then
  step 9 "Build & Push Docker Images"

  IMAGE_TAG=$(date +%Y%m%d-%H%M%S)
  BACKEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/${BACKEND_SERVICE}"
  FRONTEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/${FRONTEND_SERVICE}"

  # Configure docker for Artifact Registry
  gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

  # Ensure PiAPI MCP server is cloned and built
  if [ ! -f "mcp-servers/piapi-mcp-server/dist/index.js" ]; then
    log "Setting up PiAPI MCP server..."
    bash mcp-servers/setup.sh
  fi

  log "Building backend image..."
  docker build \
    -t "${BACKEND_IMAGE}:${IMAGE_TAG}" \
    -t "${BACKEND_IMAGE}:latest" \
    -f backend/Dockerfile \
    .

  log "Building frontend image..."
  docker build \
    -t "${FRONTEND_IMAGE}:${IMAGE_TAG}" \
    -t "${FRONTEND_IMAGE}:latest" \
    -f frontend-vue/Dockerfile.prod \
    frontend-vue/

  log "Pushing images..."
  docker push "${BACKEND_IMAGE}:${IMAGE_TAG}"
  docker push "${BACKEND_IMAGE}:latest"
  docker push "${FRONTEND_IMAGE}:${IMAGE_TAG}"
  docker push "${FRONTEND_IMAGE}:latest"

  log "Images pushed: tag=${IMAGE_TAG}"

  # Save tag for deploy step
  echo "${IMAGE_TAG}" > /tmp/vidgo-image-tag
fi

###############################################################################
# STEP 10: Deploy to Cloud Run
###############################################################################
if should_run 10 "deploy"; then
  step 10 "部署到 Cloud Run"

  IMAGE_TAG=$(cat /tmp/vidgo-image-tag 2>/dev/null || echo "latest")
  BACKEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/${BACKEND_SERVICE}:${IMAGE_TAG}"
  FRONTEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/${FRONTEND_SERVICE}:${IMAGE_TAG}"
  SQL_CONNECTION="${PROJECT_ID}:${REGION}:${SQL_INSTANCE}"
  CONNECTOR_PATH="projects/${PROJECT_ID}/locations/${REGION}/connectors/${CONNECTOR_NAME}"

  # Use custom domain URLs for production
  # These must match your GoDaddy DNS → Cloud Run domain mappings (see step "domain")
  _BACKEND_URL="https://${CUSTOM_DOMAIN_BACKEND}"
  _FRONTEND_URL="https://${CUSTOM_DOMAIN_FRONTEND}"
  log "BACKEND_URL  = ${_BACKEND_URL}"
  log "FRONTEND_URL = ${_FRONTEND_URL}"

  # Env vars that Cloud Run needs (non-secret, safe to set directly)
  COMMON_ENV="SKIP_PREGENERATION=true,SKIP_DEPENDENCY_CHECK=true,DEBUG=false,ALGORITHM=HS256,ACCESS_TOKEN_EXPIRE_MINUTES=30,REFRESH_TOKEN_EXPIRE_DAYS=7,ECPAY_ENV=production,ECPAY_PAYMENT_URL=https://payment.ecpay.com.tw/Cashier/AioCheckOut/V2,GIVEME_ENABLED=true,GIVEME_BASE_URL=https://www.giveme.com.tw/invoice.do,GIVEME_UNCODE=96003146,FRONTEND_URL=${_FRONTEND_URL},BACKEND_URL=${_BACKEND_URL},PUBLIC_APP_URL=${_BACKEND_URL},CORS_ALLOW_ALL=true,PADDLE_ENV=${PADDLE_ENV},SMTP_FROM_EMAIL=noreply@vidgo.co,SMTP_FROM_NAME=VidGo,SMTP_TLS=true,GCS_BUCKET=${BUCKET_NAME},PIAPI_MCP_PATH=/app/mcp-servers/piapi-mcp-server/dist/index.js,VERTEX_AI_PROJECT=${PROJECT_ID},VERTEX_AI_LOCATION=${REGION},VEO_MODEL=veo-3.0-generate-preview,GEMINI_MODEL=gemini-2.0-flash"

  # Secret env vars (reference from Secret Manager)
  SECRET_ENV="DATABASE_URL=DATABASE_URL:latest,REDIS_URL=REDIS_URL:latest,SECRET_KEY=SECRET_KEY:latest,PIAPI_KEY=PIAPI_KEY:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest,POLLO_API_KEY=POLLO_API_KEY:latest,A2E_API_KEY=A2E_API_KEY:latest,A2E_API_ID=A2E_API_ID:latest,A2E_DEFAULT_CREATOR_ID=A2E_DEFAULT_CREATOR_ID:latest,PADDLE_API_KEY=PADDLE_API_KEY:latest,PADDLE_PUBLIC_KEY=PADDLE_PUBLIC_KEY:latest,PADDLE_WEBHOOK_SECRET=PADDLE_WEBHOOK_SECRET:latest,SMTP_HOST=SMTP_HOST:latest,SMTP_PORT=SMTP_PORT:latest,SMTP_USER=SMTP_USER:latest,SMTP_PASSWORD=SMTP_PASSWORD:latest,ECPAY_MERCHANT_ID=ECPAY_MERCHANT_ID:latest,ECPAY_HASH_KEY=ECPAY_HASH_KEY:latest,ECPAY_HASH_IV=ECPAY_HASH_IV:latest,GIVEME_IDNO=GIVEME_IDNO:latest,GIVEME_PASSWORD=GIVEME_PASSWORD:latest,FACEBOOK_APP_ID=FACEBOOK_APP_ID:latest,FACEBOOK_APP_SECRET=FACEBOOK_APP_SECRET:latest,TIKTOK_CLIENT_KEY=TIKTOK_CLIENT_KEY:latest,TIKTOK_CLIENT_SECRET=TIKTOK_CLIENT_SECRET:latest,YOUTUBE_CLIENT_ID=YOUTUBE_CLIENT_ID:latest,YOUTUBE_CLIENT_SECRET=YOUTUBE_CLIENT_SECRET:latest"

  # ── Deploy Backend ──
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
    --timeout=900 \
    --vpc-connector="${CONNECTOR_PATH}" \
    --add-cloudsql-instances="${SQL_CONNECTION}" \
    --service-account="${BACKEND_SERVICE}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --set-env-vars="${COMMON_ENV}" \
    --set-secrets="${SECRET_ENV}" \
    --startup-cpu-boost \
    --allow-unauthenticated
  log "Backend deployed"

  # ── Deploy Worker ──
  log "Deploying worker..."
  gcloud run deploy "${WORKER_SERVICE}" \
    --image="${BACKEND_IMAGE}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --platform=managed \
    --min-instances="${WORKER_MIN_INSTANCES}" \
    --max-instances="${WORKER_MAX_INSTANCES}" \
    --memory="${WORKER_MEMORY}" \
    --cpu="${WORKER_CPU}" \
    --port=8000 \
    --no-cpu-throttling \
    --vpc-connector="${CONNECTOR_PATH}" \
    --add-cloudsql-instances="${SQL_CONNECTION}" \
    --service-account="${WORKER_SERVICE}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --command="/bin/bash" \
    --args="-c,python -m http.server 8000 & exec arq app.worker.WorkerSettings" \
    --set-env-vars="${COMMON_ENV}" \
    --set-secrets="${SECRET_ENV}" \
    --no-allow-unauthenticated
  log "Worker deployed"

  # ── Deploy Frontend ──
  log "Deploying frontend..."
  BACKEND_URL=$(gcloud run services describe "${BACKEND_SERVICE}" \
    --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)' 2>/dev/null || echo "")

  gcloud run deploy "${FRONTEND_SERVICE}" \
    --image="${FRONTEND_IMAGE}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --platform=managed \
    --min-instances="${FRONTEND_MIN_INSTANCES}" \
    --max-instances="${FRONTEND_MAX_INSTANCES}" \
    --memory="${FRONTEND_MEMORY}" \
    --cpu="${FRONTEND_CPU}" \
    --port=80 \
    --service-account="${FRONTEND_SERVICE}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --set-env-vars="BACKEND_URL=${BACKEND_URL}" \
    --allow-unauthenticated
  log "Frontend deployed"

  # Print URLs
  echo ""
  BACKEND_URL=$(gcloud run services describe "${BACKEND_SERVICE}" \
    --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')
  FRONTEND_URL=$(gcloud run services describe "${FRONTEND_SERVICE}" \
    --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')

  log "Backend URL:  ${BACKEND_URL}"
  log "Frontend URL: ${FRONTEND_URL}"
fi

###############################################################################
# STEP 11: Custom Domain Mapping (vidgo.co)
###############################################################################
if should_run 11 "domain"; then
  step 11 "設定 Custom Domain → Cloud Run"

  warn "確認你已在 GoDaddy DNS 設定以下 CNAME 記錄:"
  warn "  ${CUSTOM_DOMAIN_BACKEND}     → ghs.googlehosted.com"
  warn "  ${CUSTOM_DOMAIN_FRONTEND}    → ghs.googlehosted.com"
  warn "  ${CUSTOM_DOMAIN_FRONTEND_WWW} → ghs.googlehosted.com"

  # Map api.vidgo.co → backend
  gcloud beta run domain-mappings create \
    --service="${BACKEND_SERVICE}" \
    --domain="${CUSTOM_DOMAIN_BACKEND}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    2>/dev/null && log "Domain mapped: ${CUSTOM_DOMAIN_BACKEND} → ${BACKEND_SERVICE}" \
    || warn "Domain mapping for ${CUSTOM_DOMAIN_BACKEND} already exists"

  # Map vidgo.co → frontend
  gcloud beta run domain-mappings create \
    --service="${FRONTEND_SERVICE}" \
    --domain="${CUSTOM_DOMAIN_FRONTEND}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    2>/dev/null && log "Domain mapped: ${CUSTOM_DOMAIN_FRONTEND} → ${FRONTEND_SERVICE}" \
    || warn "Domain mapping for ${CUSTOM_DOMAIN_FRONTEND} already exists"

  # Map www.vidgo.co → frontend
  gcloud run domain-mappings create \
    --service="${FRONTEND_SERVICE}" \
    --domain="${CUSTOM_DOMAIN_FRONTEND_WWW}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    2>/dev/null && log "Domain mapped: ${CUSTOM_DOMAIN_FRONTEND_WWW} → ${FRONTEND_SERVICE}" \
    || warn "Domain mapping for ${CUSTOM_DOMAIN_FRONTEND_WWW} already exists"

  # Show required DNS records
  echo ""
  warn "請在 GoDaddy DNS Manager 加入以下記錄:"
  echo "  ┌──────────┬──────────────────────┬─────────────────────────┐"
  echo "  │ Type     │ Name                 │ Value                   │"
  echo "  ├──────────┼──────────────────────┼─────────────────────────┤"
  echo "  │ CNAME    │ api                  │ ghs.googlehosted.com    │"
  echo "  │ CNAME    │ www                  │ ghs.googlehosted.com    │"
  echo "  │ CNAME    │ @                    │ ghs.googlehosted.com    │"
  echo "  └──────────┴──────────────────────┴─────────────────────────┘"
  warn "SSL 憑證由 Cloud Run (Let's Encrypt) 自動簽發，等 DNS 生效後約 15-30 分鐘"
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
# STEP 13: Final Summary
###############################################################################
if should_run 13 "summary"; then
  step 13 "部署完成總結"

  echo ""
  echo -e "${BOLD}━━━ 基礎設施 ━━━${NC}"
  echo "  Project:    ${PROJECT_ID}"
  echo "  Region:     ${REGION}"
  echo "  Domain:     ${CUSTOM_DOMAIN_FRONTEND} / ${CUSTOM_DOMAIN_BACKEND}"

  # Cloud SQL
  SQL_IP=$(gcloud sql instances describe "${SQL_INSTANCE}" \
    --project="${PROJECT_ID}" --format='value(ipAddresses[0].ipAddress)' 2>/dev/null || echo "N/A")
  echo "  Cloud SQL:  ${SQL_INSTANCE} (${SQL_IP})"

  # Redis
  REDIS_IP=$(gcloud redis instances describe "${REDIS_INSTANCE}" \
    --project="${PROJECT_ID}" --region="${REGION}" --format='value(host)' 2>/dev/null || echo "N/A")
  echo "  Redis:      ${REDIS_INSTANCE} (${REDIS_IP})"

  # NAT Static IP
  NAT_IP=$(gcloud compute addresses describe "${APP_NAME}-nat-ip" \
    --project="${PROJECT_ID}" --region="${REGION}" \
    --format='value(address)' 2>/dev/null || echo "N/A")
  echo "  NAT IP:     ${NAT_IP}  (Giveme/ECPay 白名單用)"

  # Storage
  echo "  Bucket:     gs://${BUCKET_NAME}"

  echo ""
  echo -e "${BOLD}━━━ Cloud Run 服務 ━━━${NC}"
  for SVC in "${BACKEND_SERVICE}" "${FRONTEND_SERVICE}" "${WORKER_SERVICE}"; do
    URL=$(gcloud run services describe "${SVC}" \
      --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)' 2>/dev/null || echo "Not deployed")
    echo "  ${SVC}: ${URL}"
  done

  echo ""
  echo -e "${BOLD}━━━ Custom Domain ━━━${NC}"
  echo "  Frontend: https://${CUSTOM_DOMAIN_FRONTEND}"
  echo "  Backend:  https://${CUSTOM_DOMAIN_BACKEND}"

  echo ""
  echo -e "${BOLD}━━━ Payment & Invoice ━━━${NC}"
  echo "  ECPay:    production (MerchantID: ${ECPAY_MERCHANT_ID})"
  echo "  Giveme:   enabled (統一編號: 96003146)"
  echo "  Paddle:   ${PADDLE_ENV}"

  echo ""
  echo -e "${BOLD}━━━ 預估月費 (Phase 1, 0-500 users) ━━━${NC}"
  echo "  Cloud Run:     ~\$30–50"
  echo "  Cloud SQL:     ~\$25–35"
  echo "  Redis:         ~\$15–20"
  echo "  Storage + CDN: ~\$5–10"
  echo "  ─────────────────────"
  echo "  Total:         ~\$88–115 USD/month"
  echo ""

  echo -e "${BOLD}━━━ 待辦事項 ━━━${NC}"
  echo "  [ ] 確認 GoDaddy DNS 已設定 CNAME → ghs.googlehosted.com"
  echo "  [ ] 確認 DNS 已生效: dig ${CUSTOM_DOMAIN_BACKEND} CNAME"
  echo "  [ ] 將 NAT IP (${NAT_IP}) 加入 Giveme 白名單 (系統設定→白名單設定)"
  echo "  [ ] 將 NAT IP (${NAT_IP}) 加入 ECPay 允許 IP (系統介接設定→允許的IP)"
  echo "  [ ] 在 ECPay 商店後台設定回調 URL:"
  echo "      付款通知: https://${CUSTOM_DOMAIN_BACKEND}/api/v1/payments/ecpay/callback"
  echo "      完成返回: https://${CUSTOM_DOMAIN_FRONTEND}/subscription/ecpay-result"
  echo "  [ ] 測試: curl https://${CUSTOM_DOMAIN_BACKEND}/health"
  echo "  [ ] 測試: ECPay 付款流程 (小額測試)"
  echo "  [ ] 測試: Giveme 發票開立"
  echo "  [ ] 設定 Budget Alert (\$${BUDGET_AMOUNT}): https://console.cloud.google.com/billing/budgets"
  echo "  [ ] 設定 Cloud Build Trigger (GitHub → main branch)"
  echo "  [ ] 填入 Social Media OAuth keys (Facebook/TikTok/YouTube) 並重新部署"
  echo ""
  echo -e "${GREEN}${BOLD}Deployment complete!${NC}"
fi
