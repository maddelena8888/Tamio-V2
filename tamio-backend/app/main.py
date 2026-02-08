"""Main FastAPI application - Tamio V4."""
import logging
import sys
from contextlib import asynccontextmanager
from typing import Optional

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.asyncio import AsyncioIntegration

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.middleware import DemoGuardMiddleware, setup_rate_limiting
from app.detection.scheduler import setup_apscheduler
from app.database import get_db


# Configure structured logging
def setup_logging():
    """Configure logging for the application."""
    log_level = logging.DEBUG if settings.APP_ENV == "development" else logging.INFO

    # Create formatter
    if settings.APP_ENV == "production":
        # JSON formatter for production (better for Cloud Logging)
        class JsonFormatter(logging.Formatter):
            def format(self, record):
                log_record = {
                    "timestamp": self.formatTime(record, self.datefmt),
                    "level": record.levelname,
                    "name": record.name,
                    "message": record.getMessage(),
                }
                if record.exc_info:
                    log_record["exception"] = self.formatException(record.exc_info)
                import json
                return json.dumps(log_record)
        
        formatter = JsonFormatter(datefmt="%Y-%m-%d %H:%M:%S")
    else:
        # Standard colored/text formatter for dev
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add stdout handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(log_level)
    stdout_handler.setFormatter(formatter)
    root_logger.addHandler(stdout_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)


# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize Sentry
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.APP_ENV,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            AsyncioIntegration(),
        ],
        traces_sample_rate=0.1 if settings.APP_ENV == "production" else 1.0,
        profiles_sample_rate=0.1,
    )
    logger.info("Sentry initialized")

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
        logger.info("Background scheduler started - jobs configured:")
        logger.info("  - Critical detections: every 5 minutes")
        logger.info("  - Routine detections: every hour")
        logger.info("  - Daily detections: 6:00 AM")
        logger.info("  - Xero background sync: every 30 minutes")
        logger.info("  - OAuth state cleanup: every hour")

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


# Global exception handler - catch unhandled exceptions and return proper JSON
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled errors.

    Logs the error and returns a user-friendly JSON response instead of a 500 HTML page.
    """
    logger.error(
        f"Unhandled exception: {exc}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "error_type": type(exc).__name__,
        },
        exc_info=True
    )

    # Don't expose internal error details in production
    if settings.APP_ENV == "development":
        detail = str(exc)
    else:
        detail = "An internal error occurred. Please try again later."

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": detail,
            "path": request.url.path,
        }
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
app.add_middleware(DemoGuardMiddleware)

# Rate limiting
setup_rate_limiting(app)

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
    """Health check endpoint with database verification."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession
    from fastapi import Depends

    # Try to get a DB connection and run a simple query
    try:
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
            return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed - database error: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": str(e)}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
