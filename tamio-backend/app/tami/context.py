"""TAMI Context Builder - Loads deterministic context from database.

This module builds the context payload that is injected into Agent2.
It loads data from the database and computes forecasts/rule evaluations.
Includes user behavior signals for more relevant responses.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal

from app.data.models import User, CashAccount, Client, ExpenseBucket
from app.scenarios.models import Scenario, FinancialRule, RuleEvaluation
from app.forecast.engine_v2 import calculate_forecast_v2 as calculate_13_week_forecast
from app.scenarios.engine import compute_scenario_forecast
from app.scenarios.rule_engine import evaluate_rules
from app.tami.schemas import (
    ContextPayload,
    ForecastWeekSummary,
    RuleStatus,
    ActiveScenarioSummary,
    CurrentScenarioContext,
    TriggeredScenarioSummary,
    BehaviorInsightsSummary,
    BusinessProfileSummary,
    AlertSummary,
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

    # Load current scenario context if an active_scenario_id is provided
    current_scenario = None
    if active_scenario_id:
        current_scenario = await _load_current_scenario_context(
            db, user_id, active_scenario_id, base_forecast
        )

    # Load clients summary
    clients_summary = await _load_clients_summary(db, user_id)

    # Load expenses summary
    expenses_summary = await _load_expenses_summary(db, user_id)

    # Load behavior insights and triggered scenarios (Phase 4)
    behavior_insights, triggered_scenarios = await _load_behavior_context(db, user_id)

    # Load active detection alerts (V4)
    active_alerts = await _load_active_alerts(db, user_id)

    # Build business profile summary
    business_profile = None
    if user.industry or user.revenue_range:
        business_profile = BusinessProfileSummary(
            industry=user.industry,
            subcategory=user.subcategory,
            revenue_range=user.revenue_range,
            base_currency=user.base_currency,
        )

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
        business_profile=business_profile,
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
        current_scenario=current_scenario,
        runway_weeks=summary.get("runway_weeks", 13),
        lowest_cash_week=summary.get("lowest_cash_week", 1),
        lowest_cash_amount=str(summary.get("lowest_cash_amount", 0)),
        clients_summary=clients_summary,
        expenses_summary=expenses_summary,
        behavior_insights=behavior_insights,
        triggered_scenarios=triggered_scenarios,
        active_alerts=active_alerts,
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


async def _load_current_scenario_context(
    db: AsyncSession,
    user_id: str,
    scenario_id: str,
    base_forecast: Dict[str, Any]
) -> Optional[CurrentScenarioContext]:
    """Load detailed context for the currently active/viewed scenario."""
    # Load the scenario
    result = await db.execute(
        select(Scenario).where(Scenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        return None

    # Compute scenario forecast comparison
    try:
        comparison = await compute_scenario_forecast(db, user_id, scenario_id)
    except Exception:
        return None

    # Calculate impact
    base_weeks = base_forecast.get("weeks", [])
    scenario_weeks = comparison.get("scenario_forecast", {}).get("weeks", [])

    base_week13 = Decimal(base_weeks[-1]["ending_balance"]) if base_weeks else Decimal("0")
    scenario_week13 = Decimal(scenario_weeks[-1]["ending_balance"]) if scenario_weeks else Decimal("0")
    impact = str(scenario_week13 - base_week13)

    # Calculate weekly deltas
    weekly_deltas = []
    for i, base_week in enumerate(base_weeks):
        if i < len(scenario_weeks):
            scenario_week = scenario_weeks[i]
            base_bal = Decimal(str(base_week["ending_balance"]))
            scenario_bal = Decimal(str(scenario_week["ending_balance"]))
            weekly_deltas.append({
                "week_number": base_week["week_number"],
                "base_balance": str(base_bal),
                "scenario_balance": str(scenario_bal),
                "delta": str(scenario_bal - base_bal)
            })

    # Evaluate rules on scenario forecast
    from app.scenarios.rule_engine import evaluate_rules
    scenario_forecast = comparison.get("scenario_forecast", {})
    rule_evals = await evaluate_rules(db, user_id, scenario_forecast, scenario_id=scenario_id)

    is_buffer_safe = not any(e.is_breached for e in rule_evals)
    rule_breaches = [
        {
            "rule_name": e.rule.name if e.rule else "Cash Buffer",
            "severity": e.severity.value if hasattr(e.severity, 'value') else e.severity,
            "breach_week": e.first_breach_week,
            "breach_amount": str(e.breach_amount) if e.breach_amount else None
        }
        for e in rule_evals if e.is_breached
    ]

    return CurrentScenarioContext(
        scenario_id=scenario.id,
        name=scenario.name,
        scenario_type=scenario.scenario_type,
        status=scenario.status,
        parameters=scenario.parameters or {},
        scope_config=scenario.scope_config or {},
        impact_week_13=impact,
        scenario_ending_balance=str(scenario_week13),
        base_ending_balance=str(base_week13),
        is_buffer_safe=is_buffer_safe,
        rule_breaches=rule_breaches,
        weekly_deltas=weekly_deltas
    )


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


async def _load_active_alerts(db: AsyncSession, user_id: str) -> List[AlertSummary]:
    """Load active detection alerts for the user."""
    try:
        from app.detection.models import DetectionAlert, AlertStatus

        result = await db.execute(
            select(DetectionAlert).where(
                DetectionAlert.user_id == user_id,
                DetectionAlert.status.in_([
                    AlertStatus.ACTIVE,
                    AlertStatus.ACKNOWLEDGED,
                    AlertStatus.PREPARING
                ])
            ).order_by(DetectionAlert.deadline.asc().nullslast())
        )
        alerts = result.scalars().all()

        alert_summaries = []
        for alert in alerts:
            # Calculate days until deadline
            days_until = None
            if alert.deadline:
                delta = alert.deadline.date() - date.today()
                days_until = delta.days

            alert_summaries.append(AlertSummary(
                alert_id=alert.id,
                title=alert.title,
                description=alert.description,
                detection_type=alert.detection_type.value if hasattr(alert.detection_type, 'value') else str(alert.detection_type),
                severity=alert.severity.value if hasattr(alert.severity, 'value') else str(alert.severity),
                status=alert.status.value if hasattr(alert.status, 'value') else str(alert.status),
                cash_impact=alert.cash_impact,
                deadline=alert.deadline.isoformat() if alert.deadline else None,
                days_until_deadline=days_until,
                context_data=alert.context_data or {}
            ))

        return alert_summaries
    except Exception:
        # Detection module might not be fully set up yet
        return []


async def _load_behavior_context(
    db: AsyncSession,
    user_id: str
) -> tuple[Optional[BehaviorInsightsSummary], List[TriggeredScenarioSummary]]:
    """
    Load behavior insights and triggered scenarios for TAMI context.

    Returns:
        Tuple of (behavior_insights, triggered_scenarios)
    """
    try:
        from app.behavior.engine import calculate_all_behavior_metrics
        from app.behavior.triggers import evaluate_triggers, get_pending_triggered_scenarios

        # Calculate behavior metrics
        insights, metrics = await calculate_all_behavior_metrics(db, user_id, buffer_months=3)

        # Evaluate triggers
        triggered = await evaluate_triggers(db, user_id, metrics)

        # Get pending scenarios
        pending = await get_pending_triggered_scenarios(db, user_id)

        # Combine triggered and pending (deduplicate)
        all_triggered = list(triggered)
        triggered_ids = {t.id for t in triggered}
        for p in pending:
            if p.id not in triggered_ids:
                all_triggered.append(p)

        # Build behavior insights summary
        top_concerns = []

        # Check for client concentration risk
        client_concentration_risk = False
        if insights.client_behavior and insights.client_behavior.get("concentration"):
            conc = insights.client_behavior["concentration"]
            if conc.get("top_client_share", 0) > 40:
                client_concentration_risk = True
                top_concerns.append(f"High client concentration: top client is {conc.get('top_client_share', 0):.0f}% of revenue")

        # Check payment reliability
        payment_reliability_warning = False
        if insights.client_behavior and insights.client_behavior.get("payment_reliability"):
            for client in insights.client_behavior["payment_reliability"]:
                if client.get("trend") == "worsening":
                    payment_reliability_warning = True
                    top_concerns.append(f"Payment reliability declining for {client.get('client_name', 'a client')}")
                    break

        # Check expense volatility
        expense_volatility_warning = False
        if insights.expense_behavior and insights.expense_behavior.get("volatility"):
            for cat in insights.expense_behavior["volatility"]:
                if cat.get("variance", 0) > 0.3:  # >30% variance
                    expense_volatility_warning = True
                    top_concerns.append(f"High expense volatility in {cat.get('category', 'a category')}")
                    break

        # Check buffer integrity
        buffer_integrity_breached = False
        if insights.cash_discipline and insights.cash_discipline.get("buffer_integrity"):
            buffer = insights.cash_discipline["buffer_integrity"]
            if buffer.get("days_below_threshold", 0) > 7:
                buffer_integrity_breached = True
                top_concerns.append(f"Buffer below threshold for {buffer.get('days_below_threshold', 0)} days")

        # Calculate health score (simplified)
        health_score = 80
        if client_concentration_risk:
            health_score -= 15
        if payment_reliability_warning:
            health_score -= 10
        if expense_volatility_warning:
            health_score -= 10
        if buffer_integrity_breached:
            health_score -= 20

        health_score = max(0, min(100, health_score))

        if health_score >= 70:
            health_label = "Healthy"
        elif health_score >= 40:
            health_label = "At Risk"
        else:
            health_label = "Critical"

        behavior_summary = BehaviorInsightsSummary(
            health_score=health_score,
            health_label=health_label,
            client_concentration_risk=client_concentration_risk,
            payment_reliability_warning=payment_reliability_warning,
            expense_volatility_warning=expense_volatility_warning,
            buffer_integrity_breached=buffer_integrity_breached,
            top_concerns=top_concerns[:3],  # Limit to top 3 concerns
        )

        # Build triggered scenario summaries
        triggered_summaries = [
            TriggeredScenarioSummary(
                id=ts.id,
                trigger_name=ts.scenario_name,
                scenario_type=ts.scenario_type,
                severity=ts.severity,
                status=ts.status,
                estimated_impact=ts.estimated_impact,
                recommended_actions=ts.recommended_actions or [],
            )
            for ts in all_triggered
        ]

        return behavior_summary, triggered_summaries

    except Exception:
        # Behavior module might not be fully set up yet
        return None, []


def context_to_json(context: ContextPayload) -> Dict[str, Any]:
    """Convert context payload to JSON-serializable dict."""
    return context.model_dump()


def format_context_for_prompt(context: ContextPayload) -> str:
    """Format context as a structured string for the prompt."""
    lines = []

    # Business profile context
    if context.business_profile:
        bp = context.business_profile
        lines.append("=== BUSINESS PROFILE ===")
        industry_label = bp.industry.replace("_", " ").title() if bp.industry else "Unknown"
        lines.append(f"Industry: {industry_label}")
        if bp.subcategory:
            subcategory_label = bp.subcategory.replace("_", " ").title()
            lines.append(f"Subcategory: {subcategory_label}")
        if bp.revenue_range:
            lines.append(f"Revenue Range: ${bp.revenue_range}")
        lines.append(f"Operating Currency: {bp.base_currency}")
        lines.append("")
        lines.append("Use this context to provide industry-specific insights and comparisons.")
        lines.append("Reference typical payment terms for this industry when relevant.")
        lines.append("")

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

    # Current scenario being viewed (detailed context)
    if context.current_scenario:
        sc = context.current_scenario
        lines.append("=== CURRENTLY VIEWING SCENARIO ===")
        lines.append(f"Name: {sc.name}")
        lines.append(f"Type: {sc.scenario_type}")
        lines.append(f"Status: {sc.status}")
        if sc.parameters:
            lines.append(f"Parameters: {sc.parameters}")
        lines.append(f"Impact at Week 13: ${sc.impact_week_13}")
        lines.append(f"Base Ending Balance: ${sc.base_ending_balance}")
        lines.append(f"Scenario Ending Balance: ${sc.scenario_ending_balance}")
        lines.append(f"Buffer Safe: {'Yes' if sc.is_buffer_safe else 'NO - AT RISK'}")
        if sc.rule_breaches:
            lines.append("Rule Breaches:")
            for breach in sc.rule_breaches:
                lines.append(f"  - {breach['rule_name']}: {breach['severity']} severity, week {breach['breach_week']}")
        lines.append("")

    # Active scenarios (other drafts)
    if context.active_scenarios:
        other_scenarios = [s for s in context.active_scenarios
                         if not context.current_scenario or s.scenario_id != context.current_scenario.scenario_id]
        if other_scenarios:
            lines.append("=== OTHER ACTIVE SCENARIOS ===")
            for scenario in other_scenarios:
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
        lines.append("")

    # Behavior Insights (Phase 4)
    if context.behavior_insights:
        bi = context.behavior_insights
        lines.append("=== BEHAVIOR INSIGHTS ===")
        lines.append(f"Health Score: {bi.health_score}/100 ({bi.health_label})")
        if bi.client_concentration_risk:
            lines.append("⚠️ Client Concentration Risk: HIGH")
        if bi.payment_reliability_warning:
            lines.append("⚠️ Payment Reliability: DECLINING")
        if bi.expense_volatility_warning:
            lines.append("⚠️ Expense Volatility: HIGH")
        if bi.buffer_integrity_breached:
            lines.append("🚨 Buffer Integrity: BREACHED")
        if bi.top_concerns:
            lines.append("Top Concerns:")
            for concern in bi.top_concerns:
                lines.append(f"  - {concern}")
        lines.append("")

    # Triggered Scenarios (Phase 4)
    if context.triggered_scenarios:
        lines.append("=== TRIGGERED SCENARIOS ===")
        lines.append(f"({len(context.triggered_scenarios)} scenarios need attention)")
        for ts in context.triggered_scenarios:
            severity_icon = "🚨" if ts.severity == "critical" else "⚠️" if ts.severity == "high" else "ℹ️"
            lines.append(f"{severity_icon} {ts.trigger_name} ({ts.scenario_type})")
            lines.append(f"   Status: {ts.status}, Severity: {ts.severity}")
            if ts.recommended_actions:
                lines.append(f"   Actions: {', '.join(ts.recommended_actions[:2])}")
        lines.append("")

    # Active Detection Alerts (V4)
    if context.active_alerts:
        lines.append("=== ACTIVE ALERTS ===")
        lines.append(f"({len(context.active_alerts)} alerts requiring attention)")
        for alert in context.active_alerts:
            severity_icon = "🚨" if alert.severity == "emergency" else "⚠️" if alert.severity == "this_week" else "ℹ️"
            deadline_str = ""
            if alert.days_until_deadline is not None:
                if alert.days_until_deadline <= 0:
                    deadline_str = " - DUE TODAY/OVERDUE"
                elif alert.days_until_deadline == 1:
                    deadline_str = " - due tomorrow"
                else:
                    deadline_str = f" - due in {alert.days_until_deadline} days"
            lines.append(f"{severity_icon} {alert.title}{deadline_str}")
            if alert.cash_impact:
                lines.append(f"   Amount: ${alert.cash_impact:,.0f}")
            if alert.description:
                lines.append(f"   Details: {alert.description}")
            lines.append(f"   Type: {alert.detection_type}, Status: {alert.status}")
        lines.append("")

    return "\n".join(lines)


# ============================================================================
# USER BEHAVIOR LOADING
# ============================================================================

async def load_recent_activities(
    db: AsyncSession,
    user_id: str,
    hours: int = 24,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Load recent user activities for behavioral context.

    Args:
        db: Database session
        user_id: User ID
        hours: How many hours back to look
        limit: Maximum number of activities to return

    Returns:
        List of activity dictionaries
    """
    try:
        from app.tami.models import UserActivity

        cutoff = datetime.utcnow() - timedelta(hours=hours)

        result = await db.execute(
            select(UserActivity)
            .where(
                UserActivity.user_id == user_id,
                UserActivity.created_at >= cutoff
            )
            .order_by(desc(UserActivity.created_at))
            .limit(limit)
        )
        activities = result.scalars().all()

        return [
            {
                "activity_type": a.activity_type,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "context": a.context,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in activities
        ]
    except Exception:
        # Tables might not exist yet
        return []


async def load_recent_conversation(
    db: AsyncSession,
    user_id: str,
    session_id: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Load recent conversation messages for context.

    Args:
        db: Database session
        user_id: User ID
        session_id: Optional specific session ID
        limit: Maximum number of messages to return

    Returns:
        List of message dictionaries
    """
    try:
        from app.tami.models import ConversationSession, ConversationMessage

        # Find the most recent active session if no session_id provided
        if not session_id:
            session_result = await db.execute(
                select(ConversationSession)
                .where(
                    ConversationSession.user_id == user_id,
                    ConversationSession.is_active == True
                )
                .order_by(desc(ConversationSession.last_message_at))
                .limit(1)
            )
            session = session_result.scalar_one_or_none()
            if not session:
                return []
            session_id = session.id

        # Load messages from session
        result = await db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(desc(ConversationMessage.created_at))
            .limit(limit)
        )
        messages = result.scalars().all()

        # Reverse to get chronological order
        return [
            {
                "role": m.role,
                "content": m.content,
                "mode": m.mode,
                "detected_intent": m.detected_intent,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in reversed(list(messages))
        ]
    except Exception:
        # Tables might not exist yet
        return []


async def get_activity_summary(
    db: AsyncSession,
    user_id: str,
    hours: int = 24
) -> Dict[str, Any]:
    """
    Get a summary of user activities for TAMI context.

    Returns a summary dict with:
    - most_viewed: What areas the user has been looking at
    - recent_actions: What actions they've taken
    - focus_area: What the user seems focused on
    """
    activities = await load_recent_activities(db, user_id, hours=hours)

    if not activities:
        return {
            "most_viewed": [],
            "recent_actions": [],
            "focus_area": None,
            "activity_count": 0,
        }

    # Count activity types
    type_counts: Dict[str, int] = {}
    entity_types: Dict[str, int] = {}
    action_activities = []

    for activity in activities:
        act_type = activity["activity_type"]
        type_counts[act_type] = type_counts.get(act_type, 0) + 1

        if activity["entity_type"]:
            entity_types[activity["entity_type"]] = entity_types.get(activity["entity_type"], 0) + 1

        # Track non-view actions
        if not act_type.startswith("view_"):
            action_activities.append(activity)

    # Determine focus area
    focus_area = None
    if entity_types:
        focus_area = max(entity_types, key=entity_types.get)

    # Get most viewed areas
    view_activities = {k: v for k, v in type_counts.items() if k.startswith("view_")}
    most_viewed = sorted(view_activities.keys(), key=lambda x: view_activities[x], reverse=True)[:3]

    return {
        "most_viewed": most_viewed,
        "recent_actions": action_activities[:5],
        "focus_area": focus_area,
        "activity_count": len(activities),
    }


def format_behavior_for_prompt(
    activities: List[Dict[str, Any]],
    conversation: List[Dict[str, Any]]
) -> str:
    """
    Format user behavior signals as a prompt section.

    This gives TAMI context about what the user has been doing.
    """
    lines = []

    if activities:
        lines.append("=== RECENT USER ACTIVITY ===")
        # Group by type for a cleaner summary
        type_counts: Dict[str, int] = {}
        for act in activities:
            act_type = act["activity_type"].replace("_", " ").title()
            type_counts[act_type] = type_counts.get(act_type, 0) + 1

        for act_type, count in sorted(type_counts.items(), key=lambda x: -x[1])[:5]:
            lines.append(f"- {act_type}: {count} times")

        # Show most recent specific actions
        recent_actions = [a for a in activities if not a["activity_type"].startswith("view_")][:3]
        if recent_actions:
            lines.append("\nMost recent actions:")
            for act in recent_actions:
                act_type = act["activity_type"].replace("_", " ").title()
                context_str = ""
                if act.get("context"):
                    if "name" in act["context"]:
                        context_str = f" ({act['context']['name']})"
                    elif "scenario_type" in act["context"]:
                        context_str = f" ({act['context']['scenario_type']})"
                lines.append(f"  - {act_type}{context_str}")
        lines.append("")

    if conversation:
        lines.append("=== CONVERSATION CONTEXT ===")
        lines.append(f"Previous messages in this session: {len(conversation)}")
        # Show last user message intent if available
        user_msgs = [m for m in conversation if m["role"] == "user"]
        if user_msgs:
            last_user = user_msgs[-1]
            if last_user.get("detected_intent"):
                lines.append(f"Last topic: {last_user['detected_intent'].replace('_', ' ').title()}")
        lines.append("")

    return "\n".join(lines) if lines else ""
