from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.models import User
from app.repositories.user_repository import UserRepository
from app.utils.qr import generate_qr_hash, generate_qr_image


class UserService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)

    def create(self, payload) -> User:
        if self.users.get_by_email(str(payload.email)):
            raise HTTPException(409, "Email already registered")
        if self.users.get_by_registration_number(payload.reg_number):
            raise HTTPException(409, "Registration number already exists")
        user = User(
            full_name=payload.full_name,
            email=str(payload.email),
            reg_number=payload.reg_number,
            role=payload.role,
            password=hash_password(payload.password),
            qr_code=generate_qr_hash(payload.reg_number),
        )
        try:
            self.users.add(user)
            self.session.commit()
            self.session.refresh(user)
        except IntegrityError:
            self.session.rollback()
            raise HTTPException(409, "Email or registration number already exists")
        generate_qr_image(user.qr_code, user.full_name)
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
        self.session.delete(user)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise HTTPException(409, "User has related records and cannot be deleted")
