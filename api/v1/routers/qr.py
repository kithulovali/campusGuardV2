from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.dependencies import get_current_user, require_admin
from db.session import get_db
from models import User
from services.qr_service import flag_expired_qrs, get_qr_expiry_report, regenerate_lost_qr, renew_user_qr

router = APIRouter(tags=["QR Code Management"])


@router.post("/users/{user_id}/report-qr-lost")
def report_qr_lost(user_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    if current.role != "admin" and current.id != user_id:
        raise HTTPException(status_code=403, detail="Can only report your own QR")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        new_hash = regenerate_lost_qr(db, user, current)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not regenerate QR code") from exc
    return {"message": "QR invalidated and regenerated", "new_qr": new_hash}


@router.post("/users/{user_id}/renew-qr")
def renew_qr(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        new_hash, expiry = renew_user_qr(db, user, admin)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not renew QR code") from exc
    return {"message": "QR renewed", "new_qr": new_hash, "expires": expiry.isoformat()}


@router.get("/users/expired-qr")
def list_expired_qr(db: Session = Depends(get_db), _=Depends(require_admin)):
    return get_qr_expiry_report(db)


@router.post("/qr/check-expiry")
def auto_expire_qr(db: Session = Depends(get_db), _=Depends(require_admin)):
    try:
        flagged = flag_expired_qrs(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not process expired QR codes") from exc
    return {"flagged": len(flagged), "names": flagged}
