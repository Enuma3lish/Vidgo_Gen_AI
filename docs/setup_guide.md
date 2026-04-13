# VidGo AI — Production Setup Guide

**Company**: 瞬影科技股份有限公司 (Sunying Technology Co., Ltd.)
**統一編號**: 96003146
**Last Updated**: 2026-03-30

---

## Part 1: GoDaddy DNS & Custom Domain

### Step 1.1: Reserve a Static IP for Cloud NAT

Cloud Run uses dynamic IPs. Both Giveme and ECPay require IP whitelisting.

```bash
# Create a static IP
gcloud compute addresses create vidgo-nat-ip \
  --region=asia-east1 --project=vidgo-ai

# Get the IP address
gcloud compute addresses describe vidgo-nat-ip \
  --region=asia-east1 --project=vidgo-ai \
  --format="value(address)"
# >>> Example: 35.201.xxx.xxx  <-- SAVE THIS IP

# Attach to Cloud NAT router
gcloud compute routers nats update vidgo-nat \
  --router=vidgo-router \
  --region=asia-east1 \
  --nat-external-ip-pool=vidgo-nat-ip \
  --project=vidgo-ai
```

### Step 1.2: Map Custom Domain to Cloud Run

```bash
# Set region first (domain-mappings doesn't accept --region directly)
gcloud config set run/region asia-east1

# Map api subdomain to backend
gcloud beta run domain-mappings create \
  --service=vidgo-backend \
  --domain=api.vidgo.co \
  --project=vidgo-ai

# Map app subdomain to frontend
gcloud beta run domain-mappings create \
  --service=vidgo-frontend \
  --domain=app.vidgo.co \
  --project=vidgo-ai

# Get DNS records to add
gcloud beta run domain-mappings describe \
  --domain=api.vidgo.co \
  --format="yaml(resourceRecords)"
```

### Step 1.3: Configure GoDaddy DNS

1. Login to GoDaddy → **DNS Management** for `vidgo.co`
2. Add these records:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| CNAME | `api` | `ghs.googlehosted.com` | 3600 |
| CNAME | `app` | `ghs.googlehosted.com` | 3600 |

3. Wait 15-30 minutes for propagation
4. Verify: `curl https://api.vidgo.co/health`

---

## Part 2: ECPay Payment (Real Production)

### Step 2.1: Your ECPay Credentials

From your ECPay merchant dashboard:

| Setting | Value |
|---------|-------|
| **商店代號 (MerchantID)** | `3422044` |
| **HashKey** | `fwNTpcFCaGaiOOt7` |
| **HashIV** | `Xv8pXkFk8zEGqv3T` |

### Step 2.2: Configure ECPay Merchant Dashboard

Login: https://vendor.ecpay.com.tw

**System Settings → 系統介接設定:**

| Field | Value |
|-------|-------|
| **查詢訂單網址** | `https://api.vidgo.co/api/v1/payments/ecpay/query` |
| **付款通知網址** | `https://api.vidgo.co/api/v1/payments/ecpay/callback` |

> **If using Cloud Run URLs (before custom domain):**
> - 付款通知網址: `https://vidgo-backend-38714015566.asia-east1.run.app/api/v1/payments/ecpay/callback`

**System Settings → 介接設定 → 允許的IP:**
- Add your Cloud NAT static IP from Step 1.1

### Step 2.3: Add Secrets to GCP

```bash
# ECPay Production credentials
echo -n "3422044" | gcloud secrets create ECPAY_MERCHANT_ID \
  --project=vidgo-ai --data-file=-

echo -n "fwNTpcFCaGaiOOt7" | gcloud secrets create ECPAY_HASH_KEY \
  --project=vidgo-ai --data-file=-

echo -n "Xv8pXkFk8zEGqv3T" | gcloud secrets create ECPAY_HASH_IV \
  --project=vidgo-ai --data-file=-
```

> **If secrets already exist**, use `gcloud secrets versions add` instead:
> ```bash
> echo -n "3422044" | gcloud secrets versions add ECPAY_MERCHANT_ID \
>   --project=vidgo-ai --data-file=-
> ```

### Step 2.4: Update Deploy Command

Add to `--set-env-vars`:
```
ECPAY_ENV=production
ECPAY_PAYMENT_URL=https://payment.ecpay.com.tw/Cashier/AioCheckOut/V2
```

Add to `--set-secrets`:
```
ECPAY_MERCHANT_ID=ECPAY_MERCHANT_ID:latest
ECPAY_HASH_KEY=ECPAY_HASH_KEY:latest
ECPAY_HASH_IV=ECPAY_HASH_IV:latest
```

---

## Part 3: Giveme E-Invoice (電子發票)

### Step 3.1: Contact Giveme

**Send to Giveme support (Line @giveme):**

```
公司名稱: 瞬影科技股份有限公司
統一編號: 96003146
公司電話-分機: (your phone number)
聯絡人: (your name)
貴司固定IP: (Cloud NAT IP from Step 1.1)
```

### Step 3.2: Giveme Backend Setup (After Account Created)

Login to Giveme management console.

1. **系統設定 → 員工設定:**
   - Click "新增" (Add)
   - Create an API account with a complex password (英數大小寫+數字)
   - Example: Account=`vidgo_api`, Password=`V1dG0!Api#2026`
   - **SAVE these — you'll need them for GCP secrets**

2. **系統設定 → 白名單設定:**
   - Add your Cloud NAT static IP from Step 1.1
   - If multiple IPs, separate with semicolons

### Step 3.3: Add Giveme Secrets to GCP

```bash
echo -n "vidgo_api" | gcloud secrets create GIVEME_IDNO \
  --project=vidgo-ai --data-file=-

echo -n "V1dG0!Api#2026" | gcloud secrets create GIVEME_PASSWORD \
  --project=vidgo-ai --data-file=-
```

### Step 3.4: Update Deploy Command

Add to `--set-env-vars`:
```
GIVEME_ENABLED=true
GIVEME_BASE_URL=https://www.giveme.com.tw/invoice.do
GIVEME_UNCODE=96003146
```

Add to `--set-secrets`:
```
GIVEME_IDNO=GIVEME_IDNO:latest
GIVEME_PASSWORD=GIVEME_PASSWORD:latest
```

### Step 3.5: Giveme API Endpoints Reference

| Action | URL | Description |
|--------|-----|-------------|
| B2C 發票新增 | `?action=addB2C` | General consumer invoice |
| B2B 發票新增 | `?action=addB2B` | Business invoice with 統一編號 |
| 發票作廢 | `?action=cancelInvoice` | Void invoice |
| 發票查詢 | `?action=query` | Query invoice details |
| 發票列印 (網頁) | `?action=invoicePrint` | Web print view |
| 發票圖片列印 | `?action=picture` | Get invoice as image |

**Auth**: `sign = MD5(timeStamp + idno + password).toUpperCase()`

---

## Part 4: Full Deployment

### Step 4.1: Build and Deploy Backend

```bash
IMAGE_TAG=$(date +%Y%m%d-%H%M%S)

# Build
docker build \
  -t "asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images/vidgo-backend:${IMAGE_TAG}" \
  -f backend/Dockerfile backend/

# Push
docker push "asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images/vidgo-backend:${IMAGE_TAG}"

# Deploy with all env vars
gcloud run deploy vidgo-backend \
  --image="asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images/vidgo-backend:${IMAGE_TAG}" \
  --project=vidgo-ai --region=asia-east1 --platform=managed \
  --min-instances=1 --max-instances=10 \
  --memory=1Gi --cpu=1 --port=8000 --timeout=300 \
  --vpc-connector="projects/vidgo-ai/locations/asia-east1/connectors/vidgo-connector" \
  --add-cloudsql-instances="vidgo-ai:asia-east1:prod-db" \
  --service-account="vidgo-backend@vidgo-ai.iam.gserviceaccount.com" \
  --set-env-vars="\
SKIP_PREGENERATION=true,\
SKIP_DEPENDENCY_CHECK=true,\
DEBUG=false,\
ALGORITHM=HS256,\
ACCESS_TOKEN_EXPIRE_MINUTES=30,\
REFRESH_TOKEN_EXPIRE_DAYS=7,\
PUBLIC_APP_URL=https://api.vidgo.co,\
FRONTEND_URL=https://app.vidgo.co,\
BACKEND_URL=https://api.vidgo.co,\
ECPAY_ENV=production,\
ECPAY_PAYMENT_URL=https://payment.ecpay.com.tw/Cashier/AioCheckOut/V2,\
GIVEME_ENABLED=true,\
GIVEME_BASE_URL=https://www.giveme.com.tw/invoice.do,\
GIVEME_UNCODE=96003146,\
VERTEX_AI_PROJECT=vidgo-ai,\
VERTEX_AI_LOCATION=us-central1,\
VEO_MODEL=veo-3.0-generate-preview,\
GEMINI_MODEL=gemini-2.0-flash" \
  --set-secrets="\
DATABASE_URL=DATABASE_URL:latest,\
REDIS_URL=REDIS_URL:latest,\
SECRET_KEY=SECRET_KEY:latest,\
PIAPI_KEY=PIAPI_KEY:latest,\
POLLO_API_KEY=POLLO_API_KEY:latest,\
A2E_API_KEY=A2E_API_KEY:latest,\
A2E_API_ID=A2E_API_ID:latest,\
A2E_DEFAULT_CREATOR_ID=A2E_DEFAULT_CREATOR_ID:latest,\
PADDLE_API_KEY=PADDLE_API_KEY:latest,\
SMTP_HOST=SMTP_HOST:latest,\
SMTP_PORT=SMTP_PORT:latest,\
SMTP_USER=SMTP_USER:latest,\
SMTP_PASSWORD=SMTP_PASSWORD:latest,\
ECPAY_MERCHANT_ID=ECPAY_MERCHANT_ID:latest,\
ECPAY_HASH_KEY=ECPAY_HASH_KEY:latest,\
ECPAY_HASH_IV=ECPAY_HASH_IV:latest,\
GIVEME_IDNO=GIVEME_IDNO:latest,\
GIVEME_PASSWORD=GIVEME_PASSWORD:latest" \
  --allow-unauthenticated
```

### Step 4.2: Deploy Frontend

```bash
docker build \
  -t "asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images/vidgo-frontend:${IMAGE_TAG}" \
  -f frontend-vue/Dockerfile.prod frontend-vue/

docker push "asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images/vidgo-frontend:${IMAGE_TAG}"

gcloud run deploy vidgo-frontend \
  --image="asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images/vidgo-frontend:${IMAGE_TAG}" \
  --project=vidgo-ai --region=asia-east1 --platform=managed \
  --min-instances=0 --max-instances=4 \
  --memory=256Mi --cpu=1 --port=80 \
  --service-account="vidgo-frontend@vidgo-ai.iam.gserviceaccount.com" \
  --set-env-vars="BACKEND_URL=https://api.vidgo.co" \
  --allow-unauthenticated
```

---

## Part 5: Testing Checklist

### 5.1: ECPay Payment Test

```bash
# Login
TOKEN=$(curl -s -X POST https://api.vidgo.co/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"YOUR_EMAIL","password":"YOUR_PASS"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['tokens']['access'])")

# Subscribe via ECPay
curl -s -X POST https://api.vidgo.co/api/v1/subscriptions/subscribe \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"plan_id":"PLAN_UUID","billing_cycle":"monthly","payment_method":"ecpay"}'

# Should return: { "success": true, "ecpay_form": { "action_url": "https://payment.ecpay.com.tw/...", "params": {...} } }
```

### 5.2: Giveme Invoice Test

```bash
# After payment succeeds, check if invoice was auto-issued:
curl -s https://api.vidgo.co/api/v1/einvoices \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Manual B2C invoice test:
curl -s -X POST https://api.vidgo.co/api/v1/einvoices/b2c \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "ORDER_UUID",
    "buyer_email": "test@example.com",
    "tax_type": "taxable",
    "carrier_type": "mobile_barcode",
    "carrier_number": "/1234567",
    "is_donation": false,
    "items": [{"item_name": "VidGo Pro Plan", "item_count": 1, "item_price": 999}]
  }'
```

### 5.3: Verify Invoice Voiding

```bash
curl -s -X POST https://api.vidgo.co/api/v1/einvoices/void \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"invoice_id": "INVOICE_UUID", "reason": "Test void"}'
```

---

## Part 6: Architecture Summary

```
┌─────────────┐    ┌──────────────┐    ┌────────────────┐
│   Frontend   │───→│   Backend    │───→│  Cloud SQL DB  │
│  (app.vidgo) │    │ (api.vidgo)  │    │  (PostgreSQL)  │
└─────────────┘    └──────┬───────┘    └────────────────┘
                          │
                 ┌────────┼────────┐
                 │        │        │
           ┌─────▼──┐ ┌──▼───┐ ┌──▼──────┐
           │ ECPay  │ │Giveme│ │ PiAPI   │
           │Payment │ │E-Inv │ │ AI APIs │
           └────────┘ └──────┘ └─────────┘
                │         │
           Credit Card  電子發票
           (TWD)        (Taiwan)
```

### Invoice Flow

```
User subscribes (ECPay credit card)
    ↓
ECPay callback → Order marked "paid"
    ↓
Subscription activated → Credits allocated
    ↓
Auto-issue invoice (Giveme B2C)
    ↓
Invoice number returned (e.g. AB12345678)
    ↓
Stored in DB → User sees in dashboard
```

---

## Part 7: Important Notes

### Security
- **Never commit** ECPay HashKey/HashIV or Giveme password to git
- Always use GCP Secret Manager for credentials
- ECPay and Giveme both require IP whitelisting

### Taiwan Tax Requirements
- All subscriptions must issue 電子發票
- Tax period: bimonthly (1-2月, 3-4月, 5-6月, 7-8月, 9-10月, 11-12月)
- Invoice voiding only within current period
- 5% VAT included in all prices

### Giveme vs ECPay E-Invoice
- **Current code supports both** — controlled by `GIVEME_ENABLED` env var
- `GIVEME_ENABLED=true` → Giveme handles all invoicing
- `GIVEME_ENABLED=false` → ECPay handles all invoicing
- Switch is transparent to users and frontend

### Cloud NAT IP
- The static IP is for **outbound** traffic only (API calls to ECPay/Giveme)
- Cloud Run **inbound** traffic uses Google's managed IPs
- ECPay callback URL must be the Cloud Run URL (not the NAT IP)
