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
from app.providers.provider_router import ProviderRouter, TaskType


class TestProviderRouterModelAwareRouting:
    def test_i2v_pollo_models_prefer_pollo_rest(self):
        router = ProviderRouter.__new__(ProviderRouter)

        providers = router._get_providers_for_task(
            TaskType.I2V,
            {"model": "pixverse_v4.5"},
        )

        assert providers == ["piapi", "pollo", "pollo_mcp", "vertex_ai"]

    def test_i2v_without_pollo_model_keeps_default_chain(self):
        router = ProviderRouter.__new__(ProviderRouter)

        providers = router._get_providers_for_task(
            TaskType.I2V,
            {},
        )

        assert providers == ["piapi", "pollo_mcp", "vertex_ai"]


@pytest.mark.asyncio
async def test_route_alerts_on_piapi_failure_and_uses_pollo_backup(monkeypatch):
    router = ProviderRouter.__new__(ProviderRouter)
    router._failure_counts = {}
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
async def test_check_provider_health_alerts_when_provider_is_unhealthy(monkeypatch):
    router = ProviderRouter.__new__(ProviderRouter)
    router._status_cache = {}
    router._last_health_check = {}
    router._failure_counts = {}
    router._last_provider_alert = {}
    router._provider_alert_cooldown = timedelta(minutes=15)
    router.pollo = types.SimpleNamespace(health_check=AsyncMock(return_value=False))
    router.pollo_mcp = types.SimpleNamespace(health_check=AsyncMock(return_value=True))
    router.piapi = types.SimpleNamespace(health_check=AsyncMock(return_value=True))
    router.piapi_mcp = types.SimpleNamespace(health_check=AsyncMock(return_value=True))
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