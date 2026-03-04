"""
Social Media Publishing Service
Supports: Facebook Pages, Instagram Business, TikTok

Architecture:
- OAuth 2.0 flow for account binding
- Publishing via platform APIs
- Mock mode for development/testing (when API keys not configured)

Facebook/Instagram:
  - Uses Meta Graph API v19.0
  - Facebook: POST /me/feed (text) or /me/photos (image) or /me/videos (video)
  - Instagram: POST /{ig-user-id}/media + /{ig-user-id}/media_publish

TikTok:
  - Uses TikTok Content Posting API v2
  - POST /v2/post/publish/video/init/ + /v2/post/publish/status/fetch/
"""
import hashlib
import hmac
import json
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import httpx

from app.core.config import settings


# ─── Platform Config ──────────────────────────────────────────────────────────

FACEBOOK_APP_ID = getattr(settings, "FACEBOOK_APP_ID", "")
FACEBOOK_APP_SECRET = getattr(settings, "FACEBOOK_APP_SECRET", "")
INSTAGRAM_APP_ID = getattr(settings, "INSTAGRAM_APP_ID", FACEBOOK_APP_ID)  # Same Meta app
INSTAGRAM_APP_SECRET = getattr(settings, "INSTAGRAM_APP_SECRET", FACEBOOK_APP_SECRET)
TIKTOK_CLIENT_KEY = getattr(settings, "TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = getattr(settings, "TIKTOK_CLIENT_SECRET", "")

FACEBOOK_GRAPH_URL = "https://graph.facebook.com/v19.0"
TIKTOK_API_URL = "https://open.tiktokapis.com"

# OAuth redirect URIs (must match app settings)
FACEBOOK_REDIRECT_URI = f"{settings.BACKEND_URL}/api/v1/social/oauth/facebook/callback"
INSTAGRAM_REDIRECT_URI = f"{settings.BACKEND_URL}/api/v1/social/oauth/instagram/callback"
TIKTOK_REDIRECT_URI = f"{settings.BACKEND_URL}/api/v1/social/oauth/tiktok/callback"

# Mock mode: enabled when API keys are not configured
MOCK_MODE = not (FACEBOOK_APP_ID and TIKTOK_CLIENT_KEY)


# ─── OAuth URL Generators ─────────────────────────────────────────────────────

def get_facebook_oauth_url(state: str) -> str:
    """Generate Facebook OAuth authorization URL."""
    if MOCK_MODE:
        # Return a mock URL for development
        return f"{settings.FRONTEND_URL}/dashboard/social-accounts?mock_connect=facebook&state={state}"

    params = {
        "client_id": FACEBOOK_APP_ID,
        "redirect_uri": FACEBOOK_REDIRECT_URI,
        "scope": "pages_show_list,pages_read_engagement,pages_manage_posts,publish_to_groups",
        "response_type": "code",
        "state": state,
    }
    return f"https://www.facebook.com/v19.0/dialog/oauth?{urllib.parse.urlencode(params)}"


def get_instagram_oauth_url(state: str) -> str:
    """Generate Instagram OAuth authorization URL (via Meta Graph API)."""
    if MOCK_MODE:
        return f"{settings.FRONTEND_URL}/dashboard/social-accounts?mock_connect=instagram&state={state}"

    params = {
        "client_id": INSTAGRAM_APP_ID,
        "redirect_uri": INSTAGRAM_REDIRECT_URI,
        "scope": "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement",
        "response_type": "code",
        "state": state,
    }
    return f"https://www.facebook.com/v19.0/dialog/oauth?{urllib.parse.urlencode(params)}"


def get_tiktok_oauth_url(state: str) -> str:
    """Generate TikTok OAuth authorization URL."""
    if MOCK_MODE:
        return f"{settings.FRONTEND_URL}/dashboard/social-accounts?mock_connect=tiktok&state={state}"

    params = {
        "client_key": TIKTOK_CLIENT_KEY,
        "redirect_uri": TIKTOK_REDIRECT_URI,
        "scope": "user.info.basic,video.publish,video.upload",
        "response_type": "code",
        "state": state,
    }
    return f"https://www.tiktok.com/v2/auth/authorize/?{urllib.parse.urlencode(params)}"


# ─── OAuth Token Exchange ─────────────────────────────────────────────────────

async def exchange_facebook_code(code: str) -> Dict[str, Any]:
    """Exchange Facebook auth code for access token."""
    if MOCK_MODE:
        return {
            "access_token": f"mock_fb_token_{int(time.time())}",
            "token_type": "bearer",
            "expires_in": 5184000,  # 60 days
        }

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{FACEBOOK_GRAPH_URL}/oauth/access_token",
            params={
                "client_id": FACEBOOK_APP_ID,
                "client_secret": FACEBOOK_APP_SECRET,
                "redirect_uri": FACEBOOK_REDIRECT_URI,
                "code": code,
            }
        )
        resp.raise_for_status()
        return resp.json()


async def exchange_instagram_code(code: str) -> Dict[str, Any]:
    """Exchange Instagram auth code for access token (same as Facebook)."""
    if MOCK_MODE:
        return {
            "access_token": f"mock_ig_token_{int(time.time())}",
            "token_type": "bearer",
            "expires_in": 5184000,
        }

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{FACEBOOK_GRAPH_URL}/oauth/access_token",
            params={
                "client_id": INSTAGRAM_APP_ID,
                "client_secret": INSTAGRAM_APP_SECRET,
                "redirect_uri": INSTAGRAM_REDIRECT_URI,
                "code": code,
            }
        )
        resp.raise_for_status()
        return resp.json()


async def exchange_tiktok_code(code: str) -> Dict[str, Any]:
    """Exchange TikTok auth code for access token."""
    if MOCK_MODE:
        return {
            "access_token": f"mock_tt_token_{int(time.time())}",
            "refresh_token": f"mock_tt_refresh_{int(time.time())}",
            "open_id": f"mock_open_id_{int(time.time())}",
            "expires_in": 86400,
            "refresh_expires_in": 31536000,
            "scope": "user.info.basic,video.publish",
        }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{TIKTOK_API_URL}/v2/oauth/token/",
            data={
                "client_key": TIKTOK_CLIENT_KEY,
                "client_secret": TIKTOK_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": TIKTOK_REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        return resp.json().get("data", {})


# ─── Account Info Fetchers ────────────────────────────────────────────────────

async def get_facebook_user_info(access_token: str) -> Dict[str, Any]:
    """Get Facebook user/page info."""
    if MOCK_MODE or access_token.startswith("mock_"):
        return {
            "id": "mock_fb_user_123",
            "name": "測試粉絲專頁",
            "picture": {"data": {"url": "https://via.placeholder.com/100"}},
            "pages": [{"id": "mock_page_123", "name": "測試粉絲專頁", "access_token": access_token}],
        }

    async with httpx.AsyncClient() as client:
        # Get user info
        resp = await client.get(
            f"{FACEBOOK_GRAPH_URL}/me",
            params={"fields": "id,name,picture", "access_token": access_token}
        )
        resp.raise_for_status()
        user_data = resp.json()

        # Get pages
        pages_resp = await client.get(
            f"{FACEBOOK_GRAPH_URL}/me/accounts",
            params={"access_token": access_token}
        )
        pages_data = pages_resp.json().get("data", [])
        user_data["pages"] = pages_data
        return user_data


async def get_instagram_user_info(access_token: str) -> Dict[str, Any]:
    """Get Instagram Business account info via Graph API."""
    if MOCK_MODE or access_token.startswith("mock_"):
        return {
            "id": "mock_ig_user_456",
            "username": "mock_instagram_user",
            "name": "Mock Instagram",
            "profile_picture_url": "https://via.placeholder.com/100",
            "ig_user_id": "mock_ig_user_456",
        }

    async with httpx.AsyncClient() as client:
        # First get Facebook pages, then find connected Instagram accounts
        pages_resp = await client.get(
            f"{FACEBOOK_GRAPH_URL}/me/accounts",
            params={"access_token": access_token}
        )
        pages = pages_resp.json().get("data", [])

        for page in pages:
            ig_resp = await client.get(
                f"{FACEBOOK_GRAPH_URL}/{page['id']}",
                params={
                    "fields": "instagram_business_account",
                    "access_token": page.get("access_token", access_token)
                }
            )
            ig_data = ig_resp.json()
            if "instagram_business_account" in ig_data:
                ig_id = ig_data["instagram_business_account"]["id"]
                # Get IG account details
                ig_info_resp = await client.get(
                    f"{FACEBOOK_GRAPH_URL}/{ig_id}",
                    params={
                        "fields": "id,username,name,profile_picture_url",
                        "access_token": page.get("access_token", access_token)
                    }
                )
                ig_info = ig_info_resp.json()
                ig_info["ig_user_id"] = ig_id
                ig_info["page_id"] = page["id"]
                ig_info["page_access_token"] = page.get("access_token", access_token)
                return ig_info

    return {"error": "No Instagram Business account found"}


async def get_tiktok_user_info(access_token: str, open_id: str) -> Dict[str, Any]:
    """Get TikTok user info."""
    if MOCK_MODE or access_token.startswith("mock_"):
        return {
            "open_id": open_id or "mock_open_id_789",
            "display_name": "Mock TikTok User",
            "avatar_url": "https://via.placeholder.com/100",
            "follower_count": 0,
        }

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{TIKTOK_API_URL}/v2/user/info/",
            params={"fields": "open_id,display_name,avatar_url,follower_count"},
            headers={"Authorization": f"Bearer {access_token}"}
        )
        resp.raise_for_status()
        return resp.json().get("data", {}).get("user", {})


# ─── Publishing Functions ─────────────────────────────────────────────────────

async def publish_to_facebook(
    access_token: str,
    page_id: str,
    message: str,
    media_url: Optional[str] = None,
    is_video: bool = False,
) -> Dict[str, Any]:
    """
    Publish content to a Facebook Page.
    - Text only: POST /page_id/feed
    - Image: POST /page_id/photos
    - Video: POST /page_id/videos
    """
    if MOCK_MODE or access_token.startswith("mock_"):
        return {
            "success": True,
            "post_id": f"mock_fb_post_{int(time.time())}",
            "post_url": "https://www.facebook.com/mock_post",
            "platform": "facebook",
            "mock": True,
        }

    async with httpx.AsyncClient(timeout=60.0) as client:
        if media_url and is_video:
            # Video post
            resp = await client.post(
                f"{FACEBOOK_GRAPH_URL}/{page_id}/videos",
                data={
                    "access_token": access_token,
                    "description": message,
                    "file_url": media_url,
                }
            )
        elif media_url:
            # Image post
            resp = await client.post(
                f"{FACEBOOK_GRAPH_URL}/{page_id}/photos",
                data={
                    "access_token": access_token,
                    "caption": message,
                    "url": media_url,
                }
            )
        else:
            # Text post
            resp = await client.post(
                f"{FACEBOOK_GRAPH_URL}/{page_id}/feed",
                data={
                    "access_token": access_token,
                    "message": message,
                }
            )

        resp.raise_for_status()
        data = resp.json()
        post_id = data.get("id", "")
        return {
            "success": True,
            "post_id": post_id,
            "post_url": f"https://www.facebook.com/{post_id.replace('_', '/posts/')}",
            "platform": "facebook",
        }


async def publish_to_instagram(
    access_token: str,
    ig_user_id: str,
    caption: str,
    media_url: str,
    is_video: bool = False,
) -> Dict[str, Any]:
    """
    Publish content to Instagram Business account.
    Requires media_url (Instagram requires a public URL).
    Flow: Create media container → Publish container
    """
    if MOCK_MODE or access_token.startswith("mock_"):
        return {
            "success": True,
            "post_id": f"mock_ig_post_{int(time.time())}",
            "post_url": "https://www.instagram.com/p/mock_post/",
            "platform": "instagram",
            "mock": True,
        }

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Step 1: Create media container
        if is_video:
            container_resp = await client.post(
                f"{FACEBOOK_GRAPH_URL}/{ig_user_id}/media",
                data={
                    "access_token": access_token,
                    "caption": caption,
                    "video_url": media_url,
                    "media_type": "REELS",
                }
            )
        else:
            container_resp = await client.post(
                f"{FACEBOOK_GRAPH_URL}/{ig_user_id}/media",
                data={
                    "access_token": access_token,
                    "caption": caption,
                    "image_url": media_url,
                }
            )

        container_resp.raise_for_status()
        container_id = container_resp.json().get("id")

        if not container_id:
            return {"success": False, "error": "Failed to create media container"}

        # Step 2: Wait for video processing (if video)
        if is_video:
            await _wait_for_instagram_video(access_token, container_id)

        # Step 3: Publish the container
        publish_resp = await client.post(
            f"{FACEBOOK_GRAPH_URL}/{ig_user_id}/media_publish",
            data={
                "access_token": access_token,
                "creation_id": container_id,
            }
        )
        publish_resp.raise_for_status()
        post_id = publish_resp.json().get("id", "")

        return {
            "success": True,
            "post_id": post_id,
            "post_url": f"https://www.instagram.com/p/{post_id}/",
            "platform": "instagram",
        }


async def _wait_for_instagram_video(access_token: str, container_id: str, max_wait: int = 60):
    """Wait for Instagram video container to finish processing."""
    import asyncio
    for _ in range(max_wait // 5):
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{FACEBOOK_GRAPH_URL}/{container_id}",
                params={"fields": "status_code", "access_token": access_token}
            )
            status = resp.json().get("status_code", "")
            if status == "FINISHED":
                return
            elif status == "ERROR":
                raise Exception("Instagram video processing failed")
        await asyncio.sleep(5)


async def publish_to_tiktok(
    access_token: str,
    open_id: str,
    title: str,
    video_url: str,
    privacy_level: str = "PUBLIC_TO_EVERYONE",
) -> Dict[str, Any]:
    """
    Publish video to TikTok using Content Posting API.
    Note: TikTok only supports video publishing (not images).
    Flow: Initialize upload → Upload video → Check status
    """
    if MOCK_MODE or access_token.startswith("mock_"):
        return {
            "success": True,
            "post_id": f"mock_tt_post_{int(time.time())}",
            "post_url": "https://www.tiktok.com/@mock_user/video/mock_post",
            "platform": "tiktok",
            "mock": True,
        }

    async with httpx.AsyncClient(timeout=120.0) as client:
        # Step 1: Initialize video upload
        init_resp = await client.post(
            f"{TIKTOK_API_URL}/v2/post/publish/video/init/",
            json={
                "post_info": {
                    "title": title[:150],  # TikTok title max 150 chars
                    "privacy_level": privacy_level,
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                },
                "source_info": {
                    "source": "PULL_FROM_URL",
                    "video_url": video_url,
                }
            },
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            }
        )
        init_resp.raise_for_status()
        init_data = init_resp.json().get("data", {})
        publish_id = init_data.get("publish_id")

        if not publish_id:
            return {"success": False, "error": "Failed to initialize TikTok upload"}

        return {
            "success": True,
            "post_id": publish_id,
            "post_url": "https://www.tiktok.com/",  # URL not available immediately
            "platform": "tiktok",
            "note": "Video is being processed by TikTok. It will appear in your profile shortly.",
        }


# ─── Utility ──────────────────────────────────────────────────────────────────

def is_mock_mode() -> bool:
    """Check if running in mock mode."""
    return MOCK_MODE
