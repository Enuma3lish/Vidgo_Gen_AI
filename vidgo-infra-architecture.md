# VidGo AI Platform - Infrastructure Architecture

**Version:** 3.0  
**Last Updated:** January 8, 2026  
**Cloud Provider:** Google Cloud Platform (GCP)  
**DNS Provider:** GoDaddy  
**Max Concurrent Users:** 1,000

---

## 1. Infrastructure Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        VidGo AI Infrastructure Architecture                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│   Internet                                                                           │
│       │                                                                              │
│       ▼                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                    GoDaddy DNS                                               │  │
│   │                                                                              │  │
│   │   vidgo.ai          → GCP Load Balancer IP                                  │  │
│   │   api.vidgo.ai      → GCP Load Balancer IP                                  │  │
│   │   www.vidgo.ai      → CNAME to vidgo.ai                                     │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                                 │
│                                    ▼                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                    GCP Cloud Load Balancer                                   │  │
│   │                                                                              │  │
│   │   • HTTPS termination (Managed SSL)                                         │  │
│   │   • DDoS protection                                                          │  │
│   │   • Global routing                                                           │  │
│   │   • Health checks                                                            │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                          │                    │                                      │
│                          ▼                    ▼                                      │
│   ┌──────────────────────────────┐  ┌──────────────────────────────┐              │
│   │     Cloud Run (Frontend)     │  │     Cloud Run (API)          │              │
│   │                              │  │                              │              │
│   │   • Vue 3 + Vite            │  │   • FastAPI                  │              │
│   │   • Static hosting          │  │   • Auto-scaling 0-10        │              │
│   │   • CDN caching             │  │   • 1000 concurrent limit    │              │
│   │   • Min: 0, Max: 5          │  │   • 2 vCPU, 2GB RAM          │              │
│   └──────────────────────────────┘  └──────────────────────────────┘              │
│                                                │                                     │
│                                                ▼                                     │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                           VPC Network                                        │  │
│   │                                                                              │  │
│   │   ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐   │  │
│   │   │   Cloud SQL        │  │   Memorystore      │  │   Cloud Storage    │   │  │
│   │   │   (PostgreSQL)     │  │   (Redis)          │  │   (Media Files)    │   │  │
│   │   │                    │  │                    │  │                    │   │  │
│   │   │   • db-g1-small    │  │   • Basic 1GB      │  │   • Standard       │   │  │
│   │   │   • 10GB SSD       │  │   • Cache + Queue  │  │   • asia-east1     │   │  │
│   │   │   • Auto backup    │  │   • Session store  │  │   • CDN enabled    │   │  │
│   │   └────────────────────┘  └────────────────────┘  └────────────────────┘   │  │
│   │                                                                              │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                         Monitoring Stack                                     │  │
│   │                                                                              │  │
│   │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │  │
│   │   │ Cloud        │  │ Cloud        │  │   Sentry     │  │  SendGrid    │   │  │
│   │   │ Monitoring   │  │ Logging      │  │   (Errors)   │  │  (Alerts)    │   │  │
│   │   └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │  │
│   │                                                                              │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. GKE vs Cloud Run Analysis

### 2.1 Comparison Table

| Factor | Cloud Run | GKE (Autopilot) | GKE (Standard) |
|--------|-----------|-----------------|----------------|
| **管理複雜度** | ⭐ 最低 | ⭐⭐ 中等 | ⭐⭐⭐ 最高 |
| **自動擴展** | ✅ 自動 (0-N) | ✅ 自動 | 需配置 |
| **冷啟動** | 有 (2-5秒) | 無 | 無 |
| **最小成本** | $0 (scale to zero) | ~$70/月 | ~$150/月 |
| **1000用戶預估** | ~$100-200/月 | ~$150-250/月 | ~$200-350/月 |
| **長連接/WebSocket** | 需配置 | ✅ 原生支援 | ✅ 原生支援 |
| **GPU 支援** | ❌ | ✅ | ✅ |
| **適合場景** | HTTP API, 突發流量 | 複雜微服務 | 完全控制 |

### 2.2 建議選擇

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       建議: Cloud Run (Serverless)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ✅ 選擇 Cloud Run 的原因:                                                  │
│                                                                             │
│  1. 成本效益最佳                                                            │
│     • Scale to zero = 閒置不收費                                            │
│     • 1000 並發在 Cloud Run 完全可以處理                                    │
│     • 預估月成本 $100-200 vs GKE $200+                                     │
│                                                                             │
│  2. 管理簡單                                                                │
│     • 無需管理 Kubernetes 集群                                              │
│     • 自動擴展、自動修復                                                    │
│     • 降低 DevOps 負擔                                                      │
│                                                                             │
│  3. VidGo 使用場景適合                                                      │
│     • AI 生成是異步任務 (HTTP request + polling/webhook)                    │
│     • 不需要 GPU (AI 在外部 API)                                            │
│     • 不需要長時間 WebSocket (可用 polling)                                 │
│                                                                             │
│  4. 未來可擴展                                                              │
│     • 如果需要可以遷移到 GKE                                                │
│     • Container 架構相同                                                    │
│                                                                             │
│  ❌ 不需要 GKE 的原因:                                                      │
│                                                                             │
│  1. 沒有自建 AI 模型需求 (使用外部 API)                                     │
│  2. 沒有複雜微服務架構                                                      │
│  3. 1000 用戶不需要 Kubernetes 複雜度                                       │
│  4. 預算考量 (Cloud Run 便宜 50%+)                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 何時考慮 GKE

```
考慮遷移到 GKE 的時機:
─────────────────────────────────────────────────────────────────────────────
• 用戶超過 10,000+ 並發
• 需要自建 AI 推論 (GPU nodes)
• 需要複雜的服務網格 (service mesh)
• 需要 StatefulSet (有狀態服務)
• WebSocket 成為核心功能
• DevOps 團隊有 K8s 經驗
```

---

## 3. GCP Resource Setup

### 3.1 Prerequisites

```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init

# Login and set project
gcloud auth login
gcloud config set project vidgo-ai-prod

# Enable required APIs
gcloud services enable \
    run.googleapis.com \
    sql-component.googleapis.com \
    sqladmin.googleapis.com \
    redis.googleapis.com \
    storage.googleapis.com \
    compute.googleapis.com \
    cloudresourcemanager.googleapis.com \
    secretmanager.googleapis.com \
    monitoring.googleapis.com \
    logging.googleapis.com
```

### 3.2 Create Infrastructure

```bash
# ─────────────────────────────────────────────────────────────────────────────
# 1. CREATE VPC NETWORK
# ─────────────────────────────────────────────────────────────────────────────
gcloud compute networks create vidgo-vpc \
    --subnet-mode=auto \
    --bgp-routing-mode=regional

# Create VPC connector for Cloud Run
gcloud compute networks vpc-access connectors create vidgo-connector \
    --region=asia-east1 \
    --network=vidgo-vpc \
    --range=10.8.0.0/28

# ─────────────────────────────────────────────────────────────────────────────
# 2. CREATE CLOUD SQL (PostgreSQL)
# ─────────────────────────────────────────────────────────────────────────────
gcloud sql instances create vidgo-db \
    --database-version=POSTGRES_15 \
    --tier=db-g1-small \
    --region=asia-east1 \
    --storage-size=10GB \
    --storage-type=SSD \
    --storage-auto-increase \
    --backup-start-time=03:00 \
    --availability-type=zonal \
    --network=vidgo-vpc \
    --no-assign-ip

# Create database
gcloud sql databases create vidgo --instance=vidgo-db

# Create user
gcloud sql users create vidgo_user \
    --instance=vidgo-db \
    --password="$(openssl rand -base64 32)"

# ─────────────────────────────────────────────────────────────────────────────
# 3. CREATE MEMORYSTORE (Redis)
# ─────────────────────────────────────────────────────────────────────────────
gcloud redis instances create vidgo-redis \
    --size=1 \
    --region=asia-east1 \
    --redis-version=redis_7_0 \
    --network=vidgo-vpc \
    --tier=basic

# ─────────────────────────────────────────────────────────────────────────────
# 4. CREATE CLOUD STORAGE BUCKET
# ─────────────────────────────────────────────────────────────────────────────
gsutil mb -p vidgo-ai-prod -l asia-east1 gs://vidgo-media-prod

# Set CORS
cat > cors.json << EOF
[
  {
    "origin": ["https://vidgo.ai", "https://api.vidgo.ai"],
    "method": ["GET", "PUT", "POST", "DELETE"],
    "responseHeader": ["Content-Type"],
    "maxAgeSeconds": 3600
  }
]
EOF
gsutil cors set cors.json gs://vidgo-media-prod

# Enable CDN
gsutil web set -m index.html -e 404.html gs://vidgo-media-prod

# ─────────────────────────────────────────────────────────────────────────────
# 5. CREATE SECRETS
# ─────────────────────────────────────────────────────────────────────────────
# Store sensitive data in Secret Manager
echo -n "your-secret-key" | gcloud secrets create SECRET_KEY --data-file=-
echo -n "your-piapi-key" | gcloud secrets create PIAPI_API_KEY --data-file=-
echo -n "your-pollo-key" | gcloud secrets create POLLO_API_KEY --data-file=-
echo -n "your-a2e-key" | gcloud secrets create A2E_API_KEY --data-file=-
echo -n "your-gemini-key" | gcloud secrets create GEMINI_API_KEY --data-file=-
echo -n "your-paddle-key" | gcloud secrets create PADDLE_API_KEY --data-file=-
echo -n "your-paddle-webhook-secret" | gcloud secrets create PADDLE_WEBHOOK_SECRET --data-file=-
echo -n "your-sendgrid-key" | gcloud secrets create SENDGRID_API_KEY --data-file=-

# ─────────────────────────────────────────────────────────────────────────────
# 6. RESERVE STATIC IP
# ─────────────────────────────────────────────────────────────────────────────
gcloud compute addresses create vidgo-ip --global

# Get the IP address
gcloud compute addresses describe vidgo-ip --global --format="get(address)"
# Output: 34.xxx.xxx.xxx (use this for GoDaddy DNS)
```

### 3.3 Deploy Cloud Run Services

```bash
# ─────────────────────────────────────────────────────────────────────────────
# BUILD AND PUSH DOCKER IMAGES
# ─────────────────────────────────────────────────────────────────────────────

# Backend API
cd vidgo-backend
docker build -t asia-east1-docker.pkg.dev/vidgo-ai-prod/vidgo/api:latest .
docker push asia-east1-docker.pkg.dev/vidgo-ai-prod/vidgo/api:latest

# Frontend
cd vidgo-frontend
npm run build
docker build -t asia-east1-docker.pkg.dev/vidgo-ai-prod/vidgo/web:latest .
docker push asia-east1-docker.pkg.dev/vidgo-ai-prod/vidgo/web:latest

# ─────────────────────────────────────────────────────────────────────────────
# DEPLOY API SERVICE
# ─────────────────────────────────────────────────────────────────────────────
gcloud run deploy vidgo-api \
    --image=asia-east1-docker.pkg.dev/vidgo-ai-prod/vidgo/api:latest \
    --region=asia-east1 \
    --platform=managed \
    --allow-unauthenticated \
    --vpc-connector=vidgo-connector \
    --set-env-vars="ENVIRONMENT=production" \
    --set-secrets="SECRET_KEY=SECRET_KEY:latest,PIAPI_API_KEY=PIAPI_API_KEY:latest,POLLO_API_KEY=POLLO_API_KEY:latest,A2E_API_KEY=A2E_API_KEY:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest,PADDLE_API_KEY=PADDLE_API_KEY:latest,PADDLE_WEBHOOK_SECRET=PADDLE_WEBHOOK_SECRET:latest,SENDGRID_API_KEY=SENDGRID_API_KEY:latest" \
    --add-cloudsql-instances=vidgo-ai-prod:asia-east1:vidgo-db \
    --cpu=2 \
    --memory=2Gi \
    --min-instances=1 \
    --max-instances=10 \
    --concurrency=100 \
    --timeout=300

# ─────────────────────────────────────────────────────────────────────────────
# DEPLOY FRONTEND SERVICE
# ─────────────────────────────────────────────────────────────────────────────
gcloud run deploy vidgo-web \
    --image=asia-east1-docker.pkg.dev/vidgo-ai-prod/vidgo/web:latest \
    --region=asia-east1 \
    --platform=managed \
    --allow-unauthenticated \
    --cpu=1 \
    --memory=512Mi \
    --min-instances=0 \
    --max-instances=5 \
    --concurrency=200

# ─────────────────────────────────────────────────────────────────────────────
# SETUP LOAD BALANCER WITH SSL
# ─────────────────────────────────────────────────────────────────────────────

# Create serverless NEG for API
gcloud compute network-endpoint-groups create vidgo-api-neg \
    --region=asia-east1 \
    --network-endpoint-type=serverless \
    --cloud-run-service=vidgo-api

# Create serverless NEG for Web
gcloud compute network-endpoint-groups create vidgo-web-neg \
    --region=asia-east1 \
    --network-endpoint-type=serverless \
    --cloud-run-service=vidgo-web

# Create backend services
gcloud compute backend-services create vidgo-api-backend \
    --global \
    --load-balancing-scheme=EXTERNAL_MANAGED

gcloud compute backend-services add-backend vidgo-api-backend \
    --global \
    --network-endpoint-group=vidgo-api-neg \
    --network-endpoint-group-region=asia-east1

gcloud compute backend-services create vidgo-web-backend \
    --global \
    --load-balancing-scheme=EXTERNAL_MANAGED

gcloud compute backend-services add-backend vidgo-web-backend \
    --global \
    --network-endpoint-group=vidgo-web-neg \
    --network-endpoint-group-region=asia-east1

# Create URL map
gcloud compute url-maps create vidgo-lb \
    --default-service=vidgo-web-backend

# Add path rules for API
gcloud compute url-maps add-path-matcher vidgo-lb \
    --path-matcher-name=api-matcher \
    --default-service=vidgo-api-backend \
    --path-rules="/api/*=vidgo-api-backend"

gcloud compute url-maps add-host-rule vidgo-lb \
    --hosts="api.vidgo.ai" \
    --path-matcher-name=api-matcher

# Create SSL certificate
gcloud compute ssl-certificates create vidgo-ssl \
    --domains="vidgo.ai,www.vidgo.ai,api.vidgo.ai" \
    --global

# Create HTTPS proxy
gcloud compute target-https-proxies create vidgo-https-proxy \
    --url-map=vidgo-lb \
    --ssl-certificates=vidgo-ssl

# Create forwarding rule
gcloud compute forwarding-rules create vidgo-https-rule \
    --global \
    --target-https-proxy=vidgo-https-proxy \
    --ports=443 \
    --address=vidgo-ip
```

---

## 4. GoDaddy DNS Configuration

### 4.1 DNS Records Setup

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         GoDaddy DNS Configuration                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Domain: vidgo.ai                                                           │
│  GCP Static IP: 34.xxx.xxx.xxx (from gcloud compute addresses describe)    │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────────┐│
│  │  DNS Records                                                           ││
│  │  ─────────────────────────────────────────────────────────────────────││
│  │                                                                        ││
│  │  Type    Name    Value                        TTL                     ││
│  │  ────    ────    ─────                        ───                     ││
│  │  A       @       34.xxx.xxx.xxx               600                     ││
│  │  A       api     34.xxx.xxx.xxx               600                     ││
│  │  A       www     34.xxx.xxx.xxx               600                     ││
│  │  CNAME   www     @                            600 (alternative)       ││
│  │                                                                        ││
│  │  Optional: Email records                                              ││
│  │  TXT     @       v=spf1 include:_spf.google.com ~all                 ││
│  │  MX      @       10 mx.example.com                                    ││
│  │                                                                        ││
│  └────────────────────────────────────────────────────────────────────────┘│
│                                                                             │
│  Setup Steps:                                                               │
│  ─────────────────────────────────────────────────────────────────────────│
│                                                                             │
│  1. Login to GoDaddy: https://dcc.godaddy.com/                            │
│                                                                             │
│  2. Select domain: vidgo.ai                                                │
│                                                                             │
│  3. Go to "DNS Management"                                                 │
│                                                                             │
│  4. Edit A Record (Type A):                                               │
│     • Name: @ (or leave blank for root)                                   │
│     • Value: 34.xxx.xxx.xxx (GCP static IP)                              │
│     • TTL: 600 seconds                                                    │
│                                                                             │
│  5. Add A Record for API:                                                  │
│     • Name: api                                                           │
│     • Value: 34.xxx.xxx.xxx                                              │
│     • TTL: 600 seconds                                                    │
│                                                                             │
│  6. Add A Record for WWW:                                                  │
│     • Name: www                                                           │
│     • Value: 34.xxx.xxx.xxx                                              │
│     • TTL: 600 seconds                                                    │
│                                                                             │
│  7. Save changes                                                           │
│                                                                             │
│  8. Wait for propagation (5-30 minutes)                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 GoDaddy Configuration Steps (GUI)

```
Step-by-Step GoDaddy DNS Setup:
═════════════════════════════════════════════════════════════════════════════

1. Login to GoDaddy
   └── https://sso.godaddy.com/

2. Navigate to DNS Management
   └── My Products → Domains → vidgo.ai → DNS

3. Modify A Record (Root Domain)
   ┌─────────────────────────────────────────────────────────────────────┐
   │ Type: A                                                              │
   │ Name: @                                                              │
   │ Value: 34.xxx.xxx.xxx  ← GCP Load Balancer IP                       │
   │ TTL: 600 seconds (10 minutes)                                       │
   └─────────────────────────────────────────────────────────────────────┘

4. Add A Record (API Subdomain)
   ┌─────────────────────────────────────────────────────────────────────┐
   │ Type: A                                                              │
   │ Name: api                                                            │
   │ Value: 34.xxx.xxx.xxx  ← Same GCP Load Balancer IP                  │
   │ TTL: 600 seconds                                                     │
   └─────────────────────────────────────────────────────────────────────┘

5. Add A Record (WWW Subdomain)
   ┌─────────────────────────────────────────────────────────────────────┐
   │ Type: A                                                              │
   │ Name: www                                                            │
   │ Value: 34.xxx.xxx.xxx                                               │
   │ TTL: 600 seconds                                                     │
   └─────────────────────────────────────────────────────────────────────┘

6. Verify Configuration
   └── Wait 5-30 minutes for DNS propagation
   └── Test: nslookup vidgo.ai
   └── Test: curl -I https://vidgo.ai
   └── Test: curl -I https://api.vidgo.ai/health

7. SSL Certificate Provisioning
   └── GCP will automatically provision SSL after DNS propagation
   └── Check status: gcloud compute ssl-certificates describe vidgo-ssl
   └── Usually takes 15-60 minutes
```

### 4.3 Verify DNS Configuration

```bash
# Check DNS propagation
nslookup vidgo.ai
nslookup api.vidgo.ai
nslookup www.vidgo.ai

# Check from different DNS servers
nslookup vidgo.ai 8.8.8.8  # Google DNS
nslookup vidgo.ai 1.1.1.1  # Cloudflare DNS

# Check SSL certificate status
gcloud compute ssl-certificates describe vidgo-ssl --global

# Test endpoints
curl -I https://vidgo.ai
curl -I https://api.vidgo.ai/health
```

---

## 5. Docker Configuration

### 5.1 Backend Dockerfile

```dockerfile
# docker/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Set environment
ENV PYTHONPATH=/app
ENV PORT=8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run with Gunicorn
CMD exec gunicorn --bind :$PORT --workers 2 --threads 4 --timeout 300 \
    --worker-class uvicorn.workers.UvicornWorker app.main:app
```

### 5.2 Frontend Dockerfile

```dockerfile
# vidgo-frontend/Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
```

### 5.3 Frontend Nginx Config

```nginx
# vidgo-frontend/nginx.conf
events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    server {
        listen 8080;
        server_name _;
        root /usr/share/nginx/html;
        index index.html;

        # Gzip compression
        gzip on;
        gzip_types text/plain text/css application/json application/javascript;

        # SPA routing
        location / {
            try_files $uri $uri/ /index.html;
        }

        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }

        # Health check
        location /health {
            return 200 'OK';
            add_header Content-Type text/plain;
        }
    }
}
```

---

## 6. Monitoring Setup

### 6.1 Cloud Monitoring Dashboard

```bash
# Create custom dashboard
gcloud monitoring dashboards create --config-from-file=dashboard.json
```

```json
// dashboard.json
{
  "displayName": "VidGo AI Monitoring",
  "mosaicLayout": {
    "columns": 12,
    "tiles": [
      {
        "width": 4,
        "height": 4,
        "widget": {
          "title": "API Request Rate",
          "xyChart": {
            "dataSets": [{
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_count\"",
                  "aggregation": {
                    "alignmentPeriod": "60s",
                    "perSeriesAligner": "ALIGN_RATE"
                  }
                }
              }
            }]
          }
        }
      },
      {
        "width": 4,
        "height": 4,
        "widget": {
          "title": "API Latency (p95)",
          "xyChart": {
            "dataSets": [{
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_latencies\"",
                  "aggregation": {
                    "alignmentPeriod": "60s",
                    "perSeriesAligner": "ALIGN_PERCENTILE_95"
                  }
                }
              }
            }]
          }
        }
      },
      {
        "width": 4,
        "height": 4,
        "widget": {
          "title": "Error Rate",
          "xyChart": {
            "dataSets": [{
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class!=\"2xx\"",
                  "aggregation": {
                    "alignmentPeriod": "60s",
                    "perSeriesAligner": "ALIGN_RATE"
                  }
                }
              }
            }]
          }
        }
      }
    ]
  }
}
```

### 6.2 Alert Policies

```bash
# Create alert for high error rate
gcloud alpha monitoring policies create \
    --display-name="VidGo API High Error Rate" \
    --condition-display-name="Error rate > 5%" \
    --condition-filter='resource.type="cloud_run_revision" AND metric.type="run.googleapis.com/request_count" AND metric.labels.response_code_class!="2xx"' \
    --condition-threshold-value=0.05 \
    --condition-threshold-comparison=COMPARISON_GT \
    --notification-channels="projects/vidgo-ai-prod/notificationChannels/xxx"

# Create alert for provider failure
gcloud alpha monitoring policies create \
    --display-name="VidGo Provider Down" \
    --condition-display-name="Provider health check failed" \
    --condition-filter='resource.type="cloud_run_revision" AND metric.type="custom.googleapis.com/vidgo/provider_status"' \
    --condition-threshold-value=0 \
    --condition-threshold-comparison=COMPARISON_EQ \
    --notification-channels="projects/vidgo-ai-prod/notificationChannels/xxx"
```

---

## 7. Complete Cost Analysis

### 7.1 Infrastructure Costs (Monthly)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GCP Infrastructure Costs (1,000 Users)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Service                        Specs                     Monthly Cost      │
│  ─────────────────────────────────────────────────────────────────────────│
│                                                                             │
│  Cloud Run (API)                                                            │
│  ├── Min instances: 1          2 vCPU, 2GB RAM           $35-50           │
│  ├── Max instances: 10         ~10K requests/instance                      │
│  └── Estimated usage           ~500K requests/month                        │
│                                                                             │
│  Cloud Run (Frontend)                                                       │
│  ├── Min instances: 0          1 vCPU, 512MB RAM         $5-15            │
│  └── Max instances: 5          Static hosting                              │
│                                                                             │
│  Cloud SQL (PostgreSQL)                                                     │
│  ├── Instance: db-g1-small     1 vCPU, 1.7GB RAM         $25-35           │
│  ├── Storage: 10GB SSD                                   $2               │
│  └── Backup: 7 days                                      $1               │
│                                                                             │
│  Memorystore (Redis)                                                        │
│  └── Basic 1GB                 asia-east1                $35              │
│                                                                             │
│  Cloud Storage                                                              │
│  ├── Standard: ~50GB           Media files               $1-2             │
│  ├── Operations                ~100K/month               $0.50            │
│  └── Egress                    ~100GB/month              $8-12            │
│                                                                             │
│  Load Balancer                                                              │
│  ├── Forwarding rule           HTTPS                     $18              │
│  └── Data processing           ~500GB/month              $4               │
│                                                                             │
│  Cloud Monitoring & Logging                                                 │
│  └── Basic usage               Included in free tier     $0-5             │
│                                                                             │
│  Static IP                                                                  │
│  └── Reserved address          1 IP                      $7               │
│                                                                             │
│  Secret Manager                                                             │
│  └── 10 secrets                ~10K accesses/month       $0.50            │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────│
│  GCP Infrastructure Subtotal                             $142-192         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 AI Service Costs (Monthly)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      AI Service Costs (1,000 Users)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Assumptions:                                                               │
│  ├── 1,000 active users/month                                              │
│  ├── Average 10 generations/user/month                                     │
│  ├── Mix: 40% T2I, 30% I2V, 15% V2V, 10% Interior, 5% Avatar              │
│  └── Total: 10,000 generations/month                                       │
│                                                                             │
│  Service                        Volume          Unit Price    Monthly Cost  │
│  ─────────────────────────────────────────────────────────────────────────│
│                                                                             │
│  PiAPI (Wan API) - Primary                                                  │
│  ├── Wan T2I                   4,000 images    $0.006       $24           │
│  ├── Wan I2V (5s)              3,000 videos    $0.014       $42           │
│  ├── Wan Interior (Doodle)     1,000 images    $0.008       $8            │
│  └── PiAPI Pro Plan            1 month         $60          $60           │
│  PiAPI Subtotal                                             $134          │
│                                                                             │
│  A2E.ai (Avatar)                                                           │
│  ├── Pro Plan                  1 month         $9.90        $10           │
│  └── Usage                     500 minutes     $0.10/min    $50           │
│  A2E Subtotal                                               $60           │
│                                                                             │
│  Pollo.ai (Backup + Advanced)                                              │
│  └── Backup usage (~10%)       1,000 gen       $0.15        $150          │
│                                                                             │
│  Gemini API (Moderation)                                                    │
│  └── Flash 2.5                 10,000 calls    ~$0.001      $10           │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────│
│  AI Services Subtotal                                       $354          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.3 Third-Party Services Costs

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Third-Party Services (Monthly)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Service                        Plan              Monthly Cost              │
│  ─────────────────────────────────────────────────────────────────────────│
│                                                                             │
│  Paddle (Payment)               Standard          2.5% + $0.25/tx          │
│  ├── Estimated revenue          $15,000           ~$400                    │
│  └── Note: This is revenue share, not cost                                 │
│                                                                             │
│  SendGrid (Email)               Free tier         $0                       │
│  └── 100 emails/day             3,000/month       Free                     │
│                                                                             │
│  Sentry (Error Tracking)        Team              $26                      │
│  └── 50K events/month                                                      │
│                                                                             │
│  GoDaddy Domain                 Annual            $20/year ≈ $2/month     │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────│
│  Third-Party Subtotal                             $28                      │
│  (Paddle fees separate)                                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.4 Total Monthly Cost Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VidGo Total Cost Summary (1,000 Users)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Category                                          Monthly Cost             │
│  ─────────────────────────────────────────────────────────────────────────│
│                                                                             │
│  GCP Infrastructure                                $142 - $192             │
│  ├── Cloud Run (API + Web)                         $40 - $65               │
│  ├── Cloud SQL                                     $28 - $38               │
│  ├── Memorystore Redis                             $35                     │
│  ├── Cloud Storage + CDN                           $10 - $15               │
│  ├── Load Balancer + SSL                           $22                     │
│  └── Monitoring + Others                           $7 - $17                │
│                                                                             │
│  AI Services                                       $354                    │
│  ├── PiAPI (Wan) - Primary                         $134                    │
│  ├── A2E.ai (Avatar)                               $60                     │
│  ├── Pollo.ai (Backup)                             $150                    │
│  └── Gemini (Moderation)                           $10                     │
│                                                                             │
│  Third-Party Services                              $28                     │
│  ├── Sentry                                        $26                     │
│  └── GoDaddy Domain                                $2                      │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────│
│                                                                             │
│  TOTAL MONTHLY COST                                $524 - $574             │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────│
│                                                                             │
│  Revenue Analysis (1,000 Users):                                           │
│  ├── Starter (40%): 400 × $9.9 =                   $3,960                 │
│  ├── Pro (40%): 400 × $29 =                        $11,600                │
│  ├── Pro+ (20%): 200 × $49 =                       $9,800                 │
│  └── Total Revenue:                                $25,360                │
│                                                                             │
│  Paddle Fees (2.5% + $0.25):                                               │
│  └── ~$650 + ~$250 =                               ~$900                  │
│                                                                             │
│  NET REVENUE                                       $25,360 - $900         │
│                                                     = $24,460              │
│                                                                             │
│  GROSS PROFIT                                      $24,460 - $550         │
│                                                     = $23,910              │
│                                                                             │
│  GROSS MARGIN                                      ~94%                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.5 Cost Per User Analysis

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Cost Per User Analysis                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Per User Metrics (1,000 Users):                                           │
│                                                                             │
│  Average Cost per User:        $550 / 1000 = $0.55/user/month             │
│  Average Revenue per User:     $25,360 / 1000 = $25.36/user/month         │
│  Net Profit per User:          $23,910 / 1000 = $23.91/user/month         │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────│
│                                                                             │
│  Per Plan Profitability:                                                   │
│                                                                             │
│  Plan       Revenue    Est. Cost    Profit    Margin                       │
│  ─────────────────────────────────────────────────────────────────────────│
│  Starter    $9.90      $2.50        $7.40     75%                         │
│  Pro        $29.00     $8.00        $21.00    72%                         │
│  Pro+       $49.00     $15.00       $34.00    69%                         │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────│
│                                                                             │
│  Breakeven Analysis:                                                       │
│                                                                             │
│  Fixed Costs (Monthly):        ~$200 (min infrastructure)                  │
│  Variable Cost per Gen:        ~$0.04                                      │
│  Average Revenue per Gen:      ~$0.25                                      │
│  Contribution Margin:          ~$0.21/generation                           │
│                                                                             │
│  Breakeven Users:              $200 / $23 = ~9 users                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Deployment Checklist

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      VidGo Deployment Checklist                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Pre-Deployment:                                                            │
│  □ GCP project created and billing enabled                                 │
│  □ All required APIs enabled                                               │
│  □ GoDaddy domain purchased                                                │
│  □ Paddle account created and configured                                   │
│  □ All API keys obtained (PiAPI, Pollo, A2E, Gemini)                      │
│  □ SendGrid account created                                                │
│  □ Sentry project created                                                  │
│                                                                             │
│  Infrastructure Setup:                                                      │
│  □ VPC network created                                                     │
│  □ Cloud SQL instance created                                              │
│  □ Memorystore Redis created                                               │
│  □ Cloud Storage bucket created                                            │
│  □ Static IP reserved                                                      │
│  □ All secrets stored in Secret Manager                                    │
│                                                                             │
│  Application Deployment:                                                    │
│  □ Docker images built and pushed                                          │
│  □ Cloud Run services deployed                                             │
│  □ Load balancer configured                                                │
│  □ SSL certificate provisioned                                             │
│                                                                             │
│  DNS Configuration:                                                         │
│  □ A records added in GoDaddy                                              │
│  □ DNS propagation verified                                                │
│  □ SSL certificate active                                                  │
│  □ HTTPS working for all domains                                           │
│                                                                             │
│  Post-Deployment:                                                          │
│  □ Health checks passing                                                   │
│  □ API endpoints responding                                                │
│  □ Database migrations applied                                             │
│  □ Demo materials pre-generated                                            │
│  □ Monitoring dashboard configured                                         │
│  □ Alert policies created                                                  │
│  □ Paddle webhooks verified                                                │
│  □ Email sending tested                                                    │
│                                                                             │
│  Testing:                                                                   │
│  □ User registration flow                                                  │
│  □ Subscription payment flow                                               │
│  □ Subscription cancellation flow                                          │
│  □ All generation features                                                 │
│  □ Provider failover                                                       │
│  □ Alert notifications                                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Quick Reference Commands

```bash
# ─────────────────────────────────────────────────────────────────────────────
# DEPLOYMENT
# ─────────────────────────────────────────────────────────────────────────────

# Deploy API
gcloud run deploy vidgo-api --image=asia-east1-docker.pkg.dev/vidgo-ai-prod/vidgo/api:latest --region=asia-east1

# Deploy Frontend
gcloud run deploy vidgo-web --image=asia-east1-docker.pkg.dev/vidgo-ai-prod/vidgo/web:latest --region=asia-east1

# ─────────────────────────────────────────────────────────────────────────────
# MONITORING
# ─────────────────────────────────────────────────────────────────────────────

# View logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=vidgo-api" --limit=100

# Check service status
gcloud run services describe vidgo-api --region=asia-east1

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────────────────────

# Connect to database
gcloud sql connect vidgo-db --user=vidgo_user --database=vidgo

# ─────────────────────────────────────────────────────────────────────────────
# TROUBLESHOOTING
# ─────────────────────────────────────────────────────────────────────────────

# Check SSL certificate status
gcloud compute ssl-certificates describe vidgo-ssl --global

# Check load balancer
gcloud compute forwarding-rules describe vidgo-https-rule --global

# Test DNS
dig vidgo.ai
dig api.vidgo.ai
```

---

*Document Version: 3.0*  
*Last Updated: January 8, 2026*
