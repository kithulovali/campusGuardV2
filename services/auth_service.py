from datetime import datetime, timedelta
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.config import settings
from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from models import RefreshToken, User
from repositories.refresh_token_repository import RefreshTokenRepository
from repositories.user_repository import UserRepository
from utils.qr import generate_qr_hash, generate_qr_image


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)

    def register(self, *, full_name: str, email: str, reg_number: str, password: str) -> dict:
        normalized_email = email.strip().lower()
        normalized_reg_number = reg_number.strip()
        normalized_name = full_name.strip()
        if not normalized_name or not normalized_reg_number:
            raise HTTPException(status_code=422, detail="Name and registration number are required")
        if self.users.get_by_email(normalized_email):
            raise HTTPException(status_code=409, detail="Email already registered")
        if self.users.get_by_registration_number(normalized_reg_number):
            raise HTTPException(status_code=409, detail="Registration number already registered")

        qr_code = generate_qr_hash(normalized_reg_number)
        qr_path: str | None = None
        try:
            user = User(
                full_name=normalized_name,
                email=normalized_email,
                reg_number=normalized_reg_number,
                role="student",
                password=hash_password(password),
                qr_code=qr_code,
                qr_expires=datetime.utcnow() + timedelta(days=180),
                status="active",
            )
            self.session.add(user)
            self.session.flush()
            qr_path = generate_qr_image(qr_code, user.full_name)

            access = create_access_token({"sub": str(user.id), "role": user.role})
            refresh = create_refresh_token({"sub": str(user.id)})
            self.refresh_tokens.add(RefreshToken(
                user_id=user.id,
                token=refresh,
                expires_at=datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days),
            ))
            self.session.commit()
            self.session.refresh(user)
            return {"access_token": access, "refresh_token": refresh, "user": user}
        except IntegrityError as exc:
            self.session.rollback()
            if qr_path:
                Path(qr_path).unlink(missing_ok=True)
            raise HTTPException(status_code=409, detail="Email or registration number already registered") from exc
        except Exception:
            self.session.rollback()
            if qr_path:
                Path(qr_path).unlink(missing_ok=True)
            raise

    def login(self, identifier: str, password: str) -> dict:
        user = self.users.get_by_login(identifier.strip())
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
