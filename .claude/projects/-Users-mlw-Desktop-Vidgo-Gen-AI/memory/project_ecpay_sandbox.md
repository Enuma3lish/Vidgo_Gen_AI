---
name: ECPay Sandbox Behavior
description: ECPay Stage environment (MID 2000132) auto-sets invoice status to '已上傳' (uploaded) after issuance due to unstable 財政部 Stage system
type: project
---

ECPay Stage (sandbox) environment with MID 2000132 has a known behavior: after successfully issuing an e-invoice, the 財政部 (Ministry of Finance) Stage system directly sets the status to "已上傳" (uploaded), unlike production where it stays "issued" until the next upload batch.

**Why:** The 財政部 Stage system is unstable and behaves differently from production.

**How to apply:** When handling invoice status checks (void eligibility, display, etc.), treat both "issued" and "uploaded" as valid active statuses. The `ECPAY_ENV` setting in `.env` controls sandbox vs production mode. The code uses `_invoice_status_after_issue()` helper in `invoice_service.py` to set the correct status.
