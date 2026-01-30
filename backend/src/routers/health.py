"""Health check endpoint."""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas.common import HealthResponse

router = APIRouter(tags=["health"])
log = structlog.get_logger()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Health check endpoint for K8s probes.

    Checks database connectivity and returns overall health status.
    """
    # Check database connection
    db_status = "disconnected"
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        log.warning("health_check_db_failed", error=str(e))
        db_status = "disconnected"

    status = "healthy" if db_status == "connected" else "unhealthy"

    return HealthResponse(
        status=status,
        database=db_status,
        version="0.1.0",
    )
