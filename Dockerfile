# HireWire Unified Image
# Single image serving API, frontend, and embedded scraper scheduler
#
# Usage:
#   docker run hirewire   (starts API + scraper scheduler together)

# =============================================================================
# Stage 1: Build frontend
# =============================================================================
FROM node:20-slim@sha256:1e85773c98c31d4fe5b545e4cb17379e617b348832fb3738b22a08f68dec30f3 AS frontend-builder

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
FROM python:3.14-slim@sha256:fb83750094b46fd6b8adaa80f66e2302ecbe45d513f6cece637a841e1025b4ca

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
