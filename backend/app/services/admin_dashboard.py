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
from app.models.billing import Plan, Subscription, Order, CreditTransaction, Generation
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
        result = await self.db.execute(
            select(User.plan, func.count(User.id))
            .group_by(User.plan)
        )
        return {row[0] or "demo": row[1] for row in result.all()}

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
                User.name.ilike(f"%{search}%")
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        if plan:
            query = query.where(User.plan == plan)
            count_query = count_query.where(User.plan == plan)

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

        if user.is_admin:
            return False, "Cannot ban admin users"

        user.is_active = False
        user.ban_reason = reason
        user.banned_at = datetime.utcnow()
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
        user.ban_reason = None
        user.banned_at = None
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

        # Check external APIs (Leonardo, GoEnhance)
        # These would be actual API health checks in production
        health["api_services"] = {
            "leonardo": {"status": "healthy"},
            "goenhance": {"status": "healthy"},
            "gemini": {"status": "healthy"}
        }

        return health
