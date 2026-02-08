"""Detection models - re-exports from consolidated models package.

DEPRECATED: Import from app.models instead.
"""
from app.models.detection import (
    DetectionType,
    AlertSeverity,
    AlertStatus,
    DetectionRule,
    DetectionAlert,
)

__all__ = [
    "DetectionType",
    "AlertSeverity",
    "AlertStatus",
    "DetectionRule",
    "DetectionAlert",
]
