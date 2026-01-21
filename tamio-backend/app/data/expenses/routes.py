"""Expense Bucket API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
from datetime import date

from app.database import get_db
from app.data import models
from app.data.expenses.schemas import (
    ExpenseBucketCreate,
    ExpenseBucketResponse,
    ExpenseBucketUpdate,
    ExpenseBucketWithEventsResponse,
)
from app.data.event_generator import generate_events_from_bucket
from app.config import settings

router = APIRouter()


async def _sync_expense_to_xero(db: AsyncSession, expense: models.ExpenseBucket, create_bill: bool = False):
    """Background task to sync expense to Xero."""
    from app.xero.sync_service import SyncService

    sync = SyncService(db, expense.user_id)
    success, error = await sync.push_expense_to_xero(expense, create_bill=create_bill)
    if not success:
        print(f"Failed to sync expense {expense.id} to Xero: {error}")


@router.post("/expenses", response_model=ExpenseBucketWithEventsResponse)
async def create_expense_bucket(
    data: ExpenseBucketCreate,
    db: AsyncSession = Depends(get_db),
    sync_to_xero: bool = Query(default=True, description="Sync to Xero if connected"),
    create_xero_bill: bool = Query(default=False, description="Create repeating bill in Xero for fixed expenses"),
):
    """Create an expense bucket and auto-generate cash events.

    If sync_to_xero=True and user has an active Xero connection,
    the expense will be pushed to Xero as a Supplier Contact.
    """
    # Verify user exists
    result = await db.execute(
        select(models.User).where(models.User.id == data.user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    # Create bucket
    bucket = models.ExpenseBucket(
        user_id=data.user_id,
        name=data.name,
        category=data.category,
        bucket_type=data.bucket_type,
        monthly_amount=data.monthly_amount,
        currency=data.currency,
        priority=data.priority,
        is_stable=data.is_stable,
        due_day=data.due_day,
        frequency=data.frequency,
        employee_count=data.employee_count,
        notes=data.notes,
        source="manual",  # Created in Tamio
        sync_status="pending_push" if sync_to_xero else None,
    )
    db.add(bucket)
    await db.commit()
    await db.refresh(bucket)

    # Generate cash events (legacy approach)
    events = await generate_events_from_bucket(db, bucket)

    # Create ObligationAgreement from expense bucket (new canonical approach)
    if settings.USE_OBLIGATION_SYSTEM:
        from app.services.obligations import ObligationService
        obligation_service = ObligationService(db)
        await obligation_service.create_obligation_from_expense(bucket)

    # Sync to Xero if requested
    if sync_to_xero:
        await _sync_expense_to_xero(db, bucket, create_bill=create_xero_bill)
        await db.refresh(bucket)

    return ExpenseBucketWithEventsResponse(
        bucket=bucket,
        generated_events=events
    )


@router.get("/expenses", response_model=List[ExpenseBucketResponse])
async def get_expense_buckets(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Get all expense buckets for a user."""
    result = await db.execute(
        select(models.ExpenseBucket).where(models.ExpenseBucket.user_id == user_id)
    )
    return result.scalars().all()


@router.put("/expenses/{bucket_id}", response_model=ExpenseBucketWithEventsResponse)
async def update_expense_bucket(
    bucket_id: str,
    data: ExpenseBucketUpdate,
    db: AsyncSession = Depends(get_db),
    sync_to_xero: bool = Query(default=True, description="Sync changes to Xero if connected"),
):
    """Update an expense bucket and regenerate cash events.

    If the expense is linked to Xero, changes will be synced.
    Fields in locked_fields will not be updated if source="xero".
    """
    result = await db.execute(
        select(models.ExpenseBucket).where(models.ExpenseBucket.id == bucket_id)
    )
    bucket = result.scalar_one_or_none()
    if not bucket:
        raise HTTPException(status_code=404, detail="Expense bucket not found")

    # Check for locked fields (Xero-controlled)
    locked = bucket.locked_fields or []
    update_data = data.model_dump(exclude_unset=True)

    # If source is "xero", prevent updates to locked fields
    if bucket.source == "xero":
        for locked_field in locked:
            if locked_field in update_data:
                raise HTTPException(
                    status_code=400,
                    detail=f"Field '{locked_field}' is controlled by Xero. Edit in Xero instead."
                )

    # Update fields
    for field, value in update_data.items():
        setattr(bucket, field, value)

    # Mark as pending sync if has Xero connection
    if bucket.xero_contact_id and sync_to_xero:
        bucket.sync_status = "pending_push"

    await db.commit()
    await db.refresh(bucket)

    # Regenerate events
    await db.execute(
        delete(models.CashEvent).where(
            models.CashEvent.bucket_id == bucket_id,
            models.CashEvent.date >= date.today()
        )
    )
    await db.commit()

    events = await generate_events_from_bucket(db, bucket)

    # Sync ObligationAgreement when expense is updated (new canonical approach)
    if settings.USE_OBLIGATION_SYSTEM:
        from app.services.obligations import ObligationService
        obligation_service = ObligationService(db)
        await obligation_service.sync_obligation_from_expense(bucket)

    # Sync to Xero if requested and expense is linked
    if sync_to_xero and bucket.xero_contact_id:
        await _sync_expense_to_xero(db, bucket)
        await db.refresh(bucket)

    return ExpenseBucketWithEventsResponse(
        bucket=bucket,
        generated_events=events
    )


@router.delete("/expenses/{bucket_id}")
async def delete_expense_bucket(
    bucket_id: str,
    db: AsyncSession = Depends(get_db),
    archive_in_xero: bool = Query(default=True, description="Archive the supplier in Xero"),
):
    """Delete an expense bucket and its events.

    If the expense is linked to Xero, the supplier contact will be archived
    (not deleted) to preserve transaction history.
    """
    result = await db.execute(
        select(models.ExpenseBucket).where(models.ExpenseBucket.id == bucket_id)
    )
    bucket = result.scalar_one_or_none()
    if not bucket:
        raise HTTPException(status_code=404, detail="Expense bucket not found")

    # Archive in Xero if linked
    if archive_in_xero and bucket.xero_contact_id:
        from app.xero.sync_service import SyncService
        sync = SyncService(db, bucket.user_id)
        success, error = await sync.archive_expense_in_xero(bucket)
        if not success:
            # Log but don't fail - Tamio deletion should still proceed
            print(f"Warning: Failed to archive expense in Xero: {error}")

    await db.delete(bucket)
    await db.commit()

    return {"message": "Expense bucket deleted successfully"}
