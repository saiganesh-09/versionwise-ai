"""Logical documents and their immutable versions.

Temporal convention: a version is in force over the half-open interval
[effective_from, effective_until) — start inclusive, end exclusive, NULL end
means open-ended. The retrieval engine and every constraint follow this rule.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import (
    DocumentPermission,
    IngestionStatus,
    VersionStatus,
)

if TYPE_CHECKING:
    from app.models.chunk import Chunk
    from app.models.user import User


class Document(Base, TimestampMixin):
    """A logical document across its entire revision history."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = uuid_pk()
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    document_type: Mapped[str] = mapped_column(
        String(100), default="general", nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document",
        order_by="DocumentVersion.version_number",
        cascade="all, delete-orphan",
    )
    permissions: Mapped[list["DocumentPermissionGrant"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    owner: Mapped["User"] = relationship(back_populates="documents")


class DocumentVersion(Base):
    """One immutable revision. Never overwritten — a new upload creates a new
    row; approval/supersession only change `status`."""

    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "version_number", name="uq_document_version_number"
        ),
        CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from",
            name="ck_version_interval_valid",
        ),
        Index("ix_versions_doc_status", "document_id", "status"),
        Index("ix_versions_temporal", "effective_from", "effective_until"),
        Index("ix_versions_ingestion", "ingestion_status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Provenance of the original file
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 hex

    # Effective interval — half-open [from, until)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_until: Mapped[date | None] = mapped_column(Date)

    status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus, name="version_status"),
        default=VersionStatus.draft,
        nullable=False,
    )
    ingestion_status: Mapped[IngestionStatus] = mapped_column(
        Enum(IngestionStatus, name="ingestion_status"),
        default=IngestionStatus.queued,
        nullable=False,
    )

    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    supersedes_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_versions.id", ondelete="SET NULL")
    )

    # Non-searchable extras (parse stats, provenance). Named "metadata" in SQL;
    # `metadata` is reserved on declarative models, hence the attribute rename.
    extra: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="versions")
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )
    supersedes: Mapped["DocumentVersion | None"] = relationship(
        remote_side="DocumentVersion.id", foreign_keys=[supersedes_version_id]
    )


class DocumentPermissionGrant(Base):
    """Per-user access grant; document owner always has implicit manage."""

    __tablename__ = "document_permissions"
    __table_args__ = (
        UniqueConstraint("document_id", "user_id", name="uq_document_user_permission"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission: Mapped[DocumentPermission] = mapped_column(
        Enum(DocumentPermission, name="document_permission"), nullable=False
    )
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="permissions")
    # Two FKs point at users (user_id + granted_by) — pin the join explicitly.
    user: Mapped["User"] = relationship(
        back_populates="permissions", foreign_keys=[user_id]
    )
