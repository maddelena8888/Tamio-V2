"""
Hiring (Payroll Gain) Handler.

Implements the Mermaid decision tree:
1. Input role + start date
2. Input monthly cost + pay cycle
3. Optional one-off hiring costs
4. Add recurring payroll obligation
5. Optional linked revenue changes
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


class HiringHandler(BaseScenarioHandler):
    """Handler for Hiring scenarios."""

    def required_params(self) -> List[str]:
        return [
            "role_title",
            "start_date",
            "monthly_cost",
        ]

    def linked_prompt_types(self) -> List[str]:
        return [
            "client_gain",
            "upsell",
        ]

    async def apply(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
    ) -> ScenarioDelta:
        """
        Apply hiring scenario to add payroll costs.

        Steps per Mermaid:
        1. Add one-off hiring costs (if applicable)
        2. Generate recurring payroll events
        3. Apply linked revenue changes (if configured)
        """
        delta = ScenarioDelta(scenario_id=definition.scenario_id)
        params = definition.parameters

        role_title = params.get("role_title", "New Hire")
        start_date_str = params.get("start_date")
        if isinstance(start_date_str, str):
            start_date = date.fromisoformat(start_date_str)
        else:
            start_date = start_date_str or date.today()

        monthly_cost = Decimal(str(params.get("monthly_cost", 0)))
        pay_frequency = params.get("pay_frequency", "monthly")
        has_onboarding = params.get("has_onboarding_costs", False)
        onboarding_costs = Decimal(str(params.get("onboarding_costs", 0))) if has_onboarding else Decimal("0")

        forecast_end = date.today() + timedelta(weeks=13)

        # Step 1: Add one-off hiring costs
        if onboarding_costs > 0:
            event_data = {
                "id": generate_id("evt"),
                "user_id": definition.user_id,
                "date": str(start_date),
                "amount": str(onboarding_costs),
                "direction": "out",
                "event_type": "expected_expense",
                "category": "onboarding",
                "confidence": "high",
                "confidence_reason": "scenario_hiring_onboarding",
                "is_recurring": False,
                "scenario_id": definition.scenario_id,
            }
            delta.created_events.append(self.create_event_delta(
                scenario_id=definition.scenario_id,
                operation="add",
                event_data=event_data,
                change_reason=f"One-time hiring costs for {role_title}",
            ))

        # Step 2: Generate recurring payroll events
        if pay_frequency == "weekly":
            pay_interval = timedelta(weeks=1)
            pay_amount = monthly_cost / Decimal("4.33")  # Approx weekly
        elif pay_frequency == "bi-weekly":
            pay_interval = timedelta(weeks=2)
            pay_amount = monthly_cost / Decimal("2.17")  # Approx bi-weekly
        else:  # monthly
            pay_interval = timedelta(days=30)
            pay_amount = monthly_cost

        current_date = start_date
        while current_date <= forecast_end:
            event_data = {
                "id": generate_id("evt"),
                "user_id": definition.user_id,
                "date": str(current_date),
                "amount": str(pay_amount),
                "direction": "out",
                "event_type": "expected_expense",
                "category": "payroll",
                "confidence": "high",
                "confidence_reason": "scenario_new_hire",
                "is_recurring": True,
                "recurrence_pattern": pay_frequency,
                "scenario_id": definition.scenario_id,
            }
            delta.created_events.append(self.create_event_delta(
                scenario_id=definition.scenario_id,
                operation="add",
                event_data=event_data,
                change_reason=f"Payroll for new hire: {role_title}",
            ))

            current_date += pay_interval

        # Step 3: Apply linked revenue changes (if configured)
        needs_revenue = params.get("linked_needs_revenue", False)

        if needs_revenue:
            revenue_increase = Decimal(str(params.get("linked_revenue_increase", 0)))

            if revenue_increase > 0:
                # Add expected revenue growth
                current_date = start_date
                while current_date <= forecast_end:
                    event_data = {
                        "id": generate_id("evt"),
                        "user_id": definition.user_id,
                        "date": str(current_date),
                        "amount": str(revenue_increase),
                        "direction": "in",
                        "event_type": "expected_revenue",
                        "category": "revenue_growth",
                        "confidence": "low",
                        "confidence_reason": "scenario_hire_revenue_target",
                        "is_recurring": True,
                        "recurrence_pattern": "monthly",
                        "scenario_id": definition.scenario_id,
                    }
                    delta.created_events.append(self.create_event_delta(
                        scenario_id=definition.scenario_id,
                        operation="add",
                        event_data=event_data,
                        linked_change_id="linked_revenue",
                        change_reason=f"Expected revenue growth from {role_title}",
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

        # Calculate net impact
        total_costs = sum(
            Decimal(e.event_data["amount"])
            for e in delta.created_events
            if e.event_data.get("direction") == "out"
        )
        total_revenue = sum(
            Decimal(e.event_data["amount"])
            for e in delta.created_events
            if e.event_data.get("direction") == "in"
        )
        delta.net_cash_impact = total_revenue - total_costs

        return delta
