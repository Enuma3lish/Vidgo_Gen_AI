"""Live PayPal plan pricing for the international (USD) sticker price.

The /pricing page's USD price is sourced from the PayPal billing plans
themselves (GET /v1/billing/plans/{id}), so updating a plan's price in the
PayPal dashboard automatically flows to the frontend within the cache TTL —
no code change, no manual DB edit — and the displayed price always matches
what PayPal will actually charge.

Resilience: results are cached in-process; on a PayPal error/timeout the last
known-good prices are served (stale-while-error), and if nothing has ever been
fetched the caller falls back to the DB Plan.price_usd column. The pricing
endpoint therefore never hard-depends on PayPal being reachable, and a slow
PayPal never drags down the (LCP-critical) pricing page.

Only the *_monthly plans are fetched — the frontend renders yearly as
monthly×12 (see OVERSEAS_USD / formatOverseasUsd in Pricing.vue).
"""
import asyncio
import json
import logging
import time
from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.payment_settings_service import get_resolved_settings
from app.services.paypal_service import get_paypal_service

logger = logging.getLogger(__name__)

# PayPal plan prices change rarely and only via an admin action in the PayPal
# dashboard, so a short TTL keeps the page fast (≤1 PayPal round-trip per
# window across a process) while still surfacing a price change "automatically"
# within ~2 min. invalidate_cache() (admin remap / plan webhook) makes it
# faster still. Per-process, like payment_settings_service's cache.
_CACHE_TTL_SECONDS = 120.0
# Hard cap on how long the pricing endpoint waits on PayPal before serving
# stale/DB-fallback prices.
_FETCH_BUDGET_SECONDS = 4.0

_MONTHLY_SUFFIX = "_monthly"

_cache: dict = {}


def invalidate_cache() -> None:
    """Drop cached prices so the next request refetches from PayPal.

    Called when the PayPal plan-ID mapping changes (admin save) or a PayPal
    plan/catalog webhook arrives, so the change takes effect without waiting
    for the TTL. Per-process: other instances converge after the TTL.
    """
    _cache.pop("prices", None)
    _cache.pop("ts", None)


def _extract_monthly_price(plan_json: dict) -> Optional[float]:
    """Pull the recurring USD price out of a PayPal billing plan.

    Picks the REGULAR billing cycle (a plan may carry a TRIAL cycle first) and
    reads pricing_scheme.fixed_price.value. Returns None if the shape is
    unexpected so the caller falls back to the DB price.
    """
    try:
        cycles = plan_json.get("billing_cycles") or []
        if not cycles:
            return None
        regular = next(
            (c for c in cycles if str(c.get("tenure_type", "")).upper() == "REGULAR"),
            cycles[0],
        )
        fixed = (regular.get("pricing_scheme") or {}).get("fixed_price") or {}
        value = fixed.get("value")
        return float(value) if value is not None else None
    except (TypeError, ValueError, AttributeError):
        return None


async def _fetch_prices(db: AsyncSession) -> Dict[str, float]:
    """Fetch {plan_slug: monthly USD price} from PayPal for every *_monthly plan."""
    paypal = get_paypal_service()
    # DB creds/env (sandbox↔production) win over the eager env defaults.
    await paypal.refresh_from_db(db)
    if paypal.is_mock:
        return {}

    resolved = await get_resolved_settings(db)
    blob = resolved.paypal_plan_ids or settings.PAYPAL_PLAN_IDS
    if not blob:
        return {}
    try:
        plan_ids = json.loads(blob)
    except Exception:
        logger.error("paypal_pricing: could not parse paypal_plan_ids JSON")
        return {}

    monthly = [
        (key[: -len(_MONTHLY_SUFFIX)], pid)
        for key, pid in plan_ids.items()
        if isinstance(key, str) and key.endswith(_MONTHLY_SUFFIX) and pid
    ]
    if not monthly:
        return {}

    results = await asyncio.gather(
        *(paypal.get_plan(pid) for _, pid in monthly),
        return_exceptions=True,
    )
    prices: Dict[str, float] = {}
    for (slug, _), result in zip(monthly, results):
        if not isinstance(result, dict) or not result.get("success"):
            continue
        price = _extract_monthly_price(result.get("plan") or {})
        if price is not None and price > 0:
            prices[slug] = price
    return prices


async def get_usd_monthly_prices(db: AsyncSession) -> Dict[str, float]:
    """Return {plan_slug: monthly USD price} sourced live from PayPal, cached.

    Never raises. Returns {} (→ caller uses DB Plan.price_usd) when PayPal is
    unconfigured/mock, or when nothing could be fetched and no prior value is
    cached.
    """
    now = time.time()
    cached = _cache.get("prices")
    ts = _cache.get("ts", 0.0)
    if isinstance(cached, dict) and isinstance(ts, float) and (now - ts) < _CACHE_TTL_SECONDS:
        return cached

    try:
        prices = await asyncio.wait_for(_fetch_prices(db), timeout=_FETCH_BUDGET_SECONDS)
    except Exception as exc:  # noqa: BLE001 — a pricing fetch must never fail the page
        logger.warning("paypal_pricing: live fetch failed (%s); serving fallback", exc)
        # Stale-while-error: keep serving the last known-good prices if we have
        # any; otherwise the caller falls back to the DB price_usd column.
        return cached if isinstance(cached, dict) else {}

    _cache["prices"] = prices
    _cache["ts"] = now
    return prices
