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
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import os
import re

from app.api.deps import get_current_user, get_db, get_redis
from app.core.config import settings
from app.core.test_plans import TEST_PRO_PLAN_CREDITS, TEST_PRO_PLAN_DEFAULTS, is_test_pro_plan
from app.models.billing import Plan
from app.models.user import User, generate_referral_code
from app.providers.provider_router import get_provider_router, TaskType
from app.services.admin_dashboard import AdminDashboardService
from app.services.session_tracker import session_tracker
from app.services.subscription_service import get_subscription_service
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


class PromotionCodeRequest(BaseModel):
    promotion_code: Optional[str] = None


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
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def _plan_name(user: User) -> str:
    plan = getattr(user, "current_plan", None)
    if plan:
        if is_test_pro_plan(plan):
            return plan.name or "test_pro_usd_1"
        return plan.plan_type or plan.name or "demo"
    return "demo"


def _is_test_account(user: User) -> bool:
    return is_test_pro_plan(getattr(user, "current_plan", None))


def _display_name(user: User) -> Optional[str]:
    return user.full_name or user.username


def _normalize_promotion_code(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    normalized = code.strip().upper()
    if not normalized:
        return None
    if not re.fullmatch(r"[A-Z0-9]{3,16}", normalized):
        raise HTTPException(
            status_code=400,
            detail="Promotion code must be 3-16 letters or numbers"
        )
    return normalized


_PROVIDER_ACCOUNT_ENV = {
    "piapi_mcp": ("PIAPI_REMAINING_CREDITS", "PIAPI_SUBSCRIPTION_STATUS"),
    "piapi": ("PIAPI_REMAINING_CREDITS", "PIAPI_SUBSCRIPTION_STATUS"),
    "pollo_mcp": ("POLLO_REMAINING_CREDITS", "POLLO_SUBSCRIPTION_STATUS"),
    "pollo": ("POLLO_REMAINING_CREDITS", "POLLO_SUBSCRIPTION_STATUS"),
    "a2e": ("A2E_REMAINING_CREDITS", "A2E_SUBSCRIPTION_STATUS"),
    "vertex_ai": ("VERTEX_AI_REMAINING_CREDITS", "VERTEX_AI_SUBSCRIPTION_STATUS"),
}


def _provider_configured(provider_name: str) -> bool:
    if provider_name in {"piapi", "piapi_mcp"}:
        return bool(getattr(settings, "PIAPI_KEY", ""))
    if provider_name in {"pollo", "pollo_mcp"}:
        return bool(getattr(settings, "POLLO_API_KEY", ""))
    if provider_name == "a2e":
        return bool(getattr(settings, "A2E_API_KEY", ""))
    if provider_name == "vertex_ai":
        return bool(getattr(settings, "VERTEX_AI_PROJECT", "") or getattr(settings, "GEMINI_API_KEY", ""))
    return False


def _parse_provider_credits(raw_value: Optional[str]) -> Optional[float]:
    if raw_value is None or raw_value.strip() == "":
        return None
    try:
        return float(raw_value.replace(",", ""))
    except ValueError:
        return None


def _attach_provider_account_status(provider_name: str, status_data: Dict[str, Any]) -> Dict[str, Any]:
    credits_env, subscription_env = _PROVIDER_ACCOUNT_ENV.get(provider_name, ("", ""))
    raw_credits = os.getenv(credits_env, "") if credits_env else ""
    subscription_status = os.getenv(subscription_env, "").strip() if subscription_env else ""
    configured = _provider_configured(provider_name)

    return {
        **status_data,
        "configured": configured,
        "remaining_credits": _parse_provider_credits(raw_credits),
        "remaining_credits_label": raw_credits.strip() or None,
        "subscription_status": subscription_status or ("unknown" if configured else "not_configured"),
        "account_status_source": "environment" if raw_credits or subscription_status else "not_available",
    }


async def _alert_admins_for_provider_errors(status: Dict[str, Any]) -> None:
    router_instance = get_provider_router()
    for provider_name, provider_status in status.items():
        if str(provider_status.get("status", "")).lower() != "error":
            continue

        error = (
            provider_status.get("error")
            or provider_status.get("message")
            or f"{provider_name} health check returned error"
        )
        await router_instance._maybe_alert_provider_failure(
            provider_name=provider_name,
            task_type="health_check",
            error=str(error),
            fallback_provider=None,
            request_params={"source": "admin_ai_services"},
        )


async def _get_or_create_test_plan(db: AsyncSession) -> Plan:
    result = await db.execute(
        select(Plan).where(
            or_(
                Plan.name == TEST_PRO_PLAN_DEFAULTS["name"],
                Plan.slug == TEST_PRO_PLAN_DEFAULTS["slug"],
            )
        )
    )
    plan = result.scalars().first()

    if not plan:
        plan = Plan(**TEST_PRO_PLAN_DEFAULTS)
        db.add(plan)
    else:
        for key, value in TEST_PRO_PLAN_DEFAULTS.items():
            if getattr(plan, key, None) != value:
                setattr(plan, key, value)

    await db.flush()
    return plan


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


@router.get("/charts/revenue-daily")
async def get_revenue_daily_chart(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get daily revenue for the past N days"""
    service = AdminDashboardService(db)
    return await service.get_revenue_daily_trend(days)


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
# Tool Usage & Earnings Statistics
# ============================================================================

@router.get("/stats/tool-usage")
async def get_tool_usage_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get tool usage stats: most frequent tool and most credit-consuming tool"""
    service = AdminDashboardService(db)
    return await service.get_tool_usage_stats()


@router.get("/stats/earnings")
async def get_earnings_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get weekly, monthly, and yearly earnings from orders"""
    service = AdminDashboardService(db)
    return await service.get_earnings_stats()


@router.get("/finance/manual-actions")
async def get_finance_manual_actions(
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """List refund/invoice cases that still require manual finance action."""
    subscription_service = get_subscription_service()
    return await subscription_service.get_manual_action_queue(db=db, limit=limit)


@router.get("/stats/api-costs")
async def get_api_cost_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get API cost breakdown by service type (weekly, monthly, and yearly)"""
    service = AdminDashboardService(db)
    return await service.get_api_cost_stats()


@router.get("/costs")
async def get_costs_dashboard(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Admin /admin/costs — PiAPI monthly spend, model cost analysis,
    credit-to-API-cost ratio. Spec Section 四.
    """
    service = AdminDashboardService(db)
    return await service.get_costs_dashboard()


@router.get("/stats/active-users")
async def get_active_users_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get active generations count and online user sessions"""
    service = AdminDashboardService(db)
    return await service.get_active_users_stats()


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
                "name": _display_name(u),
                "plan": _plan_name(u),
                "is_active": u.is_active,
                "is_verified": u.email_verified,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "subscription_credits": u.subscription_credits,
                "purchased_credits": u.purchased_credits,
                "bonus_credits": u.bonus_credits,
                "referral_code": u.referral_code,
                "referral_count": u.referral_count or 0,
                "is_promotion_account": bool(u.referral_code),
                "is_test_account": _is_test_account(u),
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
            "name": _display_name(user),
            "plan": _plan_name(user),
            "is_active": user.is_active,
            "is_verified": user.email_verified,
            "is_admin": user.is_superuser,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "subscription_credits": user.subscription_credits,
            "purchased_credits": user.purchased_credits,
            "bonus_credits": user.bonus_credits,
            "referral_code": user.referral_code,
            "referral_count": user.referral_count or 0,
            "is_promotion_account": bool(user.referral_code),
            "is_test_account": _is_test_account(user),
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


@router.post("/users/{user_id}/test-account")
async def grant_test_account(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Grant the internal $1 Pro test plan and reset test credits to 10,000."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    plan = await _get_or_create_test_plan(db)
    subscription_service = get_subscription_service()
    activation = await subscription_service._activate_subscription_directly(
        db=db,
        user=user,
        plan=plan,
        billing_cycle="monthly",
        is_upgrade=bool(user.current_plan_id and user.current_plan_id != plan.id),
    )

    if not activation.get("success"):
        raise HTTPException(status_code=400, detail=activation.get("error", "Could not grant test account"))

    return {
        "success": True,
        "message": f"Test account enabled with {TEST_PRO_PLAN_CREDITS} points",
        "user_id": str(user.id),
        "plan_id": str(plan.id),
        "plan_name": plan.name,
        "subscription_credits": user.subscription_credits,
        "total_credits": user.total_credits,
        "is_test_account": True,
        "credits_allocated": activation.get("credits_allocated"),
    }


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


@router.post("/users/{user_id}/promotion-code")
async def set_user_promotion_code(
    user_id: str,
    request: PromotionCodeRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Assign or generate a promotion code for a user account."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    code = _normalize_promotion_code(request.promotion_code)
    if not code:
        for _ in range(10):
            candidate = generate_referral_code()
            existing = await db.execute(select(User).where(User.referral_code == candidate))
            if not existing.scalars().first():
                code = candidate
                break
        if not code:
            raise HTTPException(status_code=500, detail="Could not generate unique promotion code")
    else:
        existing = await db.execute(select(User).where(User.referral_code == code))
        code_owner = existing.scalars().first()
        if code_owner and str(code_owner.id) != str(user.id):
            raise HTTPException(status_code=409, detail="Promotion code is already assigned")

    user.referral_code = code
    await db.commit()
    await db.refresh(user)

    return {
        "success": True,
        "message": "Promotion code assigned",
        "user_id": str(user.id),
        "promotion_code": user.referral_code,
        "referral_code": user.referral_code,
        "referral_count": user.referral_count or 0,
        "is_promotion_account": True,
    }


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

    Returns status of the configured AI provider chain.
    """
    from app.services.rescue_service import get_rescue_service

    rescue_service = get_rescue_service()
    status = await rescue_service.check_service_status()
    await _alert_admins_for_provider_errors(status)
    services = {
        provider_name: _attach_provider_account_status(provider_name, provider_status)
        for provider_name, provider_status in status.items()
    }

    return {
        "services": services,
        "rescue_config": {
            "t2i": {"primary": "piapi_mcp/piapi", "rescue": "pollo", "final": "vertex_ai/gemini"},
            "i2v": {"primary": "piapi_mcp/piapi", "rescue": "pollo_mcp/pollo", "final": "vertex_ai/veo"},
            "t2v": {"primary": "piapi_mcp/piapi", "rescue": "pollo_mcp/pollo", "final": "vertex_ai/veo"},
            "v2v": {"primary": "piapi_mcp", "rescue": "pollo/pollo_mcp", "final": "vertex_ai/veo"},
            "interior": {"primary": "piapi_mcp/piapi", "rescue": None, "final": "vertex_ai/gemini"},
            "avatar": {"primary": "piapi", "rescue": "a2e", "final": None}
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
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket endpoint for real-time admin dashboard updates.
    Sends stats every 5 seconds.

    Requires a valid admin JWT via the ?token=... query param. The frontend
    attaches the same access token it uses for REST calls.
    """
    # Validate admin token BEFORE accepting the socket so unauthorized clients
    # are rejected without a handshake (1008 = Policy Violation).
    from jose import jwt, JWTError
    from app.core.config import settings

    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type", "access") != "access":
            await websocket.close(code=1008)
            return
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=1008)
            return
    except JWTError:
        await websocket.close(code=1008)
        return

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user or not user.is_superuser:
        await websocket.close(code=1008)
        return

    await websocket.accept()

    try:
        service = AdminDashboardService(db)

        while True:
            # Get real-time stats
            stats = await session_tracker.get_stats()

            # Get active generations count
            try:
                active_data = await service.get_active_users_stats()
                stats["active_generations_count"] = active_data["active_generations_count"]
                stats["active_generations"] = active_data["active_generations"]
                stats["online_sessions"] = active_data["online_sessions"]
                stats["online_count"] = active_data["online_count"]
            except Exception:
                stats["active_generations_count"] = 0
                stats["active_generations"] = []
                stats["online_sessions"] = []
                stats["online_count"] = stats.get("online_users", 0)

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


# ============================================================================
# Demo Example Generation (Admin only)
#
# 2-step pipeline:
#   Step 1 — Generate input material via T2I (PiAPI → Pollo fallback)
#   Step 2 — Run the tool transformation on that input
#   Store both input_image_url and result in Material DB + Redis cache
# ============================================================================

class GenerateDemoRequest(BaseModel):
    """Generate a complete demo example (input + tool result) via real API."""
    tool_type: str       # background_removal, product_scene, try_on, room_redesign, short_video, ai_avatar, pattern_generate, effect
    topic: str           # sub-category (e.g. "studio", "floral", "anime")
    prompt: str          # prompt to generate the INPUT image (Step 1)
    effect_prompt: Optional[str] = None  # prompt for the tool transformation (Step 2). Auto-generated if omitted.
    image_url: Optional[str] = None      # skip Step 1 — use this existing image as input
    style_id: Optional[str] = None       # style for room_redesign / effect


async def _t2i(provider, prompt: str) -> Optional[str]:
    """Generate an image via T2I. Returns image URL or None."""
    result = await provider.route(
        TaskType.T2I,
        {"prompt": prompt, "size": "1024*1024"}
    )
    if not result.get("success"):
        return None
    output = result.get("output", {})
    return (
        output.get("image_url")
        or (output.get("images", [{}])[0].get("url") if output.get("images") else None)
    )


def _extract_url(result: dict) -> Optional[str]:
    """Pull image/video URL from a provider result."""
    output = result.get("output", {})
    return (
        output.get("image_url")
        or output.get("video_url")
        or (output.get("images", [{}])[0].get("url") if output.get("images") else None)
    )


# Default effect prompts per tool_type (used when effect_prompt is not provided)
_DEFAULT_EFFECT_PROMPTS = {
    "background_removal": None,  # no extra prompt needed
    "product_scene": "professional studio lighting, commercial product photography, clean background",
    "try_on": None,
    "room_redesign": "modern minimalist interior design, clean lines, natural light",
    "short_video": "smooth natural camera motion, cinematic animation",
    "ai_avatar": None,
    "pattern_generate": None,  # single-step, prompt IS the effect
    "effect": "anime style, vibrant colors, detailed illustration",
}


@router.post("/generate-demo")
async def generate_demo_example(
    request: GenerateDemoRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Generate a complete demo example via real API (admin only).

    **Pipeline:**
    1. Generate input image via T2I (PiAPI → Pollo fallback) — or use provided image_url
    2. Run the tool-specific transformation on that input
    3. Store both input + result in Material DB and Redis cache

    **Tool pipelines:**
    - `background_removal`: T2I(prompt) → remove-bg
    - `product_scene`: T2I(prompt) → remove-bg → T2I(scene) → composite
    - `try_on`: T2I(prompt) → try-on API
    - `room_redesign`: T2I(prompt) → I2I(style)
    - `short_video`: T2I(prompt) → I2V
    - `ai_avatar`: T2I(prompt) → avatar API
    - `pattern_generate`: T2I(prompt) — single step
    - `effect`: T2I(prompt) → I2I(style)
    """
    from app.services.demo_cache_service import DemoCacheService

    redis = await get_redis()
    cache_svc = DemoCacheService(db, redis)
    provider = get_provider_router()

    tool = request.tool_type
    effect_prompt = request.effect_prompt or _DEFAULT_EFFECT_PROMPTS.get(tool) or ""

    logger.info(f"[generate-demo] tool={tool} topic={request.topic}")

    # ── Step 1: Get or generate input image ──
    input_url = request.image_url
    if not input_url:
        logger.info(f"[generate-demo] Step 1: T2I → generating input image")
        input_url = await _t2i(provider, request.prompt)
        if not input_url:
            return {"success": False, "error": "Step 1 failed: could not generate input image (PiAPI + backup both failed)"}
        logger.info(f"[generate-demo] Step 1 done: {input_url[:80]}...")

    # ── Step 2: Run tool-specific transformation ──
    result_url = None
    video_url = None

    try:
        if tool == "pattern_generate":
            # Single-step: the T2I result IS the pattern
            result_url = input_url
            input_url = None  # no separate input for pattern

        elif tool == "background_removal":
            r = await provider.route(TaskType.BACKGROUND_REMOVAL, {"image_url": input_url})
            if r.get("success"):
                result_url = _extract_url(r)

        elif tool == "product_scene":
            # Remove bg → generate scene → composite (simplified: just remove bg for now)
            r = await provider.route(TaskType.BACKGROUND_REMOVAL, {"image_url": input_url})
            if r.get("success"):
                result_url = _extract_url(r)

        elif tool == "room_redesign":
            style_prompt = effect_prompt or request.style_id or "modern minimalist"
            r = await provider.route(TaskType.INTERIOR, {
                "image_url": input_url,
                "prompt": style_prompt,
                "style": request.style_id or "modern_minimalist",
            })
            if r.get("success"):
                result_url = _extract_url(r)

        elif tool == "effect":
            r = await provider.route(TaskType.I2I, {
                "image_url": input_url,
                "prompt": effect_prompt,
                "strength": 0.75,
            })
            if r.get("success"):
                result_url = _extract_url(r)

        elif tool == "short_video":
            r = await provider.route(TaskType.I2V, {
                "image_url": input_url,
                "prompt": effect_prompt or "smooth natural camera motion",
                "duration": 5,
            })
            if r.get("success"):
                output = r.get("output", {})
                video_url = output.get("video_url")
                result_url = video_url

        elif tool == "try_on":
            r = await provider.route(TaskType.I2I, {
                "image_url": input_url,
                "prompt": effect_prompt or "virtual try-on, garment on model",
                "strength": 0.8,
            })
            if r.get("success"):
                result_url = _extract_url(r)

        elif tool == "ai_avatar":
            r = await provider.route(TaskType.AVATAR, {
                "image_url": input_url,
                "prompt": effect_prompt or request.prompt,
            })
            if r.get("success"):
                output = r.get("output", {})
                video_url = output.get("video_url")
                result_url = video_url or _extract_url(r)

        else:
            return {"success": False, "error": f"Unknown tool_type: {tool}"}

    except Exception as e:
        logger.error(f"[generate-demo] Step 2 failed: {e}")
        return {"success": False, "error": f"Step 2 failed: {str(e)}"}

    if not result_url:
        return {"success": False, "error": "Step 2 failed: tool transformation returned no output"}

    logger.info(f"[generate-demo] Step 2 done: {result_url[:80]}...")

    # ── Step 3: Store in DB + cache ──
    material = await cache_svc.store_demo(
        tool_type=tool,
        topic=request.topic,
        prompt=request.prompt,
        result_url=result_url,
        input_image_url=input_url,
        result_video_url=video_url,
        extra_params={"effect_prompt": effect_prompt, "style_id": request.style_id},
    )

    return {
        "success": True,
        "material_id": str(material.id),
        "input_url": input_url,
        "result_url": result_url,
        "tool_type": tool,
        "topic": request.topic,
    }


@router.get("/demos")
async def list_demo_examples(
    tool_type: Optional[str] = None,
    topic: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """List all demo examples in DB. Admin only."""
    from app.services.demo_cache_service import DemoCacheService

    redis = await get_redis()
    cache_svc = DemoCacheService(db, redis)

    if tool_type:
        demos = await cache_svc.get_demos(tool_type, topic, limit)
    else:
        from app.models.material import ToolType as TT
        demos = []
        for tt in TT:
            items = await cache_svc.get_demos(tt.value, topic, limit=5)
            demos.extend(items)

    return {"success": True, "count": len(demos), "demos": demos}


@router.delete("/demos/{material_id}")
async def delete_demo_example(
    material_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Delete a demo example. Admin only."""
    from app.models.material import Material
    from uuid import UUID

    try:
        mid = UUID(material_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid material ID")

    m = await db.get(Material, mid)
    if not m:
        raise HTTPException(status_code=404, detail="Material not found")

    await db.delete(m)
    await db.commit()

    # Invalidate cache
    from app.services.demo_cache_service import DemoCacheService
    redis = await get_redis()
    await DemoCacheService(db, redis).invalidate_cache(m.tool_type, m.topic)

    return {"success": True, "deleted": material_id}
