from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from core.dependencies import require_guard
from db.session import get_db
from models.alert import Alert
from models.user import User
from services.alert_service import create_alert, resolve_alert

router = APIRouter(tags=["Alerts & Incidents"])


class AlertCreate(BaseModel):
    type: Literal["invalid_qr", "blacklisted", "overstay", "repeated_fail", "lockdown", "qr_expired", "qr_compromised", "manual"]
    gate_id: int | None = Field(default=None, gt=0)
    description: str = Field(min_length=3, max_length=2000)


@router.get("/alerts")
def list_alerts(db: Session = Depends(get_db), _=Depends(require_guard)):
    alerts = db.query(Alert).order_by(desc(Alert.timestamp)).limit(100).all()
    return [
        {
            "id": item.id,
            "type": item.type,
            "description": item.description,
            "resolved": item.resolved,
            "gate": f"Gate {item.gate_id}" if item.gate_id else "Unknown Gate",
            "timestamp": item.timestamp.strftime("%I:%M %p") if item.timestamp else "",
        }
        for item in alerts
    ]


@router.post("/alerts")
def create_alert_endpoint(body: AlertCreate, db: Session = Depends(get_db), _: User = Depends(require_guard)):
    try:
        item = create_alert(db, alert_type=body.type, description=body.description, gate_id=body.gate_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not create alert") from exc
    return {
        "id": item.id,
        "type": item.type,
        "description": item.description,
        "resolved": item.resolved,
        "gate": f"Gate {item.gate_id}" if item.gate_id else "Unknown Gate",
        "timestamp": item.timestamp.strftime("%I:%M %p") if item.timestamp else "",
    }


@router.patch("/alerts/{alert_id}/resolve")
def resolve_alert_endpoint(alert_id: int, db: Session = Depends(get_db), _=Depends(require_guard)):
    try:
        item = resolve_alert(db, alert_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not resolve alert") from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Resolved"}
