# VidGo Deployment Guide

> Last updated: 2026-07-12. **Corrects the 2026-06 revision**, which claimed the
> frontend was on Firebase Hosting and that background tasks ran via Cloud
> Scheduler with no worker service. Neither is true in production — see the
> corrections inline below.

VidGo production runs on **GCP project `vidgo-ai`**, region **`asia-east1`**.
**All three services are Cloud Run, CPU-only (no GPU** — every model runs at an
external provider over REST, so the services only orchestrate + stream):

| Piece | Resource |
|---|---|
| Frontend | Cloud Run **`vidgo-frontend`** (nginx serving the built SPA, 1 vCPU / 256Mi). **NOT Firebase Hosting** — vidgo.co is this Cloud Run service. |
| Backend API | Cloud Run **`vidgo-backend`** (1 vCPU / 2Gi, 3600s timeout, Direct VPC egress) |
| Background tasks | Cloud Run **`vidgo-worker`** — an always-on ARQ worker running the cron jobs (reclaim every 2 min, auto-renew, monthly reset, bonus/prompt-cache/stale-row cleanup). **Cloud Scheduler was never enabled**; the `/api/v1/tasks/*` HTTP endpoints exist but nothing calls them. The worker is the only scheduler in prod. |
| Images | Artifact Registry `asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images` (backend + frontend repos; the worker shares the **backend** image) |
| Database | Cloud SQL `prod-db` (PostgreSQL, **private IP only**) |
| Secrets | Secret Manager (`DATABASE_URL`, `SECRET_KEY`, payment/API keys, …) |
| Networking | Backend/worker services use **Direct VPC egress**; one-off Cloud Run **jobs** attach via the `vidgo-connector` VPC connector + `--add-cloudsql-instances`. |
| Media | GCS bucket `vidgo-media-vidgo-ai` (generated assets are `immutable`, uuid-named) |

> ### ⚠️ Two coupling rules you must not break
> 1. **The worker shares the backend image and MUST be redeployed with the
>    backend.** The worker runs the same task code (reclaim/refund/renewal). A
>    new backend + an old worker means the old worker's stale logic runs against
>    the new schema/behavior — e.g. an old 60-second reclaim grace refunding
>    jobs that are still rendering (money leak). Always swap `vidgo-worker` to
>    the **same digest** as `vidgo-backend`.
> 2. **`arq` is a required runtime dependency.** It was wrongly removed from
>    `requirements.txt` on 2026-06-15 (assuming a Cloud Scheduler migration that
>    never completed); every image built after that failed the worker with
>    `exec: arq: not found` (exit 127), which is why the worker was pinned to a
>    stale image for weeks. Keep `arq>=0.26.0` in `requirements.txt`.

---

## The fast path — `gcp/deploy-service.sh`

Code-only re-deploy (Cloud Build image build → Artifact Registry → image-swap
onto the existing service; keeps all env/secrets/flags/scaling):

```bash
bash gcp/deploy-service.sh --backend --frontend   # builds + swaps both
```

This does **not** touch the worker. After it finishes, swap the worker to the
**same backend digest** (see the coupling rule above):

```bash
DIGEST=$(gcloud artifacts docker images describe \
  asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images/vidgo-backend:latest \
  --project vidgo-ai --format='value(image_summary.digest)')

gcloud run services update vidgo-worker \
  --image asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images/vidgo-backend@${DIGEST} \
  --project vidgo-ai --region asia-east1
```

Verify the worker actually started its crons (not just "Ready"):

```bash
gcloud logging read 'resource.type="cloud_run_revision"
  resource.labels.service_name="vidgo-worker" textPayload:"Starting worker for"' \
  --project vidgo-ai --limit 1 --format='value(textPayload)' --freshness=5m
# expect "Starting worker for N functions: … cron:reclaim_pending_provider_tasks_task …"
```

---

## DB migrations — idempotent SQL via a Cloud Run job

⚠️ **Run the migration BEFORE swapping the backend.** SQLAlchemy selects every
mapped column, so deploying a model that references a not-yet-created column
breaks every query on that table.

The alembic history has **14 un-merged heads**, so `alembic upgrade head` is not
usable. Schema changes ship as **idempotent raw SQL** (`ADD COLUMN IF NOT
EXISTS`, `CREATE INDEX IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`) in a script
under `backend/scripts/` (e.g. `migrate_perf_2026_07_12.py`), applied via a
one-off Cloud Run **job** that reuses the backend SA + secrets + Cloud SQL +
VPC connector. Because the migration script lives in the image, **build the new
image first, run the migration on it, then swap the services to that digest.**

```bash
# 1. Build the new image (does NOT swap the live service)
TAG="mig-$(date +%Y%m%d-%H%M%S)"
gcloud builds submit . --project vidgo-ai --config - <<EOF
steps:
  - name: gcr.io/cloud-builders/docker
    args: ['build','-t','asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images/vidgo-backend:${TAG}','-f','backend/Dockerfile','.']
  - name: gcr.io/cloud-builders/docker
    args: ['push','asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images/vidgo-backend:${TAG}']
images: ['asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images/vidgo-backend:${TAG}']
EOF

# 2. Run the migration on that image (reuse/clone the vidgo-db-migrate job)
gcloud run jobs update vidgo-db-migrate \
  --image asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images/vidgo-backend:${TAG} \
  --command python --args "-m,scripts.migrate_perf_2026_07_12" \
  --project vidgo-ai --region asia-east1
gcloud run jobs execute vidgo-db-migrate --project vidgo-ai --region asia-east1 --wait

# 3. Swap backend + worker to the migrated image's digest (see fast path above)
```

Existing migration/seed jobs you can repurpose: `vidgo-db-migrate`,
`vidgo-seed-pricing` (both already have the SA/secrets/VPC wiring — just
`jobs update … --args` then `jobs execute`).

---

## Verify

```bash
curl -s  https://vidgo-backend-38714015566.asia-east1.run.app/health   # 200
curl -sI https://vidgo.co                                              # 200 (Cloud Run nginx)

# no SQL echo in prod logs (echo is gated on SQL_ECHO, default off — do NOT
# key it off DEBUG, prod runs DEBUG=true):
gcloud logging read 'resource.type="cloud_run_revision"
  resource.labels.service_name="vidgo-backend" textPayload:"sqlalchemy.engine"' \
  --project vidgo-ai --limit 1 --freshness=5m     # expect empty
```

Roll back by pointing the service at the previous revision:
`gcloud run services update-traffic <svc> --to-revisions <rev>=100 --project vidgo-ai --region asia-east1`.

---

## Release checklist

1. `git push origin main` — the deployed code must be in the repo.
2. Migration needed? → build image → run migration job → **then** swap services.
3. `bash gcp/deploy-service.sh --backend --frontend`, **then swap `vidgo-worker` to the same digest.**
4. Health-check backend + frontend; confirm the worker logged "Starting worker for …".
5. `ServicePricing` / plan rows changed? → run `backend/scripts/seed_new_pricing_tiers.py`
   via a job (credit charges fall back to in-code constants until the rows exist).
   Do **not** seed a `service_type` whose deduct passes a computed total
   (e.g. `interior_batch_render`) — a seeded row REPLACES the total with a
   single per-use price (the "deduction firewall").
6. PayPal dashboard: the webhook must subscribe to `CHECKOUT.ORDER.APPROVED`,
   `PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.REFUNDED`, `PAYMENT.SALE.REFUNDED`.

## Related docs

- Infra layout: [vidgo-infra-architecture.md](./vidgo-infra-architecture.md)
- First-time DNS / payment bring-up: [setup_guide.md](./setup_guide.md),
  [dns-and-ecpay-setup.md](./dns-and-ecpay-setup.md), [PAYPAL_SETUP.md](./PAYPAL_SETUP.md)
- Costs & margins: [service-cost.md](./service-cost.md)
- Demo cache internals: [example-mode-cache-system.md](./example-mode-cache-system.md)
