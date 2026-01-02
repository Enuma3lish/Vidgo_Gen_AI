"""
Session Tracker Service for VidGo Admin Dashboard
Based on ARCHITECTURE_FINAL.md specification

Tracks:
- Online users in real-time (via heartbeat)
- Users by subscription tier
- Active users today (HyperLogLog)
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)

# Redis key patterns
ONLINE_USERS_KEY = "online_users"  # Sorted Set: {user_id: timestamp}
USER_PLANS_KEY = "user_plans"  # Hash: {user_id: plan}
ONLINE_BY_TIER_KEY = "online_users_by_tier"  # Hash: {plan: count}
ACTIVE_USERS_TODAY_KEY = "active_users_today"  # HyperLogLog

# Session timeout in seconds (5 minutes)
SESSION_TIMEOUT = 300


class SessionTracker:
    """
    Real-time session tracking using Redis.

    Redis Structures:
    - online_users (Sorted Set): Maps user_id to last heartbeat timestamp
    - user_plans (Hash): Maps user_id to their current plan
    - online_users_by_tier (Hash): Count of online users per plan tier
    - active_users_today (HyperLogLog): Unique active users today
    """

    def __init__(self):
        self.redis: Optional[redis.Redis] = None

    async def init_redis(self):
        """Initialize Redis connection"""
        if not self.redis:
            self.redis = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )

    async def heartbeat(
        self,
        user_id: str,
        plan: str = "demo",
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Record user heartbeat.
        Called by frontend every 30-60 seconds.

        Args:
            user_id: User's UUID as string
            plan: User's current plan (demo, starter, pro, pro_plus)
            ip_address: Optional IP address for rate limiting

        Returns:
            Dict with online stats
        """
        await self.init_redis()

        try:
            now = datetime.utcnow()
            timestamp = now.timestamp()

            # Get previous plan for this user (if any)
            prev_plan = await self.redis.hget(USER_PLANS_KEY, user_id)

            # Check if user was already online
            was_online = await self.redis.zscore(ONLINE_USERS_KEY, user_id) is not None

            # Update user's last heartbeat in sorted set
            await self.redis.zadd(ONLINE_USERS_KEY, {user_id: timestamp})

            # Update user's plan in hash
            await self.redis.hset(USER_PLANS_KEY, user_id, plan)

            # Update tier counts if plan changed or user just came online
            if not was_online or prev_plan != plan:
                # Decrement old tier count
                if was_online and prev_plan:
                    await self.redis.hincrby(ONLINE_BY_TIER_KEY, prev_plan, -1)
                # Increment new tier count
                await self.redis.hincrby(ONLINE_BY_TIER_KEY, plan, 1)

            # Add to today's active users (HyperLogLog)
            today_key = f"{ACTIVE_USERS_TODAY_KEY}:{now.strftime('%Y-%m-%d')}"
            await self.redis.pfadd(today_key, user_id)
            # Set expiry for HyperLogLog (2 days to allow cross-day queries)
            await self.redis.expire(today_key, 172800)

            # Get current online count
            online_count = await self.redis.zcard(ONLINE_USERS_KEY)

            return {
                "success": True,
                "online_users": online_count,
                "timestamp": timestamp
            }

        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
            return {"success": False, "error": str(e)}

    async def cleanup_expired(self) -> int:
        """
        Remove expired sessions (users who haven't sent heartbeat).
        Should be called periodically (every minute).

        Returns:
            Number of sessions removed
        """
        await self.init_redis()

        try:
            cutoff = datetime.utcnow().timestamp() - SESSION_TIMEOUT

            # Get expired user IDs
            expired_users = await self.redis.zrangebyscore(
                ONLINE_USERS_KEY,
                "-inf",
                cutoff
            )

            if not expired_users:
                return 0

            # Decrement tier counts for expired users
            for user_id in expired_users:
                plan = await self.redis.hget(USER_PLANS_KEY, user_id)
                if plan:
                    await self.redis.hincrby(ONLINE_BY_TIER_KEY, plan, -1)
                    await self.redis.hdel(USER_PLANS_KEY, user_id)

            # Remove expired users from sorted set
            removed = await self.redis.zremrangebyscore(
                ONLINE_USERS_KEY,
                "-inf",
                cutoff
            )

            logger.info(f"Cleaned up {removed} expired sessions")
            return removed

        except Exception as e:
            logger.error(f"Cleanup error: {e}")
            return 0

    async def get_online_count(self) -> int:
        """Get total number of online users"""
        await self.init_redis()
        try:
            return await self.redis.zcard(ONLINE_USERS_KEY)
        except Exception as e:
            logger.error(f"Get online count error: {e}")
            return 0

    async def get_online_by_tier(self) -> Dict[str, int]:
        """Get online user counts grouped by subscription tier"""
        await self.init_redis()
        try:
            counts = await self.redis.hgetall(ONLINE_BY_TIER_KEY)
            # Convert string values to integers
            return {k: int(v) for k, v in counts.items() if int(v) > 0}
        except Exception as e:
            logger.error(f"Get online by tier error: {e}")
            return {}

    async def get_active_today(self) -> int:
        """Get count of unique active users today (using HyperLogLog)"""
        await self.init_redis()
        try:
            today_key = f"{ACTIVE_USERS_TODAY_KEY}:{datetime.utcnow().strftime('%Y-%m-%d')}"
            return await self.redis.pfcount(today_key)
        except Exception as e:
            logger.error(f"Get active today error: {e}")
            return 0

    async def get_online_users(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get list of currently online users with their plans.

        Args:
            limit: Maximum number of users to return

        Returns:
            List of {user_id, plan, last_seen} dicts
        """
        await self.init_redis()
        try:
            # Get users sorted by most recent heartbeat
            users_with_scores = await self.redis.zrevrange(
                ONLINE_USERS_KEY,
                0,
                limit - 1,
                withscores=True
            )

            result = []
            for user_id, timestamp in users_with_scores:
                plan = await self.redis.hget(USER_PLANS_KEY, user_id)
                result.append({
                    "user_id": user_id,
                    "plan": plan or "demo",
                    "last_seen": datetime.fromtimestamp(timestamp).isoformat()
                })

            return result

        except Exception as e:
            logger.error(f"Get online users error: {e}")
            return []

    async def is_user_online(self, user_id: str) -> bool:
        """Check if a specific user is currently online"""
        await self.init_redis()
        try:
            score = await self.redis.zscore(ONLINE_USERS_KEY, user_id)
            if score is None:
                return False
            # Check if not expired
            cutoff = datetime.utcnow().timestamp() - SESSION_TIMEOUT
            return score > cutoff
        except Exception as e:
            logger.error(f"Is user online error: {e}")
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive session statistics"""
        await self.init_redis()
        try:
            online_count = await self.get_online_count()
            by_tier = await self.get_online_by_tier()
            active_today = await self.get_active_today()

            return {
                "online_users": online_count,
                "by_tier": by_tier,
                "active_today": active_today,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Get stats error: {e}")
            return {
                "online_users": 0,
                "by_tier": {},
                "active_today": 0,
                "error": str(e)
            }


# Singleton instance
session_tracker = SessionTracker()
