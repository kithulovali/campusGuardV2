import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.db.session import Base, engine
from app.models import models  # noqa: F401 - register ORM metadata


class PhotoFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/photo" not in record.getMessage()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Schema changes belong in Alembic migrations; create_all is retained only
    # as a development bootstrap for an empty local database.
    if settings.environment.lower() == "development":
        Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()


def create_app() -> FastAPI:
    logging.getLogger("uvicorn.access").addFilter(PhotoFilter())
    app = FastAPI(title=settings.app_name, version=settings.app_version,
                  lifespan=lifespan)
    static_dir = Path("static")
    (static_dir / "qr_codes").mkdir(parents=True, exist_ok=True)
    (static_dir / "photos").mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    app.include_router(api_v1_router, prefix="/api/v1")

    @app.get("/", tags=["System"])
    def root():
        return {"status": "ok", "service": settings.app_name,
                "version": settings.app_version, "docs": "/docs"}

    @app.get("/health", tags=["System"])
    def health():
        return {"status": "healthy"}

    return app


app = create_app()
