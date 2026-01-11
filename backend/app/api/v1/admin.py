"""
Admin Dashboard API Endpoints
Based on ARCHITECTURE_FINAL.md specification

Provides:
- Real-time statistics
- User management
- Material review
- Revenue analytics
- System health monitoring
"""
from fastapi import APIRouter, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.admin_dashboard import AdminDashboardService
from app.services.session_tracker import session_tracker
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class BanUserRequest(BaseModel):
    reason: Optional[str] = None


class AdjustCreditsRequest(BaseModel):
    amount: int
    reason: str


class ReviewMaterialRequest(BaseModel):
    action: str  # approve, reject, feature
    rejection_reason: Optional[str] = None


class StatsResponse(BaseModel):
    online_users: int
    by_tier: Dict[str, int]
    active_today: int
    timestamp: str


# ============================================================================
# Helper: Admin Check
# ============================================================================

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require user to be an admin"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ============================================================================
# Statistics Endpoints
# ============================================================================

@router.get("/stats/online")
async def get_online_stats(
    admin: User = Depends(require_admin)
):
    """Get real-time online user statistics"""
    return await session_tracker.get_stats()


@router.get("/stats/users-by-tier")
async def get_users_by_tier(
    admin: User = Depends(require_admin)
):
    """Get online users grouped by subscription tier"""
    return await session_tracker.get_online_by_tier()


@router.get("/stats/dashboard")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get comprehensive dashboard statistics"""
    service = AdminDashboardService(db)
    return await service.get_dashboard_stats()


# ============================================================================
# Chart Data Endpoints
# ============================================================================

@router.get("/charts/generations")
async def get_generation_chart(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get daily generation counts for chart"""
    service = AdminDashboardService(db)
    return await service.get_generation_trend(days)


@router.get("/charts/revenue")
async def get_revenue_chart(
    months: int = Query(default=12, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get monthly revenue for chart"""
    service = AdminDashboardService(db)
    return await service.get_revenue_trend(months)


@router.get("/charts/users-growth")
async def get_user_growth_chart(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get daily user registration counts for chart"""
    service = AdminDashboardService(db)
    return await service.get_user_growth_trend(days)


# ============================================================================
# User Management Endpoints
# ============================================================================

@router.get("/users")
async def get_users(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = None,
    plan: Optional[str] = None,
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get paginated list of users"""
    service = AdminDashboardService(db)
    users, total = await service.get_users(
        page=page,
        per_page=per_page,
        search=search,
        plan=plan,
        sort_by=sort_by,
        sort_order=sort_order
    )

    return {
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "name": u.name,
                "plan": u.plan,
                "is_active": u.is_active,
                "is_verified": u.is_verified,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "subscription_credits": u.subscription_credits,
                "purchased_credits": u.purchased_credits,
                "bonus_credits": u.bonus_credits
            }
            for u in users
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }


@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get detailed user information"""
    service = AdminDashboardService(db)
    result = await service.get_user_detail(user_id)

    if not result:
        raise HTTPException(status_code=404, detail="User not found")

    user = result["user"]
    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "plan": user.plan,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "is_admin": user.is_admin,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "subscription_credits": user.subscription_credits,
            "purchased_credits": user.purchased_credits,
            "bonus_credits": user.bonus_credits
        },
        "generation_count": result["generation_count"],
        "is_online": result["is_online"],
        "recent_transactions": [
            {
                "id": str(t.id),
                "amount": t.amount,
                "balance_after": t.balance_after,
                "transaction_type": t.transaction_type,
                "description": t.description,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in result["recent_transactions"]
        ]
    }


@router.post("/users/{user_id}/ban")
async def ban_user(
    user_id: str,
    request: BanUserRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Ban a user account"""
    service = AdminDashboardService(db)
    success, message = await service.ban_user(user_id, request.reason)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"success": True, "message": message}


@router.post("/users/{user_id}/unban")
async def unban_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Unban a user account"""
    service = AdminDashboardService(db)
    success, message = await service.unban_user(user_id)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"success": True, "message": message}


@router.post("/users/{user_id}/credits")
async def adjust_user_credits(
    user_id: str,
    request: AdjustCreditsRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Adjust user's credit balance"""
    service = AdminDashboardService(db)
    success, message = await service.adjust_credits(
        user_id,
        request.amount,
        request.reason
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"success": True, "message": message}


# ============================================================================
# Material Management Endpoints
# ============================================================================

@router.get("/materials")
async def get_materials(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    tool_type: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get paginated list of materials"""
    service = AdminDashboardService(db)
    materials, total = await service.get_materials(
        page=page,
        per_page=per_page,
        tool_type=tool_type,
        status=status
    )

    return {
        "materials": [
            {
                "id": str(m.id),
                "tool_type": m.tool_type.value if m.tool_type else None,
                "topic": m.topic,
                "status": m.status.value if m.status else None,
                "title_en": m.title_en,
                "title_zh": m.title_zh,
                "result_image_url": m.result_image_url,
                "result_video_url": m.result_video_url,
                "view_count": m.view_count,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in materials
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }


@router.post("/materials/{material_id}/review")
async def review_material(
    material_id: str,
    request: ReviewMaterialRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Review and update material status"""
    service = AdminDashboardService(db)
    success, message = await service.review_material(
        material_id,
        request.action,
        str(admin.id),
        request.rejection_reason
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"success": True, "message": message}


@router.get("/moderation/queue")
async def get_moderation_queue(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get materials pending review"""
    service = AdminDashboardService(db)
    materials = await service.get_moderation_queue(limit)

    return {
        "queue": [
            {
                "id": str(m.id),
                "tool_type": m.tool_type.value if m.tool_type else None,
                "topic": m.topic,
                "prompt": m.prompt[:100] if m.prompt else None,
                "result_image_url": m.result_image_url,
                "result_video_url": m.result_video_url,
                "source": m.source.value if m.source else None,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in materials
        ],
        "count": len(materials)
    }


# ============================================================================
# System Health Endpoints
# ============================================================================

@router.get("/health")
async def get_system_health(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Check health of all system components"""
    service = AdminDashboardService(db)
    return await service.get_system_health()


@router.get("/ai-services")
async def get_ai_services_status(
    admin: User = Depends(require_admin)
):
    """
    Check status of all AI services.

    Returns status of:
    - Wan 2.6 (T2I and I2V primary)
    - fal.ai (T2I and I2V rescue for Pro/Pro+)
    - Gemini (Interior Design rescue)
    - PiAPI (T2I, I2V, V2V, Interior)
    - A2E.ai (Avatar Lip-Sync)
    """
    from app.services.rescue_service import get_rescue_service

    rescue_service = get_rescue_service()
    status = await rescue_service.check_service_status()

    # Add A2E status
    try:
        from app.services.a2e_service import A2EAvatarService
        a2e = A2EAvatarService()
        a2e_test = await a2e.test_connection()
        status["a2e"] = {
            "status": "ok" if a2e_test.get("success") else "pending",
            "message": a2e_test.get("message") or a2e_test.get("error")
        }
    except Exception as e:
        status["a2e"] = {"status": "error", "error": str(e)}

    return {
        "services": status,
        "rescue_config": {
            "t2i": {"primary": "piapi_wan", "rescue": "pollo"},
            "i2v": {"primary": "piapi_wan", "rescue": "pollo"},
            "v2v": {"primary": "piapi_wan", "rescue": "pollo"},
            "interior": {"primary": "piapi_wan_doodle", "rescue": "gemini"},
            "avatar": {"primary": "a2e", "rescue": None}
        }
    }


@router.get("/generations")
async def get_recent_generations(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Get recent generation history for monitoring.

    Shows which services were used and any rescue fallbacks.
    """
    service = AdminDashboardService(db)
    # Get recent generations from the materials table
    materials = await service.get_moderation_queue(limit)

    return {
        "generations": [
            {
                "id": str(m.id),
                "tool_type": m.tool_type.value if m.tool_type else None,
                "topic": m.topic,
                "status": m.status.value if m.status else None,
                "result_image_url": m.result_image_url,
                "result_video_url": m.result_video_url,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "generation_steps": m.generation_steps if hasattr(m, 'generation_steps') else None
            }
            for m in materials
        ],
        "count": len(materials)
    }


# ============================================================================
# WebSocket for Real-time Updates
# ============================================================================

@router.websocket("/ws/realtime")
async def admin_realtime_websocket(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db)
):
    """
    WebSocket endpoint for real-time admin dashboard updates.
    Sends stats every 5 seconds.
    """
    await websocket.accept()

    try:
        # Note: In production, verify admin token from query params
        service = AdminDashboardService(db)

        while True:
            # Get real-time stats
            stats = await session_tracker.get_stats()

            # Send to client
            await websocket.send_json({
                "type": "stats_update",
                "data": stats
            })

            # Wait 5 seconds before next update
            await asyncio.sleep(5)

    except WebSocketDisconnect:
        logger.info("Admin WebSocket disconnected")
    except Exception as e:
        logger.error(f"Admin WebSocket error: {e}")
