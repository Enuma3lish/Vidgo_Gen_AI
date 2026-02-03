"""
PiAPI Client - AI Image Generation and Processing

API: https://api.piapi.ai
Features:
- Text-to-Image (Flux model) - ~$0.005/image
- Virtual Try-On (Kling AI) - $0.05/image  
- Flux Fill (I2I/Inpaint)
- Remove Background - $0.001/image
"""
import asyncio
import logging
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)

# Output directory
OUTPUT_DIR = Path("/app/static/generated")


class PiAPIClient:
    """PiAPI client for T2I generation."""

    BASE_URL = "https://api.piapi.ai/api/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }

    async def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        save_locally: bool = True
    ) -> Dict[str, Any]:
        """
        Generate image from text prompt.

        Args:
            prompt: Text description
            width: Image width (default 1024)
            height: Image height (default 1024)
            save_locally: Save to local file (default True)

        Returns:
            {
                "success": True/False,
                "image_url": str (local path or remote URL),
                "error": str (if failed)
            }
        """
        if not self.api_key:
            return {"success": False, "error": "PiAPI key not configured"}

        logger.info(f"[PiAPI] Generating: {prompt[:50]}...")

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Create task
                response = await client.post(
                    f"{self.BASE_URL}/task",
                    headers=self.headers,
                    json={
                        "model": "Qubico/flux1-schnell",
                        "task_type": "txt2img",
                        "input": {
                            "prompt": prompt,
                            "width": width,
                            "height": height
                        }
                    }
                )

                if response.status_code not in [200, 201]:
                    error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"[PiAPI] Create task failed: {error}")
                    return {"success": False, "error": error}

                data = response.json()
                task_id = data.get("data", {}).get("task_id")

                if not task_id:
                    return {"success": False, "error": "No task_id in response"}

                logger.info(f"[PiAPI] Task created: {task_id}")

                # Poll for result
                for attempt in range(60):
                    await asyncio.sleep(2)

                    status_resp = await client.get(
                        f"{self.BASE_URL}/task/{task_id}",
                        headers=self.headers
                    )

                    if status_resp.status_code != 200:
                        continue

                    status_data = status_resp.json()
                    status = status_data.get("data", {}).get("status", "")

                    if status == "completed":
                        output = status_data.get("data", {}).get("output", {})

                        # PiAPI returns image_url directly in output
                        image_url = output.get("image_url")

                        if not image_url:
                            # Fallback: check for images array
                            images = output.get("images", [])
                            if images:
                                image_url = images[0].get("url")

                        if not image_url:
                            logger.error(f"[PiAPI] Output structure: {output}")
                            return {"success": False, "error": "No image_url in output"}

                        if save_locally:
                            local_path = await self._download(client, image_url)
                            if local_path:
                                logger.info(f"[PiAPI] Saved: {local_path}")
                                return {"success": True, "image_url": local_path}

                        return {"success": True, "image_url": image_url}

                    elif status == "failed":
                        error = status_data.get("data", {}).get("error", "Unknown error")
                        logger.error(f"[PiAPI] Task failed: {error}")
                        return {"success": False, "error": error}

                return {"success": False, "error": "Timeout (2 min)"}

        except Exception as e:
            logger.exception(f"[PiAPI] Exception: {e}")
            return {"success": False, "error": str(e)}

    def _to_base64_data_url(self, file_path: str) -> Optional[str]:
        """
        Convert a local file to base64 data URL.

        Args:
            file_path: Path to local image file

        Returns:
            Base64 data URL string or None if failed
        """
        try:
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"[PiAPI] File not found: {file_path}")
                return None

            # Determine MIME type
            suffix = path.suffix.lower()
            mime_types = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".gif": "image/gif"
            }
            mime_type = mime_types.get(suffix, "image/png")

            # Read and encode
            import base64
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode("utf-8")

            return f"data:{mime_type};base64,{data}"
        except Exception as e:
            logger.warning(f"[PiAPI] Failed to encode file: {e}")
            return None

    def _resolve_image_input(self, image_input: str) -> str:
        """
        Resolve image input to a format PiAPI can use.

        Handles:
        - Remote URLs (https://...) - pass through
        - Local paths (/app/static/...) - convert to base64 data URL
        - Relative paths (/static/...) - convert to base64 data URL

        Args:
            image_input: URL or local path

        Returns:
            URL or base64 data URL
        """
        if image_input.startswith(("http://", "https://", "data:")):
            return image_input

        # Handle local paths
        if image_input.startswith("/static/"):
            local_path = f"/app{image_input}"
        elif image_input.startswith("/app/"):
            local_path = image_input
        else:
            local_path = image_input

        # Try to convert to base64
        base64_url = self._to_base64_data_url(local_path)
        if base64_url:
            logger.info(f"[PiAPI] Converted local file to base64: {local_path[:50]}...")
            return base64_url

        # Fallback to original (will likely fail but provides better error message)
        logger.warning(f"[PiAPI] Could not resolve image: {image_input}")
        return image_input

    async def virtual_try_on(
        self,
        model_image_url: str,
        garment_image_url: str,
        upper_garment_url: Optional[str] = None,
        lower_garment_url: Optional[str] = None,
        batch_size: int = 1,
        save_locally: bool = True
    ) -> Dict[str, Any]:
        """
        Virtual Try-On using Kling AI via PiAPI.
        Reference: https://piapi.ai/docs/kling-api/virtual-try-on-api

        This is a TRUE virtual try-on that overlays clothing onto a model photo.

        Args:
            model_image_url: Photo of person/model (URL or local path)
            garment_image_url: Clothing image (full body garment)
            upper_garment_url: Upper body garment only (optional)
            lower_garment_url: Lower body garment only (optional)
            batch_size: Number of output images (1-4, default 1)
            save_locally: Save to local file (default True)

        Returns:
            {"success": True, "image_url": str} or {"success": False, "error": str}

        Note:
            Local file paths (starting with /static/ or /app/) are automatically
            converted to base64 data URLs for PiAPI compatibility.
        """
        if not self.api_key:
            return {"success": False, "error": "PiAPI key not configured"}

        # Resolve image inputs (convert local files to base64 if needed)
        model_input = self._resolve_image_input(model_image_url)
        garment_input = self._resolve_image_input(garment_image_url) if garment_image_url else None

        logger.info(f"[PiAPI] Virtual Try-On: model={'base64...' if model_input.startswith('data:') else model_input[:50]}...")

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                # Build input data
                input_data = {
                    "model_input": model_input,
                    "batch_size": batch_size
                }

                # Add garment input - either full body or upper/lower
                if garment_input:
                    input_data["dress_input"] = garment_input
                else:
                    if upper_garment_url:
                        input_data["upper_input"] = self._resolve_image_input(upper_garment_url)
                    if lower_garment_url:
                        input_data["lower_input"] = self._resolve_image_input(lower_garment_url)

                # Create task
                response = await client.post(
                    f"{self.BASE_URL}/task",
                    headers=self.headers,
                    json={
                        "model": "kling",
                        "task_type": "ai_try_on",
                        "input": input_data
                    }
                )

                if response.status_code not in [200, 201]:
                    error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"[PiAPI] Virtual Try-On create task failed: {error}")
                    return {"success": False, "error": error}

                data = response.json()
                task_id = data.get("data", {}).get("task_id")

                if not task_id:
                    logger.error(f"[PiAPI] Response: {data}")
                    return {"success": False, "error": "No task_id in response"}

                logger.info(f"[PiAPI] Virtual Try-On task created: {task_id}")

                # Poll for result (Try-On takes longer)
                for attempt in range(90):  # 3 min timeout
                    await asyncio.sleep(2)

                    status_resp = await client.get(
                        f"{self.BASE_URL}/task/{task_id}",
                        headers=self.headers
                    )

                    if status_resp.status_code != 200:
                        continue

                    status_data = status_resp.json()
                    status = status_data.get("data", {}).get("status", "")

                    if status == "completed":
                        output = status_data.get("data", {}).get("output", {})

                        # Try to get image_url
                        image_url = output.get("image_url")

                        # Fallback: check for images array
                        if not image_url:
                            images = output.get("images", [])
                            if images:
                                img = images[0]
                                image_url = img.get("url") if isinstance(img, dict) else img

                        if not image_url:
                            logger.error(f"[PiAPI] Try-On output structure: {output}")
                            return {"success": False, "error": "No image_url in output"}

                        if save_locally:
                            local_path = await self._download(client, image_url)
                            if local_path:
                                logger.info(f"[PiAPI] Virtual Try-On saved: {local_path}")
                                return {"success": True, "image_url": local_path}

                        return {"success": True, "image_url": image_url}

                    elif status == "failed":
                        error = status_data.get("data", {}).get("error", "Unknown error")
                        logger.error(f"[PiAPI] Virtual Try-On failed: {error}")
                        return {"success": False, "error": error}

                return {"success": False, "error": "Timeout (3 min)"}

        except Exception as e:
            logger.exception(f"[PiAPI] Virtual Try-On exception: {e}")
            return {"success": False, "error": str(e)}

    async def flux_fill(
        self,
        image_url: str,
        prompt: str,
        mask_url: Optional[str] = None,
        save_locally: bool = True
    ) -> Dict[str, Any]:
        """
        Image-to-Image using Flux Fill (Inpaint/Outpaint).
        
        Use this for Product Scene to change background while keeping product.
        If no mask is provided, the background is automatically detected and replaced.
        
        Reference: https://piapi.ai/docs/flux-api/image-to-image
        
        Args:
            image_url: Source image URL or local path (product with current background)
            prompt: Description of desired background/scene
            mask_url: Optional mask image (white = keep, black = replace). If None, auto-detects.
            save_locally: Save to local file (default True)
            
        Returns:
            {"success": True, "image_url": str} or {"success": False, "error": str}
        """
        if not self.api_key:
            return {"success": False, "error": "PiAPI key not configured"}
        
        # Resolve image input (local paths → base64)
        image_input = self._resolve_image_input(image_url)
        
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                input_data = {
                    "prompt": prompt,
                    "image": image_input,
                }
                
                # Add mask if provided
                if mask_url:
                    input_data["mask"] = self._resolve_image_input(mask_url)
                
                # Create task - using Flux Fill model for I2I
                response = await client.post(
                    f"{self.BASE_URL}/task",
                    headers=self.headers,
                    json={
                        "model": "Qubico/flux1-dev-fill",  # Flux Fill for inpaint/I2I
                        "task_type": "img2img",
                        "input": input_data
                    }
                )
                
                if response.status_code not in [200, 201]:
                    # Fallback to flux-schnell with image reference
                    logger.warning(f"[PiAPI] Flux Fill failed, trying flux-schnell...")
                    response = await client.post(
                        f"{self.BASE_URL}/task",
                        headers=self.headers,
                        json={
                            "model": "Qubico/flux1-schnell",
                            "task_type": "img2img",
                            "input": input_data
                        }
                    )
                
                if response.status_code not in [200, 201]:
                    error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"[PiAPI] Flux Fill create task failed: {error}")
                    return {"success": False, "error": error}
                
                data = response.json()
                task_id = data.get("data", {}).get("task_id")
                
                if not task_id:
                    logger.error(f"[PiAPI] Response: {data}")
                    return {"success": False, "error": "No task_id in response"}
                
                logger.info(f"[PiAPI] Flux Fill task created: {task_id}")
                
                # Poll for result
                for attempt in range(90):  # 3 min timeout
                    await asyncio.sleep(2)
                    
                    status_resp = await client.get(
                        f"{self.BASE_URL}/task/{task_id}",
                        headers=self.headers
                    )
                    
                    if status_resp.status_code != 200:
                        continue
                    
                    status_data = status_resp.json()
                    status = status_data.get("data", {}).get("status", "")
                    
                    if status == "completed":
                        output = status_data.get("data", {}).get("output", {})
                        
                        image_url_result = output.get("image_url")
                        if not image_url_result:
                            images = output.get("images", [])
                            if images:
                                img = images[0]
                                image_url_result = img.get("url") if isinstance(img, dict) else img
                        
                        if not image_url_result:
                            logger.error(f"[PiAPI] Flux Fill output: {output}")
                            return {"success": False, "error": "No image_url in output"}
                        
                        if save_locally:
                            local_path = await self._download(client, image_url_result)
                            if local_path:
                                logger.info(f"[PiAPI] Flux Fill saved: {local_path}")
                                return {"success": True, "image_url": local_path}
                        
                        return {"success": True, "image_url": image_url_result}
                    
                    elif status == "failed":
                        error = status_data.get("data", {}).get("error", "Unknown error")
                        logger.error(f"[PiAPI] Flux Fill failed: {error}")
                        return {"success": False, "error": error}
                
                return {"success": False, "error": "Timeout (3 min)"}
        
        except Exception as e:
            logger.exception(f"[PiAPI] Flux Fill exception: {e}")
            return {"success": False, "error": str(e)}

    async def remove_background(
        self,
        image_url: str,
        save_locally: bool = True
    ) -> Dict[str, Any]:
        """
        Remove background from image using PiAPI Remove Background API.
        
        Cost: $0.001 per image
        Reference: https://piapi.ai/docs/remove-background-api
        
        Args:
            image_url: Source image URL or local path
            save_locally: Save to local file (default True)
            
        Returns:
            {"success": True, "image_url": str} or {"success": False, "error": str}
        """
        if not self.api_key:
            return {"success": False, "error": "PiAPI key not configured"}
        
        # Resolve image input (local paths → base64)
        image_input = self._resolve_image_input(image_url)
        
        logger.info(f"[PiAPI] Remove Background: {image_url[:50]}...")
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Create task - using Qubico/image-toolkit model
                # Reference: https://piapi.ai/docs/remove-background-api
                response = await client.post(
                    f"{self.BASE_URL}/task",
                    headers=self.headers,
                    json={
                        "model": "Qubico/image-toolkit",
                        "task_type": "background-remove",
                        "input": {
                            "image": image_input
                        }
                    }
                )
                
                if response.status_code not in [200, 201]:
                    error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"[PiAPI] Remove BG create task failed: {error}")
                    return {"success": False, "error": error}
                
                data = response.json()
                task_id = data.get("data", {}).get("task_id")
                
                if not task_id:
                    logger.error(f"[PiAPI] Response: {data}")
                    return {"success": False, "error": "No task_id in response"}
                
                logger.info(f"[PiAPI] Remove BG task created: {task_id}")
                
                # Poll for result (usually very fast)
                for attempt in range(30):  # 1 min timeout
                    await asyncio.sleep(2)
                    
                    status_resp = await client.get(
                        f"{self.BASE_URL}/task/{task_id}",
                        headers=self.headers
                    )
                    
                    if status_resp.status_code != 200:
                        continue
                    
                    status_data = status_resp.json()
                    status = status_data.get("data", {}).get("status", "")
                    
                    if status == "completed":
                        output = status_data.get("data", {}).get("output", {})
                        
                        image_url_result = output.get("image_url")
                        if not image_url_result:
                            images = output.get("images", [])
                            if images:
                                img = images[0]
                                image_url_result = img.get("url") if isinstance(img, dict) else img
                        
                        if not image_url_result:
                            logger.error(f"[PiAPI] Remove BG output: {output}")
                            return {"success": False, "error": "No image_url in output"}
                        
                        if save_locally:
                            local_path = await self._download(client, image_url_result)
                            if local_path:
                                logger.info(f"[PiAPI] Remove BG saved: {local_path}")
                                return {"success": True, "image_url": local_path}
                        
                        return {"success": True, "image_url": image_url_result}
                    
                    elif status == "failed":
                        error = status_data.get("data", {}).get("error", "Unknown error")
                        logger.error(f"[PiAPI] Remove BG failed: {error}")
                        return {"success": False, "error": error}
                
                return {"success": False, "error": "Timeout (1 min)"}
        
        except Exception as e:
            logger.exception(f"[PiAPI] Remove BG exception: {e}")
            return {"success": False, "error": str(e)}

    async def _download(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        """Download image and save locally."""
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            response = await client.get(url, follow_redirects=True)
            if response.status_code == 200:
                filename = f"piapi_{uuid.uuid4().hex[:8]}.png"
                filepath = OUTPUT_DIR / filename
                filepath.write_bytes(response.content)
                return f"/static/generated/{filename}"
        except Exception as e:
            logger.warning(f"[PiAPI] Download failed: {e}")
        return None


