"""Document data access with permission-aware queries.

Every read goes through `visible_documents()` or `get_visible()` — the
permission predicate lives in SQL, never post-filters rows after fetch.
"""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    Document,
    DocumentPermission,
    DocumentPermissionGrant,
    User,
    UserRole,
)


def _visibility_filter(user: User):
    """SQL predicate: documents this user may see."""
    if user.role == UserRole.admin:
        return True  # admins see everything
    granted = select(DocumentPermissionGrant.document_id).where(
        DocumentPermissionGrant.user_id == user.id
    )
    return or_(Document.owner_id == user.id, Document.id.in_(granted))


def visible_documents(
    session: Session, user: User, *, limit: int = 50, offset: int = 0
) -> list[Document]:
    stmt = (
        select(Document)
        .where(_visibility_filter(user))
        .order_by(Document.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(session.execute(stmt).scalars())


def get_visible(session: Session, user: User, document_id: uuid.UUID) -> Document | None:
    """Fetch a document only if the user may see it — returns None for both
    nonexistent and forbidden, so existence is not leaked."""
    stmt = select(Document).where(Document.id == document_id, _visibility_filter(user))
    return session.execute(stmt).scalar_one_or_none()


def can_manage(session: Session, user: User, document: Document) -> bool:
    """Owner, admin, or explicit 'manage' grant."""
    if user.role == UserRole.admin or document.owner_id == user.id:
        return True
    grant = session.execute(
        select(DocumentPermissionGrant).where(
            DocumentPermissionGrant.document_id == document.id,
            DocumentPermissionGrant.user_id == user.id,
            DocumentPermissionGrant.permission == DocumentPermission.manage,
        )
    ).scalar_one_or_none()
    return grant is not None
