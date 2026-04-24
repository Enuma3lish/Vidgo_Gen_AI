#!/usr/bin/env python3
"""
Unit checks for billing fixes A–H.

Doesn't require running the full backend or a DB; imports are kept minimal
and we use small mocks where interaction is unavoidable.
"""
import asyncio
import ast
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/vidgo_test")


def assert_eq(a, b, label):
    if a != b:
        raise AssertionError(f"FAIL {label}: got {a!r}, expected {b!r}")
    print(f"PASS {label}")


# ─── Fix A: PLAN_LEVEL dynamic rank ──────────────────────────────────────────
def test_plan_rank():
    # Parse the source to pull the _plan_rank method without DB deps
    src = (BACKEND / "app/services/subscription_service.py").read_text()
    tree = ast.parse(src)
    # Extract the classmethod by compiling its source
    method_src = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_plan_rank":
            method_src = ast.unparse(node)
            break
    assert method_src, "_plan_rank not found"

    # Evaluate in a namespace with the PLAN_LEVEL table for fallback
    ns = {"cls": type("cls", (), {"PLAN_LEVEL": {
        "demo": 0, "free": 0,
        "starter": 1, "basic": 1,
        "standard": 2, "pro": 2,
        "pro_plus": 3, "premium": 3,
        "enterprise": 4,
    }})}
    # Replace decorator & first arg so we can call it plainly; also strip the
    # `Plan` annotation since we're mocking it with MagicMock.
    rank_fn_src = method_src.replace("@classmethod\n", "").replace(
        "def _plan_rank(cls, plan: Plan)", "def _plan_rank(plan)"
    ).replace(
        "def _plan_rank(cls, plan)", "def _plan_rank(plan)"
    )
    exec(rank_fn_src, ns)
    _plan_rank = ns["_plan_rank"]

    def plan(name, price_monthly=None, monthly_credits=None):
        p = MagicMock()
        p.name = name
        p.price_monthly = price_monthly
        p.monthly_credits = monthly_credits
        p.credits_per_month = None
        return p

    # Real DB plan prices (basic 699, pro 999, premium 1 699, enterprise 15 000)
    assert_eq(_plan_rank(plan("basic", 699)), 699.0, "rank(basic)=699")
    assert_eq(_plan_rank(plan("pro", 999)), 999.0, "rank(pro)=999")
    assert_eq(_plan_rank(plan("premium", 1699)), 1699.0, "rank(premium)=1699")
    assert_eq(_plan_rank(plan("enterprise", 15000)), 15000.0, "rank(enterprise)=15000")

    # The critical property: pro < premium < enterprise
    p_pro = _plan_rank(plan("pro", 999))
    p_premium = _plan_rank(plan("premium", 1699))
    p_ent = _plan_rank(plan("enterprise", 15000))
    if not (p_pro < p_premium < p_ent):
        raise AssertionError(
            f"FAIL pro<premium<enterprise ordering: {p_pro} / {p_premium} / {p_ent}"
        )
    print("PASS pro < premium < enterprise ordering — upgrades no longer misclassified")

    # Fallback path: no price, but credits present
    r = _plan_rank(plan("weird", price_monthly=None, monthly_credits=5000))
    if r <= 0:
        raise AssertionError(f"fallback by credits gave {r}")
    print("PASS rank falls back to credits when price is missing")


# ─── Fix B: subscribe requires action='refresh' for same-plan (source-level) ─
def test_subscribe_requires_refresh_action():
    src = (BACKEND / "app/services/subscription_service.py").read_text()
    assert 'action: Optional[str] = None' in src, "subscribe lost its action param"
    assert 'action == "refresh"' in src, (
        "same-plan check no longer requires explicit action=refresh"
    )
    print("PASS subscribe() gates same-plan resubscribe behind action='refresh'")


# ─── Fix C: UserWithDetails exposes current_plan_id ──────────────────────────
def test_user_with_details_exposes_plan_id():
    src = (BACKEND / "app/schemas/user.py").read_text()
    assert "current_plan_id: Optional[UUID]" in src, (
        "UserWithDetails is missing current_plan_id"
    )
    src2 = (BACKEND / "app/api/v1/auth.py").read_text()
    assert '"current_plan_id": current_user.current_plan_id' in src2, (
        "/auth/me endpoint no longer writes current_plan_id"
    )
    print("PASS UserWithDetails + /auth/me expose current_plan_id")


# ─── Fix D: Order audit row on direct activation ─────────────────────────────
def test_direct_activation_writes_order():
    src = (BACKEND / "app/services/subscription_service.py").read_text()
    assert "status=\"complimentary\"" in src, (
        "direct activation no longer writes a complimentary Order"
    )
    assert "order_number=f\"DIRECT-" in src, "direct order numbering missing"
    # Invoices endpoint accepts complimentary orders
    src2 = (BACKEND / "app/api/v1/subscriptions.py").read_text()
    assert '"paid", "complimentary"' in src2, (
        "/invoices endpoint does not include complimentary orders"
    )
    print("PASS direct activation writes audit Order + appears on /invoices")


# ─── Fix E: refund transactions labelled 'refund' ────────────────────────────
def test_refund_transaction_labelling():
    src = (BACKEND / "app/services/credit_service.py").read_text()
    assert "transaction_type: Optional[str] = None" in src, (
        "add_credits lost transaction_type override param"
    )
    assert "transaction_type=transaction_type or credit_type" in src, (
        "add_credits doesn't honour transaction_type override"
    )
    src2 = (BACKEND / "app/api/v1/tools.py").read_text()
    assert 'transaction_type="refund"' in src2, (
        "_refund_credits doesn't pass transaction_type='refund'"
    )
    print("PASS credit-refund rows now record transaction_type='refund'")


# ─── Fix F: /plan-features accepts plan_id for preview ───────────────────────
def test_plan_features_preview():
    src = (BACKEND / "app/api/v1/subscriptions.py").read_text()
    assert 'plan_id: Optional[str] = Query' in src, (
        "/plan-features no longer accepts plan_id query param"
    )
    assert '"preview": True' in src, "preview mode flag missing in response"
    print("PASS /plan-features supports ?plan_id preview")


# ─── Fix G: verification email copy (code, not link) ─────────────────────────
def test_unverified_error_copy():
    src = (BACKEND / "app/api/v1/auth.py").read_text()
    assert "6-digit verification code" in src, (
        "unverified login copy still references a 'link'"
    )
    assert "verification link" not in src.replace("# verification link", ""), (
        "unverified login copy still mentions verification link"
    )
    print("PASS unverified-login error mentions the 6-digit code")


# ─── Fix H: /subscriptions/current alias present ─────────────────────────────
def test_current_alias():
    src = (BACKEND / "app/api/v1/subscriptions.py").read_text()
    assert '@router.get("/current"' in src, (
        "no /subscriptions/current alias registered"
    )
    print("PASS /subscriptions/current is registered as an alias for /status")


def main():
    tests = [
        test_plan_rank,
        test_subscribe_requires_refresh_action,
        test_user_with_details_exposes_plan_id,
        test_direct_activation_writes_order,
        test_refund_transaction_labelling,
        test_plan_features_preview,
        test_unverified_error_copy,
        test_current_alias,
    ]
    failures = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(e)
            failures += 1
        except Exception as e:
            import traceback; traceback.print_exc()
            failures += 1
    total = len(tests)
    print(f"\n{total - failures}/{total} checks passed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
