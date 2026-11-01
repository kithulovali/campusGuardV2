from sqlalchemy.orm import Session

from models.alert import Alert
from models.gate import Gate


def create_alert(db: Session, *, alert_type: str, description: str, gate_id: int | None = None, user_id: int | None = None) -> Alert:
    if gate_id is not None and db.query(Gate.id).filter(Gate.id == gate_id).first() is None:
        raise LookupError("Gate not found")
    alert = Alert(type=alert_type, description=description, gate_id=gate_id, user_id=user_id)
    try:
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert
    except Exception:
        db.rollback()
        raise


def resolve_alert(db: Session, alert_id: int) -> Alert | None:
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if alert is None:
        return None
    alert.resolved = True
    try:
        db.commit()
        db.refresh(alert)
        return alert
    except Exception:
        db.rollback()
        raise
