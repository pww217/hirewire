# HireWire Infrastructure & CI/CD

> Deployment model and CI pipeline for HireWire.

## Contents

- [Overview](#overview)
- [Docker Compose](#docker-compose)
- [Container Image](#container-image)
- [Environment Variables](#environment-variables)
- [Database Migrations](#database-migrations)
- [CI Pipeline](#ci-pipeline)
- [Future: K8s Deployment](#future-k8s-deployment)

---

## Overview

HireWire runs as two Docker containers orchestrated by Docker Compose:

- **postgres** — PostgreSQL 16, initialized from `shared/schema.sql`
- **web** — FastAPI backend + compiled Vue 3 frontend + embedded scraper scheduler (port 8000)

The scraper runs as an embedded scheduler within the `web` container — no separate scraper container is needed.

---

## Docker Compose

```yaml
services:
  postgres:   # PostgreSQL 16, port 5432
  web:        # FastAPI + Vue + embedded scraper, port 8000
```

### Starting everything

```bash
docker-compose up --build   # Build and start all services
docker-compose up -d        # Start in background
docker-compose logs -f      # Tail logs
docker-compose down -v      # Stop and remove volumes
```

### Trigger a manual sync

```bash
# Via make
make sync

# Directly (hits the backend API)
curl -X POST http://localhost:8000/api/companies/sync-all
```

---

## Container Image

A single `Dockerfile` builds the image using a multi-stage build:

1. **frontend-builder** — Node 20-slim, runs `npm install && npm run build`
2. **final** — Python 3.14-slim, installs Python deps, copies built frontend to `/app/static`

The default `CMD` starts the unified API (which also runs the embedded scraper scheduler):
```dockerfile
CMD ["uvicorn", "backend.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Image published to GitHub Container Registry on every push to `main`:
```
ghcr.io/pww217/hirewire:latest
ghcr.io/pww217/hirewire:<git-sha>
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `SCRAPE_SCHEDULE` | No | `09:00,17:00` | Comma-separated UTC times for scheduled scrapes |
| `CORS_ORIGINS` | No | localhost origins | Comma-separated allowed CORS origins |
| `DB_POOL_SIZE` | No | `5` | SQLAlchemy connection pool size |
| `DB_POOL_OVERFLOW` | No | `10` | Max connections above pool size |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FORMAT` | No | `json` | `json` or `console` |
| `ENVIRONMENT` | No | `production` | `development` enables `/docs` and `/redoc` |
| `STALE_JOB_DAYS` | No | `14` | Days before a job not seen in ATS is marked inactive |
| `GLASSDOOR_RATING_STALE_DAYS` | No | `7` | Days before a cached Glassdoor rating is refreshed |

---

## Database Migrations

The schema is initialized from `shared/schema.sql` when the postgres container first starts (Docker mounts it as an init script).

For incremental changes on an existing database, the app runs Alembic migrations automatically on startup. Migrations live in `alembic/versions/`.

```bash
# Generate a new migration
make migration MSG="describe change"

# Apply migrations manually
DATABASE_URL=postgresql://hirewire:localdev@localhost:5432/hirewire \
  python -m alembic upgrade head
```

### Migration history

| Revision | Description |
|----------|-------------|
| `e39303dba4ed` | Baseline schema |
| `a1b2c3d4e5f6` | Split keywords, persist filters |
| `b2c3d4e5f6a7` | Add `excluded_body_keywords` |
| `c3d4e5f6a7b8` | Drop unused `excluded_companies` column |

---

## CI Pipeline

GitHub Actions (`.github/workflows/ci.yaml`) runs on every push to `main` and on pull requests. Delegates to the reusable workflow at `pww217/k3s-home`.

---

## Future: K8s Deployment

K8s deployment is not currently active but is planned. The intended model:

- **Deployment** — `web` container (API + frontend + embedded scraper), standard HTTP ingress
- **PostgreSQL** — external managed instance or in-cluster StatefulSet

The single Docker image handles everything; K8s deployment requires only a standard Deployment manifest.
