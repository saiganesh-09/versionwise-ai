# Database Schema

PostgreSQL 16 + pgvector. Migrations in `backend/migrations/` (Alembic);
apply with `alembic upgrade head` from `backend/`.

## Temporal convention

Every version's validity is a **half-open interval** `[effective_from,
effective_until)` — `effective_from` is inclusive, `effective_until` exclusive,
NULL = open-ended. Enforced by `ck_version_interval_valid`
(`effective_until IS NULL OR effective_until > effective_from`). The retrieval
engine uses the identical predicate.

## Tables

| Table | Purpose | Key constraints |
|---|---|---|
| `users` | Accounts (auth lands Phase 3) | unique email; `role` enum |
| `documents` | Logical document across all revisions | owner `RESTRICT` |
| `document_versions` | **Immutable** revisions | unique `(document_id, version_number)`; interval CHECK; self-FK `supersedes_version_id` |
| `document_permissions` | Per-user grants | unique `(document_id, user_id)` |
| `chunks` | Text + `vector(1536)` embedding | unique `(version_id, chunk_index)`; HNSW cosine index |
| `conflicts` | Detected contradictions + review state | confidence ∈ [0,1]; evidence text denormalized so findings survive chunk deletion |
| `chat_sessions` / `chat_messages` | Conversations | `as_of_date` records resolved temporal intent |
| `source_citations` | Chunk cited by a message | `chunk_id RESTRICT` — citations never dangle |
| `audit_logs` | Append-only admin action log | actor `SET NULL` — audit survives user changes |

## Version lifecycle

`draft → pending_review → approved → superseded → archived`

- **approved** + `ingestion_status=completed` = retrieval-eligible.
- **superseded** stays fully retrievable for historical (as-of-date) queries.
- Chunks and version rows are never mutated in place; re-ingestion rebuilds
  chunks for that version.

## Embedding column

`chunks.embedding` is `vector(1536)` — the dimension is fixed at migration time
from `EMBEDDING_DIMENSIONS` because HNSW indexes require fixed-length vectors.
Changing embedding model/dimension = a new migration (correct, since stored
vectors can't mix dimensions anyway).

## Indexes that matter for retrieval

- `ix_versions_doc_status (document_id, status)`
- `ix_versions_temporal (effective_from, effective_until)`
- `ix_versions_ingestion (ingestion_status)`
- `ix_chunks_embedding_hnsw` — HNSW, `vector_cosine_ops`
- `ix_conflicts_doc_status`, `ix_conflicts_status`
- FK indexes on `document_permissions`, `chat_messages.session_id`,
  `source_citations.message_id`, `audit_logs`
