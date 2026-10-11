# VersionWise AI — Architecture

## System overview

```mermaid
flowchart LR
    subgraph Client
        UI[Next.js App Router<br/>TypeScript + Tailwind + shadcn/ui]
    end

    subgraph Backend[FastAPI service]
        API[/api/v1 routers/]
        ING[Ingestion service<br/>parse → chunk → embed → index]
        RET[Retrieval engine<br/>temporal intent → eligibility → vector search]
        GEN[Answer generation<br/>evidence-grounded + citation validation]
        CFD[Conflict detection<br/>candidates → classify → review]
        CMP[Version comparison<br/>deterministic diff + LLM summary]
        ADP[Provider adapters<br/>LLM / Embeddings]
    end

    subgraph Data
        PG[(PostgreSQL + pgvector<br/>documents, versions, chunks,<br/>conflicts, users, audit)]
        OBJ[(S3-compatible object store<br/>original files)]
    end

    UI -->|REST /api/v1| API
    API --> ING & RET & CFD & CMP
    RET --> GEN
    ING & GEN & CFD --> ADP
    API & RET & CFD --> PG
    ING --> OBJ
```

## Core principle: two clocks

Every document version carries **effective time** (`effective_from`,
`effective_until`) — when its content is/was actually in force — stored as a
half-open interval `[from, until)` with NULL meaning open-ended. Upload time is
recorded separately (`uploaded_at`). Retrieval always filters on effective time
plus approval status plus permissions *before* semantic ranking.

## Backend module map

```
app/
├── api/v1/            # routers; thin controllers, Pydantic in/out
├── core/              # settings, errors, security, logging
├── db/                # engine, session, base
├── models/            # SQLAlchemy ORM models
├── schemas/           # Pydantic request/response schemas
├── repositories/      # data access; all SQL lives here
├── services/          # business logic (documents, versions, approvals)
├── ingestion/         # parsers (pdf/docx/txt), chunker, embedding pipeline
├── retrieval/         # temporal intent, eligibility, vector search, evidence
├── conflict_detection/# candidate mining, LLM classification, review
└── main.py            # app factory, middleware, exception handlers
```

## Retrieval pipeline (implemented, Phase 6)

1. **Temporal intent parse** — explicit date/range, "current", "compare", or
   default → as-of date. Conventions: bare year → July 1, month+year → 15th,
   ambiguous relatives → default + warning flag.
2. **Eligibility filter (SQL)** — permission + `status IN (approved, superseded)`
   + `ingestion_status='completed'` + half-open interval contains the as-of
   date. Approved beats superseded when both cover the date; overlapping
   *approved* intervals → ambiguity warning, never a silent pick.
3. **Semantic rank** — pgvector cosine over eligible chunks only.
4. **Evidence objects** — chunk + doc title + version + interval + page + score.
5. **Grounded generation** — model answers only from evidence; backend, not the
   model, decides authoritative versions.
6. **Response validation** — every cited chunk must exist in the evidence set
   and pass permission/temporal checks.

## Data flow: ingestion

Upload → validate type/size → SHA-256 hash → object store → parse (page-aware)
→ chunk (heading/paragraph aware, configurable size/overlap) → batch embed →
transactional insert of chunks → version `ingestion_status=completed`.
A version is retrieval-eligible only when `approved` **and** `completed`.
Retries delete-and-rebuild that version's chunks (idempotent).

## Security model

- **AuthN**: JWT bearer tokens (HS256, `SECRET_KEY`, configurable expiry).
  Bearer over httpOnly cookie = no CSRF surface; the trade-off is client-side
  token storage (localStorage) — accepted and revisited before production.
  Passwords: argon2id via pwdlib. Roles never taken from client or token —
  `get_current_user` reloads the user row every request, so deactivated
  accounts lose access immediately even with a live token.
- Backend enforces authZ on every request; document-level permissions joined in
  retrieval SQL — never retrieve-then-filter-in-prompt. Invisible documents
  return 404 (not 403) so existence isn't leaked.
- Uploaded documents are untrusted input: content is delimited in prompts and
  can never override system instructions (prompt-injection defense, Phase 12).
- Secrets only via env vars; `.env` gitignored.
