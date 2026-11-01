from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.security import hash_password
from models import User
from repositories.user_repository import UserRepository
from utils.qr import QR_DIR, generate_qr_hash, generate_qr_image


PHOTO_DIR = Path(__file__).resolve().parents[1] / "static" / "photos"


class UserService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)

    def create(self, payload) -> User:
        if self.users.get_by_email(str(payload.email)):
            raise HTTPException(409, "Email already registered")
        if self.users.get_by_registration_number(payload.reg_number):
            raise HTTPException(409, "Registration number already exists")

        qr_code = generate_qr_hash(payload.reg_number)
        user = User(
            full_name=payload.full_name,
            email=str(payload.email),
            reg_number=payload.reg_number,
            role=payload.role,
            password=hash_password(payload.password),
            qr_code=qr_code,
        )
        qr_path = None
        try:
            self.users.add(user)
            qr_path = generate_qr_image(qr_code, user.full_name)
            self.session.commit()
            self.session.refresh(user)
        except IntegrityError:
            self.session.rollback()
            if qr_path:
                Path(qr_path).unlink(missing_ok=True)
            raise HTTPException(409, "Email or registration number already exists")
        except Exception:
            self.session.rollback()
            if qr_path:
                Path(qr_path).unlink(missing_ok=True)
            raise HTTPException(500, "Could not create user and QR code")
        return user

    def get(self, user_id: int) -> User:
        user = self.users.get_by_id(user_id)
        if not user:
            raise HTTPException(404, "User not found")
        return user

    def update(self, user_id: int, changes: dict) -> User:
        user = self.get(user_id)
        for field, value in changes.items():
            setattr(user, field, value)
        try:
            self.session.commit()
            self.session.refresh(user)
        except IntegrityError:
            self.session.rollback()
            raise HTTPException(409, "Email already registered")
        return user

    def delete(self, user_id: int) -> None:
        user = self.get(user_id)
        qr_path = QR_DIR / f"{user.qr_code}.png" if user.qr_code else None
        photo_path = PHOTO_DIR / Path(user.photo).name if user.photo else None
        self.session.delete(user)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise HTTPException(409, "User has related records and cannot be deleted")
        if qr_path:
            qr_path.unlink(missing_ok=True)
        if photo_path:
            photo_path.unlink(missing_ok=True)
            for variant in ("thumb", "small"):
                (PHOTO_DIR / f"{photo_path.stem}_{variant}.jpg").unlink(missing_ok=True)
