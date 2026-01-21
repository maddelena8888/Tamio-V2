"""
Hiring (Payroll Gain) Handler - V4 Canonical Model.

Implements the Mermaid decision tree using ObligationSchedule overlays:
1. Input role + start date
2. Input monthly cost + pay cycle
3. Optional one-off hiring costs
4. Create virtual payroll ObligationAgreement + Schedules
5. Optional linked revenue changes
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


class HiringHandler(BaseScenarioHandler):
    """
    Handler for Hiring scenarios.

    V4: Creates virtual ObligationAgreement and ObligationSchedules
    instead of CashEvents directly.
    """

    def required_params(self) -> List[str]:
        return [
            "role_title",
            "start_date",
            "monthly_cost",
        ]

    def linked_prompt_types(self) -> List[str]:
        return [
            "client_gain",
            "upsell",
        ]

    async def apply(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
    ) -> ScenarioDelta:
        """
        Apply hiring scenario to add payroll costs.

        Steps per Mermaid flowchart:
        1. Create virtual payroll ObligationAgreement
        2. Generate recurring payroll schedules
        3. Add one-off hiring costs schedule (if applicable)
        4. Apply linked revenue changes (if configured)
        """
        delta = ScenarioDelta(scenario_id=definition.scenario_id)
        params = definition.parameters

        role_title = params.get("role_title", "New Hire")
        start_date = self._parse_date(params.get("start_date")) or date.today()
        monthly_cost = Decimal(str(params.get("monthly_cost", 0)))
        pay_frequency = params.get("pay_frequency", "monthly")
        has_onboarding = params.get("has_onboarding_costs", False)
        onboarding_costs = Decimal(str(params.get("onboarding_costs", 0))) if has_onboarding else Decimal("0")

        forecast_end = date.today() + timedelta(weeks=13)

        # Step 1: Create virtual payroll ObligationAgreement
        payroll_agreement_id = generate_id("vagrmt")
        payroll_agreement_data = {
            "id": payroll_agreement_id,
            "obligation_type": "payroll",
            "amount_type": "fixed",
            "amount_source": "scenario_projection",
            "base_amount": str(monthly_cost),
            "frequency": pay_frequency,
            "start_date": str(start_date),
            "category": "payroll",
            "vendor_name": role_title,
            "confidence": "high",
            "is_virtual": True,
            "scenario_id": definition.scenario_id,
        }

        delta.created_agreements.append(self.create_agreement_delta(
            scenario_id=definition.scenario_id,
            operation="add",
            agreement_data=payroll_agreement_data,
            change_reason=f"New hire: {role_title}",
        ))

        # Step 2: Generate recurring payroll schedules
        payroll_schedules = self.generate_recurring_schedules(
            agreement_id=payroll_agreement_id,
            scenario_id=definition.scenario_id,
            start_date=start_date,
            end_date=forecast_end,
            amount=monthly_cost,
            frequency=pay_frequency,
            category="payroll",
            source_name=role_title,
            confidence="high",
        )

        for schedule_data in payroll_schedules:
            # Calculate weeks out for confidence adjustment
            due_date = date.fromisoformat(schedule_data["due_date"])
            weeks_out = (due_date - date.today()).days // 7

            confidence, factors = self._calculate_confidence(
                weeks_out=weeks_out,
                scenario_type="hiring",
                has_integration_backing=False,
            )

            delta.created_schedules.append(self.create_schedule_delta(
                scenario_id=definition.scenario_id,
                operation="add",
                schedule_data=schedule_data,
                obligation_id=payroll_agreement_id,
                change_reason=f"Payroll for new hire: {role_title}",
                confidence=confidence,
                confidence_factors=factors + ["user_provided_salary", "standard_pay_cycle"],
            ))

        # Step 3: Add one-off hiring costs (if applicable)
        if onboarding_costs > 0:
            onboarding_schedule_data = {
                "id": generate_id("vsched"),
                "obligation_id": payroll_agreement_id,
                "due_date": str(start_date),
                "estimated_amount": str(onboarding_costs),
                "estimate_source": "scenario_projection",
                "confidence": "high",
                "status": "scheduled",
                "category": "onboarding",
                "source_name": f"Hiring costs - {role_title}",
                "is_recurring": False,
                "is_virtual": True,
                "scenario_id": definition.scenario_id,
            }

            delta.created_schedules.append(self.create_schedule_delta(
                scenario_id=definition.scenario_id,
                operation="add",
                schedule_data=onboarding_schedule_data,
                obligation_id=payroll_agreement_id,
                change_reason=f"One-time hiring costs for {role_title}",
                confidence="high",
                confidence_factors=["user_provided_amount", "one_time_cost"],
            ))

        # Step 4: Apply linked revenue changes (if configured)
        needs_revenue = params.get("linked_needs_revenue", False)

        if needs_revenue:
            revenue_increase = Decimal(str(params.get("linked_revenue_increase", 0)))

            if revenue_increase > 0:
                # Create virtual revenue agreement
                revenue_agreement_id = generate_id("vagrmt")
                revenue_agreement_data = {
                    "id": revenue_agreement_id,
                    "obligation_type": "revenue",
                    "amount_type": "variable",  # Revenue growth is less certain
                    "amount_source": "scenario_projection",
                    "base_amount": str(revenue_increase),
                    "frequency": "monthly",
                    "start_date": str(start_date),
                    "category": "revenue",
                    "vendor_name": f"Revenue growth from {role_title}",
                    "confidence": "low",  # Projected revenue is lower confidence
                    "is_virtual": True,
                    "scenario_id": definition.scenario_id,
                }

                delta.created_agreements.append(self.create_agreement_delta(
                    scenario_id=definition.scenario_id,
                    operation="add",
                    agreement_data=revenue_agreement_data,
                    linked_change_id="linked_revenue",
                    change_reason=f"Expected revenue growth from {role_title}",
                ))

                # Generate revenue schedules
                revenue_schedules = self._generate_monthly_schedules(
                    agreement_id=revenue_agreement_id,
                    scenario_id=definition.scenario_id,
                    start_date=start_date,
                    end_date=forecast_end,
                    amount=revenue_increase,
                    category="revenue",
                    source_name=f"Revenue from {role_title}",
                )

                for schedule_data in revenue_schedules:
                    delta.created_schedules.append(self.create_schedule_delta(
                        scenario_id=definition.scenario_id,
                        operation="add",
                        schedule_data=schedule_data,
                        obligation_id=revenue_agreement_id,
                        linked_change_id="linked_revenue",
                        change_reason=f"Expected revenue growth from {role_title}",
                        confidence="low",
                        confidence_factors=["projected_revenue", "hire_dependent"],
                    ))

        # Update summary
        delta.total_schedules_affected = len(delta.created_schedules)

        # Calculate net impact
        total_costs = Decimal("0")
        total_revenue = Decimal("0")

        for sched in delta.created_schedules:
            amount = Decimal(str(sched.schedule_data.get("estimated_amount", 0)))
            category = sched.schedule_data.get("category", "")

            if category in ["revenue"]:
                total_revenue += amount
            else:
                total_costs += amount

        delta.net_cash_impact = total_revenue - total_costs

        # Confidence breakdown
        delta.confidence_breakdown = self._calculate_confidence_breakdown(delta)
        delta.overall_confidence = "high" if not needs_revenue else "medium"

        return delta

    def _generate_monthly_schedules(
        self,
        agreement_id: str,
        scenario_id: str,
        start_date: date,
        end_date: date,
        amount: Decimal,
        category: str,
        source_name: str,
    ) -> List[Dict[str, Any]]:
        """Generate monthly schedule data dictionaries."""
        schedules = []
        current_date = start_date

        while current_date <= end_date:
            schedules.append({
                "id": generate_id("vsched"),
                "obligation_id": agreement_id,
                "due_date": str(current_date),
                "estimated_amount": str(amount),
                "estimate_source": "scenario_projection",
                "confidence": "low",
                "status": "scheduled",
                "category": category,
                "source_name": source_name,
                "is_recurring": True,
                "recurrence_pattern": "monthly",
                "is_virtual": True,
                "scenario_id": scenario_id,
            })

            # Move to next month
            if current_date.month == 12:
                current_date = date(current_date.year + 1, 1, current_date.day)
            else:
                try:
                    current_date = date(current_date.year, current_date.month + 1, current_date.day)
                except ValueError:
                    # Handle months with fewer days
                    current_date = date(current_date.year, current_date.month + 1, 28)

        return schedules

    def _calculate_confidence_breakdown(self, delta: ScenarioDelta) -> Dict[str, int]:
        """Calculate confidence breakdown across all schedule deltas."""
        breakdown = {"high": 0, "medium": 0, "low": 0}

        for sched in delta.created_schedules + delta.updated_schedules:
            conf = sched.confidence or "medium"
            if conf in breakdown:
                breakdown[conf] += 1

        return breakdown
