from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.dependencies import require_guard
from db.session import get_db
from services.overstay_service import check_overstay_status, create_missing_overstay_alerts, find_overstaying_visitors

router = APIRouter(tags=["Alerts & Incidents"])


@router.get("/visitors/check-overstay")
def check_overstay(db: Session = Depends(get_db), _=Depends(require_guard)):
    try:
        return check_overstay_status(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not check visitor overstays") from exc


@router.post("/alerts/check-auto")
def auto_check_alerts(db: Session = Depends(get_db), _=Depends(require_guard)):
    try:
        flagged = create_missing_overstay_alerts(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not create automatic alerts") from exc
    return {
        "auto_alerts_created": len(flagged),
        "details": [f"Visitor overstay: {name}" for name in flagged],
    }
