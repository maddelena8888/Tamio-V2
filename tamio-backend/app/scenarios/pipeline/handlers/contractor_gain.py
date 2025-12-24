"""
Contractor Gain Handler.

Implements the Mermaid decision tree:
1. Input start date + monthly estimate
2. Choose fixed vs variable
3. Add contractor obligation/events
4. Optional linkage to client/project
5. Apply lag if linked
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


class ContractorGainHandler(BaseScenarioHandler):
    """Handler for Contractor Gain scenarios."""

    def required_params(self) -> List[str]:
        return [
            "start_date",
            "monthly_estimate",
        ]

    def linked_prompt_types(self) -> List[str]:
        return [
            "link_to_client",
        ]

    async def apply(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
    ) -> ScenarioDelta:
        """
        Apply contractor gain to add contractor expense events.

        Steps per Mermaid:
        1. Create contractor expense events
        2. Apply client/project linkage if configured
        3. Apply lag if linked
        """
        delta = ScenarioDelta(scenario_id=definition.scenario_id)
        params = definition.parameters

        contractor_name = params.get("contractor_name", "New Contractor")
        start_date_str = params.get("start_date")
        if isinstance(start_date_str, str):
            start_date = date.fromisoformat(start_date_str)
        else:
            start_date = start_date_str or date.today()

        monthly_estimate = Decimal(str(params.get("monthly_estimate", 0)))
        cost_type = params.get("cost_type", "variable")

        # Check for linkage
        is_linked = params.get("linked_is_linked", False)
        linked_client_id = params.get("linked_linked_client_id")
        lag_weeks = int(params.get("linked_lag_weeks", 0)) if is_linked else 0

        # Apply lag to start date
        effective_start = start_date + timedelta(weeks=lag_weeks)
        forecast_end = date.today() + timedelta(weeks=13)

        # Set confidence based on cost type
        confidence = "high" if cost_type == "fixed" else "medium"

        # Generate contractor expense events
        current_date = effective_start
        while current_date <= forecast_end:
            event_data = {
                "id": generate_id("evt"),
                "user_id": definition.user_id,
                "date": str(current_date),
                "amount": str(monthly_estimate),
                "direction": "out",
                "event_type": "expected_expense",
                "category": "contractors",
                "confidence": confidence,
                "confidence_reason": f"scenario_contractor_{cost_type}",
                "is_recurring": True,
                "recurrence_pattern": "monthly",
                "scenario_id": definition.scenario_id,
            }

            # Add linkage metadata if applicable
            if is_linked and linked_client_id:
                event_data["linked_client_id"] = linked_client_id

            change_reason = f"New contractor: {contractor_name}"
            if is_linked:
                change_reason += f" (linked to client, {lag_weeks}w lag)"

            delta.created_events.append(self.create_event_delta(
                scenario_id=definition.scenario_id,
                operation="add",
                event_data=event_data,
                linked_change_id="linked_client" if is_linked else None,
                change_reason=change_reason,
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
        delta.net_cash_impact = -monthly_estimate * len(delta.created_events)

        return delta
