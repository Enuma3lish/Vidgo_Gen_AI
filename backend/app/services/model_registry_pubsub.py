"""Cross-instance live cache invalidation for the model registry.

Problem: ``app.core.model_registry.PIAPI_MODELS`` is a sync in-process dict.
When an admin saves an override via /admin/models, only the Cloud Run
instance that handled the save mutates its dict. Other instances keep
serving the old value until they restart.

Fix: Redis pub/sub.
  - On admin save, ``ModelRegistryService.set_override`` publishes
    ``model_registry:invalidate`` with the changed key.
  - Each backend instance runs ``model_registry_subscriber_loop`` as a
    background asyncio task spawned from the FastAPI lifespan startup.
  - On message, the subscriber refetches ``list_all()`` from DB and
    rewrites every ``PIAPI_MODELS[key]`` (and Kling version dicts) in
    place so provider call sites pick up the fresh value on their next
    payload build.

We refresh the whole table rather than just the changed key because the
extra DB round-trip is amortized — admins don't flip models 100x/sec —
and it keeps the code path identical regardless of which key fired.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)

INVALIDATE_CHANNEL = "model_registry:invalidate"


async def publish_invalidate(
    redis_client: Optional[redis.Redis],
    service_key: str,
    model: str,
    version: Optional[str],
) -> None:
    """Best-effort publish. Pub/sub failure must not surface as a 500 to
    the admin — the DB write already succeeded, the only consequence of a
    failed publish is that other instances won't refresh until their next
    own write or restart."""
    if not redis_client:
        return
    try:
        await redis_client.publish(
            INVALIDATE_CHANNEL,
            json.dumps({"service_key": service_key, "model": model, "version": version}),
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("model_registry publish failed: %s", exc)


async def refresh_in_process_cache(redis_client: Optional[redis.Redis]) -> int:
    """Pull every override from DB and rewrite the in-process registry dicts.

    Returns the number of keys updated. Used both by the pub/sub
    subscriber and by the initial startup so the in-process cache
    converges with DB state even if no pub/sub event fires.
    """
    try:
        from app.core import model_registry as static_registry
        from app.core.database import AsyncSessionLocal
        from app.services.model_registry_service import ModelRegistryService

        async with AsyncSessionLocal() as session:
            svc = ModelRegistryService(session, redis_client)
            all_keys = await svc.list_all()

        updated = 0
        for key, info in all_keys.items():
            effective = info["effective"]
            model = effective.get("model")
            version = effective.get("version")
            # NOTE (Bug #7 — known edge, intentionally unfixed under Bug #2 Route B):
            # the `and model` guard only skips when the EFFECTIVE model is empty.
            # For every known key `effective` falls back to the non-empty static
            # default (ModelRegistryService.resolve: DB → env → PIAPI_MODELS), and
            # list_all only iterates keys present in PIAPI_MODELS — so clearing/
            # deleting an override DOES propagate today (this rewrites the in-process
            # dict back to the default). The guard would only swallow a propagation
            # if a future "disable / clear-to-empty" semantics is added (Bug #2
            # Route A); that feature must restore the static default (or set an
            # explicit disabled marker) here rather than skip on an empty model.
            if key in static_registry.PIAPI_MODELS and model:
                if static_registry.PIAPI_MODELS[key] != model:
                    static_registry.PIAPI_MODELS[key] = model
                    updated += 1
            if key == "kling_video_version" and version:
                if static_registry.PIAPI_KLING_VERSIONS.get("default") != version:
                    static_registry.PIAPI_KLING_VERSIONS["default"] = version
                    updated += 1
            if key == "kling_flagship_version" and version:
                if static_registry.PIAPI_KLING_VERSIONS.get("flagship") != version:
                    static_registry.PIAPI_KLING_VERSIONS["flagship"] = version
                    updated += 1
        return updated
    except Exception as exc:
        logger.warning("model_registry refresh_in_process_cache failed: %s", exc)
        return 0


async def model_registry_subscriber_loop(redis_client: redis.Redis) -> None:
    """Long-running background task. Subscribes to the invalidate channel
    and refreshes the in-process cache on each message. Owned by the
    FastAPI lifespan — cancelled on shutdown."""
    pubsub = redis_client.pubsub()
    try:
        await pubsub.subscribe(INVALIDATE_CHANNEL)
        logger.info("model_registry subscriber: listening on %s", INVALIDATE_CHANNEL)
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            try:
                payload = json.loads(message.get("data") or "{}")
                logger.info("model_registry invalidate received: %s", payload.get("service_key"))
            except Exception:
                payload = {}
            updated = await refresh_in_process_cache(redis_client)
            logger.info("model_registry: refreshed %d keys after invalidate", updated)
    except asyncio.CancelledError:
        logger.info("model_registry subscriber: cancelled")
        raise
    except Exception as exc:
        logger.warning("model_registry subscriber loop crashed: %s", exc)
    finally:
        try:
            await pubsub.unsubscribe(INVALIDATE_CHANNEL)
            await pubsub.close()
        except Exception:  # pragma: no cover
            pass
