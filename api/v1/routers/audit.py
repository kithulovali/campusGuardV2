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
# FEATURE 9 — AUDIT LOG
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/audit-logs")
def get_audit_logs(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db), _=Depends(require_admin)):
    logs = db.query(AuditLog).order_by(desc(AuditLog.timestamp)).limit(limit).all()
    return [
        {"id": l.id, "actor": l.actor_name, "action": l.action,
         "target_type": l.target_type, "target_id": l.target_id,
         "detail": l.detail, "timestamp": l.timestamp.strftime("%b %d, %Y – %I:%M %p")}
        for l in logs
    ]

# ══════════════════════════════════════════════════════════════════════════════
