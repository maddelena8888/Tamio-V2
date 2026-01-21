"""
Alerts & Actions Schemas - V4 Risk/Controls Architecture

Pydantic schemas for the refactored Alerts & Actions API.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from enum import Enum


class RiskSeverity(str, Enum):
    """Frontend-facing severity levels."""
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"


class RiskStatus(str, Enum):
    """Status of detection alerts."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    PREPARING = "preparing"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ControlState(str, Enum):
    """State of controls in the rail."""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"


class ActionStepOwner(str, Enum):
    """Who is responsible for an action step."""
    TAMIO = "tamio"
    USER = "user"


class ActionStepStatus(str, Enum):
    """Status of an action step."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


# ============================================================================
# Response Schemas
# ============================================================================

class ActionStepResponse(BaseModel):
    """Response schema for an action step."""
    id: str
    title: str
    owner: ActionStepOwner
    status: ActionStepStatus
    order: int
    description: Optional[str] = None


class RejectedSuggestionResponse(BaseModel):
    """Response schema for a rejected control suggestion."""
    id: str
    title: str
    rejected_at: datetime
    reason: Optional[str] = None


class RiskResponse(BaseModel):
    """
    Response schema for a risk card.

    Maps from DetectionAlert with computed labels.
    """
    id: str
    title: str
    severity: RiskSeverity
    detected_at: datetime

    # Due horizon
    deadline: Optional[datetime] = None
    days_until_deadline: Optional[int] = None
    due_horizon_label: str  # "Due today", "Due Friday", "In 5 days"

    # Impact
    cash_impact: Optional[float] = None
    buffer_impact_percent: Optional[float] = None

    # Driver
    primary_driver: str  # e.g., "RetailCo payment 14d overdue"
    detection_type: str

    # Context
    context_bullets: List[str]
    context_data: dict

    # Linked controls
    linked_control_ids: List[str]

    # Status
    status: RiskStatus

    class Config:
        from_attributes = True


class ControlResponse(BaseModel):
    """
    Response schema for a control in the rail.

    Maps from PreparedAction with computed state.
    """
    id: str
    name: str

    # State
    state: ControlState
    state_label: str  # "Pending", "In progress", "Completed", "Needs review"

    # Linked risks
    linked_risk_ids: List[str]

    # What/Why
    action_type: str
    why_it_exists: str

    # Responsibility split
    tamio_handles: List[str]
    user_handles: List[str]

    # Steps
    action_steps: List[ActionStepResponse]

    # Timing
    deadline: Optional[datetime] = None
    created_at: datetime
    approved_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Content
    draft_content: dict
    impact_amount: Optional[float] = None

    # Auditability
    rejected_suggestions: List[RejectedSuggestionResponse] = []

    class Config:
        from_attributes = True


class RisksListResponse(BaseModel):
    """Response schema for list of risks."""
    risks: List[RiskResponse]
    total_count: int


class ControlsListResponse(BaseModel):
    """Response schema for list of controls."""
    controls: List[ControlResponse]
    total_count: int


class ControlsForRiskResponse(BaseModel):
    """Response for controls linked to a risk."""
    controls: List[ControlResponse]


class RisksForControlResponse(BaseModel):
    """Response for risks linked to a control."""
    risks: List[RiskResponse]


# ============================================================================
# Request Schemas
# ============================================================================

class UpdateControlStateRequest(BaseModel):
    """Request to update a control's state."""
    state: ControlState
    notes: Optional[str] = None


class ApproveControlRequest(BaseModel):
    """Request to approve a suggested control."""
    option_id: Optional[str] = None


class RejectControlRequest(BaseModel):
    """Request to reject a suggested control."""
    reason: Optional[str] = None


class CompleteControlRequest(BaseModel):
    """Request to mark a control as completed."""
    external_reference: Optional[str] = None
    notes: Optional[str] = None


class SuccessResponse(BaseModel):
    """Generic success response."""
    success: bool


class ControlUpdateResponse(BaseModel):
    """Response after updating a control."""
    success: bool
    control: ControlResponse
