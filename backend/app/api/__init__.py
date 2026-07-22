"""API routers aggregated under a single router (mounted at /api)."""
from fastapi import APIRouter

from . import (
    admin,
    analytics,
    badge,
    batches,
    brand_kit,
    compliance,
    credits,
    export,
    generate,
    ledger,
    library,
    listing,
    resolve,
    skus,
    uploads,
    users,
    verify,
)

api_router = APIRouter()
api_router.include_router(users.router)
api_router.include_router(skus.router)
api_router.include_router(uploads.router)
api_router.include_router(generate.router)
api_router.include_router(batches.router)
api_router.include_router(verify.router)
api_router.include_router(badge.router)
api_router.include_router(ledger.router)
api_router.include_router(resolve.router)
api_router.include_router(analytics.router)
api_router.include_router(library.router)
api_router.include_router(export.router)
api_router.include_router(brand_kit.router)
api_router.include_router(credits.router)
api_router.include_router(listing.router)
api_router.include_router(compliance.router)
api_router.include_router(admin.router)
