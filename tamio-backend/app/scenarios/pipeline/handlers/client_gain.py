"""
Client Gain Handler.

Implements the Mermaid decision tree:
1. Input start date + agreement type
2. Input amount + cadence + payment terms
3. Create Revenue Agreement + Schedule
4. Generate expected cash-in events
5. Prompt for capacity costs (contractors/hiring/tools/onboarding)
6. Apply capacity costs
"""

from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, timedelta
from decimal import Decimal

from app.scenarios.pipeline.handlers.base import BaseScenarioHandler, generate_id
from app.scenarios.pipeline.types import (
    ScenarioDefinition,
    ScenarioDelta,
    EventDelta,
)


class ClientGainHandler(BaseScenarioHandler):
    """Handler for Client Gain scenarios."""

    def required_params(self) -> List[str]:
        return [
            "client_name",
            "start_date",
            "agreement_type",
            "monthly_amount",
        ]

    def linked_prompt_types(self) -> List[str]:
        return [
            "add_contractors",
            "add_hiring",
            "add_tools",
            "add_onboarding",
        ]

    async def apply(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
    ) -> ScenarioDelta:
        """
        Apply client gain to add new revenue stream and optional capacity costs.

        Steps per Mermaid:
        1. Parse agreement configuration
        2. Generate cash-in events based on agreement type
        3. If capacity costs configured:
           a. Add recurring costs (contractors/hiring)
           b. Add one-off costs (onboarding)
        """
        delta = ScenarioDelta(scenario_id=definition.scenario_id)
        params = definition.parameters

        client_name = params.get("client_name", "New Client")
        start_date_str = params.get("start_date")
        if isinstance(start_date_str, str):
            start_date = date.fromisoformat(start_date_str)
        else:
            start_date = start_date_str or date.today()

        agreement_type = params.get("agreement_type", "retainer")
        monthly_amount = Decimal(str(params.get("monthly_amount", 0)))
        payment_terms_days = int(params.get("payment_terms_days", 30))

        # Calculate forecast window
        forecast_end = date.today() + timedelta(weeks=13)

        # Step 2: Generate revenue events based on agreement type
        if agreement_type == "retainer":
            # Monthly recurring revenue
            current_date = start_date
            while current_date <= forecast_end:
                # Adjust for payment terms
                payment_date = current_date + timedelta(days=payment_terms_days)

                if payment_date <= forecast_end:
                    event_data = {
                        "id": generate_id("evt"),
                        "user_id": definition.user_id,
                        "date": str(payment_date),
                        "amount": str(monthly_amount),
                        "direction": "in",
                        "event_type": "expected_revenue",
                        "category": "new_client",
                        "confidence": "medium",
                        "confidence_reason": "scenario_new_client",
                        "is_recurring": True,
                        "recurrence_pattern": "monthly",
                        "scenario_id": definition.scenario_id,
                    }
                    delta.created_events.append(self.create_event_delta(
                        scenario_id=definition.scenario_id,
                        operation="add",
                        event_data=event_data,
                        change_reason=f"New client '{client_name}' retainer payment",
                    ))

                # Move to next month
                if current_date.month == 12:
                    current_date = date(current_date.year + 1, 1, current_date.day)
                else:
                    try:
                        current_date = date(current_date.year, current_date.month + 1, current_date.day)
                    except ValueError:
                        # Handle month-end edge cases
                        current_date = date(current_date.year, current_date.month + 1, 28)

        elif agreement_type == "project":
            # Milestone-based - simplified as 50% upfront, 50% at end
            # First milestone at start
            upfront_amount = monthly_amount * Decimal("0.5")
            final_amount = monthly_amount * Decimal("0.5")

            # Upfront payment
            upfront_date = start_date + timedelta(days=payment_terms_days)
            if upfront_date <= forecast_end:
                event_data = {
                    "id": generate_id("evt"),
                    "user_id": definition.user_id,
                    "date": str(upfront_date),
                    "amount": str(upfront_amount),
                    "direction": "in",
                    "event_type": "expected_revenue",
                    "category": "new_client",
                    "confidence": "medium",
                    "confidence_reason": "scenario_milestone_1",
                    "scenario_id": definition.scenario_id,
                }
                delta.created_events.append(self.create_event_delta(
                    scenario_id=definition.scenario_id,
                    operation="add",
                    event_data=event_data,
                    change_reason=f"New client '{client_name}' project milestone 1 (50%)",
                ))

            # Final payment (3 months later)
            final_date = start_date + timedelta(days=90 + payment_terms_days)
            if final_date <= forecast_end:
                event_data = {
                    "id": generate_id("evt"),
                    "user_id": definition.user_id,
                    "date": str(final_date),
                    "amount": str(final_amount),
                    "direction": "in",
                    "event_type": "expected_revenue",
                    "category": "new_client",
                    "confidence": "low",
                    "confidence_reason": "scenario_milestone_final",
                    "scenario_id": definition.scenario_id,
                }
                delta.created_events.append(self.create_event_delta(
                    scenario_id=definition.scenario_id,
                    operation="add",
                    event_data=event_data,
                    change_reason=f"New client '{client_name}' project milestone 2 (50%)",
                ))

        elif agreement_type == "usage":
            # Usage-based - monthly with variable confidence
            current_date = start_date
            while current_date <= forecast_end:
                payment_date = current_date + timedelta(days=payment_terms_days)

                if payment_date <= forecast_end:
                    event_data = {
                        "id": generate_id("evt"),
                        "user_id": definition.user_id,
                        "date": str(payment_date),
                        "amount": str(monthly_amount),
                        "direction": "in",
                        "event_type": "expected_revenue",
                        "category": "new_client",
                        "confidence": "low",  # Usage-based is variable
                        "confidence_reason": "scenario_usage_estimate",
                        "is_recurring": False,  # Each month varies
                        "scenario_id": definition.scenario_id,
                    }
                    delta.created_events.append(self.create_event_delta(
                        scenario_id=definition.scenario_id,
                        operation="add",
                        event_data=event_data,
                        change_reason=f"New client '{client_name}' usage-based payment",
                    ))

                # Move to next month
                if current_date.month == 12:
                    current_date = date(current_date.year + 1, 1, current_date.day)
                else:
                    try:
                        current_date = date(current_date.year, current_date.month + 1, current_date.day)
                    except ValueError:
                        current_date = date(current_date.year, current_date.month + 1, 28)

        # Step 3: Apply linked capacity costs
        needs_capacity = params.get("linked_needs_capacity", False)

        if needs_capacity:
            capacity_types = params.get("linked_capacity_types", [])
            monthly_cost = Decimal(str(params.get("linked_monthly_cost", 0)))
            onetime_cost = Decimal(str(params.get("linked_onetime_cost", 0)))

            # Add one-time onboarding costs
            if onetime_cost > 0 and "onboarding" in capacity_types:
                event_data = {
                    "id": generate_id("evt"),
                    "user_id": definition.user_id,
                    "date": str(start_date),
                    "amount": str(onetime_cost),
                    "direction": "out",
                    "event_type": "expected_expense",
                    "category": "onboarding",
                    "confidence": "high",
                    "confidence_reason": "scenario_onboarding",
                    "is_recurring": False,
                    "scenario_id": definition.scenario_id,
                }
                delta.created_events.append(self.create_event_delta(
                    scenario_id=definition.scenario_id,
                    operation="add",
                    event_data=event_data,
                    linked_change_id="linked_onboarding",
                    change_reason=f"Onboarding costs for new client '{client_name}'",
                ))

            # Add recurring capacity costs
            if monthly_cost > 0:
                # Determine category from capacity types
                if "hiring" in capacity_types:
                    category = "payroll"
                elif "contractors" in capacity_types:
                    category = "contractors"
                else:
                    category = "software"

                current_date = start_date
                while current_date <= forecast_end:
                    event_data = {
                        "id": generate_id("evt"),
                        "user_id": definition.user_id,
                        "date": str(current_date),
                        "amount": str(monthly_cost),
                        "direction": "out",
                        "event_type": "expected_expense",
                        "category": category,
                        "confidence": "high",
                        "confidence_reason": "scenario_capacity_cost",
                        "is_recurring": True,
                        "recurrence_pattern": "monthly",
                        "scenario_id": definition.scenario_id,
                    }
                    delta.created_events.append(self.create_event_delta(
                        scenario_id=definition.scenario_id,
                        operation="add",
                        event_data=event_data,
                        linked_change_id="linked_capacity",
                        change_reason=f"Capacity costs for new client '{client_name}'",
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
        delta.total_events_affected = len(delta.created_events)

        # Calculate net impact (revenue - costs)
        total_revenue = sum(
            Decimal(e.event_data["amount"])
            for e in delta.created_events
            if e.event_data.get("direction") == "in"
        )
        total_costs = sum(
            Decimal(e.event_data["amount"])
            for e in delta.created_events
            if e.event_data.get("direction") == "out"
        )
        delta.net_cash_impact = total_revenue - total_costs

        return delta
