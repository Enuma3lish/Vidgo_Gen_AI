"""Shared "custom prompt → subscription + bound card" access gate.

Product rule (owner directive 2026-05-29): a FREE account — no active paid
subscription, OR subscribed without a real card-backed payment on file — may
only generate from an UNMODIFIED dropdown preset, which returns the cached
example at zero API cost. Any custom / edited prompt requires an active
subscription WITH a bound credit card. Admins and the internal Pro test plan
bypass entirely so they can exercise every tool.

Lives in its own module so the tools router AND the generation router enforce
identical logic (single source of truth for the gate).
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import is_subscribed_user
from app.core.test_plans import TEST_PRO_PLAN_NAME, TEST_PRO_PLAN_SLUG
from app.models.billing import Order, Plan

# Real card-backed payment providers. A paid order through any of these is our
# proxy for "a credit card is bound" — the stack stores PayPal billing
# agreements / ECPay recurring orders rather than a vaulted card token.
# Paddle removed 2026-05-31 — we only offer ECPay (zh-TW) and PayPal (else).
CARD_BACKED_PAYMENT_METHODS = ("paypal", "ecpay")


async def has_bound_card(db: AsyncSession, user) -> bool:
    """True when the user has at least one paid order through a card-backed
    provider."""
    if not user:
        return False
    res = await db.execute(
        select(Order.id)
        .where(
            Order.user_id == user.id,
            Order.status == "paid",
            Order.payment_method.in_(CARD_BACKED_PAYMENT_METHODS),
        )
        .limit(1)
    )
    return res.first() is not None


async def is_test_account(db: AsyncSession, user) -> bool:
    """True when an admin has put this user on the internal Pro test plan
    (see /admin/users/{id}/test-account)."""
    if not user or not getattr(user, "current_plan_id", None):
        return False
    res = await db.execute(select(Plan.slug, Plan.name).where(Plan.id == user.current_plan_id))
    row = res.first()
    if not row:
        return False
    return row[0] == TEST_PRO_PLAN_SLUG or row[1] == TEST_PRO_PLAN_NAME


async def custom_prompt_gate(db: AsyncSession, user, is_custom: bool) -> str:
    """Return one of 'allow' | 'demo' | 'blocked' for a generation request.

    - allow:   run the real model (admin / test account / subscribed+card).
    - demo:    not eligible but using a preset → return the cached example.
    - blocked: not eligible and using a custom/edited prompt → caller must
               surface the subscribe-and-bind-card response.
    """
    if user and getattr(user, "is_superuser", False):
        return "allow"
    if await is_test_account(db, user):
        return "allow"
    if is_subscribed_user(user) and await has_bound_card(db, user):
        return "allow"
    return "blocked" if is_custom else "demo"
