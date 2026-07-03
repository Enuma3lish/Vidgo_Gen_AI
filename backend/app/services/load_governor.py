"""
Load governor — priority admission for generation requests under heavy load.

This is what makes a plan's `priority_queue` flag REAL (2026-07). Product
rule: every paid plan can use every model (credits are the only gate); plans
differ under load, where priority_queue subscribers go first.

Generations run synchronously inside their HTTP request (there is no job
queue), so "priority" is implemented as admission control at the entrance of
ProviderRouter.route():

  - A global in-flight counter is kept in Redis (sorted set scored by start
    timestamp, self-healing: stale members are purged, so a killed instance
    can never wedge the counter).
  - While the in-flight count is below GEN_LOAD_SOFT_LIMIT the site is not
    "heavy" and EVERYONE is admitted immediately — priority is invisible.
  - When the site is heavy:
      high   (priority_queue plans: premium / enterprise) — admitted
             immediately, no wait
      normal (other paid plans: basic / pro)  — wait for a free slot up to
             GEN_LOAD_NORMAL_MAX_WAIT_SECONDS, then admitted anyway
      low    (free tier / background jobs)    — wait up to
             GEN_LOAD_LOW_MAX_WAIT_SECONDS, then admitted anyway
    Nobody is ever rejected — lower tiers are only delayed, so under load
    the scarce provider capacity drains to subscribers first.
  - Redis being down must never break generation: every Redis error fails
    open (falls back to a per-instance counter, and on repeated failure to
    no gating at all for 60s).
"""
import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_INFLIGHT_KEY = "vidgo:generation:inflight"
_POLL_INTERVAL_S = 2.0
_REDIS_RETRY_COOLDOWN_S = 60.0

_redis: Optional[aioredis.Redis] = None
_redis_down_until: float = 0.0

# Per-instance fallback view of in-flight work, used when Redis is
# unavailable. Also maintained when Redis is up so the fallback is warm.
_local_inflight = 0


def _wait_budget_seconds(priority: str) -> float:
    if priority == "high":
        return 0.0
    if priority == "normal":
        return float(settings.GEN_LOAD_NORMAL_MAX_WAIT_SECONDS)
    return float(settings.GEN_LOAD_LOW_MAX_WAIT_SECONDS)


async def _get_redis() -> Optional[aioredis.Redis]:
    global _redis, _redis_down_until
    if time.monotonic() < _redis_down_until:
        return None
    if _redis is None:
        try:
            _redis = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
        except Exception as exc:  # bad URL etc. — fail open
            logger.warning("load_governor: redis unavailable (%s) — gating locally", exc)
            _redis_down_until = time.monotonic() + _REDIS_RETRY_COOLDOWN_S
            return None
    return _redis


def _mark_redis_down(exc: Exception) -> None:
    global _redis_down_until
    _redis_down_until = time.monotonic() + _REDIS_RETRY_COOLDOWN_S
    logger.warning(
        "load_governor: redis error (%s) — failing open for %.0fs",
        str(exc)[:200], _REDIS_RETRY_COOLDOWN_S,
    )


async def _inflight_count() -> int:
    """Global in-flight generations; purges stale members first."""
    r = await _get_redis()
    if r is not None:
        try:
            stale_before = time.time() - settings.GEN_INFLIGHT_STALE_SECONDS
            pipe = r.pipeline()
            pipe.zremrangebyscore(_INFLIGHT_KEY, 0, stale_before)
            pipe.zcard(_INFLIGHT_KEY)
            _, count = await pipe.execute()
            return int(count)
        except Exception as exc:
            _mark_redis_down(exc)
    return _local_inflight


async def _register(member: str) -> None:
    global _local_inflight
    _local_inflight += 1
    r = await _get_redis()
    if r is not None:
        try:
            pipe = r.pipeline()
            pipe.zadd(_INFLIGHT_KEY, {member: time.time()})
            # Safety TTL: if every instance dies mid-flight the key still
            # evaporates instead of permanently inflating the count.
            pipe.expire(_INFLIGHT_KEY, settings.GEN_INFLIGHT_STALE_SECONDS * 2)
            await pipe.execute()
        except Exception as exc:
            _mark_redis_down(exc)


async def _release(member: str) -> None:
    global _local_inflight
    _local_inflight = max(0, _local_inflight - 1)
    r = await _get_redis()
    if r is not None:
        try:
            await r.zrem(_INFLIGHT_KEY, member)
        except Exception as exc:
            _mark_redis_down(exc)


async def _wait_for_admission(priority: str, label: str) -> None:
    budget = _wait_budget_seconds(priority)
    soft_limit = settings.GEN_LOAD_SOFT_LIMIT

    count = await _inflight_count()
    if count < soft_limit or budget <= 0:
        if count >= soft_limit and priority == "high":
            logger.info(
                "load_governor: heavy load (%d in-flight ≥ %d) — priority "
                "caller admitted immediately task=%s",
                count, soft_limit, label,
            )
        return

    loop = asyncio.get_running_loop()
    deadline = loop.time() + budget
    logger.info(
        "load_governor: heavy load (%d in-flight ≥ %d) — %s-priority caller "
        "waiting up to %.0fs task=%s",
        count, soft_limit, priority, budget, label,
    )
    while loop.time() < deadline:
        await asyncio.sleep(min(_POLL_INTERVAL_S, max(0.1, deadline - loop.time())))
        count = await _inflight_count()
        if count < soft_limit:
            return
    # Budget exhausted — admit anyway (priority means delayed, never denied).
    logger.info(
        "load_governor: %s-priority caller admitted after full %.0fs wait "
        "(still %d in-flight) task=%s",
        priority, budget, count, label,
    )


@asynccontextmanager
async def generation_slot(priority: str, label: str = ""):
    """Hold one global in-flight slot for the duration of a generation.

    Admission may be delayed for non-priority callers when the platform is
    under heavy load; it never raises and never rejects.
    """
    member = uuid.uuid4().hex
    try:
        await _wait_for_admission((priority or "normal").lower(), label)
        await _register(member)
    except Exception as exc:
        # The governor must never take generation down with it.
        logger.warning("load_governor: admission error (%s) — proceeding ungated", exc)
        member = None
    try:
        yield
    finally:
        if member is not None:
            try:
                await _release(member)
            except Exception:
                pass
