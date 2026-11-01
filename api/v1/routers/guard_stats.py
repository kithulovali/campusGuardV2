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
# FEATURE 5 — GUARD STATISTICS
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/stats/guards")
def guard_stats(db: Session = Depends(get_db), _=Depends(require_admin)):
    today = date.today()
    guards = db.query(User).filter(User.role == "guard").all()
    result = []
    for g in guards:
        approved_today = db.query(func.count(Entry.id)).filter(
            Entry.approved_by == g.id,
            func.date(Entry.scanned_at) == today
        ).scalar()
        approved_total = db.query(func.count(Entry.id)).filter(
            Entry.approved_by == g.id
        ).scalar()
        alerts_raised = db.query(func.count(Alert.id)).filter(
            func.date(Alert.timestamp) == today
        ).scalar()
        result.append({
            "id": g.id, "name": g.full_name, "status": g.status,
            "approved_today": approved_today,
            "approved_total": approved_total,
            "alerts_today": alerts_raised,
        })
    return result

# ══════════════════════════════════════════════════════════════════════════════
