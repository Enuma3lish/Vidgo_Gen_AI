"""Idempotent perf-audit schema migration (2026-07-12).

The repo has 14 un-merged alembic heads, so schema changes are applied as
idempotent raw SQL via a Cloud Run job (same pattern as vidgo-db-migrate),
NOT `alembic upgrade`. Safe to run repeatedly.

Covers:
  #7 orders.paypal_transaction_id / paypal_capture_id indexed columns + backfill
     + processed_webhook_events dedup table
  #9 credit_transactions partial composite index (deduct/balance hot path)
     + user_generations (user_id, created_at) index (My Works)
"""
import asyncio
import os
import asyncpg


STATEMENTS = [
    # ── #7 orders: indexed PayPal ids ────────────────────────────────────
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS paypal_transaction_id VARCHAR(200)",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS paypal_capture_id VARCHAR(200)",
    "CREATE INDEX IF NOT EXISTS ix_orders_paypal_transaction_id ON orders (paypal_transaction_id)",
    "CREATE INDEX IF NOT EXISTS ix_orders_paypal_capture_id ON orders (paypal_capture_id)",
    # backfill from the existing JSON blob (JSON ->> works on json + jsonb)
    """UPDATE orders
         SET paypal_transaction_id = payment_data->>'paypal_transaction_id'
       WHERE paypal_transaction_id IS NULL
         AND payment_data->>'paypal_transaction_id' IS NOT NULL""",

    # ── #7/#10 webhook dedup belt ────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS processed_webhook_events (
          event_id     VARCHAR(255) PRIMARY KEY,
          provider     VARCHAR(32),
          processed_at TIMESTAMPTZ DEFAULT now()
       )""",
    "CREATE INDEX IF NOT EXISTS ix_processed_webhook_events_processed_at ON processed_webhook_events (processed_at)",

    # ── #9 credit_transactions deduct/balance hot path ───────────────────
    # The monthly SUM filters (user_id, amount<0, created_at, transaction_type).
    """CREATE INDEX IF NOT EXISTS ix_credit_tx_user_type_created
         ON credit_transactions (user_id, transaction_type, created_at)
       WHERE amount < 0""",

    # ── #9 user_generations My Works list ────────────────────────────────
    "CREATE INDEX IF NOT EXISTS ix_user_gen_user_created ON user_generations (user_id, created_at DESC)",
]


async def main() -> None:
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)
    try:
        for sql in STATEMENTS:
            await conn.execute(sql)
            print("APPLIED:", " ".join(sql.split())[:90])
        # Verify
        cols = await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='orders' AND column_name LIKE 'paypal_%'"
        )
        print("orders paypal_* columns:", sorted(r[0] for r in cols))
        idx = await conn.fetch(
            "SELECT indexname FROM pg_indexes "
            "WHERE indexname IN ('ix_orders_paypal_transaction_id','ix_orders_paypal_capture_id',"
            "'ix_credit_tx_user_type_created','ix_user_gen_user_created')"
        )
        print("indexes present:", sorted(r[0] for r in idx))
        backfilled = await conn.fetchval(
            "SELECT count(*) FROM orders WHERE paypal_transaction_id IS NOT NULL"
        )
        print("orders with paypal_transaction_id:", backfilled)
    finally:
        await conn.close()
    print("perf migration complete")


if __name__ == "__main__":
    asyncio.run(main())
