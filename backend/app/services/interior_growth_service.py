"""
Interior "floor plan grows into a 3D room" pipeline orchestrator.

Implements the approved Gemini → render → Kling (→ optional Trellis) pipeline
as a single async flow. Each stage reuses an existing capability:

    [2D floor plan]
        │
        ▼
    1. Gemini Vision  (gemini_service.analyze_floorplan_for_growth)
        →  render_prompt + video_motion_prompt   (the "brain")
        │
        ▼
    2. Gemini Image   (interior_design_service.render_from_floorplan)
        →  photorealistic 3D interior  ── this is the video END frame
        │
        ▼
    3. Kling 3.0/Omni (provider_router → piapi.kling_video_generation)
        →  image-to-video FIRST→LAST frame morph:
           start = original 2D plan, end = rendered room,
           prompt = video_motion_prompt   →  "growth" MP4
        │
        └─► (optional) 4. Trellis2 (provider_router → piapi.trellis_3d)
                          →  interactive GLB 3D model from the rendered room

Public URLs: the render frame must be fetchable by PiAPI/Kling. Rather than
depend on GCS/ADC (absent in local dev), any non-public image is uploaded to
PiAPI's ephemeral resource store using only PIAPI_KEY — so the render→Kling
handoff works identically locally and on Cloud Run.

This module is pure orchestration. Auth, credit deduction and refunds live in
the interior.py endpoint.
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, Optional

import httpx

from app.providers.provider_router import TaskType, get_provider_router
from app.providers.piapi_provider import KLING_OMNI_TIMEOUT_SEC
from app.services.gemini_service import get_gemini_service
from app.services.interior_design_service import (
    get_interior_design_service,
    DESIGN_STYLES,
    ROOM_TYPES,
)

logger = logging.getLogger(__name__)


class InteriorGrowthService:
    """Orchestrates the floor-plan → 3D-growth-video pipeline."""

    async def _ensure_public_image(self, url: str) -> str:
        """Return a URL that PiAPI/Kling can fetch.

        Genuine public https URLs (e.g. GCS) pass through untouched. Local
        /static paths or localhost URLs are read/fetched into bytes and pushed
        to PiAPI's ephemeral store (needs only PIAPI_KEY), so the pipeline does
        not depend on GCS/ADC being configured.
        """
        if not url:
            return url
        is_localhost = "localhost" in url or "127.0.0.1" in url
        if url.startswith("https://") and not is_localhost:
            return url

        data: Optional[bytes] = None
        try:
            if url.startswith(("/static", "static", "/app/")):
                local_path = url if url.startswith("/app/") else os.path.join("/app", url.lstrip("/"))
                if os.path.exists(local_path):
                    with open(local_path, "rb") as fh:
                        data = fh.read()
            if data is None:
                fetch_url = url
                if url.startswith(("/static", "static")):
                    base = os.environ.get("PUBLIC_APP_URL", "http://localhost:8000").rstrip("/")
                    fetch_url = f"{base}/{url.lstrip('/')}"
                async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as http:
                    resp = await http.get(fetch_url)
                    resp.raise_for_status()
                    data = resp.content
        except Exception as exc:  # noqa: BLE001
            logger.warning("[InteriorGrowth] could not read bytes for %s: %s", url, exc)
            return url

        try:
            piapi = get_provider_router().piapi
            public = await piapi._upload_ephemeral_resource(
                data,
                file_name=f"floorgrow_{uuid.uuid4().hex[:10]}.jpg",
                content_type="image/jpeg",
            )
            if public:
                return public
        except Exception as exc:  # noqa: BLE001
            logger.warning("[InteriorGrowth] ephemeral upload failed: %s", exc)
        return url

    @staticmethod
    def _style_label(style_id: Optional[str]) -> str:
        style = DESIGN_STYLES.get(style_id or "")
        return style["name"] if style else (style_id or "modern minimalist")

    @staticmethod
    def _room_label(room_type: Optional[str]) -> str:
        room = ROOM_TYPES.get(room_type or "")
        return room["name"] if room else (room_type or "living room")

    def _template_prompts(self, style_id: Optional[str], room_type: Optional[str], extra_prompt: str) -> Dict[str, str]:
        """Deterministic fallback prompts when Gemini analysis is unavailable."""
        style = DESIGN_STYLES.get(style_id or "modern_minimalist") or DESIGN_STYLES["modern_minimalist"]
        room = ROOM_TYPES.get(room_type or "living_room", {})
        room_name = (room.get("name") or "room").lower()
        render_prompt = (
            f"{style['prompt_suffix']}. {room.get('context', '')}. "
            f"{extra_prompt}"
        ).strip()
        video_motion_prompt = (
            "A flat 2D architectural floor plan smoothly extrudes and grows vertically into a "
            f"fully furnished photorealistic 3D {room_name}. Walls rise up from the floor-plan "
            f"lines, {style['name'].lower()} materials and textures spread across the floor and "
            "walls, furniture and lighting materialize in place, gentle cinematic camera push-in, "
            "smooth 5 second transformation, no people."
        )
        return {
            "render_prompt": render_prompt,
            "video_motion_prompt": video_motion_prompt,
            "structure_notes": "",
        }

    async def run(
        self,
        *,
        floorplan_url: str,
        style_id: Optional[str] = "modern_minimalist",
        room_type: Optional[str] = "living_room",
        extra_prompt: str = "",
        include_3d: bool = False,
        duration: int = 5,
        model_version: str = "v2",
        language: str = "en",
    ) -> Dict[str, Any]:
        """Run the pipeline. Returns a structured dict; never raises for an
        upstream stage failure (returns ``success=False`` + ``stage`` instead).
        """
        steps: Dict[str, str] = {}
        gemini = get_gemini_service()
        interior = get_interior_design_service()
        router = get_provider_router()

        # Kling needs a public start frame; also lets Gemini fetch it.
        public_floorplan = await self._ensure_public_image(floorplan_url)

        # ── Step 1: Gemini analysis (fail-soft → template) ──────────────────
        analysis = await gemini.analyze_floorplan_for_growth(
            image_url=public_floorplan,
            style_label=self._style_label(style_id),
            room_type_label=self._room_label(room_type),
            extra_prompt=extra_prompt,
            language=language,
        )
        if analysis.get("success"):
            render_prompt = analysis["render_prompt"]
            motion_prompt = analysis["video_motion_prompt"]
            structure_notes = analysis.get("structure_notes", "")
            steps["analysis"] = f"gemini:{analysis.get('backend', 'ok')}"
        else:
            tpl = self._template_prompts(style_id, room_type, extra_prompt)
            render_prompt = tpl["render_prompt"]
            motion_prompt = tpl["video_motion_prompt"]
            structure_notes = tpl["structure_notes"]
            steps["analysis"] = "template_fallback"
            logger.info("[InteriorGrowth] analysis fell back to template: %s", analysis.get("error"))

        prompts = {
            "render_prompt": render_prompt,
            "video_motion_prompt": motion_prompt,
            "structure_notes": structure_notes,
        }

        # ── Step 2: render the photorealistic 3D interior (END frame) ───────
        render = await interior.render_from_floorplan(
            floorplan_image_url=public_floorplan,
            style_id=style_id,
            room_type=room_type,
            extra_prompt=render_prompt,
        )
        if not render.get("success") or not render.get("image_url"):
            return {
                "success": False,
                "stage": "render",
                "error": render.get("error", "Floor-plan render failed"),
                "prompts": prompts,
                "steps": steps,
            }
        render_public = await self._ensure_public_image(render["image_url"])
        steps["render"] = "ok"

        # ── Step 3: Kling 3.0/Omni first→last frame growth video ────────────
        # router.route() RAISES (it doesn't return success=False) when every
        # provider in the chain fails, so wrap it to honor this method's
        # "never raises for an upstream stage failure" contract.
        try:
            kling = await router.route(
                TaskType.KLING_VIDEO,
                {
                    "prompt": motion_prompt,
                    "image_url": public_floorplan,      # first frame: 2D plan
                    "image_tail_url": render_public,    # last frame: rendered room
                    "tier": "omni",                     # Kling 3.0 (multimodal + audio)
                    "duration": int(duration),
                    "timeout": KLING_OMNI_TIMEOUT_SEC,  # 1800s — premium tier headroom
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("[InteriorGrowth] Kling growth video raised: %s", exc)
            kling = {"success": False, "error": str(exc)}
        if not kling.get("success"):
            return {
                "success": False,
                "stage": "video",
                "error": kling.get("error", "Kling growth video failed"),
                "render_image_url": render_public,
                "prompts": prompts,
                "steps": steps,
            }
        video_url = (
            kling.get("video_url")
            or (kling.get("output") or {}).get("video_url")
            or kling.get("output_url")
        )
        # A success response with no resolvable video URL must NOT be reported
        # as success — otherwise the endpoint charges full credits and the
        # frontend renders a blank result (its <video> has an empty src).
        if not video_url:
            logger.error("[InteriorGrowth] Kling reported success but no video URL: keys=%s",
                         list((kling.get("output") or {}).keys()))
            return {
                "success": False,
                "stage": "video",
                "error": "Kling returned no video URL",
                "render_image_url": render_public,
                "prompts": prompts,
                "steps": steps,
            }
        steps["video"] = "ok"

        result: Dict[str, Any] = {
            "success": True,
            "render_image_url": render_public,
            "video_url": video_url,
            "prompts": prompts,
            "steps": steps,
        }

        # ── Step 4 (optional): Trellis2 interactive 3D model ────────────────
        # This step is strictly optional: a failure here must not discard the
        # already-generated growth video. router.route() RAISES on failure, so
        # catch it and fall through to the graceful "model_3d failed" branch
        # (the endpoint then returns the video + a partial 3D refund).
        if include_3d:
            try:
                td = await router.route(
                    TaskType.INTERIOR_3D,
                    {"image_url": render_public, "model_version": model_version or "v2"},
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("[InteriorGrowth] Trellis 3D raised: %s", exc)
                td = {"success": False, "error": str(exc)}
            if td.get("success"):
                out = td.get("output") or {}
                result["model_url"] = out.get("model_url") or out.get("model_file") or out.get("url")
                result["model_preview_video_url"] = out.get("video_url") or out.get("combined_video")
                steps["model_3d"] = "ok" if result.get("model_url") else "no_model_url"
            else:
                result["model_3d_error"] = td.get("error", "3D reconstruction failed")
                steps["model_3d"] = "failed"

        return result


_interior_growth_service: Optional[InteriorGrowthService] = None


def get_interior_growth_service() -> InteriorGrowthService:
    """Get or create the InteriorGrowthService singleton."""
    global _interior_growth_service
    if _interior_growth_service is None:
        _interior_growth_service = InteriorGrowthService()
    return _interior_growth_service
