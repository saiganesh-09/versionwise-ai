import os
import uuid
from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.main import create_app
from app.models import Document, DocumentVersion, User, VersionStatus

TEST_DB_NAME = "versionwise_test"


@pytest.fixture(scope="session")
def client(db_url: str) -> Iterator[TestClient]:
    """API client bound to the migrated test database."""
    from app.db.session import get_session

    engine = create_engine(db_url)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_session() -> Iterator[Session]:
        s = TestingSession()
        try:
            yield s
        finally:
            s.close()

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    engine.dispose()


def _admin_url() -> str | None:
    settings = get_settings()
    if settings.database_url is None:
        return None
    return str(settings.database_url)


def _test_url() -> str:
    admin = _admin_url()
    assert admin is not None
    return admin.rsplit("/", 1)[0] + f"/{TEST_DB_NAME}"


@pytest.fixture(scope="session")
def db_url() -> str:
    """Provision a fresh test database and run the real Alembic migrations.

    Skips the whole module cleanly when no database is reachable (e.g. CI
    without docker-compose), rather than erroring.
    """
    admin = _admin_url()
    if admin is None:
        pytest.skip("DATABASE_URL not configured")
    engine = create_engine(admin, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
            conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    except OperationalError:
        engine.dispose()
        pytest.skip("database not reachable")
    engine.dispose()

    # Run real migrations — this is the migration test.
    from alembic import command
    from alembic.config import Config

    os.environ["ALEMBIC_DATABASE_URL"] = _test_url()
    try:
        cfg = Config("alembic.ini")
        command.upgrade(cfg, "head")
    finally:
        os.environ.pop("ALEMBIC_DATABASE_URL", None)
    return _test_url()


@pytest.fixture(scope="session")
def db_engine(db_url: str) -> Iterator[Engine]:
    engine = create_engine(db_url)
    yield engine
    engine.dispose()


@pytest.fixture()
def session(db_engine: Engine) -> Iterator[Session]:
    """Transaction-scoped session; rolled back after each test."""
    conn = db_engine.connect()
    trans = conn.begin()
    maker = sessionmaker(bind=conn, expire_on_commit=False)
    sess = maker()
    try:
        yield sess
    finally:
        sess.close()
        if trans.is_active:  # a failed flush may have already rolled it back
            trans.rollback()
        conn.close()


@pytest.fixture()
def commit_session(db_engine: Engine) -> Iterator[Session]:
    """Session that really commits — for seeding data API endpoints must see
    (the per-test `session` fixture rolls back)."""
    sess = sessionmaker(bind=db_engine, expire_on_commit=False)()
    try:
        yield sess
    finally:
        sess.close()


# --- Row factories -------------------------------------------------------


def make_user(session: Session, email: str | None = None, **kw) -> User:
    user = User(
        email=email or f"u-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Test User",
        **kw,
    )
    session.add(user)
    session.flush()
    return user


def make_document(session: Session, owner: User, title: str = "Test Doc") -> Document:
    doc = Document(title=title, owner_id=owner.id)
    session.add(doc)
    session.flush()
    return doc


def make_version(
    session: Session,
    document: Document,
    uploader: User,
    *,
    version_number: int,
    effective_from: date,
    effective_until: date | None = None,
    status: VersionStatus = VersionStatus.approved,
    **kw,
) -> DocumentVersion:
    v = DocumentVersion(
        document_id=document.id,
        version_number=version_number,
        original_filename=f"v{version_number}.txt",
        storage_key=f"test/{document.id}/v{version_number}-{uuid.uuid4().hex[:6]}",
        file_hash=uuid.uuid4().hex,
        effective_from=effective_from,
        effective_until=effective_until,
        status=status,
        uploaded_by=uploader.id,
        **kw,
    )
    session.add(v)
    session.flush()
    return v
