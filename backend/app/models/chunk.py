"""Text chunks with embeddings — every chunk is bound to exactly one
document version, so historical answers can cite historical text."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
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

from app.core.config import get_settings
from app.models.base import Base, uuid_pk

if TYPE_CHECKING:
    from app.models.document import DocumentVersion


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("version_id", "chunk_index", name="uq_version_chunk_index"),
        # HNSW index for cosine similarity — built once data volume justifies it
        # (index creation is in the migration; listed here for autogenerate).
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Dimension comes from EMBEDDING_DIMENSIONS at migration time — HNSW
    # indexes require fixed-length vectors, so changing the embedding model
    # (and its dimension) is itself a migration.
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(get_settings().embedding_dimensions)
    )

    page_number: Mapped[int | None] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(String(500))
    token_count: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    extra: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    version: Mapped["DocumentVersion"] = relationship(back_populates="chunks")
