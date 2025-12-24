"""
Increased Expense Handler.

Implements the Mermaid decision tree:
1. Select category (Tools/Rent/Marketing/Tax/Other)
2. Choose one-off vs recurring
3. Input amount + start date
4. Add expense event(s)
5. Optional rule gating (capex gate/buffer)
"""

from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, timedelta
from decimal import Decimal

from app.scenarios.pipeline.handlers.base import BaseScenarioHandler, generate_id
from app.scenarios.pipeline.types import (
    ScenarioDefinition,
    ScenarioDelta,
)


class IncreasedExpenseHandler(BaseScenarioHandler):
    """Handler for Increased Expense scenarios."""

    def required_params(self) -> List[str]:
        return [
            "category",
            "expense_type",
            "amount",
            "effective_date",
        ]

    def linked_prompt_types(self) -> List[str]:
        return [
            "capex_gate",
            "buffer_gate",
        ]

    async def apply(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
    ) -> ScenarioDelta:
        """
        Apply increased expense to add new expense events.

        Steps per Mermaid:
        1. Create expense event(s) based on type (one-off vs recurring)
        2. Tag as gated if configured
        """
        delta = ScenarioDelta(scenario_id=definition.scenario_id)
        params = definition.parameters

        category = params.get("category", "other")
        expense_name = params.get("expense_name", "New Expense")
        expense_type = params.get("expense_type", "one_off")
        amount = Decimal(str(params.get("amount", 0)))

        effective_date_str = params.get("effective_date")
        if isinstance(effective_date_str, str):
            effective_date = date.fromisoformat(effective_date_str)
        else:
            effective_date = effective_date_str or date.today()

        # Check for gating
        is_gated = params.get("linked_is_gated", False)
        gating_rule = params.get("linked_gating_rule")

        if expense_type == "one_off":
            # Single expense event
            event_data = {
                "id": generate_id("evt"),
                "user_id": definition.user_id,
                "date": str(effective_date),
                "amount": str(amount),
                "direction": "out",
                "event_type": "expected_expense",
                "category": category,
                "confidence": "high",
                "confidence_reason": "scenario_one_off_expense",
                "is_recurring": False,
                "scenario_id": definition.scenario_id,
            }

            if is_gated:
                event_data["is_gated"] = True
                event_data["gating_rule"] = gating_rule

            delta.created_events.append(self.create_event_delta(
                scenario_id=definition.scenario_id,
                operation="add",
                event_data=event_data,
                change_reason=f"One-off expense: {expense_name}",
            ))

        else:
            # Recurring expense
            forecast_end = date.today() + timedelta(weeks=13)
            frequency = params.get("frequency", "monthly")

            if frequency == "quarterly":
                interval = timedelta(days=90)
            elif frequency == "annual":
                interval = timedelta(days=365)
            else:  # monthly
                interval = timedelta(days=30)

            current_date = effective_date
            while current_date <= forecast_end:
                event_data = {
                    "id": generate_id("evt"),
                    "user_id": definition.user_id,
                    "date": str(current_date),
                    "amount": str(amount),
                    "direction": "out",
                    "event_type": "expected_expense",
                    "category": category,
                    "confidence": "high",
                    "confidence_reason": "scenario_recurring_expense",
                    "is_recurring": True,
                    "recurrence_pattern": frequency,
                    "scenario_id": definition.scenario_id,
                }

                if is_gated:
                    event_data["is_gated"] = True
                    event_data["gating_rule"] = gating_rule

                delta.created_events.append(self.create_event_delta(
                    scenario_id=definition.scenario_id,
                    operation="add",
                    event_data=event_data,
                    change_reason=f"Recurring expense: {expense_name} ({frequency})",
                ))

                current_date += interval

        # Update summary
        delta.total_events_affected = len(delta.created_events)
        delta.net_cash_impact = -amount * len(delta.created_events)

        # Add gating info to changes_by_linked_change if applicable
        if is_gated:
            delta.changes_by_linked_change[f"gated_{gating_rule}"] = len(delta.created_events)

        return delta
