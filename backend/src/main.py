"""HireWire API Backend - Main FastAPI application.

This module sets up the FastAPI application with:
- CORS configuration
- Static file serving (compiled Vue 3 frontend)
- API routers: health, companies, jobs, favorites, settings, stats
- Database lifecycle management (SQLAlchemy async engine)
- Structured logging with structlog
- Embedded scraper scheduler (runs on configured schedule)

Run with:
    DATABASE_URL="postgresql://..." uvicorn backend.src.main:app --reload
"""

import asyncio
import logging
import os
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
import schedule
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .routers import (
    companies_router,
    favorites_router,
    health_router,
    jobs_router,
    settings_router,
    stats_router,
)

# Wire up stdlib logging so structlog's filter_by_level actually takes effect
logging.basicConfig(
    format="%(message)s",
    stream=sys.stdout,
    level=settings.log_level,
)
# Silence noisy libraries at WARNING unless debug mode
for _noisy in ("sqlalchemy.engine", "alembic", "uvicorn.access"):
    logging.getLogger(_noisy).setLevel(
        logging.DEBUG if settings.log_level == "DEBUG" else logging.WARNING
    )

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        (
            structlog.processors.JSONRenderer()
            if settings.log_format == "json"
            else structlog.dev.ConsoleRenderer()
        ),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with method, path, status, and duration.

    Skips GET /health to avoid health-check spam in logs.
    Uses warning level for 4xx, error for 5xx.
    """

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        # Skip health check to avoid log spam
        if request.url.path == "/health" and request.method == "GET":
            return response

        status = response.status_code
        kwargs = dict(
            method=request.method,
            path=request.url.path,
            status_code=status,
            duration_ms=duration_ms,
        )
        if status >= 500:
            log.error("http_request", **kwargs)
        elif status >= 400:
            log.warning("http_request", **kwargs)
        else:
            log.info("http_request", **kwargs)

        return response

# ─────────────────────────────────────────────────────────────────────────────
# Scraper scheduler
# ─────────────────────────────────────────────────────────────────────────────

_scrape_task: asyncio.Task | None = None
_schedule_task: asyncio.Task | None = None


def _setup_schedule() -> None:
    for time_str in settings.scrape_schedule_list:
        schedule.every().day.at(time_str).do(_trigger_scheduled_scrape)
        log.info("schedule_registered", time=time_str)


def _trigger_scheduled_scrape() -> None:
    global _scrape_task
    loop = asyncio.get_event_loop()
    if _scrape_task is not None and not _scrape_task.done():
        log.warning("schedule_scrape_skipped", reason="previous run still in progress")
        return
    _scrape_task = loop.create_task(_run_scheduled_scrape())


async def _run_scheduled_scrape() -> None:
    from scraper.src.main import main as scraper_main
    log.info("scheduled_scrape_starting")
    result = await scraper_main()
    if result.success:
        log.info("scheduled_scrape_complete", new_jobs=result.new_jobs)
    else:
        log.error("scheduled_scrape_failed", error=result.error)


async def _schedule_loop() -> None:
    while True:
        schedule.run_pending()
        await asyncio.sleep(30)


async def _get_db_revision() -> str | None:
    """Get the current alembic revision from the DB using asyncpg.

    Called from the async lifespan context (not from a thread), so no asyncio.run() needed.
    """
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    try:
        conn = await asyncpg.connect(dsn)
        try:
            rows = await conn.fetch("SELECT version_num FROM alembic_version LIMIT 1")
            return rows[0]["version_num"] if rows else None
        finally:
            await conn.close()
    except Exception:
        return None


def _run_migrations() -> None:
    """Run alembic upgrade head via subprocess.

    Using a subprocess avoids asyncio/uvloop conflicts that arise when Alembic's
    own asyncio.run() is called from within a thread executor in a uvloop context.
    """
    project_root = Path(__file__).parent.parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(project_root)},
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "alembic upgrade failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    log.info("app_starting", environment=settings.environment)

    # Apply database migrations before accepting traffic
    try:
        log.info("database_migration_starting")
        # Run Alembic upgrade in a thread (it uses its own event loop internally)
        await asyncio.get_event_loop().run_in_executor(None, _run_migrations)
        # Capture current revision after upgrade to log status
        to_rev = await _get_db_revision()
        log.info("database_migration_complete", revision=to_rev)
    except Exception as e:
        log.error("database_migration_failed", error=str(e), exc_info=True)
        raise

    # Start scraper scheduler
    _setup_schedule()
    global _schedule_task
    _schedule_task = asyncio.create_task(_schedule_loop())

    yield

    # Shutdown
    if _schedule_task:
        _schedule_task.cancel()
    from .database import engine
    await engine.dispose()
    log.info("app_shutdown")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="HireWire API",
        description="Company-first job tracker API",
        version="0.2.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
    )

    # Access logging middleware (registered first = outermost = runs last on response)
    app.add_middleware(AccessLogMiddleware)

    # CORS middleware - allow frontend dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite dev server
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Catch-all exception handler for unhandled errors."""
        log.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=True,
        )

        if settings.environment != "production":
            return JSONResponse(status_code=500, content={"detail": str(exc)})

        # In production, map known exception types to actionable messages
        import sqlalchemy.exc
        if isinstance(exc, sqlalchemy.exc.OperationalError):
            detail = "Database connection error — please try again shortly"
        elif isinstance(exc, TimeoutError):
            detail = "The request timed out — please try again"
        elif isinstance(exc, PermissionError):
            detail = "Permission denied"
        else:
            detail = "An unexpected error occurred"

        return JSONResponse(status_code=500, content={"detail": detail})

    # Include API routers
    app.include_router(health_router)
    app.include_router(companies_router)
    app.include_router(jobs_router, prefix="/api")
    app.include_router(favorites_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    app.include_router(stats_router, prefix="/api")

    # Static file serving for Vue frontend
    # In Docker, frontend is built and copied to /app/static
    # Path: backend/src/main.py -> backend/src -> backend -> /app -> /app/static
    static_dir = Path(__file__).parent.parent.parent / "static"

    if static_dir.exists():
        # Serve assets directory
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount(
                "/assets", StaticFiles(directory=str(assets_dir)), name="assets"
            )

        # Serve index.html for root and SPA routes
        @app.get("/")
        async def serve_index():
            """Serve Vue frontend index.html."""
            index_path = static_dir / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
            return {"message": "HireWire API", "docs": "/docs"}

        # Catch-all for SPA routes - must be last
        @app.get("/{path:path}")
        async def serve_spa(path: str):
            """Serve SPA routes - fallback to index.html for client-side routing."""
            # Skip API routes
            if path.startswith("api/") or path.startswith("docs") or path.startswith("redoc"):
                return JSONResponse(status_code=404, content={"detail": "Not found"})

            # Try to serve static file
            file_path = static_dir / path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)

            # Fallback to index.html for SPA routing
            index_path = static_dir / "index.html"
            if index_path.exists():
                return FileResponse(index_path)

            return JSONResponse(status_code=404, content={"detail": "Not found"})
    else:
        # No static files - just serve API info at root
        @app.get("/")
        async def api_info():
            """API information when no frontend is deployed."""
            return {
                "name": "HireWire API",
                "version": "0.1.0",
                "docs": "/docs",
            }

    return app


# Create the application instance
app = create_app()
