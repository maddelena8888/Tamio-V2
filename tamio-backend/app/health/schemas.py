"""
Health Metrics Schemas - Financial Wellness Dashboard

Pydantic schemas for the Health page API.
"""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel

from app.alerts_actions.schemas import RiskResponse


class HealthRingData(BaseModel):
    """Data for a single health ring visualization."""
    value: float  # Raw value (e.g., 13 weeks, 70%, 1.8 ratio)
    percentage: float  # 0-100 for ring fill
    status: Literal["good", "warning", "critical"]
    label: str  # Display value (e.g., "13w", "70%", "1.8")
    sublabel: str  # Status description (e.g., "Healthy - 80% to target")


# Status types for monitor cards
ObligationsStatus = Literal["covered", "tight", "at_risk"]
ReceivablesStatus = Literal["healthy", "watch", "urgent"]


class ObligationsHealthData(BaseModel):
    """
    Data for the Obligations Health monitor card.
    Shows if upcoming financial obligations can be covered with available cash.
    """
    # Status indicator
    status: ObligationsStatus  # "covered" | "tight" | "at_risk"

    # Primary metric: "X of Y due"
    covered_count: int  # Number of obligations that can be covered
    total_count: int    # Total obligations in 14-day window

    # Next obligation details
    next_obligation_name: Optional[str] = None      # e.g., "Payroll"
    next_obligation_amount: Optional[float] = None  # Raw amount
    next_obligation_amount_formatted: Optional[str] = None  # e.g., "$85K"
    next_obligation_days: Optional[int] = None      # Days until due

    # Calculated values for reference
    buffer_percentage: float   # Buffer % after covering all obligations
    total_obligations: float   # Total amount due in 14-day window
    available_funds: float     # Cash + expected AR within 14 days


class ReceivablesHealthData(BaseModel):
    """
    Data for the Receivables Health monitor card.
    Shows health of money owed - focusing on overdue invoices.
    """
    # Status indicator
    status: ReceivablesStatus  # "healthy" | "watch" | "urgent"

    # Primary metric: overdue amount
    overdue_amount: float           # Raw overdue amount
    overdue_amount_formatted: str   # e.g., "$158K overdue"

    # Detail line: invoice counts and lateness
    overdue_count: int              # Number of overdue invoices
    total_outstanding_count: int    # Total outstanding invoices
    avg_days_late: int              # Average days late for overdue invoices

    # Calculated values for reference
    overdue_percentage: float       # % of outstanding that is overdue
    total_outstanding_amount: float # Total AR outstanding


class HealthMetricsResponse(BaseModel):
    """Complete response for health metrics endpoint."""
    # Health rings
    runway: HealthRingData
    liquidity: HealthRingData      # Working capital ratio (was: buffer)
    cash_velocity: HealthRingData  # Cash conversion cycle in days (was: liquidity)

    # Monitor cards
    obligations_health: ObligationsHealthData  # Forward-looking: Can you cover upcoming payments?
    receivables_health: ReceivablesHealthData  # Current state: Is money owed coming in on time?

    # Critical alerts (top 3)
    critical_alerts: List[RiskResponse]

    # Metadata
    last_updated: datetime
