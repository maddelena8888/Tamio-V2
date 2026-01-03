"""
Behavior Schemas - Pydantic models for API requests/responses.
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime


# =============================================================================
# Behavior Metric Schemas
# =============================================================================

class BehaviorMetricBase(BaseModel):
    """Base schema for behavior metrics."""
    metric_type: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    current_value: float
    previous_value: Optional[float] = None
    trend: Literal["improving", "stable", "worsening"] = "stable"
    trend_velocity: float = 0.0
    data_confidence: float = 0.5


class BehaviorMetricResponse(BehaviorMetricBase):
    """Response schema for a behavior metric."""
    id: str
    user_id: str
    mean: Optional[float] = None
    variance: Optional[float] = None
    std_dev: Optional[float] = None
    trend_confidence: float = 0.5
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    is_higher_better: bool = True
    is_breached: bool = False
    is_warning: bool = False
    context_data: Dict[str, Any] = {}
    computed_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Client Behavior Metrics
# =============================================================================

class ClientConcentrationMetric(BaseModel):
    """Client concentration metric details."""
    client_id: str
    client_name: str
    revenue_share: float  # Percentage 0-100
    cash_weighted_share: float  # Cash-weighted percentage
    is_high_concentration: bool
    payment_reliability: Optional[float] = None  # 0-100 reliability score


class PaymentReliabilityMetric(BaseModel):
    """Payment reliability metric for a client."""
    client_id: str
    client_name: str
    mean_days_to_payment: float
    variance_days: float
    trend: Literal["improving", "stable", "worsening"]
    reliability_score: float  # 0-100
    sample_size: int  # Number of payments analyzed
    monthly_amount: str


class RevenueAtRiskMetric(BaseModel):
    """Revenue at risk calculation."""
    period_days: int  # 30 or 60
    total_revenue: str
    at_risk_amount: str
    at_risk_percentage: float
    probability_weighted_amount: str
    contributing_clients: List[Dict[str, Any]]


class ClientBehaviorInsights(BaseModel):
    """Complete client behavior insights."""
    # Concentration
    concentration_score: float  # 0-100, lower = more concentrated
    top_clients: List[ClientConcentrationMetric]
    concentration_warning: Optional[str] = None

    # Payment Reliability
    overall_reliability_score: float  # 0-100
    payment_reliability: List[PaymentReliabilityMetric]
    unreliable_clients_count: int

    # Revenue at Risk
    revenue_at_risk_30: RevenueAtRiskMetric
    revenue_at_risk_60: RevenueAtRiskMetric

    # Recommendations
    recommendations: List[str]


# =============================================================================
# Expense Behavior Metrics
# =============================================================================

class ExpenseVolatilityMetric(BaseModel):
    """Expense volatility by category."""
    category: str
    monthly_average: str
    volatility_index: float  # 0-100, higher = more volatile
    drift_percentage: float  # Recent change vs baseline
    trend: Literal["rising", "stable", "declining"]
    is_concerning: bool


class DiscretionaryRatioMetric(BaseModel):
    """Discretionary vs non-discretionary spending."""
    discretionary_total: str
    non_discretionary_total: str
    discretionary_percentage: float
    delayable_amount: str  # How much could be delayed if needed
    categories_breakdown: Dict[str, str]


class UpcomingCommitment(BaseModel):
    """An upcoming financial commitment."""
    name: str
    due_date: str
    amount: str
    commitment_type: Literal["fixed", "variable", "quarterly", "annual"]
    is_delayable: bool
    days_until_due: int


class ExpenseBehaviorInsights(BaseModel):
    """Complete expense behavior insights."""
    # Volatility
    overall_volatility_score: float  # 0-100, lower = more stable
    category_volatility: List[ExpenseVolatilityMetric]
    drifting_categories_count: int

    # Discretionary Split
    discretionary_ratio: DiscretionaryRatioMetric

    # Upcoming Commitments
    total_commitments_30_days: str
    upcoming_commitments: List[UpcomingCommitment]

    # Recommendations
    recommendations: List[str]


# =============================================================================
# Cash Discipline Metrics
# =============================================================================

class BufferIntegrityMetric(BaseModel):
    """Buffer integrity measurement."""
    current_buffer: str
    target_buffer: str
    integrity_percentage: float  # current/target * 100
    days_below_target_last_90: int
    longest_streak_below: int  # Consecutive days below target
    status: Literal["healthy", "at_risk", "critical"]


class BurnMomentumMetric(BaseModel):
    """Buffer trend / burn momentum."""
    current_weekly_burn: str  # Net change per week
    trend_direction: Literal["building", "stable", "burning"]
    momentum_percentage: float  # Rate of change
    weeks_of_data: int
    projected_weeks_to_zero: Optional[int] = None


class DecisionQualityMetric(BaseModel):
    """Reactive vs deliberate decision tracking."""
    total_decisions: int
    reactive_decisions: int
    deliberate_decisions: int
    reactive_percentage: float
    decisions_under_stress: int  # Made when buffer was below target
    average_decision_quality_score: float  # 0-100


class CashDisciplineInsights(BaseModel):
    """Complete cash discipline insights."""
    # Buffer Integrity
    buffer_integrity: BufferIntegrityMetric

    # Burn Momentum
    burn_momentum: BurnMomentumMetric
    weekly_trend_data: List[Dict[str, Any]]

    # Decision Quality
    decision_quality: DecisionQualityMetric

    # Forecast Confidence
    forecast_confidence_score: float  # 0-100
    confidence_breakdown: Dict[str, int]  # {"high": 10, "medium": 25, "low": 5}
    confidence_improvement_tips: List[str]

    # Recommendations
    recommendations: List[str]


# =============================================================================
# Triggered Scenario Schemas
# =============================================================================

class TriggeredScenarioResponse(BaseModel):
    """Response schema for a triggered scenario."""
    id: str
    trigger_name: str
    trigger_description: Optional[str] = None

    # Scenario details
    scenario_name: str
    scenario_description: Optional[str] = None
    scenario_type: str
    scenario_parameters: Dict[str, Any]

    # Impact and actions
    severity: Literal["low", "medium", "high", "critical"]
    estimated_impact: Dict[str, Any]
    recommended_actions: List[str]

    # Status
    status: Literal["pending", "active", "resolved", "dismissed", "expired"]
    triggered_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TriggeredScenarioAction(BaseModel):
    """User action on a triggered scenario."""
    action: Literal["run_scenario", "dismiss", "defer"]
    notes: Optional[str] = None
    defer_until: Optional[datetime] = None


# =============================================================================
# Combined Behavior Response
# =============================================================================

class BehaviorInsightsResponse(BaseModel):
    """Complete behavior insights response."""
    # Health score
    overall_behavior_score: float  # 0-100

    # Breakdown by category
    client_behavior: ClientBehaviorInsights
    expense_behavior: ExpenseBehaviorInsights
    cash_discipline: CashDisciplineInsights

    # Triggered scenarios
    triggered_scenarios: List[TriggeredScenarioResponse]
    pending_scenarios_count: int

    # Summary
    top_concerns: List[str]
    recommended_focus_area: Literal["client", "expense", "cash"]
