"""Bi-directional sync service for Tamio ↔ Xero.

This service handles:
1. Pushing Tamio changes to Xero (create/update/archive)
2. Pulling Xero changes to Tamio (on-demand or scheduled)
3. Conflict detection and resolution
4. Sync status tracking

Design principles:
- Tamio is the "planning layer" (clients, expenses, forecasts)
- Xero is the "transaction layer" (invoices, bills, payments)
- Client/Expense core data flows: Tamio → Xero
- Transaction data flows: Xero → Tamio

V2.1 Update (Data Architecture Refactor):
- Added dual-write to IntegrationMapping table alongside legacy xero_* fields
- This enables gradual migration to centralized integration registry
- Legacy fields will be deprecated once all reads use IntegrationMapping
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.data.clients.models import Client
from app.data.expenses.models import ExpenseBucket
from app.xero.client import XeroClient, get_valid_connection
from app.xero.models import XeroConnection, XeroSyncLog
from app.integrations.services import IntegrationMappingService


class SyncService:
    """Orchestrates bi-directional sync between Tamio and Xero."""

    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id
        self._xero_client: Optional[XeroClient] = None
        self._mapping_service = IntegrationMappingService(db)

    async def _get_xero_client(self) -> Optional[XeroClient]:
        """Get a valid Xero client, refreshing token if needed."""
        if self._xero_client:
            return self._xero_client

        connection = await get_valid_connection(self.db, self.user_id)
        if not connection:
            return None

        self._xero_client = XeroClient(connection)
        return self._xero_client

    # =========================================================================
    # CLIENT SYNC: Tamio → Xero
    # =========================================================================

    async def push_client_to_xero(
        self,
        client: Client,
        create_invoice: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """
        Push a Tamio client to Xero.

        If client has no xero_contact_id, creates a new contact.
        If client has xero_contact_id, updates the existing contact.

        Args:
            client: The Tamio client to sync
            create_invoice: If True and client is retainer, create repeating invoice

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        xero = await self._get_xero_client()
        if not xero:
            return False, "No active Xero connection"

        try:
            if client.xero_contact_id:
                # Update existing contact
                xero.update_contact(
                    contact_id=client.xero_contact_id,
                    name=client.name,
                )
            else:
                # Create new contact
                result = xero.create_contact(
                    name=client.name,
                    is_customer=True,
                    is_supplier=False,
                    currency=client.currency,
                )
                client.xero_contact_id = result["contact_id"]

            # Optionally create repeating invoice for retainers
            if create_invoice and client.client_type == "retainer":
                billing = client.billing_config or {}
                amount = billing.get("amount", 0)

                if amount > 0 and client.xero_contact_id:
                    frequency_map = {
                        "weekly": "WEEKLY",
                        "monthly": "MONTHLY",
                        "quarterly": "MONTHLY",  # Xero uses period=3 for quarterly
                    }
                    schedule_unit = frequency_map.get(
                        billing.get("frequency", "monthly"), "MONTHLY"
                    )
                    schedule_period = 3 if billing.get("frequency") == "quarterly" else 1

                    result = xero.create_repeating_invoice(
                        contact_id=client.xero_contact_id,
                        line_items=[{
                            "description": f"Retainer - {client.name}",
                            "quantity": 1,
                            "unit_amount": float(amount),
                        }],
                        schedule_unit=schedule_unit,
                        schedule_period=schedule_period,
                    )
                    client.xero_repeating_invoice_id = result["repeating_invoice_id"]

            # Update sync status (legacy fields)
            client.sync_status = "synced"
            client.last_synced_at = datetime.now(timezone.utc)
            client.sync_error = None
            client.source = client.source or "manual"

            # Dual-write to IntegrationMapping table (new architecture)
            # This creates/updates the centralized mapping while keeping legacy fields
            await self._mapping_service.create_or_update_mapping(
                entity_type="client",
                entity_id=client.id,
                integration_type="xero",
                external_id=client.xero_contact_id,
                external_type="contact",
                sync_status="synced",
                metadata={
                    "xero_tenant_id": self._xero_client._connection.tenant_id if self._xero_client else None,
                    "has_repeating_invoice": client.xero_repeating_invoice_id is not None,
                }
            )

            await self.db.commit()
            await self._log_sync("client_push", client.id, "success")

            return True, None

        except Exception as e:
            client.sync_status = "error"
            client.sync_error = str(e)

            # Also update mapping status to error (dual-write)
            try:
                await self._mapping_service.update_sync_status(
                    mapping_id=client.id,  # This won't work - need to get mapping first
                    status="error",
                    error_message=str(e)
                )
            except Exception:
                pass  # Don't fail if mapping update fails

            await self.db.commit()
            await self._log_sync("client_push", client.id, "error", str(e))

            return False, str(e)

    async def archive_client_in_xero(self, client: Client) -> Tuple[bool, Optional[str]]:
        """
        Archive a client's Xero contact when deleted in Tamio.

        Note: We archive instead of delete to preserve transaction history.
        """
        if not client.xero_contact_id:
            return True, None  # Nothing to archive

        xero = await self._get_xero_client()
        if not xero:
            return False, "No active Xero connection"

        try:
            xero.archive_contact(client.xero_contact_id)
            await self._log_sync("client_archive", client.id, "success")
            return True, None

        except Exception as e:
            await self._log_sync("client_archive", client.id, "error", str(e))
            return False, str(e)

    # =========================================================================
    # EXPENSE SYNC: Tamio → Xero
    # =========================================================================

    async def push_expense_to_xero(
        self,
        expense: ExpenseBucket,
        create_bill: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """
        Push a Tamio expense bucket to Xero as a supplier contact.

        Args:
            expense: The Tamio expense bucket to sync
            create_bill: If True and expense is recurring, create repeating bill

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        xero = await self._get_xero_client()
        if not xero:
            return False, "No active Xero connection"

        try:
            if expense.xero_contact_id:
                # Update existing supplier
                xero.update_contact(
                    contact_id=expense.xero_contact_id,
                    name=expense.name,
                )
            else:
                # Create new supplier contact
                result = xero.create_contact(
                    name=expense.name,
                    is_customer=False,
                    is_supplier=True,
                    currency=expense.currency,
                )
                expense.xero_contact_id = result["contact_id"]

            # Optionally create repeating bill for fixed expenses
            if create_bill and expense.bucket_type == "fixed":
                amount = float(expense.monthly_amount or 0)

                if amount > 0 and expense.xero_contact_id:
                    frequency_map = {
                        "weekly": "WEEKLY",
                        "monthly": "MONTHLY",
                        "quarterly": "MONTHLY",
                    }
                    schedule_unit = frequency_map.get(expense.frequency or "monthly", "MONTHLY")
                    schedule_period = 3 if expense.frequency == "quarterly" else 1

                    result = xero.create_repeating_bill(
                        contact_id=expense.xero_contact_id,
                        line_items=[{
                            "description": f"{expense.category} - {expense.name}",
                            "quantity": 1,
                            "unit_amount": amount,
                        }],
                        schedule_unit=schedule_unit,
                        schedule_period=schedule_period,
                    )
                    expense.xero_repeating_bill_id = result["repeating_bill_id"]

            # Update sync status (legacy fields)
            expense.sync_status = "synced"
            expense.last_synced_at = datetime.now(timezone.utc)
            expense.sync_error = None
            expense.source = expense.source or "manual"

            # Dual-write to IntegrationMapping table (new architecture)
            await self._mapping_service.create_or_update_mapping(
                entity_type="expense_bucket",
                entity_id=expense.id,
                integration_type="xero",
                external_id=expense.xero_contact_id,
                external_type="contact",
                sync_status="synced",
                metadata={
                    "xero_tenant_id": self._xero_client._connection.tenant_id if self._xero_client else None,
                    "contact_type": "SUPPLIER",
                    "has_repeating_bill": expense.xero_repeating_bill_id is not None,
                }
            )

            await self.db.commit()
            await self._log_sync("expense_push", expense.id, "success")

            return True, None

        except Exception as e:
            expense.sync_status = "error"
            expense.sync_error = str(e)
            await self.db.commit()
            await self._log_sync("expense_push", expense.id, "error", str(e))

            return False, str(e)

    async def archive_expense_in_xero(self, expense: ExpenseBucket) -> Tuple[bool, Optional[str]]:
        """Archive an expense's Xero supplier contact when deleted in Tamio."""
        if not expense.xero_contact_id:
            return True, None

        xero = await self._get_xero_client()
        if not xero:
            return False, "No active Xero connection"

        try:
            xero.archive_contact(expense.xero_contact_id)
            await self._log_sync("expense_archive", expense.id, "success")
            return True, None

        except Exception as e:
            await self._log_sync("expense_archive", expense.id, "error", str(e))
            return False, str(e)

    # =========================================================================
    # PULL FROM XERO: Xero → Tamio
    # =========================================================================

    async def pull_clients_from_xero(self) -> Tuple[int, int, List[str]]:
        """
        Pull/sync customer contacts from Xero to Tamio.

        Returns:
            Tuple of (created_count, updated_count, errors)
        """
        xero = await self._get_xero_client()
        if not xero:
            return 0, 0, ["No active Xero connection"]

        created = 0
        updated = 0
        errors = []

        try:
            contacts = xero.get_contacts(is_customer=True)

            for contact in contacts:
                try:
                    # Check if we already have this client
                    result = await self.db.execute(
                        select(Client).where(
                            Client.user_id == self.user_id,
                            Client.xero_contact_id == contact["contact_id"]
                        )
                    )
                    existing = result.scalar_one_or_none()

                    if existing:
                        # Update if Xero-owned (source="xero")
                        if existing.source == "xero":
                            existing.name = contact["name"]
                            existing.currency = contact.get("default_currency") or existing.currency
                            existing.last_synced_at = datetime.now(timezone.utc)
                            existing.sync_status = "synced"
                            updated += 1
                    else:
                        # Create new client from Xero
                        from app.data.base import generate_id

                        new_client = Client(
                            id=generate_id("client"),
                            user_id=self.user_id,
                            name=contact["name"],
                            client_type="retainer",  # Default, user can change
                            currency=contact.get("default_currency") or "USD",
                            status="active",
                            source="xero",
                            xero_contact_id=contact["contact_id"],
                            sync_status="synced",
                            last_synced_at=datetime.now(timezone.utc),
                            locked_fields=["name"],  # Name controlled by Xero
                            billing_config={
                                "source": "xero_sync",
                                "xero_contact_id": contact["contact_id"],
                            },
                        )
                        self.db.add(new_client)
                        created += 1

                except Exception as e:
                    errors.append(f"Contact {contact.get('name', 'unknown')}: {str(e)}")

            await self.db.commit()
            await self._log_sync("clients_pull", None, "success", f"Created: {created}, Updated: {updated}")

        except Exception as e:
            errors.append(f"Failed to fetch contacts: {str(e)}")
            await self._log_sync("clients_pull", None, "error", str(e))

        return created, updated, errors

    async def pull_expenses_from_xero(self) -> Tuple[int, int, List[str]]:
        """
        Pull/sync supplier contacts from Xero to Tamio as expense buckets.

        Returns:
            Tuple of (created_count, updated_count, errors)
        """
        xero = await self._get_xero_client()
        if not xero:
            return 0, 0, ["No active Xero connection"]

        created = 0
        updated = 0
        errors = []

        try:
            contacts = xero.get_contacts(is_supplier=True)

            for contact in contacts:
                try:
                    # Check if we already have this expense
                    result = await self.db.execute(
                        select(ExpenseBucket).where(
                            ExpenseBucket.user_id == self.user_id,
                            ExpenseBucket.xero_contact_id == contact["contact_id"]
                        )
                    )
                    existing = result.scalar_one_or_none()

                    if existing:
                        # Update if Xero-owned
                        if existing.source == "xero":
                            existing.name = contact["name"]
                            existing.currency = contact.get("default_currency") or existing.currency
                            existing.last_synced_at = datetime.now(timezone.utc)
                            existing.sync_status = "synced"
                            updated += 1
                    else:
                        # Create new expense bucket from Xero
                        from app.data.base import generate_id
                        from decimal import Decimal

                        new_expense = ExpenseBucket(
                            id=generate_id("bucket"),
                            user_id=self.user_id,
                            name=contact["name"],
                            category="other",  # Default, user can categorize
                            bucket_type="variable",  # Default
                            monthly_amount=Decimal("0"),  # Unknown from contact alone
                            currency=contact.get("default_currency") or "USD",
                            priority="medium",
                            is_stable=True,
                            source="xero",
                            xero_contact_id=contact["contact_id"],
                            sync_status="synced",
                            last_synced_at=datetime.now(timezone.utc),
                            locked_fields=["name"],
                        )
                        self.db.add(new_expense)
                        created += 1

                except Exception as e:
                    errors.append(f"Supplier {contact.get('name', 'unknown')}: {str(e)}")

            await self.db.commit()
            await self._log_sync("expenses_pull", None, "success", f"Created: {created}, Updated: {updated}")

        except Exception as e:
            errors.append(f"Failed to fetch suppliers: {str(e)}")
            await self._log_sync("expenses_pull", None, "error", str(e))

        return created, updated, errors

    # =========================================================================
    # INVOICE SYNC: Xero → Tamio
    # =========================================================================

    async def pull_invoices_from_xero(self) -> Tuple[int, int, List[str]]:
        """
        Pull outstanding invoices from Xero and update client billing_config.

        This ensures the forecast reflects actual invoices from Xero, not just
        estimated billing schedules. Outstanding invoices (AUTHORISED status with
        amount_due > 0) are stored in the client's billing_config.outstanding_invoices.

        Returns:
            Tuple of (invoices_processed, clients_updated, errors)
        """
        xero = await self._get_xero_client()
        if not xero:
            return 0, 0, ["No active Xero connection"]

        invoices_processed = 0
        clients_updated = 0
        errors = []

        try:
            # Get all outstanding invoices (ACCREC = Accounts Receivable)
            outstanding = xero.get_outstanding_invoices()

            # Group invoices by contact_id
            invoices_by_contact: Dict[str, List[Dict]] = {}
            for inv in outstanding:
                # Only process ACCREC (customer invoices), not ACCPAY (bills)
                if inv.get("type") == "ACCREC" and inv.get("contact_id"):
                    contact_id = inv["contact_id"]
                    if contact_id not in invoices_by_contact:
                        invoices_by_contact[contact_id] = []
                    # Format for forecast engine compatibility
                    # Uses expected_date and amount (not due_date and amount_due)
                    due_date_val = inv.get("due_date")
                    if due_date_val:
                        if hasattr(due_date_val, 'isoformat'):
                            expected_date = due_date_val.isoformat() if hasattr(due_date_val, 'date') else str(due_date_val)[:10]
                        else:
                            expected_date = str(due_date_val)[:10]  # Handle string dates
                    else:
                        expected_date = None

                    invoices_by_contact[contact_id].append({
                        "name": f"Invoice #{inv.get('invoice_number', 'N/A')}",
                        "expected_date": expected_date,
                        "amount": inv["amount_due"],
                        "payment_terms": "net_0",  # Due date already accounts for payment terms
                        "xero_invoice_id": inv["invoice_id"],
                        "invoice_number": inv.get("invoice_number"),
                        "currency": inv.get("currency_code", "USD"),
                        "contact_name": inv.get("contact_name"),
                    })
                    invoices_processed += 1

            # Update each client with their outstanding invoices
            for contact_id, invoices in invoices_by_contact.items():
                try:
                    # Find the client by xero_contact_id
                    result = await self.db.execute(
                        select(Client).where(
                            Client.user_id == self.user_id,
                            Client.xero_contact_id == contact_id
                        )
                    )
                    client = result.scalar_one_or_none()

                    if client:
                        # Update billing_config with outstanding invoices
                        billing_config = client.billing_config or {}
                        billing_config["outstanding_invoices"] = invoices
                        billing_config["invoices_synced_at"] = datetime.now(timezone.utc).isoformat()
                        client.billing_config = billing_config
                        client.last_synced_at = datetime.now(timezone.utc)
                        clients_updated += 1
                    else:
                        # Client doesn't exist in Tamio - they may need to sync contacts first
                        contact_name = invoices[0].get("contact_name", contact_id)
                        errors.append(f"No client found for Xero contact: {contact_name}")

                except Exception as e:
                    errors.append(f"Error updating client {contact_id}: {str(e)}")

            # Also clear outstanding_invoices for clients with no current invoices
            # (in case an invoice was paid since last sync)
            result = await self.db.execute(
                select(Client).where(
                    Client.user_id == self.user_id,
                    Client.xero_contact_id.isnot(None)
                )
            )
            all_synced_clients = result.scalars().all()

            for client in all_synced_clients:
                if client.xero_contact_id not in invoices_by_contact:
                    billing_config = client.billing_config or {}
                    if "outstanding_invoices" in billing_config:
                        # Clear old invoices that are no longer outstanding
                        billing_config["outstanding_invoices"] = []
                        billing_config["invoices_synced_at"] = datetime.now(timezone.utc).isoformat()
                        client.billing_config = billing_config

            await self.db.commit()
            await self._log_sync(
                "invoices_pull",
                None,
                "success",
                f"Processed: {invoices_processed}, Clients updated: {clients_updated}"
            )

        except Exception as e:
            errors.append(f"Failed to fetch invoices: {str(e)}")
            await self._log_sync("invoices_pull", None, "error", str(e))

        return invoices_processed, clients_updated, errors

    async def full_sync_from_xero(self) -> Dict[str, Any]:
        """
        Perform a full sync: contacts + invoices.

        This is the recommended sync method to ensure forecast accuracy.
        """
        results = {
            "clients": {"created": 0, "updated": 0, "errors": []},
            "expenses": {"created": 0, "updated": 0, "errors": []},
            "invoices": {"processed": 0, "clients_updated": 0, "errors": []},
        }

        # Step 1: Sync contacts (customers → clients)
        created, updated, errors = await self.pull_clients_from_xero()
        results["clients"]["created"] = created
        results["clients"]["updated"] = updated
        results["clients"]["errors"] = errors

        # Step 2: Sync contacts (suppliers → expenses)
        created, updated, errors = await self.pull_expenses_from_xero()
        results["expenses"]["created"] = created
        results["expenses"]["updated"] = updated
        results["expenses"]["errors"] = errors

        # Step 3: Sync outstanding invoices (critical for forecast accuracy)
        processed, clients_updated, errors = await self.pull_invoices_from_xero()
        results["invoices"]["processed"] = processed
        results["invoices"]["clients_updated"] = clients_updated
        results["invoices"]["errors"] = errors

        return results

    # =========================================================================
    # HELPERS
    # =========================================================================

    async def _log_sync(
        self,
        operation: str,
        record_id: Optional[str],
        status: str,
        details: Optional[str] = None,
    ) -> None:
        """Log a sync operation for audit trail."""
        log = XeroSyncLog(
            user_id=self.user_id,
            sync_type=operation,
            status=status,
            records_created={"count": 1, "id": record_id} if record_id and status == "success" else None,
            error_message=details if status == "error" else None,
        )
        self.db.add(log)
        # Don't commit here - let the caller handle transaction

    async def get_sync_status(self) -> Dict[str, Any]:
        """Get overall sync status for the user."""
        # Count clients by sync status
        clients_result = await self.db.execute(
            select(Client).where(Client.user_id == self.user_id)
        )
        clients = clients_result.scalars().all()

        expenses_result = await self.db.execute(
            select(ExpenseBucket).where(ExpenseBucket.user_id == self.user_id)
        )
        expenses = expenses_result.scalars().all()

        return {
            "clients": {
                "total": len(clients),
                "synced": sum(1 for c in clients if c.sync_status == "synced"),
                "pending": sum(1 for c in clients if c.sync_status == "pending_push"),
                "errors": sum(1 for c in clients if c.sync_status == "error"),
                "manual_only": sum(1 for c in clients if not c.xero_contact_id),
            },
            "expenses": {
                "total": len(expenses),
                "synced": sum(1 for e in expenses if e.sync_status == "synced"),
                "pending": sum(1 for e in expenses if e.sync_status == "pending_push"),
                "errors": sum(1 for e in expenses if e.sync_status == "error"),
                "manual_only": sum(1 for e in expenses if not e.xero_contact_id),
            },
        }
