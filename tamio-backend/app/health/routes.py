"""
Health Metrics Routes - Financial Wellness Dashboard

API endpoints for the Health page showing financial wellness metrics.

Metrics:
- Runway: Weeks of operation remaining at current burn rate
- Liquidity: Working capital ratio = (Cash + 30d AR) / (30d Liabilities)
- Cash Velocity: Cash conversion cycle in days = DSO - DPO
"""

from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from typing import List, Tuple
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.data.users.models import User
from app.data.balances.models import CashAccount
from app.data.clients.models import Client
from app.data.obligations.models import ObligationAgreement, ObligationSchedule, PaymentEvent
from app.data.user_config.routes import get_or_create_config
from app.detection.models import DetectionAlert
from app.forecast.engine_v2 import calculate_forecast_v2
from app.alerts_actions.routes import _alert_to_risk
from app.alerts_actions.schemas import RiskResponse

from .schemas import (
    HealthMetricsResponse,
    HealthRingData,
    ObligationsHealthData,
    ReceivablesHealthData,
)

router = APIRouter(tags=["health"])


def _format_compact_amount(amount: float) -> str:
    """Format amount in compact form (e.g., $487K, $1.2M)."""
    abs_amount = abs(amount)
    if abs_amount >= 1_000_000:
        return f"${abs_amount / 1_000_000:.1f}M".replace(".0M", "M")
    elif abs_amount >= 1_000:
        return f"${int(abs_amount / 1_000)}K"
    else:
        return f"${int(abs_amount)}"


def _get_runway_status(weeks: float) -> Tuple[str, str, float]:
    """
    Get runway status, sublabel, and percentage based on weeks.

    Benchmark: 15 weeks = 100%
    Thresholds: ≥12w good, 6-11w warning, <6w critical
    """
    if weeks >= 12:
        status = "good"
        sublabel = "Healthy • Strong runway"
    elif weeks >= 6:
        status = "warning"
        sublabel = "Watch • Below target"
    else:
        status = "critical"
        sublabel = "Urgent • Low runway"

    # 15 weeks = 100% (optimal benchmark)
    percentage = min((weeks / 15) * 100, 100)
    return status, sublabel, percentage


def _get_liquidity_status(ratio: float) -> Tuple[str, str, float]:
    """
    Get liquidity status, sublabel, and percentage based on working capital ratio.

    Formula: (Cash + 30d AR) / (30d Liabilities)
    Benchmark: 2.0 = 100%
    Thresholds: ≥1.5 good, 1.0-1.49 warning, <1.0 critical
    """
    if ratio >= 1.5:
        status = "good"
        sublabel = "Strong • Healthy liquidity"
    elif ratio >= 1.0:
        status = "warning"
        sublabel = "Watch • Moderate liquidity"
    else:
        status = "critical"
        sublabel = "Urgent • Liquidity stress"

    # 2.0 ratio = 100% (optimal benchmark)
    percentage = min((ratio / 2.0) * 100, 100)
    return status, sublabel, percentage


def _get_cash_velocity_status(days: float) -> Tuple[str, str, float]:
    """
    Get cash velocity status, sublabel, and percentage based on days.

    Formula: DSO - DPO (cash conversion cycle)
    Benchmark: 0 days = 100%, 90 days = 0% (inverse relationship)
    Thresholds: ≤30d good, 31-60d warning, >60d critical
    """
    if days <= 30:
        status = "good"
        sublabel = "Efficient • Fast conversion"
    elif days <= 60:
        status = "warning"
        sublabel = "Watch • Slow conversion"
    else:
        status = "critical"
        sublabel = "Urgent • Very slow"

    # Inverse: 0 days = 100%, 90 days = 0%
    percentage = max(100 - (days / 90) * 100, 0)
    return status, sublabel, percentage


# =============================================================================
# Data Query Helpers for Liquidity and Cash Velocity
# =============================================================================


async def _calculate_30day_ar(db: AsyncSession, user_id: str) -> Decimal:
    """
    Calculate 30-day Accounts Receivable from outstanding invoices.

    Queries all active clients and sums outstanding invoices expected within 30 days.
    """
    result = await db.execute(
        select(Client)
        .where(Client.user_id == user_id)
        .where(Client.status == "active")
    )
    clients = result.scalars().all()

    today = date.today()
    thirty_days_out = today + timedelta(days=30)
    total_ar = Decimal("0")

    for client in clients:
        config = client.billing_config or {}
        outstanding = config.get("outstanding_invoices", [])
        for invoice in outstanding:
            expected_date_str = invoice.get("expected_date")
            if expected_date_str:
                try:
                    expected_date = date.fromisoformat(expected_date_str)
                    # Include if expected within 30 days
                    if today <= expected_date <= thirty_days_out:
                        total_ar += Decimal(str(invoice.get("amount", 0)))
                except (ValueError, TypeError):
                    pass

    return total_ar


async def _calculate_30day_liabilities(db: AsyncSession, user_id: str) -> Decimal:
    """
    Calculate 30-day liabilities from obligation schedules.

    Queries all scheduled/due obligations with due dates in the next 30 days.
    """
    today = date.today()
    thirty_days_out = today + timedelta(days=30)

    result = await db.execute(
        select(func.sum(ObligationSchedule.estimated_amount))
        .join(ObligationAgreement)
        .where(
            and_(
                ObligationAgreement.user_id == user_id,
                ObligationSchedule.due_date >= today,
                ObligationSchedule.due_date <= thirty_days_out,
                ObligationSchedule.status.in_(["scheduled", "due"]),
            )
        )
    )
    return result.scalar() or Decimal("0")


async def _calculate_cash_velocity_days(db: AsyncSession, user_id: str) -> float:
    """
    Calculate cash conversion cycle: DSO - DPO (simplified without DII).

    DSO (Days Sales Outstanding): Weighted average of client payment delays
    DPO (Days Payable Outstanding): Average days from due date to payment

    Returns the cash conversion cycle in days (minimum 0).
    """
    # Calculate weighted average DSO from clients
    result = await db.execute(
        select(Client)
        .where(Client.user_id == user_id)
        .where(Client.status == "active")
    )
    clients = result.scalars().all()

    total_dso_weighted = 0.0
    total_weight = 0.0
    for client in clients:
        delay = client.avg_payment_delay_days or 0
        config = client.billing_config or {}
        # Use monthly billing amount as weight
        amount = float(config.get("amount", 0))
        if amount > 0:
            total_dso_weighted += delay * amount
            total_weight += amount

    # Default DSO of 30 days if no client data
    avg_dso = total_dso_weighted / total_weight if total_weight > 0 else 30.0

    # Calculate average DPO from payment history (last 90 days)
    ninety_days_ago = date.today() - timedelta(days=90)
    payments_result = await db.execute(
        select(PaymentEvent, ObligationSchedule)
        .outerjoin(ObligationSchedule, PaymentEvent.schedule_id == ObligationSchedule.id)
        .where(
            and_(
                PaymentEvent.user_id == user_id,
                PaymentEvent.payment_date >= ninety_days_ago,
                PaymentEvent.status == "completed",
            )
        )
    )
    payment_rows = payments_result.all()

    total_dpo_days = 0.0
    payment_count = 0
    for payment, schedule in payment_rows:
        if schedule and schedule.due_date and payment.payment_date:
            # Days difference: positive = paid late, negative = paid early
            days_diff = (payment.payment_date - schedule.due_date).days
            # DPO represents how long we take to pay (use absolute value for calculation)
            total_dpo_days += max(0, days_diff)
            payment_count += 1

    # Default DPO of 0 if no payment history (assume on-time payments)
    avg_dpo = total_dpo_days / payment_count if payment_count > 0 else 0.0

    # Cash Velocity = DSO - DPO
    # Higher DSO = slower collection = worse
    # Higher DPO = slower payment to suppliers = better for our cash
    cash_velocity_days = avg_dso - avg_dpo

    return max(0, cash_velocity_days)


# =============================================================================
# Obligations & Receivables Health Calculations
# =============================================================================


async def _calculate_14day_ar(db: AsyncSession, user_id: str) -> Decimal:
    """
    Calculate expected AR within 14 days from outstanding invoices.
    """
    result = await db.execute(
        select(Client)
        .where(Client.user_id == user_id)
        .where(Client.status == "active")
    )
    clients = result.scalars().all()

    today = date.today()
    fourteen_days_out = today + timedelta(days=14)
    total_ar = Decimal("0")

    for client in clients:
        config = client.billing_config or {}
        outstanding = config.get("outstanding_invoices", [])
        for invoice in outstanding:
            expected_date_str = invoice.get("expected_date") or invoice.get("due_date")
            if expected_date_str:
                try:
                    expected_date = date.fromisoformat(expected_date_str)
                    if today <= expected_date <= fourteen_days_out:
                        total_ar += Decimal(str(invoice.get("amount", 0)))
                except (ValueError, TypeError):
                    pass

    return total_ar


def _get_obligation_type_label(obligation_type: str) -> str:
    """Map obligation_type to human-readable label."""
    labels = {
        "payroll": "Payroll",
        "vendor_bill": "Bills/AP",
        "subscription": "Subscription",
        "lease": "Rent",
        "loan_payment": "Loan Payment",
        "tax_obligation": "Tax",
        "contractor": "Contractor",
        "other": "Payment",
    }
    return labels.get(obligation_type, "Payment")


async def _calculate_obligations_health(
    db: AsyncSession,
    user_id: str,
    current_cash: float
) -> ObligationsHealthData:
    """
    Calculate obligations health for 14-day window.

    Status Logic:
    - COVERED: buffer >= 20% after covering all obligations
    - TIGHT: 0% < buffer < 20%
    - AT_RISK: buffer < 0% (cannot cover all obligations)
    """
    today = date.today()
    fourteen_days_out = today + timedelta(days=14)

    # 1. Get obligations due in next 14 days with details
    result = await db.execute(
        select(ObligationSchedule, ObligationAgreement)
        .join(ObligationAgreement)
        .where(
            and_(
                ObligationAgreement.user_id == user_id,
                ObligationSchedule.due_date >= today,
                ObligationSchedule.due_date <= fourteen_days_out,
                ObligationSchedule.status.in_(["scheduled", "due"]),
            )
        )
        .order_by(ObligationSchedule.due_date.asc())
    )
    obligations = result.all()

    # 2. Calculate expected AR within 14 days
    ar_14d = await _calculate_14day_ar(db, user_id)

    # 3. Calculate totals
    total_obligations = sum(float(sched.estimated_amount or 0) for sched, _ in obligations)
    available_funds = current_cash + float(ar_14d)

    # 4. Calculate buffer percentage
    if total_obligations > 0:
        buffer_pct = ((available_funds - total_obligations) / total_obligations) * 100
    else:
        buffer_pct = 100.0  # No obligations = fully covered

    # 5. Determine status
    if buffer_pct >= 20:
        status = "covered"
    elif buffer_pct > 0:
        status = "tight"
    else:
        status = "at_risk"

    # 6. Count covered obligations (simulate paying in order)
    remaining_funds = available_funds
    covered_count = 0
    for sched, agreement in obligations:
        obligation_amount = float(sched.estimated_amount or 0)
        if remaining_funds >= obligation_amount:
            remaining_funds -= obligation_amount
            covered_count += 1
        else:
            break

    # 7. Get next obligation details
    next_name = None
    next_amount = None
    next_amount_formatted = None
    next_days = None

    if obligations:
        next_sched, next_agreement = obligations[0]
        next_name = next_agreement.vendor_name or _get_obligation_type_label(
            next_agreement.obligation_type or "other"
        )
        next_amount = float(next_sched.estimated_amount or 0)
        next_amount_formatted = _format_compact_amount(next_amount)
        next_days = (next_sched.due_date - today).days

    return ObligationsHealthData(
        status=status,
        covered_count=covered_count,
        total_count=len(obligations),
        next_obligation_name=next_name,
        next_obligation_amount=next_amount,
        next_obligation_amount_formatted=next_amount_formatted,
        next_obligation_days=next_days,
        buffer_percentage=round(buffer_pct, 1),
        total_obligations=total_obligations,
        available_funds=available_funds,
    )


async def _calculate_receivables_health(
    db: AsyncSession,
    user_id: str
) -> ReceivablesHealthData:
    """
    Calculate receivables health from outstanding invoices.

    Status Logic:
    - HEALTHY: overdue % < 10% AND avg days late < 7
    - URGENT: overdue % > 30% OR avg days late > 30
    - WATCH: everything else
    """
    today = date.today()

    # Query all active clients with their outstanding invoices
    result = await db.execute(
        select(Client)
        .where(Client.user_id == user_id)
        .where(Client.status == "active")
    )
    clients = result.scalars().all()

    # Aggregate invoice data
    total_outstanding_amount = Decimal("0")
    total_outstanding_count = 0
    overdue_amount = Decimal("0")
    overdue_count = 0
    total_days_late = 0

    for client in clients:
        config = client.billing_config or {}

        # Process outstanding_invoices (from Xero sync)
        outstanding = config.get("outstanding_invoices", [])
        for invoice in outstanding:
            amount = Decimal(str(invoice.get("amount", 0)))
            total_outstanding_amount += amount
            total_outstanding_count += 1

            # Check if overdue - use due_date first, fall back to expected_date
            due_date_str = invoice.get("due_date") or invoice.get("expected_date")
            if due_date_str:
                try:
                    due_date = date.fromisoformat(due_date_str)
                    if due_date < today:
                        # Invoice is overdue
                        overdue_amount += amount
                        overdue_count += 1
                        days_late = (today - due_date).days
                        total_days_late += days_late
                except (ValueError, TypeError):
                    pass

        # Process milestones (from manual entry / seed data)
        # "completed" status = work delivered, awaiting payment (outstanding)
        # "paid" = already paid, "pending" = work not yet delivered
        milestones = config.get("milestones", [])
        for milestone in milestones:
            status = milestone.get("status", "")
            if status != "completed":
                continue  # Only count completed (delivered but unpaid) milestones

            amount = Decimal(str(milestone.get("amount", 0)))
            total_outstanding_amount += amount
            total_outstanding_count += 1

            # Check if overdue based on expected_date
            due_date_str = milestone.get("expected_date")
            if due_date_str:
                try:
                    due_date = date.fromisoformat(due_date_str)
                    if due_date < today:
                        # Milestone payment is overdue
                        overdue_amount += amount
                        overdue_count += 1
                        days_late = (today - due_date).days
                        total_days_late += days_late
                except (ValueError, TypeError):
                    pass

    # Calculate metrics
    overdue_pct = (
        float(overdue_amount) / float(total_outstanding_amount) * 100
        if total_outstanding_amount > 0 else 0
    )
    avg_days_late = total_days_late // overdue_count if overdue_count > 0 else 0

    # Determine status
    if overdue_pct > 30 or avg_days_late > 30:
        status = "urgent"
    elif overdue_pct < 10 and avg_days_late < 7:
        status = "healthy"
    else:
        status = "watch"

    # Format overdue amount
    overdue_formatted = f"{_format_compact_amount(float(overdue_amount))} overdue"

    return ReceivablesHealthData(
        status=status,
        overdue_amount=float(overdue_amount),
        overdue_amount_formatted=overdue_formatted,
        overdue_count=overdue_count,
        total_outstanding_count=total_outstanding_count,
        avg_days_late=avg_days_late,
        overdue_percentage=round(overdue_pct, 1),
        total_outstanding_amount=float(total_outstanding_amount),
    )


@router.get("/metrics", response_model=HealthMetricsResponse)
async def get_health_metrics(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all health metrics for the financial wellness dashboard.

    Returns:
        - Runway ring: Weeks of cash remaining (survival question)
        - Liquidity ring: Working capital ratio (immediate health question)
        - Cash Velocity ring: Cash conversion cycle in days (efficiency question)
        - Cash Health: Current position and trend
        - Burn Rate: Weekly average and trend
        - Critical Alerts: Top 3 most urgent alerts
    """
    try:
        # Get user configuration
        config = await get_or_create_config(db, user.id)

        # Get current cash position
        result = await db.execute(
            select(func.sum(CashAccount.balance))
            .where(CashAccount.user_id == user.id)
        )
        current_cash = float(result.scalar() or 0)

        # Get forecast data for calculations
        forecast = await calculate_forecast_v2(db, user.id, weeks=13)

        # =====================================================================
        # RUNWAY RING - "How long can we last?"
        # Weeks of operation remaining at current burn rate
        # Benchmark: 15 weeks = 100%
        # =====================================================================
        runway_weeks = float(forecast["summary"]["runway_weeks"])
        runway_status, runway_sublabel, runway_percentage = _get_runway_status(runway_weeks)

        runway = HealthRingData(
            value=runway_weeks,
            percentage=runway_percentage,
            status=runway_status,
            label=f"{int(runway_weeks)}w",
            sublabel=runway_sublabel,
        )

        # =====================================================================
        # LIQUIDITY RING - "Can we meet our obligations?"
        # Working capital ratio = (Cash + 30d AR) / (30d Liabilities)
        # Benchmark: 2.0 = 100%
        # =====================================================================
        # Calculate 30-day AR and liabilities
        ar_30d = await _calculate_30day_ar(db, user.id)
        liabilities_30d = await _calculate_30day_liabilities(db, user.id)

        # Fallback to forecast-based monthly obligations if no obligation data
        if float(liabilities_30d) == 0:
            total_cash_out = float(forecast["summary"]["total_cash_out"])
            weeks_in_forecast = len(forecast["weeks"])
            liabilities_30d = Decimal(str(
                (total_cash_out / weeks_in_forecast) * 4.33 if weeks_in_forecast > 0 else 0
            ))

        # Calculate working capital ratio
        current_assets = current_cash + float(ar_30d)
        current_liabilities = float(liabilities_30d) if float(liabilities_30d) > 0 else 1  # Avoid division by zero

        liquidity_ratio = current_assets / current_liabilities
        liquidity_status, liquidity_sublabel, liquidity_percentage = _get_liquidity_status(liquidity_ratio)

        liquidity = HealthRingData(
            value=round(liquidity_ratio, 1),
            percentage=liquidity_percentage,
            status=liquidity_status,
            label=f"{liquidity_ratio:.1f}",
            sublabel=liquidity_sublabel,
        )

        # =====================================================================
        # CASH VELOCITY RING - "How fast do we turn work into cash?"
        # Cash conversion cycle = DSO - DPO (days)
        # Benchmark: 0 days = 100%, 90 days = 0%
        # =====================================================================
        velocity_days = await _calculate_cash_velocity_days(db, user.id)
        velocity_status, velocity_sublabel, velocity_percentage = _get_cash_velocity_status(velocity_days)

        cash_velocity = HealthRingData(
            value=velocity_days,
            percentage=velocity_percentage,
            status=velocity_status,
            label=f"{int(velocity_days)}d",
            sublabel=velocity_sublabel,
        )

        # =====================================================================
        # OBLIGATIONS HEALTH MONITOR
        # Forward-looking: Can you cover upcoming payments?
        # =====================================================================
        obligations_health = await _calculate_obligations_health(db, user.id, current_cash)

        # =====================================================================
        # RECEIVABLES HEALTH MONITOR
        # Current state: Is money owed coming in on time?
        # =====================================================================
        receivables_health = await _calculate_receivables_health(db, user.id)

        # =====================================================================
        # CRITICAL ALERTS
        # =====================================================================
        # Get top 3 most critical active alerts
        alerts_result = await db.execute(
            select(DetectionAlert)
            .options(selectinload(DetectionAlert.prepared_actions))
            .where(DetectionAlert.user_id == user.id)
            .where(DetectionAlert.status.in_(["active", "acknowledged"]))
            .order_by(
                DetectionAlert.severity.asc(),  # 'emergency' < 'this_week' < 'upcoming'
                DetectionAlert.deadline.asc().nullslast(),
            )
            .limit(3)
        )
        alerts = alerts_result.scalars().all()

        # Transform alerts to RiskResponse
        critical_alerts: List[RiskResponse] = []
        for alert in alerts:
            risk = await _alert_to_risk(db, alert)
            critical_alerts.append(risk)

        # =====================================================================
        # BUILD RESPONSE
        # =====================================================================
        return HealthMetricsResponse(
            runway=runway,
            liquidity=liquidity,
            cash_velocity=cash_velocity,
            obligations_health=obligations_health,
            receivables_health=receivables_health,
            critical_alerts=critical_alerts,
            last_updated=datetime.now(timezone.utc),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating health metrics: {str(e)}")
