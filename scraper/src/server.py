"""HireWire Scraper Service.

Long-lived FastAPI service (port 8888) that:
1. Runs scheduled scrapes at configured UTC times (default: 09:00 and 17:00)
2. Accepts HTTP trigger requests for on-demand syncs from the web service

Endpoints:
  GET  /health               - Service status and next scheduled run times
  POST /trigger              - Trigger full sync of all enabled companies
  POST /trigger/company/{id} - Trigger sync for a single company by DB ID

Configuration:
  SCRAPE_SCHEDULE  Comma-separated HH:MM times in UTC (default: "09:00,17:00")
  DATABASE_URL     PostgreSQL connection string (required)

Usage:
  uvicorn scraper.src.server:app --host 0.0.0.0 --port 8888
  python -m scraper.src.server
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import schedule
import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .config import settings
from .main import ScrapeResult, configure_logging, main

log = structlog.get_logger()


class SyncResponse(BaseModel):
    success: bool
    new_jobs: int
    updated_jobs: int
    duration_ms: int
    error: str | None = None
    started_at: str


def result_to_response(result: ScrapeResult) -> SyncResponse:
    return SyncResponse(
        success=result.success,
        new_jobs=result.new_jobs,
        updated_jobs=result.updated_jobs,
        duration_ms=result.duration_ms,
        error=result.error,
        started_at=datetime.now(timezone.utc).isoformat(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Schedule management
# ─────────────────────────────────────────────────────────────────────────────

_scrape_task: asyncio.Task | None = None
_schedule_task: asyncio.Task | None = None


def _setup_schedule() -> None:
    """Register scheduled scrape jobs."""
    for time_str in settings.scrape_schedule_list:
        schedule.every().day.at(time_str).do(_trigger_scheduled_scrape)
        log.info("schedule_registered", time=time_str)


def _trigger_scheduled_scrape() -> None:
    """Called by schedule library (sync context). Submits async task."""
    global _scrape_task
    loop = asyncio.get_event_loop()
    if _scrape_task is not None and not _scrape_task.done():
        log.warning("schedule_scrape_skipped", reason="previous run still in progress")
        return
    _scrape_task = loop.create_task(_run_scheduled_scrape())


async def _run_scheduled_scrape() -> None:
    log.info("scheduled_scrape_starting")
    result = await main()
    if result.success:
        log.info("scheduled_scrape_complete", new_jobs=result.new_jobs)
    else:
        log.error("scheduled_scrape_failed", error=result.error)


async def _schedule_loop() -> None:
    """Poll schedule every 30s for pending jobs."""
    while True:
        schedule.run_pending()
        await asyncio.sleep(30)


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log.info("scraper_service_starting", schedule=settings.scrape_schedule)
    _setup_schedule()
    global _schedule_task
    _schedule_task = asyncio.create_task(_schedule_loop())
    yield
    if _schedule_task:
        _schedule_task.cancel()
    log.info("scraper_service_stopped")


app = FastAPI(
    title="HireWire Scraper Service",
    description="On-demand and scheduled ATS scraper",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
)


@app.get("/health")
async def health() -> dict:
    next_runs = [str(j.next_run) for j in schedule.jobs[:5]]
    return {
        "status": "ok",
        "schedule": settings.scrape_schedule,
        "next_runs": next_runs,
    }


@app.post("/trigger", response_model=SyncResponse)
async def trigger_all() -> SyncResponse:
    """Trigger a full sync of all tracked companies."""
    log.info("on_demand_sync_all")
    result = await main()
    return result_to_response(result)


@app.post("/trigger/company/{company_id}", response_model=SyncResponse)
async def trigger_company(company_id: int) -> SyncResponse:
    """Trigger sync for a single company."""
    log.info("on_demand_sync_company", company_id=company_id)
    result = await main(company_id=company_id)
    if not result.success and result.error and "not found" in (result.error or "").lower():
        raise HTTPException(status_code=404, detail=result.error)
    return result_to_response(result)


def run_service() -> None:
    """Entry point for running the scraper as a service."""
    import uvicorn

    uvicorn.run(
        "scraper.src.server:app",
        host="0.0.0.0",
        port=8888,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run_service()
