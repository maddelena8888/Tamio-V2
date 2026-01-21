"""
Base Scenario Handler - Abstract base class for scenario handlers.

V4: Extended with ObligationSchedule-based delta helpers for canonical model.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import secrets

from app.scenarios.pipeline.types import (
    ScenarioDefinition,
    ScenarioDelta,
    PromptRequest,
    EventDelta,
    ScheduleDelta,
    AgreementDelta,
)
from app.data.obligations.models import ObligationAgreement, ObligationSchedule


def generate_id(prefix: str) -> str:
    """Generate a unique ID with a prefix."""
    return f"{prefix}_{secrets.token_hex(8)}"


class BaseScenarioHandler(ABC):
    """
    Abstract base class for scenario handlers.

    Each scenario type has a handler that knows how to:
    1. Determine required parameters
    2. Generate linked change prompts
    3. Apply the scenario to generate deltas
    """

    @abstractmethod
    def required_params(self) -> List[str]:
        """
        Return list of required parameter names for this scenario type.

        Used to validate that all necessary inputs are provided.
        """
        pass

    @abstractmethod
    def linked_prompt_types(self) -> List[str]:
        """
        Return list of linked change types this scenario can trigger.

        Used to determine which linked prompts to generate.
        """
        pass

    @abstractmethod
    async def apply(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
    ) -> ScenarioDelta:
        """
        Apply the scenario to generate a ScenarioDelta.

        This is the core transformation that determines all changes
        to canonical data if the scenario is confirmed.
        """
        pass

    def create_event_delta(
        self,
        scenario_id: str,
        operation: str,
        event_data: Dict[str, Any],
        original_event_id: str = None,
        linked_change_id: str = None,
        change_reason: str = "",
    ) -> EventDelta:
        """Helper to create an EventDelta."""
        return EventDelta(
            event_id=event_data.get("id", generate_id("evt")),
            original_event_id=original_event_id,
            operation=operation,
            event_data=event_data,
            scenario_id=scenario_id,
            linked_change_id=linked_change_id,
            change_reason=change_reason,
        )

    def validate_params(self, definition: ScenarioDefinition) -> List[str]:
        """
        Validate that all required parameters are present.

        Returns list of missing parameter names.
        """
        required = self.required_params()
        missing = []

        for param in required:
            if param.startswith("scope."):
                attr = param.replace("scope.", "")
                val = getattr(definition.scope, attr, None)
                if val is None or (isinstance(val, list) and len(val) == 0):
                    missing.append(param)
            else:
                if param not in definition.parameters:
                    missing.append(param)

        return missing

    # =========================================================================
    # V4: SCHEDULE-BASED DELTA HELPERS
    # =========================================================================

    def create_schedule_delta(
        self,
        scenario_id: str,
        operation: str,
        schedule_data: Dict[str, Any],
        original_schedule_id: Optional[str] = None,
        obligation_id: Optional[str] = None,
        linked_change_id: Optional[str] = None,
        change_reason: str = "",
        confidence: str = "medium",
        confidence_factors: Optional[List[str]] = None,
    ) -> ScheduleDelta:
        """
        Helper to create a ScheduleDelta for ObligationSchedule overlays.

        Args:
            scenario_id: The scenario this delta belongs to
            operation: "add", "modify", "delete", or "defer"
            schedule_data: Dict containing schedule fields (due_date, estimated_amount, etc.)
            original_schedule_id: If modifying existing, the original schedule ID
            obligation_id: Parent obligation ID (existing or virtual)
            linked_change_id: If this delta is from a linked change
            change_reason: Human-readable explanation
            confidence: "high", "medium", or "low"
            confidence_factors: List of factors affecting confidence
        """
        return ScheduleDelta(
            schedule_id=schedule_data.get("id", generate_id("vsched")),
            original_schedule_id=original_schedule_id,
            obligation_id=obligation_id,
            operation=operation,
            schedule_data=schedule_data,
            scenario_id=scenario_id,
            linked_change_id=linked_change_id,
            change_reason=change_reason,
            confidence=confidence,
            confidence_factors=confidence_factors or [],
        )

    def create_agreement_delta(
        self,
        scenario_id: str,
        operation: str,
        agreement_data: Dict[str, Any],
        original_agreement_id: Optional[str] = None,
        linked_change_id: Optional[str] = None,
        change_reason: str = "",
    ) -> AgreementDelta:
        """
        Helper to create an AgreementDelta for virtual ObligationAgreements.

        Used when scenarios create new revenue/expense streams (client_gain, hiring, etc.)
        """
        return AgreementDelta(
            agreement_id=agreement_data.get("id", generate_id("vagrmt")),
            original_agreement_id=original_agreement_id,
            operation=operation,
            agreement_data=agreement_data,
            scenario_id=scenario_id,
            linked_change_id=linked_change_id,
            change_reason=change_reason,
        )

    async def get_schedules_for_client(
        self,
        db: AsyncSession,
        client_id: str,
        from_date: date,
    ) -> List[ObligationSchedule]:
        """
        Get all ObligationSchedules linked to a client from a given date.

        Returns schedules where the parent obligation has client_id set.
        """
        result = await db.execute(
            select(ObligationSchedule)
            .join(ObligationAgreement)
            .where(
                and_(
                    ObligationAgreement.client_id == client_id,
                    ObligationSchedule.due_date >= from_date,
                    ObligationSchedule.status.in_(["scheduled", "due"])
                )
            )
            .order_by(ObligationSchedule.due_date)
        )
        return list(result.scalars().all())

    async def get_schedules_for_expense(
        self,
        db: AsyncSession,
        bucket_id: str,
        from_date: date,
    ) -> List[ObligationSchedule]:
        """
        Get all ObligationSchedules linked to an ExpenseBucket from a given date.

        Returns schedules where the parent obligation has expense_bucket_id set.
        """
        result = await db.execute(
            select(ObligationSchedule)
            .join(ObligationAgreement)
            .where(
                and_(
                    ObligationAgreement.expense_bucket_id == bucket_id,
                    ObligationSchedule.due_date >= from_date,
                    ObligationSchedule.status.in_(["scheduled", "due"])
                )
            )
            .order_by(ObligationSchedule.due_date)
        )
        return list(result.scalars().all())

    async def get_agreement_for_client(
        self,
        db: AsyncSession,
        client_id: str,
    ) -> Optional[ObligationAgreement]:
        """
        Get the ObligationAgreement linked to a client.

        Returns the first active agreement for the client.
        """
        result = await db.execute(
            select(ObligationAgreement)
            .where(
                and_(
                    ObligationAgreement.client_id == client_id,
                    ObligationAgreement.end_date.is_(None)  # Active only
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_agreement_for_expense(
        self,
        db: AsyncSession,
        bucket_id: str,
    ) -> Optional[ObligationAgreement]:
        """
        Get the ObligationAgreement linked to an expense bucket.

        Returns the first active agreement for the bucket.
        """
        result = await db.execute(
            select(ObligationAgreement)
            .where(
                and_(
                    ObligationAgreement.expense_bucket_id == bucket_id,
                    ObligationAgreement.end_date.is_(None)  # Active only
                )
            )
        )
        return result.scalar_one_or_none()

    def generate_recurring_schedules(
        self,
        agreement_id: str,
        scenario_id: str,
        start_date: date,
        end_date: date,
        amount: Decimal,
        frequency: str,
        category: str,
        source_name: str = "Scenario",
        confidence: str = "medium",
    ) -> List[Dict[str, Any]]:
        """
        Generate recurring schedule data dictionaries for a virtual agreement.

        Args:
            agreement_id: Virtual agreement ID
            scenario_id: Scenario ID for attribution
            start_date: First schedule date
            end_date: Last schedule date (typically 13 weeks out)
            amount: Amount per occurrence
            frequency: "weekly", "bi_weekly", "monthly", "quarterly"
            category: Category (payroll, contractors, software, etc.)
            source_name: Human-readable name for the source
            confidence: Confidence level for these schedules
        """
        schedules = []
        current_date = start_date

        # Calculate interval
        if frequency == "weekly":
            interval = timedelta(weeks=1)
            period_amount = amount / Decimal("4.33")  # Monthly to weekly
        elif frequency == "bi_weekly":
            interval = timedelta(weeks=2)
            period_amount = amount / Decimal("2.17")  # Monthly to bi-weekly
        elif frequency == "quarterly":
            interval = timedelta(days=91)  # ~3 months
            period_amount = amount * Decimal("3")  # Monthly to quarterly
        else:  # monthly (default)
            interval = timedelta(days=30)
            period_amount = amount

        while current_date <= end_date:
            schedules.append({
                "id": generate_id("vsched"),
                "obligation_id": agreement_id,
                "due_date": str(current_date),
                "estimated_amount": str(period_amount),
                "estimate_source": "scenario_projection",
                "confidence": confidence,
                "status": "scheduled",
                "category": category,
                "source_name": source_name,
                "is_recurring": True,
                "recurrence_pattern": frequency,
                "is_virtual": True,
                "scenario_id": scenario_id,
            })
            current_date += interval

        return schedules

    def _parse_date(self, value: Any) -> Optional[date]:
        """Parse a date from various input formats."""
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value)
        return None

    def _calculate_confidence(
        self,
        weeks_out: int,
        scenario_type: str,
        has_integration_backing: bool = False,
    ) -> tuple[str, List[str]]:
        """
        Calculate confidence level based on various factors.

        Returns (confidence_level, factors_list)
        """
        factors = []
        score = 0.7  # Base

        # Time horizon factor
        if weeks_out <= 2:
            score += 0.15
            factors.append("near_term_2_weeks")
        elif weeks_out <= 4:
            score += 0.1
            factors.append("near_term_4_weeks")
        elif weeks_out > 8:
            score -= 0.1
            factors.append("far_term_8_plus_weeks")

        # Integration backing
        if has_integration_backing:
            score += 0.1
            factors.append("integration_backed")

        # Scenario type reliability
        high_reliability = {"client_loss", "firing", "decreased_expense"}
        low_reliability = {"payment_delay_in", "client_change"}

        if scenario_type in high_reliability:
            score += 0.05
            factors.append("high_reliability_type")
        elif scenario_type in low_reliability:
            score -= 0.05
            factors.append("lower_reliability_type")

        # Map to level
        if score >= 0.8:
            level = "high"
        elif score >= 0.5:
            level = "medium"
        else:
            level = "low"

        return level, factors
