"""TAMI Tools - OpenAI function calling definitions and dispatcher.

This module defines the tools that Agent2 can call, and the dispatcher
that executes them against the existing scenario engine.
"""
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.scenarios import models as scenario_models
from app.scenarios import schemas as scenario_schemas
from app.scenarios.engine import (
    build_scenario_layer,
    compute_scenario_forecast,
    build_scenario_layer_for_type,
)
from app.scenarios.rule_engine import (
    evaluate_rules,
    generate_decision_signals,
    suggest_scenarios as suggest_scenarios_engine,
)
from app.forecast.engine_v2 import calculate_forecast_v2 as calculate_13_week_forecast
from app.scenarios.pipeline.dependencies import get_suggested_scenarios as get_dependent_suggestions
from app.scenarios.pipeline.types import ScenarioTypeEnum
from sqlalchemy import select


# ============================================================================
# TOOL SCHEMAS FOR OPENAI
# ============================================================================

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "scenario_create_or_update_layer",
            "description": "Create a new scenario layer or update an existing one. Use this when the user wants to model a what-if situation like losing a client, hiring, or changing expenses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scenario_type": {
                        "type": "string",
                        "enum": [
                            "payment_delay",
                            "client_loss",
                            "client_gain",
                            "client_change",
                            "hiring",
                            "firing",
                            "contractor_gain",
                            "contractor_loss",
                            "increased_expense",
                            "decreased_expense",
                            "payment_delay_out"
                        ],
                        "description": "Type of scenario to create"
                    },
                    "scope": {
                        "type": "object",
                        "description": "Scope configuration (e.g., client_id for client scenarios, bucket_id for expense scenarios)",
                        "properties": {
                            "client_id": {"type": "string"},
                            "bucket_id": {"type": "string"},
                        }
                    },
                    "params": {
                        "type": "object",
                        "description": "Scenario-specific parameters",
                        "properties": {
                            "effective_date": {"type": "string", "description": "ISO date when scenario takes effect"},
                            "start_date": {"type": "string", "description": "Start date for gains/hires"},
                            "end_date": {"type": "string", "description": "End date for losses/firings"},
                            "monthly_amount": {"type": "number", "description": "Monthly amount for recurring items"},
                            "delay_weeks": {"type": "integer", "description": "Weeks of delay for payment scenarios"},
                            "amount": {"type": "number", "description": "One-time or total amount"},
                        }
                    },
                    "linked_changes": {
                        "type": "object",
                        "description": "Optional linked changes (e.g., reducing contractors when losing a client)",
                        "properties": {
                            "contractor_reduction": {"type": "number"},
                            "expense_reduction": {"type": "number"},
                        }
                    },
                    "name": {
                        "type": "string",
                        "description": "Optional name for the scenario"
                    }
                },
                "required": ["scenario_type", "params"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scenario_iterate_layer",
            "description": "Update parameters of an existing scenario layer. Use this when the user wants to adjust a scenario they're already building.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scenario_id": {
                        "type": "string",
                        "description": "ID of the scenario to update"
                    },
                    "patch": {
                        "type": "object",
                        "description": "Fields to update in the scenario parameters",
                        "properties": {
                            "effective_date": {"type": "string"},
                            "start_date": {"type": "string"},
                            "end_date": {"type": "string"},
                            "monthly_amount": {"type": "number"},
                            "delay_weeks": {"type": "integer"},
                            "amount": {"type": "number"},
                        }
                    }
                },
                "required": ["scenario_id", "patch"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scenario_discard_layer",
            "description": "Discard a scenario layer. Use this when the user wants to cancel or remove a scenario they were building.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scenario_id": {
                        "type": "string",
                        "description": "ID of the scenario to discard"
                    }
                },
                "required": ["scenario_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scenario_get_suggestions",
            "description": "Get suggested scenarios based on current forecast state. Use this when the user asks what scenarios they should consider or wants recommendations.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "plan_build_goal_scenarios",
            "description": "Build scenarios to achieve a financial goal. Use this when the user describes a goal like 'extend runway to 6 months' or 'reduce expenses by 20%'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "Description of the financial goal"
                    },
                    "constraints": {
                        "type": "object",
                        "description": "Constraints on achieving the goal",
                        "properties": {
                            "max_expense_reduction_pct": {"type": "number"},
                            "no_layoffs": {"type": "boolean"},
                            "protect_clients": {"type": "array", "items": {"type": "string"}},
                        }
                    }
                },
                "required": ["goal"]
            }
        }
    }
]


def get_tool_schemas() -> List[Dict[str, Any]]:
    """Get the tool schemas for OpenAI function calling."""
    return TOOL_SCHEMAS


# ============================================================================
# TOOL DISPATCHER
# ============================================================================

async def dispatch_tool(
    db: AsyncSession,
    user_id: str,
    tool_name: str,
    tool_args: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Dispatch a tool call to the appropriate handler.

    Args:
        db: Database session
        user_id: User ID for context
        tool_name: Name of the tool to call
        tool_args: Arguments for the tool

    Returns:
        Tool execution result
    """
    if tool_name == "scenario_create_or_update_layer":
        return await _create_or_update_layer(db, user_id, tool_args)
    elif tool_name == "scenario_iterate_layer":
        return await _iterate_layer(db, user_id, tool_args)
    elif tool_name == "scenario_discard_layer":
        return await _discard_layer(db, user_id, tool_args)
    elif tool_name == "scenario_get_suggestions":
        return await _get_suggestions(db, user_id, tool_args)
    elif tool_name == "plan_build_goal_scenarios":
        return await _build_goal_scenarios(db, user_id, tool_args)
    else:
        return {"error": f"Unknown tool: {tool_name}"}


async def _create_or_update_layer(
    db: AsyncSession,
    user_id: str,
    args: Dict[str, Any]
) -> Dict[str, Any]:
    """Create or update a scenario layer."""
    scenario_type = args.get("scenario_type")
    scope = args.get("scope", {})
    params = args.get("params", {})
    linked_changes = args.get("linked_changes")
    name = args.get("name") or f"{scenario_type.replace('_', ' ').title()} Scenario"

    # Create the scenario
    scenario = scenario_models.Scenario(
        user_id=user_id,
        name=name,
        description=f"Created by TAMI",
        scenario_type=scenario_type,
        entry_path="tami",
        scope_config=scope,
        parameters=params,
        linked_scenarios=[] if linked_changes else None,
        status="draft"
    )
    db.add(scenario)
    await db.flush()

    # Build scenario events
    scenario_events = await build_scenario_layer(db, scenario)
    for event in scenario_events:
        db.add(event)

    # Update status to active
    scenario.status = "active"
    await db.commit()
    await db.refresh(scenario)

    # Compute forecast impact
    try:
        comparison = await compute_scenario_forecast(db, user_id, scenario.id)
        base_week13 = float(comparison["base_forecast"]["weeks"][-1]["ending_balance"])
        scenario_week13 = float(comparison["scenario_forecast"]["weeks"][-1]["ending_balance"])
        impact = scenario_week13 - base_week13
    except Exception:
        impact = None

    return {
        "success": True,
        "scenario_id": scenario.id,
        "name": scenario.name,
        "status": scenario.status,
        "events_generated": len(scenario_events),
        "impact_week_13": impact,
        "message": f"Created scenario '{name}' with {len(scenario_events)} events"
    }


async def _iterate_layer(
    db: AsyncSession,
    user_id: str,
    args: Dict[str, Any]
) -> Dict[str, Any]:
    """Update an existing scenario layer."""
    scenario_id = args.get("scenario_id")
    patch = args.get("patch", {})

    # Load scenario
    result = await db.execute(
        select(scenario_models.Scenario).where(
            scenario_models.Scenario.id == scenario_id,
            scenario_models.Scenario.user_id == user_id
        )
    )
    scenario = result.scalar_one_or_none()

    if not scenario:
        return {"success": False, "error": "Scenario not found"}

    # Update parameters
    current_params = scenario.parameters or {}
    current_params.update(patch)
    scenario.parameters = current_params

    # Delete old events and rebuild
    await db.execute(
        select(scenario_models.ScenarioEvent).where(
            scenario_models.ScenarioEvent.scenario_id == scenario_id
        )
    )

    # Rebuild scenario events
    scenario_events = await build_scenario_layer(db, scenario)
    for event in scenario_events:
        db.add(event)

    await db.commit()

    # Compute new impact
    try:
        comparison = await compute_scenario_forecast(db, user_id, scenario.id)
        base_week13 = float(comparison["base_forecast"]["weeks"][-1]["ending_balance"])
        scenario_week13 = float(comparison["scenario_forecast"]["weeks"][-1]["ending_balance"])
        impact = scenario_week13 - base_week13
    except Exception:
        impact = None

    return {
        "success": True,
        "scenario_id": scenario.id,
        "updated_params": current_params,
        "impact_week_13": impact,
        "message": f"Updated scenario '{scenario.name}'"
    }


async def _discard_layer(
    db: AsyncSession,
    user_id: str,
    args: Dict[str, Any]
) -> Dict[str, Any]:
    """Discard a scenario layer."""
    scenario_id = args.get("scenario_id")

    # Load scenario
    result = await db.execute(
        select(scenario_models.Scenario).where(
            scenario_models.Scenario.id == scenario_id,
            scenario_models.Scenario.user_id == user_id
        )
    )
    scenario = result.scalar_one_or_none()

    if not scenario:
        return {"success": False, "error": "Scenario not found"}

    # Mark as discarded
    scenario.status = "discarded"
    await db.commit()

    return {
        "success": True,
        "scenario_id": scenario_id,
        "message": f"Discarded scenario '{scenario.name}'"
    }


async def _get_suggestions(
    db: AsyncSession,
    user_id: str,
    args: Dict[str, Any]
) -> Dict[str, Any]:
    """Get scenario suggestions based on current state."""
    # Get base forecast
    base_forecast = await calculate_13_week_forecast(db, user_id)

    # Evaluate rules
    evaluations = await evaluate_rules(db, user_id, base_forecast)

    # Get suggestions from engine
    suggestions = await suggest_scenarios_engine(db, user_id, base_forecast, evaluations)

    return {
        "success": True,
        "suggestions": suggestions,
        "based_on": {
            "runway_weeks": base_forecast.get("summary", {}).get("runway_weeks"),
            "has_rule_breaches": any(e.is_breached for e in evaluations)
        }
    }


async def _build_goal_scenarios(
    db: AsyncSession,
    user_id: str,
    args: Dict[str, Any]
) -> Dict[str, Any]:
    """Build scenarios to achieve a financial goal."""
    goal = args.get("goal", "")
    constraints = args.get("constraints", {})

    # Get current state
    base_forecast = await calculate_13_week_forecast(db, user_id)
    current_runway = base_forecast.get("summary", {}).get("runway_weeks", 13)

    # Parse goal to determine target
    suggested_scenarios = []

    goal_lower = goal.lower()

    if "runway" in goal_lower or "months" in goal_lower:
        # Goal is about extending runway
        # Calculate how much cash we need to extend

        # Get current monthly burn
        total_out = float(base_forecast.get("summary", {}).get("total_cash_out", 0))
        weekly_burn = total_out / 13
        monthly_burn = weekly_burn * 4.33

        suggested_scenarios.append({
            "type": "analyze_runway",
            "description": f"Your current runway is {current_runway} weeks. Monthly burn rate is approximately ${monthly_burn:,.0f}.",
            "options": [
                {
                    "approach": "reduce_expenses",
                    "scenario_type": "decreased_expense",
                    "description": "Reduce monthly expenses to extend runway"
                },
                {
                    "approach": "increase_revenue",
                    "scenario_type": "client_gain",
                    "description": "Add new revenue to improve cash position"
                },
                {
                    "approach": "delay_payments",
                    "scenario_type": "payment_delay_out",
                    "description": "Delay vendor payments to preserve cash"
                }
            ]
        })

    elif "reduce" in goal_lower and "expense" in goal_lower:
        # Goal is about reducing expenses
        suggested_scenarios.append({
            "type": "expense_reduction",
            "description": "To reduce expenses, consider these scenarios:",
            "options": [
                {
                    "approach": "contractor_reduction",
                    "scenario_type": "contractor_loss",
                    "description": "Reduce contractor costs"
                },
                {
                    "approach": "expense_cut",
                    "scenario_type": "decreased_expense",
                    "description": "Cut specific expense categories"
                }
            ]
        })

    elif "client" in goal_lower:
        # Goal is about client changes
        suggested_scenarios.append({
            "type": "client_planning",
            "description": "Client-related scenario options:",
            "options": [
                {
                    "approach": "prepare_for_loss",
                    "scenario_type": "client_loss",
                    "description": "Model losing a client to prepare"
                },
                {
                    "approach": "plan_new_client",
                    "scenario_type": "client_gain",
                    "description": "Model adding a new client"
                }
            ]
        })
    else:
        # Generic goal - provide general options
        suggested_scenarios.append({
            "type": "general_planning",
            "description": f"To work towards your goal: '{goal}', consider exploring these scenario types:",
            "options": [
                {"scenario_type": "client_gain", "description": "Add revenue"},
                {"scenario_type": "decreased_expense", "description": "Reduce costs"},
                {"scenario_type": "client_loss", "description": "Stress test against losses"},
            ]
        })

    return {
        "success": True,
        "goal": goal,
        "current_state": {
            "runway_weeks": current_runway,
            "starting_cash": base_forecast.get("starting_cash"),
        },
        "suggested_scenarios": suggested_scenarios,
        "constraints_applied": constraints
    }
