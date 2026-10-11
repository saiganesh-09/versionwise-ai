"""Seed the dev database with demo data for a UI walkthrough.

Uses the real API in-process: creates demo@example.com, uploads the
eval/corpus (leave 12→15→20 days, travel, security, contradictory
handbook), approves everything, runs conflict detection, and asks a few
questions so the dashboard and chat have real content.

Usage (backend venv active, Docker stack running):
    python ../scripts/run_eval.py   # or directly:
    python ../scripts/seed_demo.py
"""

import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"
CORPUS = REPO_ROOT / "eval" / "corpus" / "corpus.json"

sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)  # .env resolves relative to backend

# Fall back to deterministic mock providers when no real key is configured —
# demo data must seed successfully offline.
if not os.environ.get("EMBEDDING_API_KEY"):
    os.environ["EMBEDDING_PROVIDER"] = "mock"
if not os.environ.get("LLM_API_KEY"):
    os.environ["LLM_PROVIDER"] = "mock"

DEMO_EMAIL = "demo@versionwise.dev"
DEMO_PASSWORD = "demo-password-123"


def main() -> int:
    import argparse

    from app.eval.evaluator import load_corpus, run_case, seed_corpus

    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="Remote backend base URL (seeds via HTTP)")
    args = parser.parse_args()

    if args.url:
        import httpx

        client = httpx.Client(base_url=args.url.rstrip("/"), timeout=60)
        remote = True
    else:
        from alembic import command
        from alembic.config import Config
        from fastapi.testclient import TestClient

        from app.main import create_app

        cfg = Config(str(BACKEND / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND / "migrations"))
        command.upgrade(cfg, "head")
        client = TestClient(create_app())
        remote = False

    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": DEMO_EMAIL,
            "full_name": "Demo User",
            "password": DEMO_PASSWORD,
        },
    )
    if r.status_code not in (201, 409):
        print(f"register failed: {r.status_code} {r.text}")
        return 1
    login = client.post(
        "/api/v1/auth/login",
        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
    )
    if login.status_code != 200 and r.status_code == 409 and not remote:
        # Stale demo account with a different password — reset via ORM.
        from sqlalchemy import select

        from app.core.security import hash_password
        from app.db.session import get_session as _gs
        from app.models import User

        session = next(_gs())
        user = session.execute(
            select(User).where(User.email == DEMO_EMAIL)
        ).scalar_one()
        user.password_hash = hash_password(DEMO_PASSWORD)
        session.commit()
        login = client.post(
            "/api/v1/auth/login",
            json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        )
    if login.status_code != 200:
        print(f"login failed: {login.status_code} {login.text}")
        return 1
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    existing = client.get("/api/v1/documents", headers=headers).json()
    if existing:
        print(f"demo user already has {len(existing)} document(s) — skipping seed")
    else:
        corpus = load_corpus(CORPUS)
        doc_ids = seed_corpus(client, headers, corpus)
        print(f"seeded {len(doc_ids)} documents")

    det = client.post("/api/v1/conflicts/detect", headers=headers, json={})
    print(f"conflict detection: {len(det.json()['findings'])} findings")

    for q in [
        "What is the current annual leave allowance?",
        "What was the annual leave allowance in February 2025?",
        "What changed between 2024 and 2026 for annual leave?",
    ]:
        ans = run_case(client, headers, {"question": q})
        print(f"  asked: {q[:50]}... -> {ans['status']}")

    print(f"\nDone. Sign in as {DEMO_EMAIL} / {DEMO_PASSWORD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
