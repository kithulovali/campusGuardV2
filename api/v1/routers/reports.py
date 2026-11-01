from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.dependencies import require_admin
from db.session import get_db
from services.report_service import generate_attendance_report

router = APIRouter(tags=["Reports & Analytics"])


@router.get("/reports/generate")
def generate_report(
    type: str = Query(default="daily", pattern="^(daily|monthly|six_months)$"),
    format: str = Query(default="pdf", pattern="^(pdf|xlsx)$"),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    try:
        buffer = generate_attendance_report(db, type, format)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not generate report") from exc
    if format == "pdf":
        media_type = "application/pdf"
    else:
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename=report_{type}.{format}"},
    )
