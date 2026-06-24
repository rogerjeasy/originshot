"""API routers aggregated under a single router (mounted at /api)."""
from fastapi import APIRouter

from . import analytics, brand_kit, export, generate, skus, uploads, verify

api_router = APIRouter()
api_router.include_router(skus.router)
api_router.include_router(uploads.router)
api_router.include_router(generate.router)
api_router.include_router(verify.router)
api_router.include_router(analytics.router)
api_router.include_router(export.router)
api_router.include_router(brand_kit.router)
