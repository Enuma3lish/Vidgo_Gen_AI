import sys
import types
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest


mcp_module = types.ModuleType("mcp")
mcp_module.ClientSession = object
mcp_module.StdioServerParameters = object

mcp_client_module = types.ModuleType("mcp.client")
mcp_stdio_module = types.ModuleType("mcp.client.stdio")


async def _unused_stdio_client(*args, **kwargs):
    raise RuntimeError("stdio_client should not be used in provider router unit tests")


mcp_stdio_module.stdio_client = _unused_stdio_client

sys.modules.setdefault("mcp", mcp_module)
sys.modules.setdefault("mcp.client", mcp_client_module)
sys.modules.setdefault("mcp.client.stdio", mcp_stdio_module)

import app.providers.provider_router as provider_router_module
from app.providers.provider_router import ProviderRouter, ProviderStatus, TaskType


class TestProviderRouterModelAwareRouting:
    def test_i2v_pollo_models_prefer_pollo_rest(self):
        router = ProviderRouter.__new__(ProviderRouter)

        providers = router._get_providers_for_task(
            TaskType.I2V,
            {"model": "pixverse_v4.5"},
        )

        # 2026-06-23: Pollo replaced Vertex AI as the generation backup (Vertex
        # now only serves moderation/material + Veo). For a Pollo-native video
        # model the chain is Pollo REST → PiAPI REST; Vertex is no longer in it.
        assert providers == ["pollo", "piapi"]

    def test_i2v_without_model_uses_piapi_then_pollo_chain(self):
        router = ProviderRouter.__new__(ProviderRouter)

        providers = router._get_providers_for_task(
            TaskType.I2V,
            {},
        )

        # 2026-06-23: ROUTING_CONFIG[I2V] is {primary: piapi, backup: pollo}.
        # Vertex AI was dropped from the generation chain (it only serves Veo /
        # moderation / material now), so the default I2V chain is PiAPI → Pollo.
        assert providers == ["piapi", "pollo"]

    def test_avatar_uses_piapi_then_a2e(self):
        router = ProviderRouter.__new__(ProviderRouter)

        providers = router._get_providers_for_task(
            TaskType.AVATAR,
            {"image_url": "https://example.com/avatar.jpg", "text": "hello"},
        )

        assert providers == ["piapi", "a2e"]

    def test_3d_uses_piapi_rest_only(self):
        router = ProviderRouter.__new__(ProviderRouter)

        providers = router._get_providers_for_task(
            TaskType.INTERIOR_3D,
            {"image_url": "https://example.com/floor-plan.jpg"},
        )

        assert providers == ["piapi"]

    def test_explicit_non_pollo_model_uses_piapi_rest_first(self):
        router = ProviderRouter.__new__(ProviderRouter)

        providers = router._get_providers_for_task(
            TaskType.T2I,
            {"prompt": "studio product shot", "model": "flux-dev"},
        )

        # 2026-06-23: ROUTING_CONFIG[T2I] is {primary: piapi, backup: pollo}.
        # An explicit non-Pollo model still runs PiAPI first, then the configured
        # backup (Pollo). Vertex AI is no longer in the image chain.
        assert providers == ["piapi", "pollo"]


@pytest.mark.asyncio
async def test_route_alerts_on_piapi_failure_and_uses_pollo_backup(monkeypatch):
    router = ProviderRouter.__new__(ProviderRouter)
    router._failure_counts = {}
    router._tier_warn_seen = set()  # set by __init__ (bypassed via __new__); route() reads it
    # Make provider availability env-independent: these tests exercise circuit /
    # backup routing, not API-key config. Without this stub the result depends on
    # whether PIAPI_KEY/POLLO_API_KEY happen to be in the environment (present
    # locally via .env, absent in CI) — which made the suite pass locally but
    # fail in CI. Circuit state set up per-test is the only availability lever.
    router._is_provider_disabled_by_config = lambda provider: False
    router._status_cache = {}
    router._last_health_check = {}
    router._last_provider_alert = {}
    router._provider_alert_cooldown = timedelta(minutes=15)
    router._get_providers_for_task = lambda task_type, params: ["piapi", "pollo", "vertex_ai"]
    router._record_success = lambda provider: None
    router._record_failure = lambda provider, error: None
    router._absolutize_local_media_urls = lambda result: result
    router._persist_result_to_gcs = AsyncMock(side_effect=lambda result, task_type: result)

    async def fake_execute(provider_name, task_type, params):
        if provider_name == "piapi":
            raise Exception("PiAPI internal error: HTTP 500")
        return {"success": True, "output": {"image_url": "https://example.com/image.png"}}

    router._execute_on_provider = fake_execute

    email_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(
        provider_router_module,
        "email_service",
        types.SimpleNamespace(send_provider_failure_alert=email_mock),
    )

    result = await ProviderRouter.route(
        router,
        TaskType.T2I,
        {"prompt": "studio product shot", "model": "flux"},
        persist_to_gcs=False,
    )

    assert result["provider_used"] == "pollo"
    email_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_route_rate_limits_duplicate_piapi_alerts(monkeypatch):
    router = ProviderRouter.__new__(ProviderRouter)
    router._provider_alert_cooldown = timedelta(minutes=15)
    router._last_provider_alert = {"piapi": datetime.now()}

    email_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(
        provider_router_module,
        "email_service",
        types.SimpleNamespace(send_provider_failure_alert=email_mock),
    )

    await ProviderRouter._maybe_alert_provider_failure(
        router,
        provider_name="piapi",
        task_type=TaskType.T2I,
        error="PiAPI internal error: HTTP 500",
        fallback_provider="pollo",
        request_params={"prompt": "test"},
    )

    email_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_alerts_on_pollo_credit_failure(monkeypatch):
    router = ProviderRouter.__new__(ProviderRouter)
    router._failure_counts = {}
    router._tier_warn_seen = set()  # set by __init__ (bypassed via __new__); route() reads it
    # Make provider availability env-independent: these tests exercise circuit /
    # backup routing, not API-key config. Without this stub the result depends on
    # whether PIAPI_KEY/POLLO_API_KEY happen to be in the environment (present
    # locally via .env, absent in CI) — which made the suite pass locally but
    # fail in CI. Circuit state set up per-test is the only availability lever.
    router._is_provider_disabled_by_config = lambda provider: False
    router._status_cache = {}
    router._last_health_check = {}
    router._last_provider_alert = {}
    router._provider_alert_cooldown = timedelta(minutes=15)
    router._get_providers_for_task = lambda task_type, params: ["pollo", "vertex_ai"]
    router._record_success = lambda provider: None
    router._record_failure = lambda provider, error: None
    router._absolutize_local_media_urls = lambda result: result
    router._persist_result_to_gcs = AsyncMock(side_effect=lambda result, task_type: result)

    async def fake_execute(provider_name, task_type, params):
        if provider_name == "pollo":
            raise Exception("Pollo credits exhausted: balance is zero")
        return {"success": True, "output": {"video_url": "https://example.com/video.mp4"}}

    router._execute_on_provider = fake_execute

    email_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(
        provider_router_module,
        "email_service",
        types.SimpleNamespace(send_provider_failure_alert=email_mock),
    )

    result = await ProviderRouter.route(
        router,
        TaskType.T2V,
        {"prompt": "launch animation"},
        persist_to_gcs=False,
    )

    assert result["provider_used"] == "vertex_ai"
    email_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_route_skips_provider_with_open_circuit():
    router = ProviderRouter.__new__(ProviderRouter)
    router._failure_counts = {"piapi": 3}
    router._tier_warn_seen = set()  # set by __init__ (bypassed via __new__); route() reads it
    # Make provider availability env-independent: these tests exercise circuit /
    # backup routing, not API-key config. Without this stub the result depends on
    # whether PIAPI_KEY/POLLO_API_KEY happen to be in the environment (present
    # locally via .env, absent in CI) — which made the suite pass locally but
    # fail in CI. Circuit state set up per-test is the only availability lever.
    router._is_provider_disabled_by_config = lambda provider: False
    router._status_cache = {
        "piapi": {
            "status": ProviderStatus.DOWN,
            "failure_count": 3,
            "last_failure": datetime.now(),
            "circuit_open_until": datetime.now() + timedelta(minutes=3),
        }
    }
    router._last_health_check = {}
    router._last_provider_alert = {}
    router._provider_alert_cooldown = timedelta(minutes=15)
    router._get_providers_for_task = lambda task_type, params: ["piapi", "pollo"]
    router._record_success = lambda provider: None
    router._record_failure = lambda provider, error: None
    router._absolutize_local_media_urls = lambda result: result
    router._persist_result_to_gcs = AsyncMock(side_effect=lambda result, task_type: result)

    executed = []

    async def fake_execute(provider_name, task_type, params):
        executed.append(provider_name)
        return {"success": True, "output": {"image_url": "https://example.com/image.png"}}

    router._execute_on_provider = fake_execute

    result = await ProviderRouter.route(
        router,
        TaskType.T2I,
        {"prompt": "studio product shot"},
        persist_to_gcs=False,
    )

    assert executed == ["pollo"]
    assert result["provider_used"] == "pollo"
    assert result["used_backup"] is True
    assert result["skipped_providers"] == ["piapi"]


@pytest.mark.asyncio
async def test_route_fails_fast_when_all_provider_circuits_are_open():
    """When EVERY provider in the chain has an open circuit, route() fails fast
    with a user-friendly error rather than hammering providers that are all
    tripped. (Previously this test asserted a 'probe the primary anyway'
    behavior that the router no longer implements — _route_candidates returns
    no candidates when all circuits are open, and route() raises.)"""
    router = ProviderRouter.__new__(ProviderRouter)
    open_until = datetime.now() + timedelta(minutes=3)
    router._failure_counts = {"piapi": 3, "pollo": 3}
    router._tier_warn_seen = set()  # set by __init__ (bypassed via __new__); route() reads it
    # Make provider availability env-independent: these tests exercise circuit /
    # backup routing, not API-key config. Without this stub the result depends on
    # whether PIAPI_KEY/POLLO_API_KEY happen to be in the environment (present
    # locally via .env, absent in CI) — which made the suite pass locally but
    # fail in CI. Circuit state set up per-test is the only availability lever.
    router._is_provider_disabled_by_config = lambda provider: False
    router._status_cache = {
        "piapi": {"status": ProviderStatus.DOWN, "circuit_open_until": open_until},
        "pollo": {"status": ProviderStatus.DOWN, "circuit_open_until": open_until},
    }
    router._last_health_check = {}
    router._last_provider_alert = {}
    router._provider_alert_cooldown = timedelta(minutes=15)
    router._get_providers_for_task = lambda task_type, params: ["piapi", "pollo"]
    router._record_success = lambda provider: None
    router._record_failure = lambda provider, error: None
    router._absolutize_local_media_urls = lambda result: result
    router._persist_result_to_gcs = AsyncMock(side_effect=lambda result, task_type: result)

    executed = []

    async def fake_execute(provider_name, task_type, params):
        executed.append(provider_name)
        return {"success": True, "output": {"image_url": "https://example.com/image.png"}}

    router._execute_on_provider = fake_execute

    with pytest.raises(Exception):
        await ProviderRouter.route(
            router,
            TaskType.T2I,
            {"prompt": "studio product shot"},
            persist_to_gcs=False,
        )

    # No provider was actually called — all circuits were open.
    assert executed == []


def test_record_failure_opens_and_expires_provider_circuit():
    router = ProviderRouter.__new__(ProviderRouter)
    router._failure_counts = {}
    router._tier_warn_seen = set()  # set by __init__ (bypassed via __new__); route() reads it
    # Make provider availability env-independent: these tests exercise circuit /
    # backup routing, not API-key config. Without this stub the result depends on
    # whether PIAPI_KEY/POLLO_API_KEY happen to be in the environment (present
    # locally via .env, absent in CI) — which made the suite pass locally but
    # fail in CI. Circuit state set up per-test is the only availability lever.
    router._is_provider_disabled_by_config = lambda provider: False
    router._status_cache = {}
    router._provider_circuit_breaker_failures = 2
    router._provider_circuit_breaker_cooldown = timedelta(milliseconds=1)

    ProviderRouter._record_failure(router, "piapi", "HTTP 500")
    assert ProviderRouter._is_provider_circuit_open(router, "piapi") is False

    ProviderRouter._record_failure(router, "piapi", "HTTP 500")
    assert ProviderRouter._is_provider_circuit_open(router, "piapi") is True

    router._status_cache["piapi"]["circuit_open_until"] = datetime.now() - timedelta(seconds=1)
    assert ProviderRouter._is_provider_circuit_open(router, "piapi") is False


@pytest.mark.asyncio
async def test_check_provider_health_alerts_when_provider_is_unhealthy(monkeypatch):
    router = ProviderRouter.__new__(ProviderRouter)
    router._status_cache = {}
    router._last_health_check = {}
    router._failure_counts = {}
    router._tier_warn_seen = set()  # set by __init__ (bypassed via __new__); route() reads it
    # Make provider availability env-independent: these tests exercise circuit /
    # backup routing, not API-key config. Without this stub the result depends on
    # whether PIAPI_KEY/POLLO_API_KEY happen to be in the environment (present
    # locally via .env, absent in CI) — which made the suite pass locally but
    # fail in CI. Circuit state set up per-test is the only availability lever.
    router._is_provider_disabled_by_config = lambda provider: False
    router._last_provider_alert = {}
    router._provider_alert_cooldown = timedelta(minutes=15)
    router.pollo = types.SimpleNamespace(health_check=AsyncMock(return_value=False))
    router.piapi = types.SimpleNamespace(health_check=AsyncMock(return_value=True))
    router.vertex_ai = types.SimpleNamespace(health_check=AsyncMock(return_value=True))
    router.a2e = types.SimpleNamespace(health_check=AsyncMock(return_value=True))

    email_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(
        provider_router_module,
        "email_service",
        types.SimpleNamespace(send_provider_failure_alert=email_mock),
    )

    is_healthy = await ProviderRouter._check_provider_health(router, "pollo")

    assert is_healthy is False
    email_mock.assert_awaited_once()