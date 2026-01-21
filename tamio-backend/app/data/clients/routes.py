"""Client API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
from datetime import date

from app.database import get_db
from app.data import models
from app.data.clients.schemas import (
    ClientCreate,
    ClientResponse,
    ClientUpdate,
    ClientWithEventsResponse,
)
from app.data.event_generator import generate_events_from_client
from app.config import settings

router = APIRouter()


async def _sync_client_to_xero(db: AsyncSession, client: models.Client, create_invoice: bool = False):
    """Background task to sync client to Xero."""
    from app.xero.sync_service import SyncService

    sync = SyncService(db, client.user_id)
    success, error = await sync.push_client_to_xero(client, create_invoice=create_invoice)
    if not success:
        print(f"Failed to sync client {client.id} to Xero: {error}")


def _should_auto_pause_client(billing_config: dict, client_type: str) -> bool:
    """
    Determine if a client should be auto-paused based on $0 billing amount.

    Clients with no revenue attached should be detected as 'paused'.
    """
    if not billing_config:
        return True

    # Check based on client type
    if client_type == "retainer":
        amount = billing_config.get("amount", 0)
        try:
            return float(amount) <= 0
        except (ValueError, TypeError):
            return True

    elif client_type == "project":
        # Check milestones total or total_value
        total_value = billing_config.get("total_value", 0)
        milestones = billing_config.get("milestones", [])

        try:
            if total_value and float(total_value) > 0:
                return False
            # Check if any milestone has an amount
            for milestone in milestones:
                if float(milestone.get("amount", 0)) > 0:
                    return False
            return True
        except (ValueError, TypeError):
            return True

    elif client_type == "usage":
        typical_amount = billing_config.get("typical_amount", 0)
        try:
            return float(typical_amount) <= 0
        except (ValueError, TypeError):
            return True

    elif client_type == "mixed":
        # Check all sub-configs
        retainer = billing_config.get("retainer", {})
        project = billing_config.get("project", {})
        usage = billing_config.get("usage", {})

        has_retainer_amount = float(retainer.get("amount", 0)) > 0 if retainer else False
        has_usage_amount = float(usage.get("typical_amount", 0)) > 0 if usage else False
        has_project_value = float(project.get("total_value", 0)) > 0 if project else False

        return not (has_retainer_amount or has_usage_amount or has_project_value)

    # Default: check for generic amount field
    amount = billing_config.get("amount", 0)
    try:
        return float(amount) <= 0
    except (ValueError, TypeError):
        return True


@router.post("/clients", response_model=ClientWithEventsResponse)
async def create_client(
    data: ClientCreate,
    db: AsyncSession = Depends(get_db),
    sync_to_xero: bool = Query(default=True, description="Sync to Xero if connected"),
    create_xero_invoice: bool = Query(default=False, description="Create repeating invoice in Xero for retainers"),
):
    """Create a client and auto-generate cash events.

    If sync_to_xero=True and user has an active Xero connection,
    the client will be pushed to Xero as a Contact.
    """
    # Verify user exists
    result = await db.execute(
        select(models.User).where(models.User.id == data.user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    # Auto-detect if client should be paused (no revenue attached)
    effective_status = data.status
    if effective_status == "active" and _should_auto_pause_client(data.billing_config, data.client_type):
        effective_status = "paused"

    # Create client
    client = models.Client(
        user_id=data.user_id,
        name=data.name,
        client_type=data.client_type,
        currency=data.currency,
        status=effective_status,
        payment_behavior=data.payment_behavior,
        churn_risk=data.churn_risk,
        scope_risk=data.scope_risk,
        billing_config=data.billing_config,
        notes=data.notes,
        source="manual",  # Created in Tamio
        sync_status="pending_push" if sync_to_xero else None,
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)

    # Generate cash events from billing config (legacy approach)
    events = await generate_events_from_client(db, client)

    # Create ObligationAgreement from client (new canonical approach)
    if settings.USE_OBLIGATION_SYSTEM:
        from app.services.obligations import ObligationService
        obligation_service = ObligationService(db)
        await obligation_service.create_obligation_from_client(client)

    # Sync to Xero if requested
    if sync_to_xero:
        await _sync_client_to_xero(db, client, create_invoice=create_xero_invoice)
        await db.refresh(client)

    return ClientWithEventsResponse(
        client=client,
        generated_events=events
    )


@router.get("/clients", response_model=List[ClientResponse])
async def get_clients(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Get all clients for a user."""
    result = await db.execute(
        select(models.Client)
        .where(
            models.Client.user_id == user_id,
            models.Client.status != "deleted"
        )
    )
    return result.scalars().all()


@router.put("/clients/{client_id}", response_model=ClientWithEventsResponse)
async def update_client(
    client_id: str,
    data: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    sync_to_xero: bool = Query(default=True, description="Sync changes to Xero if connected"),
):
    """Update a client and regenerate cash events.

    If the client is linked to Xero, changes will be synced.
    Fields in locked_fields will not be updated if source="xero".
    """
    result = await db.execute(
        select(models.Client).where(models.Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Check for locked fields (Xero-controlled)
    locked = client.locked_fields or []
    update_data = data.model_dump(exclude_unset=True)

    # If source is "xero", prevent updates to locked fields
    if client.source == "xero":
        for locked_field in locked:
            if locked_field in update_data:
                raise HTTPException(
                    status_code=400,
                    detail=f"Field '{locked_field}' is controlled by Xero. Edit in Xero instead."
                )

    # Update fields
    for field, value in update_data.items():
        setattr(client, field, value)

    # Auto-detect if client should be paused (no revenue attached)
    # Only auto-pause if status is currently "active" and billing shows $0
    effective_billing = update_data.get("billing_config", client.billing_config) or client.billing_config
    effective_type = update_data.get("client_type", client.client_type) or client.client_type
    if client.status == "active" and _should_auto_pause_client(effective_billing, effective_type):
        client.status = "paused"
    # Also auto-reactivate if a paused client gets a positive amount
    elif client.status == "paused" and not _should_auto_pause_client(effective_billing, effective_type):
        client.status = "active"

    # Mark as pending sync if has Xero connection
    if client.xero_contact_id and sync_to_xero:
        client.sync_status = "pending_push"

    await db.commit()
    await db.refresh(client)

    # Regenerate events
    # Delete future events
    await db.execute(
        delete(models.CashEvent).where(
            models.CashEvent.client_id == client_id,
            models.CashEvent.date >= date.today()
        )
    )
    await db.commit()

    # Generate new events (legacy approach)
    events = await generate_events_from_client(db, client)

    # Sync ObligationAgreement when client is updated (new canonical approach)
    if settings.USE_OBLIGATION_SYSTEM:
        from app.services.obligations import ObligationService
        obligation_service = ObligationService(db)
        await obligation_service.sync_obligation_from_client(client)

    # Sync to Xero if requested and client is linked
    if sync_to_xero and client.xero_contact_id:
        await _sync_client_to_xero(db, client)
        await db.refresh(client)

    return ClientWithEventsResponse(
        client=client,
        generated_events=events
    )


@router.delete("/clients/{client_id}")
async def delete_client(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    archive_in_xero: bool = Query(default=True, description="Archive the contact in Xero"),
):
    """Soft delete a client.

    If the client is linked to Xero, the contact will be archived (not deleted)
    to preserve transaction history.
    """
    result = await db.execute(
        select(models.Client).where(models.Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Archive in Xero if linked
    if archive_in_xero and client.xero_contact_id:
        from app.xero.sync_service import SyncService
        sync = SyncService(db, client.user_id)
        success, error = await sync.archive_client_in_xero(client)
        if not success:
            # Log but don't fail - Tamio deletion should still proceed
            print(f"Warning: Failed to archive client in Xero: {error}")

    client.status = "deleted"
    await db.commit()

    return {"message": "Client deleted successfully"}
