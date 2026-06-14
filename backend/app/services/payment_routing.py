"""
Geo-based payment routing helper (VidGo 2.0 spec, Section 四).

Routes the right currency / payment gateway based on client IP:
  - 台灣 (TW)  → currency=TWD, gateway=ECPay (綠界)
  - 海外 (其他)→ currency=USD, gateway=PayPal

Detection priority (cheap first → expensive last):
  1. Cloudflare's `cf-ipcountry` header
  2. Generic `x-country` / `x-vercel-ip-country` headers
  3. Default to "OTHER" (USD + PayPal)

This helper is intentionally header-driven so it works on Cloud Run behind
Cloudflare without bundling a GeoIP database.
"""
from __future__ import annotations

from typing import NamedTuple

from fastapi import Request


class PaymentRoute(NamedTuple):
    country: str   # ISO-3166-1 alpha-2 ("TW", "US", "OTHER")
    currency: str  # "TWD" or "USD"
    gateway: str   # "ecpay" or "paypal"


_COUNTRY_HEADERS = (
    "cf-ipcountry",
    "x-vercel-ip-country",
    "x-country",
    "x-appengine-country",
)


def detect_country(request: Request) -> str:
    """Best-effort country detection from request headers."""
    if request is None:
        return "OTHER"
    for header in _COUNTRY_HEADERS:
        value = request.headers.get(header)
        if value:
            value = value.strip().upper()
            if value and value not in {"XX", "T1"}:  # XX/T1 = unknown / Tor
                return value
    return "OTHER"


def infer_payment_route(request: Request) -> PaymentRoute:
    """Determine the recommended currency + payment gateway for this request."""
    country = detect_country(request)

    if country == "TW":
        return PaymentRoute(country="TW", currency="TWD", gateway="ecpay")

    return PaymentRoute(country=country, currency="USD", gateway="paypal")
