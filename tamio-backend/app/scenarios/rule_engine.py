"""Rule Evaluation Engine - Evaluates financial safety rules."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, List, Optional
from datetime import date, timedelta
from decimal import Decimal

from app.scenarios import models
from app.data.models import ExpenseBucket


async def evaluate_rules(
    db: AsyncSession,
    user_id: str,
    forecast: Dict[str, Any],
    scenario_id: Optional[str] = None
) -> List[models.RuleEvaluation]:
    """
    Evaluate all active financial rules against a forecast.

    Args:
        db: Database session
        user_id: User ID
        forecast: Forecast data (base or scenario)
        scenario_id: Optional scenario ID (None = base forecast)

    Returns:
        List of RuleEvaluation objects
    """
    # Get active rules for user
    result = await db.execute(
        select(models.FinancialRule).where(
            models.FinancialRule.user_id == user_id,
            models.FinancialRule.is_active == True
        )
    )
    rules = result.scalars().all()

    evaluations = []

    for rule in rules:
        if rule.rule_type == models.RuleType.MINIMUM_CASH_BUFFER:
            evaluation = await _evaluate_minimum_cash_buffer(
                db, user_id, rule, forecast, scenario_id
            )
            evaluations.append(evaluation)

    return evaluations


async def _evaluate_minimum_cash_buffer(
    db: AsyncSession,
    user_id: str,
    rule: models.FinancialRule,
    forecast: Dict[str, Any],
    scenario_id: Optional[str]
) -> models.RuleEvaluation:
    """
    Evaluate minimum cash buffer rule.

    Rule: Maintain >= X months of operating expenses in cash.
    """
    threshold_config = rule.threshold_config
    required_months = threshold_config.get("months", 3)

    # Calculate monthly operating expenses (OpEx)
    monthly_opex = await _calculate_monthly_opex(db, user_id)

    # Required buffer = months * monthly OpEx
    required_buffer = monthly_opex * Decimal(str(required_months))

    # Check each week in forecast
    weeks = forecast.get("weeks", [])
    breaches = []
    first_breach_week = None
    first_breach_date = None
    breach_amount = None

    for week in weeks:
        ending_balance = Decimal(str(week["ending_balance"]))

        if ending_balance < required_buffer:
            breaches.append({
                "week_number": week["week_number"],
                "date": week["week_end"],
                "ending_balance": str(ending_balance),
                "required_buffer": str(required_buffer),
                "shortfall": str(required_buffer - ending_balance)
            })

            if first_breach_week is None:
                first_breach_week = week["week_number"]
                first_breach_date = week["week_end"]
                breach_amount = required_buffer - ending_balance

    # Determine severity
    is_breached = len(breaches) > 0
    severity = "green"

    if is_breached:
        # Check current week
        if weeks and first_breach_week == 1:
            severity = "red"  # Already breached
        elif first_breach_week and first_breach_week <= 4:
            severity = "red"  # Breach within 4 weeks
        elif first_breach_week and first_breach_week <= 8:
            severity = "amber"  # Breach within 8 weeks
        else:
            severity = "amber"  # Future breach
    else:
        # Check if approaching threshold (within 20%)
        min_balance = min([Decimal(str(w["ending_balance"])) for w in weeks] or [Decimal("0")])
        threshold_80pct = required_buffer * Decimal("0.8")

        if min_balance < threshold_80pct:
            severity = "amber"

    # Calculate action window
    action_window_weeks = None
    if first_breach_week:
        action_window_weeks = max(0, first_breach_week - 1)

    # Build evaluation details
    evaluation_details = {
        "required_buffer": str(required_buffer),
        "required_months": required_months,
        "monthly_opex": str(monthly_opex),
        "breaches": breaches,
        "total_breach_weeks": len(breaches),
    }

    evaluation = models.RuleEvaluation(
        rule_id=rule.id,
        scenario_id=scenario_id,
        user_id=user_id,
        severity=severity,
        is_breached=is_breached,
        first_breach_week=first_breach_week,
        first_breach_date=first_breach_date,
        breach_amount=breach_amount,
        action_window_weeks=action_window_weeks,
        evaluation_details=evaluation_details
    )

    return evaluation


async def _calculate_monthly_opex(
    db: AsyncSession,
    user_id: str
) -> Decimal:
    """Calculate average monthly operating expenses."""
    # Sum all expense buckets
    result = await db.execute(
        select(ExpenseBucket).where(ExpenseBucket.user_id == user_id)
    )
    buckets = result.scalars().all()

    total_opex = sum(bucket.monthly_amount for bucket in buckets)

    return total_opex if total_opex > 0 else Decimal("0")


def generate_decision_signals(
    evaluations: List[models.RuleEvaluation],
    forecast: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Generate human-readable decision signals from rule evaluations.

    Args:
        evaluations: List of rule evaluations
        forecast: Forecast data

    Returns:
        List of decision signal dicts
    """
    signals = []

    for eval in evaluations:
        if eval.is_breached:
            signal = {
                "signal_type": "rule_breach",
                "severity": eval.severity.value,
                "title": f"Cash Buffer Warning",
                "message": _format_breach_message(eval),
                "earliest_risk_week": eval.first_breach_week,
                "action_window_weeks": eval.action_window_weeks,
                "recommended_actions": _generate_recommended_actions(eval)
            }
            signals.append(signal)

        elif eval.severity == "amber":
            signal = {
                "signal_type": "approaching_threshold",
                "severity": "amber",
                "title": "Approaching Cash Buffer Threshold",
                "message": "Your cash balance is trending toward minimum buffer threshold.",
                "earliest_risk_week": None,
                "action_window_weeks": None,
                "recommended_actions": [
                    "Monitor cash flow closely",
                    "Consider delaying discretionary expenses",
                    "Review upcoming receivables"
                ]
            }
            signals.append(signal)

    return signals


def _format_breach_message(eval: models.RuleEvaluation) -> str:
    """Format a human-readable breach message."""
    details = eval.evaluation_details
    required_buffer = details.get("required_buffer", "0")
    required_months = details.get("required_months", 0)

    if eval.action_window_weeks and eval.action_window_weeks > 0:
        return (
            f"Your cash balance will fall below the required {required_months}-month "
            f"buffer (${Decimal(required_buffer):,.2f}) in Week {eval.first_breach_week}. "
            f"You have {eval.action_window_weeks} weeks to take action."
        )
    else:
        return (
            f"Your cash balance is currently below the required {required_months}-month "
            f"buffer (${Decimal(required_buffer):,.2f}). Immediate action recommended."
        )


def _generate_recommended_actions(eval: models.RuleEvaluation) -> List[str]:
    """Generate recommended actions based on breach."""
    actions = []

    if eval.action_window_weeks and eval.action_window_weeks > 4:
        # Long-term actions
        actions.extend([
            "Review and accelerate receivables collection",
            "Consider delaying non-essential expenses",
            "Evaluate funding options if cash flow doesn't improve"
        ])
    elif eval.action_window_weeks and eval.action_window_weeks > 0:
        # Medium-term actions
        actions.extend([
            "Prioritize collection of outstanding invoices",
            "Defer discretionary spending",
            "Review credit line availability",
            "Consider short-term financing"
        ])
    else:
        # Immediate actions
        actions.extend([
            "Immediately defer all non-essential expenses",
            "Accelerate all receivables collection",
            "Access available credit lines",
            "Consider emergency financing options"
        ])

    return actions


async def suggest_scenarios(
    db: AsyncSession,
    user_id: str,
    forecast: Dict[str, Any],
    evaluations: List[models.RuleEvaluation]
) -> List[Dict[str, Any]]:
    """
    Suggest relevant scenarios based on current forecast and risks.

    Returns:
        List of suggested scenario configs
    """
    suggestions = []

    # Analyze current state
    has_breach = any(e.is_breached for e in evaluations)
    runway_weeks = forecast.get("summary", {}).get("runway_weeks", 13)

    # Suggest defensive scenarios if at risk
    if has_breach or runway_weeks < 8:
        suggestions.append({
            "scenario_type": "decreased_expense",
            "reason": "Low runway - consider cost reduction",
            "suggested_params": {
                "reduction_pct": 10,
                "category": "discretionary"
            }
        })

        suggestions.append({
            "scenario_type": "payment_delay",
            "reason": "Model impact of delayed client payments",
            "suggested_params": {
                "delay_weeks": 2
            }
        })

    # Suggest growth scenarios if healthy
    if not has_breach and runway_weeks > 10:
        suggestions.append({
            "scenario_type": "hiring",
            "reason": "Runway supports potential hiring",
            "suggested_params": {}
        })

        suggestions.append({
            "scenario_type": "client_gain",
            "reason": "Model impact of new client acquisition",
            "suggested_params": {}
        })

    # Always suggest client loss scenario (defensive planning)
    suggestions.append({
        "scenario_type": "client_loss",
        "reason": "Understand impact of losing key clients",
        "suggested_params": {}
    })

    return suggestions
