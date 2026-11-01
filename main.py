import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.v1.router import router as api_v1_router
from core.config import settings
from db.session import Base, engine
import models  # noqa: F401 - registers every ORM model with SQLAlchemy metadata


class PhotoFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/photo" not in record.getMessage()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.environment.lower() == "development":
        Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()


def create_app() -> FastAPI:
    logging.getLogger("uvicorn.access").addFilter(PhotoFilter())
    app = FastAPI(
        title="CampusGuard API",
        summary="Campus access control and security management API",
        description=(
            "**Developed by kithulovali.**\n\n"
            "This is the updated version of the original CampusGuard API, "
            "providing authentication, user administration, QR-based access "
            "control, visitor management, alerts, reporting, and campus "
            "monitoring services."
        ),
        version=settings.app_version,
        openapi_tags=[
            {"name": "Authentication", "description": "Student registration, sign-in, token renewal, and sign-out."},
            {"name": "Users", "description": "User accounts, profiles, directory search, and administration."},
            {"name": "Gates & Access Control", "description": "Gate discovery, QR scanning, access decisions, and entry records."},
            {"name": "Campus Monitoring", "description": "Live campus occupancy and operational dashboard statistics."},
            {"name": "Visitors", "description": "Visitor registration, pre-registration, check-in, and check-out."},
            {"name": "Alerts & Incidents", "description": "Security alerts, incident resolution, and automated overstay alerts."},
            {"name": "QR Code Management", "description": "QR code renewal, lost-code replacement, and expiry monitoring."},
            {"name": "Photos & Profiles", "description": "User profile photo upload, retrieval, and deletion."},
            {"name": "Reports & Analytics", "description": "Attendance reports, weekly traffic, and operational statistics."},
            {"name": "Administration", "description": "Audit history, bulk user imports, lockdown controls, and guard statistics."},
            {"name": "System", "description": "API service information and health status."},
        ],
        lifespan=lifespan,
    )
    static_dir = Path(__file__).resolve().parent / "static"
    (static_dir / "qr_codes").mkdir(parents=True, exist_ok=True)
    (static_dir / "photos").mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    app.include_router(api_v1_router, prefix="/api/v1")

    @app.get("/", tags=["System"])
    def root():
        return {"status": "ok", "service": settings.app_name, "version": settings.app_version, "docs": "/docs"}

    @app.get("/health", tags=["System"])
    def health():
        return {"status": "healthy"}

    return app


app = create_app()
