from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional
from datetime import datetime, date, timedelta
from app.db.session import get_db
from app.models.models import User, Gate, Entry, Alert, SystemState, Visitor
from app.schemas.schemas import ScanRequest, AdmitRequest
from app.core.dependencies import get_current_user, require_guard

router = APIRouter(prefix="/gates", tags=["gates"])


def is_locked_down(db: Session) -> bool:
    state = db.query(SystemState).filter(SystemState.key == "lockdown").first()
    return state.value == "true" if state else False


def is_qr_expired(user: User) -> bool:
    return bool(user.qr_expires and user.qr_expires < datetime.utcnow())


def get_last_direction(db: Session, user_id: int) -> Optional[str]:
    today = date.today()
    last = (db.query(Entry)
            .filter(Entry.user_id == user_id, func.date(Entry.scanned_at) == today)
            .order_by(desc(Entry.scanned_at)).first())
    return last.direction if last else None


def count_scans_today(db: Session, user_id: int) -> int:
    today = date.today()
    return db.query(func.count(Entry.id)).filter(
        Entry.user_id == user_id,
        func.date(Entry.scanned_at) == today
    ).scalar()


def check_visitor_overstays(db: Session):
    """Auto-create alerts for visitors who have overstayed — called on every scan."""
    now = datetime.utcnow()
    overstaying = db.query(Visitor).filter(
        Visitor.checked_out == False,
        Visitor.expected_exit != None,
        Visitor.expected_exit < now
    ).all()
    for v in overstaying:
        # Only create once per visitor per day
        existing = db.query(Alert).filter(
            Alert.type == "overstay",
            Alert.description.like(f"%{v.name}%"),
            func.date(Alert.timestamp) == date.today()
        ).first()
        if not existing:
            db.add(Alert(
                type="overstay",
                description=f"Visitor '{v.name}' has overstayed. Expected exit: "
                            f"{v.expected_exit.strftime('%I:%M %p')}. Host: {v.host or 'N/A'}."
            ))


@router.get("")
def list_gates(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(Gate).filter(Gate.active == True).all()


@router.post("/scan")
def scan_qr(body: ScanRequest, db: Session = Depends(get_db), guard=Depends(require_guard)):

    # ── Check visitor overstays on every scan (passive background check) ─────
    try:
        check_visitor_overstays(db)
        db.commit()
    except Exception:
        db.rollback()

    # ── Lockdown ──────────────────────────────────────────────────────────────
    if is_locked_down(db):
        return {"valid": False, "user": None,
                "alert": "CAMPUS LOCKDOWN ACTIVE — All access denied",
                "lockdown": True, "direction_issue": None}

    user = db.query(User).filter(User.qr_code == body.qr_code).first()

    if not user:
        db.add(Alert(gate_id=body.gate_id, type="invalid_qr",
                     description=f"Unknown QR scanned at gate {body.gate_id}"))
        db.commit()
        return {"valid": False, "user": None,
                "alert": "Unknown QR code — alert logged", "direction_issue": None}

    if user.status == "blacklisted":
        db.add(Alert(gate_id=body.gate_id, user_id=user.id, type="blacklisted",
                     description=f"Blacklisted user {user.full_name} attempted entry at gate {body.gate_id}"))
        db.commit()
        return {"valid": False, "user": None,
                "alert": "Access denied — user is blacklisted", "direction_issue": None}

    if user.status == "inactive":
        return {"valid": False, "user": None,
                "alert": "Inactive account — contact admin", "direction_issue": None}

    # ── QR expiry ─────────────────────────────────────────────────────────────
    if is_qr_expired(user):
        existing = db.query(Alert).filter(
            Alert.user_id == user.id, Alert.type == "qr_expired", Alert.resolved == False
        ).first()
        if not existing:
            db.add(Alert(user_id=user.id, gate_id=body.gate_id, type="qr_expired",
                         description=f"Expired QR used by {user.full_name}. "
                                     f"Expired: {user.qr_expires.strftime('%b %d, %Y')}"))
        db.commit()
        return {"valid": False, "user": None,
                "alert": f"QR code expired on {user.qr_expires.strftime('%b %d, %Y')} — renewal required",
                "direction_issue": None}

    # ── Repeated scans (suspicious) ───────────────────────────────────────────
    scan_count = count_scans_today(db, user.id)
    if scan_count >= 6:
        existing = db.query(Alert).filter(
            Alert.user_id == user.id,
            Alert.type == "repeated_fail",
            func.date(Alert.timestamp) == date.today()
        ).first()
        if not existing:
            db.add(Alert(gate_id=body.gate_id, user_id=user.id, type="repeated_fail",
                         description=f"{user.full_name} ({user.reg_number}) has scanned "
                                     f"{scan_count} times today — flagged as suspicious activity"))
            db.commit()

    # ── Direction logic ───────────────────────────────────────────────────────
    last_direction = get_last_direction(db, user.id)
    suggested_direction = "in" if last_direction != "in" else "out"
    direction_issue = "already_in" if last_direction == "in" else None

    # ── Auto mode: log immediately ────────────────────────────────────────────
    if body.mode == "auto" and not direction_issue:
        db.add(Entry(user_id=user.id, gate_id=body.gate_id,
                     direction=suggested_direction, mode="auto"))
        db.commit()

    return {
        "valid": True,
        "lockdown": False,
        "direction_issue": direction_issue,
        "last_direction": last_direction,
        "suggested_direction": suggested_direction,
        "scan_count_today": scan_count,
        "qr_expires": user.qr_expires.strftime("%b %d, %Y") if user.qr_expires else None,
        "user": {
            "id": user.id, "full_name": user.full_name,
            "role": user.role, "reg_number": user.reg_number,
            "status": user.status, "photo": user.photo,
        }
    }


@router.post("/admit")
def admit_entry(body: AdmitRequest, db: Session = Depends(get_db), guard=Depends(require_guard)):
    if is_locked_down(db):
        raise HTTPException(403, "Campus is in lockdown — no entries allowed")
    user = db.query(User).filter(User.id == body.user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    entry = Entry(user_id=user.id, gate_id=body.gate_id,
                  direction=body.direction, mode=body.mode, approved_by=guard.id)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"message": "Entry logged", "entry_id": entry.id, "direction": body.direction}


@router.get("/entries")
def get_entries(user_id: Optional[int] = None, limit: int = 50,
                db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(Entry).order_by(desc(Entry.scanned_at))
    if user_id:
        q = q.filter(Entry.user_id == user_id)
    return [
        {
            "id": e.id, "user_id": e.user_id, "gate_id": e.gate_id,
            "direction": e.direction,
            "user_name": e.user.full_name if e.user else "Unknown",
            "role": e.user.role if e.user else "—",
            "gate": f"Gate {e.gate_id}" if e.gate_id else "Main Gate",
            "time": e.scanned_at.strftime("%b %d, %Y – %I:%M %p") if e.scanned_at else "",
            "scanned_at": e.scanned_at.isoformat() if e.scanned_at else "",
        }
        for e in q.limit(limit).all()
    ]


@router.get("/dashboard/stats")
def dashboard_stats(db: Session = Depends(get_db), _=Depends(get_current_user)):
    today = date.today()
    total   = db.query(func.count(User.id)).scalar()
    ins     = db.query(func.count(Entry.id)).filter(
        func.date(Entry.scanned_at) == today, Entry.direction == "in").scalar()
    outs    = db.query(func.count(Entry.id)).filter(
        func.date(Entry.scanned_at) == today, Entry.direction == "out").scalar()
    alerts  = db.query(func.count(Alert.id)).filter(
        func.date(Alert.timestamp) == today, Alert.resolved == False).scalar()
    vis     = db.query(func.count(Visitor.id)).filter(
        func.date(Visitor.time_in) == today).scalar()
    locked  = is_locked_down(db)
    return {
        "total_users": total,
        "on_campus": max(0, ins - outs),
        "alerts_today": alerts,
        "visitors_today": vis,
        "lockdown": locked
    }
