# VersionWise AI

**Version-aware enterprise document intelligence.** A production-oriented RAG
platform that answers questions using the document version *actually in force*
at the time asked about — not whatever was uploaded most recently.

## The problem it solves

Enterprise AI assistants silently retrieve outdated, conflicting, or
historically-invalid policies. VersionWise AI separates **upload time** from
**effective time**:

- *"What is the current leave allowance?"* → the approved version valid today
- *"What was it in February 2025?"* → the version in force then (even if since superseded)
- *"What changed between 2024 and 2026?"* → evidence from both periods + a deterministic diff
- Contradictions across documents are **detected, persisted, and surfaced to
  humans** — never averaged away

## Feature map

- **Versioned documents** — immutable revisions, half-open effective intervals
  `[from, until)`, lifecycle `draft → pending_review → approved → superseded → archived`,
  separate ingestion tracking
- **Temporal retrieval** — deterministic intent parsing (current / as-of /
  compare), SQL-level eligibility (permission + status + interval + ingestion),
  pgvector search, evidence objects → grounded answers with citation validation
- **No fabrication** — insufficient evidence is said out loud; ambiguous dates
  are flagged, not guessed; citations outside retrieved evidence are dropped
- **Conflict detection** — cross-doc contradictions vs same-doc legitimate
  updates, dedupe, human confirm/dismiss/resolve workflow, chat warnings
- **Real app, not a chat box** — dashboard, library, revision timeline,
  upload+approve, side-by-side diff, citation-rich chat, conflict review
- **AuthZ in SQL** — owner / explicit grant / admin; invisible docs return 404
- **Provider-agnostic AI** — OpenAI-compatible or deterministic offline mocks;
  the whole pipeline is testable with zero API keys

## Stack

| Tier | Tech |
|---|---|
| Frontend | Next.js 16 (App Router, Cache Components), TS strict, Tailwind 4, shadcn/ui |
| Backend | Python 3.13, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic 2 |
| Data | PostgreSQL 16 + pgvector (HNSW cosine), RustFS/S3 object storage |
| AI | Pluggable LLM + embedding adapters (`mock` ↔ `openai`) |

## Quickstart

```bash
cp .env.example .env          # dev defaults work out of the box

docker compose up -d          # postgres+pgvector + RustFS

cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows/Git Bash
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000               # :8000/docs

cd ../frontend && npm install && npm run dev            # :3000
```

Then demo data in one shot:

```bash
python ../scripts/seed_demo.py    # demo@versionwise.dev / demo-password-123
```

## Testing & evaluation

```bash
cd backend && pytest            # 105 tests — real Postgres (versionwise_test)
ruff check app tests migrations

python ../scripts/run_eval.py   # full eval on dedicated versionwise_eval DB
```

Latest eval run — **all metrics 1.0** (version selection, answer terms,
citation validity, refusal accuracy, conflict flag rate). Details:
[docs/EVALUATION.md](docs/EVALUATION.md).

## Deployment

**Live frontend**: https://frontend-ion8xnzy3-saiganesh-09s-projects.vercel.app
(auto-deploys on every push to `main`)

Managed path used: **Vercel** (frontend) + **Render Blueprint** (backend +
Postgres 16, `render.yaml` in repo root). Self-contained alternative:
`docker-compose.prod.yml`. Full matrix + checklist:
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Repository layout

```
frontend/    Next.js app — landing + (app): dashboard, documents, chat,
             conflicts, settings
backend/     FastAPI — app/{api,core,db,models,schemas,repositories,services,
             ingestion,retrieval,conflict_detection,eval}, migrations/, tests/
eval/        corpus (synthetic versioned policies) + results
scripts/     create_user.py, run_eval.py, seed_demo.py
docs/        ARCHITECTURE, IMPLEMENTATION_PLAN, PROJECT_STATUS, EVALUATION,
             DEPLOYMENT
docker-compose.yml         dev infra (postgres + RustFS)
docker-compose.prod.yml    self-contained prod stack
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — layers, data model, retrieval pipeline, security
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md) — phase checklist (14/14 done)
- [Project status](docs/PROJECT_STATUS.md) — verification matrix
- [Evaluation](docs/EVALUATION.md) — corpus + measured metrics
- [Deployment](docs/DEPLOYMENT.md) — env matrix + prod checklist

## Development Workflow

This project uses Git branches and pull requests to manage changes safely.
