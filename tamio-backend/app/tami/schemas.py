"""TAMI Pydantic schemas for request/response validation."""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime
from enum import Enum


class TAMIMode(str, Enum):
    """Response modes for TAMI."""
    EXPLAIN_FORECAST = "explain_forecast"
    SUGGEST_SCENARIOS = "suggest_scenarios"
    BUILD_SCENARIO = "build_scenario"
    GOAL_PLANNING = "goal_planning"
    CLARIFY = "clarify"


class SuggestedAction(BaseModel):
    """An action button to show in the UI."""
    label: str = Field(..., description="Button label text")
    action: Literal["call_tool", "none"] = Field(..., description="Action type")
    tool_name: Optional[str] = Field(None, description="Tool to call if action is call_tool")
    tool_args: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Tool arguments")


class UIHints(BaseModel):
    """UI rendering hints for the frontend."""
    show_scenario_banner: bool = Field(False, description="Whether to show scenario mode banner")
    suggested_actions: List[SuggestedAction] = Field(default_factory=list, description="Action buttons to display")


class TAMIResponse(BaseModel):
    """Standard TAMI response format."""
    message_markdown: str = Field(..., description="Markdown-formatted response message")
    mode: TAMIMode = Field(..., description="Current conversation mode")
    ui_hints: UIHints = Field(default_factory=UIHints, description="UI rendering hints")


# ============================================================================
# CHAT REQUEST/RESPONSE
# ============================================================================

class ChatMessage(BaseModel):
    """A single chat message."""
    role: Literal["user", "assistant", "system"] = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = Field(None, description="When message was sent")


class ChatRequest(BaseModel):
    """Request to chat with TAMI."""
    user_id: str = Field(..., description="User ID for context loading")
    message: str = Field(..., description="User's message")
    conversation_history: List[ChatMessage] = Field(
        default_factory=list,
        description="Previous messages in this conversation"
    )
    active_scenario_id: Optional[str] = Field(
        None,
        description="Currently active scenario being edited"
    )


class ChatResponse(BaseModel):
    """Response from TAMI chat endpoint."""
    response: TAMIResponse = Field(..., description="TAMI's response")
    context_summary: Optional[Dict[str, Any]] = Field(
        None,
        description="Summary of context used (for debugging)"
    )
    tool_calls_made: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Tools called during this request"
    )


# ============================================================================
# SCENARIO LAYER OPERATIONS
# ============================================================================

class ScenarioLayerCreate(BaseModel):
    """Request to create or update a scenario layer."""
    user_id: str = Field(..., description="User ID")
    scenario_type: str = Field(..., description="Type of scenario")
    scope: Dict[str, Any] = Field(default_factory=dict, description="Scope configuration")
    params: Dict[str, Any] = Field(default_factory=dict, description="Scenario parameters")
    linked_changes: Optional[Dict[str, Any]] = Field(None, description="Linked changes (optional)")
    name: Optional[str] = Field(None, description="Optional scenario name")


class ScenarioLayerIterate(BaseModel):
    """Request to iterate on an existing scenario layer."""
    scenario_id: str = Field(..., description="Scenario ID to update")
    patch: Dict[str, Any] = Field(..., description="Fields to update")


class ScenarioLayerDiscard(BaseModel):
    """Request to discard a scenario layer."""
    scenario_id: str = Field(..., description="Scenario ID to discard")


class ScenarioLayerResponse(BaseModel):
    """Response from scenario layer operations."""
    scenario_id: str = Field(..., description="Scenario ID")
    status: str = Field(..., description="Current status")
    message: str = Field(..., description="Operation result message")
    forecast_impact: Optional[Dict[str, Any]] = Field(
        None,
        description="Impact on forecast if available"
    )


# ============================================================================
# GOAL PLANNING
# ============================================================================

class GoalPlanRequest(BaseModel):
    """Request to build scenarios for a goal."""
    user_id: str = Field(..., description="User ID")
    goal: str = Field(..., description="Goal description")
    constraints: Dict[str, Any] = Field(default_factory=dict, description="Constraints on the goal")


class GoalPlanResponse(BaseModel):
    """Response with scenarios to achieve a goal."""
    goal: str = Field(..., description="The goal that was analyzed")
    scenarios: List[Dict[str, Any]] = Field(default_factory=list, description="Suggested scenarios")
    analysis: str = Field(..., description="Analysis of how to achieve the goal")


# ============================================================================
# CONTEXT PAYLOAD (internal use)
# ============================================================================

class ForecastWeekSummary(BaseModel):
    """Summary of a single forecast week."""
    week_number: int
    week_start: str
    ending_balance: str
    cash_in: str
    cash_out: str
    net_change: str


class RuleStatus(BaseModel):
    """Status of a financial rule."""
    rule_id: str
    rule_type: str
    name: str
    is_breached: bool
    severity: str
    breach_week: Optional[int] = None
    action_window_weeks: Optional[int] = None


class ActiveScenarioSummary(BaseModel):
    """Summary of an active scenario."""
    scenario_id: str
    name: str
    scenario_type: str
    status: str
    impact_week_13: Optional[str] = None
    layers: List[Dict[str, Any]] = Field(default_factory=list)


class ContextPayload(BaseModel):
    """Deterministic context injected into Agent2."""
    # User info
    user_id: str

    # Current cash position
    starting_cash: str
    as_of_date: str

    # Base forecast summary
    base_forecast: Dict[str, Any]
    forecast_weeks: List[ForecastWeekSummary]

    # Rules and evaluations
    buffer_rule: Optional[Dict[str, Any]] = None
    rule_evaluations: List[RuleStatus] = Field(default_factory=list)

    # Active scenarios
    active_scenarios: List[ActiveScenarioSummary] = Field(default_factory=list)

    # Key metrics
    runway_weeks: int
    lowest_cash_week: int
    lowest_cash_amount: str

    # Clients and expenses summary
    clients_summary: List[Dict[str, Any]] = Field(default_factory=list)
    expenses_summary: List[Dict[str, Any]] = Field(default_factory=list)

    # Timestamp
    generated_at: str
