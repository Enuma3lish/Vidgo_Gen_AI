from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch
import uuid

import pytest
from sqlalchemy.sql.elements import BinaryExpression, BindParameter, BooleanClauseList

from app.core.config import settings
from app.models.billing import CreditTransaction
from app.models.user import User
from app.services.referral_service import ReferralService


pytestmark = pytest.mark.asyncio


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FakeScalarResult:
    def __init__(self, items: list[Any]):
        self._items = items

    def first(self) -> Any:
        return self._items[0] if self._items else None


class FakeExecuteResult:
    def __init__(self, items: list[Any]):
        self._items = items

    def scalars(self) -> FakeScalarResult:
        return FakeScalarResult(self._items)

    def scalar_one_or_none(self) -> Any:
        return self._items[0] if self._items else None


class FakeReferralSession:
    def __init__(self, users: list[User]):
        self.users = users
        self.transactions: list[CreditTransaction] = []

    def add(self, instance: Any) -> None:
        if isinstance(instance, CreditTransaction):
            if not getattr(instance, "id", None):
                instance.id = uuid.uuid4()
            if not instance.created_at:
                instance.created_at = _utcnow()
            self.transactions.append(instance)
            return
        raise AssertionError(f"Unsupported add() instance: {instance!r}")

    async def commit(self) -> None:
        return None

    async def execute(self, statement: Any) -> FakeExecuteResult:
        model = statement.column_descriptions[0]["entity"]
        if model is User:
            return FakeExecuteResult([user for user in self.users if self._matches(statement, user)])
        if model is CreditTransaction:
            return FakeExecuteResult([tx for tx in self.transactions if self._matches(statement, tx)])
        raise AssertionError(f"Unsupported execute() model: {model!r}")

    def _matches(self, statement: Any, instance: Any) -> bool:
        return all(self._eval_criterion(criterion, instance) for criterion in getattr(statement, "_where_criteria", ()))

    def _eval_criterion(self, criterion: Any, instance: Any) -> bool:
        if isinstance(criterion, BooleanClauseList):
            return all(self._eval_criterion(clause, instance) for clause in criterion.clauses)

        if not isinstance(criterion, BinaryExpression):
            raise AssertionError(f"Unsupported criterion: {criterion!r}")

        operator_name = criterion.operator.__name__
        column_name = getattr(criterion.left, "name", None)
        value = criterion.right.value if isinstance(criterion.right, BindParameter) else criterion.right
        instance_value = getattr(instance, column_name)

        if isinstance(instance_value, uuid.UUID) and isinstance(value, str):
            value = uuid.UUID(value)

        if operator_name == "eq":
            return instance_value == value
        if operator_name == "in_op":
            return instance_value in value

        raise AssertionError(f"Unsupported operator: {operator_name}")


async def test_award_referral_bonus_sends_promoter_system_email() -> None:
    promoter = User(
        id=uuid.uuid4(),
        email="promoter@example.com",
        username="promoter",
        hashed_password="hashed",
        is_active=True,
        email_verified=True,
        referral_code="PROMO40",
        referral_count=0,
        subscription_credits=0,
        purchased_credits=0,
        bonus_credits=0,
        created_at=_utcnow(),
    )
    new_user = User(
        id=uuid.uuid4(),
        email="promo-member@example.com",
        username="promomember",
        hashed_password="hashed",
        is_active=True,
        email_verified=True,
        referred_by_id=promoter.id,
        subscription_credits=0,
        purchased_credits=0,
        bonus_credits=settings.REGISTRATION_BONUS_CREDITS,
        created_at=_utcnow(),
    )
    db = FakeReferralSession([promoter, new_user])

    with patch(
        "app.services.referral_service.email_service.send_promotion_code_used_email",
        new=AsyncMock(return_value=True),
    ) as promoter_email_mock:
        success, message = await ReferralService(db).award_referral_bonus(new_user)

    assert success, message
    assert promoter.referral_count == 1
    assert promoter.bonus_credits == settings.REFERRAL_BONUS_CREDITS
    assert new_user.bonus_credits == settings.REGISTRATION_BONUS_CREDITS + settings.REFERRAL_WELCOME_CREDITS
    assert len([tx for tx in db.transactions if tx.description == "Welcome bonus for using a promotion code"]) == 1

    promoter_email_mock.assert_awaited_once_with(
        to_email=promoter.email,
        username=promoter.username,
        new_user_email=new_user.email,
        promotion_code=promoter.referral_code,
        reward_credits=settings.REFERRAL_BONUS_CREDITS,
    )
