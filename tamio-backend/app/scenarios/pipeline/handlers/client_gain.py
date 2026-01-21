"""
Client Gain Handler - V4 Canonical Model.

Implements the Mermaid decision tree using ObligationSchedule overlays:
1. Input start date + agreement type
2. Input amount + cadence + payment terms
3. Create virtual Revenue ObligationAgreement + Schedules
4. Generate expected cash-in schedules
5. Prompt for capacity costs (contractors/hiring/tools/onboarding)
6. Create virtual expense ObligationAgreement + Schedules
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


class ClientGainHandler(BaseScenarioHandler):
    """
    Handler for Client Gain scenarios.

    V4: Creates virtual ObligationAgreements and ObligationSchedules
    for both revenue and capacity costs.
    """

    def required_params(self) -> List[str]:
        return [
            "client_name",
            "start_date",
            "agreement_type",
            "monthly_amount",
        ]

    def linked_prompt_types(self) -> List[str]:
        return [
            "add_contractors",
            "add_hiring",
            "add_tools",
            "add_onboarding",
        ]

    async def apply(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
    ) -> ScenarioDelta:
        """
        Apply client gain to add new revenue stream and optional capacity costs.

        Steps per Mermaid flowchart:
        1. Create virtual revenue ObligationAgreement
        2. Generate revenue schedules based on agreement type
        3. If capacity costs configured:
           a. Create virtual expense ObligationAgreement
           b. Add recurring cost schedules
           c. Add one-off onboarding schedules
        """
        delta = ScenarioDelta(scenario_id=definition.scenario_id)
        params = definition.parameters

        client_name = params.get("client_name", "New Client")
        start_date = self._parse_date(params.get("start_date")) or date.today()
        agreement_type = params.get("agreement_type", "retainer")
        monthly_amount = Decimal(str(params.get("monthly_amount", 0)))
        payment_terms_days = int(params.get("payment_terms_days", 30))

        forecast_end = date.today() + timedelta(weeks=13)

        # Step 1: Create virtual revenue ObligationAgreement
        revenue_agreement_id = generate_id("vagrmt")
        revenue_agreement_data = {
            "id": revenue_agreement_id,
            "obligation_type": "revenue",
            "amount_type": "fixed" if agreement_type == "retainer" else "variable",
            "amount_source": "scenario_projection",
            "base_amount": str(monthly_amount),
            "frequency": "monthly" if agreement_type != "project" else "one_time",
            "start_date": str(start_date),
            "category": "revenue",
            "vendor_name": client_name,
            "confidence": "medium",
            "is_virtual": True,
            "scenario_id": definition.scenario_id,
            "agreement_type": agreement_type,  # Track type for display
        }

        delta.created_agreements.append(self.create_agreement_delta(
            scenario_id=definition.scenario_id,
            operation="add",
            agreement_data=revenue_agreement_data,
            change_reason=f"New client: {client_name} ({agreement_type})",
        ))

        # Step 2: Generate revenue schedules based on agreement type
        if agreement_type == "retainer":
            self._generate_retainer_schedules(
                delta, revenue_agreement_id, definition.scenario_id,
                client_name, start_date, forecast_end,
                monthly_amount, payment_terms_days
            )
        elif agreement_type == "project":
            self._generate_project_schedules(
                delta, revenue_agreement_id, definition.scenario_id,
                client_name, start_date, forecast_end,
                monthly_amount, payment_terms_days
            )
        elif agreement_type == "usage":
            self._generate_usage_schedules(
                delta, revenue_agreement_id, definition.scenario_id,
                client_name, start_date, forecast_end,
                monthly_amount, payment_terms_days
            )

        # Step 3: Apply linked capacity costs
        needs_capacity = params.get("linked_needs_capacity", False)

        if needs_capacity:
            await self._apply_capacity_costs(
                delta, definition, client_name, start_date, forecast_end
            )

        # Update summary
        delta.total_schedules_affected = len(delta.created_schedules)

        # Calculate net impact
        total_revenue = Decimal("0")
        total_costs = Decimal("0")

        for sched in delta.created_schedules:
            amount = Decimal(str(sched.schedule_data.get("estimated_amount", 0)))
            category = sched.schedule_data.get("category", "")

            if category == "revenue":
                total_revenue += amount
            else:
                total_costs += amount

        delta.net_cash_impact = total_revenue - total_costs

        # Confidence breakdown
        delta.confidence_breakdown = self._calculate_confidence_breakdown(delta)
        delta.overall_confidence = "medium" if agreement_type == "retainer" else "low"

        return delta

    def _generate_retainer_schedules(
        self,
        delta: ScenarioDelta,
        agreement_id: str,
        scenario_id: str,
        client_name: str,
        start_date: date,
        forecast_end: date,
        monthly_amount: Decimal,
        payment_terms_days: int,
    ) -> None:
        """Generate monthly retainer revenue schedules."""
        current_date = start_date

        while current_date <= forecast_end:
            # Adjust for payment terms
            payment_date = current_date + timedelta(days=payment_terms_days)

            if payment_date <= forecast_end:
                weeks_out = (payment_date - date.today()).days // 7
                confidence, factors = self._calculate_confidence(
                    weeks_out=weeks_out,
                    scenario_type="client_gain",
                    has_integration_backing=False,
                )

                schedule_data = {
                    "id": generate_id("vsched"),
                    "obligation_id": agreement_id,
                    "due_date": str(payment_date),
                    "estimated_amount": str(monthly_amount),
                    "estimate_source": "scenario_projection",
                    "confidence": confidence,
                    "status": "scheduled",
                    "category": "revenue",
                    "source_name": client_name,
                    "is_recurring": True,
                    "recurrence_pattern": "monthly",
                    "is_virtual": True,
                    "scenario_id": scenario_id,
                }

                delta.created_schedules.append(self.create_schedule_delta(
                    scenario_id=scenario_id,
                    operation="add",
                    schedule_data=schedule_data,
                    obligation_id=agreement_id,
                    change_reason=f"New client '{client_name}' retainer payment",
                    confidence=confidence,
                    confidence_factors=factors + ["new_client_retainer"],
                ))

            # Move to next month
            current_date = self._next_month(current_date)

    def _generate_project_schedules(
        self,
        delta: ScenarioDelta,
        agreement_id: str,
        scenario_id: str,
        client_name: str,
        start_date: date,
        forecast_end: date,
        total_amount: Decimal,
        payment_terms_days: int,
    ) -> None:
        """Generate milestone-based project schedules (50% upfront, 50% at end)."""
        upfront_amount = total_amount * Decimal("0.5")
        final_amount = total_amount * Decimal("0.5")

        # Milestone 1: Upfront payment
        upfront_date = start_date + timedelta(days=payment_terms_days)
        if upfront_date <= forecast_end:
            schedule_data = {
                "id": generate_id("vsched"),
                "obligation_id": agreement_id,
                "due_date": str(upfront_date),
                "estimated_amount": str(upfront_amount),
                "estimate_source": "scenario_projection",
                "confidence": "medium",
                "status": "scheduled",
                "category": "revenue",
                "source_name": f"{client_name} - Milestone 1",
                "is_recurring": False,
                "is_virtual": True,
                "scenario_id": scenario_id,
                "milestone_number": 1,
            }

            delta.created_schedules.append(self.create_schedule_delta(
                scenario_id=scenario_id,
                operation="add",
                schedule_data=schedule_data,
                obligation_id=agreement_id,
                change_reason=f"New client '{client_name}' project milestone 1 (50%)",
                confidence="medium",
                confidence_factors=["project_milestone_upfront"],
            ))

        # Milestone 2: Final payment (3 months later)
        final_date = start_date + timedelta(days=90 + payment_terms_days)
        if final_date <= forecast_end:
            schedule_data = {
                "id": generate_id("vsched"),
                "obligation_id": agreement_id,
                "due_date": str(final_date),
                "estimated_amount": str(final_amount),
                "estimate_source": "scenario_projection",
                "confidence": "low",  # Final milestone is less certain
                "status": "scheduled",
                "category": "revenue",
                "source_name": f"{client_name} - Milestone 2",
                "is_recurring": False,
                "is_virtual": True,
                "scenario_id": scenario_id,
                "milestone_number": 2,
            }

            delta.created_schedules.append(self.create_schedule_delta(
                scenario_id=scenario_id,
                operation="add",
                schedule_data=schedule_data,
                obligation_id=agreement_id,
                change_reason=f"New client '{client_name}' project milestone 2 (50%)",
                confidence="low",
                confidence_factors=["project_milestone_final", "delivery_dependent"],
            ))

    def _generate_usage_schedules(
        self,
        delta: ScenarioDelta,
        agreement_id: str,
        scenario_id: str,
        client_name: str,
        start_date: date,
        forecast_end: date,
        monthly_amount: Decimal,
        payment_terms_days: int,
    ) -> None:
        """Generate usage-based revenue schedules (low confidence)."""
        current_date = start_date

        while current_date <= forecast_end:
            payment_date = current_date + timedelta(days=payment_terms_days)

            if payment_date <= forecast_end:
                schedule_data = {
                    "id": generate_id("vsched"),
                    "obligation_id": agreement_id,
                    "due_date": str(payment_date),
                    "estimated_amount": str(monthly_amount),
                    "estimate_source": "scenario_projection",
                    "confidence": "low",  # Usage-based is inherently variable
                    "status": "scheduled",
                    "category": "revenue",
                    "source_name": client_name,
                    "is_recurring": False,  # Each month varies
                    "is_virtual": True,
                    "scenario_id": scenario_id,
                }

                delta.created_schedules.append(self.create_schedule_delta(
                    scenario_id=scenario_id,
                    operation="add",
                    schedule_data=schedule_data,
                    obligation_id=agreement_id,
                    change_reason=f"New client '{client_name}' usage-based payment",
                    confidence="low",
                    confidence_factors=["usage_based", "variable_amount"],
                ))

            current_date = self._next_month(current_date)

    async def _apply_capacity_costs(
        self,
        delta: ScenarioDelta,
        definition: ScenarioDefinition,
        client_name: str,
        start_date: date,
        forecast_end: date,
    ) -> None:
        """Apply linked capacity costs as virtual schedules."""
        params = definition.parameters
        capacity_types = params.get("linked_capacity_types", [])
        monthly_cost = Decimal(str(params.get("linked_monthly_cost", 0)))
        onetime_cost = Decimal(str(params.get("linked_onetime_cost", 0)))

        # Create virtual expense agreement
        expense_agreement_id = generate_id("vagrmt")

        # Determine category from capacity types
        if "hiring" in capacity_types:
            category = "payroll"
            obligation_type = "payroll"
        elif "contractors" in capacity_types:
            category = "contractors"
            obligation_type = "contractor"
        else:
            category = "software"
            obligation_type = "subscription"

        expense_agreement_data = {
            "id": expense_agreement_id,
            "obligation_type": obligation_type,
            "amount_type": "fixed",
            "amount_source": "scenario_projection",
            "base_amount": str(monthly_cost),
            "frequency": "monthly",
            "start_date": str(start_date),
            "category": category,
            "vendor_name": f"Capacity for {client_name}",
            "confidence": "high",
            "is_virtual": True,
            "scenario_id": definition.scenario_id,
        }

        if monthly_cost > 0 or onetime_cost > 0:
            delta.created_agreements.append(self.create_agreement_delta(
                scenario_id=definition.scenario_id,
                operation="add",
                agreement_data=expense_agreement_data,
                linked_change_id="linked_capacity",
                change_reason=f"Capacity costs for new client '{client_name}'",
            ))

        # Add one-time onboarding costs
        if onetime_cost > 0 and "onboarding" in capacity_types:
            onboarding_schedule = {
                "id": generate_id("vsched"),
                "obligation_id": expense_agreement_id,
                "due_date": str(start_date),
                "estimated_amount": str(onetime_cost),
                "estimate_source": "scenario_projection",
                "confidence": "high",
                "status": "scheduled",
                "category": "onboarding",
                "source_name": f"Onboarding - {client_name}",
                "is_recurring": False,
                "is_virtual": True,
                "scenario_id": definition.scenario_id,
            }

            delta.created_schedules.append(self.create_schedule_delta(
                scenario_id=definition.scenario_id,
                operation="add",
                schedule_data=onboarding_schedule,
                obligation_id=expense_agreement_id,
                linked_change_id="linked_onboarding",
                change_reason=f"Onboarding costs for new client '{client_name}'",
                confidence="high",
                confidence_factors=["one_time_cost", "user_provided"],
            ))

        # Add recurring capacity costs
        if monthly_cost > 0:
            current_date = start_date

            while current_date <= forecast_end:
                weeks_out = (current_date - date.today()).days // 7
                confidence, factors = self._calculate_confidence(
                    weeks_out=weeks_out,
                    scenario_type="client_gain",
                    has_integration_backing=False,
                )

                schedule_data = {
                    "id": generate_id("vsched"),
                    "obligation_id": expense_agreement_id,
                    "due_date": str(current_date),
                    "estimated_amount": str(monthly_cost),
                    "estimate_source": "scenario_projection",
                    "confidence": confidence,
                    "status": "scheduled",
                    "category": category,
                    "source_name": f"Capacity for {client_name}",
                    "is_recurring": True,
                    "recurrence_pattern": "monthly",
                    "is_virtual": True,
                    "scenario_id": definition.scenario_id,
                }

                delta.created_schedules.append(self.create_schedule_delta(
                    scenario_id=definition.scenario_id,
                    operation="add",
                    schedule_data=schedule_data,
                    obligation_id=expense_agreement_id,
                    linked_change_id="linked_capacity",
                    change_reason=f"Capacity costs for new client '{client_name}'",
                    confidence=confidence,
                    confidence_factors=factors + ["linked_to_client"],
                ))

                current_date = self._next_month(current_date)

    def _next_month(self, current_date: date) -> date:
        """Move to the same day in the next month, handling edge cases."""
        if current_date.month == 12:
            return date(current_date.year + 1, 1, current_date.day)
        else:
            try:
                return date(current_date.year, current_date.month + 1, current_date.day)
            except ValueError:
                # Handle month-end edge cases (e.g., Jan 31 -> Feb 28)
                return date(current_date.year, current_date.month + 1, 28)

    def _calculate_confidence_breakdown(self, delta: ScenarioDelta) -> Dict[str, int]:
        """Calculate confidence breakdown across all schedule deltas."""
        breakdown = {"high": 0, "medium": 0, "low": 0}

        for sched in delta.created_schedules + delta.updated_schedules:
            conf = sched.confidence or "medium"
            if conf in breakdown:
                breakdown[conf] += 1

        return breakdown
