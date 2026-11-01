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

# ── Weekly traffic for dashboard chart ───────────────────────────────────────
@router.get("/reports/weekly")
def weekly_traffic(db: Session = Depends(get_db), _=Depends(get_current_user)):
    from datetime import date
    today = date.today()
    # Last 7 days
    days = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        count = db.query(func.count(Entry.id)).filter(
            func.date(Entry.scanned_at) == d,
            Entry.direction == 'in'
        ).scalar()
        days.append({ "day": d.strftime("%a"), "date": d.isoformat(), "entries": count })
    return days
