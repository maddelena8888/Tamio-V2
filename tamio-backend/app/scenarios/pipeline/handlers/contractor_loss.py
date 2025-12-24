"""
Contractor Loss Handler.

Implements the Mermaid decision tree:
1. Select contractor/bucket or linked client/project
2. Input end date or reduction %
3. Reduce/remove future contractor events
4. Optional linked revenue impact (delivery slowdown)
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
from app.data.models import CashEvent, ExpenseBucket


class ContractorLossHandler(BaseScenarioHandler):
    """Handler for Contractor Loss scenarios."""

    def required_params(self) -> List[str]:
        return [
            "end_date",
            "monthly_estimate",
        ]

    def linked_prompt_types(self) -> List[str]:
        return [
            "client_change",
            "delayed_milestones",
        ]

    async def apply(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
    ) -> ScenarioDelta:
        """
        Apply contractor loss to remove contractor expense events.

        Steps per Mermaid:
        1. Find contractor events by bucket or matching amount
        2. Remove/reduce future events from end date
        3. Apply linked revenue impact if configured
        """
        delta = ScenarioDelta(scenario_id=definition.scenario_id)
        params = definition.parameters
        scope = definition.scope

        end_date_str = params.get("end_date")
        if isinstance(end_date_str, str):
            end_date = date.fromisoformat(end_date_str)
        else:
            end_date = end_date_str or date.today()

        monthly_estimate = Decimal(str(params.get("monthly_estimate", 0)))

        # Find contractor events to remove
        bucket_ids = scope.bucket_ids or []

        if bucket_ids:
            # Specific bucket provided
            result = await db.execute(
                select(CashEvent).where(
                    CashEvent.bucket_id.in_(bucket_ids),
                    CashEvent.date >= end_date,
                    CashEvent.category == "contractors"
                )
            )
            contractor_events = list(result.scalars().all())
        else:
            # Find by matching amount
            result = await db.execute(
                select(CashEvent).where(
                    CashEvent.user_id == definition.user_id,
                    CashEvent.date >= end_date,
                    CashEvent.category == "contractors",
                    CashEvent.direction == "out"
                )
            )
            all_contractors = list(result.scalars().all())

            # Match events with similar amount
            tolerance = monthly_estimate * Decimal("0.15")
            contractor_events = [
                e for e in all_contractors
                if abs(e.amount - monthly_estimate) <= tolerance
            ]

        # Remove contractor events
        for event in contractor_events:
            delta.deleted_event_ids.append(event.id)
            delta.updated_events.append(self.create_event_delta(
                scenario_id=definition.scenario_id,
                operation="delete",
                event_data={"id": event.id, "deleted": True},
                original_event_id=event.id,
                change_reason=f"Contractor ended effective {end_date}",
            ))

        # Apply linked revenue impact if configured
        affects_delivery = params.get("linked_affects_delivery", False)

        if affects_delivery:
            revenue_impact = Decimal(str(params.get("linked_revenue_impact", 0)))

            if revenue_impact > 0:
                forecast_end = date.today() + timedelta(weeks=13)

                # Note: This models potential delayed milestones or reduced revenue
                # In practice, would modify specific client events
                current_date = end_date
                while current_date <= forecast_end:
                    event_data = {
                        "id": generate_id("evt"),
                        "user_id": definition.user_id,
                        "date": str(current_date),
                        "amount": str(-revenue_impact),  # Negative to reduce
                        "direction": "in",
                        "event_type": "revenue_adjustment",
                        "category": "delivery_impact",
                        "confidence": "low",
                        "confidence_reason": "scenario_contractor_loss_impact",
                        "scenario_id": definition.scenario_id,
                    }
                    delta.created_events.append(self.create_event_delta(
                        scenario_id=definition.scenario_id,
                        operation="add",
                        event_data=event_data,
                        linked_change_id="linked_delivery_impact",
                        change_reason="Revenue impact from contractor loss",
                    ))

                    # Move to next month
                    if current_date.month == 12:
                        current_date = date(current_date.year + 1, 1, current_date.day)
                    else:
                        try:
                            current_date = date(current_date.year, current_date.month + 1, current_date.day)
                        except ValueError:
                            current_date = date(current_date.year, current_date.month + 1, 28)

        # Update summary
        delta.total_events_affected = len(delta.deleted_event_ids) + len(delta.created_events)
        delta.net_cash_impact = monthly_estimate * len(delta.deleted_event_ids)  # Positive: saving money

        return delta
