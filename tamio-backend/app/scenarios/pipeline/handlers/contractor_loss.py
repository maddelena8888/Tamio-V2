"""
Contractor Loss Handler - V4 Canonical Model.

Implements the Mermaid decision tree using ObligationSchedule overlays:
1. Select contractor/bucket or linked client/project
2. Input end date or reduction %
3. Delete future contractor schedules (virtual overlay)
4. Optional linked revenue impact (delivery slowdown)
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


class ContractorLossHandler(BaseScenarioHandler):
    """
    Handler for Contractor Loss scenarios.

    V4: Uses ObligationSchedule overlays to delete future contractor schedules.
    """

    def required_params(self) -> List[str]:
        return [
            "end_date",
            "monthly_estimate",
        ]

    def linked_prompt_types(self) -> List[str]:
        return [
            "client_change",
            "delayed_milestones",
        ]

    async def apply(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
    ) -> ScenarioDelta:
        """
        Apply contractor loss to remove contractor expense schedules.

        Steps per Mermaid flowchart:
        1. Find contractor schedules by bucket or matching amount
        2. Delete future schedules from end date (virtual overlay)
        3. Apply linked revenue impact if configured
        """
        delta = ScenarioDelta(scenario_id=definition.scenario_id)
        params = definition.parameters
        scope = definition.scope

        end_date_str = params.get("end_date")
        if isinstance(end_date_str, str):
            end_date = date.fromisoformat(end_date_str)
        else:
            end_date = end_date_str or date.today()

        monthly_estimate = Decimal(str(params.get("monthly_estimate", 0)))

        total_savings = Decimal("0")

        # Step 1-2: Delete contractor schedules
        bucket_ids = scope.bucket_ids or []

        if bucket_ids:
            # Specific bucket(s) provided
            for bucket_id in bucket_ids:
                saved = await self._delete_contractor_schedules_for_bucket(
                    db, delta, definition, bucket_id, end_date
                )
                total_savings += saved
        else:
            # Find contractor schedules matching the monthly estimate
            saved = await self._delete_matching_contractor_schedules(
                db, delta, definition, end_date, monthly_estimate
            )
            total_savings += saved

        # Step 3: Apply linked revenue impact if configured
        affects_delivery = params.get("linked_affects_delivery", False)

        if affects_delivery:
            await self._apply_delivery_impact(db, definition, delta, end_date)

        # Update summary
        delta.total_schedules_affected = (
            len(delta.deleted_schedule_ids) +
            len(delta.updated_schedules) +
            len(delta.created_schedules)
        )

        # Net impact = savings from removed contractor costs
        delta.net_cash_impact = total_savings

        # Confidence breakdown
        delta.confidence_breakdown = self._calculate_confidence_breakdown(delta)
        delta.overall_confidence = "high" if not affects_delivery else "medium"

        return delta

    async def _delete_contractor_schedules_for_bucket(
        self,
        db: AsyncSession,
        delta: ScenarioDelta,
        definition: ScenarioDefinition,
        bucket_id: str,
        end_date: date,
    ) -> Decimal:
        """Delete contractor schedules for a specific expense bucket."""
        total_saved = Decimal("0")

        schedules = await self.get_schedules_for_expense(db, bucket_id, end_date)

        for schedule in schedules:
            original_amount = schedule.estimated_amount or Decimal("0")
            total_saved += original_amount

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
                change_reason=f"Contractor ended effective {end_date}",
                confidence="high",
                confidence_factors=["user_confirmed_termination"],
            ))

        return total_saved

    async def _delete_matching_contractor_schedules(
        self,
        db: AsyncSession,
        delta: ScenarioDelta,
        definition: ScenarioDefinition,
        end_date: date,
        monthly_estimate: Decimal,
    ) -> Decimal:
        """Find and delete contractor schedules matching the monthly estimate."""
        total_saved = Decimal("0")

        # Get all future contractor schedules for the user
        result = await db.execute(
            select(ObligationSchedule).join(
                ObligationAgreement,
                ObligationSchedule.obligation_id == ObligationAgreement.id
            ).where(
                and_(
                    ObligationAgreement.user_id == definition.user_id,
                    ObligationAgreement.obligation_type == "contractor",
                    ObligationSchedule.due_date >= end_date,
                    ObligationSchedule.status == "scheduled",
                )
            ).order_by(ObligationSchedule.due_date)
        )
        all_contractors = list(result.scalars().all())

        # Match schedules with similar amount (within 15%)
        tolerance = monthly_estimate * Decimal("0.15")
        matching_schedules = [
            s for s in all_contractors
            if abs((s.estimated_amount or Decimal("0")) - monthly_estimate) <= tolerance
        ]

        for schedule in matching_schedules:
            original_amount = schedule.estimated_amount or Decimal("0")
            total_saved += original_amount

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
                change_reason=f"Contractor ended effective {end_date}",
                confidence="high",
                confidence_factors=["matched_by_amount"],
            ))

        return total_saved

    async def _apply_delivery_impact(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
        delta: ScenarioDelta,
        end_date: date,
    ) -> None:
        """Apply linked delivery impact - reduce revenue schedules."""
        params = definition.parameters
        revenue_impact = Decimal(str(params.get("linked_revenue_impact", 0)))

        if revenue_impact <= 0:
            return

        forecast_end = date.today() + timedelta(weeks=13)

        # Get future revenue schedules
        result = await db.execute(
            select(ObligationSchedule).join(
                ObligationAgreement,
                ObligationSchedule.obligation_id == ObligationAgreement.id
            ).where(
                and_(
                    ObligationAgreement.user_id == definition.user_id,
                    ObligationAgreement.obligation_type == "revenue",
                    ObligationSchedule.due_date >= end_date,
                    ObligationSchedule.due_date <= forecast_end,
                    ObligationSchedule.status == "scheduled",
                )
            ).order_by(ObligationSchedule.due_date)
        )
        revenue_schedules = list(result.scalars().all())

        for schedule in revenue_schedules:
            original_amount = schedule.estimated_amount or Decimal("0")
            new_amount = original_amount - revenue_impact

            if new_amount < 0:
                new_amount = Decimal("0")

            weeks_out = (schedule.due_date - date.today()).days // 7
            confidence, factors = self._calculate_confidence(
                weeks_out=weeks_out,
                scenario_type="contractor_loss",
                has_integration_backing=False,
            )

            delta.updated_schedules.append(self.create_schedule_delta(
                scenario_id=definition.scenario_id,
                operation="modify",
                schedule_data={
                    "id": schedule.id,
                    "estimated_amount": str(new_amount),
                    "original_amount": str(original_amount),
                    "reduction_amount": str(revenue_impact),
                    "confidence": "low",  # Delivery impact is less certain
                },
                original_schedule_id=schedule.id,
                obligation_id=schedule.obligation_id,
                linked_change_id="linked_delivery_impact",
                change_reason="Revenue impact from contractor loss",
                confidence="low",
                confidence_factors=["linked_to_contractor_loss", "delivery_impact"],
            ))

    def _calculate_confidence_breakdown(self, delta: ScenarioDelta) -> Dict[str, int]:
        """Calculate confidence breakdown across all schedule deltas."""
        breakdown = {"high": 0, "medium": 0, "low": 0}

        for sched in delta.created_schedules + delta.updated_schedules:
            conf = sched.confidence or "medium"
            if conf in breakdown:
                breakdown[conf] += 1

        return breakdown
