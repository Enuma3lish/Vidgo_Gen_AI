from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.sql.elements import BinaryExpression, BindParameter, BooleanClauseList

from app.api.v1.user_works import download_generation, list_user_generations
from app.models.material import ToolType
from app.models.user import User
from app.models.user_generation import UserGeneration


pytestmark = pytest.mark.asyncio


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _paid_user(email: str) -> User:
    return User(
        id=uuid.uuid4(),
        email=email,
        username=email.split("@", 1)[0],
        hashed_password="hashed",
        is_active=True,
        email_verified=True,
        current_plan_id=uuid.uuid4(),
        plan_expires_at=_utcnow() + timedelta(days=30),
        subscription_credits=100,
        purchased_credits=0,
        bonus_credits=0,
        created_at=_utcnow(),
    )


def _generation(user: User, result_url: str) -> UserGeneration:
    generation = UserGeneration(
        id=uuid.uuid4(),
        user_id=user.id,
        tool_type=ToolType.PRODUCT_SCENE,
        input_image_url="https://cdn.example.com/input.png",
        input_params={"style": "studio"},
        result_image_url=result_url,
        credits_used=3,
        created_at=_utcnow(),
    )
    generation.set_expiry()
    return generation


class FakeScalarResult:
    def __init__(self, items: list[Any]):
        self._items = items

    def all(self) -> list[Any]:
        return list(self._items)


class FakeExecuteResult:
    def __init__(self, items: list[Any]):
        self._items = items

    def scalars(self) -> FakeScalarResult:
        return FakeScalarResult(self._items)

    def scalar_one_or_none(self) -> Any:
        return self._items[0] if self._items else None


class FakeUserWorksSession:
    def __init__(self, generations: list[UserGeneration]):
        self.generations = generations

    async def scalar(self, statement: Any) -> int:
        return len([generation for generation in self.generations if self._matches(statement, generation)])

    async def execute(self, statement: Any) -> FakeExecuteResult:
        matches = [generation for generation in self.generations if self._matches(statement, generation)]
        return FakeExecuteResult(matches)

    async def delete(self, instance: Any) -> None:
        self.generations.remove(instance)

    async def commit(self) -> None:
        return None

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

        raise AssertionError(f"Unsupported operator: {operator_name}")


async def test_paid_user_library_lists_only_current_users_generations() -> None:
    paid_user = _paid_user("paid@example.com")
    other_user = _paid_user("other@example.com")
    own_generation = _generation(paid_user, "https://cdn.example.com/own.png")
    other_generation = _generation(other_user, "https://cdn.example.com/other.png")
    db = FakeUserWorksSession([own_generation, other_generation])

    response = await list_user_generations(current_user=paid_user, db=db)

    assert response.total == 1
    assert [item.id for item in response.items] == [str(own_generation.id)]


async def test_paid_user_cannot_download_another_users_generation() -> None:
    paid_user = _paid_user("paid@example.com")
    other_user = _paid_user("other@example.com")
    other_generation = _generation(other_user, "https://cdn.example.com/other.png")
    db = FakeUserWorksSession([other_generation])

    with pytest.raises(HTTPException) as exc_info:
        await download_generation(str(other_generation.id), current_user=paid_user, db=db)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Work not found"


async def test_paid_user_can_download_own_generation() -> None:
    paid_user = _paid_user("paid@example.com")
    own_generation = _generation(paid_user, "https://cdn.example.com/own.png")
    db = FakeUserWorksSession([own_generation])

    response = await download_generation(str(own_generation.id), current_user=paid_user, db=db)

    assert response.status_code == 307
    assert response.headers["location"] == own_generation.result_image_url
