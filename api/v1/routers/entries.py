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

# ── Entries ───────────────────────────────────────────────────────────────────
@router.get("/entries")
def get_entries(user_id: int | None = Query(default=None, gt=0), limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db), _=Depends(require_guard)):
    q = db.query(Entry).order_by(desc(Entry.scanned_at))
    if user_id: q = q.filter(Entry.user_id == user_id)
    entries = q.limit(limit).all()
    return [
        {
            "id": e.id, "user_id": e.user_id, "gate_id": e.gate_id,
            "direction": e.direction,
            "user_name": e.user.full_name if e.user else "Unknown",
            "role": e.user.role if e.user else "—",
            "gate": f"Gate {e.gate_id}" if e.gate_id else "Main Gate",
            "time": e.scanned_at.strftime("%b %d, %Y – %I:%M %p") if e.scanned_at else "",
            "scanned_at": e.scanned_at.isoformat() if e.scanned_at else "",
        }
        for e in entries
    ]
