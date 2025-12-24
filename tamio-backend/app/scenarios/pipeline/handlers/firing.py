"""
Firing (Payroll Loss) Handler.

Implements the Mermaid decision tree:
1. Select role/employee + end date
2. Input monthly cost removed
3. Optional severance/termination costs
4. Remove future payroll events
5. Optional linked delivery/revenue impact
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


class FiringHandler(BaseScenarioHandler):
    """Handler for Firing scenarios."""

    def required_params(self) -> List[str]:
        return [
            "end_date",
            "monthly_cost",
        ]

    def linked_prompt_types(self) -> List[str]:
        return [
            "client_loss",
            "downsell",
            "delayed_milestones",
        ]

    async def apply(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
    ) -> ScenarioDelta:
        """
        Apply firing scenario to remove payroll and add severance.

        Steps per Mermaid:
        1. Add severance payment (if applicable)
        2. Remove future payroll events from end date
        3. Apply linked revenue impact (if configured)
        """
        delta = ScenarioDelta(scenario_id=definition.scenario_id)
        params = definition.parameters
        scope = definition.scope

        role_title = params.get("role_title", "Employee")
        end_date_str = params.get("end_date")
        if isinstance(end_date_str, str):
            end_date = date.fromisoformat(end_date_str)
        else:
            end_date = end_date_str or date.today()

        monthly_cost = Decimal(str(params.get("monthly_cost", 0)))
        has_severance = params.get("has_severance", False)
        severance_amount = Decimal(str(params.get("severance_amount", 0))) if has_severance else Decimal("0")

        # Step 1: Add severance payment
        if severance_amount > 0:
            event_data = {
                "id": generate_id("evt"),
                "user_id": definition.user_id,
                "date": str(end_date),
                "amount": str(severance_amount),
                "direction": "out",
                "event_type": "expected_expense",
                "category": "severance",
                "confidence": "high",
                "confidence_reason": "scenario_severance",
                "is_recurring": False,
                "scenario_id": definition.scenario_id,
            }
            delta.created_events.append(self.create_event_delta(
                scenario_id=definition.scenario_id,
                operation="add",
                event_data=event_data,
                change_reason=f"Severance payment for {role_title}",
            ))

        # Step 2: Remove future payroll events
        bucket_ids = scope.bucket_ids or []

        if bucket_ids:
            # Specific bucket provided
            result = await db.execute(
                select(CashEvent).where(
                    CashEvent.bucket_id.in_(bucket_ids),
                    CashEvent.date >= end_date,
                    CashEvent.category == "payroll"
                )
            )
            payroll_events = list(result.scalars().all())
        else:
            # Find payroll events matching the monthly cost
            result = await db.execute(
                select(CashEvent).where(
                    CashEvent.user_id == definition.user_id,
                    CashEvent.date >= end_date,
                    CashEvent.category == "payroll",
                    CashEvent.direction == "out"
                )
            )
            all_payroll = list(result.scalars().all())

            # Match events with similar amount (within 10%)
            tolerance = monthly_cost * Decimal("0.1")
            payroll_events = [
                e for e in all_payroll
                if abs(e.amount - monthly_cost) <= tolerance
            ]

        for event in payroll_events:
            delta.deleted_event_ids.append(event.id)
            delta.updated_events.append(self.create_event_delta(
                scenario_id=definition.scenario_id,
                operation="delete",
                event_data={"id": event.id, "deleted": True},
                original_event_id=event.id,
                change_reason=f"Payroll removed: {role_title} termination effective {end_date}",
            ))

        # Step 3: Apply linked revenue impact (if configured)
        affects_revenue = params.get("linked_affects_revenue", False)

        if affects_revenue:
            revenue_reduction = Decimal(str(params.get("linked_revenue_reduction", 0)))

            if revenue_reduction > 0:
                # Model reduced revenue capacity
                forecast_end = date.today() + timedelta(weeks=13)
                current_date = end_date

                while current_date <= forecast_end:
                    # Create negative adjustment events (or reduce existing)
                    event_data = {
                        "id": generate_id("evt"),
                        "user_id": definition.user_id,
                        "date": str(current_date),
                        "amount": str(revenue_reduction),
                        "direction": "in",  # Will be used to reduce expected revenue
                        "event_type": "revenue_reduction",
                        "category": "capacity_impact",
                        "confidence": "low",
                        "confidence_reason": "scenario_capacity_reduction",
                        "is_recurring": True,
                        "recurrence_pattern": "monthly",
                        "scenario_id": definition.scenario_id,
                    }

                    # Note: In practice, this would reduce existing revenue events
                    # For now, we're modeling as a warning/adjustment
                    delta.created_events.append(self.create_event_delta(
                        scenario_id=definition.scenario_id,
                        operation="add",
                        event_data=event_data,
                        linked_change_id="linked_revenue_impact",
                        change_reason=f"Revenue capacity reduction from {role_title} termination",
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

        # Calculate net impact (payroll saved - severance)
        payroll_saved = sum(
            Decimal(str(e.event_data.get("amount", 0)))
            for e in delta.updated_events
            if e.operation == "delete"
        ) if delta.updated_events else monthly_cost * Decimal("3")  # Estimate 3 months
        delta.net_cash_impact = payroll_saved - severance_amount

        return delta
