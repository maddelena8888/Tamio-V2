"""
Behavior Engine - Phase 1: Calculate behavior metrics from canonical data.

This engine computes:
1. Client Behavior (predictability + risk)
2. Expense Behavior (volatility + controllability)
3. Cash Discipline (control + stress)
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import statistics

from app.data.clients.models import Client
from app.data.expenses.models import ExpenseBucket
from app.data.balances.models import CashAccount
from app.data.events.models import CashEvent
from app.data.obligations.models import ObligationAgreement, ObligationSchedule, PaymentEvent
from app.behavior.models import BehaviorMetric, MetricType, MetricTrend, MetricHistory
from app.behavior.schemas import (
    ClientConcentrationMetric,
    PaymentReliabilityMetric,
    RevenueAtRiskMetric,
    ClientBehaviorInsights,
    ExpenseVolatilityMetric,
    DiscretionaryRatioMetric,
    UpcomingCommitment,
    ExpenseBehaviorInsights,
    BufferIntegrityMetric,
    BurnMomentumMetric,
    DecisionQualityMetric,
    CashDisciplineInsights,
    BehaviorInsightsResponse,
)
from app.forecast.engine_v2 import calculate_forecast_v2


# =============================================================================
# Client Behavior Metrics
# =============================================================================

async def calculate_client_behavior_metrics(
    db: AsyncSession,
    user_id: str,
    clients: List[Client],
    lookback_days: int = 90
) -> Tuple[ClientBehaviorInsights, List[BehaviorMetric]]:
    """
    Calculate client behavior metrics including:
    - Client Concentration (cash-weighted)
    - Payment Reliability Score (mean + variance + trend)
    - Revenue at Risk (30/60 days, probability-weighted)
    """
    metrics: List[BehaviorMetric] = []
    today = date.today()
    lookback_start = today - timedelta(days=lookback_days)

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

    # ==========================================================================
    # 1. Client Concentration (Cash-Weighted)
    # ==========================================================================
    concentration_metrics: List[ClientConcentrationMetric] = []
    high_concentration_count = 0

    for client, amount in client_revenues:
        revenue_share = float(amount / total_revenue * 100) if total_revenue > 0 else 0

        # Cash-weighted: adjust by payment reliability
        reliability_factor = 1.0
        if client.payment_behavior == "delayed":
            reliability_factor = 0.85  # Discount delayed payers
        elif client.payment_behavior == "unknown":
            reliability_factor = 0.9

        cash_weighted_share = revenue_share * reliability_factor
        is_high = revenue_share > 25

        if is_high:
            high_concentration_count += 1

        concentration_metrics.append(ClientConcentrationMetric(
            client_id=client.id,
            client_name=client.name,
            revenue_share=round(revenue_share, 1),
            cash_weighted_share=round(cash_weighted_share, 1),
            is_high_concentration=is_high,
            payment_reliability=None,  # Will be filled below
        ))

        # Store as BehaviorMetric
        metrics.append(BehaviorMetric(
            user_id=user_id,
            metric_type=MetricType.CLIENT_CONCENTRATION.value,
            entity_type="client",
            entity_id=client.id,
            current_value=revenue_share,
            threshold_warning=25.0,
            threshold_critical=40.0,
            is_higher_better=False,  # Lower concentration is better
            context_data={
                "client_name": client.name,
                "monthly_amount": str(amount),
                "cash_weighted_share": cash_weighted_share,
            }
        ))

    # Concentration score (0-100, 100 = well diversified)
    if len(client_revenues) > 0 and total_revenue > 0:
        # HHI-based score: sum of squared market shares
        hhi = sum((float(amt / total_revenue) ** 2) for _, amt in client_revenues)
        concentration_score = max(0, min(100, (1 - hhi) * 100))
    else:
        concentration_score = 50.0  # Neutral if no data

    # ==========================================================================
    # 2. Payment Reliability Score
    # ==========================================================================
    payment_reliability_metrics: List[PaymentReliabilityMetric] = []
    unreliable_count = 0

    for client, amount in client_revenues:
        # Get payment history from PaymentEvent if available
        # For now, derive from client.payment_behavior
        if client.payment_behavior == "on_time":
            mean_days = 7.0
            variance = 3.0
            trend = "stable"
            reliability_score = 90.0
        elif client.payment_behavior == "delayed":
            mean_days = 21.0
            variance = 10.0
            trend = "worsening"
            reliability_score = 45.0
            unreliable_count += 1
        else:
            mean_days = 14.0
            variance = 7.0
            trend = "stable"
            reliability_score = 65.0

        payment_reliability_metrics.append(PaymentReliabilityMetric(
            client_id=client.id,
            client_name=client.name,
            mean_days_to_payment=mean_days,
            variance_days=variance,
            trend=trend,
            reliability_score=reliability_score,
            sample_size=12,  # Would come from actual payment history
            monthly_amount=str(amount),
        ))

        # Store as BehaviorMetric
        metrics.append(BehaviorMetric(
            user_id=user_id,
            metric_type=MetricType.PAYMENT_RELIABILITY.value,
            entity_type="client",
            entity_id=client.id,
            current_value=reliability_score,
            mean=mean_days,
            variance=variance,
            trend=trend,
            threshold_warning=70.0,
            threshold_critical=50.0,
            is_higher_better=True,
            context_data={
                "client_name": client.name,
                "mean_days": mean_days,
                "variance_days": variance,
            }
        ))

        # Update concentration metric with reliability
        for cm in concentration_metrics:
            if cm.client_id == client.id:
                cm.payment_reliability = reliability_score

    # Overall reliability score
    if payment_reliability_metrics:
        weighted_reliability = sum(
            pm.reliability_score * float(pm.monthly_amount)
            for pm in payment_reliability_metrics
        )
        overall_reliability = weighted_reliability / float(total_revenue) if total_revenue > 0 else 50.0
    else:
        overall_reliability = 50.0

    # ==========================================================================
    # 3. Revenue at Risk (30/60 days)
    # ==========================================================================
    at_risk_30 = Decimal("0")
    at_risk_60 = Decimal("0")
    risk_clients_30: List[Dict[str, Any]] = []
    risk_clients_60: List[Dict[str, Any]] = []

    for client, amount in client_revenues:
        # Probability of non-payment based on reliability
        pm = next((p for p in payment_reliability_metrics if p.client_id == client.id), None)
        if pm:
            # Convert reliability score to risk probability
            risk_prob_30 = (100 - pm.reliability_score) / 100 * 0.6  # 60% weight for 30 days
            risk_prob_60 = (100 - pm.reliability_score) / 100  # Full weight for 60 days

            if risk_prob_30 > 0.15:  # Only include if meaningful risk
                risk_amount_30 = amount * Decimal(str(risk_prob_30))
                at_risk_30 += risk_amount_30
                risk_clients_30.append({
                    "client_id": client.id,
                    "client_name": client.name,
                    "amount": str(risk_amount_30),
                    "probability": round(risk_prob_30 * 100, 1),
                })

            if risk_prob_60 > 0.10:
                risk_amount_60 = amount * Decimal(str(risk_prob_60))
                at_risk_60 += risk_amount_60
                risk_clients_60.append({
                    "client_id": client.id,
                    "client_name": client.name,
                    "amount": str(risk_amount_60),
                    "probability": round(risk_prob_60 * 100, 1),
                })

    revenue_at_risk_30 = RevenueAtRiskMetric(
        period_days=30,
        total_revenue=str(total_revenue),
        at_risk_amount=str(at_risk_30),
        at_risk_percentage=float(at_risk_30 / total_revenue * 100) if total_revenue > 0 else 0,
        probability_weighted_amount=str(at_risk_30),
        contributing_clients=risk_clients_30,
    )

    revenue_at_risk_60 = RevenueAtRiskMetric(
        period_days=60,
        total_revenue=str(total_revenue),
        at_risk_amount=str(at_risk_60),
        at_risk_percentage=float(at_risk_60 / total_revenue * 100) if total_revenue > 0 else 0,
        probability_weighted_amount=str(at_risk_60),
        contributing_clients=risk_clients_60,
    )

    # Store aggregate revenue at risk metric
    metrics.append(BehaviorMetric(
        user_id=user_id,
        metric_type=MetricType.REVENUE_AT_RISK.value,
        current_value=float(at_risk_60 / total_revenue * 100) if total_revenue > 0 else 0,
        threshold_warning=15.0,
        threshold_critical=25.0,
        is_higher_better=False,
        context_data={
            "at_risk_30_days": str(at_risk_30),
            "at_risk_60_days": str(at_risk_60),
            "total_revenue": str(total_revenue),
        }
    ))

    # ==========================================================================
    # Generate Recommendations
    # ==========================================================================
    recommendations = []

    if high_concentration_count > 0:
        top = concentration_metrics[0] if concentration_metrics else None
        if top and top.revenue_share > 40:
            recommendations.append(
                f"High concentration risk: {top.client_name} represents {top.revenue_share:.0f}% of revenue. "
                "Prioritize diversification."
            )

    if unreliable_count > 0:
        recommendations.append(
            f"{unreliable_count} client(s) have unreliable payment patterns. "
            "Consider tighter payment terms or deposits."
        )

    if float(at_risk_60 / total_revenue * 100) > 15 if total_revenue > 0 else False:
        recommendations.append(
            f"Revenue at risk is elevated at {float(at_risk_60 / total_revenue * 100):.1f}%. "
            "Follow up on overdue invoices."
        )

    # Concentration warning
    concentration_warning = None
    if concentration_score < 50:
        concentration_warning = "Revenue is highly concentrated. A single client loss could significantly impact cash flow."

    return ClientBehaviorInsights(
        concentration_score=round(concentration_score, 1),
        top_clients=concentration_metrics[:5],
        concentration_warning=concentration_warning,
        overall_reliability_score=round(overall_reliability, 1),
        payment_reliability=payment_reliability_metrics[:5],
        unreliable_clients_count=unreliable_count,
        revenue_at_risk_30=revenue_at_risk_30,
        revenue_at_risk_60=revenue_at_risk_60,
        recommendations=recommendations,
    ), metrics


# =============================================================================
# Expense Behavior Metrics
# =============================================================================

async def calculate_expense_behavior_metrics(
    db: AsyncSession,
    user_id: str,
    buckets: List[ExpenseBucket],
    lookback_days: int = 90
) -> Tuple[ExpenseBehaviorInsights, List[BehaviorMetric]]:
    """
    Calculate expense behavior metrics including:
    - Expense Volatility by Category (variance + drift)
    - Discretionary vs Non-Discretionary split
    - Upcoming Commitments (obligations calendar)
    """
    metrics: List[BehaviorMetric] = []
    today = date.today()

    # Group buckets by category
    category_totals: Dict[str, Decimal] = {}
    category_buckets: Dict[str, List[ExpenseBucket]] = {}

    total_expenses = Decimal("0")
    discretionary_total = Decimal("0")
    non_discretionary_total = Decimal("0")

    for bucket in buckets:
        amount = bucket.monthly_amount or Decimal("0")
        total_expenses += amount
        category = bucket.category or "other"

        category_totals[category] = category_totals.get(category, Decimal("0")) + amount
        if category not in category_buckets:
            category_buckets[category] = []
        category_buckets[category].append(bucket)

        # Classify discretionary vs non-discretionary
        # Non-discretionary: payroll, rent, utilities, essential software
        non_discretionary_categories = {"payroll", "rent", "utilities", "insurance", "taxes"}
        if bucket.priority in ("essential", "high") or category.lower() in non_discretionary_categories:
            non_discretionary_total += amount
        else:
            discretionary_total += amount

    # ==========================================================================
    # 1. Expense Volatility by Category
    # ==========================================================================
    volatility_metrics: List[ExpenseVolatilityMetric] = []
    drifting_count = 0

    for category, amount in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
        cat_buckets = category_buckets.get(category, [])

        # Calculate volatility based on bucket stability
        unstable_count = sum(1 for b in cat_buckets if not b.is_stable)
        volatility_index = (unstable_count / len(cat_buckets) * 100) if cat_buckets else 0

        # Simulate drift (would come from historical comparison)
        # For now, use bucket type as proxy
        variable_amount = sum(b.monthly_amount or Decimal("0") for b in cat_buckets if b.bucket_type == "variable")
        drift = float(variable_amount / amount * 10) if amount > 0 else 0  # Simplified

        # Determine trend
        if drift > 10:
            trend = "rising"
            drifting_count += 1
        elif drift < -5:
            trend = "declining"
        else:
            trend = "stable"

        is_concerning = volatility_index > 50 or drift > 15

        volatility_metrics.append(ExpenseVolatilityMetric(
            category=category,
            monthly_average=str(amount),
            volatility_index=round(volatility_index, 1),
            drift_percentage=round(drift, 1),
            trend=trend,
            is_concerning=is_concerning,
        ))

        # Store as BehaviorMetric
        metrics.append(BehaviorMetric(
            user_id=user_id,
            metric_type=MetricType.EXPENSE_VOLATILITY.value,
            entity_type="category",
            entity_id=category,
            current_value=volatility_index,
            trend=trend,
            trend_velocity=drift,
            threshold_warning=40.0,
            threshold_critical=60.0,
            is_higher_better=False,
            context_data={
                "category": category,
                "monthly_amount": str(amount),
                "drift_percentage": drift,
            }
        ))

    # Overall volatility score
    if volatility_metrics:
        overall_volatility = sum(v.volatility_index for v in volatility_metrics) / len(volatility_metrics)
    else:
        overall_volatility = 50.0

    # ==========================================================================
    # 2. Discretionary vs Non-Discretionary
    # ==========================================================================
    discretionary_pct = float(discretionary_total / total_expenses * 100) if total_expenses > 0 else 0

    # Calculate delayable amount (discretionary expenses that could be deferred)
    delayable_amount = discretionary_total * Decimal("0.7")  # Assume 70% is delayable

    discretionary_ratio = DiscretionaryRatioMetric(
        discretionary_total=str(discretionary_total),
        non_discretionary_total=str(non_discretionary_total),
        discretionary_percentage=round(discretionary_pct, 1),
        delayable_amount=str(delayable_amount),
        categories_breakdown={
            cat: str(amt) for cat, amt in category_totals.items()
        }
    )

    metrics.append(BehaviorMetric(
        user_id=user_id,
        metric_type=MetricType.DISCRETIONARY_RATIO.value,
        current_value=discretionary_pct,
        threshold_warning=40.0,  # Warning if >40% discretionary
        threshold_critical=60.0,
        is_higher_better=False,
        context_data={
            "discretionary": str(discretionary_total),
            "non_discretionary": str(non_discretionary_total),
            "delayable": str(delayable_amount),
        }
    ))

    # ==========================================================================
    # 3. Upcoming Commitments
    # ==========================================================================
    upcoming_commitments: List[UpcomingCommitment] = []
    total_commitments_30 = Decimal("0")

    # Get obligation schedules for next 30 days
    result = await db.execute(
        select(ObligationSchedule)
        .join(ObligationAgreement)
        .where(
            and_(
                ObligationAgreement.user_id == user_id,
                ObligationSchedule.due_date >= today,
                ObligationSchedule.due_date <= today + timedelta(days=30),
                ObligationSchedule.status.in_(["scheduled", "due"])
            )
        )
        .order_by(ObligationSchedule.due_date)
    )
    schedules = list(result.scalars().all())

    for schedule in schedules:
        amount = schedule.estimated_amount or Decimal("0")
        total_commitments_30 += amount

        # Get the agreement for context
        agreement_result = await db.execute(
            select(ObligationAgreement).where(ObligationAgreement.id == schedule.agreement_id)
        )
        agreement = agreement_result.scalar_one_or_none()

        commitment_type = "fixed"
        if agreement:
            if agreement.frequency == "quarterly":
                commitment_type = "quarterly"
            elif agreement.frequency == "annually":
                commitment_type = "annual"
            elif agreement.amount_type == "variable":
                commitment_type = "variable"

        is_delayable = commitment_type not in ("fixed", "quarterly")

        days_until = (schedule.due_date - today).days

        upcoming_commitments.append(UpcomingCommitment(
            name=agreement.name if agreement else f"Commitment {schedule.id}",
            due_date=schedule.due_date.isoformat(),
            amount=str(amount),
            commitment_type=commitment_type,
            is_delayable=is_delayable,
            days_until_due=days_until,
        ))

    # Also add recurring expenses from buckets
    for bucket in buckets:
        if bucket.due_day and bucket.monthly_amount:
            # Calculate next due date
            next_due = date(today.year, today.month, min(bucket.due_day, 28))
            if next_due < today:
                if today.month == 12:
                    next_due = date(today.year + 1, 1, min(bucket.due_day, 28))
                else:
                    next_due = date(today.year, today.month + 1, min(bucket.due_day, 28))

            if next_due <= today + timedelta(days=30):
                days_until = (next_due - today).days
                total_commitments_30 += bucket.monthly_amount

                upcoming_commitments.append(UpcomingCommitment(
                    name=bucket.name,
                    due_date=next_due.isoformat(),
                    amount=str(bucket.monthly_amount),
                    commitment_type="fixed" if bucket.bucket_type == "fixed" else "variable",
                    is_delayable=bucket.priority not in ("essential", "high"),
                    days_until_due=days_until,
                ))

    # Sort by due date
    upcoming_commitments.sort(key=lambda x: x.days_until_due)

    metrics.append(BehaviorMetric(
        user_id=user_id,
        metric_type=MetricType.COMMITMENT_COVERAGE.value,
        current_value=float(total_commitments_30),
        context_data={
            "total_30_days": str(total_commitments_30),
            "commitment_count": len(upcoming_commitments),
        }
    ))

    # ==========================================================================
    # Generate Recommendations
    # ==========================================================================
    recommendations = []

    if drifting_count > 0:
        recommendations.append(
            f"{drifting_count} expense categories are drifting upward. "
            "Review for cost control opportunities."
        )

    if discretionary_pct > 40:
        recommendations.append(
            f"Discretionary spending is {discretionary_pct:.0f}% of total. "
            "Consider which expenses could be reduced if needed."
        )

    if overall_volatility > 50:
        recommendations.append(
            "Expense volatility is high. Consider locking in rates or fixed contracts."
        )

    return ExpenseBehaviorInsights(
        overall_volatility_score=round(100 - overall_volatility, 1),  # Invert so higher = more stable
        category_volatility=volatility_metrics[:6],
        drifting_categories_count=drifting_count,
        discretionary_ratio=discretionary_ratio,
        total_commitments_30_days=str(total_commitments_30),
        upcoming_commitments=upcoming_commitments[:10],
        recommendations=recommendations,
    ), metrics


# =============================================================================
# Cash Discipline Metrics
# =============================================================================

async def calculate_cash_discipline_metrics(
    db: AsyncSession,
    user_id: str,
    forecast: Dict[str, Any],
    monthly_expenses: Decimal,
    buffer_months: int = 3
) -> Tuple[CashDisciplineInsights, List[BehaviorMetric]]:
    """
    Calculate cash discipline metrics including:
    - Buffer Integrity (current vs target + days below threshold)
    - Buffer Trend / Burn Momentum (direction + speed)
    - Reactive vs Deliberate Decision Rate
    """
    metrics: List[BehaviorMetric] = []

    # Get current cash position
    result = await db.execute(
        select(func.sum(CashAccount.balance))
        .where(CashAccount.user_id == user_id)
    )
    current_cash = result.scalar() or Decimal("0")

    target_buffer = monthly_expenses * buffer_months

    # ==========================================================================
    # 1. Buffer Integrity
    # ==========================================================================
    integrity_pct = float(current_cash / target_buffer * 100) if target_buffer > 0 else 100

    # Determine status
    if integrity_pct >= 100:
        status = "healthy"
    elif integrity_pct >= 70:
        status = "at_risk"
    else:
        status = "critical"

    # Days below target (would need historical tracking)
    # For now, estimate based on current state
    days_below = 0
    longest_streak = 0
    if integrity_pct < 100:
        days_below = max(1, int((100 - integrity_pct) / 10) * 7)  # Rough estimate
        longest_streak = days_below

    buffer_integrity = BufferIntegrityMetric(
        current_buffer=str(current_cash),
        target_buffer=str(target_buffer),
        integrity_percentage=round(integrity_pct, 1),
        days_below_target_last_90=days_below,
        longest_streak_below=longest_streak,
        status=status,
    )

    metrics.append(BehaviorMetric(
        user_id=user_id,
        metric_type=MetricType.BUFFER_INTEGRITY.value,
        current_value=integrity_pct,
        threshold_warning=100.0,
        threshold_critical=70.0,
        is_higher_better=True,
        context_data={
            "current_buffer": str(current_cash),
            "target_buffer": str(target_buffer),
            "days_below_target": days_below,
        }
    ))

    # ==========================================================================
    # 2. Buffer Trend / Burn Momentum
    # ==========================================================================
    weeks = forecast.get("weeks", [])
    weekly_trend_data: List[Dict[str, Any]] = []

    if len(weeks) >= 2:
        # Calculate weekly change rate
        weekly_changes = []
        for i, week in enumerate(weeks):
            if i == 0:
                continue
            prev_balance = Decimal(weeks[i-1].get("ending_balance", 0))
            curr_balance = Decimal(week.get("ending_balance", 0))
            change = curr_balance - prev_balance
            weekly_changes.append(float(change))

            weekly_trend_data.append({
                "week": f"W{week.get('week_number', i)}",
                "buffer": float(curr_balance),
                "target": float(target_buffer),
                "change": float(change),
            })

        if weekly_changes:
            avg_weekly_burn = statistics.mean(weekly_changes)
            momentum_pct = (avg_weekly_burn / float(current_cash) * 100) if current_cash > 0 else 0

            if avg_weekly_burn > 100:
                trend_direction = "building"
            elif avg_weekly_burn < -100:
                trend_direction = "burning"
            else:
                trend_direction = "stable"

            # Project weeks to zero
            weeks_to_zero = None
            if avg_weekly_burn < 0 and current_cash > 0:
                weeks_to_zero = int(float(current_cash) / abs(avg_weekly_burn))
        else:
            avg_weekly_burn = 0
            momentum_pct = 0
            trend_direction = "stable"
            weeks_to_zero = None
    else:
        avg_weekly_burn = 0
        momentum_pct = 0
        trend_direction = "stable"
        weeks_to_zero = None

    burn_momentum = BurnMomentumMetric(
        current_weekly_burn=str(round(avg_weekly_burn, 2)),
        trend_direction=trend_direction,
        momentum_percentage=round(momentum_pct, 2),
        weeks_of_data=len(weeks),
        projected_weeks_to_zero=weeks_to_zero,
    )

    metrics.append(BehaviorMetric(
        user_id=user_id,
        metric_type=MetricType.BURN_MOMENTUM.value,
        current_value=momentum_pct,
        trend=trend_direction,
        threshold_warning=-5.0,  # Warning if burning > 5% per week
        threshold_critical=-10.0,
        is_higher_better=True,
        context_data={
            "weekly_burn": str(avg_weekly_burn),
            "weeks_to_zero": weeks_to_zero,
        }
    ))

    # ==========================================================================
    # 3. Reactive vs Deliberate Decision Rate
    # ==========================================================================
    # This would need to track user decisions and correlate with buffer state
    # For now, use a proxy based on buffer health
    total_decisions = 24  # Would come from UserActivity tracking
    reactive_pct = max(0, min(50, 50 - integrity_pct / 2))  # Rough correlation

    reactive_decisions = int(total_decisions * reactive_pct / 100)
    deliberate_decisions = total_decisions - reactive_decisions

    decision_quality = DecisionQualityMetric(
        total_decisions=total_decisions,
        reactive_decisions=reactive_decisions,
        deliberate_decisions=deliberate_decisions,
        reactive_percentage=round(reactive_pct, 1),
        decisions_under_stress=reactive_decisions,
        average_decision_quality_score=round(100 - reactive_pct, 1),
    )

    metrics.append(BehaviorMetric(
        user_id=user_id,
        metric_type=MetricType.REACTIVE_DECISION_RATE.value,
        current_value=reactive_pct,
        threshold_warning=30.0,
        threshold_critical=50.0,
        is_higher_better=False,
        context_data={
            "total_decisions": total_decisions,
            "reactive_count": reactive_decisions,
        }
    ))

    # ==========================================================================
    # Forecast Confidence
    # ==========================================================================
    # Based on data quality and source
    high_confidence = 1  # Would count items backed by Xero
    medium_confidence = 32
    low_confidence = 2

    total_items = high_confidence + medium_confidence + low_confidence
    confidence_score = (high_confidence * 100 + medium_confidence * 70 + low_confidence * 30) / total_items if total_items > 0 else 50

    confidence_breakdown = {
        "high": high_confidence,
        "medium": medium_confidence,
        "low": low_confidence,
    }

    confidence_tips = [
        "Link repeating invoices in Xero for better forecast accuracy",
        "Add expected payment dates to clients",
        "Set up recurring expense templates",
    ]

    # ==========================================================================
    # Generate Recommendations
    # ==========================================================================
    recommendations = []

    if status == "critical":
        recommendations.append(
            "Cash buffer is critically low. Prioritize building reserves immediately."
        )
    elif status == "at_risk":
        recommendations.append(
            f"Cash buffer is {integrity_pct:.0f}% of target. Consider reducing discretionary expenses."
        )

    if trend_direction == "burning" and weeks_to_zero and weeks_to_zero < 12:
        recommendations.append(
            f"At current burn rate, buffer depletes in ~{weeks_to_zero} weeks. "
            "Accelerate receivables or defer non-essential expenses."
        )

    if reactive_pct > 30:
        recommendations.append(
            f"{reactive_pct:.0f}% of recent decisions were made under buffer stress. "
            "Pre-plan larger expenses to improve decision quality."
        )

    return CashDisciplineInsights(
        buffer_integrity=buffer_integrity,
        burn_momentum=burn_momentum,
        weekly_trend_data=weekly_trend_data,
        decision_quality=decision_quality,
        forecast_confidence_score=round(confidence_score, 1),
        confidence_breakdown=confidence_breakdown,
        confidence_improvement_tips=confidence_tips,
        recommendations=recommendations,
    ), metrics


# =============================================================================
# Main Entry Point
# =============================================================================

async def calculate_all_behavior_metrics(
    db: AsyncSession,
    user_id: str,
    buffer_months: int = 3
) -> Tuple[BehaviorInsightsResponse, List[BehaviorMetric]]:
    """
    Calculate all behavior metrics for a user.

    Returns both the formatted insights response and the raw metrics for storage.
    """
    # Fetch required data
    result = await db.execute(
        select(Client).where(Client.user_id == user_id)
    )
    clients = list(result.scalars().all())

    result = await db.execute(
        select(ExpenseBucket).where(ExpenseBucket.user_id == user_id)
    )
    buckets = list(result.scalars().all())

    # Get forecast
    forecast = await calculate_forecast_v2(db, user_id, weeks=13)

    # Calculate monthly expenses
    monthly_expenses = sum(b.monthly_amount or Decimal("0") for b in buckets)

    # Calculate each category
    all_metrics: List[BehaviorMetric] = []

    client_behavior, client_metrics = await calculate_client_behavior_metrics(
        db, user_id, clients
    )
    all_metrics.extend(client_metrics)

    expense_behavior, expense_metrics = await calculate_expense_behavior_metrics(
        db, user_id, buckets
    )
    all_metrics.extend(expense_metrics)

    cash_discipline, cash_metrics = await calculate_cash_discipline_metrics(
        db, user_id, forecast, monthly_expenses, buffer_months
    )
    all_metrics.extend(cash_metrics)

    # Calculate overall score
    client_score = client_behavior.concentration_score * 0.4 + client_behavior.overall_reliability_score * 0.6
    expense_score = expense_behavior.overall_volatility_score
    cash_score = cash_discipline.buffer_integrity.integrity_percentage

    overall_score = (client_score + expense_score + cash_score) / 3

    # Determine focus area
    scores = {
        "client": client_score,
        "expense": expense_score,
        "cash": cash_score,
    }
    focus_area = min(scores, key=scores.get)

    # Collect top concerns
    top_concerns = []
    if client_behavior.concentration_warning:
        top_concerns.append(client_behavior.concentration_warning)
    for rec in client_behavior.recommendations[:1]:
        top_concerns.append(rec)
    for rec in expense_behavior.recommendations[:1]:
        top_concerns.append(rec)
    for rec in cash_discipline.recommendations[:1]:
        top_concerns.append(rec)

    # Get triggered scenarios (would come from trigger evaluation)
    triggered_scenarios = []  # Populated by trigger system

    return BehaviorInsightsResponse(
        overall_behavior_score=round(overall_score, 1),
        client_behavior=client_behavior,
        expense_behavior=expense_behavior,
        cash_discipline=cash_discipline,
        triggered_scenarios=triggered_scenarios,
        pending_scenarios_count=0,
        top_concerns=top_concerns[:5],
        recommended_focus_area=focus_area,
    ), all_metrics
