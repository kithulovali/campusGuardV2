from datetime import datetime, timedelta, date
from io import BytesIO
from pathlib import Path
from typing import Optional
import hashlib
import io
import os
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image as PILImage, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from core.dependencies import get_current_user, require_admin, require_guard
from core.security import hash_password
from db.session import get_db
from models import Alert, Entry, Gate, SystemState, User, Visitor
from utils.qr import QR_DIR, generate_qr_hash, generate_qr_image
from services.audit_service import record_audit


router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE 7 — VISITOR PRE-REGISTRATION
# ══════════════════════════════════════════════════════════════════════════════
class PreRegRequest(BaseModel):
    visitor_name: str = Field(min_length=2, max_length=120)
    visitor_email: Optional[str] = None
    visitor_phone: Optional[str] = Field(default=None, max_length=30)
    reason: str = Field(min_length=2, max_length=500)
    expected_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    expected_time: str = Field(pattern=r"^\d{2}:\d{2}$")


@router.post("/visitors/pre-register")
def pre_register_visitor(
    body: PreRegRequest,
    db: Session = Depends(get_db),
    host: User = Depends(get_current_user),
):
    token = secrets.token_urlsafe(32)
    try:
        expected_dt = datetime.strptime(
            f"{body.expected_date} {body.expected_time}",
            "%Y-%m-%d %H:%M",
        )
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="expected_date must be YYYY-MM-DD and expected_time must be HH:MM",
        )

    visitor = Visitor(
        name=body.visitor_name,
        email=body.visitor_email,
        phone=body.visitor_phone,
        reason=body.reason,
        host=host.full_name,
        host_user_id=host.id,
        temp_pass=secrets.token_hex(8),
        prereg_token=token,
        pre_registered=True,
        expected_exit=expected_dt,
        checked_out=False,
    )
    try:
        db.add(visitor)
        db.flush()
        audit(
            db,
            host,
            "visitor.pre_register",
            "visitor",
            visitor.id,
            {"name": body.visitor_name, "date": body.expected_date},
        )
        db.commit()
        db.refresh(visitor)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not create visitor pre-registration")

    return {
        "visitor_id": visitor.id,
        "token": token,
        "checkin_link": f"/visitor-checkin/{token}",
        "message": f"Pre-registration created for {body.visitor_name}",
    }


@router.get("/visitors/checkin/{token}")
def visitor_checkin(token: str, db: Session = Depends(get_db)):
    visitor = db.query(Visitor).filter(Visitor.prereg_token == token).first()
    if not visitor: raise HTTPException(404, "Invalid or expired token")
    if visitor.checked_out: raise HTTPException(400, "Already checked out")
    return {
        "name": visitor.name, "reason": visitor.reason,
        "host": visitor.host, "expected_exit": visitor.expected_exit.isoformat() if visitor.expected_exit else None,
        "pre_registered": True
    }

@router.post("/visitors/checkin/{token}/confirm")
def confirm_visitor_checkin(token: str, db: Session = Depends(get_db), guard=Depends(require_guard)):
    visitor = db.query(Visitor).filter(Visitor.prereg_token == token).first()
    if not visitor: raise HTTPException(404, "Invalid token")
    visitor.time_in = datetime.utcnow()
    db.commit()
    return {"message": "Visitor checked in", "visitor_id": visitor.id}

# ══════════════════════════════════════════════════════════════════════════════
