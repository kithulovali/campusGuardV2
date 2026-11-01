import os
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv

# Load the repository-level .env before reading any environment variables.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

_secret_key = os.getenv("SECRET_KEY", "")
if len(_secret_key) < 32:
    raise RuntimeError("SECRET_KEY must contain at least 32 characters. Set it in .env.")

settings = SimpleNamespace(
    app_name=os.getenv("APP_NAME", "CampusGuard API"),
    app_version=os.getenv("APP_VERSION", "3.0.0"),
    environment=os.getenv("ENVIRONMENT", "development"),
    # Prefer the separate Turso credentials; DATABASE_URL remains supported
    # for existing deployments and other SQLAlchemy-compatible databases.
    turso_database_url=os.getenv("TURSO_DATABASE_URL") or None,
    turso_auth_token=os.getenv("TURSO_AUTH_TOKEN") or None,
    database_url=os.getenv("DATABASE_URL") or None,
    db_host=os.getenv("DB_HOST", "localhost"),
    db_port=int(os.getenv("DB_PORT", "3306")),
    db_user=os.getenv("DB_USER", "campusguard"),
    db_password=os.getenv("DB_PASSWORD", ""),
    db_name=os.getenv("DB_NAME", "campusguard"),
    secret_key=_secret_key,
    algorithm=os.getenv("ALGORITHM", "HS256"),
    access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
    refresh_token_expire_days=int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")),
)
if settings.access_token_expire_minutes <= 0 or settings.refresh_token_expire_days <= 0:
    raise RuntimeError("Token expiration settings must be positive.")

if bool(settings.turso_database_url) != bool(settings.turso_auth_token):
    raise RuntimeError("Set both TURSO_DATABASE_URL and TURSO_AUTH_TOKEN when using Turso.")
