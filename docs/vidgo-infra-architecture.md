# VidGo AI Platform - Infrastructure Architecture

> Last updated: 2026-06-12

**Version:** 4.0
**Cloud Provider:** Google Cloud Platform (GCP) — project `vidgo-ai`, region `asia-east1`
**DNS Provider:** GoDaddy (domain `vidgo.co`)
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
│   │                    GoDaddy DNS (vidgo.co)                                    │  │
│   │                                                                              │  │
│   │   vidgo.co          → Cloud Run domain mapping → vidgo-frontend             │  │
│   │   api.vidgo.co      → Cloud Run domain mapping → vidgo-backend              │  │
│   │   app.vidgo.co      → Cloud Run domain mapping → vidgo-frontend (pending)   │  │
│   │                                                                              │  │
│   │   No GCP Load Balancer — Cloud Run domain mappings handle TLS directly.     │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                          │                    │                                      │
│                          ▼                    ▼                                      │
│   ┌──────────────────────────────┐  ┌──────────────────────────────┐               │
│   │   Cloud Run: vidgo-frontend  │  │   Cloud Run: vidgo-backend   │               │
│   │                              │  │                              │               │
│   │   • Vue 3 + Vite → nginx     │  │   • FastAPI (uvicorn)        │               │
│   │   • /api proxied to backend  │  │   • Min: 1, Max: 10          │               │
│   │   • Min: 0, Max: 4           │  │   • 1 vCPU, 2Gi RAM          │               │
│   │   • 1 vCPU, 256Mi RAM        │  │   • concurrency 80           │               │
│   │   • port 80                  │  │   • timeout 3600s, port 8000 │               │
│   └──────────────────────────────┘  └──────────────────────────────┘               │
│                                                │                                     │
│   ┌──────────────────────────────┐             │                                     │
│   │   Cloud Run: vidgo-worker    │◄────────────┤  (same backend image,               │
│   │                              │             │   custom command:                   │
│   │   • ARQ background worker    │             │   `python -m http.server 8000 &     │
│   │   • Min: 1, Max: 2           │             │    exec arq                          │
│   │   • 1 vCPU, 512Mi RAM        │             │    app.worker.WorkerSettings`)      │
│   │   • --no-cpu-throttling      │             │                                     │
│   └──────────────────────────────┘             │                                     │
│                          │                     │                                     │
│                          ▼                     ▼                                     │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │              VPC `vidgo-vpc` (via connector `vidgo-connector`)               │  │
│   │                                                                              │  │
│   │   ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐    │  │
│   │   │   Cloud SQL        │  │   Memorystore      │  │   Cloud Storage    │    │  │
│   │   │   `prod-db`        │  │   `vidgo-redis`    │  │   `vidgo-media-    │    │  │
│   │   │                    │  │                    │  │    vidgo-ai`       │    │  │
│   │   │   • PostgreSQL 15  │  │   • Basic 1GB      │  │   • static/ +      │    │  │
│   │   │   • db-f1-micro    │  │   • 10.24.105.251  │  │     generated/     │    │  │
│   │   │   • PRIVATE IP only│  │   • Cache + ARQ    │  │   • asia-east1     │    │  │
│   │   │     10.70.0.3      │  │     queue          │  │   • public media   │    │  │
│   │   └────────────────────┘  └────────────────────┘  └────────────────────┘    │  │
│   │                                                                              │  │
│   │   Cloud NAT static egress IP: 35.201.182.131 (`vidgo-nat-ip`)               │  │
│   │   — fixed outbound IP for ECPay / Giveme allowlisting                       │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                       External AI Providers (REST only)                      │  │
│   │                                                                              │  │
│   │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │  │
│   │   │   PiAPI      │  │  Vertex AI   │  │   Pollo.ai   │  │   A2E.ai     │    │  │
│   │   │  (PRIMARY)   │  │ (ADC backup) │  │ (I2V backup) │  │  (avatar)    │    │  │
│   │   └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

Key facts (verified against live `gcloud` state on 2026-06-12):

| Resource | Value |
|----------|-------|
| GCP project | `vidgo-ai` |
| Region | `asia-east1` |
| Cloud Run services | `vidgo-backend`, `vidgo-worker`, `vidgo-frontend` |
| Artifact Registry | `asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images` |
| Cloud SQL | `prod-db` (POSTGRES_15, db-f1-micro, **private IP only** `10.70.0.3`) |
| Memorystore Redis | `vidgo-redis` (Basic 1GB, `10.24.105.251:6379`, network `vidgo-vpc`) |
| VPC connector | `vidgo-connector` (`vidgo-vpc`, `10.8.0.0/28`, egress `all-traffic`) |
| Media bucket | `gs://vidgo-media-vidgo-ai` |
| Service accounts | `vidgo-backend@vidgo-ai.iam.gserviceaccount.com` (backend), `vidgo-worker@vidgo-ai.iam.gserviceaccount.com` (worker) |

Notes:
- `DATABASE_URL` and `REDIS_URL` come from **Secret Manager** (mounted as env vars); the DB is reached over its private IP through the VPC connector.
- Both backend and worker carry the `run.googleapis.com/cloudsql-instances` annotation `vidgo-ai:asia-east1:prod-db,vidgo-ai:asia-east1:vidgo-db`. The `vidgo-db` instance **no longer exists** (deleted); the annotation entry is a harmless leftover — the live connection uses `prod-db` private IP, not the SQL Auth Proxy socket.
- `vidgo-worker` runs the **backend image** with a custom command (`python -m http.server 8000 & exec arq app.worker.WorkerSettings`) — the dummy HTTP server satisfies Cloud Run's port health check while ARQ consumes the Redis queue.

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

### 2.2 選擇結果

VidGo 已採用 **Cloud Run (Serverless)** 並在生產環境運行:

```
✅ 選擇 Cloud Run 的原因 (已驗證):

1. 成本效益最佳
   • backend min=1 保持暖機, frontend scale-to-zero
   • 1000 並發在 Cloud Run 完全可以處理

2. 管理簡單
   • 無需管理 Kubernetes 集群
   • 自動擴展、自動修復、revision-based rollback

3. VidGo 使用場景適合
   • AI 生成是異步任務 (ARQ worker + polling)
   • 不需要 GPU (AI 在外部 API: PiAPI / Vertex AI / Pollo / A2E)
   • 不需要長時間 WebSocket (使用 polling / SSE)

❌ 不需要 GKE 的原因:

1. 沒有自建 AI 模型需求 (使用外部 API)
2. 沒有複雜微服務架構 (3 個 Cloud Run services)
3. 1000 用戶不需要 Kubernetes 複雜度
```

### 2.3 何時考慮 GKE

```
考慮遷移到 GKE 的時機:
─────────────────────────────────────────────────────────────────────────────
• 用戶超過 10,000+ 並發
• 需要自建 AI 推論 (GPU nodes)
• 需要複雜的服務網格 (service mesh)
• WebSocket 成為核心功能
• DevOps 團隊有 K8s 經驗
```

---

## 3. GCP Resources (As Built)

### 3.1 Cloud Run Services

| Setting | `vidgo-backend` | `vidgo-worker` | `vidgo-frontend` |
|---------|-----------------|----------------|------------------|
| Image | `…/vidgo-images/vidgo-backend:<TAG>` | same backend image | `…/vidgo-images/vidgo-frontend:<TAG>` |
| Command | default (uvicorn via entrypoint) | `/bin/bash -c "python -m http.server 8000 & exec arq app.worker.WorkerSettings"` | nginx |
| CPU / Memory | 1 vCPU / 2Gi | 1 vCPU / 512Mi (`--no-cpu-throttling`) | 1 vCPU / 256Mi |
| Scaling | min 1 / max 10 | min 1 / max 2 | min 0 / max 4 |
| Concurrency | 80 | 80 | default |
| Timeout | 3600s | 300s | default |
| Port | 8000 | 8000 (dummy health server) | 80 |
| Ingress / auth | all, `--allow-unauthenticated` | `--no-allow-unauthenticated` | all, `--allow-unauthenticated` |
| VPC | `vidgo-connector`, egress all-traffic | `vidgo-connector`, egress all-traffic | none |
| Service account | `vidgo-backend@vidgo-ai.iam` | `vidgo-worker@vidgo-ai.iam` | default |

Notable env vars on backend/worker (non-secret): `SKIP_PREGENERATION=true`, `SKIP_DEPENDENCY_CHECK=true`, `GCS_BUCKET=vidgo-media-vidgo-ai`, `VERTEX_AI_PROJECT=vidgo-ai`, `VERTEX_AI_LOCATION=asia-east1`, `GEMINI_MODEL=gemini-2.5-flash`, `GEMINI_IMAGE_MODEL=gemini-2.5-flash-image`, `VEO_MODEL=veo-3.0-fast-generate-001`, `FRONTEND_URL=https://vidgo.co`, `BACKEND_URL=https://api.vidgo.co`, `ECPAY_ENV=production`, `PAYPAL_ENV=production`, `GIVEME_ENABLED=true`.

Frontend env: `BACKEND_URL=https://vidgo-backend-r2laip67ma-de.a.run.app` (substituted into the nginx template so `/api/*` is proxied server-side to the backend).

### 3.2 Networking

```bash
# VPC + connector (existing — reference only)
# vidgo-vpc, connector vidgo-connector: 10.8.0.0/28, 2-3 instances, READY
gcloud compute networks vpc-access connectors describe vidgo-connector \
    --region=asia-east1 --project=vidgo-ai

# Cloud NAT static egress IP (for ECPay / Giveme IP allowlists)
# vidgo-nat-ip = 35.201.182.131
gcloud compute addresses list --project=vidgo-ai
```

There is **no GCP HTTPS Load Balancer, no serverless NEGs, no reserved global IP** — public traffic terminates directly on Cloud Run via domain mappings (Section 4).

### 3.3 Data Stores

```bash
# Cloud SQL — PostgreSQL 15, private IP only (10.70.0.3), no public IP
gcloud sql instances describe prod-db --project=vidgo-ai

# Memorystore Redis — Basic 1GB on vidgo-vpc (cache + ARQ task queue)
gcloud redis instances describe vidgo-redis --region=asia-east1 --project=vidgo-ai

# Media bucket — public generated/static media
gsutil ls gs://vidgo-media-vidgo-ai/
#   static/      → hub thumbnails (static/hub/...), try-on models
#                  (static/tryon/models/...), demo products (static/products/...)
#   generated/   → user/demo generation outputs persisted from provider CDNs
```

**Provider CDN persistence:** PiAPI and Pollo return temporary CDN URLs that expire after ~14 days. `app/services/gcs_storage_service.py` downloads results and re-uploads them to `gs://vidgo-media-vidgo-ai/generated/...`, persisting the GCS URL instead of the expiring provider URL.

### 3.4 Secret Manager

Secrets mounted on backend + worker (as env vars, `:latest`):

```
DATABASE_URL  REDIS_URL  SECRET_KEY
PIAPI_KEY  GEMINI_API_KEY  POLLO_API_KEY
A2E_API_KEY  A2E_API_ID  A2E_DEFAULT_CREATOR_ID
SMTP_HOST  SMTP_PORT  SMTP_USER  SMTP_PASSWORD
ECPAY_MERCHANT_ID  ECPAY_HASH_KEY  ECPAY_HASH_IV
GIVEME_IDNO  GIVEME_PASSWORD
```

Additional secrets exist in Secret Manager but are **not mounted** on the services:
- `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` / `PAYPAL_WEBHOOK_ID` / `PAYPAL_PLAN_IDS` — PayPal credentials are admin-configured in the DB (payment settings page) with env-var fallback (`app/services/payment_settings_service.py`).
- `PADDLE_*` — **legacy, unused**. Paddle was removed from the platform (payments are PayPal + ECPay, e-invoices via Giveme). Safe to delete.
- `FACEBOOK_*`, `TIKTOK_*`, `YOUTUBE_*` — social-posting integrations; `ADMIN_*`, `QA_*`, `TEST_ACCOUNTS` — seeding/QA.

> ⚠️ **`GEMINI_API_KEY` is revoked** (the key leaked and was disabled). It is still mounted but non-functional. All Gemini / Imagen / Veo calls go through **Vertex AI with Application Default Credentials (ADC)** using the service account — no API key involved. See Section 7.

---

## 4. GoDaddy DNS Configuration

Domain is **`vidgo.co`** (not vidgo.ai). TLS is provisioned automatically by Cloud Run domain mappings — no load balancer or managed SSL cert resources to maintain.

### 4.1 Domain Mappings (live)

```bash
gcloud beta run domain-mappings list --project=vidgo-ai --region=asia-east1
#  ✔  api.vidgo.co  → vidgo-backend
#  ✗  app.vidgo.co  → vidgo-frontend   (mapping created, cert not yet provisioned)
#  ✔  vidgo.co      → vidgo-frontend
```

### 4.2 GoDaddy DNS Records

```
Type    Name    Value                                  TTL
────    ────    ─────                                  ───
A/AAAA  @       Google-provided IPs (from the          600
                domain-mapping resource records)
CNAME   api     ghs.googlehosted.com                   600
CNAME   app     ghs.googlehosted.com                   600
```

Setup: GoDaddy → My Products → Domains → vidgo.co → DNS, enter the resource records shown by:

```bash
gcloud beta run domain-mappings describe --domain=vidgo.co \
    --project=vidgo-ai --region=asia-east1
```

See also `docs/dns-and-ecpay-setup.md` for the ECPay/Giveme callback and NAT egress IP requirements.

### 4.3 Verify

```bash
nslookup vidgo.co
nslookup api.vidgo.co
curl -I https://vidgo.co
curl -I https://api.vidgo.co/health
```

---

## 5. Docker Configuration

### 5.1 Backend Image (`backend/Dockerfile`)

Built from the **repo root** as build context (requirements and code are copied from `backend/`). Base: `python:3.12-slim`.

Highlights:
- System deps: `curl postgresql-client redis-tools ffmpeg dos2unix fonts-noto-cjk fonts-noto-cjk-extra` (CJK fonts are required so the image-translator can render Traditional Chinese/Japanese/Korean glyphs instead of tofu).
- **Node.js + MCP server build removed 2026-05-26** — the Pollo MCP and PiAPI MCP providers were deleted in favor of REST equivalents. This trimmed the image by ~150-200 MB and shaved ~30-60s off every build.
- Entry: `scripts/docker_entrypoint.sh` (CRLF→LF normalized at build time), default CMD `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- The same image serves both `vidgo-backend` and `vidgo-worker` (worker overrides the command).

### 5.2 Frontend Image (`frontend-vue/Dockerfile.prod`)

```dockerfile
# Stage 1: node:20-alpine — npm ci && npm run build
# Stage 2: mirror.gcr.io/library/nginx:alpine
#   dist/ → /usr/share/nginx/html
#   nginx.conf.template → /etc/nginx/templates/default.conf.template
#   NGINX_ENVSUBST_FILTER=BACKEND_URL  (only $BACKEND_URL is substituted;
#   nginx runtime vars like $host/$uri are left intact)
#   EXPOSE 80
```

The nginx template serves the SPA and reverse-proxies `/api/*` to `$BACKEND_URL`, so the browser only ever talks to the frontend origin.

### 5.3 Local Development (`docker-compose.yml`)

Services: `postgres` (15-alpine, host port 5433), `redis` (7-alpine, host port 6380), `mailpit` (SMTP testing, UI :8025), `backend` (uvicorn --reload, host port 8001), `worker` (ARQ), `frontend` (Vite dev server, host port 8501), plus profile-gated `init-materials` / `pregenerate` jobs for Material DB seeding. Generated media and materials persist in named Docker volumes (`vidgo_generated`, `vidgo_materials`, `vidgo_tryon_garments`).

---

## 6. CI/CD & Deployment

### 6.1 Cloud Build Pipelines (repo root)

| File | Purpose |
|------|---------|
| `cloudbuild.yaml` | Full pipeline: build backend + frontend images in parallel (with `--cache-from :latest`), push to `vidgo-images`, then deploy `vidgo-backend`, `vidgo-worker` (backend image + custom ARQ command), and `vidgo-frontend` with explicit flags (`SKIP_PREGENERATION=true`, `--add-cloudsql-instances`, scaling/memory per service). |
| `cloudbuild.backend-only.yaml` | Build + push the backend image only (no deploy). |
| `cloudbuild.frontend-only.yaml` | Build + push the frontend image only (no deploy). |

### 6.2 Local-Build Deploy Flow (primary day-to-day path)

Images are typically built on a **linux/amd64** Docker host (Intel Mac, or `--platform linux/amd64`), pushed directly to Artifact Registry, then rolled out with `gcloud run services update --image` — which **preserves all existing env vars / secrets / flags** on the service:

```bash
REG=asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images
TS=$(date +%Y%m%d-%H%M%S)

# Backend (+ worker shares the image) — tag convention: YYYYMMDD-HHMMSS-be
docker build --platform linux/amd64 -t $REG/vidgo-backend:${TS}-be -f backend/Dockerfile .
docker push $REG/vidgo-backend:${TS}-be
gcloud run services update vidgo-backend  --image $REG/vidgo-backend:${TS}-be --project vidgo-ai --region asia-east1
gcloud run services update vidgo-worker   --image $REG/vidgo-backend:${TS}-be --project vidgo-ai --region asia-east1

# Frontend — tag convention: YYYYMMDD-HHMMSS-fe
docker build --platform linux/amd64 -t $REG/vidgo-frontend:${TS}-fe -f frontend-vue/Dockerfile.prod frontend-vue/
docker push $REG/vidgo-frontend:${TS}-fe
gcloud run services update vidgo-frontend --image $REG/vidgo-frontend:${TS}-fe --project vidgo-ai --region asia-east1
```

Rollback: `gcloud run services update <svc> --image <previous tag>` or `gcloud run services update-traffic <svc> --to-revisions <rev>=100`. See `docs/DEPLOYMENT_GUIDE.md` for the full procedure.

### 6.3 Database Migrations — ⚠️ Manual

The Alembic history has **multiple heads** (currently 2: `e2f3g4h5i6j7` and `j4d5e6f7g8h9`), so `alembic upgrade head` is **not** run automatically. Schema changes are applied **manually via psql**, and migrations are written idempotently (`ADD COLUMN IF NOT EXISTS` / `DROP COLUMN IF EXISTS`) so they can be re-run safely.

Latest migration: **`e2f3g4h5i6j7_add_invoice_mode_prefs.py`** — adds `users.default_invoice_mode`, `users.default_buyer_tax_id`, `users.default_buyer_company_name` (發票設定 auto-issue preferences). **This must be applied to `prod-db` before deploying any backend image that contains it.**

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS default_invoice_mode VARCHAR(10);
ALTER TABLE users ADD COLUMN IF NOT EXISTS default_buyer_tax_id VARCHAR(8);
ALTER TABLE users ADD COLUMN IF NOT EXISTS default_buyer_company_name VARCHAR(100);
```

(Connect via Cloud SQL private IP from a VPC-attached workload, or `cloud-sql-proxy` with the `vidgo-ai:asia-east1:prod-db` connection name.)

---

## 7. AI Provider Architecture (REST only)

**MCP servers were removed on 2026-05-26.** The backend no longer spawns any MCP subprocesses — `app/main.py` lifespan has no MCP startup/shutdown, and the Dockerfile no longer installs Node.js or builds `piapi-mcp-server`. All providers are plain REST/SDK clients in `backend/app/providers/`:

| Provider | Role |
|----------|------|
| **PiAPI** (`piapi_provider.py`) | **PRIMARY** for nearly all generation tasks (T2I, I2I, I2V, T2V, effects, upscale, background removal, interior, avatar...). Premium tiers (e.g. Sora 2 Pro) are PiAPI-only. |
| **Vertex AI** (`vertex_ai_provider.py`) | Backup for image/video tasks and primary for Gemini text workflows. Auth: **ADC** (service-account identity) — **no API key**. `VERTEX_AI_LOCATION=asia-east1` for Gemini text; the image client is pinned to **us-central1** for `gemini-2.5-flash-image` / Imagen, and Veo also runs in us-central1. |
| **Pollo.ai** (`pollo_provider.py`) | Tertiary backup for I2V; promoted to primary for specific Pollo-exclusive model ids. |
| **A2E.ai** (`a2e_provider.py`) | Avatar / digital-human fallback after PiAPI. |

Routing/fallback order lives in `app/providers/provider_router.py` (`primary → backup → tertiary → fallback` per `TaskType`). A Redis pub/sub model-registry subscriber (started in the FastAPI lifespan) lets admin model overrides propagate to every Cloud Run instance within seconds, without a redeploy.

### 7.1 Backend Lifespan (startup behavior)

`backend/app/main.py` lifespan is designed to start **fast** so the Cloud Run health check passes:
- Material validation + startup media cleanup run as a **non-blocking background task** (5s delay, 30s timeout, non-fatal).
- Hourly media-cleanup loop task.
- Model-registry Redis pub/sub subscriber (best-effort; falls back to DB-on-write + env-on-restart).
- `SKIP_PREGENERATION=true` in production — materials are seeded via admin endpoints/scripts, never at boot.

---

## 8. Monitoring Setup

### 8.1 Cloud Monitoring / Logging

```bash
# View backend logs
gcloud logging read \
  'resource.type=cloud_run_revision AND resource.labels.service_name=vidgo-backend' \
  --project=vidgo-ai --limit=100

# Worker logs (ARQ job failures surface here)
gcloud logging read \
  'resource.type=cloud_run_revision AND resource.labels.service_name=vidgo-worker' \
  --project=vidgo-ai --limit=100
```

Useful built-in Cloud Run metrics: `run.googleapis.com/request_count` (filter `response_code_class!="2xx"` for error rate), `request_latencies` (p95), instance count, and container memory utilization (backend is 2Gi; watch for OOM on media-heavy endpoints).

### 8.2 Alert Policies

```bash
# High error rate on the backend
gcloud alpha monitoring policies create \
    --display-name="VidGo API High Error Rate" \
    --condition-display-name="Error rate > 5%" \
    --condition-filter='resource.type="cloud_run_revision" AND resource.labels.service_name="vidgo-backend" AND metric.type="run.googleapis.com/request_count" AND metric.labels.response_code_class!="2xx"' \
    --condition-threshold-value=0.05 \
    --condition-threshold-comparison=COMPARISON_GT \
    --notification-channels="projects/vidgo-ai/notificationChannels/xxx"
```

---

## 9. Cost Analysis (estimates, 1,000 users)

### 9.1 Infrastructure Costs (Monthly)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GCP Infrastructure Costs (1,000 Users)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Service                        Specs                     Monthly Cost     │
│  ─────────────────────────────────────────────────────────────────────────│
│                                                                             │
│  Cloud Run (vidgo-backend)     1 vCPU, 2Gi, min 1/max 10  $35-55          │
│  Cloud Run (vidgo-worker)      1 vCPU, 512Mi, min 1/max 2,                 │
│                                no-cpu-throttling          $20-30          │
│  Cloud Run (vidgo-frontend)    1 vCPU, 256Mi, min 0/max 4 $2-8            │
│                                                                             │
│  Cloud SQL (prod-db)           db-f1-micro, PG15          $10-15          │
│  Memorystore Redis             Basic 1GB                  $35             │
│  VPC connector                 2-3 e2 instances           $15-25          │
│  Cloud NAT + static IP         egress IP for payments     $5-10           │
│                                                                             │
│  Cloud Storage                 vidgo-media bucket + ops   $5-15           │
│  Artifact Registry             ~100GB images (prune old   $10             │
│                                tags to reduce)                             │
│  Secret Manager                ~38 secrets                $1              │
│  Monitoring & Logging          basic usage                $0-5            │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────│
│  GCP Infrastructure Subtotal                              ~$140-210       │
│                                                                             │
│  (No Load Balancer / global IP — domain mappings are free.)               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 AI Service Costs (Monthly)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      AI Service Costs (1,000 Users)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Assumptions: ~10,000 generations/month                                    │
│                                                                             │
│  PiAPI - Primary (T2I/I2V/effects/interior/...)          ~$130-150        │
│  Vertex AI (ADC) - Gemini text + image/video backup       ~$10-30         │
│  Pollo.ai - I2V backup (usage-based)                       ~$0-20          │
│  A2E.ai - avatar fallback (usage-based)                    ~$0-20          │
│                                                                             │
│  AI Services Subtotal                                      ~$140-220       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.3 Payments & Third-Party

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Payments: PayPal + ECPay (綠界), e-invoices via Giveme (發票好幫手)        │
│  — transaction fees are revenue share, not fixed cost                      │
│  (Paddle was removed; its Secret Manager entries are unused legacy.)       │
│                                                                             │
│  SMTP email                     Free/low tier             ~$0              │
│  GoDaddy domain (vidgo.co)      Annual                    ~$2/month        │
└─────────────────────────────────────────────────────────────────────────────┘
```

Per-plan pricing/margin modeling lives in `docs/service-cost.md`.

---

## 10. Deployment Checklist

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      VidGo Deployment Checklist                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Pre-Deployment:                                                            │
│  □ Any new Alembic migration applied MANUALLY to prod-db first             │
│    (multi-head history — see Section 6.3; latest: e2f3g4h5i6j7)            │
│  □ New secrets created in Secret Manager AND mounted on the service        │
│  □ Image built for linux/amd64                                             │
│                                                                             │
│  Application Deployment:                                                    │
│  □ Backend image built + pushed (tag YYYYMMDD-HHMMSS-be)                   │
│  □ vidgo-backend updated via `gcloud run services update --image`          │
│  □ vidgo-worker updated to the SAME backend image tag                      │
│  □ Frontend image built + pushed, vidgo-frontend updated                   │
│                                                                             │
│  Post-Deployment:                                                           │
│  □ https://api.vidgo.co/health responding                                  │
│  □ https://vidgo.co loads, /api proxy works                                │
│  □ Worker logs show ARQ consuming jobs (no startup crash-loop)             │
│  □ A test generation completes (PiAPI primary path)                        │
│  □ Provider fallback intact (Vertex AI ADC — no GEMINI_API_KEY usage)      │
│  □ PayPal + ECPay webhooks verified; Giveme e-invoice issued on payment    │
│  □ Email sending tested (SMTP)                                             │
│                                                                             │
│  Testing:                                                                   │
│  □ User registration flow                                                   │
│  □ Subscription payment flow (PayPal / ECPay)                              │
│  □ Subscription cancellation flow                                           │
│  □ All generation features                                                  │
│  □ Provider failover                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 11. Quick Reference Commands

```bash
# ─────────────────────────────────────────────────────────────────────────────
# DEPLOYMENT (preserves env vars / secrets / flags)
# ─────────────────────────────────────────────────────────────────────────────
REG=asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images
gcloud run services update vidgo-backend  --image $REG/vidgo-backend:<TAG>-be --project vidgo-ai --region asia-east1
gcloud run services update vidgo-worker   --image $REG/vidgo-backend:<TAG>-be --project vidgo-ai --region asia-east1
gcloud run services update vidgo-frontend --image $REG/vidgo-frontend:<TAG>   --project vidgo-ai --region asia-east1

# ─────────────────────────────────────────────────────────────────────────────
# MONITORING
# ─────────────────────────────────────────────────────────────────────────────
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=vidgo-backend" --project=vidgo-ai --limit=100
gcloud run services describe vidgo-backend --project=vidgo-ai --region=asia-east1
gcloud run revisions list --service=vidgo-backend --project=vidgo-ai --region=asia-east1

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE (private IP — connect from VPC or via cloud-sql-proxy)
# ─────────────────────────────────────────────────────────────────────────────
cloud-sql-proxy vidgo-ai:asia-east1:prod-db --port 5432 &
psql "host=127.0.0.1 port=5432 dbname=vidgo user=<user>"

# ─────────────────────────────────────────────────────────────────────────────
# TROUBLESHOOTING
# ─────────────────────────────────────────────────────────────────────────────
gcloud beta run domain-mappings list --project=vidgo-ai --region=asia-east1
gcloud redis instances describe vidgo-redis --region=asia-east1 --project=vidgo-ai
dig vidgo.co
dig api.vidgo.co
curl -I https://api.vidgo.co/health
```

---

## 12. Material Cleanup & Re-seeding

### Environment Variables

| Variable | Values | Description |
|----------|--------|-------------|
| `CLEAN_MATERIALS` | `""` (default) | No cleanup on startup |
| `CLEAN_MATERIALS` | `all` | Delete + re-seed ALL tool materials on startup |
| `CLEAN_MATERIALS` | `ai_avatar` | Delete + re-seed specific tool |
| `CLEAN_MATERIALS` | `ai_avatar,effect,short_video` | Comma-separated: multiple tools |
| `SKIP_PREGENERATION` | `true` / `false` | Skip material pre-generation on startup (**`true` in production**) |
| `PREGENERATION_LIMIT` | `10` (default) | Max materials per tool per startup |

### 14-Day Media Retention
- Hourly background task scans `user_generations` table
- Entries older than 14 days have media URLs (`result_url`, `result_video_url`) cleared
- Initial cleanup runs (non-blocking) shortly after application startup
- Provider CDN URLs themselves expire after ~14 days — durable results are persisted to GCS (Section 3.3)

## 13. 3-Tier User System Infrastructure

### 13.1 User Role Matrix

| Feature | Visitor (Guest) | Free Registered | Paid Subscriber | Admin |
|---------|----------------|-----------------|-----------------|-------|
| Browse landing page | ✅ | ✅ | ✅ | ✅ |
| Demo tools (preset, DB results) | ✅ (limit 2) | ✅ (limit 2) | ✅ | ✅ |
| Watermarked results | ✅ | ✅ | ❌ (clean) | N/A |
| Download results | ❌ | ❌ | ✅ | ✅ |
| Share to social media | ❌ | ❌ | ✅ | ❌ |
| Upload own materials | ❌ | ❌ | ✅ | ❌ |
| Real AI API generation | ❌ | ❌ | ✅ | ❌ |
| Promotion code (own) | ❌ | ❌ | ✅ (auto-issued) | Can create special ones |
| Use others' promo codes | ❌ | ✅ | ✅ | N/A |
| Private work library (14-day media retention) | ❌ | ❌ | ✅ | N/A |
| View API analytics | ❌ | ❌ | ❌ | ✅ |
| Manage users/credits | ❌ | ❌ | ❌ | ✅ |
| Create special promo codes | ❌ | ❌ | ❌ | ✅ |

### 13.2 Promotion Code System Infrastructure

**Personal Promotion Codes:**
- **Paid subscribers**: Automatically receive unique promotion code upon subscription
- **Free users**: Cannot create promotion codes, but can use others' codes
- **Admin**: Can create special promotion codes with custom credits/discounts
- **Code usage**: When someone uses a promotion code, code owner earns credits

**Promotion Code Types:**
| Type | Who Can Create | Credits Awarded | Expiry |
|------|---------------|-----------------|--------|
| Personal referral code | Auto-generated for paid subscribers | Referrer: +50, New user: +40 | Never |
| Special admin code | Admin only | Custom (e.g., 100 credits) | Custom date |
| Public promo code | Admin only | Discount or credits | Fixed expiry |

### 13.3 Work Library Retention Infrastructure

**Active subscribers**: All works stored indefinitely
**Cancelled subscribers**: Generation records remain in the private work library
**During retention**: Can download existing works, cannot generate new works
**Account deletion**: All works deleted immediately (no retention)
**Media expiry**: Generated media remains available for 14 days from creation

**Database Schema:**
- `User` model: `subscription_cancelled_at`, `work_retention_until`
- `UserGeneration` model: `media_expired` flag
- Hourly cleanup task checks for expired media and cancelled subscriptions

### 13.4 Infrastructure Requirements

**Storage Requirements:**
- **Active subscribers**: Full media storage (indefinite)
- **Cancelled subscribers**: Existing generation records remain visible; media URLs follow the 14-day expiry policy
- **Free users**: No media storage (watermarked results from Material DB only)

**Database Indexing:**
- Index on `UserGeneration.user_id` + `created_at` for retention queries
- Index on `User.subscription_cancelled_at` for retention monitoring
- Index on `Promotion.code` for fast lookup

**Redis Caching:**
- Cache promotion code validation results
- Cache user tier permissions

---

*Document Version: 4.0*
*Last Updated: 2026-06-12*
