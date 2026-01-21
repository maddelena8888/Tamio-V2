"""Rule Evaluation Engine - Evaluates financial safety rules."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, List, Optional
from datetime import date, timedelta
from decimal import Decimal

from app.scenarios import models
from app.data.models import ExpenseBucket, Client
from app.detection.models import DetectionAlert, DetectionType, AlertStatus, AlertSeverity


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
    Suggest relevant scenarios based on ACTIVE ALERTS and current forecast.

    Priority order:
    1. Scenarios derived directly from active/acknowledged detection alerts
    2. Scenarios based on forecast health and rule evaluations
    3. Fallback suggestions from client/expense data

    Each suggestion includes:
    - source_alert_id: Links to the originating alert (if applicable)
    - source_detection_type: The detection type that triggered this suggestion

    Returns:
        List of suggested scenario configs with alert linkage
    """
    suggestions = []

    # ========================================================================
    # PHASE 1: Generate scenarios from ACTIVE DETECTION ALERTS
    # These are the highest priority - they represent real, detected problems
    # ========================================================================
    result = await db.execute(
        select(DetectionAlert).where(
            DetectionAlert.user_id == user_id,
            DetectionAlert.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED])
        ).order_by(
            # Emergency alerts first, then by urgency score
            DetectionAlert.severity.asc(),  # EMERGENCY < THIS_WEEK < UPCOMING
            DetectionAlert.urgency_score.desc()
        )
    )
    active_alerts = result.scalars().all()

    # Load clients and expenses for context
    result = await db.execute(
        select(Client).where(
            Client.user_id == user_id,
            Client.status == "active"
        ).order_by(Client.created_at.desc())
    )
    clients = result.scalars().all()
    clients_by_id = {c.id: c for c in clients}

    result = await db.execute(
        select(ExpenseBucket).where(ExpenseBucket.user_id == user_id)
    )
    expenses = result.scalars().all()

    def get_client_amount(c):
        if c.billing_config and c.billing_config.get("amount"):
            return Decimal(str(c.billing_config.get("amount", 0)))
        return Decimal("0")

    clients_by_revenue = sorted(clients, key=get_client_amount, reverse=True)

    # Map detection types to scenario types
    for alert in active_alerts:
        suggestion = _alert_to_scenario_suggestion(alert, clients_by_id, expenses)
        if suggestion and not _suggestion_exists(suggestions, suggestion):
            suggestions.append(suggestion)

    # ========================================================================
    # PHASE 2: Add forecast-based suggestions if we don't have enough from alerts
    # ========================================================================
    has_breach = any(e.is_breached for e in evaluations)
    runway_weeks = forecast.get("summary", {}).get("runway_weeks", 13)

    # Find clients with risky attributes
    delayed_clients = [c for c in clients if c.payment_behavior == "delayed"]
    high_risk_clients = [c for c in clients if c.churn_risk == "high"]

    # Add payment delay scenarios for risky clients (if not already from alerts)
    if len(suggestions) < 3 and delayed_clients:
        client = delayed_clients[0]
        suggestion = {
            "scenario_type": "payment_delay_in",
            "name": f"{client.name} Delays Payment by 14 Days",
            "description": f"{client.name} has a history of delayed payments. Model the impact of a 2-week delay.",
            "priority": "high",
            "source_alert_id": None,
            "source_detection_type": None,
            "prefill_params": {
                "client_id": client.id,
                "delay_days": 14
            }
        }
        if not _suggestion_exists(suggestions, suggestion):
            suggestions.append(suggestion)

    # Add client loss for high churn risk clients
    if len(suggestions) < 3 and high_risk_clients:
        client = high_risk_clients[0]
        monthly = get_client_amount(client)
        suggestion = {
            "scenario_type": "client_loss",
            "name": f"Loss of {client.name}",
            "description": f"{client.name} is marked as high churn risk (${monthly:,.0f}/month impact).",
            "priority": "high",
            "source_alert_id": None,
            "source_detection_type": None,
            "prefill_params": {
                "client_id": client.id
            }
        }
        if not _suggestion_exists(suggestions, suggestion):
            suggestions.append(suggestion)

    # Add expense reduction if buffer is at risk
    contractor_expenses = [e for e in expenses if e.category == "contractors" or "contractor" in e.name.lower()]
    discretionary_expenses = [e for e in expenses if e.priority in ["low", "medium"]]

    if len(suggestions) < 3 and (has_breach or runway_weeks < 8) and discretionary_expenses:
        expense = discretionary_expenses[0]
        reduction_amount = float(expense.monthly_amount) * 0.25 if expense.monthly_amount else 500
        suggestion = {
            "scenario_type": "decreased_expense",
            "name": f"Reduce {expense.name}",
            "description": f"Model reducing {expense.name} by 25% to improve runway.",
            "priority": "high" if has_breach else "medium",
            "source_alert_id": None,
            "source_detection_type": None,
            "prefill_params": {
                "expense_bucket_id": expense.id,
                "amount": reduction_amount
            }
        }
        if not _suggestion_exists(suggestions, suggestion):
            suggestions.append(suggestion)

    # ========================================================================
    # PHASE 3: Fallback suggestions to ensure we always have at least 3
    # ========================================================================
    if len(suggestions) < 3 and clients_by_revenue:
        client = clients_by_revenue[0]
        monthly = get_client_amount(client)

        # Payment delay for largest client
        if not any(s["scenario_type"] == "payment_delay_in" for s in suggestions):
            suggestions.append({
                "scenario_type": "payment_delay_in",
                "name": f"{client.name} Delays Payment by 14 Days",
                "description": f"Model what happens if your largest client ({client.name}) delays payment.",
                "priority": "medium",
                "source_alert_id": None,
                "source_detection_type": None,
                "prefill_params": {
                    "client_id": client.id,
                    "delay_days": 14
                }
            })

        # Client loss for largest client
        if len(suggestions) < 3 and not any(s["scenario_type"] == "client_loss" for s in suggestions):
            suggestions.append({
                "scenario_type": "client_loss",
                "name": f"Loss of {client.name}",
                "description": f"What happens if you lose your largest client (${monthly:,.0f}/month)?",
                "priority": "medium",
                "source_alert_id": None,
                "source_detection_type": None,
                "prefill_params": {
                    "client_id": client.id
                }
            })

    # Expense increase as final fallback
    if len(suggestions) < 3:
        suggestions.append({
            "scenario_type": "increased_expense",
            "name": "Increased Operating Costs",
            "description": "Model a 10% increase in operating expenses.",
            "priority": "low",
            "source_alert_id": None,
            "source_detection_type": None,
            "prefill_params": {
                "amount": 2000
            }
        })

    return suggestions[:3]  # Return top 3 suggestions


def _alert_to_scenario_suggestion(
    alert: DetectionAlert,
    clients_by_id: Dict[str, Client],
    expenses: List[ExpenseBucket]
) -> Optional[Dict[str, Any]]:
    """
    Convert a detection alert into a scenario suggestion.

    Maps detection types to appropriate scenario types:
    - LATE_PAYMENT -> payment_delay_in
    - CLIENT_CHURN -> client_loss
    - UNEXPECTED_EXPENSE -> increased_expense
    - BUFFER_BREACH -> decreased_expense (defensive)
    - etc.
    """
    context = alert.context_data or {}
    priority = "high" if alert.severity == AlertSeverity.EMERGENCY else "medium"

    if alert.detection_type == DetectionType.LATE_PAYMENT:
        # Late payment alert -> suggest modeling extended delay
        client_id = context.get("client_id")
        client_name = context.get("client_name", "Client")
        days_overdue = context.get("days_overdue", 14)

        return {
            "scenario_type": "payment_delay_in",
            "name": f"{client_name} Delays Payment by {days_overdue} Days",
            "description": f"Active alert: {client_name} payment is {days_overdue} days overdue. Model extended delay impact.",
            "priority": priority,
            "source_alert_id": alert.id,
            "source_detection_type": alert.detection_type.value,
            "prefill_params": {
                "client_id": client_id,
                "delay_days": days_overdue
            }
        }

    elif alert.detection_type == DetectionType.CLIENT_CHURN:
        # Client churn risk -> suggest modeling client loss
        client_id = context.get("client_id")
        client_name = context.get("client_name", "Client")
        client = clients_by_id.get(client_id)
        monthly = Decimal("0")
        if client and client.billing_config:
            monthly = Decimal(str(client.billing_config.get("amount", 0)))

        return {
            "scenario_type": "client_loss",
            "name": f"Loss of {client_name}",
            "description": f"Active alert: {client_name} has high churn risk. Model losing this client (${monthly:,.0f}/month).",
            "priority": priority,
            "source_alert_id": alert.id,
            "source_detection_type": alert.detection_type.value,
            "prefill_params": {
                "client_id": client_id
            }
        }

    elif alert.detection_type == DetectionType.UNEXPECTED_EXPENSE:
        # Unexpected expense spike -> suggest modeling continued increase
        bucket_id = context.get("bucket_id")
        bucket_name = context.get("bucket_name", "Expense")
        variance_amount = context.get("variance_amount", 0)

        return {
            "scenario_type": "increased_expense",
            "name": f"Increased {bucket_name} Costs",
            "description": f"Active alert: {bucket_name} spiked unexpectedly. Model continued increase.",
            "priority": priority,
            "source_alert_id": alert.id,
            "source_detection_type": alert.detection_type.value,
            "prefill_params": {
                "expense_bucket_id": bucket_id,
                "amount": variance_amount
            }
        }

    elif alert.detection_type == DetectionType.BUFFER_BREACH:
        # Buffer breach -> suggest cost reduction scenario
        shortfall = context.get("shortfall", 0)

        # Find discretionary expense to suggest cutting
        discretionary = [e for e in expenses if e.priority in ["low", "medium"]]
        if discretionary:
            expense = discretionary[0]
            return {
                "scenario_type": "decreased_expense",
                "name": f"Reduce {expense.name} by 25%",
                "description": f"Active alert: Cash buffer breach detected. Model reducing {expense.name} to improve buffer.",
                "priority": "high",
                "source_alert_id": alert.id,
                "source_detection_type": alert.detection_type.value,
                "prefill_params": {
                    "expense_bucket_id": expense.id,
                    "amount": float(expense.monthly_amount or 0) * 0.25
                }
            }

    elif alert.detection_type == DetectionType.PAYROLL_SAFETY:
        # Payroll at risk -> suggest accelerating collections (payment delay in reverse)
        # This suggests what happens if a key client delays further
        shortfall = context.get("shortfall", 0)

        return {
            "scenario_type": "payment_delay_in",
            "name": "Key Client Payment Delay",
            "description": f"Active alert: Payroll safety at risk. Model impact if key payment is delayed.",
            "priority": "high",
            "source_alert_id": alert.id,
            "source_detection_type": alert.detection_type.value,
            "prefill_params": {
                "delay_days": 7
            }
        }

    elif alert.detection_type == DetectionType.RUNWAY_THRESHOLD:
        # Runway breach -> suggest expense reduction
        weeks_remaining = context.get("runway_weeks", 8)

        discretionary = [e for e in expenses if e.priority in ["low", "medium"]]
        if discretionary:
            expense = discretionary[0]
            return {
                "scenario_type": "decreased_expense",
                "name": f"Reduce {expense.name}",
                "description": f"Active alert: Runway is {weeks_remaining} weeks. Model cost reduction to extend runway.",
                "priority": "high",
                "source_alert_id": alert.id,
                "source_detection_type": alert.detection_type.value,
                "prefill_params": {
                    "expense_bucket_id": expense.id,
                    "amount": float(expense.monthly_amount or 0) * 0.3
                }
            }

    # For other alert types, return None (no direct scenario mapping)
    return None


def _suggestion_exists(suggestions: List[Dict], new_suggestion: Dict) -> bool:
    """Check if a similar suggestion already exists to avoid duplicates."""
    for s in suggestions:
        # Same scenario type + same client/expense = duplicate
        if s["scenario_type"] == new_suggestion["scenario_type"]:
            s_client = s.get("prefill_params", {}).get("client_id")
            n_client = new_suggestion.get("prefill_params", {}).get("client_id")
            s_expense = s.get("prefill_params", {}).get("expense_bucket_id")
            n_expense = new_suggestion.get("prefill_params", {}).get("expense_bucket_id")

            if s_client and n_client and s_client == n_client:
                return True
            if s_expense and n_expense and s_expense == n_expense:
                return True
            # If neither has specific entity, compare by type only for generic scenarios
            if not s_client and not n_client and not s_expense and not n_expense:
                return True

    return False
