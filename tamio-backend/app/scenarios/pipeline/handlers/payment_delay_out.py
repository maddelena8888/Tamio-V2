"""
Payment Delay (Cash Out) Handler - V4 Canonical Model.

Implements the Mermaid decision tree using ObligationSchedule overlays:
1. Select vendor/obligation
2. Input delay duration
3. Handle partial payment (split schedule)
4. Tag as delayed outflow
5. Optional clustering risk mitigation
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


class PaymentDelayOutHandler(BaseScenarioHandler):
    """
    Handler for Payment Delay (Cash Out) scenarios.

    V4: Uses ObligationSchedule overlays to defer expense schedule due_dates.
    """

    def required_params(self) -> List[str]:
        return [
            "delay_weeks",
        ]

    def linked_prompt_types(self) -> List[str]:
        return [
            "catch_up_schedule",
            "spread_payments",
        ]

    async def apply(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
    ) -> ScenarioDelta:
        """
        Apply payment delay to expense schedules.

        Steps per Mermaid flowchart:
        1. Get affected ObligationSchedules
        2. Shift due_dates forward by delay_weeks
        3. If partial, split into actual + remaining shifted
        4. Apply clustering risk mitigation if configured
        """
        delta = ScenarioDelta(scenario_id=definition.scenario_id)
        params = definition.parameters
        scope = definition.scope

        delay_weeks = int(params.get("delay_weeks", 0))
        is_partial = params.get("is_partial", False)
        partial_pct = params.get("partial_payment_pct", 0) if is_partial else 0

        # Get bucket IDs (expense buckets)
        bucket_ids = scope.bucket_ids or []

        if not bucket_ids or delay_weeks <= 0:
            return delta

        # Get expense schedules for the bucket(s)
        for bucket_id in bucket_ids:
            schedules = await self.get_schedules_for_expense(db, bucket_id, date.today())

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

        # Apply clustering risk mitigation if configured
        has_clustering_risk = params.get("linked_has_clustering_risk", False)
        mitigation_type = params.get("linked_mitigation_type")

        if has_clustering_risk and mitigation_type == "catch_up":
            await self._apply_catch_up_schedule(delta, definition, delay_weeks)
        elif has_clustering_risk and mitigation_type == "spread":
            await self._apply_spread_payments(db, delta, definition, delay_weeks)

        # Update summary
        delta.total_schedules_affected = len(delta.updated_schedules) + len(delta.created_schedules)
        delta.net_cash_impact = Decimal("0")  # Delay doesn't change total, just timing

        # Confidence breakdown
        delta.confidence_breakdown = self._calculate_confidence_breakdown(delta)
        delta.overall_confidence = "medium"

        return delta

    async def _apply_partial_delay(
        self,
        delta: ScenarioDelta,
        schedule: ObligationSchedule,
        definition: ScenarioDefinition,
        delay_weeks: int,
        partial_pct: int,
    ) -> None:
        """Apply partial payment delay - split into paid + deferred portions."""
        original_amount = schedule.estimated_amount or Decimal("0")
        paid_amount = original_amount * Decimal(partial_pct) / Decimal(100)
        remaining_amount = original_amount - paid_amount

        # Create schedule for paid portion (keep original date, high confidence)
        paid_schedule_data = {
            "id": generate_id("vsched"),
            "obligation_id": schedule.obligation_id,
            "due_date": str(schedule.due_date),
            "estimated_amount": str(paid_amount),
            "estimate_source": "scenario_projection",
            "confidence": "high",
            "status": "scheduled",
            "category": "expense",
            "source_name": f"Partial payment ({partial_pct}%)",
            "is_recurring": False,
            "is_virtual": True,
            "scenario_id": definition.scenario_id,
            "original_schedule_id": schedule.id,
        }

        delta.created_schedules.append(self.create_schedule_delta(
            scenario_id=definition.scenario_id,
            operation="add",
            schedule_data=paid_schedule_data,
            obligation_id=schedule.obligation_id,
            change_reason=f"Partial payment ({partial_pct}%) made on original date",
            confidence="high",
            confidence_factors=["partial_payment_made", "user_confirmed"],
        ))

        # Modify original schedule: shift date and reduce amount
        shifted_date = schedule.due_date + timedelta(weeks=delay_weeks)

        deferred_schedule_data = {
            "id": schedule.id,
            "due_date": str(shifted_date),
            "estimated_amount": str(remaining_amount),
            "original_due_date": str(schedule.due_date),
            "original_amount": str(original_amount),
            "confidence": "medium",
            "delay_weeks": delay_weeks,
        }

        weeks_out = (shifted_date - date.today()).days // 7
        confidence, factors = self._calculate_confidence(
            weeks_out=weeks_out,
            scenario_type="payment_delay_out",
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
            scenario_type="payment_delay_out",
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
            change_reason=f"Vendor payment delayed by {delay_weeks} weeks",
            confidence=confidence,
            confidence_factors=factors + ["full_delay"],
        ))

    async def _apply_catch_up_schedule(
        self,
        delta: ScenarioDelta,
        definition: ScenarioDefinition,
        delay_weeks: int,
    ) -> None:
        """Apply catch-up schedule: spread the delayed amount over future weeks."""
        # Calculate total delayed amount
        total_delayed = Decimal("0")
        for sched_delta in delta.updated_schedules:
            if sched_delta.operation == "defer":
                amount = sched_delta.schedule_data.get("estimated_amount", "0")
                total_delayed += Decimal(str(amount))

        if total_delayed <= 0:
            return

        # Create 4 weekly catch-up schedules
        catch_up_amount = total_delayed / Decimal("4")
        base_date = date.today() + timedelta(weeks=delay_weeks + 1)

        # Create a virtual agreement for catch-up payments
        catch_up_agreement_id = generate_id("vagrmt")
        catch_up_agreement_data = {
            "id": catch_up_agreement_id,
            "obligation_type": "other",
            "amount_type": "fixed",
            "amount_source": "scenario_projection",
            "base_amount": str(catch_up_amount),
            "frequency": "weekly",
            "start_date": str(base_date),
            "category": "catch_up_payment",
            "vendor_name": "Catch-up Payments",
            "confidence": "medium",
            "is_virtual": True,
            "scenario_id": definition.scenario_id,
        }

        delta.created_agreements.append(self.create_agreement_delta(
            scenario_id=definition.scenario_id,
            operation="add",
            agreement_data=catch_up_agreement_data,
            linked_change_id="linked_catch_up",
            change_reason="Catch-up schedule for delayed payments",
        ))

        for week in range(4):
            catch_up_date = base_date + timedelta(weeks=week)

            weeks_out = (catch_up_date - date.today()).days // 7
            confidence, factors = self._calculate_confidence(
                weeks_out=weeks_out,
                scenario_type="payment_delay_out",
                has_integration_backing=False,
            )

            schedule_data = {
                "id": generate_id("vsched"),
                "obligation_id": catch_up_agreement_id,
                "due_date": str(catch_up_date),
                "estimated_amount": str(catch_up_amount),
                "estimate_source": "scenario_projection",
                "confidence": confidence,
                "status": "scheduled",
                "category": "catch_up_payment",
                "source_name": f"Catch-up payment {week+1}/4",
                "is_recurring": False,
                "is_virtual": True,
                "scenario_id": definition.scenario_id,
            }

            delta.created_schedules.append(self.create_schedule_delta(
                scenario_id=definition.scenario_id,
                operation="add",
                schedule_data=schedule_data,
                obligation_id=catch_up_agreement_id,
                linked_change_id="linked_catch_up",
                change_reason=f"Catch-up payment {week+1}/4 for delayed payments",
                confidence=confidence,
                confidence_factors=factors + ["catch_up_schedule"],
            ))

    async def _apply_spread_payments(
        self,
        db: AsyncSession,
        delta: ScenarioDelta,
        definition: ScenarioDefinition,
        delay_weeks: int,
    ) -> None:
        """Apply spread payments: redistribute future payments more evenly."""
        # Get all future expense schedules after the delay period
        spread_start = date.today() + timedelta(weeks=delay_weeks)
        spread_end = date.today() + timedelta(weeks=13)

        result = await db.execute(
            select(ObligationSchedule).join(
                ObligationAgreement,
                ObligationSchedule.obligation_id == ObligationAgreement.id
            ).where(
                and_(
                    ObligationAgreement.user_id == definition.user_id,
                    ObligationSchedule.due_date >= spread_start,
                    ObligationSchedule.due_date <= spread_end,
                    ObligationSchedule.status == "scheduled",
                )
            ).order_by(ObligationSchedule.due_date)
        )
        future_schedules = list(result.scalars().all())

        if not future_schedules:
            return

        # Calculate total amount and number of weeks
        total_amount = sum(s.estimated_amount or Decimal("0") for s in future_schedules)
        num_weeks = (spread_end - spread_start).days // 7

        if num_weeks <= 0:
            return

        # Calculate average weekly amount
        avg_weekly = total_amount / Decimal(num_weeks)

        # Redistribute schedules to be more even
        # This is a simplified approach - just add a note about spreading
        # A full implementation would create new schedules to smooth the distribution

        for schedule in future_schedules:
            original_amount = schedule.estimated_amount or Decimal("0")
            # Adjust amount closer to average (simple smoothing)
            adjustment_factor = Decimal("0.7")  # Move 30% toward average
            new_amount = original_amount * adjustment_factor + avg_weekly * (1 - adjustment_factor)

            if abs(new_amount - original_amount) > Decimal("10"):  # Only if meaningful change
                modified_data = {
                    "id": schedule.id,
                    "estimated_amount": str(new_amount),
                    "original_amount": str(original_amount),
                    "spread_adjustment": str(new_amount - original_amount),
                    "confidence": "medium",
                }

                delta.updated_schedules.append(self.create_schedule_delta(
                    scenario_id=definition.scenario_id,
                    operation="modify",
                    schedule_data=modified_data,
                    original_schedule_id=schedule.id,
                    obligation_id=schedule.obligation_id,
                    linked_change_id="linked_spread",
                    change_reason="Payment smoothed to reduce clustering risk",
                    confidence="medium",
                    confidence_factors=["spread_payments", "clustering_mitigation"],
                ))

    def _calculate_confidence_breakdown(self, delta: ScenarioDelta) -> Dict[str, int]:
        """Calculate confidence breakdown across all schedule deltas."""
        breakdown = {"high": 0, "medium": 0, "low": 0}

        for sched in delta.created_schedules + delta.updated_schedules:
            conf = sched.confidence or "medium"
            if conf in breakdown:
                breakdown[conf] += 1

        return breakdown
