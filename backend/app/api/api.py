from fastapi import APIRouter
from app.api.v1 import auth, payments, demo

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(demo.router, prefix="/demo", tags=["demo"])
