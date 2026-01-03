"""Rule Evaluation Engine - Evaluates financial safety rules."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, List, Optional
from datetime import date, timedelta
from decimal import Decimal

from app.scenarios import models
from app.data.models import ExpenseBucket, Client


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
        # Handle severity as either enum or string
        severity_value = eval.severity.value if hasattr(eval.severity, 'value') else eval.severity

        if eval.is_breached:
            signal = {
                "signal_type": "rule_breach",
                "severity": severity_value,
                "title": f"Cash Buffer Warning",
                "message": _format_breach_message(eval),
                "earliest_risk_week": eval.first_breach_week,
                "action_window_weeks": eval.action_window_weeks,
                "recommended_actions": _generate_recommended_actions(eval)
            }
            signals.append(signal)

        elif severity_value == "amber":
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
    Uses real client and expense data to generate actionable suggestions.

    Returns:
        List of suggested scenario configs with real entity names
    """
    suggestions = []

    # Analyze current state
    has_breach = any(e.is_breached for e in evaluations)
    runway_weeks = forecast.get("summary", {}).get("runway_weeks", 13)

    # Load real clients
    result = await db.execute(
        select(Client).where(
            Client.user_id == user_id,
            Client.status == "active"
        ).order_by(Client.created_at.desc())
    )
    clients = result.scalars().all()

    # Load real expense buckets
    result = await db.execute(
        select(ExpenseBucket).where(ExpenseBucket.user_id == user_id)
    )
    expenses = result.scalars().all()

    # Find clients with delayed payment behavior or high churn risk
    delayed_clients = [c for c in clients if c.payment_behavior == "delayed"]
    high_risk_clients = [c for c in clients if c.churn_risk == "high"]

    # Sort clients by monthly revenue (highest first) for "key client" scenarios
    def get_client_amount(c):
        if c.billing_config and c.billing_config.get("amount"):
            return Decimal(str(c.billing_config.get("amount", 0)))
        return Decimal("0")

    clients_by_revenue = sorted(clients, key=get_client_amount, reverse=True)

    # 1. Suggest payment delay scenario for clients with delayed payment behavior
    if delayed_clients:
        client = delayed_clients[0]
        suggestions.append({
            "scenario_type": "payment_delay_in",
            "name": f"{client.name} Delays Payment by 14 Days",
            "description": f"{client.name} has a history of delayed payments. Model the impact of a 2-week delay.",
            "priority": "high",
            "prefill_params": {
                "client_id": client.id,
                "delay_days": 14
            }
        })
    elif clients_by_revenue:
        # Suggest for largest client if no delayed clients
        client = clients_by_revenue[0]
        suggestions.append({
            "scenario_type": "payment_delay_in",
            "name": f"{client.name} Delays Payment by 10 Days",
            "description": f"Model what happens if your largest client delays payment.",
            "priority": "medium",
            "prefill_params": {
                "client_id": client.id,
                "delay_days": 10
            }
        })

    # 2. Suggest client loss for high churn risk or largest client
    if high_risk_clients:
        client = high_risk_clients[0]
        monthly = get_client_amount(client)
        suggestions.append({
            "scenario_type": "client_loss",
            "name": f"Loss of {client.name}",
            "description": f"{client.name} is marked as high churn risk (${monthly:,.0f}/month impact).",
            "priority": "high",
            "prefill_params": {
                "client_id": client.id
            }
        })
    elif clients_by_revenue:
        client = clients_by_revenue[0]
        monthly = get_client_amount(client)
        suggestions.append({
            "scenario_type": "client_loss",
            "name": f"Loss of {client.name}",
            "description": f"What happens if you lose your largest client (${monthly:,.0f}/month)?",
            "priority": "medium",
            "prefill_params": {
                "client_id": client.id
            }
        })

    # 3. Suggest expense changes based on actual expense buckets
    contractor_expenses = [e for e in expenses if e.category == "contractors" or "contractor" in e.name.lower()]
    discretionary_expenses = [e for e in expenses if e.priority in ["low", "medium"]]

    if contractor_expenses and (has_breach or runway_weeks < 8):
        expense = contractor_expenses[0]
        increase_amount = float(expense.monthly_amount) * 0.2 if expense.monthly_amount else 1000
        suggestions.append({
            "scenario_type": "increased_expense",
            "name": f"Increased {expense.name} Cost",
            "description": f"Model a 20% increase in {expense.name} expenses.",
            "priority": "medium",
            "prefill_params": {
                "expense_bucket_id": expense.id,
                "amount": increase_amount
            }
        })
    elif discretionary_expenses:
        expense = discretionary_expenses[0]
        reduction_amount = float(expense.monthly_amount) * 0.25 if expense.monthly_amount else 500
        suggestions.append({
            "scenario_type": "decreased_expense",
            "name": f"Reduce {expense.name}",
            "description": f"Model reducing {expense.name} by 25% to improve runway.",
            "priority": "low" if not has_breach else "high",
            "prefill_params": {
                "expense_bucket_id": expense.id,
                "amount": reduction_amount
            }
        })

    # 4. Suggest growth scenarios if healthy runway
    if not has_breach and runway_weeks > 10:
        suggestions.append({
            "scenario_type": "hiring",
            "name": "New Team Member",
            "description": "Model adding a new hire at $8,000/month.",
            "priority": "low",
            "prefill_params": {
                "amount": 8000
            }
        })

        suggestions.append({
            "scenario_type": "client_gain",
            "name": "New Client Win",
            "description": "Model winning a new client at $5,000/month.",
            "priority": "low",
            "prefill_params": {
                "amount": 5000
            }
        })

    # Ensure we always have at least 3 suggestions with fallbacks
    if len(suggestions) < 3:
        # Add generic suggestions if we don't have real data
        if not any(s["scenario_type"] == "payment_delay_in" for s in suggestions):
            if clients_by_revenue:
                client = clients_by_revenue[0]
                suggestions.append({
                    "scenario_type": "payment_delay_in",
                    "name": f"{client.name} Delays Payment",
                    "description": "Model the impact of delayed client payment.",
                    "priority": "medium",
                    "prefill_params": {
                        "client_id": client.id,
                        "delay_days": 14
                    }
                })
            else:
                suggestions.append({
                    "scenario_type": "payment_delay_in",
                    "name": "Client Delays Payment by 10 Days",
                    "description": "Model what happens if a client delays payment.",
                    "priority": "medium",
                    "prefill_params": {
                        "delay_days": 10
                    }
                })

        if not any(s["scenario_type"] == "client_loss" for s in suggestions):
            suggestions.append({
                "scenario_type": "client_loss",
                "name": "Loss of Client",
                "description": "Model the impact of losing a client.",
                "priority": "medium",
                "prefill_params": {}
            })

        if not any(s["scenario_type"] == "increased_expense" for s in suggestions):
            suggestions.append({
                "scenario_type": "increased_expense",
                "name": "Increased Contractor Payment",
                "description": "Model increased contractor or vendor costs.",
                "priority": "low",
                "prefill_params": {
                    "amount": 2000
                }
            })

    return suggestions[:3]  # Return top 3 suggestions
