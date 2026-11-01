from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from models import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, user_id: int) -> User | None:
        return self.session.scalar(select(User).where(User.id == user_id))

    def get_by_login(self, identifier: str) -> User | None:
        return self.session.scalar(
            select(User).where(
                or_(func.lower(User.email) == identifier.lower(), User.reg_number == identifier)
            )
        )

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email))

    def get_by_registration_number(self, reg_number: str) -> User | None:
        return self.session.scalar(
            select(User).where(User.reg_number == reg_number)
        )

    def list(self, *, offset: int = 0, limit: int = 50, role: str | None = None,
             status: str | None = None) -> list[User]:
        statement = select(User).order_by(User.id).offset(offset).limit(limit)
        if role:
            statement = statement.where(User.role == role)
        if status:
            statement = statement.where(User.status == status)
        return list(self.session.scalars(statement).all())

    def search(self, term: str, *, limit: int = 10) -> list[User]:
        pattern = f"%{term.strip()}%"
        statement = (
            select(User)
            .where(or_(User.full_name.ilike(pattern), User.reg_number.ilike(pattern)))
            .order_by(User.full_name)
            .limit(limit)
        )
        return list(self.session.scalars(statement).all())

    def add(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        return user
