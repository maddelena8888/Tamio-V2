"""
Increased Expense Handler - V4 Canonical Model.

Implements the Mermaid decision tree using ObligationSchedule overlays:
1. Select category (Tools/Rent/Marketing/Tax/Other)
2. Choose one-off vs recurring
3. Input amount + start date
4. Create virtual ObligationAgreement + Schedules
5. Optional rule gating (capex gate/buffer)
"""

from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, timedelta
from decimal import Decimal

from app.scenarios.pipeline.handlers.base import BaseScenarioHandler, generate_id
from app.scenarios.pipeline.types import (
    ScenarioDefinition,
    ScenarioDelta,
    ScheduleDelta,
    AgreementDelta,
)


class IncreasedExpenseHandler(BaseScenarioHandler):
    """
    Handler for Increased Expense scenarios.

    V4: Creates virtual ObligationAgreement and ObligationSchedules
    for new expenses.
    """

    def required_params(self) -> List[str]:
        return [
            "category",
            "expense_type",
            "amount",
            "effective_date",
        ]

    def linked_prompt_types(self) -> List[str]:
        return [
            "capex_gate",
            "buffer_gate",
        ]

    async def apply(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
    ) -> ScenarioDelta:
        """
        Apply increased expense to add new expense schedules.

        Steps per Mermaid flowchart:
        1. Create virtual expense ObligationAgreement
        2. Create expense schedule(s) based on type (one-off vs recurring)
        3. Tag as gated if configured
        """
        delta = ScenarioDelta(scenario_id=definition.scenario_id)
        params = definition.parameters

        category = params.get("category", "other")
        expense_name = params.get("expense_name", "New Expense")
        expense_type = params.get("expense_type", "one_off")
        amount = Decimal(str(params.get("amount", 0)))

        effective_date_str = params.get("effective_date")
        if isinstance(effective_date_str, str):
            effective_date = date.fromisoformat(effective_date_str)
        else:
            effective_date = effective_date_str or date.today()

        # Check for gating
        is_gated = params.get("linked_is_gated", False)
        gating_rule = params.get("linked_gating_rule")

        forecast_end = date.today() + timedelta(weeks=13)

        # Determine obligation type from category
        obligation_type_map = {
            "software": "subscription",
            "rent": "subscription",
            "marketing": "other",
            "tax": "tax",
            "equipment": "other",
            "other": "other",
        }
        obligation_type = obligation_type_map.get(category, "other")

        # Step 1: Create virtual expense ObligationAgreement
        expense_agreement_id = generate_id("vagrmt")
        expense_agreement_data = {
            "id": expense_agreement_id,
            "obligation_type": obligation_type,
            "amount_type": "fixed",
            "amount_source": "scenario_projection",
            "base_amount": str(amount),
            "frequency": "one_time" if expense_type == "one_off" else params.get("frequency", "monthly"),
            "start_date": str(effective_date),
            "category": category,
            "vendor_name": expense_name,
            "confidence": "high",
            "is_virtual": True,
            "scenario_id": definition.scenario_id,
            "is_gated": is_gated,
            "gating_rule": gating_rule,
        }

        delta.created_agreements.append(self.create_agreement_delta(
            scenario_id=definition.scenario_id,
            operation="add",
            agreement_data=expense_agreement_data,
            change_reason=f"New expense: {expense_name} ({category})",
        ))

        # Step 2: Create expense schedules
        if expense_type == "one_off":
            # Single expense schedule
            self._add_one_off_schedule(
                delta, expense_agreement_id, definition.scenario_id,
                expense_name, effective_date, amount, category,
                is_gated, gating_rule
            )
        else:
            # Recurring expense schedules
            frequency = params.get("frequency", "monthly")
            self._add_recurring_schedules(
                delta, expense_agreement_id, definition.scenario_id,
                expense_name, effective_date, forecast_end, amount,
                category, frequency, is_gated, gating_rule
            )

        # Update summary
        delta.total_schedules_affected = len(delta.created_schedules)

        # Net impact = total expense amount
        total_expense = sum(
            Decimal(str(s.schedule_data.get("estimated_amount", 0)))
            for s in delta.created_schedules
        )
        delta.net_cash_impact = -total_expense

        # Add gating info to changes_by_linked_change if applicable
        if is_gated:
            delta.changes_by_linked_change[f"gated_{gating_rule}"] = len(delta.created_schedules)

        # Confidence breakdown
        delta.confidence_breakdown = self._calculate_confidence_breakdown(delta)
        delta.overall_confidence = "high"  # User-provided expenses are high confidence

        return delta

    def _add_one_off_schedule(
        self,
        delta: ScenarioDelta,
        agreement_id: str,
        scenario_id: str,
        expense_name: str,
        effective_date: date,
        amount: Decimal,
        category: str,
        is_gated: bool,
        gating_rule: str,
    ) -> None:
        """Add a single one-off expense schedule."""
        schedule_data = {
            "id": generate_id("vsched"),
            "obligation_id": agreement_id,
            "due_date": str(effective_date),
            "estimated_amount": str(amount),
            "estimate_source": "scenario_projection",
            "confidence": "high",
            "status": "scheduled",
            "category": category,
            "source_name": expense_name,
            "is_recurring": False,
            "is_virtual": True,
            "scenario_id": scenario_id,
            "is_gated": is_gated,
            "gating_rule": gating_rule,
        }

        delta.created_schedules.append(self.create_schedule_delta(
            scenario_id=scenario_id,
            operation="add",
            schedule_data=schedule_data,
            obligation_id=agreement_id,
            change_reason=f"One-off expense: {expense_name}",
            confidence="high",
            confidence_factors=["user_provided_amount", "one_time_expense"],
        ))

    def _add_recurring_schedules(
        self,
        delta: ScenarioDelta,
        agreement_id: str,
        scenario_id: str,
        expense_name: str,
        start_date: date,
        end_date: date,
        amount: Decimal,
        category: str,
        frequency: str,
        is_gated: bool,
        gating_rule: str,
    ) -> None:
        """Add recurring expense schedules."""
        # Determine interval based on frequency
        if frequency == "quarterly":
            interval_days = 90
        elif frequency == "annual":
            interval_days = 365
        elif frequency == "weekly":
            interval_days = 7
        elif frequency == "bi-weekly":
            interval_days = 14
        else:  # monthly
            interval_days = 30

        current_date = start_date
        while current_date <= end_date:
            weeks_out = (current_date - date.today()).days // 7
            confidence, factors = self._calculate_confidence(
                weeks_out=weeks_out,
                scenario_type="increased_expense",
                has_integration_backing=False,
            )

            schedule_data = {
                "id": generate_id("vsched"),
                "obligation_id": agreement_id,
                "due_date": str(current_date),
                "estimated_amount": str(amount),
                "estimate_source": "scenario_projection",
                "confidence": confidence,
                "status": "scheduled",
                "category": category,
                "source_name": expense_name,
                "is_recurring": True,
                "recurrence_pattern": frequency,
                "is_virtual": True,
                "scenario_id": scenario_id,
                "is_gated": is_gated,
                "gating_rule": gating_rule,
            }

            delta.created_schedules.append(self.create_schedule_delta(
                scenario_id=scenario_id,
                operation="add",
                schedule_data=schedule_data,
                obligation_id=agreement_id,
                change_reason=f"Recurring expense: {expense_name} ({frequency})",
                confidence=confidence,
                confidence_factors=factors + ["recurring_expense", f"{frequency}_cadence"],
            ))

            current_date += timedelta(days=interval_days)

    def _calculate_confidence_breakdown(self, delta: ScenarioDelta) -> Dict[str, int]:
        """Calculate confidence breakdown across all schedule deltas."""
        breakdown = {"high": 0, "medium": 0, "low": 0}

        for sched in delta.created_schedules + delta.updated_schedules:
            conf = sched.confidence or "medium"
            if conf in breakdown:
                breakdown[conf] += 1

        return breakdown
