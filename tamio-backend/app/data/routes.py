"""
Data API routes - Combined router that includes all entity-specific routes.

This file provides backward compatibility by creating a combined router
that includes routes from all entity-specific subdirectories.
"""
from fastapi import APIRouter

# Import entity-specific routers
from app.data.users.routes import router as users_router
from app.data.balances.routes import router as balances_router
from app.data.clients.routes import router as clients_router
from app.data.expenses.routes import router as expenses_router
from app.data.events.routes import router as events_router
from app.data.onboarding_routes import router as onboarding_router
from app.data.exchange_rates.routes import router as exchange_rates_router

# Create combined router
router = APIRouter()

# Include all entity routers
router.include_router(users_router)
router.include_router(balances_router)
router.include_router(clients_router)
router.include_router(expenses_router)
router.include_router(events_router)
router.include_router(onboarding_router)
router.include_router(exchange_rates_router, prefix="/exchange-rates", tags=["exchange-rates"])
