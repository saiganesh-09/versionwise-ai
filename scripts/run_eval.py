"""Reproducible evaluation run for VersionWise AI.

Creates/migrates a dedicated `versionwise_eval` database, spins up the app
in-process (TestClient), seeds eval/corpus, runs every case through /chat,
scores results, and writes:

  eval/results/latest.json   — machine-readable report
  eval/results/<timestamp>.json

Usage (from backend/, venv active, Docker Postgres running):
    python ../scripts/run_eval.py
"""

import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"
RESULTS = REPO_ROOT / "eval" / "results"
CORPUS = REPO_ROOT / "eval" / "corpus" / "corpus.json"

# Env BEFORE any app import — dedicated eval DB, offline providers.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://versionwise:versionwise@localhost:5432/versionwise_eval",
)
os.environ.setdefault("OBJECT_STORAGE_PROVIDER", "local")
os.environ.setdefault(
    "LOCAL_STORAGE_DIR", str(REPO_ROOT / ".local-storage" / "eval")
)
os.environ.setdefault("EMBEDDING_PROVIDER", "mock")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault(
    "SECRET_KEY", os.environ.get("SECRET_KEY", "eval-only-secret-key-0123456789abcdef")
)

sys.path.insert(0, str(BACKEND))


def ensure_database(url: str) -> None:
    """Create versionwise_eval if it doesn't exist (connects to 'versionwise')."""
    import psycopg
    from sqlalchemy.engine.url import make_url

    u = make_url(url)
    admin_dsn = (
        f"postgresql://{u.username}:{u.password}"
        f"@{u.host}:{u.port or 5432}/versionwise"
    )
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (u.database,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{u.database}"')
            print(f"created database {u.database}")


def migrate() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    command.upgrade(cfg, "head")


def main() -> int:
    from fastapi.testclient import TestClient

    from app.eval.evaluator import evaluate, load_corpus
    from app.main import create_app

    ensure_database(os.environ["DATABASE_URL"])
    migrate()

    client = TestClient(create_app())
    email = f"eval-{int(time.time())}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Eval Runner", "password": "eval-pass-123"},
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "eval-pass-123"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    corpus = load_corpus(CORPUS)
    report = evaluate(client, headers, corpus)

    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (RESULTS / f"{stamp}.json").write_text(json.dumps(report, indent=2))
    (RESULTS / "latest.json").write_text(json.dumps(report, indent=2))

    m = report["metrics"]
    print(f"\n=== Eval: {report['corpus']} — {report['totals']['cases']} cases ===")
    for k, v in m.items():
        print(f"  {k:30} {v if v is None else round(v, 3)}")
    fails = [c["case_id"] for c in report["cases"] if not c["status_ok"]]
    if fails:
        print(f"  WRONG-STATUS cases: {fails}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
