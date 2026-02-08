"""Forecast response schemas."""
from pydantic import BaseModel
from typing import List, Optional


class ForecastEventSummary(BaseModel):
    """Summary of a cash event in the forecast."""
    id: str
    date: str
    amount: str
    direction: str
    event_type: str
    category: str | None
    confidence: str
    confidence_reason: Optional[str] = None
    source_id: Optional[str] = None
    source_name: Optional[str] = None
    source_type: Optional[str] = None


class ConfidenceBreakdown(BaseModel):
    """Confidence breakdown for cash in/out."""
    high: str
    medium: str
    low: str


class WeekConfidenceBreakdown(BaseModel):
    """Weekly confidence breakdown."""
    cash_in: ConfidenceBreakdown
    cash_out: ConfidenceBreakdown


class WeekForecast(BaseModel):
    """Forecast for a single week."""
    week_number: int
    week_start: str
    week_end: str
    starting_balance: str
    cash_in: str
    cash_out: str
    net_change: str
    ending_balance: str
    events: List[ForecastEventSummary]
    confidence_breakdown: Optional[WeekConfidenceBreakdown] = None


class ForecastSummary(BaseModel):
    """Summary statistics for the forecast."""
    lowest_cash_week: int
    lowest_cash_amount: str
    total_cash_in: str
    total_cash_out: str
    runway_weeks: int


class ConfidenceCountBreakdown(BaseModel):
    """Detailed confidence breakdown with counts and amounts."""
    high_confidence_count: int
    medium_confidence_count: int
    low_confidence_count: int
    high_confidence_amount: str
    medium_confidence_amount: str
    low_confidence_amount: str


class ForecastConfidence(BaseModel):
    """Overall forecast confidence metrics."""
    overall_score: str
    overall_level: str  # "high" | "medium" | "low"
    overall_percentage: int
    breakdown: ConfidenceCountBreakdown
    improvement_suggestions: List[str]


class ForecastResponse(BaseModel):
    """Complete 13-week forecast response."""
    starting_cash: str
    forecast_start_date: str
    weeks: List[WeekForecast]
    summary: ForecastSummary
    confidence: Optional[ForecastConfidence] = None


# Legacy support - V1 response without confidence
class ForecastResponseV1(BaseModel):
    """Legacy forecast response (V1 - without confidence)."""
    starting_cash: str
    forecast_start_date: str
    weeks: List[WeekForecast]
    summary: ForecastSummary


# ============================================================================
# Scenario Bar Schemas
# ============================================================================

class MetricValue(BaseModel):
    """A single metric value with status indicator."""
    value: str  # The display value (e.g., "13", "Safe", "$15k")
    raw_value: float  # The raw numeric value for calculations
    unit: Optional[str] = None  # "w" for weeks, "$" for currency, etc.
    status: str  # "good", "warning", "critical"
    icon: str  # Icon name or emoji


class ScenarioBarMetrics(BaseModel):
    """Metrics displayed in the scenario bar."""
    runway: MetricValue  # Weeks until cash falls below buffer
    next_payroll: MetricValue  # Payroll safety status
    vat_reserve: MetricValue  # VAT/tax reserve amount


class ScenarioBarResponse(BaseModel):
    """Response for the scenario bar metrics endpoint."""
    scenario_active: bool
    scenario_name: Optional[str] = None
    impact_statement: Optional[str] = None
    metrics: ScenarioBarMetrics
    time_range: str  # "13w", "26w", "52w"


# ============================================================================
# Transaction Table Schemas
# ============================================================================

class TransactionItem(BaseModel):
    """A single transaction item for inflows/outflows tables."""
    id: str
    date: str  # ISO date string
    amount: float
    name: str  # Client name or expense/vendor name
    entity_id: str  # client_id or bucket_id
    entity_type: str  # "client" or "expense"
    status: str  # "overdue", "due", "expected", "received", "paid"
    included: bool  # Whether included in current forecast


class TransactionsResponse(BaseModel):
    """Response for the transactions endpoint."""
    transactions: List[TransactionItem]
    total_amount: float
    time_range: str


# ============================================================================
# Custom Scenario Schemas
# ============================================================================

class CustomScenarioRequest(BaseModel):
    """Request to create a custom scenario from transaction toggles."""
    user_id: str
    name: str = "Custom adjustments"
    excluded_transactions: List[str]  # Transaction IDs to exclude
    effective_date: str


class ForecastDelta(BaseModel):
    """Delta to apply to a specific week in the forecast."""
    week: int
    delta: float


class CustomScenarioResponse(BaseModel):
    """Response after creating a custom scenario."""
    scenario_id: str
    name: str
    forecast_delta: List[ForecastDelta]
