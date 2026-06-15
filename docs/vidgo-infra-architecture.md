# VidGo AI Platform - Infrastructure Architecture

> Last updated: 2026-06-15 (2026-06 cost pass)

**Version:** 5.0
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
│   │              Firebase Hosting (project vidgo-gen-ai-prod, global CDN)        │  │
│   │                                                                              │  │
│   │   vidgo.co / app.vidgo.co  → Firebase Hosting → Vue SPA (npm run build)     │  │
│   │   (firebase deploy --only hosting; separate from GCP project vidgo-ai)      │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                               │                                      │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                    GoDaddy DNS (vidgo.co)                                    │  │
│   │                                                                              │  │
│   │   vidgo.co / app.vidgo.co  → Firebase Hosting (Vue SPA, global CDN)         │  │
│   │   api.vidgo.co             → Cloud Run domain mapping → vidgo-backend       │  │
│   │                                                                              │  │
│   │   No GCP Load Balancer — Cloud Run domain mapping handles backend TLS.      │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                               │                                      │
│                                               ▼                                      │
│                              ┌──────────────────────────────┐                       │
│                              │   Cloud Run: vidgo-backend   │                       │
│                              │                              │                       │
│                              │   • FastAPI (uvicorn)        │                       │
│                              │   • Min: 1, Max: 10          │                       │
│                              │   • 1 vCPU, 1Gi RAM          │                       │
│                              │   • concurrency 80           │                       │
│                              │   • request-based CPU billing│                       │
│                              │   • timeout 3600s, port 8000 │                       │
│                              └──────────────────────────────┘                       │
│                                               ▲                                      │
│   ┌──────────────────────────────┐            │                                     │
│   │   Cloud Scheduler            │────────────┘  (background/async tasks:            │
│   │                              │   HTTP POST → /api/v1/tasks/*                     │
│   │   • cron → HTTP POST         │   authed via X-Tasks-Secret header.              │
│   │   • /api/v1/tasks/*          │   No vidgo-worker Cloud Run service; no ARQ.)    │
│   │   • X-Tasks-Secret header    │                                                  │
│   └──────────────────────────────┘            │                                     │
│                                               ▼                                      │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │     VPC `vidgo-vpc` (Direct VPC egress: subnet vidgo-subnet, all-traffic)    │  │
│   │                                                                              │  │
│   │   ┌────────────────────────────┐        ┌────────────────────────────┐      │  │
│   │   │   Cloud SQL                │        │   Cloud Storage            │      │  │
│   │   │   `prod-db`                │        │   `vidgo-media-vidgo-ai`   │      │  │
│   │   │                            │        │                            │      │  │
│   │   │   • PostgreSQL 15          │        │   • static/ + generated/   │      │  │
│   │   │   • db-f1-micro            │        │   • asia-east1             │      │  │
│   │   │   • PRIVATE IP only        │        │   • public media           │      │  │
│   │   │     10.70.0.3              │        │                            │      │  │
│   │   └────────────────────────────┘        └────────────────────────────┘      │  │
│   │   (No Memorystore Redis — removed in the 2026-06 cost pass.)                 │  │
│   │                                                                              │  │
│   │   Cloud NAT static egress IP: 35.201.182.131 (`vidgo-nat-ip`)               │  │
│   │   — egress MUST stay all-traffic so outbound ECPay / Giveme calls           │  │
│   │     come from this whitelisted IP                                           │  │
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

Key facts (verified against live `gcloud` state, 2026-06 cost pass):

| Resource | Value |
|----------|-------|
| GCP project | `vidgo-ai` |
| Region | `asia-east1` |
| Cloud Run services | `vidgo-backend` only (frontend: Firebase Hosting; no `vidgo-worker`) |
| Frontend hosting | Firebase Hosting, project `vidgo-gen-ai-prod` (separate from GCP `vidgo-ai`) |
| Async/background tasks | Cloud Scheduler → HTTP POST `/api/v1/tasks/*` (authed via `X-Tasks-Secret`); no ARQ, no worker service |
| Artifact Registry | `asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images` |
| Cloud SQL | `prod-db` (POSTGRES_15, db-f1-micro, **private IP only** `10.70.0.3`) |
| Memorystore Redis | **Removed** in the 2026-06 cost pass (`vidgo-redis` deleted; no `REDIS_URL`) |
| VPC egress | **Direct VPC egress** (`--network vidgo-vpc --subnet vidgo-subnet --vpc-egress all-traffic`) — no `vidgo-connector`. Static NAT IP retained for Giveme/ECPay whitelist (egress stays `all-traffic`). |
| Media bucket | `gs://vidgo-media-vidgo-ai` |
| Service accounts | `vidgo-backend@vidgo-ai.iam.gserviceaccount.com` only (no `vidgo-worker@`). Backend SA also has `roles/bigquery.dataViewer` + `roles/bigquery.jobUser` to read the Cloud Billing→BigQuery export for the admin Cost dashboard. |

Notes:
- `DATABASE_URL` comes from **Secret Manager** (mounted as env var); the DB is reached over its private IP via Direct VPC egress. There is **no `REDIS_URL`** anymore.
- The backend carries the `run.googleapis.com/cloudsql-instances` annotation for `vidgo-ai:asia-east1:prod-db` (attached via `--add-cloudsql-instances`). Any leftover `vidgo-db` entry is harmless — the live connection uses `prod-db` private IP.
- **No Redis in prod.** The app uses in-process caching; the model-registry live-override mechanism falls back to DB-on-write + env-on-restart (no Redis pub/sub); rate-limiting/locks fall back to Postgres.
- **Background/async tasks** run via **Cloud Scheduler → HTTP POST `/api/v1/tasks/*`** (authenticated with an `X-Tasks-Secret` header), handled by the backend service. ARQ-as-a-Cloud-Run-service is gone.

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
   • backend min=1 保持暖機 (唯一 Cloud Run service), 前端在 Firebase Hosting (全球 CDN)
   • 1000 並發在 Cloud Run 完全可以處理
   • 2026-06 cost pass 移除了 Redis / worker / VPC connector

2. 管理簡單
   • 無需管理 Kubernetes 集群
   • 自動擴展、自動修復、revision-based rollback

3. VidGo 使用場景適合
   • AI 生成是異步任務 (Cloud Scheduler → /api/v1/tasks/* + polling)
   • 不需要 GPU (AI 在外部 API: PiAPI / Vertex AI / Pollo / A2E)
   • 不需要長時間 WebSocket (使用 polling / SSE)

❌ 不需要 GKE 的原因:

1. 沒有自建 AI 模型需求 (使用外部 API)
2. 沒有複雜微服務架構 (單一 Cloud Run service + Firebase Hosting)
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

There is exactly **one** Cloud Run service: `vidgo-backend`. The frontend is served by **Firebase Hosting** (project `vidgo-gen-ai-prod`, not Cloud Run). The old `vidgo-worker` and `vidgo-frontend` Cloud Run services were removed in the 2026-06 cost pass.

| Setting | `vidgo-backend` |
|---------|-----------------|
| Image | `…/vidgo-images/vidgo-backend:<TAG>` |
| Command | default (uvicorn via entrypoint) |
| CPU / Memory | 1 vCPU / 1Gi |
| CPU billing | request-based (CPU only during requests; **no** `--no-cpu-throttling`) |
| Scaling | min 1 / max 10 |
| Concurrency | 80 |
| Timeout | 3600s |
| Port | 8000 |
| Ingress / auth | all, `--allow-unauthenticated` |
| VPC | **Direct VPC egress** (`--network vidgo-vpc --subnet vidgo-subnet --vpc-egress all-traffic`); static NAT IP for Giveme/ECPay |
| Cloud SQL | `--add-cloudsql-instances vidgo-ai:asia-east1:prod-db` |
| Service account | `vidgo-backend@vidgo-ai.iam` (+ `roles/bigquery.dataViewer`, `roles/bigquery.jobUser`) |

Notable env vars on backend (non-secret): `SKIP_PREGENERATION=true`, `SKIP_DEPENDENCY_CHECK=true`, `GCS_BUCKET=vidgo-media-vidgo-ai`, `VERTEX_AI_PROJECT=vidgo-ai`, `VERTEX_AI_LOCATION=asia-east1`, `GEMINI_MODEL=gemini-2.5-flash`, `GEMINI_IMAGE_MODEL=gemini-2.5-flash-image`, `VEO_MODEL=veo-3.0-fast-generate-001`, `FRONTEND_URL=https://vidgo.co`, `BACKEND_URL=https://api.vidgo.co`, `ECPAY_ENV=production`, `PAYPAL_ENV=production`, `GIVEME_ENABLED=true`, plus `GCP_BILLING_BQ_TABLE` (BigQuery billing-export table for the admin Cost dashboard; falls back to `GCP_*_BUDGET_USD` estimates when unset).

Async/background tasks are driven by **Cloud Scheduler → HTTP POST `/api/v1/tasks/*`** (authenticated with an `X-Tasks-Secret` header), all handled inside the `vidgo-backend` service — there is no separate worker service.

### 3.2 Networking

Cloud Run uses **Direct VPC egress** (no Serverless VPC Connector). The `vidgo-connector` was removed in the 2026-06 cost pass.

```bash
# Direct VPC egress is configured on the service, not as a standalone connector:
#   --network vidgo-vpc --subnet vidgo-subnet --vpc-egress all-traffic
# Egress MUST stay all-traffic so outbound Giveme (e-invoice) / ECPay calls
# leave via the whitelisted static NAT IP (NOT private-ranges-only).
gcloud run services describe vidgo-backend --project=vidgo-ai --region=asia-east1 \
    --format="value(spec.template.metadata.annotations)"

# Cloud NAT static egress IP (for ECPay / Giveme IP allowlists) — retained
# vidgo-nat-ip = 35.201.182.131
gcloud compute addresses list --project=vidgo-ai
```

There is **no GCP HTTPS Load Balancer, no serverless NEGs, no reserved global IP** — public traffic terminates directly on Cloud Run via domain mappings (Section 4).

### 3.3 Data Stores

```bash
# Cloud SQL — PostgreSQL 15, private IP only (10.70.0.3), no public IP
gcloud sql instances describe prod-db --project=vidgo-ai

# Memorystore Redis — REMOVED in the 2026-06 cost pass (no vidgo-redis instance).
# Caching is in-process; rate-limiting/locks fall back to Postgres.

# Media bucket — public generated/static media
gsutil ls gs://vidgo-media-vidgo-ai/
#   static/      → hub thumbnails (static/hub/...), try-on models
#                  (static/tryon/models/...), demo products (static/products/...)
#   generated/   → user/demo generation outputs persisted from provider CDNs
```

**Provider CDN persistence:** PiAPI and Pollo return temporary CDN URLs that expire after ~14 days. `app/services/gcs_storage_service.py` downloads results and re-uploads them to `gs://vidgo-media-vidgo-ai/generated/...`, persisting the GCS URL instead of the expiring provider URL.

### 3.4 Secret Manager

Secrets mounted on the `vidgo-backend` service (as env vars, `:latest`). There is **no `REDIS_URL`** anymore (Redis was removed):

```
DATABASE_URL  SECRET_KEY  TASKS_SECRET
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

Domain is **`vidgo.co`** (not vidgo.ai). The backend's TLS is provisioned automatically by its Cloud Run domain mapping; the frontend's TLS is handled by **Firebase Hosting** (project `vidgo-gen-ai-prod`). No load balancer or managed SSL cert resources to maintain.

### 4.1 Domain Mappings (live)

```bash
# Only the backend uses a Cloud Run domain mapping now.
gcloud beta run domain-mappings list --project=vidgo-ai --region=asia-east1
#  ✔  api.vidgo.co  → vidgo-backend
#
# vidgo.co / app.vidgo.co are served by Firebase Hosting (vidgo-gen-ai-prod),
# configured in the Firebase console (custom domains), not Cloud Run.
```

### 4.2 GoDaddy DNS Records

```
Type    Name    Value                                  TTL
────    ────    ─────                                  ───
A/AAAA  @       Firebase Hosting IPs (from the         600
                Firebase custom-domain setup)
CNAME   api     ghs.googlehosted.com                   600
A/AAAA  app     Firebase Hosting IPs                   600
```

Setup (backend mapping): GoDaddy → My Products → Domains → vidgo.co → DNS, enter the resource records shown by:

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
- This image serves the `vidgo-backend` Cloud Run service. There is no longer a `vidgo-worker` service — async tasks are driven by Cloud Scheduler → `/api/v1/tasks/*` against this same backend.

### 5.2 Frontend (Firebase Hosting)

The Vue SPA is no longer containerized for production. It is built with `npm run build` and deployed to **Firebase Hosting** (project `vidgo-gen-ai-prod`, global CDN):

```bash
cd frontend-vue
npm run build                       # → dist/
firebase deploy --only hosting      # uses .firebaserc / firebase.json (project vidgo-gen-ai-prod)
```

`frontend-vue/Dockerfile.prod` is retained only for local/CI parity; production traffic to `vidgo.co` / `app.vidgo.co` is served entirely by Firebase Hosting, not Cloud Run.

### 5.3 Local Development (`docker-compose.yml`)

Local dev still uses Redis and an ARQ worker (this is unchanged — only **production** dropped them). Services: `postgres` (15-alpine, host port 5433), `redis` (7-alpine, host port 6380), `mailpit` (SMTP testing, UI :8025), `backend` (uvicorn --reload, host port 8001), `worker` (ARQ), `frontend` (Vite dev server, host port 8501), plus profile-gated `init-materials` / `pregenerate` jobs for Material DB seeding. Generated media and materials persist in named Docker volumes (`vidgo_generated`, `vidgo_materials`, `vidgo_tryon_garments`).

---

## 6. CI/CD & Deployment

### 6.1 Cloud Build Pipelines (repo root)

| File | Purpose |
|------|---------|
| `cloudbuild.yaml` | Backend-only pipeline: build the **backend** image (with `--cache-from :latest`), push to `vidgo-images`, then deploy `vidgo-backend` with explicit flags (`SKIP_PREGENERATION=true`, `--add-cloudsql-instances`, Direct VPC egress, 1Gi / min 1 / max 10). The frontend is **not** built here — it ships to Firebase Hosting (`firebase deploy --only hosting`), not Cloud Run. There is no worker deploy step. |
| `cloudbuild.backend-only.yaml` | Build + push the backend image only (no deploy). |
| `cloudbuild.frontend-only.yaml` | Build + push the frontend image only (no deploy). |

The single canonical deploy script is `gcp/deploy.sh` (the old `gcp/deploy-production.sh` was consolidated into it).

### 6.2 Local-Build Deploy Flow (primary day-to-day path)

Images are typically built on a **linux/amd64** Docker host (Intel Mac, or `--platform linux/amd64`), pushed directly to Artifact Registry, then rolled out with `gcloud run services update --image` — which **preserves all existing env vars / secrets / flags** on the service:

```bash
REG=asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images
TS=$(date +%Y%m%d-%H%M%S)

# Backend (only Cloud Run service) — tag convention: YYYYMMDD-HHMMSS-be
docker build --platform linux/amd64 -t $REG/vidgo-backend:${TS}-be -f backend/Dockerfile .
docker push $REG/vidgo-backend:${TS}-be
gcloud run services update vidgo-backend  --image $REG/vidgo-backend:${TS}-be --project vidgo-ai --region asia-east1

# Frontend — Firebase Hosting (no Cloud Run, no image)
cd frontend-vue && npm run build && firebase deploy --only hosting   # project vidgo-gen-ai-prod
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

Routing/fallback order lives in `app/providers/provider_router.py` (`primary → backup → tertiary → fallback` per `TaskType`). Admin model overrides are persisted to the DB on write and applied via env-on-restart. (The previous Redis pub/sub propagation path was removed in the 2026-06 cost pass along with Redis; prod no longer fans out overrides to instances within seconds.)

### 7.1 Backend Lifespan (startup behavior)

`backend/app/main.py` lifespan is designed to start **fast** so the Cloud Run health check passes:
- Material validation + startup media cleanup run as a **non-blocking background task** (5s delay, 30s timeout, non-fatal).
- Media cleanup now runs via **Cloud Scheduler → `/api/v1/tasks/*`** rather than an in-process hourly worker loop.
- Model-registry overrides use **DB-on-write + env-on-restart** (no Redis pub/sub subscriber in prod).
- `SKIP_PREGENERATION=true` in production — materials are seeded via admin endpoints/scripts, never at boot.

---

## 8. Monitoring Setup

### 8.1 Cloud Monitoring / Logging

```bash
# View backend logs (async task runs surface here too, under /api/v1/tasks/*)
gcloud logging read \
  'resource.type=cloud_run_revision AND resource.labels.service_name=vidgo-backend' \
  --project=vidgo-ai --limit=100

# There is no vidgo-worker service — scheduled-task failures appear in the
# backend logs above (filter on httpRequest.requestUrl=~"/api/v1/tasks/").
```

Useful built-in Cloud Run metrics: `run.googleapis.com/request_count` (filter `response_code_class!="2xx"` for error rate), `request_latencies` (p95), instance count, and container memory utilization (backend is 1Gi; watch for OOM on media-heavy endpoints).

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
│  Cloud Run (vidgo-backend)     1 vCPU, 1Gi, min 1/max 10  $30-50          │
│                                request-based CPU billing                    │
│  Firebase Hosting (frontend)   global CDN, SPA            ~$0 (free tier)  │
│                                                                             │
│  Cloud SQL (prod-db)           db-f1-micro, PG15          $10-15          │
│  Cloud NAT + static IP         egress IP for payments     $5-10           │
│                                                                             │
│  Cloud Storage                 vidgo-media bucket + ops   $5-15           │
│  Artifact Registry             ~100GB images (prune old   $10             │
│                                tags to reduce)                             │
│  Secret Manager                ~38 secrets                $1              │
│  Monitoring & Logging          basic usage                $0-5            │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────│
│  GCP Infrastructure Subtotal                              ~$60-105        │
│                                                                             │
│  2026-06 cost pass: removed Memorystore Redis (~$35), VPC connector        │
│  (~$15-25) and the vidgo-worker service; frontend moved off Cloud Run      │
│  to Firebase Hosting (effectively free CDN tier).                          │
│  (No Load Balancer / global IP — backend domain mapping is free; Firebase  │
│   Hosting fronts the SPA.)                                                  │
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
│  □ Frontend built (`npm run build`) + `firebase deploy --only hosting`     │
│    (Firebase project vidgo-gen-ai-prod)                                    │
│                                                                             │
│  Post-Deployment:                                                           │
│  □ https://api.vidgo.co/health responding                                  │
│  □ https://vidgo.co loads (Firebase Hosting), API calls reach api.vidgo.co │
│  □ Cloud Scheduler → /api/v1/tasks/* runs OK (check backend logs)         │
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
# Frontend (Firebase Hosting, project vidgo-gen-ai-prod):
#   cd frontend-vue && npm run build && firebase deploy --only hosting

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
# (No Memorystore Redis and no VPC connector to inspect — removed in 2026-06 cost pass.)
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

**Caching (in-process):**
- Cache promotion code validation results
- Cache user tier permissions
- (Production no longer uses Memorystore Redis — caching is in-process and rate-limiting/locks fall back to Postgres. Removed in the 2026-06 cost pass.)

---

*Document Version: 5.0*
*Last Updated: 2026-06-15 (2026-06 cost pass)*
