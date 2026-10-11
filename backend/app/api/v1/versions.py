"""Version upload, listing, detail, and re-ingestion endpoints."""

import hashlib
import re
import uuid
from datetime import date
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.core.security import CurrentUser, ForbiddenError
from app.db.session import get_session
from app.ingestion.parsers import ParseError, detect_format
from app.ingestion.pipeline import ingest_version
from app.models import (
    Document,
    DocumentVersion,
    IngestionStatus,
    VersionStatus,
)
from app.repositories import documents as doc_repo
from app.schemas.document import ChunkResponse, DocumentVersionResponse
from app.services.audit import log_action
from app.services.storage import get_storage

router = APIRouter(tags=["versions"])

_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9._\-]")


def _safe_filename(name: str) -> str:
    base = PurePosixPath(name.replace("\\", "/")).name  # strip dirs
    return _UNSAFE_NAME.sub("_", base)[:200] or "file.bin"


def _load_document_for_write(session: Session, user, document_id: uuid.UUID) -> Document:
    """404 for invisible/missing docs; 403 for visible-but-read-only."""
    doc = doc_repo.get_document(session, document_id)
    if doc is None or not doc_repo.get_visible(session, user, document_id):
        raise NotFoundError("Document not found.")
    if not doc_repo.can_write(session, user, doc):
        raise ForbiddenError("You do not have write access to this document.")
    return doc


@router.post(
    "/documents/{document_id}/versions",
    response_model=DocumentVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_version(
    document_id: uuid.UUID,
    current: CurrentUser,
    file: UploadFile = File(...),
    effective_from: date = Form(...),
    effective_until: date | None = Form(default=None),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> DocumentVersion:
    doc = _load_document_for_write(session, current, document_id)

    # Size limit enforced while reading — +1 byte detects overflow.
    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise BadRequestError(
            f"File exceeds the {settings.max_upload_mb} MB upload limit."
        )
    if len(data) == 0:
        raise BadRequestError("Empty file.")
    if effective_until is not None and effective_until <= effective_from:
        raise BadRequestError("effective_until must be after effective_from.")

    filename = _safe_filename(file.filename or "upload")
    try:
        detect_format(filename, data)
    except ParseError as exc:
        raise BadRequestError(str(exc)) from exc
    file_hash = hashlib.sha256(data).hexdigest()

    # Reject byte-identical re-uploads of the same document.
    dupe = session.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == doc.id,
            DocumentVersion.file_hash == file_hash,
        )
    ).scalar_one_or_none()
    if dupe is not None:
        raise ConflictError(
            "This exact file was already uploaded as a version of this document.",
            details={"version_id": str(dupe.id), "version_number": dupe.version_number},
        )

    # Lock the document row so concurrent uploads can't race version numbers.
    locked = session.execute(
        select(Document).where(Document.id == doc.id).with_for_update()
    ).scalar_one()
    next_number = session.execute(
        select(func.coalesce(func.max(DocumentVersion.version_number), 0) + 1).where(
            DocumentVersion.document_id == locked.id
        )
    ).scalar_one()

    version = DocumentVersion(
        document_id=locked.id,
        version_number=next_number,
        original_filename=filename,
        storage_key="",  # set after we have the id
        file_hash=file_hash,
        effective_from=effective_from,
        effective_until=effective_until,
        status=VersionStatus.pending_review,
        ingestion_status=IngestionStatus.queued,
        uploaded_by=current.id,
    )
    session.add(version)
    session.flush()
    version.storage_key = f"documents/{doc.id}/versions/{version.id}/{filename}"
    get_storage(settings).put(version.storage_key, data)

    log_action(
        session,
        actor=current,
        action="version.uploaded",
        target_type="document_version",
        target_id=version.id,
        detail={"document_id": str(doc.id), "version_number": next_number},
    )
    session.commit()

    # Ingest synchronously — status lands completed/failed before we return.
    # (A task queue is a deliberate non-goal for this project's scale.)
    ingest_version(session, version, settings=settings)
    session.refresh(version)
    return version


@router.get(
    "/documents/{document_id}/versions",
    response_model=list[DocumentVersionResponse],
)
def list_versions(
    document_id: uuid.UUID,
    current: CurrentUser,
    session: Session = Depends(get_session),
) -> list[DocumentVersion]:
    if doc_repo.get_visible(session, current, document_id) is None:
        raise NotFoundError("Document not found.")
    return list(
        session.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number)
        ).scalars()
    )


@router.get("/versions/{version_id}", response_model=DocumentVersionResponse)
def get_version(
    version_id: uuid.UUID,
    current: CurrentUser,
    session: Session = Depends(get_session),
) -> DocumentVersion:
    version = session.get(DocumentVersion, version_id)
    if version is None or doc_repo.get_visible(session, current, version.document_id) is None:
        raise NotFoundError("Version not found.")
    return version


@router.get("/versions/{version_id}/chunks", response_model=list[ChunkResponse])
def list_version_chunks(
    version_id: uuid.UUID,
    current: CurrentUser,
    session: Session = Depends(get_session),
) -> list:
    version = session.get(DocumentVersion, version_id)
    if version is None or doc_repo.get_visible(session, current, version.document_id) is None:
        raise NotFoundError("Version not found.")
    from app.models import Chunk

    return list(
        session.execute(
            select(Chunk).where(Chunk.version_id == version_id).order_by(Chunk.chunk_index)
        ).scalars()
    )


@router.post("/versions/{version_id}/reingest", response_model=DocumentVersionResponse)
def reingest_version(
    version_id: uuid.UUID,
    current: CurrentUser,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> DocumentVersion:
    version = session.get(DocumentVersion, version_id)
    if version is None or doc_repo.get_visible(session, current, version.document_id) is None:
        raise NotFoundError("Version not found.")
    doc = doc_repo.get_document(session, version.document_id)
    assert doc is not None
    if not doc_repo.can_write(session, current, doc):
        raise ForbiddenError("You do not have write access to this document.")
    if version.ingestion_status == IngestionStatus.processing:
        raise ConflictError("Ingestion is already running for this version.")
    log_action(
        session,
        actor=current,
        action="version.reingested",
        target_type="document_version",
        target_id=version.id,
    )
    session.commit()
    ingest_version(session, version, settings=settings)
    session.refresh(version)
    return version
