from datetime import datetime, timedelta
import os

from sqlalchemy.orm import Session

from models import Alert, User
from services.audit_service import record_audit
from utils.qr import QR_DIR, generate_qr_hash, generate_qr_image


def regenerate_lost_qr(db: Session, user: User, actor: User) -> str:
    old_hash = user.qr_code
    new_hash = generate_qr_hash(user.reg_number or str(user.id))
    new_path = generate_qr_image(new_hash, user.full_name)
    user.qr_code = new_hash
    db.add(Alert(
        user_id=user.id,
        type="qr_compromised",
        description=f"{user.full_name} reported QR card lost/stolen. The previous QR was invalidated and a replacement was generated.",
    ))
    record_audit(db, actor, "user.qr_regenerate", "user", user.id)
    try:
        db.commit()
    except Exception:
        db.rollback()
        if os.path.exists(new_path):
            os.remove(new_path)
        raise
    _remove_old_qr(old_hash)
    return new_hash


def renew_user_qr(db: Session, user: User, actor: User) -> tuple[str, datetime]:
    old_hash = user.qr_code
    new_hash = generate_qr_hash(user.reg_number or str(user.id))
    expiry = datetime.utcnow() + timedelta(days=180)
    new_path = generate_qr_image(new_hash, user.full_name)
    user.qr_code = new_hash
    user.qr_expires = expiry
    record_audit(db, actor, "user.qr_renew", "user", user.id)
    try:
        db.commit()
    except Exception:
        db.rollback()
        if os.path.exists(new_path):
            os.remove(new_path)
        raise
    _remove_old_qr(old_hash)
    return new_hash, expiry


def get_qr_expiry_report(db: Session) -> dict[str, list[dict]]:
    now = datetime.utcnow()
    expired = db.query(User).filter(User.qr_expires.is_not(None), User.qr_expires < now).all()
    expiring = db.query(User).filter(
        User.qr_expires.is_not(None),
        User.qr_expires > now,
        User.qr_expires < now + timedelta(days=30),
    ).all()
    return {
        "expired": [{"id": user.id, "name": user.full_name, "reg": user.reg_number, "expired_on": user.qr_expires.strftime("%b %d, %Y")} for user in expired],
        "expiring_soon": [{"id": user.id, "name": user.full_name, "reg": user.reg_number, "expires": user.qr_expires.strftime("%b %d, %Y")} for user in expiring],
    }


def flag_expired_qrs(db: Session) -> list[str]:
    now = datetime.utcnow()
    users = db.query(User).filter(
        User.qr_expires.is_not(None), User.qr_expires < now, User.status == "active"
    ).all()
    flagged = []
    for user in users:
        existing = db.query(Alert.id).filter(
            Alert.user_id == user.id,
            Alert.type == "qr_expired",
            Alert.resolved.is_(False),
        ).first()
        if existing is None:
            db.add(Alert(
                user_id=user.id,
                type="qr_expired",
                description=f"QR code for {user.full_name} ({user.reg_number}) expired on {user.qr_expires.strftime('%b %d, %Y')}. Renewal required.",
            ))
            flagged.append(user.full_name)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return flagged


def _remove_old_qr(old_hash: str | None) -> None:
    if not old_hash:
        return
    old_path = QR_DIR / f"{old_hash}.png"
    old_path.unlink(missing_ok=True)
