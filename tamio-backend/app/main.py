"""Main FastAPI application - Tamio V4."""
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.middleware import DemoGuardMiddleware
from app.detection.scheduler import setup_apscheduler

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: Optional[AsyncIOScheduler] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Starts the detection scheduler on startup and shuts it down on shutdown.
    """
    global _scheduler

    # Startup
    if settings.APP_ENV != "test":
        logger.info("Starting detection scheduler...")
        _scheduler = AsyncIOScheduler()
        setup_apscheduler(_scheduler)
        _scheduler.start()
        logger.info("Detection scheduler started - jobs configured:")
        logger.info("  - Critical detections: every 5 minutes")
        logger.info("  - Routine detections: every hour")
        logger.info("  - Daily detections: 6:00 AM")

    yield

    # Shutdown
    if _scheduler:
        logger.info("Shutting down detection scheduler...")
        _scheduler.shutdown(wait=False)
        logger.info("Detection scheduler shut down")

# Core routes
from app.auth import routes as auth_routes
from app.data import routes as data_routes
from app.data.obligations import routes as obligation_routes
from app.forecast import routes as forecast_routes
from app.scenarios import routes as scenario_routes
from app.scenarios.pipeline import routes as pipeline_routes
from app.xero import routes as xero_routes

# V4 routes - Detection, Preparation, Actions, Execution, Notifications
from app.actions import routes as actions_routes
from app.alerts_actions import routes as alerts_actions_routes
from app.engines import routes as engines_routes
from app.data.user_config import routes as user_config_routes
from app.notifications import routes as notification_routes

# TAMI AI Assistant
from app.tami import routes as tami_routes

# Health Metrics Dashboard
from app.health import routes as health_routes

# Seed routes (demo data)
from app.seed import routes as seed_routes

# Create FastAPI app with lifespan
app = FastAPI(
    title="Tamio API",
    description="Treasury operator that removes constant vigilance required to manage cash flow",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Demo account guard - blocks mutations for demo accounts
# TODO: Re-enable before production deployment
# app.add_middleware(DemoGuardMiddleware)

# Include routers
app.include_router(auth_routes.router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["Auth"])
app.include_router(data_routes.router, prefix=f"{settings.API_V1_PREFIX}/data", tags=["Data"])
app.include_router(obligation_routes.router, prefix=f"{settings.API_V1_PREFIX}/data", tags=["Obligations"])
app.include_router(forecast_routes.router, prefix=f"{settings.API_V1_PREFIX}/forecast", tags=["Forecast"])
app.include_router(scenario_routes.router, prefix=f"{settings.API_V1_PREFIX}/scenarios", tags=["Scenarios"])
app.include_router(pipeline_routes.router, prefix=f"{settings.API_V1_PREFIX}/scenarios", tags=["Scenario Pipeline"])
app.include_router(xero_routes.router, prefix=f"{settings.API_V1_PREFIX}/xero", tags=["Xero"])

# V4 routes
app.include_router(actions_routes.router, prefix=f"{settings.API_V1_PREFIX}", tags=["Actions"])
app.include_router(alerts_actions_routes.router, prefix=f"{settings.API_V1_PREFIX}", tags=["Alerts & Actions"])
app.include_router(engines_routes.router, prefix=f"{settings.API_V1_PREFIX}", tags=["Pipeline"])
app.include_router(user_config_routes.router, prefix=f"{settings.API_V1_PREFIX}/data", tags=["User Configuration"])
app.include_router(notification_routes.router, prefix=f"{settings.API_V1_PREFIX}", tags=["Notifications"])

# Seed routes (development/demo)
app.include_router(seed_routes.router, prefix=f"{settings.API_V1_PREFIX}", tags=["Seed Data"])

# TAMI AI Assistant
app.include_router(tami_routes.router, prefix=f"{settings.API_V1_PREFIX}/tami", tags=["TAMI"])

# Health Metrics Dashboard
app.include_router(health_routes.router, prefix=f"{settings.API_V1_PREFIX}/health", tags=["Health"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Tamio API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
