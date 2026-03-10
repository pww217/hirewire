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

HireWire runs as three Docker containers orchestrated by Docker Compose:

- **postgres** — PostgreSQL 16, initialized from `shared/schema.sql`
- **web** — FastAPI backend + compiled Vue 3 frontend (port 8000)
- **scraper** — ATS scraper service with HTTP trigger + schedule (port 8888)

Both `web` and `scraper` are built from the same `Dockerfile` using different entrypoint commands.

---

## Docker Compose

```yaml
services:
  postgres:   # PostgreSQL 16, port 5432
  web:        # FastAPI + Vue, port 8000, SCRAPER_URL=http://scraper:8888
  scraper:    # Scraper service, port 8888, SCRAPE_SCHEDULE=09:00,17:00
```

### Starting everything

```bash
docker-compose up --build   # Build and start all services
docker-compose up -d        # Start in background
docker-compose logs -f      # Tail logs
docker-compose down -v      # Stop and remove volumes
```

### Individual services

```bash
# Start only postgres (for local dev)
docker-compose up -d postgres

# Rebuild and restart only the web container
docker-compose build web && docker-compose up -d web

# Rebuild and restart only the scraper
docker-compose build scraper && docker-compose up -d scraper
```

### Trigger a manual sync

```bash
# Via make (hits the scraper service)
make sync

# Directly
curl -X POST http://localhost:8888/trigger
```

---

## Container Image

A single `Dockerfile` builds both services using a multi-stage build:

1. **frontend-build** — Node 20, runs `npm ci && npm run build`
2. **final** — Python 3.12-slim, installs Python deps, copies built frontend to `/app/static`

The default `CMD` starts the web API:
```dockerfile
CMD ["uvicorn", "backend.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

The scraper container overrides the command in `docker-compose.yaml`:
```yaml
command: ["python", "-m", "scraper.src.server"]
```

Image published to GitHub Container Registry on every push to `main`:
```
ghcr.io/pww217/hirewire:latest
ghcr.io/pww217/hirewire:<git-sha>
```

---

## Environment Variables

### Web container

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `SCRAPER_URL` | No | `None` | URL of scraper service for sync triggers |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FORMAT` | No | `json` | `json` or `console` |
| `ENVIRONMENT` | No | `production` | `development` or `production` |

If `SCRAPER_URL` is unset, sync trigger endpoints return 503. The scheduler in the scraper container runs independently regardless.

### Scraper container

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `SCRAPE_SCHEDULE` | No | `09:00,17:00` | Comma-separated UTC times |
| `LOG_LEVEL` | No | `INFO` | Log level |
| `LOG_FORMAT` | No | `json` | Log format |

---

## Database Migrations

The schema is initialized from `shared/schema.sql` when the postgres container first starts (Docker mounts it as an init script).

For incremental changes on an existing database:

```bash
# Apply all migrations
make db-migrate

# Or manually
docker exec -i hirewire-postgres-1 psql -U hirewire -d hirewire \
  < shared/migrations/001_company_first.sql
```

Migration files in `shared/migrations/` are **idempotent** (`IF NOT EXISTS`, `IF EXISTS`) and safe to re-run.

### Current migrations

| File | Description |
|------|-------------|
| `001_company_first.sql` | Adds `company_id` FK to jobs, drops `search_configs` |
| `002_settings_locations.sql` | Replaces `excluded_companies` with `preferred_locations TEXT[]` |
| `003_included_keywords.sql` | Adds `included_keywords TEXT[]` to user_settings |

---

## CI Pipeline

GitHub Actions (`.github/workflows/ci.yaml`) runs on every push to `main` and on pull requests.

### Jobs

```
lint ──────────┐
               ├──► build (push image to GHCR)
typecheck ─────┘
```

**lint** — `ruff check backend/ scraper/`

**typecheck** — `vue-tsc --noEmit` in the `frontend/` directory

**build** — Docker Buildx multi-platform build; pushes `:latest` and `:<sha>` tags on `main` merges; build-only on PRs

### Image tags

| Event | Tags |
|-------|------|
| Push to `main` | `latest`, `<git-sha>` |
| Pull request | `pr-<number>` (build only, not pushed) |

---

## Future: K8s Deployment

K8s deployment is not currently active but is planned. The intended model:

- **Deployment** — `web` container (API + frontend), standard HTTP ingress
- **Deployment** — `scraper` container (long-running service), no ingress needed
- **PostgreSQL** — external managed instance or in-cluster StatefulSet

The single Docker image supports both entrypoints, so K8s deployment requires only a `values.yaml` change for the scraper command override.
