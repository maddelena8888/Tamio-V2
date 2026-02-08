"""
Pydantic schemas for AI reconciliation feature.

These schemas support the reconciliation workflow:
- AI suggestions for matching unreconciled payments to schedules
- Bulk operations for approving/rejecting suggestions
- Forecast impact calculations
- Auto-approve configuration
"""
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime

from app.schemas.obligation import (
    PaymentEventResponse,
    ObligationScheduleResponse,
    ObligationAgreementResponse,
)


# ============================================
# Reconciliation Suggestion Schemas
# ============================================

class ReconciliationSuggestion(BaseModel):
    """AI-generated suggestion for matching a payment to a schedule."""

    id: str = Field(..., description="Unique suggestion ID")
    payment_id: str = Field(..., description="ID of unreconciled payment")
    payment: PaymentEventResponse = Field(..., description="Full payment details")

    suggested_schedule_id: str = Field(..., description="ID of suggested matching schedule")
    suggested_schedule: ObligationScheduleResponse = Field(..., description="Full schedule details")
    suggested_obligation: ObligationAgreementResponse = Field(..., description="Parent obligation details")

    confidence: float = Field(..., ge=0.0, le=1.0, description="AI confidence score (0.0-1.0)")
    reasoning: str = Field(..., description="AI explanation for why this match was suggested")

    variance_amount: Optional[Decimal] = Field(
        None, description="Difference between payment amount and expected amount"
    )
    variance_percent: Optional[float] = Field(
        None, description="Variance as percentage of expected amount"
    )

    auto_approved: bool = Field(
        False, description="Whether this was auto-approved based on confidence threshold"
    )
    created_at: datetime = Field(..., description="When suggestion was generated")


class ReconciliationSuggestionList(BaseModel):
    """List of reconciliation suggestions with summary stats."""

    suggestions: List[ReconciliationSuggestion] = Field(default_factory=list)
    total_count: int = Field(0, description="Total number of suggestions")
    auto_approved_count: int = Field(0, description="Number auto-approved")
    pending_review_count: int = Field(0, description="Number awaiting review")
    unmatched_count: int = Field(0, description="Number with no match found")


# ============================================
# Reconciliation Action Schemas
# ============================================

class ReconciliationMatch(BaseModel):
    """Request to reconcile a payment to a schedule."""

    payment_id: str = Field(..., description="ID of payment to reconcile")
    schedule_id: str = Field(..., description="ID of schedule to match to")


class ApproveReconciliationRequest(BaseModel):
    """Request to approve a single reconciliation suggestion."""

    suggestion_id: Optional[str] = Field(None, description="ID of suggestion to approve")
    payment_id: str = Field(..., description="ID of payment to reconcile")
    schedule_id: str = Field(..., description="ID of schedule to match to")


class BulkReconciliationRequest(BaseModel):
    """Request to approve multiple reconciliation matches at once."""

    matches: List[ReconciliationMatch] = Field(..., min_length=1)


class BulkReconciliationResult(BaseModel):
    """Result of bulk reconciliation operation."""

    successful: int = Field(0, description="Number of successfully reconciled payments")
    failed: int = Field(0, description="Number of failed reconciliations")
    errors: List[str] = Field(default_factory=list, description="Error messages for failures")


class RejectReconciliationRequest(BaseModel):
    """Request to reject a reconciliation suggestion."""

    payment_id: str = Field(..., description="ID of payment")
    reason: Optional[str] = Field(None, description="Optional reason for rejection")


class RevertReconciliationRequest(BaseModel):
    """Request to revert an auto-approved reconciliation."""

    payment_id: str = Field(..., description="ID of payment to un-reconcile")
    reason: Optional[str] = Field(None, description="Optional reason for reverting")


# ============================================
# Forecast Impact Schemas
# ============================================

class ForecastImpactItem(BaseModel):
    """A payment event that impacts forecast accuracy."""

    payment: PaymentEventResponse
    impact_amount: Decimal = Field(..., description="Amount affecting forecast")
    days_old: int = Field(..., description="How long payment has been unreconciled")


class ForecastImpactSummary(BaseModel):
    """Summary of how unreconciled items affect forecast accuracy."""

    accuracy_score: float = Field(
        ..., ge=0.0, le=100.0,
        description="Current forecast accuracy percentage (0-100)"
    )
    unreconciled_count: int = Field(0, description="Number of unreconciled payments")
    unreconciled_amount: Decimal = Field(
        Decimal("0"), description="Total amount of unreconciled payments"
    )
    impact_percent: float = Field(
        0.0, description="Percentage impact on forecast accuracy"
    )
    top_impacting_items: List[ForecastImpactItem] = Field(
        default_factory=list,
        description="Top items affecting accuracy, sorted by impact"
    )
    severity: Literal["healthy", "warning", "critical"] = Field(
        "healthy", description="Overall severity level"
    )


# ============================================
# Settings Schemas
# ============================================

class ReconciliationSettings(BaseModel):
    """User settings for reconciliation behavior."""

    auto_approve_enabled: bool = Field(
        True, description="Whether to auto-approve high-confidence matches"
    )
    auto_approve_threshold: float = Field(
        0.95, ge=0.0, le=1.0,
        description="Minimum confidence score for auto-approval (0.0-1.0)"
    )
    review_threshold: float = Field(
        0.70, ge=0.0, le=1.0,
        description="Minimum confidence for review queue (below this = unmatched)"
    )
    notify_on_auto_approve: bool = Field(
        False, description="Send notification when items are auto-approved"
    )


class ReconciliationSettingsUpdate(BaseModel):
    """Request to update reconciliation settings."""

    auto_approve_enabled: Optional[bool] = None
    auto_approve_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    review_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    notify_on_auto_approve: Optional[bool] = None


# ============================================
# Queue Summary Schemas
# ============================================

class ReconciliationQueueSummary(BaseModel):
    """Summary of reconciliation queue for UI display."""

    total_pending: int = Field(0, description="Total items needing attention")
    affecting_forecast: int = Field(0, description="Critical items affecting forecast")
    ai_suggestions: int = Field(0, description="AI suggestions ready for review")
    needs_manual_match: int = Field(0, description="Items requiring manual matching")
    recently_auto_approved: int = Field(0, description="Items auto-approved in last 24h")
    forecast_accuracy: float = Field(100.0, description="Current forecast accuracy %")
