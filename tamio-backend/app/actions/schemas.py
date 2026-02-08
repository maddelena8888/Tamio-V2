"""Action schemas - re-exports from consolidated schemas package.

DEPRECATED: Import from app.schemas instead.
"""
from app.schemas.action import (
    ActionOptionResponse,
    EntityLink,
    ActionCardResponse,
    ActionQueueResponse,
    ApproveActionRequest,
    MarkExecutedRequest,
    SkipActionRequest,
    OverrideActionRequest,
    ExecutionArtifactsResponse,
    RecentActivityResponse,
    AgentActivityResponse,
)

# Re-export the model enums that were previously imported here
from app.models.detection import AlertSeverity
from app.models.action import ActionType, ActionStatus, RiskLevel

__all__ = [
    # Enums from models
    "AlertSeverity",
    "ActionType",
    "ActionStatus",
    "RiskLevel",
    # Schemas
    "ActionOptionResponse",
    "EntityLink",
    "ActionCardResponse",
    "ActionQueueResponse",
    "ApproveActionRequest",
    "MarkExecutedRequest",
    "SkipActionRequest",
    "OverrideActionRequest",
    "ExecutionArtifactsResponse",
    "RecentActivityResponse",
    "AgentActivityResponse",
]
