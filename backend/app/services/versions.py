"""Document-version lifecycle transitions.

Rules enforced here (not in the router):
- approve: pending_review → approved; requires ingestion completed, sets
  approver + timestamp, optionally supersedes one earlier version of the
  same document.
- reject: pending_review → archived (versions are immutable — a rework is a
  new upload, not a resurrection).
- Supersession never deletes anything: the superseded row, its file, and its
  chunks stay exactly where they were for historical retrieval.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import DocumentVersion, IngestionStatus, User, VersionStatus
from app.services.audit import log_action


def approve_version(
    session: Session,
    version: DocumentVersion,
    approver: User,
    *,
    supersede_version_id: uuid.UUID | None = None,
    note: str | None = None,
) -> DocumentVersion:
    if version.status != VersionStatus.pending_review:
        raise ConflictError(
            f"Only pending_review versions can be approved (current: {version.status})."
        )
    if version.ingestion_status != IngestionStatus.completed:
        raise ConflictError(
            "Cannot approve a version whose ingestion has not completed "
            f"(current: {version.ingestion_status})."
        )

    superseded: DocumentVersion | None = None
    if supersede_version_id is not None:
        superseded = session.get(DocumentVersion, supersede_version_id)
        if superseded is None or superseded.document_id != version.document_id:
            raise NotFoundError("Version to supersede not found in this document.")
        if superseded.id == version.id:
            raise BadRequestError("A version cannot supersede itself.")
        if superseded.status != VersionStatus.approved:
            raise ConflictError(
                "Only an approved version can be superseded "
                f"(current: {superseded.status})."
            )
        superseded.status = VersionStatus.superseded

    version.status = VersionStatus.approved
    version.approved_by = approver.id
    version.approved_at = datetime.now(UTC)
    version.supersedes_version_id = supersede_version_id
    if note:
        version.extra = {**version.extra, "approval_note": note}

    log_action(
        session,
        actor=approver,
        action="version.approved",
        target_type="document_version",
        target_id=version.id,
        detail={
            "document_id": str(version.document_id),
            "version_number": version.version_number,
            "superseded_version_id": str(supersede_version_id)
            if supersede_version_id
            else None,
        },
    )
    if superseded is not None:
        log_action(
            session,
            actor=approver,
            action="version.superseded",
            target_type="document_version",
            target_id=superseded.id,
            detail={"by_version_id": str(version.id)},
        )
    session.commit()
    return version


def reject_version(
    session: Session,
    version: DocumentVersion,
    reviewer: User,
    *,
    reason: str | None = None,
) -> DocumentVersion:
    if version.status != VersionStatus.pending_review:
        raise ConflictError(
            f"Only pending_review versions can be rejected (current: {version.status})."
        )
    version.status = VersionStatus.archived
    if reason:
        version.extra = {**version.extra, "rejection_reason": reason}
    log_action(
        session,
        actor=reviewer,
        action="version.rejected",
        target_type="document_version",
        target_id=version.id,
        detail={"reason": reason},
    )
    session.commit()
    return version
