# Deployment — VersionWise AI

## Environment matrix

| Variable | Dev | Test | Prod |
|---|---|---|---|
| `DATABASE_URL` | localhost compose | `versionwise_test` | managed Postgres (pgvector ≥0.8) |
| `OBJECT_STORAGE_PROVIDER` | `s3` (RustFS) or `local` | `local` | `s3` (RustFS or AWS S3) |
| `EMBEDDING_PROVIDER` / `LLM_PROVIDER` | `mock` ok | `mock` | `openai`/`openai_compatible` |
| `SECRET_KEY` | placeholder | test-only | **32+ random bytes, rotated** |
| `ENVIRONMENT` | `development` | `development` | `production` |

Provider selection is pure env — no code changes between mock and real.

## Option A — self-contained compose (`docker-compose.prod.yml`)

```bash
cp .env.example .env
# edit .env: POSTGRES_PASSWORD, SECRET_KEY (32+ bytes), OBJECT_STORAGE_*,
#            EMBEDDING_API_KEY, LLM_API_KEY, PUBLIC_API_BASE_URL
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

Brings up: postgres+pgvector (internal only), RustFS + bucket init, backend
(migrates on start via `alembic upgrade head`, uvicorn `$WORKERS` workers),
frontend (Next standalone). Ports: `FRONTEND_PORT` (3000), `BACKEND_PORT` (8000).

## Option B — managed services (what production used)

- **Frontend → Vercel**: deployed via `vercel deploy --prod`, Git-connected
  (auto-deploys on push to main; project root = `frontend/`). Live:
  `https://frontend-ion8xnzy3-saiganesh-09s-projects.vercel.app`.
- **Backend → Render Blueprint** (`render.yaml`): connect the repo at
  render.com → New + → Blueprint → Apply. Provisions the web service from
  `backend/Dockerfile` (migrations run on start) + free Postgres 16 with
  `DATABASE_URL` wired via `fromDatabase`. After it deploys, set
  `NEXT_PUBLIC_API_BASE_URL` in Vercel → redeploy → `FRONTEND_ORIGIN` to the
  Vercel URL → `python scripts/seed_demo.py --url <backend-url>` for demo data.
- **Free-tier notes**: Render spins down when idle (~30s cold start); uploads
  are ephemeral without a paid disk; managed Postgres free plan is 90 days.

- **Frontend → Vercel**: import `frontend/`, set `NEXT_PUBLIC_API_BASE_URL`
  to the backend's public HTTPS URL. Zero extra config — standalone output
  isn't used on Vercel.
- **Backend → Render/Fly/Railway**: build from `backend/Dockerfile`. Set all
  env vars; `DATABASE_URL` to managed Postgres **with pgvector** (RDS
  supports pgvector ≥0.8 on PG16; Supabase/Neon include it). S3 for objects
  (`OBJECT_STORAGE_PROVIDER=s3`, leave `OBJECT_STORAGE_ENDPOINT` empty for
  AWS). The container runs migrations on start.
- **HTTPS**: terminate TLS at the platform layer or a reverse proxy;
  `FRONTEND_ORIGIN` must be the exact HTTPS origin for CORS.

## Production checklist

- [ ] `SECRET_KEY` ≥ 32 random bytes (`python -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] `ENVIRONMENT=production` (disables dev conveniences)
- [ ] Real `EMBEDDING_API_KEY` + `LLM_API_KEY` — `mock` returns plausible-but-meaningless text
- [ ] `OBJECT_STORAGE_PROVIDER=s3` — `local` writes inside the container
- [ ] `FRONTEND_ORIGIN` = exact frontend URL (no trailing slash)
- [ ] Rate limits: in-memory is per-replica — with N replicas, effective limit is N×
- [ ] JWT tokens live in `localStorage` — evaluate httpOnly-cookie sessions before public exposure (documented in ARCHITECTURE.md)
- [ ] First admin: `python scripts/create_user.py --email you@co.com --password '…' --role admin`
- [ ] `GET /api/v1/health/ready` returns `ready` post-deploy

## Operational notes

- **Migrations**: run at container start — for zero-downtime deploys keep
  migrations backward-compatible within one release.
- **Rate limiting**: per-process. Multi-replica needs the Redis-backed swap
  noted in `app/core/rate_limit.py`.
- **Storage**: RustFS is dev-grade; AWS S3 is a drop-in via env.
