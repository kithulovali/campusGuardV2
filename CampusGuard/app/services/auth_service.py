from datetime import datetime, timedelta
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, decode_token, verify_password
from app.models.models import RefreshToken
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)

    def login(self, username: str, password: str) -> dict:
        user = self.users.get_by_login(username.strip())
        if not user or not verify_password(password, user.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if user.status != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

        access = create_access_token({"sub": str(user.id), "role": user.role})
        refresh = create_refresh_token({"sub": str(user.id)})
        self.refresh_tokens.add(RefreshToken(
            user_id=user.id, token=refresh,
            expires_at=datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days),
        ))
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return {"access_token": access, "refresh_token": refresh, "user": user}

    def refresh(self, raw_token: str) -> dict:
        try:
            payload = decode_token(raw_token)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        if payload.get("type") != "refresh" or not payload.get("sub"):
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        record = self.refresh_tokens.get_active(raw_token)
        if not record or str(record.user_id) != str(payload["sub"]):
            raise HTTPException(status_code=401, detail="Refresh token revoked or expired")
        user = self.users.get_by_id(record.user_id)
        if not user or user.status != "active":
            raise HTTPException(status_code=401, detail="Account is not active")

        record.revoked = True
        access = create_access_token({"sub": str(user.id), "role": user.role})
        refresh = create_refresh_token({"sub": str(user.id)})
        self.refresh_tokens.add(RefreshToken(
            user_id=user.id, token=refresh,
            expires_at=datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days),
        ))
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return {"access_token": access, "refresh_token": refresh}

    def logout(self, raw_token: str) -> None:
        record = self.refresh_tokens.get_active(raw_token)
        if record:
            record.revoked = True
            self.session.commit()
