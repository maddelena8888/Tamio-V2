"""
Firing (Payroll Loss) Handler - V4 Canonical Model.

Implements the Mermaid decision tree using ObligationSchedule overlays:
1. Select role/employee + end date
2. Input monthly cost removed
3. Optional severance/termination costs
4. Delete future payroll schedules
5. Optional linked delivery/revenue impact
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


class FiringHandler(BaseScenarioHandler):
    """
    Handler for Firing (Payroll Loss) scenarios.

    V4: Uses ObligationSchedule overlays to delete future payroll schedules
    and optionally add severance schedules.
    """

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

        Steps per Mermaid flowchart:
        1. Add severance schedule (if applicable)
        2. Delete future payroll schedules from end date
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

        total_payroll_saved = Decimal("0")

        # Step 1: Add severance schedule (if applicable)
        if severance_amount > 0:
            await self._add_severance_schedule(
                delta, definition, role_title, end_date, severance_amount
            )

        # Step 2: Delete future payroll schedules
        bucket_ids = scope.bucket_ids or []

        if bucket_ids:
            # Specific bucket(s) provided
            for bucket_id in bucket_ids:
                saved = await self._delete_payroll_schedules_for_bucket(
                    db, delta, definition, bucket_id, end_date, role_title
                )
                total_payroll_saved += saved
        else:
            # Find payroll schedules matching the monthly cost
            saved = await self._delete_matching_payroll_schedules(
                db, delta, definition, end_date, monthly_cost, role_title
            )
            total_payroll_saved += saved

        # Step 3: Apply linked revenue impact (if configured)
        affects_revenue = params.get("linked_affects_revenue", False)

        if affects_revenue:
            await self._apply_revenue_impact(db, definition, delta, end_date, role_title)

        # Update summary
        delta.total_schedules_affected = (
            len(delta.deleted_schedule_ids) +
            len(delta.updated_schedules) +
            len(delta.created_schedules)
        )

        # Calculate net impact (payroll saved - severance)
        if total_payroll_saved == 0:
            # Estimate 3 months of savings if we couldn't find specific schedules
            total_payroll_saved = monthly_cost * Decimal("3")

        delta.net_cash_impact = total_payroll_saved - severance_amount

        # Confidence breakdown
        delta.confidence_breakdown = self._calculate_confidence_breakdown(delta)
        delta.overall_confidence = "high" if not affects_revenue else "medium"

        return delta

    async def _add_severance_schedule(
        self,
        delta: ScenarioDelta,
        definition: ScenarioDefinition,
        role_title: str,
        end_date: date,
        severance_amount: Decimal,
    ) -> None:
        """Add severance payment as a virtual schedule."""
        # Create virtual agreement for severance
        severance_agreement_id = generate_id("vagrmt")
        severance_agreement_data = {
            "id": severance_agreement_id,
            "obligation_type": "other",
            "amount_type": "fixed",
            "amount_source": "scenario_projection",
            "base_amount": str(severance_amount),
            "frequency": "one_time",
            "start_date": str(end_date),
            "category": "severance",
            "vendor_name": f"Severance - {role_title}",
            "confidence": "high",
            "is_virtual": True,
            "scenario_id": definition.scenario_id,
        }

        delta.created_agreements.append(self.create_agreement_delta(
            scenario_id=definition.scenario_id,
            operation="add",
            agreement_data=severance_agreement_data,
            change_reason=f"Severance payment for {role_title}",
        ))

        # Create severance schedule
        schedule_data = {
            "id": generate_id("vsched"),
            "obligation_id": severance_agreement_id,
            "due_date": str(end_date),
            "estimated_amount": str(severance_amount),
            "estimate_source": "scenario_projection",
            "confidence": "high",
            "status": "scheduled",
            "category": "severance",
            "source_name": f"Severance - {role_title}",
            "is_recurring": False,
            "is_virtual": True,
            "scenario_id": definition.scenario_id,
        }

        delta.created_schedules.append(self.create_schedule_delta(
            scenario_id=definition.scenario_id,
            operation="add",
            schedule_data=schedule_data,
            obligation_id=severance_agreement_id,
            change_reason=f"Severance payment for {role_title}",
            confidence="high",
            confidence_factors=["user_provided_amount", "severance_payment"],
        ))

    async def _delete_payroll_schedules_for_bucket(
        self,
        db: AsyncSession,
        delta: ScenarioDelta,
        definition: ScenarioDefinition,
        bucket_id: str,
        end_date: date,
        role_title: str,
    ) -> Decimal:
        """Delete payroll schedules for a specific expense bucket."""
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
                change_reason=f"Payroll removed: {role_title} termination effective {end_date}",
                confidence="high",
                confidence_factors=["user_confirmed_termination"],
            ))

        return total_saved

    async def _delete_matching_payroll_schedules(
        self,
        db: AsyncSession,
        delta: ScenarioDelta,
        definition: ScenarioDefinition,
        end_date: date,
        monthly_cost: Decimal,
        role_title: str,
    ) -> Decimal:
        """Find and delete payroll schedules matching the monthly cost."""
        total_saved = Decimal("0")

        # Get all future payroll schedules for the user
        result = await db.execute(
            select(ObligationSchedule).join(
                ObligationAgreement,
                ObligationSchedule.obligation_id == ObligationAgreement.id
            ).where(
                and_(
                    ObligationAgreement.user_id == definition.user_id,
                    ObligationAgreement.obligation_type == "payroll",
                    ObligationSchedule.due_date >= end_date,
                    ObligationSchedule.status == "scheduled",
                )
            ).order_by(ObligationSchedule.due_date)
        )
        all_payroll = list(result.scalars().all())

        # Match schedules with similar amount (within 10%)
        tolerance = monthly_cost * Decimal("0.1")
        matching_schedules = [
            s for s in all_payroll
            if abs((s.estimated_amount or Decimal("0")) - monthly_cost) <= tolerance
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
                change_reason=f"Payroll removed: {role_title} termination effective {end_date}",
                confidence="high",
                confidence_factors=["matched_by_amount"],
            ))

        return total_saved

    async def _apply_revenue_impact(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
        delta: ScenarioDelta,
        end_date: date,
        role_title: str,
    ) -> None:
        """Apply linked revenue impact - reduce revenue schedules."""
        params = definition.parameters
        revenue_reduction = Decimal(str(params.get("linked_revenue_reduction", 0)))

        if revenue_reduction <= 0:
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
            new_amount = original_amount - revenue_reduction

            if new_amount < 0:
                new_amount = Decimal("0")

            weeks_out = (schedule.due_date - date.today()).days // 7
            confidence, factors = self._calculate_confidence(
                weeks_out=weeks_out,
                scenario_type="firing",
                has_integration_backing=False,
            )

            delta.updated_schedules.append(self.create_schedule_delta(
                scenario_id=definition.scenario_id,
                operation="modify",
                schedule_data={
                    "id": schedule.id,
                    "estimated_amount": str(new_amount),
                    "original_amount": str(original_amount),
                    "reduction_amount": str(revenue_reduction),
                    "confidence": "low",  # Revenue impact is less certain
                },
                original_schedule_id=schedule.id,
                obligation_id=schedule.obligation_id,
                linked_change_id="linked_revenue_impact",
                change_reason=f"Revenue capacity reduction from {role_title} termination",
                confidence="low",
                confidence_factors=["linked_to_termination", "capacity_impact"],
            ))

    def _calculate_confidence_breakdown(self, delta: ScenarioDelta) -> Dict[str, int]:
        """Calculate confidence breakdown across all schedule deltas."""
        breakdown = {"high": 0, "medium": 0, "low": 0}

        for sched in delta.created_schedules + delta.updated_schedules:
            conf = sched.confidence or "medium"
            if conf in breakdown:
                breakdown[conf] += 1

        return breakdown
