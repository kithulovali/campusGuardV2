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

# ── Dashboard stats ───────────────────────────────────────────────────────────
@router.get("/dashboard/stats")
def stats(db: Session = Depends(get_db), _=Depends(require_guard)):
    today = datetime.utcnow().date()
    total_users = db.query(func.count(User.id)).scalar() or 0
    latest_entries = (
        db.query(Entry.user_id, Entry.direction, Entry.scanned_at, Entry.id)
        .filter(func.date(Entry.scanned_at) == today)
        .order_by(Entry.scanned_at, Entry.id)
        .all()
    )
    latest_by_user = {}
    for user_id, direction, _, _ in latest_entries:
        latest_by_user[user_id] = direction

    alerts = (
        db.query(func.count(Alert.id))
        .filter(
            func.date(Alert.timestamp) == today,
            Alert.resolved.is_(False),
        )
        .scalar()
        or 0
    )
    visitors = (
        db.query(func.count(Visitor.id))
        .filter(func.date(Visitor.time_in) == today)
        .scalar()
        or 0
    )
    return {
        "total_users": total_users,
        "on_campus": sum(
            1 for direction in latest_by_user.values() if direction == "in"
        ),
        "alerts_today": alerts,
        "visitors_today": visitors,
    }
