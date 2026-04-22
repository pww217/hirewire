# HireWire Unified Image
# Single image serving API, frontend, and embedded scraper scheduler
#
# Usage:
#   docker run hirewire   (starts API + scraper scheduler together)

# =============================================================================
# Stage 1: Build frontend
# =============================================================================
FROM node:20-slim@sha256:9e24e50c93b2de3c02962a71c7b6ebe1396b3372016d0918f472eaf627837b59 AS frontend-builder

WORKDIR /app/frontend

# Copy package files first for caching
COPY frontend/package*.json ./
RUN npm install

# Copy frontend source and build
COPY frontend/ ./
RUN npm run build

# =============================================================================
# Stage 2: Python with API + Scraper + Frontend static files
# =============================================================================
FROM python:3.14-slim@sha256:9b9a75b908891c42b7af174dcf3f6534ebcedfc28c874c6281eb452e86470e3e

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend API code (including __init__.py for module imports)
COPY backend/ ./backend/

# Copy scraper code (including __init__.py for module imports)
COPY scraper/ ./scraper/

# Copy Alembic migrations
COPY alembic.ini .
COPY alembic/ ./alembic/

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/frontend/dist ./static

# Run as non-root user
RUN useradd -m -u 1000 app
USER app

# Expose port for API server
EXPOSE 8000

# Default: run API server
CMD ["uvicorn", "backend.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
