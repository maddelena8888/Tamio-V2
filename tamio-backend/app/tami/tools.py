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
from app.forecast.engine_v2 import calculate_forecast_v2 as calculate_13_week_forecast, ScenarioContext
from app.scenarios.pipeline.dependencies import get_suggested_scenarios as get_dependent_suggestions
from app.scenarios.pipeline.types import ScenarioTypeEnum
from sqlalchemy import select
from datetime import date
from decimal import Decimal

from app.data.expenses.models import ExpenseBucket
from app.data.obligations.models import ObligationAgreement, ObligationSchedule
from app.data.clients.models import Client


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
    },
    {
        "type": "function",
        "function": {
            "name": "check_payroll_safety",
            "description": "Check whether upcoming payroll can be covered by confirmed cash and high-confidence inflows only. Use when the user asks about payroll coverage, making payroll, or payroll safety.",
            "parameters": {
                "type": "object",
                "properties": {
                    "weeks_ahead": {
                        "type": "integer",
                        "description": "Number of weeks ahead to check (default 4, max 13)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_concentration_risk",
            "description": "Analyze client revenue concentration risk using HHI and show runway impact of losing top clients. Use when the user asks about client dependency, concentration risk, or revenue diversification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "include_runway_impact": {
                        "type": "boolean",
                        "description": "Calculate runway impact for top clients (default true)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_briefing",
            "description": "Generate a prioritized briefing of the top 3 most important treasury items right now. Use when the user asks for a briefing, daily summary, status update, or 'what should I focus on today'.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
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
    elif tool_name == "check_payroll_safety":
        return await _check_payroll_safety(db, user_id, tool_args)
    elif tool_name == "analyze_concentration_risk":
        return await _analyze_concentration_risk(db, user_id, tool_args)
    elif tool_name == "generate_briefing":
        return await _generate_briefing(db, user_id, tool_args)
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


# ============================================================================
# OPERATIONAL TOOLS
# ============================================================================

async def _compute_payroll_coverage(
    db: AsyncSession,
    user_id: str,
    weeks_ahead: int = 4,
    forecast: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compute payroll coverage using high-confidence inflows only.

    Shared between check_payroll_safety and generate_briefing.
    Uses Layer 2 behavioral override: clients with active overdue invoices
    have their inflows reclassified from HIGH -> MEDIUM.
    """
    # 1. Load payroll info from ExpenseBucket
    payroll_result = await db.execute(
        select(ExpenseBucket).where(
            ExpenseBucket.user_id == user_id,
            ExpenseBucket.category == "payroll"
        )
    )
    payroll_buckets = payroll_result.scalars().all()

    if not payroll_buckets:
        return {
            "has_payroll": False,
            "message": "No payroll expense bucket found. Add a payroll expense to enable payroll safety checks."
        }

    total_monthly_payroll = sum(
        Decimal(str(b.monthly_amount or 0)) for b in payroll_buckets
    )
    total_employee_count = sum(b.employee_count or 0 for b in payroll_buckets)
    frequency = payroll_buckets[0].frequency or "monthly"

    # Per-period amount (simplified: bi_weekly = monthly/2, weekly = monthly/4)
    if frequency == "bi_weekly":
        per_period = total_monthly_payroll / Decimal("2")
    elif frequency == "weekly":
        per_period = total_monthly_payroll / Decimal("4")
    else:
        per_period = total_monthly_payroll

    # 2. Get forecast (accept pre-computed to avoid double calls from briefing)
    if forecast is None:
        forecast = await calculate_13_week_forecast(db, user_id)
    weeks = forecast.get("weeks", [])

    # 3. Layer 2: Find clients with overdue invoices
    overdue_query = await db.execute(
        select(ObligationAgreement.client_id)
        .join(ObligationSchedule)
        .where(
            ObligationAgreement.user_id == user_id,
            ObligationAgreement.client_id.isnot(None),
            ObligationSchedule.status == "overdue"
        )
        .distinct()
    )
    overdue_client_ids = {row[0] for row in overdue_query.all()}

    # Get overdue details for reporting (amount and days overdue per client)
    overdue_details: Dict[str, Dict[str, Any]] = {}
    if overdue_client_ids:
        detail_query = await db.execute(
            select(
                ObligationSchedule.estimated_amount,
                ObligationSchedule.due_date,
                ObligationAgreement.client_id,
                Client.name
            )
            .join(ObligationAgreement)
            .join(Client, Client.id == ObligationAgreement.client_id)
            .where(
                ObligationAgreement.user_id == user_id,
                ObligationAgreement.client_id.in_(overdue_client_ids),
                ObligationSchedule.status == "overdue"
            )
        )
        today = date.today()
        for amount, due_date, client_id, client_name in detail_query.all():
            if client_id not in overdue_details:
                overdue_details[client_id] = {
                    "client_name": client_name,
                    "overdue_amount": Decimal("0"),
                    "days_overdue": 0
                }
            overdue_details[client_id]["overdue_amount"] += amount
            days = (today - due_date).days
            overdue_details[client_id]["days_overdue"] = max(
                overdue_details[client_id]["days_overdue"], days
            )

    # Build obligation_id -> client_id mapping for overdue clients.
    # Needed because obligation-sourced events use obligation.id as source_id,
    # not client.id directly.
    obligation_to_client: Dict[str, str] = {}
    if overdue_client_ids:
        mapping_query = await db.execute(
            select(ObligationAgreement.id, ObligationAgreement.client_id)
            .where(
                ObligationAgreement.user_id == user_id,
                ObligationAgreement.client_id.in_(overdue_client_ids)
            )
        )
        obligation_to_client = {
            row.id: row.client_id for row in mapping_query.all()
        }

    # 4. Compute coverage per week
    weeks_ahead = min(weeks_ahead, len(weeks) - 1)  # Week 0 is current
    coverage_by_week = []
    overall_status = "safe"
    first_risk_week = None

    for i in range(1, weeks_ahead + 1):
        if i >= len(weeks):
            break

        week = weeks[i]
        starting_balance = Decimal(str(week["starting_balance"]))
        conf = week.get("confidence_breakdown", {})
        high_conf_in = Decimal(str(conf.get("cash_in", {}).get("high", "0")))
        medium_conf_in = Decimal(str(conf.get("cash_in", {}).get("medium", "0")))
        total_cash_out = Decimal(str(week["cash_out"]))

        # Layer 2: Reclassify HIGH inflows from clients with overdue invoices
        downgraded_clients: List[Dict[str, Any]] = []
        downgrade_amount = Decimal("0")

        if overdue_client_ids:
            for event in week.get("events", []):
                if event.get("direction") != "in" or event.get("confidence") != "high":
                    continue

                # Match event to overdue client via source_id (direct client events)
                # or via obligation_to_client mapping (obligation-sourced events)
                matched_client_id = None
                source_id = event.get("source_id", "")
                if source_id in overdue_client_ids:
                    matched_client_id = source_id
                elif source_id in obligation_to_client:
                    matched_client_id = obligation_to_client[source_id]

                if matched_client_id:
                    event_amount = Decimal(str(event["amount"]))
                    downgrade_amount += event_amount
                    client_info = overdue_details.get(matched_client_id, {})
                    overdue_amt = client_info.get("overdue_amount", Decimal("0"))
                    overdue_days = client_info.get("days_overdue", 0)
                    downgraded_clients.append({
                        "client_name": client_info.get("client_name", event.get("source_name", "Unknown")),
                        "amount": str(event_amount),
                        "reason": f"Has ${overdue_amt:,.0f} overdue by {overdue_days} days"
                    })

        adjusted_high = high_conf_in - downgrade_amount
        adjusted_medium = medium_conf_in + downgrade_amount

        conservative_balance = starting_balance + adjusted_high - total_cash_out
        definitely_covered = conservative_balance >= 0
        probably_covered = (conservative_balance + adjusted_medium) >= 0

        week_data: Dict[str, Any] = {
            "week_number": i,
            "week_start": week.get("week_start"),
            "starting_balance": str(starting_balance),
            "high_conf_inflows": str(adjusted_high),
            "medium_conf_inflows": str(adjusted_medium),
            "total_cash_out": str(total_cash_out),
            "conservative_balance": str(conservative_balance),
            "definitely_covered": definitely_covered,
            "probably_covered": probably_covered,
            "surplus_or_shortfall": str(conservative_balance),
        }

        if downgraded_clients:
            week_data["downgraded_clients"] = downgraded_clients

        coverage_by_week.append(week_data)

        # Update overall status (only escalate, never de-escalate)
        if not definitely_covered:
            if not probably_covered:
                overall_status = "shortfall"
                if first_risk_week is None:
                    first_risk_week = i
            elif overall_status == "safe":
                overall_status = "at_risk"
                if first_risk_week is None:
                    first_risk_week = i

    return {
        "has_payroll": True,
        "payroll_summary": {
            "frequency": frequency,
            "per_period_amount": str(per_period.quantize(Decimal("0.01"))),
            "employee_count": total_employee_count,
            "monthly_total": str(total_monthly_payroll)
        },
        "coverage_by_week": coverage_by_week,
        "overall_status": overall_status,
        "first_risk_week": first_risk_week,
    }


async def _check_payroll_safety(
    db: AsyncSession,
    user_id: str,
    args: Dict[str, Any]
) -> Dict[str, Any]:
    """Check whether upcoming payroll can be covered by confirmed cash."""
    weeks_ahead = min(args.get("weeks_ahead", 4), 13)

    coverage = await _compute_payroll_coverage(db, user_id, weeks_ahead)

    if not coverage.get("has_payroll"):
        return {"success": True, **coverage}

    # Build human-readable message
    status = coverage["overall_status"]
    payroll = coverage["payroll_summary"]
    freq_display = payroll["frequency"].replace("_", " ")
    amount_display = f"${Decimal(payroll['per_period_amount']):,.0f}"

    if status == "safe":
        message = (
            f"Payroll is safely covered for the next {weeks_ahead} weeks. "
            f"{freq_display.title()} payroll of {amount_display} can be met "
            f"from confirmed cash and high-confidence inflows."
        )
    elif status == "at_risk":
        risk_week = coverage["first_risk_week"]
        message = (
            f"Payroll coverage is at risk starting week {risk_week}. "
            f"High-confidence inflows alone don't cover all outflows, "
            f"but medium-confidence inflows close the gap."
        )
    else:
        risk_week = coverage["first_risk_week"]
        message = (
            f"Payroll shortfall detected in week {risk_week}. "
            f"Even including medium-confidence inflows, cash may not "
            f"cover all outflows including {freq_display} payroll of {amount_display}."
        )

    return {
        "success": True,
        **coverage,
        "message": message
    }


def _extract_billing_amount(billing_config: Optional[Dict[str, Any]]) -> float:
    """Extract a monthly revenue estimate from billing_config JSONB."""
    if not billing_config:
        return 0.0
    # Retainer: direct monthly amount
    if "amount" in billing_config:
        return float(billing_config["amount"])
    # Usage-based: typical monthly amount
    if "typical_amount" in billing_config:
        return float(billing_config["typical_amount"])
    # Project: total value / duration estimate
    if "total_value" in billing_config:
        months = float(billing_config.get("duration_months", 6))
        return float(billing_config["total_value"]) / max(months, 1)
    return 0.0


async def _analyze_concentration_risk(
    db: AsyncSession,
    user_id: str,
    args: Dict[str, Any]
) -> Dict[str, Any]:
    """Analyze client revenue concentration using normalized HHI."""
    include_runway_impact = args.get("include_runway_impact", True)

    # 1. Load all active clients
    result = await db.execute(
        select(Client).where(
            Client.user_id == user_id,
            Client.status == "active"
        )
    )
    clients = result.scalars().all()

    # Capture ORM attributes into plain dicts before any heavy DB work
    client_data = [
        {
            "id": c.id,
            "name": c.name,
            "revenue_percent": float(c.revenue_percent) if c.revenue_percent else 0.0,
            "relationship_type": c.relationship_type or "managed",
            "billing_config": c.billing_config,
        }
        for c in clients
    ]

    n = len(client_data)

    # Edge case: no clients
    if n == 0:
        return {
            "success": True,
            "risk_level": "unknown",
            "portfolio_size": 0,
            "message": "No active clients found.",
        }

    # Edge case: single client
    if n == 1:
        c = client_data[0]
        return {
            "success": True,
            "raw_hhi": 10000,
            "normalized_hhi": 1.0,
            "risk_level": "high",
            "portfolio_size": 1,
            "thresholds": {"moderate": 0.15, "high": 0.35},
            "top_client_share_pct": 100.0,
            "top_3_share_pct": 100.0,
            "top_clients": [{
                "client_id": c["id"],
                "name": c["name"],
                "revenue_share_pct": 100.0,
                "relationship_type": c["relationship_type"],
                "hhi_contribution": 10000.0,
            }],
            "message": (
                f"Single-client portfolio — total dependency on {c['name']}. "
                f"Concentration risk is HIGH."
            ),
        }

    # 2. Normalize revenue percents to sum to 100
    # If any client has revenue_percent=0, fall back to billing_config amounts
    total_raw = sum(c["revenue_percent"] for c in client_data)

    if total_raw <= 0:
        # Fall back to billing_config amounts
        for c in client_data:
            c["revenue_percent"] = _extract_billing_amount(c["billing_config"])
        total_raw = sum(c["revenue_percent"] for c in client_data)

    if total_raw <= 0:
        return {
            "success": True,
            "risk_level": "unknown",
            "portfolio_size": n,
            "message": "Could not determine revenue distribution — no revenue_percent or billing_config data.",
        }

    # Normalize so shares sum to exactly 100
    for c in client_data:
        c["normalized_share"] = (c["revenue_percent"] / total_raw) * 100.0

    # 3. Compute raw HHI (scale 0–10000)
    raw_hhi = sum(c["normalized_share"] ** 2 for c in client_data)

    # 4. Compute normalized HHI* (0–1)
    min_hhi = 10000.0 / n
    hhi_star = (raw_hhi - min_hhi) / (10000.0 - min_hhi)

    # 5. Classify risk level
    if hhi_star < 0.15:
        risk_level = "low"
    elif hhi_star < 0.35:
        risk_level = "moderate"
    else:
        risk_level = "high"

    # 6. Portfolio size floor: small portfolios are inherently concentrated
    size_note = ""
    if n <= 3 and risk_level == "low":
        risk_level = "moderate"
        size_note = f" Small portfolio ({n} clients) — inherently concentrated regardless of revenue split."

    # 7. Top clients by revenue share
    sorted_clients = sorted(client_data, key=lambda c: c["normalized_share"], reverse=True)
    top_3 = sorted_clients[:3]
    top_client_share = top_3[0]["normalized_share"]
    top_3_share = sum(c["normalized_share"] for c in top_3)

    # 8. Build top_clients list with HHI contribution
    top_clients_result = []
    for c in top_3:
        entry: Dict[str, Any] = {
            "client_id": c["id"],
            "name": c["name"],
            "revenue_share_pct": round(c["normalized_share"], 1),
            "relationship_type": c["relationship_type"],
            "hhi_contribution": round(c["normalized_share"] ** 2, 1),
        }
        top_clients_result.append(entry)

    # 9. Runway impact (optional, default True)
    if include_runway_impact:
        base_forecast = await calculate_13_week_forecast(db, user_id)
        base_runway = base_forecast.get("summary", {}).get("runway_weeks", 13)

        for entry in top_clients_result:
            excluded_forecast = await calculate_13_week_forecast(
                db, user_id,
                scenario_context=ScenarioContext(excluded_client_ids=[entry["client_id"]])
            )
            excluded_runway = excluded_forecast.get("summary", {}).get("runway_weeks", 13)
            weeks_lost = base_runway - excluded_runway

            impact: Dict[str, Any] = {
                "base_runway_weeks": base_runway,
                "without_client_weeks": excluded_runway,
                "weeks_lost": weeks_lost,
            }

            # Caveat: if weeks_lost is 0 for a high-revenue client, the forecast
            # may not have obligation data for this client
            if weeks_lost == 0 and entry["revenue_share_pct"] > 10.0:
                impact["note"] = "No obligation data — runway impact may be understated"

            entry["runway_impact"] = impact

    # 10. Build message
    risk_display = risk_level.upper()
    message = (
        f"Concentration risk is {risk_display} (HHI*: {hhi_star:.2f}). "
        f"Top 3 clients = {top_3_share:.1f}% of revenue."
    )

    # Add runway impact to message if available
    if include_runway_impact and top_clients_result:
        top = top_clients_result[0]
        impact = top.get("runway_impact", {})
        weeks_lost = impact.get("weeks_lost", 0)
        if weeks_lost > 0:
            message += f" Losing {top['name']} would reduce runway by {weeks_lost} weeks."
        elif top["revenue_share_pct"] > 10.0:
            message += f" Losing {top['name']} ({top['revenue_share_pct']:.0f}% of revenue) — runway impact not modeled in obligations."

    if size_note:
        message += size_note

    return {
        "success": True,
        "raw_hhi": round(raw_hhi, 1),
        "normalized_hhi": round(hhi_star, 3),
        "risk_level": risk_level,
        "portfolio_size": n,
        "thresholds": {"moderate": 0.15, "high": 0.35},
        "top_client_share_pct": round(top_client_share, 1),
        "top_3_share_pct": round(top_3_share, 1),
        "top_clients": top_clients_result,
        "message": message,
    }


# ============================================================================
# SHARED HELPER — Overdue invoices
# ============================================================================

async def _query_overdue_invoices(db: AsyncSession, user_id: str) -> List[Dict[str, Any]]:
    """
    Overdue invoices aggregated by client. Returns plain dicts (JSON-safe).

    Shared between generate_briefing (priority scoring) and draft_collection_message (future).
    Per-client aggregation: sums amounts, takes max days_overdue.
    """
    result = await db.execute(
        select(
            ObligationSchedule.estimated_amount,
            ObligationSchedule.due_date,
            ObligationAgreement.client_id,
            Client.name,
            Client.relationship_type,
        )
        .join(ObligationAgreement)
        .join(Client, Client.id == ObligationAgreement.client_id)
        .where(
            ObligationAgreement.user_id == user_id,
            ObligationAgreement.client_id.isnot(None),
            ObligationSchedule.status == "overdue"
        )
    )
    rows = result.all()

    today = date.today()
    by_client: Dict[str, Dict[str, Any]] = {}
    for amount, due_date, client_id, client_name, relationship_type in rows:
        if client_id not in by_client:
            by_client[client_id] = {
                "client_id": client_id,
                "client_name": client_name,
                "relationship_type": relationship_type or "managed",
                "total_overdue_amount": 0.0,
                "days_overdue": 0,
                "invoice_count": 0,
            }
        by_client[client_id]["total_overdue_amount"] += float(amount or 0)
        days = (today - due_date).days
        by_client[client_id]["days_overdue"] = max(by_client[client_id]["days_overdue"], days)
        by_client[client_id]["invoice_count"] += 1

    return list(by_client.values())


# ============================================================================
# BRIEFING — Scoring and item builders
# ============================================================================

# Scoring constants
_PAYROLL_RISK_SCORE = 10000
_OVERDUE_BASE = 200
_OVERDUE_DAYS_FACTOR = 10       # points per day overdue, capped at 200
_OVERDUE_AMOUNT_DIVISOR = 1000  # $52.5K → 52.5 points, capped at 200
_OVERDUE_CAP = 999
_RELATIONSHIP_MOD = {"transactional": 1.2, "managed": 1.0, "strategic": 0.8}
_RULE_BREACH_BASE = {"red": 350, "amber": 150}
_RULE_URGENCY_BONUS = 100       # when action_window <= 2 weeks
_CONCENTRATION_SCORE = {"high": 80, "moderate": 40}
_BRIEFING_MAX_ITEMS = 3


def _score_overdue_invoice(inv: Dict[str, Any]) -> float:
    """Score an overdue invoice for briefing priority. Days dominate, amount matters, relationship adjusts."""
    base = _OVERDUE_BASE
    days_bonus = min(inv["days_overdue"] * _OVERDUE_DAYS_FACTOR, 200)
    amount_bonus = min(inv["total_overdue_amount"] / _OVERDUE_AMOUNT_DIVISOR, 200)
    rel_mod = _RELATIONSHIP_MOD.get(inv.get("relationship_type", "managed"), 1.0)
    return min((base + days_bonus + amount_bonus) * rel_mod, _OVERDUE_CAP)


def _build_payroll_item(payroll: Dict[str, Any]) -> Dict[str, Any]:
    """Build a briefing item for payroll risk."""
    status = payroll["overall_status"]
    risk_week = payroll.get("first_risk_week")
    ps = payroll.get("payroll_summary", {})
    amount = ps.get("per_period_amount", "0")
    freq = ps.get("frequency", "monthly").replace("_", " ")

    if status == "shortfall":
        headline = f"Payroll shortfall in week {risk_week}"
        detail = f"Even medium-confidence inflows may not cover {freq} payroll of ${Decimal(amount):,.0f}."
        severity = "red"
    else:
        headline = f"Payroll coverage at risk in week {risk_week}"
        detail = f"High-confidence inflows alone don't cover {freq} payroll of ${Decimal(amount):,.0f}."
        severity = "amber"

    return {
        "priority_score": _PAYROLL_RISK_SCORE,
        "category": "payroll_risk",
        "headline": headline,
        "detail": detail,
        "severity": severity,
        "next_action": {
            "label": "Review payroll coverage details",
            "tool_name": "check_payroll_safety",
            "tool_args": {"weeks_ahead": 4},
        },
    }


def _build_overdue_item(inv: Dict[str, Any]) -> Dict[str, Any]:
    """Build a briefing item for an overdue invoice."""
    score = _score_overdue_invoice(inv)
    amount = inv["total_overdue_amount"]
    days = inv["days_overdue"]
    name = inv["client_name"]
    count = inv.get("invoice_count", 1)

    headline = f"{name} is {days} days late on ${amount:,.0f}"
    if count > 1:
        detail = f"{count} overdue invoices totaling ${amount:,.0f}. Relationship: {inv['relationship_type']}."
    else:
        detail = f"Single invoice, {inv['relationship_type']} client."

    return {
        "priority_score": score,
        "category": "overdue_invoice",
        "headline": headline,
        "detail": detail,
        "severity": "red" if days >= 14 else "amber",
        "next_action": {
            "label": f"Draft a follow-up for {name}",
            "tool_name": "draft_collection_message",
            "tool_args": {
                "client_name": name,
                "overdue_amount": amount,
                "days_overdue": days,
            },
        },
    }


def _build_rule_breach_item(evaluation: Dict[str, Any]) -> Dict[str, Any]:
    """Build a briefing item for a rule breach."""
    severity = evaluation.get("severity", "amber")
    base = _RULE_BREACH_BASE.get(severity, 150)
    action_window = evaluation.get("action_window_weeks")
    urgency = _RULE_URGENCY_BONUS if action_window is not None and action_window <= 2 else 0
    score = min(base + urgency, _OVERDUE_CAP)

    breach_week = evaluation.get("breach_week")
    name = evaluation.get("name", "Cash buffer rule")

    headline = f"{name} breaches in week {breach_week}" if breach_week else f"{name} breached"
    if action_window is not None:
        detail = f"{action_window} weeks to take action. Severity: {severity}."
    else:
        detail = f"Severity: {severity}."

    return {
        "priority_score": score,
        "category": "rule_breach",
        "headline": headline,
        "detail": detail,
        "severity": severity,
        "next_action": {
            "label": "Model scenarios to restore buffer",
            "tool_name": "plan_build_goal_scenarios",
            "tool_args": {"goal": "restore cash buffer"},
        },
    }


def _build_concentration_item(concentration: Dict[str, Any]) -> Dict[str, Any]:
    """Build a briefing item for concentration risk."""
    risk_level = concentration.get("risk_level", "moderate")
    score = _CONCENTRATION_SCORE.get(risk_level, 40)
    top_share = concentration.get("top_client_share_pct", 0)
    top_clients = concentration.get("top_clients", [])
    top_name = top_clients[0]["name"] if top_clients else "Top client"

    headline = f"Top client ({top_name}) represents {top_share:.0f}% of revenue"
    detail = f"Concentration risk is {risk_level}. HHI*: {concentration.get('normalized_hhi', 0):.2f}."

    return {
        "priority_score": score,
        "category": "concentration_risk",
        "headline": headline,
        "detail": detail,
        "severity": "amber" if risk_level == "moderate" else "red",
        "next_action": {
            "label": "Run full concentration analysis",
            "tool_name": "analyze_concentration_risk",
            "tool_args": {},
        },
    }


def _build_runway_item(runway_weeks: int) -> Dict[str, Any]:
    """Build a briefing item for runway warning. Two tiers: existential (<= 4w) and concerning (5-7w)."""
    if runway_weeks <= 4:
        # Existential: always above overdue invoices, below payroll
        score = 800 + (4 - runway_weeks) * 200
        severity = "red"
        detail = f"Cash may run out in {runway_weeks} weeks."
    else:
        # Concerning: can be outranked by overdue invoices
        score = 60 + (8 - runway_weeks) * 30
        severity = "amber"
        detail = "Cash runway is below the 8-week safety threshold."

    return {
        "priority_score": score,
        "category": "runway_warning",
        "headline": f"Runway is {runway_weeks} weeks",
        "detail": detail,
        "severity": severity,
        "next_action": {
            "label": "Explore runway extension scenarios",
            "tool_name": "plan_build_goal_scenarios",
            "tool_args": {"goal": "extend runway"},
        },
    }


# ============================================================================
# BRIEFING — Main handler
# ============================================================================

async def _generate_briefing(
    db: AsyncSession,
    user_id: str,
    args: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate a prioritized briefing of the top 3 treasury items.

    Scoring tiers:
    - 10000: Payroll at-risk (always #1 when present)
    - 800-1600: Runway <= 4 weeks (existential)
    - 200-999: Overdue invoices, rule breaches
    - 60-150: Runway 5-7 weeks
    - 40-80: Concentration risk

    Each category is evaluated independently — partial failures return
    partial results rather than failing the entire briefing.
    """
    # Forecast is the foundation — if this fails, nothing works
    try:
        forecast = await calculate_13_week_forecast(db, user_id)
    except Exception as e:
        return {"success": False, "error": f"Could not compute forecast: {str(e)}"}

    candidates: List[Dict[str, Any]] = []
    errors: List[str] = []

    # --- Payroll ---
    payroll_status = "safe"
    try:
        payroll = await _compute_payroll_coverage(db, user_id, forecast=forecast)
        if payroll.get("has_payroll"):
            payroll_status = payroll.get("overall_status", "safe")
            if payroll_status != "safe":
                candidates.append(_build_payroll_item(payroll))
    except Exception as e:
        errors.append(f"payroll: {str(e)}")
        payroll_status = "unknown"

    # --- Overdue invoices ---
    total_overdue = 0.0
    overdue_count = 0
    try:
        overdue = await _query_overdue_invoices(db, user_id)
        for inv in overdue:
            candidates.append(_build_overdue_item(inv))
            total_overdue += inv["total_overdue_amount"]
            overdue_count += inv["invoice_count"]
    except Exception as e:
        errors.append(f"overdue: {str(e)}")

    # --- Rule breaches ---
    try:
        rule_evals = await evaluate_rules(db, user_id, forecast)
        for ev in rule_evals:
            if ev.is_breached:
                candidates.append(_build_rule_breach_item({
                    "severity": ev.severity,
                    "breach_week": ev.breach_week,
                    "action_window_weeks": ev.action_window_weeks,
                    "name": ev.name,
                }))
    except Exception as e:
        errors.append(f"rules: {str(e)}")

    # --- Concentration risk ---
    concentration_risk = "unknown"
    try:
        concentration = await _analyze_concentration_risk(
            db, user_id, {"include_runway_impact": False}
        )
        concentration_risk = concentration.get("risk_level", "unknown")
        if concentration_risk in ("moderate", "high"):
            candidates.append(_build_concentration_item(concentration))
    except Exception as e:
        errors.append(f"concentration: {str(e)}")

    # --- Runway warning ---
    runway_weeks = forecast.get("summary", {}).get("runway_weeks", 13)
    if runway_weeks < 8:
        candidates.append(_build_runway_item(runway_weeks))

    # Sort by priority and hard-cap at 3
    candidates.sort(key=lambda x: x["priority_score"], reverse=True)
    items = candidates[:_BRIEFING_MAX_ITEMS]

    for i, item in enumerate(items):
        item["priority_rank"] = i + 1

    # Summary snapshot
    starting_cash = forecast.get("starting_cash", "0")
    summary = {
        "as_of_date": str(date.today()),
        "starting_cash": float(Decimal(str(starting_cash))),
        "runway_weeks": runway_weeks,
        "total_overdue": total_overdue,
        "overdue_count": overdue_count,
        "payroll_status": payroll_status,
        "concentration_risk": concentration_risk,
    }

    # Human-readable message
    if not items:
        message = (
            "No urgent items. Payroll is covered, no overdue invoices, "
            "and cash buffer rules are holding."
        )
    else:
        parts = [
            f"{len(items)} item{'s' if len(items) > 1 else ''} "
            f"need{'s' if len(items) == 1 else ''} attention."
        ]
        for item in items:
            parts.append(item["headline"] + ".")
        message = " ".join(parts)

    if errors:
        message += (
            f" (Partial results — could not evaluate: "
            f"{', '.join(e.split(':')[0] for e in errors)})"
        )

    return {
        "success": True,
        "items": items,
        "summary": summary,
        "message": message,
    }
