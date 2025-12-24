"""Pydantic schemas for scenario analysis."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, date
from decimal import Decimal

from app.scenarios.models import RuleType, RuleSeverity, ScenarioType, ScenarioStatus


# ============================================================================
# FINANCIAL RULES SCHEMAS
# ============================================================================

class FinancialRuleCreate(BaseModel):
    """Schema for creating a financial rule."""
    user_id: str
    rule_type: RuleType
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    threshold_config: Dict[str, Any]  # e.g., {"months": 3}
    is_active: bool = True
    evaluation_scope: str = "all"


class FinancialRuleUpdate(BaseModel):
    """Schema for updating a financial rule."""
    name: Optional[str] = None
    description: Optional[str] = None
    threshold_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    evaluation_scope: Optional[str] = None


class FinancialRuleResponse(BaseModel):
    """Schema for financial rule response."""
    id: str
    user_id: str
    rule_type: RuleType
    name: str
    description: Optional[str]
    threshold_config: Dict[str, Any]
    is_active: bool
    evaluation_scope: str
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ============================================================================
# SCENARIO SCHEMAS
# ============================================================================

class ScenarioCreate(BaseModel):
    """Schema for creating a scenario."""
    user_id: str
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    scenario_type: ScenarioType
    entry_path: str = "user_defined"  # "user_defined" or "tamio_suggested"
    suggested_reason: Optional[str] = None
    scope_config: Dict[str, Any]
    parameters: Dict[str, Any]
    parent_scenario_id: Optional[str] = None
    layer_order: int = 0


class ScenarioUpdate(BaseModel):
    """Schema for updating a scenario."""
    name: Optional[str] = None
    description: Optional[str] = None
    scope_config: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None
    status: Optional[ScenarioStatus] = None


class ScenarioResponse(BaseModel):
    """Schema for scenario response."""
    id: str
    user_id: str
    name: str
    description: Optional[str]
    scenario_type: ScenarioType
    status: ScenarioStatus
    entry_path: str
    suggested_reason: Optional[str]
    scope_config: Dict[str, Any]
    parameters: Dict[str, Any]
    linked_scenarios: List[Dict[str, Any]]
    layer_order: int
    parent_scenario_id: Optional[str]
    confirmed_at: Optional[datetime]
    confirmed_by: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ============================================================================
# RULE EVALUATION SCHEMAS
# ============================================================================

class RuleEvaluationResponse(BaseModel):
    """Schema for rule evaluation response."""
    id: str
    rule_id: str
    scenario_id: Optional[str]
    user_id: str
    severity: RuleSeverity
    is_breached: bool
    first_breach_week: Optional[int]
    first_breach_date: Optional[str]
    breach_amount: Optional[Decimal]
    action_window_weeks: Optional[int]
    evaluation_details: Dict[str, Any]
    evaluated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# SCENARIO FORECAST SCHEMAS
# ============================================================================

class ScenarioForecastResponse(BaseModel):
    """Schema for scenario forecast response."""
    id: str
    scenario_id: str
    user_id: str
    forecast_data: Dict[str, Any]  # Full 13-week forecast
    delta_data: Dict[str, Any]     # Deltas from base
    summary: Dict[str, Any]
    computed_at: datetime

    model_config = {"from_attributes": True}


class ScenarioLayerAdd(BaseModel):
    """Schema for adding a linked layer to a scenario."""
    layer_type: str  # e.g., "contractor_loss", "decreased_expense", "firing"
    layer_name: Optional[str] = None  # Human-readable name for this layer
    parameters: Dict[str, Any] = {}  # Type-specific parameters


class SuggestedDependentScenario(BaseModel):
    """A suggested dependent scenario based on the current scenario."""
    scenario_type: str
    title: str
    description: str
    question: str
    direction: str  # "reduce_costs", "increase_costs", "reduce_revenue", "increase_revenue", "timing_change"
    typical_lag_weeks: int = 0
    confidence: str = "medium"  # "high", "medium", "low"
    prefill_params: Dict[str, Any] = {}


class ScenarioComparisonResponse(BaseModel):
    """Schema for comparing base vs scenario forecasts."""
    base_forecast: Dict[str, Any]
    scenario_forecast: Dict[str, Any]
    deltas: Dict[str, Any]
    rule_evaluations: List[RuleEvaluationResponse]
    decision_signals: Dict[str, Any]
    suggested_scenarios: List[SuggestedDependentScenario] = []


# ============================================================================
# SCENARIO LAYER SCHEMAS
# ============================================================================

class ScenarioEventDetail(BaseModel):
    """Schema for scenario event detail."""
    id: str
    scenario_id: str
    original_event_id: Optional[str]
    operation: str  # "add", "modify", "delete"
    event_data: Dict[str, Any]
    layer_attribution: Optional[str]
    change_reason: Optional[str]
    created_at: datetime


class ScenarioLayerResponse(BaseModel):
    """Schema for scenario layer with all modifications."""
    scenario: ScenarioResponse
    events: List[ScenarioEventDetail]
    event_count: int
    operations_summary: Dict[str, int]  # {"add": 5, "modify": 3, "delete": 1}


# ============================================================================
# SPECIFIC SCENARIO TYPE PARAMETERS
# ============================================================================

class PaymentDelayParams(BaseModel):
    """Parameters for payment delay scenario."""
    delay_weeks: int = Field(..., ge=1, le=52)
    partial_payment_pct: Optional[int] = Field(None, ge=0, le=100)
    event_ids: List[str]  # Which cash events to delay


class ClientLossParams(BaseModel):
    """Parameters for client loss scenario."""
    client_id: str
    effective_date: date
    impact_retainers: bool = True
    impact_milestones: bool = True
    reduce_variable_costs: Optional[Dict[str, Any]] = None


class ClientGainParams(BaseModel):
    """Parameters for client gain scenario."""
    client_name: str
    start_date: date
    agreement_type: Literal["retainer", "project", "usage", "mixed"]
    monthly_amount: Optional[Decimal] = None
    billing_config: Dict[str, Any]
    add_variable_costs: Optional[Dict[str, Any]] = None


class ClientChangeParams(BaseModel):
    """Parameters for client change scenario."""
    client_id: str
    delta_amount: Decimal  # Positive = upsell, negative = downsell
    effective_date: date
    change_reason: Optional[str] = None


class HiringParams(BaseModel):
    """Parameters for hiring scenario."""
    role_title: str
    start_date: date
    monthly_cost: Decimal
    pay_frequency: Literal["monthly", "bi-weekly", "weekly"] = "monthly"
    onboarding_costs: Optional[Decimal] = None


class FiringParams(BaseModel):
    """Parameters for firing scenario."""
    obligation_id: Optional[str] = None  # If tracking specific employee
    end_date: date
    monthly_cost: Decimal
    severance_amount: Optional[Decimal] = None


class ContractorChangeParams(BaseModel):
    """Parameters for contractor gain/loss scenario."""
    contractor_name: Optional[str] = None
    start_or_end_date: date
    monthly_estimate: Decimal
    is_recurring: bool = True


class ExpenseChangeParams(BaseModel):
    """Parameters for expense increase/decrease scenario."""
    expense_name: str
    amount: Decimal
    effective_date: date
    is_recurring: bool
    frequency: Optional[Literal["monthly", "quarterly", "annual"]] = "monthly"


# ============================================================================
# DECISION SIGNALS
# ============================================================================

class DecisionSignal(BaseModel):
    """Decision signal from scenario analysis."""
    signal_type: str  # "rule_breach", "runway_warning", "opportunity"
    severity: RuleSeverity
    title: str
    message: str
    earliest_risk_week: Optional[int]
    action_window_weeks: Optional[int]
    recommended_actions: List[str]
