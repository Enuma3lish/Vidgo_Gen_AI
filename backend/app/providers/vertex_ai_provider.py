"""
Vertex AI Provider — GCP provider for Imagen (image) + Veo (video) generation.

Gemini text operations (moderation, interior design text) use the Gemini API
(AI Studio) when GEMINI_API_KEY is set, falling back to Vertex AI otherwise.
Imagen and Veo are Vertex AI-only and always require VERTEX_AI_PROJECT + ADC.

Capabilities:
  - Content moderation (Gemini API / Vertex AI Gemini)
  - Text-to-image / Image-to-image editing (Imagen on Vertex AI)
  - Interior design suggestions (Gemini API / Vertex AI Gemini + Imagen)
  - Background removal / Upscale (local rembg / PIL)
  - Material generation (Imagen on Vertex AI)
  - Text-to-video (Veo) — 3rd backup for video tasks
  - Image-to-video (Veo) — 3rd backup for video tasks

Auth:
  - Gemini text ops: GEMINI_API_KEY (preferred) or ADC
  - Imagen / Veo: Google ADC (service account in GCP, gcloud ADC locally)

Env vars:
  - GEMINI_API_KEY: Gemini API key (for moderation / text, preferred)
  - GEMINI_MODEL: Gemini model, default "gemini-2.5-pro"
  - VERTEX_AI_PROJECT: GCP project ID (required for Imagen/Veo)
  - VERTEX_AI_LOCATION: Region, default "us-central1"
  - VEO_MODEL: Veo model name, default "veo-3.0-generate-preview"
  - GEMINI_IMAGE_MODEL: Gemini image model, default "gemini-2.5-flash-image"
"""
import asyncio
import base64
import io
import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.providers.base import BaseProvider

logger = logging.getLogger(__name__)

# Polling config for Veo long-running operations
VEO_POLL_INTERVAL = 10
VEO_POLL_MAX_ATTEMPTS = 60  # 10 minutes max


class VertexAIProvider(BaseProvider):
    """
    Vertex AI Provider — GCP-native Gemini + Veo.

    Uses the google-genai SDK (unified) for Gemini tasks and
    REST API for Veo video generation (long-running operations).
    """

    name = "vertex_ai"

    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.project = os.getenv("VERTEX_AI_PROJECT", "")
        self.location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
        # Imagen and Veo are only available in us-central1.
        self.image_location = os.getenv("VERTEX_AI_IMAGE_LOCATION", "us-central1")
        self.video_location = os.getenv("VEO_LOCATION", "us-central1")
        # Default to Veo 2 GA; set VEO_MODEL=veo-3.0-generate-preview when your project has access.
        self.veo_model = os.getenv("VEO_MODEL", "veo-2.0-generate-001")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
        self.gemini_image_model = os.getenv(
            "GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image"
        )
        self.imagen_model = os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-002")
        self.imagen_edit_model = os.getenv("IMAGEN_EDIT_MODEL", "imagen-3.0-capability-001")

        if not self.gemini_api_key and not self.project:
            logger.warning("Neither GEMINI_API_KEY nor VERTEX_AI_PROJECT set — provider degraded")
        elif not self.project:
            logger.info("[VertexAI] GEMINI_API_KEY set — text ops via Gemini API; Imagen/Veo disabled (no VERTEX_AI_PROJECT)")

        self._client: Optional[httpx.AsyncClient] = None
        self._gemini_text_client = None    # API-key preferred — text + multimodal Gemini
        self._gemini_image_client = None   # API-key preferred — gemini-2.5-flash-image
        self._genai_client = None          # Vertex AI genai — generic fallback
        self._genai_image_client = None    # Vertex AI (us-central1) — Imagen only

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client

    async def _get_access_token(self) -> str:
        """Get OAuth2 access token from ADC."""
        import google.auth
        import google.auth.transport.requests

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        credentials.refresh(google.auth.transport.requests.Request())
        return credentials.token

    def _get_gemini_text_client(self):
        """Gemini text/moderation client — prefer Gemini API key (Developer
        API) when available, fall back to Vertex AI ADC.

        Why API key first now: the Secret Manager value was rotated
        (v15) so the API path is healthy again. Going direct via
        ``generativelanguage.googleapis.com`` skips ADC token resolution
        and Vertex's region pinning entirely — gemini-2.5-pro /
        gemini-2.5-flash are available on the API in every region, which
        also unblocks local dev outside GCP. Vertex stays as the
        fallback so Cloud Run keeps working if the key is ever revoked
        again or if AI Studio quota throttles.

        Imagen + Veo paths are unaffected — those still call
        ``_get_genai_image_client`` which we keep Vertex-only because
        those models aren't published on the Gemini Developer API.
        """
        if self._gemini_text_client is None:
            from google import genai

            if self.gemini_api_key:
                self._gemini_text_client = genai.Client(api_key=self.gemini_api_key)
                logger.info("[VertexAI] Gemini text ops via Gemini API key")
            elif self.project:
                self._gemini_text_client = genai.Client(
                    vertexai=True,
                    project=self.project,
                    location=self.image_location,
                )
                logger.info(
                    "[VertexAI] Gemini text ops via Vertex AI ADC fallback (project=%s region=%s)",
                    self.project,
                    self.image_location,
                )
            else:
                raise RuntimeError("No GEMINI_API_KEY or VERTEX_AI_PROJECT configured")
        return self._gemini_text_client

    def _get_genai_client(self):
        """Vertex AI genai client — used as fallback for text ops and for Imagen."""
        if self._genai_client is None:
            from google import genai

            self._genai_client = genai.Client(
                vertexai=True,
                project=self.project,
                location=self.location,
            )
        return self._genai_client

    def _get_genai_image_client(self):
        """Vertex AI genai client pinned to us-central1 for IMAGEN image
        generation. Imagen models (imagen-3.0-generate-002,
        imagen-3.0-capability-001) are not published on the Gemini
        Developer API, so this client must stay Vertex-only.

        Gemini Flash Image (gemini-2.5-flash-image) — which IS available
        on the Developer API — should use ``_get_gemini_image_client``
        instead so production traffic goes direct via api key, faster
        and region-agnostic, falling back to Vertex only if the key is
        unset or revoked.
        """
        if self._genai_image_client is None:
            from google import genai

            self._genai_image_client = genai.Client(
                vertexai=True,
                project=self.project,
                location=self.image_location,
            )
        return self._genai_image_client

    def _get_gemini_image_client(self):
        """Gemini Flash Image client — API key preferred, Vertex fallback.

        gemini-2.5-flash-image is available on both the Gemini Developer
        API and Vertex AI. Production prefers the API key path for the
        same reasons as the text client (no region pin, faster auth,
        works in local dev). Vertex stays as the fallback when the key
        is unset / revoked. Used by ``regenerate_hero_pair`` and any
        future code that calls gemini-2.5-flash-image.
        """
        if self._gemini_image_client is None:
            from google import genai

            if self.gemini_api_key:
                self._gemini_image_client = genai.Client(api_key=self.gemini_api_key)
                logger.info("[VertexAI] Gemini Flash Image via Gemini API key")
            elif self.project:
                self._gemini_image_client = genai.Client(
                    vertexai=True,
                    project=self.project,
                    location=self.image_location,
                )
                logger.info(
                    "[VertexAI] Gemini Flash Image via Vertex AI fallback (region=%s)",
                    self.image_location,
                )
            else:
                raise RuntimeError("No GEMINI_API_KEY or VERTEX_AI_PROJECT configured")
        return self._gemini_image_client

    async def health_check(self) -> bool:
        if not self.gemini_api_key and not self.project:
            return False
        try:
            if self.gemini_api_key:
                # Quick connectivity check via Gemini API
                client = self._get_gemini_text_client()
                return client is not None
            else:
                token = await self._get_access_token()
                return bool(token)
        except Exception as e:
            logger.error(f"[VertexAI] Health check failed: {e}")
            return False

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ─────────────────────────────────────────────────────────────────────────
    # GEMINI — CONTENT MODERATION
    # ─────────────────────────────────────────────────────────────────────────

    async def moderate_content(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check content for moderation issues using Gemini on Vertex AI.

        Args:
            params: {
                "text": str (optional),
                "image_url": str (optional),
                "image_base64": str (optional)
            }
        """
        self._log_request("moderate_content", params)

        client = self._get_gemini_text_client()
        from google.genai import types

        parts = []
        parts.append(
            """Analyze this content for safety. Rate each category from 0.0 (safe) to 1.0 (unsafe):
- nsfw: Adult or sexual content
- violence: Violent or graphic content
- hate: Hate speech or discrimination
- self_harm: Self-harm or suicide content
- illegal: Illegal activities

Respond ONLY with JSON: {"nsfw": 0.0, "violence": 0.0, "hate": 0.0, "self_harm": 0.0, "illegal": 0.0, "is_safe": true}"""
        )

        if params.get("text"):
            parts.append(f"Content to analyze: {params['text']}")

        if params.get("image_base64"):
            parts.append(
                types.Part.from_bytes(
                    data=base64.b64decode(params["image_base64"]),
                    mime_type="image/jpeg",
                )
            )
        elif params.get("image_url"):
            try:
                http = self._get_http_client()
                img_resp = await http.get(params["image_url"])
                parts.append(
                    types.Part.from_bytes(data=img_resp.content, mime_type="image/jpeg")
                )
            except Exception as e:
                logger.error(f"[VertexAI] Failed to fetch image for moderation: {e}")

        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self.gemini_model,
                contents=parts,
                config=types.GenerateContentConfig(
                    temperature=0.1, max_output_tokens=256
                ),
            )

            text_response = response.text or ""
            json_match = re.search(r"\{[^}]+\}", text_response)
            if json_match:
                result = json.loads(json_match.group())
                is_safe = all(v < 0.5 for k, v in result.items() if k != "is_safe")
                result["is_safe"] = is_safe
                return {"success": True, **result}

            return {"success": True, "is_safe": True, "categories": {}}
        except Exception as e:
            logger.error(f"[VertexAI] Moderation failed: {e}")
            return {"success": False, "is_safe": True, "error": str(e)}

    # ─────────────────────────────────────────────────────────────────────────
    # IMAGEN — IMAGE EDITING / STYLE TRANSFER
    # ─────────────────────────────────────────────────────────────────────────

    async def edit_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Edit/style-transfer image using Imagen on Vertex AI.

        Uses imagen-3.0-capability-001 with edit_image API.

        Args:
            params: {"image_url": str, "prompt": str}
        """
        self._log_request("edit_image", params)

        try:
            client = self._get_genai_image_client()
            from google.genai import types

            http = self._get_http_client()
            img_resp = await http.get(params["image_url"])
            if img_resp.status_code != 200:
                raise Exception(f"Failed to fetch image: HTTP {img_resp.status_code}")

            prompt = f"Transform this image: {params['prompt']}"

            raw_ref = types.RawReferenceImage(
                reference_id=1,
                reference_image=types.Image(
                    image_bytes=img_resp.content,
                ),
            )

            response = await asyncio.to_thread(
                client.models.edit_image,
                model=self.imagen_edit_model,
                prompt=prompt,
                reference_images=[raw_ref],
                config=types.EditImageConfig(
                    number_of_images=1,
                    output_mime_type="image/png",
                ),
            )

            if response.generated_images:
                from PIL import Image

                img_data = response.generated_images[0].image.image_bytes
                output_dir = Path("/app/static/generated")
                output_dir.mkdir(parents=True, exist_ok=True)
                filename = f"vertex_{uuid.uuid4().hex[:8]}.png"
                filepath = output_dir / filename
                gen_img = Image.open(io.BytesIO(img_data))
                gen_img.save(filepath)
                local_url = f"/static/generated/{filename}"
                self._log_response("edit_image", True)
                return {"success": True, "output": {"image_url": local_url}}

            raise Exception("No image in Imagen edit response")
        except Exception as e:
            logger.error(f"[VertexAI] Image editing failed: {e}")
            self._log_response("edit_image", False, str(e))
            return {"success": False, "error": str(e)}

    # ─────────────────────────────────────────────────────────────────────────
    # GEMINI — TEXT-TO-IMAGE
    # ─────────────────────────────────────────────────────────────────────────

    async def text_to_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate image from text using Imagen on Vertex AI."""
        self._log_request("text_to_image", params)

        try:
            client = self._get_genai_image_client()
            from google.genai import types

            prompt = params["prompt"]
            if params.get("negative_prompt"):
                prompt = f"{prompt}. Avoid: {params['negative_prompt']}"

            aspect_ratio = params.get("aspect_ratio") or "1:1"
            response = await asyncio.to_thread(
                client.models.generate_images,
                model=self.imagen_model,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=aspect_ratio,
                    output_mime_type="image/png",
                ),
            )

            if response.generated_images:
                img_data = response.generated_images[0].image.image_bytes
                from PIL import Image

                output_dir = Path("/app/static/generated")
                output_dir.mkdir(parents=True, exist_ok=True)
                filename = f"vertex_{uuid.uuid4().hex[:8]}.png"
                filepath = output_dir / filename
                gen_img = Image.open(io.BytesIO(img_data))
                gen_img.save(filepath)
                local_url = f"/static/generated/{filename}"
                self._log_response("text_to_image", True)
                return {"success": True, "output": {"image_url": local_url}}

            raise Exception("No image in Imagen response")
        except Exception as e:
            logger.error(f"[VertexAI] Text-to-image failed: {e}")
            return {"success": False, "error": str(e)}

    async def image_to_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Transform image using Gemini on Vertex AI."""
        self._log_request("image_to_image", params)

        prompt = params["prompt"]
        if params.get("negative_prompt"):
            prompt = f"{prompt}. Avoid: {params['negative_prompt']}"

        strength = params.get("strength", 0.75)
        instruction = "Transform this image completely into:" if strength > 0.5 else "Make subtle adjustments to this image:"
        return await self.edit_image({
            "image_url": params["image_url"],
            "prompt": f"{instruction} {prompt}. Strength: {strength}.",
        })

    async def regenerate_hero_pair(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Re-render a hero demo AFTER image from its curated BEFORE.

        Used by /api/v1/admin/hero/regenerate to populate / refresh the
        ``hero_demo_pairs`` table. The whole point of this path versus a
        generic image_to_image call is that we want the AFTER to be the
        SAME subject (cup, room, garment, model) placed in a transformed
        scene — never a re-invented product. Routes through
        ``gemini-2.5-flash-image`` (the same model image-translator
        switched to) because it can read the input image's subject
        silhouette and render it back in a new context, where
        Imagen-edit and Flux-derive_image cannot.

        Args:
            params: {
                "image_url": str,   # BEFORE — curated GCS URL
                "prompt": str,      # full scene/style prompt with the
                                    # "preserve subject EXACTLY" clauses
                "tool_type": str,   # used only for the GCS blob name
                "slug": str,        # used only for the GCS blob name
            }
        """
        self._log_request("regenerate_hero_pair", params)
        try:
            # gemini-2.5-flash-image is available on the Gemini Developer
            # API — prefer the API-key client for lower latency / no
            # region pin. Falls back to Vertex when the key is unset.
            client = self._get_gemini_image_client()
            from google.genai import types

            http = self._get_http_client()
            img_resp = await http.get(params["image_url"])
            if img_resp.status_code != 200:
                raise Exception(f"Failed to fetch BEFORE image: HTTP {img_resp.status_code}")
            mime = img_resp.headers.get("content-type", "image/png").split(";")[0].strip()
            if mime not in {"image/jpeg", "image/png", "image/webp"}:
                mime = "image/png"

            parts = [
                types.Part.from_bytes(data=img_resp.content, mime_type=mime),
                params["prompt"],
            ]
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self.gemini_image_model,
                contents=parts,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )

            image_bytes: Optional[bytes] = None
            for candidate in getattr(response, "candidates", None) or []:
                content = getattr(candidate, "content", None)
                for part in getattr(content, "parts", None) or []:
                    inline = getattr(part, "inline_data", None)
                    data = getattr(inline, "data", None) if inline else None
                    if data:
                        image_bytes = data
                        break
                if image_bytes:
                    break

            if not image_bytes:
                raise Exception("Gemini hero regen returned no inline image data")

            from app.services.gcs_storage_service import get_gcs_storage

            gcs = get_gcs_storage()
            tool = (params.get("tool_type") or "hero").lower()
            slug = (params.get("slug") or "default").lower()
            filename = f"hero_{tool}_{slug}_{uuid.uuid4().hex[:8]}.png"
            blob_name = f"examples/hero/generated/{filename}"
            if gcs.enabled:
                result_url = gcs.upload_public(
                    data=image_bytes,
                    blob_name=blob_name,
                    content_type="image/png",
                )
            else:
                output_dir = Path("/app/static/generated/hero")
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / filename).write_bytes(image_bytes)
                result_url = f"/static/generated/hero/{filename}"

            self._log_response("regenerate_hero_pair", True)
            return {"success": True, "output": {"image_url": result_url}}
        except Exception as e:
            logger.error(f"[VertexAI] regenerate_hero_pair failed: {e}")
            self._log_response("regenerate_hero_pair", False, str(e))
            return {"success": False, "error": str(e)}

    async def translate_image_text(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """In-place image text translation via Gemini 2.5 Flash Image.

        Gemini 2.5 Flash Image (a.k.a. "nano banana") is the only model in
        our stack that can read source text from an image and re-render the
        same image with the text replaced by a translation while preserving
        layout, typography, product photography, faces, and colors. Imagen
        edit / Flux derive_image both repaint the text as decorative noise.

        Args:
            params: {
                "image_url": str,
                "target_language": str,
                "source_language": str | None,
                "instructions": str | None,
            }
        """
        self._log_request("translate_image_text", params)
        try:
            text_client = self._get_gemini_text_client()
            http = self._get_http_client()
            img_resp = await http.get(params["image_url"])
            if img_resp.status_code != 200:
                raise Exception(f"Failed to fetch image: HTTP {img_resp.status_code}")
            mime = img_resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            if mime not in {"image/jpeg", "image/png", "image/webp"}:
                mime = "image/jpeg"

            target_language = params.get("target_language") or "English"
            source_language = params.get("source_language")

            # ── Deterministic CJK-safe path ────────────────────────────────
            # Gemini 2.5 Flash Image renders CJK glyphs as visual shape-
            # matched decoration (not real characters) even when handed the
            # exact target string. We side-step that by extracting OCR +
            # bounding boxes via the text model, then rendering with PIL +
            # NotoSans CJK so every glyph is literally drawn correctly.
            from app.services.image_translator_service import translate_image_pil

            image_bytes = await translate_image_pil(
                text_client=text_client,
                text_model=self.gemini_model,
                img_bytes=img_resp.content,
                mime=mime,
                target_language=target_language,
                source_language=source_language,
            )

            from app.services.gcs_storage_service import get_gcs_storage

            gcs = get_gcs_storage()
            filename = f"translated_{uuid.uuid4().hex[:12]}.png"
            if gcs.enabled:
                result_url = gcs.upload_public(
                    data=image_bytes,
                    blob_name=f"generated/image/{filename}",
                    content_type="image/png",
                )
            else:
                output_dir = Path("/app/static/generated")
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / filename).write_bytes(image_bytes)
                result_url = f"/static/generated/{filename}"

            self._log_response("translate_image_text", True)
            return {"success": True, "output": {"image_url": result_url}}
        except Exception as e:
            logger.error(f"[VertexAI] translate_image_text failed: {e}")
            self._log_response("translate_image_text", False, str(e))
            return {"success": False, "error": str(e)}

    async def _legacy_translate_image_text_unused(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Original two-pass generative path. Kept for diff history only —
        not wired into the router. Remove once the PIL path has shipped a
        full week without regression."""
        try:
            from google.genai import types
            client = self._get_genai_image_client()
            text_client = self._get_gemini_text_client()
            http = self._get_http_client()
            img_resp = await http.get(params["image_url"])
            mime = img_resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            target_language = params.get("target_language") or "English"
            source_language = params.get("source_language")
            extra = (params.get("instructions") or "").strip()
            source_hint = f" from {source_language}" if source_language else ""

            # ── PASS 1: OCR + translate via Gemini TEXT model ──────────────
            #
            # gemini-2.5-flash-image is great at re-rendering an image with
            # changed text WHEN you tell it exactly what text to render —
            # but if you only ask "translate the text", it falls back to
            # hallucinating glyph SHAPES that look like the target script.
            # For CJK / Arabic / Thai this produces semantically garbage
            # output ("夆 专 偂 諭 石 折 復 惠" instead of "夏季特賣 五折優惠").
            #
            # So we first have the text model OCR the source text, produce
            # a real translation, and emit a JSON map of source→translated
            # phrases that the image model can use as a literal stencil.
            ocr_prompt = (
                "Extract every distinct piece of visible text in this image"
                f"{source_hint}, then translate each piece into {target_language}. "
                "Treat each visually-separated text block (line, label, sticker, "
                "price tag) as one item. Keep brand names, URLs, prices, numbers, "
                "and currency symbols unchanged unless they're normal words that "
                "must be localized. Return ONLY a JSON array of objects with this "
                "exact shape:\n"
                '  [{"source": "<original text>", "translated": "<target-language text>"}, ...]\n'
                "No prose, no markdown fences, no extra keys. If the image has no "
                "text, return []."
            )
            ocr_response = await asyncio.to_thread(
                text_client.models.generate_content,
                model=self.gemini_model,
                contents=[
                    types.Part.from_bytes(data=img_resp.content, mime_type=mime),
                    ocr_prompt,
                ],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=2048,
                    response_mime_type="application/json",
                ),
            )

            translation_map: list[Dict[str, str]] = []
            try:
                raw_text = (ocr_response.text or "").strip()
                # Strip markdown code fences if Gemini added them despite
                # the response_mime_type hint.
                if raw_text.startswith("```"):
                    raw_text = raw_text.strip("`")
                    if raw_text.startswith("json"):
                        raw_text = raw_text[4:].lstrip()
                parsed = json.loads(raw_text or "[]")
                if isinstance(parsed, list):
                    for entry in parsed:
                        if isinstance(entry, dict):
                            src = str(entry.get("source") or "").strip()
                            tgt = str(entry.get("translated") or "").strip()
                            if src and tgt:
                                translation_map.append({"source": src, "translated": tgt})
            except Exception as parse_exc:
                logger.warning("[VertexAI] OCR JSON parse failed (%s); falling back to inline-prompt path", parse_exc)
                translation_map = []

            # ── PASS 2: render the image with the precise translations ───
            #
            # Tell the image model EXACTLY which source string maps to which
            # target string. The model now does pure glyph rendering, not
            # translation guessing, so CJK / Arabic / Thai come out correct.
            mappings_block = ""
            if translation_map:
                mappings_lines = [
                    f'  "{m["source"]}" -> "{m["translated"]}"' for m in translation_map[:30]
                ]
                mappings_block = (
                    "Use this exact translation map. Replace each source phrase "
                    "with the EXACT translated phrase given here — do not paraphrase, "
                    "do not invent new characters, do not add or drop words:\n"
                    + "\n".join(mappings_lines)
                    + "\n\n"
                )
            extra_clause = f" Additional instructions: {extra}." if extra else ""

            render_prompt = (
                f"Re-render this image with every visible text element replaced "
                f"by its {target_language} translation. "
                f"{mappings_block}"
                "Place each translated phrase at the same position, same line "
                "break structure, same typography weight, same color, and inside "
                "the same signage / packaging / card / poster boundary as the "
                "original. Preserve the product, model, faces, hands, logos, "
                "photography, and background EXACTLY as they appear. Keep brand "
                "names, URLs, prices, numbers, currency symbols, and logos "
                "unchanged unless the map above explicitly translates them. Do "
                "not add new objects, captions, watermarks, signatures, or "
                "decorative text. Do not change any layer of the image except "
                "the text glyphs themselves. Return a clean, commercial-quality, "
                "photoreal localized image."
                f"{extra_clause}"
            )

            parts = [
                types.Part.from_bytes(data=img_resp.content, mime_type=mime),
                render_prompt,
            ]
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self.gemini_image_model,
                contents=parts,
                config=types.GenerateContentConfig(
                    temperature=0.15,
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )

            image_bytes: Optional[bytes] = None
            for candidate in getattr(response, "candidates", None) or []:
                content = getattr(candidate, "content", None)
                for part in getattr(content, "parts", None) or []:
                    inline = getattr(part, "inline_data", None)
                    data = getattr(inline, "data", None) if inline else None
                    if data:
                        image_bytes = data
                        break
                if image_bytes:
                    break

            if not image_bytes:
                raise Exception("Gemini image edit returned no inline image data")

            from app.services.gcs_storage_service import get_gcs_storage

            gcs = get_gcs_storage()
            filename = f"translated_{uuid.uuid4().hex[:12]}.png"
            if gcs.enabled:
                result_url = gcs.upload_public(
                    data=image_bytes,
                    blob_name=f"generated/image/{filename}",
                    content_type="image/png",
                )
            else:
                output_dir = Path("/app/static/generated")
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / filename).write_bytes(image_bytes)
                result_url = f"/static/generated/{filename}"

            self._log_response("translate_image_text", True)
            return {"success": True, "output": {"image_url": result_url}}
        except Exception as e:
            logger.error(f"[VertexAI] translate_image_text failed: {e}")
            self._log_response("translate_image_text", False, str(e))
            return {"success": False, "error": str(e)}

    # ─────────────────────────────────────────────────────────────────────────
    # GEMINI — INTERIOR DESIGN
    # ─────────────────────────────────────────────────────────────────────────

    async def doodle_interior(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate interior design from image using Gemini on Vertex AI."""
        self._log_request("doodle_interior", params)

        style = params.get("style", "modern")
        room_type = params.get("room_type", "living room")
        prompt = params.get("prompt", "")
        # Hard constraint suffix: users were reporting people, pets, and
        # invented furniture in kitchen / living-room outputs. The frontend
        # also adds these instructions but we duplicate at the provider
        # level so direct API consumers and prompt-refinement rewrites
        # cannot strip them.
        INTERIOR_CONSTRAINTS = (
            "No people, no humans, no faces, no hands, no pets. "
            "Preserve the original walls, windows, doors, ceiling height, "
            "and overall room footprint. Empty interior staged only with "
            "furniture, decor, and lighting. Photorealistic real-estate "
            "interior photography, sharp focus, balanced exposure."
        )
        full_prompt = (
            f"Transform this room into a {style} {room_type} interior design. "
            f"{prompt} {INTERIOR_CONSTRAINTS}"
        )

        try:
            result = await self.edit_image({
                "image_url": params["image_url"],
                "prompt": full_prompt,
            })
            if result.get("success"):
                text_desc = await self._interior_text_description(params)
                if text_desc:
                    result["output"]["description"] = text_desc
                return result
            return await self._interior_text_only(params)
        except Exception as e:
            logger.error(f"[VertexAI] doodle_interior failed: {e}")
            return await self._interior_text_only(params)

    async def _interior_text_description(self, params: Dict[str, Any]) -> Optional[str]:
        """Get text description for interior design."""
        try:
            client = self._get_gemini_text_client()
            from google.genai import types

            style = params.get("style", "modern")
            room_type = params.get("room_type", "living room")

            parts = []
            if params.get("image_url"):
                http = self._get_http_client()
                img_resp = await http.get(params["image_url"])
                parts.append(
                    types.Part.from_bytes(data=img_resp.content, mime_type="image/jpeg")
                )

            parts.append(
                f"As an interior design expert, describe a {style} {room_type} redesign. "
                f"Include furniture, colors, materials, lighting. Be specific and concise."
            )

            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self.gemini_model,
                contents=parts,
                config=types.GenerateContentConfig(
                    temperature=0.7, max_output_tokens=512
                ),
            )
            return response.text
        except Exception:
            return None

    async def _interior_text_only(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback: text-only interior design description."""
        desc = await self._interior_text_description(params)
        return {
            "success": True,
            "output": {
                "description": desc or "Interior design description unavailable.",
                "suggestions": [],
                "is_text_only": True,
            },
        }

    # ─────────────────────────────────────────────────────────────────────────
    # GEMINI — BACKGROUND REMOVAL / UPSCALE
    # ─────────────────────────────────────────────────────────────────────────

    async def background_removal(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Imagen edit does not produce a clean alpha cutout — the primary PiAPI
        # path already uses local rembg. Mirror that here so the fallback
        # actually produces a segmented result instead of a near-identical RGB.
        self._log_request("background_removal", params)
        try:
            from rembg import remove
            from PIL import Image

            image_url = params["image_url"]
            if image_url.startswith("/"):
                image_data = Path("/app" + image_url).read_bytes()
            else:
                http = self._get_http_client()
                img_resp = await http.get(image_url)
                if img_resp.status_code != 200:
                    raise Exception(f"Failed to fetch image: HTTP {img_resp.status_code}")
                image_data = img_resp.content

            loop = asyncio.get_event_loop()
            output_bytes = await loop.run_in_executor(None, remove, image_data)

            from app.services.gcs_storage_service import get_gcs_storage
            gcs = get_gcs_storage()
            filename = f"rembg_{uuid.uuid4().hex[:8]}.png"
            if gcs.enabled:
                result_url = gcs.upload_public(
                    output_bytes,
                    f"generated/background_removal/{filename}",
                    content_type="image/png",
                )
            else:
                output_dir = Path("/app/static/generated")
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / filename).write_bytes(output_bytes)
                result_url = f"/static/generated/{filename}"

            self._log_response("background_removal", True)
            return {"success": True, "output": {"image_url": result_url}}
        except Exception as e:
            logger.error(f"[VertexAI] Background removal failed: {e}")
            return {"success": False, "error": str(e)}

    async def upscale(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Imagen edit refuses pure upscale prompts and returns empty responses.
        # Use deterministic PIL Lanczos so the fallback is guaranteed to succeed
        # when PiAPI is unavailable — real pixels at scale beats a hard failure.
        self._log_request("upscale", params)
        try:
            scale = int(params.get("scale", 2))
            scale = max(2, min(scale, 4))

            image_url = params["image_url"]
            if image_url.startswith("/"):
                img_bytes = Path("/app" + image_url).read_bytes()
            else:
                http = self._get_http_client()
                img_resp = await http.get(image_url)
                if img_resp.status_code != 200:
                    raise Exception(f"Failed to fetch image: HTTP {img_resp.status_code}")
                img_bytes = img_resp.content

            from PIL import Image
            src = Image.open(io.BytesIO(img_bytes))
            upscaled = src.resize(
                (src.width * scale, src.height * scale),
                Image.Resampling.LANCZOS,
            )
            buf = io.BytesIO()
            upscaled.save(buf, "PNG")
            out_bytes = buf.getvalue()

            from app.services.gcs_storage_service import get_gcs_storage
            gcs = get_gcs_storage()
            filename = f"upscale_{uuid.uuid4().hex[:8]}.png"
            if gcs.enabled:
                result_url = gcs.upload_public(
                    out_bytes,
                    f"generated/image/{filename}",
                    content_type="image/png",
                )
            else:
                output_dir = Path("/app/static/generated")
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / filename).write_bytes(out_bytes)
                result_url = f"/static/generated/{filename}"

            self._log_response("upscale", True)
            return {"success": True, "output": {"image_url": result_url}}
        except Exception as e:
            logger.error(f"[VertexAI] Upscale failed: {e}")
            return {"success": False, "error": str(e)}

    # ─────────────────────────────────────────────────────────────────────────
    # GEMINI — MATERIAL GENERATION
    # ─────────────────────────────────────────────────────────────────────────

    async def generate_material(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate material images for demos."""
        self._log_request("generate_material", params)
        return await self.text_to_image({
            "prompt": params["prompt"],
            "size": "1024*1024",
        })

    # ─────────────────────────────────────────────────────────────────────────
    # VEO — VIDEO GENERATION (3rd backup)
    # ─────────────────────────────────────────────────────────────────────────

    async def text_to_video(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate video from text using Veo on Vertex AI.

        Uses the Vertex AI predict API with long-running operation polling.
        Returns `{"success": False, "error": ...}` on provider-side failures
        (model-not-available 404, quota 429, timeout, bad response shape) so
        upstream callers can degrade gracefully instead of crashing a batch.

        Args:
            params: {
                "prompt": str (required),
                "duration": int (optional, 4/6/8, default 6),
                "aspect_ratio": str (optional, "16:9"|"9:16", default "16:9"),
                "resolution": str (optional, "720p"|"1080p", default "720p"),
            }
        """
        self._log_request("text_to_video", params)

        duration = params.get("duration", 6)
        # Veo supports 4, 6, or 8 seconds
        if duration not in (4, 6, 8):
            duration = min((4, 6, 8), key=lambda x: abs(x - duration))

        aspect_ratio = params.get("aspect_ratio", "16:9")

        request_body = {
            "instances": [
                {
                    "prompt": params["prompt"],
                }
            ],
            "parameters": {
                "aspectRatio": aspect_ratio,
                "durationSeconds": duration,
                "sampleCount": 1,
            },
        }

        try:
            return await self._veo_generate(request_body)
        except Exception as e:
            logger.error(f"[VertexAI:Veo] text_to_video failed: {e}")
            return {"success": False, "error": str(e)}

    async def image_to_video(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate video from image using Veo on Vertex AI.

        Args:
            params: {
                "image_url": str (required),
                "prompt": str (optional),
                "duration": int (optional, 4/6/8, default 6),
                "aspect_ratio": str (optional, default "16:9"),
            }
        """
        self._log_request("image_to_video", params)

        # Fetch image and encode as base64
        http = self._get_http_client()
        img_resp = await http.get(params["image_url"])
        if img_resp.status_code != 200:
            raise Exception(f"Failed to fetch image: HTTP {img_resp.status_code}")
        image_b64 = base64.b64encode(img_resp.content).decode()
        # Veo I2V expects `mimeType` alongside `bytesBase64Encoded` — it is
        # marked required in the public schema and Veo 3 rejects payloads
        # without it (HTTP 400 "image.mimeType is required").
        content_type = img_resp.headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type not in {"image/jpeg", "image/png", "image/webp"}:
            content_type = "image/jpeg"

        duration = params.get("duration", 6)
        if duration not in (4, 6, 8):
            duration = min((4, 6, 8), key=lambda x: abs(x - duration))

        instance: Dict[str, Any] = {
            "image": {
                "bytesBase64Encoded": image_b64,
                "mimeType": content_type,
            },
        }
        if params.get("prompt"):
            instance["prompt"] = params["prompt"]

        request_body = {
            "instances": [instance],
            "parameters": {
                "aspectRatio": params.get("aspect_ratio", "16:9"),
                "durationSeconds": duration,
                "sampleCount": 1,
            },
        }

        try:
            return await self._veo_generate(request_body)
        except Exception as e:
            logger.error(f"[VertexAI:Veo] image_to_video failed: {e}")
            return {"success": False, "error": str(e)}

    async def video_style_transfer(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Video style transfer via Veo — approximate with image-to-video.
        Veo doesn't have a dedicated V2V tool.
        """
        self._log_request("video_style_transfer", params)

        image_url = params.get("image_url") or params.get("first_frame_url") or params.get("video_url")
        if not image_url:
            raise ValueError("image_url or video_url required for style transfer")

        return await self.image_to_video({
            "image_url": image_url,
            "prompt": params.get("prompt", "stylized video"),
            "duration": params.get("duration", 6),
            "aspect_ratio": params.get("aspect_ratio", "16:9"),
        })

    async def _veo_generate(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit Veo generation request and poll the long-running operation.

        Veo 2 / 3 GA go through the `:predictLongRunning` endpoint (NOT
        `:predict`, which returns 429 with the message
        "Veo must be accessed through the Vertex PredictLongRunning API").
        Poll via `:fetchPredictOperation` on the same model, passing the
        returned `operationName`. Result parsing is shared with the older
        preview path so downstream callers don't change.

        https://cloud.google.com/vertex-ai/generative-ai/docs/video/overview
        """
        token = await self._get_access_token()
        http = self._get_http_client()

        base_model_url = (
            f"https://{self.video_location}-aiplatform.googleapis.com/v1/"
            f"projects/{self.project}/locations/{self.video_location}/"
            f"publishers/google/models/{self.veo_model}"
        )
        predict_url = f"{base_model_url}:predictLongRunning"

        logger.info(f"[VertexAI:Veo] Submitting video generation: {predict_url}")

        resp = await http.post(
            predict_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=request_body,
        )

        if resp.status_code != 200:
            error_text = resp.text[:500]
            raise Exception(f"Veo predict failed (HTTP {resp.status_code}): {error_text}")

        result = resp.json()

        # predictLongRunning always returns `{"name": <operation>}` — we do
        # not expect inline predictions, but keep the old fast-path just in
        # case a future model variant returns synchronously.
        operation_name = result.get("name")
        if not operation_name:
            return self._parse_veo_predictions(result)

        logger.info(f"[VertexAI:Veo] Operation started: {operation_name}")

        # Poll with the model's fetchPredictOperation endpoint — the standard
        # GET-on-operation path used by Vertex generic LROs does NOT work for
        # Veo (returns 400/404 on long-running video ops).
        fetch_url = f"{base_model_url}:fetchPredictOperation"

        for attempt in range(1, VEO_POLL_MAX_ATTEMPTS + 1):
            await asyncio.sleep(VEO_POLL_INTERVAL)

            # Refresh token periodically for long polls.
            if attempt % 30 == 0:
                token = await self._get_access_token()

            try:
                poll_resp = await http.post(
                    fetch_url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json={"operationName": operation_name},
                )
                poll_data = poll_resp.json()
            except Exception as e:
                logger.warning(f"[VertexAI:Veo] Poll attempt {attempt} failed: {e}")
                continue

            if poll_data.get("done"):
                if "error" in poll_data:
                    error = poll_data["error"]
                    raise Exception(
                        f"Veo generation failed: {error.get('message', error)}"
                    )
                return self._parse_veo_predictions(poll_data.get("response", poll_data))

            logger.info(
                f"[VertexAI:Veo] Operation in progress "
                f"(attempt {attempt}/{VEO_POLL_MAX_ATTEMPTS})"
            )

        raise Exception(
            f"Veo generation timed out after "
            f"{VEO_POLL_MAX_ATTEMPTS * VEO_POLL_INTERVAL}s"
        )

    def _parse_veo_predictions(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Veo prediction response to extract a playable video asset."""
        video_uri, video_b64 = self._extract_veo_video(result)
        if video_uri:
            self._log_response("veo_generation", True)
            return {
                "success": True,
                "task_id": result.get("name", ""),
                "output": {"video_url": video_uri},
            }

        if video_b64:
            output_dir = Path("/app/static/generated")
            output_dir.mkdir(parents=True, exist_ok=True)
            filename = f"veo_{uuid.uuid4().hex[:8]}.mp4"
            filepath = output_dir / filename
            filepath.write_bytes(base64.b64decode(video_b64))
            local_url = f"/static/generated/{filename}"
            self._log_response("veo_generation", True)
            return {
                "success": True,
                "task_id": result.get("name", ""),
                "output": {"video_url": local_url},
            }

        top_level = list(result.keys()) if isinstance(result, dict) else type(result).__name__
        raise Exception(f"No video in Veo response; top-level keys: {top_level}")

    def _extract_veo_video(self, payload: Any) -> Tuple[Optional[str], Optional[str]]:
        """Find video URI/base64 payloads across Veo response variants."""
        if isinstance(payload, list):
            for item in payload:
                video_uri, video_b64 = self._extract_veo_video(item)
                if video_uri or video_b64:
                    return video_uri, video_b64
            return None, None

        if not isinstance(payload, dict):
            return None, None

        for key in ("videoUri", "gcsUri", "uri", "url", "signedUri"):
            candidate = payload.get(key)
            if isinstance(candidate, str) and self._looks_like_video_uri(candidate):
                return candidate, None

        for key in ("bytesBase64Encoded", "videoBytes", "bytes", "data"):
            candidate = payload.get(key)
            if isinstance(candidate, str):
                return None, self._normalize_base64(candidate)

        for key in (
            "predictions",
            "response",
            "videos",
            "generatedVideos",
            "samples",
            "video",
            "output",
        ):
            if key in payload:
                video_uri, video_b64 = self._extract_veo_video(payload[key])
                if video_uri or video_b64:
                    return video_uri, video_b64

        for value in payload.values():
            video_uri, video_b64 = self._extract_veo_video(value)
            if video_uri or video_b64:
                return video_uri, video_b64

        return None, None

    def _looks_like_video_uri(self, value: str) -> bool:
        return value.startswith(("gs://", "http://", "https://", "/"))

    def _normalize_base64(self, value: str) -> str:
        if value.startswith("data:") and "," in value:
            value = value.split(",", 1)[1]
        return "".join(value.split())

    # ─────────────────────────────────────────────────────────────────────────
    # UNSUPPORTED — return clear errors
    # ─────────────────────────────────────────────────────────────────────────

    async def generate_avatar(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": False,
            "error": "Avatar generation is not available via Vertex AI.",
        }
