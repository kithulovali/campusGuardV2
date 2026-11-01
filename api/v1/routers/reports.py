from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func
from datetime import datetime, timedelta
from typing import Literal
import io, secrets
from db.session import get_db
from models import Visitor, Alert, Entry, Gate, User
from schemas.schemas import VisitorCreate
from core.dependencies import get_current_user, require_guard, require_admin
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter()

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
