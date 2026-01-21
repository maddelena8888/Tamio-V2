"""
Client Loss Handler - V4 Canonical Model.

Implements the Mermaid decision tree using ObligationSchedule overlays:
1. Select client(s) + effective end date
2. Remove all future ObligationSchedules from end date
3. Mark agreement as deactivated (virtual)
4. Prompt for cost reductions (contractors/tools/project)
5. Apply cost reductions with lag to expense schedules
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
    AgreementDelta,
    LinkedChangeType,
)
from app.data.obligations.models import ObligationAgreement, ObligationSchedule
from app.data.expenses.models import ExpenseBucket


class ClientLossHandler(BaseScenarioHandler):
    """
    Handler for Client Loss scenarios.

    V4: Uses ObligationSchedule overlays instead of CashEvent deltas.
    """

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
        Apply client loss to remove future revenue schedules and optionally reduce costs.

        Steps per Mermaid flowchart:
        1. Get all future ObligationSchedules for client from effective date
        2. Delete all these schedules (virtual overlay)
        3. Mark agreement as deactivated (virtual overlay)
        4. If linked cost reductions configured:
           a. Determine reduction amount and categories
           b. Apply with lag (0-4 weeks)
           c. Reduce/delete future expense schedules
        """
        delta = ScenarioDelta(scenario_id=definition.scenario_id)
        params = definition.parameters
        scope = definition.scope

        client_ids = scope.client_ids or []
        effective_date = self._parse_date(params.get("effective_date")) or date.today()

        total_revenue_lost = Decimal("0")

        # Step 1-3: Process each client
        for client_id in client_ids:
            # Get the client's obligation agreement
            agreement = await self.get_agreement_for_client(db, client_id)

            # Get all future schedules for this client
            schedules = await self.get_schedules_for_client(db, client_id, effective_date)

            # Delete all future revenue schedules (virtual overlay)
            for schedule in schedules:
                delta.deleted_schedule_ids.append(schedule.id)
                total_revenue_lost += schedule.estimated_amount or Decimal("0")

                # Track the deletion with full context
                delta.updated_schedules.append(self.create_schedule_delta(
                    scenario_id=definition.scenario_id,
                    operation="delete",
                    schedule_data={
                        "id": schedule.id,
                        "original_due_date": str(schedule.due_date),
                        "original_amount": str(schedule.estimated_amount),
                        "cancelled": True,
                    },
                    original_schedule_id=schedule.id,
                    obligation_id=schedule.obligation_id,
                    change_reason=f"Client lost effective {effective_date}",
                    confidence="high",
                    confidence_factors=["user_confirmed_loss"],
                ))

            # Mark the agreement as deactivated (virtual overlay)
            if agreement:
                delta.deactivated_agreement_ids.append(agreement.id)
                delta.updated_agreements.append(self.create_agreement_delta(
                    scenario_id=definition.scenario_id,
                    operation="deactivate",
                    agreement_data={
                        "id": agreement.id,
                        "end_date": str(effective_date),
                        "deactivation_reason": "client_loss_scenario",
                    },
                    original_agreement_id=agreement.id,
                    change_reason=f"Client relationship ended {effective_date}",
                ))

        # Step 4-5: Apply linked cost reductions if configured
        reduce_costs = params.get("linked_reduce_costs", False)

        if reduce_costs:
            await self._apply_linked_cost_reductions(
                db, definition, delta, effective_date
            )

        # Update summary
        delta.total_schedules_affected = (
            len(delta.deleted_schedule_ids) +
            len(delta.updated_schedules) +
            len(delta.created_schedules)
        )
        delta.net_cash_impact = -total_revenue_lost  # Negative impact from lost revenue

        # Calculate confidence breakdown
        delta.confidence_breakdown = self._calculate_confidence_breakdown(delta)
        delta.overall_confidence = "high"  # Client loss is high confidence when user-confirmed

        return delta

    async def _apply_linked_cost_reductions(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
        delta: ScenarioDelta,
        effective_date: date,
    ) -> None:
        """
        Apply linked cost reductions to expense schedules.

        Reduces or deletes expense schedules based on user input.
        """
        params = definition.parameters
        cost_types = params.get("linked_cost_types", [])
        reduction_amount = Decimal(str(params.get("linked_reduction_amount", 0)))
        lag_weeks = int(params.get("linked_lag_weeks", 0))

        if not cost_types or reduction_amount <= 0:
            return

        reduction_effective_date = effective_date + timedelta(weeks=lag_weeks)

        # Map cost types to expense categories
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
                    and_(
                        ExpenseBucket.user_id == definition.user_id,
                        ExpenseBucket.category == category
                    )
                )
            )
            buckets = list(result.scalars().all())

            # Calculate total bucket amount for proportional distribution
            total_bucket_amount = sum(
                b.monthly_amount or Decimal("0") for b in buckets
            )
            if total_bucket_amount <= 0:
                continue

            for bucket in buckets:
                # Calculate this bucket's share of the reduction
                bucket_share = (
                    bucket.monthly_amount / total_bucket_amount
                ) if total_bucket_amount > 0 else Decimal("0")
                bucket_reduction = reduction_amount * bucket_share

                # Get future schedules for this expense bucket
                schedules = await self.get_schedules_for_expense(
                    db, bucket.id, reduction_effective_date
                )

                for schedule in schedules:
                    new_amount = (schedule.estimated_amount or Decimal("0")) - bucket_reduction

                    if new_amount <= 0:
                        # Remove entirely (virtual delete)
                        delta.deleted_schedule_ids.append(schedule.id)
                        delta.updated_schedules.append(self.create_schedule_delta(
                            scenario_id=definition.scenario_id,
                            operation="delete",
                            schedule_data={
                                "id": schedule.id,
                                "original_amount": str(schedule.estimated_amount),
                                "cancelled": True,
                            },
                            original_schedule_id=schedule.id,
                            obligation_id=schedule.obligation_id,
                            linked_change_id=f"linked_{cost_type}",
                            change_reason=f"{cost_type} removed due to client loss (lag: {lag_weeks}w)",
                            confidence="medium",
                            confidence_factors=["linked_to_client_loss", f"lag_{lag_weeks}w"],
                        ))
                    else:
                        # Reduce amount (virtual modify)
                        delta.updated_schedules.append(self.create_schedule_delta(
                            scenario_id=definition.scenario_id,
                            operation="modify",
                            schedule_data={
                                "id": schedule.id,
                                "estimated_amount": str(new_amount),
                                "original_amount": str(schedule.estimated_amount),
                                "reduction_amount": str(bucket_reduction),
                            },
                            original_schedule_id=schedule.id,
                            obligation_id=schedule.obligation_id,
                            linked_change_id=f"linked_{cost_type}",
                            change_reason=f"{cost_type} reduced by ${bucket_reduction:.0f}/mo due to client loss",
                            confidence="medium",
                            confidence_factors=["linked_to_client_loss", f"lag_{lag_weeks}w"],
                        ))

    def _calculate_confidence_breakdown(self, delta: ScenarioDelta) -> Dict[str, int]:
        """Calculate confidence breakdown across all schedule deltas."""
        breakdown = {"high": 0, "medium": 0, "low": 0}

        for sched in delta.created_schedules + delta.updated_schedules:
            conf = sched.confidence or "medium"
            if conf in breakdown:
                breakdown[conf] += 1

        return breakdown
