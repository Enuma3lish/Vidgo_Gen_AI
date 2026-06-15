from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest

from app.api.v1 import uploads
from app.models.user_upload import UploadStatus, UserUpload
from app.providers.provider_router import TaskType


pytestmark = pytest.mark.asyncio


class _FakeScalarResult:
    """Minimal stand-in for a SQLAlchemy Result. _trigger_generation only calls
    .scalar_one_or_none() on the User lookup it uses to resolve the tier;
    returning None makes get_user_tier fall back to "free", which is fine for
    these routing assertions."""
    def scalar_one_or_none(self) -> Any:
        return None


class FakeDb:
    def __init__(self) -> None:
        self.commits = 0

    async def execute(self, *args: Any, **kwargs: Any) -> _FakeScalarResult:
        return _FakeScalarResult()

    async def commit(self) -> None:
        self.commits += 1


async def test_upload_avatar_generation_routes_script_and_text(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeProviderRouter:
        # Accept **kwargs so the route() call's user_tier= (margin gate, 2026-06)
        # and any future keyword args don't break the capture.
        async def route(self, task_type: TaskType, params: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            captured["task_type"] = task_type
            captured["params"] = params
            return {
                "success": True,
                "output": {"video_url": "https://cdn.example.com/avatar.mp4"},
            }

    monkeypatch.setattr(uploads, "provider_router", FakeProviderRouter())

    upload = UserUpload(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        tool_type="ai_avatar",
        original_filename="headshot.jpg",
        file_url="https://cdn.example.com/headshot.jpg",
        status=UploadStatus.PROCESSING,
        credits_used=40,
    )
    db = FakeDb()

    await uploads._trigger_generation(
        upload=upload,
        file_url="https://cdn.example.com/headshot.jpg",
        tool_type="ai_avatar",
        model_id="default",
        prompt="This should become spoken avatar script.",
        db=db,
    )

    assert captured["task_type"] == TaskType.AVATAR
    assert captured["params"]["script"] == "This should become spoken avatar script."
    assert captured["params"]["text"] == "This should become spoken avatar script."
    assert captured["params"]["language"] == "en"
    assert upload.status == UploadStatus.COMPLETED
    assert upload.result_video_url == "https://cdn.example.com/avatar.mp4"
    assert db.commits == 1


# test_upload_video_transform_uses_local_fallback_when_provider_fails removed
# 2026-05-31 — V2V dropped repo-wide (TaskType.V2V no longer exists,
# _run_ffmpeg_video_transform helper deleted, video_transform tool_type
# branch removed from uploads._trigger_generation).


async def test_upload_generation_scheduler_detaches_from_response(monkeypatch: pytest.MonkeyPatch) -> None:
    started = asyncio.Event()
    completed = asyncio.Event()

    async def fake_background_generation(*args: Any) -> None:
        started.set()
        await asyncio.sleep(0)
        completed.set()

    class FakeBackgroundTasks:
        def add_task(self, *args: Any, **kwargs: Any) -> None:
            raise AssertionError("FastAPI BackgroundTasks should not be used when an event loop is running")

    monkeypatch.setattr(uploads, "_trigger_generation_background", fake_background_generation)

    uploads._schedule_generation_task(
        FakeBackgroundTasks(),
        "00000000-0000-0000-0000-000000000001",
        "https://cdn.example.com/input.jpg",
        "short_video",
        "pixverse_v4.5",
        "cinematic motion",
        {"subscription_credits": 30, "purchased_credits": 0, "bonus_credits": 0},
    )

    await asyncio.wait_for(started.wait(), timeout=1)
    await asyncio.wait_for(completed.wait(), timeout=1)