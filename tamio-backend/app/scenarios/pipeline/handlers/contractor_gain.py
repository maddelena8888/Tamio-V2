"""
Contractor Gain Handler - V4 Canonical Model.

Implements the Mermaid decision tree using ObligationSchedule overlays:
1. Input start date + monthly estimate
2. Choose fixed vs variable
3. Create virtual contractor ObligationAgreement + Schedules
4. Optional linkage to client/project
5. Apply lag if linked
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


class ContractorGainHandler(BaseScenarioHandler):
    """
    Handler for Contractor Gain scenarios.

    V4: Creates virtual ObligationAgreement and ObligationSchedules
    for new contractor expenses.
    """

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
        Apply contractor gain to add contractor expense schedules.

        Steps per Mermaid flowchart:
        1. Create virtual contractor ObligationAgreement
        2. Generate recurring contractor schedules
        3. Apply client/project linkage if configured
        4. Apply lag if linked
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
        base_confidence = "high" if cost_type == "fixed" else "medium"

        # Step 1: Create virtual contractor ObligationAgreement
        contractor_agreement_id = generate_id("vagrmt")
        contractor_agreement_data = {
            "id": contractor_agreement_id,
            "obligation_type": "contractor",
            "amount_type": cost_type,
            "amount_source": "scenario_projection",
            "base_amount": str(monthly_estimate),
            "frequency": "monthly",
            "start_date": str(effective_start),
            "category": "contractors",
            "vendor_name": contractor_name,
            "confidence": base_confidence,
            "is_virtual": True,
            "scenario_id": definition.scenario_id,
            "linked_client_id": linked_client_id if is_linked else None,
        }

        change_reason = f"New contractor: {contractor_name}"
        if is_linked:
            change_reason += f" (linked to client, {lag_weeks}w lag)"

        delta.created_agreements.append(self.create_agreement_delta(
            scenario_id=definition.scenario_id,
            operation="add",
            agreement_data=contractor_agreement_data,
            linked_change_id="linked_client" if is_linked else None,
            change_reason=change_reason,
        ))

        # Step 2: Generate recurring contractor schedules
        contractor_schedules = self.generate_recurring_schedules(
            agreement_id=contractor_agreement_id,
            scenario_id=definition.scenario_id,
            start_date=effective_start,
            end_date=forecast_end,
            amount=monthly_estimate,
            frequency="monthly",
            category="contractors",
            source_name=contractor_name,
            confidence=base_confidence,
        )

        for schedule_data in contractor_schedules:
            # Calculate weeks out for confidence adjustment
            due_date = date.fromisoformat(schedule_data["due_date"])
            weeks_out = (due_date - date.today()).days // 7

            confidence, factors = self._calculate_confidence(
                weeks_out=weeks_out,
                scenario_type="contractor_gain",
                has_integration_backing=False,
            )

            # Adjust confidence for variable costs
            if cost_type == "variable":
                confidence = "medium" if confidence == "high" else "low"
                factors.append("variable_cost")
            else:
                factors.append("fixed_cost")

            delta.created_schedules.append(self.create_schedule_delta(
                scenario_id=definition.scenario_id,
                operation="add",
                schedule_data=schedule_data,
                obligation_id=contractor_agreement_id,
                linked_change_id="linked_client" if is_linked else None,
                change_reason=change_reason,
                confidence=confidence,
                confidence_factors=factors + ["contractor_expense"],
            ))

        # Update summary
        delta.total_schedules_affected = len(delta.created_schedules)

        # Net impact = total contractor expense
        total_expense = sum(
            Decimal(str(s.schedule_data.get("estimated_amount", 0)))
            for s in delta.created_schedules
        )
        delta.net_cash_impact = -total_expense

        # Confidence breakdown
        delta.confidence_breakdown = self._calculate_confidence_breakdown(delta)
        delta.overall_confidence = base_confidence

        return delta

    def _calculate_confidence_breakdown(self, delta: ScenarioDelta) -> Dict[str, int]:
        """Calculate confidence breakdown across all schedule deltas."""
        breakdown = {"high": 0, "medium": 0, "low": 0}

        for sched in delta.created_schedules + delta.updated_schedules:
            conf = sched.confidence or "medium"
            if conf in breakdown:
                breakdown[conf] += 1

        return breakdown
