#!/usr/bin/env python3
"""
VidGo AI — Deep Tool Validation
Per tool: call endpoint, wait for output, download result, verify it's a real
image/video (not an error placeholder), report dimensions/size/content-type.
"""
import asyncio
import io
import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from PIL import Image

BACKEND = os.environ.get("VIDGO_BACKEND", "https://vidgo-backend-38714015566.asia-east1.run.app")
EMAIL = os.environ["VIDGO_EMAIL"]
PASSWORD = os.environ["VIDGO_PASSWORD"]

TEST_IMAGES = {
    "product":  "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=768",
    "garment":  "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=768",
    "room":     "https://images.unsplash.com/photo-1554995207-c18c203602cb?w=800",
    "portrait": "https://images.unsplash.com/photo-1615262239828-a4d49e6503ea?w=512",
    "food":     "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=768",
}


@dataclass
class ToolReport:
    tool: str
    ok: bool = False
    endpoint: str = ""
    api_ms: float = 0
    success_flag: Any = None
    result_url: str = ""
    credits_used: int = 0
    error: str = ""
    # Output validation
    download_ok: bool = False
    download_bytes: int = 0
    content_type: str = ""
    width: int = 0
    height: int = 0
    is_video: bool = False
    sanity: str = ""  # "looks good" / specific problem
    raw_response: dict = field(default_factory=dict)


async def login(client: httpx.AsyncClient) -> tuple[str, dict]:
    r = await client.post(f"{BACKEND}/api/v1/auth/login",
                          json={"email": EMAIL, "password": PASSWORD})
    r.raise_for_status()
    d = r.json()
    return d["tokens"]["access"], d.get("user", {})


async def upload(client: httpx.AsyncClient, token: str, source_url: str) -> str:
    img = await client.get(source_url, follow_redirects=True)
    img.raise_for_status()
    suffix = ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(img.content)
        path = f.name
    try:
        with open(path, "rb") as fh:
            up = await client.post(
                f"{BACKEND}/api/v1/demo/upload",
                files={"file": (f"src{suffix}", fh, "image/jpeg")},
                headers={"Authorization": f"Bearer {token}"},
            )
        up.raise_for_status()
        d = up.json()
        return d.get("url") or d.get("file_url") or source_url
    finally:
        os.unlink(path)


async def validate_output(client: httpx.AsyncClient, url: str, expect_video: bool = False) -> dict:
    """Download the result URL and inspect what it actually is."""
    out = {"download_ok": False, "bytes": 0, "content_type": "",
           "width": 0, "height": 0, "is_video": False, "sanity": ""}
    if not url:
        out["sanity"] = "no URL returned"
        return out
    try:
        r = await client.get(url, follow_redirects=True, timeout=60)
    except Exception as e:
        out["sanity"] = f"download failed: {e}"
        return out
    if r.status_code != 200:
        out["sanity"] = f"HTTP {r.status_code} from result URL"
        return out
    ct = r.headers.get("content-type", "").lower()
    out["content_type"] = ct
    out["bytes"] = len(r.content)
    out["download_ok"] = True
    if "video" in ct or url.lower().endswith((".mp4", ".mov", ".webm")):
        out["is_video"] = True
        if out["bytes"] < 10_000:
            out["sanity"] = f"video too small ({out['bytes']} B) — likely a stub"
        else:
            out["sanity"] = "video present"
        return out
    if "image" in ct or url.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        try:
            im = Image.open(io.BytesIO(r.content))
            im.load()
            out["width"], out["height"] = im.size
            if im.width < 64 or im.height < 64:
                out["sanity"] = f"suspiciously small image {im.size}"
            elif out["bytes"] < 2_000:
                out["sanity"] = f"image body tiny ({out['bytes']} B) — probably placeholder"
            else:
                out["sanity"] = "image decoded OK"
        except Exception as e:
            out["sanity"] = f"image decode failed: {e}"
        return out
    # If expecting video but got something else
    if expect_video:
        out["sanity"] = f"expected video, got {ct} ({out['bytes']} B)"
    else:
        out["sanity"] = f"unrecognised content-type {ct!r}"
    return out


def _extract_result_url(data: dict, *, video: bool = False) -> str:
    if not isinstance(data, dict):
        return ""
    for k in ("video_url", "output_url", "result_url", "image_url", "url"):
        v = data.get(k)
        if isinstance(v, str) and v:
            return v
    # nested
    for k in ("result", "data", "output"):
        sub = data.get(k)
        if isinstance(sub, dict):
            nested = _extract_result_url(sub, video=video)
            if nested:
                return nested
    return ""


async def call_tool(client: httpx.AsyncClient, token: str,
                    report: ToolReport, endpoint: str, body: dict,
                    expect_video: bool = False) -> None:
    report.endpoint = endpoint
    t0 = time.time()
    try:
        r = await client.post(
            f"{BACKEND}{endpoint}", json=body,
            headers={"Authorization": f"Bearer {token}"},
            timeout=300,
        )
    except Exception as e:
        report.error = f"request failed: {e}"
        return
    report.api_ms = (time.time() - t0) * 1000
    try:
        data = r.json()
    except Exception:
        report.error = f"HTTP {r.status_code}: non-JSON body ({len(r.content)} B)"
        return
    report.raw_response = {k: v for k, v in data.items()
                           if k in ("success", "message", "detail", "credits_used",
                                    "error", "is_demo", "status", "task_id")}
    report.success_flag = data.get("success")
    report.credits_used = data.get("credits_used", 0) or 0
    report.result_url = _extract_result_url(data, video=expect_video)
    if r.status_code >= 400 or report.success_flag is False:
        report.error = (data.get("message") or data.get("detail")
                        or data.get("error") or f"HTTP {r.status_code}")
        return
    if not report.result_url:
        report.error = "success=true but no URL in response"
        return
    v = await validate_output(client, report.result_url, expect_video=expect_video)
    report.download_ok = v["download_ok"]
    report.download_bytes = v["bytes"]
    report.content_type = v["content_type"]
    report.width = v["width"]
    report.height = v["height"]
    report.is_video = v["is_video"]
    report.sanity = v["sanity"]
    report.ok = v["download_ok"] and "OK" in v["sanity"] or "present" in v["sanity"] or v["sanity"] == "image decoded OK"


async def run():
    reports: list[ToolReport] = []
    async with httpx.AsyncClient(timeout=300) as client:
        token, user = await login(client)
        print(f"Logged in as plan={user.get('plan_type')} superuser={user.get('is_superuser')}")

        bal = await client.get(f"{BACKEND}/api/v1/credits/balance",
                               headers={"Authorization": f"Bearer {token}"})
        credits_before = bal.json().get("total", 0)
        print(f"Credits before: {credits_before}")

        # Pre-upload common images (so we get stable server URLs)
        print("Uploading source fixtures…")
        uploaded = {}
        for k, src in TEST_IMAGES.items():
            try:
                uploaded[k] = await upload(client, token, src)
                print(f"  {k}: {uploaded[k][:80]}")
            except Exception as e:
                uploaded[k] = src
                print(f"  {k}: upload failed ({e}), using direct URL")

        # --- Definition of tests ---
        tests = [
            ("BG Removal", "/api/v1/tools/remove-bg",
             {"image_url": uploaded["product"], "output_format": "png"}, False),
            ("Product Scene", "/api/v1/tools/product-scene",
             {"product_image_url": uploaded["product"], "scene_type": "nature"}, False),
            ("Try-On", "/api/v1/tools/try-on",
             {"garment_image_url": uploaded["garment"], "model_id": "female-2"}, False),
            ("Room Redesign", "/api/v1/tools/room-redesign",
             {"room_image_url": uploaded["room"], "style": "scandinavian"}, False),
            ("Effects (anime)", "/api/v1/effects/apply-style",
             {"image_url": uploaded["food"], "style_id": "anime", "intensity": 0.8}, False),
            ("Image Transform", "/api/v1/tools/image-transform",
             {"image_url": uploaded["food"],
              "prompt": "watercolor painting style, soft colors, artistic",
              "strength": 0.7}, False),
            ("Upscale", "/api/v1/tools/upscale",
             {"image_url": uploaded["product"], "scale": 2}, False),
            ("HD Enhance", "/api/v1/effects/hd-enhance",
             {"image_url": uploaded["product"]}, False),
            ("Short Video", "/api/v1/tools/short-video",
             {"image_url": uploaded["product"], "motion_strength": 5}, True),
            ("AI Avatar", "/api/v1/tools/avatar",
             {"image_url": uploaded["portrait"],
              "script": "Hello everyone. Welcome to VidGo AI. We help businesses make product photos and videos with AI."},
             True),
        ]

        for name, path, body, expect_video in tests:
            print(f"\n=== {name} ===")
            rep = ToolReport(tool=name)
            await call_tool(client, token, rep, path, body, expect_video=expect_video)
            reports.append(rep)
            if rep.error:
                print(f"  ✗ error: {rep.error}")
            else:
                kind = "video" if rep.is_video else f"image {rep.width}x{rep.height}"
                print(f"  ✓ {kind}  {rep.download_bytes} B  {rep.content_type}")
                print(f"  sanity: {rep.sanity}")
                print(f"  credits_used={rep.credits_used}  api_ms={rep.api_ms:.0f}")

        # Re-login — long tests may drift credits/token
        try:
            token, _ = await login(client)
            bal = await client.get(f"{BACKEND}/api/v1/credits/balance",
                                   headers={"Authorization": f"Bearer {token}"})
            credits_after = bal.json().get("total", 0)
            print(f"\nCredits after: {credits_after} (delta {credits_before - credits_after})")
        except Exception as e:
            print(f"\nCredit re-check failed: {e}")
            credits_after = None

    # --- Summary table ---
    print("\n" + "=" * 78)
    print(f"{'Tool':<20} {'API ms':>7} {'Bytes':>10} {'W×H':>10} {'Credits':>8}  Sanity")
    print("-" * 78)
    for r in reports:
        wh = f"{r.width}×{r.height}" if r.width else ("video" if r.is_video else "-")
        s = r.sanity if not r.error else f"ERR: {r.error[:40]}"
        print(f"{r.tool:<20} {r.api_ms:>7.0f} {r.download_bytes:>10} {wh:>10} {r.credits_used:>8}  {s}")
    print("=" * 78)

    passed = sum(1 for r in reports if r.ok)
    print(f"Passed: {passed}/{len(reports)}")
    # emit JSON for programmatic consumption
    out_path = "/tmp/deep_tool_report.json"
    with open(out_path, "w") as f:
        json.dump([r.__dict__ for r in reports], f, indent=2, default=str)
    print(f"Full JSON: {out_path}")
    return 0 if passed == len(reports) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
