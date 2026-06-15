# VidGo Deployment Guide

> Last updated: 2026-06-12. This replaces the earlier one-off "新定價系統部署指南"
> (the pricing rollout finished; its steps are preserved in git history).

VidGo production runs on **GCP project `vidgo-ai`**, region **`asia-east1`**
(the frontend is hosted in a separate Firebase project, `vidgo-gen-ai-prod`):

| Piece | Resource |
|---|---|
| Frontend | **Firebase Hosting** (global CDN), project `vidgo-gen-ai-prod` — built with `npm run build`, deployed via `firebase deploy --only hosting` |
| Backend API | Cloud Run `vidgo-backend` (min 1 / max 10, **1Gi**, 3600s timeout, Direct VPC egress) |
| Background tasks | **Cloud Scheduler → `POST /api/v1/tasks/*`** (auth via `X-Tasks-Secret`). No always-on worker service. |
| Images | Artifact Registry `asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images` |
| Database | Cloud SQL `prod-db` (PostgreSQL, **private IP only**), attached via `--add-cloudsql-instances` |
| Secrets | Secret Manager (`DATABASE_URL`, `SECRET_KEY`, payment/API keys, …) — **no `REDIS_URL`** |
| Networking | **Direct VPC egress** (`vidgo-vpc`/`vidgo-subnet`, `all-traffic`) + **static NAT IP** for Giveme/ECPay outbound whitelist. No VPC connector. |
| Media | GCS bucket `vidgo-media-vidgo-ai` |

> **2026-06 cost pass:** Memorystore Redis, the `vidgo-worker` service, and the
> Serverless VPC Connector were all removed; the frontend moved from Cloud Run to
> Firebase Hosting. The single canonical infra/bring-up script is now
> [`gcp/deploy.sh`](../gcp/deploy.sh) (the old `deploy-production.sh` was folded into it).

There are two supported deploy paths.

---

## Path A — Cloud Build (CI pipeline)

`cloudbuild.yaml` builds the **backend** image, pushes it, and deploys
`vidgo-backend` in one run (E2_HIGHCPU_8, layer caching from `:latest`). The
frontend is **not** in this pipeline — it ships to Firebase Hosting separately
(see *Frontend* below). Trigger it manually with:

```bash
gcloud builds submit --config cloudbuild.yaml --project vidgo-ai
```

`cloudbuild.backend-only.yaml` builds + pushes the backend image only (deploy
manually per Path B step 4).

### Frontend (Firebase Hosting)

```bash
cd frontend-vue
npm ci && npm run build
firebase deploy --only hosting --project vidgo-gen-ai-prod
```

`bash gcp/deploy.sh --step frontend` does the same. (The legacy
`cloudbuild.frontend-only.yaml` deployed a Cloud Run frontend and is obsolete.)

---

## Path B — Local build + push + deploy

Works from any **linux/amd64** Docker host (Intel Mac or `--platform linux/amd64`).

### 1. Build

```bash
cd Vidgo_Gen_AI
TS=$(date +%Y%m%d-%H%M%S)
REG=asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images

# Backend (context = repo root)
docker build -f backend/Dockerfile \
  -t $REG/vidgo-backend:${TS}-be -t $REG/vidgo-backend:latest .

# Frontend (context = frontend-vue/, uses the production Dockerfile)
docker build -f frontend-vue/Dockerfile.prod \
  -t $REG/vidgo-frontend:${TS} -t $REG/vidgo-frontend:latest frontend-vue/
```

Tag conventions: backend `YYYYMMDD-HHMMSS-be`, frontend `YYYYMMDD-HHMMSS`.
Note: local `vue-tsc` may show bogus `TS2688 "@types/* 2"` errors from
Finder-duplicated dirs in `node_modules` — the Docker build does a clean
`npm ci` and is the source of truth. (The frontend image above is only for
local/preview use — production frontend ships to Firebase Hosting, not Cloud Run.)

### 2. Push

```bash
gcloud auth configure-docker asia-east1-docker.pkg.dev   # once per machine
docker push --all-tags $REG/vidgo-backend
```

### 3. Apply DB migrations (when the release contains one)

⚠️ **Do this BEFORE deploying the backend.** SQLAlchemy selects every mapped
column, so deploying a model change without the columns breaks every query on
that table.

The alembic history has **multiple heads**; schema changes are applied
manually. Migrations are written with idempotent `ADD COLUMN IF NOT EXISTS`
SQL so they can be replayed safely. Because `prod-db` is private-IP only,
run the SQL through a one-off **Cloud Run job** that reuses the backend's
service account, secrets, Cloud SQL attachment, and Direct VPC egress:

```bash
gcloud run jobs create vidgo-db-migrate \
  --project vidgo-ai --region asia-east1 \
  --image $REG/vidgo-backend:${TS}-be \
  --service-account vidgo-backend@vidgo-ai.iam.gserviceaccount.com \
  --set-secrets DATABASE_URL=DATABASE_URL:latest \
  --set-cloudsql-instances vidgo-ai:asia-east1:prod-db \
  --network vidgo-vpc --subnet vidgo-subnet --vpc-egress all-traffic \
  --command python \
  --args '-c,<python snippet that runs the ALTER statements via asyncpg>'

gcloud run jobs execute vidgo-db-migrate --project vidgo-ai --region asia-east1 --wait
```

(If the job already exists, use `gcloud run jobs update … && gcloud run jobs execute …`.)

### 4. Deploy new revisions

`services update --image` keeps all existing env vars / secrets / flags and
only swaps the image:

```bash
gcloud run services update vidgo-backend --image $REG/vidgo-backend:${TS}-be --project vidgo-ai --region asia-east1
```

(There is no `vidgo-worker` / `vidgo-frontend` service to update. Background tasks
run via Cloud Scheduler → `/api/v1/tasks/*`; the frontend ships to Firebase Hosting.)

### 5. Verify

```bash
curl -s https://vidgo-backend-38714015566.asia-east1.run.app/api/v1/health
curl -I https://vidgo.co                                   # frontend (Firebase Hosting)
gcloud run services logs read vidgo-backend --project vidgo-ai --region asia-east1 --limit 50
```

Roll back by pointing the service at the previous tag
(`gcloud run services update <svc> --image <previous tag>`), or shift traffic
with `gcloud run services update-traffic <svc> --to-revisions <rev>=100`.

---

## Release checklist

1. `git push origin main` — the deployed code must be in the repo.
2. Migration needed? → Path B step 3 first.
3. Build + push + deploy (Path A or B).
4. Health-check backend + frontend; tail logs for the first minutes.
5. If `ServicePricing` / plan rows changed, run the matching seed script
   (e.g. `backend/scripts/seed_service_pricing.py`) — credit charges fall
   back to in-code constants until the rows exist.

## Related docs

- Infra layout: [vidgo-infra-architecture.md](./vidgo-infra-architecture.md)
- First-time DNS / payment bring-up: [setup_guide.md](./setup_guide.md),
  [dns-and-ecpay-setup.md](./dns-and-ecpay-setup.md), [PAYPAL_SETUP.md](./PAYPAL_SETUP.md)
- Costs & margins: [service-cost.md](./service-cost.md)
