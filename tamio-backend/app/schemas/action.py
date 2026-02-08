"""
Action Queue Schemas - V4 Architecture

Pydantic schemas for the Action Queue API.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from app.models.detection import AlertSeverity
from app.models.action import ActionType, ActionStatus, RiskLevel


class ActionOptionResponse(BaseModel):
    """Response schema for an action option."""
    id: str
    title: str
    description: Optional[str] = None
    risk_level: RiskLevel
    is_recommended: bool
    reasoning: list[str]
    risk_score: Optional[float] = None
    cash_impact: Optional[float] = None
    impact_description: Optional[str] = None
    prepared_content: dict
    success_probability: Optional[float] = None
    display_order: int

    class Config:
        from_attributes = True


class EntityLink(BaseModel):
    """
    Link to an underlying entity (client, expense, etc.) that caused the alert.

    Used to enable navigation from alert cards to the source data.
    """
    entity_type: str  # "client" | "expense" | "obligation" | "vendor"
    entity_id: str
    entity_name: str
    # Frontend route hint (e.g., "/clients" or "/expenses")
    route: str


class ActionCardResponse(BaseModel):
    """
    Response schema for an action card in the queue.

    Maps to the UI card anatomy from the V4 brief.
    """
    id: str
    action_type: ActionType
    status: ActionStatus

    # Urgency (from linked alert or deadline)
    urgency: AlertSeverity

    # Problem section
    problem_summary: str
    problem_context: Optional[str] = None

    # Options
    options: list[ActionOptionResponse]

    # Timing
    created_at: datetime
    deadline: Optional[datetime] = None
    time_remaining: Optional[str] = None  # e.g., "2 days", "4 hours"

    # Linked actions (if any)
    linked_action_ids: list[str] = []

    # Entity links - enables navigation to underlying data
    # Can have multiple if alert involves multiple entities (e.g., late client affecting payroll)
    entity_links: list[EntityLink] = []

    class Config:
        from_attributes = True


class ActionQueueResponse(BaseModel):
    """
    Response schema for the full action queue.

    Organized by urgency tier.
    """
    emergency: list[ActionCardResponse]
    this_week: list[ActionCardResponse]
    upcoming: list[ActionCardResponse]

    # Counts for badges
    emergency_count: int
    this_week_count: int
    upcoming_count: int
    total_count: int


class ApproveActionRequest(BaseModel):
    """Request to approve an action."""
    option_id: Optional[str] = None
    edited_content: Optional[dict] = None


class MarkExecutedRequest(BaseModel):
    """Request to mark an action as executed."""
    external_reference: Optional[str] = None
    notes: Optional[str] = None


class SkipActionRequest(BaseModel):
    """Request to skip an action."""
    reason: Optional[str] = None


class OverrideActionRequest(BaseModel):
    """Request to override an action."""
    reason: Optional[str] = None


class ExecutionArtifactsResponse(BaseModel):
    """Response with execution artifacts."""
    action_type: str
    raw_content: dict
    email: Optional[dict] = None
    payment_batch: Optional[dict] = None
    call: Optional[dict] = None


class RecentActivityResponse(BaseModel):
    """Response for recent execution activity."""
    id: str
    action_id: str
    action_type: str
    method: str
    result: str
    executed_at: datetime
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class AgentActivityResponse(BaseModel):
    """
    Aggregated agent activity statistics for the homepage.

    Shows activity over a configurable time window (default: 24 hours).
    """
    simulations_run: int = 0      # Forecast calculations
    invoices_scanned: int = 0     # Sync events (invoices/payments scanned)
    forecasts_updated: int = 0    # Execution records
    active_agents: int = 0        # Enabled detection rules
