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
import mimetypes
import os
import threading
import time
import uuid
from datetime import timedelta
from typing import Optional
from urllib.parse import urlparse

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
        # In-instance cache of freshly-signed V4 URLs so repeat read paths
        # (use-preset clicks, gallery thumbnails) don't re-run the IAM signBlob
        # network calls every time. Keyed by (blob, disposition, response_type,
        # expiration_hours). Cached for SIGNED_URL_CACHE_TTL — comfortably less
        # than the 24h URL expiry, so a served URL always has hours of validity.
        self._signed_url_cache: dict = {}
        self._signed_url_cache_ttl = 12 * 3600  # 12h (URLs are valid 24h)
        self._signed_url_cache_max = 10000
        # Whether objects in this bucket carry per-object public ACLs (set by
        # persist's make_public()) → their bare storage.googleapis.com URL works
        # forever with no signing. Resolved once (a bucket property) and cached.
        self._objects_public: Optional[bool] = None

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
                content_type = self._normalize_content_type(
                    source_url,
                    response.headers.get("content-type"),
                    media_type,
                )

            # Generate GCS path
            ext = self._extension_from_content_type(content_type, media_type, source_url)
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

    def upload_public(
        self,
        data: bytes,
        blob_name: str,
        content_type: str = "image/png",
    ) -> str:
        """
        Upload data to GCS and make it publicly accessible.
        Returns the permanent public URL (no expiry).

        Used for example mode input images generated by Gemini.
        """
        if not self.enabled:
            raise RuntimeError("GCS not configured — set GCS_BUCKET env var")

        blob = self.bucket.blob(blob_name)
        blob.upload_from_string(data, content_type=content_type)
        blob.make_public()
        logger.info(f"[GCS] Uploaded public: {blob_name} ({len(data)} bytes)")
        return blob.public_url

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

    async def safe_persist_url(
        self,
        url: Optional[str],
        media_type: str,
        user_id: Optional[str] = None,
    ) -> Optional[str]:
        """Idempotent wrapper around `persist_url` with safe short-circuits.

        Returns the original URL when:
          - URL is None / empty
          - URL is already a GCS public URL or local /static/ path
          - GCS is not configured
        Catches any exception and returns the original URL so a persistence
        failure never breaks the user-facing flow (provider CDN still serves
        the file for 14 days).
        """
        if not url:
            return url
        if "storage.googleapis.com" in url or url.startswith("/static/"):
            return url
        if not self.enabled:
            return url
        try:
            return await self.persist_url(
                source_url=url,
                media_type=media_type,
                user_id=user_id,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("safe_persist_url failed (%s, %s): %s", media_type, url, exc)
            return url

    def list_blob_names(self, prefix: str = "generated/") -> set:
        """List all blob names under a prefix. Returns set of blob names like 'generated/watermarked/foo.png'."""
        if not self.enabled:
            return set()
        try:
            blobs = self.client.list_blobs(self.bucket_name, prefix=prefix)
            return {blob.name for blob in blobs}
        except Exception as e:
            logger.warning(f"[GCS] list_blob_names failed: {e}")
            return set()

    # Class-level (singleton-shared) cache of {prefix: (set, expires_at_ts)} for
    # the existence checks, plus a per-prefix "refresh in flight" guard and a
    # lock to set it atomically.
    _blob_listing_cache: dict = {}
    _blob_refresh_inflight: dict = {}
    _blob_listing_lock = threading.Lock()

    def list_blob_names_cached(self, prefix: str = "generated/", ttl_seconds: int = 900) -> set:
        """Cached variant of `list_blob_names` for hot read paths, with
        stale-while-revalidate.

        Production discovered stale Material rows pointing at GCS objects that
        no longer exist (deleted by lifecycle, failed pregenerate uploads, etc.)
        — signing succeeds but the resulting URL 404s, breaking the LandingPage
        hero. The presets endpoint uses this set to drop dead rows.

        The GCS LIST is multi-second, so we never let it block a request once
        the cache is warm: a stale entry is returned IMMEDIATELY and refreshed
        in a background daemon thread. Only the very first call per prefix per
        instance pays the LIST cost. (The frontend also has an @error image
        fallback, so a briefly-stale entry never shows a broken image.)
        """
        now = time.time()
        cached = self._blob_listing_cache.get(prefix)
        if cached:
            names, expiry = cached
            if expiry <= now:
                # Stale → kick a single background refresh, serve stale now.
                self._kick_blob_refresh(prefix, ttl_seconds)
            return names
        # Cold (no cache yet, e.g. fresh instance): block once to populate so we
        # don't filter against an empty set and drop every row.
        names = self.list_blob_names(prefix)
        # Only cache non-empty results — an empty set might mean GCS error or
        # genuine empty prefix; we don't want to mask transient errors.
        if names:
            self._blob_listing_cache[prefix] = (names, now + ttl_seconds)
        return names

    def _kick_blob_refresh(self, prefix: str, ttl_seconds: int) -> None:
        """Refresh one prefix's blob listing in the background (at most one
        refresh in flight per prefix)."""
        with self._blob_listing_lock:
            if self._blob_refresh_inflight.get(prefix):
                return
            self._blob_refresh_inflight[prefix] = True

        def _run():
            try:
                names = self.list_blob_names(prefix)
                if names:
                    self._blob_listing_cache[prefix] = (names, time.time() + ttl_seconds)
            except Exception as e:  # noqa: BLE001
                logger.warning("[GCS] background blob-list refresh failed for %s: %s", prefix, e)
            finally:
                self._blob_refresh_inflight[prefix] = False

        threading.Thread(target=_run, name=f"gcs-blob-refresh-{prefix.strip('/')}", daemon=True).start()

    @staticmethod
    def extract_blob_name(url: Optional[str], bucket_name: str) -> Optional[str]:
        """Pull the bucket-relative blob name out of a (possibly signed) URL.

        Returns None if the URL doesn't reference our bucket so callers can
        skip existence checks for external URLs (Unsplash fallbacks, etc.).
        """
        if not url or not bucket_name:
            return None
        marker = f"/{bucket_name}/"
        if marker not in url:
            return None
        clean = url.split("?", 1)[0].split("#", 1)[0]
        try:
            return clean.split(marker, 1)[1] or None
        except IndexError:
            return None

    def refresh_signed_url(
        self,
        url: Optional[str],
        expiration_hours: int = 24,
        download_filename: Optional[str] = None,
        response_type: Optional[str] = None,
    ) -> Optional[str]:
        """
        If `url` points at our GCS bucket, return a fresh V4 signed URL.
        Otherwise return the URL unchanged.

        Use this on read paths (e.g. preset download / use-preset response)
        because long-stored signed URLs from `persist_url` expire after 7 days.

        When `download_filename` is set, the signed URL forces the browser to
        save the file as an attachment with that name (Content-Disposition).
        """
        if not url or not self.enabled:
            return url
        try:
            bucket_marker = f"/{self.bucket_name}/"
            if bucket_marker not in url:
                return url
            # Strip query/fragment, then take everything after the bucket name.
            clean = url.split("?", 1)[0].split("#", 1)[0]
            blob_name = clean.split(bucket_marker, 1)[1]
            if not blob_name:
                return url

            # Serve a recently-signed URL from the in-instance cache when one is
            # still well within its validity window — skips the per-URL IAM
            # signBlob round-trips (the dominant cost of use-preset/gallery
            # reads). Keyed so different dispositions/types don't collide.
            cache_key = (blob_name, download_filename or "", response_type or "", expiration_hours)
            now = time.monotonic()
            cached = self._signed_url_cache.get(cache_key)
            if cached and cached[0] > now:
                return cached[1]

            blob = self.bucket.blob(blob_name)

            sign_kwargs = {
                "version": "v4",
                "expiration": timedelta(hours=expiration_hours),
                "method": "GET",
            }
            if download_filename:
                # RFC 6266: quote the filename and provide UTF-8 fallback so
                # non-ASCII names (e.g. Chinese tool names) survive download.
                safe_ascii = download_filename.encode("ascii", "ignore").decode("ascii") or "vidgo-download"
                from urllib.parse import quote
                sign_kwargs["response_disposition"] = (
                    f'attachment; filename="{safe_ascii}"; '
                    f"filename*=UTF-8''{quote(download_filename)}"
                )
            if response_type:
                sign_kwargs["response_type"] = response_type

            # On Cloud Run the default credentials are GCE metadata tokens
            # which cannot sign locally. Fall back to IAM signBlob via the
            # service-account email + an OAuth access token so signed URLs
            # work without a private-key JSON file.
            def _store(signed: str) -> str:
                # Cap the cache so a long-lived instance can't grow unbounded;
                # a full clear is fine (worst case = a few re-signs).
                if len(self._signed_url_cache) >= self._signed_url_cache_max:
                    self._signed_url_cache.clear()
                self._signed_url_cache[cache_key] = (now + self._signed_url_cache_ttl, signed)
                return signed

            try:
                return _store(blob.generate_signed_url(**sign_kwargs))
            except Exception:
                import google.auth
                from google.auth.transport.requests import Request as AuthRequest

                creds, _ = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
                creds.refresh(AuthRequest())
                sa_email = (
                    getattr(creds, "service_account_email", None)
                    or os.getenv("GCS_SIGNER_SERVICE_ACCOUNT")
                )
                if not sa_email:
                    raise
                return _store(blob.generate_signed_url(
                    **sign_kwargs,
                    service_account_email=sa_email,
                    access_token=creds.token,
                ))
        except Exception as e:
            logger.warning(f"[GCS] refresh_signed_url failed for {url}: {e}")
            return url

    @property
    def objects_are_public(self) -> bool:
        """True when objects in this bucket are served via permanent public ACLs
        (persist/upload call make_public() unless the bucket uses uniform
        bucket-level access, which forbids object ACLs and forces signing).
        Cached — it's a bucket-level property that doesn't change at runtime."""
        if self._objects_public is None:
            try:
                self._objects_public = not self.bucket.iam_configuration.uniform_bucket_level_access_enabled
            except Exception:
                self._objects_public = False
        return self._objects_public

    def public_url(self, url: Optional[str]) -> Optional[str]:
        """Permanent, never-expiring URL for an object in our bucket.

        For shared, world-readable content (demo/example results — every visitor
        loads the SAME cached rows), there is no reason to mint an expiring
        signed URL: the objects are uploaded public (make_public), so the bare
        ``https://storage.googleapis.com/<bucket>/<blob>`` form works forever and
        is CDN/browser-cacheable. This strips any signature/query so the result
        is a stable, cacheable, TTL-free URL. Non-bucket URLs (Unsplash, etc.)
        pass through unchanged. If the bucket ever switches to uniform access
        (objects no longer public), we transparently fall back to a signed URL.
        """
        if not url or not self.enabled:
            return url
        if f"/{self.bucket_name}/" not in url:
            return url
        if not self.objects_are_public:
            return self.refresh_signed_url(url)
        return url.split("?", 1)[0].split("#", 1)[0]

    def _guess_content_type(self, media_type: str) -> str:
        return {
            "image": "image/png",
            "video": "video/mp4",
            "audio": "audio/wav",
            "model": "model/gltf-binary",
        }.get(media_type, "application/octet-stream")

    def _normalize_content_type(
        self,
        source_url: str,
        content_type: Optional[str],
        media_type: str,
    ) -> str:
        raw = (content_type or "").split(";", 1)[0].strip().lower()
        if raw and raw not in {"application/octet-stream", "binary/octet-stream"}:
            return raw

        path = urlparse(source_url).path
        guessed, _ = mimetypes.guess_type(path)
        if guessed:
            return guessed

        return self._guess_content_type(media_type)

    def _extension_from_content_type(
        self,
        content_type: str,
        media_type: str,
        source_url: Optional[str] = None,
    ) -> str:
        ct_map = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
            "video/mp4": ".mp4",
            "video/webm": ".webm",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/mpeg": ".mp3",
            "audio/mp3": ".mp3",
            "audio/mp4": ".m4a",
            "audio/x-m4a": ".m4a",
            "model/gltf-binary": ".glb",
        }
        ext = ct_map.get(content_type)
        if ext:
            return ext
        if source_url:
            path_ext = os.path.splitext(urlparse(source_url).path)[1].lower()
            if path_ext in {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm", ".wav", ".mp3", ".m4a", ".glb"}:
                return ".jpg" if path_ext == ".jpeg" else path_ext
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
