"""
Payment Delay (Cash In) Handler - V4 Canonical Model.

Implements the Mermaid decision tree using ObligationSchedule overlays:
1. Select scope (client + schedules)
2. Input delay duration
3. Handle partial payment (split schedule)
4. Confidence downshift
5. Optional linked changes (delay vendors / reduce discretionary)
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


class PaymentDelayInHandler(BaseScenarioHandler):
    """
    Handler for Payment Delay (Cash In) scenarios.

    V4: Uses ObligationSchedule overlays to defer revenue schedule due_dates.
    """

    def required_params(self) -> List[str]:
        return [
            "scope.client_ids",
            "delay_weeks",
        ]

    def linked_prompt_types(self) -> List[str]:
        return [
            "delay_vendor_payments",
            "reduce_discretionary",
        ]

    async def apply(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
    ) -> ScenarioDelta:
        """
        Apply payment delay to revenue schedules.

        Steps per Mermaid flowchart:
        1. Get affected ObligationSchedules (by client)
        2. Shift due_dates forward by delay_weeks
        3. If partial payment, split into actual receipt + remaining shifted
        4. Downshift confidence
        5. Apply linked changes if configured
        """
        delta = ScenarioDelta(scenario_id=definition.scenario_id)
        params = definition.parameters
        scope = definition.scope

        delay_weeks = int(params.get("delay_weeks", 0))
        is_partial = params.get("is_partial", False)
        partial_pct = params.get("partial_payment_pct", 0) if is_partial else 0

        # Get client IDs
        client_ids = scope.client_ids or []

        if not client_ids or delay_weeks <= 0:
            return delta

        # Get revenue schedules for the client(s)
        for client_id in client_ids:
            schedules = await self.get_schedules_for_client(db, client_id, date.today())

            for schedule in schedules:
                if is_partial and partial_pct > 0:
                    # Split schedule: paid portion (keep date) + remaining (shifted)
                    await self._apply_partial_delay(
                        delta, schedule, definition, delay_weeks, partial_pct
                    )
                else:
                    # Full delay - shift the entire schedule
                    await self._apply_full_delay(
                        delta, schedule, definition, delay_weeks
                    )

        # Apply linked changes if configured
        linked_adjustment = params.get("linked_adjustment_type")

        if linked_adjustment == "delay_vendors":
            # Defer expense schedules to match
            await self._apply_linked_vendor_delay(
                db, definition, delta, delay_weeks
            )
        elif linked_adjustment == "reduce_discretionary":
            # Reduce discretionary expense schedules
            await self._apply_linked_discretionary_reduction(
                db, definition, delta
            )

        # Update summary
        delta.total_schedules_affected = len(delta.updated_schedules) + len(delta.created_schedules)
        delta.net_cash_impact = Decimal("0")  # Delay doesn't change total, just timing

        # Confidence breakdown
        delta.confidence_breakdown = self._calculate_confidence_breakdown(delta)
        delta.overall_confidence = "medium"  # Delays are generally medium confidence

        return delta

    async def _apply_partial_delay(
        self,
        delta: ScenarioDelta,
        schedule: ObligationSchedule,
        definition: ScenarioDefinition,
        delay_weeks: int,
        partial_pct: int,
    ) -> None:
        """Apply partial payment delay - split into received + deferred portions."""
        original_amount = schedule.estimated_amount or Decimal("0")
        paid_amount = original_amount * Decimal(partial_pct) / Decimal(100)
        remaining_amount = original_amount - paid_amount

        # Create schedule for received portion (keep original date, high confidence)
        received_schedule_data = {
            "id": generate_id("vsched"),
            "obligation_id": schedule.obligation_id,
            "due_date": str(schedule.due_date),
            "estimated_amount": str(paid_amount),
            "estimate_source": "scenario_projection",
            "confidence": "high",
            "status": "scheduled",
            "category": "revenue",
            "source_name": f"Partial payment ({partial_pct}%)",
            "is_recurring": False,
            "is_virtual": True,
            "scenario_id": definition.scenario_id,
            "original_schedule_id": schedule.id,
        }

        delta.created_schedules.append(self.create_schedule_delta(
            scenario_id=definition.scenario_id,
            operation="add",
            schedule_data=received_schedule_data,
            obligation_id=schedule.obligation_id,
            change_reason=f"Partial payment ({partial_pct}%) received on original date",
            confidence="high",
            confidence_factors=["partial_payment_received", "user_confirmed"],
        ))

        # Modify original schedule: shift date and reduce amount
        shifted_date = schedule.due_date + timedelta(weeks=delay_weeks)

        deferred_schedule_data = {
            "id": schedule.id,
            "due_date": str(shifted_date),
            "estimated_amount": str(remaining_amount),
            "original_due_date": str(schedule.due_date),
            "original_amount": str(original_amount),
            "confidence": "medium",  # Downshifted
            "delay_weeks": delay_weeks,
        }

        weeks_out = (shifted_date - date.today()).days // 7
        confidence, factors = self._calculate_confidence(
            weeks_out=weeks_out,
            scenario_type="payment_delay_in",
            has_integration_backing=False,
        )

        delta.updated_schedules.append(self.create_schedule_delta(
            scenario_id=definition.scenario_id,
            operation="defer",
            schedule_data=deferred_schedule_data,
            original_schedule_id=schedule.id,
            obligation_id=schedule.obligation_id,
            change_reason=f"Remaining {100-partial_pct}% delayed by {delay_weeks} weeks",
            confidence=confidence,
            confidence_factors=factors + ["partial_delay", "remaining_balance"],
        ))

    async def _apply_full_delay(
        self,
        delta: ScenarioDelta,
        schedule: ObligationSchedule,
        definition: ScenarioDefinition,
        delay_weeks: int,
    ) -> None:
        """Apply full delay - shift the entire schedule forward."""
        new_date = schedule.due_date + timedelta(weeks=delay_weeks)

        weeks_out = (new_date - date.today()).days // 7
        confidence, factors = self._calculate_confidence(
            weeks_out=weeks_out,
            scenario_type="payment_delay_in",
            has_integration_backing=False,
        )

        deferred_schedule_data = {
            "id": schedule.id,
            "due_date": str(new_date),
            "original_due_date": str(schedule.due_date),
            "estimated_amount": str(schedule.estimated_amount),
            "confidence": confidence,
            "delay_weeks": delay_weeks,
        }

        delta.updated_schedules.append(self.create_schedule_delta(
            scenario_id=definition.scenario_id,
            operation="defer",
            schedule_data=deferred_schedule_data,
            original_schedule_id=schedule.id,
            obligation_id=schedule.obligation_id,
            change_reason=f"Payment delayed by {delay_weeks} weeks",
            confidence=confidence,
            confidence_factors=factors + ["full_delay"],
        ))

    async def _apply_linked_vendor_delay(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
        delta: ScenarioDelta,
        delay_weeks: int,
    ) -> None:
        """Apply linked change: delay vendor/expense schedules to match."""
        # Get expense schedules
        result = await db.execute(
            select(ObligationSchedule).join(
                ObligationAgreement,
                ObligationSchedule.obligation_id == ObligationAgreement.id
            ).where(
                and_(
                    ObligationAgreement.user_id == definition.user_id,
                    ObligationAgreement.obligation_type.in_(["subscription", "contractor", "other"]),
                    ObligationSchedule.due_date >= date.today(),
                    ObligationSchedule.status == "scheduled",
                )
            )
        )
        expense_schedules = list(result.scalars().all())

        for schedule in expense_schedules:
            new_date = schedule.due_date + timedelta(weeks=delay_weeks)

            weeks_out = (new_date - date.today()).days // 7
            confidence, factors = self._calculate_confidence(
                weeks_out=weeks_out,
                scenario_type="payment_delay_out",
                has_integration_backing=False,
            )

            deferred_data = {
                "id": schedule.id,
                "due_date": str(new_date),
                "original_due_date": str(schedule.due_date),
                "estimated_amount": str(schedule.estimated_amount),
                "confidence": confidence,
                "delay_weeks": delay_weeks,
            }

            delta.updated_schedules.append(self.create_schedule_delta(
                scenario_id=definition.scenario_id,
                operation="defer",
                schedule_data=deferred_data,
                original_schedule_id=schedule.id,
                obligation_id=schedule.obligation_id,
                linked_change_id="linked_vendor_delay",
                change_reason=f"Vendor payment delayed by {delay_weeks} weeks to match revenue delay",
                confidence=confidence,
                confidence_factors=factors + ["linked_to_revenue_delay"],
            ))

    async def _apply_linked_discretionary_reduction(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
        delta: ScenarioDelta,
    ) -> None:
        """Apply linked change: reduce discretionary expense schedules."""
        params = definition.parameters
        reduction_pct = int(params.get("linked_reduction_pct", 20))

        # Get discretionary expense schedules (software, other, marketing)
        result = await db.execute(
            select(ObligationSchedule).join(
                ObligationAgreement,
                ObligationSchedule.obligation_id == ObligationAgreement.id
            ).where(
                and_(
                    ObligationAgreement.user_id == definition.user_id,
                    ObligationAgreement.category.in_(["software", "other", "marketing"]),
                    ObligationSchedule.due_date >= date.today(),
                    ObligationSchedule.status == "scheduled",
                )
            )
        )
        discretionary_schedules = list(result.scalars().all())

        for schedule in discretionary_schedules:
            original_amount = schedule.estimated_amount or Decimal("0")
            reduction = original_amount * Decimal(reduction_pct) / Decimal(100)
            new_amount = original_amount - reduction

            modified_data = {
                "id": schedule.id,
                "estimated_amount": str(new_amount),
                "original_amount": str(original_amount),
                "reduction_amount": str(reduction),
                "confidence": "medium",
            }

            delta.updated_schedules.append(self.create_schedule_delta(
                scenario_id=definition.scenario_id,
                operation="modify",
                schedule_data=modified_data,
                original_schedule_id=schedule.id,
                obligation_id=schedule.obligation_id,
                linked_change_id="linked_discretionary_reduction",
                change_reason=f"Discretionary spending reduced by {reduction_pct}%",
                confidence="medium",
                confidence_factors=["linked_to_revenue_delay", "discretionary_cut"],
            ))

    def _calculate_confidence_breakdown(self, delta: ScenarioDelta) -> Dict[str, int]:
        """Calculate confidence breakdown across all schedule deltas."""
        breakdown = {"high": 0, "medium": 0, "low": 0}

        for sched in delta.created_schedules + delta.updated_schedules:
            conf = sched.confidence or "medium"
            if conf in breakdown:
                breakdown[conf] += 1

        return breakdown
