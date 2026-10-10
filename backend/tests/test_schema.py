"""Phase 2 acceptance tests: schema, constraints, temporal rules, pgvector.

Runs against a real Postgres test database (versionwise_test) provisioned by
conftest — the actual Alembic migrations are the thing under test.
"""

from datetime import date

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Chunk,
    Conflict,
    ConflictStatus,
    ConflictType,
    DocumentPermission,
    DocumentPermissionGrant,
    DocumentVersion,
    IngestionStatus,
    VersionStatus,
)
from tests.conftest import make_document, make_user, make_version

EXPECTED_TABLES = {
    "users",
    "documents",
    "document_versions",
    "document_permissions",
    "chunks",
    "conflicts",
    "chat_sessions",
    "chat_messages",
    "source_citations",
    "audit_logs",
}


def test_migrations_create_all_tables(db_engine) -> None:
    tables = set(inspect(db_engine).get_table_names())
    assert EXPECTED_TABLES <= tables


def test_vector_extension_installed(db_engine) -> None:
    with db_engine.connect() as conn:
        ext = conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname='vector'")
        ).scalar()
    assert ext == "vector"


def test_document_and_version_roundtrip(session: Session) -> None:
    owner = make_user(session)
    doc = make_document(session, owner)
    v1 = make_version(
        session,
        doc,
        owner,
        version_number=1,
        effective_from=date(2024, 1, 1),
        effective_until=date(2025, 1, 1),
    )
    v2 = make_version(
        session,
        doc,
        owner,
        version_number=2,
        effective_from=date(2025, 1, 1),
        status=VersionStatus.pending_review,
        supersedes_version_id=v1.id,
    )
    assert v2.supersedes_version_id == v1.id
    assert doc.versions == [v1, v2]  # ordered by version_number


def test_duplicate_version_number_rejected(session: Session) -> None:
    owner = make_user(session)
    doc = make_document(session, owner)
    make_version(session, doc, owner, version_number=1, effective_from=date(2024, 1, 1))
    dupe = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        original_filename="dupe.txt",
        storage_key="test/dupe",
        file_hash="1" * 64,
        effective_from=date(2025, 1, 1),
        uploaded_by=owner.id,
    )
    session.add(dupe)
    with pytest.raises(IntegrityError):
        session.flush()


def test_invalid_interval_rejected(session: Session) -> None:
    owner = make_user(session)
    doc = make_document(session, owner)
    # effective_until == effective_from violates (until must be strictly later)
    v = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        original_filename="x.txt",
        storage_key="test/x",
        file_hash="0" * 64,
        effective_from=date(2025, 6, 1),
        effective_until=date(2025, 6, 1),
        uploaded_by=owner.id,
    )
    session.add(v)
    with pytest.raises(IntegrityError):
        session.flush()


def test_reversed_interval_rejected(session: Session) -> None:
    owner = make_user(session)
    doc = make_document(session, owner)
    v = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        original_filename="x.txt",
        storage_key="test/y",
        file_hash="0" * 64,
        effective_from=date(2025, 6, 1),
        effective_until=date(2024, 6, 1),  # before start
        uploaded_by=owner.id,
    )
    session.add(v)
    with pytest.raises(IntegrityError):
        session.flush()


def test_open_ended_interval_allowed(session: Session) -> None:
    owner = make_user(session)
    doc = make_document(session, owner)
    v = make_version(session, doc, owner, version_number=1, effective_from=date(2024, 1, 1))
    assert v.effective_until is None


def test_chunk_requires_existing_version(session: Session) -> None:
    import uuid as _uuid

    chunk = Chunk(
        version_id=_uuid.uuid4(),  # nonexistent
        chunk_index=0,
        content="orphan",
    )
    session.add(chunk)
    with pytest.raises(IntegrityError):
        session.flush()


def test_duplicate_chunk_index_rejected(session: Session) -> None:
    owner = make_user(session)
    doc = make_document(session, owner)
    v = make_version(session, doc, owner, version_number=1, effective_from=date(2024, 1, 1))
    session.add(Chunk(version_id=v.id, chunk_index=0, content="a"))
    session.add(Chunk(version_id=v.id, chunk_index=0, content="b"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_historical_version_stays_retrievable(session: Session) -> None:
    """A superseded version must still be selectable for past-date queries."""
    owner = make_user(session)
    doc = make_document(session, owner)
    v1 = make_version(
        session,
        doc,
        owner,
        version_number=1,
        effective_from=date(2024, 1, 1),
        effective_until=date(2025, 1, 1),
    )
    v1.status = VersionStatus.superseded
    session.flush()

    as_of = date(2024, 6, 1)
    row = session.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == doc.id,
            DocumentVersion.effective_from <= as_of,
            (DocumentVersion.effective_until.is_(None))
            | (DocumentVersion.effective_until > as_of),
        )
    ).scalar_one()
    assert row.id == v1.id  # half-open interval contains the date


def test_embedding_roundtrip_and_cosine_order(session: Session) -> None:
    owner = make_user(session)
    doc = make_document(session, owner)
    v = make_version(session, doc, owner, version_number=1, effective_from=date(2024, 1, 1))

    near = [1.0] + [0.0] * 1535
    far = [0.0, 1.0] + [0.0] * 1534
    c_near = Chunk(version_id=v.id, chunk_index=0, content="near", embedding=near)
    c_far = Chunk(version_id=v.id, chunk_index=1, content="far", embedding=far)
    session.add_all([c_near, c_far])
    session.flush()

    query = [1.0] + [0.0] * 1535
    rows = session.execute(
        select(Chunk).order_by(Chunk.embedding.cosine_distance(query))
    ).scalars().all()
    assert rows[0].id == c_near.id


def test_permission_grant_unique(session: Session) -> None:
    owner = make_user(session)
    reader = make_user(session)
    doc = make_document(session, owner)
    session.add(
        DocumentPermissionGrant(
            document_id=doc.id, user_id=reader.id, permission=DocumentPermission.read
        )
    )
    session.flush()
    session.add(
        DocumentPermissionGrant(
            document_id=doc.id, user_id=reader.id, permission=DocumentPermission.write
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_document_delete_cascades_versions_and_chunks(session: Session) -> None:
    owner = make_user(session)
    doc = make_document(session, owner)
    v = make_version(session, doc, owner, version_number=1, effective_from=date(2024, 1, 1))
    session.add(Chunk(version_id=v.id, chunk_index=0, content="x"))
    session.flush()

    session.delete(doc)
    session.flush()
    remaining = session.execute(
        select(DocumentVersion).where(DocumentVersion.document_id == doc.id)
    ).scalars().all()
    assert remaining == []


def test_conflict_defaults(session: Session) -> None:
    owner = make_user(session)
    doc = make_document(session, owner)
    v = make_version(session, doc, owner, version_number=1, effective_from=date(2024, 1, 1))
    c1 = Chunk(version_id=v.id, chunk_index=0, content="12 days leave")
    c2 = Chunk(version_id=v.id, chunk_index=1, content="20 days leave")
    session.add_all([c1, c2])
    session.flush()

    conflict = Conflict(
        document_id=doc.id,
        chunk_a_id=c1.id,
        chunk_b_id=c2.id,
        conflict_type=ConflictType.contradictory,
        explanation="Different leave allowances for overlapping period",
        evidence_a=c1.content,
        evidence_b=c2.content,
        confidence=0.8,
    )
    session.add(conflict)
    session.flush()
    assert conflict.status == ConflictStatus.potential
    assert conflict.id is not None


def test_confidence_range_enforced(session: Session) -> None:
    owner = make_user(session)
    doc = make_document(session, owner)
    conflict = Conflict(
        document_id=doc.id,
        conflict_type=ConflictType.contradictory,
        explanation="x",
        evidence_a="a",
        evidence_b="b",
        confidence=1.5,  # > 1.0
    )
    session.add(conflict)
    with pytest.raises(IntegrityError):
        session.flush()


def test_ingestion_status_defaults_to_queued(session: Session) -> None:
    owner = make_user(session)
    doc = make_document(session, owner)
    v = make_version(session, doc, owner, version_number=1, effective_from=date(2024, 1, 1))
    assert v.ingestion_status == IngestionStatus.queued
