"""
Payment Delay (Cash Out) Handler.

Implements the Mermaid decision tree:
1. Select vendor/obligation
2. Input delay duration
3. Handle partial payment (split event)
4. Tag as delayed outflow
5. Optional clustering risk mitigation
"""

from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, timedelta
from decimal import Decimal

from app.scenarios.pipeline.handlers.base import BaseScenarioHandler, generate_id
from app.scenarios.pipeline.types import (
    ScenarioDefinition,
    ScenarioDelta,
)
from app.data.models import CashEvent


class PaymentDelayOutHandler(BaseScenarioHandler):
    """Handler for Payment Delay (Cash Out) scenarios."""

    def required_params(self) -> List[str]:
        return [
            "delay_weeks",
        ]

    def linked_prompt_types(self) -> List[str]:
        return [
            "catch_up_schedule",
            "spread_payments",
        ]

    async def apply(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
    ) -> ScenarioDelta:
        """
        Apply payment delay to cash-out events.

        Steps per Mermaid:
        1. Get affected events
        2. Shift dates forward by delay_weeks
        3. If partial, split into actual + remaining shifted
        4. Apply clustering risk mitigation if configured
        """
        delta = ScenarioDelta(scenario_id=definition.scenario_id)
        params = definition.parameters
        scope = definition.scope

        delay_weeks = int(params.get("delay_weeks", 0))
        is_partial = params.get("is_partial", False)
        partial_pct = params.get("partial_payment_pct", 0) if is_partial else 0

        # Get events to delay
        bucket_ids = scope.bucket_ids or []
        event_ids = scope.event_ids or []

        if event_ids:
            result = await db.execute(
                select(CashEvent).where(
                    CashEvent.id.in_(event_ids),
                    CashEvent.direction == "out"
                )
            )
            events = list(result.scalars().all())
        elif bucket_ids:
            result = await db.execute(
                select(CashEvent).where(
                    CashEvent.bucket_id.in_(bucket_ids),
                    CashEvent.date >= date.today(),
                    CashEvent.direction == "out"
                ).order_by(CashEvent.date)
            )
            events = list(result.scalars().all())
        else:
            events = []

        for event in events:
            if is_partial and partial_pct > 0:
                # Split: paid portion now + remaining shifted
                paid_amount = event.amount * Decimal(partial_pct) / Decimal(100)
                remaining_amount = event.amount - paid_amount

                # Actual payment (paid portion)
                actual_event_data = {
                    "id": generate_id("evt"),
                    "user_id": event.user_id,
                    "date": str(event.date),
                    "amount": str(paid_amount),
                    "direction": "out",
                    "event_type": "actual_payment",
                    "category": event.category,
                    "confidence": "high",
                    "confidence_reason": "partial_payment_made",
                    "bucket_id": event.bucket_id,
                    "scenario_id": definition.scenario_id,
                }
                delta.created_events.append(self.create_event_delta(
                    scenario_id=definition.scenario_id,
                    operation="add",
                    event_data=actual_event_data,
                    change_reason=f"Partial payment ({partial_pct}%) made on original date",
                ))

                # Remaining (shifted)
                shifted_date = event.date + timedelta(weeks=delay_weeks)
                remaining_event_data = {
                    "id": event.id,
                    "user_id": event.user_id,
                    "date": str(shifted_date),
                    "amount": str(remaining_amount),
                    "direction": "out",
                    "event_type": "expected_expense",
                    "category": event.category,
                    "confidence": "medium",
                    "confidence_reason": f"payment_delayed_{delay_weeks}w_remaining",
                    "bucket_id": event.bucket_id,
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
                # Full delay
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
                    "scenario_id": definition.scenario_id,
                }

                delta.updated_events.append(self.create_event_delta(
                    scenario_id=definition.scenario_id,
                    operation="modify",
                    event_data=modified_event_data,
                    original_event_id=event.id,
                    change_reason=f"Vendor payment delayed by {delay_weeks} weeks",
                ))

        # Apply clustering risk mitigation if configured
        has_clustering_risk = params.get("linked_has_clustering_risk", False)
        mitigation_type = params.get("linked_mitigation_type")

        if has_clustering_risk and mitigation_type == "catch_up":
            # Create catch-up schedule: spread the delayed amount
            total_delayed = sum(
                Decimal(e.event_data["amount"])
                for e in delta.updated_events
                if e.operation == "modify"
            )

            if total_delayed > 0:
                # Split into 4 weekly catch-up payments
                catch_up_amount = total_delayed / Decimal("4")
                base_date = date.today() + timedelta(weeks=delay_weeks + 1)

                for week in range(4):
                    catch_up_date = base_date + timedelta(weeks=week)
                    event_data = {
                        "id": generate_id("evt"),
                        "user_id": definition.user_id,
                        "date": str(catch_up_date),
                        "amount": str(catch_up_amount),
                        "direction": "out",
                        "event_type": "expected_expense",
                        "category": "catch_up_payment",
                        "confidence": "medium",
                        "confidence_reason": "catch_up_schedule",
                        "scenario_id": definition.scenario_id,
                    }
                    delta.created_events.append(self.create_event_delta(
                        scenario_id=definition.scenario_id,
                        operation="add",
                        event_data=event_data,
                        linked_change_id="linked_catch_up",
                        change_reason=f"Catch-up payment {week+1}/4 for delayed payments",
                    ))

        elif has_clustering_risk and mitigation_type == "spread":
            # Spread future payments more evenly
            # This would require more complex logic to redistribute
            pass

        # Update summary
        delta.total_events_affected = len(delta.updated_events) + len(delta.created_events)
        delta.net_cash_impact = Decimal("0")  # Delay doesn't change total, just timing

        return delta
