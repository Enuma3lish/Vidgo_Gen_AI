#!/usr/bin/env python3
"""VidGo preset/default mode E2E test harness.

For each supported tool type:
  1. GET  /api/v1/demo/presets/{tool_type}        -> pick first preset
  2. POST /api/v1/demo/use-preset                  -> resolve material URLs
  3. GET  /api/v1/demo/download/{material_id}      -> download full result
  4. Validate downloaded bytes (image or video magic + size)

Runs as an authenticated subscriber so downloads are not blocked.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import httpx


BACKEND = os.getenv(
    "VIDGO_BACKEND_URL",
    "https://vidgo-backend-r2laip67ma-de.a.run.app",
).rstrip("/")
EMAIL = os.getenv("VIDGO_TEST_EMAIL", "qaz0978005418@gmail.com")
PASSWORD = os.getenv("VIDGO_TEST_PASSWORD", "qaz129946858")
API_TIMEOUT_SECONDS = float(os.getenv("VIDGO_API_TIMEOUT_SECONDS", "300"))


@dataclass(frozen=True)
class PresetCase:
    name: str
    tool_type: str
    media_type: str  # "image" or "video"


PRESET_CASES = [
    PresetCase("background_removal", "background_removal", "image"),
    PresetCase("product_scene", "product_scene", "image"),
    PresetCase("try_on", "try_on", "image"),
    PresetCase("room_redesign", "room_redesign", "image"),
    PresetCase("pattern_generate", "pattern_generate", "image"),
    PresetCase("effect", "effect", "image"),
    PresetCase("short_video", "short_video", "video"),
    PresetCase("ai_avatar", "ai_avatar", "video"),
]


@dataclass
class CaseResult:
    name: str
    ok: bool
    tool_type: str
    media_type: str
    preset_id: str | None = None
    result_url: str | None = None
    download_path: str | None = None
    download_bytes: int = 0
    detail: str = ""
    elapsed_seconds: float = 0.0


def log(msg: str) -> None:
    print(msg, flush=True)


def has_image_magic(data: bytes) -> bool:
    return data.startswith((b"\xff\xd8", b"\x89PNG\r\n\x1a\n", b"RIFF", b"GIF8"))


def has_video_magic(data: bytes) -> bool:
    return b"ftyp" in data[:256] or data.startswith(b"\x1aE\xdf\xa3")


def validate_bytes(data: bytes, content_type: str, media_type: str) -> tuple[bool, str]:
    content_type = (content_type or "").lower()
    if media_type == "image":
        magic_ok = has_image_magic(data)
        size_ok = len(data) >= 2_000
        return magic_ok and size_ok, f"{content_type or 'unknown'} {len(data)} bytes image_magic={magic_ok}"
    magic_ok = has_video_magic(data)
    size_ok = len(data) >= 20_000
    return magic_ok and size_ok, f"{content_type or 'unknown'} {len(data)} bytes video_magic={magic_ok}"


class VidGoApi:
    def __init__(self) -> None:
        self.client = httpx.AsyncClient(timeout=API_TIMEOUT_SECONDS, follow_redirects=True)
        self.token = ""

    async def close(self) -> None:
        await self.client.aclose()

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def login(self) -> dict[str, Any]:
        resp = await self.client.post(
            f"{BACKEND}/api/v1/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
        )
        resp.raise_for_status()
        payload = resp.json()
        self.token = payload["tokens"]["access"]
        return payload.get("user", {})

    async def get_json(self, path: str, params: dict | None = None) -> dict[str, Any]:
        resp = await self.client.get(f"{BACKEND}{path}", headers=self.headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    async def post_json(self, path: str, body: dict) -> dict[str, Any]:
        resp = await self.client.post(f"{BACKEND}{path}", headers=self.headers(), json=body)
        resp.raise_for_status()
        return resp.json()

    async def run_case(self, case: PresetCase, result_dir: Path) -> CaseResult:
        started = time.monotonic()
        log(f"\n[PRESET] {case.name} ({case.tool_type})")

        try:
            # 1. fetch presets
            presets_resp = await self.get_json(
                f"/api/v1/demo/presets/{case.tool_type}",
                params={"limit": 25},
            )
            presets = presets_resp.get("presets", []) or []
            if not presets:
                return CaseResult(
                    name=case.name,
                    ok=False,
                    tool_type=case.tool_type,
                    media_type=case.media_type,
                    detail=f"no presets available (db_empty={presets_resp.get('db_empty')})",
                    elapsed_seconds=time.monotonic() - started,
                )

            preset_id = None
            result_url = None
            dl = None
            tried = 0
            last_status = ""
            for preset in presets:
                preset_id = preset["id"]
                tried += 1
                use_resp = await self.post_json(
                    "/api/v1/demo/use-preset",
                    {"preset_id": preset_id},
                )
                if not use_resp.get("success"):
                    last_status = f"use-preset failed: {use_resp.get('error')}"
                    continue
                result_url = use_resp.get("result_url") or use_resp.get("result_watermarked_url")
                dl_try = await self.client.get(
                    f"{BACKEND}/api/v1/demo/download/{preset_id}",
                    headers=self.headers(),
                    follow_redirects=True,
                    timeout=180,
                )
                if dl_try.status_code < 400:
                    dl = dl_try
                    log(f"  picked preset id={preset_id} (after {tried} tries) url={result_url}")
                    break
                last_status = f"download HTTP {dl_try.status_code}"

            if dl is None:
                return CaseResult(
                    name=case.name,
                    ok=False,
                    tool_type=case.tool_type,
                    media_type=case.media_type,
                    preset_id=preset_id,
                    result_url=result_url,
                    detail=f"all {tried} presets failed; last={last_status}",
                    elapsed_seconds=time.monotonic() - started,
                )

            data = dl.content
            content_type = dl.headers.get("content-type", "")
            ok, detail = validate_bytes(data, content_type, case.media_type)
            extension = "mp4" if case.media_type == "video" else "jpg"
            download_path = result_dir / f"preset_{case.name}_{preset_id[:8]}.{extension}"
            download_path.write_bytes(data)

            return CaseResult(
                name=case.name,
                ok=ok,
                tool_type=case.tool_type,
                media_type=case.media_type,
                preset_id=preset_id,
                result_url=result_url,
                download_path=str(download_path),
                download_bytes=len(data),
                detail=detail,
                elapsed_seconds=time.monotonic() - started,
            )
        except Exception as exc:
            return CaseResult(
                name=case.name,
                ok=False,
                tool_type=case.tool_type,
                media_type=case.media_type,
                detail=f"{type(exc).__name__}: {str(exc)[:300]}",
                elapsed_seconds=time.monotonic() - started,
            )


async def run_presets(selected: set[str] | None, result_dir: Path) -> list[CaseResult]:
    api = VidGoApi()
    try:
        health = await api.client.get(f"{BACKEND}/health", timeout=30)
        health.raise_for_status()
        log(f"Backend: {BACKEND}")
        log(f"Health: {health.text[:160]}")

        user = await api.login()
        log(f"Login: {EMAIL} plan={user.get('plan_type') or user.get('plan') or '?'} subscribed={user.get('is_subscribed', '?')}")

        results: list[CaseResult] = []
        for case in PRESET_CASES:
            if selected and case.name not in selected and case.tool_type not in selected:
                continue
            r = await api.run_case(case, result_dir)
            icon = "PASS" if r.ok else "FAIL"
            log(f"  {icon} {case.name}: {r.detail} ({r.elapsed_seconds:.1f}s)")
            results.append(r)

        return results
    finally:
        await api.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preset/default mode E2E test for VidGo tools")
    parser.add_argument("--tools", default="", help="Comma-separated names/tool types to run.")
    parser.add_argument(
        "--result-dir",
        default="TEST/e2e_results/latest_preset_api_download",
        help="Directory to store downloaded preset media + JSON summary.",
    )
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    result_dir = Path(args.result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)
    selected = {item.strip() for item in args.tools.split(",") if item.strip()} or None

    results = await run_presets(selected, result_dir)
    summary_path = result_dir / "summary.json"
    summary_path.write_text(json.dumps([asdict(r) for r in results], indent=2), encoding="utf-8")

    passed = sum(1 for r in results if r.ok)
    total = len(results)
    log("\n=== PRESET SUMMARY ===")
    log(f"Passed: {passed}/{total}")
    log(f"Summary: {summary_path}")
    for r in results:
        icon = "PASS" if r.ok else "FAIL"
        log(f"{icon} {r.name}: preset={r.preset_id} bytes={r.download_bytes} detail={r.detail}")

    return 0 if passed == total and total > 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
