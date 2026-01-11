"""
Rembg Client - Local Background Removal (FREE)

Uses rembg library for local processing.
No API cost, runs on server.

Typical response time:
- Small images (<1MB): 1-2 seconds
- Medium images (1-3MB): 2-4 seconds
- Large images (>3MB): 3-6 seconds
"""
import asyncio
import logging
import uuid
import io
from pathlib import Path
from typing import Dict, Any, Optional

import httpx
from PIL import Image

logger = logging.getLogger(__name__)

# Output directory
OUTPUT_DIR = Path("/app/static/generated")


class RembgClient:
    """Local rembg client for background removal - FREE, no API cost."""

    def __init__(self):
        # Test rembg import
        try:
            from rembg import remove
            self._remove = remove
            self.available = True
        except ImportError:
            logger.warning("[Rembg] Library not installed: pip install rembg")
            self._remove = None
            self.available = False

    async def remove_background(
        self,
        image_url: str,
        save_locally: bool = True
    ) -> Dict[str, Any]:
        """
        Remove background from image.

        Args:
            image_url: URL of source image
            save_locally: Save to local file (default True)

        Returns:
            {
                "success": True/False,
                "image_url": str (local path),
                "error": str (if failed)
            }
        """
        if not self.available:
            return {"success": False, "error": "rembg library not installed"}

        logger.info(f"[Rembg] Processing: {image_url[:60]}...")

        try:
            # Download image
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(image_url, follow_redirects=True)
                if response.status_code != 200:
                    return {"success": False, "error": f"Failed to download: HTTP {response.status_code}"}
                image_data = response.content

            logger.info(f"[Rembg] Downloaded: {len(image_data)} bytes")

            # Process in thread pool (rembg is CPU-intensive)
            loop = asyncio.get_event_loop()
            result_image = await loop.run_in_executor(
                None,
                self._process_sync,
                image_data
            )

            if result_image is None:
                return {"success": False, "error": "Processing failed"}

            # Save result
            if save_locally:
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                filename = f"bg_removed_{uuid.uuid4().hex[:8]}.png"
                filepath = OUTPUT_DIR / filename
                result_image.save(filepath, format="PNG")
                local_url = f"/static/generated/{filename}"
                logger.info(f"[Rembg] Saved: {local_url}")
                return {"success": True, "image_url": local_url}

            # Return as base64 (not recommended for large images)
            import base64
            buffered = io.BytesIO()
            result_image.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            return {"success": True, "image_url": f"data:image/png;base64,{img_base64}"}

        except Exception as e:
            logger.exception(f"[Rembg] Exception: {e}")
            return {"success": False, "error": str(e)}

    def _process_sync(self, image_data: bytes) -> Optional[Image.Image]:
        """Synchronous background removal (runs in thread pool)."""
        try:
            input_image = Image.open(io.BytesIO(image_data))
            output_image = self._remove(input_image, alpha_matting=True)
            return output_image
        except Exception as e:
            logger.error(f"[Rembg] Process error: {e}")
            return None

    async def remove_background_local(
        self,
        local_path: str,
        save_locally: bool = True
    ) -> Dict[str, Any]:
        """
        Remove background from local image file.

        Args:
            local_path: Path to local image file
            save_locally: Save to local file (default True)

        Returns:
            {
                "success": True/False,
                "image_url": str (local path),
                "error": str (if failed)
            }
        """
        if not self.available:
            return {"success": False, "error": "rembg library not installed"}

        logger.info(f"[Rembg] Processing local file: {local_path}")

        try:
            # Read local file
            local_file = Path(local_path)
            if not local_file.exists():
                return {"success": False, "error": f"File not found: {local_path}"}

            image_data = local_file.read_bytes()
            logger.info(f"[Rembg] Read: {len(image_data)} bytes")

            # Process in thread pool (rembg is CPU-intensive)
            loop = asyncio.get_event_loop()
            result_image = await loop.run_in_executor(
                None,
                self._process_sync,
                image_data
            )

            if result_image is None:
                return {"success": False, "error": "Processing failed"}

            # Save result
            if save_locally:
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                filename = f"bg_removed_{uuid.uuid4().hex[:8]}.png"
                filepath = OUTPUT_DIR / filename
                result_image.save(filepath, format="PNG")
                local_url = f"/static/generated/{filename}"
                logger.info(f"[Rembg] Saved: {local_url}")
                return {"success": True, "image_url": local_url}

            # Return as base64 (not recommended for large images)
            import base64
            buffered = io.BytesIO()
            result_image.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            return {"success": True, "image_url": f"data:image/png;base64,{img_base64}"}

        except Exception as e:
            logger.exception(f"[Rembg] Exception: {e}")
            return {"success": False, "error": str(e)}
