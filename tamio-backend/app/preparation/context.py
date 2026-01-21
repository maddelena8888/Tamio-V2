"""
Preparation Context Helpers - V4 Architecture

Helper functions for gathering context needed by preparation agents.
Each function queries related entities and returns structured context.
"""

from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.data.clients.models import Client
from app.data.expenses.models import ExpenseBucket
from app.data.obligations.models import (
    ObligationAgreement,
    ObligationSchedule,
    PaymentEvent,
)
from app.data.balances.models import CashAccount


async def get_client_context(db: AsyncSession, client_id: str) -> Dict[str, Any]:
    """
    Gather comprehensive context about a client.

    Returns:
        - Basic info (name, type, status)
        - Payment patterns (avg delay, behavior rating)
        - Relationship info (type, revenue %)
        - Historical data (payment history, recent invoices)
    """
    result = await db.execute(
        select(Client)
        .where(Client.id == client_id)
        .options(selectinload(Client.obligations))
    )
    client = result.scalar_one_or_none()

    if not client:
        return {"error": "Client not found", "client_id": client_id}

    # Get payment history from PaymentEvents
    payment_result = await db.execute(
        select(PaymentEvent)
        .join(ObligationAgreement)
        .where(ObligationAgreement.client_id == client_id)
        .where(PaymentEvent.payment_date >= date.today() - timedelta(days=365))
        .order_by(PaymentEvent.payment_date.desc())
        .limit(10)
    )
    recent_payments = payment_result.scalars().all()

    # Calculate payment behavior metrics
    on_time_count = 0
    late_count = 0
    total_variance = Decimal(0)

    for payment in recent_payments:
        if payment.variance_vs_expected is not None:
            total_variance += payment.variance_vs_expected
        # Would need to compare payment_date to schedule.due_date for late calculation

    # Get outstanding invoices
    outstanding_result = await db.execute(
        select(ObligationSchedule)
        .join(ObligationAgreement)
        .where(ObligationAgreement.client_id == client_id)
        .where(ObligationSchedule.status.in_(["scheduled", "due", "overdue"]))
        .order_by(ObligationSchedule.due_date)
    )
    outstanding = outstanding_result.scalars().all()

    total_outstanding = sum(float(s.estimated_amount) for s in outstanding)

    return {
        "client_id": client.id,
        "name": client.name,
        "client_type": client.client_type,
        "status": client.status,
        "currency": client.currency,
        # Relationship
        "relationship_type": client.relationship_type or "transactional",
        "revenue_percent": float(client.revenue_percent) if client.revenue_percent else 0,
        "risk_level": client.risk_level or "medium",
        # Payment behavior
        "payment_behavior": client.payment_behavior or "unknown",
        "avg_payment_delay_days": client.avg_payment_delay_days or 0,
        "churn_risk": client.churn_risk or "low",
        # Derived metrics
        "recent_payment_count": len(recent_payments),
        "total_outstanding": total_outstanding,
        "outstanding_invoice_count": len(outstanding),
        # For tone selection
        "suggested_tone": _get_suggested_tone(client),
        # Source info
        "source": client.source,
        "xero_contact_id": client.xero_contact_id,
    }


async def get_vendor_context(db: AsyncSession, expense_bucket_id: str) -> Dict[str, Any]:
    """
    Gather comprehensive context about a vendor (expense bucket).

    Returns:
        - Basic info (name, category, type)
        - Payment terms and flexibility
        - Criticality assessment
        - Delay history
    """
    result = await db.execute(
        select(ExpenseBucket)
        .where(ExpenseBucket.id == expense_bucket_id)
        .options(selectinload(ExpenseBucket.obligations))
    )
    bucket = result.scalar_one_or_none()

    if not bucket:
        return {"error": "Expense bucket not found", "bucket_id": expense_bucket_id}

    # Get recent payment history
    payment_result = await db.execute(
        select(PaymentEvent)
        .join(ObligationAgreement)
        .where(ObligationAgreement.expense_bucket_id == expense_bucket_id)
        .where(PaymentEvent.payment_date >= date.today() - timedelta(days=180))
        .order_by(PaymentEvent.payment_date.desc())
        .limit(6)
    )
    recent_payments = payment_result.scalars().all()

    # Analyze delay history
    delay_history = bucket.delay_history or []
    total_delays = len(delay_history)
    avg_delay_days = 0
    if delay_history:
        avg_delay_days = sum(d.get("days_delayed", 0) for d in delay_history) / len(delay_history)

    # Calculate can_delay score (0-1)
    can_delay_score = _calculate_delay_score(bucket)

    return {
        "bucket_id": bucket.id,
        "name": bucket.name,
        "category": bucket.category,
        "bucket_type": bucket.bucket_type,
        "monthly_amount": float(bucket.monthly_amount),
        "currency": bucket.currency,
        # Payment terms
        "payment_terms": bucket.payment_terms or "net_30",
        "payment_terms_days": bucket.payment_terms_days or 30,
        "due_day": bucket.due_day or 15,
        "frequency": bucket.frequency or "monthly",
        # Flexibility
        "flexibility_level": bucket.flexibility_level or "negotiable",
        "criticality": bucket.criticality or "important",
        "can_delay_score": can_delay_score,
        # History
        "delay_history_count": total_delays,
        "avg_delay_days": avg_delay_days,
        "recent_payment_count": len(recent_payments),
        # Priority
        "priority": bucket.priority,
        "is_stable": bucket.is_stable,
        # For payroll
        "employee_count": bucket.employee_count,
        # Source info
        "source": bucket.source,
        "xero_contact_id": bucket.xero_contact_id,
    }


async def get_cash_context(db: AsyncSession, user_id: str) -> Dict[str, Any]:
    """
    Gather comprehensive cash position context.

    Returns:
        - Current cash balances by account
        - Upcoming obligations (7, 14, 30 days)
        - Expected revenue
        - Runway calculation
    """
    today = date.today()

    # Get all cash accounts
    accounts_result = await db.execute(
        select(CashAccount)
        .where(CashAccount.user_id == user_id)
    )
    accounts = accounts_result.scalars().all()

    account_balances = [
        {
            "account_id": acc.id,
            "name": acc.account_name,
            "balance": float(acc.balance),
            "currency": acc.currency,
            "as_of_date": acc.as_of_date.isoformat() if acc.as_of_date else None,
        }
        for acc in accounts
    ]
    total_cash = sum(float(acc.balance) for acc in accounts)

    # Get upcoming obligations (expenses)
    async def get_obligations_in_period(start: date, end: date) -> float:
        result = await db.execute(
            select(func.sum(ObligationSchedule.estimated_amount))
            .join(ObligationAgreement)
            .where(ObligationAgreement.user_id == user_id)
            .where(ObligationAgreement.obligation_type != "revenue")
            .where(ObligationSchedule.due_date >= start)
            .where(ObligationSchedule.due_date <= end)
            .where(ObligationSchedule.status.in_(["scheduled", "due"]))
        )
        return float(result.scalar() or 0)

    # Get expected revenue
    async def get_revenue_in_period(start: date, end: date) -> float:
        result = await db.execute(
            select(func.sum(ObligationSchedule.estimated_amount))
            .join(ObligationAgreement)
            .where(ObligationAgreement.user_id == user_id)
            .where(ObligationAgreement.obligation_type == "revenue")
            .where(ObligationSchedule.due_date >= start)
            .where(ObligationSchedule.due_date <= end)
            .where(ObligationSchedule.status.in_(["scheduled", "due"]))
        )
        return float(result.scalar() or 0)

    obligations_7d = await get_obligations_in_period(today, today + timedelta(days=7))
    obligations_14d = await get_obligations_in_period(today, today + timedelta(days=14))
    obligations_30d = await get_obligations_in_period(today, today + timedelta(days=30))

    revenue_7d = await get_revenue_in_period(today, today + timedelta(days=7))
    revenue_14d = await get_revenue_in_period(today, today + timedelta(days=14))
    revenue_30d = await get_revenue_in_period(today, today + timedelta(days=30))

    # Calculate runway
    monthly_burn = obligations_30d
    monthly_revenue = revenue_30d
    net_burn = monthly_burn - monthly_revenue
    runway_months = total_cash / net_burn if net_burn > 0 else float('inf')

    return {
        "total_cash": total_cash,
        "account_count": len(accounts),
        "accounts": account_balances,
        # Obligations
        "obligations_7d": obligations_7d,
        "obligations_14d": obligations_14d,
        "obligations_30d": obligations_30d,
        # Revenue
        "revenue_7d": revenue_7d,
        "revenue_14d": revenue_14d,
        "revenue_30d": revenue_30d,
        # Net position
        "net_7d": total_cash + revenue_7d - obligations_7d,
        "net_14d": total_cash + revenue_14d - obligations_14d,
        "net_30d": total_cash + revenue_30d - obligations_30d,
        # Runway
        "monthly_burn": monthly_burn,
        "monthly_revenue": monthly_revenue,
        "net_burn": net_burn,
        "runway_months": runway_months if runway_months != float('inf') else None,
        "is_cash_flow_positive": net_burn <= 0,
    }


async def get_payroll_context(db: AsyncSession, user_id: str) -> Dict[str, Any]:
    """
    Gather payroll-specific context.

    Returns:
        - Next payroll date and amount
        - Cash position relative to payroll
        - Buffer status
    """
    today = date.today()

    # Find payroll expense buckets
    bucket_result = await db.execute(
        select(ExpenseBucket)
        .where(ExpenseBucket.user_id == user_id)
        .where(ExpenseBucket.category == "payroll")
    )
    payroll_buckets = bucket_result.scalars().all()

    if not payroll_buckets:
        return {
            "has_payroll": False,
            "message": "No payroll expense buckets configured",
        }

    # Get next payroll schedules
    schedule_result = await db.execute(
        select(ObligationSchedule)
        .join(ObligationAgreement)
        .join(ExpenseBucket, ObligationAgreement.expense_bucket_id == ExpenseBucket.id)
        .where(ObligationAgreement.user_id == user_id)
        .where(ExpenseBucket.category == "payroll")
        .where(ObligationSchedule.due_date >= today)
        .where(ObligationSchedule.status.in_(["scheduled", "due"]))
        .order_by(ObligationSchedule.due_date)
        .limit(3)
    )
    upcoming_payrolls = schedule_result.scalars().all()

    if not upcoming_payrolls:
        return {
            "has_payroll": True,
            "payroll_count": len(payroll_buckets),
            "next_payroll": None,
            "message": "No upcoming payroll schedules",
        }

    next_payroll = upcoming_payrolls[0]
    days_until_payroll = (next_payroll.due_date - today).days

    # Get current cash
    cash_context = await get_cash_context(db, user_id)
    total_cash = cash_context["total_cash"]

    # Get obligations before payroll
    obligations_result = await db.execute(
        select(func.sum(ObligationSchedule.estimated_amount))
        .join(ObligationAgreement)
        .where(ObligationAgreement.user_id == user_id)
        .where(ObligationSchedule.due_date >= today)
        .where(ObligationSchedule.due_date < next_payroll.due_date)
        .where(ObligationSchedule.status.in_(["scheduled", "due"]))
        .where(ObligationSchedule.id != next_payroll.id)
    )
    obligations_before = float(obligations_result.scalar() or 0)

    payroll_amount = float(next_payroll.estimated_amount)
    cash_after_obligations = total_cash - obligations_before
    cash_after_payroll = cash_after_obligations - payroll_amount
    buffer_10_pct = payroll_amount * 0.1

    return {
        "has_payroll": True,
        "payroll_count": len(payroll_buckets),
        "total_monthly_payroll": sum(float(b.monthly_amount) for b in payroll_buckets),
        "total_employees": sum(b.employee_count or 0 for b in payroll_buckets),
        # Next payroll
        "next_payroll": {
            "schedule_id": next_payroll.id,
            "due_date": next_payroll.due_date.isoformat(),
            "amount": payroll_amount,
            "days_until": days_until_payroll,
        },
        # Cash position
        "current_cash": total_cash,
        "obligations_before_payroll": obligations_before,
        "cash_after_obligations": cash_after_obligations,
        "cash_after_payroll": cash_after_payroll,
        # Buffer status
        "buffer_10_pct": buffer_10_pct,
        "buffer_status": "safe" if cash_after_payroll >= buffer_10_pct else (
            "at_risk" if cash_after_payroll >= 0 else "shortfall"
        ),
        "shortfall": max(0, buffer_10_pct - cash_after_payroll),
        # Upcoming
        "upcoming_payrolls": [
            {
                "schedule_id": p.id,
                "due_date": p.due_date.isoformat(),
                "amount": float(p.estimated_amount),
            }
            for p in upcoming_payrolls
        ],
    }


def _get_suggested_tone(client: Client) -> str:
    """
    Determine suggested communication tone based on client attributes.

    Returns: "soft", "professional", or "firm"
    """
    # Strategic clients get softer tone
    if client.relationship_type == "strategic":
        return "soft"

    # High revenue clients get softer tone
    if client.revenue_percent and float(client.revenue_percent) >= 15:
        return "soft"

    # Good payers get softer tone
    if client.payment_behavior == "on_time":
        return "soft"

    # Late payers get firmer tone
    if client.payment_behavior == "delayed":
        return "firm"
    if client.avg_payment_delay_days and client.avg_payment_delay_days > 14:
        return "firm"

    # High churn risk clients need careful handling
    if client.churn_risk == "high":
        return "professional"

    # Default
    return "professional"


def _calculate_delay_score(bucket: ExpenseBucket) -> float:
    """
    Calculate how safe it is to delay payment to this vendor.

    Returns: 0.0 (cannot delay) to 1.0 (can safely delay)
    """
    score = 0.5  # Base score

    # Flexibility level
    if bucket.flexibility_level == "can_delay":
        score += 0.3
    elif bucket.flexibility_level == "negotiable":
        score += 0.1
    elif bucket.flexibility_level == "cannot_delay":
        score -= 0.4

    # Criticality
    if bucket.criticality == "flexible":
        score += 0.2
    elif bucket.criticality == "important":
        score += 0.0
    elif bucket.criticality == "critical":
        score -= 0.3

    # Category-based adjustments
    if bucket.category == "payroll":
        score = 0.0  # Never delay payroll
    elif bucket.category == "rent":
        score -= 0.2

    # Payment terms give more room
    terms_days = bucket.payment_terms_days or 30
    if terms_days >= 60:
        score += 0.1
    elif terms_days <= 15:
        score -= 0.1

    # Past delays affect relationship
    delay_history = bucket.delay_history or []
    if len(delay_history) >= 3:
        score -= 0.2  # Too many past delays
    elif len(delay_history) == 0:
        score += 0.1  # Clean record

    return max(0.0, min(1.0, score))
