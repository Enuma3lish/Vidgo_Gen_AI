"""Add is_refundable / refund_blocked_at / refund_blocked_reason to subscriptions.

Revision ID: o4p5q6r7s8t9
Revises: n3o4p5q6r7s8
Create Date: 2026-05-25

Owner directive (2026-05-25):
    The 5%-usage refund gate + HQ-export gate already exist in
    ``subscription_service._refund_usage_allowed``, but they're recomputed
    on every refund request from CreditTransaction rows. That leaves two
    gaps:

      1. **No audit trail.** If transactions are deleted, expired, or the
         user clears history, refund eligibility can't be verified later.
      2. **Race window.** A user who exports an HQ render and immediately
         clicks "Refund" can hit the cancel endpoint before the gate
         finishes counting their transactions.

    This migration adds a persistent flag (``is_refundable``) that's
    flipped to FALSE the FIRST time a gate fails, plus a timestamp and
    a short machine-readable reason code. The cancel endpoint now reads
    the flag as the fast path and only falls back to recomputing the
    gates if the flag is still TRUE.

    Backfill: any existing subscription that would currently fail the
    gates is marked non-refundable at migration time. Operators can
    manually re-enable specific rows via SQL or the admin endpoint
    (PATCH /admin/subscriptions/{id}/refund-eligibility).

All operations are idempotent (ADD COLUMN IF NOT EXISTS) and fully
reversible.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o4p5q6r7s8t9"
down_revision: Union[str, None] = "n3o4p5q6r7s8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Mirror constants from app.services.subscription_service so the migration
# is self-contained (no Python import of the app at migration time).
REFUND_USAGE_THRESHOLD = 0.05  # fraction of monthly allowance
REFUND_HQ_EXPORT_THRESHOLD = 5  # credits per single generation


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. Add the three columns. Use ADD COLUMN IF NOT EXISTS so reruns
    # don't fail on Postgres ≥ 9.6.
    op.execute(
        """
        ALTER TABLE subscriptions
          ADD COLUMN IF NOT EXISTS is_refundable BOOLEAN NOT NULL DEFAULT TRUE,
          ADD COLUMN IF NOT EXISTS refund_blocked_at TIMESTAMPTZ NULL,
          ADD COLUMN IF NOT EXISTS refund_blocked_reason VARCHAR(64) NULL
        """
    )

    # ── 2. Backfill: flip is_refundable=FALSE for any subscription whose
    # accumulated generation deductions since start_date already crossed
    # either gate. We use a single UPDATE with a CTE so it runs in one
    # transaction and stays fast on tables with millions of transaction rows.
    #
    # Constants are inlined via f-string (not bindparams) because alembic's
    # offline --sql mode renders unbound parameters as literal NULL, which
    # would silently produce a no-op backfill if anyone generated SQL for
    # manual review. Both values are hardcoded module-level constants here
    # (mirrors of REFUND_USAGE_THRESHOLD / REFUND_HQ_EXPORT_THRESHOLD in
    # subscription_service.py), never user input — no injection surface.
    backfill_sql = f"""
        WITH usage AS (
            SELECT
                s.id                                  AS sub_id,
                COALESCE(p.monthly_credits, 0)        AS allowance,
                COALESCE(SUM(CASE
                    WHEN ct.transaction_type = 'generation' AND ct.amount < 0
                    THEN -ct.amount ELSE 0 END), 0)   AS used,
                COALESCE(SUM(CASE
                    WHEN ct.transaction_type = 'generation'
                     AND ct.amount <= -{REFUND_HQ_EXPORT_THRESHOLD}
                    THEN 1 ELSE 0 END), 0)            AS hq_count
            FROM subscriptions s
            LEFT JOIN plans p              ON p.id = s.plan_id
            LEFT JOIN credit_transactions ct
                   ON ct.user_id = s.user_id
                  AND ct.created_at >= s.start_date
            GROUP BY s.id, p.monthly_credits
        )
        UPDATE subscriptions s
           SET is_refundable        = FALSE,
               refund_blocked_at    = NOW(),
               refund_blocked_reason = CASE
                   WHEN u.hq_count > 0 THEN 'HQ_EXPORT_PRODUCED'
                   ELSE 'USAGE_EXCEEDED'
               END
          FROM usage u
         WHERE s.id = u.sub_id
           AND u.allowance > 0
           AND (
               u.hq_count > 0
               OR u.used >= (u.allowance * {REFUND_USAGE_THRESHOLD})
           )
    """
    bind.execute(sa.text(backfill_sql))

    # ── 3. Helpful index for the admin "non-refundable cohort" report.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_subscriptions_is_refundable
            ON subscriptions (is_refundable)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_subscriptions_is_refundable")
    op.execute(
        """
        ALTER TABLE subscriptions
          DROP COLUMN IF EXISTS refund_blocked_reason,
          DROP COLUMN IF EXISTS refund_blocked_at,
          DROP COLUMN IF EXISTS is_refundable
        """
    )
