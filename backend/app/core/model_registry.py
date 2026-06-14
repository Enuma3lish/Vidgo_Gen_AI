"""
Central registry of upstream AI-provider model identifiers.

WHY THIS EXISTS
---------------
PiAPI, Pollo and similar vendors version their models (e.g. Kling v1 → v2
→ v3 → v4). Historically every provider file in this codebase hard-coded
strings such as ``"model": "kling"`` or ``"pixverse_v4.5"``. When the
vendor released a newer alias we had to grep the codebase, edit several
files, build a new image and redeploy.

This module is the single source of truth for those identifiers and lets
us rotate to a newer vendor model with a single environment variable +
Cloud Run rolling restart — no rebuild required.

USAGE
-----
    from app.core.model_registry import PIAPI_MODELS, POLLO_MODELS

    payload = {"model": PIAPI_MODELS["kling_video_effects"], ...}

ENV OVERRIDES
-------------
Each entry below reads ``os.environ.get("<KEY>", "<default>")`` so ops
can change a model without a code release. To upgrade Kling Avatar
from the current alias to (hypothetical) ``kling-v4`` set:

    PIAPI_KLING_AVATAR_MODEL=kling-v4

…on the ``vidgo-backend`` and ``vidgo-worker`` Cloud Run services and
restart. Roll back the same way if the new version misbehaves.

NOTE ON "FULL AUTO-SYNC"
------------------------
PiAPI does NOT publish a discovery endpoint listing the current model
catalogue, and a new vendor major version (Kling 3 → 4) almost always
introduces breaking input-schema changes (new required fields, changed
duration enums, different response shape). We therefore deliberately do
NOT auto-promote — see ``report.md`` in the repo root for the full
reasoning.
"""

from __future__ import annotations

import os
from typing import Dict


# ─────────────────────────────────────────────────────────────────────────
# PiAPI
# ─────────────────────────────────────────────────────────────────────────
# Verified against piapi.ai/docs as of 2026-05:
#   - Kling   model="kling",   version∈{1.5,1.6,2.1,2.1-master,2.5,2.6}
#                              (default 2.6; 2.1-master is pro-mode flagship)
#   - Flux    "Qubico/flux1-schnell" (fast), "flux1-dev" (recommended),
#             "flux1-dev-advanced" (supports kontext editing)
#   - Wan     model="Wan", task_type="wan26-img2video" / "wan26-txt2video"
#   - Image   "Qubico/image-toolkit" → task_type "background-remove" / "upscale"
#   - TTS     "Qubico/tts" (F5; currently broken upstream as of 2026-05),
#             "tts-1" (OpenAI-compatible /v1/audio/speech; primary path)
#   - Midjourney model="midjourney" (alias auto-routes to current MJ version,
#                  cost tuned via process_mode: relax|fast|turbo)
#   - Trellis "Qubico/trellis" (v1, cheap) / "Qubico/trellis2" (v2, HQ)
#
# All four Kling endpoints use the bare ``"kling"`` alias; the version is
# selected separately via PIAPI_KLING_VIDEO_VERSION (for video_generation
# calls). Try-on, avatar, and lip_sync do NOT accept a version field.
PIAPI_MODELS: Dict[str, str] = {
    # Kling family (model field always "kling")
    "kling_video":         os.environ.get("PIAPI_KLING_VIDEO_MODEL",   "kling"),
    "kling_video_effects": os.environ.get("PIAPI_KLING_EFFECTS_MODEL", "kling"),
    "kling_try_on":        os.environ.get("PIAPI_KLING_TRYON_MODEL",   "kling"),
    "kling_avatar":        os.environ.get("PIAPI_KLING_AVATAR_MODEL",  "kling"),
    "kling_lip_sync":      os.environ.get("PIAPI_KLING_LIPSYNC_MODEL", "kling"),

    # Trellis (image → 3D GLB). v1 is cheap, v2 is HQ.
    "trellis_v1":          os.environ.get("PIAPI_TRELLIS_V1_MODEL",    "Qubico/trellis"),
    "trellis_v2":          os.environ.get("PIAPI_TRELLIS_V2_MODEL",    "Qubico/trellis2"),

    # Flux (text-to-image / image-to-image / kontext editing)
    # schnell is 4-step distilled — fastest & cheapest. dev is the recommended
    # full-quality option. dev-advanced is required for kontext editing.
    "flux_t2i":            os.environ.get("PIAPI_FLUX_T2I_MODEL",      "Qubico/flux1-schnell"),
    "flux_i2i":            os.environ.get("PIAPI_FLUX_I2I_MODEL",      "Qubico/flux1-schnell"),
    "flux_kontext":        os.environ.get("PIAPI_FLUX_KONTEXT_MODEL",  "Qubico/flux1-dev-advanced"),

    # Additional PiAPI T2I models verified against live PiAPI catalog 2026-05-20:
    # Qwen Image  — Alibaba's flagship T2I, strong on Chinese prompts ($0.015/img)
    # Z-Image     — Alibaba's fast/cheap T2I, Z-Image Turbo backend  ($0.004/img)
    # Both accept task_type="txt2img".
    "qwen_t2i":            os.environ.get("PIAPI_QWEN_T2I_MODEL",      "Qubico/qwen-image"),
    "z_image_t2i":         os.environ.get("PIAPI_Z_IMAGE_T2I_MODEL",   "Qubico/z-image"),

    # New PiAPI catalog models 2026-05-23 — verified end-to-end with real
    # generations that returned working image/video URLs. All are vendor-API
    # proxies (Google Gemini / ByteDance / Google Veo), not Qubico-hosted,
    # so latency + reliability tracks the vendor's own SLA, not PiAPI's
    # internal GPU pool. Dropped: Veo 3 (2× "too many requests" in probes),
    # Seedream 4.0 (not exposed on PiAPI), Nano Banana v1 (only v2/Pro live).
    "nano_banana_2_model":     os.environ.get("PIAPI_NANO_BANANA_2_MODEL",     "gemini"),
    "nano_banana_2_task":      os.environ.get("PIAPI_NANO_BANANA_2_TASK",      "nano-banana-2"),
    "nano_banana_pro_model":   os.environ.get("PIAPI_NANO_BANANA_PRO_MODEL",   "gemini"),
    "nano_banana_pro_task":    os.environ.get("PIAPI_NANO_BANANA_PRO_TASK",    "nano-banana-pro"),
    "seedream_5_lite_model":   os.environ.get("PIAPI_SEEDREAM_5_LITE_MODEL",   "seedream"),
    "seedream_5_lite_task":    os.environ.get("PIAPI_SEEDREAM_5_LITE_TASK",    "seedream-5-lite"),
    "veo_31_fast_model":       os.environ.get("PIAPI_VEO_31_FAST_MODEL",       "veo3.1"),
    "veo_31_fast_task":        os.environ.get("PIAPI_VEO_31_FAST_TASK",        "veo3.1-video-fast"),

    # Sora 2 Pro (2026-06-09 addition). PiAPI exposes OpenAI's Sora 2 / Sora 2
    # Pro through their proxy at piapi.ai/sora-2. Pro mode supports 720p/1080p
    # with variable 4-12s duration; we price the 5s 1080p output at 80 credits
    # (mirrors Veo 3.1) via the existing video_sora2 ServicePricing row.
    # When PiAPI renames the alias, override PIAPI_SORA2_MODEL / *_TASK without
    # rebuilding. If OpenAI shuts the underlying model down (announced EOL
    # 2026-09-24), flip the env override to point at a fallback alias.
    # 2026-06-12 fix: PiAPI rejected the original guesses ("sora" /
    # "sora-2-pro-video") with "invalid model" — Sora 2 Pro was broken since
    # launch. Verified against the live API: model="sora2" with task_type
    # "sora2-pro-video" (pro) / "sora2-video" (standard) pass validation.
    "sora2_model":             os.environ.get("PIAPI_SORA2_MODEL",             "sora2"),
    "sora2_task":              os.environ.get("PIAPI_SORA2_TASK",              "sora2-pro-video"),

    # Wan video (model="Wan"; version encoded in task_type)
    "wan_video":           os.environ.get("PIAPI_WAN_VIDEO_MODEL",     "Wan"),
    "wan_i2v_task":        os.environ.get("PIAPI_WAN_I2V_TASK",        "wan26-img2video"),
    "wan_t2v_task":        os.environ.get("PIAPI_WAN_T2V_TASK",        "wan26-txt2video"),

    # Image toolkit (background-remove, upscale)
    "image_toolkit":       os.environ.get("PIAPI_IMAGE_TOOLKIT_MODEL", "Qubico/image-toolkit"),

    # TTS
    "tts_f5":              os.environ.get("PIAPI_TTS_F5_MODEL",        "Qubico/tts"),
    "tts_openai":          os.environ.get("PIAPI_TTS_OPENAI_MODEL",    "tts-1"),

    # Midjourney (alias only; PiAPI auto-routes to current MJ version)
    "midjourney":          os.environ.get("PIAPI_MIDJOURNEY_MODEL",    "midjourney"),

    # ── New tier-based video models (2026-05-19 revision) ──
    # Picked from the SaaS tier table the owner approved:
    #   主力     Seedance 2.0 Fast      (default / best CP value)
    #   高階付費 Kling 3.0 / Omni       (premium)
    #   快速     Hailuo Fast            (cheapest + fastest)
    #   特色補充 Hunyuan                (中文 prompts + dynamic motion)
    #   利基     Wan 2.5/2.6, Veo 3.1  (specialty/high-end via PiAPI + Vertex)
    #
    # PiAPI is mandatory primary; Pollo (below) is the backup that mirrors
    # the same model family. Model IDs are env-overridable because PiAPI
    # has a history of renaming aliases without notice.
    # All four families' model/task strings were originally educated guesses
    # and ALL were rejected by PiAPI with "invalid model" / "invalid task type"
    # (verified 2026-05-22 via live probes). Updated to the values shown in
    # PiAPI's official docs + a working 200-response curl probe:
    #
    #   Seedance: model="seedance",      task_type="seedance-2-fast-preview"
    #             input.image_urls=[…]   (array, NOT image_url)
    #   Hailuo:   model="hailuo",        task_type="video_generation"
    #             input.model="i2v-01" or "t2v-01"  (NESTED variant id)
    #   Hunyuan:  model="Qubico/hunyuan", task_type="img2video-concat" / "txt2video"
    #   Wan:      model="Wan",           task_type="wan26-img2video" / "wan26-txt2video"
    #             input.image=…          (string, NOT image_url / image_urls)
    #
    # Per-family input-shape variance is handled in piapi_provider.image_to_video
    # / text_to_video — these env vars only carry the top-level model+task_type.
    "seedance_video":      os.environ.get("PIAPI_SEEDANCE_VIDEO_MODEL", "seedance"),
    "seedance_t2v_task":   os.environ.get("PIAPI_SEEDANCE_T2V_TASK",    "seedance-2-fast-preview"),
    "seedance_i2v_task":   os.environ.get("PIAPI_SEEDANCE_I2V_TASK",    "seedance-2-fast-preview"),
    "seedance_t2i_task":   os.environ.get("PIAPI_SEEDANCE_T2I_TASK",    "seedance2-txt2img"),  # T2I not exposed on PiAPI — placeholder

    "hailuo_video":        os.environ.get("PIAPI_HAILUO_VIDEO_MODEL",   "hailuo"),
    "hailuo_t2v_task":     os.environ.get("PIAPI_HAILUO_T2V_TASK",      "video_generation"),
    "hailuo_i2v_task":     os.environ.get("PIAPI_HAILUO_I2V_TASK",      "video_generation"),
    # Hailuo's nested input.model variants (t2v-01 / i2v-01 / s2v-01 / ...).
    # Override per environment if vendor changes the variant catalog.
    "hailuo_t2v_variant":  os.environ.get("PIAPI_HAILUO_T2V_VARIANT",   "t2v-01"),
    "hailuo_i2v_variant":  os.environ.get("PIAPI_HAILUO_I2V_VARIANT",   "i2v-01"),

    "hunyuan_video":       os.environ.get("PIAPI_HUNYUAN_VIDEO_MODEL",  "Qubico/hunyuan"),
    "hunyuan_t2v_task":    os.environ.get("PIAPI_HUNYUAN_T2V_TASK",     "txt2video"),
    "hunyuan_i2v_task":    os.environ.get("PIAPI_HUNYUAN_I2V_TASK",     "img2video-concat"),
    "hunyuan_t2i_task":    os.environ.get("PIAPI_HUNYUAN_T2I_TASK",     "hunyuan-txt2img"),  # T2I not exposed on PiAPI — placeholder
}


# Kling video_generation tasks accept a ``version`` field (1.5 / 1.6 / 2.1 /
# 2.1-master / 2.5 / 2.6 / 3.0). Try-on, avatar, lip_sync do NOT. Pin
# explicitly rather than relying on PiAPI's silent default so a vendor-side
# version bump never lands in prod without us deciding.
PIAPI_KLING_VERSIONS: Dict[str, str] = {
    "default":  os.environ.get("PIAPI_KLING_VIDEO_VERSION",          "2.6"),
    "flagship": os.environ.get("PIAPI_KLING_VIDEO_FLAGSHIP_VERSION", "2.1-master"),
    "omni":     os.environ.get("PIAPI_KLING_OMNI_VERSION",           "3.0"),
}


# Midjourney process_mode controls cost vs latency:
#   relax  — slowest / cheapest
#   fast   — balanced (recommended default)
#   turbo  — fastest / most expensive
PIAPI_MIDJOURNEY_PROCESS_MODE: str = os.environ.get(
    "PIAPI_MIDJOURNEY_PROCESS_MODE", "fast"
)


# ─────────────────────────────────────────────────────────────────────────
# Pollo
# ─────────────────────────────────────────────────────────────────────────
# Pollo's model field uses explicit version strings (``pixverse_v4.5``,
# ``pixverse_v5``, ``kling_v2`` …). The defaults below match the values
# previously hard-coded in providers/pollo_provider.py; bump them as new
# versions ship. (pollo_mcp_provider.py was deleted 2026-05-26.)
POLLO_MODELS: Dict[str, str] = {
    "pixverse_default": os.environ.get("POLLO_PIXVERSE_DEFAULT_MODEL", "pixverse_v4.5"),
    "pixverse_creative": os.environ.get("POLLO_PIXVERSE_CREATIVE_MODEL", "pixverse_v5"),
    "kling_video":       os.environ.get("POLLO_KLING_VIDEO_MODEL",      "kling_v2"),
    "mcp_default_video": os.environ.get("POLLO_MCP_DEFAULT_MODEL",      "pollo-v1-6"),
    # 2026-05-19 new tier — Pollo is the backup for PiAPI on these models.
    # Names match Pollo's endpoint slugs (verify against pollo.ai/docs when
    # the platform renames). All env-overridable for ops rotation.
    "seedance_default":  os.environ.get("POLLO_SEEDANCE_MODEL",         "seedance_v2"),
    "hailuo_default":    os.environ.get("POLLO_HAILUO_MODEL",           "hailuo_fast"),
    "hunyuan_default":   os.environ.get("POLLO_HUNYUAN_MODEL",          "hunyuan_v1"),
    "kling_omni":        os.environ.get("POLLO_KLING_OMNI_MODEL",       "kling_v3"),
    # Sora 2 (2026-06-09). Pollo's unified platform exposes OpenAI's Sora 2
    # at /generation/sora/sora-2 — our backup when PiAPI is rate-limited or
    # the upstream task fails. Slug is bare "sora-2" (Pollo doesn't expose a
    # separate "pro" SKU; quality is selected via request params).
    "sora2":             os.environ.get("POLLO_SORA2_MODEL",            "sora-2"),
}


def get(provider: str, key: str, fallback: str | None = None) -> str:
    """Convenience accessor used in places that prefer a single import."""
    table = {"piapi": PIAPI_MODELS, "pollo": POLLO_MODELS}.get(provider.lower())
    if table is None:
        raise KeyError(f"Unknown provider '{provider}'")
    if key not in table:
        if fallback is not None:
            return fallback
        raise KeyError(f"Unknown {provider} model key '{key}'")
    return table[key]
