from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.dependencies import get_current_user
from db.session import get_db
from services.dashboard_service import get_weekly_traffic

router = APIRouter(tags=["Reports & Analytics"])


@router.get("/reports/weekly")
def weekly_traffic(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return get_weekly_traffic(db)
