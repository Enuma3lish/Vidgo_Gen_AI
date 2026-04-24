from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, patch
import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.sql.elements import BinaryExpression, BooleanClauseList, BindParameter

from app.api.deps import get_db
from app.main import app
from app.models.user import User
from app.models.verification import EmailVerification


pytestmark = pytest.mark.asyncio


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FakeScalarResult:
    def __init__(self, items: list[Any]):
        self._items = items

    def first(self) -> Any:
        return self._items[0] if self._items else None

    def all(self) -> list[Any]:
        return list(self._items)


class FakeExecuteResult:
    def __init__(self, items: list[Any]):
        self._items = items

    def scalars(self) -> FakeScalarResult:
        return FakeScalarResult(self._items)

    def scalar_one_or_none(self) -> Any:
        if not self._items:
            return None
        return self._items[0]


@dataclass
class FakeRedis:
    values: dict[str, str] = field(default_factory=dict)
    expirations: dict[str, datetime] = field(default_factory=dict)

    def _purge_if_expired(self, key: str) -> None:
        expires_at = self.expirations.get(key)
        if expires_at and expires_at <= _utcnow():
            self.values.pop(key, None)
            self.expirations.pop(key, None)

    async def get(self, key: str) -> str | None:
        self._purge_if_expired(key)
        return self.values.get(key)

    async def setex(self, key: str, ttl_seconds: int, value: str) -> bool:
        self.values[key] = value
        self.expirations[key] = _utcnow() + timedelta(seconds=ttl_seconds)
        return True

    async def incr(self, key: str) -> int:
        self._purge_if_expired(key)
        current = int(self.values.get(key, "0")) + 1
        self.values[key] = str(current)
        return current

    async def expire(self, key: str, ttl_seconds: int) -> bool:
        if key in self.values:
            self.expirations[key] = _utcnow() + timedelta(seconds=ttl_seconds)
            return True
        return False

    async def delete(self, key: str) -> int:
        existed = key in self.values
        self.values.pop(key, None)
        self.expirations.pop(key, None)
        return 1 if existed else 0

    async def ttl(self, key: str) -> int:
        self._purge_if_expired(key)
        expires_at = self.expirations.get(key)
        if not expires_at:
            return -1
        return max(0, int((expires_at - _utcnow()).total_seconds()))

    async def close(self) -> None:
        return None


class FakeAsyncSession:
    def __init__(self):
        self.users: list[User] = []
        self.verifications: list[EmailVerification] = []

    def add(self, instance: Any) -> None:
        if isinstance(instance, User):
            if not getattr(instance, "id", None):
                instance.id = uuid.uuid4()
            if not instance.created_at:
                instance.created_at = _utcnow()
            if instance.is_superuser is None:
                instance.is_superuser = False
            if instance.subscription_credits is None:
                instance.subscription_credits = 0
            if instance.purchased_credits is None:
                instance.purchased_credits = 0
            if instance.bonus_credits is None:
                instance.bonus_credits = 0
            if instance.referral_count is None:
                instance.referral_count = 0
            if instance.demo_usage_count is None:
                instance.demo_usage_count = 0
            if instance.demo_usage_limit is None:
                instance.demo_usage_limit = 2
            if not instance.referral_code:
                instance.referral_code = "TESTREF1"
            self.users.append(instance)
            return

        if isinstance(instance, EmailVerification):
            if not getattr(instance, "id", None):
                instance.id = uuid.uuid4()
            if not instance.created_at:
                instance.created_at = _utcnow()
            if instance.attempts is None:
                instance.attempts = 0
            if not instance.status:
                instance.status = "pending"
            self.verifications.append(instance)
            return

        raise AssertionError(f"Unsupported add() instance: {instance!r}")

    async def commit(self) -> None:
        return None

    async def refresh(self, instance: Any) -> None:
        return None

    async def get(self, model: type[Any], primary_key: Any) -> Any:
        if model is User:
            for user in self.users:
                if user.id == primary_key:
                    return user
            return None
        return None

    async def execute(self, statement: Any) -> FakeExecuteResult:
        model = statement.column_descriptions[0]["entity"]

        if model is User:
            matches = [user for user in self.users if self._matches(statement, user)]
            return FakeExecuteResult(matches)

        if model is EmailVerification:
            matches = [item for item in self.verifications if self._matches(statement, item)]
            matches.sort(key=lambda item: item.created_at or _utcnow(), reverse=True)
            return FakeExecuteResult(matches)

        if getattr(model, "__name__", "") == "Subscription":
            return FakeExecuteResult([])

        raise AssertionError(f"Unsupported execute() model: {model!r}")

    def _matches(self, statement: Any, instance: Any) -> bool:
        criteria = getattr(statement, "_where_criteria", ())
        return all(self._eval_criterion(criterion, instance) for criterion in criteria)

    def _eval_criterion(self, criterion: Any, instance: Any) -> bool:
        if isinstance(criterion, BooleanClauseList):
            return all(self._eval_criterion(clause, instance) for clause in criterion.clauses)

        if not isinstance(criterion, BinaryExpression):
            raise AssertionError(f"Unsupported criterion: {criterion!r}")

        operator_name = criterion.operator.__name__
        column_name = getattr(criterion.left, "name", None)
        value = self._resolve_value(criterion.right)
        instance_value = getattr(instance, column_name)

        if isinstance(instance_value, uuid.UUID) and isinstance(value, str):
            value = uuid.UUID(value)

        if operator_name == "eq":
            return instance_value == value
        if operator_name == "in_op":
            return instance_value in value

        raise AssertionError(f"Unsupported operator: {operator_name}")

    def _resolve_value(self, value: Any) -> Any:
        if isinstance(value, BindParameter):
            return value.value
        return value


@pytest.fixture(autouse=True)
async def mock_startup() -> None:
    with patch("app.main.validate_materials_on_startup", new_callable=AsyncMock) as mock_validate:
        mock_validate.return_value = {"all_ready": True, "missing": []}
        yield


@pytest.fixture
def fake_db() -> FakeAsyncSession:
    return FakeAsyncSession()


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
async def client(fake_db: FakeAsyncSession, fake_redis: FakeRedis):
    async def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db

    with (
        patch("app.api.v1.auth.get_redis_client", new=AsyncMock(return_value=fake_redis)),
        patch("app.services.email_verify.EmailVerificationService._generate_code", return_value="246810"),
        patch("app.api.v1.auth.email_service.send_verification_code_email", new=AsyncMock(return_value=True)),
        patch("app.api.v1.auth.email_service.send_verification_email", new=AsyncMock(return_value=True)),
        patch("app.api.v1.auth.email_service.send_welcome_email", new=AsyncMock(return_value=True)),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as async_client:
            yield async_client

    app.dependency_overrides.clear()


async def test_registration_flow_visitor_to_verified_unpaid_member(
    client: AsyncClient,
    fake_db: FakeAsyncSession,
    fake_redis: FakeRedis,
) -> None:
    register_payload = {
        "email": "new-member@example.com",
        "username": "newmember",
        "full_name": "New Member",
        "password": "StrongPass123",
        "password_confirm": "StrongPass123",
    }

    register_response = await client.post("/api/v1/auth/register", json=register_payload)
    assert register_response.status_code == 200
    assert "Registration successful" in register_response.json()["message"]

    created_user = fake_db.users[0]
    assert created_user.email == register_payload["email"]
    assert created_user.is_active is False
    assert created_user.email_verified is False
    assert created_user.subscription_credits == 0
    assert created_user.current_plan_id is None
    assert created_user.bonus_credits > 0

    duplicate_response = await client.post("/api/v1/auth/register", json=register_payload)
    assert duplicate_response.status_code == 409
    assert "already exists" in duplicate_response.json()["detail"]
    assert "verification code" in duplicate_response.json()["detail"].lower()

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    assert login_response.status_code == 403
    assert "verify your email" in login_response.json()["detail"].lower()

    verify_key = f"email_verify:{register_payload['email']}"
    assert verify_key in fake_redis.values
    verification_code = "246810"

    verify_response = await client.post(
        "/api/v1/auth/verify-code",
        json={"email": register_payload["email"], "code": verification_code},
    )
    assert verify_response.status_code == 200

    verify_payload = verify_response.json()
    assert verify_payload["user"]["email"] == register_payload["email"]
    assert verify_payload["user"]["is_active"] is True
    assert verify_payload["user"]["email_verified"] is True
    assert verify_payload["user"]["plan_type"] is None
    assert verify_payload["access_token"]
    assert verify_payload["refresh_token"]

    assert created_user.is_active is True
    assert created_user.email_verified is True

    auth_headers = {"Authorization": f"Bearer {verify_payload['access_token']}"}

    me_response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me_response.status_code == 200
    me_payload = me_response.json()
    assert me_payload["email"] == register_payload["email"]
    assert me_payload["is_active"] is True
    assert me_payload["email_verified"] is True
    assert me_payload["plan_type"] is None

    subscription_response = await client.get("/api/v1/subscriptions/status", headers=auth_headers)
    assert subscription_response.status_code == 200
    subscription_payload = subscription_response.json()
    assert subscription_payload["success"] is True
    assert subscription_payload["has_subscription"] is False
    assert subscription_payload["status"] == "none"
    assert subscription_payload["plan"] is None
    assert subscription_payload["credits"]["subscription"] == 0
    assert subscription_payload["credits"]["bonus"] == created_user.bonus_credits
    assert subscription_payload["credits"]["total"] == created_user.total_credits


async def test_registration_reports_email_failure_when_smtp_send_fails(
    fake_db: FakeAsyncSession,
    fake_redis: FakeRedis,
) -> None:
    async def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db

    with (
        patch("app.api.v1.auth.get_redis_client", new=AsyncMock(return_value=fake_redis)),
        patch("app.services.email_verify.EmailVerificationService._generate_code", return_value="246810"),
        patch("app.api.v1.auth.email_service.send_verification_code_email", new=AsyncMock(return_value=False)),
        patch("app.api.v1.auth.email_service.send_verification_email", new=AsyncMock(return_value=False)),
        patch("app.api.v1.auth.email_service.send_welcome_email", new=AsyncMock(return_value=True)),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as async_client:
            response = await async_client.post(
                "/api/v1/auth/register",
                json={
                    "email": "smtp-fail@example.com",
                    "username": "smtpfail",
                    "full_name": "SMTP Fail",
                    "password": "StrongPass123",
                    "password_confirm": "StrongPass123",
                },
            )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["message"].startswith("Account created, but we could not send the verification code")