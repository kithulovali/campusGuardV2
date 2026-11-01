from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.dependencies import get_current_user, require_guard
from db.session import get_db
from models.user import User
from services.visitor_service import confirm_visitor_checkin, get_preregistered_visitor, pre_register_visitor

router = APIRouter(tags=["Visitors"])


class PreRegRequest(BaseModel):
    visitor_name: str = Field(min_length=2, max_length=120)
    visitor_email: Optional[str] = None
    visitor_phone: Optional[str] = Field(default=None, max_length=20)
    reason: str = Field(min_length=2, max_length=500)
    expected_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    expected_time: str = Field(pattern=r"^\d{2}:\d{2}$")


@router.post("/visitors/pre-register")
def pre_register(body: PreRegRequest, db: Session = Depends(get_db), host: User = Depends(get_current_user)):
    try:
        expected_exit = datetime.strptime(f"{body.expected_date} {body.expected_time}", "%Y-%m-%d %H:%M")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="expected_date must be YYYY-MM-DD and expected_time must be HH:MM") from exc
    try:
        visitor, token = pre_register_visitor(
            db,
            name=body.visitor_name,
            email=body.visitor_email,
            phone=body.visitor_phone,
            reason=body.reason,
            expected_exit=expected_exit,
            host=host,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not create visitor pre-registration") from exc
    return {
        "visitor_id": visitor.id,
        "token": token,
        "checkin_link": f"/visitor-checkin/{token}",
        "message": f"Pre-registration created for {body.visitor_name}",
    }


@router.get("/visitors/checkin/{token}")
def visitor_checkin(token: str, db: Session = Depends(get_db)):
    visitor = get_preregistered_visitor(db, token)
    if visitor is None:
        raise HTTPException(status_code=404, detail="Invalid or expired token")
    if visitor.checked_out:
        raise HTTPException(status_code=400, detail="Already checked out")
    return {
        "name": visitor.name,
        "reason": visitor.reason,
        "host": visitor.host,
        "expected_exit": visitor.expected_exit.isoformat() if visitor.expected_exit else None,
        "pre_registered": True,
    }


@router.post("/visitors/checkin/{token}/confirm")
def confirm_checkin(token: str, db: Session = Depends(get_db), guard: User = Depends(require_guard)):
    visitor = get_preregistered_visitor(db, token)
    if visitor is None:
        raise HTTPException(status_code=404, detail="Invalid token")
    try:
        confirm_visitor_checkin(db, visitor)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not confirm visitor check-in") from exc
    return {"message": "Visitor checked in", "visitor_id": visitor.id}
