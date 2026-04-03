# VidGo Production Setup Guide — DNS & ECPay

**Domain**: vidgo.co
**Company**: 瞬影科技股份有限公司 (統一編號: 96003146)
**ECPay MerchantID**: 3422044

---

## 1. GoDaddy DNS Setup

### 1.1 Log in to GoDaddy

1. Go to **https://dcc.godaddy.com/** (Domain Control Center)
2. Sign in to your GoDaddy account
3. Find **vidgo.co** → click **DNS** (or "Manage DNS")

### 1.2 Delete Conflicting Records

Before adding new records, **delete** any existing:
- Default **A record** for `@` (GoDaddy parked page)
- Any existing `www` or `api` CNAME records

### 1.3 Add DNS Records

Click **Add New Record** for each:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| **A** | `@` | *(see Step 1.4 below)* | 600 |
| **CNAME** | `www` | `ghs.googlehosted.com` | 3600 |
| **CNAME** | `api` | `ghs.googlehosted.com` | 3600 |

> **Note**: GoDaddy does **NOT** allow CNAME on root domain (`@`).
> Choose one of the two options below for the root domain.

### 1.4 Root Domain (`@`) — Choose One Option

#### Option A: Forwarding (Recommended)

1. In GoDaddy, go to **Forwarding** tab (under your domain settings)
2. Add a **Domain Forward**:
   - Forward from: `vidgo.co`
   - Forward to: `https://www.vidgo.co`
   - Type: **301 Permanent**
   - Settings: **Forward Only**
3. This way `vidgo.co` → `https://www.vidgo.co` → Cloud Run frontend

#### Option B: A Record

1. Run the Cloud Run domain mapping first (Step 2), then get the required IP:
   ```bash
   gcloud run domain-mappings describe \
     --domain=vidgo.co \
     --region=asia-east1 \
     --project=vidgo-ai \
     --format="yaml(resourceRecords)"
   ```
2. It will return an IP like `216.239.32.21`
3. Add that as an **A record** for `@` in GoDaddy

### 1.5 Verify DNS Propagation

Wait **15–30 minutes**, then run:

```bash
# Check api subdomain
dig api.vidgo.co CNAME

# Check www subdomain
dig www.vidgo.co CNAME

# Check root domain
dig vidgo.co A
```

Expected results:
- `api.vidgo.co` → `ghs.googlehosted.com`
- `www.vidgo.co` → `ghs.googlehosted.com`
- `vidgo.co` → Cloud Run IP or forwarding

---

## 2. Cloud Run Domain Mapping

After DNS records are set, run:

```bash
# Map api.vidgo.co → backend
bash gcp/deploy.sh --step domain

# Then redeploy services with correct URLs
bash gcp/deploy.sh --step deploy
```

This creates the domain mappings:
- `api.vidgo.co` → `vidgo-backend`
- `vidgo.co` → `vidgo-frontend`
- `www.vidgo.co` → `vidgo-frontend`

**SSL certificates** are auto-provisioned by Cloud Run (Let's Encrypt) ~15 minutes after DNS resolves.

---

## 3. Get NAT Static IP

You need this IP for both ECPay and Giveme whitelists:

```bash
gcloud compute addresses describe vidgo-nat-ip \
  --region=asia-east1 \
  --project=vidgo-ai \
  --format="value(address)"
```

Save this IP — you will use it in Steps 4 and 5.

---

## 4. ECPay Merchant Dashboard Setup

### 4.1 Log in

1. Go to **https://vendor.ecpay.com.tw**
2. Sign in with merchant account (商店代號: `3422044`)

### 4.2 Set Callback URLs

1. Navigate to: **系統開發管理** → **系統介接設定**
2. Update the following fields:

| Setting (欄位) | Value (值) |
|---|---|
| **付款完成通知回傳網址 (ReturnURL)** | `https://api.vidgo.co/api/v1/payments/ecpay/callback` |
| **訂單查詢網址 (OrderResultURL)** | `https://api.vidgo.co/api/v1/payments/ecpay/query` |
| **Client 端返回商店網址 (ClientBackURL)** | `https://vidgo.co/subscription/ecpay-result` |

3. Click **儲存 (Save)**

### 4.3 Whitelist NAT IP

1. Still in **系統介接設定**, find **允許的 Server 端 IP**
2. Add the NAT static IP from Step 3
3. Click **儲存 (Save)**

---

## 5. Giveme E-Invoice Whitelist

1. Log in to Giveme backend: **https://www.giveme.com.tw**
2. Go to **系統設定** → **白名單設定**
3. Add the NAT static IP from Step 3
4. Save

---

## 6. Verification Checklist

### Order of Operations

1. GoDaddy DNS records (wait 15–30 min for propagation)
2. Deploy domain mappings (`bash gcp/deploy.sh --step domain`)
3. Deploy services (`bash gcp/deploy.sh --step deploy`)
4. Wait for SSL certificate (~15 min after DNS resolves)
5. Configure ECPay dashboard (after `https://api.vidgo.co` is live)
6. Configure Giveme whitelist
7. Test end-to-end

### Test Commands

```bash
# 1. Check DNS resolution
dig api.vidgo.co CNAME
dig www.vidgo.co CNAME

# 2. Check SSL & backend health
curl https://api.vidgo.co/health

# 3. Check ECPay callback route exists (should return error, not 404)
curl -X POST https://api.vidgo.co/api/v1/payments/ecpay/callback

# 4. Check frontend loads
curl -I https://vidgo.co
curl -I https://www.vidgo.co
```

### Production Checklist

- [ ] GoDaddy DNS: `api` CNAME → `ghs.googlehosted.com`
- [ ] GoDaddy DNS: `www` CNAME → `ghs.googlehosted.com`
- [ ] GoDaddy DNS: `@` A record or forwarding to `www.vidgo.co`
- [ ] Cloud Run domain mapping created (Step 2)
- [ ] SSL certificate provisioned (auto, ~15 min)
- [ ] ECPay: 付款完成通知回傳網址 set
- [ ] ECPay: 訂單查詢網址 set
- [ ] ECPay: Client 端返回商店網址 set
- [ ] ECPay: NAT IP whitelisted
- [ ] Giveme: NAT IP whitelisted
- [ ] `curl https://api.vidgo.co/health` returns OK
- [ ] Small test payment completed successfully
- [ ] Invoice issued after test payment
- [ ] Frontend accessible at `https://vidgo.co`
