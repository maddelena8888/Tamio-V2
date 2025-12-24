"""
Client Change Handler (Upsell/Downsell).

Implements the Mermaid decision tree:
1. Select client + affected agreements
2. Input change type (upsell/downsell/scope change)
3. Input delta amount + effective date
4. Modify future cash-in amounts
5. Prompt for cost base changes
6. Apply cost delta with lag
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


class ClientChangeHandler(BaseScenarioHandler):
    """Handler for Client Change (upsell/downsell) scenarios."""

    def required_params(self) -> List[str]:
        return [
            "scope.client_ids",
            "change_type",
            "delta_amount",
            "effective_date",
        ]

    def linked_prompt_types(self) -> List[str]:
        return [
            "contractors",
            "delivery",
            "tools",
        ]

    async def apply(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
    ) -> ScenarioDelta:
        """
        Apply client change to modify future revenue and optionally costs.

        Steps per Mermaid:
        1. Get future events for client from effective date
        2. Modify amounts by delta (positive for upsell, negative for downsell)
        3. If cost changes configured:
           a. Apply cost delta with optional lag
        """
        delta = ScenarioDelta(scenario_id=definition.scenario_id)
        params = definition.parameters
        scope = definition.scope

        client_ids = scope.client_ids or []
        change_type = params.get("change_type", "scope_change")
        delta_amount = Decimal(str(params.get("delta_amount", 0)))

        effective_date_str = params.get("effective_date")
        if isinstance(effective_date_str, str):
            effective_date = date.fromisoformat(effective_date_str)
        else:
            effective_date = effective_date_str or date.today()

        # Get future events for this client
        result = await db.execute(
            select(CashEvent).where(
                CashEvent.client_id.in_(client_ids),
                CashEvent.date >= effective_date,
                CashEvent.direction == "in"
            )
        )
        events = list(result.scalars().all())

        # Modify each event
        for event in events:
            new_amount = event.amount + delta_amount

            # Don't allow negative amounts
            if new_amount < 0:
                new_amount = Decimal("0")

            modified_event_data = {
                "id": event.id,
                "user_id": event.user_id,
                "date": str(event.date),
                "amount": str(new_amount),
                "direction": event.direction,
                "event_type": event.event_type,
                "category": event.category,
                "confidence": event.confidence,
                "confidence_reason": f"client_{change_type}_{delta_amount}",
                "is_recurring": event.is_recurring,
                "recurrence_pattern": event.recurrence_pattern,
                "client_id": event.client_id,
                "scenario_id": definition.scenario_id,
            }

            change_description = "increased" if delta_amount > 0 else "decreased"
            delta.updated_events.append(self.create_event_delta(
                scenario_id=definition.scenario_id,
                operation="modify",
                event_data=modified_event_data,
                original_event_id=event.id,
                change_reason=f"Client {change_type}: amount {change_description} by ${abs(delta_amount):.0f}",
            ))

        # Apply linked cost changes if configured
        cost_changes = params.get("linked_cost_changes", False)

        if cost_changes:
            cost_drivers = params.get("linked_cost_drivers", [])
            cost_delta = Decimal(str(params.get("linked_cost_delta", 0)))
            lag_weeks = int(params.get("linked_lag_weeks", 0))

            cost_effective_date = effective_date + timedelta(weeks=lag_weeks)

            # Map cost drivers to categories
            category_map = {
                "contractors": "contractors",
                "delivery": "other",
                "tools": "software",
            }

            for driver in cost_drivers:
                category = category_map.get(driver)
                if not category:
                    continue

                # Find expense buckets
                result = await db.execute(
                    select(ExpenseBucket).where(
                        ExpenseBucket.user_id == definition.user_id,
                        ExpenseBucket.category == category
                    )
                )
                buckets = list(result.scalars().all())

                for bucket in buckets:
                    # Find and modify future events
                    result = await db.execute(
                        select(CashEvent).where(
                            CashEvent.bucket_id == bucket.id,
                            CashEvent.date >= cost_effective_date,
                            CashEvent.direction == "out"
                        )
                    )
                    cost_events = list(result.scalars().all())

                    for event in cost_events:
                        new_amount = event.amount + cost_delta

                        if new_amount <= 0:
                            delta.deleted_event_ids.append(event.id)
                            delta.updated_events.append(self.create_event_delta(
                                scenario_id=definition.scenario_id,
                                operation="delete",
                                event_data={"id": event.id, "deleted": True},
                                original_event_id=event.id,
                                linked_change_id=f"linked_{driver}",
                                change_reason=f"{driver} cost removed due to client change",
                            ))
                        else:
                            modified_event_data = {
                                "id": event.id,
                                "user_id": event.user_id,
                                "date": str(event.date),
                                "amount": str(new_amount),
                                "direction": event.direction,
                                "event_type": event.event_type,
                                "category": event.category,
                                "bucket_id": event.bucket_id,
                                "scenario_id": definition.scenario_id,
                            }
                            delta.updated_events.append(self.create_event_delta(
                                scenario_id=definition.scenario_id,
                                operation="modify",
                                event_data=modified_event_data,
                                original_event_id=event.id,
                                linked_change_id=f"linked_{driver}",
                                change_reason=f"{driver} cost adjusted by ${cost_delta:.0f} due to client change",
                            ))

        # Update summary
        delta.total_events_affected = len(delta.updated_events)
        delta.net_cash_impact = delta_amount * len([e for e in delta.updated_events if e.operation == "modify"])

        return delta
