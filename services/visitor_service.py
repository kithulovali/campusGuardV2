from datetime import datetime
import secrets

from sqlalchemy.orm import Session

from models.visitor import Visitor
from models.user import User
from services.audit_service import record_audit


def list_visitors(db: Session, limit: int = 100) -> list[Visitor]:
    return db.query(Visitor).order_by(Visitor.time_in.desc()).limit(limit).all()


def register_visitor(db: Session, *, name: str, id_number: str | None, phone: str | None, reason: str, host: str, expected_exit: datetime | None) -> Visitor:
    visitor = Visitor(
        name=name,
        id_number=id_number,
        phone=phone,
        reason=reason,
        host=host,
        temp_pass=secrets.token_hex(8),
        expected_exit=expected_exit,
    )
    try:
        db.add(visitor)
        db.commit()
        db.refresh(visitor)
        return visitor
    except Exception:
        db.rollback()
        raise


def pre_register_visitor(db: Session, *, name: str, email: str | None, phone: str | None, reason: str, expected_exit: datetime, host: User) -> tuple[Visitor, str]:
    token = secrets.token_urlsafe(32)
    visitor = Visitor(
        name=name,
        email=email,
        phone=phone,
        reason=reason,
        host=host.full_name,
        host_user_id=host.id,
        temp_pass=secrets.token_hex(8),
        prereg_token=token,
        pre_registered=True,
        expected_exit=expected_exit,
        checked_out=False,
    )
    try:
        db.add(visitor)
        db.flush()
        record_audit(db, host, "visitor.pre_register", "visitor", visitor.id, {"name": name, "expected_exit": expected_exit.isoformat()})
        db.commit()
        db.refresh(visitor)
        return visitor, token
    except Exception:
        db.rollback()
        raise


def get_preregistered_visitor(db: Session, token: str) -> Visitor | None:
    return db.query(Visitor).filter(Visitor.prereg_token == token).first()


def confirm_visitor_checkin(db: Session, visitor: Visitor) -> None:
    visitor.time_in = datetime.utcnow()
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def checkout_visitor(db: Session, visitor: Visitor) -> None:
    if visitor.checked_out:
        raise ValueError("Visitor is already checked out")
    visitor.checked_out = True
    visitor.checkout_time = datetime.utcnow()
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
