"""Auto-generate cash events from clients and expense buckets."""
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.data import models


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

    # Parse payment terms (e.g., "net_30" -> 30 days)
    payment_delay_days = int(payment_terms.replace("net_", "")) if "net_" in payment_terms else 0

    current_date = start_date
    while current_date <= end_date:
        # Calculate billing date
        if billing_day == "start_of_month":
            billing_date = current_date.replace(day=1)
        else:
            billing_date = current_date

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

    # Generate monthly recurring events for 13 weeks (~3 months)
    current_date = today.replace(day=1)  # Start of current month

    for _ in range(4):  # Generate 4 months of expenses
        if current_date <= forecast_end:
            event = models.CashEvent(
                user_id=bucket.user_id,
                bucket_id=bucket.id,
                date=current_date,
                amount=bucket.monthly_amount,
                direction="out",
                event_type="expected_expense",
                category=bucket.category,
                confidence="high" if bucket.is_stable else "medium",
                confidence_reason="user_confirmed",
                is_recurring=True,
                recurrence_pattern="monthly"
            )
            events.append(event)
            db.add(event)

        current_date += relativedelta(months=1)

    await db.commit()

    for event in events:
        await db.refresh(event)

    return events
