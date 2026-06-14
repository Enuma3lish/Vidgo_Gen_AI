"""
Social Media Integration API Routes
Handles: OAuth binding, account management, content publishing

Endpoints:
  GET  /social/accounts          - List connected accounts
  GET  /social/oauth/{platform}  - Start OAuth flow
  GET  /social/oauth/{platform}/callback - OAuth callback
  POST /social/oauth/{platform}/mock-connect - Mock connect (dev mode)
  DELETE /social/accounts/{platform} - Disconnect account
  POST /social/publish/{generation_id} - Publish work to social media
"""
import secrets
import urllib.parse
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.social_account import SocialAccount
from app.models.social_post import SocialPost
from app.models.user import User
from app.models.user_generation import UserGeneration
from app.services import social_media_service as svc
from app.services.social_media_service import is_mock_mode
from app.services.token_refresh_service import ensure_valid_token
from app.core.config import settings

# Subscription check helper
def is_subscribed_user(user: User) -> bool:
    from app.api.v1.user_works import is_subscribed_user as _check
    return _check(user)

router = APIRouter(prefix="/social", tags=["social"])

SUPPORTED_PLATFORMS = ["facebook", "instagram", "tiktok", "youtube"]


# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class SocialAccountInfo(BaseModel):
    platform: str
    platform_username: Optional[str]
    platform_avatar: Optional[str]
    platform_user_id: Optional[str]
    is_active: bool
    connected_at: Optional[datetime]

    class Config:
        from_attributes = True


class PublishRequest(BaseModel):
    platforms: List[str]          # ['facebook', 'instagram', 'tiktok', 'youtube']
    caption: str = ""             # Post caption / description
    privacy_level: str = "PUBLIC_TO_EVERYONE"  # TikTok privacy


class PublishResult(BaseModel):
    platform: str
    success: bool
    post_url: Optional[str] = None
    error: Optional[str] = None
    mock: bool = False


class MockConnectRequest(BaseModel):
    platform: str
    username: str = "測試帳號"


# ─── Account Management ───────────────────────────────────────────────────────

@router.get("/accounts", response_model=List[SocialAccountInfo])
async def list_connected_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all connected social media accounts for the current user."""
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.user_id == current_user.id,
            SocialAccount.is_active == True,
        )
    )
    accounts = result.scalars().all()
    return [
        SocialAccountInfo(
            platform=acc.platform,
            platform_username=acc.platform_username,
            platform_avatar=acc.platform_avatar,
            platform_user_id=acc.platform_user_id,
            is_active=acc.is_active,
            connected_at=acc.created_at,
        )
        for acc in accounts
    ]


@router.delete("/accounts/{platform}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_account(
    platform: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect a social media account."""
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")

    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.user_id == current_user.id,
            SocialAccount.platform == platform,
        )
    )
    account = result.scalar_one_or_none()
    if account:
        await db.delete(account)
        await db.commit()


# ─── OAuth Flow ───────────────────────────────────────────────────────────────

@router.get("/oauth/{platform}")
async def start_oauth(
    platform: str,
    current_user: User = Depends(get_current_user),
):
    """
    Start OAuth flow for a platform.
    Returns redirect URL to platform's authorization page.
    """
    if not is_subscribed_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required to connect social media accounts",
        )

    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")

    # Generate state token (includes user_id for security)
    state = f"{current_user.id}:{secrets.token_urlsafe(16)}"
    state_encoded = urllib.parse.quote(state)

    if platform == "facebook":
        url = svc.get_facebook_oauth_url(state_encoded)
    elif platform == "instagram":
        url = svc.get_instagram_oauth_url(state_encoded)
    elif platform == "tiktok":
        url = svc.get_tiktok_oauth_url(state_encoded)
    elif platform == "youtube":
        url = svc.get_youtube_oauth_url(state_encoded)
    else:
        raise HTTPException(status_code=400, detail="Unsupported platform")

    return {"oauth_url": url, "mock_mode": is_mock_mode()}


@router.get("/oauth/facebook/callback")
async def facebook_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle Facebook OAuth callback."""
    try:
        user_id = urllib.parse.unquote(state).split(":")[0]
        token_data = await svc.exchange_facebook_code(code)
        access_token = token_data.get("access_token", "")
        user_info = await svc.get_facebook_user_info(access_token)

        pages = user_info.get("pages", [])
        page_id = pages[0]["id"] if pages else user_info.get("id", "")
        page_token = pages[0].get("access_token", access_token) if pages else access_token

        await _upsert_social_account(
            db=db,
            user_id=user_id,
            platform="facebook",
            platform_user_id=user_info.get("id", ""),
            platform_username=user_info.get("name", ""),
            platform_avatar=user_info.get("picture", {}).get("data", {}).get("url", ""),
            access_token=page_token,
            page_id=page_id,
            token_expires_in=token_data.get("expires_in", 5184000),
        )

        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/social-accounts?connected=facebook"
        )
    except Exception as e:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/social-accounts?error=facebook&msg={str(e)}"
        )


@router.get("/oauth/instagram/callback")
async def instagram_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle Instagram OAuth callback."""
    try:
        user_id = urllib.parse.unquote(state).split(":")[0]
        token_data = await svc.exchange_instagram_code(code)
        access_token = token_data.get("access_token", "")
        user_info = await svc.get_instagram_user_info(access_token)

        await _upsert_social_account(
            db=db,
            user_id=user_id,
            platform="instagram",
            platform_user_id=user_info.get("ig_user_id", user_info.get("id", "")),
            platform_username=user_info.get("username", user_info.get("name", "")),
            platform_avatar=user_info.get("profile_picture_url", ""),
            access_token=user_info.get("page_access_token", access_token),
            page_id=user_info.get("page_id", ""),
            token_expires_in=token_data.get("expires_in", 5184000),
        )

        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/social-accounts?connected=instagram"
        )
    except Exception as e:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/social-accounts?error=instagram&msg={str(e)}"
        )


@router.get("/oauth/tiktok/callback")
async def tiktok_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle TikTok OAuth callback."""
    try:
        user_id = urllib.parse.unquote(state).split(":")[0]
        token_data = await svc.exchange_tiktok_code(code)
        access_token = token_data.get("access_token", "")
        open_id = token_data.get("open_id", "")
        user_info = await svc.get_tiktok_user_info(access_token, open_id)

        await _upsert_social_account(
            db=db,
            user_id=user_id,
            platform="tiktok",
            platform_user_id=open_id,
            platform_username=user_info.get("display_name", ""),
            platform_avatar=user_info.get("avatar_url", ""),
            access_token=access_token,
            refresh_token=token_data.get("refresh_token", ""),
            open_id=open_id,
            token_expires_in=token_data.get("expires_in", 86400),
        )

        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/social-accounts?connected=tiktok"
        )
    except Exception as e:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/social-accounts?error=tiktok&msg={str(e)}"
        )


@router.get("/oauth/youtube/callback")
async def youtube_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle YouTube/Google OAuth callback."""
    try:
        user_id = urllib.parse.unquote(state).split(":")[0]
        token_data = await svc.exchange_youtube_code(code)
        access_token = token_data.get("access_token", "")
        channel_info = await svc.get_youtube_user_info(access_token)

        await _upsert_social_account(
            db=db,
            user_id=user_id,
            platform="youtube",
            platform_user_id=channel_info.get("channel_id", ""),
            platform_username=channel_info.get("title", ""),
            platform_avatar=channel_info.get("thumbnail_url", ""),
            access_token=access_token,
            refresh_token=token_data.get("refresh_token", ""),
            token_expires_in=token_data.get("expires_in", 3600),
        )

        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/social-accounts?connected=youtube"
        )
    except Exception as e:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/social-accounts?error=youtube&msg={str(e)}"
        )


# ─── Mock Connect (Development Mode) ─────────────────────────────────────────

@router.post("/oauth/mock-connect")
async def mock_connect(
    req: MockConnectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mock connect a social media account (development mode only).
    Simulates OAuth flow without real API keys.
    """
    if not is_mock_mode():
        raise HTTPException(
            status_code=400,
            detail="Mock connect is only available in development mode"
        )

    if not is_subscribed_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required to connect social media accounts",
        )

    if req.platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {req.platform}")

    import time
    mock_avatars = {
        "facebook": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/05/Facebook_Logo_%282019%29.png/240px-Facebook_Logo_%282019%29.png",
        "instagram": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Instagram_icon.png/240px-Instagram_icon.png",
        "tiktok": "https://upload.wikimedia.org/wikipedia/en/thumb/a/a9/TikTok_logo.svg/240px-TikTok_logo.svg.png",
        "youtube": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/09/YouTube_full-color_icon_%282017%29.svg/240px-YouTube_full-color_icon_%282017%29.svg.png",
    }

    await _upsert_social_account(
        db=db,
        user_id=str(current_user.id),
        platform=req.platform,
        platform_user_id=f"mock_{req.platform}_{int(time.time())}",
        platform_username=req.username or f"Mock {req.platform.capitalize()} User",
        platform_avatar=mock_avatars.get(req.platform, ""),
        access_token=f"mock_{req.platform}_token_{int(time.time())}",
    )

    return {"success": True, "platform": req.platform, "mock": True}


# ─── Publishing ───────────────────────────────────────────────────────────────

@router.post("/publish/{generation_id}", response_model=List[PublishResult])
async def publish_work(
    generation_id: str,
    req: PublishRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Publish a generation result to one or more social media platforms.
    Requires active subscription.
    """
    if not is_subscribed_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required to publish to social media",
        )

    # Get the generation
    gen_result = await db.execute(
        select(UserGeneration).where(
            UserGeneration.id == generation_id,
            UserGeneration.user_id == current_user.id,
        )
    )
    generation = gen_result.scalar_one_or_none()
    if not generation:
        raise HTTPException(status_code=404, detail="Work not found")

    media_url = generation.result_video_url or generation.result_image_url
    if not media_url:
        raise HTTPException(status_code=400, detail="No media available for this work")

    is_video = bool(generation.result_video_url)
    caption = req.caption or f"Created with VidGo AI ✨ #{generation.tool_type.replace('_', '')}"

    results = []

    for platform in req.platforms:
        if platform not in SUPPORTED_PLATFORMS:
            results.append(PublishResult(platform=platform, success=False, error="Unsupported platform"))
            continue

        # Get connected account
        acc_result = await db.execute(
            select(SocialAccount).where(
                SocialAccount.user_id == current_user.id,
                SocialAccount.platform == platform,
                SocialAccount.is_active == True,
            )
        )
        account = acc_result.scalar_one_or_none()

        if not account:
            results.append(PublishResult(
                platform=platform,
                success=False,
                error=f"No connected {platform} account. Please connect your account first."
            ))
            continue

        # Refresh token if needed
        token_valid = await ensure_valid_token(db, account)
        if not token_valid:
            results.append(PublishResult(
                platform=platform,
                success=False,
                error=f"Token expired for {platform}. Please reconnect your account."
            ))
            continue

        try:
            if platform == "facebook":
                result = await svc.publish_to_facebook(
                    access_token=account.access_token,
                    page_id=account.page_id or account.platform_user_id,
                    message=caption,
                    media_url=media_url,
                    is_video=is_video,
                )
            elif platform == "instagram":
                if not media_url:
                    results.append(PublishResult(
                        platform=platform,
                        success=False,
                        error="Instagram requires media (image or video)"
                    ))
                    continue
                result = await svc.publish_to_instagram(
                    access_token=account.access_token,
                    ig_user_id=account.platform_user_id,
                    caption=caption,
                    media_url=media_url,
                    is_video=is_video,
                )
            elif platform == "tiktok":
                if not is_video:
                    results.append(PublishResult(
                        platform=platform,
                        success=False,
                        error="TikTok only supports video content"
                    ))
                    continue
                result = await svc.publish_to_tiktok(
                    access_token=account.access_token,
                    open_id=account.open_id or account.platform_user_id,
                    title=caption[:150],
                    video_url=media_url,
                    privacy_level=req.privacy_level,
                )
            elif platform == "youtube":
                if not is_video:
                    results.append(PublishResult(
                        platform=platform,
                        success=False,
                        error="YouTube only supports video content"
                    ))
                    continue
                result = await svc.publish_to_youtube(
                    access_token=account.access_token,
                    title=caption[:100],
                    description=caption,
                    video_url=media_url,
                )
            else:
                result = {"success": False, "error": "Unknown platform"}

            # Update last_used_at
            account.last_used_at = datetime.now(timezone.utc)

            # Record post in history
            if result.get("success"):
                social_post = SocialPost(
                    user_id=current_user.id,
                    social_account_id=account.id,
                    generation_id=generation_id,
                    platform=platform,
                    platform_post_id=result.get("post_id", ""),
                    post_url=result.get("post_url", ""),
                    caption=caption,
                    media_type="video" if is_video else "image",
                    status="published",
                    published_at=datetime.now(timezone.utc),
                )
                db.add(social_post)

            await db.commit()

            results.append(PublishResult(
                platform=platform,
                success=result.get("success", False),
                post_url=result.get("post_url"),
                error=result.get("error"),
                mock=result.get("mock", False),
            ))

        except Exception as e:
            results.append(PublishResult(
                platform=platform,
                success=False,
                error=str(e),
            ))

    return results


# ─── Post History ─────────────────────────────────────────────────────────────

class SocialPostInfo(BaseModel):
    id: str
    platform: str
    post_url: Optional[str]
    caption: Optional[str]
    media_type: Optional[str]
    status: str
    likes_count: int = 0
    comments_count: int = 0
    shares_count: int = 0
    views_count: int = 0
    published_at: Optional[datetime]

    class Config:
        from_attributes = True


class PostAnalytics(BaseModel):
    total_posts: int
    by_platform: dict
    total_likes: int
    total_comments: int
    total_shares: int
    total_views: int


@router.get("/posts", response_model=List[SocialPostInfo])
async def get_post_history(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    platform: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated post history for the current user."""
    from sqlalchemy import func as sqlfunc

    query = select(SocialPost).where(SocialPost.user_id == current_user.id)
    if platform:
        query = query.where(SocialPost.platform == platform)
    query = query.order_by(SocialPost.published_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    posts = result.scalars().all()

    return [
        SocialPostInfo(
            id=str(p.id),
            platform=p.platform,
            post_url=p.post_url,
            caption=p.caption,
            media_type=p.media_type,
            status=p.status,
            likes_count=p.likes_count or 0,
            comments_count=p.comments_count or 0,
            shares_count=p.shares_count or 0,
            views_count=p.views_count or 0,
            published_at=p.published_at,
        )
        for p in posts
    ]


@router.get("/posts/analytics", response_model=PostAnalytics)
async def get_post_analytics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated social media analytics for the current user."""
    from sqlalchemy import func as sqlfunc

    # Total posts
    total_result = await db.execute(
        select(sqlfunc.count(SocialPost.id)).where(
            SocialPost.user_id == current_user.id,
            SocialPost.status == "published",
        )
    )
    total_posts = total_result.scalar() or 0

    # By platform
    platform_result = await db.execute(
        select(SocialPost.platform, sqlfunc.count(SocialPost.id))
        .where(SocialPost.user_id == current_user.id, SocialPost.status == "published")
        .group_by(SocialPost.platform)
    )
    by_platform = {row[0]: row[1] for row in platform_result.all()}

    # Aggregate metrics
    metrics_result = await db.execute(
        select(
            sqlfunc.coalesce(sqlfunc.sum(SocialPost.likes_count), 0),
            sqlfunc.coalesce(sqlfunc.sum(SocialPost.comments_count), 0),
            sqlfunc.coalesce(sqlfunc.sum(SocialPost.shares_count), 0),
            sqlfunc.coalesce(sqlfunc.sum(SocialPost.views_count), 0),
        ).where(SocialPost.user_id == current_user.id)
    )
    metrics = metrics_result.one()

    return PostAnalytics(
        total_posts=total_posts,
        by_platform=by_platform,
        total_likes=metrics[0],
        total_comments=metrics[1],
        total_shares=metrics[2],
        total_views=metrics[3],
    )


# ─── Helper ───────────────────────────────────────────────────────────────────

async def _upsert_social_account(
    db: AsyncSession,
    user_id: str,
    platform: str,
    platform_user_id: str,
    platform_username: str,
    platform_avatar: str,
    access_token: str,
    refresh_token: str = "",
    page_id: str = "",
    open_id: str = "",
    token_expires_in: int = 0,
):
    """Create or update a social account record."""
    import uuid as _uuid
    from datetime import timedelta

    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.user_id == _uuid.UUID(user_id),
            SocialAccount.platform == platform,
        )
    )
    account = result.scalar_one_or_none()

    token_expires_at = None
    if token_expires_in > 0:
        token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_expires_in)

    if account:
        account.platform_user_id = platform_user_id
        account.platform_username = platform_username
        account.platform_avatar = platform_avatar
        account.access_token = access_token
        if refresh_token:
            account.refresh_token = refresh_token
        if page_id:
            account.page_id = page_id
        if open_id:
            account.open_id = open_id
        if token_expires_at:
            account.token_expires_at = token_expires_at
        account.is_active = True
        account.updated_at = datetime.now(timezone.utc)
    else:
        account = SocialAccount(
            user_id=_uuid.UUID(user_id),
            platform=platform,
            platform_user_id=platform_user_id,
            platform_username=platform_username,
            platform_avatar=platform_avatar,
            access_token=access_token,
            refresh_token=refresh_token or None,
            page_id=page_id or None,
            open_id=open_id or None,
            token_expires_at=token_expires_at,
            is_active=True,
        )
        db.add(account)

    await db.commit()
    return account
