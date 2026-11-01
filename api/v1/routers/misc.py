from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func
from datetime import datetime, timedelta
from typing import List, Literal
import io, secrets
from db.session import get_db
from models import Visitor, Alert, Entry, Gate, User
from schemas.schemas import VisitorCreate, VisitorOut, AlertOut
from core.dependencies import get_current_user, require_guard, require_admin
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter(tags=["misc"])

# ── Who is on campus ──────────────────────────────────────────────────────────
@router.get("/campus/live")
def campus_live(db: Session = Depends(get_db), _=Depends(require_guard)):
    """Return each user whose latest entry today is an entry onto campus."""
    today = datetime.utcnow().date()
    entries = (
        db.query(Entry)
        .options(joinedload(Entry.user))
        .filter(func.date(Entry.scanned_at) == today)
        .order_by(Entry.scanned_at, Entry.id)
        .all()
    )

    latest_by_user = {}
    for entry in entries:
        latest_by_user[entry.user_id] = entry

    return [
        {
            "id": entry.user.id,
            "full_name": entry.user.full_name,
            "role": entry.user.role,
            "reg_number": entry.user.reg_number,
            "entry_time": entry.scanned_at.strftime("%I:%M %p") if entry.scanned_at else "",
        }
        for entry in latest_by_user.values()
        if entry.direction == "in" and entry.user is not None
    ]


# ── Visitors ──────────────────────────────────────────────────────────────────
@router.get("/visitors")
def list_visitors(db: Session = Depends(get_db), _=Depends(require_guard)):
    visitors = db.query(Visitor).order_by(desc(Visitor.time_in)).limit(100).all()
    return [
        {
            "id": v.id, "name": v.name, "id_number": v.id_number,
            "reason": v.reason, "host": v.host,
            "time_in": v.time_in.strftime("%I:%M %p") if v.time_in else "",
            "expected_exit": v.expected_exit.strftime("%I:%M %p") if v.expected_exit else "",
            "checked_out": v.checked_out,
        }
        for v in visitors
    ]

@router.post("/visitors")
def create_visitor(
    body: VisitorCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_guard),
):
    expected = None
    if body.expected_exit:
        try:
            expected_time = datetime.strptime(body.expected_exit, "%H:%M").time()
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="expected_exit must use HH:MM format",
            )
        expected = datetime.combine(datetime.utcnow().date(), expected_time)

    visitor = Visitor(
        name=body.name,
        id_number=body.id_number,
        phone=body.phone,
        reason=body.reason,
        host=body.host,
        temp_pass=secrets.token_hex(8),
        expected_exit=expected,
    )
    try:
        db.add(visitor)
        db.commit()
        db.refresh(visitor)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not register visitor")

    return {
        "id": visitor.id,
        "name": visitor.name,
        "id_number": visitor.id_number,
        "reason": visitor.reason,
        "host": visitor.host,
        "time_in": visitor.time_in.strftime("%I:%M %p") if visitor.time_in else "",
        "expected_exit": visitor.expected_exit.strftime("%I:%M %p") if visitor.expected_exit else "",
        "checked_out": visitor.checked_out,
    }


@router.patch("/visitors/{visitor_id}/checkout")
def checkout_visitor(
    visitor_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_guard),
):
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="Visitor not found")
    if visitor.checked_out:
        raise HTTPException(status_code=409, detail="Visitor is already checked out")

    visitor.checked_out = True
    visitor.checkout_time = datetime.utcnow()
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not check out visitor")
    return {"message": "Checked out"}

# ── Alerts ────────────────────────────────────────────────────────────────────
class AlertCreate(BaseModel):
    type: Literal[
        "invalid_qr",
        "blacklisted",
        "overstay",
        "repeated_fail",
        "lockdown",
        "qr_expired",
        "qr_compromised",
        "manual",
    ]
    gate_id: int | None = Field(default=None, gt=0)
    description: str = Field(min_length=3, max_length=2000)


@router.get("/alerts")
def list_alerts(db: Session = Depends(get_db), _=Depends(require_guard)):
    alerts = db.query(Alert).order_by(desc(Alert.timestamp)).limit(100).all()
    return [
        {
            "id": a.id, "type": a.type, "description": a.description,
            "resolved": a.resolved,
            "gate": f"Gate {a.gate_id}" if a.gate_id else "Unknown Gate",
            "timestamp": a.timestamp.strftime("%I:%M %p") if a.timestamp else "",
        }
        for a in alerts
    ]

@router.post("/alerts")
def create_alert(
    body: AlertCreate,
    db: Session = Depends(get_db),
    guard: User = Depends(require_guard),
):
    if body.gate_id is not None:
        gate = db.query(Gate).filter(Gate.id == body.gate_id).first()
        if not gate:
            raise HTTPException(status_code=404, detail="Gate not found")

    alert = Alert(
        type=body.type,
        gate_id=body.gate_id,
        description=body.description,
        user_id=guard.id if body.type == "manual" else None,
    )
    try:
        db.add(alert)
        db.commit()
        db.refresh(alert)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not create alert")

    return {
        "id": alert.id,
        "type": alert.type,
        "description": alert.description,
        "resolved": alert.resolved,
        "gate": f"Gate {alert.gate_id}" if alert.gate_id else "Unknown Gate",
        "timestamp": alert.timestamp.strftime("%I:%M %p") if alert.timestamp else "",
    }


@router.patch("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, db: Session = Depends(get_db), _=Depends(require_guard)):
    a = db.query(Alert).filter(Alert.id == alert_id).first()
    if not a: raise HTTPException(404, "Alert not found")
    a.resolved = True; db.commit()
    return {"message": "Resolved"}

# ── Entries ───────────────────────────────────────────────────────────────────
@router.get("/entries")
def get_entries(user_id: int | None = Query(default=None, gt=0), limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db), _=Depends(require_guard)):
    q = db.query(Entry).order_by(desc(Entry.scanned_at))
    if user_id: q = q.filter(Entry.user_id == user_id)
    entries = q.limit(limit).all()
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
        for e in entries
    ]

# ── Dashboard stats ───────────────────────────────────────────────────────────
@router.get("/dashboard/stats")
def stats(db: Session = Depends(get_db), _=Depends(require_guard)):
    today = datetime.utcnow().date()
    total_users = db.query(func.count(User.id)).scalar() or 0
    latest_entries = (
        db.query(Entry.user_id, Entry.direction, Entry.scanned_at, Entry.id)
        .filter(func.date(Entry.scanned_at) == today)
        .order_by(Entry.scanned_at, Entry.id)
        .all()
    )
    latest_by_user = {}
    for user_id, direction, _, _ in latest_entries:
        latest_by_user[user_id] = direction

    alerts = (
        db.query(func.count(Alert.id))
        .filter(
            func.date(Alert.timestamp) == today,
            Alert.resolved.is_(False),
        )
        .scalar()
        or 0
    )
    visitors = (
        db.query(func.count(Visitor.id))
        .filter(func.date(Visitor.time_in) == today)
        .scalar()
        or 0
    )
    return {
        "total_users": total_users,
        "on_campus": sum(
            1 for direction in latest_by_user.values() if direction == "in"
        ),
        "alerts_today": alerts,
        "visitors_today": visitors,
    }


# ── Reports ───────────────────────────────────────────────────────────────────
@router.get("/reports/generate")
def generate_report(
    type: str = Query(default="daily", pattern="^(daily|monthly|six_months)$"),
    format: str = Query(default="pdf", pattern="^(pdf|xlsx)$"),
    db: Session = Depends(get_db), _=Depends(require_admin)
):
    today = datetime.utcnow().date()
    if type == "daily":
        start = datetime.combine(today, datetime.min.time())
        end   = datetime.combine(today, datetime.max.time())
    elif type == "monthly":
        start = datetime.combine(today.replace(day=1), datetime.min.time())
        end   = datetime.utcnow()
    else:
        start = datetime.combine(today - timedelta(days=180), datetime.min.time())
        end   = datetime.utcnow()

    entries = (
        db.query(Entry)
        .filter(Entry.scanned_at.between(start, end))
        .order_by(desc(Entry.scanned_at))
        .limit(5000)
        .all()
    )

    if format == "pdf":
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4)
        styles = getSampleStyleSheet()
        story = [
            Paragraph(f"CampusGuard — {type.capitalize()} Report", styles["Title"]),
            Paragraph(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]),
            Spacer(1, 20),
        ]
        data = [["#", "Name", "Direction", "Gate", "Time"]]
        for i, e in enumerate(entries[:200], 1):
            data.append([
                str(i),
                e.user.full_name if e.user else str(e.user_id),
                e.direction,
                str(e.gate_id or "—"),
                e.scanned_at.strftime("%Y-%m-%d %H:%M") if e.scanned_at else ""
            ])
        tbl = Table(data, colWidths=[30, 150, 70, 60, 130])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0D1B2A")),
            ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
            ("GRID",       (0,0), (-1,-1), 0.5, colors.grey),
            ("FONTSIZE",   (0,0), (-1,-1), 9),
        ]))
        story.append(tbl)
        doc.build(story)
        buf.seek(0)
        return StreamingResponse(buf, media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=report_{type}.pdf"})
    else:
        import openpyxl
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Entries"
        ws.append(["ID", "Name", "Direction", "Gate", "Time"])
        for e in entries[:5000]:
            ws.append([e.id, e.user.full_name if e.user else e.user_id, e.direction, e.gate_id or "",
                       e.scanned_at.strftime("%Y-%m-%d %H:%M") if e.scanned_at else ""])
        buf = io.BytesIO(); wb.save(buf); buf.seek(0)
        return StreamingResponse(buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=report_{type}.xlsx"})


# ── Weekly traffic for dashboard chart ───────────────────────────────────────
@router.get("/reports/weekly")
def weekly_traffic(db: Session = Depends(get_db), _=Depends(get_current_user)):
    from datetime import date
    today = date.today()
    # Last 7 days
    days = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        count = db.query(func.count(Entry.id)).filter(
            func.date(Entry.scanned_at) == d,
            Entry.direction == 'in'
        ).scalar()
        days.append({ "day": d.strftime("%a"), "date": d.isoformat(), "entries": count })
    return days


# ── Overstay checker ──────────────────────────────────────────────────────────
@router.get("/visitors/check-overstay")
def check_overstay(db: Session = Depends(get_db), _=Depends(require_guard)):
    """Check for visitors who have exceeded their expected exit time."""
    now = datetime.utcnow()
    overstaying = db.query(Visitor).filter(
        Visitor.checked_out == False,
        Visitor.expected_exit != None,
        Visitor.expected_exit < now
    ).all()

    flagged = []
    for v in overstaying:
        # Create alert if not already created for this visitor today
        existing = db.query(Alert).filter(
            Alert.description.like(f"%{v.name}%"),
            Alert.type == "overstay"
        ).first()
        if not existing:
            alert = Alert(
                type="overstay",
                description=f"Visitor {v.name} (host: {v.host}) has overstayed. Expected exit: {v.expected_exit.strftime('%I:%M %p')}. Still on campus."
            )
            db.add(alert)
            flagged.append(v.name)
    if flagged:
        db.commit()

    return {"overstaying": len(overstaying), "new_alerts": flagged}


@router.post("/alerts/check-auto")
def auto_check_alerts(db: Session = Depends(get_db), _=Depends(require_guard)):
    """
    Call this periodically from the frontend (every 2 min) to auto-generate
    visitor overstay alerts without needing a gate scan to trigger them.
    """
    from datetime import date
    now = datetime.utcnow()
    today = date.today()
    flagged = []

    # Visitor overstays
    overstaying = db.query(Visitor).filter(
        Visitor.checked_out == False,
        Visitor.expected_exit != None,
        Visitor.expected_exit < now
    ).all()
    for v in overstaying:
        existing = db.query(Alert).filter(
            Alert.type == "overstay",
            Alert.description.like(f"%{v.name}%"),
            func.date(Alert.timestamp) == today
        ).first()
        if not existing:
            db.add(Alert(
                type="overstay",
                description=f"Visitor '{v.name}' has overstayed. "
                            f"Expected exit: {v.expected_exit.strftime('%I:%M %p')}. "
                            f"Host: {v.host or 'N/A'}."
            ))
            flagged.append(f"Visitor overstay: {v.name}")

    if flagged:
        db.commit()

    return {"auto_alerts_created": len(flagged), "details": flagged}
