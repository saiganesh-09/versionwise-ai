# VersionWise AI

**Version-aware enterprise document intelligence.** A RAG platform that answers
questions using the document version that was *actually in force* at the time
asked about — not just whatever was uploaded most recently.

> Status: under active development. See `docs/PROJECT_STATUS.md` and
> `docs/IMPLEMENTATION_PLAN.md` for progress.

## The problem

Enterprise AI assistants routinely retrieve outdated policies, conflicting
documents, or rules that weren't valid when a question was asked. VersionWise AI
separates **upload time** from **effective time**, so:

- "What is the *current* leave policy?" → the approved version valid today.
- "What was the allowance in *February 2025*?" → the version valid then.
- "What changed between 2024 and 2026?" → a deterministic diff of the two
  versions, summarized by the LLM — never invented.

Conflicting statements across versions are detected, persisted, and flagged for
human review rather than silently averaged into an answer.

## Stack

| Tier | Tech |
|---|---|
| Frontend | Next.js (App Router), TypeScript strict, Tailwind, shadcn/ui, Recharts |
| Backend | Python 3.13, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2 |
| Data | PostgreSQL 16 + pgvector, S3-compatible object storage (MinIO dev) |
| AI | Pluggable LLM + embedding provider adapters |

## Quickstart

```bash
cp .env.example .env          # fill in values; never commit .env

docker compose up -d          # postgres + minio (Phase 2+)

cd backend
python -m venv .venv && source .venv/Scripts/activate   # Git Bash / Windows
# source .venv/bin/activate                               # macOS/Linux
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

cd ../frontend
npm install
npm run dev                   # http://localhost:3000
```

Health check: `curl http://localhost:8000/api/v1/health`

## Repository layout

```
frontend/    Next.js application
backend/     FastAPI application (app/, migrations/, tests/)
docs/        Architecture, plan, status
scripts/     Utility scripts
docker-compose.yml
.env.example
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md)
- [Project status](docs/PROJECT_STATUS.md)
