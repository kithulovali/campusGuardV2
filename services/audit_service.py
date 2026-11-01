import json
from typing import Any

from sqlalchemy.orm import Session

from models.audit_log import AuditLog
from models.user import User


def record_audit(
    db: Session,
    actor: User | None,
    action: str,
    target_type: str | None = None,
    target_id: int | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Add an audit event to the caller's transaction; do not commit here."""
    db.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            actor_name=actor.full_name if actor else "System",
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=json.dumps(detail) if detail else None,
        )
    )
