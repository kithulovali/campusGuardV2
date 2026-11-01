from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.dependencies import get_current_user, require_admin
from db.session import get_db
from models.user import User
from services.lockdown_service import get_lockdown_state, update_lockdown

router = APIRouter(tags=["Administration"])


class LockdownRequest(BaseModel):
    active: bool
    reason: Optional[str] = "Emergency lockdown"


@router.get("/lockdown/status")
def lockdown_status(db: Session = Depends(get_db), _=Depends(get_current_user)):
    state = get_lockdown_state(db)
    return {
        "active": state.value == "true" if state else False,
        "reason": state.detail if state else None,
        "since": state.updated_at.isoformat() if state else None,
    }


@router.post("/lockdown")
def set_lockdown(body: LockdownRequest, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    update_lockdown(db, admin, active=body.active, reason=body.reason)
    return {"active": body.active, "message": "Lockdown activated" if body.active else "Lockdown lifted"}
