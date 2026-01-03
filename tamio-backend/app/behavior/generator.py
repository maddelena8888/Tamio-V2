"""
Scenario Generator - Phase 3: Generate scenarios from triggered behaviors.

This module implements:
1. Scenario template instantiation
2. Parameter population from trigger context
3. Impact estimation
"""
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from decimal import Decimal

from app.behavior.models import TriggeredScenario, BehaviorMetric, TriggerStatus
from app.scenarios.models import Scenario, ScenarioType, ScenarioStatus


# =============================================================================
# Scenario Templates
# =============================================================================

SCENARIO_TEMPLATES = {
    # Payment Delay Scenarios
    "payment_delay": {
        "name_format": "{client_name} pays {delay_weeks} weeks late",
        "description_format": "Model the impact of {client_name} delaying payment by {delay_weeks} weeks for {cycles} billing cycles.",
        "default_parameters": {
            "delay_weeks": 3,
            "cycles": 2,
            "partial_payment_pct": 100,
        },
        "impact_factors": {
            "cash_flow_delay": True,
            "concentration_amplifier": True,  # Impact amplified by client concentration
        }
    },

    # Client Loss Scenarios
    "client_loss": {
        "name_format": "Lose {client_name} ({revenue_pct}% of revenue)",
        "description_format": "Model the impact of losing {client_name} who represents {revenue_pct}% of monthly revenue.",
        "default_parameters": {
            "effective_date": None,  # Auto-populated
            "notice_weeks": 4,
            "wind_down_pattern": "immediate",  # or "gradual"
        },
        "impact_factors": {
            "revenue_loss": True,
            "runway_impact": True,
        }
    },

    # Client Gain Scenarios
    "client_gain": {
        "name_format": "Win new client: {monthly_amount}/month",
        "description_format": "Model adding a new client bringing {monthly_amount} monthly revenue starting {start_date}.",
        "default_parameters": {
            "monthly_amount": 5000,
            "start_date": None,
            "ramp_up_weeks": 4,
            "payment_terms_days": 30,
        },
        "impact_factors": {
            "revenue_gain": True,
            "concentration_change": True,
        }
    },

    # Expense Scenarios
    "increased_expense": {
        "name_format": "{category} expenses increase by {increase_pct}%",
        "description_format": "Model {category} expenses increasing by {increase_pct}% for {duration_weeks} weeks.",
        "default_parameters": {
            "category": "general",
            "increase_pct": 10,
            "duration_weeks": 6,
        },
        "impact_factors": {
            "expense_increase": True,
            "buffer_impact": True,
        }
    },

    "decreased_expense": {
        "name_format": "Reduce {category} by {decrease_pct}%",
        "description_format": "Model reducing {category} expenses by {decrease_pct}% for {duration_weeks} weeks.",
        "default_parameters": {
            "category": "discretionary",
            "decrease_pct": 20,
            "duration_weeks": 12,
        },
        "impact_factors": {
            "expense_reduction": True,
            "buffer_improvement": True,
        }
    },

    # Payment Delay Out (AP)
    "payment_delay_out": {
        "name_format": "Delay {expense_name} payment by {delay_weeks} weeks",
        "description_format": "Model delaying payment for {expense_name} by {delay_weeks} weeks to manage cash flow.",
        "default_parameters": {
            "expense_id": None,
            "delay_weeks": 2,
            "negotiation_required": True,
        },
        "impact_factors": {
            "cash_preservation": True,
            "supplier_relationship": True,
        }
    },

    # Hiring/Firing
    "hiring": {
        "name_format": "Hire: {role} at {salary}/month",
        "description_format": "Model hiring a {role} with a monthly cost of {salary} starting {start_date}.",
        "default_parameters": {
            "role": "new hire",
            "salary": 5000,
            "start_date": None,
            "ramp_up_months": 1,
        },
        "impact_factors": {
            "expense_increase": True,
            "productivity_lag": True,
        }
    },

    "firing": {
        "name_format": "Let go: {role} (-{savings}/month)",
        "description_format": "Model letting go of {role} to save {savings}/month after {notice_weeks} weeks notice.",
        "default_parameters": {
            "role": "employee",
            "savings": 5000,
            "notice_weeks": 2,
            "severance_weeks": 4,
        },
        "impact_factors": {
            "expense_reduction": True,
            "severance_cost": True,
        }
    },

    # Contractor Changes
    "contractor_gain": {
        "name_format": "Add contractor: {rate}/month",
        "description_format": "Model adding a contractor at {rate}/month for {duration_weeks} weeks.",
        "default_parameters": {
            "rate": 3000,
            "duration_weeks": 12,
            "start_date": None,
        },
        "impact_factors": {
            "expense_increase": True,
            "flexibility": True,
        }
    },

    "contractor_loss": {
        "name_format": "End contractor engagement (-{savings}/month)",
        "description_format": "Model ending a contractor engagement saving {savings}/month.",
        "default_parameters": {
            "savings": 3000,
            "notice_weeks": 2,
        },
        "impact_factors": {
            "expense_reduction": True,
        }
    },
}


# =============================================================================
# Scenario Generation
# =============================================================================

def _format_template(template: str, context: Dict[str, Any]) -> str:
    """Format a template string with context values."""
    try:
        return template.format(**context)
    except KeyError:
        # Fill in missing keys with placeholders
        import re
        placeholders = re.findall(r'\{(\w+)\}', template)
        filled_context = {k: context.get(k, f"[{k}]") for k in placeholders}
        return template.format(**filled_context)


def generate_scenario_from_template(
    triggered_scenario: TriggeredScenario,
    user_id: str,
) -> Scenario:
    """
    Generate a Scenario from a TriggeredScenario.

    This creates a ready-to-run scenario that can be:
    1. Presented to user for review
    2. Run through the forecast engine
    3. Evaluated against financial rules
    """
    scenario_type = triggered_scenario.scenario_type
    template = SCENARIO_TEMPLATES.get(scenario_type, {})
    trigger_context = triggered_scenario.trigger_context
    trigger_params = triggered_scenario.scenario_parameters

    # Build context for template formatting
    context = {
        **trigger_context.get("context_data", {}),
        **trigger_params,
    }

    # Add computed values
    if "monthly_amount" in context:
        context["revenue_pct"] = round(float(context.get("cash_weighted_share", 0)), 1)

    # Format name and description
    name = _format_template(
        template.get("name_format", triggered_scenario.scenario_name),
        context
    )
    description = _format_template(
        template.get("description_format", triggered_scenario.scenario_description or ""),
        context
    )

    # Merge default parameters with trigger parameters
    parameters = {
        **template.get("default_parameters", {}),
        **trigger_params,
    }

    # Auto-populate dates if not set
    if parameters.get("start_date") is None:
        parameters["start_date"] = (date.today() + timedelta(days=7)).isoformat()
    if parameters.get("effective_date") is None:
        parameters["effective_date"] = date.today().isoformat()

    # Build scope config
    scope_config = {}
    if trigger_context.get("entity_type") == "client":
        scope_config["client_ids"] = [trigger_context.get("entity_id")]
    elif trigger_context.get("entity_type") == "category":
        scope_config["categories"] = [trigger_context.get("entity_id")]

    scope_config["effective_date"] = parameters.get("effective_date")

    return Scenario(
        user_id=user_id,
        name=name,
        description=description,
        scenario_type=scenario_type,
        status=ScenarioStatus.DRAFT.value,
        entry_path="tamio_suggested",
        suggested_reason=f"Triggered by: {triggered_scenario.scenario_name}",
        scope_config=scope_config,
        parameters=parameters,
        linked_scenarios=[],
    )


async def generate_scenarios_from_triggers(
    db: AsyncSession,
    user_id: str,
    triggered_scenarios: List[TriggeredScenario],
    auto_create: bool = False
) -> List[Dict[str, Any]]:
    """
    Generate scenario definitions from triggered scenarios.

    If auto_create is True, creates the scenarios in the database.
    Otherwise, returns scenario definitions for preview.
    """
    generated = []

    for ts in triggered_scenarios:
        scenario = generate_scenario_from_template(ts, user_id)

        if auto_create:
            db.add(scenario)
            ts.scenario_id = scenario.id
            ts.status = TriggerStatus.ACTIVE.value

        generated.append({
            "triggered_scenario_id": ts.id,
            "trigger_name": ts.scenario_name,
            "scenario_preview": {
                "name": scenario.name,
                "description": scenario.description,
                "scenario_type": scenario.scenario_type,
                "scope_config": scenario.scope_config,
                "parameters": scenario.parameters,
            },
            "recommended_actions": ts.recommended_actions,
            "severity": ts.severity,
            "estimated_impact": ts.estimated_impact,
        })

    if auto_create:
        await db.commit()

    return generated


# =============================================================================
# Action Recommendations
# =============================================================================

def get_recommended_actions(
    triggered_scenario: TriggeredScenario,
    behavior_context: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Get detailed action recommendations for a triggered scenario.

    Each action includes:
    - action_type: Type of action (communication, adjustment, control)
    - description: Human-readable description
    - urgency: How soon to act
    - automated: Whether TAMI can draft/execute this
    - parameters: Action-specific parameters
    """
    actions = []
    severity = triggered_scenario.severity
    scenario_type = triggered_scenario.scenario_type

    # Map trigger type to recommended actions
    if scenario_type == "payment_delay":
        actions.extend([
            {
                "action_type": "communication",
                "description": "Draft payment reminder sequence",
                "urgency": "high" if severity == "high" else "medium",
                "automated": True,
                "parameters": {
                    "template": "payment_reminder",
                    "escalation_levels": 3,
                }
            },
            {
                "action_type": "adjustment",
                "description": "Reduce forecast confidence for this client",
                "urgency": "medium",
                "automated": True,
                "parameters": {
                    "confidence_reduction": 0.2,
                }
            },
            {
                "action_type": "control",
                "description": "Recommend buffer hold until payment received",
                "urgency": "high" if severity == "critical" else "medium",
                "automated": False,
                "parameters": {
                    "buffer_hold_pct": 0.1,
                }
            },
        ])

    elif scenario_type == "client_loss":
        actions.extend([
            {
                "action_type": "analysis",
                "description": "Run churn impact analysis",
                "urgency": "high",
                "automated": True,
                "parameters": {}
            },
            {
                "action_type": "adjustment",
                "description": "Update forecast to exclude client revenue",
                "urgency": "medium",
                "automated": True,
                "parameters": {
                    "phase_out_weeks": 4,
                }
            },
            {
                "action_type": "control",
                "description": "Review AP commitments for potential delays",
                "urgency": "medium",
                "automated": False,
                "parameters": {}
            },
        ])

    elif scenario_type in ("increased_expense", "decreased_expense"):
        actions.extend([
            {
                "action_type": "control",
                "description": "Flag approvals in affected category",
                "urgency": "medium",
                "automated": True,
                "parameters": {
                    "approval_threshold": 500,
                }
            },
            {
                "action_type": "adjustment",
                "description": "Update expense budget forecast",
                "urgency": "low",
                "automated": True,
                "parameters": {}
            },
        ])

    elif scenario_type == "payment_delay_out":
        # Buffer stress actions
        actions.extend([
            {
                "action_type": "communication",
                "description": "AR escalation campaign",
                "urgency": "high",
                "automated": True,
                "parameters": {
                    "campaign_type": "collections",
                }
            },
            {
                "action_type": "control",
                "description": "AP reprioritization review",
                "urgency": "high",
                "automated": False,
                "parameters": {
                    "review_scope": "next_30_days",
                }
            },
            {
                "action_type": "control",
                "description": "Spending freeze proposal",
                "urgency": "high" if severity == "critical" else "medium",
                "automated": False,
                "parameters": {
                    "freeze_categories": ["discretionary"],
                }
            },
        ])

    # Add the trigger's own recommended actions
    for action_text in triggered_scenario.recommended_actions:
        if not any(a["description"] == action_text for a in actions):
            actions.append({
                "action_type": "recommendation",
                "description": action_text,
                "urgency": "medium",
                "automated": False,
                "parameters": {}
            })

    return actions


# =============================================================================
# Impact Estimation
# =============================================================================

def estimate_scenario_impact(
    triggered_scenario: TriggeredScenario,
    current_metrics: Dict[str, float]
) -> Dict[str, Any]:
    """
    Estimate the cash flow impact of a scenario.

    Returns impact metrics including:
    - cash_impact: Net cash effect
    - weeks_affected: Duration of impact
    - buffer_impact_pct: Effect on buffer as percentage
    - risk_delta: Change in overall risk
    """
    scenario_type = triggered_scenario.scenario_type
    params = triggered_scenario.scenario_parameters
    context = triggered_scenario.trigger_context.get("context_data", {})

    impact = {
        "cash_impact": 0,
        "cash_impact_weekly": 0,
        "weeks_affected": 4,
        "buffer_impact_pct": 0,
        "risk_delta": 0,
        "description": "",
    }

    monthly_amount = float(context.get("monthly_amount", 0))

    if scenario_type == "payment_delay":
        delay_weeks = params.get("delay_weeks", 3)
        cycles = params.get("cycles", 1)

        # Delayed cash = monthly amount * cycles delayed
        impact["cash_impact"] = -monthly_amount * cycles
        impact["cash_impact_weekly"] = -monthly_amount / 4
        impact["weeks_affected"] = delay_weeks * cycles
        impact["description"] = f"Cash delayed by ~${abs(impact['cash_impact']):,.0f} for {impact['weeks_affected']} weeks"

    elif scenario_type == "client_loss":
        # Permanent revenue loss
        impact["cash_impact"] = -monthly_amount * 12  # Annual impact
        impact["cash_impact_weekly"] = -monthly_amount / 4
        impact["weeks_affected"] = 52
        impact["description"] = f"Annual revenue loss of ~${abs(impact['cash_impact']):,.0f}"

    elif scenario_type == "increased_expense":
        increase_pct = params.get("increase_pct", 10) / 100
        duration_weeks = params.get("duration_weeks", 6)

        impact["cash_impact"] = -monthly_amount * increase_pct * (duration_weeks / 4)
        impact["cash_impact_weekly"] = -monthly_amount * increase_pct / 4
        impact["weeks_affected"] = duration_weeks
        impact["description"] = f"Additional expense of ~${abs(impact['cash_impact']):,.0f} over {duration_weeks} weeks"

    elif scenario_type == "decreased_expense":
        decrease_pct = params.get("decrease_pct", 20) / 100
        duration_weeks = params.get("duration_weeks", 12)

        impact["cash_impact"] = monthly_amount * decrease_pct * (duration_weeks / 4)
        impact["cash_impact_weekly"] = monthly_amount * decrease_pct / 4
        impact["weeks_affected"] = duration_weeks
        impact["description"] = f"Expense savings of ~${impact['cash_impact']:,.0f} over {duration_weeks} weeks"

    # Calculate buffer impact
    current_buffer = current_metrics.get("buffer", 50000)
    if current_buffer > 0:
        impact["buffer_impact_pct"] = round(impact["cash_impact"] / current_buffer * 100, 1)

    # Calculate risk delta (simplified)
    if impact["cash_impact"] < 0:
        impact["risk_delta"] = min(20, abs(impact["buffer_impact_pct"]) / 2)
    else:
        impact["risk_delta"] = max(-20, -impact["buffer_impact_pct"] / 2)

    return impact
