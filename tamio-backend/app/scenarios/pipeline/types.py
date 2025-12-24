"""
Scenario Pipeline Types - Core Data Structures.

Implements the data structures required for deterministic, multi-step scenario modeling:
- ScenarioDefinition: Full scenario specification with linked changes
- ScenarioDelta: Canonical adjustments (created, updated, deleted events/objects)
- PromptRequest: UI prompt requirements when information is missing
- LinkedChange: Second-order effects from primary scenarios
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal


# =============================================================================
# ENUMS
# =============================================================================

class ScenarioTypeEnum(str, Enum):
    """All supported scenario types."""
    # Cash In scenarios
    PAYMENT_DELAY_IN = "payment_delay_in"
    CLIENT_LOSS = "client_loss"
    CLIENT_GAIN = "client_gain"
    CLIENT_CHANGE = "client_change"

    # Cash Out scenarios
    HIRING = "hiring"
    FIRING = "firing"
    CONTRACTOR_GAIN = "contractor_gain"
    CONTRACTOR_LOSS = "contractor_loss"
    INCREASED_EXPENSE = "increased_expense"
    DECREASED_EXPENSE = "decreased_expense"
    PAYMENT_DELAY_OUT = "payment_delay_out"


class EntryPath(str, Enum):
    """How the scenario was initiated."""
    MANUAL = "manual"
    TAMIO_SUGGESTED = "tamio_suggested"


class ScenarioStatusEnum(str, Enum):
    """Scenario lifecycle status."""
    DRAFT = "draft"          # Being built, prompts pending
    SIMULATED = "simulated"  # Deltas computed, ready for review
    CONFIRMED = "confirmed"  # Committed to canonical data
    DISCARDED = "discarded"  # Rejected, no changes made


class AnswerType(str, Enum):
    """Types of answers for prompt requests."""
    SINGLE_SELECT = "single_select"
    MULTI_SELECT = "multi_select"
    NUMERIC = "numeric"
    DATE = "date"
    DATE_RANGE = "date_range"
    TOGGLE = "toggle"
    TEXT = "text"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"


class PipelineStage(str, Enum):
    """Stages in the scenario pipeline."""
    SCOPE = "scope"
    PARAMS = "params"
    LINKED_PROMPTS = "linked_prompts"
    CANONICAL_DELTAS = "canonical_deltas"
    OVERLAY_FORECAST = "overlay_forecast"
    RULE_EVAL = "rule_eval"


class LinkedChangeType(str, Enum):
    """Types of linked changes."""
    # Cost reduction links
    REDUCE_CONTRACTORS = "reduce_contractors"
    REDUCE_TOOLS = "reduce_tools"
    REDUCE_PROJECT_COSTS = "reduce_project_costs"
    REDUCE_DISCRETIONARY = "reduce_discretionary"

    # Cost increase links
    ADD_CONTRACTORS = "add_contractors"
    ADD_HIRING = "add_hiring"
    ADD_TOOLS = "add_tools"
    ADD_ONBOARDING = "add_onboarding"

    # Payment timing links
    DELAY_VENDOR_PAYMENTS = "delay_vendor_payments"
    ACCELERATE_COLLECTIONS = "accelerate_collections"
    CREATE_CATCH_UP_SCHEDULE = "create_catch_up_schedule"
    SPREAD_PAYMENTS = "spread_payments"

    # Revenue links
    CLIENT_LOSS_LINKED = "client_loss_linked"
    CLIENT_CHANGE_LINKED = "client_change_linked"
    DELAYED_MILESTONES = "delayed_milestones"


# =============================================================================
# PROMPT REQUEST
# =============================================================================

class PromptOption(BaseModel):
    """An option for single/multi select prompts."""
    value: str
    label: str
    description: Optional[str] = None
    is_default: bool = False


class PromptRequest(BaseModel):
    """
    A request for user input when information is missing.

    The engine returns these when it cannot proceed deterministically
    without additional user input.
    """
    prompt_id: str = Field(..., description="Unique identifier for this prompt")
    scenario_id: str = Field(..., description="Associated scenario ID")
    stage: PipelineStage = Field(..., description="Pipeline stage requiring input")

    # Question details
    question: str = Field(..., description="The question to ask the user")
    help_text: Optional[str] = Field(None, description="Additional context/help")
    answer_type: AnswerType = Field(..., description="Type of answer expected")

    # Options for select types
    options: Optional[List[PromptOption]] = Field(None, description="Available options")

    # Constraints
    required: bool = Field(True, description="Whether an answer is required")
    min_value: Optional[float] = Field(None, description="Minimum value for numeric")
    max_value: Optional[float] = Field(None, description="Maximum value for numeric")

    # Mapping
    maps_to: str = Field(..., description="Parameter path this answer populates")
    maps_to_linked: Optional[str] = Field(None, description="If for linked change")

    # Dependencies
    depends_on: Optional[List[str]] = Field(None, description="Other prompt IDs this depends on")

    # Current value (if editing)
    current_value: Optional[Any] = None


# =============================================================================
# LINKED CHANGE
# =============================================================================

class LinkedChange(BaseModel):
    """
    A linked/second-order change triggered by a primary scenario.

    Example: Client Loss → Reduce Contractors with 2-week lag
    """
    linked_change_id: str = Field(..., description="Unique ID for this linked change")
    parent_scenario_id: str = Field(..., description="The primary scenario")

    # Type and relationship
    linked_type: LinkedChangeType
    relationship: str = Field(..., description="How this links to parent")

    # Scope
    scope: Dict[str, Any] = Field(default_factory=dict)

    # Parameters
    parameters: Dict[str, Any] = Field(default_factory=dict)

    # Timing
    lag_weeks: int = Field(0, ge=0, le=52, description="Delay before this takes effect")
    effective_date: Optional[date] = None

    # Status
    is_confirmed: bool = Field(False, description="User confirmed this linked change")
    is_skipped: bool = Field(False, description="User explicitly skipped this")


# =============================================================================
# SCENARIO DEFINITION
# =============================================================================

class ScopeConfig(BaseModel):
    """Scope configuration for a scenario."""
    # Entity references
    client_ids: Optional[List[str]] = None
    agreement_ids: Optional[List[str]] = None
    obligation_ids: Optional[List[str]] = None
    event_ids: Optional[List[str]] = None
    bucket_ids: Optional[List[str]] = None
    account_ids: Optional[List[str]] = None

    # Categories
    categories: Optional[List[str]] = None

    # Date range
    effective_date: Optional[date] = None
    end_date: Optional[date] = None

    # Extra
    extra: Dict[str, Any] = Field(default_factory=dict)


class ScenarioDefinition(BaseModel):
    """
    Complete definition of a scenario with all parameters and linked changes.

    This is the core data structure that drives deterministic scenario processing.
    """
    # Identity
    scenario_id: str
    user_id: str

    # Type and entry
    scenario_type: ScenarioTypeEnum
    entry_path: EntryPath = EntryPath.MANUAL
    suggested_reason: Optional[str] = None

    # Naming
    name: Optional[str] = None
    description: Optional[str] = None

    # Scope
    scope: ScopeConfig = Field(default_factory=ScopeConfig)

    # Parameters (scenario-type specific)
    parameters: Dict[str, Any] = Field(default_factory=dict)

    # Linked changes
    linked_changes: List[LinkedChange] = Field(default_factory=list)

    # Status
    status: ScenarioStatusEnum = ScenarioStatusEnum.DRAFT

    # Pipeline progress
    current_stage: PipelineStage = PipelineStage.SCOPE
    completed_stages: List[PipelineStage] = Field(default_factory=list)

    # Pending prompts
    pending_prompts: List[PromptRequest] = Field(default_factory=list)

    # Layer ordering (for stacking)
    layer_order: int = 0
    parent_scenario_id: Optional[str] = None

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None


# =============================================================================
# SCENARIO DELTA
# =============================================================================

class EventDelta(BaseModel):
    """A single event modification."""
    event_id: str
    original_event_id: Optional[str] = None
    operation: str  # "add", "modify", "delete"

    # For add/modify: the event data
    event_data: Optional[Dict[str, Any]] = None

    # Attribution
    scenario_id: str
    linked_change_id: Optional[str] = None
    change_reason: str


class ObjectDelta(BaseModel):
    """A modification to a canonical object (agreement, schedule, etc.)."""
    object_type: str  # "agreement", "schedule", "client", "obligation"
    object_id: str
    original_object_id: Optional[str] = None
    operation: str  # "add", "modify", "delete"

    # For add/modify: the object data
    object_data: Optional[Dict[str, Any]] = None

    # Attribution
    scenario_id: str
    linked_change_id: Optional[str] = None
    change_reason: str


class ScenarioDelta(BaseModel):
    """
    Complete set of canonical adjustments for a scenario.

    This represents all changes that would be made to the canonical
    data if the scenario is confirmed.
    """
    scenario_id: str

    # Event changes
    created_events: List[EventDelta] = Field(default_factory=list)
    updated_events: List[EventDelta] = Field(default_factory=list)
    deleted_event_ids: List[str] = Field(default_factory=list)

    # Object changes (agreements, schedules, etc.)
    created_objects: List[ObjectDelta] = Field(default_factory=list)
    updated_objects: List[ObjectDelta] = Field(default_factory=list)
    deleted_object_ids: List[str] = Field(default_factory=list)

    # Summary
    total_events_affected: int = 0
    net_cash_impact: Decimal = Decimal("0")

    # Attribution breakdown
    changes_by_linked_change: Dict[str, int] = Field(default_factory=dict)


# =============================================================================
# PIPELINE RESULT
# =============================================================================

class WeekSummary(BaseModel):
    """Summary of a single forecast week."""
    week_number: int
    week_start: date
    week_end: date
    starting_balance: Decimal
    cash_in: Decimal
    cash_out: Decimal
    net_change: Decimal
    ending_balance: Decimal


class ForecastSummary(BaseModel):
    """Summary of the full forecast."""
    starting_cash: Decimal
    weeks: List[WeekSummary]
    lowest_cash_week: int
    lowest_cash_amount: Decimal
    total_cash_in: Decimal
    total_cash_out: Decimal
    runway_weeks: int


class RuleResult(BaseModel):
    """Result of evaluating a single rule."""
    rule_id: str
    rule_name: str
    rule_type: str
    severity: str  # "green", "amber", "red"
    is_breached: bool
    breach_week: Optional[int] = None
    breach_date: Optional[date] = None
    breach_amount: Optional[Decimal] = None
    action_window_weeks: Optional[int] = None
    message: str
    recommended_actions: List[str] = Field(default_factory=list)


class DeltaSummary(BaseModel):
    """Summary of changes between base and scenario."""
    week_deltas: List[Dict[str, Any]] = Field(default_factory=list)
    top_changed_weeks: List[int] = Field(default_factory=list)
    top_changed_events: List[Dict[str, Any]] = Field(default_factory=list)
    net_cash_in_change: Decimal = Decimal("0")
    net_cash_out_change: Decimal = Decimal("0")
    runway_change: int = 0


class PipelineResult(BaseModel):
    """
    Complete result from running the scenario pipeline.

    Returned after each pipeline step to show progress and any
    pending prompts that need answers.
    """
    scenario_id: str
    scenario_definition: ScenarioDefinition

    # Pipeline state
    current_stage: PipelineStage
    completed_stages: List[PipelineStage]
    is_complete: bool = False

    # Prompts needed
    prompt_requests: List[PromptRequest] = Field(default_factory=list)

    # Results (populated as stages complete)
    delta: Optional[ScenarioDelta] = None

    # Forecast comparison
    base_forecast_summary: Optional[ForecastSummary] = None
    scenario_forecast_summary: Optional[ForecastSummary] = None
    delta_summary: Optional[DeltaSummary] = None

    # Rule evaluations
    rule_results: List[RuleResult] = Field(default_factory=list)

    # Errors
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
