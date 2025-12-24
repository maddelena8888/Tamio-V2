"""TAMI Context Builder - Loads deterministic context from database.

This module builds the context payload that is injected into Agent2.
It loads data from the database and computes forecasts/rule evaluations.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from decimal import Decimal

from app.data.models import User, CashAccount, Client, ExpenseBucket, CashEvent
from app.scenarios.models import Scenario, FinancialRule, RuleEvaluation
from app.forecast.engine import calculate_13_week_forecast
from app.scenarios.engine import compute_scenario_forecast
from app.scenarios.rule_engine import evaluate_rules
from app.tami.schemas import (
    ContextPayload,
    ForecastWeekSummary,
    RuleStatus,
    ActiveScenarioSummary,
)


async def build_context(
    db: AsyncSession,
    user_id: str,
    active_scenario_id: Optional[str] = None
) -> ContextPayload:
    """
    Build the deterministic context payload for TAMI.

    Args:
        db: Database session
        user_id: User ID to load context for
        active_scenario_id: Optional currently active scenario

    Returns:
        ContextPayload with all deterministic data
    """
    # Load user data
    user = await _load_user(db, user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")

    # Load cash position
    cash_position = await _load_cash_position(db, user_id)

    # Calculate base forecast
    base_forecast = await calculate_13_week_forecast(db, user_id)

    # Load buffer rule
    buffer_rule = await _load_buffer_rule(db, user_id)

    # Evaluate rules on base forecast
    rule_evaluations = await evaluate_rules(db, user_id, base_forecast)

    # Load active scenarios
    active_scenarios = await _load_active_scenarios(db, user_id)

    # Load clients summary
    clients_summary = await _load_clients_summary(db, user_id)

    # Load expenses summary
    expenses_summary = await _load_expenses_summary(db, user_id)

    # Build forecast weeks summary
    forecast_weeks = [
        ForecastWeekSummary(
            week_number=w["week_number"],
            week_start=w["week_start"],
            ending_balance=w["ending_balance"],
            cash_in=w["cash_in"],
            cash_out=w["cash_out"],
            net_change=w["net_change"],
        )
        for w in base_forecast.get("weeks", [])
    ]

    # Build rule status list
    rule_statuses = [
        RuleStatus(
            rule_id=str(e.rule_id),
            rule_type=e.rule.rule_type if e.rule else "unknown",
            name=e.rule.name if e.rule else "Unknown Rule",
            is_breached=e.is_breached,
            severity=e.severity,
            breach_week=e.first_breach_week,
            action_window_weeks=e.action_window_weeks,
        )
        for e in rule_evaluations
    ]

    # Build context payload
    summary = base_forecast.get("summary", {})

    return ContextPayload(
        user_id=user_id,
        starting_cash=str(cash_position.get("balance", 0)),
        as_of_date=cash_position.get("as_of_date", date.today().isoformat()),
        base_forecast={
            "starting_cash": base_forecast.get("starting_cash", "0"),
            "total_cash_in": summary.get("total_cash_in", "0"),
            "total_cash_out": summary.get("total_cash_out", "0"),
        },
        forecast_weeks=forecast_weeks,
        buffer_rule=buffer_rule,
        rule_evaluations=rule_statuses,
        active_scenarios=active_scenarios,
        runway_weeks=summary.get("runway_weeks", 13),
        lowest_cash_week=summary.get("lowest_cash_week", 1),
        lowest_cash_amount=str(summary.get("lowest_cash_amount", 0)),
        clients_summary=clients_summary,
        expenses_summary=expenses_summary,
        generated_at=datetime.utcnow().isoformat(),
    )


async def _load_user(db: AsyncSession, user_id: str) -> Optional[User]:
    """Load user from database."""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def _load_cash_position(db: AsyncSession, user_id: str) -> Dict[str, Any]:
    """Load current cash position."""
    result = await db.execute(
        select(CashAccount).where(CashAccount.user_id == user_id)
    )
    accounts = result.scalars().all()

    total_balance = sum(Decimal(str(a.balance)) for a in accounts)
    as_of_date = max((a.as_of_date for a in accounts), default=date.today())

    return {
        "balance": str(total_balance),
        "as_of_date": as_of_date.isoformat() if as_of_date else date.today().isoformat(),
        "accounts_count": len(accounts),
    }


async def _load_buffer_rule(db: AsyncSession, user_id: str) -> Optional[Dict[str, Any]]:
    """Load the buffer rule configuration."""
    result = await db.execute(
        select(FinancialRule).where(
            FinancialRule.user_id == user_id,
            FinancialRule.rule_type == "minimum_cash_buffer",
            FinancialRule.is_active == True,
        )
    )
    rule = result.scalar_one_or_none()

    if not rule:
        return None

    return {
        "rule_id": rule.id,
        "name": rule.name,
        "months": rule.threshold_config.get("months", 3) if rule.threshold_config else 3,
        "threshold_config": rule.threshold_config,
    }


async def _load_active_scenarios(
    db: AsyncSession,
    user_id: str
) -> List[ActiveScenarioSummary]:
    """Load active (non-confirmed, non-discarded) scenarios."""
    result = await db.execute(
        select(Scenario).where(
            Scenario.user_id == user_id,
            Scenario.status.in_(["draft", "active"])
        ).order_by(Scenario.created_at.desc())
    )
    scenarios = result.scalars().all()

    summaries = []
    for scenario in scenarios:
        # Get impact if we can compute it
        impact = None
        try:
            comparison = await compute_scenario_forecast(
                db, user_id, scenario.id
            )
            base_week13 = Decimal(comparison["base_forecast"]["weeks"][-1]["ending_balance"])
            scenario_week13 = Decimal(comparison["scenario_forecast"]["weeks"][-1]["ending_balance"])
            impact = str(scenario_week13 - base_week13)
        except Exception:
            pass

        summaries.append(ActiveScenarioSummary(
            scenario_id=scenario.id,
            name=scenario.name,
            scenario_type=scenario.scenario_type,
            status=scenario.status,
            impact_week_13=impact,
            layers=scenario.linked_scenarios or [],
        ))

    return summaries


async def _load_clients_summary(db: AsyncSession, user_id: str) -> List[Dict[str, Any]]:
    """Load summary of clients."""
    result = await db.execute(
        select(Client).where(Client.user_id == user_id)
    )
    clients = result.scalars().all()

    return [
        {
            "client_id": c.id,
            "name": c.name,
            "type": c.client_type,
            "monthly_revenue": str(c.billing_config.get("monthly_amount", 0)) if c.billing_config else "0",
            "payment_behavior": c.payment_behavior,
            "churn_risk": c.churn_risk,
        }
        for c in clients
    ]


async def _load_expenses_summary(db: AsyncSession, user_id: str) -> List[Dict[str, Any]]:
    """Load summary of expense buckets."""
    result = await db.execute(
        select(ExpenseBucket).where(ExpenseBucket.user_id == user_id)
    )
    buckets = result.scalars().all()

    return [
        {
            "bucket_id": b.id,
            "name": b.name,
            "category": b.category,
            "type": b.bucket_type,
            "monthly_amount": str(b.monthly_amount) if b.monthly_amount else "0",
            "priority": b.priority,
        }
        for b in buckets
    ]


def context_to_json(context: ContextPayload) -> Dict[str, Any]:
    """Convert context payload to JSON-serializable dict."""
    return context.model_dump()


def format_context_for_prompt(context: ContextPayload) -> str:
    """Format context as a structured string for the prompt."""
    lines = []
    lines.append("=== CURRENT FINANCIAL STATE ===")
    lines.append(f"Starting Cash: ${context.starting_cash}")
    lines.append(f"As of Date: {context.as_of_date}")
    lines.append(f"Runway: {context.runway_weeks} weeks")
    lines.append(f"Lowest Cash: ${context.lowest_cash_amount} in week {context.lowest_cash_week}")
    lines.append("")

    # Buffer rule
    if context.buffer_rule:
        lines.append("=== BUFFER RULE ===")
        lines.append(f"Rule: {context.buffer_rule.get('name', 'Cash Buffer')}")
        lines.append(f"Minimum Months: {context.buffer_rule.get('months', 3)}")
        lines.append("")

    # Rule evaluations
    if context.rule_evaluations:
        lines.append("=== RULE STATUS ===")
        for rule in context.rule_evaluations:
            status = "BREACHED" if rule.is_breached else "OK"
            lines.append(f"- {rule.name}: {status} (severity: {rule.severity})")
            if rule.is_breached and rule.breach_week:
                lines.append(f"  First breach: week {rule.breach_week}")
                if rule.action_window_weeks:
                    lines.append(f"  Action window: {rule.action_window_weeks} weeks")
        lines.append("")

    # Forecast weeks
    lines.append("=== 13-WEEK FORECAST ===")
    for week in context.forecast_weeks:
        lines.append(
            f"Week {week.week_number}: "
            f"Balance=${week.ending_balance}, "
            f"In=${week.cash_in}, Out=${week.cash_out}"
        )
    lines.append("")

    # Active scenarios
    if context.active_scenarios:
        lines.append("=== ACTIVE SCENARIOS ===")
        for scenario in context.active_scenarios:
            impact = f"Impact: ${scenario.impact_week_13}" if scenario.impact_week_13 else "Impact: calculating..."
            lines.append(f"- {scenario.name} ({scenario.scenario_type}): {scenario.status}")
            lines.append(f"  {impact}")
            if scenario.layers:
                lines.append(f"  Layers: {len(scenario.layers)}")
        lines.append("")

    # Clients
    if context.clients_summary:
        lines.append("=== CLIENTS ===")
        for client in context.clients_summary:
            lines.append(
                f"- {client['name']}: ${client['monthly_revenue']}/month "
                f"({client['type']}, payment: {client['payment_behavior']})"
            )
        lines.append("")

    # Expenses
    if context.expenses_summary:
        lines.append("=== EXPENSES ===")
        for expense in context.expenses_summary:
            lines.append(
                f"- {expense['name']}: ${expense['monthly_amount']}/month "
                f"({expense['category']}, {expense['priority']})"
            )

    return "\n".join(lines)
