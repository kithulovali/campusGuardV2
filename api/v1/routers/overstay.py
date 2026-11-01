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

# ── Overstay checker ──────────────────────────────────────────────────────────
@router.get("/visitors/check-overstay")
def check_overstay(db: Session = Depends(get_db), _=Depends(require_guard)):
    """Check for visitors who have exceeded their expected exit time."""
    now = datetime.utcnow()
    overstaying = db.query(Visitor).filter(
        Visitor.checked_out == False,
        Visitor.expected_exit != None,
        Visitor.expected_exit < now
    ).all()

    flagged = []
    for v in overstaying:
        # Create alert if not already created for this visitor today
        existing = db.query(Alert).filter(
            Alert.description.like(f"%{v.name}%"),
            Alert.type == "overstay"
        ).first()
        if not existing:
            alert = Alert(
                type="overstay",
                description=f"Visitor {v.name} (host: {v.host}) has overstayed. Expected exit: {v.expected_exit.strftime('%I:%M %p')}. Still on campus."
            )
            db.add(alert)
            flagged.append(v.name)
    if flagged:
        db.commit()

    return {"overstaying": len(overstaying), "new_alerts": flagged}


@router.post("/alerts/check-auto")
def auto_check_alerts(db: Session = Depends(get_db), _=Depends(require_guard)):
    """
    Call this periodically from the frontend (every 2 min) to auto-generate
    visitor overstay alerts without needing a gate scan to trigger them.
    """
    from datetime import date
    now = datetime.utcnow()
    today = date.today()
    flagged = []

    # Visitor overstays
    overstaying = db.query(Visitor).filter(
        Visitor.checked_out == False,
        Visitor.expected_exit != None,
        Visitor.expected_exit < now
    ).all()
    for v in overstaying:
        existing = db.query(Alert).filter(
            Alert.type == "overstay",
            Alert.description.like(f"%{v.name}%"),
            func.date(Alert.timestamp) == today
        ).first()
        if not existing:
            db.add(Alert(
                type="overstay",
                description=f"Visitor '{v.name}' has overstayed. "
                            f"Expected exit: {v.expected_exit.strftime('%I:%M %p')}. "
                            f"Host: {v.host or 'N/A'}."
            ))
            flagged.append(f"Visitor overstay: {v.name}")

    if flagged:
        db.commit()

    return {"auto_alerts_created": len(flagged), "details": flagged}
