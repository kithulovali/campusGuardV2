from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session, joinedload

from core.dependencies import get_current_user, require_guard
from db.session import get_db
from models import Alert, Entry, Gate, User, Visitor
from schemas.schemas import AdmitRequest, ScanRequest
from services.gate_service import check_visitor_overstays, find_active_gate, get_last_direction, is_locked_down, is_qr_expired, log_denied_scan

router = APIRouter(prefix="/gates", tags=["Gates & Access Control"])


def get_active_gate(db: Session, gate_id: int) -> Gate:
    gate = find_active_gate(db, gate_id)
    if gate is None:
        raise HTTPException(status_code=404, detail="Gate not found or inactive")
    if gate.locked:
        raise HTTPException(status_code=403, detail="This gate is locked")
    return gate


@router.get("")
def list_gates(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return (
        db.query(Gate)
        .filter(Gate.active.is_(True))
        .order_by(Gate.id)
        .all()
    )


@router.post("/scan")
def scan_qr(
    body: ScanRequest,
    db: Session = Depends(get_db),
    guard: User = Depends(require_guard),
):
    gate = get_active_gate(db, body.gate_id)

    try:
        check_visitor_overstays(db)
        db.commit()
    except Exception:
        db.rollback()

    if is_locked_down(db):
        return {
            "valid": False,
            "user": None,
            "alert": "CAMPUS LOCKDOWN ACTIVE — All access denied",
            "lockdown": True,
            "direction_issue": None,
        }

    user = db.query(User).filter(User.qr_code == body.qr_code).first()
    if not user:
        log_denied_scan(
            db,
            gate_id=gate.id,
            message=f"Unknown QR scanned at gate {gate.id}",
        )
        return {
            "valid": False,
            "user": None,
            "alert": "Unknown QR code — alert logged",
            "lockdown": False,
            "direction_issue": None,
        }

    if user.status == "blacklisted":
        log_denied_scan(
            db,
            gate_id=gate.id,
            user_id=user.id,
            alert_type="blacklisted",
            message=f"Blacklisted user {user.full_name} attempted entry at gate {gate.id}",
        )
        return {
            "valid": False,
            "user": None,
            "alert": "Access denied — user is blacklisted",
            "lockdown": False,
            "direction_issue": None,
        }

    if user.status != "active":
        return {
            "valid": False,
            "user": None,
            "alert": "Inactive account — contact admin",
            "lockdown": False,
            "direction_issue": None,
        }

    if is_qr_expired(user):
        unresolved = (
            db.query(Alert.id)
            .filter(
                Alert.user_id == user.id,
                Alert.type == "qr_expired",
                Alert.resolved.is_(False),
            )
            .first()
        )
        if not unresolved:
            db.add(
                Alert(
                    user_id=user.id,
                    gate_id=gate.id,
                    type="qr_expired",
                    description=(
                        f"Expired QR used by {user.full_name}. "
                        f"Expired: {user.qr_expires:%b %d, %Y}"
                    ),
                )
            )
            db.commit()
        return {
            "valid": False,
            "user": None,
            "alert": f"QR code expired on {user.qr_expires:%b %d, %Y} — renewal required",
            "lockdown": False,
            "direction_issue": None,
        }

    today = date.today()
    scan_count = (
        db.query(func.count(Entry.id))
        .filter(
            Entry.user_id == user.id,
            func.date(Entry.scanned_at) == today,
        )
        .scalar()
        or 0
    )
    last_direction = get_last_direction(db, user.id)
    suggested_direction = "out" if last_direction == "in" else "in"
    direction_issue = "already_in" if last_direction == "in" else None

    # The gate's saved mode is authoritative; clients cannot switch a guarded
    # gate into automatic admission by changing the request payload.
    if gate.mode == "auto":
        entry = Entry(
            user_id=user.id,
            gate_id=gate.id,
            direction=suggested_direction,
            mode="auto",
        )
        db.add(entry)
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(status_code=500, detail="Could not record gate entry")
        direction_issue = None

    return {
        "valid": True,
        "lockdown": False,
        "gate_mode": gate.mode,
        "direction_issue": direction_issue,
        "last_direction": last_direction,
        "suggested_direction": suggested_direction,
        "scan_count_today": scan_count,
        "qr_expires": user.qr_expires.strftime("%b %d, %Y") if user.qr_expires else None,
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "role": user.role,
            "reg_number": user.reg_number,
            "status": user.status,
            "photo": user.photo,
        },
    }


@router.post("/admit")
def admit_entry(
    body: AdmitRequest,
    db: Session = Depends(get_db),
    guard: User = Depends(require_guard),
):
    if is_locked_down(db):
        raise HTTPException(
            status_code=403,
            detail="Campus is in lockdown — no entries allowed",
        )

    gate = get_active_gate(db, body.gate_id)
    user = db.query(User).filter(User.id == body.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="User account is not active")
    if is_qr_expired(user):
        raise HTTPException(status_code=403, detail="User QR code has expired")

    last_direction = get_last_direction(db, user.id)
    expected_direction = "out" if last_direction == "in" else "in"
    if body.direction != expected_direction:
        raise HTTPException(
            status_code=409,
            detail=f"Invalid direction. The next valid direction is '{expected_direction}'.",
        )

    entry = Entry(
        user_id=user.id,
        gate_id=gate.id,
        direction=body.direction,
        mode="guarded",
        approved_by=guard.id,
    )
    db.add(entry)
    try:
        db.commit()
        db.refresh(entry)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not record gate entry")

    return {
        "message": "Entry logged",
        "entry_id": entry.id,
        "direction": entry.direction,
        "gate_id": gate.id,
    }


@router.get("/entries")
def get_entries(
    user_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_guard),
):
    query = db.query(Entry).options(joinedload(Entry.user)).order_by(
        desc(Entry.scanned_at), desc(Entry.id)
    )
    if user_id is not None:
        query = query.filter(Entry.user_id == user_id)

    entries = query.limit(limit).all()
    return [
        {
            "id": entry.id,
            "user_id": entry.user_id,
            "gate_id": entry.gate_id,
            "direction": entry.direction,
            "user_name": entry.user.full_name if entry.user else "Unknown",
            "role": entry.user.role if entry.user else "—",
            "gate": f"Gate {entry.gate_id}" if entry.gate_id else "Main Gate",
            "time": entry.scanned_at.strftime("%b %d, %Y – %I:%M %p") if entry.scanned_at else "",
            "scanned_at": entry.scanned_at.isoformat() if entry.scanned_at else "",
        }
        for entry in entries
    ]


@router.get("/dashboard/stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_guard),
):
    today = date.today()
    total_users = db.query(func.count(User.id)).scalar() or 0
    entries = (
        db.query(Entry.user_id, Entry.direction, Entry.scanned_at, Entry.id)
        .filter(func.date(Entry.scanned_at) == today)
        .order_by(Entry.scanned_at, Entry.id)
        .all()
    )

    latest_by_user: dict[int, str] = {}
    for user_id, direction, _, _ in entries:
        latest_by_user[user_id] = direction

    on_campus = sum(1 for direction in latest_by_user.values() if direction == "in")
    alerts_today = (
        db.query(func.count(Alert.id))
        .filter(
            func.date(Alert.timestamp) == today,
            Alert.resolved.is_(False),
        )
        .scalar()
        or 0
    )
    visitors_today = (
        db.query(func.count(Visitor.id))
        .filter(func.date(Visitor.time_in) == today)
        .scalar()
        or 0
    )

    return {
        "total_users": total_users,
        "on_campus": on_campus,
        "alerts_today": alerts_today,
        "visitors_today": visitors_today,
        "lockdown": is_locked_down(db),
    }
