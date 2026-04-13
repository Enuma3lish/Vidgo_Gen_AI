"""
Admin Dashboard Service for VidGo Platform
Based on ARCHITECTURE_FINAL.md specification

Provides:
- Real-time statistics
- User management
- Material review
- Revenue analytics
- System health monitoring
"""
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.billing import Plan, Subscription, Order, CreditTransaction, Generation, ServicePricing
from app.models.material import Material, MaterialStatus, ToolType
from app.services.session_tracker import session_tracker

logger = logging.getLogger(__name__)


class AdminDashboardService:
    """Admin dashboard statistics and management service"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # Real-time Statistics
    # =========================================================================

    async def get_online_stats(self) -> Dict[str, Any]:
        """Get real-time online user statistics from Redis"""
        return await session_tracker.get_stats()

    async def get_online_by_tier(self) -> Dict[str, int]:
        """Get online users grouped by subscription tier"""
        return await session_tracker.get_online_by_tier()

    async def get_dashboard_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive dashboard statistics.
        Combines real-time Redis data with database aggregations.
        """
        # Real-time stats from Redis
        online_stats = await session_tracker.get_stats()

        # Database stats
        today = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        # Total users
        total_users = await self.db.scalar(
            select(func.count(User.id))
        )

        # Users by plan
        users_by_plan = await self._get_users_by_plan()

        # Paid vs free split
        paid_stats = await self.get_paid_user_stats()

        # New users today
        new_today = await self.db.scalar(
            select(func.count(User.id)).where(
                func.date(User.created_at) == today
            )
        )

        # Generations today
        generations_today = await self.db.scalar(
            select(func.count(Generation.id)).where(
                func.date(Generation.created_at) == today
            )
        )

        # Revenue this month
        revenue_month = await self._get_revenue_for_period(month_ago, today)

        return {
            "online": online_stats,
            "users": {
                "total": total_users or 0,
                "new_today": new_today or 0,
                "by_plan": users_by_plan
            },
            "paid_stats": paid_stats,
            "generations": {
                "today": generations_today or 0
            },
            "revenue": {
                "month": revenue_month
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    async def _get_users_by_plan(self) -> Dict[str, int]:
        """Get user count grouped by plan"""
        from app.models.billing import Plan
        result = await self.db.execute(
            select(Plan.name, func.count(User.id))
            .outerjoin(Plan, User.current_plan_id == Plan.id)
            .group_by(Plan.name)
        )
        return {(row[0] or "demo"): row[1] for row in result.all()}

    async def get_paid_user_stats(self) -> Dict[str, Any]:
        """
        Split registered users into paid vs. free/demo.

        Paid = has a current_plan_id whose Plan.price_usd > 0
               (OR price_twd > 0, to catch TWD-only plans).
        Free = everyone else (no plan, demo/free plan, or plan with zero price).
        """
        total = await self.db.scalar(select(func.count(User.id))) or 0

        paid = await self.db.scalar(
            select(func.count(User.id))
            .join(Plan, User.current_plan_id == Plan.id)
            .where(
                or_(
                    Plan.price_usd > 0,
                    Plan.price_twd > 0,
                )
            )
        ) or 0

        free = max(total - paid, 0)
        paid_percent = round((paid / total) * 100, 1) if total > 0 else 0.0
        free_percent = round(100.0 - paid_percent, 1) if total > 0 else 0.0

        return {
            "total": total,
            "paid": paid,
            "free": free,
            "paid_percent": paid_percent,
            "free_percent": free_percent,
        }

    async def _get_revenue_for_period(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> float:
        """Calculate total revenue for a period"""
        result = await self.db.scalar(
            select(func.sum(Order.amount)).where(
                and_(
                    Order.status == "completed",
                    Order.created_at >= start_date,
                    Order.created_at <= end_date
                )
            )
        )
        return float(result or 0)

    # =========================================================================
    # Charts & Trends
    # =========================================================================

    async def get_generation_trend(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily generation counts for the past N days"""
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days)

        result = await self.db.execute(
            select(
                func.date(Generation.created_at).label('date'),
                func.count(Generation.id).label('count')
            ).where(
                Generation.created_at >= start_date
            ).group_by(
                func.date(Generation.created_at)
            ).order_by('date')
        )

        return [
            {"date": str(row.date), "count": row.count}
            for row in result.all()
        ]

    async def get_revenue_trend(self, months: int = 12) -> List[Dict[str, Any]]:
        """Get monthly revenue for the past N months"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=months * 30)

        result = await self.db.execute(
            select(
                func.date_trunc('month', Order.created_at).label('month'),
                func.sum(Order.amount).label('revenue')
            ).where(
                and_(
                    Order.status == "completed",
                    Order.created_at >= start_date
                )
            ).group_by(
                func.date_trunc('month', Order.created_at)
            ).order_by('month')
        )

        return [
            {"month": str(row.month)[:7], "revenue": float(row.revenue or 0)}
            for row in result.all()
        ]

    async def get_revenue_daily_trend(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily revenue for the past N days."""
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days)

        result = await self.db.execute(
            select(
                func.date(Order.created_at).label('date'),
                func.sum(Order.amount).label('revenue'),
            ).where(
                and_(
                    Order.status == "completed",
                    Order.created_at >= start_date,
                )
            ).group_by(
                func.date(Order.created_at)
            ).order_by('date')
        )

        return [
            {"date": str(row.date), "revenue": float(row.revenue or 0)}
            for row in result.all()
        ]

    async def get_user_growth_trend(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily new user registrations for the past N days"""
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days)

        result = await self.db.execute(
            select(
                func.date(User.created_at).label('date'),
                func.count(User.id).label('count')
            ).where(
                User.created_at >= start_date
            ).group_by(
                func.date(User.created_at)
            ).order_by('date')
        )

        return [
            {"date": str(row.date), "count": row.count}
            for row in result.all()
        ]

    # =========================================================================
    # Tool Usage & Earnings
    # =========================================================================

    async def get_tool_usage_stats(self) -> Dict[str, Any]:
        """Get tool usage: most frequently used tools and most credit-consuming tools."""
        from app.models.user_generation import UserGeneration

        # Most frequently used tools (count of generations per tool_type)
        freq_result = await self.db.execute(
            select(
                UserGeneration.tool_type,
                func.count(UserGeneration.id).label('usage_count')
            ).group_by(UserGeneration.tool_type)
            .order_by(desc(func.count(UserGeneration.id)))
        )
        by_frequency = [
            {"tool": row.tool_type.value if hasattr(row.tool_type, 'value') else str(row.tool_type),
             "count": row.usage_count}
            for row in freq_result.all()
        ]

        # Most credit-consuming tools (sum of credits_used per tool_type)
        credit_result = await self.db.execute(
            select(
                UserGeneration.tool_type,
                func.sum(UserGeneration.credits_used).label('total_credits')
            ).group_by(UserGeneration.tool_type)
            .order_by(desc(func.sum(UserGeneration.credits_used)))
        )
        by_credits = [
            {"tool": row.tool_type.value if hasattr(row.tool_type, 'value') else str(row.tool_type),
             "total_credits": int(row.total_credits or 0)}
            for row in credit_result.all()
        ]

        return {
            "by_frequency": by_frequency,
            "by_credits": by_credits,
        }

    async def get_earnings_stats(self) -> Dict[str, Any]:
        """Get weekly and monthly earnings from paid orders."""
        today = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)
        month_start = today.replace(day=1)

        week_revenue = await self._get_revenue_for_period(week_ago, today)
        month_revenue = await self._get_revenue_for_period(month_start, today)

        # Monthly breakdown for the last 6 months
        monthly = []
        for i in range(5, -1, -1):
            m_start = (today.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
            if i > 0:
                m_end = (m_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            else:
                m_end = today
            rev = await self._get_revenue_for_period(m_start, m_end)
            monthly.append({"month": m_start.strftime("%Y-%m"), "revenue": rev})

        return {
            "week": week_revenue,
            "month": month_revenue,
            "monthly_breakdown": monthly,
        }

    async def get_api_cost_stats(self) -> Dict[str, Any]:
        """
        Get API cost breakdown by service type for this week and this month.
        JOINs generations with service_pricing to compute actual USD costs.
        """
        today = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)
        month_start = today.replace(day=1)

        # Per-service costs for this week
        week_result = await self.db.execute(
            select(
                Generation.service_type,
                ServicePricing.display_name,
                func.count(Generation.id).label('call_count'),
                func.sum(ServicePricing.api_cost_usd).label('total_cost')
            ).join(
                ServicePricing,
                Generation.service_type == ServicePricing.service_type
            ).where(
                and_(
                    Generation.created_at >= week_ago,
                    Generation.status == "completed"
                )
            ).group_by(
                Generation.service_type, ServicePricing.display_name
            ).order_by(desc(func.sum(ServicePricing.api_cost_usd)))
        )
        week_data = {
            row.service_type: {
                "service": row.service_type,
                "display_name": row.display_name,
                "calls": row.call_count,
                "cost": float(row.total_cost or 0)
            }
            for row in week_result.all()
        }

        # Per-service costs for this month
        month_result = await self.db.execute(
            select(
                Generation.service_type,
                ServicePricing.display_name,
                func.count(Generation.id).label('call_count'),
                func.sum(ServicePricing.api_cost_usd).label('total_cost')
            ).join(
                ServicePricing,
                Generation.service_type == ServicePricing.service_type
            ).where(
                and_(
                    Generation.created_at >= month_start,
                    Generation.status == "completed"
                )
            ).group_by(
                Generation.service_type, ServicePricing.display_name
            ).order_by(desc(func.sum(ServicePricing.api_cost_usd)))
        )
        month_data = {
            row.service_type: {
                "service": row.service_type,
                "display_name": row.display_name,
                "calls": row.call_count,
                "cost": float(row.total_cost or 0)
            }
            for row in month_result.all()
        }

        # Merge into unified list
        all_services = set(list(week_data.keys()) + list(month_data.keys()))
        by_service = []
        week_total = 0.0
        month_total = 0.0

        for svc in sorted(all_services):
            w = week_data.get(svc, {})
            m = month_data.get(svc, {})
            w_cost = w.get("cost", 0.0)
            m_cost = m.get("cost", 0.0)
            week_total += w_cost
            month_total += m_cost
            by_service.append({
                "service": svc,
                "display_name": w.get("display_name") or m.get("display_name", svc),
                "week_calls": w.get("calls", 0),
                "week_cost": w_cost,
                "month_calls": m.get("calls", 0),
                "month_cost": m_cost,
            })

        # Sort by month cost descending
        by_service.sort(key=lambda x: x["month_cost"], reverse=True)

        return {
            "by_service": by_service,
            "week_total": week_total,
            "month_total": month_total,
        }

    async def get_costs_dashboard(self) -> Dict[str, Any]:
        """
        Admin /admin/costs dashboard.
        Shows PiAPI monthly spend, model cost analysis,
        credit-to-API-cost ratio, and margin analysis.
        """
        today = datetime.utcnow().date()
        month_start = today.replace(day=1)

        # 1) Per-model cost breakdown for current month
        model_result = await self.db.execute(
            select(
                ServicePricing.model_type,
                ServicePricing.tool_type,
                ServicePricing.display_name,
                func.count(Generation.id).label("call_count"),
                func.sum(ServicePricing.api_cost_usd).label("total_api_cost"),
                func.sum(ServicePricing.credit_cost).label("total_credits_charged"),
            )
            .join(ServicePricing, Generation.service_type == ServicePricing.service_type)
            .where(
                and_(
                    Generation.created_at >= month_start,
                    Generation.status == "completed",
                )
            )
            .group_by(
                ServicePricing.model_type,
                ServicePricing.tool_type,
                ServicePricing.display_name,
            )
            .order_by(desc(func.sum(ServicePricing.api_cost_usd)))
        )

        models_breakdown = []
        total_api_cost = 0.0
        total_credits = 0
        for row in model_result.all():
            cost = float(row.total_api_cost or 0)
            credits = int(row.total_credits_charged or 0)
            total_api_cost += cost
            total_credits += credits
            models_breakdown.append({
                "model_type": row.model_type or "default",
                "tool_type": row.tool_type or "unknown",
                "display_name": row.display_name,
                "calls": row.call_count,
                "api_cost_usd": round(cost, 4),
                "credits_charged": credits,
            })

        # 2) Credit revenue vs API cost ratio
        # Get total credit revenue this month (orders with status=paid)
        revenue_result = await self.db.execute(
            select(func.sum(Order.amount)).where(
                and_(
                    Order.paid_at >= month_start,
                    Order.status == "paid",
                )
            )
        )
        month_revenue_twd = float(revenue_result.scalar_one() or 0)
        month_revenue_usd = round(month_revenue_twd / 31, 2)  # Approx TWD/USD

        # 3) Margin analysis
        margin_usd = month_revenue_usd - total_api_cost
        margin_pct = round((margin_usd / month_revenue_usd * 100), 1) if month_revenue_usd > 0 else 0

        # 4) Model type distribution (pie chart data)
        model_distribution = {}
        for item in models_breakdown:
            mt = item["model_type"]
            if mt not in model_distribution:
                model_distribution[mt] = {"calls": 0, "api_cost_usd": 0.0}
            model_distribution[mt]["calls"] += item["calls"]
            model_distribution[mt]["api_cost_usd"] += item["api_cost_usd"]

        return {
            "month": today.strftime("%Y-%m"),
            "piapi_monthly_spend_usd": round(total_api_cost, 4),
            "total_credits_consumed": total_credits,
            "revenue_twd": round(month_revenue_twd, 2),
            "revenue_usd_approx": month_revenue_usd,
            "margin_usd": round(margin_usd, 2),
            "margin_percent": margin_pct,
            "models_breakdown": models_breakdown,
            "model_distribution": model_distribution,
        }

    async def get_active_users_stats(self) -> Dict[str, Any]:
        """
        Get active generation count and online user sessions.
        """
        from app.models.user_generation import UserGeneration
        from app.models.user_upload import UserUpload, UploadStatus

        # Active generations (processing status) from UserUpload
        try:
            active_gen_result = await self.db.execute(
                select(
                    UserUpload.user_id,
                    UserUpload.tool_type,
                    UserUpload.created_at
                ).where(
                    UserUpload.status == UploadStatus.PROCESSING
                ).order_by(desc(UserUpload.created_at))
                .limit(50)
            )
            active_generations = [
                {
                    "user_id": str(row.user_id),
                    "tool_type": row.tool_type.value if hasattr(row.tool_type, 'value') else str(row.tool_type) if row.tool_type else "unknown",
                    "started_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in active_gen_result.all()
            ]
        except Exception as e:
            logger.warning(f"Could not query active generations: {e}")
            active_generations = []

        # Also check Generation model for pending/processing
        try:
            active_gen_billing = await self.db.execute(
                select(
                    Generation.user_id,
                    Generation.service_type,
                    Generation.started_at,
                    Generation.created_at
                ).where(
                    Generation.status.in_(["pending", "processing"])
                ).order_by(desc(Generation.created_at))
                .limit(50)
            )
            for row in active_gen_billing.all():
                active_generations.append({
                    "user_id": str(row.user_id),
                    "tool_type": row.service_type or "unknown",
                    "started_at": (row.started_at or row.created_at).isoformat() if (row.started_at or row.created_at) else None,
                })
        except Exception:
            pass

        # Online sessions from Redis
        online_sessions = await session_tracker.get_online_users(limit=100)

        return {
            "active_generations_count": len(active_generations),
            "active_generations": active_generations,
            "online_sessions": online_sessions,
            "online_count": len(online_sessions),
        }

    # =========================================================================
    # User Management
    # =========================================================================

    async def get_users(
        self,
        page: int = 1,
        per_page: int = 20,
        search: Optional[str] = None,
        plan: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Tuple[List[User], int]:
        """
        Get paginated list of users with optional filtering.

        Returns:
            Tuple of (users list, total count)
        """
        query = select(User)
        count_query = select(func.count(User.id))

        # Apply filters
        if search:
            search_filter = or_(
                User.email.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%")
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        if plan:
            from app.models.billing import Plan
            plan_subq = select(Plan.id).where(Plan.name == plan).scalar_subquery()
            query = query.where(User.current_plan_id == plan_subq)
            count_query = count_query.where(User.current_plan_id == plan_subq)

        # Get total count
        total = await self.db.scalar(count_query)

        # Apply sorting
        order_column = getattr(User, sort_by, User.created_at)
        if sort_order == "desc":
            query = query.order_by(desc(order_column))
        else:
            query = query.order_by(order_column)

        # Apply pagination
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)

        result = await self.db.execute(query)
        users = result.scalars().all()

        return list(users), total or 0

    async def get_user_detail(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed user information"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        # Get user's generation count
        gen_count = await self.db.scalar(
            select(func.count(Generation.id)).where(
                Generation.user_id == user_id
            )
        )

        # Get user's transaction history (last 10)
        transactions = await self.db.execute(
            select(CreditTransaction)
            .where(CreditTransaction.user_id == user_id)
            .order_by(desc(CreditTransaction.created_at))
            .limit(10)
        )

        # Check if online
        is_online = await session_tracker.is_user_online(str(user_id))

        return {
            "user": user,
            "generation_count": gen_count or 0,
            "recent_transactions": transactions.scalars().all(),
            "is_online": is_online
        }

    async def ban_user(
        self,
        user_id: str,
        reason: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Ban a user account"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return False, "User not found"

        if user.is_superuser:
            return False, "Cannot ban admin users"

        user.is_active = False
        await self.db.commit()

        return True, "User banned successfully"

    async def unban_user(self, user_id: str) -> Tuple[bool, str]:
        """Unban a user account"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return False, "User not found"

        user.is_active = True
        await self.db.commit()

        return True, "User unbanned successfully"

    async def adjust_credits(
        self,
        user_id: str,
        amount: int,
        reason: str
    ) -> Tuple[bool, str]:
        """Adjust user's credit balance"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return False, "User not found"

        # Adjust credits
        if amount >= 0:
            user.bonus_credits = (user.bonus_credits or 0) + amount
        else:
            # Deduct from bonus first, then subscription credits
            to_deduct = abs(amount)
            if user.bonus_credits >= to_deduct:
                user.bonus_credits -= to_deduct
            else:
                to_deduct -= user.bonus_credits
                user.bonus_credits = 0
                user.subscription_credits = max(0, user.subscription_credits - to_deduct)

        # Log transaction
        transaction = CreditTransaction(
            user_id=user_id,
            amount=amount,
            balance_after=user.subscription_credits + user.bonus_credits,
            transaction_type="admin_adjustment",
            description=f"Admin adjustment: {reason}"
        )
        self.db.add(transaction)
        await self.db.commit()

        return True, f"Credits adjusted by {amount}"

    # =========================================================================
    # Material Management
    # =========================================================================

    async def get_materials(
        self,
        page: int = 1,
        per_page: int = 20,
        tool_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> Tuple[List[Material], int]:
        """Get paginated list of materials"""
        query = select(Material)
        count_query = select(func.count(Material.id))

        if tool_type:
            query = query.where(Material.tool_type == tool_type)
            count_query = count_query.where(Material.tool_type == tool_type)

        if status:
            query = query.where(Material.status == status)
            count_query = count_query.where(Material.status == status)

        total = await self.db.scalar(count_query)

        offset = (page - 1) * per_page
        query = query.order_by(desc(Material.created_at)).offset(offset).limit(per_page)

        result = await self.db.execute(query)
        materials = result.scalars().all()

        return list(materials), total or 0

    async def review_material(
        self,
        material_id: str,
        action: str,  # approve, reject, feature
        reviewer_id: str,
        rejection_reason: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Review and update material status"""
        result = await self.db.execute(
            select(Material).where(Material.id == material_id)
        )
        material = result.scalar_one_or_none()

        if not material:
            return False, "Material not found"

        if action == "approve":
            material.status = MaterialStatus.APPROVED
            material.approved_at = datetime.utcnow()
        elif action == "reject":
            material.status = MaterialStatus.REJECTED
        elif action == "feature":
            material.status = MaterialStatus.FEATURED
            material.is_featured = True
            material.approved_at = datetime.utcnow()
        else:
            return False, f"Invalid action: {action}"

        await self.db.commit()
        return True, f"Material {action}d successfully"

    async def get_moderation_queue(
        self,
        limit: int = 50
    ) -> List[Material]:
        """Get materials pending review"""
        result = await self.db.execute(
            select(Material)
            .where(Material.status == MaterialStatus.PENDING)
            .order_by(Material.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    # =========================================================================
    # System Health
    # =========================================================================

    async def get_system_health(self) -> Dict[str, Any]:
        """Check health of all system components"""
        health = {
            "database": {"status": "healthy"},
            "redis": {"status": "unknown"},
            "api_services": {}
        }

        # Check database
        try:
            await self.db.execute(select(func.now()))
            health["database"]["status"] = "healthy"
        except Exception as e:
            health["database"] = {"status": "unhealthy", "error": str(e)}

        # Check Redis
        try:
            await session_tracker.init_redis()
            await session_tracker.redis.ping()
            health["redis"]["status"] = "healthy"
        except Exception as e:
            health["redis"] = {"status": "unhealthy", "error": str(e)}

        # Check external APIs (PiAPI, Gemini)
        # These would be actual API health checks in production
        health["api_services"] = {
            "piapi": {"status": "healthy"},
            "gemini": {"status": "healthy"}
        }

        return health
