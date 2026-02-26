"""API routers for the HireWire backend."""

from .favorites import router as favorites_router
from .health import router as health_router
from .jobs import router as jobs_router
from .settings import router as settings_router
from .stats import router as stats_router

__all__ = ["jobs_router", "favorites_router", "health_router", "settings_router", "stats_router"]
