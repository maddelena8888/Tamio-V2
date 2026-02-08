"""Health metrics schemas - re-exports from consolidated schemas package.

DEPRECATED: Import from app.schemas instead.
"""
from app.schemas.health import (
    HealthRingData,
    ObligationsStatus,
    ReceivablesStatus,
    ObligationsHealthData,
    ReceivablesHealthData,
    HealthMetricsResponse,
)

# Re-export RiskResponse for backward compatibility (was imported from alerts_actions.schemas)
from app.schemas.detection import RiskResponse

__all__ = [
    "HealthRingData",
    "ObligationsStatus",
    "ReceivablesStatus",
    "ObligationsHealthData",
    "ReceivablesHealthData",
    "HealthMetricsResponse",
    "RiskResponse",
]
