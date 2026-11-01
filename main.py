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
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
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
