from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from datetime import datetime, timedelta
from typing import List
import io, secrets
from app.db.session import get_db
from app.models.models import Visitor, Alert, Entry, User
from app.schemas.schemas import VisitorCreate, VisitorOut, AlertOut
from app.core.dependencies import get_current_user, require_guard, require_admin
from pydantic import BaseModel
from typing import Optional

router = APIRouter(tags=["misc"])

# ── Who is on campus ──────────────────────────────────────────────────────────
@router.get("/campus/live")
def campus_live(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Returns list of users currently on campus (entered but not yet exited today)."""
    today = datetime.utcnow().date()
    # Get all entries today
    entries = db.query(Entry).filter(
        func.date(Entry.scanned_at) == today
    ).order_by(Entry.scanned_at).all()

    # Track who is inside: increment on 'in', decrement on 'out'
    status = {}  # user_id -> latest entry record
    for e in entries:
        if e.direction == 'in':
            status[e.user_id] = e
        elif e.direction == 'out' and e.user_id in status:
            del status[e.user_id]

    result = []
    for user_id, entry in status.items():
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            result.append({
                "id": user.id,
                "full_name": user.full_name,
                "role": user.role,
                "reg_number": user.reg_number,
                "entry_time": entry.scanned_at.strftime("%I:%M %p") if entry.scanned_at else "",
            })
    return result

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
def create_visitor(body: VisitorCreate, db: Session = Depends(get_db), _=Depends(require_guard)):
    expected = None
    if body.expected_exit:
        try:
            t = datetime.strptime(body.expected_exit, "%H:%M").time()
            expected = datetime.combine(datetime.utcnow().date(), t)
        except: pass

    visitor = Visitor(
        name=body.name, id_number=body.id_number, phone=body.phone,
        reason=body.reason, host=body.host,
        temp_pass=secrets.token_hex(8), expected_exit=expected
    )
    db.add(visitor); db.commit(); db.refresh(visitor)
    return {
        "id": visitor.id, "name": visitor.name, "id_number": visitor.id_number,
        "reason": visitor.reason, "host": visitor.host,
        "time_in": visitor.time_in.strftime("%I:%M %p"),
        "expected_exit": visitor.expected_exit.strftime("%I:%M %p") if visitor.expected_exit else "",
        "checked_out": False,
    }

@router.patch("/visitors/{visitor_id}/checkout")
def checkout_visitor(visitor_id: int, db: Session = Depends(get_db), _=Depends(require_guard)):
    v = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not v: raise HTTPException(404, "Visitor not found")
    v.checked_out = True; v.checkout_time = datetime.utcnow(); db.commit()
    return {"message": "Checked out"}

# ── Alerts ────────────────────────────────────────────────────────────────────
class AlertCreate(BaseModel):
    type: str
    gate_id: Optional[int] = None
    description: str

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
def create_alert(body: AlertCreate, db: Session = Depends(get_db), guard=Depends(require_guard)):
    a = Alert(type=body.type, gate_id=body.gate_id, description=body.description)
    db.add(a); db.commit(); db.refresh(a)
    return {
        "id": a.id, "type": a.type, "description": a.description,
        "resolved": False,
        "gate": f"Gate {a.gate_id}" if a.gate_id else "Unknown Gate",
        "timestamp": a.timestamp.strftime("%I:%M %p") if a.timestamp else "",
    }

@router.patch("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, db: Session = Depends(get_db), _=Depends(require_guard)):
    a = db.query(Alert).filter(Alert.id == alert_id).first()
    if not a: raise HTTPException(404, "Alert not found")
    a.resolved = True; db.commit()
    return {"message": "Resolved"}

# ── Entries ───────────────────────────────────────────────────────────────────
@router.get("/entries")
def get_entries(user_id: int = None, limit: int = 50, db: Session = Depends(get_db), _=Depends(get_current_user)):
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
def stats(db: Session = Depends(get_db), _=Depends(get_current_user)):
    today = datetime.utcnow().date()
    total_users = db.query(func.count(User.id)).scalar()
    ins   = db.query(func.count(Entry.id)).filter(func.date(Entry.scanned_at)==today, Entry.direction=="in").scalar()
    outs  = db.query(func.count(Entry.id)).filter(func.date(Entry.scanned_at)==today, Entry.direction=="out").scalar()
    alerts= db.query(func.count(Alert.id)).filter(func.date(Alert.timestamp)==today, Alert.resolved==False).scalar()
    vis   = db.query(func.count(Visitor.id)).filter(func.date(Visitor.time_in)==today).scalar()
    return {"total_users": total_users, "on_campus": max(0, ins - outs), "alerts_today": alerts, "visitors_today": vis}

# ── Reports ───────────────────────────────────────────────────────────────────
@router.get("/reports/generate")
def generate_report(
    type: str = "daily", format: str = "pdf",
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

    entries = db.query(Entry).filter(Entry.scanned_at.between(start, end)).order_by(desc(Entry.scanned_at)).all()

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
def auto_check_alerts(db: Session = Depends(get_db), _=Depends(get_current_user)):
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
