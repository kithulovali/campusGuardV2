from datetime import datetime, timedelta
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.dependencies import get_current_user, require_admin
from db.session import get_db
from models import Alert, User
from services.audit_service import record_audit
from utils.qr import QR_DIR, generate_qr_hash, generate_qr_image


router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE 4 — QR COMPROMISE / LOST CARD
# ══════════════════════════════════════════════════════════════════════════════
@router.post("/users/{user_id}/report-qr-lost")
def report_qr_lost(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if current.role != "admin" and current.id != user_id:
        raise HTTPException(status_code=403, detail="Can only report your own QR")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_qr = user.qr_code
    new_hash = generate_qr_hash((user.reg_number or str(user.id)) + secrets.token_hex(4))
    new_qr_path = generate_qr_image(new_hash, user.full_name)
    user.qr_code = new_hash
    db.add(
        Alert(
            user_id=user.id,
            type="qr_compromised",
            description=(
                f"{user.full_name} reported QR card lost/stolen. "
                "The previous QR was invalidated and a replacement was generated."
            ),
        )
    )
    record_record_audit(db, current, "user.qr_regenerate", "user", user_id)
    try:
        db.commit()
    except Exception:
        db.rollback()
        if os.path.exists(new_qr_path):
            os.remove(new_qr_path)
        raise HTTPException(status_code=500, detail="Could not regenerate QR code")

    old_qr_path = QR_DIR / f"{old_qr}.png" if old_qr else None
    if old_qr_path and old_qr_path.exists():
        old_qr_path.unlink()

    return {"message": "QR invalidated and regenerated", "new_qr": new_hash}


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE 12 — QR EXPIRY
# ══════════════════════════════════════════════════════════════════════════════
@router.post("/users/{user_id}/renew-qr")
def renew_qr(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_qr = user.qr_code
    new_hash = generate_qr_hash((user.reg_number or str(user.id)) + secrets.token_hex(4))
    new_expiry = datetime.utcnow() + timedelta(days=180)
    new_qr_path = generate_qr_image(new_hash, user.full_name)
    user.qr_code = new_hash
    user.qr_expires = new_expiry
    audit(db, admin, "user.qr_renew", "user", user_id)
    try:
        db.commit()
    except Exception:
        db.rollback()
        if os.path.exists(new_qr_path):
            os.remove(new_qr_path)
        raise HTTPException(status_code=500, detail="Could not renew QR code")

    old_qr_path = QR_DIR / f"{old_qr}.png" if old_qr else None
    if old_qr_path and old_qr_path.exists():
        old_qr_path.unlink()

    return {
        "message": "QR renewed",
        "new_qr": new_hash,
        "expires": user.qr_expires.isoformat(),
    }


@router.get("/users/expired-qr")
def list_expired_qr(db: Session = Depends(get_db), _=Depends(require_admin)):
    now = datetime.utcnow()
    expired = db.query(User).filter(User.qr_expires != None, User.qr_expires < now).all()
    expiring_soon = db.query(User).filter(
        User.qr_expires != None,
        User.qr_expires > now,
        User.qr_expires < now + timedelta(days=30)
    ).all()
    return {
        "expired": [{"id": u.id, "name": u.full_name, "reg": u.reg_number,
                     "expired_on": u.qr_expires.strftime("%b %d, %Y")} for u in expired],
        "expiring_soon": [{"id": u.id, "name": u.full_name, "reg": u.reg_number,
                           "expires": u.qr_expires.strftime("%b %d, %Y")} for u in expiring_soon],
    }

@router.post("/qr/check-expiry")
def auto_expire_qr(db: Session = Depends(get_db), _=Depends(require_admin)):
    """Run this periodically to auto-flag expired QRs."""
    now = datetime.utcnow()
    expired_users = db.query(User).filter(
        User.qr_expires != None, User.qr_expires < now, User.status == "active"
    ).all()
    flagged = []
    for u in expired_users:
        existing = db.query(Alert).filter(
            Alert.user_id == u.id, Alert.type == "qr_expired",
            Alert.resolved == False
        ).first()
        if not existing:
            db.add(Alert(user_id=u.id, type="qr_expired",
                         description=f"QR code for {u.full_name} ({u.reg_number}) expired on {u.qr_expires.strftime('%b %d, %Y')}. Renewal required."))
            flagged.append(u.full_name)
    db.commit()
    return {"flagged": len(flagged), "names": flagged}
