"""
Decreased Expense Handler - V4 Canonical Model.

Implements the Mermaid decision tree using ObligationSchedule overlays:
1. Select obligation/expense to reduce
2. Input reduction amount + effective date
3. Handle termination logic (notice period + fee)
4. Reduce/delete future expense schedules (virtual overlay)
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


class DecreasedExpenseHandler(BaseScenarioHandler):
    """
    Handler for Decreased Expense scenarios.

    V4: Uses ObligationSchedule overlays to reduce or delete
    future expense schedules.
    """

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
        Apply decreased expense to reduce/remove expense schedules.

        Steps per Mermaid flowchart:
        1. Handle termination fee if applicable
        2. Get affected ObligationSchedules
        3. Reduce or delete future expense schedules (virtual overlay)
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
            await self._add_termination_fee(
                delta, definition, effective_date, termination_fee
            )

        # Step 2: Find and reduce/remove expense schedules
        bucket_ids = scope.bucket_ids or []
        total_savings = Decimal("0")

        if bucket_ids:
            # Specific bucket(s) provided
            for bucket_id in bucket_ids:
                savings = await self._reduce_bucket_schedules(
                    db, delta, definition, bucket_id, effective_date, reduction_amount
                )
                total_savings += savings
        else:
            # Find matching expense schedules by reduction amount
            savings = await self._reduce_matching_schedules(
                db, delta, definition, effective_date, reduction_amount
            )
            total_savings += savings

        # Update summary
        delta.total_schedules_affected = (
            len(delta.deleted_schedule_ids) +
            len(delta.updated_schedules) +
            len(delta.created_schedules)
        )

        # Net impact = reduction savings - termination fee
        delta.net_cash_impact = total_savings - termination_fee

        # Confidence breakdown
        delta.confidence_breakdown = self._calculate_confidence_breakdown(delta)
        delta.overall_confidence = "high" if not has_termination_costs else "medium"

        return delta

    async def _add_termination_fee(
        self,
        delta: ScenarioDelta,
        definition: ScenarioDefinition,
        effective_date: date,
        termination_fee: Decimal,
    ) -> None:
        """Add a one-time termination fee schedule."""
        # Create virtual agreement for termination fee
        term_agreement_id = generate_id("vagrmt")
        term_agreement_data = {
            "id": term_agreement_id,
            "obligation_type": "other",
            "amount_type": "fixed",
            "amount_source": "scenario_projection",
            "base_amount": str(termination_fee),
            "frequency": "one_time",
            "start_date": str(effective_date),
            "category": "termination_fee",
            "vendor_name": "Termination Fee",
            "confidence": "high",
            "is_virtual": True,
            "scenario_id": definition.scenario_id,
        }

        delta.created_agreements.append(self.create_agreement_delta(
            scenario_id=definition.scenario_id,
            operation="add",
            agreement_data=term_agreement_data,
            change_reason="Termination fee for expense reduction",
        ))

        # Create termination fee schedule
        schedule_data = {
            "id": generate_id("vsched"),
            "obligation_id": term_agreement_id,
            "due_date": str(effective_date),
            "estimated_amount": str(termination_fee),
            "estimate_source": "scenario_projection",
            "confidence": "high",
            "status": "scheduled",
            "category": "termination_fee",
            "source_name": "Termination Fee",
            "is_recurring": False,
            "is_virtual": True,
            "scenario_id": definition.scenario_id,
        }

        delta.created_schedules.append(self.create_schedule_delta(
            scenario_id=definition.scenario_id,
            operation="add",
            schedule_data=schedule_data,
            obligation_id=term_agreement_id,
            change_reason="Termination fee for expense reduction",
            confidence="high",
            confidence_factors=["user_provided_amount", "termination_fee"],
        ))

    async def _reduce_bucket_schedules(
        self,
        db: AsyncSession,
        delta: ScenarioDelta,
        definition: ScenarioDefinition,
        bucket_id: str,
        effective_date: date,
        reduction_amount: Decimal,
    ) -> Decimal:
        """Reduce schedules for a specific expense bucket."""
        total_savings = Decimal("0")

        # Get schedules for this expense bucket
        schedules = await self.get_schedules_for_expense(db, bucket_id, effective_date)

        for schedule in schedules:
            original_amount = schedule.estimated_amount or Decimal("0")
            new_amount = original_amount - reduction_amount

            if new_amount <= 0:
                # Remove entirely (virtual delete)
                delta.deleted_schedule_ids.append(schedule.id)
                total_savings += original_amount

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
                    change_reason=f"Expense removed effective {effective_date}",
                    confidence="high",
                    confidence_factors=["user_confirmed_reduction"],
                ))
            else:
                # Reduce amount (virtual modify)
                total_savings += reduction_amount

                delta.updated_schedules.append(self.create_schedule_delta(
                    scenario_id=definition.scenario_id,
                    operation="modify",
                    schedule_data={
                        "id": schedule.id,
                        "estimated_amount": str(new_amount),
                        "original_amount": str(original_amount),
                        "reduction_amount": str(reduction_amount),
                    },
                    original_schedule_id=schedule.id,
                    obligation_id=schedule.obligation_id,
                    change_reason=f"Expense reduced by ${reduction_amount:.0f}",
                    confidence="high",
                    confidence_factors=["user_provided_reduction"],
                ))

        return total_savings

    async def _reduce_matching_schedules(
        self,
        db: AsyncSession,
        delta: ScenarioDelta,
        definition: ScenarioDefinition,
        effective_date: date,
        reduction_amount: Decimal,
    ) -> Decimal:
        """Find and reduce matching expense schedules by amount."""
        total_savings = Decimal("0")

        # Get all future expense schedules for the user
        result = await db.execute(
            select(ObligationSchedule).join(
                ObligationAgreement,
                ObligationSchedule.obligation_id == ObligationAgreement.id
            ).where(
                and_(
                    ObligationAgreement.user_id == definition.user_id,
                    ObligationAgreement.obligation_type.not_in(["revenue", "payroll"]),
                    ObligationSchedule.due_date >= effective_date,
                    ObligationSchedule.status == "scheduled",
                )
            ).order_by(ObligationSchedule.due_date)
        )
        all_schedules = list(result.scalars().all())

        # Match schedules with amount >= reduction
        matching_schedules = [
            s for s in all_schedules
            if (s.estimated_amount or Decimal("0")) >= reduction_amount
        ][:10]  # Limit to first 10 matches

        for schedule in matching_schedules:
            original_amount = schedule.estimated_amount or Decimal("0")
            new_amount = original_amount - reduction_amount

            if new_amount <= 0:
                # Remove entirely
                delta.deleted_schedule_ids.append(schedule.id)
                total_savings += original_amount

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
                    change_reason=f"Expense removed effective {effective_date}",
                    confidence="high",
                    confidence_factors=["matched_by_amount"],
                ))
            else:
                # Reduce amount
                total_savings += reduction_amount

                delta.updated_schedules.append(self.create_schedule_delta(
                    scenario_id=definition.scenario_id,
                    operation="modify",
                    schedule_data={
                        "id": schedule.id,
                        "estimated_amount": str(new_amount),
                        "original_amount": str(original_amount),
                        "reduction_amount": str(reduction_amount),
                    },
                    original_schedule_id=schedule.id,
                    obligation_id=schedule.obligation_id,
                    change_reason=f"Expense reduced by ${reduction_amount:.0f}",
                    confidence="high",
                    confidence_factors=["matched_by_amount"],
                ))

        return total_savings

    def _calculate_confidence_breakdown(self, delta: ScenarioDelta) -> Dict[str, int]:
        """Calculate confidence breakdown across all schedule deltas."""
        breakdown = {"high": 0, "medium": 0, "low": 0}

        for sched in delta.created_schedules + delta.updated_schedules:
            conf = sched.confidence or "medium"
            if conf in breakdown:
                breakdown[conf] += 1

        return breakdown
