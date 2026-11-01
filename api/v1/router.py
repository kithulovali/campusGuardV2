from fastapi import APIRouter

from api.v1.routers import auth, features, gates, misc, users

router = APIRouter()

router.include_router(auth.router)
router.include_router(users.router)
router.include_router(gates.router)
router.include_router(misc.router)
router.include_router(features.router)
