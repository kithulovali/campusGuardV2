from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.dependencies import require_guard
from db.session import get_db
from services.dashboard_service import get_dashboard_stats

router = APIRouter(tags=["Campus Monitoring"])


@router.get("/dashboard/stats")
def stats(db: Session = Depends(get_db), _=Depends(require_guard)):
    return get_dashboard_stats(db)
