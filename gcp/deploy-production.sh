#!/bin/bash
# VidGo GCP Production Deployment Script
# Region: asia-east1 (Taiwan)
#
# This script sets up the complete GCP infrastructure for VidGo.
# Run sections individually or all at once.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Billing enabled on the project
#   - APIs enabled: run, sql, redis, compute, artifactregistry, cloudbuild, secretmanager
#
# Usage: bash gcp/deploy-production.sh <PROJECT_ID>

set -euo pipefail

PROJECT_ID="${1:?Usage: $0 <PROJECT_ID>}"
REGION="asia-east1"
VPC_NAME="vidgo-vpc"
SUBNET_NAME="vidgo-subnet"

echo "=========================================="
echo " VidGo Production Deployment"
echo " Project: ${PROJECT_ID}"
echo " Region:  ${REGION}"
echo "=========================================="

# ──────────────────────────────────────────────────────────────────────
# 1. Enable Required APIs
# ──────────────────────────────────────────────────────────────────────
echo ""
echo "[1/10] Enabling required APIs..."
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  redis.googleapis.com \
  compute.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  vpcaccess.googleapis.com \
  cloudresourcemanager.googleapis.com \
  monitoring.googleapis.com \
  logging.googleapis.com \
  aiplatform.googleapis.com \
  --project="${PROJECT_ID}"

# ──────────────────────────────────────────────────────────────────────
# 2. Create VPC Network
# ──────────────────────────────────────────────────────────────────────
echo ""
echo "[2/10] Creating VPC network..."
gcloud compute networks create "${VPC_NAME}" \
  --project="${PROJECT_ID}" \
  --subnet-mode=custom \
  2>/dev/null || echo "  VPC already exists"

gcloud compute networks subnets create "${SUBNET_NAME}" \
  --project="${PROJECT_ID}" \
  --network="${VPC_NAME}" \
  --region="${REGION}" \
  --range="10.0.1.0/24" \
  2>/dev/null || echo "  Subnet already exists"

# VPC Connector for Cloud Run
gcloud compute networks vpc-access connectors create vidgo-connector \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --network="${VPC_NAME}" \
  --range="10.8.0.0/28" \
  --min-instances=2 \
  --max-instances=3 \
  2>/dev/null || echo "  VPC connector already exists"

# Cloud NAT for outbound API calls
gcloud compute routers create vidgo-router \
  --project="${PROJECT_ID}" \
  --network="${VPC_NAME}" \
  --region="${REGION}" \
  2>/dev/null || echo "  Router already exists"

gcloud compute routers nats create vidgo-nat \
  --project="${PROJECT_ID}" \
  --router=vidgo-router \
  --region="${REGION}" \
  --auto-allocate-nat-external-ips \
  --nat-all-subnet-ip-ranges \
  2>/dev/null || echo "  NAT already exists"

# ──────────────────────────────────────────────────────────────────────
# 3. Create Artifact Registry
# ──────────────────────────────────────────────────────────────────────
echo ""
echo "[3/10] Creating Artifact Registry..."
gcloud artifacts repositories create vidgo-images \
  --project="${PROJECT_ID}" \
  --repository-format=docker \
  --location="${REGION}" \
  --description="VidGo Docker images" \
  2>/dev/null || echo "  Artifact Registry already exists"

# ──────────────────────────────────────────────────────────────────────
# 4. Create Cloud SQL (PostgreSQL 15)
# ──────────────────────────────────────────────────────────────────────
echo ""
echo "[4/10] Creating Cloud SQL instance..."
gcloud sql instances create vidgo-db \
  --project="${PROJECT_ID}" \
  --database-version=POSTGRES_15 \
  --tier=db-g1-small \
  --region="${REGION}" \
  --network="${VPC_NAME}" \
  --no-assign-ip \
  --storage-type=SSD \
  --storage-size=10GB \
  --storage-auto-increase \
  --backup-start-time="03:00" \
  --maintenance-window-day=SUN \
  --maintenance-window-hour=4 \
  --database-flags="max_connections=100" \
  2>/dev/null || echo "  Cloud SQL instance already exists"

# Create database and user
gcloud sql databases create vidgo \
  --project="${PROJECT_ID}" \
  --instance=vidgo-db \
  2>/dev/null || echo "  Database already exists"

echo "  NOTE: Set the database password manually:"
echo "    gcloud sql users set-password postgres --instance=vidgo-db --password=<YOUR_PASSWORD>"

# ──────────────────────────────────────────────────────────────────────
# 5. Create Memorystore Redis
# ──────────────────────────────────────────────────────────────────────
echo ""
echo "[5/10] Creating Memorystore Redis..."
gcloud redis instances create vidgo-redis \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --tier=basic \
  --size=1 \
  --redis-version=redis_7_0 \
  --network="${VPC_NAME}" \
  2>/dev/null || echo "  Redis instance already exists"

# ──────────────────────────────────────────────────────────────────────
# 6. Create Cloud Storage Bucket + Lifecycle + CDN
# ──────────────────────────────────────────────────────────────────────
echo ""
echo "[6/10] Creating Cloud Storage bucket..."
gsutil mb -p "${PROJECT_ID}" -l "${REGION}" -c STANDARD \
  "gs://vidgo-media-${PROJECT_ID}" \
  2>/dev/null || echo "  Bucket already exists"

# Apply lifecycle policy (14d generated, 30d uploads, 7d materials->Nearline)
gsutil lifecycle set gcp/storage-lifecycle.json "gs://vidgo-media-${PROJECT_ID}"
echo "  Storage lifecycle policy applied"

# Enable CDN on the bucket
echo "  NOTE: Enable Cloud CDN via Load Balancer backend bucket config"

# ──────────────────────────────────────────────────────────────────────
# 7. Create Service Accounts
# ──────────────────────────────────────────────────────────────────────
echo ""
echo "[7/10] Creating service accounts..."

for SA in vidgo-backend vidgo-worker vidgo-frontend; do
  gcloud iam service-accounts create "${SA}" \
    --project="${PROJECT_ID}" \
    --display-name="VidGo ${SA}" \
    2>/dev/null || echo "  ${SA} SA already exists"
done

# Grant permissions
for SA in vidgo-backend vidgo-worker; do
  SA_EMAIL="${SA}@${PROJECT_ID}.iam.gserviceaccount.com"
  for ROLE in roles/cloudsql.client roles/storage.objectAdmin roles/secretmanager.secretAccessor roles/aiplatform.user; do
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
      --member="serviceAccount:${SA_EMAIL}" \
      --role="${ROLE}" \
      --quiet 2>/dev/null
  done
done

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:vidgo-frontend@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer" \
  --quiet 2>/dev/null

echo "  Service accounts configured"

# ──────────────────────────────────────────────────────────────────────
# 8. Set Up Budget Alerts
# ──────────────────────────────────────────────────────────────────────
echo ""
echo "[8/10] Budget alerts..."
echo "  NOTE: Configure budget alerts manually in Cloud Console:"
echo "    - Budget: \$300 USD/month"
echo "    - Thresholds: 50% (\$150), 80% (\$240), 100% (\$300)"
echo "    - Notification channel: your email"

# ──────────────────────────────────────────────────────────────────────
# 9. Apply Cloud Armor Policy
# ──────────────────────────────────────────────────────────────────────
echo ""
echo "[9/10] Applying Cloud Armor policy..."
bash gcp/cloud-armor-policy.sh "${PROJECT_ID}" || echo "  Cloud Armor setup failed (may need Load Balancer first)"

# ──────────────────────────────────────────────────────────────────────
# 10. Summary
# ──────────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo " Deployment Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Set Cloud SQL password:"
echo "     gcloud sql users set-password postgres --instance=vidgo-db --password=<PASSWORD>"
echo ""
echo "  2. Store secrets in Secret Manager:"
echo "     echo -n '<value>' | gcloud secrets create DATABASE_URL --data-file=- --project=${PROJECT_ID}"
echo "     (Repeat for: REDIS_URL, PIAPI_KEY, POLLO_API_KEY, GEMINI_API_KEY, JWT_SECRET, etc.)"
echo ""
echo "  NOTE: Vertex AI uses ADC (service account), not API key."
echo "  The backend service account already has roles/aiplatform.user."
echo "  Set VERTEX_AI_PROJECT=${PROJECT_ID} and VERTEX_AI_LOCATION=${REGION} as env vars."
echo ""
echo "  3. Connect Cloud Build trigger to your repo:"
echo "     gcloud builds triggers create github \\"
echo "       --repo-name=Vidgo-Gen-AI --branch-pattern='^main$' \\"
echo "       --build-config=cloudbuild.yaml --project=${PROJECT_ID}"
echo ""
echo "  4. Run first build:"
echo "     gcloud builds submit --config=cloudbuild.yaml --project=${PROJECT_ID}"
echo ""
echo "  5. Get Redis IP for config:"
echo "     gcloud redis instances describe vidgo-redis --region=${REGION} --project=${PROJECT_ID} --format='value(host)'"
echo ""
echo "  6. After stable for 3 months, purchase Committed Use Discounts:"
echo "     - Cloud SQL: 37% savings"
echo "     - Memorystore: 35% savings"
