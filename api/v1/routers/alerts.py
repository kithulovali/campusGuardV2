from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func
from datetime import datetime, timedelta
from typing import Literal
import io, secrets
from db.session import get_db
from models import Visitor, Alert, Entry, Gate, User
from schemas.schemas import VisitorCreate
from core.dependencies import get_current_user, require_guard, require_admin
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter()

# ── Alerts ────────────────────────────────────────────────────────────────────
class AlertCreate(BaseModel):
    type: Literal[
        "invalid_qr",
        "blacklisted",
        "overstay",
        "repeated_fail",
        "lockdown",
        "qr_expired",
        "qr_compromised",
        "manual",
    ]
    gate_id: int | None = Field(default=None, gt=0)
    description: str = Field(min_length=3, max_length=2000)


@router.get("/alerts")
def list_alerts(db: Session = Depends(get_db), _=Depends(require_guard)):
    alerts = db.query(Alert).order_by(desc(Alert.timestamp)).limit(100).all()
    return [
        {
            "id": a.id, "type": a.type, "description": a.description,
            "resolved": a.resolved,
            "gate": f"Gate {a.gate_id}" if a.gate_id else "Unknown Gate",
            "timestamp": a.timestamp.strftime("%I:%M %p") if a.timestamp else "",
        }
        for a in alerts
    ]

@router.post("/alerts")
def create_alert(
    body: AlertCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_guard),
):
    if body.gate_id is not None:
        gate = db.query(Gate).filter(Gate.id == body.gate_id).first()
        if not gate:
            raise HTTPException(status_code=404, detail="Gate not found")

    alert = Alert(
        type=body.type,
        gate_id=body.gate_id,
        description=body.description,
    )
    try:
        db.add(alert)
        db.commit()
        db.refresh(alert)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not create alert")

    return {
        "id": alert.id,
        "type": alert.type,
        "description": alert.description,
        "resolved": alert.resolved,
        "gate": f"Gate {alert.gate_id}" if alert.gate_id else "Unknown Gate",
        "timestamp": alert.timestamp.strftime("%I:%M %p") if alert.timestamp else "",
    }


@router.patch("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, db: Session = Depends(get_db), _=Depends(require_guard)):
    a = db.query(Alert).filter(Alert.id == alert_id).first()
    if not a: raise HTTPException(404, "Alert not found")
    a.resolved = True; db.commit()
    return {"message": "Resolved"}
