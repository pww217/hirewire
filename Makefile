# HireWire Local Development Makefile
# Usage: make help

.PHONY: dev serve install db db-wait backend frontend scrape logs clean stop-dev venv help

# Default target
.DEFAULT_GOAL := help

# =============================================================================
# Configuration
# =============================================================================
DB_URL := postgresql://hirewire:localdev@localhost:5432/hirewire
DOCKER_COMPOSE := docker-compose
VENV := .venv
SYSTEM_PYTHON := $(shell command -v python3.12 || command -v python3.14 || command -v python3)
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

# =============================================================================
# Primary Targets
# =============================================================================

## dev: Start full development environment with hot-reload
dev: db-wait venv
	@command -v npm >/dev/null 2>&1 || { echo "Error: npm not found. Install Node.js first: brew install node"; exit 1; }
	@echo "Starting development servers..."
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:5173"
	@echo ""
	@trap 'make stop-dev' EXIT INT TERM; \
	DATABASE_URL=$(DB_URL) LOG_LEVEL=DEBUG LOG_FORMAT=console ENVIRONMENT=development \
	$(PYTHON) -m uvicorn backend.src.main:app --reload --host 0.0.0.0 --port 8000 & \
	echo $$! > .backend.pid; \
	cd frontend && npm run dev

## serve: Run production-like build via Docker Compose
serve:
	$(DOCKER_COMPOSE) up --build

## serve-detach: Run production-like build in background
serve-detach:
	$(DOCKER_COMPOSE) up --build -d

# =============================================================================
# Individual Services
# =============================================================================

## db: Start PostgreSQL database only
db:
	$(DOCKER_COMPOSE) up -d postgres

## db-wait: Start DB and wait for it to be healthy
db-wait: db
	@echo "Waiting for PostgreSQL to be ready..."
	@until docker exec $$($(DOCKER_COMPOSE) ps -q postgres) pg_isready -U hirewire > /dev/null 2>&1; do \
		sleep 1; \
	done
	@echo "PostgreSQL is ready!"

## backend: Run backend API server only (requires DB running, venv)
backend: venv
	DATABASE_URL=$(DB_URL) LOG_LEVEL=DEBUG LOG_FORMAT=console ENVIRONMENT=development \
	$(PYTHON) -m uvicorn backend.src.main:app --reload --host 0.0.0.0 --port 8000

## frontend: Run frontend dev server only (requires Node.js)
frontend:
	@command -v npm >/dev/null 2>&1 || { echo "Error: npm not found. Install Node.js or use 'make serve' for Docker-based dev."; exit 1; }
	cd frontend && npm run dev

## sync: Run ATS scraper manually (via Docker)
sync:
	$(DOCKER_COMPOSE) --profile scraper run --rm scraper

## sync-local: Run ATS scraper locally (requires DB running, venv)
sync-local: venv
	DATABASE_URL=$(DB_URL) LOG_LEVEL=DEBUG LOG_FORMAT=console \
	$(PYTHON) -m scraper.src.main

# =============================================================================
# Setup & Utilities
# =============================================================================

## venv: Create Python virtual environment
venv: $(VENV)/bin/activate

$(VENV)/bin/activate: requirements.txt
	@echo "Creating virtual environment with $(SYSTEM_PYTHON)..."
	$(SYSTEM_PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@touch $(VENV)/bin/activate

## install: Install all dependencies (Python venv + Node)
install: venv
	@command -v npm >/dev/null 2>&1 || { echo "Warning: npm not found. Skipping frontend deps. Install Node.js for local frontend dev."; exit 0; }
	cd frontend && npm install

## logs: Tail logs from all Docker services
logs:
	$(DOCKER_COMPOSE) logs -f

## clean: Stop all containers and remove volumes
clean: stop-dev
	$(DOCKER_COMPOSE) down -v
	rm -f .backend.pid

## clean-all: Clean everything including venv
clean-all: clean
	rm -rf $(VENV)
	rm -rf frontend/node_modules

## stop-dev: Stop development servers
stop-dev:
	@if [ -f .backend.pid ]; then \
		kill $$(cat .backend.pid) 2>/dev/null || true; \
		rm -f .backend.pid; \
	fi
	@pkill -f "uvicorn backend.src.main" 2>/dev/null || true

## build: Build Docker image without running
build:
	$(DOCKER_COMPOSE) build

## shell: Open shell in web container
shell:
	$(DOCKER_COMPOSE) exec web /bin/bash

## psql: Open PostgreSQL shell
psql:
	$(DOCKER_COMPOSE) exec postgres psql -U hirewire -d hirewire

# =============================================================================
# Help
# =============================================================================

## help: Show this help message
help:
	@echo "HireWire Development Commands (company-first ATS tracker)"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Quick Start:"
	@echo "  make install   # First time setup (creates venv, installs deps)"
	@echo "  make dev       # Start everything with hot-reload"
	@echo ""
	@echo "Targets:"
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## /  /' | column -t -s ':'
