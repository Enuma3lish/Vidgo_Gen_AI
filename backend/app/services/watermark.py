"""
Watermark Service
Adds watermarks to demo videos for free tier users
"""
import logging
from typing import Optional, Tuple
from pathlib import Path
import tempfile
import subprocess
import shutil

logger = logging.getLogger(__name__)


class WatermarkService:
    """
    Service for adding watermarks to videos.
    Uses FFmpeg for video processing.
    """

    def __init__(
        self,
        watermark_text: str = "VidGo Demo",
        watermark_image_path: Optional[str] = None,
        font_size: int = 24,
        opacity: float = 0.7,
        position: str = "bottom_right"  # top_left, top_right, bottom_left, bottom_right, center
    ):
        self.watermark_text = watermark_text
        self.watermark_image_path = watermark_image_path
        self.font_size = font_size
        self.opacity = opacity
        self.position = position
        self._ffmpeg_available = self._check_ffmpeg()

    def _check_ffmpeg(self) -> bool:
        """Check if FFmpeg is available"""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.warning("FFmpeg not found. Watermarking will be disabled.")
            return False

    def _get_position_filter(self, video_width: int = 1280, video_height: int = 720) -> str:
        """Get FFmpeg position filter string based on position setting"""
        padding = 20

        positions = {
            "top_left": f"x={padding}:y={padding}",
            "top_right": f"x=W-w-{padding}:y={padding}",
            "bottom_left": f"x={padding}:y=H-h-{padding}",
            "bottom_right": f"x=W-w-{padding}:y=H-h-{padding}",
            "center": "x=(W-w)/2:y=(H-h)/2",
        }

        return positions.get(self.position, positions["bottom_right"])

    async def add_text_watermark(
        self,
        input_path: str,
        output_path: str,
        custom_text: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Add text watermark to video using FFmpeg

        Args:
            input_path: Path to input video
            output_path: Path to save watermarked video
            custom_text: Optional custom watermark text

        Returns:
            Tuple of (success, message)
        """
        if not self._ffmpeg_available:
            return False, "FFmpeg not available"

        text = custom_text or self.watermark_text
        position = self._get_position_filter()

        # FFmpeg drawtext filter
        drawtext_filter = (
            f"drawtext=text='{text}':"
            f"fontsize={self.font_size}:"
            f"fontcolor=white@{self.opacity}:"
            f"{position}:"
            f"shadowcolor=black@0.5:"
            f"shadowx=2:shadowy=2"
        )

        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", input_path,
                    "-vf", drawtext_filter,
                    "-codec:a", "copy",
                    "-preset", "fast",
                    output_path
                ],
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )

            if result.returncode == 0:
                return True, "Watermark added successfully"
            else:
                logger.error(f"FFmpeg error: {result.stderr}")
                return False, f"FFmpeg error: {result.stderr[:200]}"

        except subprocess.TimeoutExpired:
            return False, "Watermarking timed out"
        except Exception as e:
            logger.error(f"Watermarking error: {e}")
            return False, str(e)

    async def add_image_watermark(
        self,
        input_path: str,
        output_path: str,
        watermark_image: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Add image watermark to video using FFmpeg

        Args:
            input_path: Path to input video
            output_path: Path to save watermarked video
            watermark_image: Path to watermark image (PNG with transparency recommended)

        Returns:
            Tuple of (success, message)
        """
        if not self._ffmpeg_available:
            return False, "FFmpeg not available"

        image_path = watermark_image or self.watermark_image_path
        if not image_path or not Path(image_path).exists():
            return False, "Watermark image not found"

        position = self._get_position_filter()

        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", input_path,
                    "-i", image_path,
                    "-filter_complex",
                    f"[1:v]format=rgba,colorchannelmixer=aa={self.opacity}[watermark];"
                    f"[0:v][watermark]overlay={position}",
                    "-codec:a", "copy",
                    "-preset", "fast",
                    output_path
                ],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0:
                return True, "Image watermark added successfully"
            else:
                logger.error(f"FFmpeg error: {result.stderr}")
                return False, f"FFmpeg error: {result.stderr[:200]}"

        except subprocess.TimeoutExpired:
            return False, "Watermarking timed out"
        except Exception as e:
            logger.error(f"Watermarking error: {e}")
            return False, str(e)

    async def process_demo_video(
        self,
        input_url: str,
        demo_id: str,
        use_image_watermark: bool = False
    ) -> Tuple[bool, Optional[str], str]:
        """
        Process a demo video - download, watermark, and prepare for serving

        Args:
            input_url: URL of the original video
            demo_id: Demo video ID for naming
            use_image_watermark: Whether to use image instead of text watermark

        Returns:
            Tuple of (success, output_path, message)
        """
        import httpx

        if not self._ffmpeg_available:
            # Return original URL if FFmpeg not available
            return True, input_url, "FFmpeg not available - using original"

        try:
            # Create temp directory
            with tempfile.TemporaryDirectory() as temp_dir:
                input_path = Path(temp_dir) / f"input_{demo_id}.mp4"
                output_path = Path(temp_dir) / f"watermarked_{demo_id}.mp4"

                # Download video
                async with httpx.AsyncClient() as client:
                    response = await client.get(input_url, timeout=60.0)
                    if response.status_code != 200:
                        return False, None, f"Failed to download video: {response.status_code}"

                    with open(input_path, "wb") as f:
                        f.write(response.content)

                # Add watermark
                if use_image_watermark and self.watermark_image_path:
                    success, message = await self.add_image_watermark(
                        str(input_path),
                        str(output_path)
                    )
                else:
                    success, message = await self.add_text_watermark(
                        str(input_path),
                        str(output_path)
                    )

                if not success:
                    return False, None, message

                # TODO: Upload to object storage and return URL
                # For now, return local path (in production, upload to S3/similar)
                return True, str(output_path), "Watermark added"

        except Exception as e:
            logger.error(f"Error processing demo video: {e}")
            return False, None, str(e)

    def get_watermark_info(self) -> dict:
        """Get current watermark configuration"""
        return {
            "text": self.watermark_text,
            "has_image": bool(self.watermark_image_path),
            "font_size": self.font_size,
            "opacity": self.opacity,
            "position": self.position,
            "ffmpeg_available": self._ffmpeg_available
        }


# Default watermark service instance
_watermark_service: Optional[WatermarkService] = None


def get_watermark_service() -> WatermarkService:
    """Get or create watermark service singleton"""
    global _watermark_service
    if _watermark_service is None:
        _watermark_service = WatermarkService()
    return _watermark_service
