"""Conflict detection + human review endpoints, and version comparison."""

import difflib
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.conflict_detection.detector import detect_conflicts
from app.core.config import Settings, get_settings
from app.core.errors import BadRequestError, NotFoundError
from app.core.security import CurrentUser, ForbiddenError
from app.db.session import get_session
from app.models import (
    Chunk,
    Conflict,
    ConflictStatus,
    DocumentVersion,
    UserRole,
)
from app.repositories import documents as doc_repo
from app.schemas.conflict import (
    CompareResponse,
    ConflictOut,
    DetectRequest,
    DetectResponse,
    ReviewRequest,
)
from app.services.audit import log_action
from app.services.llm import get_llm_provider

router = APIRouter(tags=["conflicts"])


def _conflict_docs(session: Session, conflict: Conflict) -> set[uuid.UUID]:
    """Documents on both sides of the finding (via the chunks' versions)."""
    docs = set()
    if conflict.document_id:
        docs.add(conflict.document_id)
    for chunk_id in (conflict.chunk_a_id, conflict.chunk_b_id):
        if chunk_id is None:
            continue
        chunk = session.get(Chunk, chunk_id)
        if chunk is None:
            continue
        version = session.get(DocumentVersion, chunk.version_id)
        if version:
            docs.add(version.document_id)
    return docs


def _conflict_visible(session: Session, user, conflict: Conflict) -> bool:
    """User must be able to see BOTH sides — showing one side's evidence to
    someone who can't read the other document would leak its content."""
    if user.role == UserRole.admin:
        return True
    docs = _conflict_docs(session, conflict)
    return bool(docs) and all(
        doc_repo.get_visible(session, user, d) is not None for d in docs
    )


def _conflict_manageable(session: Session, user, conflict: Conflict) -> bool:
    if user.role == UserRole.admin:
        return True
    docs = _conflict_docs(session, conflict)
    return any(
        (d := doc_repo.get_document(session, doc_id)) is not None
        and doc_repo.can_manage(session, user, d)
        for doc_id in docs
    )


@router.post("/conflicts/detect", response_model=DetectResponse)
def run_detection(
    body: DetectRequest,
    current: CurrentUser,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> DetectResponse:
    findings = detect_conflicts(
        session,
        current,
        document_id=body.document_id,
        settings=settings,
        llm=get_llm_provider(settings),
    )
    return DetectResponse(candidates_evaluated=len(findings), findings=findings)


def _chunk_doc_map(
    session: Session, rows: list[Conflict]
) -> dict[uuid.UUID, uuid.UUID]:
    """One query resolving chunk_id → document_id for a whole page."""
    chunk_ids = {
        cid for c in rows for cid in (c.chunk_a_id, c.chunk_b_id) if cid
    }
    if not chunk_ids:
        return {}
    return dict(
        session.execute(
            select(Chunk.id, DocumentVersion.document_id)
            .join(DocumentVersion, Chunk.version_id == DocumentVersion.id)
            .where(Chunk.id.in_(chunk_ids))
        ).all()
    )


@router.get("/conflicts", response_model=list[ConflictOut])
def list_conflicts(
    current: CurrentUser,
    session: Session = Depends(get_session),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[Conflict]:
    stmt = (
        select(Conflict)
        .order_by(Conflict.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status:
        stmt = stmt.where(Conflict.status == status)
    rows = list(session.execute(stmt).scalars())
    if current.role == UserRole.admin or not rows:
        return rows

    # Batched visibility — no per-row session.get.
    chunk_to_doc = _chunk_doc_map(session, rows)
    doc_visibility: dict[uuid.UUID, bool] = {}

    def docs_of(c: Conflict) -> set[uuid.UUID]:
        docs = {c.document_id} if c.document_id else set()
        docs.update(
            d
            for d in (
                chunk_to_doc.get(c.chunk_a_id), chunk_to_doc.get(c.chunk_b_id)
            )
            if d
        )
        return docs

    def visible(c: Conflict) -> bool:
        docs = docs_of(c)
        return bool(docs) and all(
            doc_visibility.setdefault(
                d, doc_repo.get_visible(session, current, d) is not None
            )
            for d in docs
        )

    return [c for c in rows if visible(c)]


@router.get("/conflicts/{conflict_id}", response_model=ConflictOut)
def get_conflict(
    conflict_id: uuid.UUID,
    current: CurrentUser,
    session: Session = Depends(get_session),
) -> Conflict:
    conflict = session.get(Conflict, conflict_id)
    if conflict is None or not _conflict_visible(session, current, conflict):
        raise NotFoundError("Conflict not found.")
    return conflict


@router.post("/conflicts/{conflict_id}/review", response_model=ConflictOut)
def review_conflict(
    conflict_id: uuid.UUID,
    body: ReviewRequest,
    current: CurrentUser,
    session: Session = Depends(get_session),
) -> Conflict:
    conflict = session.get(Conflict, conflict_id)
    if conflict is None or not _conflict_visible(session, current, conflict):
        raise NotFoundError("Conflict not found.")
    if not _conflict_manageable(session, current, conflict):
        raise ForbiddenError("You need manage access to review this conflict.")

    mapping = {
        "confirm": ConflictStatus.confirmed,
        "dismiss": ConflictStatus.dismissed,
        "resolve": ConflictStatus.resolved,
    }
    conflict.status = mapping[body.action]
    conflict.resolution_note = body.note
    conflict.reviewed_by = current.id
    log_action(
        session,
        actor=current,
        action=f"conflict.{body.action}ed",
        target_type="conflict",
        target_id=conflict.id,
        detail={"note": body.note},
    )
    session.commit()
    return conflict


@router.get("/compare", response_model=CompareResponse)
def compare_versions(
    version_a_id: uuid.UUID,
    version_b_id: uuid.UUID,
    current: CurrentUser,
    session: Session = Depends(get_session),
) -> CompareResponse:
    """Paragraph-level diff between two versions of a document."""
    va = session.get(DocumentVersion, version_a_id)
    vb = session.get(DocumentVersion, version_b_id)
    if va is None or vb is None:
        raise NotFoundError("Version not found.")
    for v in (va, vb):
        if doc_repo.get_visible(session, current, v.document_id) is None:
            raise NotFoundError("Version not found.")
    if va.document_id != vb.document_id:
        raise BadRequestError("Versions belong to different documents.")

    def text_of(v: DocumentVersion) -> list[str]:
        return [
            c.content
            for c in session.execute(
                select(Chunk)
                .where(Chunk.version_id == v.id)
                .order_by(Chunk.chunk_index)
            ).scalars()
        ]

    lines_a, lines_b = text_of(va), text_of(vb)
    matcher = difflib.SequenceMatcher(None, lines_a, lines_b, autojunk=False)
    added: list[str] = []
    removed: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("delete", "replace"):
            removed.extend(lines_a[i1:i2])
        if tag in ("insert", "replace"):
            added.extend(lines_b[j1:j2])

    meta = lambda v: {  # noqa: E731
        "id": str(v.id),
        "version_number": v.version_number,
        "effective_from": v.effective_from.isoformat(),
        "effective_until": v.effective_until.isoformat() if v.effective_until else None,
        "status": v.status.value,
    }
    return CompareResponse(
        version_a=meta(va),
        version_b=meta(vb),
        added=added,
        removed=removed,
        changed_hint=bool(added or removed),
    )
