"""Xero data sync service.

This module handles syncing data from Xero to Tamio's data models,
mapping invoices to clients/cash events, contacts to clients, etc.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.xero.client import XeroClient, get_valid_connection
from app.xero.models import XeroConnection, XeroSyncLog
from app.data import models as data_models


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
                    if terms <= 30:
                        payment_behavior = "on_time"
                    else:
                        payment_behavior = "delayed"

                new_client = data_models.Client(
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
    Sync Xero invoices to Tamio cash events.

    Mapping:
    - ACCREC (Accounts Receivable) → CashEvent direction="in"
    - ACCPAY (Accounts Payable) → CashEvent direction="out"
    - Due date → CashEvent date
    - Amount due → CashEvent amount
    """
    results = {
        "records_fetched": {"invoices": 0},
        "records_created": {"cash_events": 0},
        "records_updated": {"cash_events": 0},
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
        clients_by_name = {c.name.lower(): c for c in clients_result.scalars().all()}

        # Get today for week number calculation
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

        for invoice in invoices:
            if invoice["amount_due"] <= 0:
                continue

            # Determine direction
            is_receivable = invoice["type"] == "ACCREC"
            direction = "in" if is_receivable else "out"

            # Get due date
            due_date = invoice.get("due_date")
            if due_date and isinstance(due_date, datetime):
                due_date = due_date.date()
            elif not due_date:
                # Default to 30 days from invoice date
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

            # Create cash event
            event = data_models.CashEvent(
                user_id=user_id,
                date=due_date,
                week_number=week_number,
                amount=Decimal(str(invoice["amount_due"])),
                direction=direction,
                event_type="expected_revenue" if is_receivable else "expected_expense",
                category="client_invoice" if is_receivable else "vendor_bill",
                client_id=client_id,
                confidence=confidence,
                confidence_reason=f"Xero invoice {invoice.get('invoice_number', 'N/A')} - Status: {status}",
                is_recurring=False,
                notes=f"Synced from Xero Invoice #{invoice.get('invoice_number', 'N/A')}"
            )
            db.add(event)
            results["records_created"]["cash_events"] += 1

        await db.flush()

    except Exception as e:
        results["errors"].append(f"Invoice sync error: {str(e)}")

    return results


# ============================================================================
# REPEATING INVOICE SYNC (RETAINERS)
# ============================================================================

async def sync_repeating_invoices(
    db: AsyncSession,
    user_id: str,
    xero_client: XeroClient
) -> Dict[str, Any]:
    """
    Sync Xero repeating invoices to detect retainer clients.

    Repeating invoices indicate recurring revenue, which maps to
    Tamio's "retainer" client type.
    """
    results = {
        "records_fetched": {"repeating_invoices": 0},
        "records_updated": {"clients": 0},
        "errors": []
    }

    try:
        # Get repeating invoices
        repeating = xero_client.get_repeating_invoices()
        results["records_fetched"]["repeating_invoices"] = len(repeating)

        # Get existing clients
        clients_result = await db.execute(
            select(data_models.Client).where(
                data_models.Client.user_id == user_id
            )
        )
        clients_by_name = {c.name.lower(): c for c in clients_result.scalars().all()}

        for inv in repeating:
            if inv["type"] != "ACCREC":  # Only process receivables
                continue

            contact_name = inv.get("contact_name", "").lower()
            if contact_name in clients_by_name:
                client = clients_by_name[contact_name]

                # Update to retainer type
                client.client_type = "retainer"

                # Update billing config with Xero schedule
                schedule = inv.get("schedule", {})
                billing_config = client.billing_config or {}
                billing_config.update({
                    "source": "xero_sync",
                    "xero_repeating_id": inv.get("repeating_invoice_id"),
                    "amount": inv.get("total", 0),
                    "frequency": map_xero_frequency(schedule.get("unit"), schedule.get("period")),
                })
                client.billing_config = billing_config

                results["records_updated"]["clients"] += 1

        await db.flush()

    except Exception as e:
        results["errors"].append(f"Repeating invoice sync error: {str(e)}")

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
