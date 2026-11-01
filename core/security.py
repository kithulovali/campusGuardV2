from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from core.config import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _secret_key() -> str:
    """Return the configured signing key as a plain string."""
    return settings.secret_key


def create_access_token(data: dict) -> str:
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {**data, "exp": expires, "type": "access"}
    return jwt.encode(payload, _secret_key(), algorithm=settings.algorithm)


def create_refresh_token(data: dict) -> str:
    expires = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload = {**data, "exp": expires, "type": "refresh"}
    return jwt.encode(payload, _secret_key(), algorithm=settings.algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        _secret_key(),
        algorithms=[settings.algorithm],
    )
