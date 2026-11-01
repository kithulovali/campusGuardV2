from fastapi import APIRouter

from api.v1.routers import auth, features, gates, misc, users

router = APIRouter()

# Register static feature paths before /users/{user_id}.
router.include_router(auth.router)
router.include_router(features.router)
router.include_router(users.router)
router.include_router(gates.router)
router.include_router(misc.router)
