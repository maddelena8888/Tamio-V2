"""
Client Change Handler (Upsell/Downsell) - V4 Canonical Model.

Implements the Mermaid decision tree using ObligationSchedule overlays:
1. Select client + affected agreements
2. Input change type (upsell/downsell/scope change)
3. Input delta amount + effective date
4. Modify future revenue schedule amounts
5. Prompt for cost base changes
6. Apply cost delta with lag
"""

from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import date, timedelta
from decimal import Decimal

from app.scenarios.pipeline.handlers.base import BaseScenarioHandler, generate_id
from app.scenarios.pipeline.types import (
    ScenarioDefinition,
    ScenarioDelta,
    ScheduleDelta,
)
from app.data.obligations.models import ObligationAgreement, ObligationSchedule
from app.data.expenses.models import ExpenseBucket


class ClientChangeHandler(BaseScenarioHandler):
    """
    Handler for Client Change (upsell/downsell) scenarios.

    V4: Uses ObligationSchedule overlays to modify revenue and cost schedule amounts.
    """

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

        Steps per Mermaid flowchart:
        1. Get future ObligationSchedules for client from effective date
        2. Modify schedule amounts by delta (positive for upsell, negative for downsell)
        3. If cost changes configured:
           a. Apply cost schedule delta with optional lag
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

        total_revenue_change = Decimal("0")

        # Step 1-2: Modify revenue schedules for each client
        for client_id in client_ids:
            schedules = await self.get_schedules_for_client(db, client_id, effective_date)

            for schedule in schedules:
                original_amount = schedule.estimated_amount or Decimal("0")
                new_amount = original_amount + delta_amount

                # Don't allow negative amounts
                if new_amount < 0:
                    new_amount = Decimal("0")

                weeks_out = (schedule.due_date - date.today()).days // 7
                confidence, factors = self._calculate_confidence(
                    weeks_out=weeks_out,
                    scenario_type="client_change",
                    has_integration_backing=False,
                )

                change_description = "increased" if delta_amount > 0 else "decreased"

                modified_schedule_data = {
                    "id": schedule.id,
                    "estimated_amount": str(new_amount),
                    "original_amount": str(original_amount),
                    "delta_amount": str(delta_amount),
                    "confidence": confidence,
                    "change_type": change_type,
                }

                delta.updated_schedules.append(self.create_schedule_delta(
                    scenario_id=definition.scenario_id,
                    operation="modify",
                    schedule_data=modified_schedule_data,
                    original_schedule_id=schedule.id,
                    obligation_id=schedule.obligation_id,
                    change_reason=f"Client {change_type}: amount {change_description} by ${abs(delta_amount):.0f}",
                    confidence=confidence,
                    confidence_factors=factors + [f"client_{change_type}"],
                ))

                total_revenue_change += (new_amount - original_amount)

        # Step 3: Apply linked cost changes if configured
        cost_changes = params.get("linked_cost_changes", False)

        if cost_changes:
            await self._apply_linked_cost_changes(
                db, definition, delta, effective_date
            )

        # Update summary
        delta.total_schedules_affected = len(delta.updated_schedules) + len(delta.created_schedules)
        delta.net_cash_impact = total_revenue_change

        # Confidence breakdown
        delta.confidence_breakdown = self._calculate_confidence_breakdown(delta)
        delta.overall_confidence = "high" if change_type == "upsell" else "medium"

        return delta

    async def _apply_linked_cost_changes(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
        delta: ScenarioDelta,
        effective_date: date,
    ) -> None:
        """Apply linked cost changes to expense schedules."""
        params = definition.parameters

        cost_drivers = params.get("linked_cost_drivers", [])
        cost_delta = Decimal(str(params.get("linked_cost_delta", 0)))
        lag_weeks = int(params.get("linked_lag_weeks", 0))

        cost_effective_date = effective_date + timedelta(weeks=lag_weeks)

        # Map cost drivers to obligation categories
        category_map = {
            "contractors": "contractors",
            "delivery": "other",
            "tools": "software",
        }

        for driver in cost_drivers:
            category = category_map.get(driver)
            if not category:
                continue

            # Find expense schedules in this category
            result = await db.execute(
                select(ObligationSchedule).join(
                    ObligationAgreement,
                    ObligationSchedule.obligation_id == ObligationAgreement.id
                ).where(
                    and_(
                        ObligationAgreement.user_id == definition.user_id,
                        ObligationAgreement.category == category,
                        ObligationSchedule.due_date >= cost_effective_date,
                        ObligationSchedule.status == "scheduled",
                    )
                )
            )
            expense_schedules = list(result.scalars().all())

            for schedule in expense_schedules:
                original_amount = schedule.estimated_amount or Decimal("0")
                new_amount = original_amount + cost_delta

                if new_amount <= 0:
                    # Remove entirely
                    delta.deleted_schedule_ids.append(schedule.id)
                    delta.updated_schedules.append(self.create_schedule_delta(
                        scenario_id=definition.scenario_id,
                        operation="delete",
                        schedule_data={
                            "id": schedule.id,
                            "original_amount": str(original_amount),
                            "cancelled": True,
                        },
                        original_schedule_id=schedule.id,
                        obligation_id=schedule.obligation_id,
                        linked_change_id=f"linked_{driver}",
                        change_reason=f"{driver} cost removed due to client change",
                        confidence="medium",
                        confidence_factors=["linked_to_client_change"],
                    ))
                else:
                    # Modify amount
                    delta.updated_schedules.append(self.create_schedule_delta(
                        scenario_id=definition.scenario_id,
                        operation="modify",
                        schedule_data={
                            "id": schedule.id,
                            "estimated_amount": str(new_amount),
                            "original_amount": str(original_amount),
                            "delta_amount": str(cost_delta),
                        },
                        original_schedule_id=schedule.id,
                        obligation_id=schedule.obligation_id,
                        linked_change_id=f"linked_{driver}",
                        change_reason=f"{driver} cost adjusted by ${cost_delta:.0f} due to client change",
                        confidence="medium",
                        confidence_factors=["linked_to_client_change", f"lag_{lag_weeks}w"],
                    ))

    def _calculate_confidence_breakdown(self, delta: ScenarioDelta) -> Dict[str, int]:
        """Calculate confidence breakdown across all schedule deltas."""
        breakdown = {"high": 0, "medium": 0, "low": 0}

        for sched in delta.created_schedules + delta.updated_schedules:
            conf = sched.confidence or "medium"
            if conf in breakdown:
                breakdown[conf] += 1

        return breakdown
