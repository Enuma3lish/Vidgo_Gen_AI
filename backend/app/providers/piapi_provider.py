"""
PiAPI Provider for Wan API access.

Supported models (via PiAPI):
- Wan: wan26-txt2video (Text-to-Video)
- Wan: wan26-img2video (Image-to-Video)
- Wan: txt2img (Text-to-Image via Flux)

API Documentation: https://piapi.ai/docs/wan-api
"""
import httpx
import asyncio
from typing import Dict, Any, Optional
import logging
import base64
import io
import os
import tempfile
import uuid

from app.providers.base import BaseProvider
from app.services.gcs_storage_service import get_gcs_storage

logger = logging.getLogger(__name__)


class PiAPIProvider(BaseProvider):
    """
    PiAPI Provider - Primary provider for VidGo.
    Uses PiAPI to access Wan models for T2I, I2V, T2V.
    """

    name = "piapi"
    BASE_URL = "https://api.piapi.ai/api/v1"

    def __init__(self):
        self.api_key = os.getenv("PIAPI_KEY", "")
        if not self.api_key:
            logger.warning("PIAPI_KEY not set in environment")

        self.client = httpx.AsyncClient(
            # 10 minutes per individual HTTP call. Kling Avatar polling can
            # idle for several minutes between status transitions and the
            # default 5 minutes was tripping on long jobs even when the task
            # was still healthy server-side.
            timeout=600.0,
            headers={
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
            }
        )

    async def health_check(self) -> bool:
        """Check whether PiAPI is reachable without creating a billable task."""
        if not self.api_key:
            return False

        try:
            response = await self.client.get(
                f"{self.BASE_URL}/task",
                timeout=10.0
            )
            if response.status_code in [401, 403]:
                return False
            return response.status_code < 500
        except Exception as e:
            logger.error(f"PiAPI health check failed: {e}")
            return False

    def _resolve_image_url(self, url: str) -> str:
        """Convert local /static/ paths to accessible URLs for external API calls.
        Prefers PUBLIC_APP_URL (public URL) over base64 to avoid 'task input too large' errors."""
        if url.startswith("/static") or url.startswith("static"):
            static_path = "/" + url.lstrip("/")  # normalize to /static/...
            # Prefer public URL (works for all APIs including Kling try-on which rejects base64)
            public_base = os.environ.get("PUBLIC_APP_URL", "").rstrip("/")
            if public_base:
                return f"{public_base}{static_path}"
            # Fallback to base64 (works for Flux but may fail for Kling)
            import base64
            import mimetypes
            local_path = os.path.join("/app", url.lstrip("/"))
            if os.path.exists(local_path):
                mime_type = mimetypes.guess_type(local_path)[0] or "image/png"
                with open(local_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                return f"data:{mime_type};base64,{b64}"
            logger.warning(f"[PiAPI] Local file not found: {local_path}")
        return url

    async def _prepare_avatar_audio_url(self, audio_url: str, user_id: Optional[str] = None) -> str:
        """Convert avatar dubbing audio to a stable public MP3 for Kling ingestion."""
        if not audio_url or not audio_url.startswith(("http://", "https://")):
            return audio_url

        gcs = get_gcs_storage()
        if not gcs.enabled:
            return audio_url

        try:
            async with httpx.AsyncClient(timeout=120.0) as http:
                response = await http.get(audio_url, follow_redirects=True)
                response.raise_for_status()
                source_bytes = response.content

            with tempfile.TemporaryDirectory() as tmpdir:
                input_path = os.path.join(tmpdir, "input_audio")
                output_path = os.path.join(tmpdir, "avatar_audio.mp3")
                with open(input_path, "wb") as f:
                    f.write(source_bytes)

                proc = await asyncio.create_subprocess_exec(
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    input_path,
                    "-ac",
                    "1",
                    "-ar",
                    "44100",
                    "-codec:a",
                    "libmp3lame",
                    "-b:a",
                    "128k",
                    output_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()
                if proc.returncode != 0:
                    raise RuntimeError(stderr.decode("utf-8", errors="ignore") or "ffmpeg audio conversion failed")

                with open(output_path, "rb") as f:
                    normalized = f.read()

            prefix = f"users/{user_id}/avatar-audio" if user_id else "generated/avatar-audio"
            blob_name = f"{prefix}/avatar_tts_{uuid.uuid4().hex[:12]}.mp3"
            piapi_url = await self._upload_ephemeral_resource(
                normalized,
                file_name=f"avatar_tts_{uuid.uuid4().hex[:12]}.mp3",
                content_type="audio/mpeg",
            )
            if piapi_url:
                logger.warning(
                    "[PiAPI] Avatar: normalized TTS audio to PiAPI upload (%s -> %s bytes)",
                    len(source_bytes),
                    len(normalized),
                )
                return piapi_url

            public_url = gcs.upload_public(normalized, blob_name, content_type="audio/mpeg")
            logger.warning(
                "[PiAPI] Avatar: normalized TTS audio to GCS fallback (%s -> %s bytes)",
                len(source_bytes),
                len(normalized),
            )
            return public_url
        except Exception as e:
            logger.warning(f"[PiAPI] Avatar: audio normalization failed, trying GCS copy fallback: {e}")
            try:
                persisted = await gcs.persist_url(
                    audio_url,
                    media_type="audio",
                    user_id=user_id,
                    filename_hint=f"avatar_tts_{uuid.uuid4().hex[:12]}",
                )
                return persisted
            except Exception as fallback_error:
                logger.warning(f"[PiAPI] Avatar: audio GCS fallback failed, using provider URL: {fallback_error}")
                return audio_url

    async def _prepare_avatar_image_url(self, image_url: str, user_id: Optional[str] = None) -> str:
        """Normalize avatar input to a small public JPEG for Kling ingestion."""
        if not image_url or not image_url.startswith(("http://", "https://")):
            return image_url

        gcs = get_gcs_storage()
        if not gcs.enabled:
            return image_url

        try:
            async with httpx.AsyncClient(timeout=60.0) as http:
                response = await http.get(image_url, follow_redirects=True)
                response.raise_for_status()
                source_bytes = response.content

            from PIL import Image, ImageOps

            image = Image.open(io.BytesIO(source_bytes))
            image = ImageOps.exif_transpose(image)
            if image.mode in {"RGBA", "LA", "P"}:
                image = image.convert("RGBA")
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")

            image.thumbnail((512, 512), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=88, optimize=True, progressive=False)
            normalized = buffer.getvalue()

            piapi_url = await self._upload_ephemeral_resource(
                normalized,
                file_name=f"avatar_{uuid.uuid4().hex[:12]}.jpg",
                content_type="image/jpeg",
            )
            if piapi_url:
                logger.warning(
                    "[PiAPI] Avatar: normalized input image to PiAPI upload (%s -> %s bytes, %sx%s)",
                    len(source_bytes),
                    len(normalized),
                    image.width,
                    image.height,
                )
                return piapi_url

            prefix = f"users/{user_id}/avatar-inputs" if user_id else "generated/avatar-inputs"
            blob_name = f"{prefix}/avatar_{uuid.uuid4().hex[:12]}.jpg"
            public_url = gcs.upload_public(normalized, blob_name, content_type="image/jpeg")
            logger.warning(
                "[PiAPI] Avatar: normalized input image to GCS fallback (%s -> %s bytes, %sx%s)",
                len(source_bytes),
                len(normalized),
                image.width,
                image.height,
            )
            return public_url
        except Exception as e:
            logger.warning(f"[PiAPI] Avatar: image normalization failed, using original URL: {e}")
            return image_url

    async def _upload_ephemeral_resource(self, data: bytes, file_name: str, content_type: str) -> Optional[str]:
        """Upload a temporary resource to PiAPI storage and return its public URL."""
        if not self.api_key or not data:
            return None

        try:
            payload = {
                "file_name": file_name,
                "file_data": base64.b64encode(data).decode("ascii"),
            }
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    "https://upload.theapi.app/api/ephemeral_resource",
                    headers={
                        "x-api-key": self.api_key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            if response.status_code >= 400:
                logger.warning(
                    "[PiAPI] Avatar: ephemeral upload failed status=%s body=%s",
                    response.status_code,
                    response.text[:300],
                )
                return None

            body = response.json()
            url = (body.get("data") or {}).get("url")
            if not url:
                logger.warning("[PiAPI] Avatar: ephemeral upload returned no URL: %s", body)
                return None
            return url
        except Exception as e:
            logger.warning(f"[PiAPI] Avatar: ephemeral upload error for {content_type}: {e}")
            return None

    async def _fallback_avatar_video(self, image_url: str, audio_url: str, script: str) -> Dict[str, Any]:
        """Fallback when Kling Avatar cannot ingest an otherwise valid portrait."""
        # Same fix as the primary path (BUG-005): keep the spoken content out
        # of the visual prompt so the image-to-video model doesn't render any
        # of the script as on-screen text. The lip-sync step still uses the
        # full audio so the message itself is preserved.
        presenter_prompt = (
            "natural presenter talking to camera, subtle head movement, "
            "friendly expression, professional studio lighting, stable face, "
            "no text, no captions, no subtitles, no watermark, no logos, "
            "no on-screen graphics"
        )

        logger.warning("[PiAPI] Avatar: trying presenter image-to-video fallback")
        try:
            base_video = await self.image_to_video({
                "image_url": image_url,
                "prompt": presenter_prompt,
                "duration": 5,
                "resolution": "720P",
            })
        except Exception as e:
            logger.warning("[PiAPI] Avatar: presenter image-to-video fallback raised: %s", e)
            return await self._render_static_avatar_video(image_url, audio_url)

        if not base_video.get("success"):
            return await self._render_static_avatar_video(image_url, audio_url)

        output = base_video.get("output") or {}
        video_url = output.get("video_url") or output.get("url")
        if not video_url or not audio_url:
            base_video.setdefault("output", output)
            if video_url:
                base_video["output"]["video_url"] = video_url
            return base_video

        lip_sync_payload = {
            "model": "kling",
            "task_type": "lip_sync",
            "input": {
                "video_url": video_url,
                "tts_text": "",
                "tts_timbre": "",
                "tts_speed": 1,
                "local_dubbing_url": audio_url,
            },
            "config": {
                "service_mode": "public"
            }
        }
        logger.warning("[PiAPI] Avatar: trying lip-sync fallback on generated presenter video")
        try:
            lip_sync = await self._submit_and_poll(lip_sync_payload)
        except Exception as e:
            logger.warning("[PiAPI] Avatar: lip-sync fallback raised, returning presenter video: %s", e)
            base_video.setdefault("output", output)
            base_video["output"]["video_url"] = video_url
            base_video["output"]["avatar_fallback"] = "presenter_i2v"
            return base_video

        if lip_sync.get("success"):
            lip_output = lip_sync.get("output") or {}
            lip_video_url = lip_output.get("video_url") or lip_output.get("url")
            if not lip_video_url:
                works = lip_output.get("works") or []
                for work in works if isinstance(works, list) else []:
                    if isinstance(work, dict):
                        video = work.get("video")
                        if isinstance(video, dict) and video.get("url"):
                            lip_video_url = video["url"]
                            break
                        if isinstance(video, str):
                            lip_video_url = video
                            break
            if lip_video_url:
                lip_sync.setdefault("output", lip_output)
                lip_sync["output"]["video_url"] = lip_video_url
            return lip_sync

        logger.warning("[PiAPI] Avatar: lip-sync fallback failed, returning presenter video: %s", lip_sync.get("error"))
        base_video.setdefault("output", output)
        base_video["output"]["video_url"] = video_url
        base_video["output"]["avatar_fallback"] = "presenter_i2v"
        return base_video

    async def _render_static_avatar_video(self, image_url: str, audio_url: str) -> Dict[str, Any]:
        """Last-resort MP4 fallback with the uploaded portrait and generated speech."""
        gcs = get_gcs_storage()
        if not gcs.enabled:
            return {"success": False, "error": "Avatar fallback storage is not configured"}

        try:
            async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
                image_response = await client.get(image_url)
                image_response.raise_for_status()
                image_bytes = image_response.content

                audio_bytes = b""
                if audio_url:
                    audio_response = await client.get(audio_url)
                    audio_response.raise_for_status()
                    audio_bytes = audio_response.content

            with tempfile.TemporaryDirectory() as tmpdir:
                image_path = os.path.join(tmpdir, "avatar.jpg")
                audio_path = os.path.join(tmpdir, "speech.mp3")
                output_path = os.path.join(tmpdir, "avatar.mp4")
                with open(image_path, "wb") as f:
                    f.write(image_bytes)
                with open(audio_path, "wb") as f:
                    f.write(audio_bytes)

                if audio_bytes:
                    cmd = [
                        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-loop", "1", "-framerate", "30", "-i", image_path,
                        "-i", audio_path,
                        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
                        "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
                        "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
                        output_path,
                    ]
                else:
                    cmd = [
                        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-loop", "1", "-framerate", "30", "-i", image_path,
                        "-t", "5",
                        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
                        "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
                        "-movflags", "+faststart",
                        output_path,
                    ]

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()
                if proc.returncode != 0:
                    raise RuntimeError(stderr.decode("utf-8", errors="ignore") or "ffmpeg avatar fallback failed")

                with open(output_path, "rb") as f:
                    video_bytes = f.read()

            video_url = gcs.upload_public(
                video_bytes,
                f"generated/avatar/fallback/avatar_{uuid.uuid4().hex[:12]}.mp4",
                content_type="video/mp4",
            )
            logger.warning("[PiAPI] Avatar: rendered local portrait+audio fallback MP4 (%s bytes)", len(video_bytes))
            return {
                "success": True,
                "task_id": "local-avatar-fallback",
                "output": {
                    "video_url": video_url,
                    "avatar_fallback": "static_portrait_audio",
                },
            }
        except Exception as e:
            logger.warning("[PiAPI] Avatar: local fallback failed: %s", e)
            return {"success": False, "error": f"Avatar fallback failed: {e}"}

    # ─────────────────────────────────────────────────────────────────────────
    # TEXT TO IMAGE (using Flux via PiAPI)
    # ─────────────────────────────────────────────────────────────────────────

    async def text_to_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate image from text using Flux via PiAPI.

        Args:
            params: {
                "prompt": str,
                "negative_prompt": str (optional),
                "size": str (optional, default "1024*1024"),
            }

        Returns:
            {"success": True, "task_id": str, "output": {"image_url": str}}
        """
        self._log_request("text_to_image", params)

        # Parse size
        size = params.get("size", "1024*1024")
        if "*" in size:
            width, height = map(int, size.split("*"))
        else:
            width, height = 1024, 1024

        payload = {
            "model": "Qubico/flux1-schnell",
            "task_type": "txt2img",
            "input": {
                "prompt": params["prompt"],
                "negative_prompt": params.get("negative_prompt", ""),
                "width": width,
                "height": height
            }
        }

        return await self._submit_and_poll(payload)

    # ─────────────────────────────────────────────────────────────────────────
    # IMAGE TO IMAGE (using Flux via PiAPI)
    # ─────────────────────────────────────────────────────────────────────────

    async def image_to_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform image using Flux img2img via PiAPI.
        Reference: https://piapi.ai/docs/flux-api/image-to-image

        Args:
            params: {
                "image_url": str,  # Input image URL
                "prompt": str,
                "negative_prompt": str (optional),
                "strength": float (optional, 0.0-1.0, default 0.75),
                "width": int (optional, default 1024),
                "height": int (optional, default 768)
            }

        Returns:
            {"success": True, "task_id": str, "output": {"image_url": str}}
        """
        self._log_request("image_to_image", params)

        model = str(params.get("model") or "").strip()
        if model in {"wan_pro", "flux_kontext", "kontext", "pro"}:
            return await self.kontext_image(params)

        payload = {
            "model": "Qubico/flux1-schnell",
            "task_type": "img2img",
            "input": {
                "image": self._resolve_image_url(params["image_url"]),
                "prompt": params["prompt"],
                "negative_prompt": params.get("negative_prompt", ""),
                "denoise": params.get("strength", params.get("denoise", 0.75)),
            }
        }

        return await self._submit_and_poll(payload)

    async def kontext_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Edit image using Kontext (context-aware editing) via PiAPI.
        Alternative to img2img that might be available on more plans.
        Reference: https://piapi.ai/docs/flux-api/kontext

        Args:
            params: {
                "image_url": str,  # Input image URL
                "prompt": str,  # Editing instruction
                "width": int (optional, default 1024),
                "height": int (optional, default 768),
                "steps": int (optional, default 10)
            }

        Returns:
            {"success": True, "task_id": str, "output": {"image_url": str}}
        """
        self._log_request("kontext_image", params)

        payload = {
            "model": "Qubico/flux1-dev-advanced",
            "task_type": "kontext",
            "input": {
                "image": self._resolve_image_url(params["image_url"]),
                "prompt": params["prompt"],
                "width": params.get("width", 1024),
                "height": params.get("height", 768),
                "steps": params.get("steps", 10),
                "seed": -1
            }
        }

        return await self._submit_and_poll(payload)

    async def _resize_image_for_trellis(self, image_url: str, max_dim: int = 1024) -> str:
        """
        Download image, resize to fit within max_dim × max_dim, re-upload to GCS.
        Returns a public URL of the resized image (or original if already small enough).
        Trellis rejects images larger than 1024×1024.
        """
        try:
            from PIL import Image as PILImage
            import io as _io

            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                resp = await client.get(image_url)
                resp.raise_for_status()
                data = resp.content

            img = PILImage.open(_io.BytesIO(data))
            w, h = img.size
            if w <= max_dim and h <= max_dim:
                return image_url  # already within bounds

            scale = max_dim / max(w, h)
            new_w, new_h = int(w * scale), int(h * scale)
            img = img.resize((new_w, new_h), PILImage.LANCZOS)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            buf = _io.BytesIO()
            img.save(buf, format="JPEG", quality=92)
            resized_bytes = buf.getvalue()

            gcs = get_gcs_storage()
            if gcs.enabled:
                blob_name = f"temp/trellis_resize_{uuid.uuid4().hex}.jpg"
                resized_url = gcs.upload_public(resized_bytes, blob_name, "image/jpeg")
                logger.info(f"[trellis_3d] Resized {w}x{h} → {new_w}x{new_h}, re-uploaded to {resized_url}")
                return resized_url

            # Fallback: base64 data URL
            b64 = base64.b64encode(resized_bytes).decode()
            return f"data:image/jpeg;base64,{b64}"

        except Exception as exc:
            logger.warning(f"[trellis_3d] Could not resize image {image_url}: {exc} — using original")
            return image_url

    async def trellis_3d(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a GLB model from a public image URL using Qubico Trellis.

        Pass `model_version`: 'v1' (default, Qubico/trellis, $0.02) or
        'v2' (Qubico/trellis2, higher fidelity, $0.10). Both are image-to-3d.

        PiAPI returns Trellis outputs as no_background_image, combined_video,
        and model_file. Normalize model_file to model_url so the provider
        router can persist and return it consistently.
        Trellis hard-limits input images to 1024×1024; we auto-resize larger images.
        """
        self._log_request("image_to_3d", params)

        model_version = str(params.get("model_version", "v1")).lower()
        model_name = "Qubico/trellis2" if model_version in ("v2", "trellis2", "hq", "hd") else "Qubico/trellis"

        image_url = self._resolve_image_url(params["image_url"])
        # Trellis rejects images > 1024×1024 — auto-resize if needed
        image_url = await self._resize_image_for_trellis(image_url, max_dim=1024)

        payload = {
            "model": model_name,
            "task_type": "image-to-3d",
            "input": {
                "image": image_url,
            },
        }

        result = await self._submit_and_poll(payload)
        output = result.get("output") or {}
        if isinstance(output, dict):
            model_url = output.get("model_url") or output.get("model_file") or output.get("url")
            if model_url:
                output["model_url"] = model_url
            if output.get("no_background_image") and not output.get("image_url"):
                output["image_url"] = output["no_background_image"]
            if output.get("combined_video") and not output.get("video_url"):
                output["video_url"] = output["combined_video"]
            result["output"] = output

        return result

    # ─────────────────────────────────────────────────────────────────────────
    # VIRTUAL TRY-ON (Kling AI via PiAPI)
    # ─────────────────────────────────────────────────────────────────────────

    async def virtual_try_on(
        self,
        model_image_url: str,
        garment_image_url: Optional[str] = None,
        upper_garment_url: Optional[str] = None,
        lower_garment_url: Optional[str] = None,
        category: str = "dress",
        batch_size: int = 1
    ) -> Dict[str, Any]:
        """
        Virtual Try-On using Kling AI via PiAPI.
        Reference: https://piapi.ai/docs/kling-api/virtual-try-on-api

        This is a TRUE virtual try-on that overlays clothing onto a model photo,
        NOT just generating a new image from text.

        Args:
            model_image_url: Photo of person/model
            garment_image_url: Clothing image (full body garment OR routed by category)
            upper_garment_url: Upper body garment only (optional)
            lower_garment_url: Lower body garment only (optional)
            category: When only garment_image_url is given, controls which Kling
                input slot it goes into:
                  - "upper_body" → upper_input
                  - "lower_body" → lower_input
                  - "dress" / "full_body" → dress_input (default)
            batch_size: Number of output images (1-4, default 1)

        Notes:
            - Either garment_image_url OR (upper_garment_url + lower_garment_url) must be provided
            - garment_image_url is for full-body garments (dress_input in API)
            - upper/lower for separate top/bottom

        Returns:
            {"success": True, "task_id": str, "output": {"image_url": str, "images": [...]}}
        """
        self._log_request("virtual_try_on", {
            "model_image_url": model_image_url,
            "garment_image_url": garment_image_url,
            "category": category,
        })

        input_data = {
            "model_input": model_image_url,
            "batch_size": batch_size
        }

        # Add garment input - either full body or upper/lower
        if garment_image_url:
            cat = (category or "dress").lower()
            if cat == "upper_body":
                input_data["upper_input"] = garment_image_url
            elif cat == "lower_body":
                input_data["lower_input"] = garment_image_url
            else:  # dress / full_body / default
                input_data["dress_input"] = garment_image_url
        else:
            if upper_garment_url:
                input_data["upper_input"] = upper_garment_url
            if lower_garment_url:
                input_data["lower_input"] = lower_garment_url

        payload = {
            "model": "kling",
            "task_type": "ai_try_on",
            "input": input_data
        }

        return await self._submit_and_poll(payload)

    # ─────────────────────────────────────────────────────────────────────────
    # IMAGE TO VIDEO (Wan 2.6 via PiAPI)
    # ─────────────────────────────────────────────────────────────────────────

    async def image_to_video(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate video from image using Wan 2.6 I2V via PiAPI.

        Args:
            params: {
                "image_url": str,
                "prompt": str (optional),
                "duration": int (optional, 5/10/15, default 5),
                "resolution": str (optional, "720P" or "1080P", default "1080P"),
            }

        Returns:
            {"success": True, "task_id": str, "output": {"video_url": str}}
        """
        self._log_request("image_to_video", params)

        payload = {
            "model": "Wan",
            "task_type": "wan26-img2video",
            "input": {
                "image": self._resolve_image_url(params["image_url"]),
                "prompt": params.get("prompt", "smooth natural motion"),
                "negative_prompt": params.get("negative_prompt", ""),
                "duration": params.get("duration", 5),
                "resolution": params.get("resolution", "1080P"),
                # image_fidelity (0.0-1.0): how strictly the generated video
                # must preserve the source image's subject. We default high
                # (0.85) because product/short-video flows depend on the
                # original product staying recognizable; callers can tune
                # down for more creative motion.
                "image_fidelity": float(params.get("image_fidelity", 0.85)),
                "watermark": False,
            },
        }
        # motion_bucket_id (1-255 in SVD-style models, ~127 default). Lower =
        # less motion = more product preservation. We expose it as an optional
        # param; only forward when set so older PiAPI variants that ignore it
        # do not error on the extra key.
        if params.get("motion_bucket_id") is not None:
            payload["input"]["motion_bucket_id"] = int(params["motion_bucket_id"])

        return await self._submit_and_poll(payload)

    # ─────────────────────────────────────────────────────────────────────────
    # TEXT TO VIDEO (Wan 2.6 via PiAPI)
    # ─────────────────────────────────────────────────────────────────────────

    async def text_to_video(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate video from text using Wan 2.6 T2V via PiAPI.

        Args:
            params: {
                "prompt": str,
                "negative_prompt": str (optional),
                "duration": int (optional, 5/10/15, default 5),
                "resolution": str (optional, "720P" or "1080P", default "1080P"),
                "aspect_ratio": str (optional, "16:9", "9:16", "1:1", default "16:9")
            }

        Returns:
            {"success": True, "task_id": str, "output": {"video_url": str}}
        """
        self._log_request("text_to_video", params)

        payload = {
            "model": "Wan",
            "task_type": "wan26-txt2video",
            "input": {
                "prompt": params["prompt"],
                "negative_prompt": params.get("negative_prompt", ""),
                "duration": params.get("duration", 5),
                "resolution": params.get("resolution", "1080P"),
                "aspect_ratio": params.get("aspect_ratio", "16:9"),
                "watermark": False
            }
        }

        return await self._submit_and_poll(payload)

    # ─────────────────────────────────────────────────────────────────────────
    # INTERIOR DESIGN (using Flux img2img as fallback)
    # ─────────────────────────────────────────────────────────────────────────

    async def doodle_interior(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate interior design from image using TRUE Image-to-Image.
        Now uses Flux img2img to actually process the input image.

        Args:
            params: {
                "image_url": str,
                "prompt": str (optional),
                "style": str (optional, default "modern"),
                "room_type": str (optional, default "living_room")
            }

        Returns:
            {"success": True, "task_id": str, "output": {"image_url": str}}
        """
        self._log_request("doodle_interior", params)

        style = params.get("style", "modern")
        room_type = params.get("room_type", "living room")
        prompt = params.get("prompt", "")

        full_prompt = f"{style} {room_type} interior design, professional architectural rendering, {prompt}"

        # Try kontext first (more likely to be available)
        return await self.kontext_image({
            "image_url": params["image_url"],
            "prompt": full_prompt,
            "width": 1024,
            "height": 768,
            "steps": 10
        })

    # ─────────────────────────────────────────────────────────────────────────
    # BACKGROUND REMOVAL (using local rembg library)
    # ─────────────────────────────────────────────────────────────────────────

    async def background_removal(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Calls PiAPI image-toolkit background-remove — higher quality on
        # complex subjects (hair, fine edges) than local rembg. Router falls
        # through to Vertex's rembg fallback on 500.
        # NOTE: PiAPI image-toolkit expects the input key `image` (URL or
        # base64), NOT `image_url`. The wrong key returns HTTP 500.
        self._log_request("background_removal", params)

        input_block: Dict[str, Any] = {
            "image": self._resolve_image_url(params["image_url"]),
        }
        # Fine-edge / alpha-matting controls: enabled by default for the
        # product-cutout flow so hair, comb teeth, and translucent edges
        # come back with a real soft alpha rather than a 1-bit hard mask.
        # Toolkit accepts these as hints; ignored by older variants.
        if params.get("alpha_matting", True):
            input_block["alpha_matting"] = True
        if params.get("fine_detail", True):
            input_block["fine_detail"] = True

        payload = {
            "model": "Qubico/image-toolkit",
            "task_type": "background-remove",
            "input": input_block,
        }

        return await self._submit_and_poll(payload)

    # ─────────────────────────────────────────────────────────────────────────
    # VIDEO STYLE TRANSFER (Wan VACE via PiAPI)
    # ─────────────────────────────────────────────────────────────────────────

    async def video_style_transfer(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply style transfer to video using Wan 2.1 VACE via PiAPI.

        Args:
            params: {
                "video_url": str,
                "prompt": str,
                "style": str (optional),
            }

        Returns:
            {"success": True, "task_id": str, "output": {"video_url": str}}
        """
        self._log_request("video_style_transfer", params)

        return {
            "success": False,
            "error": "PiAPI REST video style transfer is unavailable: wan21-vace is not accepted by the current PiAPI API.",
        }


    # ─────────────────────────────────────────────────────────────────────────
    # UPSCALE
    # ─────────────────────────────────────────────────────────────────────────

    async def upscale(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upscale image resolution.

        Args:
            params: {
                "image_url": str,
                "scale": int (optional, 2 or 4)
            }

        Returns:
            {"success": True, "task_id": str, "output": {"image_url": str}}
        """
        self._log_request("upscale", params)

        # Qubico/image-toolkit upscale requires the input key `image` (not
        # `image_url`). PiAPI rejects the wrong key with a 500. Also normalize
        # backend-local /static/ paths so PiAPI can fetch the source.
        payload = {
            "model": "Qubico/image-toolkit",
            "task_type": "upscale",
            "input": {
                "image": self._resolve_image_url(params["image_url"]),
                "scale": params.get("scale", 2),
            }
        }

        return await self._submit_and_poll(payload)

    # ─────────────────────────────────────────────────────────────────────────
    # TEXT TO SPEECH (F5-TTS via PiAPI)
    # ─────────────────────────────────────────────────────────────────────────

    # ─── OpenAI-compatible TTS via PiAPI (tts-1) — primary path ────────────
    # PiAPI's Qubico/tts F5-TTS model has been returning "internal server error
    # 500" on every call for several days (task creates fine, fails at worker
    # level: `logs: ["internal server error\nstatus code: 500\nfailed to do
    # request"]`). Their OpenAI-compatible /v1/audio/speech endpoint with
    # tts-1 works reliably, supports 6 voices, no ref_audio required, and
    # returns the MP3 bytes synchronously. We use it as the primary TTS path
    # and only fall through to F5-TTS when the caller explicitly wants voice
    # cloning (ref_audio supplied AND not the dead default).

    OPENAI_COMPAT_TTS_URL = "https://api.piapi.ai/v1/audio/speech"
    OPENAI_VOICE_DEFAULT = "alloy"
    OPENAI_VOICES = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}

    async def _tts_via_openai_compat(self, text: str, voice: str | None) -> Dict[str, Any]:
        """Call PiAPI's OpenAI-compatible /v1/audio/speech, persist the MP3
        bytes to GCS, and return a result shape that matches the rest of the
        TTS pipeline ({success, output:{audio_url, duration_estimate_s}})."""
        v = (voice or self.OPENAI_VOICE_DEFAULT).lower()
        if v not in self.OPENAI_VOICES:
            v = self.OPENAI_VOICE_DEFAULT
        payload = {"model": "tts-1", "input": text, "voice": v}
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.post(
                    self.OPENAI_COMPAT_TTS_URL,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
            if r.status_code != 200:
                detail = r.text[:300]
                logger.error("[PiAPI] tts-1 HTTP %d: %s", r.status_code, detail)
                return {"success": False, "error": f"tts-1 returned HTTP {r.status_code}: {detail}"}
            audio_bytes = r.content
            if not audio_bytes or len(audio_bytes) < 1024:
                return {"success": False, "error": "tts-1 returned empty audio"}
            # Persist to GCS so the dubbing ffmpeg mux can fetch it later.
            gcs = get_gcs_storage()
            blob_name = f"generated/audio/tts_{uuid.uuid4().hex[:12]}.mp3"
            audio_url: Optional[str]
            if gcs.enabled:
                audio_url = gcs.upload_public(data=audio_bytes, blob_name=blob_name, content_type="audio/mpeg")
            else:
                # Local dev fallback — caller must be running under PUBLIC_APP_URL
                tmp = os.path.join("/app/static/generated", os.path.basename(blob_name))
                os.makedirs(os.path.dirname(tmp), exist_ok=True)
                with open(tmp, "wb") as f:
                    f.write(audio_bytes)
                public_base = os.environ.get("PUBLIC_APP_URL", "").rstrip("/")
                audio_url = f"{public_base}/static/generated/{os.path.basename(blob_name)}" if public_base else f"/static/generated/{os.path.basename(blob_name)}"
            logger.info("[PiAPI] tts-1 success: %d bytes → %s", len(audio_bytes), audio_url)
            return {
                "success": True,
                "task_id": f"tts1-{uuid.uuid4().hex[:8]}",
                "output": {"audio_url": audio_url, "voice": v, "model": "tts-1"},
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("[PiAPI] tts-1 exception: %s", exc)
            return {"success": False, "error": f"tts-1 exception: {exc}"}

    async def text_to_speech(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate speech audio from text. PiAPI exposes two TTS surfaces:

        1. OpenAI-compatible /v1/audio/speech with `tts-1` — synchronous MP3
           response, 6 fixed voices (alloy/echo/fable/onyx/nova/shimmer),
           supports en/zh/ja/ko/es and many more, no reference audio required.
        2. Qubico/tts F5-TTS via the async /api/v1/task endpoint — zero-shot
           voice cloning from a reference audio clip. Currently broken
           upstream (worker returns 500 on every call as of 2026-05-09).

        Routing rule:
          - If `ref_audio` is supplied AND non-empty AND voice cloning is
            actually required → use F5-TTS, fall back to tts-1 on 500.
          - Otherwise → use tts-1 directly (the common case for video_dubbing
            where the user just wants a localized voiceover, not a clone).

        Args:
            params: {
                "text": str,
                "ref_audio": str | None,   # voice-clone reference URL
                "ref_text": str | None,    # transcript of the reference clip
                "voice": str | None,       # tts-1 voice id (alloy/echo/...)
            }

        Returns:
            {"success": True, "task_id": str, "output": {"audio_url": str}}
        """
        self._log_request("text_to_speech", params)

        text = params.get("text") or ""
        ref_audio = (params.get("ref_audio") or "").strip()
        voice_hint = params.get("voice") or params.get("voice_id")

        # Path A: caller wants voice cloning → F5-TTS, with tts-1 fallback.
        # _submit_and_poll RAISES on task failure (not returns success=False),
        # so we have to wrap it. Auth errors get surfaced; everything else
        # (notably the persistent upstream 500) falls through to tts-1.
        if ref_audio:
            payload = {
                "model": "Qubico/tts",
                "task_type": "zero-shot",
                "input": {"gen_text": text, "ref_audio": ref_audio},
                "config": {"service_mode": "public"},
            }
            ref_text = params.get("ref_text")
            if ref_text:
                payload["input"]["ref_text"] = ref_text

            err_text = ""
            try:
                result = await self._submit_and_poll(payload)
                if isinstance(result, dict) and result.get("success") is True:
                    return result
                if isinstance(result, dict):
                    err_text = (result.get("error") or result.get("message") or "")
            except Exception as exc:  # noqa: BLE001
                err_text = str(exc)

            err_text_lower = err_text.lower()
            if any(tok in err_text_lower for tok in ("unauthorized", "forbidden", "permission", "403", "401", "model_not_authorized")):
                return {
                    "success": False,
                    "error": (
                        "Voice cloning model is not enabled on this PiAPI account. "
                        "Enable F5-TTS / voice-clone access in the PiAPI dashboard, "
                        "or omit ref_audio to use the built-in default voice."
                    ),
                }
            logger.warning("[PiAPI] F5-TTS failed (%s); falling back to tts-1", err_text[:160])
            return await self._tts_via_openai_compat(text, voice_hint)

        # Path B (default): no voice cloning needed → tts-1.
        return await self._tts_via_openai_compat(text, voice_hint)

    # ─────────────────────────────────────────────────────────────────────────
    # AVATAR (Kling Avatar via PiAPI — talking head video)
    # ─────────────────────────────────────────────────────────────────────────

    async def generate_avatar(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate talking-head avatar video using Kling Avatar via PiAPI.
        Reference: https://piapi.ai/docs/kling-api/kling-avatar-api

        Two modes:
        1. With audio URL (local_dubbing_url) — lip-syncs to provided audio
        2. With text prompt only — Kling generates audio internally

        Pipeline: If script text is provided without audio, we first try F5-TTS
        to generate audio, then pass it to Kling Avatar. If TTS fails, we fall
        back to Kling's built-in prompt-to-audio.

        Args:
            params: {
                "image_url": str,          # Avatar image (person photo)
                "script": str,             # Text script for the avatar to speak
                "language": str,           # Language code (optional)
                "voice_id": str,           # Voice reference audio URL (optional)
                "duration": int,           # Target duration in seconds (optional)
                "audio_url": str,          # Pre-generated audio URL (optional)
                "mode": str,               # "std" or "pro" (optional, default "std")
            }

        Returns:
            {"success": True, "task_id": str, "output": {"video_url": str}}
        """
        self._log_request("generate_avatar", params)

        image_url = self._resolve_image_url(params["image_url"])
        image_url = await self._prepare_avatar_image_url(image_url, params.get("user_id"))
        script = params.get("script") or params.get("text") or params.get("prompt") or ""
        audio_url = params.get("audio_url") or params.get("local_dubbing_url")
        mode = params.get("mode", "std")

        # Step 1: Kling Avatar REQUIRES local_dubbing_url (audio file).
        # Prompt-only mode is NOT supported. Generate audio via F5-TTS first.
        if script and not audio_url:
            voice_ref = params.get("voice_id", "")
            logger.info("[PiAPI] Avatar: generating speech with F5-TTS...")
            try:
                tts_result = await self.text_to_speech({
                    "text": script,
                    "ref_audio": voice_ref,  # Empty string uses default voice
                })
            except Exception as e:
                logger.warning("[PiAPI] Avatar: TTS raised, using visual fallback: %s", e)
                return await self._fallback_avatar_video(image_url, "", script)
            if tts_result.get("success"):
                audio_url = tts_result.get("output", {}).get("audio_url")
                logger.info(f"[PiAPI] Avatar: TTS audio ready: {audio_url[:80] if audio_url else 'None'}")
            else:
                tts_error = tts_result.get("error", "TTS failed")
                logger.warning("[PiAPI] Avatar: TTS failed, using visual fallback: %s", tts_error)
                return await self._fallback_avatar_video(image_url, "", script)

        if not audio_url:
            return {"success": False, "error": "Audio generation failed. Please provide an audio URL or script text."}

        audio_url = await self._prepare_avatar_audio_url(audio_url, params.get("user_id"))

        # Step 2: Build Kling Avatar request (requires local_dubbing_url).
        # NOTE: Kling's `prompt` field controls the *visual scene*, not the
        # spoken content. Passing the user's script in `prompt` made Kling
        # render parts of it as on-screen captions/text overlays (BUG-005).
        # The script reaches Kling via `local_dubbing_url` (the TTS audio);
        # the prompt should be a clean visual brief that explicitly tells
        # the model "no text, no captions, no watermark" so the output is a
        # plain talking-head video.
        input_data: Dict[str, Any] = {
            "image_url": image_url,
            "local_dubbing_url": audio_url,
            "mode": mode,
            "batch_size": params.get("batch_size", 1),
            "prompt": (
                "Natural talking-head presenter video, subtle lip-sync and "
                "head movement, neutral background, professional studio "
                "lighting, no text, no captions, no subtitles, no watermark, "
                "no logos, no on-screen graphics"
            ),
            "negative_prompt": (
                "text, captions, subtitles, watermark, logo, on-screen "
                "graphics, written words, overlays"
            ),
        }

        payload = {
            "model": "kling",
            "task_type": "avatar",
            "input": input_data,
            "config": {
                "service_mode": "public"
            }
        }

        logger.warning(
            "[PiAPI] Avatar: sending to Kling (image_host=%s, audio_host=%s, mode=%s)",
            httpx.URL(image_url).host if image_url.startswith(("http://", "https://")) else "local",
            httpx.URL(audio_url).host if audio_url.startswith(("http://", "https://")) else "local",
            mode,
        )
        try:
            result = await self._submit_and_poll(payload)
        except Exception as e:
            logger.warning("[PiAPI] Avatar: dedicated Kling Avatar raised, using fallback: %s", e)
            return await self._fallback_avatar_video(image_url, audio_url, script)

        if not result.get("success"):
            logger.warning("[PiAPI] Avatar: dedicated Kling Avatar failed, using fallback: %s", result.get("error"))
            return await self._fallback_avatar_video(image_url, audio_url, script)

        # Normalize output: Kling returns video in output
        if result.get("success"):
            output = result.get("output", {})
            video_url = output.get("video_url") or output.get("url") or ""
            if not video_url:
                # Try to find video in nested output structure
                works = output.get("works", [])
                if works and isinstance(works, list):
                    for w in works:
                        if isinstance(w, dict):
                            v = w.get("video", {})
                            if isinstance(v, dict) and v.get("url"):
                                video_url = v["url"]
                                break
                            elif isinstance(v, str):
                                video_url = v
                                break
            if video_url:
                result["output"]["video_url"] = video_url

        return result

    # ─────────────────────────────────────────────────────────────────────────
    # INTERNAL METHODS
    # ─────────────────────────────────────────────────────────────────────────

    async def _submit_and_poll(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit task and poll for result."""
        # Submit task
        try:
            response = await self.client.post(
                f"{self.BASE_URL}/task",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            self._log_response(payload.get("task_type", "unknown"), False, str(e))
            raise Exception(f"PiAPI request failed: {e.response.text}")
        except Exception as e:
            self._log_response(payload.get("task_type", "unknown"), False, str(e))
            raise

        # Handle different response formats
        if "data" in data and "task_id" in data["data"]:
            task_id = data["data"]["task_id"]
        elif "task_id" in data:
            task_id = data["task_id"]
        else:
            # Check if result is immediate
            if "output" in data or "result" in data:
                output = data.get("output") or data.get("result")
                self._log_response(payload.get("task_type", "unknown"), True)
                return {
                    "success": True,
                    "task_id": data.get("id", "immediate"),
                    "output": output
                }
            raise Exception(f"Invalid PiAPI response: {data}")

        # Poll for result
        max_attempts = 120  # 10 minutes max
        for attempt in range(max_attempts):
            try:
                status_response = await self.client.get(
                    f"{self.BASE_URL}/task/{task_id}"
                )
                status_data = status_response.json()

                # Handle different response structures
                if "data" in status_data:
                    task_data = status_data["data"]
                else:
                    task_data = status_data

                status = task_data.get("status", "").lower()

                if status in ["completed", "success", "done"]:
                    output = task_data.get("output") or task_data.get("result", {})
                    self._log_response(payload.get("task_type", "unknown"), True)
                    return {
                        "success": True,
                        "task_id": task_id,
                        "output": output
                    }
                elif status in ["failed", "error"]:
                    error_msg = task_data.get("error", "Unknown error")
                    self._log_response(payload.get("task_type", "unknown"), False, error_msg)
                    raise Exception(error_msg)

                # Still processing, wait and retry
                await asyncio.sleep(5)

            except httpx.HTTPStatusError as e:
                if attempt < max_attempts - 1:
                    await asyncio.sleep(5)
                    continue
                raise Exception(f"Failed to poll task status: {e}")

        self._log_response(payload.get("task_type", "unknown"), False, "Task timeout")
        raise Exception("PiAPI task timeout - generation took too long")

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
