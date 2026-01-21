"""
Forecast Engine V2 - On-the-fly computation with confidence scoring.

This engine computes forecasts directly from clients and expense buckets,
eliminating the need for pre-generated cash_events. This ensures the
forecast is always aligned with the source data.

Key improvements over V1:
- Computes on-the-fly (no stale data)
- Includes confidence scoring based on integration status
- Single source of truth (clients/buckets tables)
- Ready for QuickBooks integration

V2.1 Update (Data Architecture Refactor):
- Added obligation-based computation path (USE_OBLIGATION_FOR_FORECAST feature flag)
- When enabled, computes forecasts from ObligationSchedules instead of Client/ExpenseBucket
- Maintains backward compatibility with legacy approach via feature flag
- Hybrid approach: CashEvents stored for audit, forecasts computed on-the-fly
"""
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.data.clients.models import Client
from app.data.expenses.models import ExpenseBucket
from app.data.balances.models import CashAccount
from app.data.obligations.models import ObligationAgreement, ObligationSchedule, PaymentEvent
from app.integrations.confidence import (
    ConfidenceLevel,
    ConfidenceScore,
    calculate_client_confidence,
    calculate_expense_confidence,
    calculate_forecast_confidence_summary,
    ForecastConfidenceSummary,
)
from app.config import settings


@dataclass
class ForecastEvent:
    """
    A single forecast event (computed, not stored).

    This replaces the stored CashEvent for forecast purposes.
    """
    id: str  # Synthetic ID: {source_type}_{source_id}_{date}
    date: date
    amount: Decimal
    direction: str  # "in" | "out"
    event_type: str  # "expected_revenue" | "expected_expense"
    category: str
    confidence: ConfidenceLevel
    confidence_reason: str
    source_id: str  # client_id or bucket_id
    source_name: str  # client name or bucket name
    source_type: str  # "client" | "expense"
    is_recurring: bool
    recurrence_pattern: Optional[str]


def _compute_client_events(
    client: Client,
    start_date: date,
    end_date: date,
    confidence_score: ConfidenceScore,
    scenario_context: Optional['ScenarioContext'] = None
) -> List[ForecastEvent]:
    """
    Compute forecast events from a client's billing configuration.

    This is a pure function - no database writes.
    Supports scenario modifications like payment delays and amount changes.
    """
    events = []
    config = client.billing_config or {}

    if client.status != "active":
        return events

    if client.client_type == "retainer":
        events = _compute_retainer_events(client, config, start_date, end_date, confidence_score)

    elif client.client_type == "project":
        events = _compute_project_events(client, config, start_date, end_date, confidence_score)

    elif client.client_type == "usage":
        events = _compute_usage_events(client, config, start_date, end_date, confidence_score)

    elif client.client_type == "mixed":
        if "retainer" in config:
            events.extend(_compute_retainer_events(client, config["retainer"], start_date, end_date, confidence_score))
        if "project" in config:
            events.extend(_compute_project_events(client, config["project"], start_date, end_date, confidence_score))
        if "usage" in config:
            events.extend(_compute_usage_events(client, config["usage"], start_date, end_date, confidence_score))

    # Process outstanding invoices (from Xero sync) for ALL client types
    # These are one-time payments that exist regardless of billing type
    if "outstanding_invoices" in config:
        events.extend(_compute_outstanding_invoice_events(client, config, start_date, end_date, confidence_score))

    # Apply scenario modifications if provided
    if scenario_context:
        events = _apply_scenario_to_client_events(events, client.id, scenario_context)

    return events


def _apply_scenario_to_client_events(
    events: List[ForecastEvent],
    client_id: str,
    scenario_context: 'ScenarioContext'
) -> List[ForecastEvent]:
    """Apply scenario modifications to client events (payment delays, amount changes)."""
    modified_events = []

    for event in events:
        # Apply payment delay if specified for this client
        if client_id in scenario_context.client_payment_delays:
            delay_days = scenario_context.client_payment_delays[client_id]
            # Only apply to events on/after effective date
            if scenario_context.effective_date is None or event.date >= scenario_context.effective_date:
                new_date = event.date + timedelta(days=delay_days)
                event = ForecastEvent(
                    id=event.id,
                    date=new_date,
                    amount=event.amount,
                    direction=event.direction,
                    event_type=event.event_type,
                    category=event.category,
                    confidence=ConfidenceLevel.MEDIUM,  # Reduced confidence for delayed payments
                    confidence_reason=f"Payment delayed by {delay_days} days (scenario)",
                    source_id=event.source_id,
                    source_name=event.source_name,
                    source_type=event.source_type,
                    is_recurring=event.is_recurring,
                    recurrence_pattern=event.recurrence_pattern
                )

        # Apply amount modification if specified for this client
        if client_id in scenario_context.client_amount_deltas:
            delta = scenario_context.client_amount_deltas[client_id]
            # Only apply to events on/after effective date
            if scenario_context.effective_date is None or event.date >= scenario_context.effective_date:
                new_amount = event.amount + delta
                if new_amount > 0:  # Don't create negative revenue events
                    event = ForecastEvent(
                        id=event.id,
                        date=event.date,
                        amount=new_amount,
                        direction=event.direction,
                        event_type=event.event_type,
                        category=event.category,
                        confidence=event.confidence,
                        confidence_reason=f"Amount modified by ${delta} (scenario)",
                        source_id=event.source_id,
                        source_name=event.source_name,
                        source_type=event.source_type,
                        is_recurring=event.is_recurring,
                        recurrence_pattern=event.recurrence_pattern
                    )

        modified_events.append(event)

    return modified_events


def _compute_retainer_events(
    client: Client,
    config: dict,
    start_date: date,
    end_date: date,
    confidence_score: ConfidenceScore
) -> List[ForecastEvent]:
    """Compute events for retainer clients."""
    events = []
    frequency = config.get("frequency", "monthly")
    amount = Decimal(str(config.get("amount", 0)))

    if amount <= 0:
        return events

    payment_terms = config.get("payment_terms", "net_30")
    # Support both invoice_day (schema) and day_of_month (frontend) field names
    # day_of_month takes priority as it's the field used by the frontend
    raw_invoice_day = config.get("day_of_month") or config.get("invoice_day")
    try:
        invoice_day = int(raw_invoice_day) if raw_invoice_day else None
    except (ValueError, TypeError):
        invoice_day = None

    # Legacy billing_day field (only used if invoice_day not set)
    billing_day = config.get("billing_day", "start_of_month")

    # Parse payment terms
    payment_delay_days = 30
    if isinstance(payment_terms, str) and "net_" in payment_terms:
        try:
            payment_delay_days = int(payment_terms.replace("net_", ""))
        except ValueError:
            pass
    elif isinstance(payment_terms, int):
        payment_delay_days = payment_terms

    current_date = start_date.replace(day=1)
    event_num = 0

    while current_date <= end_date:
        # Calculate billing date
        # Priority: invoice_day/day_of_month (explicit day) > billing_day (legacy)
        if invoice_day is not None and invoice_day > 0:
            try:
                billing_date = current_date.replace(day=invoice_day)
            except ValueError:
                # Day doesn't exist in month (e.g., Feb 30), use last day
                next_month = current_date + relativedelta(months=1)
                billing_date = next_month - timedelta(days=1)
        elif billing_day == "start_of_month":
            billing_date = current_date.replace(day=1)
        else:
            billing_date = current_date.replace(day=1)

        # Payment date = billing date + payment terms
        payment_date = billing_date + timedelta(days=payment_delay_days)

        if start_date <= payment_date <= end_date:
            event_num += 1
            events.append(ForecastEvent(
                id=f"client_{client.id}_{payment_date.isoformat()}_{event_num}",
                date=payment_date,
                amount=amount,
                direction="in",
                event_type="expected_revenue",
                category="retainer",
                confidence=confidence_score.level,
                confidence_reason=confidence_score.reason,
                source_id=client.id,
                source_name=client.name,
                source_type="client",
                is_recurring=True,
                recurrence_pattern=frequency
            ))

        # Move to next period
        if frequency == "monthly":
            current_date += relativedelta(months=1)
        elif frequency == "quarterly":
            current_date += relativedelta(months=3)
        elif frequency == "weekly":
            current_date += timedelta(weeks=1)
        elif frequency == "bi_weekly" or frequency == "bi-weekly":
            current_date += timedelta(weeks=2)
        else:
            current_date += relativedelta(months=1)

    return events


def _compute_project_events(
    client: Client,
    config: dict,
    start_date: date,
    end_date: date,
    confidence_score: ConfidenceScore
) -> List[ForecastEvent]:
    """Compute events for project clients."""
    events = []
    milestones = config.get("milestones", [])

    for i, milestone in enumerate(milestones):
        expected_date_str = milestone.get("expected_date")
        if not expected_date_str:
            continue

        try:
            milestone_date = date.fromisoformat(expected_date_str)
        except ValueError:
            continue

        amount = Decimal(str(milestone.get("amount", 0)))
        if amount <= 0:
            continue

        payment_terms = milestone.get("payment_terms", "net_14")
        payment_delay_days = 14
        if isinstance(payment_terms, str) and "net_" in payment_terms:
            try:
                payment_delay_days = int(payment_terms.replace("net_", ""))
            except ValueError:
                pass

        payment_date = milestone_date + timedelta(days=payment_delay_days)

        if start_date <= payment_date <= end_date:
            events.append(ForecastEvent(
                id=f"client_{client.id}_milestone_{i}_{payment_date.isoformat()}",
                date=payment_date,
                amount=amount,
                direction="in",
                event_type="expected_revenue",
                category="milestone_payment",
                confidence=confidence_score.level,
                confidence_reason=confidence_score.reason,
                source_id=client.id,
                source_name=client.name,
                source_type="client",
                is_recurring=False,
                recurrence_pattern=None
            ))

    return events


def _compute_outstanding_invoice_events(
    client: Client,
    config: dict,
    start_date: date,
    end_date: date,
    confidence_score: ConfidenceScore
) -> List[ForecastEvent]:
    """
    Compute events from outstanding invoices (synced from Xero).

    These are one-time payments with specific due dates, separate from
    recurring billing configuration.
    """
    events = []
    outstanding = config.get("outstanding_invoices", [])

    for i, invoice in enumerate(outstanding):
        expected_date_str = invoice.get("expected_date")
        if not expected_date_str:
            continue

        try:
            invoice_date = date.fromisoformat(expected_date_str)
        except ValueError:
            continue

        amount = Decimal(str(invoice.get("amount", 0)))
        if amount <= 0:
            continue

        # Payment terms - usually net_0 since due date already accounts for terms
        payment_terms = invoice.get("payment_terms", "net_0")
        payment_delay_days = 0
        if isinstance(payment_terms, str) and "net_" in payment_terms:
            try:
                payment_delay_days = int(payment_terms.replace("net_", ""))
            except ValueError:
                pass

        payment_date = invoice_date + timedelta(days=payment_delay_days)

        if start_date <= payment_date <= end_date:
            # Outstanding invoices from Xero get HIGH confidence
            invoice_confidence = ConfidenceLevel.HIGH if client.xero_contact_id else confidence_score.level
            invoice_name = invoice.get("name", f"Invoice {i+1}")

            events.append(ForecastEvent(
                id=f"client_{client.id}_invoice_{i}_{payment_date.isoformat()}",
                date=payment_date,
                amount=amount,
                direction="in",
                event_type="expected_revenue",
                category="outstanding_invoice",
                confidence=invoice_confidence,
                confidence_reason=f"Outstanding invoice from Xero: {invoice_name}",
                source_id=client.id,
                source_name=client.name,
                source_type="client",
                is_recurring=False,
                recurrence_pattern=None
            ))

    return events


def _compute_usage_events(
    client: Client,
    config: dict,
    start_date: date,
    end_date: date,
    confidence_score: ConfidenceScore
) -> List[ForecastEvent]:
    """Compute events for usage-based clients."""
    events = []
    frequency = config.get("settlement_frequency", "monthly")
    typical_amount = Decimal(str(config.get("typical_amount", 0)))

    if typical_amount <= 0:
        return events

    payment_terms = config.get("payment_terms", "net_30")
    payment_delay_days = 30
    if isinstance(payment_terms, str) and "net_" in payment_terms:
        try:
            payment_delay_days = int(payment_terms.replace("net_", ""))
        except ValueError:
            pass

    current_date = start_date.replace(day=1)
    event_num = 0

    while current_date <= end_date:
        payment_date = current_date + timedelta(days=payment_delay_days)

        if start_date <= payment_date <= end_date:
            event_num += 1
            # Usage has inherently lower confidence due to variability
            usage_confidence = ConfidenceLevel.MEDIUM if confidence_score.level == ConfidenceLevel.HIGH else confidence_score.level
            events.append(ForecastEvent(
                id=f"client_{client.id}_usage_{payment_date.isoformat()}_{event_num}",
                date=payment_date,
                amount=typical_amount,
                direction="in",
                event_type="expected_revenue",
                category="usage",
                confidence=usage_confidence,
                confidence_reason="Usage-based (variable)",
                source_id=client.id,
                source_name=client.name,
                source_type="client",
                is_recurring=True,
                recurrence_pattern=frequency
            ))

        # Move to next period
        if frequency == "monthly":
            current_date += relativedelta(months=1)
        elif frequency == "bi-weekly":
            current_date += timedelta(weeks=2)
        elif frequency == "weekly":
            current_date += timedelta(weeks=1)
        else:
            current_date += relativedelta(months=1)

    return events


def _compute_expense_events(
    bucket: ExpenseBucket,
    start_date: date,
    end_date: date,
    confidence_score: ConfidenceScore,
    scenario_context: Optional['ScenarioContext'] = None
) -> List[ForecastEvent]:
    """
    Compute forecast events from an expense bucket.

    This is a pure function - no database writes.
    Supports scenario modifications like amount changes.
    """
    events = []

    if bucket.monthly_amount is None or bucket.monthly_amount <= 0:
        return events

    due_day = bucket.due_day or 15
    frequency = bucket.frequency or "monthly"

    # Check for expense amount modifications in scenario
    amount_delta = Decimal("0")
    if scenario_context and bucket.id in scenario_context.expense_amount_deltas:
        amount_delta = scenario_context.expense_amount_deltas[bucket.id]

    effective_amount = bucket.monthly_amount + amount_delta
    if effective_amount <= 0:
        return events  # Expense reduced to zero or below

    event_num = 0

    # Handle weekly and bi-weekly frequencies with proper week-based iteration
    if frequency in ("weekly", "bi_weekly", "bi-weekly"):
        # For bi-weekly, amount is half of monthly; for weekly, it's quarter of monthly
        if frequency == "weekly":
            period_amount = effective_amount / Decimal("4")
            week_increment = 1
        else:  # bi_weekly or bi-weekly
            period_amount = effective_amount / Decimal("2")
            week_increment = 2

        # Find the first occurrence on or after start_date
        # Use due_day as day-of-week indicator (1=Monday, 5=Friday, etc.)
        # If due_day > 7, it was stored as a calendar day, so find the nearest matching weekday
        target_weekday = (due_day - 1) % 7 if due_day <= 7 else 4  # Default to Friday (4) for payroll

        current_date = start_date
        # Align to the target weekday
        days_until_target = (target_weekday - current_date.weekday()) % 7
        current_date = current_date + timedelta(days=days_until_target)

        while current_date <= end_date:
            # Determine if scenario modifications apply to this date
            use_modified_amount = (
                scenario_context and
                amount_delta != 0 and
                (scenario_context.effective_date is None or current_date >= scenario_context.effective_date)
            )

            # Calculate the per-period amount with any modifications
            base_period_amount = bucket.monthly_amount / (Decimal("4") if frequency == "weekly" else Decimal("2"))
            modified_period_amount = period_amount if use_modified_amount else base_period_amount

            event_reason = confidence_score.reason
            if use_modified_amount:
                event_reason = f"Amount modified by ${amount_delta} (scenario)"

            event_num += 1
            events.append(ForecastEvent(
                id=f"expense_{bucket.id}_{current_date.isoformat()}_{event_num}",
                date=current_date,
                amount=modified_period_amount,
                direction="out",
                event_type="expected_expense",
                category=bucket.category,
                confidence=confidence_score.level,
                confidence_reason=event_reason,
                source_id=bucket.id,
                source_name=bucket.name,
                source_type="expense",
                is_recurring=True,
                recurrence_pattern=frequency
            ))

            current_date += timedelta(weeks=week_increment)

    else:
        # Monthly and quarterly frequencies use month-based iteration
        current_month = start_date.replace(day=1)

        # Generate up to 4 months of expenses
        for _ in range(4):
            try:
                expense_date = current_month.replace(day=due_day)
            except ValueError:
                # Day doesn't exist in this month, use last day
                next_month = current_month + relativedelta(months=1)
                expense_date = next_month - timedelta(days=1)

            if start_date <= expense_date <= end_date:
                # Determine if scenario modifications apply to this date
                use_modified_amount = (
                    scenario_context and
                    amount_delta != 0 and
                    (scenario_context.effective_date is None or expense_date >= scenario_context.effective_date)
                )

                event_amount = effective_amount if use_modified_amount else bucket.monthly_amount
                event_reason = confidence_score.reason
                if use_modified_amount:
                    event_reason = f"Amount modified by ${amount_delta} (scenario)"

                event_num += 1
                events.append(ForecastEvent(
                    id=f"expense_{bucket.id}_{expense_date.isoformat()}_{event_num}",
                    date=expense_date,
                    amount=event_amount,
                    direction="out",
                    event_type="expected_expense",
                    category=bucket.category,
                    confidence=confidence_score.level,
                    confidence_reason=event_reason,
                    source_id=bucket.id,
                    source_name=bucket.name,
                    source_type="expense",
                    is_recurring=True,
                    recurrence_pattern=frequency
                ))

            # Move to next period based on frequency
            if frequency == "quarterly":
                current_month += relativedelta(months=3)
            else:  # monthly or default
                current_month += relativedelta(months=1)

    return events


# =============================================================================
# New Canonical Approach: Compute events from ObligationSchedules
# =============================================================================

async def _compute_events_from_obligations(
    db: AsyncSession,
    user_id: str,
    start_date: date,
    end_date: date
) -> tuple[List[ForecastEvent], List[tuple], List[tuple]]:
    """
    Compute forecast events from ObligationSchedules (new canonical approach).

    This reads from the canonical obligation system rather than Client/ExpenseBucket.

    Args:
        db: Database session
        user_id: User ID
        start_date: Forecast start date
        end_date: Forecast end date

    Returns:
        Tuple of (events, client_confidence_data, expense_confidence_data)
    """
    events: List[ForecastEvent] = []
    client_confidence_data = []
    expense_confidence_data = []

    # Query obligation schedules in date range
    query = (
        select(ObligationSchedule)
        .join(ObligationAgreement)
        .where(
            and_(
                ObligationAgreement.user_id == user_id,
                ObligationSchedule.due_date >= start_date,
                ObligationSchedule.due_date <= end_date,
                ObligationSchedule.status.in_(["scheduled", "due"])
            )
        )
    )

    result = await db.execute(query)
    schedules = result.scalars().all()

    # Group schedules by obligation for confidence calculation
    obligation_schedules: Dict[str, List[ObligationSchedule]] = {}
    for schedule in schedules:
        if schedule.obligation_id not in obligation_schedules:
            obligation_schedules[schedule.obligation_id] = []
        obligation_schedules[schedule.obligation_id].append(schedule)

    # Process each schedule
    for schedule in schedules:
        obligation = schedule.obligation

        # Determine direction and event type based on source entity
        if obligation.client_id:
            direction = "in"
            event_type = "expected_revenue"
            source_type = "client"
            # Get client for name and confidence
            client_query = select(Client).where(Client.id == obligation.client_id)
            client_result = await db.execute(client_query)
            client = client_result.scalar_one_or_none()
            source_name = client.name if client else obligation.vendor_name or "Unknown Client"
            confidence_score = calculate_client_confidence(client) if client else ConfidenceScore(
                level=ConfidenceLevel.MEDIUM,
                score=Decimal("0.5"),
                reason="No linked client"
            )
        elif obligation.expense_bucket_id:
            direction = "out"
            event_type = "expected_expense"
            source_type = "expense"
            # Get expense bucket for name and confidence
            bucket_query = select(ExpenseBucket).where(ExpenseBucket.id == obligation.expense_bucket_id)
            bucket_result = await db.execute(bucket_query)
            bucket = bucket_result.scalar_one_or_none()
            source_name = bucket.name if bucket else obligation.vendor_name or "Unknown Expense"
            confidence_score = calculate_expense_confidence(bucket) if bucket else ConfidenceScore(
                level=ConfidenceLevel.MEDIUM,
                score=Decimal("0.5"),
                reason="No linked expense bucket"
            )
        else:
            # Generic obligation - default to expense
            direction = "out"
            event_type = "expected_expense"
            source_type = "obligation"
            source_name = obligation.vendor_name or obligation.obligation_type
            confidence_score = _calculate_obligation_confidence(obligation, schedule)

        # Map schedule confidence to ConfidenceLevel
        schedule_confidence = _map_schedule_confidence(schedule.confidence, confidence_score.level)

        # Determine recurrence
        is_recurring = obligation.frequency not in [None, "one_time"]
        recurrence_pattern = _map_obligation_frequency(obligation.frequency)

        event = ForecastEvent(
            id=f"obligation_{obligation.id}_{schedule.id}_{schedule.due_date.isoformat()}",
            date=schedule.due_date,
            amount=schedule.estimated_amount,
            direction=direction,
            event_type=event_type,
            category=obligation.category,
            confidence=schedule_confidence,
            confidence_reason=f"From obligation schedule ({schedule.estimate_source})",
            source_id=obligation.id,
            source_name=source_name,
            source_type=source_type,
            is_recurring=is_recurring,
            recurrence_pattern=recurrence_pattern
        )
        events.append(event)

    # Also include confirmed PaymentEvents as high-confidence actuals
    payment_query = (
        select(PaymentEvent)
        .where(
            and_(
                PaymentEvent.user_id == user_id,
                PaymentEvent.payment_date >= start_date,
                PaymentEvent.payment_date <= end_date,
                PaymentEvent.status == "completed"
            )
        )
    )
    payment_result = await db.execute(payment_query)
    payment_events = payment_result.scalars().all()

    for payment in payment_events:
        # Confirmed payments get HIGH confidence
        event = ForecastEvent(
            id=f"payment_{payment.id}_{payment.payment_date.isoformat()}",
            date=payment.payment_date,
            amount=payment.amount,
            direction="out",  # PaymentEvents are always outflows
            event_type="confirmed_expense",
            category="payment",
            confidence=ConfidenceLevel.HIGH,
            confidence_reason="Confirmed payment from bank",
            source_id=payment.id,
            source_name=payment.vendor_name or "Payment",
            source_type="payment",
            is_recurring=False,
            recurrence_pattern=None
        )
        events.append(event)

    # Build confidence data for summary calculation
    # Group by original source (client/expense)
    for obligation_id, schedules in obligation_schedules.items():
        total_amount = sum(s.estimated_amount for s in schedules)
        obligation = schedules[0].obligation

        if obligation.client_id:
            client_query = select(Client).where(Client.id == obligation.client_id)
            client_result = await db.execute(client_query)
            client = client_result.scalar_one_or_none()
            if client:
                confidence = calculate_client_confidence(client)
                client_confidence_data.append((client, confidence, total_amount))
        elif obligation.expense_bucket_id:
            bucket_query = select(ExpenseBucket).where(ExpenseBucket.id == obligation.expense_bucket_id)
            bucket_result = await db.execute(bucket_query)
            bucket = bucket_result.scalar_one_or_none()
            if bucket:
                confidence = calculate_expense_confidence(bucket)
                expense_confidence_data.append((bucket, confidence, total_amount))

    return events, client_confidence_data, expense_confidence_data


def _calculate_obligation_confidence(
    obligation: ObligationAgreement,
    schedule: ObligationSchedule
) -> ConfidenceScore:
    """Calculate confidence for a standalone obligation (not linked to client/expense)."""
    # Base score depends on amount_source
    if obligation.amount_source == "xero_sync":
        level = ConfidenceLevel.HIGH
        score = Decimal("0.9")
        reason = "Synced from Xero"
    elif obligation.amount_source == "repeating_invoice":
        level = ConfidenceLevel.HIGH
        score = Decimal("0.85")
        reason = "From repeating invoice"
    elif obligation.amount_source == "contract_upload":
        level = ConfidenceLevel.MEDIUM
        score = Decimal("0.7")
        reason = "From contract upload"
    else:  # manual_entry
        level = ConfidenceLevel.MEDIUM
        score = Decimal("0.6")
        reason = "Manual entry"

    # Adjust based on schedule estimate_source
    if schedule.estimate_source == "historical_average":
        score = score * Decimal("0.9")  # Slightly less confident
        reason += " (historical average)"
    elif schedule.estimate_source == "manual_estimate":
        score = score * Decimal("0.8")
        reason += " (manual estimate)"

    # Map score to level
    if score >= Decimal("0.8"):
        level = ConfidenceLevel.HIGH
    elif score >= Decimal("0.5"):
        level = ConfidenceLevel.MEDIUM
    else:
        level = ConfidenceLevel.LOW

    return ConfidenceScore(level=level, score=score, reason=reason)


def _map_schedule_confidence(
    schedule_confidence: Optional[str],
    fallback_level: ConfidenceLevel
) -> ConfidenceLevel:
    """Map schedule confidence string to ConfidenceLevel enum."""
    if schedule_confidence == "high":
        return ConfidenceLevel.HIGH
    elif schedule_confidence == "medium":
        return ConfidenceLevel.MEDIUM
    elif schedule_confidence == "low":
        return ConfidenceLevel.LOW
    return fallback_level


def _map_obligation_frequency(frequency: Optional[str]) -> Optional[str]:
    """Map obligation frequency to recurrence pattern."""
    frequency_map = {
        "weekly": "weekly",
        "bi_weekly": "bi-weekly",
        "monthly": "monthly",
        "quarterly": "quarterly",
        "annually": "yearly",
        "one_time": None,
    }
    return frequency_map.get(frequency)


def _compute_added_revenue_events(
    user_id: str,
    revenue_config: Dict[str, Any],
    start_date: date,
    end_date: date
) -> List[ForecastEvent]:
    """
    Compute forecast events for scenario-added revenue (client_gain scenario).

    Args:
        user_id: User ID
        revenue_config: Dict with keys: start_date, amount, frequency, name
        start_date: Forecast start date
        end_date: Forecast end date

    Returns:
        List of ForecastEvent objects for the added revenue
    """
    events = []

    rev_start_str = revenue_config.get("start_date")
    if rev_start_str:
        if isinstance(rev_start_str, str):
            rev_start = date.fromisoformat(rev_start_str)
        else:
            rev_start = rev_start_str
    else:
        rev_start = start_date

    amount = Decimal(str(revenue_config.get("amount", 0)))
    if amount <= 0:
        return events

    frequency = revenue_config.get("frequency", "monthly")
    name = revenue_config.get("name", "New Client (Scenario)")

    current_date = rev_start
    event_num = 0

    while current_date <= end_date:
        if current_date >= start_date:
            event_num += 1
            events.append(ForecastEvent(
                id=f"scenario_revenue_{name}_{current_date.isoformat()}_{event_num}",
                date=current_date,
                amount=amount,
                direction="in",
                event_type="expected_revenue",
                category="new_client",
                confidence=ConfidenceLevel.MEDIUM,
                confidence_reason="Scenario projection (new client)",
                source_id=f"scenario_{name}",
                source_name=name,
                source_type="scenario",
                is_recurring=True,
                recurrence_pattern=frequency
            ))

        # Move to next period
        if frequency == "monthly":
            current_date += relativedelta(months=1)
        elif frequency == "weekly":
            current_date += timedelta(weeks=1)
        elif frequency == "bi-weekly" or frequency == "bi_weekly":
            current_date += timedelta(weeks=2)
        elif frequency == "quarterly":
            current_date += relativedelta(months=3)
        else:
            current_date += relativedelta(months=1)

    return events


def _compute_added_expense_events(
    user_id: str,
    expense_config: Dict[str, Any],
    start_date: date,
    end_date: date
) -> List[ForecastEvent]:
    """
    Compute forecast events for scenario-added expenses (hiring, contractor_gain scenarios).

    Args:
        user_id: User ID
        expense_config: Dict with keys: start_date, amount, frequency, category, name, is_one_time
        start_date: Forecast start date
        end_date: Forecast end date

    Returns:
        List of ForecastEvent objects for the added expenses
    """
    events = []

    exp_start_str = expense_config.get("start_date")
    if exp_start_str:
        if isinstance(exp_start_str, str):
            exp_start = date.fromisoformat(exp_start_str)
        else:
            exp_start = exp_start_str
    else:
        exp_start = start_date

    amount = Decimal(str(expense_config.get("amount", 0)))
    if amount <= 0:
        return events

    frequency = expense_config.get("frequency", "monthly")
    category = expense_config.get("category", "other")
    name = expense_config.get("name", "New Expense (Scenario)")
    is_one_time = expense_config.get("is_one_time", False)

    if is_one_time:
        # One-time expense
        if start_date <= exp_start <= end_date:
            events.append(ForecastEvent(
                id=f"scenario_expense_{name}_{exp_start.isoformat()}_1",
                date=exp_start,
                amount=amount,
                direction="out",
                event_type="expected_expense",
                category=category,
                confidence=ConfidenceLevel.HIGH,
                confidence_reason="Scenario projection (one-time expense)",
                source_id=f"scenario_{name}",
                source_name=name,
                source_type="scenario",
                is_recurring=False,
                recurrence_pattern=None
            ))
    else:
        # Recurring expense
        current_date = exp_start
        event_num = 0

        while current_date <= end_date:
            if current_date >= start_date:
                event_num += 1
                events.append(ForecastEvent(
                    id=f"scenario_expense_{name}_{current_date.isoformat()}_{event_num}",
                    date=current_date,
                    amount=amount,
                    direction="out",
                    event_type="expected_expense",
                    category=category,
                    confidence=ConfidenceLevel.MEDIUM,
                    confidence_reason="Scenario projection (recurring expense)",
                    source_id=f"scenario_{name}",
                    source_name=name,
                    source_type="scenario",
                    is_recurring=True,
                    recurrence_pattern=frequency
                ))

            # Move to next period
            if frequency == "monthly":
                current_date += relativedelta(months=1)
            elif frequency == "weekly":
                current_date += timedelta(weeks=1)
            elif frequency == "bi-weekly" or frequency == "bi_weekly":
                current_date += timedelta(weeks=2)
            elif frequency == "quarterly":
                current_date += relativedelta(months=3)
            else:
                current_date += relativedelta(months=1)

    return events


@dataclass
class ScenarioContext:
    """
    Context for scenario modifications to the forecast.

    This allows scenarios to modify the forecast without storing CashEvents.
    The forecast engine uses this to exclude clients, modify amounts, etc.
    """
    # Clients to exclude entirely (client_loss scenario)
    excluded_client_ids: List[str] = None

    # Expense buckets to exclude entirely
    excluded_bucket_ids: List[str] = None

    # Client amount modifications: {client_id: delta_amount}
    client_amount_deltas: Dict[str, Decimal] = None

    # Expense amount modifications: {bucket_id: delta_amount}
    expense_amount_deltas: Dict[str, Decimal] = None

    # Payment delays: {client_id: delay_days}
    client_payment_delays: Dict[str, int] = None

    # New recurring revenue to add: [{start_date, amount, frequency, name}]
    added_revenue: List[Dict[str, Any]] = None

    # New recurring expenses to add: [{start_date, amount, frequency, category, name}]
    added_expenses: List[Dict[str, Any]] = None

    # Effective date for modifications (changes only apply from this date)
    effective_date: Optional[date] = None

    def __post_init__(self):
        if self.excluded_client_ids is None:
            self.excluded_client_ids = []
        if self.excluded_bucket_ids is None:
            self.excluded_bucket_ids = []
        if self.client_amount_deltas is None:
            self.client_amount_deltas = {}
        if self.expense_amount_deltas is None:
            self.expense_amount_deltas = {}
        if self.client_payment_delays is None:
            self.client_payment_delays = {}
        if self.added_revenue is None:
            self.added_revenue = []
        if self.added_expenses is None:
            self.added_expenses = []


async def calculate_forecast_v2(
    db: AsyncSession,
    user_id: str,
    weeks: int = 13,
    use_obligations: Optional[bool] = None,
    scenario_context: Optional[ScenarioContext] = None
) -> Dict[str, Any]:
    """
    Calculate a forecast by computing events on-the-fly from source data.

    This is the V2 forecast engine that:
    1. Reads directly from clients and expense_buckets tables (legacy)
       OR from ObligationSchedules (new canonical approach)
    2. Computes events on-the-fly (never stale)
    3. Includes confidence scoring based on integration status
    4. Returns comprehensive confidence breakdown

    Args:
        db: Database session
        user_id: User ID
        weeks: Number of weeks to forecast (default 13)
        use_obligations: If True, use obligation-based computation.
                        If None, uses settings.USE_OBLIGATION_FOR_FORECAST.
        scenario_context: Optional context for scenario modifications (exclusions, deltas, etc.)

    Returns:
        Dictionary containing forecast data with confidence metrics
    """
    # Determine which computation path to use
    if use_obligations is None:
        use_obligations = settings.USE_OBLIGATION_FOR_FORECAST

    # Get starting cash
    result = await db.execute(
        select(func.sum(CashAccount.balance))
        .where(CashAccount.user_id == user_id)
    )
    starting_cash = result.scalar() or Decimal("0")

    # Get forecast date range
    forecast_start = date.today()
    forecast_end = forecast_start + timedelta(weeks=weeks)

    # Compute events based on selected approach
    all_events: List[ForecastEvent] = []
    client_confidence_data = []
    expense_confidence_data = []

    if use_obligations:
        # New canonical approach: compute from ObligationSchedules
        all_events, client_confidence_data, expense_confidence_data = await _compute_events_from_obligations(
            db, user_id, forecast_start, forecast_end
        )
    else:
        # Legacy approach: compute from Client/ExpenseBucket tables

        # Get all active clients
        result = await db.execute(
            select(Client)
            .where(Client.user_id == user_id)
            .where(Client.status == "active")
        )
        clients = result.scalars().all()

        # Get all expense buckets
        result = await db.execute(
            select(ExpenseBucket)
            .where(ExpenseBucket.user_id == user_id)
        )
        buckets = result.scalars().all()

        # Process clients (with scenario context filtering)
        for client in clients:
            # Skip excluded clients (e.g., client_loss scenario)
            if scenario_context and client.id in scenario_context.excluded_client_ids:
                continue

            confidence = calculate_client_confidence(client)
            events = _compute_client_events(
                client, forecast_start, forecast_end, confidence,
                scenario_context=scenario_context
            )
            all_events.extend(events)

            # Calculate monthly amount for confidence weighting
            config = client.billing_config or {}
            monthly_amount = Decimal(str(config.get("amount", 0)))
            client_confidence_data.append((client, confidence, monthly_amount))

        # Process expenses (with scenario context filtering)
        for bucket in buckets:
            # Skip excluded buckets (e.g., contractor_loss scenario)
            if scenario_context and bucket.id in scenario_context.excluded_bucket_ids:
                continue

            confidence = calculate_expense_confidence(bucket)
            events = _compute_expense_events(
                bucket, forecast_start, forecast_end, confidence,
                scenario_context=scenario_context
            )
            all_events.extend(events)

            expense_confidence_data.append((bucket, confidence, bucket.monthly_amount or Decimal("0")))

        # Add scenario-specific revenue (e.g., client_gain scenario)
        if scenario_context and scenario_context.added_revenue:
            for revenue in scenario_context.added_revenue:
                events = _compute_added_revenue_events(
                    user_id, revenue, forecast_start, forecast_end
                )
                all_events.extend(events)

        # Add scenario-specific expenses (e.g., hiring, contractor_gain scenario)
        if scenario_context and scenario_context.added_expenses:
            for expense in scenario_context.added_expenses:
                events = _compute_added_expense_events(
                    user_id, expense, forecast_start, forecast_end
                )
                all_events.extend(events)

    # Sort events by date
    all_events.sort(key=lambda e: e.date)

    # Build weekly forecast
    week_forecasts = []
    current_balance = starting_cash

    # Add Week 0 - Current cash position (no events, just starting balance)
    today = forecast_start
    week_forecasts.append({
        "week_number": 0,
        "week_start": today.isoformat(),
        "week_end": today.isoformat(),
        "starting_balance": str(starting_cash),
        "cash_in": "0",
        "cash_out": "0",
        "net_change": "0",
        "ending_balance": str(starting_cash),
        "confidence_breakdown": {
            "cash_in": {"high": "0", "medium": "0", "low": "0"},
            "cash_out": {"high": "0", "medium": "0", "low": "0"}
        },
        "events": []
    })

    for week_num in range(1, weeks + 1):
        week_start = forecast_start + timedelta(days=(week_num - 1) * 7)
        week_end = week_start + timedelta(days=6)

        # Filter events for this week
        week_events = [e for e in all_events if week_start <= e.date <= week_end]

        # Calculate totals
        cash_in = sum(e.amount for e in week_events if e.direction == "in")
        cash_out = sum(e.amount for e in week_events if e.direction == "out")
        net_change = cash_in - cash_out
        ending_balance = current_balance + net_change

        # Calculate confidence breakdown for this week
        high_conf_in = sum(e.amount for e in week_events if e.direction == "in" and e.confidence == ConfidenceLevel.HIGH)
        medium_conf_in = sum(e.amount for e in week_events if e.direction == "in" and e.confidence == ConfidenceLevel.MEDIUM)
        low_conf_in = sum(e.amount for e in week_events if e.direction == "in" and e.confidence == ConfidenceLevel.LOW)
        high_conf_out = sum(e.amount for e in week_events if e.direction == "out" and e.confidence == ConfidenceLevel.HIGH)
        medium_conf_out = sum(e.amount for e in week_events if e.direction == "out" and e.confidence == ConfidenceLevel.MEDIUM)
        low_conf_out = sum(e.amount for e in week_events if e.direction == "out" and e.confidence == ConfidenceLevel.LOW)

        week_forecasts.append({
            "week_number": week_num,
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "starting_balance": str(current_balance),
            "cash_in": str(cash_in),
            "cash_out": str(cash_out),
            "net_change": str(net_change),
            "ending_balance": str(ending_balance),
            "confidence_breakdown": {
                "cash_in": {
                    "high": str(high_conf_in),
                    "medium": str(medium_conf_in),
                    "low": str(low_conf_in),
                },
                "cash_out": {
                    "high": str(high_conf_out),
                    "medium": str(medium_conf_out),
                    "low": str(low_conf_out),
                }
            },
            "events": [
                {
                    "id": e.id,
                    "date": e.date.isoformat(),
                    "amount": str(e.amount),
                    "direction": e.direction,
                    "event_type": e.event_type,
                    "category": e.category,
                    "confidence": e.confidence.value,
                    "confidence_reason": e.confidence_reason,
                    "source_id": e.source_id,
                    "source_name": e.source_name,
                    "source_type": e.source_type,
                }
                for e in sorted(week_events, key=lambda x: x.amount, reverse=True)[:10]
            ]
        })

        current_balance = ending_balance

    # Calculate summary statistics (exclude Week 0 from min calculation since it's just starting position)
    forecast_weeks = [w for w in week_forecasts if w["week_number"] > 0]
    balances = [Decimal(w["ending_balance"]) for w in forecast_weeks]
    lowest_balance = min(balances) if balances else Decimal("0")
    lowest_week_idx = balances.index(lowest_balance) if balances else 0
    lowest_week = forecast_weeks[lowest_week_idx]["week_number"] if forecast_weeks else 1

    total_cash_in = sum(Decimal(w["cash_in"]) for w in forecast_weeks)
    total_cash_out = sum(Decimal(w["cash_out"]) for w in forecast_weeks)

    # Calculate runway (based on forecast weeks, not Week 0)
    runway_weeks = weeks
    for i, balance in enumerate(balances):
        if balance <= 0:
            runway_weeks = i + 1
            break

    # Calculate overall confidence summary
    confidence_summary = calculate_forecast_confidence_summary(
        client_confidence_data,
        expense_confidence_data
    )

    return {
        "starting_cash": str(starting_cash),
        "forecast_start_date": forecast_start.isoformat(),
        "weeks": week_forecasts,
        "summary": {
            "lowest_cash_week": lowest_week,
            "lowest_cash_amount": str(lowest_balance),
            "total_cash_in": str(total_cash_in),
            "total_cash_out": str(total_cash_out),
            "runway_weeks": runway_weeks,
        },
        "confidence": {
            "overall_score": str(confidence_summary.overall_score),
            "overall_level": confidence_summary.overall_level.value,
            "overall_percentage": confidence_summary.overall_percentage,
            "breakdown": {
                "high_confidence_count": confidence_summary.high_confidence_count,
                "medium_confidence_count": confidence_summary.medium_confidence_count,
                "low_confidence_count": confidence_summary.low_confidence_count,
                "high_confidence_amount": str(confidence_summary.high_confidence_amount),
                "medium_confidence_amount": str(confidence_summary.medium_confidence_amount),
                "low_confidence_amount": str(confidence_summary.low_confidence_amount),
            },
            "improvement_suggestions": confidence_summary.improvement_suggestions,
        }
    }


# Backward compatibility alias for code that imports from old engine.py
calculate_13_week_forecast = calculate_forecast_v2
