"""
Live upstream-provider account status (2026-05-20).

WHY THIS EXISTS
---------------
VidGo's operating model is: end users buy our subscription credits → we
fulfill their generations by spending our own credits at PiAPI / Pollo /
Vertex AI. So the *upstream* balance is what determines whether
the platform can keep serving generations — not the per-user credit
balance (which the existing /credits endpoint already returns).

Before this service the admin page read these numbers from environment
variables that ops had to set by hand. That was useful as a stopgap but
goes stale the moment anyone tops up via the vendor UI. This service
calls each provider's account API where one exists, returns a friendly
"manual check URL" where it doesn't, and caches the result for 5 minutes
so we don't hammer vendor APIs on every dashboard load.

OPERATING NOTES
---------------
- Cache TTL: 5 minutes. Tunable via PROVIDER_BALANCE_CACHE_SECONDS env.
- Fail-open: any provider call that errors returns ``status="unknown"``
  with the manual-check URL so the dashboard still renders the rest.
- Currency is normalized to "credits" or "USD" per provider; the frontend
  decides what to show.
- Provider URLs are documented inline next to each fetcher so ops can
  bookmark them; they're also returned in the response payload as the
  "one-click visit" target.

USED BY
-------
- /api/v1/admin/ai-services (extends the existing payload with live data)
- /api/v1/dashboard/provider-status (new user-facing summary)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = int(os.getenv("PROVIDER_BALANCE_CACHE_SECONDS", "300"))


# ── Provider metadata ──────────────────────────────────────────────────────
# Each row describes how to render the provider on the dashboard plus the
# vendor account URL to open when the user clicks the "Check manually"
# button. Status values are: healthy / low / depleted / unknown / disabled.
#
# `low_threshold_credits` is the cutoff under which we flip status from
# healthy to low. We keep these conservative — flipping early is much
# cheaper than a generation failure on the user side.
_PROVIDERS = {
    "piapi": {
        "display_name": "PiAPI",
        "vendor_url": "https://piapi.ai/workspace/billing",
        "low_threshold_credits": 50.0,
        "currency": "USD",
        "supports_live_api": True,
    },
    "pollo": {
        "display_name": "Pollo AI",
        "vendor_url": "https://pollo.ai/dashboard",
        "low_threshold_credits": 50.0,
        "currency": "USD",
        # Pollo currently has no documented public balance endpoint —
        # users see a "Check manually" CTA instead.
        "supports_live_api": False,
    },
    # OpenAI (Sora 2) removed 2026-05-20 — owner rule is no provider unless
    # it's exposed via PiAPI or Pollo, and Sora is OpenAI-direct.
    "vertex_ai": {
        "display_name": "Google Vertex AI / Veo",
        "vendor_url": "https://console.cloud.google.com/billing",
        "low_threshold_credits": None,  # GCP billing is post-paid, no balance concept
        "currency": "USD",
        "supports_live_api": False,
    },
    "a2e": {
        "display_name": "A2E.ai (Avatar backup)",
        "vendor_url": "https://www.a2e.ai/account",
        "low_threshold_credits": 10.0,
        "currency": "credits",
        "supports_live_api": False,
    },
}


@dataclass
class ProviderAccountStatus:
    """Normalized per-provider account status."""

    provider: str
    display_name: str
    configured: bool
    """True when the API key is present (we know enough to call the API
    even if the call itself fails)."""

    status: str
    """One of: healthy | low | depleted | unknown | disabled."""

    balance: Optional[float]
    """Remaining credits / dollars on the vendor account. None when the
    vendor doesn't expose a balance endpoint, or the call failed."""

    balance_label: Optional[str]
    """Human-readable balance string e.g. "$42.50" or "1,200 credits"."""

    currency: str
    vendor_url: str
    supports_live_api: bool
    source: str
    """How we know this number:
        live   — fetched from vendor API just now
        cache  — fetched within the last TTL window
        env    — pulled from a hand-set env var (legacy fallback)
        manual — vendor doesn't expose a balance API; user must check
                 the vendor_url
        disabled — provider isn't configured on this deployment
    """
    error: Optional[str]
    last_checked: Optional[float]
    """Unix timestamp of the most recent live fetch. None for manual/disabled."""


class _BalanceCache:
    """In-process TTL cache. One process per Cloud Run container is fine —
    cache is per-instance, and the 5 min TTL keeps cross-instance drift
    tolerable while keeping us off the vendor's rate limits."""

    def __init__(self) -> None:
        self._store: Dict[str, tuple[float, ProviderAccountStatus]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[ProviderAccountStatus]:
        async with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            ts, value = entry
            if time.time() - ts > _CACHE_TTL_SECONDS:
                self._store.pop(key, None)
                return None
            # Return a copy with source="cache" so callers can render the
            # right "x mins ago" label.
            value = ProviderAccountStatus(**{**asdict(value), "source": "cache"})
            return value

    async def set(self, key: str, value: ProviderAccountStatus) -> None:
        async with self._lock:
            self._store[key] = (time.time(), value)


_CACHE = _BalanceCache()


# ── Vendor balance fetchers ────────────────────────────────────────────────
# Each fetcher returns (balance, balance_label, error). When the provider
# doesn't expose a balance API, the fetcher is omitted and the calling
# function returns a manual-source status.


async def _fetch_piapi_balance() -> tuple[Optional[float], Optional[str], Optional[str]]:
    """PiAPI workspace balance via /api/v1/account.

    Endpoint docs: piapi.ai/docs/account (returns ``{ data: { quota } }``
    where quota is the remaining USD balance on the workspace).
    """
    api_key = os.getenv("PIAPI_KEY", "")
    if not api_key:
        return None, None, "PIAPI_KEY not set"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.piapi.ai/api/v1/account",
                headers={"X-API-Key": api_key},
            )
        if resp.status_code != 200:
            return None, None, f"PiAPI account API HTTP {resp.status_code}"

        data = resp.json()
        # PiAPI's response shape has shifted twice in 2025 — defensive parsing.
        body = data.get("data") if isinstance(data, dict) else None
        if not isinstance(body, dict):
            body = data if isinstance(data, dict) else {}
        balance = body.get("quota") or body.get("balance") or body.get("remaining_quota")
        if balance is None:
            return None, None, f"PiAPI balance field missing in response: {data}"
        balance_f = float(balance)
        return balance_f, f"${balance_f:,.2f}", None
    except Exception as exc:  # pragma: no cover — exercised in prod
        logger.warning("PiAPI balance fetch failed: %s", exc)
        return None, None, str(exc)


# ── Public service ─────────────────────────────────────────────────────────


def _env_balance(provider: str) -> tuple[Optional[float], Optional[str]]:
    """Pull a manually-set balance from env (legacy fallback before this
    service existed). Returns (balance, label)."""
    env_var = {
        "piapi": "PIAPI_REMAINING_CREDITS",
        "pollo": "POLLO_REMAINING_CREDITS",
        "vertex_ai": "VERTEX_AI_REMAINING_CREDITS",
        "a2e": "A2E_REMAINING_CREDITS",
    }.get(provider)
    if not env_var:
        return None, None
    raw = os.getenv(env_var, "").strip()
    if not raw:
        return None, None
    try:
        return float(raw.replace(",", "")), raw
    except ValueError:
        return None, raw


def _classify(provider: str, balance: Optional[float]) -> str:
    meta = _PROVIDERS[provider]
    if balance is None:
        return "unknown"
    threshold = meta.get("low_threshold_credits")
    if threshold is None:
        return "healthy"
    if balance <= 0:
        return "depleted"
    if balance < threshold:
        return "low"
    return "healthy"


def _is_configured(provider: str) -> bool:
    if provider == "piapi":
        return bool(os.getenv("PIAPI_KEY", ""))
    if provider == "pollo":
        return bool(os.getenv("POLLO_API_KEY", ""))
    if provider == "vertex_ai":
        return bool(os.getenv("VERTEX_AI_PROJECT", "") or os.getenv("GEMINI_API_KEY", ""))
    if provider == "a2e":
        return bool(os.getenv("A2E_API_KEY", ""))
    return False


async def _resolve_provider(provider: str) -> ProviderAccountStatus:
    meta = _PROVIDERS[provider]
    configured = _is_configured(provider)

    if not configured:
        return ProviderAccountStatus(
            provider=provider,
            display_name=meta["display_name"],
            configured=False,
            status="disabled",
            balance=None,
            balance_label=None,
            currency=meta["currency"],
            vendor_url=meta["vendor_url"],
            supports_live_api=meta["supports_live_api"],
            source="disabled",
            error=None,
            last_checked=None,
        )

    cached = await _CACHE.get(provider)
    if cached:
        return cached

    balance: Optional[float] = None
    balance_label: Optional[str] = None
    error: Optional[str] = None
    source = "manual"

    if meta["supports_live_api"]:
        if provider == "piapi":
            balance, balance_label, error = await _fetch_piapi_balance()
            source = "live" if balance is not None else "env"
        # Future providers with live APIs land here.

    # Fall back to env-supplied number when the live call failed/absent.
    if balance is None:
        env_bal, env_label = _env_balance(provider)
        if env_bal is not None:
            balance = env_bal
            balance_label = env_label and f"~{env_label}"
            source = "env"

    status_value = _classify(provider, balance)
    result = ProviderAccountStatus(
        provider=provider,
        display_name=meta["display_name"],
        configured=True,
        status=status_value,
        balance=balance,
        balance_label=balance_label,
        currency=meta["currency"],
        vendor_url=meta["vendor_url"],
        supports_live_api=meta["supports_live_api"],
        source=source,
        error=error,
        last_checked=time.time() if source == "live" else None,
    )
    # Only cache live + env results. Manual-check (no API) statuses
    # don't change unless config changes, so caching them would just
    # delay a re-evaluation if the user updates the env var.
    if source in {"live", "env"}:
        await _CACHE.set(provider, result)
    return result


async def get_all_provider_status() -> List[ProviderAccountStatus]:
    """Return live status for every provider VidGo can route to.

    Calls run in parallel so the slowest fetcher doesn't gate the
    dashboard's render. A 10s per-fetcher timeout (set inside each
    fetcher) bounds total latency.
    """
    providers = list(_PROVIDERS.keys())
    results = await asyncio.gather(
        *(_resolve_provider(p) for p in providers),
        return_exceptions=True,
    )
    out: List[ProviderAccountStatus] = []
    for provider, result in zip(providers, results):
        if isinstance(result, Exception):
            # Defensive — _resolve_provider already swallows its own
            # exceptions, but if a programming bug ever leaks one we
            # still want the dashboard to render the other providers.
            logger.error("provider status resolution failed for %s: %s", provider, result)
            meta = _PROVIDERS[provider]
            out.append(
                ProviderAccountStatus(
                    provider=provider,
                    display_name=meta["display_name"],
                    configured=_is_configured(provider),
                    status="unknown",
                    balance=None,
                    balance_label=None,
                    currency=meta["currency"],
                    vendor_url=meta["vendor_url"],
                    supports_live_api=meta["supports_live_api"],
                    source="manual",
                    error=str(result),
                    last_checked=None,
                )
            )
        else:
            out.append(result)
    return out


def as_dict(status: ProviderAccountStatus) -> Dict:
    return asdict(status)
