"""Audit logging — append-only record of security-relevant actions."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def log_action(
    session: Session,
    *,
    actor: User | None,
    action: str,
    target_type: str,
    target_id: uuid.UUID | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail or {},
    )
    session.add(entry)
    session.flush()
    return entry
