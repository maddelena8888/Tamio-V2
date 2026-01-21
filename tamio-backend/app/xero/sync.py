"""Xero data sync service.

This module handles syncing data from Xero to Tamio's data models,
mapping invoices to clients/cash events, contacts to clients, etc.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import attributes

from app.xero.client import XeroClient, get_valid_connection
from app.xero.models import XeroConnection, XeroSyncLog
from app.data import models as data_models
from app.data.client_utils import build_canonical_client, update_client_billing_from_repeating_invoice
from app.xero.categorization import get_category_from_line_items


# ============================================================================
# SYNC ORCHESTRATOR
# ============================================================================

async def sync_xero_data(
    db: AsyncSession,
    user_id: str,
    sync_type: str = "full"
) -> Dict[str, Any]:
    """
    Main sync function - orchestrates the full sync process.

    Args:
        db: Database session
        user_id: User ID to sync for
        sync_type: "full" | "incremental" | "invoices" | "contacts"

    Returns:
        Sync result with counts and any errors
    """
    # Get valid connection
    connection = await get_valid_connection(db, user_id)
    if not connection:
        return {
            "success": False,
            "message": "No active Xero connection found. Please reconnect to Xero.",
            "records_fetched": {},
            "records_created": {},
            "records_updated": {},
            "errors": ["No active connection"]
        }

    # Create sync log
    sync_log = XeroSyncLog(
        user_id=user_id,
        sync_type=sync_type,
        status="started"
    )
    db.add(sync_log)
    await db.flush()

    try:
        # Initialize Xero client
        xero_client = XeroClient(connection)

        results = {
            "records_fetched": {},
            "records_created": {},
            "records_updated": {},
            "errors": []
        }

        # Sync based on type
        if sync_type in ["full", "contacts"]:
            contact_results = await sync_contacts(db, user_id, xero_client)
            merge_results(results, contact_results)

        if sync_type in ["full", "invoices"]:
            invoice_results = await sync_invoices(db, user_id, xero_client)
            merge_results(results, invoice_results)

        if sync_type == "full":
            # Also sync repeating invoices for retainer detection
            repeating_results = await sync_repeating_invoices(db, user_id, xero_client)
            merge_results(results, repeating_results)

            # Sync suppliers as expense buckets
            supplier_results = await sync_suppliers(db, user_id, xero_client)
            merge_results(results, supplier_results)

        # Update sync log
        sync_log.status = "completed"
        sync_log.records_fetched = results["records_fetched"]
        sync_log.records_created = results["records_created"]
        sync_log.records_updated = results["records_updated"]
        sync_log.completed_at = datetime.now(timezone.utc)

        # Update connection last sync time
        connection.last_sync_at = datetime.now(timezone.utc)
        connection.sync_error = None

        await db.commit()

        return {
            "success": True,
            "message": f"Sync completed successfully",
            **results
        }

    except Exception as e:
        sync_log.status = "failed"
        sync_log.error_message = str(e)
        sync_log.completed_at = datetime.now(timezone.utc)

        connection.sync_error = str(e)

        await db.commit()

        return {
            "success": False,
            "message": f"Sync failed: {str(e)}",
            "records_fetched": {},
            "records_created": {},
            "records_updated": {},
            "errors": [str(e)]
        }


def merge_results(target: Dict, source: Dict):
    """Merge sync results from different operations."""
    for key in ["records_fetched", "records_created", "records_updated"]:
        if key in source:
            for entity, count in source[key].items():
                target[key][entity] = target[key].get(entity, 0) + count
    if "errors" in source:
        target["errors"].extend(source["errors"])


# ============================================================================
# CONTACT SYNC
# ============================================================================

async def sync_contacts(
    db: AsyncSession,
    user_id: str,
    xero_client: XeroClient
) -> Dict[str, Any]:
    """
    Sync Xero contacts to Tamio clients.

    Mapping:
    - Xero Contact (is_customer=True) → Tamio Client
    - Contact name → Client name
    - Payment terms → payment_behavior inference
    """
    results = {
        "records_fetched": {"contacts": 0},
        "records_created": {"clients": 0},
        "records_updated": {"clients": 0},
        "errors": []
    }

    try:
        # Get customers from Xero
        contacts = xero_client.get_contacts(is_customer=True)
        results["records_fetched"]["contacts"] = len(contacts)

        # Get existing clients for this user
        existing_result = await db.execute(
            select(data_models.Client).where(
                data_models.Client.user_id == user_id
            )
        )
        existing_clients = {c.name.lower(): c for c in existing_result.scalars().all()}

        for contact in contacts:
            contact_name = contact["name"]
            contact_lower = contact_name.lower()

            # Check if client already exists (by name match)
            if contact_lower in existing_clients:
                # Update existing client with Xero data
                client = existing_clients[contact_lower]

                # Link to Xero contact if not already linked
                if not client.xero_contact_id:
                    client.xero_contact_id = contact["contact_id"]
                    client.sync_status = "synced"
                    client.last_synced_at = datetime.now(timezone.utc)

                # Update payment behavior based on payment terms
                if contact.get("payment_terms"):
                    terms = contact["payment_terms"]
                    if terms <= 14:
                        client.payment_behavior = "on_time"
                    elif terms <= 30:
                        client.payment_behavior = "on_time"
                    else:
                        client.payment_behavior = "delayed"

                results["records_updated"]["clients"] += 1
            else:
                # Create new client from contact
                # Determine client type - default to retainer if they have recurring invoices
                client_type = "project"  # Default

                # Infer payment behavior from terms
                payment_behavior = "unknown"
                if contact.get("payment_terms"):
                    terms = contact["payment_terms"]
                    if terms <= 14:
                        payment_behavior = "on_time"
                    elif terms <= 30:
                        payment_behavior = "on_time"
                    else:
                        payment_behavior = "delayed"

                # Use canonical builder for consistent structure
                new_client = build_canonical_client(
                    user_id=user_id,
                    name=contact_name,
                    client_type=client_type,
                    currency=contact.get("default_currency") or "USD",
                    status="active",
                    payment_behavior=payment_behavior,
                    churn_risk="low",
                    scope_risk="low",
                    billing_config={
                        "xero_contact_id": contact["contact_id"],
                        "source": "xero_sync"
                    },
                    notes=f"Imported from Xero (Contact ID: {contact['contact_id']})"
                )
                # Set Xero fields directly on the model
                new_client.xero_contact_id = contact["contact_id"]
                new_client.source = "xero"
                new_client.sync_status = "synced"
                new_client.last_synced_at = datetime.now(timezone.utc)

                db.add(new_client)
                results["records_created"]["clients"] += 1

        await db.flush()

    except Exception as e:
        results["errors"].append(f"Contact sync error: {str(e)}")

    return results


# ============================================================================
# INVOICE SYNC
# ============================================================================

async def sync_invoices(
    db: AsyncSession,
    user_id: str,
    xero_client: XeroClient
) -> Dict[str, Any]:
    """
    Sync Xero invoices to Tamio clients and cash events.

    Mapping:
    - ACCREC (Accounts Receivable) → Client (project type) + CashEvent direction="in"
    - ACCPAY (Accounts Payable) → CashEvent direction="out"
    - Due date → CashEvent date / Client milestone
    - Amount due → CashEvent amount / Client milestone amount
    """
    from app.data.base import generate_id

    results = {
        "records_fetched": {"invoices": 0},
        "records_created": {"cash_events": 0, "clients": 0},
        "records_updated": {"cash_events": 0, "clients": 0},
        "errors": []
    }

    try:
        # Get outstanding invoices
        invoices = xero_client.get_outstanding_invoices()
        results["records_fetched"]["invoices"] = len(invoices)

        # Get existing clients to link
        clients_result = await db.execute(
            select(data_models.Client).where(
                data_models.Client.user_id == user_id
            )
        )
        existing_clients = list(clients_result.scalars().all())
        clients_by_name = {c.name.lower(): c for c in existing_clients}
        clients_by_xero_id = {c.xero_contact_id: c for c in existing_clients if c.xero_contact_id}

        # Get today for week number calculation
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

        # Group receivable invoices by contact for client creation/update
        receivables_by_contact: Dict[str, List[dict]] = {}

        for invoice in invoices:
            if invoice["amount_due"] <= 0:
                continue

            is_receivable = invoice["type"] == "ACCREC"

            if is_receivable:
                contact_name = invoice.get("contact_name", "")
                contact_id = invoice.get("contact_id", "")
                if contact_name:
                    key = contact_id or contact_name.lower()
                    if key not in receivables_by_contact:
                        receivables_by_contact[key] = []
                    receivables_by_contact[key].append(invoice)

            # Get due date
            due_date = invoice.get("due_date")
            if due_date and isinstance(due_date, datetime):
                due_date = due_date.date()
            elif not due_date:
                inv_date = invoice.get("date")
                if inv_date and isinstance(inv_date, datetime):
                    due_date = (inv_date + timedelta(days=30)).date()
                else:
                    due_date = today + timedelta(days=30)

            # Calculate week number
            days_diff = (due_date - week_start).days
            week_number = max(0, days_diff // 7)

            # Find linked client
            client_id = None
            client_name = invoice.get("contact_name", "").lower()
            if client_name in clients_by_name:
                client_id = clients_by_name[client_name].id

            # Determine confidence based on invoice status
            status = invoice.get("status", "").upper()
            if status in ["AUTHORISED", "SUBMITTED"]:
                confidence = "high"
            elif status == "DRAFT":
                confidence = "medium"
            else:
                confidence = "low"

            # Determine category
            if is_receivable:
                category = "client_invoice"
            else:
                line_items = invoice.get("line_items", [])
                category = get_category_from_line_items(line_items)

            # Create cash event
            event = data_models.CashEvent(
                user_id=user_id,
                date=due_date,
                week_number=week_number,
                amount=Decimal(str(invoice["amount_due"])),
                direction="in" if is_receivable else "out",
                event_type="expected_revenue" if is_receivable else "expected_expense",
                category=category,
                client_id=client_id,
                confidence=confidence,
                confidence_reason=f"Xero invoice {invoice.get('invoice_number', 'N/A')} - Status: {status}",
                is_recurring=False,
                notes=f"Synced from Xero Invoice #{invoice.get('invoice_number', 'N/A')}"
            )
            db.add(event)
            results["records_created"]["cash_events"] += 1

        # Create/update clients from receivable invoices
        for contact_key, contact_invoices in receivables_by_contact.items():
            first_invoice = contact_invoices[0]
            contact_name = first_invoice.get("contact_name", "")
            contact_id = first_invoice.get("contact_id")
            contact_lower = contact_name.lower()

            # Check if client exists by Xero ID or name
            existing_client = None
            if contact_id and contact_id in clients_by_xero_id:
                existing_client = clients_by_xero_id[contact_id]
            elif contact_lower in clients_by_name:
                existing_client = clients_by_name[contact_lower]

            # Build milestones from outstanding invoices
            milestones = []
            for inv in contact_invoices:
                inv_due_date = inv.get("due_date")
                if inv_due_date and isinstance(inv_due_date, datetime):
                    inv_due_date = inv_due_date.date()
                elif not inv_due_date:
                    inv_due_date = today + timedelta(days=30)

                milestones.append({
                    "name": f"Invoice #{inv.get('invoice_number', 'N/A')}",
                    "expected_date": inv_due_date.isoformat(),
                    "amount": float(inv["amount_due"]),
                    "payment_terms": "net_0",  # Due date already accounts for terms
                    "xero_invoice_id": inv.get("invoice_id"),
                })

            if existing_client:
                # Update existing client with outstanding invoices
                existing_config = dict(existing_client.billing_config or {})

                # Store outstanding invoices for ALL client types
                # These are one-time payments separate from recurring billing
                existing_config["outstanding_invoices"] = milestones

                # For project clients, also set as milestones for backward compatibility
                if existing_client.client_type == "project":
                    existing_config["milestones"] = milestones

                # Assign a NEW dict to force SQLAlchemy to detect the change
                existing_client.billing_config = existing_config
                # Explicitly flag as modified for JSONB column
                attributes.flag_modified(existing_client, "billing_config")

                # Link to Xero if not already
                if contact_id and not existing_client.xero_contact_id:
                    existing_client.xero_contact_id = contact_id
                    existing_client.source = "xero"
                    existing_client.sync_status = "synced"
                    existing_client.last_synced_at = datetime.now(timezone.utc)

                results["records_updated"]["clients"] += 1
            else:
                # Create new client as project type with milestones
                new_client = build_canonical_client(
                    user_id=user_id,
                    name=contact_name,
                    client_type="project",
                    currency=first_invoice.get("currency_code") or "USD",
                    status="active",
                    payment_behavior="unknown",
                    churn_risk="low",
                    scope_risk="low",
                    billing_config={
                        "milestones": milestones,
                    },
                    notes=f"Imported from Xero outstanding invoices"
                )
                new_client.xero_contact_id = contact_id
                new_client.source = "xero"
                new_client.sync_status = "synced"
                new_client.last_synced_at = datetime.now(timezone.utc)

                db.add(new_client)
                # Add to lookup for subsequent invoices
                clients_by_name[contact_lower] = new_client
                if contact_id:
                    clients_by_xero_id[contact_id] = new_client

                results["records_created"]["clients"] += 1

        await db.flush()

    except Exception as e:
        results["errors"].append(f"Invoice sync error: {str(e)}")

    return results


# ============================================================================
# REPEATING INVOICE SYNC (RETAINERS & RECURRING EXPENSES)
# ============================================================================

async def sync_repeating_invoices(
    db: AsyncSession,
    user_id: str,
    xero_client: XeroClient
) -> Dict[str, Any]:
    """
    Sync Xero repeating invoices to:
    1. Detect retainer clients (ACCREC - recurring revenue)
    2. Create recurring cash events for both ACCREC and ACCPAY

    This generates events for weeks 1-13 based on the repeating invoice schedule.
    """
    results = {
        "records_fetched": {"repeating_invoices": 0},
        "records_created": {"cash_events": 0},
        "records_updated": {"clients": 0},
        "errors": []
    }

    try:
        # Get repeating invoices
        repeating = xero_client.get_repeating_invoices()
        results["records_fetched"]["repeating_invoices"] = len(repeating)

        # Get existing clients for linking
        clients_result = await db.execute(
            select(data_models.Client).where(
                data_models.Client.user_id == user_id
            )
        )
        clients_by_name = {c.name.lower(): c for c in clients_result.scalars().all()}

        # Get today for week number calculation
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

        for inv in repeating:
            is_receivable = inv["type"] == "ACCREC"
            direction = "in" if is_receivable else "out"
            amount = Decimal(str(inv.get("total", 0)))

            if amount <= 0:
                continue

            # Only process AUTHORISED repeating invoices
            if inv.get("status") != "AUTHORISED":
                continue

            contact_name = inv.get("contact_name", "")
            contact_lower = contact_name.lower()

            # Update client to retainer type if it's a receivable
            if is_receivable and contact_lower in clients_by_name:
                client = clients_by_name[contact_lower]

                # Use canonical utility to update billing from repeating invoice
                update_client_billing_from_repeating_invoice(client, inv)
                results["records_updated"]["clients"] += 1

            # Get schedule info
            schedule = inv.get("schedule", {})
            frequency = map_xero_frequency(schedule.get("unit"), schedule.get("period"))

            # Determine payment interval in days
            if frequency == "weekly":
                interval_days = 7
            elif frequency == "bi-weekly":
                interval_days = 14
            elif frequency == "monthly":
                interval_days = 30
            elif frequency == "quarterly":
                interval_days = 91
            else:
                interval_days = 30  # Default to monthly

            # Generate events for weeks 1-13 (skip week 0 as one-time invoices cover near-term)
            # Start from next week to avoid duplicating with outstanding invoices
            next_payment_date = today + timedelta(days=interval_days)

            events_created = 0
            while next_payment_date <= today + timedelta(weeks=13):
                # Calculate week number
                days_diff = (next_payment_date - week_start).days
                week_number = max(1, days_diff // 7)

                if week_number > 13:
                    break

                # Find linked client
                client_id = None
                if contact_lower in clients_by_name:
                    client_id = clients_by_name[contact_lower].id

                # Create recurring cash event
                event = data_models.CashEvent(
                    user_id=user_id,
                    date=next_payment_date,
                    week_number=week_number,
                    amount=amount,
                    direction=direction,
                    event_type="expected_revenue" if is_receivable else "expected_expense",
                    category="recurring_invoice" if is_receivable else "recurring_bill",
                    client_id=client_id,
                    confidence="high",
                    confidence_reason=f"Xero repeating invoice - {contact_name}",
                    is_recurring=True,
                    recurrence_pattern=frequency,
                    notes=f"Recurring {frequency} from Xero: {contact_name}"
                )
                db.add(event)
                events_created += 1

                # Move to next payment date
                next_payment_date += timedelta(days=interval_days)

            results["records_created"]["cash_events"] += events_created

        await db.flush()

    except Exception as e:
        results["errors"].append(f"Repeating invoice sync error: {str(e)}")

    return results


# ============================================================================
# SUPPLIER SYNC (EXPENSE BUCKETS)
# ============================================================================

async def sync_suppliers(
    db: AsyncSession,
    user_id: str,
    xero_client: XeroClient
) -> Dict[str, Any]:
    """
    Sync Xero suppliers to Tamio expense buckets.

    Mapping:
    - Xero Contact (is_supplier=True) → Tamio ExpenseBucket
    - Supplier name → Expense bucket name
    - Outstanding bills → monthly_amount (average or total)
    """
    results = {
        "records_fetched": {"suppliers": 0},
        "records_created": {"expense_buckets": 0},
        "records_updated": {"expense_buckets": 0},
        "errors": []
    }

    try:
        # Get suppliers from Xero
        contacts = xero_client.get_contacts(is_supplier=True)
        results["records_fetched"]["suppliers"] = len(contacts)

        # Get outstanding bills to calculate amounts per supplier
        bills = xero_client.get_outstanding_invoices()
        payables = [b for b in bills if b["type"] == "ACCPAY"]

        # Calculate total outstanding per supplier and track due days
        supplier_amounts: Dict[str, Decimal] = {}
        supplier_due_days: Dict[str, int] = {}  # Track due day from bills
        for bill in payables:
            contact_name = bill.get("contact_name", "").lower()
            amount = Decimal(str(bill.get("amount_due", 0)))
            if contact_name:
                supplier_amounts[contact_name] = supplier_amounts.get(contact_name, Decimal("0")) + amount
                # Extract due day from bill due date
                due_date_val = bill.get("due_date")
                if due_date_val:
                    try:
                        # Handle both datetime objects and strings
                        if hasattr(due_date_val, 'day'):
                            # It's a datetime.date or datetime.datetime object
                            supplier_due_days[contact_name] = due_date_val.day
                        elif isinstance(due_date_val, str):
                            from datetime import datetime as dt
                            due_date = dt.fromisoformat(due_date_val.replace("Z", "+00:00"))
                            supplier_due_days[contact_name] = due_date.day
                    except (ValueError, AttributeError):
                        pass

        # Also get repeating bills for recurring expense amounts
        repeating = xero_client.get_repeating_invoices()
        repeating_bills = [r for r in repeating if r["type"] == "ACCPAY" and r.get("status") == "AUTHORISED"]

        supplier_recurring: Dict[str, Decimal] = {}
        supplier_recurring_due_days: Dict[str, int] = {}  # Track due day from repeating bills
        for bill in repeating_bills:
            contact_name = bill.get("contact_name", "").lower()
            amount = Decimal(str(bill.get("total", 0)))
            if contact_name:
                supplier_recurring[contact_name] = amount
                # Extract due day from schedule if available
                schedule = bill.get("schedule", {})
                due_day_of_month = schedule.get("due_day_of_month")
                if due_day_of_month:
                    supplier_recurring_due_days[contact_name] = due_day_of_month

        # Get existing expense buckets for this user
        existing_result = await db.execute(
            select(data_models.ExpenseBucket).where(
                data_models.ExpenseBucket.user_id == user_id
            )
        )
        all_buckets = existing_result.scalars().all()
        existing_buckets = {b.name.lower(): b for b in all_buckets}
        existing_by_xero_id = {
            b.xero_contact_id: b for b in all_buckets
            if b.xero_contact_id
        }

        for contact in contacts:
            contact_name = contact["name"]
            contact_lower = contact_name.lower()
            contact_id = contact["contact_id"]

            # Get amount from outstanding bills or recurring bills
            monthly_amount = supplier_recurring.get(contact_lower, Decimal("0"))
            if monthly_amount == 0:
                # Fall back to outstanding amount
                monthly_amount = supplier_amounts.get(contact_lower, Decimal("0"))

            # Get due day: prefer recurring bill schedule, fall back to outstanding bill due date
            due_day = supplier_recurring_due_days.get(
                contact_lower,
                supplier_due_days.get(contact_lower, 15)  # Default to 15 if no data
            )

            # Skip if already linked by Xero ID
            if contact_id in existing_by_xero_id:
                bucket = existing_by_xero_id[contact_id]
                if bucket.source == "xero":
                    bucket.name = contact_name
                    bucket.last_synced_at = datetime.now(timezone.utc)
                    bucket.sync_status = "synced"
                    # Update amount if we have bill data
                    if monthly_amount > 0:
                        bucket.monthly_amount = monthly_amount
                    # Update due day from Xero
                    bucket.due_day = due_day
                results["records_updated"]["expense_buckets"] += 1
                continue

            # Check if bucket exists by name match
            if contact_lower in existing_buckets:
                # Link existing bucket to Xero contact
                bucket = existing_buckets[contact_lower]
                bucket.xero_contact_id = contact_id
                bucket.sync_status = "synced"
                bucket.last_synced_at = datetime.now(timezone.utc)
                # Update amount if we have bill data and bucket is from xero
                if monthly_amount > 0 and bucket.source == "xero":
                    bucket.monthly_amount = monthly_amount
                # Update due day from Xero
                if bucket.source == "xero":
                    bucket.due_day = due_day
                results["records_updated"]["expense_buckets"] += 1
            else:
                # Create new expense bucket from supplier
                from app.data.base import generate_id

                # Determine bucket type based on whether there's a recurring bill
                is_recurring = contact_lower in supplier_recurring
                bucket_type = "fixed" if is_recurring else "variable"

                new_bucket = data_models.ExpenseBucket(
                    id=generate_id("bucket"),
                    user_id=user_id,
                    name=contact_name,
                    category="other",  # Default, user can categorize
                    bucket_type=bucket_type,
                    monthly_amount=monthly_amount,
                    currency=contact.get("default_currency") or "USD",
                    priority="medium",
                    is_stable=is_recurring,
                    due_day=due_day,
                    frequency="monthly",
                    source="xero",
                    xero_contact_id=contact_id,
                    sync_status="synced",
                    last_synced_at=datetime.now(timezone.utc),
                    locked_fields=["name"],
                )
                db.add(new_bucket)
                results["records_created"]["expense_buckets"] += 1

        await db.flush()

    except Exception as e:
        results["errors"].append(f"Supplier sync error: {str(e)}")

    return results


def map_xero_frequency(unit: Optional[str], period: Optional[int]) -> str:
    """Map Xero schedule unit to Tamio frequency."""
    if not unit:
        return "monthly"

    unit = unit.upper()
    period = period or 1

    if unit == "MONTHLY":
        if period == 1:
            return "monthly"
        elif period == 3:
            return "quarterly"
        elif period == 12:
            return "yearly"
    elif unit == "WEEKLY":
        if period == 1:
            return "weekly"
        elif period == 2:
            return "bi-weekly"

    return "monthly"


# ============================================================================
# PAYMENT BEHAVIOR ANALYSIS
# ============================================================================

async def analyze_payment_behavior(
    db: AsyncSession,
    user_id: str,
    xero_client: XeroClient
) -> Dict[str, Any]:
    """
    Analyze aged receivables to determine payment behavior for each client.

    Returns payment behavior analysis that can be used to update clients.
    """
    results = {
        "analysis": [],
        "errors": []
    }

    try:
        aged_ar = xero_client.get_aged_receivables()

        # Get existing clients
        clients_result = await db.execute(
            select(data_models.Client).where(
                data_models.Client.user_id == user_id
            )
        )
        clients_by_name = {c.name.lower(): c for c in clients_result.scalars().all()}

        for contact_data in aged_ar.get("contacts", []):
            contact_name = contact_data.get("contact", "")
            if not contact_name:
                continue

            # Calculate payment behavior score
            current = contact_data.get("current", 0)
            days_30 = contact_data.get("30_days", 0)
            days_60 = contact_data.get("60_days", 0)
            days_90 = contact_data.get("90_days", 0)
            older = contact_data.get("older", 0)
            total = contact_data.get("total", 0)

            if total <= 0:
                continue

            # Calculate weighted average days outstanding
            weighted_days = (
                current * 0 +
                days_30 * 30 +
                days_60 * 60 +
                days_90 * 90 +
                older * 120
            ) / total if total > 0 else 0

            # Determine behavior
            if weighted_days < 15:
                behavior = "on_time"
            elif weighted_days < 45:
                behavior = "on_time"  # Mostly on time
            else:
                behavior = "delayed"

            # Update client if exists
            contact_lower = contact_name.lower()
            if contact_lower in clients_by_name:
                client = clients_by_name[contact_lower]
                client.payment_behavior = behavior

                results["analysis"].append({
                    "client_name": contact_name,
                    "weighted_days": round(weighted_days, 1),
                    "behavior": behavior,
                    "outstanding_total": total
                })

        await db.flush()

    except Exception as e:
        results["errors"].append(f"Payment analysis error: {str(e)}")

    return results
