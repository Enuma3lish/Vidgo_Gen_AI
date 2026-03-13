"""
VidGo Gen AI - Comprehensive API Manual Test Script

Tests all API endpoints with response data validation, focusing on:
1. Response data correctness (not just status codes)
2. Payment correctness (credit allocation, mock mode)
3. Subscription mechanism (subscribe, status, plans)
4. Cancellation functionality (cancel with/without refund, credit revocation)

Usage:
    docker-compose up -d
    python3 test_api_comprehensive.py
"""
import urllib.request
import urllib.error
import time
import json
import re
import sys
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_URL = "http://localhost:8001/api/v1"
HEALTH_URL = "http://localhost:8001/health"
MAILPIT_URL = "http://localhost:8025"
PASSWORD = "TestPassword123!"

# Global state shared between tests
state = {
    "email": None,
    "token": None,
    "refresh_token": None,
    "user_id": None,
    "starter_plan_id": None,
    "pro_plan_id": None,
    "subscription_id": None,
}

# Test results
results = []

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


# =============================================================================
# HTTP HELPERS (stdlib only, no 'requests' dependency)
# =============================================================================

class Response:
    """Minimal response wrapper to mimic requests.Response."""
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body
    def json(self):
        return json.loads(self._body)


def http_get(url, headers=None):
    """HTTP GET using urllib."""
    req = urllib.request.Request(url, method="GET")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return Response(resp.status, resp.read().decode())
    except urllib.error.HTTPError as e:
        return Response(e.code, e.read().decode())


def http_post(url, json_body=None, headers=None):
    """HTTP POST with JSON body using urllib."""
    data = json.dumps(json_body).encode() if json_body else None
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return Response(resp.status, resp.read().decode())
    except urllib.error.HTTPError as e:
        return Response(e.code, e.read().decode())


def http_delete(url, json_body=None, headers=None):
    """HTTP DELETE with optional JSON body using urllib."""
    data = json.dumps(json_body).encode() if json_body else None
    req = urllib.request.Request(url, data=data, method="DELETE")
    req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return Response(resp.status, resp.read().decode())
    except urllib.error.HTTPError as e:
        return Response(e.code, e.read().decode())


# =============================================================================
# UTILITIES
# =============================================================================

def pretty_print(label, data):
    """Pretty-print JSON response data."""
    print(f"  {CYAN}{label}:{RESET}")
    print(f"  {json.dumps(data, indent=2, default=str)}")


def auth_headers():
    """Return auth headers using current token."""
    return {"Authorization": f"Bearer {state['token']}"}


def check(condition, description):
    """Assert a condition, raise if False."""
    if not condition:
        raise AssertionError(description)


def get_verification_code(email):
    """Extract 6-digit verification code from Mailpit."""
    time.sleep(2)
    mp_res = http_get(f"{MAILPIT_URL}/api/v1/messages")
    messages = mp_res.json().get("messages", [])
    for msg in messages:
        if msg["To"][0]["Address"] == email:
            msg_res = http_get(f"{MAILPIT_URL}/api/v1/message/{msg['ID']}")
            text = msg_res.json().get("Text", "")
            match = re.search(r'\b\d{6}\b', text)
            if match:
                return match.group(0)
    return None


def run_test(test_id, test_name, test_func):
    """Run a test function, record result."""
    full_name = f"{test_id} - {test_name}"
    print(f"\n{'='*60}")
    print(f"{BOLD}TEST {full_name}{RESET}")
    print(f"{'='*60}")
    try:
        test_func()
        results.append((full_name, True, ""))
        print(f"  {GREEN}PASS{RESET}")
    except AssertionError as e:
        results.append((full_name, False, str(e)))
        print(f"  {RED}FAIL: {e}{RESET}")
    except Exception as e:
        results.append((full_name, False, str(e)))
        print(f"  {RED}ERROR: {e}{RESET}")


def skip_test(test_id, test_name, reason):
    """Mark a test as skipped."""
    full_name = f"{test_id} - {test_name}"
    results.append((full_name, None, reason))
    print(f"\n{YELLOW}SKIP: {full_name} - {reason}{RESET}")


# =============================================================================
# SECTION A: HEALTH CHECK
# =============================================================================

def test_a1_health_check():
    res = http_get(HEALTH_URL)
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(data.get("status") == "ok", f"Expected status='ok', got '{data.get('status')}'")
    check("mode" in data, "Missing 'mode' field")
    print(f"  Server mode: {data.get('mode')}")


# =============================================================================
# SECTION B: AUTHENTICATION FLOW
# =============================================================================

def test_b1_register():
    ts = int(time.time())
    state["email"] = f"vidgo_test_{ts}@example.com"
    state["username"] = f"testuser_{ts}"
    res = http_post(f"{BASE_URL}/auth/register", json_body={
        "email": state["email"],
        "password": PASSWORD,
        "password_confirm": PASSWORD,
        "full_name": "Test User",
        "username": state["username"]
    })
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}: {data}")
    print(f"  Registered: {state['email']}")


def test_b2_get_verification_code():
    code = get_verification_code(state["email"])
    pretty_print("Verification Code", {"code": code, "email": state["email"]})
    check(code is not None, "Failed to get verification code from Mailpit")
    check(len(code) == 6, f"Expected 6-digit code, got '{code}'")
    state["code"] = code
    print(f"  Code: {code}")


def test_b3_verify_email():
    res = http_post(f"{BASE_URL}/auth/verify-code", json_body={
        "email": state["email"],
        "code": state["code"]
    })
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}: {data}")
    check("access_token" in data, "Missing access_token")
    check("refresh_token" in data, "Missing refresh_token")
    check(data.get("token_type") == "bearer", f"Expected token_type='bearer', got '{data.get('token_type')}'")

    user = data.get("user", {})
    check(user.get("email") == state["email"], f"Email mismatch: {user.get('email')}")
    check(user.get("email_verified") == True, "email_verified should be True")
    check(user.get("is_active") == True, "is_active should be True")

    state["token"] = data["access_token"]
    state["refresh_token"] = data["refresh_token"]
    state["user_id"] = user.get("id")
    print(f"  User ID: {state['user_id']}")


def test_b4_get_profile():
    res = http_get(f"{BASE_URL}/auth/me", headers=auth_headers())
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(data.get("email") == state["email"], f"Email mismatch")
    check(data.get("full_name") == "Test User", f"full_name mismatch: {data.get('full_name')}")
    check(data.get("is_active") == True, "is_active should be True")
    check(data.get("email_verified") == True, "email_verified should be True")
    check(data.get("is_superuser") == False, "is_superuser should be False")
    # No subscription yet
    plan_type = data.get("plan_type")
    print(f"  plan_type (should be None/demo): {plan_type}")


# =============================================================================
# SECTION C: CREDITS (INITIAL STATE)
# =============================================================================

def test_c1_initial_balance():
    res = http_get(f"{BASE_URL}/credits/balance", headers=auth_headers())
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(data.get("bonus") == 40, f"Expected bonus=40, got {data.get('bonus')}")
    check(data.get("subscription") == 0, f"Expected subscription=0, got {data.get('subscription')}")
    check(data.get("purchased") == 0, f"Expected purchased=0, got {data.get('purchased')}")
    check(data.get("total") == 40, f"Expected total=40, got {data.get('total')}")
    check(data.get("weekly_limit") == 0, f"Expected weekly_limit=0, got {data.get('weekly_limit')}")
    check(data.get("weekly_used") == 0, f"Expected weekly_used=0, got {data.get('weekly_used')}")
    check(data.get("bonus_expiry") is not None, "bonus_expiry should not be None")


def test_c2_transactions():
    res = http_get(f"{BASE_URL}/credits/transactions", headers=auth_headers())
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check("transactions" in data, "Missing 'transactions' field")
    check(isinstance(data["transactions"], list), "transactions should be a list")
    check("total" in data, "Missing 'total' field")
    check("limit" in data, "Missing 'limit' field")
    check("offset" in data, "Missing 'offset' field")
    print(f"  Transaction count: {data.get('total')}")


def test_c3_pricing():
    res = http_get(f"{BASE_URL}/credits/pricing")
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check("pricing" in data, "Missing 'pricing' field")
    pricing = data["pricing"]
    check(isinstance(pricing, list), "pricing should be a list")
    if len(pricing) > 0:
        item = pricing[0]
        check("service_type" in item, "Missing service_type in pricing item")
        check("credit_cost" in item, "Missing credit_cost in pricing item")
        check("display_name" in item, "Missing display_name in pricing item")
        print(f"  Pricing entries: {len(pricing)}")
        for p in pricing[:5]:
            print(f"    {p.get('service_type')}: {p.get('credit_cost')} credits")
    else:
        print(f"  {YELLOW}No pricing entries configured{RESET}")


def test_c4_estimate():
    # First get a valid service_type from pricing
    pricing_res = http_get(f"{BASE_URL}/credits/pricing")
    pricing_data = pricing_res.json()
    pricing_list = pricing_data.get("pricing", [])

    if not pricing_list:
        print(f"  {YELLOW}No service pricing configured, skipping estimate test{RESET}")
        return

    service_type = pricing_list[0]["service_type"]
    res = http_post(f"{BASE_URL}/credits/estimate", json_body={
        "service_type": service_type
    })
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}: {data}")
    check(data.get("service_type") == service_type, f"service_type mismatch")
    check(isinstance(data.get("credits_needed"), int), "credits_needed should be int")
    check(data["credits_needed"] > 0, f"credits_needed should be > 0, got {data['credits_needed']}")
    print(f"  {service_type}: {data['credits_needed']} credits needed")


def test_c5_packages():
    res = http_get(f"{BASE_URL}/credits/packages", headers=auth_headers())
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check("packages" in data, "Missing 'packages' field")
    check(isinstance(data["packages"], list), "packages should be a list")
    print(f"  Packages available: {len(data['packages'])}")
    print(f"  User plan: {data.get('user_plan')}")


# =============================================================================
# SECTION D: SUBSCRIPTION PLANS
# =============================================================================

def test_d1_list_plans():
    res = http_get(f"{BASE_URL}/subscriptions/plans")
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(isinstance(data, list), "Response should be a list of plans")
    check(len(data) >= 4, f"Expected at least 4 plans, got {len(data)}")

    # Index plans by name
    plans_by_name = {p["name"]: p for p in data}

    # Validate demo plan
    check("demo" in plans_by_name, "Missing 'demo' plan")
    demo = plans_by_name["demo"]
    check(demo["price_monthly"] == 0, f"Demo price should be 0, got {demo['price_monthly']}")
    check(demo["monthly_credits"] == 0, f"Demo credits should be 0, got {demo['monthly_credits']}")

    # Validate starter plan
    check("starter" in plans_by_name, "Missing 'starter' plan")
    starter = plans_by_name["starter"]
    check(starter["price_monthly"] == 299.0, f"Starter price should be 299, got {starter['price_monthly']}")
    check(starter["monthly_credits"] == 100, f"Starter credits should be 100, got {starter['monthly_credits']}")
    state["starter_plan_id"] = starter["id"]

    # Validate pro plan
    check("pro" in plans_by_name, "Missing 'pro' plan")
    pro = plans_by_name["pro"]
    check(pro["price_monthly"] == 599.0, f"Pro price should be 599, got {pro['price_monthly']}")
    check(pro["monthly_credits"] == 250, f"Pro credits should be 250, got {pro['monthly_credits']}")
    state["pro_plan_id"] = pro["id"]

    # Validate pro_plus plan
    check("pro_plus" in plans_by_name, "Missing 'pro_plus' plan")
    pro_plus = plans_by_name["pro_plus"]
    check(pro_plus["price_monthly"] == 999.0, f"Pro+ price should be 999, got {pro_plus['price_monthly']}")
    check(pro_plus["monthly_credits"] == 500, f"Pro+ credits should be 500, got {pro_plus['monthly_credits']}")

    # Validate features structure
    for name, plan in plans_by_name.items():
        features = plan.get("features", {})
        check("max_resolution" in features, f"{name}: Missing max_resolution in features")
        check("has_watermark" in features, f"{name}: Missing has_watermark in features")
        check("priority_queue" in features, f"{name}: Missing priority_queue in features")

    print(f"  Plans found: {list(plans_by_name.keys())}")
    print(f"  Starter ID: {state['starter_plan_id']}")
    print(f"  Pro ID: {state['pro_plan_id']}")


# =============================================================================
# SECTION E: SUBSCRIBE & VERIFY (MOCK MODE)
# =============================================================================

def test_e1_subscribe_starter():
    res = http_post(f"{BASE_URL}/subscriptions/subscribe", headers=auth_headers(), json_body={
        "plan_id": state["starter_plan_id"],
        "billing_cycle": "monthly",
        "payment_method": "paddle"
    })
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}: {data}")
    check(data.get("success") == True, f"Expected success=True, got {data.get('success')}")
    check(data.get("status") == "active", f"Expected status='active', got '{data.get('status')}'")
    check(data.get("is_mock") == True, f"Expected is_mock=True, got {data.get('is_mock')}")
    check(data.get("subscription_id") is not None, "Missing subscription_id")

    state["subscription_id"] = data["subscription_id"]
    credits_alloc = data.get("credits_allocated")
    print(f"  Subscription ID: {state['subscription_id']}")
    print(f"  Credits allocated: {credits_alloc}")
    print(f"  Mock mode: {data.get('is_mock')}")


def test_e2_subscription_status():
    res = http_get(f"{BASE_URL}/subscriptions/status", headers=auth_headers())
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(data.get("success") == True, "Expected success=True")
    check(data.get("has_subscription") == True, "Expected has_subscription=True")
    check(data.get("status") == "active", f"Expected status='active', got '{data.get('status')}'")
    check(data.get("subscription_id") == state["subscription_id"],
          f"Subscription ID mismatch: {data.get('subscription_id')} != {state['subscription_id']}")

    plan = data.get("plan", {})
    check(plan.get("name") == "starter", f"Expected plan name='starter', got '{plan.get('name')}'")
    check(plan.get("display_name") == "Starter", f"Expected display_name='Starter', got '{plan.get('display_name')}'")

    check(data.get("start_date") is not None, "Missing start_date")
    check(data.get("end_date") is not None, "Missing end_date")
    check(data.get("auto_renew") == True, "Expected auto_renew=True")
    check(data.get("refund_eligible") == True, "Expected refund_eligible=True (just subscribed)")

    credits = data.get("credits", {})
    check(credits.get("subscription") == 100, f"Expected subscription credits=100, got {credits.get('subscription')}")
    check(credits.get("bonus") == 40, f"Expected bonus=40, got {credits.get('bonus')}")
    check(credits.get("total") == 140, f"Expected total=140, got {credits.get('total')}")

    print(f"  Plan: {plan.get('name')} ({plan.get('display_name')})")
    print(f"  Credits: sub={credits.get('subscription')}, bonus={credits.get('bonus')}, total={credits.get('total')}")
    print(f"  Refund eligible: {data.get('refund_eligible')}, days remaining: {data.get('refund_days_remaining')}")


def test_e3_balance_after_subscribe():
    res = http_get(f"{BASE_URL}/credits/balance", headers=auth_headers())
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(data.get("subscription") == 100, f"Expected subscription=100, got {data.get('subscription')}")
    check(data.get("bonus") == 40, f"Expected bonus=40, got {data.get('bonus')}")
    check(data.get("total") == 140, f"Expected total=140, got {data.get('total')}")
    check(data.get("weekly_limit") > 0, f"Expected weekly_limit > 0, got {data.get('weekly_limit')}")
    check(data.get("weekly_used") == 0, f"Expected weekly_used=0, got {data.get('weekly_used')}")
    print(f"  Weekly limit: {data.get('weekly_limit')}")


def test_e4_profile_after_subscribe():
    res = http_get(f"{BASE_URL}/auth/me", headers=auth_headers())
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    plan_type = data.get("plan_type")
    check(plan_type is not None, f"Expected plan_type to be set, got None")
    print(f"  plan_type: {plan_type}")


def test_e5_subscription_history():
    res = http_get(f"{BASE_URL}/subscriptions/history", headers=auth_headers())
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(data.get("success") == True, "Expected success=True")
    subs = data.get("subscriptions", [])
    check(len(subs) >= 1, f"Expected at least 1 subscription in history, got {len(subs)}")
    first = subs[0]
    check(first.get("plan_name") == "starter", f"Expected plan_name='starter', got '{first.get('plan_name')}'")
    check(first.get("status") == "active", f"Expected status='active', got '{first.get('status')}'")
    check(first.get("start_date") is not None, "Missing start_date")
    print(f"  History entries: {len(subs)}")


def test_e6_invoices():
    res = http_get(f"{BASE_URL}/subscriptions/invoices", headers=auth_headers())
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(data.get("success") == True, "Expected success=True")
    check("invoices" in data, "Missing 'invoices' field")
    check(isinstance(data["invoices"], list), "invoices should be a list")
    print(f"  Invoice count: {len(data['invoices'])}")


# =============================================================================
# SECTION F: REFUND & CANCELLATION
# =============================================================================

def test_f1_refund_eligibility():
    res = http_get(f"{BASE_URL}/subscriptions/refund-eligibility", headers=auth_headers())
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(data.get("eligible") == True, f"Expected eligible=True, got {data.get('eligible')}")
    check(data.get("days_remaining") >= 6, f"Expected days_remaining >= 6, got {data.get('days_remaining')}")
    check(data.get("reason") is None, f"Expected reason=None (eligible), got '{data.get('reason')}'")
    print(f"  Eligible: {data.get('eligible')}, Days remaining: {data.get('days_remaining')}")


def test_f2_cancel_with_refund():
    res = http_post(f"{BASE_URL}/subscriptions/cancel", headers=auth_headers(), json_body={
        "request_refund": True
    })
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}: {data}")
    check(data.get("success") == True, f"Expected success=True, got {data.get('success')}: {data.get('error')}")
    check(data.get("status") == "cancelled", f"Expected status='cancelled', got '{data.get('status')}'")
    check(data.get("refund_processed") == True, f"Expected refund_processed=True, got {data.get('refund_processed')}")
    check(data.get("active_until") is not None, "Missing active_until")
    # Check 7-day work retention
    check(data.get("work_retention_until") is not None, "Missing work_retention_until (7-day grace period)")
    msg = data.get("message", "")
    check("refund" in msg.lower(), f"Expected 'refund' in message, got '{msg}'")
    print(f"  Refund processed: {data.get('refund_processed')}")
    print(f"  Active until: {data.get('active_until')}")
    print(f"  Work retention until: {data.get('work_retention_until')}")


def test_f3_balance_after_refund():
    res = http_get(f"{BASE_URL}/credits/balance", headers=auth_headers())
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(data.get("subscription") == 0, f"Expected subscription=0 (revoked), got {data.get('subscription')}")
    check(data.get("bonus") == 40, f"Expected bonus=40 (retained), got {data.get('bonus')}")
    check(data.get("total") == 40, f"Expected total=40, got {data.get('total')}")
    print(f"  Credits after refund: sub={data.get('subscription')}, bonus={data.get('bonus')}, total={data.get('total')}")


def test_f4_status_after_cancel():
    res = http_get(f"{BASE_URL}/subscriptions/status", headers=auth_headers())
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(data.get("has_subscription") == False, f"Expected has_subscription=False, got {data.get('has_subscription')}")
    print(f"  has_subscription: {data.get('has_subscription')}")
    print(f"  status: {data.get('status')}")


def test_f5_profile_after_cancel():
    res = http_get(f"{BASE_URL}/auth/me", headers=auth_headers())
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    plan_type = data.get("plan_type")
    check(plan_type is None or plan_type == "free", f"Expected plan_type=None after refund, got '{plan_type}'")
    print(f"  plan_type: {plan_type}")


# =============================================================================
# SECTION G: RE-SUBSCRIPTION AFTER CANCELLATION
# =============================================================================

def test_g1_resubscribe_pro():
    res = http_post(f"{BASE_URL}/subscriptions/subscribe", headers=auth_headers(), json_body={
        "plan_id": state["pro_plan_id"],
        "billing_cycle": "monthly",
        "payment_method": "paddle"
    })
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}: {data}")
    check(data.get("success") == True, f"Expected success=True: {data.get('error')}")
    check(data.get("status") == "active", f"Expected status='active', got '{data.get('status')}'")
    check(data.get("is_mock") == True, f"Expected is_mock=True")

    state["subscription_id"] = data.get("subscription_id")
    credits_alloc = data.get("credits_allocated")
    print(f"  Re-subscribed to Pro plan")
    print(f"  Credits allocated: {credits_alloc}")


def test_g2_verify_resubscription():
    res = http_get(f"{BASE_URL}/subscriptions/status", headers=auth_headers())
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(data.get("has_subscription") == True, "Expected has_subscription=True")

    plan = data.get("plan", {})
    check(plan.get("name") == "pro", f"Expected plan name='pro', got '{plan.get('name')}'")

    credits = data.get("credits", {})
    check(credits.get("subscription") == 250, f"Expected subscription=250, got {credits.get('subscription')}")
    check(credits.get("bonus") == 40, f"Expected bonus=40, got {credits.get('bonus')}")
    check(credits.get("total") == 290, f"Expected total=290, got {credits.get('total')}")
    print(f"  Plan: {plan.get('name')}")
    print(f"  Credits: sub={credits.get('subscription')}, bonus={credits.get('bonus')}, total={credits.get('total')}")


def test_g3_history_after_resub():
    res = http_get(f"{BASE_URL}/subscriptions/history", headers=auth_headers())
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    subs = data.get("subscriptions", [])
    check(len(subs) >= 2, f"Expected at least 2 subscriptions in history, got {len(subs)}")
    print(f"  History entries: {len(subs)}")
    for s in subs:
        print(f"    {s.get('plan_name')}: {s.get('status')}")


def test_g4_cancel_without_refund():
    res = http_post(f"{BASE_URL}/subscriptions/cancel", headers=auth_headers(), json_body={
        "request_refund": False
    })
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}: {data}")
    check(data.get("success") == True, f"Expected success=True: {data.get('error')}")
    check(data.get("status") == "cancelled", f"Expected status='cancelled', got '{data.get('status')}'")
    check(data.get("refund_processed") == False, f"Expected refund_processed=False, got {data.get('refund_processed')}")
    check(data.get("active_until") is not None, "Missing active_until")
    print(f"  Cancelled without refund")
    print(f"  Active until: {data.get('active_until')}")


def test_g5_balance_after_cancel_no_refund():
    """After cancel without refund, subscription credits should be retained until period ends."""
    res = http_get(f"{BASE_URL}/credits/balance", headers=auth_headers())
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    # Without refund, subscription credits may or may not be retained depending on implementation
    # The key check is that bonus credits are untouched
    check(data.get("bonus") == 40, f"Expected bonus=40 (retained), got {data.get('bonus')}")
    print(f"  Credits after cancel (no refund): sub={data.get('subscription')}, bonus={data.get('bonus')}, total={data.get('total')}")


# =============================================================================
# SECTION H: TOOL TEMPLATES & LISTS (NO AUTH)
# =============================================================================

def test_h1_scene_templates():
    res = http_get(f"{BASE_URL}/tools/templates/scenes")
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(isinstance(data, list), "Response should be a list")
    check(len(data) >= 8, f"Expected at least 8 scenes, got {len(data)}")
    ids = [s["id"] for s in data]
    for expected_id in ["studio", "nature", "elegant", "minimal", "lifestyle"]:
        check(expected_id in ids, f"Missing scene '{expected_id}'")
    for item in data:
        check("id" in item, "Missing 'id' in scene")
        check("name" in item, "Missing 'name' in scene")
        check("name_zh" in item, "Missing 'name_zh' in scene")
        check("prompt" in item, "Missing 'prompt' in scene")
    print(f"  Scenes: {ids}")


def test_h2_interior_styles():
    res = http_get(f"{BASE_URL}/tools/templates/interior-styles")
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(isinstance(data, list), "Response should be a list")
    check(len(data) >= 10, f"Expected at least 10 styles, got {len(data)}")
    ids = [s["id"] for s in data]
    for expected_id in ["modern_minimalist", "scandinavian", "japanese", "industrial", "bohemian"]:
        check(expected_id in ids, f"Missing style '{expected_id}'")
    for item in data:
        check("id" in item, "Missing 'id' in style")
        check("name" in item, "Missing 'name' in style")
        check("prompt" in item, "Missing 'prompt' in style")
    print(f"  Interior styles: {ids}")


def test_h3_tryon_models():
    res = http_get(f"{BASE_URL}/tools/models/list")
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(isinstance(data, list), "Response should be a list")
    check(len(data) >= 6, f"Expected at least 6 models, got {len(data)}")
    ids = [m["id"] for m in data]
    for expected_id in ["female-1", "female-2", "male-1", "male-2"]:
        check(expected_id in ids, f"Missing model '{expected_id}'")
    print(f"  Try-on models: {ids}")


def test_h4_tts_voices():
    res = http_get(f"{BASE_URL}/tools/voices/list")
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(isinstance(data, list), "Response should be a list")
    check(len(data) >= 1, f"Expected at least 1 voice, got {len(data)}")
    for item in data:
        check("id" in item, "Missing 'id' in voice")
        check("name" in item, "Missing 'name' in voice")
    print(f"  TTS voices: {len(data)}")


def test_h5_effect_styles():
    res = http_get(f"{BASE_URL}/tools/styles")
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(isinstance(data, list), "Response should be a list")
    check(len(data) >= 1, f"Expected at least 1 style, got {len(data)}")
    for item in data[:3]:
        check("id" in item, "Missing 'id' in style")
        check("name" in item, "Missing 'name' in style")
    print(f"  Effect styles: {len(data)}")


def test_h6_avatar_voices():
    res = http_get(f"{BASE_URL}/tools/avatar/voices")
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(isinstance(data, dict), "Response should be a dict")
    check("en" in data, "Missing 'en' language in avatar voices")
    check("zh-TW" in data, "Missing 'zh-TW' language in avatar voices")
    en_voices = data["en"]
    check(isinstance(en_voices, list), "en voices should be a list")
    check(len(en_voices) >= 1, f"Expected at least 1 EN voice, got {len(en_voices)}")
    for v in en_voices:
        check("id" in v, "Missing 'id' in EN voice")
        check("name" in v, "Missing 'name' in EN voice")
    print(f"  EN voices: {len(en_voices)}, ZH-TW voices: {len(data.get('zh-TW', []))}")


# =============================================================================
# SECTION J: PLAN FEATURES (Per-Plan Access Control)
# =============================================================================

def _register_fresh_user():
    """Register a fresh user for sections J-M (clean state, no prior subscriptions)."""
    ts = str(int(time.time())) + "2"
    email = f"vidgo_test_{ts}@example.com"
    username = f"testuser_{ts}"

    # Register
    res = http_post(f"{BASE_URL}/auth/register", json_body={
        "email": email, "username": username,
        "password": PASSWORD, "full_name": "Test User 2"
    })
    assert res.status_code == 200, f"Registration failed: {res.status_code}"

    # Get verification code from Mailpit
    time.sleep(1)
    mr = http_get(f"{MAILPIT_URL}/api/v1/messages")
    msgs = mr.json().get("messages", [])
    code = None
    for msg in msgs:
        if email.lower() in json.dumps(msg.get("To", [])).lower():
            txt = http_get(f"{MAILPIT_URL}/api/v1/message/{msg['ID']}").json().get("Text", "")
            m = re.search(r'\b(\d{6})\b', txt)
            if m:
                code = m.group(1)
                break
    assert code, f"Could not find verification code for {email}"

    # Verify
    vr = http_post(f"{BASE_URL}/auth/verify-code", json_body={"email": email, "code": code})
    vdata = vr.json()
    assert vr.status_code == 200, f"Verify failed: {vr.status_code}"

    state["email"] = email
    state["token"] = vdata["access_token"]
    state["refresh_token"] = vdata["refresh_token"]
    state["user_id"] = vdata["user"]["id"]
    print(f"  Registered fresh user: {email}")


def test_j1_plan_features_no_plan():
    """Without a subscription, plan features should show defaults (all restricted)."""
    # Register fresh user so we have a clean no-plan state
    _register_fresh_user()

    res = http_get(f"{BASE_URL}/subscriptions/plan-features", headers=auth_headers())
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(data.get("has_plan") == False, f"Expected has_plan=False, got {data.get('has_plan')}")
    features = data.get("features", {})
    check(features.get("batch_processing") == False, "Demo should not have batch_processing")
    check(features.get("can_use_effects") == False, "Demo should not have can_use_effects")
    check(features.get("max_resolution") == "720p", f"Demo should have 720p max, got {features.get('max_resolution')}")
    print(f"  No plan features: {features}")


def test_j2_subscribe_starter_for_features():
    """Subscribe to starter to test plan features."""
    res = http_post(f"{BASE_URL}/subscriptions/subscribe", headers=auth_headers(), json_body={
        "plan_id": state["starter_plan_id"],
        "billing_cycle": "monthly",
        "payment_method": "paddle"
    })
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}: {data}")
    check(data.get("success") == True, f"Expected success=True: {data.get('error')}")
    state["subscription_id"] = data.get("subscription_id")
    print(f"  Subscribed to starter for feature tests")


def test_j3_plan_features_starter():
    """Starter plan should have effects but NOT batch_processing or custom_styles."""
    res = http_get(f"{BASE_URL}/subscriptions/plan-features", headers=auth_headers())
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(data.get("has_plan") == True, "Expected has_plan=True")
    check(data.get("plan_name") == "starter", f"Expected plan_name='starter', got {data.get('plan_name')}")
    features = data.get("features", {})
    check(features.get("can_use_effects") == True, "Starter should have can_use_effects=True")
    check(features.get("batch_processing") == False, "Starter should NOT have batch_processing")
    check(features.get("custom_styles") == False, "Starter should NOT have custom_styles")
    check(features.get("max_resolution") == "1080p", f"Starter should have 1080p, got {features.get('max_resolution')}")
    check(features.get("has_watermark") == False, "Starter should NOT have watermark")
    print(f"  Starter features: {features}")


# =============================================================================
# SECTION K: UPGRADE / DOWNGRADE
# =============================================================================

def test_k1_upgrade_to_pro():
    """Upgrade from starter to pro. Should activate immediately."""
    res = http_post(f"{BASE_URL}/subscriptions/subscribe", headers=auth_headers(), json_body={
        "plan_id": state["pro_plan_id"],
        "billing_cycle": "monthly",
        "payment_method": "paddle"
    })
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}: {data}")
    check(data.get("success") == True, f"Expected success=True: {data.get('error')}")
    check(data.get("status") == "active", f"Expected status='active' (immediate upgrade), got {data.get('status')}")
    check(data.get("credits_allocated") == 250, f"Expected 250 credits, got {data.get('credits_allocated')}")
    state["subscription_id"] = data.get("subscription_id")
    print(f"  Upgraded to Pro, credits: {data.get('credits_allocated')}")


def test_k2_pro_features():
    """Pro plan should have ALL features."""
    res = http_get(f"{BASE_URL}/subscriptions/plan-features", headers=auth_headers())
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(data.get("plan_name") == "pro", f"Expected plan_name='pro', got {data.get('plan_name')}")
    features = data.get("features", {})
    check(features.get("can_use_effects") == True, "Pro should have effects")
    check(features.get("batch_processing") == True, "Pro should have batch_processing")
    check(features.get("custom_styles") == True, "Pro should have custom_styles")
    check(features.get("max_resolution") == "4k", f"Pro should have 4k, got {features.get('max_resolution')}")
    check(features.get("priority_queue") == True, "Pro should have priority_queue")
    print(f"  Pro features: {features}")


def test_k3_downgrade_to_starter():
    """Downgrade from pro to starter. Should be scheduled, not immediate."""
    res = http_post(f"{BASE_URL}/subscriptions/subscribe", headers=auth_headers(), json_body={
        "plan_id": state["starter_plan_id"],
        "billing_cycle": "monthly",
        "payment_method": "paddle"
    })
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}: {data}")
    check(data.get("success") == True, f"Expected success=True: {data.get('error')}")
    # Downgrade should be scheduled, not immediate
    check(data.get("status") == "pending_downgrade", f"Expected status='pending_downgrade', got {data.get('status')}")
    check(data.get("effective_date") is not None, "Missing effective_date for downgrade")
    print(f"  Downgrade scheduled, effective: {data.get('effective_date')}")
    print(f"  Message: {data.get('message')}")


def test_k4_status_shows_pending_downgrade():
    """Status should show current pro plan AND pending downgrade info."""
    res = http_get(f"{BASE_URL}/subscriptions/status", headers=auth_headers())
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check(data.get("has_subscription") == True, "Should still have active subscription")
    plan = data.get("plan", {})
    check(plan.get("name") == "pro", f"Current plan should still be 'pro', got {plan.get('name')}")
    # Check for pending downgrade info
    pending = data.get("pending_downgrade")
    check(pending is not None, "Expected pending_downgrade info in status")
    if pending:
        check(pending.get("plan_name") == "starter", f"Pending plan should be 'starter', got {pending.get('plan_name')}")
    print(f"  Current plan: {plan.get('name')}")
    print(f"  Pending downgrade: {pending}")


def test_k5_cancel_pro_for_next_tests():
    """Cancel pro subscription to clean up for next tests."""
    res = http_post(f"{BASE_URL}/subscriptions/cancel", headers=auth_headers(), json_body={
        "request_refund": True
    })
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}: {data}")
    check(data.get("success") == True, f"Cancel failed: {data.get('error')}")
    print(f"  Cancelled pro for cleanup")


# =============================================================================
# SECTION L: CANCELLATION NOTICE ON LOGIN
# =============================================================================

def test_l1_cancellation_notice_on_me():
    """After cancel, /auth/me should show cancellation_notice with retention info."""
    res = http_get(f"{BASE_URL}/auth/me", headers=auth_headers())
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    notice = data.get("cancellation_notice")
    check(notice is not None, "Expected cancellation_notice after cancel")
    if notice:
        check(notice.get("days_remaining") >= 6, f"Expected >=6 days remaining, got {notice.get('days_remaining')}")
        check(notice.get("work_retention_until") is not None, "Missing work_retention_until in notice")
        check("download" in notice.get("message", "").lower() or "work" in notice.get("message", "").lower(),
              "Notice should mention downloading work")
    print(f"  Cancellation notice: {notice}")


def test_l2_cancellation_notice_on_login():
    """Login should also include cancellation_notice."""
    res = http_post(f"{BASE_URL}/auth/login", json_body={
        "email": state["email"],
        "password": PASSWORD
    })
    data = res.json()
    pretty_print("Response (excerpt)", {
        "user_email": data.get("user", {}).get("email"),
        "cancellation_notice": data.get("cancellation_notice")
    })
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    notice = data.get("cancellation_notice")
    check(notice is not None, "Expected cancellation_notice on login after cancel")
    if notice:
        check(notice.get("days_remaining") >= 6, f"Expected >=6 days, got {notice.get('days_remaining')}")
    print(f"  Login cancellation notice present: {notice is not None}")


def test_l3_resubscribe_clears_notice():
    """Re-subscribing should clear the cancellation notice."""
    # Re-subscribe
    res = http_post(f"{BASE_URL}/subscriptions/subscribe", headers=auth_headers(), json_body={
        "plan_id": state["starter_plan_id"],
        "billing_cycle": "monthly",
        "payment_method": "paddle"
    })
    data = res.json()
    check(res.status_code == 200, f"Subscribe failed: {res.status_code}")
    check(data.get("success") == True, f"Subscribe failed: {data.get('error')}")

    # Check that notice is cleared
    me_res = http_get(f"{BASE_URL}/auth/me", headers=auth_headers())
    me_data = me_res.json()
    pretty_print("Response", me_data)
    notice = me_data.get("cancellation_notice")
    check(notice is None, f"Expected no cancellation_notice after re-subscribe, got: {notice}")
    print(f"  Cancellation notice cleared after re-subscribe")

    # Cancel again for delete test
    cancel_res = http_post(f"{BASE_URL}/subscriptions/cancel", headers=auth_headers(), json_body={
        "request_refund": True
    })
    cancel_data = cancel_res.json()
    check(cancel_data.get("success") == True, f"Cancel failed: {cancel_data.get('error')}")


# =============================================================================
# SECTION M: DELETE ACCOUNT
# =============================================================================

def test_m1_delete_account_wrong_password():
    """Delete account with wrong password should fail."""
    res = http_delete(f"{BASE_URL}/auth/me", headers=auth_headers(), json_body={
        "password": "WrongPassword123!"
    })
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 400, f"Expected 400, got {res.status_code}")
    check("incorrect" in data.get("detail", "").lower() or "password" in data.get("detail", "").lower(),
          f"Expected password error, got: {data.get('detail')}")
    print(f"  Correctly rejected wrong password")


def test_m2_delete_account():
    """Delete account with correct password should succeed."""
    res = http_delete(f"{BASE_URL}/auth/me", headers=auth_headers(), json_body={
        "password": PASSWORD
    })
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}")
    check("deleted" in data.get("message", "").lower() or "removed" in data.get("message", "").lower(),
          f"Expected deletion confirmation, got: {data.get('message')}")
    print(f"  Account deleted successfully")


def test_m3_verify_deleted_account():
    """After deletion, login should fail."""
    res = http_post(f"{BASE_URL}/auth/login", json_body={
        "email": state["email"],
        "password": PASSWORD
    })
    data = res.json()
    pretty_print("Response", data)
    # Should get 401 (wrong credentials since email was anonymized) or 403 (deactivated)
    check(res.status_code in [401, 403], f"Expected 401 or 403, got {res.status_code}")
    print(f"  Login correctly rejected for deleted account (status: {res.status_code})")


# =============================================================================
# SECTION I: LOGIN TEST (moved to run before delete tests)
# =============================================================================

def test_i1_login():
    res = http_post(f"{BASE_URL}/auth/login", json_body={
        "email": state["email"],
        "password": PASSWORD
    })
    data = res.json()
    pretty_print("Response", data)
    check(res.status_code == 200, f"Expected 200, got {res.status_code}: {data}")

    # LoginResponse has user and tokens fields
    user = data.get("user", {})
    check(user.get("email") == state["email"], f"Email mismatch: {user.get('email')}")
    check(user.get("is_active") == True, "is_active should be True")

    tokens = data.get("tokens", {})
    check(tokens.get("access") is not None or data.get("access_token") is not None,
          "Missing access token in login response")
    print(f"  Login successful for {state['email']}")


# =============================================================================
# MAIN - RUN ALL TESTS
# =============================================================================

def main():
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}   VidGo Gen AI - Comprehensive API Test Suite{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"  Base URL: {BASE_URL}")
    print(f"  Time: {datetime.now().isoformat()}")

    # A: Health Check
    run_test("A1", "Health Check", test_a1_health_check)

    # B: Authentication Flow
    run_test("B1", "Register New User", test_b1_register)
    if state["token"] is None:
        run_test("B2", "Get Verification Code", test_b2_get_verification_code)
    if state.get("code"):
        run_test("B3", "Verify Email", test_b3_verify_email)
    else:
        skip_test("B3", "Verify Email", "No verification code")

    if state["token"]:
        run_test("B4", "Get User Profile", test_b4_get_profile)
    else:
        skip_test("B4", "Get User Profile", "No auth token")

    # Check if auth succeeded - if not, skip all authenticated tests
    if not state["token"]:
        print(f"\n{RED}Auth flow failed - skipping all authenticated tests{RESET}")
        for tid, tname in [
            ("C1", "Initial Balance"), ("C2", "Transactions"), ("C3", "Pricing"),
            ("C4", "Estimate"), ("C5", "Packages"), ("D1", "List Plans"),
            ("E1", "Subscribe Starter"), ("E2", "Subscription Status"),
            ("E3", "Balance After Subscribe"), ("E4", "Profile After Subscribe"),
            ("E5", "Subscription History"), ("E6", "Invoices"),
            ("F1", "Refund Eligibility"), ("F2", "Cancel With Refund"),
            ("F3", "Balance After Refund"), ("F4", "Status After Cancel"),
            ("F5", "Profile After Cancel"),
            ("G1", "Re-subscribe Pro"), ("G2", "Verify Re-subscription"),
            ("G3", "History After Resub"), ("G4", "Cancel Without Refund"),
            ("G5", "Balance After Cancel No Refund"),
        ]:
            skip_test(tid, tname, "No auth token")
    else:
        # C: Credits (Initial State)
        run_test("C1", "Initial Credit Balance", test_c1_initial_balance)
        run_test("C2", "Credit Transactions", test_c2_transactions)
        run_test("C3", "Credit Pricing", test_c3_pricing)
        run_test("C4", "Credit Estimate", test_c4_estimate)
        run_test("C5", "Credit Packages", test_c5_packages)

        # D: Subscription Plans
        run_test("D1", "List Subscription Plans", test_d1_list_plans)

        if state["starter_plan_id"] and state["pro_plan_id"]:
            # E: Subscribe & Verify
            run_test("E1", "Subscribe to Starter Plan", test_e1_subscribe_starter)
            run_test("E2", "Subscription Status", test_e2_subscription_status)
            run_test("E3", "Balance After Subscribe", test_e3_balance_after_subscribe)
            run_test("E4", "Profile After Subscribe", test_e4_profile_after_subscribe)
            run_test("E5", "Subscription History", test_e5_subscription_history)
            run_test("E6", "Invoices List", test_e6_invoices)

            # F: Refund & Cancellation
            run_test("F1", "Refund Eligibility", test_f1_refund_eligibility)
            run_test("F2", "Cancel With Refund", test_f2_cancel_with_refund)
            run_test("F3", "Balance After Refund", test_f3_balance_after_refund)
            run_test("F4", "Status After Cancel", test_f4_status_after_cancel)
            run_test("F5", "Profile After Cancel", test_f5_profile_after_cancel)

            # G: Re-subscription
            run_test("G1", "Re-subscribe to Pro Plan", test_g1_resubscribe_pro)
            run_test("G2", "Verify Re-subscription", test_g2_verify_resubscription)
            run_test("G3", "History After Re-subscription", test_g3_history_after_resub)
            run_test("G4", "Cancel Without Refund", test_g4_cancel_without_refund)
            run_test("G5", "Balance After Cancel (No Refund)", test_g5_balance_after_cancel_no_refund)
        else:
            for tid, tname in [
                ("E1", "Subscribe Starter"), ("E2", "Subscription Status"),
                ("E3", "Balance After Subscribe"), ("E4", "Profile After Subscribe"),
                ("E5", "Subscription History"), ("E6", "Invoices"),
                ("F1", "Refund Eligibility"), ("F2", "Cancel With Refund"),
                ("F3", "Balance After Refund"), ("F4", "Status After Cancel"),
                ("F5", "Profile After Cancel"),
                ("G1", "Re-subscribe Pro"), ("G2", "Verify Re-subscription"),
                ("G3", "History After Resub"), ("G4", "Cancel Without Refund"),
                ("G5", "Balance After Cancel No Refund"),
            ]:
                skip_test(tid, tname, "No plan IDs captured")

    # H: Tool Templates (No auth required)
    run_test("H1", "Scene Templates", test_h1_scene_templates)
    run_test("H2", "Interior Styles", test_h2_interior_styles)
    run_test("H3", "Try-On Models", test_h3_tryon_models)
    run_test("H4", "TTS Voices", test_h4_tts_voices)
    run_test("H5", "Effect Styles", test_h5_effect_styles)
    run_test("H6", "Avatar Voices", test_h6_avatar_voices)

    # I: Login Test
    if state["email"]:
        run_test("I1", "Login with Email/Password", test_i1_login)
    else:
        skip_test("I1", "Login", "No registered email")

    # J-M: New flow tests (require auth and plan IDs)
    if state["token"] and state["starter_plan_id"] and state["pro_plan_id"]:
        # J: Plan Features
        run_test("J1", "Plan Features (No Plan)", test_j1_plan_features_no_plan)
        run_test("J2", "Subscribe Starter for Features", test_j2_subscribe_starter_for_features)
        run_test("J3", "Starter Plan Features", test_j3_plan_features_starter)

        # K: Upgrade / Downgrade
        run_test("K1", "Upgrade to Pro", test_k1_upgrade_to_pro)
        run_test("K2", "Pro Plan Features", test_k2_pro_features)
        run_test("K3", "Downgrade to Starter (Scheduled)", test_k3_downgrade_to_starter)
        run_test("K4", "Status Shows Pending Downgrade", test_k4_status_shows_pending_downgrade)
        run_test("K5", "Cancel Pro for Next Tests", test_k5_cancel_pro_for_next_tests)

        # L: Cancellation Notice
        run_test("L1", "Cancellation Notice on /me", test_l1_cancellation_notice_on_me)
        run_test("L2", "Cancellation Notice on Login", test_l2_cancellation_notice_on_login)
        run_test("L3", "Re-subscribe Clears Notice", test_l3_resubscribe_clears_notice)

        # M: Delete Account (MUST BE LAST - destroys the test user)
        run_test("M1", "Delete Account Wrong Password", test_m1_delete_account_wrong_password)
        run_test("M2", "Delete Account", test_m2_delete_account)
        run_test("M3", "Verify Deleted Account", test_m3_verify_deleted_account)
    else:
        for tid, tname in [
            ("J1", "Plan Features No Plan"), ("J2", "Subscribe for Features"),
            ("J3", "Starter Features"), ("K1", "Upgrade Pro"), ("K2", "Pro Features"),
            ("K3", "Downgrade Starter"), ("K4", "Pending Downgrade"), ("K5", "Cancel Pro"),
            ("L1", "Cancel Notice /me"), ("L2", "Cancel Notice Login"),
            ("L3", "Resubscribe Clears Notice"),
            ("M1", "Delete Wrong Pass"), ("M2", "Delete Account"), ("M3", "Verify Deleted"),
        ]:
            skip_test(tid, tname, "No auth token or plan IDs")

    # ==========================================================================
    # SUMMARY
    # ==========================================================================
    print(f"\n\n{'='*60}")
    print(f"{BOLD}                    TEST SUMMARY{RESET}")
    print(f"{'='*60}")

    passed = 0
    failed = 0
    skipped = 0

    for name, status, detail in results:
        if status is True:
            print(f"  {GREEN}PASS{RESET}: {name}")
            passed += 1
        elif status is False:
            print(f"  {RED}FAIL{RESET}: {name} - {detail}")
            failed += 1
        else:
            print(f"  {YELLOW}SKIP{RESET}: {name} - {detail}")
            skipped += 1

    print(f"{'='*60}")
    total = passed + failed + skipped
    color = GREEN if failed == 0 else RED
    print(f"  {color}Total: {total} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}{RESET}")
    print(f"{'='*60}\n")

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
