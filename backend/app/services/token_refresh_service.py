"""
Token Refresh Service
Automatically refreshes social media tokens before they expire.
"""
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.social_account import SocialAccount
from app.services import social_media_service as svc

logger = logging.getLogger(__name__)

# Refresh tokens if they expire within this window
REFRESH_WINDOW_HOURS = 24


async def ensure_valid_token(db: AsyncSession, account: SocialAccount) -> bool:
    """
    Check if a social account's token is valid. If expiring soon, attempt refresh.
    Returns True if token is valid (or was refreshed), False if refresh failed.
    """
    if not account.token_expires_at:
        # No expiry tracked — assume valid (legacy accounts)
        return True

    now = datetime.now(timezone.utc)
    expires_at = account.token_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    # Token still valid and not near expiry
    if expires_at > now + timedelta(hours=REFRESH_WINDOW_HOURS):
        return True

    # Token expired or expiring soon — attempt refresh
    logger.info(f"Token for {account.platform} (user={account.user_id}) expiring/expired, refreshing...")

    try:
        if account.platform == "facebook" or account.platform == "instagram":
            token_data = await svc.refresh_facebook_token(account.access_token)
            account.access_token = token_data.get("access_token", account.access_token)
            expires_in = token_data.get("expires_in", 5184000)

        elif account.platform == "tiktok":
            if not account.refresh_token:
                logger.warning(f"No refresh token for TikTok account {account.id}")
                return False
            token_data = await svc.refresh_tiktok_token(account.refresh_token)
            account.access_token = token_data.get("access_token", account.access_token)
            if token_data.get("refresh_token"):
                account.refresh_token = token_data["refresh_token"]
            expires_in = token_data.get("expires_in", 86400)

        elif account.platform == "youtube":
            if not account.refresh_token:
                logger.warning(f"No refresh token for YouTube account {account.id}")
                return False
            token_data = await svc.refresh_youtube_token(account.refresh_token)
            account.access_token = token_data.get("access_token", account.access_token)
            expires_in = token_data.get("expires_in", 3600)

        else:
            logger.warning(f"Unknown platform {account.platform}, skipping refresh")
            return True

        account.token_expires_at = now + timedelta(seconds=expires_in)
        account.updated_at = now
        await db.commit()
        logger.info(f"Token refreshed for {account.platform} (user={account.user_id})")
        return True

    except Exception as e:
        logger.error(f"Failed to refresh token for {account.platform}: {e}")
        return False
