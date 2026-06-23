"""Server-side prompt library + validation.

Loads the same JSON the frontend ships under `frontend-vue/src/data/`
(mirrored to `backend/app/data/prompt_library.json` so the file is part of
the Docker image). Endpoints look up a `prompt_id` here and use the
canonical EN/ZH text — never an arbitrary string the client passes in.

Why server-side: the frontend already locks the dropdown, but the API is
public. Without this lookup, a determined caller could still submit any
prompt by editing the request in DevTools or curl. With it, the backend
ignores any free-form text whenever a prompt_id resolves.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

LIBRARY_PATH = Path(__file__).resolve().parents[1] / "data" / "prompt_library.json"

# Tools that route through the curated library. Adding a new tool requires
# matching entries in prompt_library.json.
SUPPORTED_TOOLS = {
    "product_scene",
    "room_redesign",
    "short_video",
    "ai_avatar",
    "pattern_generate",
    # 2026-06-23 — added so the premium T2I (MidjourneyImagine) page can resolve
    # curated dropdown prompts server-side for the free-visitor demo path, and so
    # Kling-video presets validate. Backed by the synced prompt_library.json.
    "premium_image",
    "kling_video",
}


@lru_cache(maxsize=1)
def _load_library() -> dict:
    """Read the JSON once at process start; cached for the life of the process."""
    if not LIBRARY_PATH.exists():
        logger.error("prompt_library.json not found at %s", LIBRARY_PATH)
        return {"tools": {}}
    try:
        return json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.error("failed to parse prompt_library.json: %s", exc)
        return {"tools": {}}


def _normalize_locale(raw: Optional[str]) -> str:
    """Reduce any UI locale string to one of the two submission languages
    we actually pass to upstream models (en / zh). zh-* → zh; everything
    else → en. We do not localize prompts to ja / ko / es because the
    upstream image / video models perform unevenly outside en + zh.
    """
    if not raw:
        return "en"
    low = str(raw).lower()
    return "zh" if low.startswith("zh") else "en"


def lookup_prompt(
    tool_key: str,
    prompt_id: str,
    locale: Optional[str] = None,
) -> Optional[str]:
    """Return the canonical prompt text for a (tool_key, prompt_id) pair.

    Returns None when:
      • tool_key is not one of the curated tools
      • prompt_id does not exist in that tool's library
      • the entry is missing both en and zh text (corrupt library)
    """
    if tool_key not in SUPPORTED_TOOLS:
        return None

    lib = _load_library()
    entry = (lib.get("tools") or {}).get(tool_key)
    if not entry:
        return None

    lang = _normalize_locale(locale)
    for item in entry.get("prompts", []) or []:
        if item.get("id") == prompt_id:
            text = item.get(lang) or item.get("en") or item.get("zh")
            return text or None
    return None


def is_valid_prompt_id(tool_key: str, prompt_id: str) -> bool:
    return lookup_prompt(tool_key, prompt_id) is not None


def list_prompt_ids(tool_key: str) -> list[str]:
    lib = _load_library()
    entry = (lib.get("tools") or {}).get(tool_key)
    if not entry:
        return []
    return [p.get("id") for p in entry.get("prompts") or [] if p.get("id")]
