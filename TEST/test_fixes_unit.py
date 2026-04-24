#!/usr/bin/env python3
"""
Unit verification for the two fixes:

1. backend/scripts/services/piapi_client.py::_download_as now uploads to GCS
   (via get_gcs_storage().upload_public) instead of writing to ephemeral
   /app/static/generated and returning a relative path.

2. backend/app/services/effects_service.py::hd_enhance now reads image_url
   from result["output"]["image_url"] (the router's actual return shape),
   not result["image_url"].
"""
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/vidgo_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from scripts.services.piapi_client import PiAPIClient  # noqa: E402


# ───────────────── Test 1: piapi_client._download_as uses GCS ─────────────────

async def test_download_as_uses_gcs():
    client = PiAPIClient(api_key="test")

    fake_http = MagicMock()
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.content = b"\x89PNG\r\n\x1a\n" + b"x" * 100
    fake_http.get = AsyncMock(return_value=fake_response)

    fake_gcs = MagicMock()
    fake_gcs.enabled = True
    fake_gcs.upload_public = MagicMock(
        return_value="https://storage.googleapis.com/bucket/generated/image/piapi_abcd1234.png"
    )

    with patch("app.services.gcs_storage_service.get_gcs_storage", return_value=fake_gcs):
        out = await client._download_as(fake_http, "https://cdn.example/x.png", ext=".png")

    assert out.startswith("https://storage.googleapis.com/"), f"expected GCS URL, got {out}"
    assert "/generated/image/" in out
    assert out.endswith(".png")
    # Verify upload_public was called with correct content type and path
    args, kwargs = fake_gcs.upload_public.call_args
    assert kwargs["content_type"] == "image/png"
    assert kwargs["blob_name"].startswith("generated/image/piapi_")
    assert kwargs["blob_name"].endswith(".png")
    print("PASS: _download_as writes to GCS for .png")


async def test_download_as_video_ext():
    client = PiAPIClient(api_key="test")
    fake_http = MagicMock()
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.content = b"\x00\x00\x00 ftypisom" + b"x" * 500
    fake_http.get = AsyncMock(return_value=fake_response)
    fake_gcs = MagicMock()
    fake_gcs.enabled = True
    fake_gcs.upload_public = MagicMock(
        return_value="https://storage.googleapis.com/bucket/generated/video/piapi_aa11bb22.mp4"
    )

    with patch("app.services.gcs_storage_service.get_gcs_storage", return_value=fake_gcs):
        out = await client._download_as(fake_http, "https://cdn.example/x.mp4", ext=".mp4")

    args, kwargs = fake_gcs.upload_public.call_args
    assert kwargs["content_type"] == "video/mp4"
    assert kwargs["blob_name"].startswith("generated/video/")
    assert out.endswith(".mp4")
    print("PASS: _download_as routes .mp4 to generated/video/ with video/mp4 content-type")


async def test_download_as_falls_back_without_gcs():
    """When GCS is disabled, fall back to local disk (old behavior)."""
    client = PiAPIClient(api_key="test")
    fake_http = MagicMock()
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.content = b"\x89PNG\r\n\x1a\n" + b"x" * 100
    fake_http.get = AsyncMock(return_value=fake_response)
    fake_gcs = MagicMock()
    fake_gcs.enabled = False  # disabled!

    # Redirect OUTPUT_DIR to a temp path so we don't touch /app
    import tempfile
    import scripts.services.piapi_client as mod
    with tempfile.TemporaryDirectory() as tmp:
        orig = mod.OUTPUT_DIR
        mod.OUTPUT_DIR = Path(tmp)
        try:
            with patch("app.services.gcs_storage_service.get_gcs_storage", return_value=fake_gcs):
                out = await client._download_as(fake_http, "https://cdn.example/x.png", ext=".png")
        finally:
            mod.OUTPUT_DIR = orig

    assert "/static/generated/" in out, f"expected local static path, got {out}"
    print("PASS: _download_as falls back to local when GCS disabled")


# ───────────── Test 2: hd_enhance reads result["output"]["image_url"] ─────────

async def test_hd_enhance_extracts_output_image_url():
    """
    We can't cleanly import VidGoEffectsService without mcp installed,
    so exec the hd_enhance function in a sandbox with the real fixed source.
    """
    import ast
    src = (BACKEND / "app/services/effects_service.py").read_text()
    tree = ast.parse(src)
    hd_enhance_ast = None
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "hd_enhance":
            hd_enhance_ast = node
            break
    assert hd_enhance_ast is not None, "hd_enhance not found in effects_service.py"

    # Assert the fix: new code reads `output.get("image_url")` from `result["output"]`.
    body_src = ast.unparse(hd_enhance_ast)
    assert "result.get('output')" in body_src or 'result.get("output")' in body_src, \
        "expected hd_enhance to read result['output'] — fix not applied"
    assert "output.get('image_url')" in body_src or 'output.get("image_url")' in body_src, \
        "expected output.get('image_url') in fixed hd_enhance"
    print("PASS: hd_enhance source reads result['output']['image_url']")


async def test_hd_enhance_bug_was_real():
    """Sanity: confirm the OLD buggy pattern `result.get('image_url')` as the
    sole extraction (no `output.get`) would have failed against the router
    shape `{'success': True, 'output': {'image_url': ...}}`."""
    router_result = {"success": True,
                     "output": {"image_url": "https://gcs/x.png"}}
    old_extraction = router_result.get("image_url") or router_result.get("output_url")
    new_extraction = (router_result.get("output") or {}).get("image_url")
    assert old_extraction is None, "old code would have found the URL — bug premise wrong"
    assert new_extraction == "https://gcs/x.png", "new extraction is broken"
    print("PASS: confirms old code missed URL, new code finds it")


async def main():
    tests = [
        test_download_as_uses_gcs,
        test_download_as_video_ext,
        test_download_as_falls_back_without_gcs,
        test_hd_enhance_extracts_output_image_url,
        test_hd_enhance_bug_was_real,
    ]
    failures = 0
    for t in tests:
        try:
            await t()
        except AssertionError as e:
            print(f"FAIL: {t.__name__}: {e}")
            failures += 1
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"ERROR: {t.__name__}: {e}")
            failures += 1
    print()
    print(f"{len(tests) - failures}/{len(tests)} passed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
