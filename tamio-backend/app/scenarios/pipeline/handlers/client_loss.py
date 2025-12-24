"""
Client Loss Handler.

Implements the Mermaid decision tree:
1. Select client(s) + effective end date
2. Remove all future cash-in events from end date
3. Mark agreement inactive
4. Prompt for cost reductions (contractors/tools/project)
5. Apply cost reductions with lag
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
    LinkedChangeType,
)
from app.data.models import CashEvent, ExpenseBucket


class ClientLossHandler(BaseScenarioHandler):
    """Handler for Client Loss scenarios."""

    def required_params(self) -> List[str]:
        return [
            "scope.client_ids",
            "effective_date",
        ]

    def linked_prompt_types(self) -> List[str]:
        return [
            "reduce_contractors",
            "reduce_tools",
            "reduce_project_costs",
        ]

    async def apply(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
    ) -> ScenarioDelta:
        """
        Apply client loss to remove future revenue and optionally reduce costs.

        Steps per Mermaid:
        1. Get all future cash-in events for client from effective date
        2. Delete/mark inactive all these events
        3. If linked cost reductions configured:
           a. Determine reduction amount and categories
           b. Apply with lag (0-4 weeks)
           c. Reduce future cash-out events
        """
        delta = ScenarioDelta(scenario_id=definition.scenario_id)
        params = definition.parameters
        scope = definition.scope

        client_ids = scope.client_ids or []
        effective_date_str = params.get("effective_date")
        if isinstance(effective_date_str, str):
            effective_date = date.fromisoformat(effective_date_str)
        else:
            effective_date = effective_date_str or date.today()

        # Step 1-2: Remove all future revenue events for this client
        result = await db.execute(
            select(CashEvent).where(
                CashEvent.client_id.in_(client_ids),
                CashEvent.date >= effective_date,
                CashEvent.direction == "in"
            )
        )
        revenue_events = list(result.scalars().all())

        total_revenue_lost = Decimal("0")
        for event in revenue_events:
            delta.deleted_event_ids.append(event.id)
            total_revenue_lost += event.amount

            # Track for audit
            delta.updated_events.append(self.create_event_delta(
                scenario_id=definition.scenario_id,
                operation="delete",
                event_data={"id": event.id, "deleted": True},
                original_event_id=event.id,
                change_reason=f"Client lost effective {effective_date}",
            ))

        # Step 3-5: Apply linked cost reductions if configured
        reduce_costs = params.get("linked_reduce_costs", False)

        if reduce_costs:
            cost_types = params.get("linked_cost_types", [])
            reduction_amount = Decimal(str(params.get("linked_reduction_amount", 0)))
            lag_weeks = int(params.get("linked_lag_weeks", 0))

            reduction_effective_date = effective_date + timedelta(weeks=lag_weeks)

            # Map cost types to categories
            category_map = {
                "contractors": "contractors",
                "tools": "software",
                "project_costs": "other",
            }

            for cost_type in cost_types:
                category = category_map.get(cost_type)
                if not category:
                    continue

                # Find expense buckets in this category
                result = await db.execute(
                    select(ExpenseBucket).where(
                        ExpenseBucket.user_id == definition.user_id,
                        ExpenseBucket.category == category
                    )
                )
                buckets = list(result.scalars().all())

                # Distribute reduction across buckets proportionally
                total_bucket_amount = sum(b.monthly_amount or 0 for b in buckets)
                if total_bucket_amount <= 0:
                    continue

                for bucket in buckets:
                    bucket_share = (bucket.monthly_amount / total_bucket_amount) if total_bucket_amount > 0 else 0
                    bucket_reduction = reduction_amount * Decimal(str(bucket_share))

                    # Find future events for this bucket and reduce/remove
                    result = await db.execute(
                        select(CashEvent).where(
                            CashEvent.bucket_id == bucket.id,
                            CashEvent.date >= reduction_effective_date,
                            CashEvent.direction == "out"
                        )
                    )
                    bucket_events = list(result.scalars().all())

                    for event in bucket_events:
                        new_amount = event.amount - bucket_reduction
                        if new_amount <= 0:
                            # Remove entirely
                            delta.deleted_event_ids.append(event.id)
                            delta.updated_events.append(self.create_event_delta(
                                scenario_id=definition.scenario_id,
                                operation="delete",
                                event_data={"id": event.id, "deleted": True},
                                original_event_id=event.id,
                                linked_change_id=f"linked_{cost_type}",
                                change_reason=f"{cost_type} reduced due to client loss (lag: {lag_weeks}w)",
                            ))
                        else:
                            # Reduce amount
                            modified_event_data = {
                                "id": event.id,
                                "user_id": event.user_id,
                                "date": str(event.date),
                                "amount": str(new_amount),
                                "direction": event.direction,
                                "event_type": event.event_type,
                                "category": event.category,
                                "confidence": event.confidence,
                                "bucket_id": event.bucket_id,
                                "scenario_id": definition.scenario_id,
                            }
                            delta.updated_events.append(self.create_event_delta(
                                scenario_id=definition.scenario_id,
                                operation="modify",
                                event_data=modified_event_data,
                                original_event_id=event.id,
                                linked_change_id=f"linked_{cost_type}",
                                change_reason=f"{cost_type} reduced by ${bucket_reduction:.0f}/mo due to client loss",
                            ))

        # Update summary
        delta.total_events_affected = len(delta.deleted_event_ids) + len(delta.updated_events)
        delta.net_cash_impact = -total_revenue_lost  # Negative impact from lost revenue

        return delta
