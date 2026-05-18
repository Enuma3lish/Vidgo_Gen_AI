"""
PaymentSettings — single-row table holding admin-editable PayPal config.

Lets an admin flip PayPal sandbox ↔ production and rotate credentials /
plan IDs from /admin/settings/payment without a redeploy. Reads from this
table take priority over the Cloud Run env / Secret Manager values; when
a column is NULL or absent the runtime falls back to the env value.

Secrets (`paypal_client_secret`) are stored encrypted at rest with
Fernet, keyed off settings.SECRET_KEY — same key used by JWT signing.
Plaintext columns (`paypal_client_id`, `paypal_webhook_id`,
`paypal_plan_ids`, `paypal_env`) are stored as-is.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.core.database import Base


class PaymentSettings(Base):
    __tablename__ = "payment_settings"

    id = Column(Integer, primary_key=True, default=1)

    # 'sandbox' or 'production'. NULL → falls back to env PAYPAL_ENV.
    paypal_env = Column(String(20), nullable=True)

    # Client ID is treated as semi-public (it's used in client-side SDKs)
    # but we still keep it in DB to allow flipping between sandbox / prod
    # alongside the secret.
    paypal_client_id = Column(String(255), nullable=True)

    # Encrypted via Fernet (services.payment_settings_service.encrypt_secret).
    # Stored as a base64-encoded ciphertext string; decryption requires
    # settings.SECRET_KEY to be unchanged. Rotating SECRET_KEY invalidates
    # all stored secrets and the admin must re-enter the value.
    paypal_client_secret_encrypted = Column(Text, nullable=True)

    paypal_webhook_id = Column(String(120), nullable=True)

    # JSON-encoded mapping: {"basic_monthly":"P-...", "pro_yearly":"P-...", ...}
    # Stored as text so the admin can paste the full block from PayPal's
    # plan dashboard without any pre-parsing.
    paypal_plan_ids = Column(Text, nullable=True)

    updated_by = Column(String(120), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
