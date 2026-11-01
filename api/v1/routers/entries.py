from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.dependencies import require_guard
from db.session import get_db
from services.dashboard_service import get_entry_history

router = APIRouter(tags=["Gates & Access Control"])


@router.get("/entries")
def get_entries(user_id: int | None = Query(default=None, gt=0), limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db), _=Depends(require_guard)):
    return get_entry_history(db, user_id, limit)
