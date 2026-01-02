"""
Session API Endpoints
Based on ARCHITECTURE_FINAL.md specification

Provides:
- User heartbeat for online tracking
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from typing import Optional

from app.api.deps import get_current_user_optional
from app.models.user import User
from app.services.session_tracker import session_tracker
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class HeartbeatResponse(BaseModel):
    success: bool
    online_users: Optional[int] = None
    timestamp: Optional[float] = None
    error: Optional[str] = None


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Record user heartbeat for online tracking.

    Should be called by frontend every 30-60 seconds.
    Updates:
    - User's last seen timestamp
    - Online user count by tier
    - Active users today (HyperLogLog)
    """
    # Get user info
    if current_user:
        user_id = str(current_user.id)
        plan = current_user.plan or "demo"
    else:
        # For anonymous users, use IP-based session
        client_ip = request.client.host if request.client else "unknown"
        user_id = f"anon:{client_ip}"
        plan = "anonymous"

    # Get client IP for rate limiting
    ip_address = request.client.host if request.client else None

    # Record heartbeat
    result = await session_tracker.heartbeat(
        user_id=user_id,
        plan=plan,
        ip_address=ip_address
    )

    return HeartbeatResponse(**result)


@router.get("/online-count")
async def get_online_count():
    """Get current number of online users (public endpoint)"""
    count = await session_tracker.get_online_count()
    return {"online_users": count}
