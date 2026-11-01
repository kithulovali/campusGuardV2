from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import Alert, Visitor


def find_overstaying_visitors(db: Session) -> list[Visitor]:
    now = datetime.utcnow()
    return db.query(Visitor).filter(
        Visitor.checked_out.is_(False),
        Visitor.expected_exit.is_not(None),
        Visitor.expected_exit < now,
    ).all()


def create_missing_overstay_alerts(db: Session) -> list[str]:
    today = date.today()
    overstaying = find_overstaying_visitors(db)
    created = []
    for visitor in overstaying:
        existing = db.query(Alert.id).filter(
            Alert.type == "overstay",
            Alert.description.like(f"%{visitor.name}%"),
            func.date(Alert.timestamp) == today,
        ).first()
        if existing is None:
            db.add(Alert(
                type="overstay",
                description=(
                    f"Visitor '{visitor.name}' has overstayed. "
                    f"Expected exit: {visitor.expected_exit.strftime('%I:%M %p')}. "
                    f"Host: {visitor.host or 'N/A'}."
                ),
            ))
            created.append(visitor.name)
    if created:
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
    return created


def check_overstay_status(db: Session) -> dict:
    overstaying = find_overstaying_visitors(db)
    created = create_missing_overstay_alerts(db)
    return {"overstaying": len(overstaying), "new_alerts": created}
