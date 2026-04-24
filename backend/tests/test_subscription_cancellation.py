import pytest
from unittest.mock import AsyncMock
from unittest.mock import Mock, patch
from types import SimpleNamespace
from uuid import uuid4
from datetime import timedelta

from app.services.subscription_service import SubscriptionService, utc_now
from app.models.user import User


pytestmark = pytest.mark.asyncio


def _mock_db_with_empty_execute():
    db = AsyncMock()
    empty_result = Mock()
    scalars_obj = Mock()
    scalars_obj.first.return_value = None
    empty_result.scalars.return_value = scalars_obj
    db.execute = AsyncMock(return_value=empty_result)
    db.add = Mock()
    db.commit = AsyncMock()
    return db


def _build_user():
    return SimpleNamespace(
        id=uuid4(),
        email="qa-user@vidgo.local",
        username="qa-user",
        current_plan_id=uuid4(),
        plan_expires_at=utc_now() + timedelta(days=30),
        subscription_cancelled_at=None,
        work_retention_until=None,
        subscription_credits=20,
        purchased_credits=15,
        bonus_credits=5,
        total_credits=40,
    )


def _build_subscription(active_days=2):
    return SimpleNamespace(
        id=uuid4(),
        start_date=utc_now() - timedelta(days=active_days),
        end_date=utc_now() + timedelta(days=28),
        status="active",
        auto_renew=True,
    )


def _build_order():
    return SimpleNamespace(
        id=uuid4(),
        order_number="SUBTEST001",
        amount=399,
        status="paid",
        payment_method="ecpay",
        payment_data={"refund": {"status": "pending_manual"}},
        created_at=utc_now(),
        paid_at=utc_now(),
        user_id=uuid4(),
    )


async def test_cancel_with_refund_auto_processed_message_and_state():
    service = SubscriptionService()
    db = _mock_db_with_empty_execute()

    user = _build_user()
    subscription = _build_subscription(active_days=1)
    order = _build_order()

    db.get = AsyncMock(side_effect=lambda model, _id: user if model is User else None)
    service._get_active_subscription = AsyncMock(return_value=subscription)
    service._get_subscription_order = AsyncMock(return_value=order)
    service._process_refund = AsyncMock(return_value={"success": True, "amount": 399, "requires_manual": False})
    service._revoke_subscription_credits = AsyncMock(return_value=None)

    with patch("app.services.email_service.email_service.send_refund_notification", new=AsyncMock(return_value=True)):
        result = await service.cancel_subscription(db=db, user_id=user.id, request_refund=True)

    assert result["success"] is True
    assert result["refund_processed"] is True
    assert result["refund_requires_manual"] is False
    assert "immediately" in result["message"].lower()
    assert subscription.status == "cancelled"
    assert user.current_plan_id is None
    assert user.purchased_credits == 0
    assert user.bonus_credits == 0
    service._revoke_subscription_credits.assert_awaited_once()


async def test_cancel_with_refund_manual_processed_message_and_flag():
    service = SubscriptionService()
    db = _mock_db_with_empty_execute()

    user = _build_user()
    subscription = _build_subscription(active_days=1)
    order = _build_order()

    db.get = AsyncMock(side_effect=lambda model, _id: user if model is User else None)
    service._get_active_subscription = AsyncMock(return_value=subscription)
    service._get_subscription_order = AsyncMock(return_value=order)
    service._process_refund = AsyncMock(return_value={"success": True, "amount": 399, "requires_manual": True})
    service._revoke_subscription_credits = AsyncMock(return_value=None)

    with patch("app.services.email_service.email_service.send_refund_notification", new=AsyncMock(return_value=True)):
        result = await service.cancel_subscription(db=db, user_id=user.id, request_refund=True)

    assert result["success"] is True
    assert result["refund_processed"] is True
    assert result["refund_requires_manual"] is True
    assert "manual" in result["message"].lower()
    assert subscription.status == "cancelled"


async def test_cancel_without_refund_end_of_billing_period_message():
    service = SubscriptionService()
    db = _mock_db_with_empty_execute()

    user = _build_user()
    subscription = _build_subscription(active_days=20)
    order = _build_order()
    order.payment_data = {}

    db.get = AsyncMock(side_effect=lambda model, _id: user if model is User else None)
    service._get_active_subscription = AsyncMock(return_value=subscription)
    service._get_subscription_order = AsyncMock(return_value=order)
    service._process_refund = AsyncMock()

    result = await service.cancel_subscription(db=db, user_id=user.id, request_refund=False)

    assert result["success"] is True
    assert result["refund_processed"] is False
    assert "billing period" in result["message"].lower()
    assert subscription.status == "cancelled"
    assert user.current_plan_id is not None
    service._process_refund.assert_not_called()
