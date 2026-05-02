#!/usr/bin/env python3
"""VidGo direct API E2E spot checks.

This complements e2e_upload_api_download_all_tools.py by exercising direct JSON
endpoints that are not represented by /api/v1/uploads/material. Each successful
case downloads the returned media/model URL and validates the bytes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx


BACKEND = os.getenv("VIDGO_BACKEND_URL", "https://vidgo-backend-r2laip67ma-de.a.run.app").rstrip("/")
EMAIL = os.getenv("VIDGO_TEST_EMAIL", "qaz0978005418@gmail.com")
PASSWORD = os.getenv("VIDGO_TEST_PASSWORD", "qaz129946858")
API_TIMEOUT_SECONDS = float(os.getenv("VIDGO_API_TIMEOUT_SECONDS", "900"))

PRODUCT_URL = os.getenv(
    "VIDGO_TEST_PRODUCT_URL",
    "https://storage.googleapis.com/vidgo-media-vidgo-ai/generated/image/b19aa6abafe4.png",
)
PATTERN_URL = os.getenv(
    "VIDGO_TEST_PATTERN_URL",
    "https://storage.googleapis.com/vidgo-media-vidgo-ai/generated/image/4fa74c34423a.png",
)
ROOM_URL = os.getenv(
    "VIDGO_TEST_ROOM_URL",
    "https://storage.googleapis.com/vidgo-media-vidgo-ai/generated/image/3b70f8d1eb58.png",
)


@dataclass(frozen=True)
class JsonCase:
    name: str
    path: str
    body: dict[str, Any]
    media_type: str
    result_key: str
    extension: str
    timeout_seconds: float = 300.0


@dataclass
class CaseResult:
    name: str
    ok: bool
    path: str = ""
    status_code: int | None = None
    result_url: str | None = None
    download_path: str | None = None
    detail: str = ""
    seconds: float = 0.0


JSON_CASES = [
    JsonCase(
        name="upscale",
        path="/api/v1/tools/upscale",
        body={"image_url": PRODUCT_URL, "scale": 2},
        media_type="image",
        result_key="result_url",
        extension="jpg",
        timeout_seconds=300.0,
    ),
    JsonCase(
        name="image_transform",
        path="/api/v1/tools/image-transform",
        body={
            "image_url": PRODUCT_URL,
            "prompt": "clean watercolor product illustration, soft colors, commercial packshot",
            "strength": 0.55,
        },
        media_type="image",
        result_key="result_url",
        extension="jpg",
        timeout_seconds=300.0,
    ),
    JsonCase(
        name="pattern_generate_sync",
        path="/api/v1/generate/pattern/generate",
        body={
            "prompt": "small blue ceramic tile motif, clean geometric textile pattern",
            "style": "geometric",
            "width": 1024,
            "height": 1024,
        },
        media_type="image",
        result_key="result_url",
        extension="jpg",
        timeout_seconds=300.0,
    ),
    JsonCase(
        name="pattern_transfer_sync",
        path="/api/v1/generate/pattern/transfer",
        body={"product_image_url": PRODUCT_URL, "pattern_image_url": PATTERN_URL, "blend_strength": 0.55},
        media_type="image",
        result_key="result_url",
        extension="jpg",
        timeout_seconds=300.0,
    ),
    JsonCase(
        name="interior_3d_model",
        path="/api/v1/interior/3d-model",
        body={"image_url": ROOM_URL, "texture_size": 1024, "mesh_simplify": 0.95},
        media_type="model",
        result_key="model_url",
        extension="glb",
        timeout_seconds=900.0,
    ),
]


def log(message: str) -> None:
    print(message, flush=True)


def validate_bytes(data: bytes, content_type: str, media_type: str) -> tuple[bool, str]:
    content_type = (content_type or "").lower()
    if media_type == "image":
        magic_ok = data.startswith((b"\xff\xd8", b"\x89PNG\r\n\x1a\n", b"RIFF"))
        return len(data) >= 5_000 and magic_ok, f"{content_type or 'unknown'} {len(data)} bytes image_magic={magic_ok}"

    if media_type == "video":
        magic_ok = b"ftyp" in data[:256] or data.startswith(b"\x1aE\xdf\xa3")
        return len(data) >= 50_000 and magic_ok, f"{content_type or 'unknown'} {len(data)} bytes video_magic={magic_ok}"

    glb_ok = data[:4] == b"glTF"
    obj_like = data[:128].lstrip().startswith((b"o ", b"v ", b"#"))
    type_ok = "model" in content_type or "octet-stream" in content_type or glb_ok or obj_like
    return len(data) >= 1_000 and type_ok and (glb_ok or obj_like), (
        f"{content_type or 'unknown'} {len(data)} bytes glb_magic={glb_ok} obj_like={obj_like}"
    )


def absolute_url(url: str) -> str:
    return url if url.startswith("http") else f"{BACKEND}{url}"


class VidGoApi:
    def __init__(self) -> None:
        timeout = httpx.Timeout(API_TIMEOUT_SECONDS, connect=60.0)
        self.client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)
        self.token = ""

    async def close(self) -> None:
        await self.client.aclose()

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def login(self) -> dict[str, Any]:
        response = await self.client.post(
            f"{BACKEND}/api/v1/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
        )
        response.raise_for_status()
        payload = response.json()
        self.token = payload["tokens"]["access"]
        return payload.get("user", {})

    async def get_json(self, path: str) -> dict[str, Any]:
        response = await self.client.get(f"{BACKEND}{path}", headers=self.headers())
        response.raise_for_status()
        return response.json()

    async def run_json_case(self, case: JsonCase, result_dir: Path) -> CaseResult:
        started = time.monotonic()
        log(f"\n[SYNC] {case.name} -> {case.path}")
        record = CaseResult(name=case.name, ok=False, path=case.path)

        try:
            response = await self.client.post(
                f"{BACKEND}{case.path}",
                json=case.body,
                headers=self.headers(),
                timeout=case.timeout_seconds,
            )
            record.status_code = response.status_code
            try:
                payload = response.json()
            except Exception:
                payload = {"raw": response.text[:500]}

            success = bool(payload.get("success")) if "success" in payload else response.is_success
            result_url = payload.get(case.result_key) or payload.get("result_url") or payload.get("image_url") or payload.get("video_url")
            record.result_url = result_url

            if not response.is_success or not success or not result_url:
                record.detail = payload.get("message") or payload.get("error") or payload.get("detail") or response.text[:500]
                log(f"  FAIL response: HTTP {response.status_code} {record.detail}")
                return record

            media_headers = self.headers() if result_url.startswith("/") or result_url.startswith(BACKEND) else None
            media_response = await self.client.get(absolute_url(result_url), headers=media_headers, timeout=180.0)
            media_response.raise_for_status()
            ok, detail = validate_bytes(media_response.content, media_response.headers.get("content-type", ""), case.media_type)
            download_path = result_dir / f"{case.name}.{case.extension}"
            download_path.write_bytes(media_response.content)

            record.ok = ok
            record.download_path = str(download_path)
            record.detail = detail
            log(f"  {'PASS' if ok else 'FAIL'} {detail} -> {download_path}")
            return record
        except Exception as exc:
            record.detail = f"{type(exc).__name__}: {str(exc)[:300]}"
            log(f"  FAIL exception: {record.detail}")
            return record
        finally:
            record.seconds = time.monotonic() - started

    async def run_user_works_download(self) -> CaseResult:
        log("\n[SYNC] my_works_download -> /api/v1/user/generations")
        record = CaseResult(name="my_works_download", ok=False, path="/api/v1/user/generations")
        started = time.monotonic()
        try:
            works = await self.get_json("/api/v1/user/generations?page=1&per_page=10&show_expired=false")
            items = works.get("items", [])
            selected = next((item for item in items if item.get("result_image_url") or item.get("result_video_url")), None)
            if not selected:
                record.detail = f"No active downloadable work in {len(items)} listed items"
                log(f"  FAIL {record.detail}")
                return record

            response = await self.client.get(
                f"{BACKEND}/api/v1/user/generations/{selected['id']}/download",
                headers=self.headers(),
                follow_redirects=False,
            )
            record.status_code = response.status_code
            record.ok = response.status_code in {200, 302, 307}
            record.detail = f"HTTP {response.status_code} tool={selected.get('tool_type')}"
            log(f"  {'PASS' if record.ok else 'FAIL'} {record.detail}")
            return record
        except Exception as exc:
            record.detail = f"{type(exc).__name__}: {str(exc)[:300]}"
            log(f"  FAIL exception: {record.detail}")
            return record
        finally:
            record.seconds = time.monotonic() - started


async def main() -> int:
    parser = argparse.ArgumentParser(description="VidGo direct API E2E spot checks")
    parser.add_argument("--result-dir", default="TEST/e2e_results/latest_sync_api_spotcheck")
    parser.add_argument("--skip-3d", action="store_true", help="Skip the potentially long interior 3D provider call")
    parser.add_argument(
        "--tools",
        default="",
        help="Comma-separated direct case names to run. Default runs all direct cases.",
    )
    args = parser.parse_args()

    result_dir = Path(args.result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)

    api = VidGoApi()
    results: list[CaseResult] = []
    try:
        health = await api.client.get(f"{BACKEND}/health", timeout=30)
        health.raise_for_status()
        log(f"Backend: {BACKEND}")
        log(f"Health: {health.text[:160]}")

        user = await api.login()
        log(f"Login: {EMAIL} plan={user.get('plan_type') or user.get('plan') or '?'} admin={user.get('is_superuser', False)}")
        before = await api.get_json("/api/v1/credits/balance")
        log(f"Credits before: {before.get('total')} total")

        selected = {item.strip() for item in args.tools.split(",") if item.strip()}
        for case in JSON_CASES:
            if selected and case.name not in selected:
                continue
            if args.skip_3d and case.name == "interior_3d_model":
                continue
            results.append(await api.run_json_case(case, result_dir))

        await api.login()
        results.append(await api.run_user_works_download())
        after = await api.get_json("/api/v1/credits/balance")
        log(f"Credits after: {after.get('total')} total")
    finally:
        await api.close()

    summary_path = result_dir / "summary.json"
    summary_path.write_text(json.dumps([asdict(result) for result in results], indent=2), encoding="utf-8")
    passed = sum(1 for result in results if result.ok)
    log("\n=== SUMMARY ===")
    log(f"Passed: {passed}/{len(results)}")
    log(f"Summary: {summary_path}")
    for result in results:
        log(f"{'PASS' if result.ok else 'FAIL'} {result.name}: {result.detail}")

    return 0 if results and passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))