"""QuickBooks data sync service.

This module handles syncing data from QuickBooks to Tamio's data models,
mapping invoices to clients/cash events, customers to clients, etc.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.quickbooks.client import QuickBooksClient, get_valid_connection
from app.quickbooks.models import QuickBooksConnection, QuickBooksSyncLog
from app.data import models as data_models
from app.data.client_utils import build_canonical_client
from app.quickbooks.categorization import get_category_from_account


# ============================================================================
# SYNC ORCHESTRATOR
# ============================================================================

async def sync_quickbooks_data(
    db: AsyncSession,
    user_id: str,
    sync_type: str = "full"
) -> Dict[str, Any]:
    """
    Main sync function - orchestrates the full sync process.

    Args:
        db: Database session
        user_id: User ID to sync for
        sync_type: "full" | "incremental" | "invoices" | "customers"

    Returns:
        Sync result with counts and any errors
    """
    # Get valid connection
    connection = await get_valid_connection(db, user_id)
    if not connection:
        return {
            "success": False,
            "message": "No active QuickBooks connection found. Please reconnect to QuickBooks.",
            "records_fetched": {},
            "records_created": {},
            "records_updated": {},
            "errors": ["No active connection"]
        }

    # Create sync log
    sync_log = QuickBooksSyncLog(
        user_id=user_id,
        sync_type=sync_type,
        status="started"
    )
    db.add(sync_log)
    await db.flush()

    try:
        # Initialize QuickBooks client
        qb_client = QuickBooksClient(connection)

        results = {
            "records_fetched": {},
            "records_created": {},
            "records_updated": {},
            "errors": []
        }

        # Sync based on type
        if sync_type in ["full", "customers"]:
            customer_results = await sync_customers(db, user_id, qb_client)
            merge_results(results, customer_results)

        if sync_type in ["full", "invoices"]:
            invoice_results = await sync_invoices(db, user_id, qb_client)
            merge_results(results, invoice_results)

        if sync_type == "full":
            # Sync vendors as expense buckets
            vendor_results = await sync_vendors(db, user_id, qb_client)
            merge_results(results, vendor_results)

            # Sync bills
            bill_results = await sync_bills(db, user_id, qb_client)
            merge_results(results, bill_results)

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
            "message": "Sync completed successfully",
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
# CUSTOMER SYNC
# ============================================================================

async def sync_customers(
    db: AsyncSession,
    user_id: str,
    qb_client: QuickBooksClient
) -> Dict[str, Any]:
    """
    Sync QuickBooks customers to Tamio clients.

    Mapping:
    - QuickBooks Customer -> Tamio Client
    - Display name -> Client name
    - Balance -> Outstanding amount
    """
    results = {
        "records_fetched": {"customers": 0},
        "records_created": {"clients": 0},
        "records_updated": {"clients": 0},
        "errors": []
    }

    try:
        # Get customers from QuickBooks
        customers = await qb_client.get_customers()
        results["records_fetched"]["customers"] = len(customers)

        # Get existing clients for this user
        existing_result = await db.execute(
            select(data_models.Client).where(
                data_models.Client.user_id == user_id
            )
        )
        existing_clients = {c.name.lower(): c for c in existing_result.scalars().all()}

        # Also index by quickbooks_customer_id if available
        existing_by_qb_id = {
            c.quickbooks_customer_id: c for c in existing_result.scalars().all()
            if hasattr(c, 'quickbooks_customer_id') and c.quickbooks_customer_id
        }

        for customer in customers:
            customer_name = customer["display_name"]
            customer_lower = customer_name.lower()
            customer_id = customer["customer_id"]

            # Check if already linked by QuickBooks ID
            if customer_id in existing_by_qb_id:
                client = existing_by_qb_id[customer_id]
                # Update synced fields
                if client.source == "quickbooks":
                    client.name = customer_name
                client.sync_status = "synced"
                client.last_synced_at = datetime.now(timezone.utc)
                results["records_updated"]["clients"] += 1
                continue

            # Check if client already exists (by name match)
            if customer_lower in existing_clients:
                # Update existing client with QuickBooks data
                client = existing_clients[customer_lower]

                # Link to QuickBooks customer if not already linked
                if hasattr(client, 'quickbooks_customer_id') and not client.quickbooks_customer_id:
                    client.quickbooks_customer_id = customer_id
                    client.sync_status = "synced"
                    client.last_synced_at = datetime.now(timezone.utc)

                results["records_updated"]["clients"] += 1
            else:
                # Create new client from customer
                new_client = build_canonical_client(
                    user_id=user_id,
                    name=customer_name,
                    client_type="project",  # Default
                    currency=customer.get("currency") or "USD",
                    status="active",
                    payment_behavior="unknown",
                    churn_risk="low",
                    scope_risk="low",
                    billing_config={
                        "quickbooks_customer_id": customer_id,
                        "source": "quickbooks_sync"
                    },
                    notes=f"Imported from QuickBooks (Customer ID: {customer_id})"
                )
                # Set QuickBooks fields directly on the model
                if hasattr(new_client, 'quickbooks_customer_id'):
                    new_client.quickbooks_customer_id = customer_id
                new_client.source = "quickbooks"
                new_client.sync_status = "synced"
                new_client.last_synced_at = datetime.now(timezone.utc)

                db.add(new_client)
                results["records_created"]["clients"] += 1

        await db.flush()

    except Exception as e:
        results["errors"].append(f"Customer sync error: {str(e)}")

    return results


# ============================================================================
# INVOICE SYNC
# ============================================================================

async def sync_invoices(
    db: AsyncSession,
    user_id: str,
    qb_client: QuickBooksClient
) -> Dict[str, Any]:
    """
    Sync QuickBooks invoices to Tamio cash events.

    Mapping:
    - Invoice (balance > 0) -> CashEvent direction="in"
    - Due date -> CashEvent date
    - Balance -> CashEvent amount
    """
    results = {
        "records_fetched": {"invoices": 0},
        "records_created": {"cash_events": 0},
        "records_updated": {"cash_events": 0},
        "errors": []
    }

    try:
        # Get outstanding invoices
        invoices = await qb_client.get_outstanding_invoices()
        results["records_fetched"]["invoices"] = len(invoices)

        # Get existing clients to link
        clients_result = await db.execute(
            select(data_models.Client).where(
                data_models.Client.user_id == user_id
            )
        )
        clients_by_name = {c.name.lower(): c for c in clients_result.scalars().all()}

        # Get today for week number calculation
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

        for invoice in invoices:
            balance = invoice.get("balance", 0)
            if balance <= 0:
                continue

            # Get due date
            due_date_str = invoice.get("due_date")
            if due_date_str:
                try:
                    due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    due_date = today + timedelta(days=30)
            else:
                due_date = today + timedelta(days=30)

            # Calculate week number
            days_diff = (due_date - week_start).days
            week_number = max(0, days_diff // 7)

            # Find linked client
            client_id = None
            customer_name = invoice.get("customer_name", "").lower()
            if customer_name in clients_by_name:
                client_id = clients_by_name[customer_name].id

            # Determine confidence based on invoice status
            status = invoice.get("status", "").lower()
            if status == "open":
                confidence = "high"
            else:
                confidence = "medium"

            # Create cash event
            event = data_models.CashEvent(
                user_id=user_id,
                date=due_date,
                week_number=week_number,
                amount=Decimal(str(balance)),
                direction="in",
                event_type="expected_revenue",
                category="client_invoice",
                client_id=client_id,
                confidence=confidence,
                confidence_reason=f"QuickBooks invoice {invoice.get('doc_number', 'N/A')} - Status: {status}",
                is_recurring=False,
                notes=f"Synced from QuickBooks Invoice #{invoice.get('doc_number', 'N/A')}"
            )
            db.add(event)
            results["records_created"]["cash_events"] += 1

        await db.flush()

    except Exception as e:
        results["errors"].append(f"Invoice sync error: {str(e)}")

    return results


# ============================================================================
# VENDOR SYNC (EXPENSE BUCKETS)
# ============================================================================

async def sync_vendors(
    db: AsyncSession,
    user_id: str,
    qb_client: QuickBooksClient
) -> Dict[str, Any]:
    """
    Sync QuickBooks vendors to Tamio expense buckets.

    Mapping:
    - QuickBooks Vendor -> Tamio ExpenseBucket
    - Vendor name -> Expense bucket name
    - Outstanding bills -> monthly_amount
    """
    results = {
        "records_fetched": {"vendors": 0},
        "records_created": {"expense_buckets": 0},
        "records_updated": {"expense_buckets": 0},
        "errors": []
    }

    try:
        # Get vendors from QuickBooks
        vendors = await qb_client.get_vendors()
        results["records_fetched"]["vendors"] = len(vendors)

        # Get outstanding bills to calculate amounts per vendor
        bills = await qb_client.get_outstanding_bills()

        # Calculate total outstanding per vendor
        vendor_amounts: Dict[str, Decimal] = {}
        for bill in bills:
            vendor_name = bill.get("vendor_name", "").lower()
            amount = Decimal(str(bill.get("balance", 0)))
            if vendor_name:
                vendor_amounts[vendor_name] = vendor_amounts.get(vendor_name, Decimal("0")) + amount

        # Get existing expense buckets for this user
        existing_result = await db.execute(
            select(data_models.ExpenseBucket).where(
                data_models.ExpenseBucket.user_id == user_id
            )
        )
        all_buckets = existing_result.scalars().all()
        existing_buckets = {b.name.lower(): b for b in all_buckets}
        existing_by_qb_id = {
            b.quickbooks_vendor_id: b for b in all_buckets
            if hasattr(b, 'quickbooks_vendor_id') and b.quickbooks_vendor_id
        }

        for vendor in vendors:
            vendor_name = vendor["display_name"]
            vendor_lower = vendor_name.lower()
            vendor_id = vendor["vendor_id"]

            # Get amount from outstanding bills
            monthly_amount = vendor_amounts.get(vendor_lower, Decimal("0"))

            # Skip if already linked by QuickBooks ID
            if vendor_id in existing_by_qb_id:
                bucket = existing_by_qb_id[vendor_id]
                if bucket.source == "quickbooks":
                    bucket.name = vendor_name
                    bucket.last_synced_at = datetime.now(timezone.utc)
                    bucket.sync_status = "synced"
                    if monthly_amount > 0:
                        bucket.monthly_amount = monthly_amount
                results["records_updated"]["expense_buckets"] += 1
                continue

            # Check if bucket exists by name match
            if vendor_lower in existing_buckets:
                # Link existing bucket to QuickBooks vendor
                bucket = existing_buckets[vendor_lower]
                if hasattr(bucket, 'quickbooks_vendor_id'):
                    bucket.quickbooks_vendor_id = vendor_id
                bucket.sync_status = "synced"
                bucket.last_synced_at = datetime.now(timezone.utc)
                if monthly_amount > 0 and bucket.source == "quickbooks":
                    bucket.monthly_amount = monthly_amount
                results["records_updated"]["expense_buckets"] += 1
            else:
                # Create new expense bucket from vendor
                from app.data.base import generate_id

                new_bucket = data_models.ExpenseBucket(
                    id=generate_id("bucket"),
                    user_id=user_id,
                    name=vendor_name,
                    category="other",  # Default, user can categorize
                    bucket_type="variable",  # Default to variable
                    monthly_amount=monthly_amount,
                    currency=vendor.get("currency") or "USD",
                    priority="medium",
                    is_stable=False,
                    due_day=15,  # Default
                    frequency="monthly",
                    source="quickbooks",
                    sync_status="synced",
                    last_synced_at=datetime.now(timezone.utc),
                    locked_fields=["name"],
                )
                # Set QuickBooks fields if available
                if hasattr(new_bucket, 'quickbooks_vendor_id'):
                    new_bucket.quickbooks_vendor_id = vendor_id

                db.add(new_bucket)
                results["records_created"]["expense_buckets"] += 1

        await db.flush()

    except Exception as e:
        results["errors"].append(f"Vendor sync error: {str(e)}")

    return results


# ============================================================================
# BILL SYNC
# ============================================================================

async def sync_bills(
    db: AsyncSession,
    user_id: str,
    qb_client: QuickBooksClient
) -> Dict[str, Any]:
    """
    Sync QuickBooks bills to Tamio cash events.

    Mapping:
    - Bill (balance > 0) -> CashEvent direction="out"
    - Due date -> CashEvent date
    - Balance -> CashEvent amount
    """
    results = {
        "records_fetched": {"bills": 0},
        "records_created": {"cash_events": 0},
        "errors": []
    }

    try:
        # Get outstanding bills
        bills = await qb_client.get_outstanding_bills()
        results["records_fetched"]["bills"] = len(bills)

        # Get today for week number calculation
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

        for bill in bills:
            balance = bill.get("balance", 0)
            if balance <= 0:
                continue

            # Get due date
            due_date_str = bill.get("due_date")
            if due_date_str:
                try:
                    due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    due_date = today + timedelta(days=30)
            else:
                due_date = today + timedelta(days=30)

            # Calculate week number
            days_diff = (due_date - week_start).days
            week_number = max(0, days_diff // 7)

            # Create cash event
            event = data_models.CashEvent(
                user_id=user_id,
                date=due_date,
                week_number=week_number,
                amount=Decimal(str(balance)),
                direction="out",
                event_type="expected_expense",
                category="bill",
                confidence="high",
                confidence_reason=f"QuickBooks bill {bill.get('doc_number', 'N/A')} - Vendor: {bill.get('vendor_name', 'Unknown')}",
                is_recurring=False,
                notes=f"Synced from QuickBooks Bill #{bill.get('doc_number', 'N/A')} - {bill.get('vendor_name', 'Unknown')}"
            )
            db.add(event)
            results["records_created"]["cash_events"] += 1

        await db.flush()

    except Exception as e:
        results["errors"].append(f"Bill sync error: {str(e)}")

    return results


# ============================================================================
# PAYMENT BEHAVIOR ANALYSIS
# ============================================================================

async def analyze_payment_behavior(
    db: AsyncSession,
    user_id: str,
    qb_client: QuickBooksClient
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
        aged_ar = await qb_client.get_aged_receivables()

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
