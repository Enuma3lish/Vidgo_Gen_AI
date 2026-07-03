from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

import pytest
from fastapi import HTTPException

from app.api.v1 import interior
from app.models.user import User
from app.providers.piapi_provider import PiAPIProvider
from app.providers.provider_router import TaskType


pytestmark = pytest.mark.asyncio


def _paid_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="paid@example.com",
        username="paid",
        hashed_password="hashed",
        is_active=True,
        email_verified=True,
        current_plan_id=uuid.uuid4(),
        plan_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        subscription_credits=100,
        purchased_credits=0,
        bonus_credits=0,
    )


def _free_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="free@example.com",
        username="free",
        hashed_password="hashed",
        is_active=True,
        email_verified=True,
        subscription_credits=0,
        purchased_credits=0,
        bonus_credits=0,
    )


async def test_generate_3d_model_routes_to_trellis(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeProviderRouter:
        async def route(self, task_type: TaskType, params: dict[str, Any], user_tier: str = "starter") -> dict[str, Any]:
            captured["task_type"] = task_type
            captured["params"] = params
            captured["user_tier"] = user_tier
            return {
                "success": True,
                "task_id": "trellis-task-1",
                "output": {
                    "model_url": "https://cdn.example.com/model.glb",
                    "image_url": "https://cdn.example.com/preview.png",
                    "video_url": "https://cdn.example.com/preview.mp4",
                },
            }

    monkeypatch.setattr(interior, "get_provider_router", lambda: FakeProviderRouter())

    response = await interior.generate_3d_model(
        interior.Generate3DRequest(
            image_url="https://cdn.example.com/floor-plan.jpg",
            texture_size=1024,
            mesh_simplify=0.95,
        ),
        current_user=_paid_user(),
    )

    assert response.success is True
    assert response.model_url == "https://cdn.example.com/model.glb"
    assert response.preview_image_url == "https://cdn.example.com/preview.png"
    assert response.preview_video_url == "https://cdn.example.com/preview.mp4"
    assert response.task_id == "trellis-task-1"
    assert captured == {
        "task_type": TaskType.INTERIOR_3D,
        "params": {
            "image_url": "https://cdn.example.com/floor-plan.jpg",
            "texture_size": 1024,
            "mesh_simplify": 0.95,
            "model_version": "v1",
        },
        # 2026-07: the endpoint passes the user's REAL tier (get_user_tier)
        # instead of a hardcoded "paid"; a subscriber whose plan row isn't
        # loaded resolves to at least "basic".
        "user_tier": "basic",
    }


async def test_generate_3d_model_requires_subscription() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await interior.generate_3d_model(
            interior.Generate3DRequest(image_url="https://cdn.example.com/floor-plan.jpg"),
            current_user=_free_user(),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "3D model generation requires an active subscription"


async def test_piapi_trellis_3d_normalizes_model_url(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = PiAPIProvider()
    captured: dict[str, Any] = {}

    async def fake_submit_and_poll(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        # trellis_3d passes max_wait_seconds (TRELLIS_TIMEOUT_SEC) since 2026-07
        captured["payload"] = payload
        captured["max_wait_seconds"] = kwargs.get("max_wait_seconds")
        return {
            "success": True,
            "task_id": "task-123",
            "output": {
                "no_background_image": "https://cdn.example.com/no-bg.png",
                "combined_video": "https://cdn.example.com/spin.mp4",
                "model_file": "https://cdn.example.com/model.glb",
            },
        }

    monkeypatch.setattr(provider, "_submit_and_poll", fake_submit_and_poll)

    try:
        result = await provider.trellis_3d({"image_url": "https://cdn.example.com/floor-plan.jpg"})
    finally:
        await provider.close()

    assert captured["payload"] == {
        "model": "Qubico/trellis",
        "task_type": "image-to-3d",
        "input": {"image": "https://cdn.example.com/floor-plan.jpg"},
    }
    assert result["output"]["model_url"] == "https://cdn.example.com/model.glb"
    assert result["output"]["image_url"] == "https://cdn.example.com/no-bg.png"
    assert result["output"]["video_url"] == "https://cdn.example.com/spin.mp4"
