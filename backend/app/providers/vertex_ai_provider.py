"""
Vertex AI Provider — Unified GCP provider for Gemini (image/text) + Veo (video).

Replaces the old GeminiProvider that used API key auth against
generativelanguage.googleapis.com. Now uses Vertex AI SDK with
service account / ADC authentication.

Capabilities:
  - Content moderation (Gemini)
  - Text-to-image / Image-to-image editing (Gemini)
  - Interior design suggestions (Gemini)
  - Background removal / Upscale (Gemini)
  - Material generation (Gemini)
  - Text-to-video (Veo) — 3rd backup for video tasks
  - Image-to-video (Veo) — 3rd backup for video tasks

Auth: Uses Google Application Default Credentials (ADC).
  - On GCP (Cloud Run / GKE): automatic via service account
  - Local dev: set GOOGLE_APPLICATION_CREDENTIALS env var or run `gcloud auth application-default login`

Env vars:
  - VERTEX_AI_PROJECT: GCP project ID (required)
  - VERTEX_AI_LOCATION: Region, default "us-central1"
  - VEO_MODEL: Veo model name, default "veo-3.0-generate-preview"
  - GEMINI_MODEL: Gemini model for Vertex AI, default "gemini-2.0-flash"
  - GEMINI_IMAGE_MODEL: Gemini image model, default "gemini-2.0-flash-exp-image-generation"
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
from typing import Any, Dict, List, Optional

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
        self.project = os.getenv("VERTEX_AI_PROJECT", "")
        self.location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
        # Image generation models are only available in us-central1.
        self.image_location = os.getenv("VERTEX_AI_IMAGE_LOCATION", "us-central1")
        # Veo is only available in us-central1 today. Pin it independently so
        # deployments that set VERTEX_AI_LOCATION to a regional Gemini endpoint
        # (e.g. asia-east1) still resolve Veo to the correct regional host.
        self.video_location = os.getenv("VEO_LOCATION", "us-central1")
        # Default to Veo 2 GA (`veo-2.0-generate-001`) since Veo 3 preview is
        # behind an allowlist that most projects don't have. Set VEO_MODEL
        # explicitly when your project has 3.0 access.
        self.veo_model = os.getenv("VEO_MODEL", "veo-2.0-generate-001")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.gemini_image_model = os.getenv(
            "GEMINI_IMAGE_MODEL", "gemini-2.0-flash-exp-image-generation"
        )
        self.imagen_model = os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-002")
        self.imagen_edit_model = os.getenv("IMAGEN_EDIT_MODEL", "imagen-3.0-capability-001")

        if not self.project:
            logger.warning("VERTEX_AI_PROJECT not set — Vertex AI provider disabled")

        self._client: Optional[httpx.AsyncClient] = None
        self._genai_client = None
        self._genai_image_client = None

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

    def _get_genai_client(self):
        """Lazy-init the google-genai client configured for Vertex AI."""
        if self._genai_client is None:
            from google import genai

            self._genai_client = genai.Client(
                vertexai=True,
                project=self.project,
                location=self.location,
            )
        return self._genai_client

    def _get_genai_image_client(self):
        """Lazy-init a separate client for image generation (us-central1 only)."""
        if self._genai_image_client is None:
            from google import genai

            self._genai_image_client = genai.Client(
                vertexai=True,
                project=self.project,
                location=self.image_location,
            )
        return self._genai_image_client

    async def health_check(self) -> bool:
        if not self.project:
            return False
        try:
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

        client = self._get_genai_client()
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

    # ─────────────────────────────────────────────────────────────────────────
    # GEMINI — INTERIOR DESIGN
    # ─────────────────────────────────────────────────────────────────────────

    async def doodle_interior(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate interior design from image using Gemini on Vertex AI."""
        self._log_request("doodle_interior", params)

        style = params.get("style", "modern")
        room_type = params.get("room_type", "living room")
        prompt = params.get("prompt", "")
        full_prompt = f"Transform this room into a {style} {room_type} interior design. {prompt}"

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
            client = self._get_genai_client()
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

        duration = params.get("duration", 6)
        if duration not in (4, 6, 8):
            duration = min((4, 6, 8), key=lambda x: abs(x - duration))

        instance: Dict[str, Any] = {
            "image": {"bytesBase64Encoded": image_b64},
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

        image_url = params.get("image_url") or params.get("video_url")
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
        """Parse Veo prediction response to extract video URL."""
        predictions = result.get("predictions", [])
        if not predictions:
            raise Exception(f"No predictions in Veo response: {result}")

        prediction = predictions[0]

        # Veo can return video as GCS URI or base64
        video_uri = prediction.get("videoUri") or prediction.get("gcsUri")
        if video_uri:
            self._log_response("veo_generation", True)
            return {
                "success": True,
                "task_id": result.get("name", ""),
                "output": {"video_url": video_uri},
            }

        # Base64-encoded video
        video_b64 = prediction.get("bytesBase64Encoded")
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
                "task_id": "",
                "output": {"video_url": local_url},
            }

        raise Exception(f"No video in Veo response: {list(prediction.keys())}")

    # ─────────────────────────────────────────────────────────────────────────
    # UNSUPPORTED — return clear errors
    # ─────────────────────────────────────────────────────────────────────────

    async def generate_avatar(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": False,
            "error": "Avatar generation is not available via Vertex AI.",
        }
