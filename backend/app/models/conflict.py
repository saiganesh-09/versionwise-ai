"""Conflict findings between chunks, plus human review state.

Evidence text is duplicated into the row (evidence_a/evidence_b) so a finding
remains reviewable even if a chunk is later deleted — the FKs use SET NULL.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Enum,
    Float,
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import ConflictStatus, ConflictType

if TYPE_CHECKING:
    from app.models.chunk import Chunk
    from app.models.document import Document
    from app.models.user import User


class Conflict(Base, TimestampMixin):
    __tablename__ = "conflicts"
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_conflict_confidence_range",
        ),
        Index("ix_conflicts_doc_status", "document_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    # Nullable: cross-document conflicts and chunk deletion both allowed
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        index=True,
    )
    chunk_a_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chunks.id", ondelete="SET NULL")
    )
    chunk_b_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chunks.id", ondelete="SET NULL")
    )

    conflict_type: Mapped[ConflictType] = mapped_column(
        Enum(ConflictType, name="conflict_type"), nullable=False
    )
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_a: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_b: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)

    status: Mapped[ConflictStatus] = mapped_column(
        Enum(ConflictStatus, name="conflict_status"),
        default=ConflictStatus.potential,
        nullable=False,
        index=True,
    )
    resolution_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    document: Mapped["Document | None"] = relationship()
    chunk_a: Mapped["Chunk | None"] = relationship(foreign_keys=[chunk_a_id])
    chunk_b: Mapped["Chunk | None"] = relationship(foreign_keys=[chunk_b_id])
    reviewer: Mapped["User | None"] = relationship(foreign_keys=[reviewed_by])
