"""
PaymentSettingsService — single source of truth for PayPal runtime config.

Why this exists: PayPal credentials, the sandbox/production flag, and the
PayPal Plan ID mapping all need to change without a redeploy so admins
can rotate keys or flip environments from /admin/settings/payment. This
service reads from the `payment_settings` DB row first; any column that
is NULL or missing falls back to the value Cloud Run mounted from Secret
Manager.

The secret column is encrypted at rest with Fernet keyed off
`settings.SECRET_KEY`. Rotating SECRET_KEY invalidates stored secrets —
the admin then has to re-enter the value via the UI. That's intentional:
key rotation should never silently expose old ciphertexts.

The resolved values are cached in-process for `_CACHE_TTL_SECONDS` to
avoid hammering the DB on every PayPal API call. Admin writes call
`invalidate_cache()` to force the next read to refresh.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.payment_settings import PaymentSettings

logger = logging.getLogger(__name__)


_CACHE_TTL_SECONDS = 60.0
_cache: dict[str, "ResolvedPaymentSettings | float"] = {}


def _fernet() -> Fernet:
    """Derive a stable 32-byte Fernet key from SECRET_KEY.

    Fernet requires a url-safe base64-encoded 32-byte key. We SHA-256 the
    raw SECRET_KEY so callers can use any string length and we still get
    a valid key. Same derivation pattern used by many FastAPI projects.
    """
    raw = settings.SECRET_KEY.encode("utf-8")
    derived = hashlib.sha256(raw).digest()  # exactly 32 bytes
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_secret(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        # Most likely cause: SECRET_KEY was rotated and this row was
        # encrypted under the old key. Log loudly so the admin notices
        # in /admin and surfaces a "Re-enter your PayPal secret" banner.
        logger.error("Failed to decrypt payment secret — SECRET_KEY rotated? %s", exc)
        return ""


@dataclass(frozen=True)
class ResolvedPaymentSettings:
    """The effective PayPal config the runtime should use right now.

    Each field returns the DB value if set, otherwise the env / Secret
    Manager fallback. `source_*` flags let the admin UI show "from DB"
    vs "from environment" so they understand where each value came from.
    """
    paypal_env: str
    paypal_client_id: str
    paypal_client_secret: str
    paypal_webhook_id: str
    paypal_plan_ids: str

    # Bookkeeping shown in the admin UI.
    source_env_from_db: bool
    source_client_id_from_db: bool
    source_secret_from_db: bool
    source_webhook_from_db: bool
    source_plans_from_db: bool
    updated_at_iso: Optional[str]
    updated_by: Optional[str]


async def get_resolved_settings(db: AsyncSession) -> ResolvedPaymentSettings:
    """Return the effective PayPal config — DB-first, env fallback.

    Caches the result for `_CACHE_TTL_SECONDS` per process. Call
    `invalidate_cache()` after any admin write so the next request
    re-reads.
    """
    cached = _cache.get("resolved")
    ts = _cache.get("ts", 0)
    if isinstance(cached, ResolvedPaymentSettings) and isinstance(ts, float) and (time.time() - ts) < _CACHE_TTL_SECONDS:
        return cached

    row = (await db.execute(select(PaymentSettings).where(PaymentSettings.id == 1))).scalar_one_or_none()

    db_env       = (row.paypal_env or "").strip() if row else ""
    db_cid       = (row.paypal_client_id or "").strip() if row else ""
    db_secret_ct = (row.paypal_client_secret_encrypted or "").strip() if row else ""
    db_webhook   = (row.paypal_webhook_id or "").strip() if row else ""
    db_plans     = (row.paypal_plan_ids or "").strip() if row else ""

    decrypted_secret = decrypt_secret(db_secret_ct) if db_secret_ct else ""

    resolved = ResolvedPaymentSettings(
        paypal_env           = db_env       or (getattr(settings, "PAYPAL_ENV", "") or "sandbox"),
        paypal_client_id     = db_cid       or getattr(settings, "PAYPAL_CLIENT_ID", "") or "",
        paypal_client_secret = decrypted_secret or getattr(settings, "PAYPAL_CLIENT_SECRET", "") or "",
        paypal_webhook_id    = db_webhook   or getattr(settings, "PAYPAL_WEBHOOK_ID", "") or "",
        paypal_plan_ids      = db_plans     or getattr(settings, "PAYPAL_PLAN_IDS", "") or "",
        source_env_from_db        = bool(db_env),
        source_client_id_from_db  = bool(db_cid),
        source_secret_from_db     = bool(decrypted_secret),
        source_webhook_from_db    = bool(db_webhook),
        source_plans_from_db      = bool(db_plans),
        updated_at_iso = row.updated_at.isoformat() if (row and row.updated_at) else None,
        updated_by     = row.updated_by if row else None,
    )

    _cache["resolved"] = resolved
    _cache["ts"] = time.time()
    return resolved


async def update_settings(
    db: AsyncSession,
    *,
    updated_by: str,
    paypal_env: Optional[str] = None,
    paypal_client_id: Optional[str] = None,
    paypal_client_secret: Optional[str] = None,
    paypal_webhook_id: Optional[str] = None,
    paypal_plan_ids: Optional[str] = None,
) -> ResolvedPaymentSettings:
    """Write any subset of fields. None = "leave existing value alone";
    empty string = "clear DB override, fall back to env".
    """
    row = (await db.execute(select(PaymentSettings).where(PaymentSettings.id == 1))).scalar_one_or_none()
    if row is None:
        row = PaymentSettings(id=1)
        db.add(row)

    if paypal_env is not None:
        row.paypal_env = paypal_env or None
    if paypal_client_id is not None:
        row.paypal_client_id = paypal_client_id or None
    if paypal_client_secret is not None:
        # Empty string = clear; otherwise encrypt before storing.
        row.paypal_client_secret_encrypted = encrypt_secret(paypal_client_secret) if paypal_client_secret else None
    if paypal_webhook_id is not None:
        row.paypal_webhook_id = paypal_webhook_id or None
    if paypal_plan_ids is not None:
        row.paypal_plan_ids = paypal_plan_ids or None

    row.updated_by = updated_by
    await db.commit()
    invalidate_cache()
    return await get_resolved_settings(db)


def invalidate_cache() -> None:
    _cache.pop("resolved", None)
    _cache.pop("ts", None)
