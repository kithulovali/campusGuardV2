from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.dependencies import require_guard
from db.session import get_db
from models.user import User
from schemas.schemas import VisitorCreate
from services.visitor_service import checkout_visitor as checkout_visitor_record
from services.visitor_service import list_visitors as list_visitor_records
from services.visitor_service import register_visitor

router = APIRouter(tags=["Visitors"])


@router.get("/visitors")
def list_visitors(db: Session = Depends(get_db), _=Depends(require_guard)):
    visitors = list_visitor_records(db)
    return [
        {
            "id": visitor.id,
            "name": visitor.name,
            "id_number": visitor.id_number,
            "reason": visitor.reason,
            "host": visitor.host,
            "time_in": visitor.time_in.strftime("%I:%M %p") if visitor.time_in else "",
            "expected_exit": visitor.expected_exit.strftime("%I:%M %p") if visitor.expected_exit else "",
            "checked_out": visitor.checked_out,
        }
        for visitor in visitors
    ]


@router.post("/visitors")
def create_visitor(body: VisitorCreate, db: Session = Depends(get_db), _: User = Depends(require_guard)):
    expected_exit = None
    if body.expected_exit:
        try:
            expected_time = datetime.strptime(body.expected_exit, "%H:%M").time()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="expected_exit must use HH:MM format") from exc
        expected_exit = datetime.combine(datetime.utcnow().date(), expected_time)
    try:
        visitor = register_visitor(
            db,
            name=body.name,
            id_number=body.id_number,
            phone=body.phone,
            reason=body.reason,
            host=body.host,
            expected_exit=expected_exit,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not register visitor") from exc
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
def checkout_visitor(visitor_id: int, db: Session = Depends(get_db), _: User = Depends(require_guard)):
    from models.visitor import Visitor
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if visitor is None:
        raise HTTPException(status_code=404, detail="Visitor not found")
    if visitor.checked_out:
        raise HTTPException(status_code=409, detail="Visitor is already checked out")
    try:
        checkout_visitor_record(db, visitor)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not check out visitor") from exc
    return {"message": "Checked out"}
