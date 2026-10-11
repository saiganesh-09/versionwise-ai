# Evaluation — VersionWise AI

## Corpus

`eval/corpus/` — fully synthetic (no real company data):

| Document | Versions | Coverage |
|---|---|---|
| Employee Leave Policy | 3 | 12 days (2024) → 15 days (2025–2026-03-31) → 20 days (2026-04-01→) |
| Travel Expense Policy | 2 | $50/$150 caps (→2025) → $75/$200 caps (2026→) |
| Security Standard | 2 | 90-day rotation (→2025) → 180-day, 14 chars (2026→) |
| Manager Handbook | 1 | States 10 days — **deliberate contradiction** with Leave Policy |

12 cases: current/historical questions, boundary dates, comparisons,
an out-of-corpus refusal, and a conflict-surfacing question.

## Reproduce

```bash
# Docker Postgres running, backend venv active
cd backend
python ../scripts/run_eval.py
```

Creates and migrates a dedicated `versionwise_eval` database, seeds the
corpus via the real API (upload → ingest → approve), runs every case through
`POST /api/v1/chat`, and writes `eval/results/latest.json`
(served by `GET /api/v1/eval/latest`).

## Results (2026-10-11 run, mock providers)

| Metric | Score | Meaning |
|---|---|---|
| version_selection_accuracy | **1.00** | Expected (document, version) pairs in evidence |
| answer_terms_accuracy | **1.00** | Expected values ("15", "20") present in answer |
| citation_validity | **1.00** | Every cited chunk exists in retrieved evidence |
| refusal_accuracy | **1.00** | Out-of-corpus question → `insufficient_evidence` |
| conflict_flag_rate | **1.00** | Open conflict on evidence → warning surfaced |

Per-case detail: `eval/results/latest.json`.

## Notes and limits

- **Mock providers**: BoW-hash embeddings + extractive mock LLM exercise the
  whole pipeline offline, but real `EMBEDDING_API_KEY`/`LLM_API_KEY` will shift
  ranking quality. The harness accepts any provider via env — rerun with real
  keys before claiming production-quality numbers.
- `answer_terms_accuracy` measures presence of expected tokens, not factual
  correctness — with mock answers it is a retrieval-proximity check; with a
  real LLM it approximates grounded-answer fidelity.
- The conflict case relies on `POST /conflicts/detect` having run (the runner
  does it after seeding). In production, detection runs as part of review
  workflows or scheduled jobs.
