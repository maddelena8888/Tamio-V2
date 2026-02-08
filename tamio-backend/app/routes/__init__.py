"""
Consolidated routes module.

All API routers are exported from this module for centralized access.
Routes remain in their domain directories but are re-exported here.

Usage:
    from app.routes import auth_router, data_router, forecast_router

    # Or import all routers
    from app.routes import ALL_ROUTERS
"""
from typing import List, Tuple
from fastapi import APIRouter

# Core routes
from app.auth.routes import router as auth_router
from app.data.routes import router as data_router
from app.data.obligations.routes import router as obligation_router
from app.forecast.routes import router as forecast_router
from app.scenarios.routes import router as scenario_router
from app.scenarios.pipeline.routes import router as pipeline_router
from app.xero.routes import router as xero_router

# V4 routes - Detection, Preparation, Actions, Execution, Notifications
from app.actions.routes import router as actions_router
from app.alerts_actions.routes import router as alerts_actions_router
from app.engines.routes import router as engines_router
from app.data.user_config.routes import router as user_config_router
from app.notifications.routes import router as notification_router

# TAMI AI Assistant
from app.tami.routes import router as tami_router

# Health Metrics Dashboard
from app.health.routes import router as health_router

# Seed routes (demo data)
from app.seed.routes import router as seed_router


# Router configuration for easy registration
# Each tuple: (router, prefix, tags)
ROUTER_CONFIGS: List[Tuple[APIRouter, str, List[str]]] = [
    # Core routes
    (auth_router, "/auth", ["Auth"]),
    (data_router, "/data", ["Data"]),
    (obligation_router, "/data", ["Obligations"]),
    (forecast_router, "/forecast", ["Forecast"]),
    (scenario_router, "/scenarios", ["Scenarios"]),
    (pipeline_router, "/scenarios", ["Scenario Pipeline"]),
    (xero_router, "/xero", ["Xero"]),
    # V4 routes
    (actions_router, "", ["Actions"]),
    (alerts_actions_router, "", ["Alerts & Actions"]),
    (engines_router, "", ["Pipeline"]),
    (user_config_router, "/data", ["User Configuration"]),
    (notification_router, "", ["Notifications"]),
    # Seed routes
    (seed_router, "", ["Seed Data"]),
    # TAMI
    (tami_router, "/tami", ["TAMI"]),
    # Health
    (health_router, "/health", ["Health"]),
]


def register_all_routes(app, api_prefix: str = "/api/v1") -> None:
    """
    Register all routers with the FastAPI app.

    Args:
        app: FastAPI application instance
        api_prefix: API version prefix (default: /api/v1)
    """
    for router, prefix, tags in ROUTER_CONFIGS:
        full_prefix = f"{api_prefix}{prefix}" if prefix else api_prefix
        app.include_router(router, prefix=full_prefix, tags=tags)


__all__ = [
    # Individual routers
    "auth_router",
    "data_router",
    "obligation_router",
    "forecast_router",
    "scenario_router",
    "pipeline_router",
    "xero_router",
    "actions_router",
    "alerts_actions_router",
    "engines_router",
    "user_config_router",
    "notification_router",
    "tami_router",
    "health_router",
    "seed_router",
    # Config and helper
    "ROUTER_CONFIGS",
    "register_all_routes",
]
