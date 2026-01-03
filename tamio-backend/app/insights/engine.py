"""
Insights Engine - Computes behavioral insights from source data.

This engine analyzes:
1. Income Behaviour: Client payment patterns and revenue concentration
2. Expense Behaviour: Budget compliance and expense trends
3. Cash Discipline: Buffer health and upcoming risk windows
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.data.clients.models import Client
from app.data.expenses.models import ExpenseBucket
from app.data.balances.models import CashAccount
from app.forecast.engine_v2 import calculate_forecast_v2
from app.insights.schemas import (
    ClientPaymentBehaviour,
    RevenueConcentration,
    IncomeBehaviourInsights,
    ExpenseCategoryTrend,
    ExpenseBucketDetail,
    ExpenseBehaviourInsights,
    BufferHealthMetric,
    UpcomingRiskWindow,
    CashDisciplineInsights,
    TrafficLightCondition,
    TrafficLightStatus,
    InsightsSummary,
    InsightsResponse,
)


# =============================================================================
# Income Behaviour Analysis
# =============================================================================

async def calculate_income_behaviour(
    db: AsyncSession,
    user_id: str,
    clients: List[Client]
) -> IncomeBehaviourInsights:
    """
    Analyze income behaviour including payment patterns and revenue concentration.
    """
    # Calculate total monthly revenue
    total_revenue = Decimal("0")
    client_revenues: List[Tuple[Client, Decimal]] = []

    for client in clients:
        if client.status != "active":
            continue
        config = client.billing_config or {}
        amount = Decimal(str(config.get("amount", 0)))
        if amount > 0:
            total_revenue += amount
            client_revenues.append((client, amount))

    # Sort by revenue descending
    client_revenues.sort(key=lambda x: x[1], reverse=True)

    # Analyze payment behaviour
    payment_behaviours: List[ClientPaymentBehaviour] = []
    delayed_count = 0
    delayed_revenue = Decimal("0")

    for client, amount in client_revenues:
        pct = (amount / total_revenue * 100) if total_revenue > 0 else Decimal("0")
        is_delayed = client.payment_behavior == "delayed"
        if is_delayed:
            delayed_count += 1
            delayed_revenue += amount

        # Determine risk level
        risk_level = "low"
        if is_delayed and pct > 20:
            risk_level = "high"
        elif is_delayed or pct > 30:
            risk_level = "medium"

        payment_behaviours.append(ClientPaymentBehaviour(
            client_id=client.id,
            client_name=client.name,
            payment_behavior=client.payment_behavior or "unknown",
            monthly_amount=str(amount),
            percentage_of_revenue=f"{pct:.1f}",
            risk_level=risk_level,
        ))

    # Analyze revenue concentration
    concentrations: List[RevenueConcentration] = []
    high_concentration_count = 0

    for client, amount in client_revenues:
        pct = (amount / total_revenue * 100) if total_revenue > 0 else Decimal("0")
        is_high = pct > 25

        if is_high:
            high_concentration_count += 1

        concentrations.append(RevenueConcentration(
            client_id=client.id,
            client_name=client.name,
            monthly_amount=str(amount),
            percentage=f"{pct:.1f}",
            is_high_concentration=is_high,
        ))

    # Generate recommendations
    recommendations = []
    if high_concentration_count > 0:
        top_client = concentrations[0] if concentrations else None
        if top_client and float(top_client.percentage) > 40:
            recommendations.append(
                f"High revenue concentration: {top_client.client_name} represents "
                f"{top_client.percentage}% of revenue. Consider diversifying."
            )
    if delayed_count > 0:
        recommendations.append(
            f"{delayed_count} client(s) have delayed payment patterns. "
            "Consider tighter payment terms or deposits."
        )
    if total_revenue == 0:
        recommendations.append("No active revenue sources. Add clients to track income.")

    revenue_at_risk_pct = (
        (delayed_revenue / total_revenue * 100) if total_revenue > 0 else Decimal("0")
    )

    return IncomeBehaviourInsights(
        total_monthly_revenue=str(total_revenue),
        clients_with_delayed_payments=delayed_count,
        clients_with_high_concentration=high_concentration_count,
        revenue_at_risk_percentage=f"{revenue_at_risk_pct:.1f}",
        payment_behaviour=payment_behaviours,
        revenue_concentration=concentrations,
        recommendations=recommendations,
    )


# =============================================================================
# Expense Behaviour Analysis
# =============================================================================

async def calculate_expense_behaviour(
    db: AsyncSession,
    user_id: str,
    buckets: List[ExpenseBucket]
) -> ExpenseBehaviourInsights:
    """
    Analyze expense behaviour including category trends and budget compliance.
    """
    total_expenses = Decimal("0")
    fixed_expenses = Decimal("0")
    variable_expenses = Decimal("0")

    # Group by category
    category_totals: Dict[str, Decimal] = {}
    expense_details: List[ExpenseBucketDetail] = []

    for bucket in buckets:
        amount = bucket.monthly_amount or Decimal("0")
        total_expenses += amount

        if bucket.bucket_type == "fixed":
            fixed_expenses += amount
        else:
            variable_expenses += amount

        category = bucket.category or "other"
        category_totals[category] = category_totals.get(category, Decimal("0")) + amount

        expense_details.append(ExpenseBucketDetail(
            bucket_id=bucket.id,
            name=bucket.name,
            category=category,
            monthly_amount=str(amount),
            bucket_type=bucket.bucket_type,
            priority=bucket.priority,
            is_stable=bucket.is_stable,
        ))

    # Analyze category trends
    # Note: Without historical data, we simulate "previous" as current
    # In production, this would compare against actual historical values
    category_trends: List[ExpenseCategoryTrend] = []
    categories_rising = 0
    categories_over_budget = 0

    for category, amount in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
        # Simulated previous (would come from historical data)
        previous = amount  # Same as current without history
        change_pct = Decimal("0")

        # Determine trend based on bucket stability
        category_buckets = [b for b in buckets if b.category == category]
        unstable_count = sum(1 for b in category_buckets if not b.is_stable)
        trend = "stable"
        if unstable_count > len(category_buckets) / 2:
            trend = "rising"  # More variable buckets suggest rising
            categories_rising += 1

        # Budget variance (simplified - would compare against budget if stored)
        is_over_budget = False
        budget_variance = "0"

        category_trends.append(ExpenseCategoryTrend(
            category=category,
            current_monthly=str(amount),
            previous_monthly=str(previous),
            change_percentage=f"{change_pct:.1f}",
            trend=trend,
            is_over_budget=is_over_budget,
            budget_variance=budget_variance,
        ))

    # Generate recommendations
    recommendations = []
    if variable_expenses > fixed_expenses:
        recommendations.append(
            "Variable expenses exceed fixed. Consider locking in rates where possible."
        )
    if categories_rising > 0:
        recommendations.append(
            f"{categories_rising} expense categories marked as unstable/rising. "
            "Review for cost control opportunities."
        )

    high_priority_total = sum(
        b.monthly_amount or Decimal("0")
        for b in buckets
        if b.priority in ("high", "essential")
    )
    if total_expenses > 0:
        essential_pct = high_priority_total / total_expenses * 100
        if essential_pct < 50:
            recommendations.append(
                f"Only {essential_pct:.0f}% of expenses are essential. "
                "Review discretionary spending."
            )

    return ExpenseBehaviourInsights(
        total_monthly_expenses=str(total_expenses),
        fixed_expenses=str(fixed_expenses),
        variable_expenses=str(variable_expenses),
        categories_rising=categories_rising,
        categories_over_budget=categories_over_budget,
        category_trends=category_trends,
        expense_details=expense_details,
        recommendations=recommendations,
    )


# =============================================================================
# Cash Discipline Analysis
# =============================================================================

async def calculate_cash_discipline(
    db: AsyncSession,
    user_id: str,
    forecast: Dict[str, Any],
    monthly_expenses: Decimal,
    buffer_months: int = 3
) -> CashDisciplineInsights:
    """
    Analyze cash discipline including buffer health and upcoming risks.
    """
    # Get current cash position
    result = await db.execute(
        select(func.sum(CashAccount.balance))
        .where(CashAccount.user_id == user_id)
    )
    current_cash = result.scalar() or Decimal("0")

    # Calculate target buffer
    target_buffer = monthly_expenses * buffer_months

    # Analyze forecast weeks for risk windows
    weeks = forecast.get("weeks", [])
    upcoming_risks: List[UpcomingRiskWindow] = []
    weeks_until_risk = None

    for week in weeks:
        if week["week_number"] == 0:
            continue  # Skip week 0 (current position)

        ending_balance = Decimal(week["ending_balance"])
        if ending_balance < target_buffer:
            shortfall = target_buffer - ending_balance
            severity = "critical" if ending_balance <= 0 else "warning"

            if weeks_until_risk is None:
                weeks_until_risk = week["week_number"]

            # Identify contributing factors
            factors = []
            cash_out = Decimal(week["cash_out"])
            cash_in = Decimal(week["cash_in"])
            if cash_out > cash_in:
                factors.append(f"Net outflow of ${cash_out - cash_in:,.0f}")
            if cash_in == 0:
                factors.append("No expected income")

            upcoming_risks.append(UpcomingRiskWindow(
                week_number=week["week_number"],
                week_start=week["week_start"],
                projected_balance=str(ending_balance),
                target_buffer=str(target_buffer),
                shortfall=str(shortfall),
                severity=severity,
                contributing_factors=factors,
            ))

    # Calculate buffer health score (0-100)
    if target_buffer > 0:
        buffer_ratio = float(current_cash / target_buffer)
        if buffer_ratio >= 1.5:
            buffer_health_score = 100
        elif buffer_ratio >= 1.0:
            buffer_health_score = 70 + int((buffer_ratio - 1.0) * 60)
        elif buffer_ratio >= 0.5:
            buffer_health_score = 30 + int((buffer_ratio - 0.5) * 80)
        else:
            buffer_health_score = int(buffer_ratio * 60)
    else:
        buffer_health_score = 50  # No expenses means neutral score

    # Determine buffer status
    if buffer_health_score >= 70:
        buffer_status = "healthy"
    elif buffer_health_score >= 40:
        buffer_status = "at_risk"
    else:
        buffer_status = "critical"

    # Determine trend (would use historical data)
    buffer_trend = "stable"
    if upcoming_risks:
        buffer_trend = "declining"

    # Generate recommendations
    recommendations = []
    if buffer_status == "critical":
        recommendations.append(
            "Cash buffer is critically low. Prioritize building reserves immediately."
        )
    elif buffer_status == "at_risk":
        recommendations.append(
            f"Cash buffer below {buffer_months}-month target. "
            "Consider reducing discretionary expenses."
        )
    if weeks_until_risk and weeks_until_risk <= 4:
        recommendations.append(
            f"Buffer breach projected in {weeks_until_risk} weeks. "
            "Accelerate receivables or defer non-essential expenses."
        )
    if not recommendations:
        recommendations.append(
            "Cash discipline is healthy. Maintain current practices."
        )

    return CashDisciplineInsights(
        current_buffer=str(current_cash),
        target_buffer=str(target_buffer),
        buffer_months=buffer_months,
        buffer_health_score=buffer_health_score,
        buffer_status=buffer_status,
        days_below_target_last_90=0,  # Would need historical tracking
        buffer_trend=buffer_trend,
        upcoming_risks=upcoming_risks[:5],  # Limit to 5 risk windows
        weeks_until_risk=weeks_until_risk,
        recommendations=recommendations,
    )


# =============================================================================
# Main Insights Calculation
# =============================================================================

async def calculate_insights(
    db: AsyncSession,
    user_id: str,
    buffer_months: int = 3
) -> InsightsResponse:
    """
    Calculate complete insights for a user.

    This is the main entry point that coordinates all insight calculations.
    """
    # Fetch all required data
    result = await db.execute(
        select(Client).where(Client.user_id == user_id)
    )
    clients = list(result.scalars().all())

    result = await db.execute(
        select(ExpenseBucket).where(ExpenseBucket.user_id == user_id)
    )
    buckets = list(result.scalars().all())

    # Get forecast for cash discipline analysis
    forecast = await calculate_forecast_v2(db, user_id, weeks=13)

    # Calculate monthly expenses for buffer calculations
    monthly_expenses = sum(
        b.monthly_amount or Decimal("0") for b in buckets
    )

    # Calculate each insight category
    income_insights = await calculate_income_behaviour(db, user_id, clients)
    expense_insights = await calculate_expense_behaviour(db, user_id, buckets)
    cash_insights = await calculate_cash_discipline(
        db, user_id, forecast, monthly_expenses, buffer_months
    )

    # Calculate summary scores
    income_score = _calculate_income_score(income_insights)
    expense_score = _calculate_expense_score(expense_insights)
    cash_score = cash_insights.buffer_health_score
    overall_score = (income_score + expense_score + cash_score) // 3

    # Calculate traffic light status using deterministic rules
    traffic_light = _calculate_traffic_light(
        income_insights,
        expense_insights,
        cash_insights,
        forecast,
    )

    # Collect alerts from traffic light conditions
    alerts = [
        c.condition for c in traffic_light.conditions_met
        if c.severity in ("red", "amber")
    ]

    # Combine top recommendations
    all_recommendations = (
        income_insights.recommendations +
        expense_insights.recommendations +
        cash_insights.recommendations
    )
    top_recommendations = all_recommendations[:5]

    summary = InsightsSummary(
        traffic_light=traffic_light,
        income_health_score=income_score,
        expense_health_score=expense_score,
        cash_discipline_score=cash_score,
        overall_health_score=overall_score,
        alerts=alerts,
        top_recommendations=top_recommendations,
    )

    return InsightsResponse(
        summary=summary,
        income_behaviour=income_insights,
        expense_behaviour=expense_insights,
        cash_discipline=cash_insights,
    )


def _calculate_income_score(insights: IncomeBehaviourInsights) -> int:
    """Calculate income health score (0-100)."""
    score = 100

    # Deduct for high concentration
    if insights.clients_with_high_concentration > 0:
        score -= 15 * min(insights.clients_with_high_concentration, 3)

    # Deduct for delayed payments
    if insights.clients_with_delayed_payments > 0:
        score -= 10 * min(insights.clients_with_delayed_payments, 3)

    # Deduct for revenue at risk
    revenue_at_risk = float(insights.revenue_at_risk_percentage)
    if revenue_at_risk > 30:
        score -= 20
    elif revenue_at_risk > 15:
        score -= 10

    return max(0, score)


def _calculate_expense_score(insights: ExpenseBehaviourInsights) -> int:
    """Calculate expense health score (0-100)."""
    score = 100

    # Deduct for rising categories
    if insights.categories_rising > 0:
        score -= 10 * min(insights.categories_rising, 3)

    # Deduct for over budget
    if insights.categories_over_budget > 0:
        score -= 15 * min(insights.categories_over_budget, 3)

    # Deduct if variable > fixed (less predictable)
    fixed = Decimal(insights.fixed_expenses)
    variable = Decimal(insights.variable_expenses)
    if variable > fixed and (fixed + variable) > 0:
        variable_ratio = float(variable / (fixed + variable))
        if variable_ratio > 0.6:
            score -= 15

    return max(0, score)


# =============================================================================
# Traffic Light Status Calculation (TAMI Knowledge Framework)
# =============================================================================

def _calculate_traffic_light(
    income_insights: IncomeBehaviourInsights,
    expense_insights: ExpenseBehaviourInsights,
    cash_insights: CashDisciplineInsights,
    forecast: Dict[str, Any],
) -> TrafficLightStatus:
    """
    Calculate traffic light status using deterministic rules.

    Rules are based on TAMI's curated knowledge framework:

    RED (Action Required) - Any of:
    - Buffer breached or projected breach within 0-4 weeks
    - Payroll coverage at risk (cash < fixed expenses)
    - Cash-out exceeds cash-in with no recovery path
    - Clustering of delayed payments (multiple clients)

    AMBER (Watch Closely) - Any of:
    - Buffer likely breached in 4-12 weeks
    - One or more delayed payments
    - Cost growth outpacing inflows
    - Increased forecast variance (high concentration risk)

    GREEN (Stable) - All of:
    - Buffer threshold maintained
    - Cash-in covers fixed cash-out
    - Forecast volatility is low
    """
    conditions: List[TrafficLightCondition] = []

    # Get key metrics
    current_buffer = Decimal(cash_insights.current_buffer)
    target_buffer = Decimal(cash_insights.target_buffer)
    weeks_until_risk = cash_insights.weeks_until_risk
    total_income = Decimal(income_insights.total_monthly_revenue)
    fixed_expenses = Decimal(expense_insights.fixed_expenses)
    total_expenses = Decimal(expense_insights.total_monthly_expenses)
    delayed_payment_count = income_insights.clients_with_delayed_payments
    high_concentration_count = income_insights.clients_with_high_concentration

    # Check for critical risk windows
    critical_risk_weeks = [
        r for r in cash_insights.upcoming_risks
        if r.severity == "critical"
    ]

    # ==========================================================================
    # RED CONDITIONS (Action Required)
    # ==========================================================================

    # Condition 1: Buffer breached or projected breach within 0-4 weeks
    buffer_breach_imminent = weeks_until_risk is not None and weeks_until_risk <= 4
    conditions.append(TrafficLightCondition(
        condition="Buffer breach projected within 0-4 weeks",
        met=buffer_breach_imminent,
        severity="red",
    ))

    # Condition 2: Current cash below buffer (already breached)
    buffer_already_breached = current_buffer < target_buffer and target_buffer > 0
    conditions.append(TrafficLightCondition(
        condition="Current cash below buffer target",
        met=buffer_already_breached,
        severity="red" if current_buffer <= 0 else "amber",
    ))

    # Condition 3: Payroll/fixed expenses at risk (cash < monthly fixed expenses)
    payroll_at_risk = current_buffer < fixed_expenses and fixed_expenses > 0
    conditions.append(TrafficLightCondition(
        condition="Cash insufficient to cover fixed expenses",
        met=payroll_at_risk,
        severity="red",
    ))

    # Condition 4: Cash-out exceeds cash-in with no recovery
    # Check if expenses > income consistently (negative runway)
    negative_cash_flow = total_expenses > total_income and total_income > 0
    conditions.append(TrafficLightCondition(
        condition="Monthly expenses exceed monthly income",
        met=negative_cash_flow,
        severity="red" if negative_cash_flow and buffer_breach_imminent else "amber",
    ))

    # Condition 5: Clustering of delayed payments (>= 2 clients)
    clustered_delays = delayed_payment_count >= 2
    conditions.append(TrafficLightCondition(
        condition="Multiple clients with payment delays",
        met=clustered_delays,
        severity="red" if clustered_delays and high_concentration_count > 0 else "amber",
    ))

    # ==========================================================================
    # AMBER CONDITIONS (Watch Closely)
    # ==========================================================================

    # Condition 6: Buffer breach projected in 4-12 weeks
    buffer_breach_medium_term = (
        weeks_until_risk is not None and
        4 < weeks_until_risk <= 12
    )
    conditions.append(TrafficLightCondition(
        condition="Buffer breach projected in 4-12 weeks",
        met=buffer_breach_medium_term,
        severity="amber",
    ))

    # Condition 7: Any delayed payments
    has_delayed_payments = delayed_payment_count > 0
    conditions.append(TrafficLightCondition(
        condition="One or more clients with delayed payment patterns",
        met=has_delayed_payments,
        severity="amber",
    ))

    # Condition 8: High revenue concentration (forecast variance risk)
    has_concentration_risk = high_concentration_count > 0
    conditions.append(TrafficLightCondition(
        condition="High revenue concentration (client >25% of revenue)",
        met=has_concentration_risk,
        severity="amber",
    ))

    # Condition 9: Cost growth outpacing inflows (variable expenses rising)
    categories_rising = expense_insights.categories_rising > 0
    conditions.append(TrafficLightCondition(
        condition="Expense categories marked as rising/unstable",
        met=categories_rising,
        severity="amber",
    ))

    # ==========================================================================
    # GREEN CONDITIONS (Stable)
    # ==========================================================================

    # Condition 10: Buffer threshold maintained
    buffer_healthy = current_buffer >= target_buffer
    conditions.append(TrafficLightCondition(
        condition="Cash buffer at or above target",
        met=buffer_healthy,
        severity="green",
    ))

    # Condition 11: Income covers fixed expenses
    income_covers_fixed = total_income >= fixed_expenses
    conditions.append(TrafficLightCondition(
        condition="Monthly income covers fixed expenses",
        met=income_covers_fixed,
        severity="green",
    ))

    # ==========================================================================
    # Determine Final Status
    # ==========================================================================

    # Check for RED conditions
    red_conditions = [c for c in conditions if c.met and c.severity == "red"]
    amber_conditions = [c for c in conditions if c.met and c.severity == "amber"]
    green_conditions = [c for c in conditions if c.met and c.severity == "green"]

    if red_conditions:
        # RED: Action Required
        return TrafficLightStatus(
            status="red",
            label="Action Required",
            meaning=(
                "Material liquidity risk is imminent or already present. "
                "Delay reduces available options."
            ),
            conditions_met=red_conditions + amber_conditions,
            guidance=[
                "Immediate scenario modelling recommended",
                "Prioritise reversible actions first",
                "Confirm which decisions need to be made now vs deferred",
            ],
            tami_message="This needs attention now. Let's look at your options.",
            action_window="0-4 weeks",
            urgency="high",
        )

    elif amber_conditions:
        # AMBER: Watch Closely
        return TrafficLightStatus(
            status="amber",
            label="Watch Closely",
            meaning=(
                "Risk is emerging but still manageable. "
                "Action window exists, but it's not closing yet."
            ),
            conditions_met=amber_conditions,
            guidance=[
                "Review scenarios",
                "Prepare contingency actions",
                "Decide what levers are available if conditions worsen",
            ],
            tami_message="This isn't urgent yet, but it's worth preparing.",
            action_window="4-12 weeks",
            urgency="medium",
        )

    else:
        # GREEN: Stable
        return TrafficLightStatus(
            status="green",
            label="Stable",
            meaning=(
                "Cash position is healthy. Buffer rules are respected. "
                "No near-term liquidity stress."
            ),
            conditions_met=green_conditions,
            guidance=[
                "No action required",
                "Good time for planning, growth scenarios, or investment decisions",
            ],
            tami_message="You're in a stable position. Nothing urgent to act on. It's a good time for growth.",
            action_window=None,
            urgency="none",
        )
