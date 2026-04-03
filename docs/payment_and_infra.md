# VidGo AI - Payment & Invoice Infrastructure Setup Guide

**Company**: 瞬影科技股份有限公司
**Unified Business Number (統一編號)**: 96003146
**Date**: 2026-03-30

---

## Table of Contents

1. [Overview](#1-overview)
2. [GoDaddy DNS & Fixed IP Setup](#2-godaddy-dns--fixed-ip-setup)
3. [ECPay Payment Integration (Real)](#3-ecpay-payment-integration-real)
4. [Giveme E-Invoice Integration](#4-giveme-e-invoice-integration)
5. [Environment Variables & Secrets](#5-environment-variables--secrets)
6. [Backend Code Changes Required](#6-backend-code-changes-required)
7. [Deployment Checklist](#7-deployment-checklist)

---

## 1. Overview

### Current State
- **Payment**: Paddle (sandbox key `pdl_sdbx_...`) — mock mode
- **E-Invoice**: ECPay E-Invoice API (sandbox) — not connected
- **DNS**: Cloud Run auto-generated URLs (`*.run.app`)

### Target State
- **Payment**: ECPay (real production) — Taiwan credit card
- **E-Invoice**: Giveme 電子發票加值中心 — B2C/B2B invoicing
- **DNS**: Custom domain via GoDaddy → Cloud Run
- **Fixed IP**: Cloud NAT (for Giveme IP whitelist)

---

## 2. GoDaddy DNS & Fixed IP Setup

### 2.1 Get Cloud Run Fixed IP (for API whitelisting)

Cloud Run uses dynamic IPs. For Giveme's IP whitelist, you need a **fixed outbound IP** via Cloud NAT.

**Your current Cloud NAT** (from deploy.sh):
```bash
# Check existing NAT IP
gcloud compute routers nats describe vidgo-nat \
  --router=vidgo-router \
  --region=asia-east1 \
  --project=vidgo-ai \
  --format="value(natIps)"

# If no static IP, create one:
gcloud compute addresses create vidgo-nat-ip \
  --region=asia-east1 \
  --project=vidgo-ai

# Get the IP:
gcloud compute addresses describe vidgo-nat-ip \
  --region=asia-east1 \
  --project=vidgo-ai \
  --format="value(address)"
```

**This IP is what you whitelist in Giveme and ECPay.**

### 2.2 GoDaddy Custom Domain Setup

**Goal**: `api.vidgo.ai` → backend, `app.vidgo.ai` → frontend

```bash
# Step 1: Map custom domain to Cloud Run backend
gcloud run domain-mappings create \
  --service=vidgo-backend \
  --domain=api.vidgo.ai \
  --region=asia-east1 \
  --project=vidgo-ai

# Step 2: Map custom domain to Cloud Run frontend
gcloud run domain-mappings create \
  --service=vidgo-frontend \
  --domain=app.vidgo.ai \
  --region=asia-east1 \
  --project=vidgo-ai

# Step 3: Get the DNS records to add in GoDaddy
gcloud run domain-mappings describe \
  --domain=api.vidgo.ai \
  --region=asia-east1 \
  --format="yaml(resourceRecords)"
```

**In GoDaddy DNS Manager, add:**

| Type | Name | Value | TTL |
|------|------|-------|-----|
| CNAME | api | ghs.googlehosted.com | 3600 |
| CNAME | app | ghs.googlehosted.com | 3600 |

**Wait 15-30 minutes for DNS propagation.**

### 2.3 SSL Certificate

Cloud Run automatically provisions SSL for custom domains via Let's Encrypt. No action needed.

---

## 3. ECPay Payment Integration (Real)

### 3.1 ECPay Account Info (from your screenshots)

| Setting | Value |
|---------|-------|
| **商店代號 (MerchantID)** | `3422044` |
| **HashKey** | `fwNTpcFCaGaiOOt7` |
| **HashIV** | `Xv8pXkFk8zEGqv3T` |
| **使用版本** | 2:網路版 |
| **啟用功能** | 金流, 物流, 綁定會員 |

### 3.2 ECPay URLs to Configure

**In ECPay Merchant Dashboard (https://vendor.ecpay.com.tw):**

| Setting | Value |
|---------|-------|
| **查詢訂單網址** | `https://api.vidgo.ai/api/v1/payments/ecpay/query` |
| **付款通知網址** | `https://api.vidgo.ai/api/v1/payments/ecpay/callback` |
| **付款完成返回網址** | `https://app.vidgo.ai/subscription/ecpay-result` |

**If using Cloud Run URLs (before custom domain):**

| Setting | Value |
|---------|-------|
| **付款通知網址** | `https://vidgo-backend-38714015566.asia-east1.run.app/api/v1/payments/ecpay/callback` |
| **付款完成返回網址** | `https://vidgo-frontend-38714015566.asia-east1.run.app/subscription/ecpay-result` |

### 3.3 ECPay API Endpoints

| Environment | Payment URL |
|-------------|------------|
| **Sandbox (測試)** | `https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V2` |
| **Production (正式)** | `https://payment.ecpay.com.tw/Cashier/AioCheckOut/V2` |

### 3.4 ECPay IP Whitelist

**In ECPay Dashboard → 系統介接設定 → 允許的IP:**

Add the Cloud NAT static IP from step 2.1.

### 3.5 Environment Variables for ECPay

```env
ECPAY_ENV=production
ECPAY_MERCHANT_ID=3422044
ECPAY_HASH_KEY=fwNTpcFCaGaiOOt7
ECPAY_HASH_IV=Xv8pXkFk8zEGqv3T
ECPAY_PAYMENT_URL=https://payment.ecpay.com.tw/Cashier/AioCheckOut/V2
```

---

## 4. Giveme E-Invoice Integration

### 4.1 Giveme Account Setup

**Provider**: Giveme 電子發票加值中心 (https://www.giveme.com.tw)

**Required Info to Provide Giveme:**

| Field | Value |
|-------|-------|
| **公司名稱** | 瞬影科技股份有限公司 |
| **統一編號** | 96003146 |
| **公司電話-分機** | *(fill your phone)* |
| **聯絡人** | *(fill your name)* |
| **貴司固定IP** | *(Cloud NAT IP from step 2.1)* |

### 4.2 Giveme Backend Settings

After Giveme creates your account:
1. **系統設定 → 員工設定** → Create API account + complex password
2. **系統設定 → 白名單設定** → Add your Cloud NAT static IP

### 4.3 Giveme API Spec

**Base URL**: `https://www.giveme.com.tw/invoice.do`

**Authentication**: Sign = MD5(timeStamp + idno + password).toUpperCase()

| Action | URL | Method |
|--------|-----|--------|
| **B2C Invoice** | `?action=addB2C` | POST |
| **B2B Invoice** | `?action=addB2B` | POST |
| **Void Invoice** | `?action=cancelInvoice` | POST |
| **Print Invoice** | `?action=invoicePrint` | GET |
| **Invoice Image** | `?action=picture` | POST |
| **Query Invoice** | `?action=query` | POST |

### 4.4 B2C Invoice Request Format

```json
{
  "timeStamp": "1711800000000",
  "uncode": "96003146",
  "idno": "YOUR_API_ACCOUNT",
  "sign": "MD5(timeStamp+idno+password).toUpperCase()",
  "customerName": "VidGo AI Subscription",
  "phone": "/1234567",
  "orderCode": "VIDGO-ORD-20260330-001",
  "datetime": "2026-03-30",
  "email": "customer@example.com",
  "state": "0",
  "totalFee": "999",
  "content": "VidGo AI Pro Plan - Monthly",
  "items": [
    {
      "name": "VidGo AI Pro Plan Monthly",
      "money": 999,
      "number": 1
    }
  ]
}
```

### 4.5 B2C Invoice Response

```json
{
  "success": "true",
  "code": "AB12345678",
  "totalFee": "999",
  "orderCode": "VIDGO-ORD-20260330-001",
  "phone": "/1234567"
}
```

### 4.6 Void Invoice Request

```json
{
  "timeStamp": "1711800000000",
  "uncode": "96003146",
  "idno": "YOUR_API_ACCOUNT",
  "sign": "MD5(timeStamp+idno+password).toUpperCase()",
  "code": "AB12345678",
  "remark": "Customer refund"
}
```

### 4.7 Environment Variables for Giveme

```env
GIVEME_ENABLED=true
GIVEME_BASE_URL=https://www.giveme.com.tw/invoice.do
GIVEME_UNCODE=96003146
GIVEME_IDNO=YOUR_API_ACCOUNT
GIVEME_PASSWORD=YOUR_API_PASSWORD
```

---

## 5. Environment Variables & Secrets

### 5.1 All Secrets to Add to GCP Secret Manager

```bash
PROJECT_ID="vidgo-ai"

# ECPay Production
gcloud secrets create ECPAY_MERCHANT_ID --project=$PROJECT_ID --data-file=- <<< "3422044"
gcloud secrets create ECPAY_HASH_KEY --project=$PROJECT_ID --data-file=- <<< "fwNTpcFCaGaiOOt7"
gcloud secrets create ECPAY_HASH_IV --project=$PROJECT_ID --data-file=- <<< "Xv8pXkFk8zEGqv3T"

# Giveme E-Invoice
gcloud secrets create GIVEME_IDNO --project=$PROJECT_ID --data-file=- <<< "qaz0978005418"
gcloud secrets create GIVEME_PASSWORD --project=$PROJECT_ID --data-file=- <<< "qaz129946858"
```

### 5.2 Cloud Run Environment Variables

Add to `gcloud run deploy` command:

```bash
--set-env-vars="...,ECPAY_ENV=production,ECPAY_PAYMENT_URL=https://payment.ecpay.com.tw/Cashier/AioCheckOut/V2,GIVEME_ENABLED=true,GIVEME_BASE_URL=https://www.giveme.com.tw/invoice.do,GIVEME_UNCODE=96003146"

--set-secrets="...,ECPAY_MERCHANT_ID=ECPAY_MERCHANT_ID:latest,ECPAY_HASH_KEY=ECPAY_HASH_KEY:latest,ECPAY_HASH_IV=ECPAY_HASH_IV:latest,GIVEME_IDNO=GIVEME_IDNO:latest,GIVEME_PASSWORD=GIVEME_PASSWORD:latest"
```

---

## 6. Backend Code Changes Required

### 6.1 Create Giveme Invoice Client

**New file**: `backend/app/services/giveme/client.py`

Implement the Giveme API according to the PDF spec:
- `create_b2c_invoice()` — B2C invoice with carrier/donation support
- `create_b2b_invoice()` — B2B invoice with buyer tax ID
- `void_invoice()` — Void invoice by code
- `query_invoice()` — Query invoice status
- Sign generation: `MD5(timeStamp + idno + password).toUpperCase()`

### 6.2 Add Giveme Config to `config.py`

```python
# Giveme E-Invoice
GIVEME_ENABLED: bool = False
GIVEME_BASE_URL: str = "https://www.giveme.com.tw/invoice.do"
GIVEME_UNCODE: str = ""      # Company unified business number (統一編號)
GIVEME_IDNO: str = ""        # API account
GIVEME_PASSWORD: str = ""    # API password
```

### 6.3 Update Invoice Service

Replace or supplement the ECPay einvoice client with Giveme:
- After successful payment → auto-issue B2C invoice via Giveme
- After refund → auto-void invoice via Giveme
- Store invoice number in Order/Subscription record

### 6.4 Switch ECPay from Sandbox to Production

In `backend/app/core/config.py`:
```python
ECPAY_ENV: str = "production"  # Changed from "sandbox"
ECPAY_PAYMENT_URL: str = "https://payment.ecpay.com.tw/Cashier/AioCheckOut/V2"
```

### 6.5 Update Frontend ECPay Return URL

In `frontend-vue/src/views/Pricing.vue`, ensure the ECPay return URL points to production:
```
https://app.vidgo.ai/subscription/ecpay-result
```

---

## 7. Deployment Checklist

### Pre-deployment

- [ ] Get Cloud NAT static IP
- [ ] Configure GoDaddy DNS (api.vidgo.ai, app.vidgo.ai)
- [ ] Wait for DNS propagation (15-30 min)
- [ ] Configure ECPay merchant dashboard:
  - [ ] Set callback URLs
  - [ ] Whitelist Cloud NAT IP
- [ ] Contact Giveme to set up API account:
  - [ ] Company: 瞬影科技股份有限公司
  - [ ] 統一編號: 96003146
  - [ ] Provide fixed IP (Cloud NAT)
- [ ] Set Giveme backend:
  - [ ] Create API account (系統設定 → 員工設定)
  - [ ] Whitelist IP (系統設定 → 白名單設定)
- [ ] Add secrets to GCP Secret Manager

### Code Changes

- [ ] Create `backend/app/services/giveme/client.py`
- [ ] Add Giveme config to `config.py`
- [ ] Update invoice service to use Giveme
- [ ] Switch ECPay to production URLs
- [ ] Update `PUBLIC_APP_URL` to custom domain
- [ ] Update `FRONTEND_URL` to custom domain

### Deployment

- [ ] Build and push new backend image
- [ ] Deploy with new env vars and secrets
- [ ] Test ECPay payment flow end-to-end
- [ ] Test Giveme B2C invoice issuance
- [ ] Test invoice voiding
- [ ] Verify Cloud NAT IP works with Giveme whitelist

### Post-deployment Verification

- [ ] ECPay payment creates real charge
- [ ] Invoice issued after payment
- [ ] Invoice number stored in database
- [ ] Refund triggers invoice void
- [ ] Frontend shows invoice in dashboard
- [ ] Custom domain working (api.vidgo.ai, app.vidgo.ai)

---

## Appendix: Giveme vs ECPay E-Invoice Comparison

| Feature | Giveme | ECPay E-Invoice |
|---------|--------|-----------------|
| B2C Invoice | Yes | Yes |
| B2B Invoice | Yes | Yes |
| Void Invoice | Yes | Yes |
| Print (thermal) | Yes (cloud printer) | No |
| Image Print | Yes | No |
| Query | Yes | Yes |
| API Auth | MD5 sign | CheckMacValue SHA256 |
| IP Whitelist | Required | Optional |
| Carrier (載具) | Phone barcode + custom | Phone barcode + natural person |
| Donation (捐贈) | Yes | Yes |
| Mixed Tax (混合稅) | Yes | Limited |

**Recommendation**: Use **Giveme** for e-invoicing (more features, thermal printer support) and **ECPay** for payment processing only.
