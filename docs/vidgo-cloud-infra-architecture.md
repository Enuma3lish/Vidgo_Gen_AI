# VidGo Gen AI — GCP Cloud Infrastructure Architecture

## Overview

This document describes the recommended Google Cloud Platform (GCP) architecture for deploying the VidGo Gen AI platform in production. It covers service selection, network topology, deployment steps, and cost-optimization strategies.

The platform is a dual-mode SaaS AI video/image tool:
- **Frontend:** Vue 3 (Vite, TypeScript)
- **Backend:** FastAPI (Python 3.12, async)
- **Background Worker:** ARQ (async Redis task queue)
- **Database:** PostgreSQL 15
- **Cache / Queue:** Redis 7
- **Media Storage:** Generated images, videos, garment assets

---

## Architecture Diagram

```
                          ┌─────────────────────────────────────────────────┐
                          │              Google Cloud Platform               │
                          │                  (asia-east1)                   │
                          │                                                  │
  Users                   │  ┌──────────────────────────────────────────┐   │
  ─────────               │  │         Cloud Load Balancer (HTTPS)      │   │
  Browser ──────────────────►│  SSL cert (managed), DDoS protection,    │   │
                          │  │  HTTP→HTTPS redirect, URL path routing   │   │
                          │  └───────────┬──────────────┬───────────────┘   │
                          │              │              │                    │
                          │  ┌───────────▼──┐  ┌───────▼──────────────┐    │
                          │  │  Cloud Run   │  │     Cloud Run        │    │
                          │  │  (Frontend)  │  │     (Backend API)    │    │
                          │  │  Vue 3 / Nginx│  │   FastAPI :8001     │    │
                          │  │  min 0 / max 4│  │   min 1 / max 10    │    │
                          │  └──────────────┘  └───────┬──────────────┘    │
                          │                            │                    │
                          │              ┌─────────────┼──────────┐         │
                          │              │             │          │         │
                          │  ┌───────────▼──┐  ┌──────▼───┐  ┌───▼──────┐  │
                          │  │  Cloud Run   │  │ Cloud SQL│  │Memorystore│  │
                          │  │  (ARQ Worker)│  │(PostgreSQL│  │ (Redis)  │  │
                          │  │  min 1/max 3 │  │  15)     │  │  1-5 GB  │  │
                          │  └──────────────┘  └──────────┘  └──────────┘  │
                          │                                                  │
                          │  ┌────────────────────────────────────────────┐  │
                          │  │               Cloud Storage                │  │
                          │  │  vidgo-media bucket (CDN-enabled)          │  │
                          │  │  generated/, materials/, tryon_garments/   │  │
                          │  └────────────────────────────────────────────┘  │
                          │                                                  │
                          │  ┌──────────────┐  ┌──────────┐  ┌───────────┐  │
                          │  │  Secret Mgr  │  │  Cloud   │  │  Artifact │  │
                          │  │  (env vars,  │  │  Build   │  │ Registry  │  │
                          │  │   API keys)  │  │  CI/CD   │  │ (Docker)  │  │
                          │  └──────────────┘  └──────────┘  └───────────┘  │
                          └─────────────────────────────────────────────────┘
```

---

## GCP Services Summary

| Service | Role | Tier / Config |
|---|---|---|
| **Cloud Run** | Frontend, Backend, ARQ Worker | Serverless containers; auto-scaling |
| **Cloud SQL** | PostgreSQL 15 | `db-g1-small` → `db-n1-standard-2` at scale |
| **Memorystore** | Redis 7 (cache + ARQ queue) | Basic 1 GB → Standard 5 GB at scale |
| **Cloud Storage** | Media files, static assets | Standard + CDN (Cloud CDN) |
| **Cloud Load Balancer** | HTTPS ingress, URL routing | Global external HTTPS LB |
| **Artifact Registry** | Docker image storage | Standard repository |
| **Cloud Build** | CI/CD pipeline | Build + deploy triggers |
| **Secret Manager** | API keys, DB passwords | All sensitive env vars |
| **Cloud Monitoring** | Metrics, alerts | Custom dashboards |
| **Cloud Logging** | Structured logs | Log-based metrics + alerts |
| **Cloud Armor** | WAF, DDoS protection | Security policy on LB |
| **VPC** | Private networking | Custom VPC with private service connect |

---

## Networking & Security

### VPC Design

```
VPC: vidgo-vpc (10.0.0.0/16)
├── Subnet: vidgo-subnet (10.0.1.0/24) — Cloud Run VPC connector
├── Private Service Connect — Cloud SQL & Memorystore (no public IP)
└── Cloud NAT — outbound internet for workers (AI API calls)
```

- Cloud Run services connect to Cloud SQL and Memorystore via **VPC connector** over private IPs.
- Cloud SQL has **no public IP**; accessible only from the VPC.
- Memorystore is **VPC-native**; accessible only from the same VPC.
- Outbound AI API calls (PiAPI, Pollo, A2E) route through **Cloud NAT**.

### Cloud Armor (WAF)

- Rate limiting: 100 req/min per IP on `/auth/*` routes
- Block common exploit signatures (OWASP rules)
- Geo-restriction (optional, if needed)

### IAM Service Accounts

| Account | Permissions |
|---|---|
| `vidgo-backend@PROJECT.iam` | `cloudsql.client`, `storage.objectAdmin`, `secretmanager.secretAccessor` |
| `vidgo-worker@PROJECT.iam` | `cloudsql.client`, `storage.objectAdmin`, `secretmanager.secretAccessor` |
| `vidgo-frontend@PROJECT.iam` | `storage.objectViewer` |
| `vidgo-cloudbuild@PROJECT.iam` | `run.admin`, `artifactregistry.writer`, `iam.serviceAccountUser` |

---

## Cloud Run Configuration

### Frontend (Vue 3 / Nginx)

```yaml
Service: vidgo-frontend
Region: asia-east1
Image: asia-east1-docker.pkg.dev/PROJECT/vidgo/frontend:TAG
Resources:
  cpu: 1
  memory: 512Mi
Scaling:
  minInstances: 0
  maxInstances: 4
  concurrency: 1000
Port: 8080
```

**Dockerfile for production frontend:**
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
```

**nginx.conf (SPA routing + gzip):**
```nginx
server {
    listen 8080;
    root /usr/share/nginx/html;
    gzip on;
    gzip_types text/plain text/css application/javascript application/json;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### Backend (FastAPI)

```yaml
Service: vidgo-backend
Region: asia-east1
Image: asia-east1-docker.pkg.dev/PROJECT/vidgo/backend:TAG
Resources:
  cpu: 2
  memory: 2Gi
Scaling:
  minInstances: 1          # Keep warm — avoid cold start latency
  maxInstances: 10
  concurrency: 80
Port: 8001
VpcConnector: vidgo-vpc-connector
Env:
  - SKIP_PREGENERATION: "true"    # Don't run pre-gen on Cloud Run startup
  - All secrets via Secret Manager
```

### ARQ Worker

```yaml
Service: vidgo-worker
Region: asia-east1
Image: asia-east1-docker.pkg.dev/PROJECT/vidgo/backend:TAG
Command: ["python", "-m", "app.worker"]
Resources:
  cpu: 2
  memory: 2Gi
Scaling:
  minInstances: 1
  maxInstances: 3
  concurrency: 1            # Workers should not share instances
VpcConnector: vidgo-vpc-connector
```

> **Note:** The ARQ worker does not serve HTTP traffic. Deploy it as a Cloud Run **Job** (for batch pre-generation) or as a **Service** with a minimal HTTP health endpoint for continuous queue processing.

---

## Database — Cloud SQL (PostgreSQL 15)

```
Instance: vidgo-postgres
Tier: db-g1-small (1 vCPU, 614 MB RAM) → db-n1-standard-2 for production load
Storage: 10 GB SSD, auto-grow enabled (max 100 GB)
Availability: Single zone (dev) → High availability (regional) for production
Backups: Daily automated, 7-day retention
Flags:
  max_connections: 100
  shared_buffers: 128MB
Private IP: Yes (no public IP)
Region: asia-east1
```

**Connection via Cloud SQL Auth Proxy (built into Cloud Run):**
```
/cloudsql/PROJECT:asia-east1:vidgo-postgres
```

Set `DATABASE_URL` in Secret Manager:
```
postgresql+asyncpg://vidgo_user:PASSWORD@/vidgo_db?host=/cloudsql/PROJECT:asia-east1:vidgo-postgres
```

---

## Cache & Queue — Memorystore (Redis 7)

```
Instance: vidgo-redis
Tier: Basic (no replication) → Standard (with replica) for production
Capacity: 1 GB → 5 GB at scale
Region: asia-east1
Version: Redis 7.0
Auth: Enabled (AUTH token via Secret Manager)
```

Set `REDIS_URL` in Secret Manager:
```
redis://:AUTH_TOKEN@REDIS_IP:6379/0
```

---

## Media Storage — Cloud Storage

```
Bucket: vidgo-media-asia
Location: asia-east1 (regional)
Storage class: Standard
Lifecycle rules:
  - Delete objects in generated/ older than 14 days (matches cleanup policy)
  - Delete objects in uploads/ older than 30 days
CDN: Cloud CDN enabled on the bucket backend
CORS: Allow GET from https://vidgo.ai
IAM: vidgo-backend SA has objectAdmin; public read for /materials/ prefix
```

**Bucket structure:**
```
vidgo-media-asia/
├── generated/          # Subscriber-generated outputs (14-day cleanup)
├── materials/          # Pre-generated showcase materials (permanent)
├── tryon_garments/     # Virtual Try-On cached garments
└── uploads/            # User uploads (30-day cleanup)
```

---

## CI/CD — Cloud Build

`cloudbuild.yaml`:
```yaml
steps:
  # Build backend image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'asia-east1-docker.pkg.dev/$PROJECT_ID/vidgo/backend:$SHORT_SHA', './backend']

  # Build frontend image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'asia-east1-docker.pkg.dev/$PROJECT_ID/vidgo/frontend:$SHORT_SHA', './frontend-vue']

  # Push images
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'asia-east1-docker.pkg.dev/$PROJECT_ID/vidgo/backend:$SHORT_SHA']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'asia-east1-docker.pkg.dev/$PROJECT_ID/vidgo/frontend:$SHORT_SHA']

  # Deploy backend
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    args:
      - 'run'
      - 'deploy'
      - 'vidgo-backend'
      - '--image=asia-east1-docker.pkg.dev/$PROJECT_ID/vidgo/backend:$SHORT_SHA'
      - '--region=asia-east1'

  # Deploy frontend
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    args:
      - 'run'
      - 'deploy'
      - 'vidgo-frontend'
      - '--image=asia-east1-docker.pkg.dev/$PROJECT_ID/vidgo/frontend:$SHORT_SHA'
      - '--region=asia-east1'

  # Deploy worker
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    args:
      - 'run'
      - 'deploy'
      - 'vidgo-worker'
      - '--image=asia-east1-docker.pkg.dev/$PROJECT_ID/vidgo/backend:$SHORT_SHA'
      - '--region=asia-east1'
      - '--command=python,-m,app.worker'

options:
  logging: CLOUD_LOGGING_ONLY

triggers:
  - branch: main     # Production deploy
  - branch: staging  # Staging deploy
```

---

## DNS & Domain Setup

Domains are managed through **GoDaddy** (vidgo.ai).

| Domain | Cloud LB IP | Service |
|---|---|---|
| `vidgo.ai` | LB_IP | Frontend (Cloud Run) |
| `www.vidgo.ai` | LB_IP | Redirect → vidgo.ai |
| `api.vidgo.ai` | LB_IP | Backend API (Cloud Run) |

**GoDaddy DNS records:**
```
A    @         LB_IP    TTL 300
A    www       LB_IP    TTL 300
A    api       LB_IP    TTL 300
```

**Cloud Load Balancer URL map:**
```
Host: vidgo.ai      → Backend service: vidgo-frontend-neg
Host: api.vidgo.ai  → Backend service: vidgo-backend-neg
```

SSL certificates are managed certificates (auto-renewed by GCP).

---

## Step-by-Step Deployment Guide

### Prerequisites

```bash
# Install gcloud CLI and authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud config set compute/region asia-east1

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  redis.googleapis.com \
  storage.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  vpcaccess.googleapis.com \
  compute.googleapis.com \
  cloudarmor.googleapis.com
```

### Step 1 — VPC & Networking

```bash
# Create VPC
gcloud compute networks create vidgo-vpc --subnet-mode=custom

# Create subnet
gcloud compute networks subnets create vidgo-subnet \
  --network=vidgo-vpc \
  --region=asia-east1 \
  --range=10.0.1.0/24

# Create VPC connector for Cloud Run
gcloud compute networks vpc-access connectors create vidgo-vpc-connector \
  --region=asia-east1 \
  --subnet=vidgo-subnet \
  --min-instances=2 \
  --max-instances=10

# Create Cloud NAT for outbound access
gcloud compute routers create vidgo-router \
  --network=vidgo-vpc \
  --region=asia-east1

gcloud compute routers nats create vidgo-nat \
  --router=vidgo-router \
  --region=asia-east1 \
  --auto-allocate-nat-external-ips \
  --nat-all-subnet-ip-ranges
```

### Step 2 — Service Accounts

```bash
# Create service accounts
for SA in backend worker frontend cloudbuild; do
  gcloud iam service-accounts create vidgo-$SA \
    --display-name="VidGo $SA"
done

PROJECT=$(gcloud config get-value project)

# Backend permissions
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:vidgo-backend@$PROJECT.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:vidgo-backend@$PROJECT.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:vidgo-backend@$PROJECT.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Worker same as backend
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:vidgo-worker@$PROJECT.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:vidgo-worker@$PROJECT.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:vidgo-worker@$PROJECT.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Step 3 — Cloud SQL

```bash
gcloud sql instances create vidgo-postgres \
  --database-version=POSTGRES_15 \
  --tier=db-g1-small \
  --region=asia-east1 \
  --no-assign-ip \
  --network=vidgo-vpc \
  --storage-type=SSD \
  --storage-size=10GB \
  --storage-auto-increase \
  --backup-start-time=03:00 \
  --retained-backups-count=7

gcloud sql databases create vidgo_db --instance=vidgo-postgres
gcloud sql users create vidgo_user \
  --instance=vidgo-postgres \
  --password=STRONG_PASSWORD
```

### Step 4 — Memorystore (Redis)

```bash
gcloud redis instances create vidgo-redis \
  --size=1 \
  --region=asia-east1 \
  --network=vidgo-vpc \
  --redis-version=redis_7_0 \
  --enable-auth

# Get auth token
gcloud redis instances get-auth-string vidgo-redis --region=asia-east1
```

### Step 5 — Cloud Storage

```bash
PROJECT=$(gcloud config get-value project)

gcloud storage buckets create gs://vidgo-media-$PROJECT \
  --location=asia-east1 \
  --storage-class=STANDARD

# Lifecycle: delete generated files after 14 days
cat > lifecycle.json <<EOF
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {
        "age": 14,
        "matchesPrefix": ["generated/"]
      }
    },
    {
      "action": {"type": "Delete"},
      "condition": {
        "age": 30,
        "matchesPrefix": ["uploads/"]
      }
    }
  ]
}
EOF
gcloud storage buckets update gs://vidgo-media-$PROJECT --lifecycle-file=lifecycle.json

# Enable CDN (via backend bucket in Load Balancer step)
# Make materials/ prefix public
gcloud storage buckets add-iam-policy-binding gs://vidgo-media-$PROJECT \
  --member=allUsers \
  --role=roles/storage.objectViewer \
  --condition='expression=resource.name.startsWith("projects/_/buckets/vidgo-media-'"$PROJECT"'/objects/materials/"),title=materials-public'
```

### Step 6 — Secret Manager

```bash
# Store all secrets
for SECRET_NAME in \
  db-url redis-url secret-key \
  piapi-key pollo-api-key a2e-api-key a2e-api-id a2e-creator-id \
  gemini-api-key paddle-api-key paddle-public-key \
  ecpay-merchant-id ecpay-hash-key ecpay-hash-iv \
  recaptcha-secret recaptcha-site-key \
  gcs-bucket-name; do
  echo -n "PLACEHOLDER" | gcloud secrets create $SECRET_NAME --data-file=-
done

# Update actual values
echo -n "postgresql+asyncpg://vidgo_user:PASSWORD@/vidgo_db?host=/cloudsql/PROJECT:asia-east1:vidgo-postgres" \
  | gcloud secrets versions add db-url --data-file=-
```

### Step 7 — Artifact Registry & Build Images

```bash
PROJECT=$(gcloud config get-value project)

gcloud artifacts repositories create vidgo \
  --repository-format=docker \
  --location=asia-east1

# Build and push images
gcloud builds submit ./backend \
  --tag=asia-east1-docker.pkg.dev/$PROJECT/vidgo/backend:latest

gcloud builds submit ./frontend-vue \
  --tag=asia-east1-docker.pkg.dev/$PROJECT/vidgo/frontend:latest
```

### Step 8 — Deploy Cloud Run Services

```bash
PROJECT=$(gcloud config get-value project)

# Backend
gcloud run deploy vidgo-backend \
  --image=asia-east1-docker.pkg.dev/$PROJECT/vidgo/backend:latest \
  --region=asia-east1 \
  --platform=managed \
  --service-account=vidgo-backend@$PROJECT.iam.gserviceaccount.com \
  --vpc-connector=vidgo-vpc-connector \
  --vpc-egress=private-ranges-only \
  --add-cloudsql-instances=$PROJECT:asia-east1:vidgo-postgres \
  --set-secrets="DATABASE_URL=db-url:latest,REDIS_URL=redis-url:latest,SECRET_KEY=secret-key:latest,PIAPI_KEY=piapi-key:latest,GEMINI_API_KEY=gemini-api-key:latest,PADDLE_API_KEY=paddle-api-key:latest,PADDLE_PUBLIC_KEY=paddle-public-key:latest,RECAPTCHA_SECRET_KEY=recaptcha-secret:latest" \
  --set-env-vars="SKIP_PREGENERATION=true,GCS_BUCKET=vidgo-media-$PROJECT" \
  --min-instances=1 \
  --max-instances=10 \
  --concurrency=80 \
  --cpu=2 \
  --memory=2Gi \
  --port=8001 \
  --allow-unauthenticated

# Worker
gcloud run deploy vidgo-worker \
  --image=asia-east1-docker.pkg.dev/$PROJECT/vidgo/backend:latest \
  --region=asia-east1 \
  --platform=managed \
  --service-account=vidgo-worker@$PROJECT.iam.gserviceaccount.com \
  --vpc-connector=vidgo-vpc-connector \
  --vpc-egress=all-traffic \
  --add-cloudsql-instances=$PROJECT:asia-east1:vidgo-postgres \
  --set-secrets="DATABASE_URL=db-url:latest,REDIS_URL=redis-url:latest,SECRET_KEY=secret-key:latest,PIAPI_KEY=piapi-key:latest,POLLO_API_KEY=pollo-api-key:latest,A2E_API_KEY=a2e-api-key:latest,GEMINI_API_KEY=gemini-api-key:latest" \
  --set-env-vars="SKIP_PREGENERATION=true,GCS_BUCKET=vidgo-media-$PROJECT" \
  --command="python,-m,app.worker" \
  --min-instances=1 \
  --max-instances=3 \
  --concurrency=1 \
  --cpu=2 \
  --memory=2Gi \
  --no-allow-unauthenticated

# Frontend
gcloud run deploy vidgo-frontend \
  --image=asia-east1-docker.pkg.dev/$PROJECT/vidgo/frontend:latest \
  --region=asia-east1 \
  --platform=managed \
  --min-instances=0 \
  --max-instances=4 \
  --concurrency=1000 \
  --cpu=1 \
  --memory=512Mi \
  --port=8080 \
  --allow-unauthenticated
```

### Step 9 — Cloud Load Balancer

```bash
PROJECT=$(gcloud config get-value project)
REGION=asia-east1

# Reserve static IP
gcloud compute addresses create vidgo-lb-ip --global

# Create NEGs for Cloud Run services
gcloud compute network-endpoint-groups create vidgo-backend-neg \
  --region=$REGION \
  --network-endpoint-type=serverless \
  --cloud-run-service=vidgo-backend

gcloud compute network-endpoint-groups create vidgo-frontend-neg \
  --region=$REGION \
  --network-endpoint-type=serverless \
  --cloud-run-service=vidgo-frontend

# Backend services
gcloud compute backend-services create vidgo-backend-svc \
  --global --load-balancing-scheme=EXTERNAL_MANAGED
gcloud compute backend-services add-backend vidgo-backend-svc \
  --global --network-endpoint-group=vidgo-backend-neg \
  --network-endpoint-group-region=$REGION

gcloud compute backend-services create vidgo-frontend-svc \
  --global --load-balancing-scheme=EXTERNAL_MANAGED
gcloud compute backend-services add-backend vidgo-frontend-svc \
  --global --network-endpoint-group=vidgo-frontend-neg \
  --network-endpoint-group-region=$REGION

# Enable CDN on frontend
gcloud compute backend-services update vidgo-frontend-svc --global --enable-cdn

# URL map
gcloud compute url-maps create vidgo-url-map \
  --default-service=vidgo-frontend-svc

gcloud compute url-maps add-host-rule vidgo-url-map \
  --hosts=api.vidgo.ai \
  --path-matcher-name=api-matcher
gcloud compute url-maps add-path-matcher vidgo-url-map \
  --path-matcher-name=api-matcher \
  --default-service=vidgo-backend-svc

# SSL certificate
gcloud compute ssl-certificates create vidgo-ssl \
  --domains=vidgo.ai,www.vidgo.ai,api.vidgo.ai \
  --global

# HTTPS proxy and forwarding rule
gcloud compute target-https-proxies create vidgo-https-proxy \
  --url-map=vidgo-url-map \
  --ssl-certificates=vidgo-ssl

gcloud compute forwarding-rules create vidgo-https-rule \
  --global \
  --target-https-proxy=vidgo-https-proxy \
  --address=vidgo-lb-ip \
  --ports=443

# HTTP → HTTPS redirect
gcloud compute url-maps import vidgo-http-redirect --global <<EOF
kind: compute#urlMap
name: vidgo-http-redirect
defaultUrlRedirect:
  redirectResponseCode: MOVED_PERMANENTLY_DEFAULT
  httpsRedirect: true
EOF

gcloud compute target-http-proxies create vidgo-http-proxy \
  --url-map=vidgo-http-redirect

gcloud compute forwarding-rules create vidgo-http-rule \
  --global \
  --target-http-proxy=vidgo-http-proxy \
  --address=vidgo-lb-ip \
  --ports=80
```

### Step 10 — Database Migrations

```bash
# Run Alembic migrations via Cloud Run Job
gcloud run jobs create vidgo-migrate \
  --image=asia-east1-docker.pkg.dev/$PROJECT/vidgo/backend:latest \
  --region=asia-east1 \
  --service-account=vidgo-backend@$PROJECT.iam.gserviceaccount.com \
  --vpc-connector=vidgo-vpc-connector \
  --add-cloudsql-instances=$PROJECT:asia-east1:vidgo-postgres \
  --set-secrets="DATABASE_URL=db-url:latest" \
  --command="alembic,upgrade,head"

gcloud run jobs execute vidgo-migrate --region=asia-east1 --wait
```

### Step 11 — Pre-generation Materials (One-Time)

```bash
# Run material pre-generation as a Cloud Run Job
gcloud run jobs create vidgo-init-materials \
  --image=asia-east1-docker.pkg.dev/$PROJECT/vidgo/backend:latest \
  --region=asia-east1 \
  --service-account=vidgo-backend@$PROJECT.iam.gserviceaccount.com \
  --vpc-connector=vidgo-vpc-connector \
  --vpc-egress=all-traffic \
  --add-cloudsql-instances=$PROJECT:asia-east1:vidgo-postgres \
  --set-secrets="DATABASE_URL=db-url:latest,REDIS_URL=redis-url:latest,PIAPI_KEY=piapi-key:latest,GEMINI_API_KEY=gemini-api-key:latest,GCS_BUCKET=gcs-bucket-name:latest" \
  --set-env-vars="PREGENERATION_LIMIT=10" \
  --command="python,scripts/generate_materials.py" \
  --task-timeout=3600 \
  --cpu=2 \
  --memory=4Gi

gcloud run jobs execute vidgo-init-materials --region=asia-east1
```

---

## Cost Optimization Strategies

### 1. Cloud Run — Scale to Zero for Frontend

- Set `minInstances=0` for the Vue frontend. Static assets are served by Nginx inside the container; cold start is <1 second.
- Keep `minInstances=1` only for the backend to avoid latency on first API call.
- Use **CPU throttling** (default) rather than "CPU always allocated" — you pay only when processing requests.

### 2. Cloud SQL — Right-Size the Instance

- Start with `db-g1-small` ($9/month). Upgrade only when query latency degrades.
- Enable **automatic storage increase** but set a max cap to avoid surprise bills.
- Use **Cloud SQL Insights** (free) to identify slow queries before scaling up.
- Enable **connection pooling** via PgBouncer or SQLAlchemy pool settings to reduce connection overhead on a small instance.

### 3. Memorystore — Use Basic Tier for Staging

- Basic tier (no replication) is sufficient for staging and early production.
- Only upgrade to Standard tier (replicated) when Redis availability becomes critical.
- Use Redis `EXPIRE` on all cached keys (already in `block_cache.py`) to keep memory usage low.

### 4. Cloud Storage — Lifecycle Policies

- The 14-day cleanup for `generated/` and 30-day for `uploads/` directly aligns with the platform's data retention policy and eliminates manual cleanup costs.
- Use **Nearline storage class** for `materials/` if they are accessed less than once per month.
- Enable **Object versioning off** on the media bucket to avoid retaining deleted object versions.

### 5. Cloud Build — Cache Docker Layers

```yaml
# In cloudbuild.yaml, use cache-from to speed up builds and reduce compute costs
- name: 'gcr.io/cloud-builders/docker'
  args:
    - 'build'
    - '--cache-from=asia-east1-docker.pkg.dev/$PROJECT_ID/vidgo/backend:latest'
    - '-t'
    - 'asia-east1-docker.pkg.dev/$PROJECT_ID/vidgo/backend:$SHORT_SHA'
    - './backend'
```

### 6. Networking — Minimize Egress Costs

- Cloud Run worker uses `--vpc-egress=all-traffic` to route AI API calls through Cloud NAT. This avoids public IP assignment costs per instance.
- Backend uses `--vpc-egress=private-ranges-only` (Cloud SQL, Redis traffic stays private; AI API calls go direct).
- Cloud CDN caches static frontend assets and `materials/` bucket content at edge — reduces Cloud Run invocations and storage egress.

### 7. Committed Use Discounts

- After 3 months of stable usage, purchase **1-year committed use** for Cloud SQL to save ~37%.
- Memorystore Standard tier also supports committed use discounts.

### 8. Monitoring & Budget Alerts

```bash
# Set a billing budget alert at $200/month to catch runaway costs
gcloud billing budgets create \
  --billing-account=BILLING_ACCOUNT_ID \
  --display-name="VidGo Monthly Budget" \
  --budget-amount=200USD \
  --threshold-rule=percent=50 \
  --threshold-rule=percent=90 \
  --threshold-rule=percent=100
```

---

## Monitoring & Observability

### Cloud Monitoring Dashboards

Key metrics to track:

| Metric | Service | Alert Threshold |
|---|---|---|
| Request latency (p99) | Cloud Run backend | > 5s |
| Instance count | Cloud Run all | Max instances reached |
| CPU utilization | Cloud SQL | > 80% |
| Memory utilization | Memorystore | > 80% |
| Error rate (5xx) | Cloud Run backend | > 1% |
| Storage egress | Cloud Storage | > 50 GB/day |

### Log-Based Metrics

```bash
# Create a metric for 5xx errors on backend
gcloud logging metrics create vidgo-5xx-errors \
  --description="5xx error rate on backend" \
  --log-filter='resource.type="cloud_run_revision" resource.labels.service_name="vidgo-backend" httpRequest.status>=500'
```

### Uptime Checks

```bash
gcloud monitoring uptime-checks create http vidgo-health-check \
  --display-name="VidGo API Health" \
  --uri="https://api.vidgo.ai/health" \
  --period=60
```

---

## Environment Tiers

| Setting | Local (Docker Compose) | Staging (GCP) | Production (GCP) |
|---|---|---|---|
| Cloud Run min instances | N/A | 0 / 0 / 0 | 1 / 0 / 1 (backend/frontend/worker) |
| Cloud SQL tier | postgres:15-alpine | db-g1-small | db-n1-standard-2 |
| Redis | redis:7-alpine | Memorystore 1GB Basic | Memorystore 5GB Standard |
| Cloud Armor | No | No | Yes |
| CDN | No | No | Yes |
| Min backend instances | N/A | 0 | 1 |
| `SKIP_PREGENERATION` | false | true | true |

---

## Quick Reference — Useful Commands

```bash
# View Cloud Run logs
gcloud run logs tail vidgo-backend --region=asia-east1

# Redeploy backend with new image tag
gcloud run deploy vidgo-backend \
  --image=asia-east1-docker.pkg.dev/$PROJECT/vidgo/backend:NEW_TAG \
  --region=asia-east1

# Connect to Cloud SQL from local (via proxy)
cloud-sql-proxy $PROJECT:asia-east1:vidgo-postgres &
psql -h 127.0.0.1 -U vidgo_user -d vidgo_db

# Update a secret value
echo -n "NEW_VALUE" | gcloud secrets versions add SECRET_NAME --data-file=-

# Force worker restart
gcloud run services update vidgo-worker --region=asia-east1 --no-traffic

# Check Cloud Run service URLs
gcloud run services list --region=asia-east1 --format="table(metadata.name,status.url)"
```
