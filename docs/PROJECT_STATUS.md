# Project Status

Updated after each phase. Last updated: 2026-10-10.

## Current phase: 10 — API hardening (up next)

## Completed

- [x] Phase 0 — Repository inspected (empty), architecture + plan written.
- [x] Phase 1 — Monorepo foundation: FastAPI backend (health/readiness,
      consistent error envelope, settings validation) + Next.js 16 frontend
      (TS strict, Tailwind, typed API client, backend status indicator).
- [x] Phase 2 — Full schema (10 tables, native PG enums, half-open temporal
      intervals, HNSW cosine index) + Alembic migrations verified on real
      Postgres, upgrade/downgrade/upgrade cycle clean. See
      docs/DATABASE_SCHEMA.md.
- [x] Phase 3 — JWT bearer auth (argon2id hashes), register/login/logout/me,
      roles, permission-filtered document list/detail, audit logging, frontend
      /login page (real credentials, RHF+Zod), scripts/create_user.py for
      role grants.
- [x] Phase 4 — Ingestion pipeline: upload validation (ext + magic bytes +
      size), SHA-256 dedupe, RustFS/local storage adapters, PDF/DOCX/TXT
      parsers w/ page+section metadata, scanned-PDF → explicit OCR failure,
      token-aware chunker (tiktoken), batched pluggable embeddings
      (openai|mock), idempotent reingest.
- [x] Phase 5 — Version lifecycle: approve (requires ingestion completed),
      reject → archived, supersession via approve (same-document, approved-
      only target), manage-permission enforcement, full audit trail,
      history preserved on supersede.
- [x] Phase 6 — Temporal retrieval engine: deterministic intent parsing
      (current/as_of/compare w/ documented midpoint conventions), SQL
      eligibility (visibility + approved/superseded + interval + ingestion
      complete + superseded-vs-approved precedence + ambiguity warnings),
      pgvector top-k, evidence objects, pluggable LLM (openai|mock) with
      grounded JSON contract, citation validation, /chat + session
      persistence. Full spec eval corpus (12→15→20 days, boundary dates,
      future/unapproved exclusion, overlap ambiguity) passes offline.
- [x] Phase 7 — Conflict detection (cross-doc contradictions vs same-doc
      legitimate updates, interval-overlap aware, canonical-pair dedupe,
      no reopen of dismissed/resolved), human review workflow
      (confirm/dismiss/resolve + notes + audit), chat warnings on evidence
      touching open conflicts, /compare paragraph diff endpoint.
- [x] Phase 8+11 — Eval harness: eval/corpus (4 docs, 8 versions, 12 cases),
      app/eval/evaluator + scripts/run_eval.py (dedicated versionwise_eval
      DB, in-process app), dashboard stats + /eval/latest endpoints.
      Real run: all metrics 1.0 (see docs/EVALUATION.md). Also set a real
      RETRIEVAL_SIMILARITY_THRESHOLD floor (0.15) + compare-with-one-date
      intent parsing.
- [x] Phase 9 — Full frontend: shadcn/ui (Base UI variant) + Tailwind 4 +
      Lucide. Landing, /dashboard (stats + open conflicts), /documents
      (search/filter/create), /documents/[id] (version timeline, approve/
      reject, upload w/ effective dates, side-by-side compare diff), /chat
      (as-of date picker, intent badge, evidence citations w/ version +
      effective range + page, conflict warnings), /conflicts (detect +
      expand-evidence + confirm/dismiss/resolve), /settings (public config).
      Auth shell w/ guard + Suspense boundary for Next 16 Cache Components.

## Test results

| Check | Status | Notes |
|---|---|---|
| Backend `ruff check` | ✅ pass | |
| Backend `pytest` | ✅ 3/3 | health, readiness, 404 |
| Backend live `GET /api/v1/health` | ✅ 200 | |
| Backend live `GET /api/v1/health/ready` | ✅ 503 degraded | correct — DB not yet running |
| Frontend `eslint` | ✅ pass | |
| Frontend `tsc --noEmit` | ✅ pass | |
| Frontend `next build` | ✅ pass | static prerender |
| Frontend dev server `GET /` | ✅ 200 | page renders |
| `docker compose up -d` | ✅ pass | postgres healthy, storage up, bucket created |
| pgvector extension | ✅ 0.8.7 | `CREATE EXTENSION vector` verified |
| Backend readiness w/ DB | ✅ 200 ready | end-to-end DB connectivity |
| `alembic upgrade/downgrade/upgrade` | ✅ pass | clean cycle on real Postgres |
| Backend `pytest` (Phase 2) | ✅ 19/19 | constraints, intervals, pgvector, cascades |
| Backend `pytest` (Phase 3) | ✅ 33/33 total | auth flow, 401s, cross-user isolation, admin, role-escalation block |
| Live auth smoke test | ✅ pass | register→login→me→create doc→401 unauth |
| Backend `pytest` (Phase 4) | ✅ 46/46 total | all parsers, scanned-PDF, dedupe, oversize, idempotent reingest |
| Live ingest → RustFS | ✅ pass | upload→version→chunks→object stored in bucket |
| Backend `pytest` (Phase 5) | ✅ 57/57 total | approve/reject/supersede rules, perms, audit, lineage |
| Backend `pytest` (Phase 6) | ✅ 78/78 total | intent parsing, temporal correctness, boundaries, exclusions, ambiguity, citations, isolation, sessions |
| Backend `pytest` (Phase 7) | ✅ 90/90 total | contradiction vs update classification, dedupe, review workflow, chat warnings, compare diff, perms |
| Backend `pytest` (Phase 8) | ✅ 99/99 total | eval harness, dashboard, all metric gates |
| `scripts/run_eval.py` live | ✅ 1.0 all metrics | real eval DB, real pipeline, see docs/EVALUATION.md |

## Known limitations

- No LLM/embedding credentials configured yet; provider adapters not yet built.
- ~~Docker engine cannot start~~ **RESOLVED**: installed WSL 2.7.13 +
  enabled Virtual Machine Platform + reboot. `docker compose up -d` verified:
  postgres healthy, pgvector 0.8.7 enabled, bucket `versionwise-documents`
  created, backend `/health/ready` returns `ready`.
- Object storage dev image changed MinIO → **RustFS** (MinIO stopped
  publishing container images in 2025 — pulls fail on both Hub and quay.io).
- `npm audit` flags 5 high-severity issues — all one transitive chain:
  `braces` (unpatched glob DoS, GHSA-vfj7-8cjw-p6xm) via
  `eslint-config-next → fast-glob → micromatch`. **No upstream fix exists**
  (braces@3.0.3 is latest); `npm audit fix --force` would downgrade
  eslint-config-next 16→14 without removing the package — rejected.
  Dev-tooling only, nothing ships to production. Re-check when
  eslint-config-next/fast-glob update.

## Next up

- Phase 2: database schema + Alembic migrations (documents, versions, chunks,
  conflicts, users, permissions, chat, audit).
