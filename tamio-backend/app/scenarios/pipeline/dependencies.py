"""
Scenario Dependencies - Maps primary scenarios to suggested dependent scenarios.

This module defines the relationships between scenario types based on real-world
business logic. When a user creates a scenario, the system suggests related
scenarios that typically follow or should be considered together.

Example: If you lose a client, you might also:
- Reduce contractor costs
- Cancel software subscriptions
- Delay vendor payments

These dependencies are presented as optional prompts to the user during scenario creation.
"""

from typing import List, Dict, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field

from app.scenarios.pipeline.types import ScenarioTypeEnum


class DependencyDirection(str, Enum):
    """Direction of cash flow impact."""
    REDUCE_COSTS = "reduce_costs"  # Suggests reducing expenses
    INCREASE_COSTS = "increase_costs"  # Suggests new expenses
    REDUCE_REVENUE = "reduce_revenue"  # Suggests revenue impact
    INCREASE_REVENUE = "increase_revenue"  # Suggests new revenue
    TIMING_CHANGE = "timing_change"  # Suggests payment timing changes


class SuggestedScenario(BaseModel):
    """A suggested dependent scenario based on the primary scenario."""
    scenario_type: ScenarioTypeEnum
    title: str = Field(..., description="User-friendly title for the suggestion")
    description: str = Field(..., description="Why this scenario might be relevant")
    question: str = Field(..., description="Question to ask the user")
    direction: DependencyDirection
    typical_lag_weeks: int = Field(0, ge=0, le=12, description="Typical delay before this takes effect")
    confidence: str = Field("medium", description="How likely this is relevant (high/medium/low)")

    # Pre-filled parameters if the user accepts
    prefill_params: Dict[str, Any] = Field(default_factory=dict)

    # Reference to parent scenario
    parent_param_key: Optional[str] = Field(None, description="Key to link back to parent")


# =============================================================================
# DEPENDENCY DEFINITIONS
# =============================================================================

# Core dependency mappings: what scenarios typically follow each other
SCENARIO_DEPENDENCIES: Dict[ScenarioTypeEnum, List[SuggestedScenario]] = {

    # -------------------------------------------------------------------------
    # CLIENT LOSS: Major cash-in reduction, suggests cost cutting
    # -------------------------------------------------------------------------
    ScenarioTypeEnum.CLIENT_LOSS: [
        SuggestedScenario(
            scenario_type=ScenarioTypeEnum.CONTRACTOR_LOSS,
            title="Reduce Contractor Costs",
            description="With reduced workload, you may need fewer contractors",
            question="Will you reduce contractor spending due to this client loss?",
            direction=DependencyDirection.REDUCE_COSTS,
            typical_lag_weeks=2,
            confidence="high",
            parent_param_key="linked_client_loss_id",
        ),
        SuggestedScenario(
            scenario_type=ScenarioTypeEnum.DECREASED_EXPENSE,
            title="Cancel Software/Tools",
            description="You may be able to cancel or downgrade software licenses",
            question="Are there any tools or software subscriptions you can reduce?",
            direction=DependencyDirection.REDUCE_COSTS,
            typical_lag_weeks=0,
            confidence="medium",
            prefill_params={"category": "software"},
        ),
        SuggestedScenario(
            scenario_type=ScenarioTypeEnum.FIRING,
            title="Reduce Headcount",
            description="Significant client loss may require staffing adjustments",
            question="Will you need to reduce permanent staff?",
            direction=DependencyDirection.REDUCE_COSTS,
            typical_lag_weeks=4,
            confidence="low",
        ),
        SuggestedScenario(
            scenario_type=ScenarioTypeEnum.PAYMENT_DELAY_OUT,
            title="Delay Vendor Payments",
            description="To manage cash flow, you might delay some vendor payments",
            question="Do you need to delay any vendor payments to manage cash flow?",
            direction=DependencyDirection.TIMING_CHANGE,
            typical_lag_weeks=0,
            confidence="medium",
        ),
    ],

    # -------------------------------------------------------------------------
    # CLIENT GAIN: New revenue, may require capacity investment
    # -------------------------------------------------------------------------
    ScenarioTypeEnum.CLIENT_GAIN: [
        SuggestedScenario(
            scenario_type=ScenarioTypeEnum.CONTRACTOR_GAIN,
            title="Add Contractors",
            description="New client work may require additional contractor capacity",
            question="Will you need to bring on contractors for this client?",
            direction=DependencyDirection.INCREASE_COSTS,
            typical_lag_weeks=1,
            confidence="high",
        ),
        SuggestedScenario(
            scenario_type=ScenarioTypeEnum.HIRING,
            title="Hire New Team Members",
            description="Growing client base may justify new permanent hires",
            question="Will this client revenue support a new hire?",
            direction=DependencyDirection.INCREASE_COSTS,
            typical_lag_weeks=4,
            confidence="medium",
        ),
        SuggestedScenario(
            scenario_type=ScenarioTypeEnum.INCREASED_EXPENSE,
            title="New Tools/Software",
            description="You may need additional tools to serve this client",
            question="Do you need new tools or software for this client?",
            direction=DependencyDirection.INCREASE_COSTS,
            typical_lag_weeks=0,
            confidence="medium",
            prefill_params={"category": "software"},
        ),
    ],

    # -------------------------------------------------------------------------
    # HIRING: Adding payroll costs, may be tied to revenue growth
    # -------------------------------------------------------------------------
    ScenarioTypeEnum.HIRING: [
        SuggestedScenario(
            scenario_type=ScenarioTypeEnum.CLIENT_GAIN,
            title="Expected Revenue Growth",
            description="This hire may be tied to winning new clients",
            question="Is this hire tied to expected new client revenue?",
            direction=DependencyDirection.INCREASE_REVENUE,
            typical_lag_weeks=4,
            confidence="medium",
        ),
        SuggestedScenario(
            scenario_type=ScenarioTypeEnum.INCREASED_EXPENSE,
            title="Onboarding Costs",
            description="New hires often require equipment and onboarding expenses",
            question="Will there be equipment or training costs for this hire?",
            direction=DependencyDirection.INCREASE_COSTS,
            typical_lag_weeks=0,
            confidence="high",
            prefill_params={"category": "onboarding", "expense_type": "one_off"},
        ),
    ],

    # -------------------------------------------------------------------------
    # FIRING: Reducing payroll, may affect delivery capacity
    # -------------------------------------------------------------------------
    ScenarioTypeEnum.FIRING: [
        SuggestedScenario(
            scenario_type=ScenarioTypeEnum.CLIENT_LOSS,
            title="Potential Client Impact",
            description="Reduced team capacity may affect client relationships",
            question="Might any clients be affected by reduced delivery capacity?",
            direction=DependencyDirection.REDUCE_REVENUE,
            typical_lag_weeks=4,
            confidence="low",
        ),
        SuggestedScenario(
            scenario_type=ScenarioTypeEnum.CONTRACTOR_GAIN,
            title="Replace with Contractor",
            description="You might replace full-time with more flexible contractor",
            question="Will you replace this role with contractor support?",
            direction=DependencyDirection.INCREASE_COSTS,
            typical_lag_weeks=2,
            confidence="low",
        ),
        SuggestedScenario(
            scenario_type=ScenarioTypeEnum.DECREASED_EXPENSE,
            title="Cancel Unused Licenses",
            description="Fewer team members may allow canceling software licenses",
            question="Can you cancel any software licenses this person used?",
            direction=DependencyDirection.REDUCE_COSTS,
            typical_lag_weeks=0,
            confidence="medium",
            prefill_params={"category": "software"},
        ),
    ],

    # -------------------------------------------------------------------------
    # CONTRACTOR GAIN: Adding capacity, may be linked to client work
    # -------------------------------------------------------------------------
    ScenarioTypeEnum.CONTRACTOR_GAIN: [
        SuggestedScenario(
            scenario_type=ScenarioTypeEnum.CLIENT_GAIN,
            title="Link to Client Project",
            description="This contractor may be tied to specific client revenue",
            question="Is this contractor tied to a specific client or project?",
            direction=DependencyDirection.INCREASE_REVENUE,
            typical_lag_weeks=0,
            confidence="high",
        ),
    ],

    # -------------------------------------------------------------------------
    # CONTRACTOR LOSS: Reducing capacity, may affect delivery
    # -------------------------------------------------------------------------
    ScenarioTypeEnum.CONTRACTOR_LOSS: [
        SuggestedScenario(
            scenario_type=ScenarioTypeEnum.CLIENT_CHANGE,
            title="Client Scope Change",
            description="Losing this contractor may require adjusting client scope",
            question="Will any client engagements need to be adjusted?",
            direction=DependencyDirection.REDUCE_REVENUE,
            typical_lag_weeks=2,
            confidence="medium",
        ),
        SuggestedScenario(
            scenario_type=ScenarioTypeEnum.HIRING,
            title="Replace with Full-Time",
            description="You might replace contractor with permanent hire",
            question="Should this role become a full-time position?",
            direction=DependencyDirection.INCREASE_COSTS,
            typical_lag_weeks=4,
            confidence="low",
        ),
    ],

    # -------------------------------------------------------------------------
    # INCREASED EXPENSE: New costs, may trigger gates or require offsets
    # -------------------------------------------------------------------------
    ScenarioTypeEnum.INCREASED_EXPENSE: [
        SuggestedScenario(
            scenario_type=ScenarioTypeEnum.DECREASED_EXPENSE,
            title="Offset with Cost Reduction",
            description="You might offset this expense by reducing another",
            question="Can you reduce another expense to offset this cost?",
            direction=DependencyDirection.REDUCE_COSTS,
            typical_lag_weeks=0,
            confidence="low",
        ),
        SuggestedScenario(
            scenario_type=ScenarioTypeEnum.PAYMENT_DELAY_OUT,
            title="Delay Other Payments",
            description="To manage cash flow, delay other vendor payments",
            question="Should any vendor payments be delayed to manage cash flow?",
            direction=DependencyDirection.TIMING_CHANGE,
            typical_lag_weeks=0,
            confidence="medium",
        ),
    ],

    # -------------------------------------------------------------------------
    # DECREASED EXPENSE: Saving money, may have termination costs
    # -------------------------------------------------------------------------
    ScenarioTypeEnum.DECREASED_EXPENSE: [
        # Termination fees are handled inline by the handler
        # No strong external dependencies
    ],

    # -------------------------------------------------------------------------
    # PAYMENT DELAY IN: Customer paying late, may need cost adjustments
    # -------------------------------------------------------------------------
    ScenarioTypeEnum.PAYMENT_DELAY_IN: [
        SuggestedScenario(
            scenario_type=ScenarioTypeEnum.PAYMENT_DELAY_OUT,
            title="Delay Vendor Payments",
            description="Late customer payments may require delaying your payments",
            question="Do you need to delay vendor payments due to this delay?",
            direction=DependencyDirection.TIMING_CHANGE,
            typical_lag_weeks=0,
            confidence="high",
        ),
    ],

    # -------------------------------------------------------------------------
    # PAYMENT DELAY OUT: Delaying vendor payments
    # -------------------------------------------------------------------------
    ScenarioTypeEnum.PAYMENT_DELAY_OUT: [
        # Catch-up schedules and spreading are handled inline
        # No strong external dependencies
    ],

    # -------------------------------------------------------------------------
    # CLIENT CHANGE: Adjusting existing client relationship
    # -------------------------------------------------------------------------
    ScenarioTypeEnum.CLIENT_CHANGE: [
        SuggestedScenario(
            scenario_type=ScenarioTypeEnum.CONTRACTOR_LOSS,
            title="Reduce Contractor Support",
            description="Changed scope may allow reducing contractor costs",
            question="Can you reduce contractor support for this client?",
            direction=DependencyDirection.REDUCE_COSTS,
            typical_lag_weeks=2,
            confidence="medium",
        ),
        SuggestedScenario(
            scenario_type=ScenarioTypeEnum.CONTRACTOR_GAIN,
            title="Add Contractor Support",
            description="Changed scope may require additional contractors",
            question="Do you need more contractor support for this client?",
            direction=DependencyDirection.INCREASE_COSTS,
            typical_lag_weeks=1,
            confidence="medium",
        ),
    ],
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_suggested_scenarios(
    scenario_type: ScenarioTypeEnum,
    include_low_confidence: bool = True,
) -> List[SuggestedScenario]:
    """
    Get suggested dependent scenarios for a given scenario type.

    Args:
        scenario_type: The primary scenario type
        include_low_confidence: Whether to include low-confidence suggestions

    Returns:
        List of suggested scenarios
    """
    suggestions = SCENARIO_DEPENDENCIES.get(scenario_type, [])

    if not include_low_confidence:
        suggestions = [s for s in suggestions if s.confidence != "low"]

    return suggestions


def get_high_priority_suggestions(
    scenario_type: ScenarioTypeEnum,
) -> List[SuggestedScenario]:
    """Get only high-confidence suggestions for a scenario type."""
    return [
        s for s in SCENARIO_DEPENDENCIES.get(scenario_type, [])
        if s.confidence == "high"
    ]


def format_suggestions_for_ui(
    scenario_type: ScenarioTypeEnum,
    parent_scenario_id: str,
) -> List[Dict[str, Any]]:
    """
    Format suggestions for the UI response.

    Returns a list of suggestion objects ready for the frontend.
    """
    suggestions = get_suggested_scenarios(scenario_type)

    return [
        {
            "id": f"{parent_scenario_id}_suggest_{s.scenario_type.value}",
            "parent_scenario_id": parent_scenario_id,
            "scenario_type": s.scenario_type.value,
            "title": s.title,
            "description": s.description,
            "question": s.question,
            "direction": s.direction.value,
            "typical_lag_weeks": s.typical_lag_weeks,
            "confidence": s.confidence,
            "prefill_params": {
                **s.prefill_params,
                s.parent_param_key: parent_scenario_id,
            } if s.parent_param_key else s.prefill_params,
        }
        for s in suggestions
    ]


def get_reverse_dependencies(
    scenario_type: ScenarioTypeEnum,
) -> List[ScenarioTypeEnum]:
    """
    Find which scenarios suggest the given type as a dependent.

    Useful for understanding "what could lead to this scenario?"
    """
    reverse = []
    for parent_type, suggestions in SCENARIO_DEPENDENCIES.items():
        for s in suggestions:
            if s.scenario_type == scenario_type:
                reverse.append(parent_type)
                break
    return reverse
