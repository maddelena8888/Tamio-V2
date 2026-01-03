"""
API routes for canonical obligation structure.

Endpoints for managing the 3-layer expense/obligation architecture:
- ObligationAgreement (WHY)
- ObligationSchedule (WHEN)
- PaymentEvent (REALITY)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import date, datetime, timedelta

from app.database import get_db
from app.data import models
from app.data.obligations.schemas import (
    ObligationAgreementCreate,
    ObligationAgreementUpdate,
    ObligationAgreementResponse,
    ObligationWithSchedules,
    ObligationWithPayments,
    ObligationFull,
    ObligationScheduleCreate,
    ObligationScheduleUpdate,
    ObligationScheduleResponse,
    PaymentEventCreate,
    PaymentEventUpdate,
    PaymentEventResponse,
)

router = APIRouter()


# ============================================
# ObligationAgreement Endpoints (Layer 1)
# ============================================

@router.post("/obligations", response_model=ObligationAgreementResponse, status_code=status.HTTP_201_CREATED)
async def create_obligation_agreement(
    obligation: ObligationAgreementCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new obligation agreement (Layer 1: WHY).

    This defines the structural reason for a committed cash-out.
    """
    # Create obligation agreement
    db_obligation = models.ObligationAgreement(**obligation.model_dump())

    db.add(db_obligation)
    await db.commit()
    await db.refresh(db_obligation)

    return db_obligation


@router.get("/obligations", response_model=List[ObligationAgreementResponse])
async def list_obligation_agreements(
    user_id: str,
    category: Optional[str] = None,
    obligation_type: Optional[str] = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """
    List all obligation agreements for a user.

    Filters:
    - category: Filter by expense category (payroll, rent, etc.)
    - obligation_type: Filter by type (subscription, vendor_bill, etc.)
    - active_only: Only show active obligations (end_date is null or in future)
    """
    query = select(models.ObligationAgreement).where(
        models.ObligationAgreement.user_id == user_id
    )

    if category:
        query = query.where(models.ObligationAgreement.category == category)

    if obligation_type:
        query = query.where(models.ObligationAgreement.obligation_type == obligation_type)

    if active_only:
        today = date.today()
        query = query.where(
            or_(
                models.ObligationAgreement.end_date.is_(None),
                models.ObligationAgreement.end_date >= today
            )
        )

    query = query.order_by(models.ObligationAgreement.created_at.desc())

    result = await db.execute(query)
    obligations = result.scalars().all()

    return obligations


@router.get("/obligations/{obligation_id}", response_model=ObligationFull)
async def get_obligation_agreement(
    obligation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a single obligation agreement with all schedules and payments.
    """
    query = select(models.ObligationAgreement).where(
        models.ObligationAgreement.id == obligation_id
    ).options(
        selectinload(models.ObligationAgreement.schedules),
        selectinload(models.ObligationAgreement.payment_events)
    )

    result = await db.execute(query)
    obligation = result.scalar_one_or_none()

    if not obligation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Obligation {obligation_id} not found"
        )

    return obligation


@router.patch("/obligations/{obligation_id}", response_model=ObligationAgreementResponse)
async def update_obligation_agreement(
    obligation_id: str,
    updates: ObligationAgreementUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update an existing obligation agreement.
    """
    query = select(models.ObligationAgreement).where(
        models.ObligationAgreement.id == obligation_id
    )

    result = await db.execute(query)
    obligation = result.scalar_one_or_none()

    if not obligation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Obligation {obligation_id} not found"
        )

    # Apply updates
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(obligation, field, value)

    await db.commit()
    await db.refresh(obligation)

    return obligation


@router.delete("/obligations/{obligation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_obligation_agreement(
    obligation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete an obligation agreement and all associated schedules and payments.
    """
    query = select(models.ObligationAgreement).where(
        models.ObligationAgreement.id == obligation_id
    )

    result = await db.execute(query)
    obligation = result.scalar_one_or_none()

    if not obligation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Obligation {obligation_id} not found"
        )

    await db.delete(obligation)
    await db.commit()


# ============================================
# ObligationSchedule Endpoints (Layer 2)
# ============================================

@router.post("/schedules", response_model=ObligationScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_obligation_schedule(
    schedule: ObligationScheduleCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new scheduled payment (Layer 2: WHEN).

    This defines when a payment is expected for an obligation.
    """
    # Verify obligation exists
    obligation_query = select(models.ObligationAgreement).where(
        models.ObligationAgreement.id == schedule.obligation_id
    )
    result = await db.execute(obligation_query)
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Obligation {schedule.obligation_id} not found"
        )

    # Create schedule
    db_schedule = models.ObligationSchedule(**schedule.model_dump())

    db.add(db_schedule)
    await db.commit()
    await db.refresh(db_schedule)

    return db_schedule


@router.get("/schedules", response_model=List[ObligationScheduleResponse])
async def list_obligation_schedules(
    obligation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    schedule_status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List scheduled payments.

    Filters:
    - obligation_id: Get schedules for specific obligation
    - user_id: Get all schedules for a user
    - from_date / to_date: Filter by due date range
    - schedule_status: Filter by status (scheduled, due, paid, overdue, cancelled)
    """
    query = select(models.ObligationSchedule)

    if obligation_id:
        query = query.where(models.ObligationSchedule.obligation_id == obligation_id)

    if user_id:
        # Join with ObligationAgreement to filter by user
        query = query.join(models.ObligationAgreement).where(
            models.ObligationAgreement.user_id == user_id
        )

    if from_date:
        query = query.where(models.ObligationSchedule.due_date >= from_date)

    if to_date:
        query = query.where(models.ObligationSchedule.due_date <= to_date)

    if schedule_status:
        query = query.where(models.ObligationSchedule.status == schedule_status)

    query = query.order_by(models.ObligationSchedule.due_date.asc())

    result = await db.execute(query)
    schedules = result.scalars().all()

    return schedules


@router.get("/schedules/{schedule_id}", response_model=ObligationScheduleResponse)
async def get_obligation_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a single scheduled payment.
    """
    query = select(models.ObligationSchedule).where(
        models.ObligationSchedule.id == schedule_id
    )

    result = await db.execute(query)
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )

    return schedule


@router.patch("/schedules/{schedule_id}", response_model=ObligationScheduleResponse)
async def update_obligation_schedule(
    schedule_id: str,
    updates: ObligationScheduleUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update a scheduled payment.
    """
    query = select(models.ObligationSchedule).where(
        models.ObligationSchedule.id == schedule_id
    )

    result = await db.execute(query)
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )

    # Apply updates
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(schedule, field, value)

    await db.commit()
    await db.refresh(schedule)

    return schedule


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_obligation_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a scheduled payment.
    """
    query = select(models.ObligationSchedule).where(
        models.ObligationSchedule.id == schedule_id
    )

    result = await db.execute(query)
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )

    await db.delete(schedule)
    await db.commit()


# ============================================
# PaymentEvent Endpoints (Layer 3)
# ============================================

@router.post("/payments", response_model=PaymentEventResponse, status_code=status.HTTP_201_CREATED)
async def create_payment_event(
    payment: PaymentEventCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Record an actual payment (Layer 3: REALITY).

    This represents confirmed cash-out from a bank account.

    If schedule_id is provided, will automatically mark that schedule as "paid"
    and set is_reconciled to True.
    """
    # Create payment event
    db_payment = models.PaymentEvent(**payment.model_dump())

    # If schedule_id provided, mark schedule as paid
    if payment.schedule_id:
        schedule_query = select(models.ObligationSchedule).where(
            models.ObligationSchedule.id == payment.schedule_id
        )
        result = await db.execute(schedule_query)
        schedule = result.scalar_one_or_none()

        if schedule:
            schedule.status = "paid"
            db_payment.is_reconciled = True
            db_payment.reconciled_at = datetime.utcnow()

    db.add(db_payment)
    await db.commit()
    await db.refresh(db_payment)

    return db_payment


@router.get("/payments", response_model=List[PaymentEventResponse])
async def list_payment_events(
    user_id: str,
    obligation_id: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    payment_status: Optional[str] = None,
    reconciled_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    List actual payment events.

    Filters:
    - user_id: Required - get payments for specific user
    - obligation_id: Filter by specific obligation
    - from_date / to_date: Filter by payment date range
    - payment_status: Filter by status (pending, completed, failed, reversed)
    - reconciled_only: Only show reconciled payments
    """
    query = select(models.PaymentEvent).where(
        models.PaymentEvent.user_id == user_id
    )

    if obligation_id:
        query = query.where(models.PaymentEvent.obligation_id == obligation_id)

    if from_date:
        query = query.where(models.PaymentEvent.payment_date >= from_date)

    if to_date:
        query = query.where(models.PaymentEvent.payment_date <= to_date)

    if payment_status:
        query = query.where(models.PaymentEvent.status == payment_status)

    if reconciled_only:
        query = query.where(models.PaymentEvent.is_reconciled == True)

    query = query.order_by(models.PaymentEvent.payment_date.desc())

    result = await db.execute(query)
    payments = result.scalars().all()

    return payments


@router.get("/payments/{payment_id}", response_model=PaymentEventResponse)
async def get_payment_event(
    payment_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a single payment event.
    """
    query = select(models.PaymentEvent).where(
        models.PaymentEvent.id == payment_id
    )

    result = await db.execute(query)
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment {payment_id} not found"
        )

    return payment


@router.patch("/payments/{payment_id}", response_model=PaymentEventResponse)
async def update_payment_event(
    payment_id: str,
    updates: PaymentEventUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update a payment event.
    """
    query = select(models.PaymentEvent).where(
        models.PaymentEvent.id == payment_id
    )

    result = await db.execute(query)
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment {payment_id} not found"
        )

    # Apply updates
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(payment, field, value)

    # If reconciliation status changed to True, set reconciled_at
    if updates.is_reconciled and not payment.reconciled_at:
        payment.reconciled_at = datetime.utcnow()

    await db.commit()
    await db.refresh(payment)

    return payment


@router.delete("/payments/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment_event(
    payment_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a payment event.
    """
    query = select(models.PaymentEvent).where(
        models.PaymentEvent.id == payment_id
    )

    result = await db.execute(query)
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment {payment_id} not found"
        )

    await db.delete(payment)
    await db.commit()


# ============================================
# Reconciliation Endpoints
# ============================================

@router.post("/payments/{payment_id}/reconcile/{schedule_id}", response_model=PaymentEventResponse)
async def reconcile_payment_to_schedule(
    payment_id: str,
    schedule_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Link a payment event to a scheduled payment (reconciliation).

    This connects Layer 3 (REALITY) to Layer 2 (WHEN).
    """
    # Get payment
    payment_query = select(models.PaymentEvent).where(
        models.PaymentEvent.id == payment_id
    )
    result = await db.execute(payment_query)
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment {payment_id} not found"
        )

    # Get schedule
    schedule_query = select(models.ObligationSchedule).where(
        models.ObligationSchedule.id == schedule_id
    )
    result = await db.execute(schedule_query)
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )

    # Link payment to schedule
    payment.schedule_id = schedule_id
    payment.obligation_id = schedule.obligation_id
    payment.is_reconciled = True
    payment.reconciled_at = datetime.utcnow()

    # Mark schedule as paid
    schedule.status = "paid"

    await db.commit()
    await db.refresh(payment)

    return payment


@router.get("/reconciliation/unreconciled-payments", response_model=List[PaymentEventResponse])
async def list_unreconciled_payments(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all payments that haven't been reconciled to a schedule.
    """
    query = select(models.PaymentEvent).where(
        and_(
            models.PaymentEvent.user_id == user_id,
            models.PaymentEvent.is_reconciled == False
        )
    ).order_by(models.PaymentEvent.payment_date.desc())

    result = await db.execute(query)
    payments = result.scalars().all()

    return payments


@router.get("/reconciliation/unpaid-schedules", response_model=List[ObligationScheduleResponse])
async def list_unpaid_schedules(
    user_id: str,
    overdue_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all scheduled payments that haven't been paid yet.

    Use overdue_only=true to only see overdue payments.
    """
    query = select(models.ObligationSchedule).join(
        models.ObligationAgreement
    ).where(
        and_(
            models.ObligationAgreement.user_id == user_id,
            models.ObligationSchedule.status.in_(["scheduled", "due", "overdue"])
        )
    )

    if overdue_only:
        today = date.today()
        query = query.where(
            and_(
                models.ObligationSchedule.due_date < today,
                models.ObligationSchedule.status != "paid"
            )
        )

    query = query.order_by(models.ObligationSchedule.due_date.asc())

    result = await db.execute(query)
    schedules = result.scalars().all()

    return schedules
