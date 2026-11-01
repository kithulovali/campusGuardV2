from datetime import date, datetime
from typing import Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from models import Alert, Entry, Gate, SystemState, User, Visitor


def is_locked_down(db: Session) -> bool:
    state = db.query(SystemState).filter(SystemState.key == "lockdown").first()
    return bool(state and state.value == "true")


def is_qr_expired(user: User) -> bool:
    return bool(user.qr_expires and user.qr_expires < datetime.utcnow())


def get_last_direction(db: Session, user_id: int) -> Optional[str]:
    today = date.today()
    entry = db.query(Entry).filter(
        Entry.user_id == user_id,
        func.date(Entry.scanned_at) == today,
    ).order_by(desc(Entry.scanned_at), desc(Entry.id)).first()
    return entry.direction if entry else None


def find_active_gate(db: Session, gate_id: int) -> Gate | None:
    return db.query(Gate).filter(Gate.id == gate_id, Gate.active.is_(True)).first()


def check_visitor_overstays(db: Session) -> None:
    now = datetime.utcnow()
    today = date.today()
    visitors = db.query(Visitor).filter(
        Visitor.checked_out.is_(False),
        Visitor.expected_exit.is_not(None),
        Visitor.expected_exit < now,
    ).all()
    for visitor in visitors:
        existing = db.query(Alert.id).filter(
            Alert.type == "overstay",
            Alert.description.like(f"%Visitor '{visitor.name}'%"),
            func.date(Alert.timestamp) == today,
        ).first()
        if existing is None:
            db.add(Alert(
                type="overstay",
                description=(
                    f"Visitor '{visitor.name}' has overstayed. "
                    f"Expected exit: {visitor.expected_exit:%I:%M %p}. "
                    f"Host: {visitor.host or 'N/A'}."
                ),
            ))


def log_denied_scan(db: Session, *, gate_id: int, message: str, user_id: int | None = None, alert_type: str = "invalid_qr") -> None:
    db.add(Alert(gate_id=gate_id, user_id=user_id, type=alert_type, description=message))
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
