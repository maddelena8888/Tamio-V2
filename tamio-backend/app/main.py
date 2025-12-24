"""Main FastAPI application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.data import routes as data_routes
from app.forecast import routes as forecast_routes
from app.scenarios import routes as scenario_routes
from app.scenarios.pipeline import routes as pipeline_routes
from app.tami import routes as tami_routes
from app.xero import routes as xero_routes

# Create FastAPI app
app = FastAPI(
    title="Tamio API",
    description="Cash flow forecasting for SMEs - Manual data entry simplified",
    version="0.4.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(data_routes.router, prefix=f"{settings.API_V1_PREFIX}/data", tags=["Data"])
app.include_router(forecast_routes.router, prefix=f"{settings.API_V1_PREFIX}/forecast", tags=["Forecast"])
app.include_router(scenario_routes.router, prefix=f"{settings.API_V1_PREFIX}/scenarios", tags=["Scenarios"])
app.include_router(pipeline_routes.router, prefix=f"{settings.API_V1_PREFIX}/scenarios", tags=["Scenario Pipeline"])
app.include_router(tami_routes.router, prefix=f"{settings.API_V1_PREFIX}/tami", tags=["TAMI"])
app.include_router(xero_routes.router, prefix=f"{settings.API_V1_PREFIX}/xero", tags=["Xero"])


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
