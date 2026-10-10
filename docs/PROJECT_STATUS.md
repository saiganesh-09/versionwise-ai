# Project Status

Updated after each phase. Last updated: 2026-10-10.

## Current phase: 3 — Auth (up next)

## Completed

- [x] Phase 0 — Repository inspected (empty), architecture + plan written.
- [x] Phase 1 — Monorepo foundation: FastAPI backend (health/readiness,
      consistent error envelope, settings validation) + Next.js 16 frontend
      (TS strict, Tailwind, typed API client, backend status indicator).
- [x] Phase 2 — Full schema (10 tables, native PG enums, half-open temporal
      intervals, HNSW cosine index) + Alembic migrations verified on real
      Postgres, upgrade/downgrade/upgrade cycle clean. See
      docs/DATABASE_SCHEMA.md.

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
