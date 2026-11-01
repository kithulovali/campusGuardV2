from fastapi import APIRouter

from api.v1.routers import alerts, campus, dashboard, entries, overstay, reports, traffic, visitors

router = APIRouter()

for module in (campus, visitors, alerts, entries, dashboard, reports, traffic, overstay):
    router.include_router(module.router)
