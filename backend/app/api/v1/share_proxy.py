"""
Public CORS-friendly media proxy for the Web Share / auto-download fallback.

Some upstream provider CDNs (PiAPI, Pollo, Kling) serve generated media WITHOUT
`Access-Control-Allow-Origin`, so the browser cannot fetch them via
`fetch().blob()` to feed `navigator.share({files:[...]})` or trigger an in-page
download. This endpoint streams those bytes through the backend and re-emits
them with `Access-Control-Allow-Origin: *`.

Security:
- ALLOW only http(s) URLs whose host matches a fixed allowlist of provider
  CDNs and our own GCS bucket. This prevents the endpoint from being used as
  an open SSRF/proxy.
- No auth required (the underlying URLs are already publicly reachable from
  the user's browser).
- Cap response size at 50 MB to avoid runaway streams.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# Hosts we are willing to proxy. Strict match: exact hostname OR a true
# subdomain (host endswith "." + entry). NEVER use plain `endswith(entry)`
# because it would let `evilpiapi.ai` impersonate `piapi.ai`.
_ALLOWED_HOSTS = (
    "storage.googleapis.com",
    "vidgo-media-vidgo-ai.storage.googleapis.com",
    "piapi.ai",
    "theapi.app",
    "pollo.ai",
    "klingai.com",
    "kling-ai.com",
    "a2e.ai",
)
# These suffixes match many GCP-managed buckets/CDNs; safe because we only
# allow them as a true subdomain match.
_ALLOWED_PARENT_DOMAINS = (
    "googleusercontent.com",
    "googleapis.com",
)

_MAX_BYTES = 50 * 1024 * 1024  # 50 MB hard cap


def _host_allowed(host: str) -> bool:
    host = (host or "").lower().strip(".")
    if not host:
        return False
    if host in _ALLOWED_HOSTS:
        return True
    # True subdomain check (must end with ".<entry>", not just "<entry>").
    if any(host.endswith("." + h) for h in _ALLOWED_HOSTS):
        return True
    if any(host.endswith("." + p) for p in _ALLOWED_PARENT_DOMAINS):
        return True
    return False


@router.get("/share-media")
async def share_media_proxy(url: str = Query(..., min_length=8, max_length=2048)):
    """Stream a remote media file with CORS=* so the browser can build a File()."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid URL scheme")
    if not _host_allowed(parsed.hostname or ""):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Host not allowed")

    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Expose-Headers": "Content-Type, Content-Length, Content-Disposition",
        "Cache-Control": "public, max-age=600",
    }

    client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)
    try:
        upstream = await client.send(client.build_request("GET", url), stream=True)
    except Exception as exc:  # pragma: no cover - network errors
        await client.aclose()
        logger.warning("[share_proxy] upstream fetch failed url=%s err=%s", url, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Upstream fetch failed")

    if upstream.status_code != 200:
        await upstream.aclose()
        await client.aclose()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Upstream {upstream.status_code}")

    media_type = upstream.headers.get("content-type", "application/octet-stream")
    content_length = upstream.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > _MAX_BYTES:
        await upstream.aclose()
        await client.aclose()
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Media too large")

    headers = dict(cors_headers)
    if content_length:
        headers["Content-Length"] = content_length

    async def _gen():
        sent = 0
        try:
            async for chunk in upstream.aiter_bytes(64 * 1024):
                sent += len(chunk)
                if sent > _MAX_BYTES:
                    logger.warning("[share_proxy] aborting oversized stream url=%s sent=%d", url, sent)
                    break
                yield chunk
        finally:
            # Always release upstream connection AND the client, even if the
            # downstream consumer disconnects mid-stream (StreamingResponse
            # invokes the generator's aclose on disconnect, which triggers
            # this finally block).
            try:
                await upstream.aclose()
            finally:
                await client.aclose()

    return StreamingResponse(_gen(), media_type=media_type, headers=headers)
