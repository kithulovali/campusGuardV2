from fastapi import APIRouter

from api.v1.routers import audit, bulk_users, guard_stats, lockdown, photos, qr, visitor_preregistration

router = APIRouter()

for module in (lockdown, photos, qr, guard_stats, visitor_preregistration, bulk_users, audit):
    router.include_router(module.router)
