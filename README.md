# HireWire

Job search aggregator for finding marketing/SEO/analytics/content roles at startups.

## Structure

```
apps/hirewire/
├── Dockerfile        # Unified multi-stage build
├── Makefile          # Development commands
├── requirements.txt  # Combined Python dependencies
├── backend/          # FastAPI backend
│   └── src/
├── frontend/         # Vue 3 frontend
│   ├── package.json
│   └── src/
├── scraper/          # Job scraping code
│   └── src/
├── shared/
│   └── schema.sql    # PostgreSQL schema
└── docs/             # Design documentation
```

## Quick Start

```bash
# First time setup
make install

# Start development environment (hot-reload)
make dev

# Or use Docker (no local deps needed)
make serve
```

## Development Commands

```bash
make help          # Show all commands

# Primary
make dev           # Full hot-reload dev (DB + backend + frontend)
make serve         # Production-like via Docker Compose

# Individual services
make db            # Start PostgreSQL only
make backend       # Run backend with reload (requires DB)
make frontend      # Run frontend with HMR (requires Node.js)

# Utilities
make scrape        # Run scraper via Docker
make psql          # Open PostgreSQL shell
make logs          # Tail Docker logs
make clean         # Stop containers, remove volumes
```

## Architecture

Single Docker image with two entrypoints:
- **API**: `uvicorn backend.src.main:app` (default)
- **Scraper**: `python -m scraper.src.main`

## Kubernetes Deployment

Deployed via Helm chart using the workload library:
- **Deployment**: API server (uses default CMD)
- **CronJob**: Scraper (overrides CMD, runs every 2 hours)

Image: `ghcr.io/pww217/hirewire:latest`

See `k3s/applications/hirewire/` for configuration.

## Features

- Job aggregation from Indeed, Glassdoor via JobSpy
- Full-text search with comma-separated OR support
- Filter by location, remote, company size, job type
- Favorites and hidden jobs with undo support
- Manual sync trigger from UI
- Search configuration management with multi-country support
- Viewed job tracking (persisted to localStorage)
- Auto-refresh with visibility detection

### Keyboard Shortcuts

Navigate the job list efficiently with keyboard shortcuts:

- `j` / `↓` - Move to next job
- `k` / `↑` - Move to previous job
- `f` - Toggle favorite on selected job
- `h` - Hide selected job (with undo)
- `Enter` - Open job details
- `/` - Focus search input
- `Esc` - Clear selection or close panels

## Documentation

- [Scraping Tools Analysis](docs/scraping-tools.md)
- [Scraper Service Design](docs/scraper-service.md)
- [API Backend Spec](docs/api-backend.md)
- [Frontend Spec](docs/frontend.md)
- [Infrastructure & CI/CD](docs/infra-cicd.md)
