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

# ── Visitors ──────────────────────────────────────────────────────────────────
@router.get("/visitors")
def list_visitors(db: Session = Depends(get_db), _=Depends(require_guard)):
    visitors = db.query(Visitor).order_by(desc(Visitor.time_in)).limit(100).all()
    return [
        {
            "id": v.id, "name": v.name, "id_number": v.id_number,
            "reason": v.reason, "host": v.host,
            "time_in": v.time_in.strftime("%I:%M %p") if v.time_in else "",
            "expected_exit": v.expected_exit.strftime("%I:%M %p") if v.expected_exit else "",
            "checked_out": v.checked_out,
        }
        for v in visitors
    ]

@router.post("/visitors")
def create_visitor(
    body: VisitorCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_guard),
):
    expected = None
    if body.expected_exit:
        try:
            expected_time = datetime.strptime(body.expected_exit, "%H:%M").time()
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="expected_exit must use HH:MM format",
            )
        expected = datetime.combine(datetime.utcnow().date(), expected_time)

    visitor = Visitor(
        name=body.name,
        id_number=body.id_number,
        phone=body.phone,
        reason=body.reason,
        host=body.host,
        temp_pass=secrets.token_hex(8),
        expected_exit=expected,
    )
    try:
        db.add(visitor)
        db.commit()
        db.refresh(visitor)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not register visitor")

    return {
        "id": visitor.id,
        "name": visitor.name,
        "id_number": visitor.id_number,
        "reason": visitor.reason,
        "host": visitor.host,
        "time_in": visitor.time_in.strftime("%I:%M %p") if visitor.time_in else "",
        "expected_exit": visitor.expected_exit.strftime("%I:%M %p") if visitor.expected_exit else "",
        "checked_out": visitor.checked_out,
    }


@router.patch("/visitors/{visitor_id}/checkout")
def checkout_visitor(
    visitor_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_guard),
):
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="Visitor not found")
    if visitor.checked_out:
        raise HTTPException(status_code=409, detail="Visitor is already checked out")

    visitor.checked_out = True
    visitor.checkout_time = datetime.utcnow()
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not check out visitor")
    return {"message": "Checked out"}
