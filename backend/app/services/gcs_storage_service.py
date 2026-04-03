"""
GCS Storage Service — downloads generated media from temporary CDN URLs
and persists them in Google Cloud Storage.

Both Pollo.ai and PiAPI return temporary CDN URLs (14-day expiry).
This service downloads the content and uploads to the project's GCS bucket
so media URLs remain accessible beyond the provider's retention period.

Uses Application Default Credentials on Cloud Run (via service account).
For local dev, set GOOGLE_APPLICATION_CREDENTIALS or use `gcloud auth application-default login`.
"""
import hashlib
import logging
import os
import uuid
from datetime import timedelta
from typing import Optional

import httpx
from google.cloud import storage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class GCSStorageService:
    """Upload generated media to GCS and return public/signed URLs."""

    def __init__(self):
        settings = get_settings()
        self.bucket_name = settings.GCS_BUCKET
        self.enabled = bool(self.bucket_name)
        self._client: Optional[storage.Client] = None

    @property
    def client(self) -> storage.Client:
        if self._client is None:
            self._client = storage.Client()
        return self._client

    @property
    def bucket(self) -> storage.Bucket:
        return self.client.bucket(self.bucket_name)

    async def persist_url(
        self,
        source_url: str,
        media_type: str = "image",
        user_id: Optional[str] = None,
        filename_hint: Optional[str] = None,
    ) -> str:
        """
        Download media from a temporary CDN URL and upload to GCS.

        Args:
            source_url: Temporary URL from Pollo/PiAPI CDN
            media_type: "image", "video", "audio", "model"
            user_id: Optional user ID for path organization
            filename_hint: Optional filename hint

        Returns:
            Public GCS URL (or signed URL if bucket is not public)
        """
        if not self.enabled:
            logger.debug("GCS not configured — returning original URL")
            return source_url

        try:
            # Download from CDN
            async with httpx.AsyncClient(timeout=120.0) as http:
                response = await http.get(source_url)
                response.raise_for_status()
                content = response.content
                content_type = response.headers.get("content-type", self._guess_content_type(media_type))

            # Generate GCS path
            ext = self._extension_from_content_type(content_type, media_type)
            file_id = filename_hint or uuid.uuid4().hex[:12]
            prefix = f"generated/{media_type}"
            if user_id:
                prefix = f"users/{user_id}/{media_type}"
            blob_name = f"{prefix}/{file_id}{ext}"

            # Upload to GCS
            blob = self.bucket.blob(blob_name)
            blob.upload_from_string(content, content_type=content_type)

            # Return public URL or signed URL
            if self.bucket.iam_configuration.uniform_bucket_level_access_enabled:
                # Use signed URL for uniform access buckets
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(days=7),
                    method="GET",
                )
            else:
                blob.make_public()
                url = blob.public_url

            logger.info(f"[GCS] Persisted {media_type}: {blob_name} ({len(content)} bytes)")
            return url

        except Exception as e:
            logger.error(f"[GCS] Failed to persist {source_url}: {e}")
            # Return original URL as fallback — still usable for 14 days
            return source_url

    async def delete_blob(self, blob_name: str) -> bool:
        """Delete a blob from GCS."""
        if not self.enabled:
            return False
        try:
            blob = self.bucket.blob(blob_name)
            blob.delete()
            logger.info(f"[GCS] Deleted: {blob_name}")
            return True
        except Exception as e:
            logger.error(f"[GCS] Failed to delete {blob_name}: {e}")
            return False

    def _guess_content_type(self, media_type: str) -> str:
        return {
            "image": "image/png",
            "video": "video/mp4",
            "audio": "audio/wav",
            "model": "model/gltf-binary",
        }.get(media_type, "application/octet-stream")

    def _extension_from_content_type(self, content_type: str, media_type: str) -> str:
        ct_map = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
            "video/mp4": ".mp4",
            "video/webm": ".webm",
            "audio/wav": ".wav",
            "audio/mpeg": ".mp3",
            "model/gltf-binary": ".glb",
        }
        ext = ct_map.get(content_type)
        if ext:
            return ext
        # Fallback by media type
        return {
            "image": ".png",
            "video": ".mp4",
            "audio": ".wav",
            "model": ".glb",
        }.get(media_type, ".bin")


# ── Singleton ──

_gcs_instance: Optional[GCSStorageService] = None


def get_gcs_storage() -> GCSStorageService:
    global _gcs_instance
    if _gcs_instance is None:
        _gcs_instance = GCSStorageService()
    return _gcs_instance
