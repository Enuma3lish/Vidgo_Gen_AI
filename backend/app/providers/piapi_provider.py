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
import os

from app.providers.base import BaseProvider

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
            timeout=300.0,  # 5 minutes for video generation
            headers={
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
            }
        )

    async def health_check(self) -> bool:
        """Check if PiAPI is healthy by making a simple API call."""
        try:
            # PiAPI doesn't have a dedicated health endpoint, so we check by testing the API
            # We'll just verify the connection works
            response = await self.client.post(
                f"{self.BASE_URL}/task",
                json={
                    "model": "Qubico/flux1-schnell",
                    "task_type": "txt2img",
                    "input": {"prompt": "test", "width": 64, "height": 64}
                },
                timeout=10.0
            )
            # If we get any response (even error), the API is reachable
            return response.status_code in [200, 201, 400, 402, 429]
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

    # ─────────────────────────────────────────────────────────────────────────
    # VIRTUAL TRY-ON (Kling AI via PiAPI)
    # ─────────────────────────────────────────────────────────────────────────

    async def virtual_try_on(
        self,
        model_image_url: str,
        garment_image_url: Optional[str] = None,
        upper_garment_url: Optional[str] = None,
        lower_garment_url: Optional[str] = None,
        batch_size: int = 1
    ) -> Dict[str, Any]:
        """
        Virtual Try-On using Kling AI via PiAPI.
        Reference: https://piapi.ai/docs/kling-api/virtual-try-on-api

        This is a TRUE virtual try-on that overlays clothing onto a model photo,
        NOT just generating a new image from text.

        Args:
            model_image_url: Photo of person/model
            garment_image_url: Clothing image (full body garment)
            upper_garment_url: Upper body garment only (optional)
            lower_garment_url: Lower body garment only (optional)
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
            "garment_image_url": garment_image_url
        })

        input_data = {
            "model_input": model_image_url,
            "batch_size": batch_size
        }

        # Add garment input - either full body or upper/lower
        if garment_image_url:
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
                "duration": params.get("duration", 5),
                "resolution": params.get("resolution", "1080P"),
                "watermark": False
            }
        }

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
        """
        Remove background from image using local rembg library.

        Args:
            params: {
                "image_url": str,
            }

        Returns:
            {"success": True, "task_id": str, "output": {"image_url": str}}
        """
        self._log_request("background_removal", params)

        try:
            import httpx as _httpx
            from rembg import remove
            from PIL import Image
            from io import BytesIO
            import base64
            import uuid
            import os

            # Load the image (local path or remote URL)
            image_url = params["image_url"]
            if image_url.startswith("/static") or image_url.startswith("static"):
                local_path = os.path.join("/app", image_url.lstrip("/"))
                with open(local_path, "rb") as f:
                    image_data = f.read()
            else:
                async with _httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers={"User-Agent": "VidGo/1.0"}) as dl_client:
                    resp = await dl_client.get(image_url)
                    resp.raise_for_status()
                    image_data = resp.content

            # Remove background using rembg (runs in thread to avoid blocking)
            input_image = Image.open(BytesIO(image_data))
            loop = asyncio.get_event_loop()
            output_image = await loop.run_in_executor(None, remove, input_image)

            # Save to /app/static/generated/
            filename = f"rembg_{uuid.uuid4().hex}.png"
            output_dir = "/app/static/generated"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, filename)
            output_image.save(output_path, "PNG")

            result_url = f"/static/generated/{filename}"
            self._log_response("background_removal", True)

            return {
                "success": True,
                "task_id": f"local-rembg-{filename}",
                "output": {"image_url": result_url}
            }
        except Exception as e:
            self._log_response("background_removal", False, str(e))
            raise

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

        style = params.get("style", "")
        prompt = params.get("prompt", "")
        if style and style not in prompt:
            prompt = f"{style} style, {prompt}"

        payload = {
            "model": "Wan",
            "task_type": "wan21-vace",
            "input": {
                "video": params["video_url"],
                "prompt": prompt,
                "watermark": False
            }
        }

        return await self._submit_and_poll(payload)


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

        payload = {
            "model": "Qubico/image-toolkit",
            "task_type": "upscale",
            "input": {
                "image_url": params["image_url"],
                "scale": params.get("scale", 2)
            }
        }

        return await self._submit_and_poll(payload)

    # ─────────────────────────────────────────────────────────────────────────
    # TEXT TO SPEECH (F5-TTS via PiAPI)
    # ─────────────────────────────────────────────────────────────────────────

    async def text_to_speech(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate speech audio from text using F5-TTS (zero-shot) via PiAPI.
        Reference: https://piapi.ai/docs/tts-api/f5-tts

        Args:
            params: {
                "text": str,           # Text to synthesize
                "ref_audio": str,      # Reference audio URL for voice cloning
                "ref_text": str,       # (optional) Text of the reference audio
            }

        Returns:
            {"success": True, "task_id": str, "output": {"audio_url": str}}
        """
        self._log_request("text_to_speech", params)

        # Reference audio for voice cloning. If not provided, use a default sample.
        ref_audio = params.get("ref_audio", "")
        if not ref_audio:
            # Default: use Kling's sample audio as reference voice
            ref_audio = "https://v15-kling.klingai.com/bs2/upload-ylab-stunt-sgp/minimax_tts/05648231552788212e980aade977d672/audio.mp3"
            logger.info("[PiAPI] Using default Kling sample as TTS reference voice")

        payload = {
            "model": "Qubico/tts",
            "task_type": "zero-shot",
            "input": {
                "gen_text": params["text"],
                "ref_audio": ref_audio,
            },
            "config": {
                "service_mode": "public"
            }
        }

        ref_text = params.get("ref_text")
        if ref_text:
            payload["input"]["ref_text"] = ref_text

        return await self._submit_and_poll(payload)

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
        script = params.get("script", "")
        audio_url = params.get("audio_url") or params.get("local_dubbing_url")
        mode = params.get("mode", "std")

        # Step 1: Kling Avatar REQUIRES local_dubbing_url (audio file).
        # Prompt-only mode is NOT supported. Generate audio via F5-TTS first.
        if script and not audio_url:
            voice_ref = params.get("voice_id", "")
            logger.info("[PiAPI] Avatar: generating speech with F5-TTS...")
            tts_result = await self.text_to_speech({
                "text": script,
                "ref_audio": voice_ref,  # Empty string uses default voice
            })
            if tts_result.get("success"):
                audio_url = tts_result.get("output", {}).get("audio_url")
                logger.info(f"[PiAPI] Avatar: TTS audio ready: {audio_url[:80] if audio_url else 'None'}")
            else:
                tts_error = tts_result.get("error", "TTS failed")
                logger.error(f"[PiAPI] Avatar: TTS failed: {tts_error}")
                return {"success": False, "error": f"Speech generation failed: {tts_error}"}

        if not audio_url:
            return {"success": False, "error": "Audio generation failed. Please provide an audio URL or script text."}

        # Step 2: Build Kling Avatar request (requires local_dubbing_url)
        input_data: Dict[str, Any] = {
            "image_url": image_url,
            "local_dubbing_url": audio_url,
            "mode": mode,
        }
        if script:
            input_data["prompt"] = script  # Additional context for lip-sync

        payload = {
            "model": "kling",
            "task_type": "avatar",
            "input": input_data,
            "config": {
                "service_mode": "public"
            }
        }

        logger.info(f"[PiAPI] Avatar: sending to Kling (audio={'yes' if audio_url else 'prompt-only'}, mode={mode})")
        result = await self._submit_and_poll(payload)

        # Normalize output: Kling returns video in output
        if result.get("success"):
            output = result.get("output", {})
            video_url = output.get("video_url") or output.get("works", [{}])[0].get("video", {}).get("url", "") if isinstance(output.get("works"), list) and output.get("works") else output.get("video_url", "")
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
