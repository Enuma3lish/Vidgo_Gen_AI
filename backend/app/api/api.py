from fastapi import APIRouter, Depends
from app.api.v1 import (
    auth, payments, demo, plans, promotions, credits, effects, generation,
    landing, quota, tools, admin, admin_models, session, interior, workflow, subscriptions,
    prompts, user_works, uploads, referrals, social_media, einvoices,
    example, downloads, share_proxy, hero, tasks,
)
from app.api.deps import capture_client_task_id

# Applied to every generation-producing router so the X-Client-Task-Id header
# (P0-2) is stamped onto the UserGeneration / PendingProviderTask rows they
# create, enabling GET /user/tasks/{id} status polling + refresh recovery.
_task_id_dep = [Depends(capture_client_task_id)]

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(subscriptions.router, tags=["subscriptions"])
api_router.include_router(demo.router, prefix="/demo", tags=["demo"])
api_router.include_router(plans.router, tags=["plans"])
api_router.include_router(promotions.router, prefix="/promotions", tags=["promotions"])
api_router.include_router(credits.router, tags=["credits"])
api_router.include_router(effects.router, tags=["effects"], dependencies=_task_id_dep)
api_router.include_router(generation.router, prefix="/generate", tags=["generation"], dependencies=_task_id_dep)
api_router.include_router(landing.router, prefix="/landing", tags=["landing"])
api_router.include_router(quota.router, prefix="/quota", tags=["quota"])
api_router.include_router(tools.router, prefix="/tools", tags=["tools"], dependencies=_task_id_dep)
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_models.router, prefix="/admin", tags=["admin-models"])
api_router.include_router(session.router, prefix="/session", tags=["session"])
api_router.include_router(interior.router, tags=["interior"], dependencies=_task_id_dep)
api_router.include_router(workflow.router, tags=["workflow"])
api_router.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
api_router.include_router(user_works.router, prefix="/user", tags=["user"])
api_router.include_router(downloads.router, prefix="/downloads", tags=["downloads"])
api_router.include_router(uploads.router, tags=["uploads"])
api_router.include_router(referrals.router, tags=["referrals"])
api_router.include_router(social_media.router, tags=["social"])
api_router.include_router(einvoices.router, prefix="/einvoices", tags=["einvoices"])
api_router.include_router(example.router, prefix="/examples", tags=["examples"])
api_router.include_router(share_proxy.router, prefix="/share", tags=["share"])
api_router.include_router(hero.router, tags=["hero"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
