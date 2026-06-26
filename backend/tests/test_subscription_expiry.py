"""Regression tests for the 'expired subscription still shows active' bug.

The $1 Pro test plan (auto_renew may be off, and the daily renew task never
flips status) kept status='active' after its end_date passed, so the pricing
page showed it active with a live cancel button. _get_active_subscription must
treat an active/pending row past its end_date as not-current.
"""
import pytest
from unittest.mock import AsyncMock, Mock
from types import SimpleNamespace
from uuid import uuid4
from datetime import timedelta

from app.services.subscription_service import SubscriptionService, utc_now

pytestmark = pytest.mark.asyncio


def _db_returning(subs):
    """Fake AsyncSession whose execute().scalars().all() yields `subs`."""
    db = AsyncMock()
    result = Mock()
    scalars_obj = Mock()
    scalars_obj.all.return_value = subs
    result.scalars.return_value = scalars_obj
    db.execute = AsyncMock(return_value=result)
    return db


def _sub(status, end_days):
    return SimpleNamespace(
        id=uuid4(),
        status=status,
        end_date=utc_now() + timedelta(days=end_days),
        start_date=utc_now() - timedelta(days=10),
        created_at=utc_now(),
    )


async def test_expired_active_subscription_is_not_returned():
    svc = SubscriptionService()
    db = _db_returning([_sub("active", -7)])  # ended 7 days ago
    assert await svc._get_active_subscription(db, uuid4()) is None


async def test_live_active_subscription_is_returned():
    svc = SubscriptionService()
    db = _db_returning([_sub("active", 7)])
    result = await svc._get_active_subscription(db, uuid4())
    assert result is not None and result.status == "active"


async def test_expired_active_skipped_then_live_one_returned():
    svc = SubscriptionService()
    expired, live = _sub("active", -3), _sub("active", 30)
    result = await svc._get_active_subscription(_db_returning([expired, live]), uuid4())
    assert result is live


async def test_cancelled_within_period_still_returned():
    svc = SubscriptionService()
    db = _db_returning([_sub("cancelled", 5)])  # cancel-at-period-end, still valid
    result = await svc._get_active_subscription(db, uuid4())
    assert result is not None and result.status == "cancelled"


async def test_active_without_end_date_is_returned():
    svc = SubscriptionService()
    sub = _sub("active", 0)
    sub.end_date = None  # open-ended subs must stay active
    result = await svc._get_active_subscription(_db_returning([sub]), uuid4())
    assert result is not None
