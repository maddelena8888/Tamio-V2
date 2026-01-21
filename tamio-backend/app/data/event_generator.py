"""Auto-generate cash events from clients and expense buckets."""
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.data import models
from app.data.obligations.models import ObligationSchedule, ObligationAgreement


async def generate_events_from_client(
    db: AsyncSession,
    client: models.Client
) -> List[models.CashEvent]:
    """
    Generate cash events from a client's billing configuration.

    Args:
        db: Database session
        client: Client model instance

    Returns:
        List of generated CashEvent models
    """
    events = []
    config = client.billing_config
    today = date.today()
    forecast_end = today + timedelta(weeks=13)

    if client.client_type == "retainer":
        events = _generate_retainer_events(client, config, today, forecast_end)

    elif client.client_type == "project":
        events = _generate_project_events(client, config, today, forecast_end)

    elif client.client_type == "usage":
        events = _generate_usage_events(client, config, today, forecast_end)

    elif client.client_type == "mixed":
        # Generate events for each component
        if "retainer" in config:
            events.extend(_generate_retainer_events(client, config["retainer"], today, forecast_end))
        if "project" in config:
            events.extend(_generate_project_events(client, config["project"], today, forecast_end))
        if "usage" in config:
            events.extend(_generate_usage_events(client, config["usage"], today, forecast_end))

    # Save events to database
    for event in events:
        db.add(event)

    await db.commit()

    for event in events:
        await db.refresh(event)

    return events


def _generate_retainer_events(
    client: models.Client,
    config: dict,
    start_date: date,
    end_date: date
) -> List[models.CashEvent]:
    """Generate events for retainer clients."""
    events = []
    frequency = config.get("frequency", "monthly")
    amount = Decimal(str(config.get("amount", 0)))
    payment_terms = config.get("payment_terms", "net_30")
    billing_day = config.get("billing_day", "start_of_month")
    # Support both invoice_day (schema) and day_of_month (frontend) field names
    # Ensure we get an integer value
    raw_invoice_day = config.get("invoice_day") or config.get("day_of_month")
    try:
        invoice_day = int(raw_invoice_day) if raw_invoice_day else 1
    except (ValueError, TypeError):
        invoice_day = 1

    # Parse payment terms (e.g., "net_30" -> 30 days)
    payment_delay_days = int(payment_terms.replace("net_", "")) if "net_" in payment_terms else 0

    current_date = start_date
    while current_date <= end_date:
        # Calculate billing date
        if billing_day == "start_of_month" and invoice_day == 1:
            billing_date = current_date.replace(day=1)
        else:
            try:
                billing_date = current_date.replace(day=invoice_day)
            except ValueError:
                billing_date = current_date.replace(day=1)

        # Payment date = billing date + payment terms
        payment_date = billing_date + timedelta(days=payment_delay_days)

        if start_date <= payment_date <= end_date:
            event = models.CashEvent(
                user_id=client.user_id,
                client_id=client.id,
                date=payment_date,
                amount=amount,
                direction="in",
                event_type="expected_revenue",
                category="retainer",
                confidence="high",
                confidence_reason="inferred_pattern" if current_date > start_date else "user_confirmed",
                is_recurring=True,
                recurrence_pattern=frequency
            )
            events.append(event)

        # Move to next period
        if frequency == "monthly":
            current_date += relativedelta(months=1)
        elif frequency == "quarterly":
            current_date += relativedelta(months=3)
        else:
            break

    return events


def _generate_project_events(
    client: models.Client,
    config: dict,
    start_date: date,
    end_date: date
) -> List[models.CashEvent]:
    """Generate events for project clients."""
    events = []
    milestones = config.get("milestones", [])

    for milestone in milestones:
        milestone_date = date.fromisoformat(milestone.get("expected_date", str(start_date)))
        amount = Decimal(str(milestone.get("amount", 0)))
        payment_terms = milestone.get("payment_terms", "net_14")
        payment_delay_days = int(payment_terms.replace("net_", "")) if "net_" in payment_terms else 0

        payment_date = milestone_date + timedelta(days=payment_delay_days)

        if start_date <= payment_date <= end_date:
            event = models.CashEvent(
                user_id=client.user_id,
                client_id=client.id,
                date=payment_date,
                amount=amount,
                direction="in",
                event_type="expected_revenue",
                category="milestone_payment",
                confidence="high" if milestone.get("trigger_type") == "date" else "medium",
                confidence_reason="user_confirmed",
                is_recurring=False,
                notes=milestone.get("name")
            )
            events.append(event)

    return events


def _generate_usage_events(
    client: models.Client,
    config: dict,
    start_date: date,
    end_date: date
) -> List[models.CashEvent]:
    """Generate events for usage-based clients."""
    events = []
    frequency = config.get("settlement_frequency", "monthly")
    typical_amount = Decimal(str(config.get("typical_amount", 0)))
    payment_terms = config.get("payment_terms", "net_30")
    payment_delay_days = int(payment_terms.replace("net_", "")) if "net_" in payment_terms else 0

    current_date = start_date
    while current_date <= end_date:
        payment_date = current_date + timedelta(days=payment_delay_days)

        if start_date <= payment_date <= end_date:
            event = models.CashEvent(
                user_id=client.user_id,
                client_id=client.id,
                date=payment_date,
                amount=typical_amount,
                direction="in",
                event_type="expected_revenue",
                category="usage",
                confidence="medium",  # Usage is variable
                confidence_reason="user_estimate",
                is_recurring=True,
                recurrence_pattern=frequency
            )
            events.append(event)

        # Move to next period
        if frequency == "monthly":
            current_date += relativedelta(months=1)
        elif frequency == "bi-weekly":
            current_date += timedelta(weeks=2)
        elif frequency == "weekly":
            current_date += timedelta(weeks=1)
        else:
            break

    return events


async def generate_events_from_bucket(
    db: AsyncSession,
    bucket: models.ExpenseBucket
) -> List[models.CashEvent]:
    """
    Generate recurring cash events from an expense bucket.

    Args:
        db: Database session
        bucket: ExpenseBucket model instance

    Returns:
        List of generated CashEvent models
    """
    events = []
    today = date.today()
    forecast_end = today + timedelta(weeks=13)

    # Use the bucket's due_day, defaulting to 15 if not set
    due_day = bucket.due_day or 15

    # Generate monthly recurring events for 13 weeks (~3 months)
    # Start from current month
    current_month = today.replace(day=1)

    for _ in range(4):  # Generate 4 months of expenses
        # Calculate the actual due date for this month
        # Handle months with fewer days (e.g., Feb 30 -> Feb 28)
        try:
            expense_date = current_month.replace(day=due_day)
        except ValueError:
            # Day doesn't exist in this month (e.g., Feb 30), use last day
            next_month = current_month + relativedelta(months=1)
            expense_date = next_month - timedelta(days=1)

        if today <= expense_date <= forecast_end:
            event = models.CashEvent(
                user_id=bucket.user_id,
                bucket_id=bucket.id,
                date=expense_date,
                amount=bucket.monthly_amount,
                direction="out",
                event_type="expected_expense",
                category=bucket.category,
                confidence="high" if bucket.is_stable else "medium",
                confidence_reason="user_confirmed",
                is_recurring=True,
                recurrence_pattern="monthly",
                notes=f"Recurring {bucket.frequency}: {bucket.name}"
            )
            events.append(event)
            db.add(event)

        current_month += relativedelta(months=1)

    await db.commit()

    for event in events:
        await db.refresh(event)

    return events


# =============================================================================
# New Canonical Approach: Generate CashEvents from ObligationSchedules
# =============================================================================

async def generate_events_from_schedules(
    db: AsyncSession,
    user_id: str,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    skip_existing: bool = True
) -> List[models.CashEvent]:
    """
    Generate CashEvents from ObligationSchedules.

    This is the new canonical approach for generating cash events:
    - Query schedules in date range with status in ['scheduled', 'due']
    - Skip if CashEvent already exists for schedule (idempotent)
    - Set direction based on obligation's client_id vs expense_bucket_id

    Args:
        db: Database session
        user_id: User ID to generate events for
        from_date: Start date for event generation (default: today)
        to_date: End date for event generation (default: today + 13 weeks)
        skip_existing: If True, skip schedules that already have CashEvents

    Returns:
        List of generated CashEvent models
    """
    if from_date is None:
        from_date = date.today()
    if to_date is None:
        to_date = from_date + timedelta(weeks=13)

    # Query obligation schedules in date range
    query = (
        select(ObligationSchedule)
        .join(ObligationAgreement)
        .where(
            and_(
                ObligationAgreement.user_id == user_id,
                ObligationSchedule.due_date >= from_date,
                ObligationSchedule.due_date <= to_date,
                ObligationSchedule.status.in_(["scheduled", "due"])
            )
        )
    )

    result = await db.execute(query)
    schedules = result.scalars().all()

    events = []

    for schedule in schedules:
        # Check if event already exists for this schedule (idempotent)
        if skip_existing:
            existing_query = select(models.CashEvent).where(
                models.CashEvent.obligation_schedule_id == schedule.id
            )
            existing_result = await db.execute(existing_query)
            if existing_result.scalar_one_or_none():
                continue  # Skip, event already exists

        # Get the parent obligation to determine direction and other fields
        obligation = schedule.obligation

        # Determine direction and event type based on source entity
        if obligation.client_id:
            # Revenue obligation (from client)
            direction = "in"
            event_type = "expected_revenue"
            client_id = obligation.client_id
            bucket_id = None
        elif obligation.expense_bucket_id:
            # Expense obligation (from expense bucket)
            direction = "out"
            event_type = "expected_expense"
            client_id = None
            bucket_id = obligation.expense_bucket_id
        else:
            # Generic obligation - default to expense (conservative)
            direction = "out"
            event_type = "expected_expense"
            client_id = None
            bucket_id = None

        # Map obligation frequency to recurrence pattern
        recurrence_pattern = _map_frequency_to_pattern(obligation.frequency)
        is_recurring = obligation.frequency not in [None, "one_time"]

        # Map confidence levels
        confidence = schedule.confidence or "medium"

        event = models.CashEvent(
            user_id=user_id,
            date=schedule.due_date,
            week_number=_calculate_week_number(schedule.due_date, from_date),
            amount=schedule.estimated_amount,
            direction=direction,
            event_type=event_type,
            category=obligation.category,
            client_id=client_id,
            bucket_id=bucket_id,
            obligation_schedule_id=schedule.id,  # Link to source schedule
            confidence=confidence,
            confidence_reason=f"from_obligation_{schedule.estimate_source}",
            is_recurring=is_recurring,
            recurrence_pattern=recurrence_pattern,
            notes=schedule.notes or f"Generated from obligation: {obligation.vendor_name or obligation.obligation_type}"
        )

        events.append(event)
        db.add(event)

    if events:
        await db.commit()
        for event in events:
            await db.refresh(event)

    return events


def _map_frequency_to_pattern(frequency: Optional[str]) -> Optional[str]:
    """Map obligation frequency to CashEvent recurrence pattern."""
    frequency_map = {
        "weekly": "weekly",
        "bi_weekly": "bi-weekly",
        "monthly": "monthly",
        "quarterly": "quarterly",
        "annually": "yearly",
        "one_time": None,
    }
    return frequency_map.get(frequency)


def _calculate_week_number(event_date: date, reference_date: date) -> int:
    """Calculate week number relative to reference date."""
    delta = event_date - reference_date
    return max(0, delta.days // 7)


async def regenerate_events_for_obligation(
    db: AsyncSession,
    obligation_id: str,
    delete_future_only: bool = True
) -> List[models.CashEvent]:
    """
    Regenerate CashEvents for a specific obligation.

    This is useful when an obligation is updated and its schedules change.

    Args:
        db: Database session
        obligation_id: ID of the obligation to regenerate events for
        delete_future_only: If True, only delete events from today forward

    Returns:
        List of newly generated CashEvent models
    """
    from sqlalchemy import delete as sql_delete

    # Get the obligation
    obligation_query = select(ObligationAgreement).where(
        ObligationAgreement.id == obligation_id
    )
    result = await db.execute(obligation_query)
    obligation = result.scalar_one_or_none()

    if not obligation:
        return []

    # Get schedule IDs for this obligation
    schedule_query = select(ObligationSchedule.id).where(
        ObligationSchedule.obligation_id == obligation_id
    )
    schedule_result = await db.execute(schedule_query)
    schedule_ids = [s[0] for s in schedule_result.fetchall()]

    if not schedule_ids:
        return []

    # Delete existing events linked to these schedules
    delete_conditions = [
        models.CashEvent.obligation_schedule_id.in_(schedule_ids)
    ]
    if delete_future_only:
        delete_conditions.append(models.CashEvent.date >= date.today())

    await db.execute(
        sql_delete(models.CashEvent).where(and_(*delete_conditions))
    )
    await db.commit()

    # Generate new events from schedules
    return await generate_events_from_schedules(
        db,
        user_id=obligation.user_id,
        from_date=date.today() if delete_future_only else None,
        skip_existing=False  # We just deleted them
    )
