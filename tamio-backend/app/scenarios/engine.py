"""Scenario Engine - Builds and evaluates scenario layers."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Dict, Any, List, Optional
from datetime import date, timedelta, datetime
from decimal import Decimal
from copy import deepcopy
import secrets

from app.scenarios import models
from app.data.models import CashEvent, Client, ExpenseBucket, User, CashAccount
from app.forecast.engine import calculate_13_week_forecast


async def build_scenario_layer(
    db: AsyncSession,
    scenario: models.Scenario
) -> List[models.ScenarioEvent]:
    """
    Build scenario layer by cloning and modifying canonical objects.

    Returns list of ScenarioEvent objects representing all changes.
    """
    scenario_events = []

    if scenario.scenario_type == models.ScenarioType.PAYMENT_DELAY:
        scenario_events = await _build_payment_delay(db, scenario)

    elif scenario.scenario_type == models.ScenarioType.CLIENT_LOSS:
        scenario_events = await _build_client_loss(db, scenario)

    elif scenario.scenario_type == models.ScenarioType.CLIENT_GAIN:
        scenario_events = await _build_client_gain(db, scenario)

    elif scenario.scenario_type == models.ScenarioType.CLIENT_CHANGE:
        scenario_events = await _build_client_change(db, scenario)

    elif scenario.scenario_type == models.ScenarioType.HIRING:
        scenario_events = await _build_hiring(db, scenario)

    elif scenario.scenario_type == models.ScenarioType.FIRING:
        scenario_events = await _build_firing(db, scenario)

    elif scenario.scenario_type == models.ScenarioType.CONTRACTOR_GAIN:
        scenario_events = await _build_contractor_gain(db, scenario)

    elif scenario.scenario_type == models.ScenarioType.CONTRACTOR_LOSS:
        scenario_events = await _build_contractor_loss(db, scenario)

    elif scenario.scenario_type == models.ScenarioType.INCREASED_EXPENSE:
        scenario_events = await _build_expense_increase(db, scenario)

    elif scenario.scenario_type == models.ScenarioType.DECREASED_EXPENSE:
        scenario_events = await _build_expense_decrease(db, scenario)

    elif scenario.scenario_type == models.ScenarioType.PAYMENT_DELAY_OUT:
        scenario_events = await _build_payment_delay_out(db, scenario)

    return scenario_events


async def build_scenario_layer_for_type(
    db: AsyncSession,
    scenario: models.Scenario,
    layer_type: str,
    parameters: Dict[str, Any],
    layer_attribution: str = None
) -> List[models.ScenarioEvent]:
    """
    Build scenario events for a specific layer type.

    This allows adding multiple layers to a single scenario.
    Each layer can have different types (e.g., client_loss + contractor_loss).
    """
    # Create a temporary scenario-like object with the layer's type and params
    class TempScenario:
        def __init__(self, base_scenario, layer_type, layer_params):
            self.id = base_scenario.id
            self.user_id = base_scenario.user_id
            self.name = layer_attribution or f"{layer_type} layer"
            self.scenario_type = layer_type
            self.parameters = layer_params
            self.scope_config = layer_params.get("scope_config", {})

    temp_scenario = TempScenario(scenario, layer_type, parameters)

    # Build the layer based on type
    scenario_events = []

    if layer_type == "contractor_loss":
        scenario_events = await _build_contractor_loss(db, temp_scenario)
    elif layer_type == "decreased_expense":
        scenario_events = await _build_expense_decrease(db, temp_scenario)
    elif layer_type == "firing":
        scenario_events = await _build_firing(db, temp_scenario)
    elif layer_type == "contractor_gain":
        scenario_events = await _build_contractor_gain(db, temp_scenario)
    elif layer_type == "increased_expense":
        scenario_events = await _build_expense_increase(db, temp_scenario)
    elif layer_type == "payment_delay_out":
        scenario_events = await _build_payment_delay_out(db, temp_scenario)
    elif layer_type == "hiring":
        scenario_events = await _build_hiring(db, temp_scenario)
    elif layer_type == "client_gain":
        scenario_events = await _build_client_gain(db, temp_scenario)
    elif layer_type == "payment_delay":
        scenario_events = await _build_payment_delay(db, temp_scenario)

    # Update layer attribution for all events
    for event in scenario_events:
        event.layer_attribution = layer_attribution or f"{layer_type} layer"

    return scenario_events


async def _build_payment_delay(
    db: AsyncSession,
    scenario: models.Scenario
) -> List[models.ScenarioEvent]:
    """Build payment delay scenario."""
    scenario_events = []
    params = scenario.parameters
    scope = scenario.scope_config

    delay_weeks = params.get("delay_weeks") or 0
    if isinstance(delay_weeks, str):
        delay_weeks = int(delay_weeks) if delay_weeks else 0
    delay_weeks = int(delay_weeks) if delay_weeks else 0
    partial_pct = params.get("partial_payment_pct")
    event_ids = params.get("event_ids", [])

    # If no specific event_ids provided, find all future receivables for the client
    if not event_ids and scope.get("client_id"):
        client_id = scope.get("client_id")
        result = await db.execute(
            select(CashEvent).where(
                CashEvent.client_id == client_id,
                CashEvent.date >= date.today(),
                CashEvent.direction == "in"
            ).order_by(CashEvent.date)
        )
        events = result.scalars().all()
    else:
        # Use specific event_ids
        events = []
        for event_id in event_ids:
            result = await db.execute(
                select(CashEvent).where(CashEvent.id == event_id)
            )
            event = result.scalar_one_or_none()
            if event:
                events.append(event)

    for event in events:
        # Modify: Shift date forward
        new_date = event.date + timedelta(weeks=delay_weeks)

        modified_event_data = {
            "id": event.id,
            "user_id": event.user_id,
            "date": str(new_date),
            "amount": str(event.amount),
            "direction": event.direction,
            "event_type": event.event_type,
            "category": event.category,
            "confidence": "medium",  # Reduced confidence
            "confidence_reason": f"payment_delayed_{delay_weeks}w",
            "is_recurring": event.is_recurring,
            "recurrence_pattern": event.recurrence_pattern,
            "client_id": event.client_id,
            "bucket_id": event.bucket_id,
        }

        scenario_event = models.ScenarioEvent(
            scenario_id=scenario.id,
            original_event_id=event.id,
            operation="modify",
            event_data=modified_event_data,
            layer_attribution=scenario.name,
            change_reason=f"Payment delayed by {delay_weeks} weeks"
        )
        scenario_events.append(scenario_event)

    return scenario_events


async def _build_client_loss(
    db: AsyncSession,
    scenario: models.Scenario
) -> List[models.ScenarioEvent]:
    """Build client loss scenario."""
    scenario_events = []
    params = scenario.parameters
    scope = scenario.scope_config

    client_id = scope.get("client_id")
    effective_date = date.fromisoformat(params.get("effective_date"))

    # Get all future cash events for this client
    result = await db.execute(
        select(CashEvent).where(
            CashEvent.client_id == client_id,
            CashEvent.date >= effective_date,
            CashEvent.direction == "in"
        )
    )
    events = result.scalars().all()

    for event in events:
        scenario_event = models.ScenarioEvent(
            scenario_id=scenario.id,
            original_event_id=event.id,
            operation="delete",
            event_data={"id": event.id, "deleted": True},
            layer_attribution=scenario.name,
            change_reason=f"Client lost effective {effective_date}"
        )
        scenario_events.append(scenario_event)

    return scenario_events


async def _build_client_gain(
    db: AsyncSession,
    scenario: models.Scenario
) -> List[models.ScenarioEvent]:
    """Build client gain scenario."""
    scenario_events = []
    params = scenario.parameters

    # Handle multiple parameter name aliases
    date_str = params.get("start_date") or params.get("effective_date")
    if date_str:
        if isinstance(date_str, str):
            start_date = date.fromisoformat(date_str)
        else:
            start_date = date_str
    else:
        start_date = date.today() + timedelta(weeks=2)

    monthly_amount = Decimal(str(params.get("monthly_amount") or params.get("monthly_revenue") or params.get("amount") or 0))
    frequency = params.get("frequency", "monthly")

    # Generate new cash-in events for 13 weeks
    forecast_end = date.today() + timedelta(weeks=13)
    current_date = start_date

    while current_date <= forecast_end:
        event_data = {
            "user_id": scenario.user_id,
            "date": str(current_date),
            "amount": str(monthly_amount),
            "direction": "in",
            "event_type": "expected_revenue",
            "category": "new_client",
            "confidence": "medium",
            "confidence_reason": "scenario_projection",
            "is_recurring": True,
            "recurrence_pattern": frequency,
        }

        scenario_event = models.ScenarioEvent(
            scenario_id=scenario.id,
            original_event_id=None,
            operation="add",
            event_data=event_data,
            layer_attribution=scenario.name,
            change_reason=f"New client starting {start_date}"
        )
        scenario_events.append(scenario_event)

        # Move to next period
        if frequency == "monthly":
            current_date += timedelta(days=30)
        elif frequency == "weekly":
            current_date += timedelta(weeks=1)
        else:
            break

    return scenario_events


async def _build_client_change(
    db: AsyncSession,
    scenario: models.Scenario
) -> List[models.ScenarioEvent]:
    """Build client change (upsell/downsell) scenario."""
    scenario_events = []
    params = scenario.parameters
    scope = scenario.scope_config

    client_id = scope.get("client_id")
    delta_amount = Decimal(str(params.get("delta_amount", 0)))
    effective_date = date.fromisoformat(params.get("effective_date"))

    # Get future events for this client
    result = await db.execute(
        select(CashEvent).where(
            CashEvent.client_id == client_id,
            CashEvent.date >= effective_date,
            CashEvent.direction == "in"
        )
    )
    events = result.scalars().all()

    for event in events:
        new_amount = event.amount + delta_amount

        modified_event_data = {
            "id": event.id,
            "user_id": event.user_id,
            "date": str(event.date),
            "amount": str(new_amount),
            "direction": event.direction,
            "event_type": event.event_type,
            "category": event.category,
            "confidence": event.confidence,
            "confidence_reason": f"client_change_{delta_amount}",
            "is_recurring": event.is_recurring,
            "recurrence_pattern": event.recurrence_pattern,
            "client_id": event.client_id,
        }

        change_type = "upsell" if delta_amount > 0 else "downsell"
        scenario_event = models.ScenarioEvent(
            scenario_id=scenario.id,
            original_event_id=event.id,
            operation="modify",
            event_data=modified_event_data,
            layer_attribution=scenario.name,
            change_reason=f"Client {change_type} by ${delta_amount}"
        )
        scenario_events.append(scenario_event)

    return scenario_events


async def _build_hiring(
    db: AsyncSession,
    scenario: models.Scenario
) -> List[models.ScenarioEvent]:
    """Build hiring scenario."""
    scenario_events = []
    params = scenario.parameters

    # Handle multiple parameter name aliases
    date_str = params.get("start_date") or params.get("effective_date")
    if date_str:
        if isinstance(date_str, str):
            start_date = date.fromisoformat(date_str)
        else:
            start_date = date_str
    else:
        start_date = date.today() + timedelta(weeks=2)

    monthly_cost = Decimal(str(params.get("monthly_cost") or params.get("monthly_salary") or params.get("amount") or 0))
    onboarding_costs = params.get("onboarding_costs")

    # Add onboarding cost if specified
    if onboarding_costs:
        onboarding_event_data = {
            "user_id": scenario.user_id,
            "date": str(start_date),
            "amount": str(onboarding_costs),
            "direction": "out",
            "event_type": "expected_expense",
            "category": "payroll_onboarding",
            "confidence": "high",
            "confidence_reason": "scenario_projection",
            "is_recurring": False,
        }

        scenario_events.append(models.ScenarioEvent(
            scenario_id=scenario.id,
            original_event_id=None,
            operation="add",
            event_data=onboarding_event_data,
            layer_attribution=scenario.name,
            change_reason="One-time onboarding costs"
        ))

    # Add recurring payroll events
    forecast_end = date.today() + timedelta(weeks=13)
    current_date = start_date

    while current_date <= forecast_end:
        payroll_event_data = {
            "user_id": scenario.user_id,
            "date": str(current_date),
            "amount": str(monthly_cost),
            "direction": "out",
            "event_type": "expected_expense",
            "category": "payroll",
            "confidence": "high",
            "confidence_reason": "scenario_projection",
            "is_recurring": True,
            "recurrence_pattern": "monthly",
        }

        scenario_events.append(models.ScenarioEvent(
            scenario_id=scenario.id,
            original_event_id=None,
            operation="add",
            event_data=payroll_event_data,
            layer_attribution=scenario.name,
            change_reason=f"New hire starting {start_date}"
        ))

        current_date += timedelta(days=30)

    return scenario_events


async def _build_firing(
    db: AsyncSession,
    scenario: models.Scenario
) -> List[models.ScenarioEvent]:
    """Build firing scenario."""
    scenario_events = []
    params = scenario.parameters
    scope = scenario.scope_config

    # Handle end_date - required parameter
    end_date_str = params.get("end_date") or params.get("effective_date")
    if not end_date_str:
        # Default to 2 weeks from today if not specified
        end_date = date.today() + timedelta(weeks=2)
    elif isinstance(end_date_str, str):
        end_date = date.fromisoformat(end_date_str)
    else:
        end_date = end_date_str

    severance = params.get("severance_amount")
    bucket_id = scope.get("bucket_id")

    # Delete future payroll events
    if bucket_id:
        result = await db.execute(
            select(CashEvent).where(
                CashEvent.bucket_id == bucket_id,
                CashEvent.date >= end_date,
                CashEvent.category == "payroll"
            )
        )
        events = result.scalars().all()

        for event in events:
            scenario_events.append(models.ScenarioEvent(
                scenario_id=scenario.id,
                original_event_id=event.id,
                operation="delete",
                event_data={"id": event.id, "deleted": True},
                layer_attribution=scenario.name,
                change_reason=f"Employee terminated {end_date}"
            ))

    # Add severance if specified
    if severance:
        severance_event_data = {
            "user_id": scenario.user_id,
            "date": str(end_date),
            "amount": str(severance),
            "direction": "out",
            "event_type": "expected_expense",
            "category": "severance",
            "confidence": "high",
            "confidence_reason": "scenario_projection",
            "is_recurring": False,
        }

        scenario_events.append(models.ScenarioEvent(
            scenario_id=scenario.id,
            original_event_id=None,
            operation="add",
            event_data=severance_event_data,
            layer_attribution=scenario.name,
            change_reason="Severance payment"
        ))

    return scenario_events


async def _build_contractor_gain(
    db: AsyncSession,
    scenario: models.Scenario
) -> List[models.ScenarioEvent]:
    """Build contractor gain scenario."""
    return await _build_contractor_change(db, scenario, is_gain=True)


async def _build_contractor_loss(
    db: AsyncSession,
    scenario: models.Scenario
) -> List[models.ScenarioEvent]:
    """Build contractor loss scenario."""
    return await _build_contractor_change(db, scenario, is_gain=False)


async def _build_contractor_change(
    db: AsyncSession,
    scenario: models.Scenario,
    is_gain: bool
) -> List[models.ScenarioEvent]:
    """Build contractor gain/loss scenario."""
    scenario_events = []
    params = scenario.parameters

    # Handle multiple parameter name aliases
    date_str = (
        params.get("start_or_end_date") or
        params.get("start_date") or
        params.get("end_date") or
        params.get("effective_date")
    )
    if date_str:
        if isinstance(date_str, str):
            start_or_end_date = date.fromisoformat(date_str)
        else:
            start_or_end_date = date_str
    else:
        start_or_end_date = date.today() + timedelta(weeks=2)

    monthly_estimate = Decimal(str(params.get("monthly_estimate") or params.get("amount") or 0))

    if is_gain:
        # Add new contractor expenses
        forecast_end = date.today() + timedelta(weeks=13)
        current_date = start_or_end_date

        while current_date <= forecast_end:
            event_data = {
                "user_id": scenario.user_id,
                "date": str(current_date),
                "amount": str(monthly_estimate),
                "direction": "out",
                "event_type": "expected_expense",
                "category": "contractors",
                "confidence": "medium",
                "confidence_reason": "scenario_projection",
                "is_recurring": True,
                "recurrence_pattern": "monthly",
            }

            scenario_events.append(models.ScenarioEvent(
                scenario_id=scenario.id,
                original_event_id=None,
                operation="add",
                event_data=event_data,
                layer_attribution=scenario.name,
                change_reason=f"New contractor starting {start_or_end_date}"
            ))

            current_date += timedelta(days=30)
    else:
        # Remove contractor expenses (would need bucket_id in scope_config)
        bucket_id = scenario.scope_config.get("bucket_id")
        if bucket_id:
            result = await db.execute(
                select(CashEvent).where(
                    CashEvent.bucket_id == bucket_id,
                    CashEvent.date >= start_or_end_date,
                    CashEvent.category == "contractors"
                )
            )
            events = result.scalars().all()

            for event in events:
                scenario_events.append(models.ScenarioEvent(
                    scenario_id=scenario.id,
                    original_event_id=event.id,
                    operation="delete",
                    event_data={"id": event.id, "deleted": True},
                    layer_attribution=scenario.name,
                    change_reason=f"Contractor ended {start_or_end_date}"
                ))

    return scenario_events


async def _build_expense_increase(
    db: AsyncSession,
    scenario: models.Scenario
) -> List[models.ScenarioEvent]:
    """Build expense increase scenario."""
    return await _build_expense_change(db, scenario, is_increase=True)


async def _build_expense_decrease(
    db: AsyncSession,
    scenario: models.Scenario
) -> List[models.ScenarioEvent]:
    """Build expense decrease scenario."""
    return await _build_expense_change(db, scenario, is_increase=False)


async def _build_expense_change(
    db: AsyncSession,
    scenario: models.Scenario,
    is_increase: bool
) -> List[models.ScenarioEvent]:
    """Build expense increase/decrease scenario."""
    scenario_events = []
    params = scenario.parameters

    amount = Decimal(str(params.get("amount") or params.get("monthly_estimate") or 0))

    # Handle multiple parameter name aliases
    date_str = params.get("effective_date") or params.get("end_date") or params.get("start_date")
    if date_str:
        if isinstance(date_str, str):
            effective_date = date.fromisoformat(date_str)
        else:
            effective_date = date_str
    else:
        effective_date = date.today() + timedelta(weeks=2)

    is_recurring = params.get("is_recurring", True)
    category = params.get("category", "other")

    if is_increase:
        # Add new expense events
        if is_recurring:
            forecast_end = date.today() + timedelta(weeks=13)
            current_date = effective_date

            while current_date <= forecast_end:
                event_data = {
                    "user_id": scenario.user_id,
                    "date": str(current_date),
                    "amount": str(amount),
                    "direction": "out",
                    "event_type": "expected_expense",
                    "category": category,
                    "confidence": "high",
                    "confidence_reason": "scenario_projection",
                    "is_recurring": True,
                    "recurrence_pattern": "monthly",
                }

                scenario_events.append(models.ScenarioEvent(
                    scenario_id=scenario.id,
                    original_event_id=None,
                    operation="add",
                    event_data=event_data,
                    layer_attribution=scenario.name,
                    change_reason=f"New recurring expense starting {effective_date}"
                ))

                current_date += timedelta(days=30)
        else:
            # One-time expense
            event_data = {
                "user_id": scenario.user_id,
                "date": str(effective_date),
                "amount": str(amount),
                "direction": "out",
                "event_type": "expected_expense",
                "category": category,
                "confidence": "high",
                "confidence_reason": "scenario_projection",
                "is_recurring": False,
            }

            scenario_events.append(models.ScenarioEvent(
                scenario_id=scenario.id,
                original_event_id=None,
                operation="add",
                event_data=event_data,
                layer_attribution=scenario.name,
                change_reason=f"One-time expense on {effective_date}"
            ))
    else:
        # Decrease/remove expense (would need bucket_id)
        bucket_id = scenario.scope_config.get("bucket_id")
        if bucket_id:
            result = await db.execute(
                select(CashEvent).where(
                    CashEvent.bucket_id == bucket_id,
                    CashEvent.date >= effective_date
                )
            )
            events = result.scalars().all()

            for event in events:
                # Could modify to reduce or delete entirely
                scenario_events.append(models.ScenarioEvent(
                    scenario_id=scenario.id,
                    original_event_id=event.id,
                    operation="delete",
                    event_data={"id": event.id, "deleted": True},
                    layer_attribution=scenario.name,
                    change_reason=f"Expense removed from {effective_date}"
                ))

    return scenario_events


async def _build_payment_delay_out(
    db: AsyncSession,
    scenario: models.Scenario
) -> List[models.ScenarioEvent]:
    """Build outgoing payment delay scenario."""
    scenario_events = []
    params = scenario.parameters

    delay_weeks = params.get("delay_weeks") or 2
    if isinstance(delay_weeks, str):
        delay_weeks = int(delay_weeks) if delay_weeks else 2
    delay_weeks = int(delay_weeks) if delay_weeks else 2

    event_ids = params.get("event_ids", [])
    amount = Decimal(str(params.get("amount") or 0))

    # If no specific events provided but amount given, create synthetic delay effect
    if not event_ids and amount > 0:
        # Model the cash flow timing benefit of delaying a payment
        today = date.today()
        delay_date = today + timedelta(weeks=delay_weeks)

        # Positive cash impact today (money stays in account longer)
        event_data = {
            "user_id": scenario.user_id,
            "date": str(today),
            "amount": str(amount),
            "direction": "in",  # Effective cash benefit
            "event_type": "payment_delay_benefit",
            "category": "timing_adjustment",
            "confidence": "high",
            "confidence_reason": "scenario_payment_delay",
            "is_recurring": False,
        }
        scenario_events.append(models.ScenarioEvent(
            scenario_id=scenario.id,
            original_event_id=None,
            operation="add",
            event_data=event_data,
            layer_attribution=scenario.name,
            change_reason=f"Cash preserved by delaying vendor payment {delay_weeks} weeks"
        ))

        # Negative cash impact when payment eventually goes out
        deferred_event_data = {
            "user_id": scenario.user_id,
            "date": str(delay_date),
            "amount": str(amount),
            "direction": "out",
            "event_type": "deferred_payment",
            "category": "timing_adjustment",
            "confidence": "high",
            "confidence_reason": "scenario_payment_delay",
            "is_recurring": False,
        }
        scenario_events.append(models.ScenarioEvent(
            scenario_id=scenario.id,
            original_event_id=None,
            operation="add",
            event_data=deferred_event_data,
            layer_attribution=scenario.name,
            change_reason=f"Deferred payment due in {delay_weeks} weeks"
        ))

        return scenario_events

    for event_id in event_ids:
        result = await db.execute(
            select(CashEvent).where(CashEvent.id == event_id)
        )
        event = result.scalar_one_or_none()
        if not event or event.direction != "out":
            continue

        # Shift payment date forward
        new_date = event.date + timedelta(weeks=delay_weeks)

        modified_event_data = {
            "id": event.id,
            "user_id": event.user_id,
            "date": str(new_date),
            "amount": str(event.amount),
            "direction": event.direction,
            "event_type": event.event_type,
            "category": event.category,
            "confidence": event.confidence,
            "confidence_reason": f"payment_delayed_{delay_weeks}w_out",
            "is_recurring": event.is_recurring,
            "recurrence_pattern": event.recurrence_pattern,
            "bucket_id": event.bucket_id,
        }

        scenario_event = models.ScenarioEvent(
            scenario_id=scenario.id,
            original_event_id=event.id,
            operation="modify",
            event_data=modified_event_data,
            layer_attribution=scenario.name,
            change_reason=f"Vendor payment delayed by {delay_weeks} weeks"
        )
        scenario_events.append(scenario_event)

    return scenario_events


async def compute_scenario_forecast(
    db: AsyncSession,
    user_id: str,
    scenario_id: str
) -> Dict[str, Any]:
    """
    Compute forecast with scenario overlay.

    Returns both base and scenario forecasts with delta analysis.
    """
    # Get base forecast
    base_forecast = await calculate_13_week_forecast(db, user_id)

    # Get scenario and its events
    result = await db.execute(
        select(models.Scenario).where(models.Scenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise ValueError(f"Scenario {scenario_id} not found")

    # Get scenario events
    result = await db.execute(
        select(models.ScenarioEvent).where(
            models.ScenarioEvent.scenario_id == scenario_id
        )
    )
    scenario_events = result.scalars().all()

    # Build modified event list
    modified_events = await _apply_scenario_layer(db, user_id, scenario_events)

    # Compute scenario forecast with modified events
    scenario_forecast = await _compute_forecast_with_events(
        db, user_id, modified_events
    )

    # Calculate deltas
    deltas = _calculate_forecast_deltas(base_forecast, scenario_forecast)

    return {
        "base_forecast": base_forecast,
        "scenario_forecast": scenario_forecast,
        "deltas": deltas,
        "scenario": {
            "id": scenario.id,
            "name": scenario.name,
            "type": scenario.scenario_type,
        }
    }


async def _apply_scenario_layer(
    db: AsyncSession,
    user_id: str,
    scenario_events: List[models.ScenarioEvent]
) -> List[Any]:
    """Apply scenario modifications to create modified event list."""
    # Get all base events
    result = await db.execute(
        select(CashEvent).where(
            CashEvent.user_id == user_id,
            CashEvent.date >= date.today()
        ).order_by(CashEvent.date)
    )
    base_events = result.scalars().all()

    # Convert to dict for easy manipulation
    events_dict = {event.id: event for event in base_events}

    # Apply scenario modifications
    added_events = []

    for sc_event in scenario_events:
        if sc_event.operation == "modify":
            # Update existing event with modified data
            if sc_event.original_event_id in events_dict:
                event_data = sc_event.event_data
                # Create a mock object with the modified data
                class MockEvent:
                    def __init__(self, data, event_id=None):
                        self.id = event_id or data.get("id", f"mock_{secrets.token_hex(4)}")
                        self.date = datetime.fromisoformat(data["date"]).date() if isinstance(data["date"], str) else data["date"]
                        self.amount = Decimal(str(data["amount"]))
                        self.direction = data["direction"]
                        self.event_type = data.get("event_type", "manual")
                        self.category = data.get("category")
                        self.confidence = data.get("confidence", "medium")

                events_dict[sc_event.original_event_id] = MockEvent(event_data, sc_event.original_event_id)

        elif sc_event.operation == "delete":
            # Remove event
            if sc_event.original_event_id in events_dict:
                del events_dict[sc_event.original_event_id]

        elif sc_event.operation == "add":
            # Add new event as mock object
            event_data = sc_event.event_data
            class MockEvent:
                def __init__(self, data, event_id=None):
                    self.id = event_id or data.get("id", f"mock_{secrets.token_hex(4)}")
                    self.date = datetime.fromisoformat(data["date"]).date() if isinstance(data["date"], str) else data["date"]
                    self.amount = Decimal(str(data["amount"]))
                    self.direction = data["direction"]
                    self.event_type = data.get("event_type", "manual")
                    self.category = data.get("category")
                    self.confidence = data.get("confidence", "medium")

            added_events.append(MockEvent(event_data))

    # Combine all events
    all_events = list(events_dict.values()) + added_events

    return all_events


async def _compute_forecast_with_events(
    db: AsyncSession,
    user_id: str,
    events: List[Any]
) -> Dict[str, Any]:
    """Compute 13-week forecast using provided event list."""
    # Get starting cash
    result = await db.execute(
        select(func.sum(CashAccount.balance))
        .where(CashAccount.user_id == user_id)
    )
    starting_cash = result.scalar() or Decimal("0")

    # Get forecast start date (today)
    forecast_start = date.today()

    # Build 13-week forecast
    weeks = []
    current_balance = starting_cash

    for week_num in range(1, 14):
        week_start = forecast_start + timedelta(days=(week_num - 1) * 7)
        week_end = week_start + timedelta(days=6)

        # Filter events for this week
        week_events = [
            e for e in events
            if week_start <= e.date <= week_end
        ]

        # Calculate cash in/out
        cash_in = sum(
            e.amount for e in week_events if e.direction == "in"
        )
        cash_out = sum(
            e.amount for e in week_events if e.direction == "out"
        )

        net_change = cash_in - cash_out
        ending_balance = current_balance + net_change

        weeks.append({
            "week_number": week_num,
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "starting_balance": str(current_balance),
            "cash_in": str(cash_in),
            "cash_out": str(cash_out),
            "net_change": str(net_change),
            "ending_balance": str(ending_balance),
            "events": [
                {
                    "id": e.id,
                    "date": e.date.isoformat(),
                    "amount": str(e.amount),
                    "direction": e.direction,
                    "event_type": e.event_type,
                    "category": e.category,
                    "confidence": e.confidence,
                }
                for e in sorted(week_events, key=lambda x: x.amount, reverse=True)[:10]
            ]
        })

        current_balance = ending_balance

    # Calculate summary statistics
    balances = [Decimal(w["ending_balance"]) for w in weeks]
    lowest_balance = min(balances)
    lowest_week = balances.index(lowest_balance) + 1

    total_cash_in = sum(Decimal(w["cash_in"]) for w in weeks)
    total_cash_out = sum(Decimal(w["cash_out"]) for w in weeks)

    # Calculate runway (weeks until cash hits 0)
    runway_weeks = 13
    for i, balance in enumerate(balances):
        if balance <= 0:
            runway_weeks = i + 1
            break

    return {
        "starting_cash": str(starting_cash),
        "forecast_start_date": forecast_start.isoformat(),
        "weeks": weeks,
        "summary": {
            "lowest_cash_week": lowest_week,
            "lowest_cash_amount": str(lowest_balance),
            "total_cash_in": str(total_cash_in),
            "total_cash_out": str(total_cash_out),
            "runway_weeks": runway_weeks,
        }
    }


def _calculate_forecast_deltas(
    base: Dict[str, Any],
    scenario: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate week-by-week deltas between base and scenario."""
    deltas = {
        "weeks": [],
        "summary": {}
    }

    base_weeks = base.get("weeks", [])
    scenario_weeks = scenario.get("weeks", [])

    for i, (base_week, sc_week) in enumerate(zip(base_weeks, scenario_weeks)):
        delta_week = {
            "week_number": base_week["week_number"],
            "delta_cash_in": Decimal(sc_week["cash_in"]) - Decimal(base_week["cash_in"]),
            "delta_cash_out": Decimal(sc_week["cash_out"]) - Decimal(base_week["cash_out"]),
            "delta_ending_balance": Decimal(sc_week["ending_balance"]) - Decimal(base_week["ending_balance"]),
        }
        deltas["weeks"].append(delta_week)

    # Summary deltas
    base_summary = base.get("summary", {})
    sc_summary = scenario.get("summary", {})

    deltas["summary"] = {
        "delta_total_cash_in": Decimal(sc_summary.get("total_cash_in", 0)) - Decimal(base_summary.get("total_cash_in", 0)),
        "delta_total_cash_out": Decimal(sc_summary.get("total_cash_out", 0)) - Decimal(base_summary.get("total_cash_out", 0)),
        "delta_runway_weeks": sc_summary.get("runway_weeks", 0) - base_summary.get("runway_weeks", 0),
    }

    return deltas
