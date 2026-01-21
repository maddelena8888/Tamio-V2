"""
Obligation Service - Generates ObligationAgreements from Clients and ExpenseBuckets.

This service bridges the planning layer (Client/ExpenseBucket) with the canonical
obligation layer (ObligationAgreement/ObligationSchedule).

Data Flow:
    Client / ExpenseBucket (User Input)
                ↓
    ObligationAgreement (Contract/Agreement) ← SOURCE OF TRUTH
                ↓
    ObligationSchedule (When payments occur)
                ↓
    CashEvent / ForecastEvent (For forecast engine)
"""
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.data.clients.models import Client
from app.data.expenses.models import ExpenseBucket
from app.data.obligations.models import ObligationAgreement, ObligationSchedule
from app.data.base import generate_id


class ObligationService:
    """
    Service for managing ObligationAgreements and their schedules.

    This service handles:
    1. Creating obligations from Clients (revenue)
    2. Creating obligations from ExpenseBuckets (expenses)
    3. Generating ObligationSchedules for recurring obligations
    4. Syncing obligations when source entities are updated
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==========================================================================
    # Client -> Obligation Flow
    # ==========================================================================

    async def create_obligation_from_client(
        self,
        client: Client,
        auto_generate_schedules: bool = True
    ) -> Optional[ObligationAgreement]:
        """
        Create an ObligationAgreement from a Client's billing configuration.

        Maps:
        - retainer -> fixed obligation with recurring schedule
        - project -> milestone obligations with one-time schedules
        - usage -> variable obligation with estimated schedule
        - mixed -> multiple obligations (one per component)

        Args:
            client: The Client to create obligation from
            auto_generate_schedules: Whether to generate schedules automatically

        Returns:
            The created ObligationAgreement, or None if client has no revenue
        """
        if client.status != "active":
            return None

        config = client.billing_config or {}

        if client.client_type == "retainer":
            return await self._create_retainer_obligation(client, config, auto_generate_schedules)

        elif client.client_type == "project":
            return await self._create_project_obligation(client, config, auto_generate_schedules)

        elif client.client_type == "usage":
            return await self._create_usage_obligation(client, config, auto_generate_schedules)

        elif client.client_type == "mixed":
            # For mixed clients, create primary obligation from retainer component
            # Additional obligations (project milestones) can be added separately
            if "retainer" in config:
                return await self._create_retainer_obligation(client, config["retainer"], auto_generate_schedules)
            elif "usage" in config:
                return await self._create_usage_obligation(client, config["usage"], auto_generate_schedules)

        return None

    async def _create_retainer_obligation(
        self,
        client: Client,
        config: dict,
        auto_generate_schedules: bool
    ) -> Optional[ObligationAgreement]:
        """Create a fixed recurring obligation from retainer configuration."""
        amount = Decimal(str(config.get("amount", 0)))
        if amount <= 0:
            return None

        frequency = config.get("frequency", "monthly")
        confidence = self._calculate_client_confidence(client)

        obligation = ObligationAgreement(
            id=generate_id("obl"),
            user_id=client.user_id,
            client_id=client.id,
            obligation_type="revenue",
            amount_type="fixed",
            amount_source="manual_entry",
            base_amount=amount,
            currency=client.currency,
            frequency=frequency,
            start_date=date.today(),
            category="other",  # Revenue doesn't fit standard expense categories
            confidence=confidence,
            vendor_name=client.name,
            notes=f"Auto-generated from client: {client.name}",
        )

        self.db.add(obligation)
        await self.db.commit()
        await self.db.refresh(obligation)

        if auto_generate_schedules:
            await self.generate_schedules_from_agreement(obligation)

        return obligation

    async def _create_project_obligation(
        self,
        client: Client,
        config: dict,
        auto_generate_schedules: bool
    ) -> Optional[ObligationAgreement]:
        """Create milestone-based obligation from project configuration."""
        milestones = config.get("milestones", [])
        total_value = sum(Decimal(str(m.get("amount", 0))) for m in milestones)

        if total_value <= 0:
            return None

        confidence = self._calculate_client_confidence(client)

        obligation = ObligationAgreement(
            id=generate_id("obl"),
            user_id=client.user_id,
            client_id=client.id,
            obligation_type="revenue",
            amount_type="milestone",
            amount_source="manual_entry",
            base_amount=total_value,
            currency=client.currency,
            frequency="one_time",
            start_date=date.today(),
            category="other",
            confidence=confidence,
            vendor_name=client.name,
            notes=f"Auto-generated from project client: {client.name}",
            variability_rule={"milestones": milestones},  # Store milestone details
        )

        self.db.add(obligation)
        await self.db.commit()
        await self.db.refresh(obligation)

        if auto_generate_schedules:
            await self._generate_milestone_schedules(obligation, milestones)

        return obligation

    async def _create_usage_obligation(
        self,
        client: Client,
        config: dict,
        auto_generate_schedules: bool
    ) -> Optional[ObligationAgreement]:
        """Create variable obligation from usage-based configuration."""
        typical_amount = Decimal(str(config.get("typical_amount", 0)))
        if typical_amount <= 0:
            return None

        frequency = config.get("settlement_frequency", "monthly")

        obligation = ObligationAgreement(
            id=generate_id("obl"),
            user_id=client.user_id,
            client_id=client.id,
            obligation_type="revenue",
            amount_type="variable",
            amount_source="manual_entry",
            base_amount=typical_amount,
            currency=client.currency,
            frequency=frequency,
            start_date=date.today(),
            category="other",
            confidence="medium",  # Usage is inherently variable
            vendor_name=client.name,
            notes=f"Auto-generated from usage-based client: {client.name}",
            variability_rule={"typical_amount": str(typical_amount)},
        )

        self.db.add(obligation)
        await self.db.commit()
        await self.db.refresh(obligation)

        if auto_generate_schedules:
            await self.generate_schedules_from_agreement(obligation)

        return obligation

    # ==========================================================================
    # ExpenseBucket -> Obligation Flow
    # ==========================================================================

    async def create_obligation_from_expense(
        self,
        bucket: ExpenseBucket,
        auto_generate_schedules: bool = True
    ) -> Optional[ObligationAgreement]:
        """
        Create an ObligationAgreement from an ExpenseBucket.

        Args:
            bucket: The ExpenseBucket to create obligation from
            auto_generate_schedules: Whether to generate schedules automatically

        Returns:
            The created ObligationAgreement, or None if bucket has no amount
        """
        if bucket.monthly_amount is None or bucket.monthly_amount <= 0:
            return None

        # Map expense bucket category to obligation type
        obligation_type = self._map_category_to_obligation_type(bucket.category)
        amount_type = "fixed" if bucket.is_stable else "variable"
        confidence = "high" if bucket.is_stable else "medium"

        obligation = ObligationAgreement(
            id=generate_id("obl"),
            user_id=bucket.user_id,
            expense_bucket_id=bucket.id,
            obligation_type=obligation_type,
            amount_type=amount_type,
            amount_source="manual_entry",
            base_amount=bucket.monthly_amount,
            currency=bucket.currency,
            frequency=bucket.frequency or "monthly",
            start_date=date.today(),
            category=bucket.category,
            confidence=confidence,
            vendor_name=bucket.name,
            notes=f"Auto-generated from expense bucket: {bucket.name}",
        )

        self.db.add(obligation)
        await self.db.commit()
        await self.db.refresh(obligation)

        if auto_generate_schedules:
            await self.generate_schedules_from_agreement(obligation, due_day=bucket.due_day)

        return obligation

    def _map_category_to_obligation_type(self, category: str) -> str:
        """Map expense bucket category to obligation type."""
        category_map = {
            "payroll": "payroll",
            "rent": "lease",
            "contractor": "contractor",
            "software": "subscription",
            "marketing": "vendor_bill",
            "other": "other",
        }
        return category_map.get(category, "other")

    # ==========================================================================
    # Schedule Generation
    # ==========================================================================

    async def generate_schedules_from_agreement(
        self,
        obligation: ObligationAgreement,
        months_ahead: int = 3,
        due_day: Optional[int] = None
    ) -> List[ObligationSchedule]:
        """
        Generate ObligationSchedule entries for a recurring agreement.

        Args:
            obligation: The ObligationAgreement to generate schedules for
            months_ahead: Number of months to generate schedules for
            due_day: Day of month for due dates (default: 1 for revenue, 15 for expenses)

        Returns:
            List of generated ObligationSchedule entries
        """
        if obligation.frequency == "one_time":
            # For one-time obligations, create a single schedule
            schedule = ObligationSchedule(
                id=generate_id("sched"),
                obligation_id=obligation.id,
                due_date=obligation.start_date,
                estimated_amount=obligation.base_amount or Decimal("0"),
                estimate_source="fixed_agreement",
                confidence=obligation.confidence,
                status="scheduled",
            )
            self.db.add(schedule)
            await self.db.commit()
            return [schedule]

        schedules = []

        # Determine due day
        if due_day is None:
            due_day = 1 if obligation.client_id else 15

        # Calculate schedule dates
        current_date = date.today().replace(day=1)
        end_date = current_date + relativedelta(months=months_ahead)

        while current_date < end_date:
            # Calculate due date for this period
            try:
                schedule_due_date = current_date.replace(day=due_day)
            except ValueError:
                # Day doesn't exist in this month, use last day
                next_month = current_date + relativedelta(months=1)
                schedule_due_date = next_month - timedelta(days=1)

            # Only create schedule if due date is in the future
            if schedule_due_date >= date.today():
                schedule = ObligationSchedule(
                    id=generate_id("sched"),
                    obligation_id=obligation.id,
                    due_date=schedule_due_date,
                    period_start=current_date,
                    period_end=current_date + relativedelta(months=1) - timedelta(days=1),
                    estimated_amount=obligation.base_amount or Decimal("0"),
                    estimate_source="fixed_agreement",
                    confidence=obligation.confidence,
                    status="scheduled",
                )
                schedules.append(schedule)
                self.db.add(schedule)

            # Move to next period based on frequency
            if obligation.frequency == "monthly":
                current_date += relativedelta(months=1)
            elif obligation.frequency == "weekly":
                current_date += timedelta(weeks=1)
            elif obligation.frequency == "bi_weekly":
                current_date += timedelta(weeks=2)
            elif obligation.frequency == "quarterly":
                current_date += relativedelta(months=3)
            elif obligation.frequency == "annually":
                current_date += relativedelta(years=1)
            else:
                current_date += relativedelta(months=1)

        await self.db.commit()
        return schedules

    async def _generate_milestone_schedules(
        self,
        obligation: ObligationAgreement,
        milestones: List[Dict[str, Any]]
    ) -> List[ObligationSchedule]:
        """Generate schedules from project milestones."""
        schedules = []

        for milestone in milestones:
            expected_date_str = milestone.get("expected_date")
            if not expected_date_str:
                continue

            try:
                milestone_date = date.fromisoformat(expected_date_str)
            except ValueError:
                continue

            amount = Decimal(str(milestone.get("amount", 0)))
            if amount <= 0:
                continue

            # Apply payment terms
            payment_terms = milestone.get("payment_terms", "net_14")
            payment_delay_days = 14
            if isinstance(payment_terms, str) and "net_" in payment_terms:
                try:
                    payment_delay_days = int(payment_terms.replace("net_", ""))
                except ValueError:
                    pass

            due_date = milestone_date + timedelta(days=payment_delay_days)

            schedule = ObligationSchedule(
                id=generate_id("sched"),
                obligation_id=obligation.id,
                due_date=due_date,
                estimated_amount=amount,
                estimate_source="fixed_agreement",
                confidence=obligation.confidence,
                status="scheduled",
                notes=milestone.get("name", "Project milestone"),
            )
            schedules.append(schedule)
            self.db.add(schedule)

        await self.db.commit()
        return schedules

    # ==========================================================================
    # Sync Operations
    # ==========================================================================

    async def sync_obligation_from_client(
        self,
        client: Client
    ) -> Optional[ObligationAgreement]:
        """
        Sync an existing obligation when client is updated.

        - If no obligation exists, create one
        - If obligation exists, update amount/frequency
        - Regenerate future schedules

        Args:
            client: The updated Client

        Returns:
            The synced ObligationAgreement
        """
        # Find existing obligation for this client
        result = await self.db.execute(
            select(ObligationAgreement).where(
                ObligationAgreement.client_id == client.id
            )
        )
        existing = result.scalars().first()

        if client.status != "active":
            # If client is no longer active, deactivate obligations
            if existing:
                existing.end_date = date.today()
                await self.db.commit()
            return existing

        if not existing:
            # Create new obligation
            return await self.create_obligation_from_client(client)

        # Update existing obligation
        config = client.billing_config or {}
        amount = self._get_amount_from_config(client.client_type, config)

        if amount:
            existing.base_amount = amount
            existing.currency = client.currency
            existing.vendor_name = client.name
            existing.confidence = self._calculate_client_confidence(client)

            # Delete future schedules and regenerate
            await self.db.execute(
                delete(ObligationSchedule).where(
                    ObligationSchedule.obligation_id == existing.id,
                    ObligationSchedule.due_date >= date.today(),
                    ObligationSchedule.status == "scheduled"
                )
            )
            await self.db.commit()
            await self.generate_schedules_from_agreement(existing)

        return existing

    async def sync_obligation_from_expense(
        self,
        bucket: ExpenseBucket
    ) -> Optional[ObligationAgreement]:
        """
        Sync an existing obligation when expense bucket is updated.

        Args:
            bucket: The updated ExpenseBucket

        Returns:
            The synced ObligationAgreement
        """
        # Find existing obligation for this bucket
        result = await self.db.execute(
            select(ObligationAgreement).where(
                ObligationAgreement.expense_bucket_id == bucket.id
            )
        )
        existing = result.scalars().first()

        if bucket.monthly_amount is None or bucket.monthly_amount <= 0:
            # If bucket has no amount, deactivate obligation
            if existing:
                existing.end_date = date.today()
                await self.db.commit()
            return existing

        if not existing:
            # Create new obligation
            return await self.create_obligation_from_expense(bucket)

        # Update existing obligation
        existing.base_amount = bucket.monthly_amount
        existing.currency = bucket.currency
        existing.vendor_name = bucket.name
        existing.amount_type = "fixed" if bucket.is_stable else "variable"
        existing.confidence = "high" if bucket.is_stable else "medium"

        # Delete future schedules and regenerate
        await self.db.execute(
            delete(ObligationSchedule).where(
                ObligationSchedule.obligation_id == existing.id,
                ObligationSchedule.due_date >= date.today(),
                ObligationSchedule.status == "scheduled"
            )
        )
        await self.db.commit()
        await self.generate_schedules_from_agreement(existing, due_day=bucket.due_day)

        return existing

    async def delete_obligations_for_client(self, client_id: str) -> int:
        """Delete all obligations linked to a client."""
        result = await self.db.execute(
            delete(ObligationAgreement).where(
                ObligationAgreement.client_id == client_id
            )
        )
        await self.db.commit()
        return result.rowcount

    async def delete_obligations_for_expense(self, expense_bucket_id: str) -> int:
        """Delete all obligations linked to an expense bucket."""
        result = await self.db.execute(
            delete(ObligationAgreement).where(
                ObligationAgreement.expense_bucket_id == expense_bucket_id
            )
        )
        await self.db.commit()
        return result.rowcount

    # ==========================================================================
    # Helper Methods
    # ==========================================================================

    def _calculate_client_confidence(self, client: Client) -> str:
        """Calculate confidence level based on client properties."""
        # High confidence: linked to Xero with repeating invoice
        if client.xero_repeating_invoice_id:
            return "high"

        # Medium confidence: linked to Xero or QuickBooks
        if client.xero_contact_id or client.quickbooks_customer_id:
            return "medium"

        # Based on payment behavior
        behavior_map = {
            "on_time": "high",
            "usually_late": "medium",
            "unknown": "medium",
            "frequently_late": "low",
        }
        return behavior_map.get(client.payment_behavior or "unknown", "medium")

    def _get_amount_from_config(self, client_type: str, config: dict) -> Optional[Decimal]:
        """Extract amount from billing config based on client type."""
        if client_type == "retainer":
            amount = config.get("amount", 0)
        elif client_type == "usage":
            amount = config.get("typical_amount", 0)
        elif client_type == "project":
            milestones = config.get("milestones", [])
            amount = sum(float(m.get("amount", 0)) for m in milestones)
        elif client_type == "mixed":
            # Sum all components
            amount = 0
            if "retainer" in config:
                amount += float(config["retainer"].get("amount", 0))
            if "usage" in config:
                amount += float(config["usage"].get("typical_amount", 0))
        else:
            amount = config.get("amount", 0)

        try:
            return Decimal(str(amount)) if amount > 0 else None
        except (ValueError, TypeError):
            return None
