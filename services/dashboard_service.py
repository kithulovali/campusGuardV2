from datetime import date, datetime, timedelta

from sqlalchemy import desc, func
from sqlalchemy.orm import Session, joinedload

from models import Alert, Entry, User, Visitor


def get_campus_occupancy(db: Session) -> list[dict]:
    today = datetime.utcnow().date()
    rows = db.query(Entry).options(joinedload(Entry.user)).filter(func.date(Entry.scanned_at) == today).order_by(Entry.scanned_at, Entry.id).all()
    latest = {}
    for row in rows:
        latest[row.user_id] = row
    return [{"id": row.user.id, "full_name": row.user.full_name, "role": row.user.role, "reg_number": row.user.reg_number, "entry_time": row.scanned_at.strftime("%I:%M %p") if row.scanned_at else ""} for row in latest.values() if row.direction == "in" and row.user is not None]


def get_dashboard_stats(db: Session) -> dict:
    today = datetime.utcnow().date()
    total_users = db.query(func.count(User.id)).scalar() or 0
    rows = db.query(Entry.user_id, Entry.direction, Entry.scanned_at, Entry.id).filter(func.date(Entry.scanned_at) == today).order_by(Entry.scanned_at, Entry.id).all()
    latest = {}
    for user_id, direction, _, _ in rows:
        latest[user_id] = direction
    alerts = db.query(func.count(Alert.id)).filter(func.date(Alert.timestamp) == today, Alert.resolved.is_(False)).scalar() or 0
    visitors = db.query(func.count(Visitor.id)).filter(func.date(Visitor.time_in) == today).scalar() or 0
    return {"total_users": total_users, "on_campus": sum(1 for direction in latest.values() if direction == "in"), "alerts_today": alerts, "visitors_today": visitors}


def get_entry_history(db: Session, user_id: int | None, limit: int) -> list[dict]:
    query = db.query(Entry).options(joinedload(Entry.user)).order_by(desc(Entry.scanned_at))
    if user_id is not None:
        query = query.filter(Entry.user_id == user_id)
    rows = query.limit(limit).all()
    return [{"id": row.id, "user_id": row.user_id, "gate_id": row.gate_id, "direction": row.direction, "user_name": row.user.full_name if row.user else "Unknown", "role": row.user.role if row.user else "—", "gate": f"Gate {row.gate_id}" if row.gate_id else "Main Gate", "time": row.scanned_at.strftime("%b %d, %Y – %I:%M %p") if row.scanned_at else "", "scanned_at": row.scanned_at.isoformat() if row.scanned_at else ""} for row in rows]


def get_weekly_traffic(db: Session) -> list[dict]:
    today = date.today()
    result = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        count = db.query(func.count(Entry.id)).filter(func.date(Entry.scanned_at) == day, Entry.direction == "in").scalar() or 0
        result.append({"day": day.strftime("%a"), "date": day.isoformat(), "entries": count})
    return result


def get_guard_statistics(db: Session) -> list[dict]:
    today = date.today()
    guards = db.query(User).filter(User.role == "guard").all()
    alerts_today = db.query(func.count(Alert.id)).filter(func.date(Alert.timestamp) == today).scalar() or 0
    result = []
    for guard in guards:
        today_count = db.query(func.count(Entry.id)).filter(Entry.approved_by == guard.id, func.date(Entry.scanned_at) == today).scalar() or 0
        total_count = db.query(func.count(Entry.id)).filter(Entry.approved_by == guard.id).scalar() or 0
        result.append({"id": guard.id, "name": guard.full_name, "status": guard.status, "approved_today": today_count, "approved_total": total_count, "alerts_today": alerts_today})
    return result
