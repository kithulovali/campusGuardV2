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

# ── Who is on campus ──────────────────────────────────────────────────────────
@router.get("/campus/live")
def campus_live(db: Session = Depends(get_db), _=Depends(require_guard)):
    """Return each user whose latest entry today is an entry onto campus."""
    today = datetime.utcnow().date()
    entries = (
        db.query(Entry)
        .options(joinedload(Entry.user))
        .filter(func.date(Entry.scanned_at) == today)
        .order_by(Entry.scanned_at, Entry.id)
        .all()
    )

    latest_by_user = {}
    for entry in entries:
        latest_by_user[entry.user_id] = entry

    return [
        {
            "id": entry.user.id,
            "full_name": entry.user.full_name,
            "role": entry.user.role,
            "reg_number": entry.user.reg_number,
            "entry_time": entry.scanned_at.strftime("%I:%M %p") if entry.scanned_at else "",
        }
        for entry in latest_by_user.values()
        if entry.direction == "in" and entry.user is not None
    ]
