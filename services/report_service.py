from datetime import datetime, timedelta
from io import BytesIO

from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from models import Entry


def generate_attendance_report(db: Session, report_type: str, output_format: str) -> BytesIO:
    today = datetime.utcnow().date()
    if report_type == "daily":
        start = datetime.combine(today, datetime.min.time())
        end = datetime.combine(today, datetime.max.time())
    elif report_type == "monthly":
        start = datetime.combine(today.replace(day=1), datetime.min.time())
        end = datetime.utcnow()
    else:
        start = datetime.combine(today - timedelta(days=180), datetime.min.time())
        end = datetime.utcnow()

    entries = (
        db.query(Entry)
        .options(joinedload(Entry.user))
        .filter(Entry.scanned_at.between(start, end))
        .order_by(desc(Entry.scanned_at))
        .limit(5000)
        .all()
    )
    buffer = BytesIO()
    if output_format == "pdf":
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        document = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = [
            Paragraph(f"CampusGuard — {report_type.capitalize()} Report", styles["Title"]),
            Paragraph(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]),
            Spacer(1, 20),
        ]
        rows = [["#", "Name", "Direction", "Gate", "Time"]]
        for index, entry in enumerate(entries[:200], 1):
            rows.append([
                str(index),
                entry.user.full_name if entry.user else str(entry.user_id),
                entry.direction,
                str(entry.gate_id or "—"),
                entry.scanned_at.strftime("%Y-%m-%d %H:%M") if entry.scanned_at else "",
            ])
        table = Table(rows, colWidths=[30, 150, 70, 60, 130])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D1B2A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        story.append(table)
        document.build(story)
    else:
        import openpyxl
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = "Entries"
        worksheet.append(["ID", "Name", "Direction", "Gate", "Time"])
        for entry in entries:
            worksheet.append([
                entry.id,
                entry.user.full_name if entry.user else entry.user_id,
                entry.direction,
                entry.gate_id or "",
                entry.scanned_at.strftime("%Y-%m-%d %H:%M") if entry.scanned_at else "",
            ])
        workbook.save(buffer)
    buffer.seek(0)
    return buffer
