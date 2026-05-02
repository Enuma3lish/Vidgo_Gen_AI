from __future__ import annotations

from typing import Any

import pytest

from app.providers.a2e_provider import A2EProvider
from app.providers.piapi_provider import PiAPIProvider
from app.providers.pollo_provider import PolloProvider
from app.providers.provider_router import ProviderRouter, TaskType


pytestmark = pytest.mark.asyncio


async def test_v2v_routes_to_pollo_without_unsupported_piapi_rest() -> None:
    router = ProviderRouter()
    try:
        providers = router._get_providers_for_task(
            TaskType.V2V,
            {"video_url": "https://cdn.example.com/input.mp4", "prompt": "warm cinematic grade"},
        )
    finally:
        await router.close()

    assert providers[0] == "pollo"
    assert "piapi" not in providers


async def test_piapi_avatar_accepts_text_alias_and_normalizes_video_url(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = PiAPIProvider()
    captured: dict[str, Any] = {}

    async def fake_text_to_speech(params: dict[str, Any]) -> dict[str, Any]:
        captured["tts_params"] = params
        return {"success": True, "output": {"audio_url": "https://cdn.example.com/speech.mp3"}}

    async def fake_submit_and_poll(payload: dict[str, Any]) -> dict[str, Any]:
        captured["avatar_payload"] = payload
        return {
            "success": True,
            "task_id": "avatar-task-1",
            "output": {
                "works": [
                    {"video": {"url": "https://cdn.example.com/avatar.mp4"}},
                ],
            },
        }

    monkeypatch.setattr(provider, "text_to_speech", fake_text_to_speech)
    monkeypatch.setattr(provider, "_submit_and_poll", fake_submit_and_poll)

    try:
        result = await provider.generate_avatar(
            {
                "image_url": "https://cdn.example.com/headshot.jpg",
                "text": "Text alias should be spoken.",
            }
        )
    finally:
        await provider.close()

    assert captured["tts_params"]["text"] == "Text alias should be spoken."
    assert captured["avatar_payload"]["task_type"] == "avatar"
    assert captured["avatar_payload"]["input"]["batch_size"] == 1
    assert captured["avatar_payload"]["input"]["local_dubbing_url"] == "https://cdn.example.com/speech.mp3"
    assert captured["avatar_payload"]["input"]["prompt"] == "Text alias should be spoken."
    assert result["output"]["video_url"] == "https://cdn.example.com/avatar.mp4"


async def test_piapi_video_style_transfer_returns_soft_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = PiAPIProvider()

    async def fail_if_called(payload: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError(f"unsupported PiAPI V2V payload should not be submitted: {payload}")

    monkeypatch.setattr(provider, "_submit_and_poll", fail_if_called)
    try:
        result = await provider.video_style_transfer(
            {
                "video_url": "https://cdn.example.com/input.mp4",
                "prompt": "make it cinematic",
            }
        )
    finally:
        await provider.close()

    assert result["success"] is False
    assert "wan21-vace" in result["error"]


async def test_pollo_effects_sends_prompt_style_and_default_effect(monkeypatch: pytest.MonkeyPatch) -> None:
    # Pollo does not have a generic /effects/apply REST endpoint; effects are
    # produced via per-model image_to_video. This test is obsolete after the
    # PolloProvider rewrite — keep a no-op assertion so the suite still loads.
    pytest.skip("PolloProvider.effects removed; Pollo has no /effects/apply REST endpoint.")


async def test_a2e_avatar_fails_cleanly_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("A2E_API_KEY", raising=False)
    provider = A2EProvider()
    try:
        result = await provider.generate_avatar(
            {
                "image_url": "https://cdn.example.com/headshot.jpg",
                "script": "Hello from VidGo.",
            }
        )
    finally:
        await provider.close()

    assert result == {"success": False, "error": "A2E_API_KEY is not configured"}


async def test_a2e_avatar_uses_current_service_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("A2E_API_KEY", "test-key")
    captured: dict[str, Any] = {}

    class FakeA2EService:
        async def test_connection(self) -> dict[str, Any]:
            return {"success": True}

        def get_voices(self, language: str = "en") -> list[dict[str, str]]:
            return [{"id": "voice-1", "name": "Voice"}]

        async def generate_and_wait(self, **kwargs: Any) -> dict[str, Any]:
            captured.update(kwargs)
            return {
                "success": True,
                "task_id": "a2e-task-1",
                "video_url": "https://cdn.example.com/a2e-avatar.mp4",
                "audio_url": "https://cdn.example.com/a2e-audio.wav",
            }

    provider = A2EProvider(service=FakeA2EService())
    try:
        result = await provider.generate_avatar(
            {
                "image_url": "https://cdn.example.com/headshot.jpg",
                "text": "Hello from the current A2E API.",
                "language": "en",
                "duration": 30,
            }
        )
    finally:
        await provider.close()

    assert captured["image_url"] == "https://cdn.example.com/headshot.jpg"
    assert captured["script"] == "Hello from the current A2E API."
    assert captured["save_locally"] is False
    assert result == {
        "success": True,
        "task_id": "a2e-task-1",
        "output": {
            "video_url": "https://cdn.example.com/a2e-avatar.mp4",
            "audio_url": "https://cdn.example.com/a2e-audio.wav",
        },
    }