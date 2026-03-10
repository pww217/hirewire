# HireWire

Company-first job tracker. Add the companies you care about, and HireWire polls their ATS job boards (Greenhouse, Lever, Ashby) automatically — twice a day and on demand — displaying all open roles in a single searchable dashboard.

## Structure

```
hirewire/
├── Dockerfile            # Unified multi-stage build (web + scraper)
├── Makefile              # Development commands
├── requirements.txt      # Python dependencies
├── docker-compose.yaml   # Local dev orchestration
├── backend/              # FastAPI backend + Vue frontend (served as static)
│   └── src/
├── frontend/             # Vue 3 + Vite frontend source
│   ├── package.json
│   └── src/
├── scraper/              # ATS scraper service
│   └── src/
├── shared/
│   ├── schema.sql        # PostgreSQL schema
│   └── migrations/       # Incremental schema migrations
└── docs/                 # Design documentation
```

## Quick Start

```bash
# First time setup
make install

# Start everything via Docker (recommended)
make serve

# Or start with hot-reload (requires Node.js locally)
make dev
```

Open http://localhost:8000 — add companies via the + button in the sidebar.

## Development Commands

```bash
make help           # Show all commands

# Primary
make serve          # Run via Docker Compose (web + scraper + postgres)
make dev            # Full hot-reload dev (requires local Node.js + Python venv)

# Individual services
make db             # Start PostgreSQL only
make backend        # Run backend API with reload (requires DB)
make frontend       # Run Vite dev server (requires Node.js)
make scraper-service # Run scraper service locally (scheduled + HTTP triggers)

# Database
make db-migrate     # Apply all pending migrations
make db-reset       # Destroy and recreate DB (DELETES ALL DATA)

# Sync
make sync           # Trigger full sync via running scraper service
make sync-local     # Run scraper once locally (one-shot)

# Utilities
make psql           # Open PostgreSQL shell
make logs           # Tail Docker logs
make clean          # Stop containers, remove volumes
```

## Architecture

Two Docker containers sharing a PostgreSQL database:

```
┌─────────────────────────────────────────────┐
│  web container (:8000)                       │
│  FastAPI API + Vue 3 frontend (static)       │
└──────────────────┬──────────────────────────┘
                   │ HTTP POST /trigger
┌──────────────────▼──────────────────────────┐
│  scraper container (:8888)                   │
│  FastAPI service — scheduled + on-demand     │
│  Polls Greenhouse / Lever / Ashby APIs       │
└──────────────────┬──────────────────────────┘
                   │
         ┌─────────▼─────────┐
         │   PostgreSQL       │
         │   (jobs, companies │
         │    settings, etc.) │
         └───────────────────┘
```

The scraper runs on a schedule (9 AM and 5 PM UTC by default) and also accepts HTTP trigger requests from the web service for on-demand syncs.

## Features

- Add companies by pasting any Greenhouse, Lever, or Ashby career page URL — ATS type and slug are auto-detected
- Per-company and global sync buttons; scheduled sync twice daily
- Master-detail job view with full HTML job descriptions
- Favorites
- Disappearance detection — jobs are marked inactive immediately when they vanish from the ATS feed
- Settings: preferred locations (chip input), included/excluded title keywords, remote-only toggle
- Full-text search across all job listings

## Documentation

- [API Backend](docs/api-backend.md)
- [Frontend](docs/frontend.md)
- [Scraper Service](docs/scraper-service.md)
- [ATS Scraping Tools](docs/scraping-tools.md)
- [Infrastructure & CI/CD](docs/infra-cicd.md)
