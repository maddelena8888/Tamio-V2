"""Expense Bucket API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, TYPE_CHECKING
from datetime import date

from app.database import get_db
from app.data import models
from app.data.expenses.schemas import (
    ExpenseBucketCreate,
    ExpenseBucketResponse,
    ExpenseBucketUpdate,
    ExpenseBucketWithEventsResponse,
)
from app.auth.dependencies import get_current_user

if TYPE_CHECKING:
    from app.services.obligations import ObligationService

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
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_to_xero: bool = Query(default=True, description="Sync to Xero if connected"),
    create_xero_bill: bool = Query(default=False, description="Create repeating bill in Xero for fixed expenses"),
):
    """Create an expense bucket and auto-generate cash events.

    If sync_to_xero=True and user has an active Xero connection,
    the expense will be pushed to Xero as a Supplier Contact.
    """
    # Create bucket - use authenticated user's ID
    bucket = models.ExpenseBucket(
        user_id=current_user.id,
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

    # Create ObligationAgreement and schedules from expense bucket
    from app.services.obligations import ObligationService
    obligation_svc = ObligationService(db)
    await obligation_svc.create_obligation_from_expense(bucket)

    # Sync to Xero if requested
    if sync_to_xero:
        await _sync_expense_to_xero(db, bucket, create_bill=create_xero_bill)
        await db.refresh(bucket)

    return ExpenseBucketWithEventsResponse(
        bucket=bucket,
        generated_events=[]  # Events are now computed on-the-fly from obligations
    )


@router.get("/expenses", response_model=List[ExpenseBucketResponse])
async def get_expense_buckets(
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all expense buckets for the authenticated user."""
    result = await db.execute(
        select(models.ExpenseBucket).where(models.ExpenseBucket.user_id == current_user.id)
    )
    return result.scalars().all()


@router.put("/expenses/{bucket_id}", response_model=ExpenseBucketWithEventsResponse)
async def update_expense_bucket(
    bucket_id: str,
    data: ExpenseBucketUpdate,
    current_user: models.User = Depends(get_current_user),
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

    # Verify ownership - user can only update their own expenses
    if bucket.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this expense")

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

    # Sync ObligationAgreement when expense is updated
    from app.services.obligations import ObligationService
    obligation_svc = ObligationService(db)
    await obligation_svc.sync_obligation_from_expense(bucket)

    # Sync to Xero if requested and expense is linked
    if sync_to_xero and bucket.xero_contact_id:
        await _sync_expense_to_xero(db, bucket)
        await db.refresh(bucket)

    return ExpenseBucketWithEventsResponse(
        bucket=bucket,
        generated_events=[]  # Events are now computed on-the-fly from obligations
    )


@router.delete("/expenses/{bucket_id}")
async def delete_expense_bucket(
    bucket_id: str,
    current_user: models.User = Depends(get_current_user),
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

    # Verify ownership - user can only delete their own expenses
    if bucket.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this expense")

    # Archive in Xero if linked
    if archive_in_xero and bucket.xero_contact_id:
        from app.xero.sync_service import SyncService
        sync = SyncService(db, bucket.user_id)
        success, error = await sync.archive_expense_in_xero(bucket)
        if not success:
            # Log but don't fail - Tamio deletion should still proceed
            print(f"Warning: Failed to archive expense in Xero: {error}")

    # Clean up related obligations
    from app.services.obligations import ObligationService
    obligation_svc = ObligationService(db)
    await obligation_svc.delete_obligations_for_expense(bucket_id)

    await db.delete(bucket)
    await db.commit()

    return {"message": "Expense bucket deleted successfully"}
