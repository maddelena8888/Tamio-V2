"""
Payment Delay (Cash In) Handler.

Implements the Mermaid decision tree:
1. Select scope (client + events)
2. Input delay duration
3. Handle partial payment (split event)
4. Confidence downshift
5. Optional linked changes (delay vendors / reduce discretionary)
"""

from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, timedelta
from decimal import Decimal

from app.scenarios.pipeline.handlers.base import BaseScenarioHandler, generate_id
from app.scenarios.pipeline.types import (
    ScenarioDefinition,
    ScenarioDelta,
    EventDelta,
)
from app.data.models import CashEvent


class PaymentDelayInHandler(BaseScenarioHandler):
    """Handler for Payment Delay (Cash In) scenarios."""

    def required_params(self) -> List[str]:
        return [
            "scope.client_ids",
            "delay_weeks",
        ]

    def linked_prompt_types(self) -> List[str]:
        return [
            "delay_vendor_payments",
            "reduce_discretionary",
        ]

    async def apply(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
    ) -> ScenarioDelta:
        """
        Apply payment delay to cash-in events.

        Steps per Mermaid:
        1. Get affected events (by client or event_ids)
        2. Shift dates forward by delay_weeks
        3. If partial payment, split into actual receipt + remaining shifted
        4. Downshift confidence
        5. Apply linked changes if configured
        """
        delta = ScenarioDelta(scenario_id=definition.scenario_id)
        params = definition.parameters
        scope = definition.scope

        delay_weeks = int(params.get("delay_weeks", 0))
        is_partial = params.get("is_partial", False)
        partial_pct = params.get("partial_payment_pct", 0) if is_partial else 0

        # Get events to delay
        client_ids = scope.client_ids or []
        event_ids = scope.event_ids or []

        if event_ids:
            # Specific events provided
            result = await db.execute(
                select(CashEvent).where(
                    CashEvent.id.in_(event_ids),
                    CashEvent.direction == "in"
                )
            )
            events = list(result.scalars().all())
        elif client_ids:
            # All future events for the client
            result = await db.execute(
                select(CashEvent).where(
                    CashEvent.client_id.in_(client_ids),
                    CashEvent.date >= date.today(),
                    CashEvent.direction == "in"
                ).order_by(CashEvent.date)
            )
            events = list(result.scalars().all())
        else:
            events = []

        for event in events:
            if is_partial and partial_pct > 0:
                # Split event: paid portion (actual) + remaining (shifted)
                paid_amount = event.amount * Decimal(partial_pct) / Decimal(100)
                remaining_amount = event.amount - paid_amount

                # Actual receipt (paid portion - keep original date)
                actual_event_data = {
                    "id": generate_id("evt"),
                    "user_id": event.user_id,
                    "date": str(event.date),
                    "amount": str(paid_amount),
                    "direction": "in",
                    "event_type": "actual_receipt",
                    "category": event.category,
                    "confidence": "high",
                    "confidence_reason": "partial_payment_received",
                    "client_id": event.client_id,
                    "scenario_id": definition.scenario_id,
                }
                delta.created_events.append(self.create_event_delta(
                    scenario_id=definition.scenario_id,
                    operation="add",
                    event_data=actual_event_data,
                    change_reason=f"Partial payment ({partial_pct}%) received on original date",
                ))

                # Remaining expected (shifted)
                shifted_date = event.date + timedelta(weeks=delay_weeks)
                remaining_event_data = {
                    "id": event.id,
                    "user_id": event.user_id,
                    "date": str(shifted_date),
                    "amount": str(remaining_amount),
                    "direction": "in",
                    "event_type": "expected_revenue",
                    "category": event.category,
                    "confidence": "medium",  # Downshifted
                    "confidence_reason": f"payment_delayed_{delay_weeks}w_remaining",
                    "client_id": event.client_id,
                    "is_recurring": event.is_recurring,
                    "recurrence_pattern": event.recurrence_pattern,
                    "scenario_id": definition.scenario_id,
                }
                delta.updated_events.append(self.create_event_delta(
                    scenario_id=definition.scenario_id,
                    operation="modify",
                    event_data=remaining_event_data,
                    original_event_id=event.id,
                    change_reason=f"Remaining {100-partial_pct}% delayed by {delay_weeks} weeks",
                ))

            else:
                # Full delay - shift the entire payment
                new_date = event.date + timedelta(weeks=delay_weeks)

                modified_event_data = {
                    "id": event.id,
                    "user_id": event.user_id,
                    "date": str(new_date),
                    "amount": str(event.amount),
                    "direction": event.direction,
                    "event_type": event.event_type,
                    "category": event.category,
                    "confidence": "medium",  # Downshifted from original
                    "confidence_reason": f"payment_delayed_{delay_weeks}w",
                    "is_recurring": event.is_recurring,
                    "recurrence_pattern": event.recurrence_pattern,
                    "client_id": event.client_id,
                    "bucket_id": event.bucket_id,
                    "scenario_id": definition.scenario_id,
                }

                delta.updated_events.append(self.create_event_delta(
                    scenario_id=definition.scenario_id,
                    operation="modify",
                    event_data=modified_event_data,
                    original_event_id=event.id,
                    change_reason=f"Payment delayed by {delay_weeks} weeks",
                ))

        # Apply linked changes if configured
        linked_adjustment = params.get("linked_adjustment_type")

        if linked_adjustment == "delay_vendors":
            # Would delay vendor payments - create linked scenario
            # This would be handled by linked change processing
            pass
        elif linked_adjustment == "reduce_discretionary":
            # Would reduce discretionary spending
            # This would be handled by linked change processing
            pass

        # Update summary
        delta.total_events_affected = len(delta.updated_events) + len(delta.created_events)
        delta.net_cash_impact = Decimal("0")  # Delay doesn't change total, just timing

        return delta
