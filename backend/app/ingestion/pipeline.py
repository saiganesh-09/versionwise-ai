"""Ingestion pipeline: stored file -> parse -> chunk -> embed -> index.

Idempotent by design: a retry deletes and rebuilds the version's chunks, so
re-running can never duplicate rows. A version is retrieval-eligible only when
ingestion_status=completed (and its approval status allows) — a partially
indexed version is never exposed as ready.
"""

import logging

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.ingestion.chunker import chunk_document
from app.ingestion.parsers import ParseError, parse_document
from app.models import Chunk, DocumentVersion, IngestionStatus
from app.services.embeddings import EmbeddingProvider, get_embedding_provider
from app.services.storage import ObjectStorage, get_storage

logger = logging.getLogger(__name__)


class IngestionError(Exception):
    pass


def ingest_version(
    session: Session,
    version: DocumentVersion,
    *,
    storage: ObjectStorage | None = None,
    embedder: EmbeddingProvider | None = None,
    settings: Settings | None = None,
) -> DocumentVersion:
    """Run ingestion synchronously. Status is committed either way so the
    UI can always show the true state."""
    settings = settings or get_settings()
    storage = storage or get_storage(settings)
    embedder = embedder or get_embedding_provider(settings)

    version.ingestion_status = IngestionStatus.processing
    version.extra = {**version.extra, "ingestion_error": None}
    session.commit()

    try:
        data = storage.get(version.storage_key)
        parsed = parse_document(version.original_filename, data)
        chunks = chunk_document(
            parsed,
            max_tokens=settings.chunk_size_tokens,
            overlap_tokens=settings.chunk_overlap_tokens,
        )
        if not chunks:
            raise ParseError("Document produced no chunks.")

        # Wipe any previous attempt's chunks first — retry is rebuild, not append.
        session.execute(delete(Chunk).where(Chunk.version_id == version.id))

        # Batch embeddings; a mid-pipeline failure leaves status=failed below.
        batch = settings.embedding_batch_size
        embeddings: list[list[float]] = []
        for i in range(0, len(chunks), batch):
            embeddings.extend(
                embedder.embed([c.content for c in chunks[i : i + batch]])
            )

        for c, vec in zip(chunks, embeddings, strict=True):
            session.add(
                Chunk(
                    version_id=version.id,
                    chunk_index=c.chunk_index,
                    content=c.content,
                    embedding=vec,
                    page_number=c.page_number,
                    section_title=c.section_title,
                    token_count=c.token_count,
                    content_hash=c.content_hash,
                )
            )

        version.ingestion_status = IngestionStatus.completed
        version.extra = {
            **version.extra,
            "ingestion_error": None,
            "chunk_count": len(chunks),
            "embedding_model": settings.embedding_model,
        }
        session.commit()
        logger.info(
            "Ingested version %s: %d chunks", version.id, len(chunks)
        )
        return version

    except Exception as exc:
        # Sanitized: error type + message only — no stack, no file content.
        version.ingestion_status = IngestionStatus.failed
        version.extra = {
            **version.extra,
            "ingestion_error": f"{type(exc).__name__}: {exc}"[:1000],
        }
        session.commit()
        logger.warning("Ingestion failed for version %s: %s", version.id, exc)
        return version
