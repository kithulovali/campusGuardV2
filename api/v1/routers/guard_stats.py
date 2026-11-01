from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.dependencies import require_admin
from db.session import get_db
from services.dashboard_service import get_guard_statistics

router = APIRouter(tags=["Administration"])


@router.get("/stats/guards")
def guard_stats(db: Session = Depends(get_db), _=Depends(require_admin)):
    return get_guard_statistics(db)
