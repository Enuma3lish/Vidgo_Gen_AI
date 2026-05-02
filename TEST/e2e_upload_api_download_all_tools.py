#!/usr/bin/env python3
"""VidGo upload/API/download E2E test harness.

Runs subscriber uploads through /api/v1/uploads/material, polls generation status,
downloads the finished result through /api/v1/uploads/{id}/download, and validates
that the returned media bytes look like an image or video.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import httpx

try:
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover - fallback only for very slim envs
    Image = None
    ImageDraw = None


BACKEND = os.getenv("VIDGO_BACKEND_URL", "https://vidgo-backend-r2laip67ma-de.a.run.app").rstrip("/")
EMAIL = os.getenv("VIDGO_TEST_EMAIL", "qaz0978005418@gmail.com")
PASSWORD = os.getenv("VIDGO_TEST_PASSWORD", "qaz129946858")
API_TIMEOUT_SECONDS = float(os.getenv("VIDGO_API_TIMEOUT_SECONDS", "900"))
POLL_INTERVAL_SECONDS = float(os.getenv("VIDGO_UPLOAD_POLL_INTERVAL_SECONDS", "5"))

VIDEO_FIXTURE_URL = os.getenv(
    "VIDGO_TEST_VIDEO_URL",
    "https://filesamples.com/samples/video/mp4/sample_640x360.mp4",
)
PORTRAIT_FIXTURE_URL = os.getenv(
    "VIDGO_TEST_PORTRAIT_URL",
    "https://storage.googleapis.com/vidgo-media-vidgo-ai/static/avatars/female-1.png",
)


@dataclass
class CaseResult:
    name: str
    ok: bool
    upload_id: str | None = None
    status: str | None = None
    media_type: str | None = None
    result_url: str | None = None
    download_path: str | None = None
    detail: str = ""
    submit_seconds: float = 0.0
    total_seconds: float = 0.0
    credits_used: int = 0


@dataclass(frozen=True)
class UploadCase:
    name: str
    tool_type: str
    fixture_key: str
    filename: str
    content_type: str
    media_type: str
    model_id: str = "default"
    prompt: str = ""
    max_wait_seconds: int = 900


UPLOAD_CASES = [
    UploadCase(
        name="background_removal",
        tool_type="background_removal",
        fixture_key="product",
        filename="product.jpg",
        content_type="image/jpeg",
        media_type="image",
        prompt="clean product cutout on transparent background",
        max_wait_seconds=600,
    ),
    UploadCase(
        name="product_scene",
        tool_type="product_scene",
        fixture_key="product",
        filename="product.jpg",
        content_type="image/jpeg",
        media_type="image",
        prompt="premium studio product photography on a warm wood tabletop with soft window light",
        max_wait_seconds=900,
    ),
    UploadCase(
        name="try_on",
        tool_type="try_on",
        fixture_key="garment",
        filename="garment.jpg",
        content_type="image/jpeg",
        media_type="image",
        prompt="professional ecommerce apparel try-on on a neutral studio model",
        max_wait_seconds=900,
    ),
    UploadCase(
        name="room_redesign",
        tool_type="room_redesign",
        fixture_key="room",
        filename="room.jpg",
        content_type="image/jpeg",
        media_type="image",
        prompt="modern Scandinavian interior redesign with natural wood, soft beige textiles, and clean daylight",
        max_wait_seconds=900,
    ),
    UploadCase(
        name="pattern_generate",
        tool_type="pattern_generate",
        fixture_key="product",
        filename="pattern-source.jpg",
        content_type="image/jpeg",
        media_type="image",
        prompt="seamless botanical packaging pattern in teal and coral, commercial textile design",
        max_wait_seconds=600,
    ),
    UploadCase(
        name="effect",
        tool_type="effect",
        fixture_key="food",
        filename="food.jpg",
        content_type="image/jpeg",
        media_type="image",
        prompt="anime watercolor food illustration, clean commercial social media style",
        max_wait_seconds=600,
    ),
    UploadCase(
        name="short_video",
        tool_type="short_video",
        fixture_key="product",
        filename="product-video-source.jpg",
        content_type="image/jpeg",
        media_type="video",
        model_id="pixverse_v4.5",
        prompt="slow cinematic push-in product advertising video, subtle highlights, no text",
        max_wait_seconds=1200,
    ),
    UploadCase(
        name="video_transform",
        tool_type="video_transform",
        fixture_key="video",
        filename="sample.mp4",
        content_type="video/mp4",
        media_type="video",
        prompt="cinematic warm color grade with premium product-ad lighting",
        max_wait_seconds=1200,
    ),
    UploadCase(
        name="ai_avatar",
        tool_type="ai_avatar",
        fixture_key="portrait",
        filename="portrait.jpg",
        content_type="image/jpeg",
        media_type="video",
        prompt="Hello, this is a VidGo AI end to end upload test. The upload API should generate and download this result successfully.",
        max_wait_seconds=1200,
    ),
]


def log(message: str) -> None:
    print(message, flush=True)


def build_image_fixture(path: Path, label: str, fill: tuple[int, int, int]) -> None:
    if Image is None:
        # Tiny but valid fallback. Real provider tests should use the PIL path.
        path.write_bytes(
            bytes.fromhex(
                "ffd8ffe000104a46494600010100000100010000ffdb004300"
                "080606070605080707070909080a0c140d0c0b0b0c1912130f"
                "141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30"
                "313434341f27393d38323c2e333432ffdb0043010909090c0b"
                "0c180d0d1832211c213232323232323232323232323232323232"
                "3232323232323232323232323232323232323232323232323232"
                "3232323232ffc00011080001000103012200021101031101ffc4"
                "001f000001050101010101010000000000000000010203040506"
                "0708090a0bffc400b5100002010303020403050504040000017d"
                "01020300041105122131410613516107227114328191a1082342"
                "b1c11552d1f02433627282090a161718191a25262728292a3435"
                "363738393a434445464748494a535455565758595a6364656667"
                "68696a737475767778797a838485868788898a92939495969798"
                "999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4"
                "c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8"
                "e9eaf1f2f3f4f5f6f7f8f9faffe000fda000c030100021103"
                "11003f00f7fa28a2803fffd9"
            )
        )
        return

    image = Image.new("RGB", (768, 768), fill)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((110, 110, 658, 658), radius=60, outline=(255, 255, 255), width=8)
    draw.ellipse((255, 235, 513, 493), fill=tuple(min(255, value + 45) for value in fill))
    draw.rectangle((285, 410, 483, 610), fill=tuple(max(0, value - 45) for value in fill))
    draw.text((120, 690), f"VidGo E2E {label}", fill=(255, 255, 255))
    image.save(path, "JPEG", quality=92)


async def build_fixtures(root: Path, client: httpx.AsyncClient) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    fixtures = {
        "product": root / "product.jpg",
        "garment": root / "garment.jpg",
        "room": root / "room.jpg",
        "food": root / "food.jpg",
        "portrait": root / "portrait.jpg",
        "video": root / "sample.mp4",
    }

    build_image_fixture(fixtures["product"], "product", (32, 104, 178))
    build_image_fixture(fixtures["garment"], "garment", (176, 72, 88))
    build_image_fixture(fixtures["room"], "room", (104, 132, 88))
    build_image_fixture(fixtures["food"], "food", (201, 132, 52))
    portrait_response = await client.get(PORTRAIT_FIXTURE_URL, follow_redirects=True, timeout=120)
    portrait_response.raise_for_status()
    portrait_bytes = portrait_response.content
    if len(portrait_bytes) < 20_000 or not has_image_magic(portrait_bytes):
        raise RuntimeError(f"Portrait fixture is not a usable face image: {len(portrait_bytes)} bytes")
    fixtures["portrait"].write_bytes(portrait_bytes)

    response = await client.get(VIDEO_FIXTURE_URL, follow_redirects=True, timeout=120)
    response.raise_for_status()
    video_bytes = response.content
    if len(video_bytes) < 50_000 or b"ftyp" not in video_bytes[:256]:
        raise RuntimeError(f"Video fixture is not a usable mp4: {len(video_bytes)} bytes")
    fixtures["video"].write_bytes(video_bytes)
    return fixtures


def has_image_magic(data: bytes) -> bool:
    return data.startswith((b"\xff\xd8", b"\x89PNG\r\n\x1a\n", b"RIFF"))


def has_video_magic(data: bytes) -> bool:
    return b"ftyp" in data[:256] or data.startswith(b"\x1aE\xdf\xa3")


def validate_bytes(data: bytes, content_type: str, media_type: str) -> tuple[bool, str]:
    content_type = (content_type or "").lower()
    if media_type == "image":
        magic_ok = has_image_magic(data)
        size_ok = len(data) >= 5_000
        type_ok = "image" in content_type or magic_ok
        return type_ok and magic_ok and size_ok, f"{content_type or 'unknown'} {len(data)} bytes image_magic={magic_ok}"

    magic_ok = has_video_magic(data)
    size_ok = len(data) >= 50_000
    type_ok = "video" in content_type or magic_ok
    return type_ok and magic_ok and size_ok, f"{content_type or 'unknown'} {len(data)} bytes video_magic={magic_ok}"


class VidGoApi:
    def __init__(self) -> None:
        self.client = httpx.AsyncClient(timeout=API_TIMEOUT_SECONDS, follow_redirects=True)
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

    async def upload_case(self, case: UploadCase, fixtures: dict[str, Path], result_dir: Path) -> CaseResult:
        started = time.monotonic()
        fixture_path = fixtures[case.fixture_key]
        log(f"\n[UPLOAD] {case.name} -> {case.tool_type} using {fixture_path.name}")

        try:
            with fixture_path.open("rb") as file_handle:
                submit_started = time.monotonic()
                response = await self.client.post(
                    f"{BACKEND}/api/v1/uploads/material",
                    data={"tool_type": case.tool_type, "model_id": case.model_id, "prompt": case.prompt},
                    files={"file": (case.filename, file_handle, case.content_type)},
                    headers=self.headers(),
                    timeout=120,
                )
            submit_seconds = time.monotonic() - submit_started
            if response.status_code >= 400:
                return CaseResult(
                    name=case.name,
                    ok=False,
                    status="submit_failed",
                    media_type=case.media_type,
                    detail=f"HTTP {response.status_code}: {response.text[:300]}",
                    submit_seconds=submit_seconds,
                    total_seconds=time.monotonic() - started,
                )

            upload_payload = response.json()
            upload_id = upload_payload["upload_id"]
            log(f"  submitted id={upload_id} status={upload_payload.get('status')} in {submit_seconds:.1f}s")

            deadline = time.monotonic() + case.max_wait_seconds
            status_payload: dict[str, Any] = {}
            while time.monotonic() < deadline:
                status_payload = await self.get_json(f"/api/v1/uploads/{upload_id}")
                status_value = status_payload.get("status")
                log(f"  poll status={status_value}")
                if status_value in {"completed", "failed"}:
                    break
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

            status_value = status_payload.get("status")
            if status_value != "completed":
                return CaseResult(
                    name=case.name,
                    ok=False,
                    upload_id=upload_id,
                    status=status_value or "timeout",
                    media_type=case.media_type,
                    detail=status_payload.get("error_message") or "Timed out waiting for completion",
                    submit_seconds=submit_seconds,
                    total_seconds=time.monotonic() - started,
                    credits_used=status_payload.get("credits_used", upload_payload.get("credits_used", 0)),
                )

            result_url = status_payload.get("result_video_url") or status_payload.get("result_url")
            if not result_url:
                return CaseResult(
                    name=case.name,
                    ok=False,
                    upload_id=upload_id,
                    status=status_value,
                    media_type=case.media_type,
                    detail="Completed without result URL",
                    submit_seconds=submit_seconds,
                    total_seconds=time.monotonic() - started,
                    credits_used=status_payload.get("credits_used", 0),
                )

            download_response = await self.client.get(
                f"{BACKEND}/api/v1/uploads/{upload_id}/download",
                headers=self.headers(),
                follow_redirects=True,
                timeout=180,
            )
            if download_response.status_code >= 400:
                return CaseResult(
                    name=case.name,
                    ok=False,
                    upload_id=upload_id,
                    status="download_failed",
                    media_type=case.media_type,
                    result_url=result_url,
                    detail=f"HTTP {download_response.status_code}: {download_response.text[:300]}",
                    submit_seconds=submit_seconds,
                    total_seconds=time.monotonic() - started,
                    credits_used=status_payload.get("credits_used", 0),
                )

            data = download_response.content
            content_type = download_response.headers.get("content-type", "")
            bytes_ok, bytes_detail = validate_bytes(data, content_type, case.media_type)
            extension = "mp4" if case.media_type == "video" else "jpg"
            download_path = result_dir / f"upload_{case.name}_{upload_id[:8]}.{extension}"
            download_path.write_bytes(data)

            return CaseResult(
                name=case.name,
                ok=bytes_ok,
                upload_id=upload_id,
                status="completed",
                media_type=case.media_type,
                result_url=result_url,
                download_path=str(download_path),
                detail=bytes_detail,
                submit_seconds=submit_seconds,
                total_seconds=time.monotonic() - started,
                credits_used=status_payload.get("credits_used", 0),
            )
        except Exception as exc:
            return CaseResult(
                name=case.name,
                ok=False,
                status="exception",
                media_type=case.media_type,
                detail=f"{type(exc).__name__}: {str(exc)[:300]}",
                total_seconds=time.monotonic() - started,
            )


async def run_uploads(selected: set[str] | None, result_dir: Path) -> list[CaseResult]:
    api = VidGoApi()
    try:
        health = await api.client.get(f"{BACKEND}/health", timeout=30)
        health.raise_for_status()
        log(f"Backend: {BACKEND}")
        log(f"Health: {health.text[:160]}")

        user = await api.login()
        log(f"Login: {EMAIL} plan={user.get('plan_type') or user.get('plan') or '?'} admin={user.get('is_superuser', False)}")
        balance_before = await api.get_json("/api/v1/credits/balance")
        log(f"Credits before: {balance_before.get('total')} total")

        with tempfile.TemporaryDirectory(prefix="vidgo-e2e-assets-") as tmp:
            fixtures = await build_fixtures(Path(tmp), api.client)
            results: list[CaseResult] = []
            for case in UPLOAD_CASES:
                if selected and case.name not in selected and case.tool_type not in selected:
                    continue
                case_result = await api.upload_case(case, fixtures, result_dir)
                icon = "PASS" if case_result.ok else "FAIL"
                log(f"  {icon} {case.name}: {case_result.detail} ({case_result.total_seconds:.1f}s)")
                results.append(case_result)

        await api.login()
        balance_after = await api.get_json("/api/v1/credits/balance")
        log(f"Credits after: {balance_after.get('total')} total")
        return results
    finally:
        await api.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deep upload/API/download E2E test for VidGo tools")
    parser.add_argument(
        "--tools",
        default="",
        help="Comma-separated case names/tool types to run. Default runs all upload-supported tools.",
    )
    parser.add_argument(
        "--result-dir",
        default="TEST/e2e_results/latest_upload_api_download",
        help="Directory to store downloaded result media and JSON summary.",
    )
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    result_dir = Path(args.result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)
    selected = {item.strip() for item in args.tools.split(",") if item.strip()} or None

    results = await run_uploads(selected, result_dir)
    summary_path = result_dir / "summary.json"
    summary_path.write_text(json.dumps([asdict(result) for result in results], indent=2), encoding="utf-8")

    passed = sum(1 for result in results if result.ok)
    total = len(results)
    log("\n=== SUMMARY ===")
    log(f"Passed: {passed}/{total}")
    log(f"Summary: {summary_path}")
    for result in results:
        icon = "PASS" if result.ok else "FAIL"
        log(f"{icon} {result.name}: status={result.status} credits={result.credits_used} detail={result.detail}")

    return 0 if passed == total and total > 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))