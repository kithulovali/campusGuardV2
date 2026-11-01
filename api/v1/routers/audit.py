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
