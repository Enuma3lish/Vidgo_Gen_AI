from __future__ import annotations

from typing import Any

import pytest

from app.providers.a2e_provider import A2EProvider
from app.providers.piapi_provider import PiAPIProvider
from app.providers.pollo_provider import PolloProvider
from app.providers.provider_router import ProviderRouter, TaskType


pytestmark = pytest.mark.asyncio


# test_v2v_routes_to_piapi_rest_then_vertex removed 2026-05-31 — V2V dropped.


async def test_piapi_avatar_accepts_text_alias_and_normalizes_video_url(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = PiAPIProvider()
    captured: dict[str, Any] = {}

    async def fake_text_to_speech(params: dict[str, Any]) -> dict[str, Any]:
        captured["tts_params"] = params
        return {"success": True, "output": {"audio_url": "https://cdn.example.com/speech.mp3"}}

    async def fake_submit_and_poll(payload: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
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
    # BUG-005: the spoken script must NOT leak into Kling's visual `prompt`
    # (that rendered the words as on-screen captions). The script reaches Kling
    # via local_dubbing_url (asserted above); `prompt` is a clean talking-head
    # visual brief that explicitly forbids on-screen text.
    assert "Text alias should be spoken." not in captured["avatar_payload"]["input"]["prompt"]
    assert "no text" in captured["avatar_payload"]["input"]["prompt"].lower()
    assert result["output"]["video_url"] == "https://cdn.example.com/avatar.mp4"


# test_piapi_video_style_transfer_returns_soft_failure removed 2026-05-31 —
# V2V dropped repo-wide (piapi_provider.video_style_transfer no longer exists).


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