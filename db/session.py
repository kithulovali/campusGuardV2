from collections.abc import Generator
from urllib.parse import urlsplit

from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from core.config import settings


class Base(DeclarativeBase):
    pass


def build_database_url() -> str | URL:
    """Build the SQLAlchemy URL for the configured database.

    Turso authentication is excluded from the URL because the
    sqlalchemy-libsql dialect expects its JWT through connect_args.
    """
    if settings.turso_database_url:
        parsed = urlsplit(settings.turso_database_url)
        if parsed.scheme != "libsql" or not parsed.hostname:
            raise RuntimeError(
                "TURSO_DATABASE_URL must be a valid libsql:// database URL."
            )
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise RuntimeError(
                "TURSO_DATABASE_URL must contain only the libsql:// host; "
                "provide authentication separately with TURSO_AUTH_TOKEN."
            )

        return URL.create(
            "sqlite+libsql",
            host=parsed.hostname,
            port=parsed.port,
            query={"secure": "true"},
        )

    if settings.database_url:
        return settings.database_url

    return URL.create(
        "mysql+pymysql",
        username=settings.db_user,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        query={"charset": "utf8mb4"},
    )


database_url = build_database_url()
connect_args = (
    {"auth_token": settings.turso_auth_token}
    if settings.turso_database_url
    else {}
)

engine = create_engine(
    database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
