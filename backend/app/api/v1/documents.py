"""Document endpoints — every read is permission-filtered in SQL."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, NotFoundError
from app.core.security import CurrentUser, ForbiddenError
from app.db.session import get_session
from app.models import Document, DocumentPermissionGrant, User
from app.models.enums import DocumentPermission
from app.repositories import documents as doc_repo
from app.schemas.document import (
    DocumentCreateRequest,
    DocumentDetailResponse,
    DocumentResponse,
    GrantRequest,
    GrantResponse,
)
from app.services.audit import log_action

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    current: CurrentUser,
    session: Session = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[Document]:
    """Documents the caller is allowed to see — owned, granted, or (admin) all."""
    return doc_repo.visible_documents(session, current, limit=limit, offset=offset)


@router.post(
    "", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED
)
def create_document(
    body: DocumentCreateRequest,
    current: CurrentUser,
    session: Session = Depends(get_session),
) -> Document:
    """Create a new logical document shell; versions are uploaded separately."""
    doc = Document(
        title=body.title,
        description=body.description,
        document_type=body.document_type,
        owner_id=current.id,
    )
    session.add(doc)
    log_action(
        session,
        actor=current,
        action="document.created",
        target_type="document",
        target_id=doc.id,
    )
    session.commit()
    session.refresh(doc)
    return doc


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    document_id: uuid.UUID,
    current: CurrentUser,
    session: Session = Depends(get_session),
) -> Document:
    # 404 both for missing and forbidden — existence is not leaked.
    doc = doc_repo.get_visible(session, current, document_id)
    if doc is None:
        raise NotFoundError("Document not found.")
    return doc


@router.get("/{document_id}/permissions", response_model=list[GrantResponse])
def list_permissions(
    document_id: uuid.UUID,
    current: CurrentUser,
    session: Session = Depends(get_session),
) -> list[GrantResponse]:
    doc = doc_repo.get_visible(session, current, document_id)
    if doc is None:
        raise NotFoundError("Document not found.")
    if not doc_repo.can_manage(session, current, doc):
        raise ForbiddenError("Manage permission required to view grants.")
    grants = session.execute(
        select(DocumentPermissionGrant).where(
            DocumentPermissionGrant.document_id == doc.id
        )
    ).scalars().all()
    return [
        GrantResponse(
            user_id=g.user_id,
            email=g.user.email,
            full_name=g.user.full_name,
            permission=g.permission.value,
            created_at=g.created_at,
        )
        for g in grants
    ]


@router.post(
    "/{document_id}/permissions",
    response_model=GrantResponse,
    status_code=status.HTTP_201_CREATED,
)
def grant_permission(
    document_id: uuid.UUID,
    body: GrantRequest,
    current: CurrentUser,
    session: Session = Depends(get_session),
) -> GrantResponse:
    doc = doc_repo.get_visible(session, current, document_id)
    if doc is None:
        raise NotFoundError("Document not found.")
    if not doc_repo.can_manage(session, current, doc):
        raise ForbiddenError("Manage permission required to share.")
    grantee = session.execute(
        select(User).where(User.email == body.email.lower().strip())
    ).scalar_one_or_none()
    if grantee is None:
        raise NotFoundError("No user with that email.")
    if grantee.id == doc.owner_id:
        raise BadRequestError("The owner already has full access.")

    grant = session.execute(
        select(DocumentPermissionGrant).where(
            DocumentPermissionGrant.document_id == doc.id,
            DocumentPermissionGrant.user_id == grantee.id,
        )
    ).scalar_one_or_none()
    if grant is None:
        grant = DocumentPermissionGrant(
            document_id=doc.id, user_id=grantee.id, granted_by=current.id
        )
        session.add(grant)
    grant.permission = DocumentPermission(body.permission)
    log_action(
        session, actor=current, action="document.shared",
        target_type="document", target_id=doc.id,
    )
    session.commit()
    session.refresh(grant)
    return GrantResponse(
        user_id=grantee.id,
        email=grantee.email,
        full_name=grantee.full_name,
        permission=grant.permission.value,
        created_at=grant.created_at,
    )


@router.delete("/{document_id}/permissions/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_permission(
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    current: CurrentUser,
    session: Session = Depends(get_session),
) -> None:
    doc = doc_repo.get_visible(session, current, document_id)
    if doc is None:
        raise NotFoundError("Document not found.")
    if not doc_repo.can_manage(session, current, doc):
        raise ForbiddenError("Manage permission required.")
    grant = session.execute(
        select(DocumentPermissionGrant).where(
            DocumentPermissionGrant.document_id == doc.id,
            DocumentPermissionGrant.user_id == user_id,
        )
    ).scalar_one_or_none()
    if grant is None:
        raise NotFoundError("Grant not found.")
    session.delete(grant)
    log_action(
        session, actor=current, action="document.unshared",
        target_type="document", target_id=doc.id,
    )
    session.commit()
