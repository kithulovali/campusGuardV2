from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_active(self, token: str) -> RefreshToken | None:
        statement = select(RefreshToken).where(
            RefreshToken.token == token,
            RefreshToken.revoked.is_(False),
            RefreshToken.expires_at > datetime.utcnow(),
        )
        return self.session.scalar(statement)

    def add(self, token: RefreshToken) -> RefreshToken:
        self.session.add(token)
        self.session.flush()
        return token
