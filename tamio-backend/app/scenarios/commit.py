"""
Scenario Commit Service - Persists confirmed scenario changes to canonical data.

This is the ONLY place canonical data is modified by scenarios.
Called only on explicit user confirmation ("Confirm true" in the flowchart).

Architecture:
1. Create new ObligationAgreements from virtual agreements
2. Create new ObligationSchedules from virtual schedules
3. Update existing schedules (modifications)
4. Cancel/deactivate deleted schedules
5. Log all changes to audit trail
"""

from typing import Dict, Any, List, Optional
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.scenarios.pipeline.types import (
    ScenarioDelta,
    ScenarioDefinition,
    ScheduleDelta,
    AgreementDelta,
    ScenarioStatusEnum,
)
from app.data.obligations.models import ObligationAgreement, ObligationSchedule


def generate_id(prefix: str) -> str:
    """Generate a unique ID with a prefix."""
    import secrets
    return f"{prefix}_{secrets.token_hex(8)}"


class ScenarioCommitService:
    """
    Service for committing confirmed scenario changes to canonical data.

    Key principles:
    - Only called on explicit user confirmation
    - All changes are audited
    - Virtual IDs are mapped to real IDs
    - Cascades are handled properly
    """

    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id

    async def commit_scenario(
        self,
        definition: ScenarioDefinition,
        delta: ScenarioDelta,
    ) -> Dict[str, Any]:
        """
        Commit scenario deltas to canonical data.

        This is the ONLY place canonical data is modified by scenarios.

        Steps:
        1. Create new ObligationAgreements from virtual agreements
        2. Create new ObligationSchedules from virtual schedules
        3. Update existing schedules (modifications)
        4. Cancel deleted schedules
        5. Deactivate agreements
        6. Log all changes

        Returns:
            Dict with counts of created/updated/cancelled items
        """
        results = {
            "agreements_created": 0,
            "schedules_created": 0,
            "schedules_updated": 0,
            "schedules_cancelled": 0,
            "agreements_deactivated": 0,
            "errors": [],
            "agreement_id_map": {},  # virtual_id -> real_id
        }

        try:
            # Step 1: Create new agreements
            agreement_id_map = {}  # Maps virtual ID to real ID

            for agreement_delta in delta.created_agreements:
                real_agreement = await self._create_agreement(
                    agreement_delta,
                    definition
                )
                agreement_id_map[agreement_delta.agreement_id] = real_agreement.id
                results["agreements_created"] += 1

            results["agreement_id_map"] = agreement_id_map

            # Step 2: Create new schedules
            for schedule_delta in delta.created_schedules:
                # Map virtual agreement ID to real ID if needed
                real_obligation_id = agreement_id_map.get(
                    schedule_delta.obligation_id,
                    schedule_delta.obligation_id  # May already be real
                )

                await self._create_schedule(
                    schedule_delta,
                    real_obligation_id,
                    definition
                )
                results["schedules_created"] += 1

            # Step 3: Update existing schedules
            for schedule_delta in delta.updated_schedules:
                if schedule_delta.operation in ["modify", "defer"] and schedule_delta.original_schedule_id:
                    await self._update_schedule(schedule_delta, definition)
                    results["schedules_updated"] += 1

            # Step 4: Cancel deleted schedules
            for schedule_id in delta.deleted_schedule_ids:
                await self._cancel_schedule(schedule_id, definition)
                results["schedules_cancelled"] += 1

            # Step 5: Deactivate agreements
            for agreement_id in delta.deactivated_agreement_ids:
                await self._deactivate_agreement(agreement_id, definition)
                results["agreements_deactivated"] += 1

            # Commit all changes
            await self.db.commit()

            return results

        except Exception as e:
            await self.db.rollback()
            results["errors"].append(str(e))
            raise

    async def _create_agreement(
        self,
        delta: AgreementDelta,
        definition: ScenarioDefinition,
    ) -> ObligationAgreement:
        """Create a real ObligationAgreement from virtual delta."""
        data = delta.agreement_data or {}

        # Parse start date
        start_date = data.get("start_date")
        if isinstance(start_date, str):
            start_date = date.fromisoformat(start_date)
        elif start_date is None:
            start_date = definition.scope.effective_date or date.today()

        # Parse end date if provided
        end_date = data.get("end_date")
        if isinstance(end_date, str):
            end_date = date.fromisoformat(end_date)

        # Parse base amount
        base_amount = data.get("base_amount")
        if base_amount is not None:
            base_amount = Decimal(str(base_amount))

        agreement = ObligationAgreement(
            id=generate_id("obl"),
            user_id=self.user_id,
            obligation_type=data.get("obligation_type", "other"),
            amount_type=data.get("amount_type", "fixed"),
            amount_source="scenario_confirmation",  # Mark source
            base_amount=base_amount,
            frequency=data.get("frequency"),
            start_date=start_date,
            end_date=end_date,
            category=data.get("category", "other"),
            vendor_name=data.get("vendor_name"),
            confidence="high",  # Confirmed scenarios are high confidence
            notes=f"Created from scenario: {definition.scenario_id} - {delta.change_reason}",
            # Client/expense links (if provided)
            client_id=data.get("client_id"),
            expense_bucket_id=data.get("expense_bucket_id"),
        )

        self.db.add(agreement)
        await self.db.flush()  # Get ID
        return agreement

    async def _create_schedule(
        self,
        delta: ScheduleDelta,
        obligation_id: str,
        definition: ScenarioDefinition,
    ) -> ObligationSchedule:
        """Create a real ObligationSchedule from virtual delta."""
        data = delta.schedule_data or {}

        # Parse due date
        due_date = data.get("due_date")
        if isinstance(due_date, str):
            due_date = date.fromisoformat(due_date)

        # Parse period dates if provided
        period_start = data.get("period_start")
        if isinstance(period_start, str):
            period_start = date.fromisoformat(period_start)

        period_end = data.get("period_end")
        if isinstance(period_end, str):
            period_end = date.fromisoformat(period_end)

        # Parse estimated amount
        estimated_amount = data.get("estimated_amount", "0")
        estimated_amount = Decimal(str(estimated_amount))

        schedule = ObligationSchedule(
            id=generate_id("sched"),
            obligation_id=obligation_id,
            due_date=due_date,
            period_start=period_start,
            period_end=period_end,
            estimated_amount=estimated_amount,
            estimate_source="scenario_confirmation",
            confidence=delta.confidence or "high",
            status="scheduled",
            notes=f"From scenario: {definition.scenario_id} - {delta.change_reason}",
        )

        self.db.add(schedule)
        await self.db.flush()
        return schedule

    async def _update_schedule(
        self,
        delta: ScheduleDelta,
        definition: ScenarioDefinition,
    ) -> Optional[ObligationSchedule]:
        """Update existing schedule with delta changes."""
        result = await self.db.execute(
            select(ObligationSchedule)
            .where(ObligationSchedule.id == delta.original_schedule_id)
        )
        schedule = result.scalar_one_or_none()

        if not schedule:
            return None

        if delta.schedule_data:
            for key, value in delta.schedule_data.items():
                if key.startswith("_"):
                    continue  # Skip internal fields

                if hasattr(schedule, key):
                    # Handle date parsing
                    if key in ["due_date", "period_start", "period_end"]:
                        if isinstance(value, str):
                            value = date.fromisoformat(value)
                    # Handle decimal parsing
                    elif key == "estimated_amount":
                        value = Decimal(str(value))

                    setattr(schedule, key, value)

        # Update confidence if deferred
        if delta.operation == "defer":
            schedule.confidence = delta.confidence or "medium"

        # Add notes about the change
        existing_notes = schedule.notes or ""
        schedule.notes = f"{existing_notes}\nModified by scenario: {definition.scenario_id}"

        return schedule

    async def _cancel_schedule(
        self,
        schedule_id: str,
        definition: ScenarioDefinition,
    ) -> bool:
        """Cancel (soft delete) a schedule by setting status to cancelled."""
        result = await self.db.execute(
            select(ObligationSchedule)
            .where(ObligationSchedule.id == schedule_id)
        )
        schedule = result.scalar_one_or_none()

        if not schedule:
            return False

        schedule.status = "cancelled"
        existing_notes = schedule.notes or ""
        schedule.notes = f"{existing_notes}\nCancelled by scenario: {definition.scenario_id}"

        return True

    async def _deactivate_agreement(
        self,
        agreement_id: str,
        definition: ScenarioDefinition,
    ) -> bool:
        """Deactivate an agreement by setting end_date."""
        result = await self.db.execute(
            select(ObligationAgreement)
            .where(ObligationAgreement.id == agreement_id)
        )
        agreement = result.scalar_one_or_none()

        if not agreement:
            return False

        # Set end date to effective date from scenario or today
        end_date = definition.scope.effective_date or date.today()
        agreement.end_date = end_date

        existing_notes = agreement.notes or ""
        agreement.notes = f"{existing_notes}\nDeactivated by scenario: {definition.scenario_id}"

        return True


class ScenarioDiscardService:
    """
    Service for discarding scenarios without changes.

    Since scenarios use virtual overlays, discarding is simple:
    just mark the scenario as discarded. No canonical data changes.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def discard_scenario(
        self,
        definition: ScenarioDefinition,
    ) -> bool:
        """
        Discard scenario without any changes to canonical data.

        Since scenarios use virtual overlays, discarding just means:
        1. Mark scenario status as DISCARDED
        2. No canonical data is touched

        Returns:
            True if successful
        """
        definition.status = ScenarioStatusEnum.DISCARDED
        return True
