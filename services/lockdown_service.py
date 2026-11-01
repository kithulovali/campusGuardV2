from datetime import datetime

from sqlalchemy.orm import Session

from models.alert import Alert
from models.system_state import SystemState
from models.user import User
from services.audit_service import record_audit


def get_lockdown_state(db: Session) -> SystemState | None:
    return db.query(SystemState).filter(SystemState.key == "lockdown").first()


def update_lockdown(db: Session, admin: User, *, active: bool, reason: str | None) -> None:
    state = get_lockdown_state(db)
    if state is None:
        state = SystemState(key="lockdown", value="false")
        db.add(state)
    state.value = "true" if active else "false"
    state.detail = reason
    state.updated_by = admin.id
    state.updated_at = datetime.utcnow()
    db.add(Alert(type="lockdown", description=f"{'EMERGENCY LOCKDOWN ACTIVATED' if active else 'Lockdown lifted'} by {admin.full_name}. Reason: {reason}"))
    record_audit(db, admin, "lockdown.activate" if active else "lockdown.lift", detail={"reason": reason})
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
