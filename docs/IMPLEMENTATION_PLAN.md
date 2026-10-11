# VersionWise AI — Implementation Plan

**Status:** Living document. Updated at the end of every phase.

## Project summary

VersionWise AI is a version-aware RAG (retrieval-augmented generation) platform for
enterprise documents. Its core differentiator: answers are grounded in the document
version that was *valid at the requested point in time*, not merely the most
recently uploaded file. It distinguishes **upload time** (when the system learned
something) from **effective time** (when a rule was actually in force).

## Key design decisions (locked in Phase 0/1)

| Decision | Choice | Rationale |
|---|---|---|
| Repo layout | `frontend/` + `backend/` monorepo | Simple, single deployment per tier |
| Python | 3.13 | Installed locally; supported by FastAPI/SQLAlchemy 2.x/psycopg 3 |
| Frontend | Next.js App Router + TS strict + Tailwind + shadcn/ui | Per spec |
| Database | PostgreSQL 16 + pgvector | Per spec; `pgvector/pgvector` Docker image for dev |
| Object storage | S3-compatible; RustFS in dev via docker-compose | MinIO stopped publishing images (2025); RustFS is the maintained drop-in |
| Temporal model | Half-open interval `[effective_from, effective_until)`; NULL end = open-ended | Unambiguous boundary semantics; indexed range queries |
| LLM/embeddings | Provider adapters behind interfaces; OpenAI-compatible default | Swappable without touching retrieval logic |
| Auth | Session/JWT bearer for API + role-based permissions | Implemented Phase 3; documented then |
| Chunk/version immutability | `document_versions` and `chunks` are immutable once created | Auditability; re-ingestion creates new rows, never mutates |

## Phase checklist

- [x] **Phase 0** — Repo inspection, architecture, this plan
- [x] **Phase 1** — Monorepo foundation: Next.js + FastAPI, health checks, env config, linting, docker-compose
- [x] **Phase 2** — DB schema + Alembic migrations (documents, versions, chunks, conflicts, users, permissions, chat, audit)
- [x] **Phase 3** — AuthN/AuthZ (JWT bearer, argon2id, roles: user / document_manager / admin)
- [x] **Phase 4** — Ingestion pipeline (PDF/DOCX/TXT, page metadata, chunking, batched embeddings, status tracking)
- [x] **Phase 5** — Version management APIs + UI (revisions, approval, supersession, dedupe by hash)
- [x] **Phase 6** — Temporal retrieval engine (intent parsing → eligibility filter → vector search → evidence → grounded answer → citation validation)
- [x] **Phase 7** — Conflict detection engine + human review workflow
- [x] **Phase 8** — Version comparison (deterministic diff + LLM summary) — `GET /compare` ships paragraph-level diffs; shipped with Phase 7
- [x] **Phase 9** — Full frontend (landing, dashboard, library, doc detail, chat, compare, conflicts, settings)
- [x] **Phase 10** — API hardening (versioned routes, consistent errors, pagination, no N+1)
- [x] **Phase 11** — Test suite + eval corpus + metrics (version-selection accuracy, Recall@k, citation correctness) — 99 tests, `eval/corpus`, `run_eval.py`, all metrics 1.0; see docs/EVALUATION.md
- [ ] **Phase 12** — Security & reliability (rate limits, prompt-injection defenses, audit)
- [ ] **Phase 13** — Deployment prep (Vercel + Python host + managed Postgres + object storage)
- [ ] **Phase 14** — README/portfolio polish, screenshots, eval report

## Phase acceptance criteria (summary)

| Phase | Gate to proceed |
|---|---|
| 1 | Frontend + backend start; `/api/v1/health` returns 200; lint/typecheck/pytest pass |
| 2 | Migrations apply clean; constraints tested; invalid intervals rejected |
| 3 | Unauthenticated → 401; cross-user access denied; role tests pass |
| 4 | PDF/DOCX/TXT ingest; page numbers preserved; retry is idempotent; failures visible |
| 5 | Multi-revision docs; historical retrievable; no duplicate version numbers |
| 6 | Date-aware version selection; unapproved/future versions excluded; citations validated; ambiguity flagged |
| 7 | Known contradictions detected; period-separated changes not flagged; dismissals audited |
| 8 | Real diffs highlighted; no phantom changes; LLM summary grounded in diff |
| 9 | End-to-end: upload → version → ask → cite → compare → review |
| 10 | All routes validated; OpenAPI docs; consistent error shape |
| 11 | Boundary tests pass; no auth leaks; metrics measured (not fabricated) |
| 12 | Rate limits, size limits, injection defenses verified |
| 13 | Deployed and smoke-tested, or explicitly marked incomplete |
| 14 | Docs complete with real screenshots/results only |

## Running locally (Phase 1)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Git Bash on Windows
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev                                             # http://localhost:3000

# Infrastructure (Phase 2+)
docker compose up -d postgres storage
```

## Known blockers / open items

- LLM + embedding API keys not yet configured — adapters will be built with
  `LLM_PROVIDER`/`EMBEDDING_PROVIDER` env vars; dev/test paths will work without keys.
- `.env` must be created locally from `.env.example`; never committed.
