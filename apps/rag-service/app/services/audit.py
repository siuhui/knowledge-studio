import uuid

from sqlalchemy.orm import Session

from ..models import AuditLog


def write_audit_log(
    db: Session,
    *,
    actor_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str,
    trace_id: str,
) -> None:
    row = AuditLog(
        id=str(uuid.uuid4()),
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        trace_id=trace_id,
    )
    db.add(row)
