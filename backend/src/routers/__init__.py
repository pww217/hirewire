"""API routers for the HireWire backend."""

from .companies import router as companies_router
from .favorites import router as favorites_router
from .health import router as health_router
from .jobs import router as jobs_router
from .settings import router as settings_router
from .stats import router as stats_router

__all__ = [
    "companies_router",
    "jobs_router",
    "favorites_router",
    "health_router",
    "settings_router",
    "stats_router",
]
