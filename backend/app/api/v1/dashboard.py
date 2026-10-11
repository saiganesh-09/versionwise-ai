"""Dashboard stats + latest eval report endpoints."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import CurrentUser
from app.db.session import get_session
from app.models import (
    ChatSession,
    Chunk,
    Conflict,
    ConflictStatus,
    Document,
    DocumentVersion,
    IngestionStatus,
)
from app.repositories import documents as doc_repo

router = APIRouter(tags=["dashboard"])

_EVAL_LATEST = Path(__file__).resolve().parents[4] / "eval" / "results" / "latest.json"


@router.get("/dashboard/stats")
def dashboard_stats(
    current: CurrentUser, session: Session = Depends(get_session)
) -> dict:
    """Permission-scoped counts: regular users see their visible docs only,
    admins see the whole tenant."""
    # Ids only — never materialize document objects just to count children.
    visible_ids = doc_repo.visible_document_ids(session, current)
    docs = session.execute(
        select(func.count()).select_from(Document).where(Document.id.in_(visible_ids))
    ).scalar_one()
    versions = session.execute(
        select(func.count())
        .select_from(DocumentVersion)
        .where(DocumentVersion.document_id.in_(visible_ids))
    ).scalar_one()
    version_ids = select(DocumentVersion.id).where(
        DocumentVersion.document_id.in_(visible_ids)
    )
    chunks = session.execute(
        select(func.count()).select_from(Chunk).where(Chunk.version_id.in_(version_ids))
    ).scalar_one()
    failed = session.execute(
        select(func.count())
        .select_from(DocumentVersion)
        .where(
            DocumentVersion.document_id.in_(visible_ids),
            DocumentVersion.ingestion_status == IngestionStatus.failed,
        )
    ).scalar_one()
    by_status = dict(
        session.execute(
            select(DocumentVersion.status, func.count())
            .where(DocumentVersion.document_id.in_(visible_ids))
            .group_by(DocumentVersion.status)
        ).all()
    )
    open_conflicts = session.execute(
        select(func.count()).select_from(Conflict).where(
            Conflict.status.in_([ConflictStatus.potential, ConflictStatus.confirmed])
        )
    ).scalar_one()
    my_sessions = session.execute(
        select(func.count()).select_from(ChatSession).where(
            ChatSession.user_id == current.id
        )
    ).scalar_one()
    return {
        "documents": docs,
        "versions": versions,
        "chunks": chunks,
        "versions_by_status": {k.value if k else "unknown": v for k, v in by_status.items()},
        "ingestion_failures": failed,
        "open_conflicts": open_conflicts,
        "my_chat_sessions": my_sessions,
    }


@router.get("/eval/latest")
def eval_latest(current: CurrentUser) -> dict:
    """Latest eval report written by scripts/run_eval.py."""
    if not _EVAL_LATEST.exists():
        return {"status": "no_report", "detail": "Run scripts/run_eval.py first."}
    return json.loads(_EVAL_LATEST.read_text(encoding="utf-8"))
