
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.api.deps import get_db

# Mark all tests as async
pytestmark = pytest.mark.asyncio

# Mock DB Session
async def override_get_db():
    mock_session = AsyncMock()
    # Mock execute result for scalar_one_or_none
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result
    yield mock_session

# Apply override
app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
async def mock_startup():
    """Mock startup validation to avoid DB calls"""
    with patch("app.main.validate_materials_on_startup", new_callable=AsyncMock) as mock_val:
        mock_val.return_value = {"all_ready": True, "missing": []}
        yield mock_val

async def test_health_check(mock_startup):
    """Verify health endpoint returns correct mode"""
    # Use ASGITransport to avoid lifespan issues if possible, or just rely on mocks
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "preset-only"

async def test_get_presets_background_removal():
    """Verify getting presets returns structure"""
    # Mock MaterialLookupService inside the endpoint
    with patch("app.services.material_lookup.get_material_lookup_service") as mock_service_factory:
        mock_service = AsyncMock()
        mock_service.get_presets_for_tool.return_value = [] # Return empty list for safety
        mock_service_factory.return_value = mock_service
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v1/demo/presets/background_removal")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

async def test_get_presets_includes_input_params():
    """Verify presets response includes parameters for frontend matching"""
    with patch("app.services.material_lookup.get_material_lookup_service") as mock_service_factory:
        mock_service = AsyncMock()
        
        # Mock a material-like object
        class MockMaterial:
            id = "123"
            prompt = "test"
            prompt_zh = "test_zh"
            input_image_url = None
            input_video_url = None
            result_image_url = "http://img"
            result_video_url = None
            result_watermarked_url = "http://wm"
            result_thumbnail_url = None
            topic = "test"
            tags = []
            input_params = {"avatar_id": "female-1", "script_id": "welcome"}
            
        mock_service.get_presets_for_tool.return_value = [MockMaterial()]
        mock_service_factory.return_value = mock_service
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v1/demo/presets/ai_avatar")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["presets"]) == 1
        assert "input_params" in data["presets"][0]
        assert data["presets"][0]["input_params"]["avatar_id"] == "female-1"

async def test_download_blocked():
    """Verify download endpoint is blocked"""
    fake_id = "00000000-0000-0000-0000-000000000000"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(f"/api/v1/demo/download/{fake_id}")
    
    assert response.status_code == 403
    data = response.json()
    assert data["detail"]["error"] == "download_blocked"
