"""Document endpoints — every read is permission-filtered in SQL."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.security import CurrentUser
from app.db.session import get_session
from app.models import Document
from app.repositories import documents as doc_repo
from app.schemas.document import (
    DocumentCreateRequest,
    DocumentDetailResponse,
    DocumentResponse,
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
