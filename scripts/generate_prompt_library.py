#!/usr/bin/env python3
"""
Generate a curated prompt library for VidGo's prompt-driven tools.

Calls Gemini once per tool category and writes a single JSON file at
`frontend-vue/src/data/prompt_library.json`. The frontend ships this JSON as a
static asset; the prompt input UI becomes a locked dropdown sourced from this
file (no free-form user prompts in MVP).

Each tool entry:
{
  "tool_key": {
    "label_en": "...",
    "label_zh": "...",
    "prompts": [
      {"id": "ps_001", "en": "...", "zh": "..."},
      ...
    ]
  }
}

Usage:
  GOOGLE_CLOUD_PROJECT=vidgo-ai python3 scripts/generate_prompt_library.py
or:
  GEMINI_API_KEY=... python3 scripts/generate_prompt_library.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types as genai_types


REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "frontend-vue" / "src" / "data" / "prompt_library.json"

MODEL = os.getenv("GEMINI_MODEL_PROMPTGEN", "gemini-2.5-flash")
PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("VERTEX_AI_PROJECT") or "vidgo-ai"
LOCATION = os.getenv("VERTEX_AI_LOCATION", "us-central1")

# Per-tool spec: id_prefix, English label, Chinese label, generator instruction.
TOOLS: list[dict[str, str]] = [
    {
        "key": "product_scene",
        "id_prefix": "ps",
        "label_en": "Product Scene",
        "label_zh": "商品場景",
        "instruction": (
            "Write 22 distinct prompts for an AI image generator that places a "
            "real product onto a generated background. Each prompt should describe "
            "the SCENE / BACKGROUND ONLY (lighting, surface, environment, mood, "
            "props, camera angle), NOT the product itself. Cover diverse styles: "
            "studio, lifestyle, outdoor, holiday, seasonal, minimalist, "
            "luxurious, technological, natural, urban, kitchen, beach, dark "
            "moody, bright airy, festive. 18-35 English words each. Avoid "
            "explicit brand names. The Chinese version must be a faithful "
            "translation of the same scene, 25-50 Chinese characters."
        ),
    },
    {
        "key": "room_redesign",
        "id_prefix": "rr",
        "label_en": "Room Redesign",
        "label_zh": "房間重新設計",
        "instruction": (
            "Write 22 distinct prompts for an AI interior design tool that "
            "redesigns a real photo of a room. Each prompt names a STYLE + key "
            "design elements (palette, materials, lighting, furniture, mood). "
            "Cover Scandinavian, Japandi, Industrial, Mid-century modern, "
            "Bohemian, Coastal, Farmhouse, Art Deco, Minimalist, Maximalist, "
            "Cyberpunk, Wabi-sabi, Mediterranean, Traditional Chinese, "
            "Biophilic, Luxury, Rustic, French country, Loft, Tropical. "
            "20-40 English words each, 30-60 Chinese characters."
        ),
    },
    {
        "key": "short_video",
        "id_prefix": "sv",
        "label_en": "Short Video Effect",
        "label_zh": "短影片效果",
        "instruction": (
            "Write 22 distinct prompts for an AI image-to-video generator that "
            "animates a still product / scene image. Each prompt describes the "
            "MOTION + atmosphere (camera move, particles, lighting changes, "
            "subject animation, mood). Examples: cinematic dolly-in, slow "
            "rotation, sparkles falling, steam rising, zoom-out reveal, "
            "parallax, water ripples, light flicker, smoke swirl. 15-30 "
            "English words each, 20-45 Chinese characters."
        ),
    },
    {
        "key": "ai_avatar",
        "id_prefix": "av",
        "label_en": "AI Avatar Script",
        "label_zh": "AI 代言人腳本",
        "instruction": (
            "Write 22 distinct short scripts for an AI talking-avatar tool. "
            "Each script is what a virtual presenter would SAY to camera. Cover "
            "use cases: product launch, e-commerce promotion, customer service "
            "greeting, social-media hook, brand storytelling, holiday wish, "
            "tutorial intro, business announcement, livestream opener, thank-"
            "you message. 25-45 English words each (around 12 seconds of "
            "speech), 40-80 Chinese characters. Tone should be warm, "
            "professional, and brand-safe. No real person/brand names."
        ),
    },
    {
        "key": "pattern_generate",
        "id_prefix": "pg",
        "label_en": "Pattern Generate",
        "label_zh": "圖案生成",
        "instruction": (
            "Write 22 distinct prompts for an AI generator that creates "
            "seamless decorative patterns / textures suitable for textiles, "
            "wallpaper, packaging. Each prompt describes the MOTIF + color "
            "palette + style (geometric, floral, animal print, abstract, "
            "watercolor, vintage, art-nouveau, tropical, Scandinavian folk, "
            "Japanese washi, Moroccan tile, etc.). 15-30 English words, "
            "20-45 Chinese characters."
        ),
    },
]


SYSTEM_INSTRUCTION = (
    "You are a senior creative director writing prompt presets for VidGo, a "
    "Taiwan-focused premium e-commerce creative tool. Output STRICT JSON "
    "only — no markdown, no commentary. Each item must be a fresh idea, "
    "not a paraphrase. All Chinese must be Traditional Chinese (zh-TW).\n\n"
    "ANTI-HALLUCINATION RULES (apply to every prompt):\n"
    "  • Use concrete materials (oak, marble, linen, ceramic, terrazzo) — "
    "    NEVER vague adjectives ('beautiful', 'stunning', 'amazing').\n"
    "  • Specify lighting type + direction + color temperature (e.g. "
    "    '5500K softbox from upper-left 45°').\n"
    "  • Specify camera angle + distance (e.g. '3/4 front, eye-level, "
    "    medium shot').\n"
    "  • Use named or HEX color palettes — NEVER 'warm tones' alone.\n"
    "  • End every prompt with a preserve-target constraint: \n"
    "      product_scene → 'Keep the product's shape, label, color and "
    "        proportions identical to the input.'\n"
    "      room_redesign → 'Preserve the original walls, windows, doors "
    "        and ceiling height.'\n"
    "      short_video   → 'Keep the subject's shape, label and color "
    "        exactly the same; no morphing.'\n"
    "      pattern_generate → 'Seamless tile, no text or watermark.'\n"
    "  • Avoid copyrighted brand or person names.\n\n"
    "TAIWAN E-COMMERCE BIAS:\n"
    "  • Prefer realistic SMB scenes: skincare flat-lay, F&B / bubble tea / "
    "    tea, fashion accessories, lifestyle / home goods, electronics.\n"
    "  • Mix in TW seasonal contexts: Lunar New Year (red/gold), "
    "    Mid-Autumn (moon, osmanthus), Mother's Day (peony, soft pastel), "
    "    night-market warm bokeh.\n"
    "  • Skew interior styles toward Modern Minimalist, Japandi, Muji, "
    "    Korean modern, Log/Cabin warm wood, Modern Luxury — these are "
    "    the most-searched styles in TW residential."
)

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "prompts": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "en": {"type": "STRING"},
                    "zh": {"type": "STRING"},
                },
                "required": ["en", "zh"],
            },
        }
    },
    "required": ["prompts"],
}


def build_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        print(f"[init] Gemini API mode (key=***{api_key[-4:]})")
        return genai.Client(api_key=api_key)
    print(f"[init] Vertex AI mode (project={PROJECT}, location={LOCATION})")
    return genai.Client(vertexai=True, project=PROJECT, location=LOCATION)


def generate_for_tool(client: genai.Client, tool: dict[str, str]) -> list[dict[str, str]]:
    prompt_text = (
        f"{tool['instruction']}\n\n"
        "Return JSON of the form:\n"
        '{"prompts": [{"en": "...", "zh": "..."}, ...]}\n'
        "Exactly 22 items."
    )
    cfg = genai_types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=RESPONSE_SCHEMA,
        temperature=0.95,
        max_output_tokens=8192,
    )
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            resp = client.models.generate_content(
                model=MODEL, contents=prompt_text, config=cfg
            )
            text = resp.text or ""
            data = json.loads(text)
            items = data.get("prompts") or []
            cleaned: list[dict[str, str]] = []
            seen: set[str] = set()
            for i, raw in enumerate(items):
                en = (raw.get("en") or "").strip()
                zh = (raw.get("zh") or "").strip()
                if not en or not zh:
                    continue
                key = en.lower()
                if key in seen:
                    continue
                seen.add(key)
                cleaned.append(
                    {
                        "id": f"{tool['id_prefix']}_{i + 1:03d}",
                        "en": en,
                        "zh": zh,
                    }
                )
            if len(cleaned) >= 20:
                return cleaned[:22]
            raise RuntimeError(f"only {len(cleaned)} valid prompts (need >=20)")
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"  [retry {attempt + 1}/3] {e}")
            time.sleep(2 + attempt)
    raise RuntimeError(f"failed to generate prompts for {tool['key']}: {last_err}")


def main() -> int:
    client = build_client()
    library: dict[str, Any] = {
        "_meta": {
            "model": MODEL,
            "generated_at": int(time.time()),
            "version": str(uuid.uuid4())[:8],
            "note": "Auto-generated by scripts/generate_prompt_library.py — "
            "regenerate (do not hand-edit) if you want fresh prompts.",
        },
        "tools": {},
    }
    for tool in TOOLS:
        print(f"[gen] {tool['key']} ...")
        prompts = generate_for_tool(client, tool)
        library["tools"][tool["key"]] = {
            "label_en": tool["label_en"],
            "label_zh": tool["label_zh"],
            "prompts": prompts,
        }
        print(f"  -> {len(prompts)} prompts")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(library, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[done] wrote {OUT_PATH.relative_to(REPO_ROOT)}")
    total = sum(len(v["prompts"]) for v in library["tools"].values())
    print(f"[done] {len(library['tools'])} tools, {total} prompts total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
