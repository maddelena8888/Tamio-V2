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

router = APIRouter()


async def _sync_client_to_xero(db: AsyncSession, client: models.Client, create_invoice: bool = False):
    """Background task to sync client to Xero."""
    from app.xero.sync_service import SyncService

    sync = SyncService(db, client.user_id)
    success, error = await sync.push_client_to_xero(client, create_invoice=create_invoice)
    if not success:
        print(f"Failed to sync client {client.id} to Xero: {error}")


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

    # Create client
    client = models.Client(
        user_id=data.user_id,
        name=data.name,
        client_type=data.client_type,
        currency=data.currency,
        status=data.status,
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

    # Generate cash events from billing config
    events = await generate_events_from_client(db, client)

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

    # Generate new events
    events = await generate_events_from_client(db, client)

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
