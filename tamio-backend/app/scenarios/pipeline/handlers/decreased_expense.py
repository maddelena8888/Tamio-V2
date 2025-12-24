"""
Decreased Expense Handler.

Implements the Mermaid decision tree:
1. Select obligation/expense to reduce
2. Input reduction amount + effective date
3. Handle termination logic (notice period + fee)
4. Reduce/remove future events
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


class DecreasedExpenseHandler(BaseScenarioHandler):
    """Handler for Decreased Expense scenarios."""

    def required_params(self) -> List[str]:
        return [
            "reduction_amount",
            "effective_date",
        ]

    def linked_prompt_types(self) -> List[str]:
        return [
            "termination_fee",
        ]

    async def apply(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
    ) -> ScenarioDelta:
        """
        Apply decreased expense to reduce/remove expense events.

        Steps per Mermaid:
        1. Handle termination fee if applicable
        2. Reduce or remove future expense events
        """
        delta = ScenarioDelta(scenario_id=definition.scenario_id)
        params = definition.parameters
        scope = definition.scope

        reduction_amount = Decimal(str(params.get("reduction_amount", 0)))

        effective_date_str = params.get("effective_date")
        if isinstance(effective_date_str, str):
            effective_date = date.fromisoformat(effective_date_str)
        else:
            effective_date = effective_date_str or date.today()

        has_termination_costs = params.get("has_termination_costs", False)
        termination_fee = Decimal(str(params.get("termination_fee", 0))) if has_termination_costs else Decimal("0")

        # Step 1: Add termination fee if applicable
        if termination_fee > 0:
            event_data = {
                "id": generate_id("evt"),
                "user_id": definition.user_id,
                "date": str(effective_date),
                "amount": str(termination_fee),
                "direction": "out",
                "event_type": "expected_expense",
                "category": "termination_fee",
                "confidence": "high",
                "confidence_reason": "scenario_termination_fee",
                "is_recurring": False,
                "scenario_id": definition.scenario_id,
            }
            delta.created_events.append(self.create_event_delta(
                scenario_id=definition.scenario_id,
                operation="add",
                event_data=event_data,
                change_reason="Termination fee for expense reduction",
            ))

        # Step 2: Find and reduce/remove expense events
        bucket_ids = scope.bucket_ids or []

        if bucket_ids:
            # Specific bucket provided
            result = await db.execute(
                select(CashEvent).where(
                    CashEvent.bucket_id.in_(bucket_ids),
                    CashEvent.date >= effective_date,
                    CashEvent.direction == "out"
                )
            )
            expense_events = list(result.scalars().all())
        else:
            # Find matching expense events by amount
            result = await db.execute(
                select(CashEvent).where(
                    CashEvent.user_id == definition.user_id,
                    CashEvent.date >= effective_date,
                    CashEvent.direction == "out"
                )
            )
            all_expenses = list(result.scalars().all())

            # Match events with amount >= reduction
            expense_events = [
                e for e in all_expenses
                if e.amount >= reduction_amount
            ][:10]  # Limit to first 10 matches

        for event in expense_events:
            new_amount = event.amount - reduction_amount

            if new_amount <= 0:
                # Remove entirely
                delta.deleted_event_ids.append(event.id)
                delta.updated_events.append(self.create_event_delta(
                    scenario_id=definition.scenario_id,
                    operation="delete",
                    event_data={"id": event.id, "deleted": True},
                    original_event_id=event.id,
                    change_reason=f"Expense removed effective {effective_date}",
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
                    "is_recurring": event.is_recurring,
                    "recurrence_pattern": event.recurrence_pattern,
                    "scenario_id": definition.scenario_id,
                }
                delta.updated_events.append(self.create_event_delta(
                    scenario_id=definition.scenario_id,
                    operation="modify",
                    event_data=modified_event_data,
                    original_event_id=event.id,
                    change_reason=f"Expense reduced by ${reduction_amount:.0f}",
                ))

        # Update summary
        delta.total_events_affected = len(delta.deleted_event_ids) + len(delta.updated_events) + len(delta.created_events)

        # Net impact = reduction savings - termination fee
        events_modified = len([e for e in delta.updated_events if e.operation != "delete"])
        events_deleted = len(delta.deleted_event_ids)
        total_savings = (reduction_amount * events_modified) + (reduction_amount * events_deleted)
        delta.net_cash_impact = total_savings - termination_fee

        return delta
