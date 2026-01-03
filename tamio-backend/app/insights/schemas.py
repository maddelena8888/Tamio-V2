"""Pydantic schemas for insights API responses."""
from pydantic import BaseModel
from typing import List, Optional, Literal
from decimal import Decimal


# =============================================================================
# Income Behaviour Schemas
# =============================================================================

class ClientPaymentBehaviour(BaseModel):
    """Payment behaviour analysis for a single client."""
    client_id: str
    client_name: str
    payment_behavior: Literal["on_time", "delayed", "unknown"]
    monthly_amount: str
    percentage_of_revenue: str
    risk_level: Literal["low", "medium", "high"]


class RevenueConcentration(BaseModel):
    """Revenue concentration for a single client."""
    client_id: str
    client_name: str
    monthly_amount: str
    percentage: str
    is_high_concentration: bool  # >25% of revenue


class IncomeBehaviourInsights(BaseModel):
    """Complete income behaviour insights."""
    # Summary metrics
    total_monthly_revenue: str
    clients_with_delayed_payments: int
    clients_with_high_concentration: int
    revenue_at_risk_percentage: str  # Revenue from delayed payers

    # Detailed breakdowns
    payment_behaviour: List[ClientPaymentBehaviour]
    revenue_concentration: List[RevenueConcentration]

    # Recommendations
    recommendations: List[str]


# =============================================================================
# Expense Behaviour Schemas
# =============================================================================

class ExpenseCategoryTrend(BaseModel):
    """Trend analysis for an expense category."""
    category: str
    current_monthly: str
    previous_monthly: str  # Based on historical if available
    change_percentage: str
    trend: Literal["rising", "stable", "declining"]
    is_over_budget: bool
    budget_variance: str  # Amount over/under


class ExpenseBucketDetail(BaseModel):
    """Detail for a single expense bucket."""
    bucket_id: str
    name: str
    category: str
    monthly_amount: str
    bucket_type: Literal["fixed", "variable"]
    priority: str
    is_stable: bool


class ExpenseBehaviourInsights(BaseModel):
    """Complete expense behaviour insights."""
    # Summary metrics
    total_monthly_expenses: str
    fixed_expenses: str
    variable_expenses: str
    categories_rising: int
    categories_over_budget: int

    # Detailed breakdowns
    category_trends: List[ExpenseCategoryTrend]
    expense_details: List[ExpenseBucketDetail]

    # Recommendations
    recommendations: List[str]


# =============================================================================
# Cash Discipline Schemas
# =============================================================================

class BufferHealthMetric(BaseModel):
    """Buffer health over a time period."""
    period: str  # e.g., "Last 30 days", "Week 3"
    average_buffer: str
    minimum_buffer: str
    target_buffer: str
    buffer_coverage_days: int
    was_below_target: bool


class UpcomingRiskWindow(BaseModel):
    """Upcoming period where buffer may be at risk."""
    week_number: int
    week_start: str
    projected_balance: str
    target_buffer: str
    shortfall: str
    severity: Literal["warning", "critical"]
    contributing_factors: List[str]


class CashDisciplineInsights(BaseModel):
    """Complete cash discipline insights."""
    # Current state
    current_buffer: str
    target_buffer: str
    buffer_months: int
    buffer_health_score: int  # 0-100
    buffer_status: Literal["healthy", "at_risk", "critical"]

    # Historical behaviour
    days_below_target_last_90: int  # Would need historical data
    buffer_trend: Literal["improving", "stable", "declining"]

    # Forward-looking
    upcoming_risks: List[UpcomingRiskWindow]
    weeks_until_risk: Optional[int]  # None if no risk in forecast

    # Recommendations
    recommendations: List[str]


# =============================================================================
# Traffic Light Status (TAMI Knowledge Framework)
# =============================================================================

class TrafficLightCondition(BaseModel):
    """A single condition contributing to the traffic light status."""
    condition: str  # Description of the condition
    met: bool  # Whether this condition is currently met
    severity: Literal["green", "amber", "red"]  # What status this triggers if met


class TrafficLightStatus(BaseModel):
    """
    Traffic light health status with deterministic rules.

    GREEN (Stable): Cash position healthy, buffer rules respected, no near-term stress
    AMBER (Watch Closely): Risk emerging but manageable, action window exists
    RED (Action Required): Material liquidity risk imminent or present
    """
    status: Literal["green", "amber", "red"]
    label: str  # "Stable", "Watch Closely", "Action Required"

    # What it means
    meaning: str

    # The conditions that led to this status
    conditions_met: List[TrafficLightCondition]

    # User guidance
    guidance: List[str]

    # TAMI's tone/message for this status
    tami_message: str

    # Time-sensitive context
    action_window: Optional[str] = None  # e.g., "4-12 weeks", "0-4 weeks", None for green
    urgency: Literal["none", "low", "medium", "high"]


# =============================================================================
# Combined Insights Response
# =============================================================================

class InsightsSummary(BaseModel):
    """High-level summary across all insight types."""
    # Traffic light status (primary indicator)
    traffic_light: TrafficLightStatus

    # Health scores (0-100) - supporting detail
    income_health_score: int
    expense_health_score: int
    cash_discipline_score: int
    overall_health_score: int

    # Key alerts
    alerts: List[str]

    # Top recommendations
    top_recommendations: List[str]


class InsightsResponse(BaseModel):
    """Complete insights response."""
    summary: InsightsSummary
    income_behaviour: IncomeBehaviourInsights
    expense_behaviour: ExpenseBehaviourInsights
    cash_discipline: CashDisciplineInsights
