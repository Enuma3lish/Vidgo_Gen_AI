"""
ARQ Worker for Background Tasks
Handles scheduled demo regeneration and cleanup.

Usage:
    arq app.worker.WorkerSettings
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

# The standalone ARQ worker was retired 2026-06 (background tasks now run via
# Cloud Scheduler → POST /api/v1/tasks/*, which imports the task functions below
# directly). `arq` is therefore no longer a runtime/CI dependency. Import it when
# present (local dev that still runs `arq app.worker.WorkerSettings`), but fall
# back to inert stubs so this module — and anything importing its task functions
# — loads cleanly without arq installed.
try:
    from arq import cron
    from arq.connections import RedisSettings
except ModuleNotFoundError:  # arq not installed (production / CI)
    def cron(*args, **kwargs):  # type: ignore
        return None

    class RedisSettings:  # type: ignore
        @staticmethod
        def from_dsn(*args, **kwargs):
            return None
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.services.demo_service import get_demo_service
from app.services.credit_service import CreditService

logger = logging.getLogger(__name__)
settings = get_settings()


# Database session for worker
async def get_db_session() -> AsyncSession:
    """Create database session for worker tasks"""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


# =============================================================================
# SCHEDULED TASKS
# =============================================================================

async def regenerate_demos_task(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Daily task to regenerate demo images.
    Runs every 24 hours to refresh demos with new styles.
    """
    logger.info("Starting daily demo regeneration task")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as db:
            demo_service = get_demo_service()

            # First cleanup expired demos
            cleaned = await demo_service.cleanup_expired_demos(db)
            logger.info(f"Cleaned up {cleaned} expired demos")

            # Regenerate new demos
            results = await demo_service.regenerate_demos(
                db=db,
                count_per_category=15,  # 15 topics per category
                styles_per_topic=2      # 2 different styles per topic
            )

            return {
                "status": "completed",
                "cleaned_up": cleaned,
                "regeneration": results
            }

    except Exception as e:
        logger.error(f"Demo regeneration failed: {e}")
        return {"status": "failed", "error": str(e)}

    finally:
        await engine.dispose()


async def cleanup_expired_demos_task(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Hourly task to cleanup expired demos.
    More frequent than regeneration to keep DB clean.
    """
    logger.info("Starting demo cleanup task")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as db:
            demo_service = get_demo_service()
            cleaned = await demo_service.cleanup_expired_demos(db)

            return {"status": "completed", "cleaned_up": cleaned}

    except Exception as e:
        logger.error(f"Demo cleanup failed: {e}")
        return {"status": "failed", "error": str(e)}

    finally:
        await engine.dispose()


async def health_check_task(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Simple health check task"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


async def auto_renew_subscriptions_task(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Daily task to settle subscriptions whose period has ended.

    2026-07-10 rewrite: the old version extended end_date and granted a fresh
    credit allotment for EVERY overdue active subscription without collecting
    or verifying any payment — ECPay has no recurring mandate (one-time aio
    payment) and PayPal was never consulted, so a single NT$399 payment
    renewed with full credits forever, and PayPal subs whose external billing
    had failed kept renewing locally. Credits must only ever be granted on a
    payment signal (webhook / callback / verified gateway state).

    New behavior per overdue active subscription (end_date <= now):
      - PayPal-billed + PayPal reports ACTIVE  → extend the local period one
        cycle, NO credit grant (PAYMENT.SALE.COMPLETED grants per cycle).
      - PayPal-billed + PayPal reports cancelled/suspended/expired, or any
        non-recurring method (ECPay one-time, direct) → after a 3-day grace,
        mark the subscription expired, and if the user has no other active
        subscription: clear current_plan_id and zero subscription_credits
        (with an expiry ledger row). Purchased/bonus credits untouched.
      - PayPal lookup transient failure → skip, retry next run.
    """
    logger.info("Starting subscription settlement (auto-renew) check")

    from sqlalchemy import select, and_
    from app.models.user import User
    from app.models.billing import Plan, Subscription, CreditTransaction, Order as _Order

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    GRACE = timedelta(days=3)
    now = datetime.utcnow()

    extended_count = 0
    expired_count = 0
    skipped_count = 0
    error_count = 0

    try:
        async with async_session() as db:
            # ALL overdue active subs — including auto_renew=False (cancel-at-
            # period-end rows previously never transitioned out of "active",
            # leaving plan access + monthly resets running forever).
            result = await db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.status == "active",
                        Subscription.end_date <= now,
                    )
                )
            )
            subscriptions = result.scalars().all()

            for sub in subscriptions:
                try:
                    user = await db.get(User, sub.user_id)
                    plan = await db.get(Plan, sub.plan_id)
                    if not user or not plan:
                        continue

                    _last_order = (await db.execute(
                        select(_Order)
                        .where(_Order.subscription_id == sub.id)
                        .order_by(_Order.created_at.desc())
                    )).scalars().first()
                    _pay_method = (_last_order.payment_method if _last_order else "") or ""
                    _paypal_sub_id = ((_last_order.payment_data or {}).get("paypal_subscription_id")
                                      if _last_order else None)

                    is_yearly = (getattr(sub, "billing_cycle", None) or "monthly") == "yearly"

                    # ── PayPal: trust the gateway, not the calendar ──────────
                    if sub.auto_renew and _pay_method.lower() == "paypal" and _paypal_sub_id:
                        try:
                            from app.services.paypal_service import get_paypal_service
                            pp = get_paypal_service()
                            pp_resp = await pp.get_subscription(_paypal_sub_id)
                            if not (pp_resp or {}).get("success"):
                                raise RuntimeError((pp_resp or {}).get("error") or "lookup failed")
                            pp_status = str(((pp_resp or {}).get("subscription") or {}).get("status") or "").upper()
                        except Exception as exc:
                            logger.warning(
                                "auto-renew: PayPal lookup failed for sub %s (%s); retrying next run: %s",
                                sub.id, _paypal_sub_id, exc,
                            )
                            skipped_count += 1
                            continue

                        if pp_status == "ACTIVE":
                            old_end = sub.end_date
                            new_end = old_end + timedelta(days=365 if is_yearly else 30)
                            sub.start_date = old_end
                            sub.end_date = new_end
                            user.plan_started_at = old_end
                            user.plan_expires_at = new_end
                            extended_count += 1
                            logger.info(
                                "auto-renew: extended PayPal-active sub for user %s (%s) until %s "
                                "(credits granted by SALE webhook, not here)",
                                user.id, plan.name, new_end,
                            )
                            continue
                        # Non-active at PayPal → fall through to grace/expiry.

                    # ── No payment signal → expire after grace ───────────────
                    if sub.end_date.replace(tzinfo=None) > now - GRACE:
                        skipped_count += 1
                        continue

                    sub.status = "expired"
                    sub.auto_renew = False

                    other_active = (await db.execute(
                        select(Subscription.id).where(
                            and_(
                                Subscription.user_id == user.id,
                                Subscription.id != sub.id,
                                Subscription.status == "active",
                                Subscription.end_date > now,
                            )
                        ).limit(1)
                    )).scalar_one_or_none()

                    if other_active is None:
                        user.current_plan_id = None
                        old_credits = user.subscription_credits or 0
                        if old_credits > 0:
                            user.subscription_credits = 0
                            db.add(CreditTransaction(
                                user_id=user.id,
                                amount=-old_credits,
                                balance_after=(user.purchased_credits or 0) + (user.bonus_credits or 0),
                                transaction_type="expiry",
                                description=f"Subscription expired — {old_credits} unused subscription credits removed",
                            ))
                    expired_count += 1
                    logger.info("auto-renew: expired unpaid sub %s (user %s, %s, method=%s)",
                                sub.id, user.id, plan.name, _pay_method or "?")

                except Exception as e:
                    logger.error(f"Failed to settle subscription {sub.id}: {e}")
                    try:
                        await db.rollback()
                    except Exception:
                        pass
                    error_count += 1

            await db.commit()

        return {
            "status": "completed",
            "extended": extended_count,
            "expired": expired_count,
            "skipped": skipped_count,
            "errors": error_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Auto-renewal task failed: {e}")
        return {"status": "failed", "error": str(e)}

    finally:
        await engine.dispose()


# =============================================================================
# CREDIT MANAGEMENT TASKS
# =============================================================================

async def monthly_credit_reset_task(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Monthly task to reset subscription credits for all active subscribers.
    Runs on the 1st of each month at 00:05 UTC.

    Subscription credits DO NOT carry over — they reset to the plan's monthly_credits.
    Purchased credits and bonus credits are NOT affected.
    """
    logger.info("Starting monthly credit reset task")

    from sqlalchemy import select, and_, desc
    from app.models.user import User
    from app.models.billing import Plan, CreditTransaction, Subscription

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    reset_count = 0
    error_count = 0

    try:
        async with async_session() as db:
            # Get all active users with a plan
            result = await db.execute(
                select(User).where(
                    and_(
                        User.current_plan_id != None,
                        User.is_active == True,
                    )
                )
            )
            users = result.scalars().all()

            for user in users:
                try:
                    # Get user's plan
                    plan_result = await db.execute(
                        select(Plan).where(Plan.id == user.current_plan_id)
                    )
                    plan = plan_result.scalar_one_or_none()

                    if not plan or not plan.monthly_credits:
                        continue

                    now_utc = datetime.utcnow()

                    # Guard (a) 2026-07-10 — idempotency + anniversary overlap:
                    # every grant path (activation, SALE-webhook renewal, this
                    # task) stamps credits_reset_at. Skipping anyone refreshed
                    # in the last 25 days prevents (1) a double-fired reset
                    # re-filling mid-cycle spend, and (2) the calendar reset
                    # topping users up AGAIN days after an anniversary grant.
                    _reset_at = user.credits_reset_at
                    if _reset_at and _reset_at.replace(tzinfo=None) > now_utc - timedelta(days=25):
                        continue

                    # Guard (b) 2026-07-10 — entitlement: current_plan_id
                    # survives natural expiry and cancel-at-period-end, so
                    # filtering on it alone granted full free credits to lapsed
                    # accounts forever. Require a currently-valid subscription.
                    sub_res = await db.execute(
                        select(Subscription)
                        .where(
                            Subscription.user_id == user.id,
                            Subscription.status == "active",
                            Subscription.end_date >= now_utc,
                        )
                        .order_by(desc(Subscription.start_date))
                        .limit(1)
                    )
                    sub = sub_res.scalar_one_or_none()
                    if sub is None:
                        continue
                    is_yearly = (getattr(sub, "billing_cycle", None) or "monthly") == "yearly"

                    # Guard (c)/(d) 2026-07-10 — monthly PayPal subs get their
                    # allotment per-cycle from PAYMENT.SALE.COMPLETED (this
                    # reset was a second, uncoordinated top-up for them), and
                    # amounts are currency-aware (TWD payers previously got
                    # the larger USD allowance every month).
                    from app.models.billing import Order as _Order
                    from app.services.subscription_service import (
                        subscription_period_credits as _period_credits,
                    )
                    _last_order = (await db.execute(
                        select(_Order)
                        .where(_Order.subscription_id == sub.id)
                        .order_by(desc(_Order.created_at))
                    )).scalars().first()
                    _pay_method = (_last_order.payment_method if _last_order else "") or ""
                    if not is_yearly and _pay_method.lower() == "paypal":
                        continue

                    old_credits = user.subscription_credits or 0
                    month_base = _period_credits(plan, _pay_method, "monthly")
                    if is_yearly:
                        new_credits = int(round(month_base * 11 / 12))
                    else:
                        new_credits = month_base
                    if new_credits <= 0:
                        continue

                    # Reset subscription credits to plan amount
                    user.subscription_credits = new_credits
                    user.credits_reset_at = now_utc

                    # Record the reset as a transaction
                    # First record expiry of old credits if any
                    if old_credits > 0:
                        expiry_tx = CreditTransaction(
                            user_id=user.id,
                            amount=-old_credits,
                            balance_after=(user.purchased_credits or 0) + (user.bonus_credits or 0) + new_credits,
                            transaction_type="expiry",
                            description=f"Monthly subscription credit reset — {old_credits} unused credits expired",
                        )
                        db.add(expiry_tx)

                    # Then record the new allocation
                    alloc_tx = CreditTransaction(
                        user_id=user.id,
                        amount=new_credits,
                        balance_after=(user.purchased_credits or 0) + (user.bonus_credits or 0) + new_credits,
                        transaction_type="subscription",
                        description=f"Monthly credit allocation — {plan.display_name or plan.name} plan ({new_credits} credits)",
                    )
                    db.add(alloc_tx)

                    reset_count += 1

                except Exception as e:
                    logger.error(f"Failed to reset credits for user {user.id}: {e}")
                    try:
                        await db.rollback()
                    except Exception:
                        pass
                    error_count += 1

            await db.commit()
            logger.info(f"Monthly credit reset completed: {reset_count} users reset, {error_count} errors")

        return {
            "status": "completed",
            "users_reset": reset_count,
            "errors": error_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Monthly credit reset task failed: {e}")
        return {"status": "failed", "error": str(e)}

    finally:
        await engine.dispose()


async def cleanup_expired_bonus_credits_task(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Daily task to clean up expired bonus credits.
    Zeroes out bonus_credits where bonus_credits_expiry has passed.
    """
    logger.info("Starting expired bonus credits cleanup")

    from sqlalchemy import select, and_
    from app.models.user import User
    from app.models.billing import CreditTransaction

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    cleaned_count = 0

    try:
        async with async_session() as db:
            result = await db.execute(
                select(User).where(
                    and_(
                        User.bonus_credits > 0,
                        User.bonus_credits_expiry != None,
                        User.bonus_credits_expiry < datetime.utcnow(),
                    )
                )
            )
            users = result.scalars().all()

            for user in users:
                expired_amount = user.bonus_credits
                user.bonus_credits = 0
                user.bonus_credits_expiry = None

                tx = CreditTransaction(
                    user_id=user.id,
                    amount=-expired_amount,
                    balance_after=(user.subscription_credits or 0) + (user.purchased_credits or 0),
                    transaction_type="expiry",
                    description=f"Bonus credits expired ({expired_amount} credits)",
                )
                db.add(tx)
                cleaned_count += 1

            await db.commit()
            logger.info(f"Cleaned up bonus credits for {cleaned_count} users")

        return {"status": "completed", "users_cleaned": cleaned_count}

    except Exception as e:
        logger.error(f"Bonus credit cleanup failed: {e}")
        return {"status": "failed", "error": str(e)}

    finally:
        await engine.dispose()


# =============================================================================
# ON-DEMAND TASKS (called via API)
# =============================================================================

async def generate_single_demo_task(
    ctx: Dict[str, Any],
    prompt: str,
    style: str = None
) -> Dict[str, Any]:
    """
    Generate a single demo on demand.
    Called when user prompt doesn't match any existing demo.
    """
    logger.info(f"Generating on-demand demo: {prompt[:50]}...")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as db:
            demo_service = get_demo_service()
            result = await demo_service.get_or_create_demo(
                db=db,
                prompt=prompt,
                preferred_style=style
            )
            return result

    except Exception as e:
        logger.error(f"On-demand demo generation failed: {e}")
        return {"status": "failed", "error": str(e)}

    finally:
        await engine.dispose()


# =============================================================================
# RECLAIM ORPHANED PROVIDER TASKS (2026-06)
# =============================================================================
# Long-poll endpoints (avatar, Veo, Kling Omni) can have their foreground
# request killed by Cloud Run (cold migration, SIGTERM at the request
# timeout, worker OOM). The upstream provider task keeps running — we lost
# the in-process poll loop, not the work. Each such endpoint writes a row
# to `pending_provider_tasks` BEFORE polling, capturing user_id, payload,
# and (as soon as the provider returns it) the upstream task_id. This task
# re-polls those rows and either:
#   - materialises a UserGeneration on success, OR
#   - refunds the credits on permanent failure, OR
#   - abandons + refunds after RECLAIM_MAX_AGE_HOURS.
# Cadence: every 2 minutes. Tasks polled by the foreground request have
# their status flipped to "completed"/"failed" inside that request — this
# worker only touches rows still in "submitting"/"polling" past the grace.

# 2026-07-10 fix: was 60s, which assumed on_submit flips the row to
# "polling" within seconds of submit. That is only true for PiAPI/A2E.
# Pollo (and any provider that polls internally without firing on_submit)
# leaves the row in "submitting" for the WHOLE render (2-20 min), and the
# foreground itself legitimately polls up to 55 min (avatar 3300s, kling
# 1800s, I2V 1200s) — so the old 60s grace made the reclaim worker refund
# tasks that were still being served: the user received the video AND a
# full refund on essentially every Pollo-served generation. The grace must
# exceed the longest legitimate foreground window; genuinely-dead requests
# are still recovered, just 90 min later instead of 60 s.
RECLAIM_FOREGROUND_GRACE_SEC = 5400    # 90 min > max foreground poll (avatar 3300s + pre-stages)
RECLAIM_MAX_AGE_HOURS = 6              # after this, abandon + refund


# tool_type → media kind. Drives which output key the worker looks for
# in the upstream response AND which UserGeneration column receives the
# reclaimed URL. Default for unknown tools is "video".
TOOL_TYPE_KIND = {
    "ai_avatar":               "video",
    "short_video":             "video",
    "claymation":              "video",  # only T2V mode reaches reclaim
    "video_background_remove": "video",
    "image_upscale":           "image",
    "try_on":                  "image",  # Kling try-on (≤600s poll) — added 2026-06
    "kling_video":             "video",  # Kling video (≤1800s poll) — added 2026-06
    "product_recolor":         "image",  # Kontext recolor — was missing, so reclaim
                                         # treated it as video, found no video_url,
                                         # and refunded delivered images (2026-07-10)
    "room_redesign":           "image",  # disconnect-coverage rows (2026-07-10) — no
    "sora2":                   "video",  # task_id is ever captured on these, so they
                                         # only reach the orphan-submit refund branch;
                                         # mapped anyway so a future on_submit wiring
                                         # can't hit the unknown-tool warning.
}


# tool_type → ToolType enum so the reclaim worker can materialise the
# UserGeneration row with the same tool_type the foreground handler used.
# NOT in this map (intentional, ordered by reason):
#   - video_dubbing      → not long-poll vulnerable (TTS ~30 s + local
#                          ffmpeg ~few s, well inside Cloud Run 3600 s).
#   - image_translation  → Vertex Gemini synchronous; no task_id exists
#                          to poll, so reclaim cannot help even in theory.
#   - bg_removal         → fast image op (<5 s), no reclaim need.
def _build_tool_enum_map():
    """Built lazily inside the reclaim task — importing material at
    module scope would create a circular import with app.models."""
    from app.models.material import ToolType as _ToolType
    return {
        "ai_avatar":               _ToolType.AI_AVATAR,
        "short_video":             _ToolType.SHORT_VIDEO,
        "claymation":              _ToolType.SHORT_VIDEO,
        "video_background_remove": _ToolType.SHORT_VIDEO,
        "image_upscale":           _ToolType.EFFECT,  # matches foreground choice
        "try_on":                  _ToolType.TRY_ON,
        "kling_video":             _ToolType.KLING_VIDEO,
        "product_recolor":         _ToolType.EFFECT,  # matches foreground choice (tools.py recolor)
        "room_redesign":           _ToolType.ROOM_REDESIGN,
        "sora2":                   _ToolType.SORA2,
    }


def _extract_piapi_media_url(out, kind: str = "video") -> str | None:
    """Pull a usable media URL out of PiAPI's many output shapes.

    Mirrors the unpacking the foreground handler in tools.py already does
    (claymation/short_video for video, upscale for image). We go straight
    from the raw PiAPI response (no piapi_provider normalisation pass), so
    we have to cover all the per-model shapes ourselves.

    Shapes seen in prod (2026-05 audit):
      Video — Seedance / Hailuo / Wan / Hunyuan / Veo (generic I2V/T2V):
        output.video_url = "https://…"
      Video — Kling 1.6 / 2.6 / 2.1-master (older versions):
        output.works[].video.url
      Video — Kling 3.0 / Omni (newest, multimodal):
        output.video = "https://…"                          OR
        output.video = {"url": "…"}                          OR
        output.video = {"resource": "…"}                     OR
        output.video = {"resource_without_watermark": "…"}
      Image — Qubico/image-toolkit upscale, T2I models:
        output.image_url = "https://…"                       OR
        output.images = [{"url": "…"} | "https://…", …]
      Defensive fallbacks (older PiAPI normalised key):
        top-level output_url
    """
    if not isinstance(out, dict):
        return None
    primary_key = "image_url" if kind == "image" else "video_url"
    # 1) Direct primary key + the universal fallbacks
    for k in (primary_key, "url", "output_url"):
        v = out.get(k)
        if isinstance(v, str) and v:
            return v
    if kind == "video":
        # 2) Kling 3.0/Omni — "video" key, string or dict
        video = out.get("video")
        if isinstance(video, str) and video:
            return video
        if isinstance(video, dict):
            for k in ("url", "video_url", "resource", "resource_without_watermark"):
                v = video.get(k)
                if isinstance(v, str) and v:
                    return v
        # 3) Kling older — works[].video.url
        works = out.get("works") or out.get("video_urls")
        if isinstance(works, list):
            for w in works:
                if isinstance(w, str) and w:
                    return w
                if isinstance(w, dict):
                    wv = w.get("video") or w
                    if isinstance(wv, dict):
                        for k in ("url", "video_url", "resource", "resource_without_watermark"):
                            v = wv.get(k)
                            if isinstance(v, str) and v:
                                return v
                    elif isinstance(wv, str) and wv:
                        return wv
    # 4) Array shapes — images[] / image_urls[]
    arr = out.get("images") or out.get("image_urls")
    if isinstance(arr, list) and arr:
        first = arr[0]
        if isinstance(first, dict):
            for k in ("url", "image_url"):
                v = first.get(k)
                if isinstance(v, str) and v:
                    return v
        if isinstance(first, str) and first:
            return first
    return None


# Back-compat alias — internal callers used the old name before 2026-06.
_extract_piapi_video_url = _extract_piapi_media_url


async def _reclaim_check_piapi(provider_task_id: str, kind: str = "video") -> Dict[str, Any]:
    """One-shot PiAPI poll. Returns {status, media_url?, error?}.

    status ∈ {"completed", "failed", "running"}.
    kind ∈ {"video", "image"} — determines which output key to prefer.
    """
    import os
    import httpx
    base_url = "https://api.piapi.ai/api/v1"
    api_key = os.getenv("PIAPI_KEY", "")
    if not api_key:
        return {"status": "running", "error": "PIAPI_KEY missing in worker env"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{base_url}/task/{provider_task_id}",
                headers={"X-API-Key": api_key},
            )
            if resp.status_code >= 500:
                return {"status": "running", "error": f"upstream {resp.status_code}"}
            data = resp.json()
    except Exception as exc:
        return {"status": "running", "error": str(exc)[:160]}

    task_data = data.get("data", data)
    upstream = (task_data.get("status") or "").lower()
    if upstream in ("completed", "success", "done"):
        out = task_data.get("output") or task_data.get("result") or {}
        media_url = _extract_piapi_media_url(out, kind=kind)
        if media_url:
            return {"status": "completed", "media_url": media_url}
        # success without URL — treat as permanent failure (matches the
        # foreground handler in tools.py).
        return {"status": "failed", "error": f"no {kind}_url in completed task"}
    if upstream in ("failed", "error"):
        return {"status": "failed", "error": (task_data.get("error") or "upstream failure")[:200]}
    return {"status": "running"}


async def _reclaim_check_a2e(provider_task_id: str, kind: str = "video") -> Dict[str, Any]:
    """One-shot A2E poll. Same return shape as _reclaim_check_piapi.

    A2E only emits avatar/lip-sync videos today, but `kind` is accepted so
    callers don't have to special-case providers — uniform call signature
    across all reclaim adapters.
    """
    try:
        from app.providers.a2e_provider import A2EProvider
        a2e = A2EProvider()
        status = await a2e.service.get_task_status(provider_task_id)
    except Exception as exc:
        return {"status": "running", "error": str(exc)[:160]}
    upstream = (status.get("status") or "").lower()
    if upstream == "succeed":
        media_url = status.get("video_url") or status.get("remote_url")
        if media_url:
            return {"status": "completed", "media_url": media_url}
        return {"status": "failed", "error": "no video_url in completed task"}
    if upstream == "failed":
        return {"status": "failed", "error": (status.get("error") or "upstream failure")[:200]}
    return {"status": "running"}


async def _finalize_pending_and_refund(db, p, *, status: str, error_message: str, now, description: str) -> bool:
    """Flip a pending row to a terminal status FIRST (own commit), THEN refund.

    Order matters: CreditService.add_credits commits internally, so refunding
    first left a window where the refund was booked while the row was still
    submitting/polling — the next 2-minute tick would refund it AGAIN. With
    terminal-status-first, a crash after the status commit costs one refund
    that ops can replay from the REFUND_FAILED marker; it can never mint
    duplicate refunds.

    Refunds land in the PURCHASED bucket (2026-07-10): the old
    credit_type="subscription" was absolute-overwritten by every renewal /
    monthly reset, so a refund issued near a cycle boundary silently
    evaporated — and never-expiring purchased credits came back as expiring
    subscription ones. The worker has no per-bucket deduction snapshot (the
    foreground's _refund_credits does), so purchased — the one bucket nothing
    ever overwrites — is the only safe destination.
    """
    p.status = status
    p.error_message = error_message
    p.completed_at = now
    await db.commit()
    if p.credits_charged and p.credits_charged > 0:
        try:
            await CreditService(db).add_credits(
                user_id=str(p.user_id),
                amount=p.credits_charged,
                credit_type="purchased",
                transaction_type="refund",
                description=description,
                metadata={"pending_task_id": str(p.id)},
            )
        except Exception as exc:
            logger.error(
                "reclaim: REFUND FAILED for %s (%s credits, user %s): %s — replay manually",
                p.id, p.credits_charged, p.user_id, exc,
            )
            try:
                p.error_message = f"{error_message} | REFUND_FAILED: {str(exc)[:120]}"
                await db.commit()
            except Exception:
                await db.rollback()
            return False
    return True


async def reclaim_pending_provider_tasks_task(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Re-poll orphaned upstream tasks, materialise results or refund."""
    from sqlalchemy import select, and_, or_
    from app.models.user import User
    from app.models.pending_provider_task import PendingProviderTask
    from app.models.user_generation import UserGeneration
    from app.services.gcs_storage_service import get_gcs_storage

    TOOL_TYPE_TO_ENUM = _build_tool_enum_map()

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    now = datetime.utcnow()
    grace = now - timedelta(seconds=RECLAIM_FOREGROUND_GRACE_SEC)
    abandon_cutoff = now - timedelta(hours=RECLAIM_MAX_AGE_HOURS)

    stats = {"checked": 0, "completed": 0, "failed": 0, "abandoned": 0, "still_running": 0, "errors": 0}

    try:
        async with async_session() as db:
            res = await db.execute(
                select(PendingProviderTask).where(
                    and_(
                        PendingProviderTask.status.in_(["submitting", "polling"]),
                        PendingProviderTask.created_at <= grace,
                    )
                )
            )
            pendings = res.scalars().all()
            stats["checked"] = len(pendings)

            for p in pendings:
                # Abandon rows that exceeded the max retention window —
                # refund the user; assume the upstream is permanently lost.
                if p.created_at and p.created_at.replace(tzinfo=None) < abandon_cutoff:
                    try:
                        ok = await _finalize_pending_and_refund(
                            db, p,
                            status="abandoned",
                            error_message=f"reclaim age exceeded {RECLAIM_MAX_AGE_HOURS}h",
                            now=now,
                            description=f"Refund: abandoned {p.service_type} (reclaim age > {RECLAIM_MAX_AGE_HOURS}h)",
                        )
                        stats["abandoned" if ok else "errors"] += 1
                    except Exception as exc:
                        logger.warning("reclaim: abandon refund failed for %s: %s", p.id, exc)
                        await db.rollback()
                        stats["errors"] += 1
                    continue

                # Rows still in "submitting" never captured a task_id — either
                # the original request died before the upstream API responded,
                # or the serving provider never fires on_submit (Pollo polls
                # internally). The 90-min grace above guarantees no live
                # foreground still owns this row. Abandon + refund.
                if p.status == "submitting" or not p.provider_task_id:
                    try:
                        ok = await _finalize_pending_and_refund(
                            db, p,
                            status="abandoned",
                            error_message="provider submit died before task_id was captured",
                            now=now,
                            description=f"Refund: {p.service_type} never received provider task_id",
                        )
                        stats["abandoned" if ok else "errors"] += 1
                    except Exception as exc:
                        logger.warning("reclaim: orphan-submit refund failed for %s: %s", p.id, exc)
                        await db.rollback()
                        stats["errors"] += 1
                    continue

                # Per-tool media kind. Determines which upstream output key
                # to look for AND which UserGeneration column to populate.
                kind = TOOL_TYPE_KIND.get(p.tool_type, "video")

                # Re-poll the upstream provider.
                try:
                    if p.provider_name == "piapi":
                        check = await _reclaim_check_piapi(p.provider_task_id, kind=kind)
                    elif p.provider_name == "a2e":
                        check = await _reclaim_check_a2e(p.provider_task_id, kind=kind)
                    else:
                        # Un-pollable provider (renamed/removed, or an
                        # on_submit wrote a name we can't re-poll). The old
                        # skip left the row active — it occupied the user's
                        # concurrent-limit slot for up to 6h until the abandon
                        # cutoff finally refunded it (2026-07-10 round 5).
                        # Terminal-mark + refund immediately instead.
                        logger.warning("reclaim: unknown provider %r on task %s — abandoning + refunding", p.provider_name, p.id)
                        try:
                            ok = await _finalize_pending_and_refund(
                                db, p,
                                status="abandoned",
                                error_message=f"unknown provider '{p.provider_name}' — cannot re-poll",
                                now=now,
                                description=f"Refund: {p.service_type} on un-pollable provider {p.provider_name}",
                            )
                            stats["abandoned" if ok else "errors"] += 1
                        except Exception as exc:
                            logger.warning("reclaim: unknown-provider refund failed for %s: %s", p.id, exc)
                            await db.rollback()
                            stats["errors"] += 1
                        continue
                except Exception as exc:
                    logger.warning("reclaim: poll exception for %s: %s", p.id, exc)
                    stats["errors"] += 1
                    continue

                p.last_polled_at = now

                if check["status"] == "running":
                    stats["still_running"] += 1
                    try:
                        await db.commit()
                    except Exception as exc:
                        logger.warning("reclaim: last_polled_at commit failed for %s: %s", p.id, exc)
                        await db.rollback()
                    continue

                if check["status"] == "completed":
                    # Persist provider CDN URL into GCS so it survives 14-day expiry.
                    media_url = check.get("media_url")
                    try:
                        media_url = await get_gcs_storage().safe_persist_url(
                            media_url, kind, str(p.user_id),
                        )
                    except Exception:
                        pass  # fall back to provider CDN (safe_persist_url already guards)

                    if not media_url:
                        # completed but somehow no URL → treat as failure + refund.
                        # Terminal-first via the helper: the old order refunded
                        # first and swallowed refund errors while still marking
                        # the row failed — the refund was then lost forever.
                        try:
                            ok = await _finalize_pending_and_refund(
                                db, p,
                                status="failed",
                                error_message="completed without media URL",
                                now=now,
                                description=f"Refund: {p.service_type} completed without URL",
                            )
                            stats["failed" if ok else "errors"] += 1
                        except Exception as exc:
                            logger.warning("reclaim: refund-on-empty failed for %s: %s", p.id, exc)
                            await db.rollback()
                            stats["errors"] += 1
                        continue

                    try:
                        input_p = p.input_params or {}
                        tool_enum = TOOL_TYPE_TO_ENUM.get(p.tool_type)
                        if tool_enum is not None:
                            # Pull the input_text the foreground would have set —
                            # avatar uses `script`, short-video / claymation
                            # use `prompt` / `final_prompt`.
                            input_text = (
                                input_p.get("script")
                                or input_p.get("prompt")
                                or input_p.get("final_prompt")
                            )
                            user_gen = UserGeneration(
                                user_id=p.user_id,
                                tool_type=tool_enum,
                                input_image_url=input_p.get("image_url"),
                                input_video_url=input_p.get("video_url"),
                                input_text=input_text,
                                input_params={
                                    **{k: v for k, v in input_p.items()
                                       if k not in ("image_url", "video_url",
                                                    "script", "prompt", "final_prompt")},
                                    "reclaimed": True,
                                },
                                # Write the result into the correct column.
                                # kind=="image" → result_image_url (upscale);
                                # kind=="video" → result_video_url (avatar,
                                # short-video, claymation T2V, vbg-remove).
                                result_image_url=media_url if kind == "image" else None,
                                result_video_url=media_url if kind == "video" else None,
                                result_metadata={
                                    "api": p.provider_name,
                                    "reclaimed_at": now.isoformat(),
                                    "pending_task_id": str(p.id),
                                },
                                credits_used=p.credits_charged,
                                # Carry the client correlation id (P0-2) forward so a
                                # client polling GET /user/tasks/{id} sees "completed"
                                # the moment the reclaim worker materialises the row.
                                client_task_id=p.client_task_id,
                            )
                            user_gen.set_expiry()
                            db.add(user_gen)
                        else:
                            logger.warning(
                                "reclaim: no UserGeneration mapping for tool_type=%r "
                                "(pending_task=%s) — marking completed but no gallery row",
                                p.tool_type, p.id,
                            )

                        p.status = "completed"
                        p.result_url = media_url
                        p.completed_at = now
                        await db.commit()
                        stats["completed"] += 1
                        logger.info(
                            "reclaim: recovered %s task %s for user %s",
                            p.tool_type, p.id, p.user_id,
                        )
                    except Exception as exc:
                        logger.error("reclaim: materialise failed for %s: %s", p.id, exc, exc_info=True)
                        # Roll back so the poisoned transaction doesn't abort
                        # every remaining row in this run.
                        try:
                            await db.rollback()
                        except Exception:
                            pass
                        stats["errors"] += 1
                    continue

                # status == "failed" — mark failed first, then refund.
                if check["status"] == "failed":
                    try:
                        ok = await _finalize_pending_and_refund(
                            db, p,
                            status="failed",
                            error_message=check.get("error") or "upstream failure",
                            now=now,
                            description=f"Refund: {p.service_type} upstream failed (reclaim)",
                        )
                        stats["failed" if ok else "errors"] += 1
                    except Exception as exc:
                        logger.warning("reclaim: refund-on-fail failed for %s: %s", p.id, exc)
                        await db.rollback()
                        stats["errors"] += 1
                    continue

        return {"status": "completed", "timestamp": now.isoformat(), **stats}

    except Exception as exc:
        logger.error("reclaim_pending_provider_tasks_task failed: %s", exc, exc_info=True)
        return {"status": "failed", "error": str(exc), **stats}

    finally:
        await engine.dispose()


# =============================================================================
# WORKER SETTINGS
# =============================================================================

class WorkerSettings:
    """ARQ Worker configuration"""

    # Redis connection
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)

    # Available functions
    functions = [
        regenerate_demos_task,
        cleanup_expired_demos_task,
        health_check_task,
        generate_single_demo_task,
        monthly_credit_reset_task,
        cleanup_expired_bonus_credits_task,
        auto_renew_subscriptions_task,
        reclaim_pending_provider_tasks_task,
    ]

    # Cron jobs (scheduled tasks)
    cron_jobs = [
        # Daily demo regeneration DISABLED — pre-generated content is permanent.
        # Use main_pregenerate.py for one-time generation instead of wasting
        # API credits on daily regeneration that nobody specifically requested.
        # To re-enable: uncomment the cron below.
        # cron(
        #     regenerate_demos_task,
        #     hour=3,
        #     minute=0,
        #     run_at_startup=False
        # ),
        # Hourly cleanup of expired demos
        cron(
            cleanup_expired_demos_task,
            minute=30,  # Run at :30 every hour
            run_at_startup=True  # Run once on startup
        ),
        # Health check every 5 minutes
        cron(
            health_check_task,
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
            run_at_startup=True
        ),
        # Monthly credit reset — 1st of each month at 00:05 UTC
        cron(
            monthly_credit_reset_task,
            month=None,  # Every month
            day=1,
            hour=0,
            minute=5,
            run_at_startup=False
        ),
        # Daily expired bonus credit cleanup — 2:00 AM UTC
        cron(
            cleanup_expired_bonus_credits_task,
            hour=2,
            minute=0,
            run_at_startup=False
        ),
        # Daily auto-renewal check — 1:00 AM UTC
        # Renews expired subscriptions with auto_renew=True and allocates new credits
        cron(
            auto_renew_subscriptions_task,
            hour=1,
            minute=0,
            run_at_startup=False
        ),
        # Reclaim orphaned upstream provider tasks every 2 minutes.
        # Foreground requests that get killed by Cloud Run mid-poll leave
        # a `pending_provider_tasks` row behind; this re-polls the upstream
        # provider, materialises the result, or refunds. See the function
        # docstring + app/models/pending_provider_task.py for the lifecycle.
        cron(
            reclaim_pending_provider_tasks_task,
            minute={0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28,
                    30, 32, 34, 36, 38, 40, 42, 44, 46, 48, 50, 52, 54, 56, 58},
            run_at_startup=False
        ),
    ]

    # Worker settings
    max_jobs = 3
    job_timeout = 600  # 10 minutes max per job
    keep_result = 3600  # Keep results for 1 hour
    health_check_interval = 30

    # Logging
    @staticmethod
    async def on_startup(ctx: Dict[str, Any]) -> None:
        logger.info("ARQ Worker started")

    @staticmethod
    async def on_shutdown(ctx: Dict[str, Any]) -> None:
        logger.info("ARQ Worker shutting down")
