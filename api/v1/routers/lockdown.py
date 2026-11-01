from datetime import datetime, timedelta, date
from io import BytesIO
from pathlib import Path
from typing import Optional
import hashlib
import io
import json
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
from models import Alert, AuditLog, Entry, Gate, SystemState, User, Visitor
from utils.qr import QR_DIR, generate_qr_hash, generate_qr_image


router = APIRouter()


# ── Audit helper ──────────────────────────────────────────────────────────────
def audit(db, actor, action, target_type=None, target_id=None, detail=None):
    log = AuditLog(
        actor_id=actor.id if actor else None,
        actor_name=actor.full_name if actor else "System",
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=json.dumps(detail) if detail else None,
    )
    db.add(log)

# ══════════════════════════════════════════════════════════════════════════════
# FEATURE 2 — EMERGENCY LOCKDOWN
# ══════════════════════════════════════════════════════════════════════════════
class LockdownRequest(BaseModel):
    active: bool
    reason: Optional[str] = "Emergency lockdown"

@router.get("/lockdown/status")
def lockdown_status(db: Session = Depends(get_db), _=Depends(get_current_user)):
    state = db.query(SystemState).filter(SystemState.key == "lockdown").first()
    return {"active": state.value == "true" if state else False,
            "reason": state.detail if state else None,
            "since": state.updated_at.isoformat() if state else None}

@router.post("/lockdown")
def set_lockdown(body: LockdownRequest, db: Session = Depends(get_db), admin=Depends(require_admin)):
    state = db.query(SystemState).filter(SystemState.key == "lockdown").first()
    if not state:
        state = SystemState(key="lockdown", value="false")
        db.add(state)

    state.value      = "true" if body.active else "false"
    state.detail     = body.reason
    state.updated_by = admin.id
    state.updated_at = datetime.utcnow()

    # Global lockdown is independent of each gate's manual lock state.

    # Create alert
    alert = Alert(
        type="lockdown",
        description=f"{'🔴 EMERGENCY LOCKDOWN ACTIVATED' if body.active else '🟢 Lockdown lifted'} by {admin.full_name}. Reason: {body.reason}"
    )
    db.add(alert)
    audit(db, admin, "lockdown.activate" if body.active else "lockdown.lift", detail={"reason": body.reason})
    db.commit()
    return {"active": body.active, "message": "Lockdown activated" if body.active else "Lockdown lifted"}

# ══════════════════════════════════════════════════════════════════════════════
